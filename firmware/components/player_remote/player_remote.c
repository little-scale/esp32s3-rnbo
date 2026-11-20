/* SPDX-License-Identifier: MIT */
#include "player_remote.h"
#include "cJSON.h"
#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include <errno.h>
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "player_remote_page.h"
enum { OSC_PORT=1234, WEB_PORT=80, REMOTE_QUEUE=8, POST_BYTES=2048 };
static SemaphoreHandle_t mutex;
static QueueHandle_t queue;
static TaskHandle_t worker;
static httpd_handle_t server;
static remote_route route;
static const cJSON *parameter_options[RNBO_S3_MAX_PARAMETERS];
static player_remote_read_fn read_values;
static char patch[64],identity[13],token[33];
static atomic_bool online,playing,installing,refresh;
static atomic_uint received,rejected,dropped,accepted,delivered,discarded;
static atomic_int last_error;
static atomic_int web_last_error;
static atomic_uint web_start_attempts,web_start_internal_free,web_start_internal_largest;
static atomic_uint web_stack_high_water;
static atomic_uint input_epoch;
static void lock(void){xSemaphoreTake(mutex,portMAX_DELAY);}
static void unlock(void){xSemaphoreGive(mutex);}
static bool ready(void){return atomic_load(&online)&&atomic_load(&playing)&&!atomic_load(&installing);}
static bool ensure_mutex(void){if(!mutex)mutex=xSemaphoreCreateMutex();return mutex!=NULL;}
void player_remote_bind(const remote_route *r,const char *name)
{
    if(!ensure_mutex())return;
    lock();route=r?*r:(remote_route){0};route.options=NULL;
    for(unsigned i=0;i<route.count;++i)parameter_options[i]=remote_parameter_options(&route,i);
    route.options=parameter_options;snprintf(patch,sizeof patch,"%s",name?name:"");
    if(queue)xQueueReset(queue);
    unlock();
}
void player_remote_gate(bool play,bool maintenance)
{
    bool before=atomic_load(&playing)&&!atomic_load(&installing);
    atomic_store(&installing,maintenance);atomic_store(&playing,play);
    if(before&&(!play||maintenance))atomic_fetch_add(&input_epoch,1);
}
void player_remote_network(bool connected)
{if(atomic_exchange(&online,connected)&&!connected)atomic_fetch_add(&input_epoch,1);}
void player_remote_set_reader(player_remote_read_fn reader){read_values=reader;}
bool player_remote_receive(remote_batch *batch,unsigned budget)
{
    for(unsigned i=0;queue&&budget&&i<REMOTE_QUEUE&&xQueuePeek(queue,batch,0)==pdTRUE;++i){
        if(batch->epoch==atomic_load(&input_epoch)&&batch->count>budget)return false;
        if(xQueueReceive(queue,batch,0)!=pdTRUE)return false;
        if(batch->epoch==atomic_load(&input_epoch))return true;
        atomic_fetch_add(&discarded,batch->count);
    }
    return false;
}
void player_remote_delivered(unsigned count,bool stale)
{atomic_fetch_add(stale?&discarded:&delivered,count);}
bool player_remote_refresh_requested(void){return atomic_exchange(&refresh,false);}
static bool enqueue(remote_batch *batch)
{
    batch->epoch=atomic_load(&input_epoch);
    if(!ready()||!queue||xQueueSend(queue,batch,0)!=pdTRUE){atomic_fetch_add(&dropped,batch->count);return false;}
    atomic_fetch_add(&accepted,batch->count);return true;
}
static void udp_task(void *unused)
{
    (void)unused;uint8_t bytes[REMOTE_OSC_BYTES+1];remote_batch batch;
    for(;;){
        if(!atomic_load(&online)){vTaskDelay(pdMS_TO_TICKS(250));continue;}
        int fd=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
        if(fd<0){atomic_store(&last_error,errno);vTaskDelay(pdMS_TO_TICKS(1000));continue;}
        struct sockaddr_in addr={.sin_family=AF_INET,.sin_port=htons(OSC_PORT),.sin_addr.s_addr=htonl(INADDR_ANY)};
        struct timeval timeout={.tv_sec=0,.tv_usec=100000};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout);
        if(bind(fd,(struct sockaddr *)&addr,sizeof addr)){atomic_store(&last_error,errno);close(fd);vTaskDelay(pdMS_TO_TICKS(1000));continue;}
        unsigned burst=0;
        while(atomic_load(&online)){
            ssize_t n=recv(fd,bytes,sizeof bytes,0);
            if(n<0){if(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR){burst=0;continue;}break;}
            atomic_fetch_add(&received,1);
            lock();bool valid=remote_decode(&route,bytes,(size_t)n,&batch);
            if(valid)enqueue(&batch);else atomic_fetch_add(&rejected,1);
            unlock();
            /* Fixed service-pass bound, not a per-parameter rate limiter. */
            if(++burst==8){burst=0;vTaskDelay(1);}
        }
        close(fd);
    }
}
static esp_err_t error(httpd_req_t *req,const char *status,const char *message)
{httpd_resp_set_status(req,status);httpd_resp_set_type(req,"application/json");return httpd_resp_send(req,message,HTTPD_RESP_USE_STRLEN);}
static bool same_host(httpd_req_t *req)
{
    char host[64],expected[48];struct sockaddr_storage local={0};socklen_t n=sizeof local;
    if(httpd_req_get_hdr_value_str(req,"Host",host,sizeof host)!=ESP_OK||getsockname(httpd_req_to_sockfd(req),(struct sockaddr *)&local,&n))return false;
    /* IDF's dual-stack listener returns IPv4 clients as IPv4-mapped IPv6.
     * Reading that sockaddr as sockaddr_in mistakes flowinfo for the IP. */
    struct in_addr address;
    if(local.ss_family==AF_INET&&n>=sizeof(struct sockaddr_in))
        memcpy(&address,&((struct sockaddr_in *)&local)->sin_addr,sizeof address);
#if LWIP_IPV6
    else if(local.ss_family==AF_INET6&&n>=sizeof(struct sockaddr_in6)){
        const uint8_t *bytes=((struct sockaddr_in6 *)&local)->sin6_addr.s6_addr;
        static const uint8_t mapped[12]={0,0,0,0,0,0,0,0,0,0,255,255};
        if(memcmp(bytes,mapped,sizeof mapped))return false;
        memcpy(&address,bytes+12,sizeof address);
    }
#endif
    else return false;
    if(address.s_addr==htonl(INADDR_ANY))return false;
    char ip[INET_ADDRSTRLEN];if(!inet_ntop(AF_INET,&address,ip,sizeof ip))return false;
    snprintf(expected,sizeof expected,"%s:%u",ip,WEB_PORT);
    return !strcmp(host,ip)||!strcmp(host,expected);
}
static bool http_ready(httpd_req_t *req)
{
    atomic_store(&web_stack_high_water,uxTaskGetStackHighWaterMark(NULL));
    httpd_resp_set_hdr(req,"Cache-Control","no-store");
    httpd_resp_set_hdr(req,"X-Content-Type-Options","nosniff");
    return same_host(req)&&atomic_load(&online);
}
static esp_err_t page(httpd_req_t *req)
{
    if(!http_ready(req))return error(req,"403 Forbidden","{\"error\":\"Use the board IP on its Wi-Fi network\"}");
    httpd_resp_set_type(req,"text/html; charset=utf-8");
    httpd_resp_set_hdr(req,"Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'");
    httpd_resp_set_hdr(req,"Content-Encoding","gzip");
    httpd_resp_set_hdr(req,"Cache-Control","private, max-age=3600");
    return httpd_resp_send(req,(const char *)player_remote_page,sizeof player_remote_page);
}
static esp_err_t schema(httpd_req_t *req)
{
    if(!http_ready(req))return error(req,"403 Forbidden","{}");
    httpd_resp_set_type(req,"application/json");
    /* Serialize one small metadata row at a time. Never hold the route mutex
     * across network I/O; generation checks make concurrent replacement explicit. */
    lock();unsigned gen=route.generation,count=route.count;
    cJSON *head=cJSON_CreateObject();
    cJSON_AddNumberToObject(head,"generation",gen);cJSON_AddStringToObject(head,"device_id",identity);
    cJSON_AddStringToObject(head,"patch",patch);cJSON_AddStringToObject(head,"token",token);
    cJSON_AddNumberToObject(head,"osc_port",OSC_PORT);
    char *header=cJSON_PrintUnformatted(head);cJSON_Delete(head);unlock();
    if(!header)return error(req,"503 Service Unavailable","{}");
    size_t len=strlen(header);header[len-1]=0;
    esp_err_t e=httpd_resp_send_chunk(req,header,len-1);cJSON_free(header);
    if(e!=ESP_OK)return e;
    if((e=httpd_resp_send_chunk(req,",\"parameters\":[",HTTPD_RESP_USE_STRLEN))!=ESP_OK)return e;
    unsigned emitted=0;bool valid=true;
    for(unsigned i=0;i<count;++i){
        lock();if(route.generation!=gen){valid=false;unlock();break;}
        if(!remote_visible(&route,i)){unlock();continue;}
        const rnbo_s3_parameter_info *p=&route.parameters[i];const cJSON *options=remote_parameter_options(&route,i);
        cJSON *o=cJSON_CreateObject();
        cJSON_AddStringToObject(o,"id",p->id);cJSON_AddStringToObject(o,"name",p->name);cJSON_AddStringToObject(o,"unit",p->unit);
        cJSON_AddNumberToObject(o,"min",p->minimum);cJSON_AddNumberToObject(o,"max",p->maximum);
        cJSON_AddNumberToObject(o,"steps",p->steps);cJSON_AddNumberToObject(o,"index",i);
        const cJSON *labels=cJSON_GetObjectItemCaseSensitive(options,"enum_values"),*alias=cJSON_GetObjectItemCaseSensitive(options,"osc");
        if(labels)cJSON_AddItemToObject(o,"enum_values",cJSON_Duplicate(labels,true));
        if(alias)cJSON_AddItemToObject(o,"osc",cJSON_Duplicate(alias,true));
        char *row=cJSON_PrintUnformatted(o);cJSON_Delete(o);unlock();
        if(!row){valid=false;break;}
        if(emitted++)e=httpd_resp_send_chunk(req,",",1);
        if(e==ESP_OK)e=httpd_resp_send_chunk(req,row,HTTPD_RESP_USE_STRLEN);
        cJSON_free(row);
        if(e!=ESP_OK)return e;
    }
    lock();valid=valid&&route.generation==gen;unlock();
    if((e=httpd_resp_send_chunk(req,valid?"],\"valid\":true}":"],\"valid\":false}",HTTPD_RESP_USE_STRLEN))!=ESP_OK)return e;
    return httpd_resp_send_chunk(req,NULL,0);
}
static esp_err_t values(httpd_req_t *req)
{
    if(!http_ready(req))return error(req,"403 Forbidden","{}");
    httpd_resp_set_type(req,"application/json");
    /* At most128 scalar snapshots; no module invocation and no JSON tree. */
    char buffer[6144];size_t used=0;
    lock();
    used=(size_t)snprintf(buffer,sizeof buffer,"{\"generation\":%u,\"playing\":%s,\"maintenance\":%s,\"values\":[",route.generation,atomic_load(&playing)?"true":"false",atomic_load(&installing)?"true":"false");
    for(unsigned i=0;i<route.count;++i){
        if(!remote_visible(&route,i)){
            int bytes=snprintf(buffer+used,sizeof buffer-used,"%snull",i?",":"");
            if(bytes<0||(size_t)bytes>=sizeof buffer-used){unlock();return error(req,"503 Service Unavailable","{}");}
            used+=(size_t)bytes;continue;
        }
        float a=route.parameters[i].initial,n=0;
        if(read_values)(void)read_values(i,&a,&n);
        int bytes=snprintf(buffer+used,sizeof buffer-used,"%s[%.9g,%.9g]",i?",":"",(double)a,(double)n);
        if(bytes<0||(size_t)bytes>=sizeof buffer-used){unlock();return error(req,"503 Service Unavailable","{}");}
        used+=(size_t)bytes;
    }
    unlock();
    int bytes=snprintf(buffer+used,sizeof buffer-used,"],\"dropped\":%u,\"rejected\":%u}",atomic_load(&dropped),atomic_load(&rejected));
    if(bytes<0||(size_t)bytes>=sizeof buffer-used)return error(req,"503 Service Unavailable","{}");
    atomic_store(&refresh,true);
    return httpd_resp_send(req,buffer,used+(size_t)bytes);
}
static esp_err_t update(httpd_req_t *req)
{
    if(!http_ready(req))return error(req,"403 Forbidden","{}");
    char supplied[40];
    if(httpd_req_get_hdr_value_str(req,"X-RNBO-Control",supplied,sizeof supplied)!=ESP_OK||strcmp(supplied,token))return error(req,"403 Forbidden","{\"error\":\"Reload this page before sending controls\"}");
    if(req->content_len<1||req->content_len>POST_BYTES)return error(req,"413 Content Too Large","{}");
    char bytes[POST_BYTES+1];size_t used=0;
    while(used<req->content_len){int n=httpd_req_recv(req,bytes+used,req->content_len-used);if(n<=0)return ESP_FAIL;used+=(size_t)n;}bytes[used]=0;
    if(!remote_json_shallow(bytes,used))return error(req,"400 Bad Request","{\"error\":\"Invalid or excessively nested request\"}");
    const char *end=NULL;cJSON *body=cJSON_ParseWithLengthOpts(bytes,used+1,&end,true);
    if(!body)return error(req,"400 Bad Request","{\"error\":\"Invalid parameter request\"}");
    const cJSON *gen=cJSON_GetObjectItemCaseSensitive(body,"generation"),*updates=cJSON_GetObjectItemCaseSensitive(body,"updates");
    remote_batch batch={0};bool valid=cJSON_IsNumber(gen)&&cJSON_IsArray(updates)&&cJSON_GetArraySize(updates)>0&&cJSON_GetArraySize(updates)<=REMOTE_BATCH;
    lock();valid=valid&&gen->valuedouble==route.generation;batch.generation=route.generation;
    const cJSON *p=NULL;
    if(valid)cJSON_ArrayForEach(p,updates){
        const cJSON *id=cJSON_GetObjectItemCaseSensitive(p,"id"),*v=cJSON_GetObjectItemCaseSensitive(p,"value"),*norm=cJSON_GetObjectItemCaseSensitive(p,"normalized");
        if(!cJSON_IsString(id)||!cJSON_IsBool(norm)||(!cJSON_IsNumber(v)&&!cJSON_IsString(v))||
           !remote_parameter_update(&route,id->valuestring,cJSON_IsTrue(norm),cJSON_IsString(v)?'s':'f',cJSON_IsNumber(v)?(float)v->valuedouble:0,cJSON_IsString(v)?v->valuestring:NULL,&batch.updates[batch.count])){valid=false;break;}
        ++batch.count;
    }
    bool queued=valid&&enqueue(&batch);unlock();cJSON_Delete(body);
    httpd_resp_set_type(req,"application/json");
    if(!valid){atomic_fetch_add(&rejected,1);return error(req,"409 Conflict","{\"error\":\"Patch or parameter changed; reload controls\"}");}
    if(!queued)return error(req,"429 Too Many Requests","{\"error\":\"Player paused, busy, or control queue full\"}");
    return httpd_resp_sendstr(req,"{\"queued\":true}");
}
esp_err_t player_remote_start(const char *id)
{
    if(!ensure_mutex())return ESP_ERR_NO_MEM;
    if(!queue)queue=xQueueCreate(REMOTE_QUEUE,sizeof(remote_batch));
    if(!queue)return ESP_ERR_NO_MEM;
    if(!identity[0])snprintf(identity,sizeof identity,"%s",id);
    if(!token[0]){uint8_t random[16];esp_fill_random(random,sizeof random);for(unsigned i=0;i<16;++i)snprintf(token+2*i,3,"%02x",random[i]);}
    if(!worker&&xTaskCreatePinnedToCore(udp_task,"rnbo_osc",4096,NULL,2,&worker,0)!=pdPASS)return ESP_ERR_NO_MEM;
    if(!server){
        httpd_config_t cfg=HTTPD_DEFAULT_CONFIG();cfg.stack_size=12288;cfg.task_priority=2;cfg.core_id=0;
        cfg.max_open_sockets=2;cfg.max_uri_handlers=4;cfg.max_resp_headers=6;cfg.backlog_conn=2;
        cfg.recv_wait_timeout=1;cfg.send_wait_timeout=1;cfg.lru_purge_enable=true;
        atomic_fetch_add(&web_start_attempts,1);
        atomic_store(&web_start_internal_free,heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));
        atomic_store(&web_start_internal_largest,heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));
        esp_err_t result=httpd_start(&server,&cfg);atomic_store(&web_last_error,result);
        if(result!=ESP_OK){atomic_store(&last_error,result);return result;}
        const httpd_uri_t handlers[]={
            {.uri="/",.method=HTTP_GET,.handler=page}, {.uri="/api/schema",.method=HTTP_GET,.handler=schema},
            {.uri="/api/values",.method=HTTP_GET,.handler=values}, {.uri="/api/parameter",.method=HTTP_POST,.handler=update}};
        for(unsigned i=0;i<4;++i){result=httpd_register_uri_handler(server,&handlers[i]);if(result!=ESP_OK){httpd_stop(server);server=NULL;return result;}}
    }
    return ESP_OK;
}
void player_remote_add_status(cJSON *parent)
{
    cJSON *o=cJSON_AddObjectToObject(parent,"remote_control");if(!o)return;
    cJSON_AddNumberToObject(o,"version",1);cJSON_AddBoolToObject(o,"online",atomic_load(&online));
    cJSON_AddBoolToObject(o,"osc_started",worker!=NULL);cJSON_AddBoolToObject(o,"web_started",server!=NULL);
    cJSON_AddNumberToObject(o,"osc_port",OSC_PORT);cJSON_AddNumberToObject(o,"web_port",WEB_PORT);
    cJSON_AddNumberToObject(o,"packets",atomic_load(&received));cJSON_AddNumberToObject(o,"accepted",atomic_load(&accepted));
    cJSON_AddNumberToObject(o,"delivered",atomic_load(&delivered));cJSON_AddNumberToObject(o,"discarded",atomic_load(&discarded));
    cJSON_AddNumberToObject(o,"rejected",atomic_load(&rejected));cJSON_AddNumberToObject(o,"dropped",atomic_load(&dropped));
    cJSON_AddNumberToObject(o,"last_error",atomic_load(&last_error));
    cJSON_AddNumberToObject(o,"web_last_error",atomic_load(&web_last_error));
    cJSON_AddNumberToObject(o,"web_start_attempts",atomic_load(&web_start_attempts));
    cJSON_AddNumberToObject(o,"web_start_internal_free_bytes",atomic_load(&web_start_internal_free));
    cJSON_AddNumberToObject(o,"web_start_internal_largest_block_bytes",atomic_load(&web_start_internal_largest));
    cJSON_AddNumberToObject(o,"web_stack_high_water_bytes",atomic_load(&web_stack_high_water));
}
