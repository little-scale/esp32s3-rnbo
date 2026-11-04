// SPDX-License-Identifier: MIT
#include "player_store.h"

#include "cJSON.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_partition.h"
#include "esp_spiffs.h"
#include "mbedtls/sha256.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef PLAYER_STORE_PATH
#define PLAYER_STORE_PATH "/player"
#endif

#define SELECTOR_BYTES 72u
#define NO_PREVIOUS 255u

typedef struct {
    bool present;
    uint8_t raw[SELECTOR_BYTES];
} selection;

typedef struct {
    bool valid;
    uint8_t slot;
    uint8_t sha[32];
    selection base;
} staging;

static bool initialized;
static staging staged;

static bool fail(char *error, size_t capacity, const char *text) {
    if (error && capacity) snprintf(error, capacity, "%s", text);
    return false;
}

static void clear_error(char *error, size_t capacity) {
    if (error && capacity) error[0] = '\0';
}

static uint32_t read_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static bool hash_bytes(const uint8_t *bytes, size_t length, uint8_t out[32]) {
    return mbedtls_sha256(bytes, length, out, 0) == 0;
}

static void hex_sha(const uint8_t digest[32], char out[65]) {
    static const char digits[] = "0123456789abcdef";
    for (unsigned i = 0; i < 32; ++i) {
        out[2 * i] = digits[digest[i] >> 4];
        out[2 * i + 1] = digits[digest[i] & 15];
    }
    out[64] = '\0';
}

static bool parse_sha(const char *text, uint8_t digest[32]) {
    if (!text) return false;
    for (unsigned i = 0; i < 64; ++i) {
        unsigned char c = (unsigned char)text[i];
        unsigned value;
        if (c >= '0' && c <= '9') value = c - '0';
        else if (c >= 'a' && c <= 'f') value = c - 'a' + 10;
        else return false;
        if ((i & 1u) == 0) digest[i / 2] = (uint8_t)(value << 4);
        else digest[i / 2] |= (uint8_t)value;
    }
    return text[64] == '\0';
}

/* Reject malformed/overlong UTF-8, surrogate encodings and embedded NUL. */
static bool valid_utf8(const uint8_t *text, size_t length) {
    for (size_t i = 0; i < length;) {
        uint32_t c = text[i++];
        if (c == 0) return false;
        if (c < 0x80) continue;
        unsigned extra;
        uint32_t minimum;
        if (c >= 0xc2 && c <= 0xdf) { extra = 1; minimum = 0x80; c &= 0x1f; }
        else if (c >= 0xe0 && c <= 0xef) { extra = 2; minimum = 0x800; c &= 0x0f; }
        else if (c >= 0xf0 && c <= 0xf4) { extra = 3; minimum = 0x10000; c &= 7; }
        else return false;
        if (length - i < extra) return false;
        for (unsigned j = 0; j < extra; ++j) {
            uint8_t next = text[i++];
            if ((next & 0xc0) != 0x80) return false;
            c = (c << 6) | (next & 0x3f);
        }
        if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return false;
    }
    return true;
}

/* cJSON strings are C strings, so an escaped NUL would hide a suffix. */
static bool bounded_json_text(const uint8_t *text, size_t length) {
    bool string = false;
    unsigned depth = 0;
    for (size_t i = 0; i < length; ++i) {
        if (text[i] == '"') string = !string;
        else if (string && text[i] == '\\' && i + 1 < length) {
            ++i;
            if (text[i] == 'u' && length - i > 4 &&
                memcmp(text + i + 1, "0000", 4) == 0) return false;
        } else if (!string && (text[i] == '{' || text[i] == '[')) {
            if (++depth > 32) return false;
        } else if (!string && (text[i] == '}' || text[i] == ']')) {
            if (!depth) return false;
            --depth;
        }
    }
    return !string && depth == 0;
}

void player_package_clear(player_package *package) {
    if (!package) return;
    cJSON_Delete(package->metadata_json);
    memset(package, 0, sizeof(*package));
}

