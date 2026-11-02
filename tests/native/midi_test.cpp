/* SPDX-License-Identifier: MIT */
/* Authored midi-envelope fixture tests, not a general RNBO MIDI claim. */
#include "rnbo_s3_module.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

/* Executable-only probe. Firmware/global application allocation stays intact. */
static bool observe=false;
static unsigned late_cpp_allocations=0;
void *operator new(std::size_t n) {
    if(observe)++late_cpp_allocations;
    if(void *p=std::malloc(n?n:1))return p;
    throw std::bad_alloc();
}
void *operator new[](std::size_t n) {return ::operator new(n);}
void operator delete(void *p) noexcept {std::free(p);}
void operator delete[](void *p) noexcept {std::free(p);}
void operator delete(void *p,std::size_t) noexcept {std::free(p);}
void operator delete[](void *p,std::size_t) noexcept {std::free(p);}
void *operator new(std::size_t n,std::align_val_t alignment) {
    if(observe)++late_cpp_allocations;
    void *p=nullptr;
    if(!posix_memalign(&p,static_cast<std::size_t>(alignment),n?n:1))return p;
    throw std::bad_alloc();
}
void *operator new[](std::size_t n,std::align_val_t a) {return ::operator new(n,a);}
void operator delete(void *p,std::align_val_t) noexcept {std::free(p);}
void operator delete[](void *p,std::align_val_t) noexcept {std::free(p);}
void operator delete(void *p,std::size_t,std::align_val_t) noexcept {std::free(p);}
void operator delete[](void *p,std::size_t,std::align_val_t) noexcept {std::free(p);}

struct Instrument {
    const rnbo_s3_module *m=rnbo_s3_static_module();
    void *ctx=nullptr;
    uint64_t sample=0;
    float left[256]{},right[256]{};
    Instrument() {
        rnbo_s3_create_options options{sizeof(options),1024*1024,1,12345};
        assert(m->create(&options,&ctx)==0 && m->prepare(ctx)==0);
    }
    ~Instrument() {m->destroy(ctx);}
    void midi(unsigned status,unsigned a,unsigned b) {
        rnbo_s3_event e{};e.struct_bytes=sizeof(e);e.kind=RNBO_S3_MIDI;
        e.midi_length=3;e.midi[0]=status;e.midi[1]=a;e.midi[2]=b;
        observe=true;int result=m->event(ctx,&e);observe=false;assert(result==0);
    }
    void block() {
        float *out[]={left,right};
        observe=true;int result=m->process(ctx,nullptr,out,256,sample);observe=false;assert(result==0);
        sample+=256;
        for(unsigned i=0;i<256;++i)assert(std::isfinite(left[i]) && left[i]==right[i]);
    }
    double render(unsigned blocks) {
        double squares=0;
        for(unsigned b=0;b<blocks;++b) {
            block();for(float v:left)squares+=double(v)*v;
        }
        return std::sqrt(squares/(blocks*256.0));
    }
    double active() {render(16);double rms=render(8);assert(rms>0.005);return rms;}
    void silent() {render(24);assert(render(8)<1e-7);}
    double amplitude(unsigned note) {
        const double hz=440*std::pow(2.0,(double(note)-69)/12.0);
        double a=0,b=0;
        for(unsigned j=0;j<128;++j) {
            uint64_t start=sample;block();
            for(unsigned i=0;i<256;++i) {
                double phase=2*3.141592653589793*hz*double(start+i)/44100;
                a+=left[i]*std::sin(phase);b+=left[i]*std::cos(phase);
            }
        }
        return 2*std::hypot(a,b)/(128*256);
    }
    void clean() {
        rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);
        assert(m->statistics(ctx,&stats)==0);
        assert(!stats.late_platform_allocations && !stats.errors && !stats.invalid_samples);
        assert(late_cpp_allocations==0);
    }
};

int main(int argc,char **argv) {
    unsigned voices=argc==2?static_cast<unsigned>(std::strtoul(argv[1],nullptr,10)):0;
    assert(voices==1 || voices==2 || voices==4);
    double note_rms=0,sustain_rms=0,stolen_amplitude=0,newest_amplitude=0;
    {
        Instrument p;assert(p.render(8)==0);
        p.midi(0x93,69,100);note_rms=p.active(); // channel four survives the C boundary
        p.midi(0x93,69,100);p.active(); // repeated note-on remains an event
        p.midi(0x93,69,0);p.silent(); // note-on velocity zero releases
        p.midi(0x93,69,100);p.active();p.midi(0x83,69,64);p.silent();
        p.clean();
    }
    if(voices>1) {
        {
            Instrument p;
            p.midi(0x90,60,100);p.render(8);p.midi(0x90,67,100);p.active();
            p.midi(0x80,60,64);p.active(); // independent overlapping release
            p.midi(0x80,67,64);p.silent();p.clean();
        }
        {
            Instrument p;
            p.midi(0x94,72,100);p.active();
            p.midi(0x85,72,64);p.active(); // wrong channel must leave note held
            p.midi(0x84,72,64);p.silent();p.clean();
        }
        {
            Instrument p;
            p.midi(0x90,64,100);p.active();p.midi(0xb0,64,127);
            p.midi(0x80,64,64);sustain_rms=p.active();
            p.midi(0xb0,64,0);p.silent();p.clean();
        }
        {
            Instrument p;
            constexpr unsigned notes[]={60,62,64,65,67};
            for(unsigned i=0;i<=voices;++i){p.midi(0x90,notes[i],100);p.render(8);}
            p.render(16);
            stolen_amplitude=p.amplitude(notes[0]);newest_amplitude=p.amplitude(notes[voices]);
            assert(stolen_amplitude<0.015 && newest_amplitude>0.04);
            p.midi(0x80,notes[0],64);p.active(); // stale release cannot kill replacement
            for(unsigned i=1;i<=voices;++i)p.midi(0x80,notes[i],64);
            p.silent();p.clean();
        }
    }
    {
        Instrument p;p.midi(0x90,69,100);p.active();p.clean();
        assert(p.m->panic(p.ctx)==0);
        float *out[]={p.left,p.right};
        assert(p.m->process(p.ctx,nullptr,out,256,p.sample)==RNBO_S3_FAULT);
        for(unsigned i=0;i<256;++i)assert(p.left[i]==0 && p.right[i]==0);
        p.clean();
    }
    std::printf("{\"evidence_kind\":\"native-host-midi-fixture\",\"voices\":%u,\"note_rms\":%.9g,\"sustain_rms\":%.9g,\"stolen_note_amplitude\":%.9g,\"newest_note_amplitude\":%.9g,\"late_cpp_allocations\":%u,\"result\":\"passed\",\"mono_sustain_implemented\":false,\"target_qualified\":false}\n",
                voices,note_rms,sustain_rms,stolen_amplitude,newest_amplitude,late_cpp_allocations);
}
