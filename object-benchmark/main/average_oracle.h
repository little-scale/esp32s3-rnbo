/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
/* Recompute each causal window in Float64 from immutable Float32 stereo input.
 * Missing prepared history contains zeros. Results round once into a Float32
 * cache. This is not the generated running accumulator or a claim of fsum bits. */
bool object_average_oracle_fill(const float *input,uint32_t total_frames,
    uint32_t first_frame,uint32_t frames,uint32_t window,uint32_t initial_available,
    float *output,double *maximum_cache_rounding_error);
