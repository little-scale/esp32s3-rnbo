/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_elf.h"
#include "rnbo_s3_dynamic.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PLAYER_MAX_PARAMETERS 32u
#define PLAYER_MAX_ELF_BYTES (512u * 1024u)
#define PLAYER_MAX_ARENA_BYTES (4u * 1024u * 1024u)

/* Zero-initialize before first use. This is an exclusive, maintenance-owner
 * object: load/unload/statistics must never race any callback or DMA owner.
 * Loaded native code is trusted, not sandboxed or authenticated. Do not copy a
 * live player_image: the module retains &finalized until after its finalizers.
 */
typedef struct {
    esp_elf_t elf;
    rnbo_s3_module module;
    rnbo_s3_dynamic_info info;
    void *state, *context;
    uint32_t state_bytes, arena_bytes, parameter_count;
    volatile uint32_t finalized;
    uint64_t position;
    /* Actual mapped section sizes, not an allocation high-water claim. */
    uint32_t text_bytes, data_bytes;
    uintptr_t executable_base;
    rnbo_s3_stats stats;
    rnbo_s3_dynamic_stats dynamic_stats;
    bool initialized, loaded, callbacks_admitted;
} player_image;

/* Require an empty image; a failure cleans it back to empty and writes a
 * bounded diagnostic if error/error_bytes allow it. ELF bytes are needed only
 * during this call, may be unaligned, and must not mutate during the call.
 * No payload pointer is retained. This player admits Main only: 0 inputs and
 * 2 outputs. Effects belong inside that authored Main graph.
 * Normal success performs DESCRIBE/BIND/create/prepare, warmup=4, fixed seed,
 * validates parameter schema/readbacks and clean initial resource statistics.
 * Host memory/loader/returned callback failures are recoverable. An unchecked
 * allocation failure inside trusted native code can still trap; the arena must
 * be sufficient for the graph, not merely its structural descriptor minimum.
 */
esp_err_t player_image_load(player_image *, const uint8_t *payload, size_t bytes,
                            uint32_t role, uint32_t arena_bytes,
                            char *error, size_t error_bytes);

/* Safe on empty or partially loaded images. Context destroy precedes module
 * finalizers/unmapping; shell-owned state is freed last. Never call from audio.
 */
void player_image_unload(player_image *);

/* Refresh the public stats snapshots and check health, arena and position.
 * Audio owner advances image.position only after a successful process block.
 */
esp_err_t player_image_statistics(player_image *, char *error, size_t error_bytes);

#ifdef __cplusplus
}
#endif
