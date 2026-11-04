// SPDX-License-Identifier: MIT
#include "player_network.h"
#include "player_network_protocol.h"
#include "player_network_scan.h"
#include "player_network_handoff.h"
#include "cJSON.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

enum { CONFIG_BYTES=136, NETWORK_PRIORITY=3, REPLY_TIMEOUT_MS=60000 };
typedef player_network_handoff request_slot;
typedef struct {int fd;uint8_t buffer[512];size_t start,end;} reader;

static SemaphoreHandle_t mutex;
static TaskHandle_t worker;
static request_slot *request;
static char *wire;
static esp_netif_t *station;
static esp_event_handler_instance_t wifi_handler,ip_handler;
static bool initialized,driver_initialized,station_started,configured,connected,scanning;
static uint8_t credentials[CONFIG_BYTES];
static uint32_t credential_epoch,session_counter;
static int client_fd=-1;
static int64_t retry_at;
static unsigned retry_delay_ms=1000;
static uint32_t ip_v4;
static unsigned disconnect_reason;
static bool retry_notice;
static char device_id[13],last_error[96];
/* sys_evt owns only this scalar mailbox. It never enters the socket/JSON/
 * newlib/state-mutex paths, which can require much more event-task stack. */
static portMUX_TYPE event_mux=portMUX_INITIALIZER_UNLOCKED;
static struct {
    bool station_changed,station_running,link_changed,link_up;
    uint32_t ip;
    unsigned reason;
} wifi_events;

