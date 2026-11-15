/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdint.h>
#include <stddef.h>
/* Audio-owner-only 5ms fade. Independent of user gain; no overlap renderer. */
typedef struct { uint32_t at,length; int up; } pcm_transition;
static inline void pcm_transition_begin(pcm_transition *s,unsigned rate,int up)
{*s=(pcm_transition){.at=0,.length=rate/200u,.up=up};}
static inline void pcm_transition_apply(pcm_transition *s,int16_t *pcm,size_t frames,unsigned channels)
{
    for(size_t i=0;i<frames;++i){
        float gain=s->length?(float)s->at/(float)s->length:1;
        if(!s->up)gain=1-gain;
        for(unsigned c=0;c<channels;++c)pcm[i*channels+c]=(int16_t)((float)pcm[i*channels+c]*gain);
        if(s->at<s->length)++s->at;
    }
}
