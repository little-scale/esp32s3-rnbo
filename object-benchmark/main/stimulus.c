/* SPDX-License-Identifier: MIT */
#include "stimulus.h"
#include <math.h>
#include <stddef.h>
bool object_stimulus_fill(const object_stimulus *s,uint32_t first_frame,uint32_t frames,float *stereo)
{
    if(!s || !stereo || !frames || first_frame>1024u*256u || frames>1024u*256u-first_frame || s->kind<OBJECT_STIMULUS_MIDI || s->kind>OBJECT_STIMULUS_NONLINEAR_GRID)return false;
    const double tau=6.283185307179586476925286766559;
    for(uint32_t n=0;n<frames;++n) {
        uint32_t frame=first_frame+n;
        double left,right;
        if(s->kind==OBJECT_STIMULUS_IMPULSE_STEP){
            left=frame==0?1.0:frame==4096u?-0.5:0.0;
            right=frame<8192u?0.25:-0.125;
        }else if(s->kind==OBJECT_STIMULUS_NONLINEAR_GRID){
            const double x[9]={-4,-2,-1,-.5,0,.5,1,2,4};
            const double y[11]={-3,-2,-1,-.5,0,.25,.5,1,1.5,2,3};
            left=x[(frame/64u)%9u];right=y[(frame/64u)%11u];
        }else if(s->kind==OBJECT_STIMULUS_MIXED_TONE){
            left=0.2*sin(tau*440.0*(double)frame/44100.0)+0.19*sin(tau*441.0*(double)frame/44100.0);
            right=0.2*sin(tau*660.0*(double)frame/44100.0)-0.2*sin(tau*661.0*(double)frame/44100.0)+1.0e-5;
        }else{
            double t=(double)frame/44100.0;
            double modulation=s->depth*sin(tau*s->rate*t);
            if(s->kind==OBJECT_STIMULUS_RESON){
                left=s->level*sin(tau*s->excitation*t);right=s->base+modulation;
            }else{
                left=s->base+modulation;right=s->pilot_amplitude*sin(tau*s->pilot_frequency*t);
            }
        }
        float a=(float)left,b=(float)right;
        if(!isfinite(a)||!isfinite(b))return false;
        stereo[2u*n]=a;stereo[2u*n+1u]=b;
    }
    return true;
}
