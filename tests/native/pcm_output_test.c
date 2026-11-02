/* SPDX-License-Identifier: MIT */
#include "pcm_output.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
    float left[256], right[256];
    int16_t pcm[512];
    pcm_output state;
    pcm_output_init(&state);
    for (unsigned i=0;i<256;++i) { left[i]=0.5f; right[i]=-0.25f; }
    assert(pcm_output_render(&state,left,right,pcm,256,2,100,1.0f,0));
    /* Startup ramp must complete before checking unity conversion. */
    for(unsigned i=0;i<5;++i) assert(pcm_output_render(&state,left,right,pcm,256,2,100,1,0));
    assert(abs(pcm[0]-16384)<=1 && abs(pcm[1]+8192)<=1);
    assert(pcm_output_render(&state,left,right,pcm,256,1,100,1,0));
    assert(abs(pcm[0]-4096)<=1); // mono = (L+R)/2
    for(unsigned i=0;i<256;++i) { left[i]=2; right[i]=-2; }
    assert(pcm_output_render(&state,left,right,pcm,256,2,100,1,0));
    assert(pcm[0]==32767 && pcm[1]==-32767 && state.clipped>=512);
    left[0]=NAN; right[1]=INFINITY;
    assert(pcm_output_render(&state,left,right,pcm,256,2,100,1,0));
    assert(pcm[0]==0 && pcm[3]==0 && state.nonfinite==2);
    assert(pcm_output_render(&state,left,right,pcm,256,2,100,1,1));
    for(unsigned i=0;i<512;++i) assert(pcm[i]==0);
    for(unsigned i=0;i<256;++i) left[i]=right[i]=0.25f;
    for(unsigned i=0;i<5;++i) assert(pcm_output_render(&state,left,right,pcm,256,2,100,1,0));
    int16_t previous=pcm[0];
    assert(pcm_output_render(&state,left,right,pcm,256,2,0,1,0));
    for(unsigned i=0;i<256;++i) { assert(pcm[2*i]<=previous); previous=pcm[2*i]; }
    for(unsigned i=0;i<5;++i) assert(pcm_output_render(&state,left,right,pcm,256,2,0,1,0));
    for(unsigned i=0;i<512;++i) assert(pcm[i]==0);
    pcm[0]=123;
    assert(!pcm_output_render(&state,left,right,pcm,64,2,100,1,0));
    assert(pcm[0]==123);
    assert(!pcm_output_render(&state,left,right,pcm,256,2,100,NAN,0));
    puts("pcm_output: stereo, mono, ramp, saturation, finite guard, panic and vector checks passed");
    return 0;
}
