/* SPDX-License-Identifier: MIT */
/* Offline object comparisons: timers exclude input generation, output analysis,
 * event dispatch and detached preparation. These observations are not bounds
 * on an instrument with I2S, display, networking or other application tasks. */
#include "module_host.h"
#include "bench_check.h"
#include "allocation_probe.h"
#include "stimulus.h"
#include "average_oracle.h"
#include "wave2_oracle.h"
#include "wave4_oracle.h"
#include "gen_history_oracle.h"
#include "gen_arithmetic_oracle.h"
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
typedef struct { uint32_t kind,window,initial_available;double maximum_error;double coefficients[5];double exponent; } bench_verification;
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
typedef struct { uint64_t samples,pcm_different;uint32_t max_pcm_lsb;double max_abs,error_square_sum;uint64_t float_bit_different,zero_sign_different; } compare_metrics;
static profile_metrics profiles[2];
static int64_t benchmark_started;
static compare_metrics aggregate;
typedef struct { uint64_t samples;double max_abs;uint64_t bit_different,zero_sign_different,observer_samples,observer_bit_different;uint64_t witness_samples,witness_differences;double witness_max_abs; } semantic_metrics;
static float *reference,*work,*stimulus_cache,*oracle_cache;
static const bench_verification *active_verification;
static double oracle_rounding_error;
static uint32_t oracle_rechecks;
static uint64_t semantic_sample_checks;
static uint64_t oracle_bit_sample_checks,oracle_bit_differences;
static uint64_t dc_sample_checks;
static uint64_t wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences;
static uint64_t observer_bit_sample_checks,observer_bit_differences;
static uint64_t gen_arith_bit_sample_checks,gen_arith_bit_differences,gen_arith_zero_sign_differences;
static double dc_expected;
static const object_stimulus *active_stimulus;
static uint32_t input_rechecks;
static uint64_t pilot_sample_checks;
static char event_schedule_sha[65],reset_witness_sha[65];
static uint8_t reset_witness_mask[64];
static uint32_t reset_witness_count;
static uint64_t gen_reset_events,gen_reset_witness_events,gen_reset_witness_sample_checks,gen_reset_witness_differences;
static float *inputs[2],*outputs[2];

static const char *verification_name(uint32_t kind)
{
    switch(kind){
    case 1:return "average-window-v1";
    case OBJECT_WAVE2_BIQUAD:return "biquad-response-v1";
    case OBJECT_WAVE2_NONLINEAR:return "nonlinear-chain-v1";
    case OBJECT_WAVE2_WRAP_FINITE:return "wrap-finite-v1";
    case OBJECT_WAVE2_POWER_MODES:return "nonlinear-power-modes-v1";
    case OBJECT_WAVE4_KIND:return "wave4-mathematical-v1";
    case OBJECT_GEN_HISTORY_KIND:return "gen-history-v1";
    case OBJECT_GEN_ARITH_KIND:return "gen-arithmetic-v1";
    default:CHECK(false);return "invalid";
    }
}

