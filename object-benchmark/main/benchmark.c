/* SPDX-License-Identifier: MIT */
/* Offline object comparisons: timers exclude input generation, output analysis,
 * event dispatch and detached preparation. These observations are not bounds
 * on an instrument with I2S, display, networking or other application tasks. */
#include "module_host.h"
#include "bench_check.h"
#include "allocation_probe.h"
#include "stimulus.h"
#include "average_oracle.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef struct { uint32_t block,index,kind;float value; } bench_event;
typedef struct { const char *name;uint32_t event_begin,event_count; } bench_case;
typedef struct { const char *id;float minimum,maximum,initial,exponent;uint32_t steps; } bench_parameter;
typedef struct { uint32_t kind,window,initial_available;double maximum_error; } bench_verification;
#include "bench_config.h"

extern const uint8_t strict_start[] asm("_binary_object_strict_payload_bin_start");
extern const uint8_t strict_end[] asm("_binary_object_strict_payload_bin_end");
extern const uint8_t optimized_start[] asm("_binary_object_optimized_payload_bin_start");
extern const uint8_t optimized_end[] asm("_binary_object_optimized_payload_bin_end");
static StackType_t worker_stack[24576/sizeof(StackType_t)];
static StaticTask_t worker_task;

typedef struct {
    uint64_t blocks,timed_blocks,process_us,event_us,events,prepare_us;
    uint32_t peak_us,arena_high_water,context_bytes,code_bytes,cpp_new_calls,total_arena_allocations;
    uint64_t samples,clipped;
    double square_sum,peak;
} profile_metrics;
typedef struct { uint64_t samples,pcm_different;uint32_t max_pcm_lsb;double max_abs,error_square_sum; } compare_metrics;
static profile_metrics profiles[2];
static int64_t benchmark_started;
static compare_metrics aggregate;
typedef struct { uint64_t samples;double max_abs; } semantic_metrics;
static float *reference,*work,*stimulus_cache,*oracle_cache;
static const bench_verification *active_verification;
static double oracle_rounding_error;
static uint32_t oracle_rechecks;
static uint64_t semantic_sample_checks;
static const object_stimulus *active_stimulus;
static uint32_t input_rechecks;
static uint64_t pilot_sample_checks;
static float *inputs[2],*outputs[2];

