/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    uint32_t calls, resets, prepares, context_bytes;
    uint32_t histogram[257];
    uint64_t cycles, max_call_cycles;
    uint32_t numeric_mismatches, within_limit, bit_differences, zero_sign_differences, partition_differences;
    uint32_t first_numeric_word, first_actual, first_expected;
    uint32_t process_allocations, process_frees, event_allocations, event_frees;
    uint32_t guard_checks, unchanged_input_words;
    double maximum_error;
} gen_probe_result;
typedef void (*gen_probe_program)(unsigned stimulus,unsigned partition,uint32_t *capture,
                                const uint32_t *baseline,gen_probe_result *result);
void gen_partition_program_1(unsigned,unsigned,uint32_t*,const uint32_t*,gen_probe_result*);
void gen_partition_program_2(unsigned,unsigned,uint32_t*,const uint32_t*,gen_probe_result*);
void gen_partition_program_3(unsigned,unsigned,uint32_t*,const uint32_t*,gen_probe_result*);
void *gen_probe_allocate(size_t bytes);
void gen_probe_release(void *pointer);
uint32_t gen_probe_cycles(void);
uint64_t gen_probe_watch_begin(void);
void gen_probe_watch_end(uint64_t token,uint32_t *allocations,uint32_t *frees);
void gen_probe_fault(const char *reason);
void gen_probe_yield(void);
#ifdef __cplusplus
}
#endif
