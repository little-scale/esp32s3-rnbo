/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#define SPIKE_ABI 1u
#define SPIKE_FRAMES 256u
typedef struct {
    uint32_t struct_bytes, abi;
    int (*integer_callback)(int, int);
    float (*float_callback)(float);
    float *psram_state;
    uint32_t state_frames;
    volatile uint32_t *finalizer_observer;
} spike_host;
typedef struct {
    uint32_t struct_bytes, abi, constructor_count, startup_stage;
    uint32_t initialized_data;
    float readonly_constant;
    const float *readonly_data;
    const void *bss_address;
    int (*process)(const float *, float *, uint32_t);
    uint32_t (*run_count)(void);
} spike_module;
typedef struct {
    uint32_t struct_bytes;
    const spike_host *host;
    spike_module *module;
} spike_handshake;
