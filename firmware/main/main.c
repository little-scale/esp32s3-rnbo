/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Initial engine-neutral hardware shell; the default source is a test signal. */
#include "board_audio.h"
#include "pcm_output.h"
#include "output_meter.h"
#include "allocation_watch.h"
#include "audio_lifecycle.h"
#ifndef CONFIG_RNBO_S3_HEADLESS
#include "board_display.h"
#include "patch_layout.h"
#include "pcm_capture.h"
#include "esp_random.h"
static pcm_capture capture;
#endif
#include "esp_app_desc.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef RNBO_S3_STATIC_MODULE
#include "rnbo_s3_module.h"
static const rnbo_s3_module *module;
static void *module_context;
static rnbo_s3_parameter_info *parameter_schema;
static uint32_t parameter_count;
static float saved_parameters[RNBO_S3_MAX_PARAMETERS];
/* Only the audio owner calls the live instance. UI/USB read lock-free copies;
 * updates happen on parameter events, never on every sample or vector. */
static atomic_uint parameter_actual_bits[RNBO_S3_MAX_PARAMETERS];
static atomic_uint parameter_normalized_bits[RNBO_S3_MAX_PARAMETERS];
static void publish_parameter(void *context,unsigned index)
{
    float actual,normalized;unsigned a,n;
    if (module->parameter_value(context,index,&actual,&normalized)!=RNBO_S3_OK) return;
    memcpy(&a,&actual,sizeof a);memcpy(&n,&normalized,sizeof n);
    atomic_store_explicit(&parameter_actual_bits[index],a,memory_order_release);
    atomic_store_explicit(&parameter_normalized_bits[index],n,memory_order_release);
}
static bool read_parameter(unsigned index,float *actual,float *normalized)
{
    if (index>=parameter_count) return false;
    unsigned a=atomic_load_explicit(&parameter_actual_bits[index],memory_order_acquire);
    unsigned n=atomic_load_explicit(&parameter_normalized_bits[index],memory_order_acquire);
    memcpy(actual,&a,sizeof a);memcpy(normalized,&n,sizeof n);return true;
}
#define SOURCE_NAME "static-rnbo"
#else
#define SOURCE_NAME "engine-neutral-stereo-tone"
#endif
#ifndef RNBO_S3_MODULE_SOURCE_SHA256
#define RNBO_S3_MODULE_SOURCE_SHA256 "none"
#endif
#ifndef RNBO_S3_ARENA_BYTES
#define RNBO_S3_ARENA_BYTES (1024*1024)
#endif
#ifndef RNBO_S3_INITIAL_VOLUME
#define RNBO_S3_INITIAL_VOLUME 100
#endif

enum { AUDIO_STACK_BYTES=16384, CONTROL_STACK_BYTES=8192, EVENT_CAPACITY=32 };
typedef struct {
    unsigned kind, index, generation;
    float value;
    uint8_t midi[3], midi_length;
} control_event;
typedef struct {
    uint64_t frames, nonfinite, clipped, write_errors;
    /* All lifetime counters include muted/Panic zero vectors and failed sink
     * write attempts. Render elapsed time covers the owner loop through PCM;
     * it excludes the blocking driver call and post-write capture/statistics.
     * These sampled elapsed times are not a measured worst-case hard bound or
     * a complete audio-task CPU accounting profile. */
    uint64_t blocks, render_busy_total_us, render_deadline_overruns;
    uint64_t driver_elapsed_total_us, post_write_capture_elapsed_total_us;
    uint32_t render_us, peak_us, dma_errors, muted, volume, queue_errors;
    uint32_t output_peak_q15;
    uint32_t module_errors;
    uint32_t allocation_fault;
    allocation_watch_stats heap;
#ifdef RNBO_S3_STATIC_MODULE
    rnbo_s3_stats module_stats;
#endif
} audio_stats;
static audio_lifecycle lifecycle;
static atomic_uint queue_errors;
static atomic_uint volume_target=RNBO_S3_INITIAL_VOLUME;
/* Maximum final-PCM peak since the display last consumed it. No display or
 * floating logarithm work runs on the audio owner. */
#ifndef CONFIG_RNBO_S3_HEADLESS
static atomic_uint display_output_peak;
#endif
static QueueHandle_t controls, telemetry;
static StaticTask_t audio_tcb, control_tcb;
static TaskHandle_t audio_handle, control_handle, main_handle;
static const char *TAG="rnbo_s3";

