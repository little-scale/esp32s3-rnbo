/* SPDX-License-Identifier: MIT
 * Actual player control/audio functions; all hardware/ELF/storage boundaries fake.
 * The package parser, cJSON, SHA and PCM implementation remain real host code.
 */
#include <assert.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
static int control_printf(const char *, ...);
static int control_puts(const char *);
static int control_getchar(void);
#define printf control_printf
#define puts control_puts
#define getchar control_getchar
#include PLAYER_MAIN_SOURCE
#undef printf
#undef puts
#undef getchar

static char reply[16384];
static size_t reply_used;
static unsigned loader_calls,stage_calls,commit_calls,unloads,guard_clears;
static unsigned mode,failed_boundary,delay_calls,received_blocks;
static unsigned net_delivered,net_completed,net_responses,net_start_calls,net_getchars;
static bool network_stepping,net_pending,net_answered,net_abandoned,abandon_first,json_oom;
static uint32_t net_session;
static char net_reply[256];
static bool usb_stepping,usb_timeout;
static const char *usb_program;
static size_t usb_cursor;
static int64_t now;
static bool audio_stepping,control_stepping,dma_running;
static player_stats published;
static player_slot *old_slot,*new_slot;
static jmp_buf task_exit;
enum {ACK_NORMAL,ACK_STALE,ACK_RESUME_FAILURE,ACK_STOP_FAILURE};
enum {FAIL_NONE,FAIL_LOAD,FAIL_STAGE,FAIL_COMMIT};

