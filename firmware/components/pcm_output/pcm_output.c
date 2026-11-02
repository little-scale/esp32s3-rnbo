/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Gain-ramp behaviour extracted from little-scale/synthdefs-for-esp32-s3-touch-amoled-1.8,
 * 59e19441408a4df14cf2f5b6e8ba527929e74d9b, output_volume.c.
 * Changed to planar float input and explicit exact-vector validation. */
#include "pcm_output.h"
#include <math.h>
#include <stddef.h>

void pcm_output_init(pcm_output *s)
{
    if (s) *s = (pcm_output){.current=1.0f, .target=1.0f,
                            .ramp_samples=RNBO_S3_SAMPLE_RATE/50u};
}

static float finite_sample(pcm_output *s, float value)
{
    if (!isfinite(value)) { ++s->nonfinite; return 0.0f; }
    return value;
}

static int16_t quantize(pcm_output *s, float value)
{
    if (value > 1.0f) { ++s->clipped; value=1.0f; }
    else if (value < -1.0f) { ++s->clipped; value=-1.0f; }
    /* Symmetric scale keeps zero and unity deterministic. -32768 is unused. */
    return (int16_t)lrintf(value*32767.0f);
}

int pcm_output_render(pcm_output *s, const float *left, const float *right,
                      int16_t *output, uint32_t frames, uint32_t channels,
                      uint32_t percent, float headroom, int mute)
{
    if (!s || !left || !right || !output || frames!=RNBO_S3_BLOCK_FRAMES ||
        (channels!=1 && channels!=2) || !isfinite(headroom) || headroom<0.0f || headroom>1.0f)
        return 0;
    if (percent>100) percent=100;
    float target=(float)percent*0.01f;
    if (target!=s->target) {
        s->target=target;
        s->remaining=s->ramp_samples ? s->ramp_samples : 1;
        s->step=(target-s->current)/(float)s->remaining;
    }
    for (uint32_t i=0; i<frames; ++i) {
        if (s->remaining) {
            s->current+=s->step;
            if (!--s->remaining) s->current=s->target;
        }
        float a=finite_sample(s,left[i]);
        float b=finite_sample(s,right[i]);
        float gain=mute ? 0.0f : headroom*s->current;
        if (channels==1) output[i]=quantize(s,(a*0.5f+b*0.5f)*gain);
        else {
            output[i*2]=quantize(s,a*gain);
            output[i*2+1]=quantize(s,b*gain);
        }
    }
    return 1;
}
