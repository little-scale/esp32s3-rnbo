// SPDX-License-Identifier: MIT
// Independent direct-producer capture for native scheduling diagnosis only.
// No SDK ABI, allocation, timing, target-output or complete Max-engine claim.
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#define RNBO_USE_FLOAT32
#define RNBO_NOSTL
#define RNBO_NOTHROW
#define RNBO_NO_PATCHERFACTORY
#define RNBO_FIXEDLISTSIZE 16
#include "RNBO_Common.h"
#include "rnbo_source.h"
#undef trunc
#undef autoref
int main(int argc,char**argv){
    if(argc!=3)return 2;
    uint32_t words[512];FILE*f=std::fopen(argv[1],"rb");if(!f)return 3;
    if(std::fread(words,sizeof(words),1,f)!=1||std::fgetc(f)!=EOF)return 4;
    std::fclose(f);float in[2][256],out[2][256];
    for(unsigned i=0;i<512;++i)std::memcpy(&in[i%2][i/2],&words[i],4);
    const float*inputs[]={in[0],in[1]};float*outputs[]={out[0],out[1]};
    RNBO::rnbos3patch<> patch;patch.initialize();patch.prepareToProcess(44100,256,true);
    if(patch.getNumInputChannels()!=2||patch.getNumOutputChannels()!=2)return 5;
    FILE*capture=std::fopen(argv[2],"wb");if(!capture)return 6;
    for(unsigned block=0;block<20;++block){
        patch.process(inputs,2,outputs,2,256);
        for(unsigned i=0;i<512;++i){
            float v=out[i%2][i/2];if(!std::isfinite(v)||std::fwrite(&v,4,1,capture)!=1)return 7;
        }
    }
    return std::fclose(capture)?8:0;
}
