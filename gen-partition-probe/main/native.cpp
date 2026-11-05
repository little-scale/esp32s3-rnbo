/* SPDX-License-Identifier: MIT */
// Same harness and source producers on the host. CPU/heap hooks are absent;
// zero-valued timing/allocation fields here are placeholders, not measurements.
#include "probe_api.h"
#include "report.h"
#include <cstdlib>
#include <string>
extern "C" void *gen_probe_allocate(size_t n){return std::malloc(n);}
extern "C" void gen_probe_release(void*p){std::free(p);}
extern "C" uint32_t gen_probe_cycles(){return 0;}
extern "C" uint64_t gen_probe_watch_begin(){return 0;}
extern "C" void gen_probe_watch_end(uint64_t,uint32_t*,uint32_t*){}
extern "C" void gen_probe_yield(){}
extern "C" void gen_probe_fault(const char*reason){std::fprintf(stderr,"FAULT %s\n",reason);std::exit(2);}
int main(int argc,char**argv){
    if(argc!=2)gen_probe_fault("capture-directory-required");
    auto*baseline=static_cast<uint32_t*>(gen_probe_allocate(8192*4));auto*capture=static_cast<uint32_t*>(gen_probe_allocate(8192*4));if(!baseline||!capture)gen_probe_fault("capture-storage");
    gen_probe_program programs[]={gen_partition_program_1,gen_partition_program_2,gen_partition_program_3};
    for(unsigned model=1;model<=3;++model)for(unsigned stimulus=0;stimulus<2;++stimulus)for(unsigned run=0;run<13;++run){
        unsigned repeat=run?1+(run-1)/6:0,nominal=run?gen_probe_partitions[(run-1)%6]:1;gen_probe_result result{};
        programs[model-1](stimulus,nominal,run?capture:baseline,run?baseline:nullptr,&result);gen_probe_print(model,stimulus,repeat,nominal,result,"native-file");
        std::string file=std::string(argv[1])+"/"+gen_probe_names[model-1]+"-"+gen_probe_stimuli[stimulus]+"-r"+std::to_string(repeat)+"-p"+std::to_string(nominal)+".u32";
        FILE*out=std::fopen(file.c_str(),"wb");if(!out||std::fwrite(run?capture:baseline,4,8192,out)!=8192||std::fclose(out))gen_probe_fault("capture-write");
    }
    gen_probe_release(capture);gen_probe_release(baseline);
}
