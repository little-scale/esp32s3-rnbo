#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "../../firmware/components/player_remote/player_remote.c"
static struct {remote_batch items[8];unsigned start,count;} fifo;
static esp_err_t start_error;
static unsigned udp_starts,http_starts;
static unsigned local_socket_mode;
size_t heap_caps_get_free_size(unsigned caps){(void)caps;return 100000;}
size_t heap_caps_get_largest_free_block(unsigned caps){(void)caps;return 50000;}
unsigned uxTaskGetStackHighWaterMark(TaskHandle_t task){(void)task;return 4096;}
SemaphoreHandle_t xSemaphoreCreateMutex(void){return (void *)1;}
int xSemaphoreTake(SemaphoreHandle_t m,unsigned n){(void)m;(void)n;return 1;}
int xSemaphoreGive(SemaphoreHandle_t m){(void)m;return 1;}
QueueHandle_t xQueueCreate(unsigned n,unsigned size){assert(n==8&&size==sizeof(remote_batch));return &fifo;}
int xQueueReset(QueueHandle_t q){(void)q;fifo.count=fifo.start=0;return 1;}
int xQueueSend(QueueHandle_t q,const void *p,unsigned t){(void)q;(void)t;if(fifo.count==8)return 0;fifo.items[(fifo.start+fifo.count++)%8]=*(const remote_batch *)p;return 1;}
int xQueueReceive(QueueHandle_t q,void *p,unsigned t){(void)q;(void)t;if(!fifo.count)return 0;*(remote_batch *)p=fifo.items[fifo.start++%8];--fifo.count;return 1;}
int xQueuePeek(QueueHandle_t q,void *p,unsigned t){(void)q;(void)t;if(!fifo.count)return 0;*(remote_batch *)p=fifo.items[fifo.start%8];return 1;}
void vTaskDelay(unsigned n){(void)n;}
int xTaskCreatePinnedToCore(void (*f)(void *),const char *n,unsigned s,void *p,unsigned pri,TaskHandle_t *h,unsigned core){(void)f;(void)n;(void)s;(void)p;(void)pri;assert(core==0);++udp_starts;*h=(void *)1;return 1;}
void esp_fill_random(void *p,size_t n){memset(p,0x5a,n);}
esp_err_t httpd_resp_set_status(httpd_req_t *r,const char *s){snprintf(r->status,sizeof r->status,"%s",s);return 0;}
esp_err_t httpd_resp_set_type(httpd_req_t *r,const char *s){(void)r;(void)s;return 0;}
esp_err_t httpd_resp_set_hdr(httpd_req_t *r,const char *k,const char *v){(void)r;(void)k;(void)v;return 0;}
esp_err_t httpd_resp_send(httpd_req_t *r,const char *p,int bytes){size_t n=bytes<0?strlen(p):(size_t)bytes;assert(n<sizeof r->response);memcpy(r->response,p,n);r->response[n]=0;r->response_len=n;return 0;}
esp_err_t httpd_resp_send_chunk(httpd_req_t *r,const char *p,int bytes){if(!p)return 0;size_t n=bytes<0?strlen(p):(size_t)bytes;assert(n+r->response_len<sizeof r->response);memcpy(r->response+r->response_len,p,n);r->response_len+=n;r->response[r->response_len]=0;return 0;}
esp_err_t httpd_resp_sendstr(httpd_req_t *r,const char *s){return httpd_resp_send(r,s,-1);}
int httpd_req_get_hdr_value_str(httpd_req_t *r,const char *key,char *out,size_t n){const char *s=!strcmp(key,"Host")?r->host:r->control;if(!s||strlen(s)>=n)return -1;strcpy(out,s);return 0;}
int httpd_req_to_sockfd(httpd_req_t *r){(void)r;return 10;}
int remote_test_getsockname(int fd,struct sockaddr *p,socklen_t *n){
    (void)fd;
    if(local_socket_mode==4)return -1;
    if(local_socket_mode){
        assert(*n>=sizeof(struct sockaddr_in6));
        struct sockaddr_in6 a={.sin6_family=AF_INET6};
        assert(inet_pton(AF_INET6,local_socket_mode==2?"::1":"::ffff:127.0.0.1",&a.sin6_addr)==1);
        memcpy(p,&a,sizeof a);*n=local_socket_mode==3?sizeof(struct sockaddr_in):sizeof a;return 0;
    }
    assert(*n>=sizeof(struct sockaddr_in));struct sockaddr_in a={.sin_family=AF_INET,.sin_addr.s_addr=htonl(0x7f000001u)};memcpy(p,&a,sizeof a);*n=sizeof a;return 0;
}
int httpd_req_recv(httpd_req_t *r,char *out,size_t n){size_t left=r->content_len-r->cursor;if(n>left)n=left;if(n>7)n=7;memcpy(out,r->input+r->cursor,n);r->cursor+=n;return (int)n;}
esp_err_t httpd_start(httpd_handle_t *h,const httpd_config_t *c){assert(c->max_open_sockets==2&&c->stack_size==12288);++http_starts;if(start_error)return start_error;*h=(void *)1;return 0;}
esp_err_t httpd_stop(httpd_handle_t h){(void)h;return 0;}
esp_err_t httpd_register_uri_handler(httpd_handle_t h,const httpd_uri_t *u){(void)h;assert(u->handler);return 0;}
static bool readback(unsigned i,float *a,float *n){*a=i?1:1200;*n=i?1:.25f;return true;}
static httpd_req_t req;
static void request_reset(const char *body){memset(&req,0,sizeof req);req.host="127.0.0.1";req.control=token;req.input=body;req.content_len=body?strlen(body):0;}
int main(void)
{
    rnbo_s3_parameter_info info[2]={{.id="cutoff",.name="Cutoff <script>",.minimum=20,.maximum=20000},{.id="mode",.name="Mode",.minimum=0,.maximum=2,.steps=3}};
    cJSON *plan=cJSON_Parse("{\"version\":1,\"parameters\":[{\"parameter_id\":\"mode\",\"enum_values\":[\"a\",\"b\",\"c\"]}]}");
    remote_route r={.parameters=info,.count=2,.generation=22,.plan=plan};
    assert(remote_plan_valid(&r));player_remote_bind(&r,"Example");player_remote_set_reader(readback);
    start_error=0xb008;
    assert(player_remote_start("1020ba0697d4")==start_error);
    assert(worker&&!server&&atomic_load(&web_last_error)==start_error);
    assert(atomic_load(&web_start_internal_free)==100000&&atomic_load(&web_start_internal_largest)==50000);
    start_error=ESP_OK;
    assert(player_remote_start("1020ba0697d4")==ESP_OK);
    assert(udp_starts==1&&http_starts==2&&atomic_load(&web_start_attempts)==2&&!atomic_load(&web_last_error));
    assert(player_remote_start("1020ba0697d4")==ESP_OK&&http_starts==2);player_remote_network(true);player_remote_gate(true,false);
    /* The real IDF listener is dual-stack even when the browser uses IPv4. */
    for(local_socket_mode=0;local_socket_mode<5;++local_socket_mode){
        request_reset(NULL);assert(same_host(&req)==(local_socket_mode<2));
        req.host="127.0.0.1:80";assert(same_host(&req)==(local_socket_mode<2));
        req.host="127.0.0.1:8080";assert(!same_host(&req));
        req.host="evil.example";assert(!same_host(&req));
    }
    local_socket_mode=1;
    request_reset(NULL);assert(schema(&req)==ESP_OK);cJSON *json=cJSON_Parse(req.response);assert(json&&cJSON_IsTrue(cJSON_GetObjectItem(json,"valid")));assert(cJSON_GetArraySize(cJSON_GetObjectItem(json,"parameters"))==2);cJSON_Delete(json);
    request_reset(NULL);assert(values(&req)==ESP_OK);json=cJSON_Parse(req.response);assert(json&&cJSON_GetArraySize(cJSON_GetObjectItem(json,"values"))==2);cJSON_Delete(json);assert(player_remote_refresh_requested());assert(!player_remote_refresh_requested());
    request_reset(NULL);req.host="evil.example";assert(page(&req)==ESP_OK);assert(!strcmp(req.status,"403 Forbidden"));
    request_reset("{\"generation\":22,\"updates\":[{\"id\":\"cutoff\",\"value\":30000,\"normalized\":false}]}");req.control=NULL;assert(update(&req)==ESP_OK);assert(!strcmp(req.status,"403 Forbidden")&&fifo.count==0);
    request_reset("{\"generation\":21,\"updates\":[{\"id\":\"cutoff\",\"value\":30000,\"normalized\":false}]}");assert(update(&req)==ESP_OK);assert(!strcmp(req.status,"409 Conflict")&&fifo.count==0);
    const char *valid="{\"generation\":22,\"updates\":[{\"id\":\"cutoff\",\"value\":30000,\"normalized\":false},{\"id\":\"mode\",\"value\":\"b\",\"normalized\":false}]}";
    request_reset(valid);assert(update(&req)==ESP_OK);assert(strstr(req.response,"queued"));remote_batch b;assert(!player_remote_receive(&b,1)&&fifo.count==1);assert(player_remote_receive(&b,8)&&b.count==2&&b.generation==22&&b.updates[0].value==20000&&b.updates[1].value==1);
    request_reset("{\"generation\":22,\"updates\":[{\"id\":\"cutoff\",\"value\":1000,\"normalized\":false},{\"id\":\"missing\",\"value\":0,\"normalized\":false}]}");update(&req);assert(fifo.count==0); /* atomic batch rejection */
    for(unsigned i=0;i<8;++i){request_reset(valid);update(&req);assert(!req.status[0]);}
    request_reset(valid);update(&req);assert(!strcmp(req.status,"429 Too Many Requests"));assert(atomic_load(&playing)&&atomic_load(&dropped)==2);
    player_remote_gate(false,false);player_remote_gate(true,false);assert(!player_remote_receive(&b,8)&&atomic_load(&discarded)==16);
    request_reset(valid);update(&req);player_remote_network(false);player_remote_network(true);assert(!player_remote_receive(&b,8));
    request_reset(valid);update(&req);r.generation=23;player_remote_bind(&r,"New");assert(!player_remote_receive(&b,8));
    request_reset(valid);update(&req);assert(!strcmp(req.status,"409 Conflict"));
    player_remote_bind(NULL,NULL);cJSON_Delete(plan);
    puts("HTTP schema/values/CSRF/host/generation/batches/overflow/pause/disconnect PASS");return 0;
}
