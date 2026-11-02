/* SPDX-License-Identifier: MIT */
#include "rnbo_s3_module.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>

/* Test executable only: observe C++ allocations around owner callbacks.
 * The firmware does not replace process-wide new/delete. Direct libc malloc
 * remains outside this probe; target task-aware heap qualification is needed. */
static bool observe=false;
static unsigned cpp_allocations=0;
static unsigned cpp_live=0;
void *operator new(std::size_t n) {
    if(observe)++cpp_allocations;
    if(void *p=std::malloc(n?n:1)){++cpp_live;return p;}
    throw std::bad_alloc();
}
void *operator new[](std::size_t n) {return ::operator new(n);}
void operator delete(void *p) noexcept {if(p)--cpp_live;std::free(p);}
void operator delete[](void *p) noexcept {::operator delete(p);}
void operator delete(void *p,std::size_t) noexcept {::operator delete(p);}
void operator delete[](void *p,std::size_t) noexcept {::operator delete(p);}
void *operator new(std::size_t n,std::align_val_t alignment) {
    if(observe)++cpp_allocations;
    void *p=nullptr;
    if(!posix_memalign(&p,static_cast<std::size_t>(alignment),n?n:1)){++cpp_live;return p;}
    throw std::bad_alloc();
}
void *operator new[](std::size_t n,std::align_val_t a) {return ::operator new(n,a);}
void operator delete(void *p,std::align_val_t) noexcept {::operator delete(p);}
void operator delete[](void *p,std::align_val_t) noexcept {::operator delete(p);}
void operator delete(void *p,std::size_t,std::align_val_t) noexcept {::operator delete(p);}
void operator delete[](void *p,std::size_t,std::align_val_t) noexcept {::operator delete(p);}

int main() {
    const rnbo_s3_module *m=rnbo_s3_static_module();
    assert(m->struct_bytes>=sizeof(*m) && m->abi_major==1 && m->block_frames==256);
    assert(m->sample_rate==44100 && m->audio_outputs==2);
    assert(m->flags&RNBO_S3_SINGLE_INSTANCE);
    rnbo_s3_create_options options{sizeof(options),1024*1024,1,12345};
    float reference[2][256]{};
    const unsigned initial_cpp_live=cpp_live;
    for(unsigned round=0;round<16;++round) {
        void *ctx=nullptr;
        assert(m->create(&options,&ctx)==0 && ctx);
        void *second=nullptr;
        assert(m->create(&options,&second)==RNBO_S3_BUSY && !second);
        assert(m->prepare(ctx)==0);
        assert(m->prepare(ctx)==RNBO_S3_INVALID);
        for(unsigned i=0;i<m->parameter_count(ctx);++i) {
            rnbo_s3_parameter_info info{};info.struct_bytes=sizeof(info);
            assert(m->parameter_info(ctx,i,&info)==0 && *info.id);
            float actual,normalized,converted;
            assert(m->parameter_value(ctx,i,&actual,&normalized)==0);
            assert(normalized>=0 && normalized<=1);
            assert(m->parameter_convert(ctx,i,normalized,1,&converted)==0);
            assert(std::fabs(converted-actual)<=1e-4f*std::fmax(1.0f,std::fabs(actual)));
            rnbo_s3_event e{};e.struct_bytes=sizeof(e);e.kind=RNBO_S3_PARAMETER_NORMALIZED;e.parameter_index=i;
            e.value=std::numeric_limits<float>::quiet_NaN();
            assert(m->event(ctx,&e)==RNBO_S3_INVALID);
            e.value=1.1f;assert(m->event(ctx,&e)==RNBO_S3_INVALID);
            e.value=normalized;observe=true;assert(m->event(ctx,&e)==0);observe=false;
        }
        float left[256],right[256],in_left[256],in_right[256];
        for(unsigned i=0;i<256;++i){in_left[i]=0.25f;in_right[i]=-0.125f;left[i]=right[i]=1;}
        const float *in[]={in_left,in_right};float *out[]={left,right};
        assert(m->process(ctx,in,out,64,0)==RNBO_S3_INVALID);
        assert(m->process(ctx,in,out,256,256)==RNBO_S3_INVALID);
        for(unsigned i=0;i<256;++i)assert(left[i]==0 && right[i]==0);
        for(unsigned block=0;block<128;++block) {
            observe=true;
            int result=m->process(ctx,m->audio_inputs?in:nullptr,out,256,block*uint64_t(256));
            observe=false;assert(result==0);
            for(unsigned i=0;i<256;++i)assert(std::isfinite(left[i]) && std::isfinite(right[i]));
            if(block==0) {
                if(round==0) {std::memcpy(reference[0],left,sizeof left);std::memcpy(reference[1],right,sizeof right);}
                else {assert(!std::memcmp(reference[0],left,sizeof left));assert(!std::memcmp(reference[1],right,sizeof right));}
            }
        }
        rnbo_s3_event invalid{};invalid.struct_bytes=sizeof(invalid);invalid.kind=RNBO_S3_MIDI;
        invalid.midi_length=3;invalid.midi[0]=0x90;invalid.midi[1]=200;
        assert(m->event(ctx,&invalid)==RNBO_S3_INVALID);
        assert(m->panic(ctx)==0);
        observe=true;assert(m->process(ctx,in,out,256,128*uint64_t(256))==RNBO_S3_FAULT);observe=false;
        for(unsigned i=0;i<256;++i)assert(left[i]==0 && right[i]==0);
        rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
        assert(!stats.errors && !stats.invalid_samples && !stats.late_platform_allocations);
        assert(stats.blocks==128 && stats.sample_position==128*256 && stats.warmup_blocks==1);
        assert(cpp_allocations==0);
        m->destroy(ctx);
        assert(cpp_live==initial_cpp_live); // generated objects must retire too
        assert(m->statistics(ctx,&stats)==RNBO_S3_INVALID);
    }
    puts("rnbo_contract: 16 deterministic lifecycles, parameter conversions, planar render, vector/time rejection, Panic, zero observed late platform/C++ allocations passed");
}
