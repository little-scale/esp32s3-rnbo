/* SPDX-License-Identifier: MIT */
#include "player_remote_core.h"
#include "cJSON.h"
#include <math.h>
#include <string.h>
static const cJSON *item(const cJSON *o,const char *key){return cJSON_GetObjectItemCaseSensitive(o,key);}
static bool text(const cJSON *v,size_t maximum){return cJSON_IsString(v)&&v->valuestring[0]&&strlen(v->valuestring)<=maximum;}
const cJSON *remote_parameter_options(const remote_route *r,unsigned index)
{
    if(index>=r->count)return NULL;
    if(r->options)return r->options[index];
    const cJSON *row=NULL;
    cJSON_ArrayForEach(row,item(r->plan,"parameters")){
        const cJSON *id=item(row,"parameter_id");
        if(cJSON_IsString(id)&&!strcmp(id->valuestring,r->parameters[index].id))return row;
    }
    return NULL;
}
bool remote_visible(const remote_route *r,unsigned index)
{return index<r->count&&!cJSON_IsFalse(item(remote_parameter_options(r,index),"visible"));}
static bool literal(const char *s){return s&&*s&&!strpbrk(s," \t\r\n*?,[]{}#")&&!strstr(s,"//");}
bool remote_plan_valid(const remote_route *r)
{
    if(r->count>RNBO_S3_MAX_PARAMETERS)return false;
    /* Reject ambiguous canonical names rather than accidentally directing a
     * normalized update to another parameter with that literal ID. */
    for(unsigned i=0;i<r->count;++i){
        const char *id=r->parameters[i].id;
        if(!literal(id)||*id=='/'||id[strlen(id)-1]=='/'||(strlen(id)>11&&!strcmp(id+strlen(id)-11,"/normalized")))return false;
        for(unsigned j=0;j<i;++j){
            const char *other=r->parameters[j].id;size_t a=strlen(id),b=strlen(other);
            if(!strcmp(id,other)||(a==b+11&&!memcmp(id,other,b)&&!strcmp(id+b,"/normalized"))||
               (b==a+11&&!memcmp(other,id,a)&&!strcmp(other+a,"/normalized")))return false;
        }
    }
    if(!r->plan)return true;
    if(!cJSON_IsObject(r->plan)||cJSON_GetArraySize(r->plan)!=2)return false;
    const cJSON *version=item(r->plan,"version"),*rows=item(r->plan,"parameters");
    if(!cJSON_IsNumber(version)||version->valuedouble!=1||!cJSON_IsArray(rows)||cJSON_GetArraySize(rows)>128)return false;
    const cJSON *row=NULL;
    cJSON_ArrayForEach(row,rows){
        const cJSON *id=item(row,"parameter_id");if(!cJSON_IsObject(row)||!text(id,191))return false;
        unsigned index=r->count;for(unsigned i=0;i<r->count;++i)if(!strcmp(id->valuestring,r->parameters[i].id))index=i;
        if(index==r->count)return false;
        for(const cJSON *p=rows->child;p!=row;p=p->next)if(!strcmp(item(p,"parameter_id")->valuestring,id->valuestring))return false;
        for(const cJSON *p=row->child;p;p=p->next)if(strcmp(p->string,"parameter_id")&&strcmp(p->string,"visible")&&strcmp(p->string,"enum_values")&&strcmp(p->string,"osc"))return false;
        const cJSON *visible=item(row,"visible"),*labels=item(row,"enum_values"),*osc=item(row,"osc");
        if(visible&&!cJSON_IsFalse(visible))return false;
        if(labels){
            int n=cJSON_GetArraySize(labels);const rnbo_s3_parameter_info *info=&r->parameters[index];
            if(!cJSON_IsArray(labels)||n<1||n>32||info->steps!=(unsigned)n||info->minimum!=0||info->maximum!=n-1)return false;
            for(const cJSON *p=labels->child;p;p=p->next){
                if(!text(p,63))return false;
                for(const cJSON *q=labels->child;q!=p;q=q->next)if(!strcmp(p->valuestring,q->valuestring))return false;
            }
        }
        if(osc){
            const cJSON *a=item(osc,"address"),*norm=item(osc,"normalized");
            if(!cJSON_IsObject(osc)||cJSON_GetArraySize(osc)!=2||!text(a,255)||!cJSON_IsBool(norm)||!literal(a->valuestring)||a->valuestring[0]!='/'||!strcmp(a->valuestring,"/rnbo")||!strncmp(a->valuestring,"/rnbo/",6)||a->valuestring[strlen(a->valuestring)-1]=='/')return false;
            for(const cJSON *p=rows->child;p!=row;p=p->next){
                const cJSON *other=item(item(p,"osc"),"address");
                if(cJSON_IsString(other)&&!strcmp(a->valuestring,other->valuestring))return false;
            }
        }
    }
    return true;
}
static bool value(const remote_route *r,unsigned i,bool norm,char type,float number,const char *label,remote_update *out)
{
    if(!remote_visible(r,i))return false;
    const cJSON *labels=item(remote_parameter_options(r,i),"enum_values");
    if(!norm&&labels){
        if(type!='s'||!label)return false;
        unsigned n=0;bool found=false;
        for(const cJSON *p=labels->child;p;p=p->next,++n)if(!strcmp(label,p->valuestring)){number=(float)n;found=true;break;}
        if(!found)return false;
    }else{
        if(norm?type!='f':(type!='f'&&type!='i'&&type!='T'&&type!='F'))return false;
        if(!isfinite(number))return false;
    }
    float lo=norm?0:r->parameters[i].minimum,hi=norm?1:r->parameters[i].maximum;
    *out=(remote_update){.index=i,.kind=norm?RNBO_S3_PARAMETER_NORMALIZED:RNBO_S3_PARAMETER_ACTUAL,.value=number<lo?lo:number>hi?hi:number};
    return true;
}
bool remote_parameter_update(const remote_route *r,const char *id,bool norm,char type,float number,const char *label,remote_update *out)
{
    for(unsigned i=0;i<r->count;++i)if(!strcmp(r->parameters[i].id,id))return value(r,i,norm,type,number,label,out);
    return false;
}
bool remote_resolve(const remote_route *r,const char *address,char type,float number,const char *label,remote_update *out)
{
    const char prefix[]="/rnbo/inst/0/params/";
    if(!strncmp(address,prefix,sizeof(prefix)-1)){
        const char *id=address+sizeof(prefix)-1;size_t n=strlen(id);bool norm=n>11&&!strcmp(id+n-11,"/normalized");
        if(norm)n-=11;
        for(unsigned i=0;i<r->count;++i)if(strlen(r->parameters[i].id)==n&&!memcmp(r->parameters[i].id,id,n))return value(r,i,norm,type,number,label,out);
        return false;
    }
    for(unsigned i=0;i<r->count;++i){
        const cJSON *osc=item(remote_parameter_options(r,i),"osc"),*a=item(osc,"address");
        if(cJSON_IsString(a)&&!strcmp(address,a->valuestring))return value(r,i,cJSON_IsTrue(item(osc,"normalized")),type,number,label,out);
    }
    return false;
}
static uint32_t be32(const uint8_t *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
bool remote_json_shallow(const char *bytes,size_t length)
{
    char stack[8];unsigned depth=0;bool quoted=false,escaped=false;
    for(size_t i=0;i<length;++i){
        char c=bytes[i];if(!c)return false;
        if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;continue;}
        if(c=='"')quoted=true;
        else if(c=='{'||c=='['){if(depth==sizeof stack)return false;stack[depth++]=c;}
        else if(c=='}'||c==']'){if(!depth||stack[--depth]!=(c=='}'?'{':'['))return false;}
    }
    return !quoted&&!depth;
}
static const char *string(const uint8_t *p,size_t n,size_t *used,size_t maximum)
{
    const uint8_t *end=memchr(p,0,n);if(!end)return NULL;
    size_t length=(size_t)(end-p),padded=(length+4)&~(size_t)3;
    if(length>maximum||padded>n)return NULL;
    for(size_t i=length;i<padded;++i)if(p[i])return NULL;
    *used=padded;return (const char *)p;
}
static bool decode(const remote_route *r,const uint8_t *p,size_t n,unsigned depth,remote_batch *out)
{
    if(n<4||(n&3))return false;
    if(n>=8&&!memcmp(p,"#bundle\0",8)){
        if(depth>2||n<16||be32(p+8)!=0||be32(p+12)!=1)return false;
        size_t pos=16;
        while(pos<n){if(n-pos<4)return false;size_t bytes=be32(p+pos);pos+=4;
            if(!bytes||bytes>n-pos||!decode(r,p+pos,bytes,depth+1,out))return false;
            pos+=bytes;}
        return true;
    }
    size_t a,t;const char *addr=string(p,n,&a,255);if(!addr||addr[0]!='/')return false;
    const char *tag=string(p+a,n-a,&t,2);if(!tag||tag[0]!=','||!tag[1]||tag[2])return false;
    size_t pos=a+t;float v=0;const char *label=NULL;
    switch(tag[1]){
    case 'f':case 'i':{if(n-pos!=4)return false;uint32_t bits=be32(p+pos);
        if(tag[1]=='f')memcpy(&v,&bits,4);else{int32_t integer;memcpy(&integer,&bits,4);v=(float)integer;}pos+=4;break;}
    case 'T':case 'F':v=tag[1]=='T'?1:0;break;
    case 's':{size_t bytes;label=string(p+pos,n-pos,&bytes,63);if(!label)return false;pos+=bytes;break;}
    default:return false;
    }
    if(pos!=n||out->count>=REMOTE_BATCH)return false;
    if(!remote_resolve(r,addr,tag[1],v,label,&out->updates[out->count]))return false;
    ++out->count;return true;
}
bool remote_decode(const remote_route *r,const uint8_t *p,size_t n,remote_batch *out)
{
    memset(out,0,sizeof(*out));out->generation=r->generation;
    if(!p||n>REMOTE_OSC_BYTES||!decode(r,p,n,0,out)||!out->count){out->count=0;return false;}
    return true;
}
