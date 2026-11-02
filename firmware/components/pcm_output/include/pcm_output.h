/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define RNBO_S3_SAMPLE_RATE 44100u
#define RNBO_S3_BLOCK_FRAMES 256u
typedef struct {
    float current, target, step;
    uint32_t remaining, ramp_samples;
    uint64_t nonfinite, clipped;
} pcm_output;
/* Engine-neutral extraction of the SynthDef output gain ramp. Initial unity
 * volume; a 20ms ramp applies subsequent volume changes. No allocation. */
void pcm_output_init(pcm_output *state);
/* One exact 256-frame planar stereo block. channels must be 1 or 2; mono is
 * 0.5*(left+right). headroom is a fixed sink gain, separate from 0..100 volume.
 * mute is an immediate latch supplied by the shell and overrides the ramp.
 * Returns 0 on invalid arguments, with no write to the output buffer. */
int pcm_output_render(pcm_output *state, const float *left, const float *right,
                      int16_t *output, uint32_t frames, uint32_t channels,
                      uint32_t volume_percent, float headroom, int mute);
#ifdef __cplusplus
}
#endif
