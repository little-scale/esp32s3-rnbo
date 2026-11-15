/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_LED_H
#define RNBO_S3_LED_H
#include <stdint.h>
#include <math.h>
#define RNBO_S3_LED_VERSION 1u
#define RNBO_S3_LED_VALUES 36u
#define RNBO_S3_LED_MESSAGES_PER_BLOCK 32u
typedef struct {
    uint32_t struct_bytes, version, sequence, accepted, rejected, dropped;
    float rgb[RNBO_S3_LED_VALUES];
} rnbo_s3_led_frame;
/* Exclusively owned by the module callback thread. No allocation or I/O. */
typedef struct { rnbo_s3_led_frame frame; uint32_t block_messages; } rnbo_s3_led_state;
static inline int rnbo_s3_led_apply(rnbo_s3_led_state *s,const float *v,uint32_t n)
{
    if(s->block_messages>=RNBO_S3_LED_MESSAGES_PER_BLOCK){++s->frame.dropped;return 0;}
    ++s->block_messages;
    if(!v||(n!=3&&n!=4&&n!=36)){++s->frame.rejected;return 0;}
    unsigned first=n==4?1:0,index=0;
    if(n==4){
        if(!isfinite(v[0])||v[0]<0||v[0]>11||v[0]!=(float)(unsigned)v[0]){++s->frame.rejected;return 0;}
        index=(unsigned)v[0];
    }
    /* Validate the complete update before changing even one channel. */
    for(unsigned i=first;i<n;++i)if(!isfinite(v[i])){++s->frame.rejected;return 0;}
    float rgb[36];
    for(unsigned i=first;i<n;++i)rgb[i-first]=(float)(v[i]<0?0:v[i]>1?1:v[i]);
    if(n==36)for(unsigned i=0;i<36;++i)s->frame.rgb[i]=rgb[i];
    else for(unsigned led=n==4?index:0;led<(n==4?index+1:12);++led)
        for(unsigned c=0;c<3;++c)s->frame.rgb[led*3+c]=rgb[c];
    s->frame.struct_bytes=sizeof s->frame;s->frame.version=RNBO_S3_LED_VERSION;
    if(!++s->frame.sequence)++s->frame.sequence;
    ++s->frame.accepted;return 1;
}
#endif
