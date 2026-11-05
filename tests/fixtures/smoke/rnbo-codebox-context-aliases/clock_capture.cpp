// SPDX-License-Identifier: MIT
// Native SDK capture for secondary clock diagnosis; no hardware/timing claim.
#include "rnbo_s3_module.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
int main(int argc,char**argv){
    assert(argc==3);uint32_t words[512],captured[10240];
    FILE*f=std::fopen(argv[1],"rb");assert(f);
    assert(std::fread(words,sizeof(words),1,f)==1&&std::fgetc(f)==EOF);std::fclose(f);
    const auto*m=rnbo_s3_static_module();assert(m->role==RNBO_S3_FX);
    void*ctx=nullptr;rnbo_s3_create_options options{sizeof(options),4096,0,12345};
    assert(m->create(&options,&ctx)==0&&m->prepare(ctx)==0&&m->parameter_count(ctx)==0);
    float in[2][256],out[2][256];const float*inputs[]={in[0],in[1]};float*outputs[]={out[0],out[1]};
    for(unsigned i=0;i<512;++i)std::memcpy(&in[i%2][i/2],&words[i],4);
    for(unsigned b=0;b<20;++b){
        assert(m->process(ctx,inputs,outputs,256,uint64_t(b)*256)==0);
        for(unsigned i=0;i<512;++i){
            assert(std::isfinite(out[i%2][i/2]));
            std::memcpy(&captured[b*512+i],&out[i%2][i/2],4);
        }
    }
    rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
    assert(!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations);m->destroy(ctx);
    f=std::fopen(argv[2],"wb");assert(f);assert(std::fwrite(captured,sizeof(captured),1,f)==1);assert(std::fclose(f)==0);
}