static int control_printf(const char *format,...) {
    if(strstr(format,"\"upload\":\"committed\""))assert(dma_running&&!atomic_load(&maintenance)&&!atomic_load(&parked));
    va_list args;va_start(args,format);
    int n=vsnprintf(reply+reply_used,sizeof reply-reply_used,format,args);va_end(args);
    assert(n>=0 && (size_t)n<sizeof reply-reply_used);reply_used+=(size_t)n;return n;
}
static int control_puts(const char *text) {return control_printf("%s\n",text);}
static void clear_reply(void){reply_used=0;reply[0]=0;}
static cJSON *last_reply(void) {
    cJSON *o=cJSON_Parse(reply);assert(o);return o;
}
static void assert_reply_error(bool retained) {
    cJSON *o=last_reply();assert(cJSON_IsString(cJSON_GetObjectItemCaseSensitive(o,"error")));
    assert(cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(o,"old_retained"))==retained);cJSON_Delete(o);
}
static void must_park(void) {
    unsigned request=atomic_load(&maintenance_epoch);
    assert((request&1u) && atomic_load(&maintenance) && atomic_load(&parked));
    assert(atomic_load(&acknowledged_epoch)==request);
}
void *heap_caps_malloc(size_t n,unsigned cap){(void)cap;return malloc(n);}
void *heap_caps_calloc(size_t n,size_t bytes,unsigned cap){(void)cap;return calloc(n,bytes);}
void heap_caps_free(void *p){free(p);}
size_t heap_caps_get_free_size(unsigned caps){(void)caps;return 1000000;}
void allocation_watch_start(unsigned phase){(void)phase;}
void allocation_watch_stop(void){}
allocation_watch_stats allocation_watch_snapshot(unsigned phase){(void)phase;return (allocation_watch_stats){0};}
int64_t esp_timer_get_time(void){unsigned request=atomic_load(&maintenance_epoch);bool preparing=(request&1u)&&atomic_load(&acknowledged_epoch)==request;now+=audio_stepping||preparing?1:100000;return now;}
static void fake_ack(void) {
    unsigned request=atomic_load(&maintenance_epoch);
    if(mode==ACK_STALE)return;
    if(request&1u) {
        atomic_store(&parked,true);dma_running=false;
        if(mode==ACK_STOP_FAILURE)atomic_store(&park_failed,true);
    } else {
        if(mode==ACK_RESUME_FAILURE)return;
        atomic_store(&parked,false);dma_running=true;
    }
    atomic_store(&acknowledged_epoch,request);
}
void vTaskDelay(unsigned ticks) {
    (void)ticks;++delay_calls;
    if(control_stepping && ticks==2 &&
       (usb_stepping?net_completed>=1:!network_stepping||net_completed>=2))longjmp(task_exit,1);
    fake_ack();
}
void vTaskDelete(void *task){(void)task;assert(!"unexpected task deletion");}
TaskHandle_t xTaskCreateStaticPinnedToCore(void (*f)(void *),const char *name,unsigned stack,void *arg,unsigned prio,StackType_t *buf,StaticTask_t *tcb,unsigned core) {
    (void)f;(void)name;(void)stack;(void)arg;(void)prio;(void)buf;(void)tcb;(void)core;return (void *)1;
}
QueueHandle_t xQueueCreate(unsigned count,unsigned bytes){(void)count;(void)bytes;return (void *)1;}
int xQueueSend(QueueHandle_t queue,const void *value,unsigned wait){(void)queue;(void)value;(void)wait;return pdTRUE;}
int xQueueReceive(QueueHandle_t queue,void *value,unsigned wait){(void)queue;(void)value;(void)wait;return 0;}
int xQueueReset(QueueHandle_t queue){(void)queue;return pdTRUE;}
int xQueuePeek(QueueHandle_t queue,void *value,unsigned wait){(void)queue;(void)wait;memcpy(value,&published,sizeof published);return pdTRUE;}
int xQueueOverwrite(QueueHandle_t queue,const void *value) {
    (void)queue;memcpy(&published,value,sizeof published);
    if(audio_stepping) {
        ++received_blocks;
        if(received_blocks==1) {
            assert(published.fault && published.module_errors==1 && published.since.module_errors==1);
            activate(new_slot,true);
        } else if(received_blocks==2)longjmp(task_exit,1);
    }
    return pdTRUE;
}
esp_err_t board_audio_init(uint32_t rate){assert(rate==44100);return ESP_OK;}
esp_err_t board_audio_start_dma(void){dma_running=true;return ESP_OK;}
esp_err_t board_audio_stop_dma(void){dma_running=false;return ESP_OK;}
uint32_t board_audio_dma_errors(void){return 0;}
void board_audio_activity(bool enabled){(void)enabled;}
esp_err_t board_audio_write(const int16_t *pcm,size_t frames,size_t *written){(void)pcm;assert(frames==256);*written=frames*BOARD_AUDIO_CHANNELS*2;return ESP_OK;}
const esp_app_desc_t *esp_app_get_description(void){static esp_app_desc_t d;return &d;}
esp_err_t nvs_open(const char *space,int mode,nvs_handle_t *h){(void)space;(void)mode;*h=1;return ESP_OK;}
void nvs_close(nvs_handle_t h){(void)h;}
esp_err_t nvs_get_str(nvs_handle_t h,const char *key,char *out,size_t *size){(void)h;(void)key;(void)out;(void)size;return ESP_ERR_NVS_NOT_FOUND;}
esp_err_t nvs_set_str(nvs_handle_t h,const char *key,const char *value){(void)h;assert(!strcmp(key,"inflight")||!strcmp(key,"blocked"));if(!value[0])++guard_clears;return ESP_OK;}
esp_err_t nvs_commit(nvs_handle_t h){(void)h;return ESP_OK;}
/* Dormant real store methods are linked under private names, but never called. */
esp_err_t nvs_get_blob(nvs_handle_t h,const char *key,void *out,size_t *size){(void)h;(void)key;(void)out;(void)size;return ESP_ERR_NVS_NOT_FOUND;}
esp_err_t nvs_set_blob(nvs_handle_t h,const char *key,const void *in,size_t n){(void)h;(void)key;(void)in;(void)n;return ESP_OK;}
esp_err_t nvs_erase_key(nvs_handle_t h,const char *key){(void)h;(void)key;return ESP_OK;}
esp_err_t nvs_flash_init(void){return ESP_OK;}
#include "esp_spiffs.h"
#include "esp_partition.h"
esp_err_t esp_vfs_spiffs_register(const esp_vfs_spiffs_conf_t *c){(void)c;assert(!"unexpected real storage mount");return ESP_FAIL;}
const esp_partition_t *esp_partition_find_first(int t,int s,const char *n){(void)t;(void)s;(void)n;return NULL;}
esp_err_t esp_partition_read(const esp_partition_t *p,size_t o,void *v,size_t n){(void)p;(void)o;(void)v;(void)n;return ESP_FAIL;}

