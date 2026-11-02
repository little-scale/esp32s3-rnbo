/* SPDX-License-Identifier: MIT */
/* Original second-wave fixture harness. Scheduled parameter changes occur at
 * declared block boundaries; optional FX input is a bounded stereo float file. */
#include "rnbo_s3_module.h"
#include "pcm_output.h"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

static void le16(FILE *f, uint16_t v) { std::fputc(v & 255,f); std::fputc(v>>8,f); }
static void le32(FILE *f, uint32_t v) { le16(f,v&65535);le16(f,v>>16); }
static bool input_block(FILE *f, float *left, float *right) {
    static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559);
    for(unsigned i=0;i<256;++i)for(float *channel:{left,right}) {
        uint32_t bits=0;
        for(unsigned byte=0;byte<4;++byte) {int c=std::fgetc(f);if(c==EOF)return false;bits|=static_cast<uint32_t>(c)<<(byte*8);}
        std::memcpy(channel+i,&bits,sizeof(bits));
        if(!std::isfinite(channel[i]))return false;
    }
    return true;
}
struct Setting { std::string id; float value; bool normalized; unsigned block=0; };
static unsigned number(const char *s) {
    char *end; unsigned long n=std::strtoul(s,&end,0);
    if(!*s || *end || n>UINT32_MAX) { std::fprintf(stderr,"invalid integer: %s\n",s); std::exit(2); }
    return static_cast<unsigned>(n);
}
int main(int argc, char **argv) {
    const char *output=nullptr, *float_output=nullptr, *input_path=nullptr;
    unsigned blocks=173,warmup=1,seed=12345,arena_bytes=1024*1024;
    bool normalized=false;
    std::vector<Setting> settings;
    std::vector<rnbo_s3_event> midi;
    for(int i=1;i<argc;++i) {
        if(std::strcmp(argv[i],"--output")==0 && i+1<argc) output=argv[++i];
        else if(std::strcmp(argv[i],"--input-float")==0 && i+1<argc) input_path=argv[++i];
        else if(std::strcmp(argv[i],"--float-output")==0 && i+1<argc) float_output=argv[++i];
        else if(std::strcmp(argv[i],"--blocks")==0 && i+1<argc) blocks=number(argv[++i]);
        else if(std::strcmp(argv[i],"--warmup")==0 && i+1<argc) warmup=number(argv[++i]);
        else if(std::strcmp(argv[i],"--seed")==0 && i+1<argc) seed=number(argv[++i]);
        else if(std::strcmp(argv[i],"--arena-bytes")==0 && i+1<argc) arena_bytes=number(argv[++i]);
        else if(std::strcmp(argv[i],"--normalized")==0) normalized=true;
        else if(std::strcmp(argv[i],"--at-parameter")==0 && i+3<argc) {
            unsigned block=number(argv[++i]);std::string id=argv[++i];char *end;float v=std::strtof(argv[++i],&end);
            if(*end || !std::isfinite(v))return 2;
            settings.push_back({id,v,normalized,block});
        } else if(std::strcmp(argv[i],"--parameter")==0 && i+2<argc) {
            std::string id=argv[++i];char *end;float v=std::strtof(argv[++i],&end);
            if(*end || !std::isfinite(v)) return 2;
            settings.push_back({id,v,normalized});
        } else if(std::strcmp(argv[i],"--midi")==0 && i+3<argc) {
            rnbo_s3_event e{};e.struct_bytes=sizeof(e);e.kind=RNBO_S3_MIDI;e.midi_length=3;
            for(unsigned b=0;b<3;++b) { unsigned v=number(argv[++i]);if(v>255)return 2;e.midi[b]=v; }
            if((e.midi[0]&0xf0)==0xc0 || (e.midi[0]&0xf0)==0xd0)e.midi_length=2;
            midi.push_back(e);
        } else { std::fprintf(stderr,"usage: rnbo_render --output FILE.wav [--float-output FILE.f32] [--blocks N] [--warmup N] [--seed UINT32] [--normalized] [--parameter ID VALUE] [--midi STATUS D1 D2]\n"); return 2; }
    }
    if(!output || !blocks || blocks>4096 || warmup>64 || arena_bytes<4096 || arena_bytes>4*1024*1024)return 2;
    const rnbo_s3_module *m=rnbo_s3_static_module();
    if(m->audio_inputs!=(m->role==RNBO_S3_FX?2u:0u) || m->audio_outputs!=2 || (m->role==RNBO_S3_FX&&!input_path))return 2;
    for(const auto &setting:settings)if(setting.block>=blocks)return 2;
    void *ctx=nullptr;rnbo_s3_create_options options{sizeof(options),arena_bytes,warmup,seed};
    if(m->create(&options,&ctx) || m->prepare(ctx)) { std::fprintf(stderr,"module preparation failed\n");if(ctx)m->destroy(ctx);return 1; }
    auto apply=[&](unsigned block) {
    for(const auto &setting:settings) {
        if(setting.block!=block)continue;
        bool found=false;
        for(uint32_t i=0;i<m->parameter_count(ctx);++i) {
            rnbo_s3_parameter_info info{};info.struct_bytes=sizeof(info);
            if(m->parameter_info(ctx,i,&info))return 1;
            if(setting.id!=info.id)continue;
            rnbo_s3_event e{};e.struct_bytes=sizeof(e);e.parameter_index=i;e.value=setting.value;
            e.kind=setting.normalized?RNBO_S3_PARAMETER_NORMALIZED:RNBO_S3_PARAMETER_ACTUAL;
            if(m->event(ctx,&e)) { std::fprintf(stderr,"invalid parameter value: %s\n",info.id);return 1; }
            found=true;break;
        }
        if(!found) { std::fprintf(stderr,"unknown parameter: %s\n",setting.id.c_str());return 2; }
    }
        return 0;
    };
    for(const auto &e:midi)if(m->event(ctx,&e))return 1;
    FILE *f=std::fopen(output,"wb");if(!f){std::perror(output);m->destroy(ctx);return 1;}
    FILE *input=input_path?std::fopen(input_path,"rb"):nullptr;if(input_path&&!input){std::fclose(f);m->destroy(ctx);return 1;}
    FILE *floats=float_output?std::fopen(float_output,"wb"):nullptr;
    if(float_output && !floats){std::perror(float_output);std::fclose(f);m->destroy(ctx);return 1;}
    uint32_t bytes=blocks*RNBO_S3_BLOCK_FRAMES*4;
    std::fwrite("RIFF",1,4,f);le32(f,36+bytes);std::fwrite("WAVEfmt ",1,8,f);le32(f,16);
    le16(f,1);le16(f,2);le32(f,RNBO_S3_SAMPLE_RATE);le32(f,RNBO_S3_SAMPLE_RATE*4);le16(f,4);le16(f,16);
    std::fwrite("data",1,4,f);le32(f,bytes);
    float left[256]{},right[256]{},input_left[256]{},input_right[256]{};
    float *out[]={left,right};const float *in[]={input_left,input_right};int16_t pcm[512];
    pcm_output sink;pcm_output_init(&sink);
    double squares=0,peak=0,total_us=0,max_us=0;
    int status=0;
    for(unsigned block=0;block<blocks;++block) {
        if(int error=apply(block)){status=error;break;}
        if(input && !input_block(input,input_left,input_right)) {status=1;break;}
        auto start=std::chrono::steady_clock::now();
        if(m->process(ctx,m->audio_inputs?in:nullptr,out,256,static_cast<uint64_t>(block)*256)) { status=1;break; }
        double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        total_us+=us;if(us>max_us)max_us=us;
        for(unsigned i=0;i<256;++i)for(float v:{left[i],right[i]}) {
            squares+=static_cast<double>(v)*v;if(std::fabs(v)>peak)peak=std::fabs(v);
            if(floats) {uint32_t bits;static_assert(sizeof(v)==sizeof(bits));std::memcpy(&bits,&v,sizeof bits);le32(floats,bits);}
        }
        if(!pcm_output_render(&sink,left,right,pcm,256,2,100,0.5f,0)) { status=1;break; }
        for(int16_t value:pcm)le16(f,static_cast<uint16_t>(value));
        if(std::ferror(f) || (floats && std::ferror(floats))) {status=1;break;}
    }
    if(input){if(std::fgetc(input)!=EOF || std::ferror(input))status=1;if(std::fclose(input))status=1;}
    if(std::fclose(f))status=1;
    if(floats && std::fclose(floats))status=1;
    rnbo_s3_stats stats{};stats.struct_bytes=sizeof(stats);m->statistics(ctx,&stats);
    std::printf("{\"evidence_kind\":\"host_render\",\"sample_rate\":44100,\"block_frames\":256,\"blocks\":%llu,\"warmup_blocks\":%u,\"seed\":%u,\"peak\":%.9g,\"rms\":%.9g,\"mean_process_us\":%.4f,\"max_process_us\":%.4f,\"platform_allocations\":%llu,\"late_platform_allocations\":%llu,\"arena_used\":%u,\"errors\":%llu,\"invalid_samples\":%llu,\"allocation_coverage\":\"RNBO platform hooks only\",\"target_performance_qualified\":false}\n",
        static_cast<unsigned long long>(stats.blocks),stats.warmup_blocks,seed,peak,std::sqrt(squares/(blocks*512.0)),total_us/blocks,max_us,
        static_cast<unsigned long long>(stats.platform_allocations),static_cast<unsigned long long>(stats.late_platform_allocations),stats.arena_used,
        static_cast<unsigned long long>(stats.errors),static_cast<unsigned long long>(stats.invalid_samples));
    m->destroy(ctx);return status;
}