static void lock(void){xSemaphoreTake(mutex,portMAX_DELAY);}
static void unlock(void){xSemaphoreGive(mutex);}
static void wipe(void *data,size_t count){volatile uint8_t *p=data;while(count--)*p++=0;}
static bool failure(char *error,size_t capacity,const char *text)
{
    if(error&&capacity)snprintf(error,capacity,"%s",text);
    return false;
}
static void status_error(const char *text)
{
    lock();snprintf(last_error,sizeof(last_error),"%s",text);retry_notice=false;unlock();
}
static bool valid_credentials(const uint8_t *ssid,size_t ns,const uint8_t *password,size_t np)
{
    if(!ssid||ns<1||ns>32||np>64||(np&&!password))return false;
    for(size_t i=0;i<ns;++i)if(!ssid[i])return false;
    for(size_t i=0;i<np;++i)if(!password[i])return false;
    if(np>0&&np<8)return false;
    if(np==64)for(size_t i=0;i<np;++i){uint8_t c=password[i];
        if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F')))return false;}
    return true;
}
static bool config_valid(const uint8_t raw[CONFIG_BYTES])
{
    return !memcmp(raw,"RWF1",4)&&raw[4]==1&&raw[7]==0&&
           valid_credentials(raw+8,raw[5],raw+40,raw[6]);
}

/* This is the only credential persistence. All driver operations use RAM. */
static bool persist(const uint8_t *next,char *error,size_t capacity)
{
    nvs_handle_t handle;
    if(nvs_open("rnbo_wifi",NVS_READWRITE,&handle)!=ESP_OK)
        return failure(error,capacity,"Could not open Wi-Fi settings");
    uint8_t previous[CONFIG_BYTES];size_t length=sizeof(previous);
    bool had_previous=nvs_get_blob(handle,"config",previous,&length)==ESP_OK&&length==sizeof(previous);
    esp_err_t result=next?nvs_set_blob(handle,"config",next,CONFIG_BYTES):nvs_erase_key(handle,"config");
    if(result==ESP_ERR_NVS_NOT_FOUND&&!next)result=ESP_OK;
    if(result==ESP_OK)result=nvs_commit(handle);
    if(result!=ESP_OK){
        esp_err_t restore=had_previous?nvs_set_blob(handle,"config",previous,sizeof(previous)):nvs_erase_key(handle,"config");
        if(restore==ESP_OK||restore==ESP_ERR_NVS_NOT_FOUND)(void)nvs_commit(handle);
    }
    wipe(previous,sizeof(previous));nvs_close(handle);
    return result==ESP_OK?true:failure(error,capacity,"Could not save Wi-Fi settings");
}
static void abandon_locked(void)
{
    player_handoff_abandon(request);
    if(client_fd>=0)(void)shutdown(client_fd,SHUT_RDWR);
    if(worker)xTaskNotifyGive(worker);
}
static void wifi_event(void *argument,esp_event_base_t base,int32_t id,void *data)
{
    (void)argument;portENTER_CRITICAL(&event_mux);
    if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_START){
        wifi_events.station_changed=true;wifi_events.station_running=true;
    }else if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_STOP){
        wifi_events.station_changed=true;wifi_events.station_running=false;
        wifi_events.link_changed=true;wifi_events.link_up=false;wifi_events.reason=0;
    }else if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_DISCONNECTED){
        const wifi_event_sta_disconnected_t *event=data;
        wifi_events.link_changed=true;wifi_events.link_up=false;
        wifi_events.reason=event?(unsigned)event->reason:0;
    }else if(base==IP_EVENT&&id==IP_EVENT_STA_GOT_IP&&data){
        const ip_event_got_ip_t *event=data;
        wifi_events.link_changed=true;wifi_events.link_up=true;
        wifi_events.ip=event->ip_info.ip.addr;wifi_events.reason=0;
    }
    portEXIT_CRITICAL(&event_mux);
}
static void drain_wifi_events(void)
{
    /* Serialize snapshot+application between worker and control callers; a
     * later snapshot must not be applied before an older one. sys_evt never
     * takes this mutex and only holds the short mailbox critical section. */
    lock();
    portENTER_CRITICAL(&event_mux);
    bool station_changed=wifi_events.station_changed,running=wifi_events.station_running;
    bool link_changed=wifi_events.link_changed,up=wifi_events.link_up;
    uint32_t ip=wifi_events.ip;unsigned reason=wifi_events.reason;
    wifi_events.station_changed=false;wifi_events.link_changed=false;
    portEXIT_CRITICAL(&event_mux);
    if(!station_changed&&!link_changed){unlock();return;}
    if(station_changed){station_started=running&&driver_initialized;if(station_started)retry_at=0;}
    if(link_changed){
        connected=up&&configured&&driver_initialized&&station_started;
        ip_v4=connected?ip:0;disconnect_reason=reason;
        if(connected){retry_delay_ms=1000;last_error[0]=0;retry_notice=false;}
        else{
            abandon_locked();retry_notice=configured;
            if(configured){
                retry_at=esp_timer_get_time()+(int64_t)retry_delay_ms*1000;
                if(retry_delay_ms<30000)retry_delay_ms=retry_delay_ms>15000?30000:retry_delay_ms*2;
            }
        }
    }
    unlock();
}

