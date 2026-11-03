/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
enum { OBJECT_STIMULUS_MIDI=1,OBJECT_STIMULUS_FREQUENCY=2,OBJECT_STIMULUS_RESON=3,OBJECT_STIMULUS_IMPULSE_STEP=4,OBJECT_STIMULUS_MIXED_TONE=5,OBJECT_STIMULUS_NONLINEAR_GRID=6,
       OBJECT_STIMULUS_WRAP_BOUNDARIES=7,OBJECT_STIMULUS_WRAP_SAFE=8,OBJECT_STIMULUS_WRAP_STRATA=9,OBJECT_STIMULUS_WRAP_ZERO_ENDPOINTS=10,
       OBJECT_STIMULUS_NONLINEAR_DENSE=11,
       OBJECT_STIMULUS_WAVE4_GRID=12,OBJECT_STIMULUS_WAVE4_DENSE=13,OBJECT_STIMULUS_WAVE4_BOUNDARIES=14,OBJECT_STIMULUS_GEN_HISTORY=15 };
/* Fields retain catalog Float64 values during generation. Each final sample
 * rounds once to Float32, matching the authored host stimulus contract. */
typedef struct {
    uint32_t kind;
    double base,depth,rate,pilot_frequency,pilot_amplitude,excitation,level;
} object_stimulus;
/* Output is stereo interleaved Float32, zero-based rendered time n/44100 after
 * zero-input prepare warmup. No allocation, state or engine callbacks. */
bool object_stimulus_fill(const object_stimulus *,uint32_t first_frame,uint32_t frames,float *stereo);