static void digest_hex(const uint8_t *bytes,size_t count,char result[65])
{
    uint8_t digest[32];CHECK(mbedtls_sha256(bytes,count,digest,0)==0);
    for (unsigned i=0;i<32;++i) sprintf(result+2*i,"%02x",digest[i]);
    result[64]=0;
}
static int16_t pcm(float value)
{
    float scaled=value*0.5f;
    if (scaled>1) scaled=1;else if(scaled< -1) scaled=-1;
    return (int16_t)lrintf(scaled*32767.0f);
}
static void verify_parameters(object_image *image)
{
    CHECK(image->module.parameter_count(image->context)==BENCH_PARAMETER_COUNT);
    (void)bench_parameters;
#if BENCH_PARAMETER_COUNT > 0
    for (uint32_t i=0;i<BENCH_PARAMETER_COUNT;++i) {
        rnbo_s3_parameter_info info={.struct_bytes=sizeof info};
        CHECK(image->module.parameter_info(image->context,i,&info)==RNBO_S3_OK);
        CHECK(info.index==i && !strcmp(info.id,bench_parameters[i].id));
        CHECK(info.minimum==bench_parameters[i].minimum && info.maximum==bench_parameters[i].maximum);
        CHECK(info.initial==bench_parameters[i].initial && info.exponent==bench_parameters[i].exponent && info.steps==bench_parameters[i].steps);
    }
#endif
}
static void prepare_stimulus(unsigned test,char fingerprint[65],char oracle_sha[65])
{
    active_verification=&bench_verifications[test];strcpy(oracle_sha,"none");oracle_rounding_error=0;
    if(BENCH_ROLE!=RNBO_S3_FX){strcpy(fingerprint,"none");return;}
    active_stimulus=&bench_stimuli[test];
    for(unsigned block=0;block<BENCH_BLOCKS;++block) {
        CHECK(object_stimulus_fill(active_stimulus,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,stimulus_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES));
        if((block&31u)==31u){CHECK(esp_timer_get_time()-benchmark_started<550000000);vTaskDelay(1);}
    }
    digest_hex((const uint8_t*)stimulus_cache,(size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),fingerprint);
    if(active_verification->kind){
        CHECK(BENCH_HAS_ORACLE && oracle_cache && active_verification->kind==1);
        for(unsigned block=0;block<BENCH_BLOCKS;++block){
            CHECK(object_average_oracle_fill(stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,active_verification->window,active_verification->initial_available,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,&oracle_rounding_error));
            if((block&31u)==31u){CHECK(esp_timer_get_time()-benchmark_started<550000000);vTaskDelay(1);}
        }
        CHECK(oracle_rounding_error<=0x1p-24);
        digest_hex((const uint8_t*)oracle_cache,(size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),oracle_sha);
    }
}
static void excitation(uint32_t block)
{
    for(uint32_t i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {
        size_t offset=((size_t)block*RNBO_S3_BLOCK_FRAMES+i)*2u;
        inputs[0][i]=stimulus_cache[offset];inputs[1][i]=stimulus_cache[offset+1u];
    }
}
static void verify_stimulus(const char *expected,const char *oracle_sha)
{
    if(BENCH_ROLE!=RNBO_S3_FX)return;
    char actual[65];digest_hex((const uint8_t*)stimulus_cache,(size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),actual);
    CHECK(!strcmp(actual,expected));++input_rechecks;
    if(active_verification->kind){
        digest_hex((const uint8_t*)oracle_cache,(size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),actual);
        CHECK(!strcmp(actual,oracle_sha));++oracle_rechecks;
    }
}
static void dispatch(object_image *image,const bench_case *test,uint32_t block,profile_metrics *metrics)
{
    for (uint32_t i=0;i<test->event_count;++i) {
        const bench_event *source=&bench_events[test->event_begin+i];if(source->block!=block)continue;
        rnbo_s3_event event={.struct_bytes=sizeof event,.kind=source->kind,.parameter_index=source->index,.value=source->value};
        allocation_probe_begin();int64_t began=esp_timer_get_time();
        int result=image->module.event(image->context,&event);
        uint64_t elapsed=(uint64_t)(esp_timer_get_time()-began);allocation_probe_end();
        CHECK(result==RNBO_S3_OK);metrics->event_us+=elapsed;++metrics->events;
    }
}
static void step(object_image *image,uint32_t block,profile_metrics *metrics,bool measured)
{
    if (BENCH_ROLE==RNBO_S3_FX) excitation(block);
    for (unsigned c=0;c<2;++c) for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) outputs[c][i]=NAN;
    allocation_probe_begin();int64_t began=esp_timer_get_time();
    int result=image->module.process(image->context,BENCH_ROLE==RNBO_S3_FX?(const float *const*)inputs:NULL,outputs,RNBO_S3_BLOCK_FRAMES,image->position);
    uint64_t elapsed=(uint64_t)(esp_timer_get_time()-began);allocation_probe_end();
    CHECK(result==RNBO_S3_OK);image->position+=RNBO_S3_BLOCK_FRAMES;
    ++metrics->blocks;
    if (measured && block>=BENCH_TIMING_EXCLUDE) {
        ++metrics->timed_blocks;metrics->process_us+=elapsed;
        if(elapsed>metrics->peak_us)metrics->peak_us=(uint32_t)elapsed;
    }
    for (unsigned c=0;c<2;++c) for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)CHECK(isfinite(outputs[c][i]));
}
static void collect(object_image *image,profile_metrics *metrics)
{
    rnbo_s3_stats base;rnbo_s3_dynamic_stats extra;object_image_statistics(image,&base,&extra);
    CHECK(base.warmup_blocks==BENCH_WARMUP && base.blocks==image->position/RNBO_S3_BLOCK_FRAMES);
    if(extra.arena_high_water>metrics->arena_high_water)metrics->arena_high_water=extra.arena_high_water;
    if(extra.cpp_new_calls>metrics->cpp_new_calls)metrics->cpp_new_calls=(uint32_t)extra.cpp_new_calls;
    if(extra.total_arena_allocations>metrics->total_arena_allocations)metrics->total_arena_allocations=(uint32_t)extra.total_arena_allocations;
    metrics->context_bytes=image->info.context_bytes;metrics->code_bytes=image->elf.sec[ELF_SEC_TEXT].size;
}
static void load_pair(object_image images[2])
{
    object_image_load(&images[0],strict_start,(size_t)(strict_end-strict_start),BENCH_ROLE,BENCH_ARENA_BYTES);
    object_image_load(&images[1],optimized_start,(size_t)(optimized_end-optimized_start),BENCH_ROLE,BENCH_ARENA_BYTES);
}
static void prewarm(void)
{
    object_image images[2];load_pair(images);
    for (unsigned p=0;p<2;++p) {
        profile_metrics ignored={0};object_image_prepare(&images[p],BENCH_WARMUP,BENCH_SEED);verify_parameters(&images[p]);
        for(unsigned b=0;b<2;++b){dispatch(&images[p],&bench_cases[0],b,&ignored);step(&images[p],b,&ignored,false);}
        collect(&images[p],&ignored);object_image_destroy_context(&images[p]);object_image_unload(&images[p]);
    }
}
static void run_pass(object_image *image,unsigned profile,const bench_case *test,bool save,compare_metrics *comparison,double squares[2],profile_metrics *metrics,semantic_metrics *semantic)
{
    int64_t began=esp_timer_get_time();
    object_image_prepare(image,BENCH_WARMUP,BENCH_SEED);metrics->prepare_us+=(uint64_t)(esp_timer_get_time()-began);
    verify_parameters(image);
    for(uint32_t b=0;b<BENCH_BLOCKS;++b) {
        dispatch(image,test,b,metrics);step(image,b,metrics,true);
        if(BENCH_ROLE==RNBO_S3_FX && !active_verification->kind) {
            CHECK(active_stimulus->kind>=OBJECT_STIMULUS_MIDI && active_stimulus->kind<=OBJECT_STIMULUS_RESON);
            unsigned observed=active_stimulus->kind==OBJECT_STIMULUS_FREQUENCY?1u:0u;
            unsigned source=active_stimulus->kind==OBJECT_STIMULUS_RESON?0u:1u;
            for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i){CHECK(outputs[observed][i]==inputs[source][i]);++pilot_sample_checks;}
        }
        for(unsigned c=0;c<2;++c)for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {
            size_t offset=((size_t)b*2u+c)*RNBO_S3_BLOCK_FRAMES+i;
            float actual=outputs[c][i];double value=actual;
            if(active_verification->kind){
                size_t expected_offset=((size_t)b*RNBO_S3_BLOCK_FRAMES+i)*2u+c;
                double error=fabs(value-(double)oracle_cache[expected_offset]);
                if(error>semantic->max_abs)semantic->max_abs=error;
                ++semantic->samples;++semantic_sample_checks;
            }
            ++metrics->samples;metrics->square_sum+=value*value;squares[profile]+=value*value;
            if(fabs(value)>metrics->peak)metrics->peak=fabs(value);
            if(fabs(value*0.5)>1)++metrics->clipped;
            if(save)reference[offset]=actual;
            else {
                double difference=value-(double)reference[offset];double absolute=fabs(difference);
                if(absolute>comparison->max_abs)comparison->max_abs=absolute;
                comparison->error_square_sum+=difference*difference;++comparison->samples;
                int delta=(int)pcm(actual)-(int)pcm(reference[offset]);if(delta<0)delta= -delta;
                if(delta){++comparison->pcm_different;if((uint32_t)delta>comparison->max_pcm_lsb)comparison->max_pcm_lsb=(uint32_t)delta;}
            }
        }
        /* Yield outside the process timer/probe so the offline tight loop does
         * not starve the idle watchdog. This is not an audio scheduling test. */
        if((b&31u)==31u){CHECK(esp_timer_get_time()-benchmark_started<550000000);vTaskDelay(1);}
    }
    collect(image,metrics);object_image_destroy_context(image);
}
static void worker(void *unused)
{
    (void)unused;benchmark_started=esp_timer_get_time();char strict_sha[65],optimized_sha[65],firmware_sha[65];
    digest_hex(strict_start,(size_t)(strict_end-strict_start),strict_sha);
    digest_hex(optimized_start,(size_t)(optimized_end-optimized_start),optimized_sha);
    CHECK(!strcmp(strict_sha,BENCH_STRICT_SHA256)&&!strcmp(optimized_sha,BENCH_OPTIMIZED_SHA256));
    const esp_app_desc_t *app=esp_app_get_description();
    for(unsigned i=0;i<32;++i)sprintf(firmware_sha+2*i,"%02x",app->app_elf_sha256[i]);
    firmware_sha[64]=0;
    /* Settle newlib stream/dtoa caches before leak baselines. Formatting remains
     * outside timed/heap-observed module callbacks throughout the benchmark. */
    char formatted[192];
    CHECK(snprintf(formatted,sizeof formatted,"%.9g %.9g %.9g %.9g",1.0/3.0,1.401298464324817e-45,3.4028234663852886e38,1.0e-12)>0);
    CHECK(snprintf(formatted,sizeof formatted,"%.17g %.17g %.17g %.17g",1.0/3.0,1.401298464324817e-45,3.4028234663852886e38,1.0e-12)>0);
    printf("RNBO_OBJECT_BENCHMARK START fixture=%s firmware_elf_sha256=%s strict_module_sha256=%s optimized_module_sha256=%s\n",BENCH_FIXTURE,firmware_sha,strict_sha,optimized_sha);fflush(stdout);
    printf("RNBO_OBJECT_BENCHMARK NUMERICAL_PROFILES fixture=%s reference=%s candidate=%s\n",BENCH_FIXTURE,BENCH_REFERENCE_PROFILE,BENCH_CANDIDATE_PROFILE);fflush(stdout);
    /* All workspace/output buffers persist across both heap baseline snapshots. */
    reference=heap_caps_malloc((size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    work=heap_caps_malloc(4u*RNBO_S3_BLOCK_FRAMES*sizeof(float),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);CHECK(reference&&work);
    inputs[0]=work;inputs[1]=work+RNBO_S3_BLOCK_FRAMES;outputs[0]=work+2u*RNBO_S3_BLOCK_FRAMES;outputs[1]=work+3u*RNBO_S3_BLOCK_FRAMES;
    if(BENCH_ROLE==RNBO_S3_FX) {
        stimulus_cache=heap_caps_malloc((size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        CHECK(stimulus_cache);
    }
    if(BENCH_HAS_ORACLE){
        oracle_cache=heap_caps_malloc((size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
        CHECK(oracle_cache);
    }
    char initial_input_sha[65],initial_oracle_sha[65];prepare_stimulus(0,initial_input_sha,initial_oracle_sha);
    prewarm();CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());CHECK(heap_caps_check_integrity_all(true));
    size_t psram_before=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),internal_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    object_image images[2];load_pair(images);
    for(unsigned c=0;c<BENCH_CASE_COUNT;++c) {
        compare_metrics comparison={0};double squares[2]={0};profile_metrics current[2]={{0}};semantic_metrics semantic[2]={{0}};
        char input_sha[65],oracle_sha[65];prepare_stimulus(c,input_sha,oracle_sha);
        if(BENCH_ROLE==RNBO_S3_FX) {
            printf("RNBO_OBJECT_BENCHMARK INPUT fixture=%s case=%s input_sha256=%s input_bytes=%u layout=float32_stereo_interleaved_le stimulus_kind=%"PRIu32"\n",BENCH_FIXTURE,bench_cases[c].name,input_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_stimulus->kind);fflush(stdout);
        }
        if(active_verification->kind){
            printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=average-window-v1 window=%"PRIu32" initial_available=%"PRIu32" max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=fresh-float64-window-sum rounding=once-float32\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->window,active_verification->initial_available,active_verification->maximum_error,oracle_rounding_error);fflush(stdout);
        }
        for(unsigned round=0;round<BENCH_ROUNDS;++round) {
            unsigned first=round&1u;
            verify_stimulus(input_sha,oracle_sha);
            run_pass(&images[first],first,&bench_cases[c],true,&comparison,squares,&current[first],&semantic[first]);
            verify_stimulus(input_sha,oracle_sha);
            run_pass(&images[first^1u],first^1u,&bench_cases[c],false,&comparison,squares,&current[first^1u],&semantic[first^1u]);
            verify_stimulus(input_sha,oracle_sha);
        }
        double relative=squares[0]>0?fabs(sqrt(squares[1]/squares[0])-1.0):(squares[1]==0?0:INFINITY);
        printf("RNBO_OBJECT_BENCHMARK CASE fixture=%s case=%s samples=%"PRIu64" max_abs=%.9g rms_error=%.9g relative_rms=%.9g pcm_different=%"PRIu64" max_pcm_lsb=%"PRIu32"\n",BENCH_FIXTURE,bench_cases[c].name,comparison.samples,comparison.max_abs,sqrt(comparison.error_square_sum/(double)comparison.samples),relative,comparison.pcm_different,comparison.max_pcm_lsb);fflush(stdout);
        if(active_verification->kind){
            for(unsigned p=0;p<2;++p){
                double bound=semantic[p].max_abs+oracle_rounding_error;
                printf("RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture=%s case=%s profile=%s semantic_kind=average-window-v1 samples=%"PRIu64" max_abs=%.17g max_model_error_bound=%.17g max_abs_tolerance=%.17g oracle_sha256=%s\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",semantic[p].samples,semantic[p].max_abs,bound,active_verification->maximum_error,oracle_sha);fflush(stdout);
                CHECK(bound<=active_verification->maximum_error);
            }
        }
        CHECK(comparison.max_abs<=BENCH_MAX_ABS && comparison.max_pcm_lsb<=BENCH_MAX_PCM_LSB && relative<=BENCH_MAX_RELATIVE_RMS);
        for(unsigned p=0;p<2;++p) {
            profile_metrics *m=&current[p],*total=&profiles[p];
            printf("RNBO_OBJECT_BENCHMARK CASE_PROFILE fixture=%s case=%s profile=%s timed_blocks=%"PRIu64" process_us=%"PRIu64" peak_us=%"PRIu32" event_us=%"PRIu64" prepare_us=%"PRIu64" rms=%.9g peak=%.9g arena_high_water=%"PRIu32"\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",m->timed_blocks,m->process_us,m->peak_us,m->event_us,m->prepare_us,sqrt(m->square_sum/(double)m->samples),m->peak,m->arena_high_water);
            total->blocks+=m->blocks;total->timed_blocks+=m->timed_blocks;total->process_us+=m->process_us;total->event_us+=m->event_us;total->events+=m->events;total->prepare_us+=m->prepare_us;total->samples+=m->samples;total->clipped+=m->clipped;total->square_sum+=m->square_sum;
            if(m->peak_us>total->peak_us)total->peak_us=m->peak_us;
            if(m->peak>total->peak)total->peak=m->peak;
            if(m->arena_high_water>total->arena_high_water)total->arena_high_water=m->arena_high_water;
            if(m->cpp_new_calls>total->cpp_new_calls)total->cpp_new_calls=m->cpp_new_calls;
            if(m->total_arena_allocations>total->total_arena_allocations)total->total_arena_allocations=m->total_arena_allocations;
            total->context_bytes=m->context_bytes;total->code_bytes=m->code_bytes;
        }
        aggregate.samples+=comparison.samples;aggregate.pcm_different+=comparison.pcm_different;aggregate.error_square_sum+=comparison.error_square_sum;
        if(comparison.max_abs>aggregate.max_abs)aggregate.max_abs=comparison.max_abs;
        if(comparison.max_pcm_lsb>aggregate.max_pcm_lsb)aggregate.max_pcm_lsb=comparison.max_pcm_lsb;
    }
    for(unsigned p=0;p<2;++p)object_image_unload(&images[p]);
    CHECK(heap_caps_check_integrity_all(true));size_t psram_after=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),internal_after=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    CHECK(psram_after==psram_before && internal_after>=internal_before);
    CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());
    for(unsigned p=0;p<2;++p) {
        profile_metrics *m=&profiles[p];
        printf("RNBO_OBJECT_BENCHMARK PROFILE fixture=%s profile=%s blocks=%"PRIu64" timed_blocks=%"PRIu64" process_us=%"PRIu64" peak_us=%"PRIu32" event_us=%"PRIu64" events=%"PRIu64" prepare_us=%"PRIu64" rms=%.9g peak=%.9g clipped=%"PRIu64" context_bytes=%"PRIu32" arena_capacity=%u arena_high_water=%"PRIu32" code_bytes=%"PRIu32" max_cpp_new_calls=%"PRIu32" max_arena_requests=%"PRIu32"\n",BENCH_FIXTURE,p?"optimized":"strict",m->blocks,m->timed_blocks,m->process_us,m->peak_us,m->event_us,m->events,m->prepare_us,sqrt(m->square_sum/(double)m->samples),m->peak,m->clipped,m->context_bytes,BENCH_ARENA_BYTES,m->arena_high_water,m->code_bytes,m->cpp_new_calls,m->total_arena_allocations);
    }
    printf("RNBO_OBJECT_BENCHMARK PASS fixture=%s firmware_elf_sha256=%s strict_module_sha256=%s optimized_module_sha256=%s cases=%u rounds=%u blocks_per_pass=%u warmup=%u seed=%u timing_exclude=%u compared_samples=%"PRIu64" max_abs=%.9g rms_error=%.9g pcm_different=%"PRIu64" max_pcm_lsb=%"PRIu32" max_abs_tolerance=%.9g max_pcm_lsb_tolerance=%u relative_rms_tolerance=%.9g strict_timed_blocks=%"PRIu64" strict_process_us=%"PRIu64" strict_peak_us=%"PRIu32" optimized_timed_blocks=%"PRIu64" optimized_process_us=%"PRIu64" optimized_peak_us=%"PRIu32" psram_before=%u psram_after=%u internal_before=%u internal_after=%u host_heap_allocations=%"PRIu32" host_heap_frees=%"PRIu32" local_late_allocations=0 images=4 finalized_images=4 input_cases=%u input_rechecks=%"PRIu32" pilot_sample_checks=%"PRIu64" oracle_cases=%u oracle_rechecks=%"PRIu32" semantic_sample_checks=%"PRIu64" stack_margin=%u scope=offline_no_i2s_ui_network\n",BENCH_FIXTURE,firmware_sha,strict_sha,optimized_sha,BENCH_CASE_COUNT,BENCH_ROUNDS,BENCH_BLOCKS,BENCH_WARMUP,BENCH_SEED,BENCH_TIMING_EXCLUDE,aggregate.samples,aggregate.max_abs,sqrt(aggregate.error_square_sum/(double)aggregate.samples),aggregate.pcm_different,aggregate.max_pcm_lsb,(double)BENCH_MAX_ABS,BENCH_MAX_PCM_LSB,(double)BENCH_MAX_RELATIVE_RMS,profiles[0].timed_blocks,profiles[0].process_us,profiles[0].peak_us,profiles[1].timed_blocks,profiles[1].process_us,profiles[1].peak_us,(unsigned)psram_before,(unsigned)psram_after,(unsigned)internal_before,(unsigned)internal_after,allocation_probe_allocations(),allocation_probe_frees(),BENCH_ROLE==RNBO_S3_FX?BENCH_CASE_COUNT:0u,input_rechecks,pilot_sample_checks,BENCH_HAS_ORACLE?BENCH_CASE_COUNT:0u,oracle_rechecks,semantic_sample_checks,(unsigned)uxTaskGetStackHighWaterMark(NULL));fflush(stdout);
    heap_caps_free(oracle_cache);heap_caps_free(stimulus_cache);heap_caps_free(reference);heap_caps_free(work);vTaskDelete(NULL);
}
void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(2000));
    CHECK(xTaskCreateStaticPinnedToCore(worker,"object_bench",sizeof worker_stack,NULL,5,worker_stack,&worker_task,1));
}