static bool live(uint32_t epoch)
{
    drain_wifi_events();
    lock();bool ok=configured&&connected&&credential_epoch==epoch;unlock();return ok;
}
static bool receive_line(reader *input,char *out,size_t capacity,unsigned timeout_ms,uint32_t epoch)
{
    size_t used=0;int64_t deadline=esp_timer_get_time()+(int64_t)timeout_ms*1000;
    while(live(epoch)){
        if(input->start==input->end){
            int64_t left=deadline-esp_timer_get_time();if(left<=0)return false;
            if(left>200000)left=200000;
            struct timeval timeout={.tv_sec=(long)(left/1000000),.tv_usec=(long)(left%1000000)};
            fd_set set;FD_ZERO(&set);FD_SET(input->fd,&set);
            int ready=select(input->fd+1,&set,NULL,NULL,&timeout);
            if(ready<0&&errno==EINTR)continue;
            if(ready<0)return false;
            if(ready==0)continue;
            ssize_t count=recv(input->fd,input->buffer,sizeof(input->buffer),0);
            if(count<=0)return false;
            input->start=0;input->end=(size_t)count;
        }
        unsigned char c=input->buffer[input->start++];
        if(c=='\n'){out[used]=0;return used>0;}
        if(!c||c>127||used+1>=capacity)return false;
        out[used++]=(char)c;
    }
    return false;
}
static bool send_all(int fd,const char *text)
{
    size_t length=strlen(text),sent=0;
    int64_t deadline=esp_timer_get_time()+INT64_C(5000000);
    while(sent<length){
        if(esp_timer_get_time()>=deadline)return false;
        ssize_t n=send(fd,text+sent,length-sent,0);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)return false;
        sent+=(size_t)n;
    }
    return true;
}
static void nonce_hex(char out[65])
{
    static const char digits[]="0123456789abcdef";uint8_t random[32];esp_fill_random(random,sizeof(random));
    for(unsigned i=0;i<32;++i){out[2*i]=digits[random[i]>>4];out[2*i+1]=digits[random[i]&15];}
    out[64]=0;wipe(random,sizeof(random));
}
static bool wait_reply(uint32_t session,uint32_t epoch)
{
    int64_t deadline=esp_timer_get_time()+(int64_t)REPLY_TIMEOUT_MS*1000;
    for(;;){
        drain_wifi_events();
        lock();
        bool valid=request->pending&&request->session==session&&!request->abandoned;
        bool answered=valid&&request->answered;
        unlock();
        if(answered)return true;
        if(!valid||!live(epoch)||esp_timer_get_time()>=deadline){
            lock();
            if(request->session==session)player_handoff_abandon(request);
            unlock();return false;
        }
        (void)ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(200));
    }
}
static void serve(int fd,uint32_t epoch,const uint8_t key[32])
{
    char server_nonce[65],client_nonce[65];nonce_hex(server_nonce);
    snprintf(wire,PLAYER_WIFI_RESPONSE_WIRE_BYTES,"{\"protocol\":\"rnbo-wifi-v1\",\"nonce\":\"%s\",\"device_id\":\"%s\"}\n",server_nonce,device_id);
    reader input={.fd=fd};
    if(!send_all(fd,wire)||!receive_line(&input,wire,512,5000,epoch)||
       !player_wifi_authenticate(key,server_nonce,wire,strlen(wire),client_nonce))return;
    if(!send_all(fd,"{\"authenticated\":true}\n"))return;
    lock();uint32_t session=++session_counter;if(!session)session=++session_counter;unlock();
    for(uint64_t sequence=1;sequence<=PLAYER_WIFI_MAX_SEQUENCE;++sequence){
        if(!receive_line(&input,wire,PLAYER_WIFI_REQUEST_WIRE_BYTES,30000,epoch))break;
        lock();bool available=!request->pending;unlock();if(!available)break;
        /* Control cannot observe the command until MAC verification finishes. */
        if(!player_wifi_request(key,server_nonce,client_nonce,sequence,wire,strlen(wire),request->command,sizeof(request->command)))break;
        (void)ulTaskNotifyTake(pdTRUE,0);
        lock();
        if(!configured||credential_epoch!=epoch||request->pending){unlock();break;}
        if(!player_handoff_publish(request,session)){unlock();break;}
        unlock();
        if(!wait_reply(session,epoch))break;
        /* Root has completed its one reply and no longer writes this slot. */
        bool encoded=player_wifi_response(key,server_nonce,client_nonce,sequence,request->response,wire,PLAYER_WIFI_RESPONSE_WIRE_BYTES);
        lock();request->pending=false;request->answered=false;unlock();
        if(!encoded||!live(epoch)||!send_all(fd,wire))break;
    }
    wipe(client_nonce,sizeof(client_nonce));
}

