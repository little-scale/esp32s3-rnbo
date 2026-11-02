/* SPDX-License-Identifier: MIT */
/* Host-only callback fault test. Actual dynamic wrapper/allocator, with one
 * explicit injected generated-process allocation. It does not test ELF unload
 * or real module constructors; those remain the isolated target harness. */
#include "rnbo_s3_dynamic.h"
#include "lifecycle.hpp"
#include <cassert>
#include <cstdint>
#include <cstring>

extern "C" int rnbo_test_module_entry(int,char **);
extern "C" { int rnbo_test_allocation_mode=0; }
namespace rnbo_dynamic {
std::uint32_t constructor_runs=1;
volatile std::uint32_t *finalizer_observer=nullptr;
std::uint32_t registered_finalizers(){return 1;}
}
alignas(4096) static unsigned char storage[2*1024*1024];

int main(int argc,char **argv)
{
    assert(argc==2);
    rnbo_test_allocation_mode=!std::strcmp(argv[1],"cpp")?1:!std::strcmp(argv[1],"platform")?2:0;
    rnbo_s3_module module{};module.struct_bytes=sizeof module;
    rnbo_s3_dynamic_info info{};info.struct_bytes=sizeof info;
    rnbo_s3_dynamic_request request{};request.struct_bytes=sizeof request;
    request.magic=RNBO_S3_DYNAMIC_MAGIC;request.abi_major=RNBO_S3_DYNAMIC_ABI_MAJOR;
    request.operation=RNBO_S3_DYNAMIC_DESCRIBE;request.out_module=&module;request.out_info=&info;
    auto invoke=[&](int expected){
        request.result=RNBO_S3_DYNAMIC_RESULT_PENDING;
        char *arguments[]={reinterpret_cast<char*>(&request)};
        assert(rnbo_test_module_entry(1,arguments)==expected);
        assert(request.result==expected);
    };
    invoke(RNBO_S3_OK);
    request.operation=RNBO_S3_DYNAMIC_BIND;
    request.state=storage;request.state_bytes=info.maximum_state_bytes+16;
    invoke(RNBO_S3_INVALID);
    request.state=reinterpret_cast<void*>(UINTPTR_MAX-15);request.state_bytes=info.minimum_state_bytes;
    invoke(RNBO_S3_INVALID);
    // A base that is16-byte aligned but deliberately not32-byte aligned.
    request.state=storage+16;request.state_bytes=info.context_bytes+1024*1024;
    assert(request.state_bytes<=sizeof storage-16);invoke(RNBO_S3_OK);
    rnbo_s3_create_options options{sizeof options,1024*1024,1,12345};
    void *context=nullptr;
    assert(module.create(&options,&context)==RNBO_S3_OK && context);
    assert(module.prepare(context)==RNBO_S3_OK);
    float left[256],right[256];float *outputs[]={left,right};
    for(auto &value:left)value=123;
    for(auto &value:right)value=123;
    int status=module.process(context,nullptr,outputs,256,0);
    rnbo_s3_dynamic_stats extra{};extra.struct_bytes=sizeof extra;
    rnbo_s3_stats base{};base.struct_bytes=sizeof base;
    assert(info.statistics(context,&extra)==RNBO_S3_OK);
    assert(module.statistics(context,&base)==RNBO_S3_OK);
    assert(extra.arena_used<=extra.arena_capacity && extra.bootstrap_allocation_attempts==0);
    if(rnbo_test_allocation_mode) {
        assert(status==RNBO_S3_FAULT && base.faulted);
        assert(extra.total_late_allocations==1);
        assert(extra.late_cpp_new_calls==(rnbo_test_allocation_mode==1?1u:0u));
        assert(base.late_platform_allocations==(rnbo_test_allocation_mode==2?1u:0u));
        // The same block that allocated must be entirely silent.
        for(float value:left)assert(value==0);
        for(float value:right)assert(value==0);
        assert(module.process(context,nullptr,outputs,256,256)==RNBO_S3_FAULT);
        assert(info.statistics(context,&extra)==RNBO_S3_OK && extra.total_late_allocations==1);
    } else {
        assert(status==RNBO_S3_OK && !base.faulted && !extra.total_late_allocations);
        bool sound=false;for(float value:left)if(value!=0)sound=true;assert(sound);
    }
    module.destroy(context);
    return 0;
}
