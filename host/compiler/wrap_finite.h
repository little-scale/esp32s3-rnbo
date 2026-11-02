/* SPDX-License-Identifier: MIT */
/* Private finite-input experiment. Nonfinite policy is deliberately separate. */
#ifndef PRIVATE_FINITE_WRAP_H
#define PRIVATE_FINITE_WRAP_H
#include <stdint.h>
#include <float.h>
#include <math.h>
#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128
#error "Private experiment requires binary32"
#endif
static inline uint32_t private_wrap_bits(float value)
{uint32_t result;__builtin_memcpy(&result,&value,4);return result;}
static inline float private_wrap_float(uint32_t bits)
{float result;__builtin_memcpy(&result,&bits,4);return result;}

/* Threshold is a positive binary32 magnitude. False leaves output untouched.
 * This is a research comparator, not a newly admitted generic wrap API. */
static inline bool private_wrap_fmod_large(float value,float *output,uint32_t threshold)
{
    uint32_t magnitude=private_wrap_bits(value)&UINT32_C(0x7fffffff);
    if(magnitude<threshold||magnitude>=UINT32_C(0x7f800000))return false;
    float remainder=fmodf(value,2.0f);
    if(remainder>=1.0f)remainder-=2.0f;
    else if(remainder< -1.0f)remainder+=2.0f;
    /* Original exact even-integer cancellation yields +0. The in-range
     * branch retains input -0 before either large-input guard is reached. */
    *output=remainder==0.0f?0.0f:remainder;return true;
}
static inline bool private_wrap_even_large(float value,float *output)
{
    uint32_t magnitude=private_wrap_bits(value)&UINT32_C(0x7fffffff);
    if(magnitude<UINT32_C(0x4b800000)||magnitude>=UINT32_C(0x7f800000))return false;
    /* Every finite binary32 |value|>=2^24 is a multiple of two. */
    *output=0.0f;return true;
}
#endif
