/* SPDX-License-Identifier: MIT */
/* Independent Float64 convolution / integer-period model, not generated DSP. */
#include "gen_history_oracle.h"
#include <float.h>
#include <math.h>
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(float)==4 && FLT_RADIX==2 && FLT_MANT_DIG==24,"binary32 cache");
_Static_assert(sizeof(double)==8 && DBL_MANT_DIG==53 && FLT_EVAL_METHOD==0,"strict binary64 oracle");
#define GEN_HISTORY_MAGIC 0x47484f31u
static bool model_valid(uint32_t model){return model>=1 && model<=3;}
static bool valid(const object_gen_history_oracle *s){
    return s && s->magic==GEN_HISTORY_MAGIC && model_valid(s->model) &&
        s->next_frame<=OBJECT_GEN_HISTORY_MAX_FRAMES &&
        (s->epoch==-1024 || (s->epoch>=0 && s->epoch%256==0)) &&
        s->epoch<=(int64_t)s->next_frame;
}
bool object_gen_history_oracle_init(object_gen_history_oracle *s,uint32_t model,uint32_t warmup){
    if(!s || !model_valid(model) || warmup!=4)return false;
    *s=(object_gen_history_oracle){.magic=GEN_HISTORY_MAGIC,.model=model,.next_frame=0,.epoch=-1024};return true;
}
bool object_gen_history_oracle_reset(object_gen_history_oracle *s,uint32_t first){
    if(!valid(s) || first!=s->next_frame || first%256)return false;
    s->epoch=first;return true;
}
double object_gen_history_oracle_tail_bound(uint32_t model){return !model_valid(model) ? NAN : model==1 ? 0x1p-64 : 0.0;}
double object_gen_history_oracle_evaluation_bound(uint32_t model){return !model_valid(model) ? NAN : model==1 ? 128.0*DBL_EPSILON : 0.0;}
static uint32_t word(float x){uint32_t v;memcpy(&v,&x,4);return v;}
static float expected(uint32_t frame,uint32_t channel){
    static const float p[7]={.25f,-.125f,.5f,0.f,-.25f,.125f,-.5f};return p[(frame+3*channel)%7];
}
static bool valid_input(const object_gen_history_oracle *s,const float *input,uint32_t first,uint32_t frames){
    uint32_t start=s->epoch<0 ? 0u:(uint32_t)s->epoch;
    uint32_t check_first=first;
    if(s->model==1){check_first=first>64 ? first-64:0;if(check_first<start)check_first=start;}
    for(uint32_t n=check_first;n<first+frames;++n)
        for(uint32_t c=0;c<2;++c)if(word(input[2*n+c])!=word(expected(n,c)))return false;
    return true;
}
static void truth_pair(uint32_t model,const float *input,uint32_t n,int64_t epoch,double truth[2]){
    if(model==1){
        uint32_t start=epoch<0 ? 0u:(uint32_t)epoch;
        volatile double history=0.0;
        uint32_t count=n-start;if(count>64)count=64;
        for(uint32_t age=1;age<=count;++age){
            volatile double term=ldexp((double)input[2*(n-age)],-(int)(age-1));
            volatile double next=history+term;history=next;
        }
        volatile double half=0.5*history;
        volatile double current=(double)input[2*n]+half;
        truth[0]=current;truth[1]=history;
    }else{
        uint32_t phase=(uint32_t)(((int64_t)n-epoch)%(int64_t)model);
        truth[0]=(double)(1+phase);truth[1]=(double)(1+(phase+1)%model);
    }
}
bool object_gen_history_oracle_reset_witness(const object_gen_history_oracle *s,const float *input,
        uint32_t total,uint32_t first,bool *observable){
    if(!valid(s) || !input || !observable || !total || total>OBJECT_GEN_HISTORY_MAX_FRAMES ||
        first!=s->next_frame || first>=total || first%256 || !valid_input(s,input,first,1))return false;
    double prior[2],reset[2];truth_pair(s->model,input,first,s->epoch,prior);
    truth_pair(s->model,input,first,(int64_t)first,reset);
    bool result=false;
    for(uint32_t c=0;c<2;++c){
        float before=(float)prior[c],after=(float)reset[c];
        if(fabs((double)after-(double)before)>8e-6)result=true;
    }
    *observable=result;return true;
}
bool object_gen_history_oracle_fill(object_gen_history_oracle *s,const float *input,uint32_t total,
        uint32_t first,uint32_t frames,float *output,uint32_t values,double *rounding){
    if(!valid(s) || !input || !output || !rounding || !isfinite(*rounding) || *rounding<0 ||
       !total || total>OBJECT_GEN_HISTORY_MAX_FRAMES || first!=s->next_frame || !frames ||
       first>total || frames>total-first || values<2*frames)return false;
    uintptr_t in=(uintptr_t)input,out=(uintptr_t)output;
    uintptr_t in_bytes=(uintptr_t)total*2*sizeof(float),out_bytes=(uintptr_t)frames*2*sizeof(float);
    if(in>UINTPTR_MAX-in_bytes || out>UINTPTR_MAX-out_bytes || (in<out+out_bytes && out<in+in_bytes))return false;
    if(!valid_input(s,input,first,frames))return false;
    double maximum=*rounding;
    for(uint32_t n=first;n<first+frames;++n){
        double truth[2];
        truth_pair(s->model,input,n,s->epoch,truth);
        for(uint32_t c=0;c<2;++c){
            float cache=(float)truth[c];double error=fabs((double)cache-truth[c]);
            if(error>maximum)maximum=error;
            output[2*(n-first)+c]=cache;
        }
    }
    s->next_frame=first+frames;*rounding=maximum;return true;
}
