/* SPDX-License-Identifier: MIT */
#pragma once
#include "probe_api.h"
#include "gen_plan.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <new>
static_assert(sizeof(RNBO::SampleValue)==4,"Float32 audio is required");
static_assert(sizeof(RNBO::MillisecondTime)==8,"Scheduler time must remain Double");
namespace gen_partition_probe {
inline void check(bool valid,const char *reason){if(!valid)gen_probe_fault(reason);}
inline uint32_t bits(float f){uint32_t w;std::memcpy(&w,&f,4);return w;}
inline float value(uint32_t w){float f;std::memcpy(&f,&w,4);return f;}
struct GuardedPlane {uint32_t before;float data[256];uint32_t after;};
inline void fill(GuardedPlane &p){p.before=p.after=0x7fc12345u;for(auto &v:p.data){uint32_t w=0x7fc12345u;std::memcpy(&v,&w,4);}}
inline void guards(const GuardedPlane&p,unsigned count){check(p.before==0x7fc12345u&&p.after==0x7fc12345u,"outer-buffer-guard");for(unsigned i=count;i<256;++i)check(bits(p.data[i])==0x7fc12345u,"inactive-buffer-write");}
template<class Patch,unsigned Model>
void render(unsigned stimulus,unsigned nominal,uint32_t *capture,const uint32_t *baseline,gen_probe_result *r){
    check(stimulus<2&&capture&&r,"probe-arguments");
    check(nominal==0||nominal==1||nominal==2||nominal==7||nominal==255||nominal==256,"partition-range");
    *r={};r->first_numeric_word=UINT32_MAX;r->context_bytes=sizeof(Patch);
    check(sizeof(Patch)<=65536,"patch-context-budget");
    void*storage=gen_probe_allocate(sizeof(Patch));check(storage!=nullptr,"patch-storage");
    Patch *patch=new(storage)Patch;
    patch->initialize();patch->prepareToProcess(44100,256,true);
    check(patch->getNumInputChannels()==2&&patch->getNumOutputChannels()==2&&patch->getNumParameters()==1&&patch->getNumDataRefs()==0,"producer-shape");
    check(std::strcmp(patch->getParameterName(0),"reset")==0,"reset-parameter-identity");
    GuardedPlane left,right,out_left,out_right;
    const float*ins[]={left.data,right.data};float*outs[]={out_left.data,out_right.data};
    const double limit=Model==1?GEN_PROBE_LIMIT:0;
    unsigned position=0,chunk=0,next_yield=1024;
    while(position<GEN_PROBE_FRAMES){
        for(unsigned event:gen_probe_resets)if(position==event){
            auto token=gen_probe_watch_begin();patch->setParameterValue(0,1,RNBO::TimeNow);
            gen_probe_watch_end(token,&r->event_allocations,&r->event_frees);
            check(patch->getParameterValue(0)==1,"reset-readback");++r->resets;
        }
        for(unsigned event:gen_probe_prepares)if(position==event){
            auto token=gen_probe_watch_begin();patch->prepareToProcess(44100,256,true);
            gen_probe_watch_end(token,&r->event_allocations,&r->event_frees);++r->prepares;
        }
        unsigned count=nominal?nominal:gen_probe_mixed[chunk%7];++chunk;
        count=std::min(count,GEN_PROBE_FRAMES-position);
        for(unsigned event:gen_probe_resets)if(event>position)count=std::min(count,event-position);
        for(unsigned event:gen_probe_prepares)if(event>position)count=std::min(count,event-position);
        check(count>0&&count<=256,"call-span");
        fill(left);fill(right);fill(out_left);fill(out_right);
        for(unsigned i=0;i<count;++i){left.data[i]=value(gen_probe_inputs[stimulus][2*(position+i)]);right.data[i]=value(gen_probe_inputs[stimulus][2*(position+i)+1]);}
        auto token=gen_probe_watch_begin();uint32_t started=gen_probe_cycles();
        patch->process(ins,2,outs,2,count);
        uint32_t elapsed=gen_probe_cycles()-started;gen_probe_watch_end(token,&r->process_allocations,&r->process_frees);
        r->cycles+=elapsed;r->max_call_cycles=std::max(r->max_call_cycles,uint64_t(elapsed));++r->calls;++r->histogram[count];
        guards(left,count);guards(right,count);guards(out_left,count);guards(out_right,count);++r->guard_checks;
        for(unsigned i=0;i<count;++i)for(unsigned ch=0;ch<2;++ch){
            unsigned word=2*(position+i)+ch;float actual=ch?out_right.data[i]:out_left.data[i];
            check(std::isfinite(actual),"nonfinite-output");uint32_t actual_bits=bits(actual),expected=gen_probe_expected[(Model-1)*2+stimulus][word];
            double error=std::abs(double(actual)-double(value(expected)));r->maximum_error=std::max(r->maximum_error,error);
            if(actual_bits!=expected){++r->bit_differences;if((actual_bits&0x7fffffffu)==0&&(expected&0x7fffffffu)==0)++r->zero_sign_differences;else if(error<=limit)++r->within_limit;}
            if(error>limit){if(r->first_numeric_word==UINT32_MAX){r->first_numeric_word=word;r->first_actual=actual_bits;r->first_expected=expected;}++r->numeric_mismatches;}
            if(baseline&&actual_bits!=baseline[word])++r->partition_differences;
            capture[word]=actual_bits;
            check(bits(ch?right.data[i]:left.data[i])==gen_probe_inputs[stimulus][word],"input-buffer-modified");++r->unchanged_input_words;
        }
        position+=count;
        if(position>=next_yield){gen_probe_yield();next_yield+=1024;}
    }
    check(r->resets==4&&r->prepares==2,"event-counts");
    patch->~Patch();gen_probe_release(storage);
}
}
