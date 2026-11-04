/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
typedef struct {
    const char *id;
    float minimum,maximum,initial,exponent;
    uint32_t steps;
} smoke_parameter_contract;
typedef struct {
    uint32_t before_call,parameter_slot,value_word;
} smoke_parameter_action;
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
    uint32_t arena_bytes; /* Zero selects the legacy four-KiB arena. */
    uint32_t expected[512];
    uint32_t expected_parameter_count; /* Zero preserves the legacy p0 case. */
    const smoke_parameter_contract *parameters;
    uint32_t parameter_event_count;
    const smoke_parameter_action *parameter_events;
    const uint32_t *const *expected_block_refs; /* Optional twenty shared 512-word blocks; preferred over flat storage. */
    uint32_t strict_zero_sign_channels; /* Bits0/1 require exact zero signs on the corresponding output lane. */
} smoke_case;
