/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Stable Main player. Native images are trusted; installation is detached. */
#include "board_audio.h"
#include "pcm_output.h"
#include "allocation_watch.h"
#include "player_loader.h"
#include "player_store.h"
#include "player_inputs.h"
#include "player_midi.h"
#include "cJSON.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "mbedtls/sha256.h"
#include "nvs.h"
#include <inttypes.h>
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdarg.h>
#ifdef RNBO_S3_WIFI
#include "player_network.h"
#endif
#include <stdlib.h>
#include <string.h>
#ifndef CONFIG_RNBO_S3_HEADLESS
#include "board_display.h"
#include "patch_layout.h"
#endif

enum { AUDIO_STACK=24576, CONTROL_STACK=24576, EVENT_COUNT=32, LINE_BYTES=8192 };
typedef struct {
    uint64_t overruns,nonfinite,clipped,write_errors;
    uint32_t dma_errors,module_errors,queue_errors;
    allocation_watch_stats heap;
} player_errors;
typedef struct {
    player_image image;
    player_package package;
    rnbo_s3_parameter_info parameters[PLAYER_MAX_PARAMETERS];
    player_input_plan inputs;
} player_slot;
typedef struct {
    unsigned kind,index,generation;
    float value;
    uint8_t midi[3],midi_length;
} player_event;
typedef struct {
    uint64_t frames,blocks,busy_us,overruns,nonfinite,clipped,write_errors,position;
    uint32_t render_us,peak_us,dma_errors,module_errors,arena_used,output_peak,late_allocations,queue_errors;
    bool fault;
    allocation_watch_stats heap;
    player_errors since;
    unsigned generation;
} player_stats;
static _Atomic(player_slot *) active;
static atomic_bool paused=true,maintenance=false,parked=false,park_failed=false,audio_ready=false;
static atomic_uint generation=1,volume=50,queue_errors=0,parameter_count=0;
static atomic_uint maintenance_epoch=0,acknowledged_epoch=0;
static atomic_uint actual_bits[PLAYER_MAX_PARAMETERS],normalized_bits[PLAYER_MAX_PARAMETERS];
/* UINT32_MAX cannot encode a finite normalized value. One mailbox per parameter
 * coalesces physical changes without competing with the bounded command queue. */
static atomic_uint physical_pending[PLAYER_MAX_PARAMETERS];
static midi_note_state midi_notes;
static unsigned midi_recovery;
static QueueHandle_t events,telemetry;
static TaskHandle_t audio_handle,control_handle;
static StaticTask_t audio_tcb,control_tcb;
static bool store_ready,boot_guard_pending;
static uint64_t guard_start_position;
static unsigned guard_generation;
static nvs_handle_t guard_handle;
static char blocked_package[65],boot_error[192];
static const char *TAG="rnbo_player";
#ifndef CONFIG_RNBO_S3_HEADLESS
static atomic_bool display_enabled=false;
#endif
static struct {uint8_t *bytes;size_t total,used;char hash[65];int64_t touched;uint32_t owner;} incoming;
static uint32_t command_source; /* Zero is the physical USB console. */

static void reply_line(const char *text)
{
#ifdef RNBO_S3_WIFI
    if(command_source){player_network_respond(text);return;}
#endif
    puts(text);
}
static void reply_format(const char *format,...)
{
    char text[256];va_list args;va_start(args,format);
    int n=vsnprintf(text,sizeof text,format,args);va_end(args);
    if(n<0||(size_t)n>=sizeof text){reply_line("{\"error\":\"Reply exceeded limit\"}");return;}
    while(n&&text[n-1]=='\n')text[--n]=0;
    reply_line(text);
}

