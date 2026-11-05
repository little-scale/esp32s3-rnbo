/* SPDX-License-Identifier: MIT */
#include "probe_api.h"
#include "report.h"
#include "esp_app_desc.h"
#include "esp_cpu.h"
#include "esp_heap_caps.h"
#include "esp_private/esp_clk.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mbedtls/sha256.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>
extern "C" {
#include "allocation_probe.h"
}
#ifndef CONFIG_HEAP_USE_HOOKS
#error This qualification requires target heap hooks
#endif
extern "C" void *gen_probe_allocate(size_t n){return heap_caps_malloc(n,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);}
extern "C" void gen_probe_release(void*p){heap_caps_free(p);}
extern "C" uint32_t gen_probe_cycles(){return esp_cpu_get_cycle_count();}
extern "C" uint64_t gen_probe_watch_begin(){uint64_t v=(uint64_t(allocation_probe_allocations())<<32)|allocation_probe_frees();allocation_probe_begin();return v;}
extern "C" void gen_probe_watch_end(uint64_t token,uint32_t*a,uint32_t*f){allocation_probe_end();*a+=allocation_probe_allocations()-uint32_t(token>>32);*f+=allocation_probe_frees()-uint32_t(token);}
extern "C" void gen_probe_yield(){vTaskDelay(1);}
extern "C" void gen_probe_fault(const char *reason){std::printf("RNBO_SMOKE FAULT reason=%s\n",reason);std::fflush(stdout);std::abort();}
static void digest(const uint32_t*words,char*text){uint8_t sha[32];if(mbedtls_sha256(reinterpret_cast<const unsigned char*>(words),8192*4,sha,0))gen_probe_fault("capture-sha");for(unsigned i=0;i<32;++i)std::sprintf(text+2*i,"%02x",sha[i]);}
extern "C" void app_main(){
    vTaskDelay(pdMS_TO_TICKS(1500));
    if(esp_clk_cpu_freq()!=240000000)gen_probe_fault("cpu-frequency");
    uint32_t empty[64];for(auto &v:empty){uint32_t start=gen_probe_cycles();v=gen_probe_cycles()-start;}std::sort(empty,empty+64);
    const auto *app=esp_app_get_description();char firmware_sha[65];for(unsigned i=0;i<32;++i)std::sprintf(firmware_sha+2*i,"%02x",app->app_elf_sha256[i]);
    std::printf("RNBO_SMOKE START firmware_elf_sha256=%s plan_sha256=%s cases=78 route=direct-variable-producer module_abi=0 cpu_hz=240000000 clock_empty_median_cycles=%u allocation_monitor=task-heap-hooks\n",firmware_sha,GEN_PROBE_PLAN_SHA256,unsigned(empty[32]));std::fflush(stdout);
    for(unsigned model=1;model<=3;++model)for(unsigned stimulus=0;stimulus<2;++stimulus){
        char input_sha[65],expected_sha[65];digest(gen_probe_inputs[stimulus],input_sha);digest(gen_probe_expected[(model-1)*2+stimulus],expected_sha);
        std::printf("RNBO_SMOKE CACHE model=%u stimulus=%s input_sha256=%s expected_sha256=%s\n",model,gen_probe_stimuli[stimulus],input_sha,expected_sha);std::fflush(stdout);
    }
    auto*baseline=static_cast<uint32_t*>(gen_probe_allocate(8192*4));auto*capture=static_cast<uint32_t*>(gen_probe_allocate(8192*4));if(!baseline||!capture)gen_probe_fault("capture-storage");
    gen_probe_program programs[]={gen_partition_program_1,gen_partition_program_2,gen_partition_program_3};
    unsigned passed=0,mismatched=0;uint64_t process_allocations=0,process_frees=0;
    const size_t psram_before=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),internal_before=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    for(unsigned model=1;model<=3;++model)for(unsigned stimulus=0;stimulus<2;++stimulus){
        for(unsigned run=0;run<13;++run){
            unsigned repeat=run?1+(run-1)/6:0,nominal=run?gen_probe_partitions[(run-1)%6]:1;
            gen_probe_result result{};programs[model-1](stimulus,nominal,run?capture:baseline,run?baseline:nullptr,&result);
            char hash[65];digest(run?capture:baseline,hash);gen_probe_print(model,stimulus,repeat,nominal,result,hash);
            if(result.numeric_mismatches||result.partition_differences)++mismatched;else ++passed;
            process_allocations+=result.process_allocations;process_frees+=result.process_frees;vTaskDelay(1);
        }
    }
    const size_t psram_after=heap_caps_get_free_size(MALLOC_CAP_SPIRAM),internal_after=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    gen_probe_release(capture);gen_probe_release(baseline);
    std::printf("RNBO_SMOKE DONE firmware_elf_sha256=%s plan_sha256=%s cases=78 passed=%u mismatched=%u constructions=78 destructions=78 process_allocations=%" PRIu64 " process_frees=%" PRIu64 " psram_before=%u psram_after=%u internal_before=%u internal_after=%u route=direct-variable-producer module_abi=0 scope=offline_no_i2s_ui_network\n",firmware_sha,GEN_PROBE_PLAN_SHA256,passed,mismatched,process_allocations,process_frees,unsigned(psram_before),unsigned(psram_after),unsigned(internal_before),unsigned(internal_after));std::fflush(stdout);
}
