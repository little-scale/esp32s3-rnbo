/* SPDX-License-Identifier: MIT */
#include "wave2_oracle.h"
#include <float.h>
#include <math.h>
#include <stddef.h>
#include <string.h>

#define MAGIC UINT32_C(0x57324f31)
_Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24,"binary32 cache");
_Static_assert(sizeof(double)==8 && DBL_MANT_DIG==53,"binary64 model");

bool object_wave2_oracle_init(object_wave2_oracle *s,uint32_t kind,const double values[5],
                              double exponent,uint32_t warmup)
{
    if(!s||!values||(kind!=OBJECT_WAVE2_BIQUAD&&kind!=OBJECT_WAVE2_NONLINEAR&&kind!=OBJECT_WAVE2_POWER_MODES)||warmup!=4)return false;
    object_wave2_oracle fresh={0};fresh.magic=MAGIC;fresh.kind=kind;
    /* Exact same Float64 catalog values used by qualify_wave2.semantics;
     * intentionally not quantized to module Float32 parameters. */
    if(kind==OBJECT_WAVE2_BIQUAD){
        const double coefficients[3][5]={{.5,.25,.125,-.4,.2},{1,0,0,0,0},{.05,0,0,-.95,0}};
        if(exponent!=0)return false;
        unsigned selected=0;
        for(;selected<3;++selected){
            unsigned i=0;for(;i<5;++i)if(values[i]!=coefficients[selected][i])break;
            if(i==5)break;
        }
        if(selected==3)return false;
        fresh.case_index=selected;
        memcpy(fresh.coefficients,values,sizeof fresh.coefficients);
    }else{
        for(unsigned i=0;i<5;++i)if(values[i]!=0)return false;
        if(kind==OBJECT_WAVE2_POWER_MODES){
            if(!isfinite(exponent)||exponent<.25||exponent>4||exponent!=(double)(float)exponent)return false;
            fresh.coefficients[0]=exponent;*s=fresh;return true;
        }
        const double exponents[3]={2,.25,4};unsigned selected=0;
        for(;selected<3;++selected)if(exponent==exponents[selected])break;
        if(selected==3)return false;
        fresh.case_index=selected;fresh.coefficients[0]=exponent;
    }
    *s=fresh;return true;
}


static bool valid(const object_wave2_oracle *s)
{return s&&s->magic==MAGIC&&(s->kind==OBJECT_WAVE2_BIQUAD||s->kind==OBJECT_WAVE2_NONLINEAR||s->kind==OBJECT_WAVE2_POWER_MODES)&&s->case_index<=2&&s->next_frame<OBJECT_WAVE2_MAX_FRAMES;}

bool object_wave2_oracle_set_exponent(object_wave2_oracle *s,float exponent)
{
    if(!valid(s)||s->kind!=OBJECT_WAVE2_POWER_MODES||s->next_frame%256u||
       !isfinite(exponent)||exponent<.25f||exponent>4.f)return false;
    s->coefficients[0]=(double)exponent;return true;
}

static bool input_domain(uint32_t kind,float a,float b)
{
    if(!isfinite(a)||!isfinite(b))return false;
    if(kind==OBJECT_WAVE2_BIQUAD)return fabs((double)a)<=1&&fabs((double)b)<=1;
    return a>=-4&&a<=4&&b>=-3&&b<=3;
}

bool object_wave2_oracle_step(object_wave2_oracle *s,const float input[2],double truth[2])
{
    if(!valid(s)||!input||!truth||!input_domain(s->kind,input[0],input[1]))return false;
    double expected[2];
    if(s->kind==OBJECT_WAVE2_BIQUAD){
        for(unsigned c=0;c<2;++c){
            double x=(double)input[c];const double *a=s->coefficients;
            /* Preserve the independent native model's written operation
             * order, not the generated Float32 feedback accumulator. */
            expected[c]=a[0]*x+a[1]*s->x1[c]+a[2]*s->x2[c]-a[3]*s->y1[c]-a[4]*s->y2[c];
        }
        if(!isfinite(expected[0])||!isfinite(expected[1]))return false;
        for(unsigned c=0;c<2;++c){s->x2[c]=s->x1[c];s->x1[c]=input[c];s->y2[c]=s->y1[c];s->y1[c]=expected[c];}
    }else{
        double a=(double)input[0],b=(double)input[1];
        expected[0]=tanh(a);
        double wrapped=b-2*floor((b+1)/2);
        double clipped=wrapped>1?1:wrapped<0?0:wrapped;
        expected[1]=pow(clipped,s->coefficients[0]);
        if(!isfinite(expected[0])||!isfinite(expected[1]))return false;
    }
    truth[0]=expected[0];truth[1]=expected[1];++s->next_frame;return true;
}

