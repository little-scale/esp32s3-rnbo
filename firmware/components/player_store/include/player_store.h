// SPDX-License-Identifier: MIT
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct cJSON cJSON;

enum {
    PLAYER_ROLE_MAIN = 1,
    PLAYER_PACKAGE_HEADER_BYTES = 128,
    PLAYER_PACKAGE_MAX_METADATA_BYTES = 65536,
    PLAYER_PACKAGE_MAX_ELF_BYTES = 524288,
    PLAYER_PACKAGE_MAX_BYTES = 128 + 65536 + 524288,
};

/* payload/metadata/elf borrow the caller's immutable buffer. metadata is NOT
 * NUL-terminated. metadata_json owns its cJSON tree; visual borrows a child
 * which may be invalid for display (the UI must fall back, not reject DSP).
 * Keep payload alive until player_package_clear(), which frees only the JSON
 * tree. Clear a previously parsed package before parsing into it again. */
typedef struct {
    const uint8_t *payload;
    size_t payload_bytes;
    const uint8_t *metadata;
    size_t metadata_bytes;
    const uint8_t *elf;
    size_t elf_bytes;
    uint32_t role;
    uint32_t arena_bytes;
    uint32_t initial_volume;
    char name[64];
    char source_sha256[65];
    char package_sha256[65];
    cJSON *metadata_json;
    const cJSON *visual;
} player_package;

/* Package envelope/hash/JSON validation; the runtime must separately admit the
 * ELF and prepare its image before committing storage. This is not a loader. */
bool player_package_parse(const uint8_t *bytes, size_t length,
                          player_package *package, char *error, size_t error_capacity);
void player_package_clear(player_package *package);

/* Single control/storage owner only. Call while audio DMA is parked. These
 * functions never acquire audio ownership or erase NVS. A failed SPIFFS mount
 * may format only after every byte of the storage partition is proven 0xff.
 * Only PLAYER_ROLE_MAIN is accepted; FX stays inside that authored patch. */
bool player_store_init(char *error, size_t error_capacity);
bool player_store_stage(uint32_t role, const uint8_t *bytes, size_t length,
                        uint8_t *slot, char *error, size_t error_capacity);
bool player_store_commit(uint32_t role, uint8_t slot, const char *package_sha256,
                         char *error, size_t error_capacity);
/* After admitting/preparing the previous boot package, promote its EXISTING
 * checked file by selector only. No SPIFFS write/truncate/sync is performed. */
bool player_store_promote_previous(uint32_t role, const char *package_sha256,
                                   char *error, size_t error_capacity);

/* Read selected or previous and revalidate all hashes. On success, caller owns
 * a PSRAM allocation and must call player_store_free(). Failure returns NULL/0.
 * Boot may explicitly try previous=true after selected admission fails. */
bool player_store_read(uint32_t role, bool previous, uint8_t **bytes, size_t *length,
                       char *error, size_t error_capacity);
void player_store_free(void *bytes);

#ifdef __cplusplus
}
#endif
