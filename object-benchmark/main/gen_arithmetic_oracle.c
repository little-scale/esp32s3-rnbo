/* SPDX-License-Identifier: MIT */
#include "gen_arithmetic_oracle.h"
#include <float.h>
#include <math.h>
#include <stddef.h>

_Static_assert(FLT_RADIX==2 && FLT_MANT_DIG==24 && FLT_MAX_EXP==128 && sizeof(float)==4 &&
               DBL_MANT_DIG==53 && DBL_MAX_EXP==1024 && sizeof(double)==8 && FLT_EVAL_METHOD==0,
               "Gen arithmetic reference requires binary32/binary64 without excess evaluation precision");

bool object_gen_arithmetic_model(uint32_t model)
{
    return (model>=OBJECT_GEN_ARITH_ABS && model<=OBJECT_GEN_ARITH_LT) ||
        (model>=OBJECT_GEN_ARITH_SUM && model<=OBJECT_GEN_ARITH_SWITCH);
}
static bool overlaps(const void *a,size_t an,const void *b,size_t bn)
{
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y?y-x<an:x-y<bn;
}
static float operation(uint32_t model,float left,float right)
{
    /* Every input binary32 value is exact in binary64. Two significands have
     * at most48 product bits, so their product is exact before RN32. Bounded
     * sum/difference are also independently rounded once to the output type. */
    volatile double x=left,y=right,value=0;
    switch(model){
    case OBJECT_GEN_ARITH_ABS:value=fabs(x);break;
    /* First-argument ties canonically define the reference cache, without
     * prescribing the Gen operation's signed-zero selection policy. */
    case OBJECT_GEN_ARITH_MIN:value=x<=y?x:y;break;
    case OBJECT_GEN_ARITH_MAX:value=x>=y?x:y;break;
    case OBJECT_GEN_ARITH_SUB:value=x-y;break;
    case OBJECT_GEN_ARITH_EQ:value=x==y?1:0;break;
    case OBJECT_GEN_ARITH_LT:value=x<y?1:0;break;
    case OBJECT_GEN_ARITH_SUM:value=x+y;break;
    case OBJECT_GEN_ARITH_PRODUCT:value=x*y;break;
    case OBJECT_GEN_ARITH_NEQ:value=x!=y?1:0;break;
    case OBJECT_GEN_ARITH_GT:value=x>y?1:0;break;
    case OBJECT_GEN_ARITH_GTE:value=x>=y?1:0;break;
    case OBJECT_GEN_ARITH_LTE:value=x<=y?1:0;break;
    case OBJECT_GEN_ARITH_AND:value=(x!=0 && y!=0)?1:0;break;
    case OBJECT_GEN_ARITH_OR:value=(x!=0 || y!=0)?1:0;break;
    case OBJECT_GEN_ARITH_XOR:value=((x!=0)!=(y!=0))?1:0;break;
    case OBJECT_GEN_ARITH_NOT:value=x==0?1:0;break;
    case OBJECT_GEN_ARITH_BOOL:value=x!=0?1:0;break;
    /* The documented first-argument ordering is deliberate. A producer that
     * reverses step's arguments must fail, rather than redefine the oracle. */
    case OBJECT_GEN_ARITH_STEP:value=x>=y?1:0;break;
    /* Canonical +0 is diagnostic, as in the existing min/max cache policy. */
    case OBJECT_GEN_ARITH_SIGN:value=x>0?1:x<0?-1:0;break;
    case OBJECT_GEN_ARITH_SWITCH:value=x!=0?y:-y;break;
    }
    return (float)value;
}
bool object_gen_arithmetic_oracle_fill(uint32_t model,const float *input,
    uint32_t total,uint32_t first,uint32_t frames,float *output,uint32_t values)
{
    if(!object_gen_arithmetic_model(model) || !input || !output || !total || total>16384u ||
       !frames || first>total || frames>total-first || values<2u*frames ||
       overlaps(input,(size_t)total*2u*sizeof(float),output,(size_t)frames*2u*sizeof(float)))return false;
    const float *source=input+(size_t)first*2u;
    /* Validate the complete requested input before writing a single result. */
    for(uint32_t n=0;n<2u*frames;++n)
        if(!isfinite(source[n]) || fabsf(source[n])>1.f)return false;
    for(uint32_t n=0;n<frames;++n){
        float a=source[2u*n],b=source[2u*n+1u];
        output[2u*n]=operation(model,a,b);
        output[2u*n+1u]=operation(model,b,a);
    }
    return true;
}