bool object_wave2_oracle_fill(object_wave2_oracle *s,const float *input,uint32_t total,uint32_t first,
                       uint32_t frames,float *output,uint32_t capacity,double *rounding)
{
    if(!valid(s)||!input||!output||!rounding||!total||total>OBJECT_WAVE2_MAX_FRAMES||!frames||
       first!=s->next_frame||first>total||frames>total-first||capacity/2u<frames||
       !isfinite(*rounding)||*rounding<0)return false;
    /* Validate the whole requested input span before advancing model state. */
    for(uint32_t i=first;i<first+frames;++i)
        if(!input_domain(s->kind,input[2u*i],input[2u*i+1u]))return false;
    for(uint32_t offset=0;offset<frames;++offset){
        double expected[2];if(!object_wave2_oracle_step(s,input+2u*(first+offset),expected))return false;
        for(unsigned c=0;c<2;++c){
            float rounded=(float)expected[c];if(!isfinite(rounded))return false;
            double error=fabs(expected[c]-(double)rounded);if(error>*rounding)*rounding=error;
            output[2u*offset+c]=rounded;
        }
    }
    return true;
}

bool object_wave2_biquad_dc_gain(const object_wave2_oracle *s,double *gain)
{
    if(!s||s->magic!=MAGIC||s->kind!=OBJECT_WAVE2_BIQUAD||s->case_index>2||!gain)return false;
    const double *a=s->coefficients;double denominator=1+a[3]+a[4];
    if(!isfinite(denominator)||denominator==0)return false;
    double value=(a[0]+a[1]+a[2])/denominator;
    if(!isfinite(value))return false;
    *gain=value;return true;
}

bool object_wrap_finite_oracle_word(uint32_t input,uint32_t *output)
{
    uint32_t magnitude=input&0x7fffffffu,sign=input>>31;
    if(!output||magnitude>=0x7f800000u)return false;
    if(magnitude<0x3f800000u){*output=input;return true;}
    unsigned exponent=magnitude>>23;
    if(exponent>=151u){*output=0;return true;}
    uint32_t significand=(magnitude&0x7fffffu)|0x800000u;
    unsigned fractional=150u-exponent;
    uint32_t denominator=1u<<fractional,period=denominator*2u;
    uint32_t remainder=significand&(period-1u);
    int32_t numerator=sign?(remainder>denominator?(int32_t)(period-remainder):-(int32_t)remainder):
        (remainder>=denominator?(int32_t)remainder-(int32_t)period:(int32_t)remainder);
    if(!numerator){*output=0;return true;}
    uint32_t negative=numerator<0,absolute=(uint32_t)(negative?-numerator:numerator);
    unsigned leading=31u-(unsigned)__builtin_clz(absolute);
    uint32_t packed=(absolute<<(23u-leading))&0x7fffffu;
    *output=(negative<<31)|((127u+leading-fractional)<<23)|packed;return true;
}

bool object_wrap_finite_oracle_fill(const float *input,uint32_t total,uint32_t first,
    uint32_t frames,float *output,uint32_t capacity)
{
    if(!input||!output||!total||total>OBJECT_WAVE2_MAX_FRAMES||!frames||first>total||
       frames>total-first||capacity/2u<frames)return false;
    for(uint32_t n=first;n<first+frames;++n)for(unsigned c=0;c<2;++c){
        uint32_t word;__builtin_memcpy(&word,input+2u*n+c,sizeof word);
        if((word&0x7fffffffu)>=0x7f800000u)return false;
    }
    for(uint32_t n=0;n<frames;++n)for(unsigned c=0;c<2;++c){
        uint32_t word,expected;__builtin_memcpy(&word,input+2u*(first+n)+c,sizeof word);
        if(!object_wrap_finite_oracle_word(word,&expected))return false;
        __builtin_memcpy(output+2u*n+c,&expected,sizeof expected);
    }
    return true;
}