static void network_worker(void *argument)
{
    (void)argument;
    for(;;){
        drain_wifi_events();
        lock();bool run=configured&&driver_initialized&&station_started&&!scanning;bool online=connected;
        bool retry=run&&!online&&esp_timer_get_time()>=retry_at;
        if(retry)retry_at=esp_timer_get_time()+INT64_C(15000000);
        unlock();
        if(retry&&esp_wifi_connect()!=ESP_OK)status_error("Wi-Fi connection attempt failed; retrying");
        if(!online){vTaskDelay(pdMS_TO_TICKS(250));continue;}
        int listener=socket(AF_INET,SOCK_STREAM,IPPROTO_IP);
        if(listener<0){status_error("Could not create Wi-Fi command socket");vTaskDelay(pdMS_TO_TICKS(1000));continue;}
        int yes=1;(void)setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
        struct sockaddr_in address={.sin_family=AF_INET,.sin_port=htons(PLAYER_NETWORK_PORT),.sin_addr.s_addr=htonl(INADDR_ANY)};
        if(bind(listener,(struct sockaddr *)&address,sizeof(address))||listen(listener,1)){
            close(listener);status_error("Could not listen for Wi-Fi commands");vTaskDelay(pdMS_TO_TICKS(1000));continue;
        }
        for(;;){
            drain_wifi_events();
            lock();online=configured&&connected;unlock();if(!online)break;
            fd_set set;FD_ZERO(&set);FD_SET(listener,&set);struct timeval timeout={.tv_sec=1};
            int ready=select(listener+1,&set,NULL,NULL,&timeout);
            if(ready<0){if(errno==EINTR)continue;break;}if(!ready)continue;
            int fd=accept(listener,NULL,NULL);if(fd<0)continue;
            struct timeval io_timeout={.tv_sec=5};(void)setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&io_timeout,sizeof(io_timeout));
            lock();client_fd=fd;uint32_t epoch=credential_epoch;uint8_t key[32];memcpy(key,credentials+104,32);unlock();
            serve(fd,epoch,key);wipe(key,sizeof(key));
            lock();client_fd=-1;
            player_handoff_abandon(request);
            unlock();shutdown(fd,SHUT_RDWR);close(fd);
        }
        close(listener);
    }
}

