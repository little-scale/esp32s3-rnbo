// SPDX-License-Identifier: MIT
// Exact finite binary32 stream preflight for one boundary-controlled stereo FX module.
// Explicit arm then21 drives; triplets(call,semantic-slot,value-word),
// slot0=drive, slot1=arm. Resolve parameter IDs instead of assuming ABI indices.
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
    assert(argc==5);float tolerance=std::strtof(argv[4],nullptr);assert(std::isfinite(tolerance)&&tolerance>=0&&tolerance<=.001f);uint32_t events[66],input[512],expected[10240];read(argv[3],events,sizeof events);read(argv[1],input,sizeof input);read(argv[2],expected,sizeof expected);
    const auto *m=rnbo_s3_static_module();assert(m->role==RNBO_S3_FX);
    void *ctx=nullptr;rnbo_s3_create_options options{sizeof(options),4096,0,12345};
    assert(m->create(&options,&ctx)==0&&m->prepare(ctx)==0&&m->parameter_count(ctx)==2);
    uint32_t resolved[2]={UINT32_MAX,UINT32_MAX};
    for(unsigned i=0;i<2;++i){
        rnbo_s3_parameter_info info{};info.struct_bytes=sizeof info;
        assert(m->parameter_info(ctx,i,&info)==0&&info.initial==0&&info.exponent==1&&info.steps==0);
        if(!strcmp(info.id,"drive")){assert(info.minimum==-8&&info.maximum==8);resolved[0]=i;}
        else{assert(!strcmp(info.id,"arm")&&info.minimum==0&&info.maximum==1);resolved[1]=i;}
    }
    assert(resolved[0]!=UINT32_MAX&&resolved[1]!=UINT32_MAX&&resolved[0]!=resolved[1]);
    unsigned next_event=0;
    float in[2][256],out[2][256];const float *inputs[]={in[0],in[1]};float *outputs[]={out[0],out[1]};
    for(unsigned i=0;i<512;++i)memcpy(&in[i%2][i/2],input+i,4);
    unsigned mismatches=0,bit_differences=0,within=0;double maximum=0;
    for(unsigned block=0;block<20;++block){
        while(next_event<22&&events[next_event*3]==block){
            rnbo_s3_event event{};event.struct_bytes=sizeof event;event.kind=RNBO_S3_PARAMETER_ACTUAL;
            unsigned slot=events[next_event*3+1];assert(slot<2);event.parameter_index=resolved[slot];memcpy(&event.value,events+next_event*3+2,4);
            observing=true;int status=m->event(ctx,&event);observing=false;
            if(status!=0){
                rnbo_s3_stats fault{};fault.struct_bytes=sizeof fault;assert(m->statistics(ctx,&fault)==0);
                printf("{\"samples\":%u,\"event_status\":%d,\"fault_call\":%u,\"fault_event\":%u,\"event_parameter_slot\":%u,\"platform_errors\":%llu,\"invalid_samples\":%llu,\"late_platform_allocations\":%llu,\"late_cpp_allocations\":%u}\n",
                    block*512,status,block,next_event,slot,(unsigned long long)fault.errors,(unsigned long long)fault.invalid_samples,
                    (unsigned long long)fault.late_platform_allocations,allocations);
                m->destroy(ctx);return 3;
            }
            float actual,normalized;assert(m->parameter_value(ctx,resolved[slot],&actual,&normalized)==0);
            assert(actual==event.value&&normalized==(slot==0?(event.value+8)/16:event.value));
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
    assert(next_event==22);rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
    assert(!allocations&&!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations);
    m->destroy(ctx);
    printf("{\"samples\":10240,\"numeric_mismatches\":%u,\"bit_differences\":%u,\"within_tolerance_differences\":%u,\"max_error\":%.17g,\"late_cpp_allocations\":%u}\n",
           mismatches,bit_differences,within,maximum,allocations);
    // A finite mismatch remains a result, so the hardware can independently test it.
}
