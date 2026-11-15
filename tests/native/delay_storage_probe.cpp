// SPDX-License-Identifier: MIT
// Offline research for the single delaytilde_01 ring in SawSAHArpy.
// Same production wrapper, included so this probe can exercise generated ring
// methods directly. Never linked into firmware or the production renderer.
#include <chrono>
#include <cassert>
#include "../../module-sdk/wrapper/rnbo_s3_static.cpp"

// Public member pointers expose only these protected members for this probe;
// the live object remains a real Patch (no downcast to an unconstructed subtype).
struct RingAccess : Patch {
    static constexpr auto reset=&RingAccess::delaytilde_01_del_reset;
    static constexpr auto clear=&RingAccess::delaytilde_01_del_clear;
    static constexpr auto read=&RingAccess::delaytilde_01_del_read;
    static constexpr auto write=&RingAccess::delaytilde_01_del_write;
    static constexpr auto step=&RingAccess::delaytilde_01_del_step;
    static constexpr auto reader=&RingAccess::delaytilde_01_del_reader;
    static constexpr auto writer=&RingAccess::delaytilde_01_del_writer;
    static constexpr auto buffer=&RingAccess::delaytilde_01_del_buffer;
};

static void word(FILE *f, float value) {
    assert(std::isfinite(value));
    uint32_t bits; std::memcpy(&bits, &value, 4);
    for (unsigned i=0;i<4;++i) assert(std::fputc((bits>>(8*i))&255, f)!=EOF);
}
static void parameter(const rnbo_s3_module *m, void *ctx, const char *id, float value) {
    for (unsigned i=0;i<m->parameter_count(ctx);++i) {
        rnbo_s3_parameter_info info{}; info.struct_bytes=sizeof info;
        assert(m->parameter_info(ctx,i,&info)==0);
        if (std::strcmp(info.id,id)) continue;
        rnbo_s3_event e{}; e.struct_bytes=sizeof e;
        e.kind=RNBO_S3_PARAMETER_ACTUAL; e.parameter_index=i; e.value=value;
        assert(m->event(ctx,&e)==0); return;
    }
    assert(false && "Missing authored parameter");
}
int main(int argc,char **argv) {
    assert(argc==4);
    const char *mode=argv[1]; unsigned count=std::strtoul(argv[2],nullptr,10);
    assert(count>=512 && count<=1000000);
    FILE *capture=std::fopen(argv[3],"wb"); assert(capture);
    const auto *m=rnbo_s3_static_module(); void *ctx=nullptr;
    rnbo_s3_create_options options{sizeof options,1048576,0,12345};
    assert(m->create(&options,&ctx)==0 && m->prepare(ctx)==0);
    auto *patch=static_cast<Context *>(ctx)->patch;
    uint64_t words=0; double total_us=0,peak_us=0;
    if (!std::strcmp(mode,"ring")) {
        // Values 0..7 cover all seven generated interpolation branches
        // (4 and 5 share the fallback), plus clamp/fractional
        // boundaries, repeated wraps, decaying feedback, clear and reset.
        const float delays[]={-1,0,0.5f,1,1.25f,2.5f,11025,11025.5f,22049.75f,22050,22051};
        for (unsigned interpolation=0;interpolation<8;++interpolation) {
            (patch->*RingAccess::reset)();
            (patch->*RingAccess::reader)=(patch->*RingAccess::writer)=0;
            uint32_t random=12345; float feedback=0;
            for (unsigned i=0;i<count;++i) {
                if (i==count/2) {
                    (patch->*RingAccess::clear)();
                    // Independently verify clearing, rather than just matching
                    // two implementations that could both fail to clear.
                    for (unsigned j=0;j<32768;++j) assert((patch->*RingAccess::buffer)[j]==0);
                    feedback=0;
                }
                float delay=delays[(i/257)%11];
                float output=(patch->*RingAccess::read)(delay,interpolation);
                random^=random<<13; random^=random>>17; random^=random<<5;
                float input=i%32768<1024 ? (float(int(random&65535)-32768)/65536) : 0;
                feedback=input+output*0.6f;
                (patch->*RingAccess::write)(feedback);
                (patch->*RingAccess::step)(); word(capture,output); ++words;
            }
        }
        // Independent integer-delay impulse oracle, including wrap and reset.
        (patch->*RingAccess::reset)();
        (patch->*RingAccess::reader)=(patch->*RingAccess::writer)=0;
        for (unsigned i=0;i<66000;++i) {
            float value=(patch->*RingAccess::read)(22050,0);
            assert(value==(i==22050 ? 1.0f : 0.0f));
            (patch->*RingAccess::write)(i==0 ? 1 : 0);
            (patch->*RingAccess::step)();
        }
    } else {
        assert(!std::strcmp(mode,"default") || !std::strcmp(mode,"minimum") ||
            !std::strcmp(mode,"maximum") || !std::strcmp(mode,"fractional") ||
            !std::strcmp(mode,"sweep") || !std::strcmp(mode,"jumps"));
        if (!std::strcmp(mode,"minimum")) {parameter(m,ctx,"touch_x",0.1f);parameter(m,ctx,"touch_y",25);}
        if (!std::strcmp(mode,"maximum")) {parameter(m,ctx,"touch_x",1);parameter(m,ctx,"touch_y",250);}
        if (!std::strcmp(mode,"fractional")) {parameter(m,ctx,"touch_x",0.37f);parameter(m,ctx,"touch_y",81.125f);}
        float l[256],r[256]; float *out[]={l,r};
        for (unsigned b=0;b<count;++b) {
            if (!std::strcmp(mode,"sweep") && b%8==0) {
                float value=float((b/8)%129)/128;
                parameter(m,ctx,"touch_x",0.1f+0.9f*value);
                parameter(m,ctx,"touch_y",25+225*value);
            }
            if (!std::strcmp(mode,"jumps")) {
                parameter(m,ctx,"touch_x",b%2 ? 0.1f : 1);
                parameter(m,ctx,"touch_y",b%2 ? 25 : 250);
            }
            auto start=std::chrono::steady_clock::now();
            assert(m->process(ctx,nullptr,out,256,uint64_t(b)*256)==0);
            double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
            total_us+=us; peak_us=std::fmax(peak_us,us);
            for (unsigned i=0;i<256;++i) {word(capture,l[i]);word(capture,r[i]);words+=2;}
        }
    }
    rnbo_s3_stats stats{}; stats.struct_bytes=sizeof stats;
    assert(m->statistics(ctx,&stats)==0);
    assert(!stats.errors && !stats.invalid_samples && !stats.late_platform_allocations);
    assert(std::fclose(capture)==0);
    std::printf("{\"words\":%llu,\"arena_used\":%u,\"errors\":%llu,\"invalid_samples\":%llu,\"late_platform_allocations\":%llu,\"host_mean_process_us\":%.6f,\"host_peak_process_us\":%.6f}\n",
        (unsigned long long)words,stats.arena_used,(unsigned long long)stats.errors,
        (unsigned long long)stats.invalid_samples,(unsigned long long)stats.late_platform_allocations,
        total_us/count,peak_us);
    m->destroy(ctx);
}
