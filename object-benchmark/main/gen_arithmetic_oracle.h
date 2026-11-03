/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
enum { OBJECT_GEN_ARITH_KIND=8, OBJECT_GEN_ARITH_ABS=1, OBJECT_GEN_ARITH_MIN=2,
       OBJECT_GEN_ARITH_MAX=3, OBJECT_GEN_ARITH_SUB=4, OBJECT_GEN_ARITH_EQ=5,
       OBJECT_GEN_ARITH_LT=6, OBJECT_GEN_ARITH_SUM=9, OBJECT_GEN_ARITH_PRODUCT=10 };
/* Independent finite binary32 operation model; cache work is never timed DSP.
 * Symmetric argument order on the two output planes; abs treats each input.
 * Operation zero signs are diagnostics, not an undocumented selection rule. */
bool object_gen_arithmetic_model(uint32_t model);
bool object_gen_arithmetic_oracle_fill(uint32_t model,const float *input,
    uint32_t total_frames,uint32_t first_frame,uint32_t frames,
    float *output,uint32_t output_values);