static int fake_process(void *ctx,const float *const *in,float *const *out,uint32_t frames,uint64_t pos) {
    (void)ctx;(void)in;(void)pos;assert(frames==256);memset(out[0],0,frames*sizeof(float));memset(out[1],0,frames*sizeof(float));
    return audio_stepping && received_blocks==0 ? RNBO_S3_INVALID : RNBO_S3_OK;
}
esp_err_t player_image_load(player_image *image,const uint8_t *bytes,size_t length,uint32_t role,uint32_t arena,char *error,size_t size) {
    must_park();++loader_calls;assert(role==1 && bytes && length && arena>=4096);
    if(failed_boundary==FAIL_LOAD){snprintf(error,size,"injected prepare failure");return ESP_FAIL;}
    image->arena_bytes=arena;image->info.context_bytes=32;image->module.process=fake_process;return ESP_OK;
}
void player_image_unload(player_image *image){(void)image;++unloads;}
esp_err_t player_image_statistics(player_image *image,char *error,size_t size){(void)image;(void)error;(void)size;return ESP_OK;}
bool player_store_init(char *error,size_t size){(void)error;(void)size;return true;}
bool player_store_stage(uint32_t role,const uint8_t *bytes,size_t length,uint8_t *slot,char *error,size_t size) {
    must_park();++stage_calls;assert(role==1&&bytes&&length);*slot=1;
    if(failed_boundary==FAIL_STAGE){snprintf(error,size,"injected staging failure");return false;}return true;
}
bool player_store_commit(uint32_t role,uint8_t slot,const char *hash,char *error,size_t size) {
    must_park();++commit_calls;assert(role==1&&slot==1&&strlen(hash)==64);
    if(failed_boundary==FAIL_COMMIT){snprintf(error,size,"injected selector failure");return false;}return true;
}
bool player_store_promote_previous(uint32_t role,const char *hash,char *error,size_t size){(void)role;(void)hash;(void)error;(void)size;return false;}
bool player_store_read(uint32_t role,bool prev,uint8_t **bytes,size_t *len,char *error,size_t size){(void)role;(void)prev;(void)bytes;(void)len;(void)error;(void)size;return false;}
void player_store_free(void *p){free(p);}

/* Network boundary doubles only. The actual owner command(), cJSON allocation
 * failure, mandatory response fallback, EOF polling and guard logic run above.
 * A completed slot is recycled by the simulated worker only on the next poll;
 * a delivered abandoned slot remains held until the owner completion call.
 */