static void request_panic(void)
{
    (void)audio_lifecycle_panic(&lifecycle);
}
static void request_resume(void)
{
    audio_lifecycle_resume(&lifecycle);
}
enum { CONTROL_POST_OK, CONTROL_POST_MUTED, CONTROL_POST_FULL };
static int post_control(control_event *event,bool panic_on_overflow)
{
    unsigned token=audio_lifecycle_token(&lifecycle);
    if ((token&1u) || audio_lifecycle_owner(&lifecycle)!=AUDIO_LIFECYCLE_AUDIO) return CONTROL_POST_MUTED;
    event->generation=token&~1u;
    if (xQueueSend(controls,event,0)==pdTRUE) return CONTROL_POST_OK;
    atomic_fetch_add_explicit(&queue_errors,1,memory_order_relaxed);
    /* MIDI events are never coalesced. A lost release/sustain-off cannot be
     * allowed to leave an audible voice held by queue congestion. */
    if (panic_on_overflow) request_panic();
    return CONTROL_POST_FULL;
}
static bool post_volume(unsigned percent)
{
    if (percent>100) return false;
    atomic_store_explicit(&volume_target,percent,memory_order_release);
    return true;
}
#ifdef RNBO_S3_STATIC_MODULE
static bool post_parameter(unsigned index,float normalized)
{
    if (index>=parameter_count || !isfinite(normalized) || normalized<0 || normalized>1) return false;
    control_event event={.kind=3,.index=index,.value=normalized};
    return post_control(&event,false)==CONTROL_POST_OK;
}
#endif
static void control_response(int result,bool midi)
{
    if (result==CONTROL_POST_OK) puts("{\"queued\":true}");
    else if (result==CONTROL_POST_MUTED) puts("{\"error\":\"module muted or rebuilding; Resume required\"}");
    else puts(midi?"{\"error\":\"MIDI queue full; Panic latched\"}":"{\"error\":\"control queue full\"}");
}

