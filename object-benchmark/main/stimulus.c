/* SPDX-License-Identifier: MIT */
#include "stimulus.h"
#include <math.h>
#include <stddef.h>
static uint32_t wrap_word(uint32_t kind,uint32_t frame,unsigned channel)
{
    const uint32_t magnitudes[]={0,1,0x7fffff,0x800000,0x3f7fffff,0x3f800000,0x3f800001,0x40000000,0x40400000,
        0x4b7fffff,0x4b800000,0x4b800001,0x4bffffff,0x4c000000,0x4c000001,0x4effffff,0x4f000000,0x4f000001,
        0x4f7fffff,0x4f800000,0x4f800001,0x7f7fffff};
    if(kind==OBJECT_STIMULUS_WRAP_BOUNDARIES||kind==OBJECT_STIMULUS_WRAP_ZERO_ENDPOINTS){
        uint32_t index=frame+(channel?(kind==OBJECT_STIMULUS_WRAP_BOUNDARIES?13u:7u):0u);
        unsigned count=kind==OBJECT_STIMULUS_WRAP_BOUNDARIES?22u:9u;
        return ((index&1u)<<31)|magnitudes[(index/2u)%count];
    }
    const uint32_t mantissas[]={0,1,2,0x3fffff,0x400000,0x7ffffd,0x7ffffe,0x7fffff};
    uint32_t index=frame+(channel?2039u:0u),lane=index%16u;
    uint32_t exponent=(index/16u)%(kind==OBJECT_STIMULUS_WRAP_SAFE?151u:255u);
    return ((lane/8u)<<31)|(exponent<<23)|mantissas[lane%8u];
}
static uint32_t nonlinear_dense_word(uint32_t frame,unsigned channel)
{
    const uint32_t edges[]={0,0x80000000,1,0x80000001,0x7fffff,0x807fffff,0x800000,0x80800000,
        0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f7fffff,0xbf7fffff,0x3f800000,0xbf800000,
        0x3f800001,0xbf800001,0x3fc00000,0xbfc00000,0x3fffffff,0xbfffffff,0x40000000,0xc0000000,
        0x40000001,0xc0000001,0x40400000,0xc0400000,0x40800000,0xc0800000};
    if(frame%16u==0){
        unsigned count=channel?28u:30u,index=frame/16u+(channel?13u:0u);
        return edges[index%count];
    }
    if(channel){
        uint32_t hash=frame*1664525u+1013904223u;
        uint32_t exponent=frame%4u?127u-frame%4u:(frame/4u)%127u;
        return (exponent<<23)|(hash&0x7fffffu);
    }
    uint32_t hash=(frame+2039u)*22695477u+1u;
    return (hash&0x80000000u)|((124u+(frame/4u)%5u)<<23)|(hash&0x7fffffu);
}
/* Original wave4 input programs; all words are authored independently of DSP
 * output. Seek the LCG by affine exponentiation, then consume two words/frame. */
static uint32_t wave4_advance(uint32_t seed,uint32_t count)
{
    uint32_t multiplier=1664525u,increment=1013904223u,total_multiplier=1u,total_increment=0u;
    while(count){
        if(count&1u){total_multiplier*=multiplier;total_increment=total_increment*multiplier+increment;}
        increment=(multiplier+1u)*increment;multiplier*=multiplier;count>>=1;
    }
    return total_multiplier*seed+total_increment;
}
static bool wave4_input(uint32_t kind,uint32_t first,uint32_t frames,float *stereo)
{
    static const uint32_t grid[12][2]={
        {0,0x80000000u},{0xbf800000u,0x3f800000u},{0x3f800000u,0xbf800000u},
        {0x3f000000u,0x3f000000u},{0xbf000000u,0xbf000000u},{0x3f7fffffu,0x3f800000u},
        {1u,0},{0x80000001u,0},{0x3f000001u,0x3f000000u},{0x3effffffu,0x3f000000u},
        {0x80000000u,0},{0x3f800000u,0x3f800000u}};
    uint32_t state=wave4_advance(0x12345678u,2u*first);
    for(uint32_t i=0;i<frames;++i){
        uint32_t n=first+i,a,b;
        if(kind==OBJECT_STIMULUS_WAVE4_GRID){a=grid[(n/17u)%12u][0];b=grid[(n/17u)%12u][1];}
        else if(kind==OBJECT_STIMULUS_WAVE4_DENSE){
            state=1664525u*state+1013904223u;a=(state&0x807fffffu)|(((state>>24u)%127u)<<23u);
            state=1664525u*state+1013904223u;b=(state&0x807fffffu)|(((state>>24u)%127u)<<23u);
            if(n%17u==0)b=a;
            if(n%31u==0)b=a^0x80000000u;
        }else{
            uint32_t cycle=n%1024u;
            a=(cycle==0u||cycle==255u||cycle==256u||cycle==511u||cycle==512u)?
                (0x3f400000u|(((n/1024u)&1u)<<31u)):(cycle>=768u?0x3e800000u:0u);
            b=cycle>=256u&&cycle<512u?0xbf000000u:cycle>=512u&&cycle<768u?0x3f000000u:0x80000000u;
        }
        __builtin_memcpy(stereo+2u*i,&a,4);__builtin_memcpy(stereo+2u*i+1u,&b,4);
    }
    return true;
}
bool object_stimulus_fill(const object_stimulus *s,uint32_t first_frame,uint32_t frames,float *stereo)
{
    if(!s || !stereo || !frames || first_frame>1024u*256u || frames>1024u*256u-first_frame || s->kind<OBJECT_STIMULUS_MIDI || s->kind>OBJECT_STIMULUS_ABS_BOUNDARIES)return false;
    if(s->kind==OBJECT_STIMULUS_ABS_BOUNDARIES){
        static const uint32_t magnitude[]={0,1,2,0x3fffff,0x400000,0x7ffffe,0x7fffff,0x800000,0x800001,
            0xffffff,0x1000000,0x3e800000,0x3effffff,0x3f000000,0x3f000001,0x3f7ffffe,0x3f7fffff,0x3f800000};
        for(uint32_t n=0;n<frames;++n)for(unsigned c=0;c<2;++c){
            uint32_t lane=first_frame+n+(c?17u:0u),word=magnitude[(lane/2u)%18u]|((lane&1u)<<31u);
            __builtin_memcpy(stereo+2u*n+c,&word,4);
        }
        return true;
    }
    if(s->kind==OBJECT_STIMULUS_GEN_HISTORY){
        static const float pattern[]={.25f,-.125f,.5f,0.f,-.25f,.125f,-.5f};
        if(first_frame>16384u || frames>16384u-first_frame)return false;
        for(uint32_t n=0;n<frames;++n){
            stereo[2u*n]=pattern[(first_frame+n)%7u];
            stereo[2u*n+1u]=pattern[(first_frame+n+3u)%7u];
        }
        return true;
    }
    if(s->kind>=OBJECT_STIMULUS_WAVE4_GRID)return wave4_input(s->kind,first_frame,frames,stereo);
    if(s->kind>=OBJECT_STIMULUS_WRAP_BOUNDARIES){
        for(uint32_t n=0;n<frames;++n)for(unsigned channel=0;channel<2;++channel){
            uint32_t word=s->kind==OBJECT_STIMULUS_NONLINEAR_DENSE?nonlinear_dense_word(first_frame+n,channel):wrap_word(s->kind,first_frame+n,channel);
            if((word&0x7fffffffu)>=0x7f800000u)return false;
            __builtin_memcpy(stereo+2u*n+channel,&word,sizeof word);
        }
        return true;
    }
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
