/* SPDX-License-Identifier: MIT */
#include "wave4_oracle.h"
#include <math.h>
#include <stddef.h>
#define WAVE4_MAGIC 0x57415634u
bool object_wave4_oracle_init(object_wave4_oracle *s,uint32_t model,uint32_t warmup)
{
    if(!s || model<OBJECT_WAVE4_ABSOLUTE || model>OBJECT_WAVE4_DELTA || warmup!=4)return false;
    *s=(object_wave4_oracle){WAVE4_MAGIC,model,0,0.0f};return true;
}
static bool wire(float x){return isfinite(x) && x>=-1.0f && x<=1.0f;}
/* Binary64 evaluates the mathematical sum/difference of the binary32 operands
 * before one explicit binary32 rounding. No generated Float32 state is used;
 * delta retains the previous INPUT, not the previous difference. */
static float operation(uint32_t model,float x,float y)
{
    volatile double a=(double)x,b=(double)y;
    switch(model){
    case OBJECT_WAVE4_ABSOLUTE:return (float)fabs(a);
    /* The mathematical cache selects the first operand on equality, matching
     * Python's model including its zero-sign convention. DSP tie signs remain
     * diagnostic, but the independent cache bytes have a single identity. */
    case OBJECT_WAVE4_MINIMUM:return a<=b?x:y;
    case OBJECT_WAVE4_MAXIMUM:return a>=b?x:y;
    case OBJECT_WAVE4_SUBTRACT:return (float)(a-b);
    case OBJECT_WAVE4_EQUAL:return a==b?1.0f:0.0f;
    case OBJECT_WAVE4_LESS:return a<b?1.0f:0.0f;
    default:return NAN;
    }
}
bool object_wave4_oracle_fill(object_wave4_oracle *s,const float *input,uint32_t total,
    uint32_t first,uint32_t frames,float *out,uint32_t values)
{
    if(!s || s->magic!=WAVE4_MAGIC || s->model<1 || s->model>OBJECT_WAVE4_DELTA ||
       !wire(s->previous) || !input || !out || input==out || !frames || total>1048576u ||
       first!=s->next_frame || first>total || frames>total-first || values<frames*2u)return false;
    /* Reject the entire input chunk before changing output or history. */
    for(uint32_t i=0;i<frames*2u;++i)if(!wire(input[first*2u+i]))return false;
    for(uint32_t i=0;i<frames;++i){
        float x=input[(first+i)*2u],y=input[(first+i)*2u+1u];
        if(s->model==OBJECT_WAVE4_SUM_DIFFERENCE){
            volatile double a=(double)x,b=(double)y;
            out[2u*i]=(float)(a+b);out[2u*i+1u]=(float)(a-b);
        }else if(s->model==OBJECT_WAVE4_DELTA){
            volatile double a=(double)x,b=(double)s->previous;
            out[2u*i]=(float)(a-b);
            /* A direct wire is a raw observer, including signed zero. */
            __builtin_memcpy(out+2u*i+1u,input+(first+i)*2u+1u,sizeof(float));s->previous=x;
        }else{
            out[2u*i]=operation(s->model,x,y);out[2u*i+1u]=operation(s->model,y,x);
        }
    }
    s->next_frame+=frames;return true;
}