esp_err_t player_network_init(void){return ESP_OK;}
bool player_network_start_saved(char *error,size_t size)
{(void)error;(void)size;must_park();assert(!boot_guard_pending);++net_start_calls;return true;}
bool player_network_configure(const uint8_t *ssid,size_t ns,const uint8_t *password,size_t np,
                              const uint8_t key[32],char *error,size_t size)
{(void)ssid;(void)ns;(void)password;(void)np;(void)key;(void)error;(void)size;assert(!"unexpected provisioning");return false;}
bool player_network_forget(char *error,size_t size)
{(void)error;(void)size;assert(!"unexpected forget");return false;}
bool player_network_scan(cJSON *parent,char *error,size_t size)
{(void)parent;(void)error;(void)size;assert(!"unexpected scan before guard verification");return false;}
void player_network_add_status(cJSON *parent){(void)parent;}
uint32_t player_network_current_session_id(void){return net_pending?net_session:0;}
uint32_t player_network_poll_request(char *line,size_t capacity)
{
    if(usb_stepping){
        if(usb_cursor<7||net_delivered)return 0; /* Peer becomes pending between USB bytes. */
        assert(usb_cursor==strlen(usb_program));
        if(usb_timeout)assert(strstr(reply,"Incomplete USB line timed out"));
        else assert(atomic_load(&volume)==19);
        assert(capacity>strlen("player-info"));strcpy(line,"player-info");
        ++net_delivered;net_pending=true;net_answered=false;net_session=200;return net_session;
    }
    if(!network_stepping)return 0;
    if(net_answered){net_pending=net_answered=false;}
    if(net_pending||net_delivered>=2)return 0;
    const char *text=net_delivered==0?"player-info":"player-volume 7";
    assert(strlen(text)<capacity);strcpy(line,text);++net_delivered;
    net_pending=true;net_answered=false;net_session=100+net_delivered;
    net_abandoned=net_delivered==1&&abandon_first;
    json_oom=net_delivered==1;
    return net_session;
}
bool player_network_respond(const char *json)
{
    if(usb_stepping){
        if(!net_pending||net_answered)return false;
        cJSON *o=cJSON_Parse(json);assert(o);
        const cJSON *value=cJSON_GetObjectItemCaseSensitive(o,"volume");
        assert(cJSON_IsNumber(value)&&value->valuedouble==(usb_timeout?50:19));cJSON_Delete(o);
        ++net_responses;++net_completed;net_answered=true;return true;
    }
    if(!network_stepping){control_puts(json);return true;}
    if(!net_pending||net_answered)return false;
    ++net_responses;++net_completed;
    if(net_delivered==1){
        assert(json_oom); /* cJSON never produced a reply: this is the static fallback. */
        assert(strlen(json)<sizeof net_reply);strcpy(net_reply,json);
        json_oom=false;
    }
    if(net_abandoned){net_pending=false;return false;}
    net_answered=true;return true;
}
static void *json_allocate(size_t bytes){return json_oom?NULL:malloc(bytes);}

