/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_PHASE_TRUNC_H
#define RNBO_S3_PHASE_TRUNC_H
#include <stdint.h>

/* Experimental exact conversion candidate; not enabled in generated DSP yet.
 * Matches RNBO's float -> int64_t -> uint32_t conversion for finite inputs
 * whose truncated value fits int64_t. NaN, infinity and out-of-range inputs
 * retain the upstream undefined conversion domain and are not qualified.
 * UINT32_MAX is not a safe floating upper bound: it rounds to 2^32.
 * On the pinned Xtensa compiler the accepted path uses hardware utrunc.s.
 */
static inline uint32_t rnbo_s3_phase_trunc_f32(float value)
{
    if (value>=0.0f && value<4294967296.0f)
        return (uint32_t)value;
    return (uint32_t)(int64_t)value;
}
#endif