static void audio_task(void *unused)
{
    (void)unused;
    /* These arrays live on a deliberately internal-RAM task stack. */
    float left[RNBO_S3_BLOCK_FRAMES], right[RNBO_S3_BLOCK_FRAMES];
    int16_t pcm[RNBO_S3_BLOCK_FRAMES*BOARD_AUDIO_CHANNELS];
    pcm_output output;
    pcm_output_init(&output);
    audio_stats stats={.volume=RNBO_S3_INITIAL_VOLUME};
#ifndef RNBO_S3_STATIC_MODULE
    float phase_l=0.0f, phase_r=0.0f;
#else
    float *outputs[2]={left,right};
    uint64_t module_position=0;
#endif
    ESP_ERROR_CHECK(board_audio_start_dma());
    allocation_watch_start(ALLOCATION_WATCH_AUDIO);
    for (;;) {
        int64_t began=esp_timer_get_time();
        unsigned panic=audio_lifecycle_token(&lifecycle);
        if (panic&1u) {
            /* Panic does not depend on space in the ordinary control queue.
             * Discard stale controls before an explicit resume is accepted. */
            xQueueReset(controls);
            if (audio_lifecycle_owner(&lifecycle)==AUDIO_LIFECYCLE_AUDIO)
                allocation_watch_stop();
            (void)audio_lifecycle_park(&lifecycle,panic);
            if (audio_lifecycle_attach(&lifecycle)) {
#ifdef RNBO_S3_STATIC_MODULE
                module_position=0;
#else
                phase_l=phase_r=0.0f;
#endif
                allocation_watch_start(ALLOCATION_WATCH_AUDIO);
            }
        }
        bool owns_module=audio_lifecycle_owner(&lifecycle)==AUDIO_LIFECYCLE_AUDIO &&
                         !(audio_lifecycle_token(&lifecycle)&1u);
        control_event event;
        for (unsigned count=0;owns_module && count<EVENT_CAPACITY && xQueueReceive(controls,&event,0)==pdTRUE;++count) {
            unsigned current_panic=audio_lifecycle_token(&lifecycle);
            if ((current_panic&1u) || event.generation!=(current_panic&~1u)) continue;
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
            if (event.kind==4) {
                /* Explicit negative qualification: a user-requested ordinary
                 * heap allocation must be seen and fault the final sink. */
                void *probe=heap_caps_malloc(16,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
                heap_caps_free(probe);
            }
#endif
#ifdef RNBO_S3_STATIC_MODULE
            if (event.kind==2 || event.kind==3) {
                rnbo_s3_event e={.struct_bytes=sizeof e,
                    .kind=event.kind==2 ? RNBO_S3_PARAMETER_ACTUAL : RNBO_S3_PARAMETER_NORMALIZED,
                    .parameter_index=event.index,.value=event.value};
                if (module->event(module_context,&e)!=RNBO_S3_OK) ++stats.module_errors;
                else publish_parameter(module_context,event.index);
            }
            else if (event.kind==5) {
                rnbo_s3_event e={.struct_bytes=sizeof e,.kind=RNBO_S3_MIDI,
                    .midi_length=event.midi_length,.midi_port=0};
                memcpy(e.midi,event.midi,sizeof e.midi);
                if (module->event(module_context,&e)!=RNBO_S3_OK) ++stats.module_errors;
            }
#endif
        }
        stats.volume=atomic_load_explicit(&volume_target,memory_order_acquire);
        if (!owns_module) {
            memset(left,0,sizeof left);memset(right,0,sizeof right);
        } else {
#ifdef RNBO_S3_STATIC_MODULE
        if (module->process(module_context,NULL,outputs,RNBO_S3_BLOCK_FRAMES,module_position)!=RNBO_S3_OK) {
            memset(left,0,sizeof left);memset(right,0,sizeof right);
            request_panic();
            ++stats.module_errors;
        }
        module_position+=RNBO_S3_BLOCK_FRAMES;
#else
        for (unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {
            left[i]=0.125f*sinf(phase_l);
            right[i]=0.125f*sinf(phase_r);
            phase_l+=6.2831853071795864769f*440.0f/(float)RNBO_S3_SAMPLE_RATE;
            phase_r+=6.2831853071795864769f*660.0f/(float)RNBO_S3_SAMPLE_RATE;
            if (phase_l>=6.2831853071795864769f) phase_l-=6.2831853071795864769f;
            if (phase_r>=6.2831853071795864769f) phase_r-=6.2831853071795864769f;
        }
#endif
        }
        stats.heap=allocation_watch_snapshot(ALLOCATION_WATCH_AUDIO);
        if (stats.heap.allocations && !stats.allocation_fault) {
            stats.allocation_fault=1;
            request_panic();
        }
        stats.muted=(audio_lifecycle_token(&lifecycle)&1u) || !owns_module || stats.allocation_fault;
        /* Fixed 0.5 headroom is explicit and independent of 100% module volume.
         * The mono sink averages L/R once, at this final conversion boundary. */
        if (!pcm_output_render(&output,left,right,pcm,RNBO_S3_BLOCK_FRAMES,
                               BOARD_AUDIO_CHANNELS,stats.volume,0.5f,stats.muted))
            memset(pcm,0,sizeof pcm);
        stats.render_us=(uint32_t)(esp_timer_get_time()-began);
        stats.render_busy_total_us+=stats.render_us;
        /* Compare the exact nominal period, without rounding 256/44100 to an
         * integer number of microseconds. This counter excludes driver wait. */
        if ((uint64_t)stats.render_us*RNBO_S3_SAMPLE_RATE>
            (uint64_t)RNBO_S3_BLOCK_FRAMES*1000000u) ++stats.render_deadline_overruns;
        if (stats.render_us>stats.peak_us) stats.peak_us=stats.render_us;
        size_t written=0;
        int64_t driver_began=esp_timer_get_time();
        esp_err_t result=board_audio_write(pcm,RNBO_S3_BLOCK_FRAMES,&written);
        /* Wall time, including blocking I2S waits. The XIAO adapter also
         * performs its capture copy inside this call; this is not CPU time. */
        stats.driver_elapsed_total_us+=(uint64_t)(esp_timer_get_time()-driver_began);
#ifndef CONFIG_RNBO_S3_HEADLESS
        int64_t capture_began=esp_timer_get_time();
        if (result==ESP_OK && written==sizeof pcm) {
            pcm_capture_append(&capture,pcm,RNBO_S3_BLOCK_FRAMES);
            stats.output_peak_q15=output_meter_peak_q15(pcm,RNBO_S3_BLOCK_FRAMES*BOARD_AUDIO_CHANNELS);
            unsigned previous=atomic_load_explicit(&display_output_peak,memory_order_relaxed);
            while (stats.output_peak_q15>previous &&
                   !atomic_compare_exchange_weak_explicit(&display_output_peak,&previous,stats.output_peak_q15,
                                                         memory_order_relaxed,memory_order_relaxed)) {}
        } else stats.output_peak_q15=0;
        stats.post_write_capture_elapsed_total_us+=(uint64_t)(esp_timer_get_time()-capture_began);
#endif
        if (result!=ESP_OK || written!=sizeof pcm) {
            ++stats.write_errors;
            request_panic();
            /* A failing sink must not turn this high-priority loop into a spin. */
            vTaskDelay(pdMS_TO_TICKS(5));
        }
        /* Sink-side allocations are also detected; an already submitted DMA
         * buffer cannot be recalled, so the following vector is muted. */
        stats.heap=allocation_watch_snapshot(ALLOCATION_WATCH_AUDIO);
        if (stats.heap.allocations && !stats.allocation_fault) {
            stats.allocation_fault=1;
            request_panic();
        }
        stats.frames+=RNBO_S3_BLOCK_FRAMES;
        ++stats.blocks;
        stats.nonfinite=output.nonfinite;
        stats.clipped=output.clipped;
        stats.dma_errors=board_audio_dma_errors();
        stats.queue_errors=atomic_load_explicit(&queue_errors,memory_order_relaxed);
#ifdef RNBO_S3_STATIC_MODULE
        if (owns_module) {
            stats.module_stats.struct_bytes=sizeof stats.module_stats;
            (void)module->statistics(module_context,&stats.module_stats);
        }
#endif
        xQueueOverwrite(telemetry,&stats);
    }
}

static void put32(unsigned char *p, uint32_t value)
{
    for (unsigned i=0;i<4;++i) p[i]=(unsigned char)(value>>(8*i));
}

static int capture_command(const char *op,const unsigned char *payload,size_t bytes,char *out,size_t capacity)
{
#ifdef CONFIG_RNBO_S3_HEADLESS
    return board_audio_capture_command(op,payload,bytes,out,capacity);
#else
    if (!strcmp(op,"CAPBEGIN") && bytes==4) {
        uint32_t frames=(uint32_t)payload[0]|((uint32_t)payload[1]<<8)|((uint32_t)payload[2]<<16)|((uint32_t)payload[3]<<24),id;
        if (!pcm_capture_begin(&capture,frames,&id)) return 0;
        int count=snprintf(out,capacity,"{\"recording\":true,\"frames\":%" PRIu32 ",\"capture_id\":%" PRIu32 "}",frames,id);
        return count>0 && (size_t)count<capacity;
    }
    if (!strcmp(op,"CAPINFO") && !bytes) {
        pcm_capture_info info;
        if (!pcm_capture_snapshot(&capture,&info)) return 0;
        int count=snprintf(out,capacity,"{\"state\":%" PRIu32 ",\"frames\":%" PRIu32 ",\"requested\":%" PRIu32
            ",\"channels\":%" PRIu32 ",\"rate\":%" PRIu32 ",\"bytes\":%" PRIu32 ",\"capture_id\":%" PRIu32 ",\"max_chunk_bytes\":%u}",
            info.state,info.frames,info.requested,info.channels,info.rate,info.bytes,info.capture_id,BOARD_CAPTURE_CHUNK_BYTES);
        return count>0 && (size_t)count<capacity;
    }
    if (!strcmp(op,"CAPREAD") && bytes==10) {
        uint32_t id=0,offset=0;
        for (unsigned i=0;i<4;++i) { id|=(uint32_t)payload[i]<<(8*i);offset|=(uint32_t)payload[i+4]<<(8*i); }
        unsigned count=(unsigned)payload[8]|((unsigned)payload[9]<<8);
        unsigned char data[BOARD_CAPTURE_CHUNK_BYTES];
        if (capacity<count*2u+96u || !pcm_capture_read(&capture,id,offset,count,data,sizeof data)) return 0;
        int at=snprintf(out,capacity,"{\"offset\":%" PRIu32 ",\"capture_id\":%" PRIu32 ",\"data\":\"",offset,id);
        static const char hex[]="0123456789abcdef";
        if (at<=0 || (size_t)at>=capacity) return 0;
        for (unsigned i=0;i<count;++i) { out[at++]=hex[data[i]>>4];out[at++]=hex[data[i]&15]; }
        strcpy(out+at,"\"}");return 1;
    }
    return 0;
#endif
}

static void command(const char *line)
{
    audio_stats stats={0};
    (void)xQueuePeek(telemetry,&stats,0);
    if (!strcmp(line,"panic") || !strcmp(line,"!")) {
        request_panic();
        puts("{\"panic\":true}");
    } else if (!strcmp(line,"resume")) {
        request_resume();
        puts("{\"resume_requested\":true}");
    } else if (!strcmp(line,"status")) {
        const esp_app_desc_t *app=esp_app_get_description();
        char firmware_hash[65];
        static const char hex[]="0123456789abcdef";
        for (unsigned i=0;i<32;++i) {
            firmware_hash[i*2]=hex[app->app_elf_sha256[i]>>4];
            firmware_hash[i*2+1]=hex[app->app_elf_sha256[i]&15];
        }
        firmware_hash[64]=0;
        printf("{\"runtime\":\"rnbo-esp32s3-bringup\",\"board\":\"%s\",\"source\":\"%s\","
               "\"firmware_elf_sha256\":\"%s\",\"module_source_sha256\":\"" RNBO_S3_MODULE_SOURCE_SHA256 "\","
               "\"rate\":%u,\"block_frames\":%u,\"channels\":%u,\"frames\":%" PRIu64 ","
               "\"panic\":%s,\"volume\":%" PRIu32 ",\"render_us\":%" PRIu32 ",\"peak_us\":%" PRIu32 ","
               "\"nonfinite\":%" PRIu64 ",\"clipped\":%" PRIu64 ",\"write_errors\":%" PRIu64 ","
               "\"dma_errors\":%" PRIu32 ",\"queue_errors\":%" PRIu32 ",\"audio_stack_free\":%u,\"module_errors\":%" PRIu32 ","
               "\"audio_heap_allocations\":%" PRIu32 ",\"audio_heap_frees\":%" PRIu32 ",\"audio_heap_requested_bytes\":%" PRIu64 ",\"allocation_fault\":%s",
               BOARD_MODEL,SOURCE_NAME,firmware_hash,RNBO_S3_SAMPLE_RATE,RNBO_S3_BLOCK_FRAMES,BOARD_AUDIO_CHANNELS,stats.frames,
               stats.muted?"true":"false",stats.volume,stats.render_us,stats.peak_us,
               stats.nonfinite,stats.clipped,stats.write_errors,stats.dma_errors,stats.queue_errors,
               (unsigned)uxTaskGetStackHighWaterMark(audio_handle),stats.module_errors,
               stats.heap.allocations,stats.heap.frees,stats.heap.requested_bytes,stats.allocation_fault?"true":"false");
#ifndef CONFIG_RNBO_S3_HEADLESS
        printf(",\"output_peak_q15\":%" PRIu32 ",\"output_meter_scope\":\"final PCM after volume, routing and saturation\"",stats.output_peak_q15);
#endif
        printf(",\"blocks\":%" PRIu64 ",\"render_busy_total_us\":%" PRIu64 ",\"render_deadline_overruns\":%" PRIu64
               ",\"driver_elapsed_total_us\":%" PRIu64 ",\"post_write_capture_elapsed_total_us\":%" PRIu64
               ",\"render_timing_scope\":\"owner-through-PCM; excludes driver and post-write capture\"",
               stats.blocks,stats.render_busy_total_us,stats.render_deadline_overruns,
               stats.driver_elapsed_total_us,stats.post_write_capture_elapsed_total_us);
#ifdef CONFIG_RNBO_S3_HEADLESS
        printf(",\"driver_timing_scope\":\"wall time including I2S wait and internal capture\",\"post_write_capture_timed\":false");
#else
        printf(",\"driver_timing_scope\":\"wall time including I2S wait\",\"post_write_capture_timed\":true");
        printf(",\"visual_nodes\":%u,\"visual_segments\":%u,\"visual_source_sha256\":\"%s\"",
               (unsigned)rnbo_patch_layout.node_count,(unsigned)rnbo_patch_layout.segment_count,rnbo_patch_layout.source_sha256);
#endif
        /* Heap traversal and stack scans are diagnostics on the control task,
         * never work performed in the audio owner. Heap figures are current
         * snapshots; requested-byte accounting above is cumulative, not live. */
        printf(",\"internal_free_bytes\":%u,\"internal_largest_free_bytes\":%u,\"psram_free_bytes\":%u,\"psram_largest_free_bytes\":%u,"
               "\"control_stack_free\":%u,\"main_stack_free\":%u,\"uptime_us\":%" PRIu64,
               (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
               (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
               (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT),
               (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT),
               (unsigned)uxTaskGetStackHighWaterMark(control_handle),
               (unsigned)uxTaskGetStackHighWaterMark(main_handle),(uint64_t)esp_timer_get_time());
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
        printf(",\"heap_guard\":\"audio-task-successful-heap-operations\"");
#else
        printf(",\"heap_guard\":\"disabled\"");
#endif
        unsigned owner=audio_lifecycle_owner(&lifecycle);
        printf(",\"rebuilding\":%s,\"ready_to_resume\":%s,\"reconstruction_failed\":%s",
               owner==AUDIO_LIFECYCLE_PREPARING?"true":"false",owner==AUDIO_LIFECYCLE_READY?"true":"false",
               owner==AUDIO_LIFECYCLE_FAULT?"true":"false");
#ifdef RNBO_S3_STATIC_MODULE
        printf(",\"arena_used\":%" PRIu32 ",\"arena_capacity\":%" PRIu32 ",\"platform_allocations\":%" PRIu64
               ",\"late_platform_allocations\":%" PRIu64,
               stats.module_stats.arena_used,stats.module_stats.arena_capacity,
               stats.module_stats.platform_allocations,stats.module_stats.late_platform_allocations);
#endif
        puts("}");
#ifdef RNBO_S3_STATIC_MODULE
    } else if (!strcmp(line,"parameter-values")) {
        printf("{\"parameters\":[");
        for (unsigned i=0;i<parameter_count;++i) {
            float actual,normalized;read_parameter(i,&actual,&normalized);
            printf("%s{\"index\":%u,\"actual\":%.9g,\"normalized\":%.9g}",i?",":"",i,(double)actual,(double)normalized);
        }
        puts("]}");
    } else if (!strcmp(line,"parameters")) {
        /* Copied during detached preparation. The control task never calls the
         * live patch or retains generated/runtime-owned string pointers. */
        for (unsigned i=0;i<parameter_count;++i)
            printf("parameter %u id=%s name=%s unit=%s min=%g max=%g default=%g\n",i,
                   parameter_schema[i].id,parameter_schema[i].name,parameter_schema[i].unit,
                   parameter_schema[i].minimum,parameter_schema[i].maximum,parameter_schema[i].initial);
#endif
    } else {
        unsigned value; char trailing;
#ifdef CONFIG_RNBO_S3_ALLOCATION_WATCH
        if (!strcmp(line,"heap_probe")) {
            control_event event={.kind=4};
            int result=post_control(&event,false);
            if (result!=CONTROL_POST_OK) control_response(result,false);
            else puts("{\"queued\":true,\"expected_result\":\"allocation fault; reboot to recover\"}");
            return;
        }
#endif
        if (sscanf(line,"volume %u %c",&value,&trailing)==1 && value<=100) {
            (void)post_volume(value);
            printf("{\"volume\":%u,\"accepted\":true}\n",value);
            return;
        }
#ifdef RNBO_S3_STATIC_MODULE
        if (!strncmp(line,"midi ",5)) {
            int status=0;unsigned data1=0,data2=0;
            bool valid=false;
            if (sscanf(line+5,"%i",&status)==1 && status>=0x80 && status<0xf0) {
                unsigned kind=(unsigned)status&0xf0u;
                unsigned bytes=(kind==0xc0u || kind==0xd0u) ? 2u : 3u;
                int fields=bytes==2 ? sscanf(line+5,"%i %u %c",&status,&data1,&trailing) :
                                     sscanf(line+5,"%i %u %u %c",&status,&data1,&data2,&trailing);
                valid=fields==(int)bytes && data1<=127 && data2<=127;
                if (valid) {
                    control_event event={.kind=5,.midi={(uint8_t)status,(uint8_t)data1,(uint8_t)data2},.midi_length=(uint8_t)bytes};
                    control_response(post_control(&event,true),true);
                    return;
                }
            }
            puts("{\"error\":\"invalid complete channel MIDI message\"}");
            return;
        }
        float parameter;
        unsigned kind=0;
        if (sscanf(line,"param %u %f %c",&value,&parameter,&trailing)==2) kind=2;
        else if (sscanf(line,"normalized %u %f %c",&value,&parameter,&trailing)==2) kind=3;
        if (kind && value<parameter_count && isfinite(parameter)) {
            control_event event={.kind=kind,.index=value,.value=parameter};
            control_response(post_control(&event,false),false);
            return;
        }
#endif
        char out[BOARD_CAPTURE_CHUNK_BYTES*2+128];
        unsigned char payload[10];
        int ok=0;
        if (sscanf(line,"capture %u %c",&value,&trailing)==1) {
            put32(payload,value);
            ok=capture_command("CAPBEGIN",payload,4,out,sizeof out);
        } else if (!strcmp(line,"capinfo")) {
            ok=capture_command("CAPINFO",NULL,0,out,sizeof out);
        } else {
            unsigned id, offset, count;
            if (sscanf(line,"capread %u %u %u %c",&id,&offset,&count,&trailing)==3 && count<=BOARD_CAPTURE_CHUNK_BYTES) {
                put32(payload,id);put32(payload+4,offset);
                payload[8]=(unsigned char)count;payload[9]=(unsigned char)(count>>8);
                ok=capture_command("CAPREAD",payload,10,out,sizeof out);
            }
        }
        if (ok) { puts(out); return; }
        puts("{\"error\":\"invalid command or capture state\"}");
    }
}

static void control_task(void *unused)
{
    (void)unused;
    char line[128];unsigned at=0;bool overflow=false;
    for (;;) {
        int c=getchar();
        if (c==EOF) { clearerr(stdin);vTaskDelay(pdMS_TO_TICKS(10));continue; }
        if (c=='\r') continue;
        if (c=='\n') {
            if (overflow) puts("{\"error\":\"command too long\"}");
            else if (at) { line[at]=0; command(line); }
            at=0;overflow=false;fflush(stdout);
        } else if (at+1<sizeof line) line[at++]=(char)c;
        else overflow=true;
    }
}

static void maintenance_service(void)
{
    unsigned token;
    if (!audio_lifecycle_claim(&lifecycle,&token)) return;
    bool success=true;
#ifdef RNBO_S3_STATIC_MODULE
    /* PARKED is an acquire/release ownership transfer. Audio now writes zeros
     * and performs no callback, including statistics, on this context. */
    allocation_watch_start(ALLOCATION_WATCH_PREPARE);
    if (module_context) {
        for (unsigned i=0;i<parameter_count;++i) {
            float actual,normalized;
            if (module->parameter_value(module_context,i,&actual,&normalized)==RNBO_S3_OK)
                saved_parameters[i]=actual;
            else success=false;
        }
        module->destroy(module_context);
        module_context=NULL;
    }
    void *replacement=NULL;
    rnbo_s3_create_options options={.struct_bytes=sizeof options,.arena_bytes=RNBO_S3_ARENA_BYTES,
                                    .warmup_blocks=4,.seed=0x12345678};
    if (success && (module->create(&options,&replacement)!=RNBO_S3_OK ||
                    module->prepare(replacement)!=RNBO_S3_OK)) success=false;
    if (success && module->parameter_count(replacement)!=parameter_count) success=false;
    for (unsigned i=0;success && i<parameter_count;++i) {
        rnbo_s3_event event={.struct_bytes=sizeof event,.kind=RNBO_S3_PARAMETER_ACTUAL,
                             .parameter_index=i,.value=saved_parameters[i]};
        if (module->event(replacement,&event)!=RNBO_S3_OK) success=false;
        else publish_parameter(replacement,i);
    }
    if (success) module_context=replacement;
    else if (replacement) module->destroy(replacement);
    allocation_watch_stop();
#endif
    /* The context assignment, restored parameters and stopped PREPARE heap
     * watch all precede this release. Only the audio owner can attach it. */
    audio_lifecycle_ready(&lifecycle,token,success);
    if (success) ESP_LOGI(TAG,"Panic generation %u reconstructed; explicit Resume required",token);
    else ESP_LOGE(TAG,"Panic reconstruction failed; output remains silent");
}

void app_main(void)
{
    main_handle=xTaskGetCurrentTaskHandle();
    audio_lifecycle_init(&lifecycle);
    uint32_t flash_bytes=0;
    ESP_ERROR_CHECK(esp_flash_get_size(NULL,&flash_bytes));
    const esp_app_desc_t *app=esp_app_get_description();
    ESP_LOGI(TAG,"%s app=%s IDF=%s compiler=%s flash=%" PRIu32 " PSRAM=%u",
             BOARD_MODEL,app->project_name,esp_get_idf_version(),__VERSION__,flash_bytes,(unsigned)esp_psram_get_size());
    ESP_LOGI(TAG,"Source=%s: planar float32 44100/256 -> int16 %u channel(s), 0.5 headroom",SOURCE_NAME,BOARD_AUDIO_CHANNELS);
    ESP_LOGI(TAG,"Autostart; USB commands: status, volume 0..100, panic, resume");
    StackType_t *audio_stack=heap_caps_malloc(AUDIO_STACK_BYTES,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    StackType_t *control_stack=heap_caps_malloc(CONTROL_STACK_BYTES,MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    controls=xQueueCreate(EVENT_CAPACITY,sizeof(control_event));
    telemetry=xQueueCreate(1,sizeof(audio_stats));
    if (!audio_stack || !control_stack || !controls || !telemetry) {
        ESP_LOGE(TAG,"Shell resource allocation failed");return;
    }
#ifndef CONFIG_RNBO_S3_HEADLESS
    int16_t *capture_storage=heap_caps_malloc(RNBO_S3_SAMPLE_RATE*BOARD_AUDIO_CHANNELS*sizeof(int16_t),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if (!capture_storage || !pcm_capture_init(&capture,capture_storage,RNBO_S3_SAMPLE_RATE,BOARD_AUDIO_CHANNELS,RNBO_S3_SAMPLE_RATE,esp_random())) {
        ESP_LOGE(TAG,"Capture allocation failed");return;
    }
#endif
#ifdef RNBO_S3_STATIC_MODULE
    allocation_watch_start(ALLOCATION_WATCH_PREPARE);
    module=rnbo_s3_static_module();
    if (!module || module->struct_bytes<sizeof *module || module->abi_major!=RNBO_S3_ABI_MAJOR ||
        module->pointer_bits!=32 || module->sample_rate!=RNBO_S3_SAMPLE_RATE ||
        module->block_frames!=RNBO_S3_BLOCK_FRAMES || module->role!=RNBO_S3_MAIN ||
        module->audio_inputs!=0 || module->audio_outputs!=2) {
        allocation_watch_stop();ESP_LOGE(TAG,"Static module ABI/profile mismatch");return;
    }
    rnbo_s3_create_options options={.struct_bytes=sizeof options,.arena_bytes=RNBO_S3_ARENA_BYTES,
                                    .warmup_blocks=4,.seed=0x12345678};
    if (module->create(&options,&module_context)!=RNBO_S3_OK || module->prepare(module_context)!=RNBO_S3_OK) {
        ESP_LOGE(TAG,"Static RNBO preparation failed");
        if (module_context) module->destroy(module_context);
        allocation_watch_stop();
        return;
    }
    parameter_count=module->parameter_count(module_context);
    if (parameter_count) {
        parameter_schema=heap_caps_calloc(parameter_count,sizeof *parameter_schema,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        if (!parameter_schema) { module->destroy(module_context);allocation_watch_stop();return; }
        for (unsigned i=0;i<parameter_count;++i) {
            parameter_schema[i].struct_bytes=sizeof *parameter_schema;
            if (module->parameter_info(module_context,i,&parameter_schema[i])!=RNBO_S3_OK) {
                module->destroy(module_context);allocation_watch_stop();return;
            }
            float normalized;
            if (module->parameter_value(module_context,i,&saved_parameters[i],&normalized)!=RNBO_S3_OK) {
                module->destroy(module_context);allocation_watch_stop();return;
            }
            publish_parameter(module_context,i);
        }
    }
    ESP_LOGI(TAG,"Static RNBO ready: parameters=%" PRIu32 ", warmup=4, deterministic seed, one image/instance",parameter_count);
    allocation_watch_stop();
    allocation_watch_stats prepared_heap=allocation_watch_snapshot(ALLOCATION_WATCH_PREPARE);
    ESP_LOGI(TAG,"Detached successful heap requests=%" PRIu32 " bytes=%" PRIu64 " internal=%" PRIu64 " external=%" PRIu64,
             prepared_heap.allocations,prepared_heap.requested_bytes,prepared_heap.internal_bytes,prepared_heap.external_bytes);
#endif
#ifndef CONFIG_RNBO_S3_HEADLESS
    board_display_actions display_actions={.panic=request_panic,.resume=request_resume,.volume=post_volume,
        .initial_volume=RNBO_S3_INITIAL_VOLUME,
#ifdef RNBO_S3_STATIC_MODULE
        .source_label="RNBO instrument",
        .parameter=post_parameter,.parameter_value=read_parameter,
#else
        .source_label="Stereo audio test tones",
#endif
    };
    esp_err_t display_result=board_display_start(&display_actions);
    if (display_result!=ESP_OK) ESP_LOGE(TAG,"Display startup failed: %s; USB controls retained",esp_err_to_name(display_result));
#endif
    ESP_ERROR_CHECK(board_audio_init(RNBO_S3_SAMPLE_RATE));
    audio_handle=xTaskCreateStaticPinnedToCore(audio_task,"audio",AUDIO_STACK_BYTES,NULL,20,audio_stack,&audio_tcb,1);
    control_handle=xTaskCreateStaticPinnedToCore(control_task,"controls",CONTROL_STACK_BYTES,NULL,3,control_stack,&control_tcb,0);
    configASSERT(audio_handle && control_handle);
    TickType_t last_display=xTaskGetTickCount();
    for (;;) {
        maintenance_service();
#ifndef CONFIG_RNBO_S3_HEADLESS
        audio_stats stats;
        if (xTaskGetTickCount()-last_display>=pdMS_TO_TICKS(50) && xQueuePeek(telemetry,&stats,0)==pdTRUE) {
            last_display=xTaskGetTickCount();
            bool fault=stats.allocation_fault || stats.write_errors || audio_lifecycle_owner(&lifecycle)==AUDIO_LIFECYCLE_FAULT;
            unsigned output_peak=atomic_exchange_explicit(&display_output_peak,0,memory_order_relaxed);
            board_display_update(stats.muted,fault,stats.volume,stats.render_us,stats.peak_us,output_peak);
        }
#else
        (void)last_display;
#endif
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
