/* SPDX-License-Identifier: MIT */
#include "stimulus.h"
#include <math.h>
#include <stddef.h>
bool object_stimulus_fill(const object_stimulus *s,uint32_t first_frame,uint32_t frames,float *stereo)
{
    if(!s || !stereo || !frames || first_frame>1024u*256u || frames>1024u*256u-first_frame || s->kind<OBJECT_STIMULUS_MIDI || s->kind>OBJECT_STIMULUS_RESON)return false;
    const double tau=6.283185307179586476925286766559;
    for(uint32_t n=0;n<frames;++n) {
        double t=(double)(first_frame+n)/44100.0;
        double modulation=s->depth*sin(tau*s->rate*t),left,right;
        if(s->kind==OBJECT_STIMULUS_RESON) {
            left=s->level*sin(tau*s->excitation*t);right=s->base+modulation;
        } else {
            left=s->base+modulation;right=s->pilot_amplitude*sin(tau*s->pilot_frequency*t);
        }
        float a=(float)left,b=(float)right;
        if(!isfinite(a)||!isfinite(b))return false;
        stereo[2u*n]=a;stereo[2u*n+1u]=b;
    }
    return true;
}
