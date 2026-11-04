// SPDX-License-Identifier: MIT
// Only examples/midi-monitor.rnbopat: validates actual RNBO short-system input.
#include "rnbo_s3_module.h"
#include "rnbo_s3_midi.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>

int main() {
    const auto *m=rnbo_s3_static_module();
    assert(m->flags&RNBO_S3_SHORT_MIDI_INPUT);
    void *ctx=nullptr;rnbo_s3_create_options options{sizeof(options),1048576,1,12345};
    assert(m->create(&options,&ctx)==0 && m->prepare(ctx)==0);
    float left[256]{},right[256]{};float *out[]={left,right};uint64_t position=0;
    auto render=[&](){assert(m->process(ctx,nullptr,out,256,position)==0);position+=256;};
    auto send=[&](unsigned status,unsigned a=0,unsigned b=0){
        rnbo_s3_event e{};e.struct_bytes=sizeof(e);e.kind=RNBO_S3_MIDI;
        e.midi[0]=status;e.midi[1]=a;e.midi[2]=b;e.midi_length=rnbo_s3_midi_length(status);
        assert(m->event(ctx,&e)==0);
    };
    auto value=[&](const char *name){
        for(unsigned i=0;i<m->parameter_count(ctx);++i){rnbo_s3_parameter_info p{};p.struct_bytes=sizeof(p);
            assert(m->parameter_info(ctx,i,&p)==0);
            if(!strcmp(p.name,name)){float a,n;assert(m->parameter_value(ctx,i,&a,&n)==0);return a;}}
        assert(false);return -1.0f;
    };
    send(0x92,60,100);render();assert(value("last-note")==60&&value("last-velocity")==100);
    send(0x92,60,0);render();assert(value("last-velocity")==0);
    send(0xf8);render();float start=value("clock-count");
    for(unsigned i=0;i<96;++i){send(0xf8);render();}
    assert(value("clock-count")==start+96&&value("last-byte")==248);
    for(unsigned status:{0xfau,0xfbu,0xfcu,0xfeu,0xffu,0xf6u,0xf1u,0xf2u,0xf3u}){
        send(status,1,2);render();assert(value("last-byte")== (rnbo_s3_midi_length(status)==1?float(status):rnbo_s3_midi_length(status)==2?1.0f:2.0f));
    }
    rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);assert(m->statistics(ctx,&stats)==0);
    assert(!stats.errors&&!stats.invalid_samples&&!stats.late_platform_allocations);
    m->destroy(ctx);puts("RNBO note/velocity, 96 clocks and short-system input passed");
}
