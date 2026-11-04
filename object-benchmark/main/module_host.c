/* SPDX-License-Identifier: MIT */
/* Admission and lifecycle checks adapted from the physically qualified
 * rnbo-loader-test. This separate benchmark does not modify that candidate. */
#include "module_host.h"
#include "mapped_range.h"
#include "bench_check.h"
#include "esp_heap_caps.h"
#include "esp_memory_utils.h"
#include <string.h>

/* Hardware smoke can admit a larger caller arena without changing other benches. */
#ifndef RNBO_TEST_MAX_ARENA_BYTES
#define RNBO_TEST_MAX_ARENA_BYTES (1024u*1024u)
#endif
_Static_assert(RNBO_TEST_MAX_ARENA_BYTES>=4096u && RNBO_TEST_MAX_ARENA_BYTES<=4u*1024u*1024u,
               "caller arena cap must stay within the dynamic ABI");
static bool caller_arena_allowed(uint32_t bytes)
{
    return bytes>=4096u && bytes<=RNBO_TEST_MAX_ARENA_BYTES;
}
_Static_assert(sizeof(void*)==4 && sizeof(void(*)(void))==4,"Xtensa32 ABI required");
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
static void admit_table(object_image *a,uint32_t role)
{
    rnbo_s3_module *m=&a->module;rnbo_s3_dynamic_info *d=&a->info;
    CHECK(d->struct_bytes==sizeof *d && d->abi_major==RNBO_S3_DYNAMIC_ABI_MAJOR && d->abi_minor<=RNBO_S3_DYNAMIC_ABI_MINOR && d->pointer_bits==32);
    uint32_t required=RNBO_S3_DYNAMIC_CALLER_STATE|RNBO_S3_DYNAMIC_PRIVATE_CPP_ALLOCATOR|RNBO_S3_DYNAMIC_DETERMINISTIC_SAMPLE_CLOCK;
    CHECK(d->flags==required && d->constructor_runs==1 && d->registered_finalizers>0);
    CHECK(d->state_alignment>=16 && d->state_alignment<=64 && !(d->state_alignment&(d->state_alignment-1)));
    CHECK(d->context_bytes && d->context_bytes<=1024u*1024u && d->minimum_arena_bytes>=4096 && d->minimum_arena_bytes<=a->arena_bytes);
    CHECK(d->maximum_arena_bytes>=a->arena_bytes && d->maximum_arena_bytes<=4u*1024u*1024u && d->minimum_state_bytes>=d->context_bytes && d->maximum_state_bytes<=5u*1024u*1024u);
    CHECK(d->minimum_state_bytes<=d->maximum_state_bytes && d->minimum_state_bytes-d->context_bytes>=d->minimum_arena_bytes);
    CHECK(d->maximum_state_bytes>=d->context_bytes && d->maximum_state_bytes-d->context_bytes>=d->maximum_arena_bytes);
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
static void request(object_image *a,unsigned operation,void *state,uint32_t bytes,int expected)
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

void object_image_load(object_image *a,const uint8_t *payload,size_t bytes,uint32_t role,uint32_t arena_bytes)
{
    memset(a,0,sizeof *a);a->arena_bytes=arena_bytes;
    CHECK(caller_arena_allowed(arena_bytes));
    CHECK(((uintptr_t)payload&3u)==0 && esp_elf_init(&a->elf)==0);
    CHECK(esp_elf_relocate(&a->elf,payload,bytes)==0);a->loaded=true;
    CHECK(executable(&a->elf,(uintptr_t)a->elf.entry) && esp_ptr_external_ram(a->elf.ptext));
    CHECK(!a->elf.init_done && a->elf.init_count && a->elf.fini_count);
    lifecycle_array(&a->elf,a->elf.preinit_array,a->elf.preinit_count,ELF_SEC_PREINIT);
    lifecycle_array(&a->elf,a->elf.init_array,a->elf.init_count,ELF_SEC_INIT);
    lifecycle_array(&a->elf,a->elf.fini_array,a->elf.fini_count,ELF_SEC_FINI);
    request(a,RNBO_S3_DYNAMIC_DESCRIBE,NULL,0,RNBO_S3_OK);admit_table(a,role);
    CHECK(a->elf.init_done);
    request(a,RNBO_S3_DYNAMIC_DESCRIBE,NULL,0,RNBO_S3_OK);admit_table(a,role);
    CHECK(a->info.context_bytes<=UINT32_MAX-arena_bytes);
    a->state_bytes=a->info.context_bytes+arena_bytes;
    CHECK(a->state_bytes>=a->info.minimum_state_bytes && a->state_bytes<=a->info.maximum_state_bytes);
    a->state=heap_caps_aligned_alloc(a->info.state_alignment,a->state_bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    CHECK(a->state && esp_ptr_external_ram(a->state));
    request(a,RNBO_S3_DYNAMIC_BIND,a->state,a->state_bytes,RNBO_S3_OK);admit_table(a,role);
}
void object_image_prepare(object_image *a,uint32_t warmup,uint32_t seed)
{
    CHECK(a->loaded && !a->context && !a->finalized);
    rnbo_s3_create_options options={sizeof options,a->arena_bytes,warmup,seed};
    CHECK(a->module.create(&options,&a->context)==RNBO_S3_OK);
    CHECK(rnbo_test_range((uintptr_t)a->state,a->state_bytes,(uintptr_t)a->context,a->info.context_bytes));
    CHECK(a->module.prepare(a->context)==RNBO_S3_OK);a->position=0;
}
void object_image_statistics(object_image *a,rnbo_s3_stats *base,rnbo_s3_dynamic_stats *extra)
{
    *base=(rnbo_s3_stats){.struct_bytes=sizeof *base};
    *extra=(rnbo_s3_dynamic_stats){.struct_bytes=sizeof *extra};
    CHECK(a->module.statistics(a->context,base)==RNBO_S3_OK && a->info.statistics(a->context,extra)==RNBO_S3_OK);
    CHECK(!base->errors && !base->invalid_samples && !base->late_platform_allocations && !base->faulted);
    CHECK(!extra->late_cpp_new_calls && !extra->total_late_allocations && !extra->bootstrap_allocation_attempts);
    CHECK(extra->arena_used<=extra->arena_capacity && extra->arena_high_water<=extra->arena_capacity && extra->arena_capacity==a->arena_bytes);
    CHECK(base->sample_position==a->position);
}
void object_image_destroy_context(object_image *a)
{
    CHECK(a->loaded && a->context && !a->finalized);
    rnbo_s3_stats base;rnbo_s3_dynamic_stats extra;object_image_statistics(a,&base,&extra);
    a->module.destroy(a->context);a->context=NULL;a->position=0;CHECK(!a->finalized);
}
void object_image_unload(object_image *a)
{
    CHECK(a->loaded && !a->context && !a->finalized);
    esp_elf_deinit(&a->elf);CHECK(a->finalized==1);
    heap_caps_free(a->state);memset(a,0,sizeof *a);
}