static void reset_test(void) {
    discard_incoming();memset(&published,0,sizeof published);clear_reply();
    loader_calls=stage_calls=commit_calls=unloads=guard_clears=delay_calls=received_blocks=0;
    failed_boundary=FAIL_NONE;mode=ACK_NORMAL;now=0;audio_stepping=control_stepping=false;dma_running=true;
    network_stepping=net_pending=net_answered=net_abandoned=abandon_first=json_oom=false;
    usb_stepping=usb_timeout=false;usb_program=NULL;usb_cursor=0;
    net_delivered=net_completed=net_responses=net_start_calls=net_getchars=0;net_reply[0]=0;
    atomic_store(&active,NULL);atomic_store(&paused,false);atomic_store(&maintenance,false);atomic_store(&parked,false);
    atomic_store(&park_failed,false);atomic_store(&audio_ready,true);atomic_store(&generation,1);
    atomic_store(&maintenance_epoch,0);atomic_store(&acknowledged_epoch,0);atomic_store(&parameter_count,0);
    atomic_store(&queue_errors,0);boot_guard_pending=false;blocked_package[0]=boot_error[0]=0;store_ready=true;
    atomic_store(&volume,50);
    events=telemetry=(void *)1;
    old_slot=calloc(1,sizeof *old_slot);old_slot->image.module.process=fake_process;old_slot->image.position=4096;
    atomic_store(&active,old_slot);
}
static void dispose_test(void) {player_slot *s=atomic_exchange(&active,NULL);unload_slot(s);discard_incoming();}
static void feed(const uint8_t *bytes,size_t length) {
    char line[8192],hash[65];hash_bytes(bytes,length,hash);
    snprintf(line,sizeof line,"player-begin 1 %zu %s",length,hash);command(line);
    assert(incoming.bytes&&incoming.total==length);
    for(size_t offset=0;offset<length;offset+=1024) {
        size_t count=length-offset;if(count>1024)count=1024;
        int n=snprintf(line,sizeof line,"player-data %zu ",offset);
        for(size_t i=0;i<count;++i)sprintf(line+n+2*i,"%02x",bytes[offset+i]);
        command(line);
    }
    assert(incoming.used==length);clear_reply();
}
static void commit_test(void){char text[]="player-commit";command(text);}
static void test_ownership(const uint8_t *bytes,size_t length) {
    for(unsigned which=0;which<3;++which) {
        reset_test();feed(bytes,length);
        if(which==0)mode=ACK_STALE;
        else if(which==1){atomic_store(&maintenance_epoch,2);atomic_store(&acknowledged_epoch,1);mode=ACK_STALE;}
        else mode=ACK_STOP_FAILURE;
        commit_test();assert_reply_error(true);
        assert(!loader_calls&&!stage_calls&&!commit_calls);assert(atomic_load(&active)==old_slot);
        /* A late stale park ACK cannot retroactively run FS/ELF work. */
        atomic_store(&acknowledged_epoch,atomic_load(&maintenance_epoch)-1);
        assert(!incoming.bytes&&!loader_calls&&!stage_calls);dispose_test();
    }
}
static void test_incoming(const uint8_t *bytes,size_t length) {
    reset_test();feed(bytes,length);command_source=99;
    commit_test();assert_reply_error(true);assert(incoming.bytes&&!loader_calls&&!stage_calls);
    char foreign_abort[]="player-abort";command(foreign_abort);assert(incoming.bytes);assert_reply_error(true);
    command_source=0;incoming.owner=99;
    char physical_abort[]="player-abort";command(physical_abort);assert(!incoming.bytes);dispose_test();
    reset_test();feed(bytes,length);--incoming.used;commit_test();assert_reply_error(true);
    assert(!loader_calls&&!stage_calls);dispose_test();
    reset_test();feed(bytes,length);incoming.bytes[length-1]^=1;commit_test();assert_reply_error(true);
    assert(!loader_calls&&!stage_calls);dispose_test();
    reset_test();feed(bytes,length);char bad[]="player-data 999 ff";command(bad);assert(!incoming.bytes);assert_reply_error(true);
    assert(!loader_calls&&!stage_calls);dispose_test();
    reset_test();uint8_t *bad_package=malloc(length);memcpy(bad_package,bytes,length);bad_package[0]^=1;
    feed(bad_package,length);free(bad_package);commit_test();assert_reply_error(true);
    assert(!loader_calls&&!stage_calls);dispose_test();
}
static void test_transactions(const uint8_t *bytes,size_t length) {
    for(unsigned failure=FAIL_LOAD;failure<=FAIL_COMMIT;++failure) {
        reset_test();feed(bytes,length);failed_boundary=failure;commit_test();assert_reply_error(true);
        assert(atomic_load(&active)==old_slot && atomic_load(&generation)==1 && dma_running);
        assert(loader_calls==1);assert(stage_calls==(failure>=FAIL_STAGE));assert(commit_calls==(failure>=FAIL_COMMIT));dispose_test();
    }
    reset_test();feed(bytes,length);commit_test();
    cJSON *o=last_reply();assert(!strcmp(cJSON_GetObjectItemCaseSensitive(o,"upload")->valuestring,"committed"));cJSON_Delete(o);
    assert(dma_running&&!atomic_load(&maintenance)&&!atomic_load(&parked));
    assert(atomic_load(&active)!=old_slot&&atomic_load(&generation)==2&&unloads==1);dispose_test();
    reset_test();feed(bytes,length);mode=ACK_RESUME_FAILURE;commit_test();assert_reply_error(false);
    assert(commit_calls==1 && atomic_load(&active)!=old_slot && atomic_load(&generation)==2);
    assert(atomic_load(&park_failed));dispose_test();
}
static int control_getchar(void){
    if(usb_stepping){
        if(usb_cursor<strlen(usb_program))return (unsigned char)usb_program[usb_cursor++];
        if(!usb_timeout)assert(net_completed==1);
        return EOF;
    }
    if(network_stepping){++net_getchars;assert(net_completed==net_getchars);assert(!json_oom);}
    return EOF;
}
static void test_guard(void) {
    for(unsigned which=0;which<5;++which) {
        reset_test();boot_guard_pending=true;guard_start_position=4096;guard_generation=1;
        published.generation=1;published.frames=100000000;published.position=4096;
        if(which)published.position=4608;
        if(which==1)atomic_store(&paused,true);
        if(which==2)published.generation=2;
        if(which==3)published.fault=true;
        control_stepping=true;
        if(!setjmp(task_exit))control_task(NULL);
        control_stepping=false;
        assert(guard_clears==(which==4?1u:0u));
        assert(net_start_calls==(which==4?1u:0u));dispose_test();
    }
}
static void test_generation_reset(void) {
    reset_test();new_slot=calloc(1,sizeof *new_slot);new_slot->image.module.process=fake_process;
    new_slot->package.initial_volume=25;audio_stepping=true;
    if(!setjmp(task_exit))audio_task(NULL);
    audio_stepping=false;
    assert(received_blocks==2&&!published.fault&&published.module_errors==1&&published.since.module_errors==0);
    assert(published.frames==512&&published.generation==2&&published.position==256);
    free(old_slot);dispose_test();
}
static void test_network_owner_completion(void)
{
    for(unsigned abandoned=0;abandoned<2;++abandoned){
        reset_test();network_stepping=control_stepping=true;abandon_first=abandoned!=0;
        if(!setjmp(task_exit))control_task(NULL);
        control_stepping=network_stepping=false;
        assert(net_delivered==2&&net_completed==2&&net_getchars==2&&net_responses==2);
        assert(atomic_load(&volume)==7 && !json_oom && net_start_calls==1);
        cJSON *fallback=cJSON_Parse(net_reply);assert(fallback);
        assert(cJSON_IsString(cJSON_GetObjectItemCaseSensitive(fallback,"error")));cJSON_Delete(fallback);
        dispose_test();
    }
    puts("network OOM fallback, abandoned handoff and deferred radio PASS");
}
static void test_wifi_guard_blocks_early_settings_and_scan(void)
{
    reset_test();boot_guard_pending=true;
    const char *commands[]={"player-wifi-forget","player-wifi-scan","player-wifi-setup 61 - 0000000000000000000000000000000000000000000000000000000000000000"};
    for(unsigned i=0;i<sizeof commands/sizeof *commands;++i){
        char line[256];strcpy(line,commands[i]);clear_reply();command(line);
        assert_reply_error(true);assert(!net_start_calls && atomic_load(&maintenance_epoch)==0);
    }
    dispose_test();
}
static void test_usb_line_defers_network_and_timeout_unblocks(void)
{
    for(unsigned timeout=0;timeout<2;++timeout){
        reset_test();usb_stepping=control_stepping=true;usb_timeout=timeout!=0;
        usb_program=usb_timeout?"player-vol":"player-volume 19\n";
        if(!setjmp(task_exit))control_task(NULL);
        control_stepping=usb_stepping=false;
        assert(net_delivered==1&&net_completed==1&&net_responses==1);
        assert(atomic_load(&volume)==(timeout?50u:19u));
        if(timeout)assert(strstr(reply,"Incomplete USB line timed out"));
        else assert(!strstr(reply,"\"error\""));
        dispose_test();
    }
    puts("USB split-line deferral and bounded partial timeout PASS");
}
int main(int argc,char **argv) {
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);rewind(f);
    uint8_t *bytes=malloc((size_t)n);assert(bytes&&fread(bytes,1,(size_t)n,f)==(size_t)n);fclose(f);
    test_ownership(bytes,(size_t)n);test_incoming(bytes,(size_t)n);test_transactions(bytes,(size_t)n);
    cJSON_Hooks hooks={.malloc_fn=json_allocate,.free_fn=free};cJSON_InitHooks(&hooks);
    test_guard();test_generation_reset();test_network_owner_completion();test_wifi_guard_blocks_early_settings_and_scan();
    test_usb_line_defers_network_and_timeout_unblocks();cJSON_InitHooks(NULL);free(bytes);
    puts("player control: ownership, transactions, candidate guard, lifetime counters PASS");return 0;
}
