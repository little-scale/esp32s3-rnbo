/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
enum { OBJECT_GEN_ARITH_KIND=8, OBJECT_GEN_ARITH_ABS=1, OBJECT_GEN_ARITH_MIN=2,
       OBJECT_GEN_ARITH_MAX=3, OBJECT_GEN_ARITH_SUB=4, OBJECT_GEN_ARITH_EQ=5,
       OBJECT_GEN_ARITH_LT=6, OBJECT_GEN_ARITH_SUM=9, OBJECT_GEN_ARITH_PRODUCT=10,
       OBJECT_GEN_ARITH_NEQ=11, OBJECT_GEN_ARITH_GT=12, OBJECT_GEN_ARITH_GTE=13,
       OBJECT_GEN_ARITH_LTE=14, OBJECT_GEN_ARITH_AND=15, OBJECT_GEN_ARITH_OR=16,
       OBJECT_GEN_ARITH_XOR=17, OBJECT_GEN_ARITH_NOT=18, OBJECT_GEN_ARITH_BOOL=19,
       OBJECT_GEN_ARITH_STEP=20, OBJECT_GEN_ARITH_SIGN=21, OBJECT_GEN_ARITH_SWITCH=22 };
/* Independent finite binary32 operation model; cache work is never timed DSP.
 * Reversed argument order on the two output planes; unary models treat each input.
 * Operation zero signs are diagnostics, not an undocumented selection rule. */
bool object_gen_arithmetic_model(uint32_t model);
bool object_gen_arithmetic_oracle_fill(uint32_t model,const float *input,
    uint32_t total_frames,uint32_t first_frame,uint32_t frames,
    float *output,uint32_t output_values);
