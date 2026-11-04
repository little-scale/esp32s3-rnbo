/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
/* Expected and input words are stereo interleaved IEEE binary32 bit patterns.
 * Zero tolerance requires exact nonzero words. Approximation tolerances and
 * per-case input vectors are declared before execution, outside DSP timing. */
typedef struct {
    const char *id;
    const char *sha;
    const char *reference_policy;
    const uint8_t *payload_start;
    const uint8_t *payload_end;
    const uint32_t *input_words; /* NULL selects the legacy common vector. */
    float absolute_tolerance;
    const uint32_t *expected_blocks; /* Optional twenty-block continuous stream. */
    uint32_t expected[512];
} smoke_case;