static void digest_hex(const uint8_t *bytes,size_t count,char result[65])
{
    uint8_t digest[32];CHECK(mbedtls_sha256(bytes,count,digest,0)==0);
    for (unsigned i=0;i<32;++i) sprintf(result+2*i,"%02x",digest[i]);
    result[64]=0;
}
static void put_u32le(uint8_t *out,uint32_t value)
{for(unsigned n=0;n<4;++n)out[n]=(uint8_t)(value>>(n*8u));}
static void power_schedule_fingerprint(const bench_case *test)
{
    /* Canonical wire bytes, never C structure padding: initial Float32 bits,
     * count, then block/index/kind/Float32-value for each actual event. */
    CHECK(test->event_count<=16u);
    uint8_t bytes[8u+16u*16u];float initial=(float)active_verification->exponent;uint32_t bits;
    __builtin_memcpy(&bits,&initial,4);put_u32le(bytes,bits);put_u32le(bytes+4,test->event_count);
    for(uint32_t n=0;n<test->event_count;++n){
        const bench_event *event=&bench_events[test->event_begin+n];uint8_t *p=bytes+8u+16u*n;
        CHECK(event->kind==1u && event->index==0u && event->block<BENCH_BLOCKS && isfinite(event->value) && event->value>=.25f && event->value<=4.f);
        if(n)CHECK(bench_events[test->event_begin+n-1u].block<event->block);
        __builtin_memcpy(&bits,&event->value,4);
        put_u32le(p,event->block);put_u32le(p+4,event->index);put_u32le(p+8,event->kind);put_u32le(p+12,bits);
    }
    digest_hex(bytes,8u+16u*test->event_count,event_schedule_sha);
}
static void gen_schedule_fingerprint(const bench_case *test,unsigned case_index)
{
    CHECK(case_index<3u && test->event_count==(case_index==0?0u:case_index==1?6u:64u));
    static const uint32_t boundaries[]={1,2,7,31,32,63};
    uint8_t bytes[8u+64u*16u];put_u32le(bytes,0);put_u32le(bytes+4,test->event_count);
    for(uint32_t n=0;n<test->event_count;++n){
        const bench_event *event=&bench_events[test->event_begin+n];uint8_t *p=bytes+8u+16u*n;uint32_t bits;
        CHECK(event->kind==1u && event->index==0u && event->value==1.f && event->block==(case_index==1?boundaries[n]:n));
        __builtin_memcpy(&bits,&event->value,4);
        put_u32le(p,event->block);put_u32le(p+4,event->index);put_u32le(p+8,event->kind);put_u32le(p+12,bits);
    }
    digest_hex(bytes,8u+16u*test->event_count,event_schedule_sha);
}
static int16_t pcm(float value)
{
    float scaled=value*(active_verification->kind==OBJECT_GEN_HISTORY_KIND?.25f:.5f);
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
    active_verification=&bench_verifications[test];strcpy(oracle_sha,"none");strcpy(event_schedule_sha,"none");strcpy(reset_witness_sha,"none");memset(reset_witness_mask,0,sizeof reset_witness_mask);reset_witness_count=0;oracle_rounding_error=0;dc_expected=0;
    CHECK(active_verification->kind<=OBJECT_GEN_ARITH_KIND);
    CHECK(!active_verification->kind || BENCH_ROLE==RNBO_S3_FX);
    if(BENCH_ROLE!=RNBO_S3_FX){strcpy(fingerprint,"none");return;}
    active_stimulus=&bench_stimuli[test];
    for(unsigned block=0;block<BENCH_BLOCKS;++block) {
        CHECK(object_stimulus_fill(active_stimulus,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,stimulus_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES));
        if((block&31u)==31u){CHECK(esp_timer_get_time()-benchmark_started<550000000);vTaskDelay(1);}
    }
    digest_hex((const uint8_t*)stimulus_cache,(size_t)BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*sizeof(float),fingerprint);
    if(active_verification->kind){
        CHECK(BENCH_HAS_ORACLE && oracle_cache);
        object_wave2_oracle model;
        object_wave4_oracle wave4;
        object_gen_history_oracle gen;
        if(active_verification->kind==OBJECT_GEN_ARITH_KIND){
            CHECK(BENCH_GEN_ARITH && BENCH_BLOCKS==64 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==3 && BENCH_PARAMETER_COUNT==0);
            CHECK(!strcmp(BENCH_STRICT_SHA256,BENCH_OPTIMIZED_SHA256));
            CHECK(active_stimulus->kind==OBJECT_STIMULUS_WAVE4_GRID+test && bench_cases[test].event_count==0);
            CHECK(active_verification->initial_available==0 && active_verification->maximum_error==0 && active_verification->exponent==0);
            for(unsigned i=0;i<5;++i)CHECK(active_verification->coefficients[i]==0);
            CHECK(object_gen_arithmetic_model(active_verification->window));
        }else if(active_verification->kind==OBJECT_GEN_HISTORY_KIND){
            CHECK(BENCH_GEN_HISTORY && BENCH_BLOCKS==64 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==3 && BENCH_PARAMETER_COUNT==1);
            CHECK(BENCH_GEN_FEEDBACK_F32?strcmp(BENCH_STRICT_SHA256,BENCH_OPTIMIZED_SHA256)!=0:!strcmp(BENCH_STRICT_SHA256,BENCH_OPTIMIZED_SHA256));
            if(BENCH_GEN_FEEDBACK_F32)CHECK(active_verification->window==OBJECT_GEN_HISTORY_FEEDBACK && BENCH_MAX_ABS==2e-6 && BENCH_MAX_PCM_LSB==1 && BENCH_MAX_RELATIVE_RMS==1e-4);
            CHECK(active_stimulus->kind==OBJECT_STIMULUS_GEN_HISTORY && active_verification->initial_available==0 && active_verification->maximum_error==2e-6 && active_verification->exponent==0);
            for(unsigned i=0;i<5;++i)CHECK(active_verification->coefficients[i]==0);
            CHECK(object_gen_history_oracle_init(&gen,active_verification->window,BENCH_WARMUP));
            gen_schedule_fingerprint(&bench_cases[test],test);
        }else if(active_verification->kind==OBJECT_WAVE4_KIND){
            CHECK(BENCH_WAVE4 && BENCH_BLOCKS==64 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==3 && BENCH_PARAMETER_COUNT==0);
            CHECK(!strcmp(BENCH_STRICT_SHA256,BENCH_OPTIMIZED_SHA256));
            CHECK(active_stimulus->kind==OBJECT_STIMULUS_WAVE4_GRID+test && bench_cases[test].event_count==0);
            CHECK(active_verification->initial_available==0 && active_verification->maximum_error==0 && active_verification->exponent==0);
            for(unsigned i=0;i<5;++i)CHECK(active_verification->coefficients[i]==0);
            CHECK(object_wave4_oracle_init(&wave4,active_verification->window,BENCH_WARMUP));
        }else if(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE){
            CHECK(BENCH_BLOCKS==512 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==4 && BENCH_PARAMETER_COUNT==0);
            CHECK(!strcmp(BENCH_STRICT_SHA256,BENCH_OPTIMIZED_SHA256));
            CHECK(active_stimulus->kind==OBJECT_STIMULUS_WRAP_BOUNDARIES+test && bench_cases[test].event_count==0);
            CHECK(active_verification->window==0 && active_verification->initial_available==0 && active_verification->maximum_error==0 && active_verification->exponent==0);
            for(unsigned i=0;i<5;++i)CHECK(active_verification->coefficients[i]==0);
        }else if(active_verification->kind==OBJECT_WAVE2_POWER_MODES){
            CHECK(BENCH_BLOCKS==512 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==15 && BENCH_PARAMETER_COUNT==1);
            CHECK(active_stimulus->kind==(test<3?OBJECT_STIMULUS_NONLINEAR_GRID:OBJECT_STIMULUS_NONLINEAR_DENSE));
            CHECK(active_verification->window==0 && active_verification->initial_available==0 && active_verification->maximum_error==2e-6 && active_verification->exponent==2);
            for(unsigned i=0;i<5;++i)CHECK(active_verification->coefficients[i]==0);
            CHECK(object_wave2_oracle_init(&model,active_verification->kind,active_verification->coefficients,active_verification->exponent,BENCH_WARMUP));
            power_schedule_fingerprint(&bench_cases[test]);
        }else if(active_verification->kind!=1){
            CHECK(BENCH_BLOCKS==512 && BENCH_WARMUP==4 && BENCH_SEED==0x12345678u && BENCH_CASE_COUNT==3);
            for(uint32_t i=0;i<bench_cases[test].event_count;++i)
                CHECK(bench_events[bench_cases[test].event_begin+i].block==0);
            CHECK(active_verification->window==0 && active_verification->initial_available==0);
            CHECK(active_verification->maximum_error==(active_verification->kind==OBJECT_WAVE2_BIQUAD?3e-6:2e-6));
            CHECK(active_stimulus->kind==(active_verification->kind==OBJECT_WAVE2_BIQUAD?OBJECT_STIMULUS_IMPULSE_STEP:OBJECT_STIMULUS_NONLINEAR_GRID));
            CHECK(object_wave2_oracle_init(&model,active_verification->kind,active_verification->coefficients,active_verification->exponent,BENCH_WARMUP));
            if(active_verification->kind==OBJECT_WAVE2_BIQUAD){
                double gain;CHECK(object_wave2_biquad_dc_gain(&model,&gain));
                dc_expected=-0.125*gain;
            }
        }
        for(unsigned block=0;block<BENCH_BLOCKS;++block){
            if(active_verification->kind==OBJECT_WAVE2_POWER_MODES){
                const bench_case *source=&bench_cases[test];
                for(uint32_t n=0;n<source->event_count;++n){
                    const bench_event *event=&bench_events[source->event_begin+n];
                    if(event->block==block)CHECK(object_wave2_oracle_set_exponent(&model,event->value));
                }
            }
            if(active_verification->kind==OBJECT_GEN_ARITH_KIND){
                CHECK(object_gen_arithmetic_oracle_fill(active_verification->window,stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,2u*RNBO_S3_BLOCK_FRAMES));
            }else if(active_verification->kind==OBJECT_GEN_HISTORY_KIND){
                const bench_case *source=&bench_cases[test];
                for(uint32_t n=0;n<source->event_count;++n){
                    const bench_event *event=&bench_events[source->event_begin+n];
                    if(event->block==block){
                        bool observable=false;
                        CHECK(object_gen_history_oracle_reset_witness(&gen,stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,&observable));
                        reset_witness_mask[block]=(uint8_t)observable;reset_witness_count+=observable;
                        CHECK(object_gen_history_oracle_reset(&gen,block*RNBO_S3_BLOCK_FRAMES));
                    }
                }
                CHECK(object_gen_history_oracle_fill(&gen,stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,2u*RNBO_S3_BLOCK_FRAMES,&oracle_rounding_error));
            }else if(active_verification->kind==OBJECT_WAVE4_KIND){
                CHECK(object_wave4_oracle_fill(&wave4,stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,2u*RNBO_S3_BLOCK_FRAMES));
            }else if(active_verification->kind==1){
                CHECK(object_average_oracle_fill(stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,active_verification->window,active_verification->initial_available,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,&oracle_rounding_error));
            }else if(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE){
                CHECK(object_wrap_finite_oracle_fill(stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,2u*RNBO_S3_BLOCK_FRAMES));
            }else{
                CHECK(object_wave2_oracle_fill(&model,stimulus_cache,BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES,block*RNBO_S3_BLOCK_FRAMES,RNBO_S3_BLOCK_FRAMES,oracle_cache+(size_t)block*2u*RNBO_S3_BLOCK_FRAMES,2u*RNBO_S3_BLOCK_FRAMES,&oracle_rounding_error));
            }
            if((block&31u)==31u){CHECK(esp_timer_get_time()-benchmark_started<550000000);vTaskDelay(1);}
        }
        if(active_verification->kind==OBJECT_GEN_HISTORY_KIND)
            digest_hex(reset_witness_mask,sizeof reset_witness_mask,reset_witness_sha);
        CHECK(oracle_rounding_error<=0x1p-24);
        if(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE || active_verification->kind==OBJECT_WAVE4_KIND || active_verification->kind==OBJECT_GEN_ARITH_KIND)CHECK(oracle_rounding_error==0);
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
static void run_pass(object_image *image,unsigned profile,const bench_case *test,bool save,compare_metrics *comparison,double squares[2],profile_metrics *metrics,semantic_metrics *semantic,semantic_metrics *dc)
{
    int64_t began=esp_timer_get_time();
    object_image_prepare(image,BENCH_WARMUP,BENCH_SEED);metrics->prepare_us+=(uint64_t)(esp_timer_get_time()-began);
    verify_parameters(image);
    double final_right_sum=0;
    for(uint32_t b=0;b<BENCH_BLOCKS;++b) {
        dispatch(image,test,b,metrics);step(image,b,metrics,true);
        /* Match the native oracle's final1024-sample right-channel mean.
         * Output analysis is outside the timed/heap-observed callback. */
        if(active_verification->kind==OBJECT_WAVE2_BIQUAD && b>=BENCH_BLOCKS-4u)
            for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)final_right_sum+=(double)outputs[1][i];
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
                if(active_verification->kind==OBJECT_GEN_HISTORY_KIND && reset_witness_mask[b] && i==0u){
                    ++semantic->witness_samples;
                    if(error>semantic->witness_max_abs)semantic->witness_max_abs=error;
                    if(error>active_verification->maximum_error)++semantic->witness_differences;
                }
                if(active_verification->kind==OBJECT_GEN_ARITH_KIND){
                    uint32_t actual_word,expected_word;
                    __builtin_memcpy(&actual_word,&actual,4);__builtin_memcpy(&expected_word,oracle_cache+expected_offset,4);
                    bool different=actual_word!=expected_word;
                    bool zero_sign=different && (actual_word&0x7fffffffu)==0 && (expected_word&0x7fffffffu)==0;
                    ++gen_arith_bit_sample_checks;semantic->bit_different+=different;gen_arith_bit_differences+=different;
                    semantic->zero_sign_different+=zero_sign;gen_arith_zero_sign_differences+=zero_sign;
                }
                if(active_verification->kind==OBJECT_WAVE4_KIND){
                    uint32_t actual_word,expected_word;
                    __builtin_memcpy(&actual_word,&actual,4);__builtin_memcpy(&expected_word,oracle_cache+expected_offset,4);
                    ++wave4_bit_sample_checks;
                    bool different=actual_word!=expected_word;
                    bool zero_sign=different && (actual_word&0x7fffffffu)==0 && (expected_word&0x7fffffffu)==0;
                    semantic->bit_different+=different;wave4_bit_differences+=different;
                    semantic->zero_sign_different+=zero_sign;wave4_zero_sign_differences+=zero_sign;
                    if(active_verification->window==OBJECT_WAVE4_DELTA && c==1u){
                        ++semantic->observer_samples;++observer_bit_sample_checks;
                        semantic->observer_bit_different+=different;observer_bit_differences+=different;
                    }
                }
                if(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE){
                    uint32_t actual_word,expected_word;
                    __builtin_memcpy(&actual_word,&actual,sizeof actual_word);
                    __builtin_memcpy(&expected_word,oracle_cache+expected_offset,sizeof expected_word);
                    ++oracle_bit_sample_checks;
                    if(actual_word!=expected_word){++semantic->bit_different;++oracle_bit_differences;}
                }
            }
            ++metrics->samples;metrics->square_sum+=value*value;squares[profile]+=value*value;
            if(fabs(value)>metrics->peak)metrics->peak=fabs(value);
            if(fabs(value*(active_verification->kind==OBJECT_GEN_HISTORY_KIND?.25:.5))>1)++metrics->clipped;
            if(save)reference[offset]=actual;
            else {
                if(active_verification->kind==OBJECT_WAVE2_POWER_MODES || active_verification->kind==OBJECT_WAVE4_KIND || active_verification->kind==OBJECT_GEN_HISTORY_KIND || active_verification->kind==OBJECT_GEN_ARITH_KIND){
                    uint32_t actual_word,reference_word;
                    __builtin_memcpy(&actual_word,&actual,4);__builtin_memcpy(&reference_word,reference+offset,4);
                    if(actual_word!=reference_word){
                        ++comparison->float_bit_different;
                        if((actual_word&0x7fffffffu)==0 && (reference_word&0x7fffffffu)==0)++comparison->zero_sign_different;
                    }
                }
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
    if(active_verification->kind==OBJECT_WAVE2_BIQUAD){
        double error=fabs(final_right_sum/1024.0-dc_expected);
        if(error>dc->max_abs)dc->max_abs=error;
        ++dc->samples;++dc_sample_checks;
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
        compare_metrics comparison={0};double squares[2]={0};profile_metrics current[2]={{0}};semantic_metrics semantic[2]={{0}},dc[2]={{0}};
        char input_sha[65],oracle_sha[65];prepare_stimulus(c,input_sha,oracle_sha);
        if(BENCH_ROLE==RNBO_S3_FX) {
            printf("RNBO_OBJECT_BENCHMARK INPUT fixture=%s case=%s input_sha256=%s input_bytes=%u layout=float32_stereo_interleaved_le stimulus_kind=%"PRIu32"\n",BENCH_FIXTURE,bench_cases[c].name,input_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_stimulus->kind);fflush(stdout);
        }
        if(active_verification->kind){
            if(active_verification->kind==OBJECT_GEN_ARITH_KIND){
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=gen-arithmetic-v1 model_code=%"PRIu32" observer_channel=2 max_abs_tolerance=0 max_cache_rounding_error=0 model=independent-binary32-operations rounding=once-binary32-per-output-operation\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->window);
            }else if(active_verification->kind==OBJECT_GEN_HISTORY_KIND){
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=gen-history-v1 model_code=%"PRIu32" initial_epoch_frames=-1024 event_schedule_sha256=%s reset_witness_sha256=%s witness_minimum_separation=%.17g model_tail_bound=%.17g model_evaluation_bound=%.17g max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=fresh-float64-input-convolution-or-integer-cycle rounding=once-float32\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->window,event_schedule_sha,reset_witness_sha,8e-6,object_gen_history_oracle_tail_bound(active_verification->window),object_gen_history_oracle_evaluation_bound(active_verification->window),active_verification->maximum_error,oracle_rounding_error);
            }else if(active_verification->kind==1){
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=average-window-v1 window=%"PRIu32" initial_available=%"PRIu32" max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=fresh-float64-window-sum rounding=once-float32\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->window,active_verification->initial_available,active_verification->maximum_error,oracle_rounding_error);
            }else if(active_verification->kind==OBJECT_WAVE2_BIQUAD){
                const double *a=active_verification->coefficients;
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=biquad-response-v1 max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=fresh-float64-difference-equation rounding=once-float32 a0=%.17g a1=%.17g a2=%.17g b1=%.17g b2=%.17g\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->maximum_error,oracle_rounding_error,a[0],a[1],a[2],a[3],a[4]);
            }else if(active_verification->kind==OBJECT_WAVE2_NONLINEAR){
                CHECK(active_verification->kind==OBJECT_WAVE2_NONLINEAR);
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=nonlinear-chain-v1 max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=float64-tanh-wrap-clip-pow rounding=once-float32 exponent=%.17g\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->maximum_error,oracle_rounding_error,active_verification->exponent);
            }else if(active_verification->kind==OBJECT_WAVE2_POWER_MODES){
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=nonlinear-power-modes-v1 max_abs_tolerance=%.17g max_cache_rounding_error=%.17g model=float64-tanh-wrap-clip-pow-events-v1 rounding=once-float32 initial_exponent=%.17g event_schedule_sha256=%s\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->maximum_error,oracle_rounding_error,active_verification->exponent,event_schedule_sha);
            }else if(active_verification->kind==OBJECT_WAVE4_KIND){
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=wave4-mathematical-v1 model_code=%"PRIu32" observer_channel=%u max_abs_tolerance=0 max_cache_rounding_error=0 model=independent-binary32-operations-and-input-history rounding=once-binary32-per-output-operation\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float),active_verification->window,active_verification->window==OBJECT_WAVE4_DELTA?1u:2u);
            }else{
                CHECK(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE);
                printf("RNBO_OBJECT_BENCHMARK ORACLE fixture=%s case=%s oracle_sha256=%s oracle_bytes=%u layout=float32_stereo_interleaved_le oracle_kind=wrap-finite-v1 max_abs_tolerance=0 max_cache_rounding_error=0 model=exact-binary32-modulo2 rounding=exact-binary32\n",BENCH_FIXTURE,bench_cases[c].name,oracle_sha,BENCH_BLOCKS*2u*RNBO_S3_BLOCK_FRAMES*(unsigned)sizeof(float));
            }
            fflush(stdout);
        }
        for(unsigned round=0;round<BENCH_ROUNDS;++round) {
            unsigned first=round&1u;
            verify_stimulus(input_sha,oracle_sha);
            run_pass(&images[first],first,&bench_cases[c],true,&comparison,squares,&current[first],&semantic[first],&dc[first]);
            verify_stimulus(input_sha,oracle_sha);
            run_pass(&images[first^1u],first^1u,&bench_cases[c],false,&comparison,squares,&current[first^1u],&semantic[first^1u],&dc[first^1u]);
            verify_stimulus(input_sha,oracle_sha);
        }
        double relative=squares[0]>0?fabs(sqrt(squares[1]/squares[0])-1.0):(squares[1]==0?0:INFINITY);
        printf("RNBO_OBJECT_BENCHMARK CASE fixture=%s case=%s samples=%"PRIu64" max_abs=%.9g rms_error=%.9g relative_rms=%.9g pcm_different=%"PRIu64" max_pcm_lsb=%"PRIu32"\n",BENCH_FIXTURE,bench_cases[c].name,comparison.samples,comparison.max_abs,sqrt(comparison.error_square_sum/(double)comparison.samples),relative,comparison.pcm_different,comparison.max_pcm_lsb);fflush(stdout);
        if(active_verification->kind==OBJECT_WAVE2_POWER_MODES || active_verification->kind==OBJECT_WAVE4_KIND || active_verification->kind==OBJECT_GEN_HISTORY_KIND || active_verification->kind==OBJECT_GEN_ARITH_KIND){
            printf("RNBO_OBJECT_BENCHMARK CASE_ROUNDING fixture=%s case=%s samples=%"PRIu64" float_bit_different=%"PRIu64" zero_sign_different=%"PRIu64"\n",BENCH_FIXTURE,bench_cases[c].name,comparison.samples,comparison.float_bit_different,comparison.zero_sign_different);fflush(stdout);
            CHECK(comparison.zero_sign_different<=comparison.float_bit_different && comparison.float_bit_different<=comparison.samples);
            if(active_verification->kind==OBJECT_WAVE4_KIND || active_verification->kind==OBJECT_GEN_ARITH_KIND || (active_verification->kind==OBJECT_GEN_HISTORY_KIND && !BENCH_GEN_FEEDBACK_F32))CHECK(comparison.float_bit_different==0);
        }
        if(active_verification->kind){
            for(unsigned p=0;p<2;++p){
                double bound=semantic[p].max_abs+oracle_rounding_error;
                if(active_verification->kind==OBJECT_GEN_HISTORY_KIND){
                    bound+=object_gen_history_oracle_tail_bound(active_verification->window);
                    bound+=object_gen_history_oracle_evaluation_bound(active_verification->window);
                }
                printf("RNBO_OBJECT_BENCHMARK CASE_SEMANTIC fixture=%s case=%s profile=%s semantic_kind=%s samples=%"PRIu64" max_abs=%.17g max_model_error_bound=%.17g max_abs_tolerance=%.17g oracle_sha256=%s\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",verification_name(active_verification->kind),semantic[p].samples,semantic[p].max_abs,bound,active_verification->maximum_error,oracle_sha);fflush(stdout);
                CHECK(bound<=active_verification->maximum_error);
                if(active_verification->kind==OBJECT_GEN_HISTORY_KIND){
                    uint64_t witnesses=(uint64_t)reset_witness_count*BENCH_ROUNDS;
                    CHECK(current[p].events==(uint64_t)bench_cases[c].event_count*BENCH_ROUNDS);
                    CHECK(semantic[p].witness_samples==2u*witnesses && !semantic[p].witness_differences && semantic[p].witness_max_abs<=active_verification->maximum_error);
                    printf("RNBO_OBJECT_BENCHMARK CASE_GEN_RESET fixture=%s case=%s profile=%s oracle_sha256=%s event_schedule_sha256=%s reset_witness_sha256=%s reset_events=%"PRIu64" witness_events=%"PRIu64" witness_sample_checks=%"PRIu64" witness_differences=%"PRIu64" max_abs=%.17g max_abs_tolerance=%.17g\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",oracle_sha,event_schedule_sha,reset_witness_sha,current[p].events,witnesses,semantic[p].witness_samples,semantic[p].witness_differences,semantic[p].witness_max_abs,active_verification->maximum_error);
                    gen_reset_events+=current[p].events;gen_reset_witness_events+=witnesses;
                    gen_reset_witness_sample_checks+=semantic[p].witness_samples;gen_reset_witness_differences+=semantic[p].witness_differences;
                }
                if(active_verification->kind==OBJECT_GEN_ARITH_KIND){
                    printf("RNBO_OBJECT_BENCHMARK CASE_GEN_ARITH_BITS fixture=%s case=%s profile=%s oracle_sha256=%s samples=%"PRIu64" bit_different=%"PRIu64" zero_sign_different=%"PRIu64"\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",oracle_sha,semantic[p].samples,semantic[p].bit_different,semantic[p].zero_sign_different);fflush(stdout);
                    CHECK(semantic[p].bit_different==semantic[p].zero_sign_different && semantic[p].bit_different<=semantic[p].samples);
                }
                if(active_verification->kind==OBJECT_WAVE4_KIND){
                    printf("RNBO_OBJECT_BENCHMARK CASE_WAVE4_BITS fixture=%s case=%s profile=%s oracle_sha256=%s samples=%"PRIu64" bit_different=%"PRIu64" zero_sign_different=%"PRIu64" observer_samples=%"PRIu64" observer_bit_different=%"PRIu64"\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",oracle_sha,semantic[p].samples,semantic[p].bit_different,semantic[p].zero_sign_different,semantic[p].observer_samples,semantic[p].observer_bit_different);fflush(stdout);
                    CHECK(semantic[p].bit_different==semantic[p].zero_sign_different && semantic[p].observer_bit_different==0);
                    CHECK(semantic[p].observer_samples==(active_verification->window==OBJECT_WAVE4_DELTA?(uint64_t)BENCH_ROUNDS*BENCH_BLOCKS*RNBO_S3_BLOCK_FRAMES:0));
                }
                if(active_verification->kind==OBJECT_WAVE2_WRAP_FINITE){
                    printf("RNBO_OBJECT_BENCHMARK CASE_BITS fixture=%s case=%s profile=%s oracle_sha256=%s samples=%"PRIu64" bit_different=%"PRIu64"\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",oracle_sha,semantic[p].samples,semantic[p].bit_different);fflush(stdout);
                    CHECK(semantic[p].bit_different==0);
                }
                if(active_verification->kind==OBJECT_WAVE2_BIQUAD){
                    printf("RNBO_OBJECT_BENCHMARK CASE_DC fixture=%s case=%s profile=%s oracle_sha256=%s expected=%.17g max_abs=%.17g samples=%"PRIu64" mean_frames=1024 max_abs_tolerance=%.17g\n",BENCH_FIXTURE,bench_cases[c].name,p?"optimized":"strict",oracle_sha,dc_expected,dc[p].max_abs,dc[p].samples,3e-6);fflush(stdout);
                    CHECK(dc[p].samples==BENCH_ROUNDS && dc[p].max_abs<=3e-6);
                }
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
    printf("RNBO_OBJECT_BENCHMARK PASS fixture=%s firmware_elf_sha256=%s strict_module_sha256=%s optimized_module_sha256=%s cases=%u rounds=%u blocks_per_pass=%u warmup=%u seed=%u timing_exclude=%u compared_samples=%"PRIu64" max_abs=%.9g rms_error=%.9g pcm_different=%"PRIu64" max_pcm_lsb=%"PRIu32" max_abs_tolerance=%.9g max_pcm_lsb_tolerance=%u relative_rms_tolerance=%.9g strict_timed_blocks=%"PRIu64" strict_process_us=%"PRIu64" strict_peak_us=%"PRIu32" optimized_timed_blocks=%"PRIu64" optimized_process_us=%"PRIu64" optimized_peak_us=%"PRIu32" psram_before=%u psram_after=%u internal_before=%u internal_after=%u host_heap_allocations=%"PRIu32" host_heap_frees=%"PRIu32" local_late_allocations=0 images=4 finalized_images=4 input_cases=%u input_rechecks=%"PRIu32" pilot_sample_checks=%"PRIu64" oracle_cases=%u oracle_rechecks=%"PRIu32" semantic_sample_checks=%"PRIu64" dc_sample_checks=%"PRIu64" oracle_bit_sample_checks=%"PRIu64" oracle_bit_differences=%"PRIu64" stack_margin=%u scope=offline_no_i2s_ui_network",BENCH_FIXTURE,firmware_sha,strict_sha,optimized_sha,BENCH_CASE_COUNT,BENCH_ROUNDS,BENCH_BLOCKS,BENCH_WARMUP,BENCH_SEED,BENCH_TIMING_EXCLUDE,aggregate.samples,aggregate.max_abs,sqrt(aggregate.error_square_sum/(double)aggregate.samples),aggregate.pcm_different,aggregate.max_pcm_lsb,(double)BENCH_MAX_ABS,BENCH_MAX_PCM_LSB,(double)BENCH_MAX_RELATIVE_RMS,profiles[0].timed_blocks,profiles[0].process_us,profiles[0].peak_us,profiles[1].timed_blocks,profiles[1].process_us,profiles[1].peak_us,(unsigned)psram_before,(unsigned)psram_after,(unsigned)internal_before,(unsigned)internal_after,allocation_probe_allocations(),allocation_probe_frees(),BENCH_ROLE==RNBO_S3_FX?BENCH_CASE_COUNT:0u,input_rechecks,pilot_sample_checks,BENCH_HAS_ORACLE?BENCH_CASE_COUNT:0u,oracle_rechecks,semantic_sample_checks,dc_sample_checks,oracle_bit_sample_checks,oracle_bit_differences,(unsigned)uxTaskGetStackHighWaterMark(NULL));
#if BENCH_WAVE4
    printf(" wave4_bit_sample_checks=%"PRIu64" wave4_bit_differences=%"PRIu64" wave4_zero_sign_differences=%"PRIu64" observer_bit_sample_checks=%"PRIu64" observer_bit_differences=%"PRIu64,wave4_bit_sample_checks,wave4_bit_differences,wave4_zero_sign_differences,observer_bit_sample_checks,observer_bit_differences);
#endif
#if BENCH_GEN_ARITH
    printf(" gen_arith_bit_sample_checks=%"PRIu64" gen_arith_bit_differences=%"PRIu64" gen_arith_zero_sign_differences=%"PRIu64,gen_arith_bit_sample_checks,gen_arith_bit_differences,gen_arith_zero_sign_differences);
#endif
#if BENCH_GEN_HISTORY
    printf(" gen_reset_events=%"PRIu64" gen_reset_witness_events=%"PRIu64" gen_reset_witness_sample_checks=%"PRIu64" gen_reset_witness_differences=%"PRIu64" pcm_gain=0.25",gen_reset_events,gen_reset_witness_events,gen_reset_witness_sample_checks,gen_reset_witness_differences);
#endif
    putchar('\n');fflush(stdout);
    heap_caps_free(oracle_cache);heap_caps_free(stimulus_cache);heap_caps_free(reference);heap_caps_free(work);vTaskDelete(NULL);
}
void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(2000));
    CHECK(xTaskCreateStaticPinnedToCore(worker,"object_bench",sizeof worker_stack,NULL,5,worker_stack,&worker_task,1));
}
