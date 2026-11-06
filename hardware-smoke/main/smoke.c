/* SPDX-License-Identifier: MIT */
/* Fast offline functional checks and callback timing, one image at a time. */
#include "module_host.h"
#include "allocation_probe.h"
#include "bench_check.h"
#include "smoke_types.h"
#include "smoke_payloads.h"
#include "smoke_cases.h"
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

#ifndef SMOKE_PLAN_SHA256
#error "Generated smoke_cases.h must bind SMOKE_PLAN_SHA256"
#endif
#ifndef SMOKE_ABSOLUTE_TOLERANCE_CEILING
#define SMOKE_ABSOLUTE_TOLERANCE_CEILING .001f
#endif
#ifndef SMOKE_PREPARE_WARM_BLOCKS
#define SMOKE_PREPARE_WARM_BLOCKS 4u
#endif
_Static_assert(sizeof(float)==4 && RNBO_S3_BLOCK_FRAMES==256 && RNBO_S3_SAMPLE_RATE==44100,"fixed binary32 44100/256 ABI required");
_Static_assert(SMOKE_CASE_COUNT==SMOKE_EMBEDDED_MODULE_COUNT,"header/embedded manifest case count differs");
_Static_assert(sizeof smoke_cases/sizeof *smoke_cases==SMOKE_CASE_COUNT,"case table length differs");
_Static_assert(sizeof smoke_inputs/sizeof *smoke_inputs==512,"one stereo input vector required");
_Static_assert(SMOKE_ARENA_BYTES>=4096 && SMOKE_ARENA_BYTES<=2097152u,"caller arena bound required");
enum { MANUAL_WARM_CALLS=4, TIMED_CALLS=16 };
static StackType_t worker_stack[24576/sizeof(StackType_t)];
static StaticTask_t worker_task;
_Alignas(16) static float input_storage[2][RNBO_S3_BLOCK_FRAMES];
_Alignas(16) static float output_storage[2][RNBO_S3_BLOCK_FRAMES];
static const float *const inputs[2]={input_storage[0],input_storage[1]};
static float *const outputs[2]={output_storage[0],output_storage[1]};
/* Raw right-lane capture is outside process timing and never uses its tolerance. */
static uint32_t right_capture[(MANUAL_WARM_CALLS+TIMED_CALLS)*RNBO_S3_BLOCK_FRAMES];

typedef struct {
    uint64_t samples,bit_mismatches,zero_sign_differences,numeric_mismatches,within_tolerance_differences,nonfinite_outputs,strict_zero_sign_mismatches;
    double max_absolute_error;
    uint32_t first_mismatch,first_mismatch_call,first_actual,first_expected;
} output_checks;
typedef struct {
    uint32_t resolved[32],next_event;
    uint64_t events,total_us,peak_us;
} parameter_checks;

