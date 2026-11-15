/* SPDX-License-Identifier: MIT */
#include "rnbo_s3_led.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void){
    rnbo_s3_led_state s={0};float red[]={1,0,0},one[]={3,0,1,0};
    assert(rnbo_s3_led_apply(&s,red,3));
    assert(rnbo_s3_led_apply(&s,one,4));
    for(unsigned i=0;i<12;++i){assert(s.frame.rgb[i*3]==(i==3?0:1));assert(s.frame.rgb[i*3+1]==(i==3?1:0));}
    float previous[36];memcpy(previous,s.frame.rgb,sizeof previous);
    float bad[][4]={{12,1,1,1},{-1,1,1,1},{3.5,1,1,1},{NAN,0,0,0},{3,0,NAN,0},{3,0,INFINITY,0}};
    for(unsigned i=0;i<6;++i){assert(!rnbo_s3_led_apply(&s,bad[i],4));assert(!memcmp(previous,s.frame.rgb,sizeof previous));}
    assert(!rnbo_s3_led_apply(&s,red,2));assert(!memcmp(previous,s.frame.rgb,sizeof previous));
    float all[36];for(unsigned i=0;i<36;++i)all[i]=(i+1)/36.0f;
    assert(rnbo_s3_led_apply(&s,all,36));for(unsigned i=0;i<36;++i)assert(s.frame.rgb[i]==(float)all[i]);
    float clamp[]={-10,.5,100};assert(rnbo_s3_led_apply(&s,clamp,3));
    for(unsigned i=0;i<12;++i){assert(s.frame.rgb[i*3]==0&&s.frame.rgb[i*3+1]==.5f&&s.frame.rgb[i*3+2]==1);}
    s.block_messages=0;
    for(unsigned i=0;i<RNBO_S3_LED_MESSAGES_PER_BLOCK;++i)assert(rnbo_s3_led_apply(&s,red,3));
    memcpy(previous,s.frame.rgb,sizeof previous);
    assert(!rnbo_s3_led_apply(&s,one,4));assert(s.frame.dropped==1&&!memcmp(previous,s.frame.rgb,sizeof previous));
    s.block_messages=0;s.frame.sequence=UINT32_MAX;assert(rnbo_s3_led_apply(&s,one,4));assert(s.frame.sequence==1);
    puts("PASS: RGB3, indexed RGB4, full RGB36, atomic invalid rejection, clamping and bounded floods");
}