static void error_reply(const char *message,bool retained)
{
    cJSON *o=cJSON_CreateObject();if(!o)return;
    cJSON_AddStringToObject(o,"error",message);cJSON_AddBoolToObject(o,"old_retained",retained);
    cJSON_AddNumberToObject(o,"generation",atomic_load(&generation));
    char *text=cJSON_PrintUnformatted(o);if(text){reply_line(text);cJSON_free(text);}cJSON_Delete(o);
}
static void hash_bytes(const void *bytes,size_t count,char hex[65])
{
    unsigned char hash[32];mbedtls_sha256(bytes,count,hash,0);
    static const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hex[2*i]=digits[hash[i]>>4];hex[2*i+1]=digits[hash[i]&15];}hex[64]=0;
}
static bool hash_string(const char *s)
{
    if(!s || strlen(s)!=64)return false;
    for(unsigned i=0;i<64;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;
    return true;
}
static bool guard_write(const char *hash)
{
    if(nvs_set_str(guard_handle,"inflight",hash)!=ESP_OK || nvs_commit(guard_handle)!=ESP_OK)return false;
    boot_guard_pending=hash[0]!=0;return true;
}
static bool guard_init(void)
{
    if(nvs_open("rnbo_guard",NVS_READWRITE,&guard_handle)!=ESP_OK)return false;
    char failed[65]={0};size_t n=sizeof failed;
    esp_err_t r=nvs_get_str(guard_handle,"inflight",failed,&n);
    if(r!=ESP_OK && r!=ESP_ERR_NVS_NOT_FOUND)return false;
    n=sizeof blocked_package;
    r=nvs_get_str(guard_handle,"blocked",blocked_package,&n);
    if(r!=ESP_OK && r!=ESP_ERR_NVS_NOT_FOUND)return false;
    if(failed[0]) {
        if(!hash_string(failed) || nvs_set_str(guard_handle,"blocked",failed)!=ESP_OK)return false;
        memcpy(blocked_package,failed,sizeof blocked_package);
        if(!guard_write(""))return false;
        snprintf(boot_error,sizeof boot_error,"Previous native startup did not finish; failed package is blocked");
    }
    return true;
}
static void publish_parameter(player_slot *s,unsigned i)
{
    float a,n;unsigned ab,nb;
    if(s->image.module.parameter_value(s->image.context,i,&a,&n)!=RNBO_S3_OK || !isfinite(a)||!isfinite(n))return;
    memcpy(&ab,&a,4);memcpy(&nb,&n,4);
    atomic_store_explicit(&actual_bits[i],ab,memory_order_release);
    atomic_store_explicit(&normalized_bits[i],nb,memory_order_release);
}
static bool read_parameter(unsigned i,float *a,float *n)
{
    if(i>=atomic_load(&parameter_count))return false;
    unsigned ab=atomic_load_explicit(&actual_bits[i],memory_order_acquire),nb=atomic_load_explicit(&normalized_bits[i],memory_order_acquire);
    memcpy(a,&ab,4);memcpy(n,&nb,4);return true;
}
static bool post_volume(unsigned value)
{if(value>100)return false;atomic_store(&volume,value);return true;}
static void request_pause(void){atomic_store(&paused,true);player_midi_set_playing(false);}
static bool can_resume(void)
{
    if(!atomic_load(&active)||atomic_load(&park_failed)||atomic_load(&maintenance))return false;
    player_stats stats={0};if(telemetry)xQueuePeek(telemetry,&stats,0);
    return stats.generation!=atomic_load(&generation)||!stats.fault;
}
static void request_resume(void){if(can_resume())atomic_store(&paused,false);}
static bool queue_event(player_event *e)
{
    if(atomic_load(&maintenance)||atomic_load(&paused)||!atomic_load(&active))return false;
    if(e->generation!=atomic_load(&generation))return false;
    if(xQueueSend(events,e,0)==pdTRUE)return true;
    atomic_fetch_add(&queue_errors,1);request_pause();return false;
}
static void physical_publish(unsigned index,float normalized)
{
    if(index>=atomic_load(&parameter_count)||!isfinite(normalized)||normalized<0||normalized>1)return;
    unsigned bits;memcpy(&bits,&normalized,sizeof bits);
    atomic_store_explicit(&physical_pending[index],bits,memory_order_release);
}
#ifndef CONFIG_RNBO_S3_HEADLESS
static bool post_parameter(unsigned i,float n)
{
    if(!atomic_load(&display_enabled)||i>=atomic_load(&parameter_count)||!isfinite(n)||n<0||n>1)return false;
    player_event e={.kind=RNBO_S3_PARAMETER_NORMALIZED,.index=i,.value=n,.generation=atomic_load(&generation)};
    return queue_event(&e);
}
static bool read_display_parameter(unsigned i,float *a,float *n)
{return atomic_load(&display_enabled)&&read_parameter(i,a,n);}
static void display_slot(player_slot *s)
{
    atomic_store(&display_enabled,false);
    unsigned count=s?s->image.parameter_count:0;
    patch_parameter *labels=heap_caps_calloc(count?count:1,sizeof *labels,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!labels)return;
    for(unsigned i=0;i<count;++i){snprintf(labels[i].name,sizeof labels[i].name,"%s",s->parameters[i].name);snprintf(labels[i].unit,sizeof labels[i].unit,"%s",s->parameters[i].unit);}
    if(board_display_player_layout(s?s->package.name:"RNBO Player",s?s->package.source_sha256:"none",s?s->package.visual:NULL,labels,count)==ESP_OK)
        atomic_store(&display_enabled,true);
    heap_caps_free(labels);
}
#endif
static void audio_task(void *unused)
{
    (void)unused;
    float left[256],right[256];float *outputs[2]={left,right};
    int16_t pcm[256*BOARD_AUDIO_CHANNELS];pcm_output sink;pcm_output_init(&sink);
    player_stats stats={0},baseline={0};unsigned observed_generation=0;
    if(board_audio_start_dma()!=ESP_OK){atomic_store(&park_failed,true);vTaskDelete(NULL);return;}
    allocation_watch_start(ALLOCATION_WATCH_AUDIO);
    atomic_store_explicit(&audio_ready,true,memory_order_release);
    for(;;) {
        unsigned request=atomic_load_explicit(&maintenance_epoch,memory_order_acquire);
        if(request&1u) {
            allocation_watch_stop();
            esp_err_t stopped=board_audio_stop_dma();
            atomic_store(&park_failed,stopped!=ESP_OK);
            atomic_store_explicit(&parked,true,memory_order_release);
            atomic_store_explicit(&acknowledged_epoch,request,memory_order_release);
            while(atomic_load_explicit(&maintenance_epoch,memory_order_acquire)==request)vTaskDelay(pdMS_TO_TICKS(1));
            if(stopped==ESP_OK && board_audio_start_dma()!=ESP_OK){stats.fault=true;atomic_store(&park_failed,true);request_pause();}
            allocation_watch_start(ALLOCATION_WATCH_AUDIO);
            atomic_store_explicit(&parked,false,memory_order_release);
            atomic_store_explicit(&acknowledged_epoch,atomic_load(&maintenance_epoch),memory_order_release);
        } else atomic_store_explicit(&acknowledged_epoch,request,memory_order_release);
        int64_t began=esp_timer_get_time();
        unsigned now_generation=atomic_load(&generation);
        if(now_generation!=observed_generation) {
            baseline=stats;baseline.dma_errors=board_audio_dma_errors();
            baseline.queue_errors=atomic_load(&queue_errors);
            baseline.heap=allocation_watch_snapshot(ALLOCATION_WATCH_AUDIO);
            stats.fault=false;stats.peak_us=0;stats.late_allocations=0;
            observed_generation=now_generation;stats.generation=now_generation;
            player_slot *replacement=atomic_load(&active);
            stats.position=replacement?replacement->image.position:0;
            stats.arena_used=replacement?replacement->image.stats.arena_used:0;
        }
        player_slot *s=atomic_load_explicit(&active,memory_order_acquire);
        bool play=s&&!atomic_load(&paused)&&!stats.fault&&!atomic_load(&park_failed);
        player_midi_set_playing(play);
        bool midi_changed=false;
        player_event e;
        for(unsigned i=0;i<EVENT_COUNT && xQueueReceive(events,&e,0)==pdTRUE;++i) {
            if(!play||e.generation!=atomic_load(&generation))continue;
            rnbo_s3_event event={.struct_bytes=sizeof event,.kind=e.kind,.parameter_index=e.index,.value=e.value,.midi_length=e.midi_length};
            memcpy(event.midi,e.midi,sizeof event.midi);
            if(s->image.module.event(s->image.context,&event)!=RNBO_S3_OK){++stats.module_errors;stats.fault=true;}
            else if(e.kind!=RNBO_S3_MIDI)publish_parameter(s,e.index);
            else {midi_notes_observe(&midi_notes,e.midi,e.midi_length);midi_changed=true;}
        }
        if(play&&!stats.fault&&(s->image.module.flags&RNBO_S3_SHORT_MIDI_INPUT)) {
            unsigned recovery=player_midi_recovery_epoch();
            if(recovery&&recovery!=midi_recovery) {
                midi_recovery=recovery;player_midi_flush_queue();midi_notes_recover(&midi_notes);
            }
            for(unsigned i=0;i<64&&!stats.fault;++i) {
                player_midi_message message={0};bool cleanup=midi_notes.recovering;
                if(cleanup) {
                    if(!midi_notes_recovery_next(&midi_notes,message.bytes)) {
                        player_midi_recovery_done(midi_recovery);midi_recovery=0;break;
                    }
                    message.length=3;
                } else if(!player_midi_receive(&message))break;
                rnbo_s3_event event={.struct_bytes=sizeof event,.kind=RNBO_S3_MIDI,.midi_port=0,.midi_length=message.length};
                memcpy(event.midi,message.bytes,sizeof event.midi);
                if(s->image.module.event(s->image.context,&event)!=RNBO_S3_OK){++stats.module_errors;stats.fault=true;break;}
                midi_changed=true;
                if(!cleanup){midi_notes_observe(&midi_notes,message.bytes,message.length);player_midi_delivered();}
                if(message.bytes[0]==0xff){player_midi_request_recovery();break;}
            }
        }
        if(play&&!stats.fault)for(unsigned i=0;i<s->inputs.count;++i) {
            unsigned index=s->inputs.bindings[i].parameter_index;
            unsigned bits=atomic_exchange_explicit(&physical_pending[index],UINT32_MAX,memory_order_acq_rel);
            if(bits==UINT32_MAX)continue;
            float value;memcpy(&value,&bits,sizeof value);
            rnbo_s3_event event={.struct_bytes=sizeof event,.kind=RNBO_S3_PARAMETER_NORMALIZED,.parameter_index=index,.value=value};
            if(s->image.module.event(s->image.context,&event)!=RNBO_S3_OK){++stats.module_errors;stats.fault=true;break;}
            publish_parameter(s,index);
        }
        if(play && !stats.fault) {
            if(s->image.module.process(s->image.context,NULL,outputs,256,s->image.position)!=RNBO_S3_OK){++stats.module_errors;stats.fault=true;}
            else s->image.position+=256;
            char error[128];
            if(player_image_statistics(&s->image,error,sizeof error)!=ESP_OK){++stats.module_errors;stats.fault=true;}
            stats.arena_used=s->image.stats.arena_used;
            stats.late_allocations=(uint32_t)s->image.dynamic_stats.total_late_allocations;
            stats.position=s->image.position;
            if(midi_changed)for(unsigned i=0;i<s->image.parameter_count;++i)publish_parameter(s,i);
        } else {memset(left,0,sizeof left);memset(right,0,sizeof right);}
        if(!pcm_output_render(&sink,left,right,pcm,256,BOARD_AUDIO_CHANNELS,atomic_load(&volume),0.5f,!play||stats.fault))stats.fault=true;
        stats.nonfinite=sink.nonfinite;stats.clipped=sink.clipped;
        if(stats.nonfinite>baseline.nonfinite)stats.fault=true;
        unsigned peak=0;for(unsigned i=0;i<256*BOARD_AUDIO_CHANNELS;++i){unsigned a=pcm[i]<0?-(int)pcm[i]:pcm[i];if(a>peak)peak=a;}
        stats.output_peak=peak;
        stats.render_us=(uint32_t)(esp_timer_get_time()-began);
        if(stats.render_us>stats.peak_us)stats.peak_us=stats.render_us;
        stats.busy_us+=stats.render_us;++stats.blocks;
        if((uint64_t)stats.render_us*44100u>256u*1000000u)++stats.overruns;
        size_t written=0;
        if(board_audio_write(pcm,256,&written)!=ESP_OK || written!=sizeof pcm)++stats.write_errors;
        stats.frames+=256;stats.dma_errors=board_audio_dma_errors();stats.queue_errors=atomic_load(&queue_errors);
        stats.heap=allocation_watch_snapshot(ALLOCATION_WATCH_AUDIO);
        stats.since=(player_errors){.overruns=stats.overruns-baseline.overruns,.nonfinite=stats.nonfinite-baseline.nonfinite,
            .clipped=stats.clipped-baseline.clipped,.write_errors=stats.write_errors-baseline.write_errors,
            .dma_errors=stats.dma_errors-baseline.dma_errors,.module_errors=stats.module_errors-baseline.module_errors,.queue_errors=stats.queue_errors-baseline.queue_errors,
            .heap={.allocations=stats.heap.allocations-baseline.heap.allocations,.frees=stats.heap.frees-baseline.heap.frees,
                .requested_bytes=stats.heap.requested_bytes-baseline.heap.requested_bytes}};
        if(stats.since.heap.allocations||stats.since.heap.frees||stats.late_allocations)stats.fault=true;
        if(stats.fault)request_pause();
        xQueueOverwrite(telemetry,&stats);
#ifdef CONFIG_RNBO_S3_HEADLESS
        board_audio_activity(play&&!stats.fault);
#endif
    }
}
static bool begin_maintenance(char *error,size_t size)
{
    if(!atomic_load(&audio_ready)||atomic_load(&park_failed)){snprintf(error,size,"Audio owner is not available for maintenance");return false;}
    atomic_store_explicit(&maintenance,true,memory_order_release);
    player_midi_set_playing(false);
    unsigned request=atomic_fetch_add_explicit(&maintenance_epoch,1,memory_order_acq_rel)+1;
    int64_t deadline=esp_timer_get_time()+3000000;
    while(atomic_load_explicit(&acknowledged_epoch,memory_order_acquire)!=request) {
        if(esp_timer_get_time()>deadline){
            atomic_store(&maintenance,false);unsigned resumed=atomic_fetch_add(&maintenance_epoch,1)+1;
            deadline=esp_timer_get_time()+3000000;
            while(atomic_load(&acknowledged_epoch)!=resumed&&esp_timer_get_time()<deadline)vTaskDelay(pdMS_TO_TICKS(1));
            if(atomic_load(&acknowledged_epoch)!=resumed)atomic_store(&park_failed,true);
            snprintf(error,size,"Audio owner did not park; no storage write attempted");return false;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    if(atomic_load(&park_failed)){
        atomic_store(&maintenance,false);unsigned resumed=atomic_fetch_add(&maintenance_epoch,1)+1;
        deadline=esp_timer_get_time()+3000000;
        while(atomic_load(&acknowledged_epoch)!=resumed&&esp_timer_get_time()<deadline)vTaskDelay(pdMS_TO_TICKS(1));
        snprintf(error,size,"Audio DMA stop failed; no storage write attempted");return false;
    }
    xQueueReset(events);return true;
}
static bool end_maintenance(void)
{
    atomic_store_explicit(&maintenance,false,memory_order_release);
    unsigned resumed=atomic_fetch_add_explicit(&maintenance_epoch,1,memory_order_acq_rel)+1;
    int64_t deadline=esp_timer_get_time()+3000000;
    while(atomic_load_explicit(&acknowledged_epoch,memory_order_acquire)!=resumed&&esp_timer_get_time()<deadline)vTaskDelay(pdMS_TO_TICKS(1));
    if(atomic_load(&acknowledged_epoch)!=resumed)atomic_store(&park_failed,true);
    return !atomic_load(&park_failed);
}
static void unload_slot(player_slot *s)
{
    if(!s)return;
    player_image_unload(&s->image);player_package_clear(&s->package);heap_caps_free(s);
}
static const char *input_parameter_id(void *context,unsigned index)
{return ((player_slot *)context)->parameters[index].id;}
static player_slot *load_slot(const uint8_t *bytes,size_t length,char *error,size_t size)
{
    player_slot *s=heap_caps_calloc(1,sizeof *s,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!s){snprintf(error,size,"Insufficient player metadata memory");return NULL;}
    if(!player_package_parse(bytes,length,&s->package,error,size))goto fail;
    if(s->package.role!=PLAYER_ROLE_MAIN){snprintf(error,size,"Only one Main patch is supported");goto fail;}
    if(blocked_package[0]&&!strcmp(blocked_package,s->package.package_sha256)){snprintf(error,size,"Package previously failed native startup; rebuild it before retrying");goto fail;}
    if(!guard_write(s->package.package_sha256)){snprintf(error,size,"Cannot save native startup recovery guard");goto fail;}
    allocation_watch_start(ALLOCATION_WATCH_PREPARE);
    esp_err_t r=player_image_load(&s->image,s->package.elf,s->package.elf_bytes,RNBO_S3_MAIN,s->package.arena_bytes,error,size);
    allocation_watch_stop();
    if(r!=ESP_OK)goto fail;
    for(unsigned i=0;i<s->image.parameter_count;++i) {
        s->parameters[i].struct_bytes=sizeof s->parameters[i];
        if(s->image.module.parameter_info(s->image.context,i,&s->parameters[i])!=RNBO_S3_OK){snprintf(error,size,"Cannot copy parameter schema");goto fail;}
    }
#ifdef CONFIG_RNBO_S3_HEADLESS
    if(!player_inputs_plan_parse(s->package.metadata_json,true,CONFIG_RNBO_S3_I2S_BCLK,CONFIG_RNBO_S3_I2S_WS,CONFIG_RNBO_S3_I2S_DOUT,
                                s->image.parameter_count,input_parameter_id,s,&s->inputs,error,size))goto fail;
#else
    if(!player_inputs_plan_parse(s->package.metadata_json,false,-1,-1,-1,
                                s->image.parameter_count,input_parameter_id,s,&s->inputs,error,size))goto fail;
#endif
    for(unsigned i=0;i<s->inputs.count;++i)if(player_midi_uart_enabled()&&s->inputs.bindings[i].gpio==44) {
        snprintf(error,size,"D7/GPIO44 is reserved by enabled UART MIDI");goto fail;
    }
    /* Detached finite/CPU screen; an actual system deadline remains a hardware
     * observation. The screen advances the candidate by sixteen callbacks. */
    float left[256],right[256];float *outputs[2]={left,right};
    for(unsigned call=0;call<16;++call) {
        int64_t start=esp_timer_get_time();
        int result=s->image.module.process(s->image.context,NULL,outputs,256,s->image.position);
        int64_t elapsed=esp_timer_get_time()-start;
        if(result!=RNBO_S3_OK){snprintf(error,size,"Candidate render failed during detached preparation");goto fail;}
        s->image.position+=256;
        if(player_image_statistics(&s->image,error,size)!=ESP_OK)goto fail;
        for(unsigned i=0;i<256;++i)if(!isfinite(left[i])||!isfinite(right[i])){snprintf(error,size,"Candidate produced a nonfinite sample");goto fail;}
        if(elapsed>5224){snprintf(error,size,"Candidate uses %lldus per callback; player screen reserves time for the audio sink",(long long)elapsed);goto fail;}
    }
    /* Parsed JSON is separately owned. No source payload address is retained. */
    s->package.payload=s->package.metadata=s->package.elf=NULL;
    return s;
fail:
    allocation_watch_stop();unload_slot(s);(void)guard_write("");return NULL;
}
static void activate(player_slot *s,bool autostart)
{
    guard_start_position=s?s->image.position:0;
#ifndef CONFIG_RNBO_S3_HEADLESS
    atomic_store(&display_enabled,false);
#endif
    atomic_store(&parameter_count,0);
    for(unsigned i=0;i<PLAYER_MAX_PARAMETERS;++i)atomic_store(&physical_pending[i],UINT32_MAX);
    player_input_plan empty={0};char input_error[128];
    if(!player_inputs_open(s?&s->inputs:&empty,input_error,sizeof input_error))ESP_LOGW(TAG,"%s",input_error);
    atomic_store_explicit(&active,s,memory_order_release);
    if(s)for(unsigned i=0;i<s->image.parameter_count;++i)publish_parameter(s,i);
    atomic_store(&parameter_count,s?s->image.parameter_count:0);
    guard_generation=atomic_fetch_add(&generation,1)+1;
    memset(&midi_notes,0,sizeof midi_notes);midi_recovery=0;
    player_midi_set_route(guard_generation,s&&(s->image.module.flags&RNBO_S3_SHORT_MIDI_INPUT));
    if(s&&autostart){atomic_store(&volume,s->package.initial_volume);atomic_store(&paused,false);}
#ifndef CONFIG_RNBO_S3_HEADLESS
    display_slot(s);
#endif
}
static void discard_incoming(void)
{heap_caps_free(incoming.bytes);memset(&incoming,0,sizeof incoming);}
static void commit_incoming(void)
{
    char error[256];player_slot *candidate=NULL,*old=atomic_load(&active);bool held=false;uint8_t slot;
    char actual[65];hash_bytes(incoming.bytes,incoming.used,actual);
    if(incoming.used!=incoming.total||strcmp(actual,incoming.hash)){error_reply("Incomplete package or transfer checksum differs",true);discard_incoming();return;}
    if(!store_ready){error_reply(boot_error[0]?boot_error:"Player storage unavailable",true);discard_incoming();return;}
    if(!begin_maintenance(error,sizeof error)){error_reply(error,true);discard_incoming();return;}held=true;
    candidate=load_slot(incoming.bytes,incoming.total,error,sizeof error);
    if(!candidate)goto fail;
    if(!player_store_stage(PLAYER_ROLE_MAIN,incoming.bytes,incoming.total,&slot,error,sizeof error))goto fail;
    if(!player_store_commit(PLAYER_ROLE_MAIN,slot,candidate->package.package_sha256,error,sizeof error))goto fail;
    activate(candidate,true);candidate=NULL;
    unload_slot(old);
    bool resumed=end_maintenance();held=false;
    if(!resumed){error_reply("New patch is saved, but audio DMA could not resume; restart the player",false);discard_incoming();return;}
    player_slot *now=atomic_load(&active);
    reply_format("{\"upload\":\"committed\",\"generation\":%u,\"role\":1,\"package_sha256\":\"%s\"}\n",atomic_load(&generation),now->package.package_sha256);
    discard_incoming();return;
fail:
    unload_slot(candidate);(void)guard_write("");if(held)end_maintenance();
    error_reply(error,true);discard_incoming();
}
static void add_number(cJSON *o,const char *key,double value){cJSON_AddNumberToObject(o,key,value);}
static void player_info(void)
{
    player_stats stats={0};xQueuePeek(telemetry,&stats,0);
    player_slot *s=atomic_load(&active);const esp_app_desc_t *app=esp_app_get_description();
    char firmware[65];static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i){firmware[2*i]=hex[app->app_elf_sha256[i]>>4];firmware[2*i+1]=hex[app->app_elf_sha256[i]&15];}firmware[64]=0;
    cJSON *o=cJSON_CreateObject();if(!o){error_reply("Cannot allocate player status",true);return;}
    cJSON_AddStringToObject(o,"runtime","rnbo-esp32s3-player");add_number(o,"api_version",1);cJSON_AddStringToObject(o,"board",BOARD_MODEL);
    add_number(o,"physical_inputs_version",1);
    add_number(o,"midi_input_version",1);player_midi_add_status(o);
    cJSON_AddStringToObject(o,"firmware_elf_sha256",firmware);add_number(o,"rate",44100);add_number(o,"block_frames",256);add_number(o,"channels",BOARD_AUDIO_CHANNELS);
    add_number(o,"generation",atomic_load(&generation));cJSON_AddBoolToObject(o,"paused",atomic_load(&paused));cJSON_AddBoolToObject(o,"panic",atomic_load(&paused)||!s);
    cJSON_AddBoolToObject(o,"maintenance",atomic_load(&maintenance));add_number(o,"volume",atomic_load(&volume));
    cJSON_AddBoolToObject(o,"boot_verified",!boot_guard_pending);cJSON_AddBoolToObject(o,"storage_ready",store_ready);
    if(boot_error[0])cJSON_AddStringToObject(o,"boot_note",boot_error);
#ifdef RNBO_S3_WIFI
    player_network_add_status(o);
#endif
    add_number(o,"frames",stats.frames);add_number(o,"blocks",stats.blocks);add_number(o,"render_us",stats.render_us);add_number(o,"peak_us",stats.peak_us);
    add_number(o,"output_peak_q15",stats.output_peak);cJSON_AddStringToObject(o,"output_meter_scope","final PCM after volume and saturation");
    bool current=stats.generation==atomic_load(&generation);
    add_number(o,"telemetry_generation",stats.generation);add_number(o,"render_busy_total_us",stats.busy_us);
    add_number(o,"render_deadline_overruns",current?stats.since.overruns:0);add_number(o,"nonfinite",current?stats.since.nonfinite:0);add_number(o,"clipped",current?stats.since.clipped:0);
    add_number(o,"write_errors",current?stats.since.write_errors:0);add_number(o,"dma_errors",current?stats.since.dma_errors:0);add_number(o,"queue_errors",current?stats.since.queue_errors:0);add_number(o,"module_errors",current?stats.since.module_errors:0);
    add_number(o,"audio_heap_allocations",current?stats.since.heap.allocations:0);add_number(o,"audio_heap_frees",current?stats.since.heap.frees:0);add_number(o,"late_platform_allocations",current?stats.late_allocations:0);
    cJSON_AddBoolToObject(o,"allocation_fault",(current&&stats.fault)||atomic_load(&park_failed));cJSON_AddBoolToObject(o,"reconstruction_failed",false);
    cJSON *history=cJSON_AddObjectToObject(o,"lifetime");
    add_number(history,"render_deadline_overruns",stats.overruns);add_number(history,"nonfinite",stats.nonfinite);add_number(history,"clipped",stats.clipped);
    add_number(history,"write_errors",stats.write_errors);add_number(history,"dma_errors",stats.dma_errors);add_number(history,"module_errors",stats.module_errors);
    add_number(history,"queue_errors",atomic_load(&queue_errors));
    add_number(history,"audio_heap_allocations",stats.heap.allocations);add_number(history,"audio_heap_frees",stats.heap.frees);
    add_number(o,"internal_free_bytes",heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT));add_number(o,"psram_free_bytes",heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));add_number(o,"uptime_us",esp_timer_get_time());
    if(!s)cJSON_AddNullToObject(o,"main");
    else {
        cJSON *m=cJSON_AddObjectToObject(o,"main");cJSON_AddStringToObject(m,"name",s->package.name);cJSON_AddStringToObject(m,"package_sha256",s->package.package_sha256);
        cJSON_AddStringToObject(m,"source_sha256",s->package.source_sha256);add_number(m,"arena_bytes",s->image.arena_bytes);add_number(m,"arena_used",stats.arena_used);
        add_number(m,"context_bytes",s->image.info.context_bytes);add_number(m,"sample_position",stats.position);add_number(m,"parameter_count",s->image.parameter_count);
        cJSON *p=cJSON_AddArrayToObject(m,"parameters");
        player_inputs_add_status(m);
        for(unsigned i=0;i<s->image.parameter_count;++i) {
            rnbo_s3_parameter_info *meta=&s->parameters[i];float a=meta->initial,n=0;read_parameter(i,&a,&n);
            cJSON *row=cJSON_CreateObject();add_number(row,"index",i);cJSON_AddStringToObject(row,"name",meta->name);cJSON_AddStringToObject(row,"unit",meta->unit);
            add_number(row,"min",meta->minimum);add_number(row,"max",meta->maximum);add_number(row,"initial",meta->initial);add_number(row,"actual",a);add_number(row,"normalized",n);cJSON_AddItemToArray(p,row);
        }
    }
    char *text=cJSON_PrintUnformatted(o);if(text){reply_line(text);cJSON_free(text);}else error_reply("Cannot encode player status",true);cJSON_Delete(o);
}
static int unhex(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;}
#ifdef RNBO_S3_WIFI
static bool decode_wifi_hex(const char *text,uint8_t *bytes,size_t capacity,size_t *length)
{
    size_t n=strlen(text);if(!strcmp(text,"-")){*length=0;return true;}
    if(!n||(n&1)||n/2>capacity)return false;
    for(size_t i=0;i<n;i+=2){int a=unhex(text[i]),b=unhex(text[i+1]);if(a<0||b<0)return false;bytes[i/2]=(uint8_t)(a*16+b);if(!bytes[i/2])return false;}
    *length=n/2;return true;
}
static void wifi_command(char *line)
{
    if(command_source){error_reply("Wi-Fi settings require the physical USB connection",true);return;}
    if(boot_guard_pending){error_reply("Wait for the Main startup check before changing Wi-Fi",true);return;}
    if(incoming.bytes){error_reply("Finish or abort the current package before changing Wi-Fi",true);return;}
    char error[192]={0};bool ok=false;
    if(!strcmp(line,"player-wifi-scan")) {
        if(!begin_maintenance(error,sizeof error)){error_reply(error,true);return;}
        cJSON *result=cJSON_CreateObject();
        ok=result&&player_network_scan(result,error,sizeof error);
        bool resumed=end_maintenance();
        if(!ok||!resumed){cJSON_Delete(result);error_reply(error[0]?error:"Network scan failed or audio could not resume",true);return;}
        char *text=cJSON_PrintUnformatted(result);
        if(text){reply_line(text);cJSON_free(text);}else error_reply("Cannot encode nearby networks",true);
        cJSON_Delete(result);return;
    }
    if(!strcmp(line,"player-wifi-forget")) {
        if(!begin_maintenance(error,sizeof error)){error_reply(error,true);return;}
        ok=player_network_forget(error,sizeof error);
    } else {
        char ssid_hex[65],password_hex[127],key_hex[65],tail;
        uint8_t ssid[32],password[63],key[32];size_t ssid_n,password_n;
        if(sscanf(line,"player-wifi-setup %64s %126s %64s %c",ssid_hex,password_hex,key_hex,&tail)!=3 ||
           !decode_wifi_hex(ssid_hex,ssid,sizeof ssid,&ssid_n)||!ssid_n||
           !decode_wifi_hex(password_hex,password,sizeof password,&password_n)||
           (password_n&&password_n<8)||!hash_string(key_hex)) {
            error_reply("Invalid Wi-Fi settings; use a network name and an empty or 8-63 byte password",true);return;
        }
        for(unsigned i=0;i<32;++i)key[i]=(uint8_t)(unhex(key_hex[2*i])*16+unhex(key_hex[2*i+1]));
        if(!begin_maintenance(error,sizeof error)){memset(password,0,sizeof password);memset(key,0,sizeof key);error_reply(error,true);return;}
        ok=player_network_configure(ssid,ssid_n,password,password_n,key,error,sizeof error);
        memset(password,0,sizeof password);memset(key,0,sizeof key);
    }
    bool resumed=end_maintenance();
    if(!ok){error_reply(error[0]?error:"Cannot save Wi-Fi settings",true);return;}
    if(!resumed){error_reply("Wi-Fi settings saved; restart the player because its audio driver did not resume",true);return;}
    reply_line(!strcmp(line,"player-wifi-forget")?"{\"wifi_forgotten\":true}":"{\"wifi_configured\":true}");
}
#endif
static void command(char *line)
{
    if(!strcmp(line,"player-info")){player_info();return;}
    if(!strcmp(line,"player-midi-config off")||!strcmp(line,"player-midi-config uart")) {
        if(incoming.bytes){error_reply("Finish the current package upload before changing MIDI",true);return;}
        bool enable=!strcmp(line,"player-midi-config uart");player_slot *slot=atomic_load(&active);
        if(enable&&slot)for(unsigned i=0;i<slot->inputs.count;++i)if(slot->inputs.bindings[i].gpio==44) {
            error_reply("D7/GPIO44 is already bound to a physical parameter",true);return;
        }
        char error[192];if(!begin_maintenance(error,sizeof error)){error_reply(error,true);return;}
        bool ok=player_midi_configure_uart(enable,error,sizeof error);bool resumed=end_maintenance();
        if(!ok||!resumed){error_reply(ok?"MIDI settings saved but audio could not resume":error,true);return;}
        reply_line("{\"midi_configured\":true}");return;
    }
#ifdef RNBO_S3_WIFI
    if(!strncmp(line,"player-wifi-",12)) {wifi_command(line);return;}
#endif
    bool transfer=!strncmp(line,"player-begin ",13)||!strncmp(line,"player-data ",12)||!strcmp(line,"player-commit")||!strcmp(line,"player-abort");
    if(transfer && incoming.bytes && incoming.owner!=command_source && !(command_source==0&&!strcmp(line,"player-abort"))) {
        error_reply("Another connection owns the incoming package; abort over USB or wait for its timeout",true);return;
    }
    if(!strcmp(line,"player-abort")){discard_incoming();reply_line("{\"upload\":\"aborted\"}");return;}
    if(!strcmp(line,"player-commit")){if(!incoming.bytes)error_reply("No incoming package",true);else commit_incoming();return;}
    if(!strcmp(line,"player-pause")){request_pause();reply_line("{\"paused\":true}");return;}
    if(!strcmp(line,"player-resume")){if(!can_resume()){error_reply("Load a healthy Main patch, finish installation, or restart a failed audio driver",true);return;}request_resume();reply_line("{\"paused\":false}");return;}
    unsigned role,total,value,gen,index;float normalized;char hash[65],tail;
    char midi_hex[257];
    bool loopback=!strncmp(line,"player-midi-loopback ",21);
    if(sscanf(line,loopback?"player-midi-loopback %u %256s %c":"player-midi-stream %u %256s %c",&gen,midi_hex,&tail)==2) {
        size_t n=strlen(midi_hex);uint8_t bytes[128];
        if(gen!=atomic_load(&generation)||!n||(n&1)||!player_midi_has_input()) {
            error_reply("MIDI stream needs the current generation and a recompiled MIDI-input patch",true);return;
        }
        for(size_t i=0;i<n;i+=2){int a=unhex(midi_hex[i]),b=unhex(midi_hex[i+1]);if(a<0||b<0){error_reply("MIDI stream must be hexadecimal bytes",true);return;}bytes[i/2]=(uint8_t)(a*16+b);}
        if(loopback) {
            char error[128];if(!player_midi_uart_loopback(bytes,n/2,error,sizeof error)){error_reply(error,true);return;}
        } else player_midi_stream_test(bytes,n/2);
        reply_line("{\"midi_stream_accepted\":true}");return;
    }
    if(sscanf(line,"player-begin %u %u %64s %c",&role,&total,hash,&tail)==3) {
        if(role!=1||total<128||total>PLAYER_PACKAGE_MAX_BYTES||!hash_string(hash)){error_reply("Invalid Main package size or hash",true);return;}
        discard_incoming();incoming.bytes=heap_caps_malloc(total,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if(!incoming.bytes){error_reply("Cannot allocate incoming package buffer",true);return;}
        incoming.total=total;incoming.owner=command_source;incoming.touched=esp_timer_get_time();memcpy(incoming.hash,hash,65);
        reply_line("{\"upload\":\"ready\",\"offset\":0,\"chunk_bytes\":1024}");return;
    }
    if(!strncmp(line,"player-data ",12)) {
        char *end=NULL;unsigned long offset=strtoul(line+12,&end,10);
        if(!incoming.bytes||end==line+12||*end!=' '){error_reply("No incoming package or invalid chunk",true);discard_incoming();return;}
        const char *data=end+1;size_t n=strlen(data);
        if(offset!=incoming.used||!n||n>2048||(n&1)||n/2>incoming.total-incoming.used){error_reply("Invalid package chunk offset or size",true);discard_incoming();return;}
        for(size_t i=0;i<n;i+=2){int a=unhex(data[i]),b=unhex(data[i+1]);if(a<0||b<0){error_reply("Invalid hex package chunk",true);discard_incoming();return;}incoming.bytes[incoming.used+i/2]=(uint8_t)((a<<4)|b);}
        incoming.used+=n/2;incoming.touched=esp_timer_get_time();reply_format("{\"upload\":\"chunk\",\"offset\":%u}\n",(unsigned)incoming.used);return;
    }
    if(sscanf(line,"player-volume %u %c",&value,&tail)==1&&post_volume(value)){reply_format("{\"volume\":%u,\"accepted\":true}\n",value);return;}
    if(sscanf(line,"player-param %u %u %u %f %c",&role,&gen,&index,&normalized,&tail)==4) {
        if(role!=1||gen!=atomic_load(&generation)||index>=atomic_load(&parameter_count)||!isfinite(normalized)||normalized<0||normalized>1){error_reply("Parameter generation/index/value differs from active Main",true);return;}
        player_event e={.kind=RNBO_S3_PARAMETER_NORMALIZED,.index=index,.value=normalized,.generation=gen};
        if(!queue_event(&e))error_reply("Main is paused, installing or its event queue is full",true);else reply_line("{\"queued\":true}");return;
    }
    unsigned status,d1,d2;
    if(sscanf(line,"player-midi %u %u %u %u %c",&gen,&status,&d1,&d2,&tail)==4) {
        uint8_t message[3]={(uint8_t)status,(uint8_t)d1,(uint8_t)d2};unsigned length=rnbo_s3_midi_length((uint8_t)status);
        if(gen!=atomic_load(&generation)||status>255||d1>127||d2>127||!length){error_reply("Invalid complete MIDI message or generation",true);return;}
        if(!player_midi_submit(PLAYER_MIDI_TEST,message,length))error_reply("MIDI needs a recompiled input patch, playing state and queue capacity",true);else reply_line("{\"queued\":true}");return;
    }
    error_reply("Unknown player command",true);
}
static void control_task(void *unused)
{
    (void)unused;char *line=heap_caps_malloc(LINE_BYTES,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);size_t used=0;bool overflow=false;int64_t last_usb_byte=0;
    if(!line){ESP_LOGE(TAG,"No USB command buffer");vTaskDelete(NULL);return;}
#ifdef RNBO_S3_WIFI
    bool radio_start_attempted=false;
#endif
    for(;;) {
        /* This owner also installs packages. Input drivers cannot run during
         * flash maintenance/rebinding, and the audio owner only sees mailboxes. */
        if(!atomic_load(&maintenance)){int64_t now=esp_timer_get_time();player_inputs_poll(now,physical_publish);player_midi_poll(now);}
        if(incoming.bytes&&esp_timer_get_time()-incoming.touched>30000000)discard_incoming();
#ifdef RNBO_S3_WIFI
        uint32_t session=used==0?player_network_poll_request(line,LINE_BYTES):0;
        if(session) {
            command_source=session;command(line);
            /* Allocation/encoding failure must complete an otherwise unanswered
             * slot too. An already answered slot treats this as a no-op. */
            (void)player_network_respond("{\"error\":\"Player could not return a reply; query status before retrying\"}");
            command_source=0;
            /* Poll only at a USB line boundary so the two streams cannot overwrite one another. */
        }
#endif
#ifdef CONFIG_RNBO_S3_USB_MIDI_HOST
        int c=EOF;
#else
        int c=getchar();
#endif
        if(c==EOF) {
            clearerr(stdin);
            if(used&&esp_timer_get_time()-last_usb_byte>2000000) {
                used=0;overflow=false;
                error_reply("Incomplete USB line timed out; resend the complete command",true);
            }
            if(incoming.bytes&&esp_timer_get_time()-incoming.touched>30000000)discard_incoming();
            if(boot_guard_pending) {
                player_stats s={0};xQueuePeek(telemetry,&s,0);
                if(s.generation==guard_generation && s.position>=guard_start_position+512 && !atomic_load(&paused) && !s.fault && !s.since.module_errors && !s.since.nonfinite && !s.since.overruns && !s.since.dma_errors && !s.since.write_errors && !s.since.queue_errors) {
                    char error[128];if(begin_maintenance(error,sizeof error)){(void)guard_write("");end_maintenance();}
                }
            }
#ifdef RNBO_S3_WIFI
            /* A radio startup failure must never blame a healthy native image's
             * recovery guard. Start only after actual image blocks clear it. */
            if(!radio_start_attempted&&!boot_guard_pending&&atomic_load(&audio_ready)) {
                char error[128];
                if(begin_maintenance(error,sizeof error)) {
                    radio_start_attempted=true;
                    (void)player_network_start_saved(error,sizeof error);
                    (void)end_maintenance();
                }
            }
#endif
            vTaskDelay(pdMS_TO_TICKS(2));continue;
        }
        last_usb_byte=esp_timer_get_time();
        if(c=='\r')continue;
        if(c=='\n') {line[used]=0;if(overflow){error_reply("Player command line exceeds limit",true);discard_incoming();}else command(line);used=0;overflow=false;continue;}
        if(c<32||c>126){overflow=true;continue;}
        if(used+1<LINE_BYTES)line[used++]=(char)c;else overflow=true;
    }
}
static void restore_boot(void)
{
    for(unsigned previous=0;previous<2;++previous) {
        uint8_t *bytes=NULL;size_t length=0;char error[192];
        if(!player_store_read(1,previous,&bytes,&length,error,sizeof error))continue;
        player_slot *s=load_slot(bytes,length,error,sizeof error);
        if(s && previous) {
            if(!player_store_promote_previous(1,s->package.package_sha256,error,sizeof error)){unload_slot(s);s=NULL;}
        }
        player_store_free(bytes);
        if(s){activate(s,true);return;}
        snprintf(boot_error,sizeof boot_error,"Boot package rejected: %.160s",error);
    }
    (void)guard_write("");
}
void app_main(void)
{
    setvbuf(stdin,NULL,_IONBF,0);setvbuf(stdout,NULL,_IONBF,0);
    ESP_LOGI(TAG,"Stable Main player v1; fixed44100/256, trusted zero-import native packages");
    char error[192];store_ready=player_store_init(error,sizeof error);
    if(!store_ready)snprintf(boot_error,sizeof boot_error,"%s",error);
    if(store_ready&&!guard_init()){store_ready=false;snprintf(boot_error,sizeof boot_error,"Player recovery metadata unavailable");}
    if(!player_midi_init(
#ifdef CONFIG_RNBO_S3_HEADLESS
        CONFIG_RNBO_S3_I2S_BCLK!=44&&CONFIG_RNBO_S3_I2S_WS!=44&&CONFIG_RNBO_S3_I2S_DOUT!=44,
#else
        false,
#endif
        error,sizeof error))ESP_LOGW(TAG,"MIDI: %s",error);
    events=xQueueCreate(EVENT_COUNT,sizeof(player_event));telemetry=xQueueCreate(1,sizeof(player_stats));
    StackType_t *audio_stack=heap_caps_malloc(AUDIO_STACK,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),*control_stack=heap_caps_malloc(CONTROL_STACK,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    if(!events||!telemetry||!audio_stack||!control_stack){ESP_LOGE(TAG,"Player task allocation failed");return;}
    ESP_ERROR_CHECK(board_audio_init(44100));
#ifndef CONFIG_RNBO_S3_HEADLESS
    board_display_actions actions={.panic=request_pause,.resume=request_resume,.volume=post_volume,.parameter=post_parameter,.parameter_value=read_display_parameter,.initial_volume=50,.source_label="RNBO Player"};
    ESP_ERROR_CHECK(board_display_start(&actions));
#endif
    if(store_ready)restore_boot();
#ifdef RNBO_S3_WIFI
    /* Startup may initialise radio/NVS before DMA exists. Later settings changes park DMA. */
    player_network_init();
#endif
    if(!player_usb_midi_start(error,sizeof error))ESP_LOGW(TAG,"USB MIDI host: %s",error);
    audio_handle=xTaskCreateStaticPinnedToCore(audio_task,"rnbo_player_audio",AUDIO_STACK,NULL,20,audio_stack,&audio_tcb,1);
    control_handle=xTaskCreateStaticPinnedToCore(control_task,"rnbo_player_usb",CONTROL_STACK,NULL,5,control_stack,&control_tcb,0);
    if(!audio_handle||!control_handle){ESP_LOGE(TAG,"Cannot start player tasks");return;}
    for(;;) {
#ifndef CONFIG_RNBO_S3_HEADLESS
        player_stats stats={0};xQueuePeek(telemetry,&stats,0);
        board_display_update(atomic_load(&paused)||!atomic_load(&active),stats.fault,atomic_load(&volume),stats.render_us,stats.peak_us,stats.output_peak);
#endif
        vTaskDelay(pdMS_TO_TICKS(40));
    }
}
