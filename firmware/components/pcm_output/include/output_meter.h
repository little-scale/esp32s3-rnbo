/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stddef.h>

/* Read-only measurement of the final interleaved PCM buffer, after gain,
 * mono/stereo routing, finite handling, clipping and quantization. */
static inline uint32_t output_meter_peak_q15(const int16_t *pcm,size_t samples)
{
    uint32_t peak=0;
    if (!pcm) return 0;
    for (size_t i=0;i<samples;++i) {
        int32_t value=pcm[i];
        uint32_t magnitude=(uint32_t)(value<0?-value:value);
        if (magnitude>peak) peak=magnitude;
    }
    return peak;
}
