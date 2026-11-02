/* SPDX-License-Identifier: MIT */
#include "phase_trunc.h"
#include "esp_app_desc.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static volatile float inputs[256];
static volatile uint64_t sink;
static const char *TAG="phase_benchmark";
#define CHECK(x) do {if(!(x)){ESP_LOGE(TAG,": FAIL line=%d",__LINE__);abort();}}while(0)
static __attribute__((noinline)) uint32_t reference(float x){return (uint32_t)(int64_t)x;}
static __attribute__((noinline)) uint32_t candidate(float x){return rnbo_s3_phase_trunc_f32(x);}
static __attribute__((noinline)) uint64_t measure(uint32_t (*function)(float),uint32_t loops,uint64_t *checksum)
{
    uint64_t sum=0;int64_t began=esp_timer_get_time();
    for(uint32_t repeat=0;repeat<loops;++repeat)for(unsigned i=0;i<256;++i)sum+=function(inputs[i]);
    uint64_t elapsed=(uint64_t)(esp_timer_get_time()-began);sink=sum;*checksum=sum;return elapsed;
}
static void run(void *unused)
{
    (void)unused;vTaskDelay(pdMS_TO_TICKS(2000));
    char hash[65];const uint8_t *digest=esp_app_get_description()->app_elf_sha256;
    for(unsigned i=0;i<32;++i)snprintf(hash+i*2,3,"%02x",digest[i]);
    uint64_t before_us[3]={0},after_us[3]={0};unsigned checked=0;
    const char *names[]={"positive-phase","positive-increment","mixed-fallback"};
    for(unsigned kind=0;kind<3;++kind) {
        uint32_t seed=0x12345678;
        for(unsigned i=0;i<256;++i) {
            seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;
            float value;
            if(kind<2) {
                value=(float)(seed&0x7fffffffu);
                if(kind==0 && (i&1u))value+=2147483520.0f;
                if(value>=4294967296.0f)value=4294967040.0f;
            } else {
                uint32_t bits=((126u+seed%64u)<<23)|(seed&0x7fffffu)|(i&1u?0x80000000u:0);
                memcpy(&value,&bits,sizeof value);
            }
            inputs[i]=value;CHECK(reference(value)==candidate(value));++checked;
        }
        const float boundaries[]={0.0f,-0.0f,0.5f,-0.5f,2147483648.0f,4294967040.0f,4294967296.0f,4294967808.0f,-4294967296.0f,-9223372036854775808.0f};
        for(unsigned i=0;i<sizeof boundaries/sizeof *boundaries;++i){CHECK(reference(boundaries[i])==candidate(boundaries[i]));++checked;}
        uint64_t a,b;measure(reference,16,&a);measure(candidate,16,&b);CHECK(a==b);
        for(unsigned round=0;round<4;++round) {
            uint64_t first,second;
            if(round&1u){second=measure(candidate,512,&b);first=measure(reference,512,&a);}
            else {first=measure(reference,512,&a);second=measure(candidate,512,&b);}
            CHECK(a==b);before_us[kind]+=first;after_us[kind]+=second;vTaskDelay(pdMS_TO_TICKS(1));
        }
        printf("PHASE_CASE name=%s inputs=256 timed_calls_each=524288 reference_us=%" PRIu64 " candidate_us=%" PRIu64 " exact=1 alternating_order=1\n",names[kind],before_us[kind],after_us[kind]);fflush(stdout);
    }
    printf("RNBO_PHASE_BENCHMARK PASS firmware_elf_sha256=%s cases=3 exact_input_checks=%u timed_calls_each=1572864 positive_reference_us=%" PRIu64 " positive_candidate_us=%" PRIu64 " increment_reference_us=%" PRIu64 " increment_candidate_us=%" PRIu64 " mixed_reference_us=%" PRIu64 " mixed_candidate_us=%" PRIu64 " scope=native-firmware-indirect-function-microbenchmark integration_enabled=0\n",hash,checked,before_us[0],after_us[0],before_us[1],after_us[1],before_us[2],after_us[2]);fflush(stdout);vTaskDelete(NULL);
}
void app_main(void){CHECK(xTaskCreatePinnedToCore(run,"phase",6144,NULL,5,NULL,1)==pdPASS);}
