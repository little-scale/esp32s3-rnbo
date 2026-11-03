/* SPDX-License-Identifier: MIT */
/* Standalone real-header robustness checks. Not an RNBO module/ELF test. */
#pragma STDC FENV_ACCESS ON
#include "onepole_stable.h"
#include <algorithm>
#include <cassert>
#include <cfenv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
static float number(uint32_t u){float f;std::memcpy(&f,&u,4);return f;}
static uint32_t bits(float f){uint32_t u;std::memcpy(&u,&f,4);return u;}
static uint32_t finite(uint32_t u){return (u&0x7f800000u)==0x7f800000u?u&0xff7fffffu:u;}
static uint64_t trials=0,coefficient_trials=0,nonfinite=0,coefficient_bad=0;
static void trial(float x,float a,float y,float correction){
 assert(std::isfinite(x)&&std::isfinite(y)&&std::isfinite(correction)&&std::isfinite(a)&&a>=0.f&&a<=rnbo_s3_onepole::maximum_coefficient);
 float output=rnbo_s3_onepole::step(x,a,y,correction);++trials;
 if(!std::isfinite(output)||!std::isfinite(y)||!std::isfinite(correction)||bits(output)!=bits(y))++nonfinite;
}
static void coefficient(uint32_t word){
 float hz=number(word);assert(std::isfinite(hz));float a=rnbo_s3_onepole::coefficient(hz);++coefficient_trials;
 if(!std::isfinite(a)||a<rnbo_s3_onepole::minimum_coefficient||a>rnbo_s3_onepole::maximum_coefficient)++coefficient_bad;
 if(hz<=0.f)assert(bits(a)==bits(rnbo_s3_onepole::minimum_coefficient));
 if(hz>=100000.f)assert(bits(a)==bits(rnbo_s3_onepole::maximum_coefficient));
}
int main(){
 assert(!std::fesetround(FE_TONEAREST)&&std::fegetround()==FE_TONEAREST);
 const uint32_t alphas[]={0,0x80000000u,1,0x007fffffu,0x00800000u,0x3727c5acu,0x3effffffu,0x3f000000u,0x3f000001u,0x3f7fff57u,0x3f7fff58u};
 const uint32_t positive[]={0,1,2,0x007fffffu,0x00800000u,0x00800001u,0x3dccccccu,0x3effffffu,0x3f000000u,0x3f800000u,0x4b800000u,0x7f000000u,0x7f7ffffeu,0x7f7fffffu};
 std::vector<uint32_t> edges;for(auto x:positive){edges.push_back(x);edges.push_back(x|0x80000000u);}
 const uint32_t debts[]={0,0x80000000u,1,0x80000001u,0x3f000000u,0xbf000000u,0x7f7fffffu,0xff7fffffu};
 for(auto x:edges)for(auto y:edges)for(auto a:alphas)for(auto c:debts)trial(number(x),number(a),number(y),number(c));
 float y=FLT_MAX,c=-FLT_MAX;float forced=rnbo_s3_onepole::step(FLT_MAX,.5f,y,c);assert(forced==FLT_MAX&&y==FLT_MAX&&c==0.f);
 y=-FLT_MAX;c=FLT_MAX;float symmetric=rnbo_s3_onepole::step(-FLT_MAX,.5f,y,c);assert(symmetric==-FLT_MAX&&y==-FLT_MAX&&c==0.f);
 y=-FLT_MAX;c=0.f;float opposite=rnbo_s3_onepole::step(FLT_MAX,.5f,y,c);assert(opposite==0.f&&y==0.f&&c==0.f);
 uint32_t random=0xa341316cu;
 auto next=[&](){random^=random<<13;random^=random>>17;random^=random<<5;return random;};
 for(unsigned i=0;i<1048576;++i){
  uint32_t x=finite(next()),yb=finite(next()),debt=finite(next()),a=next()%0x3f7fff59u;
  trial(number(x),number(a),number(yb),number(debt));coefficient(finite(next()));
 }
 for(uint32_t e=0;e<255;++e)for(uint32_t mantissa:{0u,1u,0x3fffffu,0x7ffffeu,0x7fffffu})for(uint32_t sign:{0u,0x80000000u})coefficient((e<<23)|mantissa|sign);
 // The ideal clamp boundaries are used only to select neighbours, never as an
 // accuracy gate or to fit outputs. The tested contract here is finite/range.
 const float boundary_low=float(-std::log1p(-double(rnbo_s3_onepole::minimum_coefficient))*44100.0/(2.0*3.14159265358979323846));
 const float boundary_high=float(-std::log1p(-double(rnbo_s3_onepole::maximum_coefficient))*44100.0/(2.0*3.14159265358979323846));
 for(float centre:{0.f,100000.f,.05f,1.f,boundary_low,boundary_high})for(int offset=-128;offset<=128;++offset){
  uint32_t word=bits(centre);if(word>=uint32_t(-std::min(offset,0)))coefficient(finite(word+offset));
 }
 uint64_t sequence_samples=0;
 for(unsigned chain=0;chain<32;++chain){
  y=number(finite(next()));c=number(finite(next()));
  for(unsigned i=0;i<8192;++i){float x=number(finite(next())),a=rnbo_s3_onepole::coefficient(number(finite(next())));float out=rnbo_s3_onepole::step(x,a,y,c);++sequence_samples;assert(std::isfinite(out)&&std::isfinite(y)&&std::isfinite(c)&&bits(out)==bits(y));}
 }
 assert(!nonfinite&&!coefficient_bad);
 std::printf("{\"standalone_state_trials\":%llu,\"state_nonfinite_or_return_mismatch\":%llu,\"coefficient_frequency_trials\":%llu,\"coefficient_nonfinite_or_out_of_bounds\":%llu,\"stateful_sequence_samples\":%llu,\"forced_debt_overflow_y_bits\":\"%08x\",\"forced_symmetric_y_bits\":\"%08x\",\"opposite_extreme_result_bits\":\"%08x\",\"rounding\":\"FE_TONEAREST\",\"hardware_executed\":false,\"full_RNBO_wrapper_executed\":false}\n",(unsigned long long)trials,(unsigned long long)nonfinite,(unsigned long long)coefficient_trials,(unsigned long long)coefficient_bad,(unsigned long long)sequence_samples,bits(forced),bits(symmetric),bits(opposite));
}
