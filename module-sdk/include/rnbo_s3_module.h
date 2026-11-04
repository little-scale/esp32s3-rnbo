/* SPDX-License-Identifier: MIT */
#ifndef RNBO_S3_MODULE_H
#define RNBO_S3_MODULE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* In-memory C ABI, never a wire/file layout. ABI major must match; callers
 * check struct_bytes before reading any fields added in a minor version. */
#define RNBO_S3_ABI_MAJOR 1u
#define RNBO_S3_ABI_MINOR 0u
#define RNBO_S3_SAMPLE_RATE 44100u
#define RNBO_S3_BLOCK_FRAMES 256u
#define RNBO_S3_MAX_PARAMETERS 128u
enum { RNBO_S3_MAIN = 1, RNBO_S3_FX = 2 };
enum { RNBO_S3_OK = 0, RNBO_S3_INVALID = -1, RNBO_S3_BUSY = -2,
       RNBO_S3_NO_MEMORY = -3, RNBO_S3_FAULT = -4, RNBO_S3_UNSUPPORTED = -5 };
enum { RNBO_S3_SINGLE_INSTANCE = 1u, RNBO_S3_BOUNDARY_EVENTS = 2u,
       RNBO_S3_PLATFORM_ALLOCATIONS_ONLY = 4u, RNBO_S3_DISCARDS_MIDI_OUTPUT = 8u,
       RNBO_S3_SHORT_MIDI_INPUT = 16u }; /* port0 + channel/system short messages */
enum { RNBO_S3_PARAMETER_ACTUAL = 1, RNBO_S3_PARAMETER_NORMALIZED = 2,
       RNBO_S3_MIDI = 3 };

typedef struct {
    uint32_t struct_bytes;
    uint32_t arena_bytes;
    uint32_t warmup_blocks; /* detached blocks; advance patch state before sample_position 0 */
    uint32_t seed; /* deterministic; caller supplies entropy for fresh instances */
} rnbo_s3_create_options;

typedef struct {
    uint32_t struct_bytes;
    uint32_t kind;
    uint32_t parameter_index; /* revision-specific; resolve stable ID first */
    float value;
    uint32_t midi_port;
    uint32_t midi_length;
    uint8_t midi[3]; /* complete short messages; system statuses require capability flag */
    uint8_t reserved;
} rnbo_s3_event;

typedef struct {
    uint32_t struct_bytes;
    uint32_t index;
    char id[192];
    char name[96];
    char unit[32];
    float minimum, maximum, initial, exponent;
    uint32_t steps;
} rnbo_s3_parameter_info;

typedef struct {
    uint32_t struct_bytes;
    uint32_t arena_capacity, arena_used;
    uint64_t platform_allocations, late_platform_allocations;
    uint64_t errors, invalid_samples, blocks, sample_position;
    uint32_t warmup_blocks;
    uint32_t faulted;
} rnbo_s3_stats;

typedef struct rnbo_s3_module {
    uint32_t struct_bytes, abi_major, abi_minor, pointer_bits;
    uint32_t sample_rate, block_frames, role, audio_inputs, audio_outputs;
    uint32_t max_parameters, flags;
    int (*create)(const rnbo_s3_create_options *, void **context);
    int (*prepare)(void *context); /* once per context; destroy after any failure */
    int (*process)(void *context, const float *const *inputs,
                   float *const *outputs, uint32_t frames, uint64_t sample_position);
    int (*event)(void *context, const rnbo_s3_event *);
    int (*panic)(void *context); /* latch silent; detached reconstruction resumes */
    uint32_t (*parameter_count)(void *context);
    int (*parameter_info)(void *, uint32_t, rnbo_s3_parameter_info *);
    int (*parameter_value)(void *, uint32_t, float *actual, float *normalized);
    int (*parameter_convert)(void *, uint32_t, float value, uint32_t normalized_to_actual, float *result);
    int (*statistics)(void *, rnbo_s3_stats *);
    void (*destroy)(void *context);
} rnbo_s3_module;

/* Static bring-up only: one generated image, one active context per program.
 * All callbacks require exclusive ownership. No callback is thread safe.
 * Buffer arrays contain exactly two channel pointers; each nonnull pointer
 * addresses at least block_frames floats. Callers own their storage lifetime.
 * Pass disjoint input/output channel storage; in-place processing is unqualified.
 * String fields are copied, NUL-terminated UTF-8 from the admitted export.
 * PLATFORM_ALLOCATIONS_ONLY counts RNBO platform hooks, not raw C++ new.
 * Dynamic loader handshake/ABI admission is a separate unqualified milestone. */
const rnbo_s3_module *rnbo_s3_static_module(void);
#ifdef __cplusplus
}
#endif
#endif