bool player_package_parse(const uint8_t *bytes, size_t length, player_package *package,
                          char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    if (!package) return fail(error, error_capacity, "Missing package output");
    memset(package, 0, sizeof(*package));
    if (!bytes || length < PLAYER_PACKAGE_HEADER_BYTES || length > PLAYER_PACKAGE_MAX_BYTES)
        return fail(error, error_capacity, "Package size is outside its bounds");
    if (memcmp(bytes, "RNBOS3P1", 8) != 0 || read_u32(bytes + 8) != 128 ||
        (read_u32(bytes + 12) != 1 && read_u32(bytes + 12) != 2) || read_u32(bytes + 16) != 1)
        return fail(error, error_capacity, "Unsupported package header or ABI");
    uint32_t role = read_u32(bytes + 20), rate = read_u32(bytes + 24);
    uint32_t block = read_u32(bytes + 28), arena = read_u32(bytes + 32);
    uint32_t metadata_length = read_u32(bytes + 36), elf_length = read_u32(bytes + 40);
    if (role != PLAYER_ROLE_MAIN || rate != 44100 || block != 256 ||
        arena < 4096 || arena > 4194304)
        return fail(error, error_capacity, "Invalid role, audio format or arena budget");
    for (unsigned i = 108; i < 128; ++i)
        if (bytes[i] != 0) return fail(error, error_capacity, "Reserved header bytes must be zero");
    if (metadata_length == 0 || metadata_length > PLAYER_PACKAGE_MAX_METADATA_BYTES ||
        elf_length < 16 || elf_length > PLAYER_PACKAGE_MAX_ELF_BYTES ||
        (size_t)128 + metadata_length + elf_length != length)
        return fail(error, error_capacity, "Package payload lengths do not match");
    const uint8_t *metadata = bytes + 128, *elf = metadata + metadata_length;
    uint8_t digest[32];
    if (!hash_bytes(elf, elf_length, digest) || memcmp(digest, bytes + 44, 32) != 0)
        return fail(error, error_capacity, "ELF checksum does not match");
    if (!hash_bytes(metadata, metadata_length, digest) || memcmp(digest, bytes + 76, 32) != 0)
        return fail(error, error_capacity, "Metadata checksum does not match");
    if (memcmp(elf, "\177ELF\001\001\001", 7) != 0)
        return fail(error, error_capacity, "Expected a little-endian 32-bit ELF");
    if (!valid_utf8(metadata, metadata_length) || !bounded_json_text(metadata, metadata_length))
        return fail(error, error_capacity, "Metadata must be bounded UTF-8 JSON without embedded NUL");
    const char *end = NULL;
    cJSON *json = cJSON_ParseWithLengthOpts((const char *)metadata, metadata_length, &end, false);
    if (json && end) {
        const char *limit = (const char *)metadata + metadata_length;
        while (end < limit && (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n')) ++end;
        if (end != limit) { cJSON_Delete(json); json = NULL; }
    }
    if (!cJSON_IsObject(json)) {
        cJSON_Delete(json);
        return fail(error, error_capacity, "Metadata must be one JSON object");
    }
    cJSON *name = NULL, *source = NULL, *volume = NULL, *visual = NULL;
    bool duplicate = false, ambiguous_visual = false;
    for (cJSON *item = json->child; item; item = item->next) {
        cJSON **field = NULL;
        if (strcmp(item->string, "name") == 0) field = &name;
        else if (strcmp(item->string, "source_sha256") == 0) field = &source;
        else if (strcmp(item->string, "initial_volume") == 0) field = &volume;
        else if (strcmp(item->string, "visual") == 0) field = &visual;
        if (field) {
            if (*field) {
                if (field == &visual) ambiguous_visual = true;
                else duplicate = true;
            } else *field = item;
        }
    }
    if (ambiguous_visual) visual = NULL;
    unsigned inputs_count = 0;
    for (const cJSON *item = json->child; item; item = item->next)
        if (strcmp(item->string, "physical_inputs") == 0) ++inputs_count;
    if ((read_u32(bytes + 12) == 2 ? inputs_count != 1 : inputs_count != 0)) {
        cJSON_Delete(json);
        return fail(error, error_capacity, "Physical inputs require envelope v2; ordinary packages require v1");
    }
    size_t name_length = cJSON_IsString(name) ? strlen(name->valuestring) : 0;
    if (duplicate || name_length < 1 || name_length > 63 ||
        !valid_utf8((const uint8_t *)name->valuestring, name_length) ||
        !cJSON_IsString(source) || !parse_sha(source->valuestring, digest) ||
        !cJSON_IsNumber(volume) || !isfinite(volume->valuedouble) ||
        volume->valuedouble < 0 || volume->valuedouble > 100 ||
        floor(volume->valuedouble) != volume->valuedouble) {
        cJSON_Delete(json);
        return fail(error, error_capacity, "Invalid required metadata");
    }
    if (!hash_bytes(bytes, length, digest)) {
        cJSON_Delete(json);
        return fail(error, error_capacity, "Could not hash the complete package");
    }
    package->payload = bytes; package->payload_bytes = length;
    package->metadata = metadata; package->metadata_bytes = metadata_length;
    package->elf = elf; package->elf_bytes = elf_length;
    package->role = role; package->arena_bytes = arena;
    package->initial_volume = (uint32_t)volume->valuedouble;
    memcpy(package->name, name->valuestring, name_length + 1);
    memcpy(package->source_sha256, source->valuestring, 65);
    hex_sha(digest, package->package_sha256);
    package->metadata_json = json; package->visual = visual;
    return true;
}

static const char *role_key(uint32_t role) {
    return role == PLAYER_ROLE_MAIN ? "main" : NULL;
}

static const char *slot_path(uint32_t role, uint8_t slot) {
    static const char *paths[2] = {PLAYER_STORE_PATH "/main0.pkg", PLAYER_STORE_PATH "/main1.pkg"};
    return role_key(role) && slot < 2 ? paths[slot] : NULL;
}

static bool load_selection(uint32_t role, selection *out, char *error, size_t capacity) {
    memset(out, 0, sizeof(*out));
    nvs_handle_t handle;
    esp_err_t result = nvs_open("rnbo_player", NVS_READONLY, &handle);
    if (result == ESP_ERR_NVS_NOT_FOUND) return true;
    if (result != ESP_OK) return fail(error, capacity, "Could not open package selectors");
    size_t length = sizeof(out->raw);
    result = nvs_get_blob(handle, role_key(role), out->raw, &length);
    nvs_close(handle);
    if (result == ESP_ERR_NVS_NOT_FOUND) return true;
    if (result != ESP_OK || length != SELECTOR_BYTES || memcmp(out->raw, "PLR1", 4) != 0 ||
        out->raw[4] > 1 || (out->raw[5] > 1 && out->raw[5] != NO_PREVIOUS) ||
        out->raw[4] == out->raw[5] || out->raw[6] || out->raw[7])
        return fail(error, capacity, "Package selector is invalid");
    out->present = true;
    return true;
}

static bool storage_is_erased(void) {
    const esp_partition_t *partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "storage");
    if (!partition || !partition->size) return false;
    uint8_t *chunk = heap_caps_malloc(4096, MALLOC_CAP_8BIT);
    if (!chunk) return false;
    bool erased = true;
    for (size_t offset = 0; offset < partition->size;) {
        size_t count = partition->size - offset;
        if (count > 4096) count = 4096;
        if (esp_partition_read(partition, offset, chunk, count) != ESP_OK) { erased = false; break; }
        for (size_t i = 0; i < count; ++i) {
            if (chunk[i] != 0xff) { erased = false; break; }
        }
        if (!erased) break;
        offset += count;
    }
    heap_caps_free(chunk);
    return erased;
}

bool player_store_init(char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    if (initialized) return true;
    if (nvs_flash_init() != ESP_OK)
        return fail(error, error_capacity, "NVS initialization failed; existing storage was not erased");
    esp_vfs_spiffs_conf_t config = {
        .base_path = PLAYER_STORE_PATH, .partition_label = "storage",
        .max_files = 4, .format_if_mount_failed = false,
    };
    if (esp_vfs_spiffs_register(&config) != ESP_OK) {
        if (!storage_is_erased())
            return fail(error, error_capacity, "Storage is not wholly erased; refusing to format after mount failure");
        config.format_if_mount_failed = true;
        if (esp_vfs_spiffs_register(&config) != ESP_OK)
            return fail(error, error_capacity, "Could not initialize verified erased storage");
    }
    initialized = true;
    return true;
}

void player_store_free(void *bytes) { heap_caps_free(bytes); }

static bool read_slot(uint32_t role, uint8_t slot, uint8_t **bytes, size_t *length,
                      player_package *package, char *error, size_t capacity) {
    *bytes = NULL; *length = 0;
    const char *path = slot_path(role, slot);
    if (!path) return fail(error, capacity, "Invalid package role or slot");
    FILE *file = fopen(path, "rb");
    if (!file) return fail(error, capacity, "Package file is unavailable");
    struct stat info;
    if (fstat(fileno(file), &info) != 0 || !S_ISREG(info.st_mode) ||
        info.st_size < 128 || info.st_size > PLAYER_PACKAGE_MAX_BYTES) {
        fclose(file);
        return fail(error, capacity, "Stored package size is invalid");
    }
    size_t count = (size_t)info.st_size;
    uint8_t *data = heap_caps_malloc(count, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!data) { fclose(file); return fail(error, capacity, "Not enough PSRAM to read package"); }
    bool ok = fread(data, 1, count, file) == count && fgetc(file) == EOF && !ferror(file);
    if (fclose(file) != 0) ok = false;
    if (!ok) { player_store_free(data); return fail(error, capacity, "Stored package read failed"); }
    if (!player_package_parse(data, count, package, error, capacity)) {
        player_store_free(data); return false;
    }
    if (package->role != role) {
        player_package_clear(package); player_store_free(data);
        return fail(error, capacity, "Stored package role does not match");
    }
    *bytes = data; *length = count;
    return true;
}

bool player_store_stage(uint32_t role, const uint8_t *bytes, size_t length,
                        uint8_t *slot, char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    if (slot) *slot = NO_PREVIOUS;
    if (!initialized || !role_key(role) || !slot)
        return fail(error, error_capacity, "Storage is not initialized or stage arguments are invalid");
    staging *pending = &staged; pending->valid = false;
    player_package package;
    if (!player_package_parse(bytes, length, &package, error, error_capacity)) return false;
    if (package.role != role) {
        player_package_clear(&package); return fail(error, error_capacity, "Package role does not match upload role");
    }
    parse_sha(package.package_sha256, pending->sha);
    player_package_clear(&package);
    if (!load_selection(role, &pending->base, error, error_capacity)) return false;
    uint8_t next = pending->base.present ? (uint8_t)(pending->base.raw[4] ^ 1u) : 0;
    const char *path = slot_path(role, next);
    FILE *file = fopen(path, "wb");
    if (!file) return fail(error, error_capacity, "Could not open inactive package file");
    bool ok = fwrite(bytes, 1, length, file) == length;
    if (ok && fflush(file) != 0) ok = false;
    if (ok && fsync(fileno(file)) != 0) ok = false;
    if (fclose(file) != 0) ok = false;
    if (!ok) { unlink(path); return fail(error, error_capacity, "Inactive package write or sync failed"); }
    uint8_t *check = NULL; size_t check_length = 0;
    if (!read_slot(role, next, &check, &check_length, &package, error, error_capacity)) {
        unlink(path); return false;
    }
    uint8_t digest[32]; parse_sha(package.package_sha256, digest);
    ok = check_length == length && memcmp(digest, pending->sha, 32) == 0;
    player_package_clear(&package); player_store_free(check);
    if (!ok) { unlink(path); return fail(error, error_capacity, "Inactive package verification failed"); }
    pending->slot = next; pending->valid = true; *slot = next;
    return true;
}

bool player_store_commit(uint32_t role, uint8_t slot, const char *package_sha256,
                         char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    uint8_t expected[32];
    if (!initialized || !role_key(role) || slot > 1 || !parse_sha(package_sha256, expected))
        return fail(error, error_capacity, "Invalid package commit arguments");
    staging *pending = &staged;
    if (!pending->valid || pending->slot != slot || memcmp(expected, pending->sha, 32) != 0)
        return fail(error, error_capacity, "Commit does not match the staged package");
    selection before;
    if (!load_selection(role, &before, error, error_capacity)) return false;
    if (before.present != pending->base.present ||
        (before.present && memcmp(before.raw, pending->base.raw, SELECTOR_BYTES) != 0))
        return fail(error, error_capacity, "Package selection changed after staging");
    uint8_t *bytes = NULL; size_t length = 0; player_package package;
    if (!read_slot(role, slot, &bytes, &length, &package, error, error_capacity)) return false;
    uint8_t actual[32]; parse_sha(package.package_sha256, actual);
    player_package_clear(&package); player_store_free(bytes);
    if (memcmp(expected, actual, 32) != 0)
        return fail(error, error_capacity, "Staged package changed before commit");
    uint8_t next[SELECTOR_BYTES] = {0};
    memcpy(next, "PLR1", 4); next[4] = slot; next[5] = before.present ? before.raw[4] : NO_PREVIOUS;
    memcpy(next + 8, actual, 32);
    if (before.present) memcpy(next + 40, before.raw + 8, 32);
    nvs_handle_t handle;
    if (nvs_open("rnbo_player", NVS_READWRITE, &handle) != ESP_OK)
        return fail(error, error_capacity, "Could not open package selector for commit");
    esp_err_t status = nvs_set_blob(handle, role_key(role), next, sizeof(next));
    if (status == ESP_OK) status = nvs_commit(handle);
    uint8_t readback[SELECTOR_BYTES]; size_t readback_size = sizeof(readback);
    if (status == ESP_OK) status = nvs_get_blob(handle, role_key(role), readback, &readback_size);
    if (status == ESP_OK && (readback_size != sizeof(next) || memcmp(next, readback, sizeof(next)) != 0)) status = ESP_FAIL;
    if (status != ESP_OK) {
        esp_err_t rollback = before.present ? nvs_set_blob(handle, role_key(role), before.raw, sizeof(before.raw))
                                            : nvs_erase_key(handle, role_key(role));
        if (rollback == ESP_ERR_NVS_NOT_FOUND) rollback = ESP_OK;
        if (rollback == ESP_OK) rollback = nvs_commit(handle);
        nvs_close(handle);
        return fail(error, error_capacity, rollback == ESP_OK ? "Package selector commit failed; previous selection retained"
                                                             : "Package selector commit and rollback failed");
    }
    nvs_close(handle); pending->valid = false;
    return true;
}

bool player_store_read(uint32_t role, bool previous, uint8_t **bytes, size_t *length,
                       char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    if (bytes) *bytes = NULL;
    if (length) *length = 0;
    if (!initialized || !role_key(role) || !bytes || !length)
        return fail(error, error_capacity, "Invalid package read arguments or storage is not initialized");
    selection current;
    if (!load_selection(role, &current, error, error_capacity)) return false;
    if (!current.present || (previous && current.raw[5] == NO_PREVIOUS))
        return fail(error, error_capacity, previous ? "No previous package is selected" : "No package is selected");
    uint8_t slot = current.raw[previous ? 5 : 4];
    player_package package;
    if (!read_slot(role, slot, bytes, length, &package, error, error_capacity)) return false;
    uint8_t digest[32]; parse_sha(package.package_sha256, digest);
    bool ok = memcmp(digest, current.raw + (previous ? 40 : 8), 32) == 0;
    player_package_clear(&package);
    if (!ok) {
        player_store_free(*bytes); *bytes = NULL; *length = 0;
        return fail(error, error_capacity, "Stored package does not match its committed selector");
    }
    return true;
}

bool player_store_promote_previous(uint32_t role, const char *package_sha256,
                                   char *error, size_t error_capacity) {
    clear_error(error, error_capacity);
    uint8_t expected[32];
    if (!initialized || !role_key(role) || !parse_sha(package_sha256, expected))
        return fail(error, error_capacity, "Invalid previous-package promotion arguments");
    selection current;
    if (!load_selection(role, &current, error, error_capacity)) return false;
    if (!current.present || current.raw[5] == NO_PREVIOUS ||
        memcmp(expected, current.raw + 40, 32) != 0)
        return fail(error, error_capacity, "Previous package identity does not match the selector");
    /* Commit re-reads and fully validates the existing previous file and swaps
     * one NVS selector. Crucially, stage() and its wb path are never called. */
    staged.base = current;
    staged.slot = current.raw[5];
    memcpy(staged.sha, expected, 32);
    staged.valid = true;
    return player_store_commit(role, staged.slot, package_sha256, error, error_capacity);
}
