// SPDX-License-Identifier: MIT
// Unit-aware finite binary32 stream preflight for one boundary-controlled stereo FX module.
// Supply inputs, twenty expected blocks, and21(call,value-word) event pairs.
#include "rnbo_s3_module.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

static bool observing=false;
static unsigned allocations=0;
void *operator new(std::size_t n){if(observing)++allocations;if(void *p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void *operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void *p)noexcept{std::free(p);}
void operator delete[](void *p)noexcept{std::free(p);}
void operator delete(void *p,std::size_t)noexcept{std::free(p);}
void operator delete[](void *p,std::size_t)noexcept{std::free(p);}
void *operator new(std::size_t n,std::align_val_t a){if(observing)++allocations;void *p=nullptr;
    if(!posix_memalign(&p,static_cast<size_t>(a),n?n:1))return p;throw std::bad_alloc();}
void *operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void *p,std::align_val_t)noexcept{std::free(p);}
void operator delete[](void *p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void *p,std::size_t,std::align_val_t)noexcept{std::free(p);}
void operator delete[](void *p,std::size_t,std::align_val_t)noexcept{std::free(p);}

static void read(const char *path,void *out,size_t bytes){
    FILE *f=fopen(path,"rb");assert(f);assert(fread(out,1,bytes,f)==bytes&&fgetc(f)==EOF);fclose(f);
}
int main(int argc,char **argv){
    assert(argc==5);float tolerance=std::strtof(argv[4],nullptr);assert(std::isfinite(tolerance)&&tolerance>=0&&tolerance<=.008f);uint32_t events[42],input[512],expected[10240];read(argv[3],events,sizeof events);read(argv[1],input,sizeof input);read(argv[2],expected,sizeof expected);
    const auto *m=rnbo_s3_static_module();assert(m->role==RNBO_S3_FX);
    void *ctx=nullptr;rnbo_s3_create_options options{sizeof(options),4096,0,12345};
    assert(m->create(&options,&ctx)==0&&m->prepare(ctx)==0&&m->parameter_count(ctx)==1);
    rnbo_s3_parameter_info info{};info.struct_bytes=sizeof info;
    assert(m->parameter_info(ctx,0,&info)==0&&!strcmp(info.id,"drive"));
    assert(info.minimum==-8&&info.maximum==8&&info.initial==0&&info.exponent==1&&info.steps==0);
    unsigned next_event=0;
    float in[2][256],out[2][256];const float *inputs[]={in[0],in[1]};float *outputs[]={out[0],out[1]};
    for(unsigned i=0;i<512;++i)memcpy(&in[i%2][i/2],input+i,4);
    unsigned mismatches=0,bit_differences=0,within=0;double maximum=0;
    for(unsigned block=0;block<20;++block){
        while(next_event<21&&events[next_event*2]==block){
            rnbo_s3_event event{};event.struct_bytes=sizeof event;event.kind=RNBO_S3_PARAMETER_ACTUAL;
            event.parameter_index=0;memcpy(&event.value,events+next_event*2+1,4);
            observing=true;int status=m->event(ctx,&event);observing=false;assert(status==0);
            float actual,normalized;assert(m->parameter_value(ctx,0,&actual,&normalized)==0);
            assert(actual==event.value&&normalized==(event.value+8)/16);
            ++next_event;
        }
        observing=true;int result=m->process(ctx,inputs,outputs,256,uint64_t(block)*256);observing=false;
        if(result!=0){
            rnbo_s3_stats fault{};fault.struct_bytes=sizeof(fault);assert(m->statistics(ctx,&fault)==0);
            printf("{\"samples\":%u,\"process_status\":%d,\"fault_call\":%u,\"platform_errors\":%llu,\"invalid_samples\":%llu,\"late_platform_allocations\":%llu,\"late_cpp_allocations\":%u}\n",
                block*512,result,block,(unsigned long long)fault.errors,(unsigned long long)fault.invalid_samples,
                (unsigned long long)fault.late_platform_allocations,allocations);
            m->destroy(ctx);return 3;
        }
        for(unsigned i=0;i<512;++i){uint32_t actual;memcpy(&actual,&out[i%2][i/2],4);auto wanted=expected[block*512+i];
            if(actual!=wanted){++bit_differences;
                float target;memcpy(&target,&wanted,4);
                double error=std::fabs(double(out[i%2][i/2])-target);maximum=std::fmax(maximum,error);
                bool allowed_zero=i%2==0&&((actual|wanted)&0x7fffffff)==0;
                if(!allowed_zero){if(i%2==0&&error<=tolerance)++within;else++mismatches;}}
            assert(std::isfinite(out[i%2][i/2]));}
    }
    assert(next_event==21);rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
    assert(!allocations&&!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations);
    m->destroy(ctx);
    printf("{\"samples\":10240,\"numeric_mismatches\":%u,\"bit_differences\":%u,\"within_tolerance_differences\":%u,\"max_error\":%.17g,\"late_cpp_allocations\":%u}\n",
           mismatches,bit_differences,within,maximum,allocations);
    // A finite mismatch remains a result, so the hardware can independently test it.
}
