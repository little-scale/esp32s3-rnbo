/* SPDX-License-Identifier: MIT */
/* Trusted-code, offline target qualification. No I2S, display, flash writes,
 * networking or module activation in the working instrument application. */
#include "rnbo_s3_dynamic.h"
#include "allocation_probe.h"
#include "mapped_range.h"
#include "test_identity.h"
#include "esp_elf.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_memory_utils.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(void *)==4 && sizeof(void (*)(void))==4,"Xtensa32 native ABI required");
enum { ARENA_BYTES=1024*1024, SEED=0x12345678, WARMUP=4, CYCLES=32, TEST_STACK=24576 };
static const char *TAG="rnbo_dynamic_test";
#define CHECK(c) do { if (!(c)) { allocation_probe_end();ESP_LOGE(TAG,"FAIL line=%d condition=%s",__LINE__,#c);abort(); } } while (0)
extern const uint8_t sine_start[] asm("_binary_rnbo_sine_payload_bin_start");
extern const uint8_t sine_end[] asm("_binary_rnbo_sine_payload_bin_end");
extern const uint8_t fx_start[] asm("_binary_rnbo_fx_payload_bin_start");
extern const uint8_t fx_end[] asm("_binary_rnbo_fx_payload_bin_end");
#if RNBO_TEST_HAVE_MIDI
extern const uint8_t midi_start[] asm("_binary_rnbo_midi_payload_bin_start");
extern const uint8_t midi_end[] asm("_binary_rnbo_midi_payload_bin_end");
#endif
typedef struct { const uint8_t *start,*end;const char *name,*sha;uint32_t role; } fixture;
static const fixture sine_fixture={sine_start,sine_end,"sine",RNBO_TEST_SINE_SHA256,RNBO_S3_MAIN};
static const fixture fx_fixture={fx_start,fx_end,"fx-pass-through",RNBO_TEST_FX_SHA256,RNBO_S3_FX};
#if RNBO_TEST_HAVE_MIDI
static const fixture midi_fixture={midi_start,midi_end,"midi4",RNBO_TEST_MIDI_SHA256,RNBO_S3_MAIN};
#endif
typedef struct {
    esp_elf_t elf;
    rnbo_s3_module module;
    rnbo_s3_dynamic_info info;
    void *state,*context;
    uint32_t state_bytes;
    volatile uint32_t finalized;
    uint64_t position;
    bool loaded;
} image;
typedef struct { uint64_t blocks,total_us;uint32_t peak_us; } timings;
static timings reference_timing,sine_timing,fx_timing,midi_timing;
static uint64_t compared_samples,pcm_compared_samples,constructors_checked,finalizers_checked;
static uint64_t module_cpp_new_calls,module_arena_allocations;
static uint32_t negative_handshakes;
static uint32_t maximum_arena_used;
static float (*buffers)[RNBO_S3_BLOCK_FRAMES];
static StaticTask_t task_tcb;
static StackType_t task_stack[TEST_STACK/sizeof(StackType_t)];
static char firmware_sha[65];

