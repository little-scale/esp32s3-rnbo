/* SPDX-License-Identifier: MIT */
/* Portable failure/lifetime tests of the ACTUAL player_loader.c. The single
 * Xtensa32 sizeof assertion is disabled in this host inclusion only. ELF
 * relocation and RNBO callbacks are explicit doubles; no native ELF, hardware,
 * sandbox or arbitrary-code safety qualification is implied. */
#define _POSIX_C_SOURCE 200112L
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define _Static_assert(condition, message)
#include "player_loader.c"
#undef _Static_assert

enum {GOOD, BAD_ELF, IMPORT, NO_SYMBOLS, RELOCATE_FAIL, BAD_ENTRY, BAD_PSRAM,
      BAD_INIT, BAD_FINI, BAD_CALLBACK, BAD_DESCRIPTOR, BAD_ROLE, BAD_FLAGS,
      BAD_BOUNDS, BAD_CONSTRUCTORS, DESCRIBE_FAIL, DESCRIBE_CHANGED, BIND_FAIL,
      STATE_OOM, CREATE_FAIL, CREATE_BAD_POINTER, PREPARE_FAIL, PARAM_LIMIT,
      PARAM_STRING, PARAM_DUPLICATE, PARAM_READBACK, STATS_FAIL, BAD_SAMPLES,
      LATE_ALLOCATIONS, BAD_POSITION, BAD_ARENA, COPY_OOM};
static int mode, requests, creates, prepares, destroys, deinits, allocations, frees, active;
static void *bound;
static volatile uint32_t *observer;
static rnbo_s3_module descriptor;
static void (*init_functions[1])(void), (*fini_functions[1])(void);
static unsigned char payload[512] __attribute__((aligned(16)));
static char actions[128];
static unsigned action_count;

static void action(char c) {assert(action_count+1<sizeof actions); actions[action_count++]=c; actions[action_count]=0;}
static void reset(int selected)
{
    mode=selected; requests=creates=prepares=destroys=deinits=allocations=frees=active=0;
    bound=NULL; observer=NULL; action_count=0; actions[0]=0;
    memset(payload,0,sizeof payload);
    elf32_hdr_t *h=(void *)payload; h->shoff=64; h->shnum=2;
    elf32_shdr_t *s=(void *)(payload+64);
    s[0]=(elf32_shdr_t){.type=SHT_STRTAB,.offset=256,.size=8};
    s[1]=(elf32_shdr_t){.type=SHT_SYMTAB,.offset=224,.size=sizeof(elf32_sym_t),.link=0};
    if(selected==IMPORT) {elf32_sym_t *sym=(void *)(payload+224);sym->name=1;payload[257]='x';}
    if(selected==NO_SYMBOLS) s[1].type=0;
}

