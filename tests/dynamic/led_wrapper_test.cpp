/* SPDX-License-Identifier: MIT */
/* Actual generated Max LED patch, wrapper, fixed lists and dynamic allocator. */
#include "rnbo_s3_dynamic.h"
#include "lifecycle.hpp"
#include <cassert>
#include <cstdio>
#include <cstring>
extern "C" int rnbo_test_module_entry(int,char**);
namespace rnbo_dynamic {std::uint32_t constructor_runs=1;volatile std::uint32_t *finalizer_observer=nullptr;std::uint32_t registered_finalizers(){return 1;}}
alignas(16) static unsigned char storage[2*1024*1024];
int main(){
    rnbo_s3_module m{};m.struct_bytes=sizeof m;rnbo_s3_dynamic_info info{};info.struct_bytes=sizeof info;
    rnbo_s3_dynamic_request r{sizeof r,RNBO_S3_DYNAMIC_MAGIC,1,0,RNBO_S3_DYNAMIC_DESCRIBE,nullptr,0,&m,&info,nullptr,0};
    char *args[]={reinterpret_cast<char*>(&r)};assert(rnbo_test_module_entry(1,args)==0);
    assert(m.abi_minor==1 && (m.flags&RNBO_S3_LED_OUTPUT) && m.led_snapshot);
    r.operation=RNBO_S3_DYNAMIC_BIND;r.state=storage;r.state_bytes=info.context_bytes+1024*1024;
    assert(rnbo_test_module_entry(1,args)==0);
    rnbo_s3_create_options options{sizeof options,1024*1024,4,123};void *context=nullptr;
    assert(m.create(&options,&context)==0 && m.prepare(context)==0);
    uint64_t position=0;float l[256],rr[256];float *out[]={l,rr};
    auto render=[&](){assert(m.process(context,nullptr,out,256,position)==0);position+=256;};
    auto snapshot=[&](){rnbo_s3_led_frame f{};f.struct_bytes=sizeof f;assert(m.led_snapshot(context,&f)==0);return f;};
    auto set=[&](float value){rnbo_s3_event e{sizeof e,RNBO_S3_PARAMETER_ACTUAL,0,value,0,0,{0},0};assert(m.event(context,&e)==0);render();return snapshot();};
    render();auto f=snapshot();assert(f.accepted>=1);for(unsigned i=0;i<12;++i)assert(f.rgb[i*3]==1&&f.rgb[i*3+1]==0);
    f=set(1);for(unsigned i=0;i<12;++i){assert(f.rgb[i*3]==(i==3?0:1));assert(f.rgb[i*3+1]==(i==3?1:0));}
    f=set(2);assert(f.rgb[33]==0 && f.rgb[35]==1 && f.rgb[10]==1 && f.rgb[0]==1);
    f=set(3);for(unsigned i=0;i<36;++i)assert(f.rgb[i]==(i%3==2?.5f:0));
    float keep[36];std::memcpy(keep,f.rgb,sizeof keep);auto rejected=f.rejected;
    for(unsigned mode=4;mode<=6;++mode){f=set((float)mode);assert(!std::memcmp(keep,f.rgb,sizeof keep));}
    assert(f.rejected==rejected+3);
    f=set(7);for(unsigned i=0;i<12;++i)assert(f.rgb[i*3]==0&&f.rgb[i*3+1]==.5f&&f.rgb[i*3+2]==1);
    for(unsigned i=0;i<1000;++i)set((float)(i%10));
    rnbo_s3_stats stats{};stats.struct_bytes=sizeof stats;assert(m.statistics(context,&stats)==0);
    rnbo_s3_dynamic_stats extra{};extra.struct_bytes=sizeof extra;assert(info.statistics(context,&extra)==0);
    assert(!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations&&!extra.total_late_allocations&&!extra.bootstrap_allocation_attempts);
    m.destroy(context);puts("PASS: genuine Max RGB3/4/36 outputs, rejected updates, 1000 changes, zero late allocations");
}
