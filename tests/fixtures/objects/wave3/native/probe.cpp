/* SPDX-License-Identifier: MIT */
/* Original observer using actual production dynamic C ABI and private arena.
 * Native lifecycle counters below are stubs; this is not an ELF lifecycle test. */
#include "rnbo_s3_dynamic.h"
#include "lifecycle.hpp"
#include "pcm_output.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
extern "C" int rnbo_native_entry(int,char **);
namespace rnbo_dynamic {std::uint32_t constructor_runs=1;volatile std::uint32_t *finalizer_observer=nullptr;std::uint32_t registered_finalizers(){return 1;}}
alignas(4096) static unsigned char storage[262144];
struct Event{uint32_t block,index,raw;};static_assert(sizeof(Event)==12,"event layout");
static FILE *open(const char *p,const char *m){FILE *f=std::fopen(p,m);assert(f);return f;}
static uint32_t bits(float x){uint32_t b;std::memcpy(&b,&x,4);return b;}
static float value(uint32_t x){float b;std::memcpy(&b,&x,4);return b;}
struct Stats{rnbo_s3_stats b{};rnbo_s3_dynamic_stats d{};};
static Stats stats(const rnbo_s3_module&m,const rnbo_s3_dynamic_info&i,void*c){Stats s;s.b.struct_bytes=sizeof s.b;s.d.struct_bytes=sizeof s.d;assert(!m.statistics(c,&s.b)&&!i.statistics(c,&s.d));return s;}
static bool healthy(const Stats&s){return !s.b.errors&&!s.b.invalid_samples&&!s.b.faulted&&!s.b.late_platform_allocations&&!s.d.late_cpp_new_calls&&!s.d.total_late_allocations&&!s.d.bootstrap_allocation_attempts;}
static void fields(FILE*f,const Stats&s){std::fprintf(f,"\"blocks\":%llu,\"position\":%llu,\"arena_used\":%u,\"arena_high_water\":%u,\"platform_allocations\":%llu,\"late_platform\":%llu,\"cpp_new\":%llu,\"late_cpp\":%llu,\"total_late\":%llu,\"errors\":%llu,\"invalid_samples\":%llu,\"faulted\":%u,\"bootstrap_attempts\":%u",(unsigned long long)s.b.blocks,(unsigned long long)s.b.sample_position,s.d.arena_used,s.d.arena_high_water,(unsigned long long)s.b.platform_allocations,(unsigned long long)s.b.late_platform_allocations,(unsigned long long)s.d.cpp_new_calls,(unsigned long long)s.d.late_cpp_new_calls,(unsigned long long)s.d.total_late_allocations,(unsigned long long)s.b.errors,(unsigned long long)s.b.invalid_samples,s.b.faulted,s.d.bootstrap_allocation_attempts);}
static void readbacks(FILE*f,const rnbo_s3_module&m,void*c,unsigned count){float a[8],n[8];for(unsigned i=0;i<count;++i)assert(!m.parameter_value(c,i,&a[i],&n[i])&&std::isfinite(a[i])&&std::isfinite(n[i]));std::fprintf(f,"\"actual_bits\":[");for(unsigned i=0;i<count;++i)std::fprintf(f,"%s\"%08x\"",i?",":"",bits(a[i]));std::fprintf(f,"],\"normalized_bits\":[");for(unsigned i=0;i<count;++i)std::fprintf(f,"%s\"%08x\"",i?",":"",bits(n[i]));std::fprintf(f,"]");}
int main(int argc,char**argv){
 assert(argc==4);FILE*pf=open(argv[1],"rb");uint32_t h[8];assert(std::fread(h,4,8,pf)==8&&h[0]==0x57563331&&h[1]==1);unsigned blocks=h[2],warm=h[3],seed=h[4],count=h[5],cycles=h[6],params=h[7];assert(blocks<=4096&&warm<=4&&count<=4096&&cycles==2&&params<=8);Event events[4096];assert(std::fread(events,12,count,pf)==count&&std::fgetc(pf)==EOF&&!std::fclose(pf));
 FILE*input=open(argv[2],"rb");char path[2048];std::snprintf(path,sizeof path,"%s.f32",argv[3]);FILE*audio=open(path,"wb");std::snprintf(path,sizeof path,"%s.pcm16",argv[3]);FILE*pcm=open(path,"wb");std::snprintf(path,sizeof path,"%s.trace.jsonl",argv[3]);FILE*trace=open(path,"w");
 rnbo_s3_module m{};m.struct_bytes=sizeof m;rnbo_s3_dynamic_info info{};info.struct_bytes=sizeof info;rnbo_s3_dynamic_request req{};req.struct_bytes=sizeof req;req.magic=RNBO_S3_DYNAMIC_MAGIC;req.abi_major=RNBO_S3_DYNAMIC_ABI_MAJOR;req.operation=RNBO_S3_DYNAMIC_DESCRIBE;req.out_module=&m;req.out_info=&info;req.result=RNBO_S3_DYNAMIC_RESULT_PENDING;char*args[]={reinterpret_cast<char*>(&req)};assert(!rnbo_native_entry(1,args)&&!req.result);assert(m.role==RNBO_S3_FX&&m.audio_inputs==2&&m.audio_outputs==2&&m.sample_rate==44100&&m.block_frames==256);
 req.operation=RNBO_S3_DYNAMIC_BIND;req.state=storage;req.state_bytes=info.context_bytes+4096;req.result=RNBO_S3_DYNAMIC_RESULT_PENDING;assert(req.state_bytes<=sizeof storage&&!rnbo_native_entry(1,args)&&!req.result);
 std::printf("{\"context_bytes\":%u,\"arena_capacity\":4096,\"cycles\":[",info.context_bytes);
 for(unsigned cycle=0;cycle<cycles;++cycle){
  std::rewind(input);rnbo_s3_create_options options{sizeof options,4096,warm,seed};void*c=nullptr;assert(!m.create(&options,&c)&&!m.prepare(c)&&m.parameter_count(c)==params);
  rnbo_s3_parameter_info schema[8]{};for(unsigned i=0;i<params;++i){schema[i].struct_bytes=sizeof schema[i];assert(!m.parameter_info(c,i,&schema[i])&&schema[i].index==i);}
  alignas(16)float inL[256],inR[256],outL[256],outR[256],wire[512];const float*ins[]={inL,inR};float*outs[]={outL,outR};int16_t words[512];pcm_output sink;pcm_output_init(&sink);unsigned at=0,captured=0;int failure=0;const char*stage="none";
  for(unsigned block=0;block<blocks&&!failure;++block){
   while(at<count&&events[at].block==block){const auto&e=events[at];assert(e.index<params);rnbo_s3_event ev{};ev.struct_bytes=sizeof ev;ev.kind=RNBO_S3_PARAMETER_ACTUAL;ev.parameter_index=e.index;ev.value=value(e.raw);int result=m.event(c,&ev);Stats state=stats(m,info,c);std::fprintf(trace,"{\"kind\":\"event\",\"cycle\":%u,\"block\":%u,\"order\":%u,\"id\":\"%s\",\"index\":%u,\"requested_bits\":\"%08x\",\"result\":%d,",cycle,block,at,schema[e.index].id,e.index,e.raw,result);readbacks(trace,m,c,params);std::fprintf(trace,",");fields(trace,state);std::fprintf(trace,"}\n");std::fflush(trace);++at;if(result||!healthy(state)){failure=result?result:RNBO_S3_FAULT;stage="event";break;}}
   if(failure)break;assert(std::fread(wire,4,512,input)==512);for(unsigned i=0;i<256;++i){inL[i]=wire[2*i];inR[i]=wire[2*i+1];assert(std::isfinite(inL[i])&&std::isfinite(inR[i]));}
   int result=m.process(c,ins,outs,256,uint64_t(block)*256);Stats state=stats(m,info,c);std::fprintf(trace,"{\"kind\":\"block\",\"cycle\":%u,\"block\":%u,\"result\":%d,\"first_input_bits\":[\"%08x\",\"%08x\"],\"first_output_bits\":[\"%08x\",\"%08x\"],\"last_output_bits\":[\"%08x\",\"%08x\"],",cycle,block,result,bits(inL[0]),bits(inR[0]),bits(outL[0]),bits(outR[0]),bits(outL[255]),bits(outR[255]));readbacks(trace,m,c,params);std::fprintf(trace,",");fields(trace,state);std::fprintf(trace,"}\n");
   for(unsigned i=0;i<256;++i){wire[2*i]=outL[i];wire[2*i+1]=outR[i];}assert(std::fwrite(wire,4,512,audio)==512&&pcm_output_render(&sink,outL,outR,words,256,2,100,.5f,0)&&std::fwrite(words,2,512,pcm)==512);++captured;if(result||!healthy(state)){failure=result?result:RNBO_S3_FAULT;stage="process";break;}
  }
  Stats final=stats(m,info,c);bool completed=!failure&&captured==blocks&&at==count;if(completed){assert(std::fgetc(input)==EOF&&final.b.blocks==blocks&&final.b.sample_position==uint64_t(blocks)*256&&healthy(final));}
  assert(!m.panic(c)&&m.process(c,ins,outs,256,final.b.sample_position)==RNBO_S3_FAULT);for(unsigned i=0;i<256;++i)assert(outL[i]==0&&outR[i]==0);
  if(cycle)std::printf(",");std::printf("{\"cycle\":%u,\"completed\":%s,\"captured_blocks\":%u,\"events_applied\":%u,\"first_failure\":%d,\"failure_stage\":\"%s\",\"panic_silent\":true,",cycle,completed?"true":"false",captured,at,failure,stage);fields(stdout,final);std::printf(",\"pcm_nonfinite\":%llu,\"pcm_clipped\":%llu}",(unsigned long long)sink.nonfinite,(unsigned long long)sink.clipped);m.destroy(c);
 }
 std::printf("]}\n");assert(!std::fclose(input)&&!std::fclose(audio)&&!std::fclose(pcm)&&!std::fclose(trace));
}
