/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
/* Expected and input words are stereo interleaved IEEE binary32 bit patterns.
 * Policy is a provenance label, not a relaxed error limit. Every nonzero output
 * must match exactly; either zero sign is an explicitly counted diagnostic. */
typedef struct {
    const char *id;
    const char *sha;
    const char *reference_policy;
    const uint8_t *payload_start;
    const uint8_t *payload_end;
    uint32_t expected[512];
} smoke_case;
