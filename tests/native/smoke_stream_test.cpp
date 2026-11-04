// SPDX-License-Identifier: MIT
// Exact finite binary32 stream preflight for parameter-free stereo FX modules.
// Supply a512-word input vector and twenty512-word expected output vectors.
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
    assert(argc==3);uint32_t input[512],expected[10240];read(argv[1],input,sizeof input);read(argv[2],expected,sizeof expected);
    const auto *m=rnbo_s3_static_module();assert(m->role==RNBO_S3_FX);
    void *ctx=nullptr;rnbo_s3_create_options options{sizeof(options),4096,0,12345};
    assert(m->create(&options,&ctx)==0&&m->prepare(ctx)==0&&m->parameter_count(ctx)==0);
    float in[2][256],out[2][256];const float *inputs[]={in[0],in[1]};float *outputs[]={out[0],out[1]};
    for(unsigned i=0;i<512;++i)memcpy(&in[i%2][i/2],input+i,4);
    unsigned mismatches=0,bit_differences=0;double maximum=0;
    for(unsigned block=0;block<20;++block){
        observing=true;int result=m->process(ctx,inputs,outputs,256,uint64_t(block)*256);observing=false;assert(result==0);
        for(unsigned i=0;i<512;++i){uint32_t actual;memcpy(&actual,&out[i%2][i/2],4);auto wanted=expected[block*512+i];
            if(actual!=wanted){++bit_differences;
                if((actual&0x7fffffff)||(wanted&0x7fffffff)){++mismatches;float value;memcpy(&value,&wanted,4);
                    maximum=std::fmax(maximum,std::fabs(double(out[i%2][i/2])-value));}}
            assert(std::isfinite(out[i%2][i/2]));}
    }
    rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
    assert(!allocations&&!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations);
    m->destroy(ctx);
    printf("{\"samples\":10240,\"numeric_mismatches\":%u,\"bit_differences\":%u,\"max_error\":%.17g,\"late_cpp_allocations\":%u}\n",
           mismatches,bit_differences,maximum,allocations);
    // A finite mismatch remains a result, so the hardware can independently test it.
}
