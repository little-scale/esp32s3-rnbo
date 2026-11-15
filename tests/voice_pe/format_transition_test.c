/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "voice_pe_format.h"
#include "voice_pe_controls.h"
#include "pcm_transition.h"
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
int main(void){
    for(unsigned frames=1;frames<=256;frames*=2){
        int16_t pcm[512];int32_t out[512];
        for(unsigned i=0;i<frames*2;++i)pcm[i]=i%2?INT16_MIN:INT16_MAX;
        assert(voice_pe_pack_s16(pcm,frames,out,512)==(int)frames*2);
        for(unsigned i=0;i<frames*2;++i)assert(out[i]==(int32_t)pcm[i]*65536);
        assert(voice_pe_pack_s16(pcm,frames,out,frames*2-1)==-1);
    }
    for(unsigned rate=16000;rate<=48000;rate+=32000){
        for(unsigned up=0;up<2;++up){
            pcm_transition s;pcm_transition_begin(&s,rate,up);int16_t pcm[512];
            for(unsigned i=0;i<512;++i)pcm[i]=10000;
            pcm_transition_apply(&s,pcm,256,2);
            assert(pcm[0]==(up?0:10000));assert(pcm[(rate/200)*2]==(up?10000:0));
            for(unsigned i=1;i<256;++i){assert(pcm[i*2]==pcm[i*2+1]);assert(up?pcm[i*2]>=pcm[(i-1)*2]:pcm[i*2]<=pcm[(i-1)*2]);}
        }
    }
    float rgb[36]={0};uint8_t grb[36];rgb[0]=1;rgb[1]=NAN;rgb[2]=-1;
    vpe_led_pack(rgb,grb);assert(grb[7*3]==0 && grb[7*3+1]==51 && grb[7*3+2]==0);
    puts("PASS: S16/S32 packing, independent channels, 16/48k fade endpoints, ring mapping and clamps");
}