static bool word_finite(uint32_t word) { return (word&0x7f800000u)!=0x7f800000u; }
static bool token(const char *text)
{
    if(!text || !*text)return false;
    for(const unsigned char *p=(const unsigned char *)text;*p;++p)
        if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='_'||*p=='-'||*p=='.'))return false;
    return true;
}
static bool hex_digest(const char *text)
{
    if(!text || strlen(text)!=64)return false;
    for(unsigned i=0;i<64;++i)if(!((text[i]>='0'&&text[i]<='9')||(text[i]>='a'&&text[i]<='f')))return false;
    return true;
}
static void digest_hex(const uint8_t *bytes,size_t count,char result[65])
{
    uint8_t digest[32];CHECK(mbedtls_sha256(bytes,count,digest,0)==0);
    for(unsigned i=0;i<32;++i)sprintf(result+2*i,"%02x",digest[i]);
    result[64]=0;
}
static void compare_output(const smoke_case *test,output_checks *checks)
{
    unsigned call=(unsigned)(checks->samples/512u);CHECK(call<MANUAL_WARM_CALLS+TIMED_CALLS);
    const uint32_t *expected_words=test->expected_block_refs?test->expected_block_refs[call]:
        test->expected_blocks?test->expected_blocks+call*512u:test->expected;
    CHECK(expected_words!=NULL);
    memcpy(right_capture+call*RNBO_S3_BLOCK_FRAMES,outputs[1],RNBO_S3_BLOCK_FRAMES*sizeof(uint32_t));
    for(unsigned frame=0;frame<RNBO_S3_BLOCK_FRAMES;++frame)for(unsigned channel=0;channel<2;++channel){
        uint32_t actual;memcpy(&actual,&outputs[channel][frame],sizeof actual);
        uint32_t expected=expected_words[2u*frame+channel];++checks->samples;
        if(actual==expected)continue;
        ++checks->bit_mismatches;
        bool strict_zero=false;
        if(((actual|expected)&0x7fffffffu)==0){
            if(test->strict_zero_sign_channels&(1u<<channel)){
                ++checks->strict_zero_sign_mismatches;strict_zero=true;
            }else{++checks->zero_sign_differences;continue;}
        }
        if(!strict_zero && word_finite(actual)){
            float target;memcpy(&target,&expected,sizeof target);
            double error=fabs((double)outputs[channel][frame]-(double)target);
            if(error>checks->max_absolute_error)checks->max_absolute_error=error;
            if(error<=(double)test->absolute_tolerance){++checks->within_tolerance_differences;continue;}
        }else if(!strict_zero)++checks->nonfinite_outputs;
        ++checks->numeric_mismatches;
        if(checks->first_mismatch==UINT32_MAX){
            checks->first_mismatch_call=call;
            checks->first_mismatch=2u*frame+channel;checks->first_actual=actual;checks->first_expected=expected;
        }
    }
}
static uint32_t float_word(float value)
{
    uint32_t word;memcpy(&word,&value,sizeof word);return word;
}
static bool same_numeric_word(uint32_t actual,uint32_t expected)
{
    return actual==expected || ((actual|expected)&0x7fffffffu)==0u;
}
static float affine_normalized(const smoke_parameter_contract *parameter,float actual)
{
    /* Independent affine reference, outside all callback timing. The initial
     * parameter scenario has exponent1, steps0 and exact dyadic [-8,8] values. */
    return (float)(((double)actual-(double)parameter->minimum)/
                   ((double)parameter->maximum-(double)parameter->minimum));
}
static void verify_parameters(object_image *image,const smoke_case *test,parameter_checks *checks)
{
    CHECK(test->expected_parameter_count<=32u);
    CHECK(image->module.parameter_count(image->context)==test->expected_parameter_count);
    CHECK((test->expected_parameter_count!=0u)==(test->parameters!=NULL));
    CHECK((test->parameter_event_count!=0u)==(test->parameter_events!=NULL));
    for(uint32_t slot=0;slot<test->expected_parameter_count;++slot){
        const smoke_parameter_contract *parameter=&test->parameters[slot];
        CHECK(token(parameter->id) && strlen(parameter->id)<sizeof(((rnbo_s3_parameter_info *)0)->id));
        CHECK(isfinite(parameter->minimum) && isfinite(parameter->maximum) && parameter->minimum<parameter->maximum);
        CHECK(isfinite(parameter->initial) && parameter->initial>=parameter->minimum && parameter->initial<=parameter->maximum);
        CHECK(parameter->exponent==1.f && parameter->steps==0u);
        for(uint32_t prior=0;prior<slot;++prior)CHECK(strcmp(parameter->id,test->parameters[prior].id));
        checks->resolved[slot]=UINT32_MAX;
    }
    for(uint32_t index=0;index<test->expected_parameter_count;++index){
        rnbo_s3_parameter_info info={.struct_bytes=sizeof info};
        allocation_probe_begin();int result=image->module.parameter_info(image->context,index,&info);allocation_probe_end();
        CHECK(result==RNBO_S3_OK && info.struct_bytes==sizeof info && info.index==index);
        CHECK(memchr(info.id,0,sizeof info.id)!=NULL);
        uint32_t slot=0;
        while(slot<test->expected_parameter_count && strcmp(info.id,test->parameters[slot].id))++slot;
        CHECK(slot<test->expected_parameter_count && checks->resolved[slot]==UINT32_MAX);
        const smoke_parameter_contract *parameter=&test->parameters[slot];
        CHECK(float_word(info.minimum)==float_word(parameter->minimum) && float_word(info.maximum)==float_word(parameter->maximum));
        CHECK(float_word(info.initial)==float_word(parameter->initial) && float_word(info.exponent)==float_word(parameter->exponent) && info.steps==parameter->steps);
        checks->resolved[slot]=index;
        float actual=NAN,normalized=NAN;
        allocation_probe_begin();result=image->module.parameter_value(image->context,index,&actual,&normalized);allocation_probe_end();
        CHECK(result==RNBO_S3_OK && float_word(actual)==float_word(parameter->initial));
        CHECK(float_word(normalized)==float_word(affine_normalized(parameter,parameter->initial)));
        CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());
    }
    for(uint32_t n=0;n<test->parameter_event_count;++n){
        const smoke_parameter_action *action=&test->parameter_events[n];
        CHECK(action->before_call<MANUAL_WARM_CALLS+TIMED_CALLS && action->parameter_slot<test->expected_parameter_count);
        if(n)CHECK(test->parameter_events[n-1u].before_call<=action->before_call);
        CHECK(word_finite(action->value_word));
        float value;memcpy(&value,&action->value_word,sizeof value);
        const smoke_parameter_contract *parameter=&test->parameters[action->parameter_slot];
        CHECK(value>=parameter->minimum && value<=parameter->maximum);
    }
}
static void apply_parameter_events(object_image *image,const smoke_case *test,parameter_checks *checks,uint32_t call)
{
    while(checks->next_event<test->parameter_event_count){
        uint32_t ordinal=checks->next_event;
        const smoke_parameter_action *action=&test->parameter_events[ordinal];
        CHECK(action->before_call>=call);
        if(action->before_call!=call)break;
        const smoke_parameter_contract *parameter=&test->parameters[action->parameter_slot];
        uint32_t index=checks->resolved[action->parameter_slot];
        float value;memcpy(&value,&action->value_word,sizeof value);
        rnbo_s3_event event={.struct_bytes=sizeof event,.kind=RNBO_S3_PARAMETER_ACTUAL,.parameter_index=index,.value=value};
        allocation_probe_begin();int64_t start=esp_timer_get_time();
        int result=image->module.event(image->context,&event);
        int64_t elapsed=esp_timer_get_time()-start;
        float actual=NAN,normalized=NAN;
        int readback=image->module.parameter_value(image->context,index,&actual,&normalized);allocation_probe_end();
        if(result!=RNBO_S3_OK || elapsed<0 || readback!=RNBO_S3_OK){
            /* Diagnostic only: outside the event/readback timer and allocation probe. */
            rnbo_s3_stats fault={.struct_bytes=sizeof fault};
            int statistics=image->module.statistics(image->context,&fault);
            printf("RNBO_SMOKE EVENT_RESULT case_id=%s ordinal=%" PRIu32 " before_call=%" PRIu32 " parameter_slot=%" PRIu32 " value_word=%08" PRIx32
                   " status=%d readback_status=%d elapsed_us=%" PRIi64 " statistics_status=%d platform_errors=%" PRIu64 " late_platform_allocations=%" PRIu64 " invalid_samples=%" PRIu64 "\n",
                   test->id,ordinal,call,action->parameter_slot,action->value_word,result,readback,elapsed,statistics,
                   (uint64_t)fault.errors,(uint64_t)fault.late_platform_allocations,(uint64_t)fault.invalid_samples);
        }
        CHECK(result==RNBO_S3_OK && elapsed>=0 && readback==RNBO_S3_OK);
        CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());
        uint32_t actual_word=float_word(actual),normalized_word=float_word(normalized);
        CHECK(same_numeric_word(actual_word,action->value_word) && same_numeric_word(normalized_word,float_word(affine_normalized(parameter,value))));
        CHECK(UINT64_MAX-checks->total_us>=(uint64_t)elapsed);
        checks->total_us+=(uint64_t)elapsed;
        if((uint64_t)elapsed>checks->peak_us)checks->peak_us=(uint64_t)elapsed;
        ++checks->events;++checks->next_event;
        printf("RNBO_SMOKE EVENT case_id=%s ordinal=%"PRIu32" before_call=%"PRIu32" parameter_slot=%"PRIu32" resolved_index=%"PRIu32" value_word=%08"PRIx32" actual_word=%08"PRIx32" normalized_word=%08"PRIx32" event_us=%"PRIu64"\n",test->id,ordinal,call,action->parameter_slot,index,action->value_word,actual_word,normalized_word,(uint64_t)elapsed);
    }
}
static uint64_t process_once(object_image *image,const smoke_case *test,output_checks *checks,parameter_checks *parameters)
{
    uint32_t call=(uint32_t)(checks->samples/512u);
    CHECK(call<MANUAL_WARM_CALLS+TIMED_CALLS);
    apply_parameter_events(image,test,parameters,call);
    for(unsigned ch=0;ch<2;++ch)for(unsigned f=0;f<RNBO_S3_BLOCK_FRAMES;++f)outputs[ch][f]=NAN;
    allocation_probe_begin();int64_t start=esp_timer_get_time();
    int result=image->module.process(image->context,inputs,outputs,RNBO_S3_BLOCK_FRAMES,image->position);
    int64_t elapsed=esp_timer_get_time()-start;allocation_probe_end();
    if(result!=RNBO_S3_OK || elapsed<0){
        /* Fault receipt only: outside the callback timer and allocation probe. */
        rnbo_s3_stats fault={.struct_bytes=sizeof fault};
        int statistics=image->module.statistics(image->context,&fault);
        printf("RNBO_SMOKE PROCESS_RESULT case_id=%s before_call=%" PRIu32 " status=%d elapsed_us=%" PRIi64
               " statistics_status=%d platform_errors=%" PRIu64 " late_platform_allocations=%" PRIu64 " invalid_samples=%" PRIu64 "\n",
               test->id,call,result,elapsed,statistics,(uint64_t)fault.errors,
               (uint64_t)fault.late_platform_allocations,(uint64_t)fault.invalid_samples);
    }
    CHECK(result==RNBO_S3_OK && elapsed>=0);image->position+=RNBO_S3_BLOCK_FRAMES;
    CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());
    compare_output(test,checks); /* Every expected-word check is outside timing. */
    return (uint64_t)elapsed;
}
static double median(const uint64_t times[TIMED_CALLS])
{
    uint64_t sorted[TIMED_CALLS];memcpy(sorted,times,sizeof sorted);
    for(unsigned i=1;i<TIMED_CALLS;++i){
        uint64_t value=sorted[i];unsigned j=i;
        while(j && sorted[j-1]>value){sorted[j]=sorted[j-1];--j;}
        sorted[j]=value;
    }
    return (double)sorted[TIMED_CALLS/2-1]/2.0+(double)sorted[TIMED_CALLS/2]/2.0;
}
static void worker(void *unused)
{
    (void)unused;CHECK(hex_digest(SMOKE_PLAN_SHA256));
    const esp_app_desc_t *app=esp_app_get_description();char firmware_sha[65];
    for(unsigned i=0;i<32;++i){sprintf(firmware_sha+2*i,"%02x",app->app_elf_sha256[i]);}
    firmware_sha[64]=0;
    /* Settle stream/dtoa buffers before every module's heap baseline. */
    char formatted[192];CHECK(snprintf(formatted,sizeof formatted,"%.6f %.6f %.6f %.6f %"PRIu64"",1.0/3.0,.5,12345.0625,580.498866,UINT64_C(123))>0);
    printf("RNBO_SMOKE START firmware_elf_sha256=%s plan_sha256=%s cases=%u scope=offline_no_i2s_ui_network\n",firmware_sha,SMOKE_PLAN_SHA256,(unsigned)SMOKE_CASE_COUNT);fflush(stdout);
    /* The hardware SHA backend lazily allocates its shared lock. Establish
     * that framework resource before the module heap baseline. */
    char prewarm_sha[65];digest_hex((const uint8_t *)smoke_inputs,sizeof smoke_inputs,prewarm_sha);
    size_t observer_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    digest_hex((const uint8_t *)right_capture,sizeof right_capture,prewarm_sha);
    size_t observer_after=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    printf("RNBO_SMOKE OBSERVER_PREWARM internal_before=%u internal_after=%u bytes=%u\n",(unsigned)observer_before,(unsigned)observer_after,(unsigned)sizeof right_capture);
    CHECK(heap_caps_check_integrity_all(true));
    size_t psram_start=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t internal_start=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    unsigned passed=0,mismatched=0,cpu_review=0,images=0,finalized=0;
    for(unsigned n=0;n<SMOKE_CASE_COUNT;++n){
        const smoke_case *test=&smoke_cases[n];CHECK(token(test->id)&&hex_digest(test->sha));
        CHECK(test->reference_policy && (!strcmp(test->reference_policy,"documented-basic")||!strcmp(test->reference_policy,"observational-signed-fraction")||!strcmp(test->reference_policy,"mathematical-approximation")));
        CHECK(isfinite(test->absolute_tolerance) && test->absolute_tolerance>=0 && test->absolute_tolerance<=SMOKE_ABSOLUTE_TOLERANCE_CEILING);
        CHECK((test->strict_zero_sign_channels&~3u)==0u);
        CHECK((uintptr_t)test->payload_end>(uintptr_t)test->payload_start);
        for(unsigned i=0;i<512;++i)CHECK(word_finite(test->expected[i]));
        if(test->expected_block_refs){
            for(unsigned b=0;b<20u;++b){
                CHECK(test->expected_block_refs[b]!=NULL);
                for(unsigned i=0;i<512u;++i)CHECK(word_finite(test->expected_block_refs[b][i]));
            }
        }else if(test->expected_blocks){for(unsigned i=0;i<20u*512u;++i)CHECK(word_finite(test->expected_blocks[i]));}
        const uint32_t *vector=test->input_words?test->input_words:smoke_inputs;
        for(unsigned frame=0;frame<RNBO_S3_BLOCK_FRAMES;++frame)for(unsigned channel=0;channel<2;++channel){
            uint32_t word=vector[2u*frame+channel];CHECK(word_finite(word));
            memcpy(&input_storage[channel][frame],&word,sizeof word);
        }
        char input_sha[65];digest_hex((const uint8_t *)vector,512u*sizeof(uint32_t),input_sha);
        char actual_sha[65];digest_hex(test->payload_start,(size_t)(test->payload_end-test->payload_start),actual_sha);CHECK(!strcmp(actual_sha,test->sha));
        size_t psram_before=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        size_t internal_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
        uint32_t arena_bytes=test->arena_bytes?test->arena_bytes:SMOKE_ARENA_BYTES;
        CHECK(arena_bytes>=4096u && arena_bytes<=2097152u);
        object_image image;object_image_load(&image,test->payload_start,(size_t)(test->payload_end-test->payload_start),RNBO_S3_FX,arena_bytes);++images;
        object_image_prepare(&image,SMOKE_PREPARE_WARM_BLOCKS,SMOKE_SEED);
        parameter_checks parameters={0};verify_parameters(&image,test,&parameters);
        output_checks checks={.first_mismatch=UINT32_MAX,.first_mismatch_call=UINT32_MAX};
        for(unsigned b=0;b<MANUAL_WARM_CALLS;++b)(void)process_once(&image,test,&checks,&parameters);
        uint64_t times[TIMED_CALLS],total=0,peak=0;
        for(unsigned b=0;b<TIMED_CALLS;++b){
            times[b]=process_once(&image,test,&checks,&parameters);CHECK(UINT64_MAX-total>=times[b]);total+=times[b];
            if(times[b]>peak)peak=times[b];
        }
        CHECK(parameters.next_event==test->parameter_event_count && parameters.events==test->parameter_event_count);
        rnbo_s3_stats stats;rnbo_s3_dynamic_stats dynamic;object_image_statistics(&image,&stats,&dynamic);
        uint32_t context_bytes=image.info.context_bytes,code_bytes=image.elf.sec[ELF_SEC_TEXT].size;
        object_image_destroy_context(&image);object_image_unload(&image);++finalized;
        CHECK(heap_caps_check_integrity_all(true));
        size_t psram_after=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        size_t internal_after=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
        CHECK(psram_after==psram_before && internal_after>=internal_before);
        CHECK(checks.bit_mismatches==checks.zero_sign_differences+checks.within_tolerance_differences+checks.numeric_mismatches);
        bool output_ok=checks.numeric_mismatches==0;
        if(output_ok)++passed;else ++mismatched;
        double med=median(times),mean=(double)total/TIMED_CALLS;
        double median_limit=.1*((double)RNBO_S3_BLOCK_FRAMES*1000000.0/RNBO_S3_SAMPLE_RATE);
        double spike_limit=3.0*med>med+100.0?3.0*med:med+100.0;
        bool high_median=med>median_limit,spike=(double)peak>spike_limit;
        if(high_median||spike)++cpu_review;
        const char *reasons=high_median?(spike?"median_budget,peak_spike":"median_budget"):(spike?"peak_spike":"none");
        size_t print_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
        printf("RNBO_SMOKE CASE id=%s module_sha256=%s status=%s reference_policy=%s samples=%"PRIu64" bit_mismatches=%"PRIu64" zero_sign_differences=%"PRIu64" first_mismatch_word=%"PRIu32" first_actual=%08"PRIx32" first_expected=%08"PRIx32" mean_us=%.6f median_us=%.6f peak_us=%"PRIu64" review_cpu=%u cpu_reasons=%s median_budget_us=%.6f peak_review_limit_us=%.6f context_bytes=%"PRIu32" arena_used=%"PRIu32" arena_high_water=%"PRIu32" arena_capacity=%"PRIu32" code_bytes=%"PRIu32" cpp_new_calls=%"PRIu64" arena_requests=%"PRIu64" timed_calls=%u warm_calls=%u prepare_zero_warm_blocks=%u finalized=1 psram_before=%u psram_after=%u internal_before=%u internal_after=%u times_us=",test->id,actual_sha,output_ok?"pass":"output_mismatch",test->reference_policy,checks.samples,checks.bit_mismatches,checks.zero_sign_differences,checks.first_mismatch,checks.first_actual,checks.first_expected,mean,med,peak,(unsigned)(high_median||spike),reasons,median_limit,spike_limit,context_bytes,dynamic.arena_used,dynamic.arena_high_water,dynamic.arena_capacity,code_bytes,dynamic.cpp_new_calls,dynamic.total_arena_allocations,TIMED_CALLS,MANUAL_WARM_CALLS,(unsigned)SMOKE_PREPARE_WARM_BLOCKS,(unsigned)psram_before,(unsigned)psram_after,(unsigned)internal_before,(unsigned)internal_after);
        for(unsigned b=0;b<TIMED_CALLS;++b){printf("%s%"PRIu64,b?",":"",times[b]);}
        uint64_t error_bits;uint32_t tolerance_bits;
        memcpy(&error_bits,&checks.max_absolute_error,sizeof error_bits);
        memcpy(&tolerance_bits,&test->absolute_tolerance,sizeof tolerance_bits);
        printf(" numeric_mismatches=%"PRIu64" within_tolerance_differences=%"PRIu64" nonfinite_outputs=%"PRIu64" max_absolute_error_bits=%016"PRIx64" absolute_tolerance_bits=%08"PRIx32" input_words_sha256=%s strict_zero_sign_mismatches=%"PRIu64,checks.numeric_mismatches,checks.within_tolerance_differences,checks.nonfinite_outputs,error_bits,tolerance_bits,input_sha,checks.strict_zero_sign_mismatches);
        printf(" first_mismatch_call=%"PRIu32" expected_block_count=%u",checks.first_mismatch_call,(test->expected_blocks||test->expected_block_refs)?20u:1u);
        printf(" parameter_count=%"PRIu32" parameter_events_applied=%"PRIu64" event_total_us=%"PRIu64" event_peak_us=%"PRIu64,test->expected_parameter_count,parameters.events,parameters.total_us,parameters.peak_us);
        char right_sha[65];digest_hex((const uint8_t *)right_capture,sizeof right_capture,right_sha);
        printf(" right_output_sha256=%s",right_sha);
        putchar('\n');fflush(stdout);
        size_t print_after=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
        printf("RNBO_SMOKE OBSERVER_HEAP id=%s internal_before=%u internal_after=%u\n",test->id,(unsigned)print_before,(unsigned)print_after);
    }
    size_t psram_end=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    size_t internal_end=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    CHECK(psram_end==psram_start && internal_end>=internal_start);
    CHECK(images==SMOKE_CASE_COUNT && finalized==images && passed+mismatched==images);
    CHECK(!allocation_probe_allocations()&&!allocation_probe_frees());
    printf("RNBO_SMOKE DONE firmware_elf_sha256=%s plan_sha256=%s cases=%u passed=%u mismatched=%u cpu_review=%u images=%u finalized_images=%u host_heap_allocations=%"PRIu32" host_heap_frees=%"PRIu32" local_late_allocations=0 psram_before=%u psram_after=%u internal_before=%u internal_after=%u scope=offline_no_i2s_ui_network\n",firmware_sha,SMOKE_PLAN_SHA256,(unsigned)SMOKE_CASE_COUNT,passed,mismatched,cpu_review,images,finalized,allocation_probe_allocations(),allocation_probe_frees(),(unsigned)psram_start,(unsigned)psram_end,(unsigned)internal_start,(unsigned)internal_end);fflush(stdout);
    /* Leave the completed quiet image installed, without rerunning or reset. */
    for(;;)vTaskDelay(pdMS_TO_TICKS(1000));
}
void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(2000));
    CHECK(xTaskCreateStaticPinnedToCore(worker,"rnbo_smoke",sizeof worker_stack,NULL,5,worker_stack,&worker_task,1));
}