static esp_err_t ensure_driver(void)
{
    if(driver_initialized)return ESP_OK;
    if(!request){
        request=heap_caps_calloc(1,sizeof(*request),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        wire=heap_caps_malloc(PLAYER_WIFI_RESPONSE_WIRE_BYTES,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!request||!wire){heap_caps_free(request);heap_caps_free(wire);request=NULL;wire=NULL;return ESP_ERR_NO_MEM;}
    }
    esp_err_t status=esp_netif_init();if(status!=ESP_OK&&status!=ESP_ERR_INVALID_STATE)return status;
    status=esp_event_loop_create_default();if(status!=ESP_OK&&status!=ESP_ERR_INVALID_STATE)return status;
    if(!station)station=esp_netif_create_default_wifi_sta();
    if(!station)return ESP_ERR_NO_MEM;
    if(!wifi_handler){
        status=esp_event_handler_instance_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL,&wifi_handler);
        if(status!=ESP_OK)return status;
    }
    if(!ip_handler){
        status=esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,NULL,&ip_handler);
        if(status!=ESP_OK)return status;
    }
    wifi_init_config_t config=WIFI_INIT_CONFIG_DEFAULT();config.nvs_enable=0;config.wifi_task_core_id=0;
    esp_log_level_set("wifi",ESP_LOG_WARN);esp_log_level_set("wifi_init",ESP_LOG_WARN);
    status=esp_wifi_init(&config);if(status!=ESP_OK)return status;
    status=esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if(status==ESP_OK)status=esp_wifi_set_mode(WIFI_MODE_STA);
    if(status!=ESP_OK){esp_wifi_deinit();return status;}
    lock();driver_initialized=true;unlock();
    if(!worker&&xTaskCreatePinnedToCore(network_worker,"player_net",6144,NULL,NETWORK_PRIORITY,&worker,0)!=pdPASS){
        lock();driver_initialized=false;unlock();esp_wifi_deinit();return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
static esp_err_t apply_credentials(void)
{
    esp_err_t result=ensure_driver();if(result!=ESP_OK)return result;
    wifi_config_t config={0};
    lock();memcpy(config.sta.ssid,credentials+8,credentials[5]);memcpy(config.sta.password,credentials+40,credentials[6]);
    retry_delay_ms=1000;retry_at=esp_timer_get_time();unlock();
    config.sta.pmf_cfg.capable=true;config.sta.pmf_cfg.required=false;
    (void)esp_wifi_disconnect();
    result=esp_wifi_set_config(WIFI_IF_STA,&config);wipe(&config,sizeof(config));
    if(result!=ESP_OK)return result;
    result=esp_wifi_start();
    return result;
}

esp_err_t player_network_init(void)
{
    if(initialized)return ESP_OK;
    if(!mutex)mutex=xSemaphoreCreateMutex();
    if(!mutex)return ESP_ERR_NO_MEM;
    uint8_t mac[6];esp_err_t result=esp_read_mac(mac,ESP_MAC_WIFI_STA);
    if(result!=ESP_OK)return result;
    snprintf(device_id,sizeof(device_id),"%02x%02x%02x%02x%02x%02x",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
    result=nvs_flash_init();if(result!=ESP_OK)return result;
    initialized=true;
    nvs_handle_t handle;result=nvs_open("rnbo_wifi",NVS_READONLY,&handle);
    if(result==ESP_ERR_NVS_NOT_FOUND)return ESP_OK;
    if(result!=ESP_OK){status_error("Could not read saved Wi-Fi settings");return result;}
    uint8_t raw[CONFIG_BYTES];size_t length=sizeof(raw);
    result=nvs_get_blob(handle,"config",raw,&length);nvs_close(handle);
    if(result==ESP_ERR_NVS_NOT_FOUND)return ESP_OK;
    if(result!=ESP_OK||length!=sizeof(raw)||!config_valid(raw)){
        wipe(raw,sizeof(raw));status_error("Saved Wi-Fi settings are invalid; provision over USB");return ESP_OK;
    }
    lock();memcpy(credentials,raw,sizeof(raw));configured=true;++credential_epoch;unlock();wipe(raw,sizeof(raw));
    return ESP_OK;
}
bool player_network_start_saved(char *error,size_t capacity)
{
    if(error&&capacity)error[0]=0;
    if(!initialized)return failure(error,capacity,"Network is not initialized");
    lock();bool start=configured&&!driver_initialized;unlock();
    if(!start)return true;
    if(apply_credentials()!=ESP_OK){
        status_error("Could not start configured Wi-Fi");
        return failure(error,capacity,"Could not start configured Wi-Fi");
    }
    return true;
}
bool player_network_configure(const uint8_t *ssid,size_t ns,const uint8_t *password,size_t np,
                              const uint8_t key[32],char *error,size_t capacity)
{
    if(error&&capacity)error[0]=0;
    if(!initialized||!key||!valid_credentials(ssid,ns,password,np))
        return failure(error,capacity,"Invalid Wi-Fi credentials or network is not initialized");
    uint8_t raw[CONFIG_BYTES]={0};memcpy(raw,"RWF1",4);raw[4]=1;raw[5]=(uint8_t)ns;raw[6]=(uint8_t)np;
    memcpy(raw+8,ssid,ns);if(np)memcpy(raw+40,password,np);memcpy(raw+104,key,32);
    if(!persist(raw,error,capacity)){wipe(raw,sizeof(raw));return false;}
    lock();abandon_locked();memcpy(credentials,raw,sizeof(raw));++credential_epoch;
    configured=true;connected=false;ip_v4=0;last_error[0]=0;retry_notice=false;unlock();wipe(raw,sizeof(raw));
    if(apply_credentials()!=ESP_OK){status_error("Wi-Fi settings saved, but Wi-Fi could not start");return failure(error,capacity,"Wi-Fi settings saved, but Wi-Fi could not start");}
    return true;
}
bool player_network_forget(char *error,size_t capacity)
{
    if(error&&capacity)error[0]=0;
    if(!initialized)return failure(error,capacity,"Network is not initialized");
    if(!persist(NULL,error,capacity))return false;
    lock();configured=false;connected=false;station_started=false;++credential_epoch;
    ip_v4=0;last_error[0]=0;retry_notice=false;wipe(credentials,sizeof(credentials));abandon_locked();
    bool stop=driver_initialized;driver_initialized=false;unlock();
    if(stop){(void)esp_wifi_disconnect();(void)esp_wifi_stop();(void)esp_wifi_deinit();}
    return true;
}
bool player_network_scan(cJSON *parent,char *error,size_t capacity)
{
    if(error&&capacity)error[0]=0;
    if(!initialized||!cJSON_IsObject(parent))return failure(error,capacity,"Network scan is not initialized");
    drain_wifi_events();
    lock();
    if(scanning){unlock();return failure(error,capacity,"A network scan is already running");}
    scanning=true;bool temporary=!configured;bool started=station_started;unlock();
    esp_err_t status=ensure_driver();
    if(status==ESP_OK&&!started)status=esp_wifi_start();
    wifi_ap_record_t *records=NULL;
    if(status==ESP_OK){
        wifi_scan_config_t config={.show_hidden=false,.scan_type=WIFI_SCAN_TYPE_ACTIVE,
            .scan_time={.active={.min=0,.max=100},.passive=100},.home_chan_dwell_time=30};
        status=esp_wifi_scan_start(&config,true);
    }
    if(status==ESP_OK){
        records=heap_caps_calloc(PLAYER_WIFI_SCAN_MAX,sizeof(*records),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!records)status=ESP_ERR_NO_MEM;
    }
    bool ok=false;
    if(status==ESP_OK){
        uint16_t count=PLAYER_WIFI_SCAN_MAX;
        status=esp_wifi_scan_get_ap_records(&count,records);
        if(status==ESP_OK)ok=player_wifi_scan_results(parent,records,count);
    }
    /* get_ap_records frees the driver's AP list; clear also covers failures. */
    (void)esp_wifi_clear_ap_list();heap_caps_free(records);
    if(temporary){
        (void)esp_wifi_stop();(void)esp_wifi_deinit();
        lock();driver_initialized=false;station_started=false;connected=false;ip_v4=0;unlock();
    }
    lock();scanning=false;if(configured&&!connected)retry_at=esp_timer_get_time()+1000000;unlock();
    return ok?true:failure(error,capacity,status==ESP_ERR_NO_MEM?"Not enough memory for network scan":"Network scan failed or Wi-Fi is busy; try again");
}
void player_network_add_status(cJSON *parent)
{
    if(!parent)return;
    bool saved=false,online=false;char ip[16]="",identity[13]="",error[96]="";
    uint32_t address=0;unsigned reason=0;bool retry=false;
    if(mutex){
        drain_wifi_events();lock();saved=configured;online=connected;address=ip_v4;
        reason=disconnect_reason;retry=retry_notice;
        memcpy(identity,device_id,sizeof(identity));memcpy(error,last_error,sizeof(error));unlock();
    }
    if(online){esp_ip4_addr_t value={.addr=address};snprintf(ip,sizeof(ip),IPSTR,IP2STR(&value));}
    if(retry&&saved&&!online)snprintf(error,sizeof(error),"Wi-Fi disconnected (reason %u); retrying",reason);
    cJSON *wifi=cJSON_AddObjectToObject(parent,"wifi");if(!wifi)return;
    cJSON_AddBoolToObject(wifi,"supported",true);cJSON_AddBoolToObject(wifi,"configured",saved);cJSON_AddBoolToObject(wifi,"connected",online);
    cJSON_AddStringToObject(wifi,"ip",ip);cJSON_AddStringToObject(wifi,"device_id",identity);cJSON_AddNumberToObject(wifi,"port",PLAYER_NETWORK_PORT);
    if(error[0])cJSON_AddStringToObject(wifi,"error",error);
}
uint32_t player_network_poll_request(char *line,size_t capacity)
{
    if(!mutex||!line||!capacity)return 0;
    lock();uint32_t session=player_handoff_poll(request,line,capacity);
    unlock();return session;
}
uint32_t player_network_current_session_id(void)
{
    if(!mutex)return 0;
    lock();uint32_t session=request&&request->pending&&request->delivered?request->session:0;unlock();return session;
}
bool player_network_respond(const char *json)
{
    if(!mutex)return false;
    lock();
    bool ok=player_handoff_reply(request,json);
    if(worker)xTaskNotifyGive(worker);
    unlock();return ok;
}
