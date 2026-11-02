/* SPDX-License-Identifier: MIT */
/* Private fixed-rate audio experiment. No production admission.
 * Only Float32 input, round-to-nearest/even, fixed44100 and 0..40ms use
 * the integer path. Other inputs retain the original double expression.
 * This is not a replacement for RNBO's shared MillisecondTime helper. */
#ifndef PRIVATE_EXACT_DELAY44100_H
#define PRIVATE_EXACT_DELAY44100_H
#include <stdint.h>
#include <float.h>
#include <limits.h>
#if UINT_MAX != UINT32_MAX
#error "Private experiment requires 32-bit unsigned int for __builtin_clz"
#endif
#ifdef __cplusplus
static_assert(sizeof(float) == 4, "binary32 storage width");
#else
_Static_assert(sizeof(float) == 4, "binary32 storage width");
#endif

#if FLT_RADIX != 2 || FLT_MANT_DIG != 24 || FLT_MAX_EXP != 128 || FLT_MIN_EXP != -125
#error "Private experiment requires IEEE binary32 float"
#endif

static inline uint32_t private_f32_bits(float value)
{
    uint32_t bits;
    __builtin_memcpy(&bits, &value, 4);
    return bits;
}

static inline float private_f32_from_bits(uint32_t bits)
{
    float value;
    __builtin_memcpy(&value, &bits, 4);
    return value;
}

/* Precondition: nonnegative input bits <= bits(40.f), including +0.
 * q + r/5 = M*441/5 = M*88 + M/5, with q < 2^31 and r in0..4.
 * No 64-bit product, division, shift, or floating arithmetic is needed. */
static inline uint32_t private_delay44100_positive_bits(uint32_t bits)
{
    uint32_t exponent = bits >> 23;
    uint32_t significand = bits & UINT32_C(0x007fffff);
    if (exponent) significand |= UINT32_C(0x00800000);
    if (!significand) return 0;
    uint32_t fifth = significand / 5u;
    uint32_t q = significand * 88u + fifth;
    uint32_t r = significand - fifth * 5u;

    if (!exponent && q < UINT32_C(0x01000000)) {
        /* Subnormal output: exact subnormal units = M*441/10.
         * q's low bit gives half, and r distinguishes greater-than-half. */
        uint32_t rounded = q >> 1;
        return rounded + ((q & 1u) && (r || (rounded & 1u)));
    }

    /* q>0, and this branch has floor(log2(q)) in24..30.
     * For normal inputs its narrower range is29..30. */
    unsigned shift = 8u - (unsigned)__builtin_clz(q); /* 1..7 */
    uint32_t rounded = q >> shift;
    uint32_t tail = q & ((UINT32_C(1) << shift) - 1u);
    uint32_t half = UINT32_C(1) << (shift - 1u);
    rounded += tail > half || (tail == half && (r || (rounded & 1u)));
    uint32_t effective_exponent = exponent ? exponent : 1u;
    /* rounded includes the hidden bit, including a carry into the next
     * binade. This addition packs that carry without a separate branch. */
    return ((effective_exponent + shift - 2u) << 23) + rounded;
}

static inline float private_delay44100_reference(float ms, float sample_rate)
{
    return (float)((double)ms * (double)sample_rate * 0.001);
}

static inline float private_delay44100(float ms, float sample_rate)
{
    uint32_t bits = private_f32_bits(ms);
    if (bits <= UINT32_C(0x42200000) && sample_rate == 44100.0f)
        return private_f32_from_bits(private_delay44100_positive_bits(bits));
    /* Negative values including -0, NaN/Inf, >40ms, and changed rates. */
    return private_delay44100_reference(ms, sample_rate);
}

/* Exact scope of the reviewed audio callsites: preserve their original
 * Double ternary cap on the fallback route, without a Double->Float32->
 * Double round trip. Raw duration is still consumed once per sample. */
static inline float private_delay44100_capped40(float raw_ms, float sample_rate)
{
    uint32_t bits = private_f32_bits(raw_ms);
    if (bits <= UINT32_C(0x42200000) && sample_rate == 44100.0f)
        return private_f32_from_bits(private_delay44100_positive_bits(bits));
    double promoted = (double)raw_ms;
    double capped = promoted > 40.0 ? 40.0 : promoted;
    return (float)(capped * (double)sample_rate * 0.001);
}
#endif
