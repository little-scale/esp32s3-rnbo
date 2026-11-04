// SPDX-License-Identifier: MIT
#include "player_network_protocol.h"
#include "cJSON.h"
#include "mbedtls/md.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void wipe(void *bytes,size_t count){volatile uint8_t *p=bytes;while(count--)*p++=0;}
static int nibble(unsigned char c)
{
    if(c>='0'&&c<='9')return c-'0';
    if(c>='a'&&c<='f')return c-'a'+10;
    return -1;
}
static bool digest_text(const char *text,uint8_t digest[32])
{
    if(!text)return false;
    for(unsigned i=0;i<64;++i){int n=nibble((unsigned char)text[i]);if(n<0)return false;
        if(i&1u)digest[i/2]|=(uint8_t)n;else digest[i/2]=(uint8_t)(n<<4);}
    return text[64]=='\0';
}
static bool nonce_valid(const char *nonce){uint8_t bytes[32];return digest_text(nonce,bytes);}
static bool hmac(const uint8_t key[32],const char *server,const char *client,const char *purpose,
                 uint64_t sequence,const char *text,uint8_t out[32])
{
    if(!key||!nonce_valid(server)||!nonce_valid(client))return false;
    char prefix[224];int count;
    if(text)count=snprintf(prefix,sizeof(prefix),"RNBO-WIFI1 %s %s %s %"PRIu64" ",purpose,server,client,sequence);
    else count=snprintf(prefix,sizeof(prefix),"RNBO-WIFI1 %s %s %s",purpose,server,client);
    if(count<0||(size_t)count>=sizeof(prefix))return false;
    mbedtls_md_context_t ctx;mbedtls_md_init(&ctx);
    const mbedtls_md_info_t *info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    bool ok=info&&mbedtls_md_setup(&ctx,info,1)==0&&mbedtls_md_hmac_starts(&ctx,key,32)==0&&
            mbedtls_md_hmac_update(&ctx,(const unsigned char *)prefix,(size_t)count)==0;
    if(ok&&text)ok=mbedtls_md_hmac_update(&ctx,(const unsigned char *)text,strlen(text))==0;
    if(ok)ok=mbedtls_md_hmac_finish(&ctx,out)==0;
    mbedtls_md_free(&ctx);return ok;
}
static bool mac_matches(const uint8_t actual[32],const char *provided)
{
    uint8_t expected[32];if(!digest_text(provided,expected))return false;
    volatile unsigned difference=0;
    for(unsigned i=0;i<32;++i)difference|=actual[i]^expected[i];
    wipe(expected,sizeof(expected));return difference==0;
}
static cJSON *packet(const char *line,size_t length)
{
    if(!line||!length||length>=PLAYER_WIFI_REQUEST_WIRE_BYTES)return NULL;
    bool string=false;unsigned depth=0;
    for(size_t i=0;i<length;++i){unsigned char c=(unsigned char)line[i];
        if(c==0||c>127)return NULL;
        if(c=='"')string=!string;
        else if(string&&c=='\\'&&i+1<length){++i;
            if(line[i]=='u'&&length-i>4&&!memcmp(line+i+1,"0000",4))return NULL;
        }else if(!string&&(c=='{'||c=='[')){if(++depth>4)return NULL;}
        else if(!string&&(c=='}'||c==']')){if(!depth)return NULL;--depth;}
        else if(!string&&(c=='.'||c=='e'||c=='E'||c=='-'||c=='+'))return NULL;
    }
    if(string||depth)return NULL;
    const char *end=NULL;cJSON *json=cJSON_ParseWithLengthOpts(line,length,&end,false);
    if(!json)return NULL;
    while(end&&end<line+length&&(*end==' '||*end=='\r'||*end=='\t'))++end;
    if(!cJSON_IsObject(json)||end!=line+length){cJSON_Delete(json);return NULL;}
    return json;
}
static bool fields(const cJSON *json,const char *a,const char *b,const char *c)
{
    unsigned seen=0;
    for(const cJSON *p=json->child;p;p=p->next){unsigned bit;
        if(!strcmp(p->string,a))bit=1;
        else if(!strcmp(p->string,b))bit=2;
        else if(c&&!strcmp(p->string,c))bit=4;
        else return false;
        if(seen&bit)return false;
        seen|=bit;
    }
    return seen==(c?7u:3u);
}
bool player_wifi_authenticate(const uint8_t key[32],const char server[65],
                              const char *line,size_t length,char client[65])
{
    if(!client)return false;
    client[0]=0;
    cJSON *json=packet(line,length);if(!json)return false;
    const cJSON *nonce=cJSON_GetObjectItemCaseSensitive(json,"client_nonce");
    const cJSON *auth=cJSON_GetObjectItemCaseSensitive(json,"auth");
    uint8_t actual[32];
    bool ok=fields(json,"client_nonce","auth",NULL)&&cJSON_IsString(nonce)&&cJSON_IsString(auth)&&
        hmac(key,server,nonce->valuestring,"AUTH",0,NULL,actual)&&mac_matches(actual,auth->valuestring);
    if(ok)memcpy(client,nonce->valuestring,65);
    wipe(actual,sizeof(actual));cJSON_Delete(json);return ok;
}
bool player_wifi_request(const uint8_t key[32],const char server[65],const char client[65],
                         uint64_t sequence,const char *line,size_t length,char *command,size_t capacity)
{
    if(!command||!capacity)return false;
    command[0]=0;
    if(!sequence||sequence>PLAYER_WIFI_MAX_SEQUENCE)return false;
    cJSON *json=packet(line,length);if(!json)return false;
    const cJSON *seq=cJSON_GetObjectItemCaseSensitive(json,"seq");
    const cJSON *cmd=cJSON_GetObjectItemCaseSensitive(json,"command");
    const cJSON *mac=cJSON_GetObjectItemCaseSensitive(json,"mac");
    bool ok=fields(json,"seq","command","mac")&&cJSON_IsNumber(seq)&&isfinite(seq->valuedouble)&&
        seq->valuedouble==(double)sequence&&cJSON_IsString(cmd)&&cJSON_IsString(mac);
    size_t count=ok?strlen(cmd->valuestring):0;
    if(!count||count>8191||count>=capacity)ok=false;
    for(size_t i=0;ok&&i<count;++i){unsigned char c=(unsigned char)cmd->valuestring[i];if(c<32||c>126)ok=false;}
    uint8_t actual[32];
    if(ok)ok=hmac(key,server,client,"REQUEST",sequence,cmd->valuestring,actual)&&mac_matches(actual,mac->valuestring);
    if(ok)memcpy(command,cmd->valuestring,count+1);
    wipe(actual,sizeof(actual));cJSON_Delete(json);return ok;
}
bool player_wifi_response(const uint8_t key[32],const char server[65],const char client[65],
                          uint64_t sequence,const char *response,char *wire,size_t capacity)
{
    if(!response||!wire||!capacity||!sequence||sequence>PLAYER_WIFI_MAX_SEQUENCE)return false;
    size_t count=strnlen(response,16385);if(!count||count>16384)return false;
    uint8_t digest[32];if(!hmac(key,server,client,"RESPONSE",sequence,response,digest))return false;
    char hex[65];static const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hex[2*i]=digits[digest[i]>>4];hex[2*i+1]=digits[digest[i]&15];}hex[64]=0;
    wipe(digest,sizeof(digest));
    int prefix=snprintf(wire,capacity,"{\"seq\":%"PRIu64",\"response\":\"",sequence);
    if(prefix<0||(size_t)prefix>=capacity)return false;
    size_t used=(size_t)prefix;
    for(size_t i=0;i<count;++i){unsigned char c=(unsigned char)response[i];char escaped[6];size_t n=1;escaped[0]=(char)c;
        if(c=='"'||c=='\\'){escaped[0]='\\';escaped[1]=(char)c;n=2;}
        else if(c<32){escaped[0]='\\';escaped[1]='u';escaped[2]='0';escaped[3]='0';escaped[4]=digits[c>>4];escaped[5]=digits[c&15];n=6;}
        if(n>=capacity-used)return false;
        memcpy(wire+used,escaped,n);used+=n;
    }
    int suffix=snprintf(wire+used,capacity-used,"\",\"mac\":\"%s\"}\n",hex);
    return suffix>=0&&(size_t)suffix<capacity-used;
}
