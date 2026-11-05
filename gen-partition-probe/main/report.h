/* SPDX-License-Identifier: MIT */
#pragma once
#include "probe_api.h"
#include "gen_plan.h"
#include <cstdio>
#include <cstring>
#include <inttypes.h>
inline void gen_probe_print(unsigned model,unsigned stimulus,unsigned repeat,unsigned nominal,
                            const gen_probe_result&r,const char *capture_sha){
    uint64_t error_bits;std::memcpy(&error_bits,&r.maximum_error,8);
    const bool pass=r.numeric_mismatches==0&&r.partition_differences==0;
    std::printf("RNBO_SMOKE CASE id=%s-%s-r%u-p%u model=%u stimulus=%s repeat=%u nominal=%u status=%s samples=8192 partition_compared_words=%u partition_bit_differences=%u calls=%u cycles=%" PRIu64 " max_call_cycles=%" PRIu64 " resets=%u prepares=%u context_bytes=%u numeric_mismatches=%u within_tolerance_differences=%u bit_differences=%u zero_sign_differences=%u max_error_bits=%016" PRIx64 " first_numeric_word=%u first_actual=%08x first_expected=%08x process_allocations=%u process_frees=%u event_allocations=%u event_frees=%u guard_checks=%u unchanged_input_words=%u capture_sha256=%s histogram=",
      gen_probe_names[model-1],gen_probe_stimuli[stimulus],repeat,nominal,model,gen_probe_stimuli[stimulus],repeat,nominal,pass?"pass":"output_mismatch",repeat?8192:0,unsigned(r.partition_differences),unsigned(r.calls),r.cycles,r.max_call_cycles,unsigned(r.resets),unsigned(r.prepares),unsigned(r.context_bytes),unsigned(r.numeric_mismatches),unsigned(r.within_limit),unsigned(r.bit_differences),unsigned(r.zero_sign_differences),error_bits,unsigned(r.first_numeric_word),unsigned(r.first_actual),unsigned(r.first_expected),unsigned(r.process_allocations),unsigned(r.process_frees),unsigned(r.event_allocations),unsigned(r.event_frees),unsigned(r.guard_checks),unsigned(r.unchanged_input_words),capture_sha);
    bool first=true;for(unsigned n=1;n<=256;++n)if(r.histogram[n]){std::printf("%s%u:%u",first?"":",",n,unsigned(r.histogram[n]));first=false;}
    std::printf("\n");std::fflush(stdout);
}
