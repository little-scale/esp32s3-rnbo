// SPDX-License-Identifier: MIT
// Host storage faults are simulated; the component's parser/file/selector code
// and the installed cJSON implementation are compiled unchanged.
#include "player_store.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_partition.h"
#include "esp_spiffs.h"
#include "nvs.h"
#include "nvs_flash.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned mounts, formats, scan_bytes, fsyncs;
static bool mount_failure;
static size_t dirty_offset = (size_t)-1, read_failure_offset = (size_t)-1;
static unsigned commit_failures, fsync_failures;
static uint8_t committed[72], pending[72];
static bool has_committed, has_pending, pending_erase;

esp_err_t nvs_flash_init(void) { return ESP_OK; }
esp_err_t esp_vfs_spiffs_register(const esp_vfs_spiffs_conf_t *config) {
    assert(strcmp(config->partition_label, "storage") == 0);
    assert(config->max_files == 4);
    ++mounts;
    if (config->format_if_mount_failed) ++formats;
    return mount_failure && !config->format_if_mount_failed ? ESP_FAIL : ESP_OK;
}
const esp_partition_t *esp_partition_find_first(int type, int subtype, const char *label) {
    static const esp_partition_t partition = {.size = 8193};
    assert(type == ESP_PARTITION_TYPE_DATA && subtype == ESP_PARTITION_SUBTYPE_DATA_SPIFFS);
    assert(strcmp(label, "storage") == 0);
    return &partition;
}
esp_err_t esp_partition_read(const esp_partition_t *partition, size_t offset, void *out, size_t count) {
    assert(offset + count <= partition->size && count <= 4096);
    if (offset == read_failure_offset) return ESP_FAIL;
    memset(out, 0xff, count);
    if (dirty_offset >= offset && dirty_offset - offset < count) ((uint8_t *)out)[dirty_offset - offset] = 0;
    scan_bytes += (unsigned)count;
    return ESP_OK;
}
void *heap_caps_malloc(size_t count, unsigned capabilities) { (void)capabilities; return malloc(count); }
void heap_caps_free(void *bytes) { free(bytes); }
int player_test_fsync(int fd) {
    assert(fd >= 0); ++fsyncs;
    if (fsync_failures) { --fsync_failures; return -1; }
    return 0;
}
esp_err_t nvs_open(const char *space, int mode, nvs_handle_t *handle) {
    assert(strcmp(space, "rnbo_player") == 0); *handle = mode == NVS_READWRITE ? 2 : 1; return ESP_OK;
}
void nvs_close(nvs_handle_t handle) { assert(handle == 1 || handle == 2); }
esp_err_t nvs_get_blob(nvs_handle_t handle, const char *key, void *out, size_t *count) {
    (void)handle; assert(strcmp(key, "main") == 0);
    if (!has_committed) return ESP_ERR_NVS_NOT_FOUND;
    if (*count < sizeof(committed)) { *count = sizeof(committed); return ESP_FAIL; }
    memcpy(out, committed, sizeof(committed)); *count = sizeof(committed); return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t handle, const char *key, const void *bytes, size_t count) {
    assert(handle == 2 && strcmp(key, "main") == 0 && count == sizeof(pending));
    memcpy(pending, bytes, count); has_pending = true; pending_erase = false; return ESP_OK;
}
esp_err_t nvs_erase_key(nvs_handle_t handle, const char *key) {
    assert(handle == 2 && strcmp(key, "main") == 0); has_pending = true; pending_erase = true; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t handle) {
    assert(handle == 2);
    if (commit_failures) { --commit_failures; return ESP_FAIL; }
    if (has_pending) {
        if (!pending_erase) memcpy(committed, pending, sizeof(committed));
        has_committed = !pending_erase; has_pending = false;
    }
    return ESP_OK;
}

static uint8_t *file_bytes(const char *path, size_t *length) {
    FILE *f = fopen(path, "rb"); assert(f);
    assert(fseek(f, 0, SEEK_END) == 0); long count = ftell(f); assert(count > 0);
    assert(fseek(f, 0, SEEK_SET) == 0);
    uint8_t *bytes = malloc((size_t)count); assert(bytes);
    assert(fread(bytes, 1, (size_t)count, f) == (size_t)count); assert(fclose(f) == 0);
    *length = (size_t)count; return bytes;
}
static void expect_read(bool previous, const uint8_t *expected, size_t expected_length) {
    char error[180]; uint8_t *bytes = NULL; size_t length = 0;
    assert(player_store_read(1, previous, &bytes, &length, error, sizeof(error)));
    assert(length == expected_length && memcmp(bytes, expected, length) == 0);
    player_store_free(bytes);
}