void *heap_caps_aligned_alloc(size_t alignment,size_t bytes,unsigned caps)
{
    assert(caps==(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
    if(mode==STATE_OOM || mode==COPY_OOM) return NULL;
    void *p=NULL; if(posix_memalign(&p,alignment,bytes))return NULL;
    ++allocations; action('A'); return p;
}
void heap_caps_free(void *p)
{
    if(!p)return;
    if(p==bound) {assert(!active);assert(deinits>0);action('S');bound=NULL;}
    else action('T');
    ++frees;free(p);
}
bool esp_ptr_external_ram(const void *p) {return p && mode!=BAD_PSRAM;}
int esp_elf_validate(const uint8_t *p,size_t bytes)
{
    assert(p && !((uintptr_t)p&3) && bytes==sizeof payload);
    return mode==BAD_ELF?-1:0;
}
static int create(const rnbo_s3_create_options *options,void **context)
{
    assert(options->arena_bytes>=4096 && options->warmup_blocks==4 && options->seed==0x12345678);
    ++creates;action('C');*context=bound;active=1;
    if(mode==CREATE_BAD_POINTER) {*context=NULL;active=0;return RNBO_S3_FAULT;}
    return mode==CREATE_FAIL?RNBO_S3_FAULT:RNBO_S3_OK;
}
static int prepare(void *p) {assert(p==bound);++prepares;action('P');return mode==PREPARE_FAIL?RNBO_S3_FAULT:RNBO_S3_OK;}
static int process(void *p,const float *const *i,float *const *o,uint32_t n,uint64_t t)
{(void)p;(void)i;(void)o;(void)n;(void)t;return RNBO_S3_OK;}
static int event(void *p,const rnbo_s3_event *e) {(void)p;(void)e;return RNBO_S3_OK;}
static int panic_callback(void *p) {(void)p;return RNBO_S3_OK;}
static uint32_t parameter_count(void *p) {(void)p;return mode==PARAM_LIMIT?33:mode==PARAM_DUPLICATE?2:1;}
static int parameter_info(void *p,uint32_t i,rnbo_s3_parameter_info *out)
{
    assert(p==bound);*out=(rnbo_s3_parameter_info){.struct_bytes=sizeof *out,.index=i,
        .minimum=0,.maximum=100,.initial=50,.exponent=1};
    strcpy(out->id,"freq");strcpy(out->name,"Frequency");
    if(mode==PARAM_STRING) memset(out->id,'x',sizeof out->id);
    return RNBO_S3_OK;
}
static int parameter_value(void *p,uint32_t i,float *actual,float *normalized)
{assert(p==bound);(void)i;*actual=50;*normalized=mode==PARAM_READBACK?2:.5f;return RNBO_S3_OK;}
static int parameter_convert(void *p,uint32_t i,float v,uint32_t n,float *r)
{(void)p;(void)i;(void)n;*r=v;return RNBO_S3_OK;}
static int statistics(void *p,rnbo_s3_stats *out)
{
    assert(p==bound);*out=(rnbo_s3_stats){.struct_bytes=sizeof *out,.arena_capacity=4096,.warmup_blocks=4};
    if(mode==BAD_SAMPLES)out->invalid_samples=1;
    if(mode==BAD_POSITION)out->sample_position=256;
    return mode==STATS_FAIL?RNBO_S3_FAULT:RNBO_S3_OK;
}
static int dynamic_statistics(void *p,rnbo_s3_dynamic_stats *out)
{
    assert(p==bound);*out=(rnbo_s3_dynamic_stats){.struct_bytes=sizeof *out,.arena_capacity=4096};
    if(mode==LATE_ALLOCATIONS)out->total_late_allocations=1;
    if(mode==BAD_ARENA)out->arena_used=4097;
    return RNBO_S3_OK;
}
static void destroy(void *p) {assert(p==bound && active);++destroys;active=0;action('D');}
static void constructor(void) {}
static void finalizer(void) {}
static int entry(int argc,char **argv)
{
    assert(argc==1);rnbo_s3_dynamic_request *r=(void *)argv[0];++requests;
    descriptor=(rnbo_s3_module){.struct_bytes=sizeof descriptor,.abi_major=1,.pointer_bits=32,
        .sample_rate=44100,.block_frames=256,.role=RNBO_S3_MAIN,.audio_outputs=2,.max_parameters=128,
        .flags=RNBO_S3_SINGLE_INSTANCE|RNBO_S3_BOUNDARY_EVENTS|RNBO_S3_PLATFORM_ALLOCATIONS_ONLY,
        .create=create,.prepare=prepare,.process=process,.event=event,.panic=panic_callback,
        .parameter_count=parameter_count,.parameter_info=parameter_info,.parameter_value=parameter_value,
        .parameter_convert=parameter_convert,.statistics=statistics,.destroy=destroy};
    if(mode==BAD_CALLBACK)descriptor.process=(void *)1;
    if(mode==BAD_DESCRIPTOR)descriptor.block_frames=64;
    if(mode==BAD_ROLE)descriptor.role=RNBO_S3_FX;
    if(mode==BAD_FLAGS)descriptor.flags|=0x100;
    if(mode==DESCRIBE_CHANGED && requests==2)descriptor.flags|=RNBO_S3_DISCARDS_MIDI_OUTPUT;
    *r->out_module=descriptor;
    *r->out_info=(rnbo_s3_dynamic_info){.struct_bytes=sizeof *r->out_info,.abi_major=1,.pointer_bits=32,
        .state_alignment=16,.context_bytes=256,.minimum_arena_bytes=4096,.maximum_arena_bytes=4194304,
        .minimum_state_bytes=4352,.maximum_state_bytes=4194560,.flags=7,.constructor_runs=1,
        .registered_finalizers=1,.descriptor_address=&descriptor,.statistics=dynamic_statistics};
    if(mode==BAD_CONSTRUCTORS)r->out_info->constructor_runs=2;
    if(mode==BAD_BOUNDS)r->out_info->maximum_state_bytes=1;
    if(r->operation==RNBO_S3_DYNAMIC_BIND) {
        if(mode==BIND_FAIL) {r->result=RNBO_S3_INVALID;return 0;}
        bound=r->state;observer=r->finalizer_observer;
    }
    r->result=mode==DESCRIBE_FAIL?RNBO_S3_FAULT:RNBO_S3_OK;return 0;
}
int esp_elf_init(esp_elf_t *e) {memset(e,0,sizeof *e);return 0;}
int esp_elf_relocate(esp_elf_t *e,const uint8_t *p,size_t bytes)
{
    (void)p;(void)bytes;if(mode==RELOCATE_FAIL)return -1;
    uintptr_t low=UINTPTR_MAX,high=0;
    uintptr_t functions[]={(uintptr_t)entry,(uintptr_t)create,(uintptr_t)prepare,(uintptr_t)process,
        (uintptr_t)event,(uintptr_t)panic_callback,(uintptr_t)parameter_count,(uintptr_t)parameter_info,
        (uintptr_t)parameter_value,(uintptr_t)parameter_convert,(uintptr_t)statistics,(uintptr_t)destroy,
        (uintptr_t)dynamic_statistics,(uintptr_t)constructor,(uintptr_t)finalizer};
    for(unsigned i=0;i<sizeof functions/sizeof *functions;++i){if(functions[i]<low)low=functions[i];if(functions[i]>high)high=functions[i];}
    e->sec[ELF_SEC_TEXT]=(esp_elf_sec_t){low,(uint32_t)(high-low+128)};
    e->sec[ELF_SEC_DATA]=(esp_elf_sec_t){(uintptr_t)&descriptor,sizeof descriptor};
    e->entry=mode==BAD_ENTRY?(int (*)(int,char **))1:entry;e->ptext=(void *)low;
    init_functions[0]=mode==BAD_INIT?(void (*)(void))1:constructor;
    fini_functions[0]=mode==BAD_FINI?(void (*)(void))1:finalizer;
    e->init_array=init_functions;e->init_count=1;e->fini_array=fini_functions;e->fini_count=1;
    e->sec[ELF_SEC_INIT]=(esp_elf_sec_t){(uintptr_t)init_functions,sizeof init_functions};
    e->sec[ELF_SEC_FINI]=(esp_elf_sec_t){(uintptr_t)fini_functions,sizeof fini_functions};
    return 0;
}
uintptr_t esp_elf_runtime_base(esp_elf_t *e) {return e->sec[ELF_SEC_TEXT].addr;}
int esp_elf_request(esp_elf_t *e,int options,int argc,char **argv)
{(void)options;e->init_done=true;return e->entry(argc,argv);}
void esp_elf_deinit(esp_elf_t *e)
{
    assert(!active);++deinits;action('F');
    if(e->init_done && observer)++*observer;
    memset(e,0,sizeof *e);
}

int main(void)
{
    char error[160];player_image a={0};
    reset(GOOD);
    assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_MAIN,4096,error,sizeof error)==ESP_OK);
    assert(a.context && a.loaded && a.parameter_count==1 && a.text_bytes && a.executable_base);
    assert(requests==3 && creates==1 && prepares==1);
    assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_MAIN,4096,error,sizeof error)==ESP_ERR_INVALID_STATE);
    assert(a.loaded && !destroys);
    player_image_unload(&a);assert(!a.loaded && !a.context && !a.state && destroys==1);
    assert(strstr(actions,"DFS") && allocations==frees);
    player_image_unload(&a);assert(destroys==1);
    for(int selected=BAD_ELF;selected<=BAD_ARENA;++selected) {
        reset(selected);a=(player_image){0};
        assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_MAIN,4096,error,sizeof error)!=ESP_OK);
        assert(error[0] && !a.loaded && !a.context && !a.state && !active && allocations==frees);
        if(selected>=CREATE_FAIL && selected!=CREATE_BAD_POINTER)assert(destroys==1);
        if(selected==BAD_ELF || selected==IMPORT || selected==NO_SYMBOLS)assert(!requests && !creates);
        if(selected==BAD_ENTRY || selected==BAD_INIT || selected==BAD_FINI)assert(!requests);
    }
    reset(GOOD);unsigned char unaligned[513] __attribute__((aligned(16)));memcpy(unaligned+1,payload,sizeof payload);
    assert(player_image_load(&a,unaligned+1,sizeof payload,RNBO_S3_MAIN,4096,error,sizeof error)==ESP_OK);
    assert(allocations==2 && frees==1);player_image_unload(&a);assert(allocations==frees);
    reset(COPY_OOM);
    assert(player_image_load(&a,unaligned+1,sizeof payload,RNBO_S3_MAIN,4096,error,sizeof error)==ESP_ERR_NO_MEM);
    reset(GOOD);char tiny[2]={1,1};
    assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_FX,4096,tiny,sizeof tiny)==ESP_ERR_INVALID_ARG);
    assert(tiny[1]==0 && !allocations && !requests);
    assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_MAIN,PLAYER_MAX_ARENA_BYTES+1,NULL,0)==ESP_ERR_INVALID_ARG);
    assert(player_image_load(&a,payload,sizeof payload,RNBO_S3_MAIN,4095,NULL,0)==ESP_ERR_INVALID_ARG);
    assert(player_image_load(&a,NULL,0,RNBO_S3_MAIN,4096,NULL,0)==ESP_ERR_INVALID_ARG);
    assert(player_image_statistics(&a,error,sizeof error)==ESP_ERR_INVALID_STATE);
    player_image_unload(NULL);
    puts("player loader: success, partial failures, cleanup order and Main-only admission PASS");
    return 0;
}