static void hex_digest(const uint8_t bytes[32],char output[65])
{
    static const char alphabet[]="0123456789abcdef";
    for (unsigned i=0;i<32;++i) {output[i*2]=alphabet[bytes[i]>>4];output[i*2+1]=alphabet[bytes[i]&15];}
    output[64]=0;
}
static void verify_payload(const fixture *f)
{
    uint8_t bytes[32];char actual[65];
    CHECK(((uintptr_t)f->start&3u)==0 && f->end>f->start);
    CHECK(mbedtls_sha256(f->start,(size_t)(f->end-f->start),bytes,0)==0);
    hex_digest(bytes,actual);CHECK(!strcmp(actual,f->sha));
    ESP_LOGI(TAG,"PAYLOAD name=%s elf_sha256=%s bytes=%u",f->name,actual,(unsigned)(f->end-f->start));
}
static bool executable(const esp_elf_t *elf,uintptr_t pointer)
{
    return rnbo_test_range(esp_elf_runtime_base((esp_elf_t *)elf),elf->sec[ELF_SEC_TEXT].size,pointer,1);
}
static bool data_span(const esp_elf_t *elf,const void *pointer,size_t bytes)
{
    const unsigned allowed[]={ELF_SEC_DATA,ELF_SEC_BSS,ELF_SEC_RODATA,ELF_SEC_DRLRO};
    for (unsigned i=0;i<sizeof allowed/sizeof *allowed;++i) {
        const esp_elf_sec_t *s=&elf->sec[allowed[i]];
        if (rnbo_test_range(s->addr,s->size,(uintptr_t)pointer,bytes)) return true;
    }
    return false;
}
static void lifecycle_array(const esp_elf_t *elf,void (**array)(void),uint32_t count,unsigned section)
{
    if (!count) return;
    CHECK(count<=UINT32_MAX/sizeof(*array));
    CHECK(rnbo_test_range(elf->sec[section].addr,elf->sec[section].size,(uintptr_t)array,count*sizeof(*array)));
    for (uint32_t i=0;i<count;++i) {
        uintptr_t target=(uintptr_t)array[i];
        if (target && target!=UINT32_MAX) CHECK(executable(elf,target));
    }
}
static void admit_table(image *a,uint32_t role)
{
    rnbo_s3_module *m=&a->module;rnbo_s3_dynamic_info *d=&a->info;
    CHECK(d->struct_bytes==sizeof *d && d->abi_major==RNBO_S3_DYNAMIC_ABI_MAJOR && d->abi_minor<=RNBO_S3_DYNAMIC_ABI_MINOR && d->pointer_bits==32);
    uint32_t required=RNBO_S3_DYNAMIC_CALLER_STATE|RNBO_S3_DYNAMIC_PRIVATE_CPP_ALLOCATOR|RNBO_S3_DYNAMIC_DETERMINISTIC_SAMPLE_CLOCK;
    CHECK(d->flags==required && d->constructor_runs==1 && d->registered_finalizers>0);
    CHECK(d->state_alignment>=16 && d->state_alignment<=64 && !(d->state_alignment&(d->state_alignment-1)));
    CHECK(d->context_bytes && d->context_bytes<=ARENA_BYTES && d->minimum_arena_bytes>=4096 && d->minimum_arena_bytes<=ARENA_BYTES);
    CHECK(d->maximum_arena_bytes==ARENA_BYTES && d->minimum_state_bytes>=d->context_bytes && d->maximum_state_bytes<=2u*ARENA_BYTES);
    CHECK(d->minimum_state_bytes<=d->maximum_state_bytes && d->minimum_state_bytes-d->context_bytes>=d->minimum_arena_bytes);
    CHECK(d->maximum_state_bytes>=d->context_bytes && d->maximum_state_bytes-d->context_bytes>=ARENA_BYTES);
    CHECK(data_span(&a->elf,d->descriptor_address,sizeof(uint32_t)));
    uint32_t descriptor_bytes;memcpy(&descriptor_bytes,d->descriptor_address,sizeof descriptor_bytes);
    CHECK(descriptor_bytes>=sizeof *m && data_span(&a->elf,d->descriptor_address,descriptor_bytes));
    CHECK(!memcmp(m,d->descriptor_address,sizeof *m));
    CHECK(m->struct_bytes>=sizeof *m && m->abi_major==RNBO_S3_ABI_MAJOR && m->abi_minor<=RNBO_S3_ABI_MINOR && m->pointer_bits==32);
    CHECK(m->sample_rate==RNBO_S3_SAMPLE_RATE && m->block_frames==RNBO_S3_BLOCK_FRAMES && m->role==role && m->audio_outputs==2);
    CHECK(m->audio_inputs==(role==RNBO_S3_FX?2u:0u) && m->max_parameters<=RNBO_S3_MAX_PARAMETERS);
    const uint32_t flags=RNBO_S3_SINGLE_INSTANCE|RNBO_S3_BOUNDARY_EVENTS|RNBO_S3_PLATFORM_ALLOCATIONS_ONLY|RNBO_S3_DISCARDS_MIDI_OUTPUT;
    CHECK((m->flags&~flags)==0 && (m->flags&RNBO_S3_SINGLE_INSTANCE) && (m->flags&RNBO_S3_BOUNDARY_EVENTS));
#define CALLBACK(name) CHECK(executable(&a->elf,(uintptr_t)m->name))
    CALLBACK(create);CALLBACK(prepare);CALLBACK(process);CALLBACK(event);CALLBACK(panic);
    CALLBACK(parameter_count);CALLBACK(parameter_info);CALLBACK(parameter_value);
    CALLBACK(parameter_convert);CALLBACK(statistics);CALLBACK(destroy);
#undef CALLBACK
    CHECK(executable(&a->elf,(uintptr_t)d->statistics));
}
static void request(image *a,unsigned operation,void *state,uint32_t bytes,int expected)
{
    a->module=(rnbo_s3_module){.struct_bytes=sizeof a->module};
    a->info=(rnbo_s3_dynamic_info){.struct_bytes=sizeof a->info};
    rnbo_s3_dynamic_request request={.struct_bytes=sizeof request,.magic=RNBO_S3_DYNAMIC_MAGIC,
        .abi_major=RNBO_S3_DYNAMIC_ABI_MAJOR,.abi_minor=RNBO_S3_DYNAMIC_ABI_MINOR,.operation=operation,
        .state=state,.state_bytes=bytes,.out_module=&a->module,.out_info=&a->info,
        .finalizer_observer=&a->finalized,.result=RNBO_S3_DYNAMIC_RESULT_PENDING};
    char *arguments[]={(char *)&request};
    CHECK(esp_elf_request(&a->elf,0,1,arguments)==0);
    CHECK(request.result==expected); /* Entry return is discarded by this loader. */
}
static void negative_request(image *a,unsigned which)
{
    rnbo_s3_dynamic_request request={.struct_bytes=sizeof request,.magic=RNBO_S3_DYNAMIC_MAGIC,
        .abi_major=RNBO_S3_DYNAMIC_ABI_MAJOR,.abi_minor=RNBO_S3_DYNAMIC_ABI_MINOR,.operation=RNBO_S3_DYNAMIC_BIND,
        .state=a->state,.state_bytes=a->state_bytes,.out_module=&a->module,.out_info=&a->info,
        .finalizer_observer=&a->finalized,.result=RNBO_S3_DYNAMIC_RESULT_PENDING};
    int expected=RNBO_S3_INVALID;
    switch(which) {
        case 0:request.magic=0;break;
        case 1:request.abi_major=RNBO_S3_DYNAMIC_ABI_MAJOR+1;break;
        case 2:a->module.struct_bytes=sizeof a->module-1;break;
        case 3:a->info.struct_bytes=sizeof a->info-1;break;
        case 4:request.state=(void *)((uintptr_t)a->state+1);break;
        case 5:request.state_bytes=a->info.minimum_state_bytes-1;break;
        case 6:request.state_bytes=a->info.maximum_state_bytes+1;break;
        case 7:request.state=(void *)UINT32_C(0xfffffff0);request.state_bytes=a->info.minimum_state_bytes;break;
        case 8:expected=RNBO_S3_BUSY;break; /* valid state, already-live image */
        default:CHECK(0);
    }
    char *arguments[]={(char *)&request};
    CHECK(esp_elf_request(&a->elf,0,1,arguments)==0 && request.result==expected);
    a->module.struct_bytes=sizeof a->module;a->info.struct_bytes=sizeof a->info;
    ++negative_handshakes;
}
static void load_image(image *a,const fixture *f)
{
    memset(a,0,sizeof *a);
    CHECK(esp_elf_init(&a->elf)==0);
    CHECK(esp_elf_relocate(&a->elf,f->start,(size_t)(f->end-f->start))==0);
    a->loaded=true;
    CHECK(esp_elf_runtime_base(&a->elf) && executable(&a->elf,(uintptr_t)a->elf.entry));
    CHECK(esp_ptr_external_ram(a->elf.ptext));
    CHECK(!a->elf.init_done && a->elf.init_count && a->elf.fini_count);
    lifecycle_array(&a->elf,a->elf.preinit_array,a->elf.preinit_count,ELF_SEC_PREINIT);
    lifecycle_array(&a->elf,a->elf.init_array,a->elf.init_count,ELF_SEC_INIT);
    lifecycle_array(&a->elf,a->elf.fini_array,a->elf.fini_count,ELF_SEC_FINI);
    request(a,RNBO_S3_DYNAMIC_DESCRIBE,NULL,0,RNBO_S3_OK);admit_table(a,f->role);
    CHECK(a->elf.init_done);
    request(a,RNBO_S3_DYNAMIC_DESCRIBE,NULL,0,RNBO_S3_OK);admit_table(a,f->role);
    ++constructors_checked;
    a->state_bytes=a->info.maximum_state_bytes;
    a->state=heap_caps_aligned_alloc(a->info.state_alignment,a->state_bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    CHECK(a->state && esp_ptr_external_ram(a->state));
    for(unsigned i=0;i<8;++i)negative_request(a,i);
    request(a,RNBO_S3_DYNAMIC_BIND,a->state,a->state_bytes,RNBO_S3_OK);admit_table(a,f->role);
    rnbo_s3_create_options options={sizeof options,ARENA_BYTES,WARMUP,SEED};
    CHECK(a->module.create(&options,&a->context)==RNBO_S3_OK);
    CHECK(rnbo_test_range((uintptr_t)a->state,a->state_bytes,(uintptr_t)a->context,a->info.context_bytes));
    CHECK(a->module.prepare(a->context)==RNBO_S3_OK);
    negative_request(a,8);
    CHECK(a->module.parameter_count(a->context)<=a->module.max_parameters);
}
static void clean_image(image *a)
{
    rnbo_s3_stats base={.struct_bytes=sizeof base};
    rnbo_s3_dynamic_stats extra={.struct_bytes=sizeof extra};
    CHECK(a->module.statistics(a->context,&base)==RNBO_S3_OK && a->info.statistics(a->context,&extra)==RNBO_S3_OK);
    CHECK(!base.errors && !base.invalid_samples && !base.late_platform_allocations && !base.faulted);
    CHECK(!extra.late_cpp_new_calls && !extra.total_late_allocations && !extra.bootstrap_allocation_attempts);
    CHECK(extra.arena_used<=extra.arena_capacity && extra.arena_high_water<=extra.arena_capacity && extra.arena_capacity==ARENA_BYTES);
    CHECK(base.warmup_blocks==WARMUP && base.sample_position==a->position);
    if (extra.arena_high_water>maximum_arena_used) maximum_arena_used=extra.arena_high_water;
}
static void unload_image(image *a)
{
    CHECK(a->loaded && a->context && !a->finalized);clean_image(a);
    rnbo_s3_dynamic_stats extra={.struct_bytes=sizeof extra};
    CHECK(a->info.statistics(a->context,&extra)==RNBO_S3_OK);
    module_cpp_new_calls+=extra.cpp_new_calls;module_arena_allocations+=extra.total_arena_allocations;
    a->module.destroy(a->context);a->context=NULL;
    CHECK(!a->finalized);
    esp_elf_deinit(&a->elf);
    CHECK(a->finalized==1);++finalizers_checked;
    heap_caps_free(a->state);
    memset(a,0,sizeof *a); /* Every copied callback expires before further code. */
}
static uint32_t parameter_index(const rnbo_s3_module *m,void *context,const char *id)
{
    for (unsigned i=0;i<m->parameter_count(context);++i) {
        rnbo_s3_parameter_info p={.struct_bytes=sizeof p};
        CHECK(m->parameter_info(context,i,&p)==RNBO_S3_OK && p.index==i);
        CHECK(memchr(p.id,0,sizeof p.id) && memchr(p.name,0,sizeof p.name) && memchr(p.unit,0,sizeof p.unit));
        CHECK(isfinite(p.minimum) && isfinite(p.maximum) && p.minimum<=p.maximum);
        if (!strcmp(p.id,id)) return i;
    }
    CHECK(0);return 0;
}
static void parameter(const rnbo_s3_module *m,void *context,uint32_t index,float value,uint32_t kind)
{
    rnbo_s3_event event={.struct_bytes=sizeof event,.kind=kind,.parameter_index=index,.value=value};
    allocation_probe_begin();int result=m->event(context,&event);allocation_probe_end();CHECK(result==RNBO_S3_OK);
}
static void record(timings *t,int64_t began)
{
    uint32_t elapsed=(uint32_t)(esp_timer_get_time()-began);
    ++t->blocks;t->total_us+=elapsed;if(elapsed>t->peak_us)t->peak_us=elapsed;
}
static void process(image *a,const float *const *input,float *const output[2],timings *t)
{
    allocation_probe_begin();int64_t began=esp_timer_get_time();
    int result=a->module.process(a->context,input,output,RNBO_S3_BLOCK_FRAMES,a->position);
    record(t,began);allocation_probe_end();CHECK(result==RNBO_S3_OK);
    a->position+=RNBO_S3_BLOCK_FRAMES;
    for(unsigned c=0;c<2;++c)for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)CHECK(isfinite(output[c][i]));
}
static void reference_process(const rnbo_s3_module *m,void *context,float *const output[2],uint64_t position)
{
    allocation_probe_begin();int64_t began=esp_timer_get_time();
    int result=m->process(context,NULL,output,RNBO_S3_BLOCK_FRAMES,position);
    record(&reference_timing,began);allocation_probe_end();CHECK(result==RNBO_S3_OK);
}
static void reference_clean(const rnbo_s3_module *m,void *context,uint64_t position)
{
    rnbo_s3_stats statistics={.struct_bytes=sizeof statistics};
    CHECK(m->statistics(context,&statistics)==RNBO_S3_OK && statistics.sample_position==position);
    CHECK(!statistics.late_platform_allocations && !statistics.errors && !statistics.invalid_samples && !statistics.faulted);
}
static int16_t pcm(float value)
{
    value*=0.5f;if(value>1)value=1;else if(value< -1)value= -1;
    return (int16_t)lrintf(value*32767.0f);
}
static void compare(float *const a[2],float *const b[2])
{
    for(unsigned c=0;c<2;++c)for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {
        CHECK(isfinite(a[c][i]) && isfinite(b[c][i]) && a[c][i]==b[c][i]);++compared_samples;
        CHECK(pcm(a[c][i])==pcm(b[c][i]));++pcm_compared_samples;
    }
}
static void sine_pair(unsigned blocks)
{
    image first,second;
    load_image(&first,&sine_fixture);load_image(&second,&sine_fixture);
    CHECK(first.context!=second.context && first.module.process!=second.module.process && first.info.descriptor_address!=second.info.descriptor_address);
    const rnbo_s3_module *reference=rnbo_s3_static_module();void *reference_context=NULL;
    rnbo_s3_create_options options={sizeof options,ARENA_BYTES,WARMUP,SEED};
    CHECK(reference->create(&options,&reference_context)==RNBO_S3_OK && reference->prepare(reference_context)==RNBO_S3_OK);
    uint32_t frequency=parameter_index(&first.module,first.context,"frequency");
    uint32_t level=parameter_index(&first.module,first.context,"level");
    CHECK(frequency==parameter_index(reference,reference_context,"frequency") && level==parameter_index(reference,reference_context,"level"));
    float converted,reference_converted;
    CHECK(first.module.parameter_convert(first.context,frequency,440.0f,0,&converted)==RNBO_S3_OK);
    CHECK(reference->parameter_convert(reference_context,frequency,440.0f,0,&reference_converted)==RNBO_S3_OK && converted==reference_converted);
    CHECK(first.module.parameter_convert(first.context,level,0.37f,1,&converted)==RNBO_S3_OK && converted==0.37f);
    float *a[2]={buffers[0],buffers[1]},*b[2]={buffers[2],buffers[3]},*expected[2]={buffers[4],buffers[5]};
    uint64_t position=0;
    for(unsigned block=0;block<blocks;++block) {
        if(block==4 || block==12) {
            float hz=block==4?110.0f:1760.0f;
            parameter(&first.module,first.context,frequency,hz,RNBO_S3_PARAMETER_ACTUAL);
            parameter(reference,reference_context,frequency,hz,RNBO_S3_PARAMETER_ACTUAL);
        }
        if(block==8) {
            parameter(&first.module,first.context,level,0.37f,RNBO_S3_PARAMETER_NORMALIZED);
            parameter(reference,reference_context,level,0.37f,RNBO_S3_PARAMETER_NORMALIZED);
        }
        reference_process(reference,reference_context,expected,position);
        position+=RNBO_S3_BLOCK_FRAMES;
        process(&first,NULL,a,&sine_timing);compare(a,expected);
    }
    float actual,normalized;
    CHECK(second.module.parameter_value(second.context,frequency,&actual,&normalized)==RNBO_S3_OK && actual==440.0f);
    CHECK(second.module.parameter_value(second.context,level,&actual,&normalized)==RNBO_S3_OK && actual==0.2f);
    rnbo_s3_stats untouched={.struct_bytes=sizeof untouched};
    CHECK(second.module.statistics(second.context,&untouched)==RNBO_S3_OK && untouched.blocks==0 && untouched.sample_position==0);
    /* Start the second image only after the first has advanced/changed params.
     * Its first output must equal a freshly reconstructed static reference. */
    reference_clean(reference,reference_context,position);reference->destroy(reference_context);reference_context=NULL;
    CHECK(reference->create(&options,&reference_context)==RNBO_S3_OK && reference->prepare(reference_context)==RNBO_S3_OK);
    reference_process(reference,reference_context,expected,0);
    process(&second,NULL,b,&sine_timing);compare(b,expected);
    rnbo_s3_parameter_info retained={.struct_bytes=sizeof retained};
    CHECK(first.module.parameter_info(first.context,frequency,&retained)==RNBO_S3_OK);
    /* Reconstruct an already-bound image without rerunning global constructors.
     * The sibling and a fresh static reference have matching initial state. */
    clean_image(&first);
    rnbo_s3_dynamic_stats previous={.struct_bytes=sizeof previous};
    CHECK(first.info.statistics(first.context,&previous)==RNBO_S3_OK);
    module_cpp_new_calls+=previous.cpp_new_calls;module_arena_allocations+=previous.total_arena_allocations;
    first.module.destroy(first.context);first.context=NULL;first.position=0;
    CHECK(first.module.create(&options,&first.context)==RNBO_S3_OK && first.module.prepare(first.context)==RNBO_S3_OK);
    process(&first,NULL,a,&sine_timing);compare(a,expected);
    unload_image(&first);
    CHECK(!strcmp(retained.id,"frequency")); /* shell-owned metadata survives unload */
    reference_process(reference,reference_context,expected,RNBO_S3_BLOCK_FRAMES);
    process(&second,NULL,b,&sine_timing);compare(b,expected); /* sibling remains callable */
    reference_clean(reference,reference_context,2*RNBO_S3_BLOCK_FRAMES);reference->destroy(reference_context);
    unload_image(&second);
}
static void fx_case(void)
{
    image effect;load_image(&effect,&fx_fixture);
    CHECK(effect.module.parameter_count(effect.context)==0);
    float *output[2]={buffers[0],buffers[1]};const float *input[2]={buffers[6],buffers[7]};
    for(unsigned block=0;block<8;++block) {
        for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {
            buffers[6][i]=((int)((i+block)%31)-15)*0.03125f;
            buffers[7][i]=((int)((i*3+block)%47)-23)*0.015625f;
        }
        process(&effect,input,output,&fx_timing);
        for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)CHECK(output[0][i]==input[0][i] && output[1][i]==input[1][i]);
    }
    allocation_probe_begin();
    int panic_result=effect.module.panic(effect.context);
    int process_result=effect.module.process(effect.context,input,output,RNBO_S3_BLOCK_FRAMES,effect.position);
    allocation_probe_end();CHECK(panic_result==RNBO_S3_OK && process_result==RNBO_S3_FAULT);
    for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)CHECK(output[0][i]==0 && output[1][i]==0);
    unload_image(&effect);
}
#if RNBO_TEST_HAVE_MIDI
static void midi(image *a,unsigned status,unsigned data1,unsigned data2)
{
    rnbo_s3_event event={.struct_bytes=sizeof event,.kind=RNBO_S3_MIDI,.midi_length=3,
        .midi={(uint8_t)status,(uint8_t)data1,(uint8_t)data2}};
    allocation_probe_begin();int result=a->module.event(a->context,&event);allocation_probe_end();CHECK(result==RNBO_S3_OK);
}
static double render_energy(image *a,unsigned blocks)
{
    float *output[2]={buffers[0],buffers[1]};double energy=0;
    for(unsigned b=0;b<blocks;++b) {
        process(a,NULL,output,&midi_timing);
        for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i) {CHECK(output[0][i]==output[1][i]);energy+=(double)output[0][i]*output[0][i];}
    }
    return energy/(blocks*RNBO_S3_BLOCK_FRAMES);
}
static void midi_spectrum(image *a)
{
    const unsigned notes[]={60,64,67,71};double real[4]={0},imaginary[4]={0},hz[4];
    for(unsigned n=0;n<4;++n)hz[n]=440.0*pow(2.0,((double)notes[n]-69.0)/12.0);
    float *output[2]={buffers[0],buffers[1]};
    const unsigned blocks=128;
    for(unsigned block=0;block<blocks;++block) {
        uint64_t at=a->position;process(a,NULL,output,&midi_timing);
        for(unsigned i=0;i<RNBO_S3_BLOCK_FRAMES;++i)for(unsigned n=0;n<4;++n) {
            double phase=6.2831853071795864769*hz[n]*(double)(at+i)/(double)RNBO_S3_SAMPLE_RATE;
            real[n]+=(double)output[0][i]*cos(phase);imaginary[n]+=(double)output[0][i]*sin(phase);
        }
        if((block&7u)==7u)vTaskDelay(pdMS_TO_TICKS(1));
    }
    for(unsigned n=0;n<4;++n) {
        double amplitude=2.0*hypot(real[n],imaginary[n])/(blocks*RNBO_S3_BLOCK_FRAMES);
        CHECK(amplitude>0.015);
        ESP_LOGI(TAG,"MIDI_SPECTRUM note=%u amplitude=%.9g",notes[n],amplitude);
    }
}
static void midi_case(bool spectrum)
{
    image instrument;load_image(&instrument,&midi_fixture);
    CHECK(instrument.module.flags&RNBO_S3_DISCARDS_MIDI_OUTPUT);
    CHECK(render_energy(&instrument,4)==0);
    const unsigned notes[]={60,64,67,71};
    for(unsigned i=0;i<4;++i)midi(&instrument,0x93,notes[i],100);
    CHECK(render_energy(&instrument,24)>0.000025);
    if(spectrum)midi_spectrum(&instrument);
    /* A different MIDI channel cannot release these four channel-four notes. */
    for(unsigned i=0;i<4;++i)midi(&instrument,0x84,notes[i],64);
    CHECK(render_energy(&instrument,8)>0.000025);
    for(unsigned i=0;i<4;++i)midi(&instrument,0x83,notes[i],64);
    (void)render_energy(&instrument,24);CHECK(render_energy(&instrument,8)<1e-14);
    unload_image(&instrument);
}
#endif
static void cycle(unsigned blocks)
{
    sine_pair(blocks);fx_case();
#if RNBO_TEST_HAVE_MIDI
    midi_case(blocks>16);
#endif
    CHECK(allocation_probe_allocations()==0 && allocation_probe_frees()==0);
    CHECK(heap_caps_check_integrity_all(true));
}
static void run(void *unused)
{
    (void)unused;
    /* main() may have just returned on core0. Allow its task cleanup and USB
     * attach to settle before the first memory observation. */
    vTaskDelay(pdMS_TO_TICKS(20));
    hex_digest(esp_app_get_description()->app_elf_sha256,firmware_sha);
    ESP_LOGI(TAG,"START firmware_elf_sha256=%s board=%s profile=%s cpu=%u sample_rate=%u block_frames=%u warmup=%u seed=%u scope=offline-no-I2S-UI-network",
             firmware_sha,RNBO_TEST_BOARD,RNBO_TEST_PROFILE,xPortGetCoreID(),RNBO_S3_SAMPLE_RATE,RNBO_S3_BLOCK_FRAMES,WARMUP,SEED);
    CHECK(esp_elf_find_symbol("printf")==0 && esp_elf_find_symbol("esp_restart")==0 && esp_elf_find_symbol("_Znwj")==0 && esp_elf_find_symbol("rnbo_s3_static_module")==0);
    verify_payload(&sine_fixture);verify_payload(&fx_fixture);
#if RNBO_TEST_HAVE_MIDI
    verify_payload(&midi_fixture);
#endif
    esp_elf_t malformed;CHECK(esp_elf_init(&malformed)==0);
    CHECK(esp_elf_relocate(&malformed,sine_start,16)!=0);esp_elf_deinit(&malformed);
    buffers=heap_caps_calloc(8,sizeof *buffers,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    CHECK(buffers && esp_ptr_external_ram(buffers));
    cycle(128); /* first-event paths and one-time shell allocation warm-up */
    vTaskDelay(pdMS_TO_TICKS(20));
    size_t psram_before=heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    size_t internal_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    for(unsigned i=0;i<CYCLES;++i) {
        cycle(16);vTaskDelay(pdMS_TO_TICKS(1));
        CHECK(heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)==psram_before);
        CHECK(heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)>=internal_before);
    }
    printf("RNBO_DYNAMIC_LOADER_TEST PASS firmware_elf_sha256=%s sine_elf_sha256=%s fx_elf_sha256=%s midi_elf_sha256=%s "
           "cycles=%u modules_per_cycle=%u loaded_images=%" PRIu64 " unloaded_images=%" PRIu64 " ctor_once=1 finalizers=1 globals_isolated=1 parameters=1 midi=%u midi_distinct_notes=%u fx_stereo=1 negative_handshakes=%" PRIu32 " same_image_reconstruct=1 panic=1 "
           "float_abs_tolerance=0 pcm_lsb_tolerance=0 compared_samples=%" PRIu64 " pcm_compared_samples=%" PRIu64 " "
           "late_allocations=0 host_heap_allocations=%" PRIu32 " host_heap_frees=%" PRIu32 " cpp_new_calls=%" PRIu64 " arena_allocations=%" PRIu64 " arena_high_water=%" PRIu32 " "
           "psram_before=%u psram_after=%u internal_before=%u internal_after=%u "
           "static_blocks=%" PRIu64 " static_total_us=%" PRIu64 " static_peak_us=%" PRIu32 " sine_blocks=%" PRIu64 " sine_total_us=%" PRIu64 " sine_peak_us=%" PRIu32 " "
           "fx_blocks=%" PRIu64 " fx_total_us=%" PRIu64 " midi_blocks=%" PRIu64 " midi_total_us=%" PRIu64 " stack_free=%u\n",
           firmware_sha,RNBO_TEST_SINE_SHA256,RNBO_TEST_FX_SHA256,RNBO_TEST_MIDI_SHA256,CYCLES,RNBO_TEST_HAVE_MIDI?4:3,constructors_checked,finalizers_checked,RNBO_TEST_HAVE_MIDI,RNBO_TEST_HAVE_MIDI?4:0,negative_handshakes,
           compared_samples,pcm_compared_samples,allocation_probe_allocations(),allocation_probe_frees(),module_cpp_new_calls,module_arena_allocations,maximum_arena_used,
           (unsigned)psram_before,(unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT),(unsigned)internal_before,(unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT),
           reference_timing.blocks,reference_timing.total_us,reference_timing.peak_us,sine_timing.blocks,sine_timing.total_us,sine_timing.peak_us,
           fx_timing.blocks,fx_timing.total_us,midi_timing.blocks,midi_timing.total_us,(unsigned)uxTaskGetStackHighWaterMark(NULL));
    fflush(stdout);heap_caps_free(buffers);vTaskDelete(NULL);
}
void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(2000));
    TaskHandle_t task=xTaskCreateStaticPinnedToCore(run,"rnbo_load_test",TEST_STACK,NULL,20,task_stack,&task_tcb,1);
    configASSERT(task);
}