int main(int argc, char **argv) {
    assert(argc >= 2); char error[180];
    if (strcmp(argv[1], "init-blank") == 0) {
        mount_failure = true;
        assert(player_store_init(error, sizeof(error)));
        assert(mounts == 2 && formats == 1 && scan_bytes == 8193);
    } else if (strcmp(argv[1], "init-dirty") == 0) {
        mount_failure = true; dirty_offset = 8192;
        assert(!player_store_init(error, sizeof(error)));
        assert(mounts == 1 && formats == 0 && scan_bytes == 8193);
        dirty_offset = (size_t)-1; read_failure_offset = 4096;
        assert(!player_store_init(error, sizeof(error)));
        assert(mounts == 2 && formats == 0);
    } else if (strcmp(argv[1], "init-existing") == 0) {
        assert(player_store_init(error, sizeof(error)));
        assert(player_store_init(error, sizeof(error)));
        assert(mounts == 1 && formats == 0 && scan_bytes == 0);
    } else if (strcmp(argv[1], "parse") == 0) {
        assert(argc == 4); size_t length; uint8_t *bytes = file_bytes(argv[2], &length);
        player_package package;
        bool valid = player_package_parse(bytes, length, &package, error, sizeof(error));
        if (valid != (strcmp(argv[3], "yes") == 0)) {
            fprintf(stderr, "Unexpected package result %d: %s\n", valid, error); return 1;
        }
        if (valid) {
            assert(package.role == 1 && package.metadata_json && package.elf > bytes && package.payload == bytes);
            printf("%s\n", package.package_sha256);
            player_package_clear(&package);
            assert(!package.payload && !package.metadata_json && !package.visual);
        } else assert(!package.payload && !package.metadata_json && error[0]);
        free(bytes);
    } else {
        assert(argc == 4); size_t na, nb; uint8_t *a = file_bytes(argv[2], &na), *b = file_bytes(argv[3], &nb);
        assert(player_store_init(error, sizeof(error)));
        player_package pa, pb;
        assert(player_package_parse(a, na, &pa, error, sizeof(error)));
        assert(player_package_parse(b, nb, &pb, error, sizeof(error)));
        uint8_t slot = 255; uint8_t *none = (void *)1; size_t no_length = 1;
        assert(!player_store_read(1, false, &none, &no_length, error, sizeof(error)) && !none && !no_length);
        assert(!player_store_stage(2, a, na, &slot, error, sizeof(error)) && slot == 255);
        assert(player_store_stage(1, a, na, &slot, error, sizeof(error)) && slot == 0);
        assert(!player_store_read(1, false, &none, &no_length, error, sizeof(error)));
        assert(!player_store_commit(1, slot, pb.package_sha256, error, sizeof(error)));
        assert(player_store_commit(1, slot, pa.package_sha256, error, sizeof(error)));
        expect_read(false, a, na);
        assert(!player_store_read(1, true, &none, &no_length, error, sizeof(error)));
        if (strcmp(argv[1], "failures") == 0) {
            fsync_failures = 1;
            assert(!player_store_stage(1, b, nb, &slot, error, sizeof(error)));
            expect_read(false, a, na);
            assert(player_store_stage(1, b, nb, &slot, error, sizeof(error)) && slot == 1);
            commit_failures = 1;
            assert(!player_store_commit(1, slot, pb.package_sha256, error, sizeof(error)));
            expect_read(false, a, na);
            FILE *f = fopen(PLAYER_STORE_PATH "/main1.pkg", "r+b"); assert(f);
            assert(fseek(f, -1, SEEK_END) == 0); int byte = fgetc(f); assert(byte != EOF);
            assert(fseek(f, -1, SEEK_END) == 0 && fputc(byte ^ 1, f) != EOF && fclose(f) == 0);
            assert(!player_store_commit(1, slot, pb.package_sha256, error, sizeof(error)));
            expect_read(false, a, na);
        } else {
            assert(player_store_stage(1, b, nb, &slot, error, sizeof(error)) && slot == 1);
            expect_read(false, a, na);
            assert(player_store_commit(1, slot, pb.package_sha256, error, sizeof(error)));
            expect_read(false, b, nb); expect_read(true, a, na);
            // Even a fully rehashed valid replacement must match the selector.
            FILE *f = fopen(PLAYER_STORE_PATH "/main1.pkg", "wb"); assert(f);
            assert(fwrite(a, 1, na, f) == na && fclose(f) == 0);
            assert(!player_store_read(1, false, &none, &no_length, error, sizeof(error)) && !none && !no_length);
            expect_read(true, a, na);
            unsigned synced_before=fsyncs;
            assert(!player_store_promote_previous(1,pb.package_sha256,error,sizeof(error)));
            assert(player_store_promote_previous(1,pa.package_sha256,error,sizeof(error)));
            assert(fsyncs==synced_before);
            expect_read(false,a,na);
            // A second promotion to the now-corrupt other file must reject.
            assert(!player_store_promote_previous(1,pb.package_sha256,error,sizeof(error)));
            expect_read(false,a,na);
        }
        assert(fsyncs >= 2);
        player_package_clear(&pa); player_package_clear(&pb); free(a); free(b);
    }
    return 0;
}
