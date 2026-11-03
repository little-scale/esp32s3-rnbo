/* SPDX-License-Identifier: MIT */
#ifndef RNBO_OBJECT_WAVE4_ORACLE_H
#define RNBO_OBJECT_WAVE4_ORACLE_H
#include <stdbool.h>
#include <stdint.h>
enum { OBJECT_WAVE4_KIND=6, OBJECT_WAVE4_ABSOLUTE=1, OBJECT_WAVE4_MINIMUM,
    OBJECT_WAVE4_MAXIMUM, OBJECT_WAVE4_SUBTRACT, OBJECT_WAVE4_EQUAL,
    OBJECT_WAVE4_LESS, OBJECT_WAVE4_SUM_DIFFERENCE, OBJECT_WAVE4_DELTA };
typedef struct { uint32_t magic,model,next_frame; float previous; } object_wave4_oracle;
/* Independent mathematical binary32 outputs, not a generated DSP kernel.
 * Four zero-input warmup blocks leave previous input at +0. Cache history
 * must continue across chunks. Inputs must be finite binary32 in [-1,1]. */
bool object_wave4_oracle_init(object_wave4_oracle *,uint32_t model,uint32_t warmup);
bool object_wave4_oracle_fill(object_wave4_oracle *,const float *input,uint32_t total_frames,
    uint32_t first_frame,uint32_t frames,float *output,uint32_t output_values);
#endif
