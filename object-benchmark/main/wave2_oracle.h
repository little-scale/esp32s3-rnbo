/* SPDX-License-Identifier: MIT */
/* Independent offline Float64 models; no generated DSP implementation. */
#ifndef RNBO_OBJECT_WAVE2_ORACLE_H
#define RNBO_OBJECT_WAVE2_ORACLE_H
#include <stdbool.h>
#include <stdint.h>

enum { OBJECT_WAVE2_BIQUAD=2, OBJECT_WAVE2_NONLINEAR=3 };
enum { OBJECT_WAVE2_MAX_FRAMES=1024*256 };
typedef struct {
    uint32_t magic,kind,case_index,next_frame;
    double coefficients[5]; /* a0,a1,a2,b1,b2; or exponent in element0 */
    double x1[2],x2[2],y1[2],y2[2];
} object_wave2_oracle;

/* Accept only the three authored biquad coefficient vectors or nonlinear
 * exponents2/.25/4. Coefficients retain catalog Float64 values. Other fields
 * must be zero. Four zero-input warmup blocks leave fresh history at zero. */
bool object_wave2_oracle_init(object_wave2_oracle *state,uint32_t kind,
    const double coefficients[5],double exponent,uint32_t warmup_blocks);
/* One independent Float64 model step, available for native model tests.
 * The model state is Float64; no generated Float32 accumulator is copied. */
bool object_wave2_oracle_step(object_wave2_oracle *state,const float input[2],double truth[2]);
/* Fill a contiguous Float32 oracle-cache chunk outside timed callbacks.
 * first_frame must equal state.next_frame. max_rounding accumulates the
 * absolute model->cache rounding error. Actual input is interleaved Float32;
 * input/cache are separate valid caller-owned buffers. No heap operations. */
bool object_wave2_oracle_fill(object_wave2_oracle *state,const float *input,uint32_t total_frames,
                       uint32_t first_frame,uint32_t frames,float *output,
                       uint32_t output_values,double *maximum_cache_rounding);
bool object_wave2_biquad_dc_gain(const object_wave2_oracle *state,double *gain);
#endif
