/* SPDX-License-Identifier: MIT */
#ifndef RNBO_OBJECT_GEN_HISTORY_ORACLE_H
#define RNBO_OBJECT_GEN_HISTORY_ORACLE_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { OBJECT_GEN_HISTORY_KIND=7, OBJECT_GEN_HISTORY_FEEDBACK=1, OBJECT_GEN_HISTORY_SWAP=2,
       OBJECT_GEN_HISTORY_ROTATE=3, OBJECT_GEN_HISTORY_MAX_FRAMES=16384 };
typedef struct {
    uint32_t magic, model, next_frame;
    int64_t epoch; /* −1024 initially, actual capture-frame index after reset */
} object_gen_history_oracle;
bool object_gen_history_oracle_init(object_gen_history_oracle *,uint32_t model,uint32_t warmup_blocks);
/* Reset at the current cursor on a256-frame boundary. Repeated commands at
 * the same cursor are legal; no scheduling/dispatch claim is made here. */
bool object_gen_history_oracle_reset(object_gen_history_oracle *,uint32_t first_frame);
/* Before reset: compare independently predicted first cachedFloat32 pairs
 * with/without this reset (all prior resets retained). True only for maximum
 * pair separation>8e-6. Does not mutate state; this is not a dispatch proof. */
bool object_gen_history_oracle_reset_witness(const object_gen_history_oracle *,
    const float *input,uint32_t total_frames,uint32_t first_frame,bool *observable);
/* Input points to the full interleaved2*total cache; output to this chunk.
 * Contiguous cursor required. Actual dyadic stimulus words are validated.
 * Cache construction is offline, allocation-free, never a timed DSP callback. */
bool object_gen_history_oracle_fill(object_gen_history_oracle *,const float *input,
    uint32_t total_frames,uint32_t first_frame,uint32_t frames,float *output,
    uint32_t output_values,double *maximum_cache_rounding);
double object_gen_history_oracle_tail_bound(uint32_t model);
double object_gen_history_oracle_evaluation_bound(uint32_t model);
#ifdef __cplusplus
}
#endif
#endif
