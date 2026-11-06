# SPDX-License-Identifier: MIT
"""Compile the actual package/store C with real cJSON and host flash/NVS stubs.

Packages and their checksums are independently authored with Python stdlib.
No ELF execution, ESP toolchain, network, flash or device access is performed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'firmware/components/player_store'
STUBS = {
    'esp_err.h': '''#pragma once
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NVS_NOT_FOUND 1
''',
    'esp_heap_caps.h': '''#pragma once
#include <stddef.h>
#define MALLOC_CAP_8BIT 1u
#define MALLOC_CAP_SPIRAM 2u
void *heap_caps_malloc(size_t, unsigned);
void heap_caps_free(void *);
''',
    'esp_spiffs.h': '''#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
typedef struct {const char *base_path; const char *partition_label; size_t max_files; bool format_if_mount_failed;} esp_vfs_spiffs_conf_t;
esp_err_t esp_vfs_spiffs_register(const esp_vfs_spiffs_conf_t *);
''',
    'esp_partition.h': '''#pragma once
#include <stddef.h>
#include "esp_err.h"
#define ESP_PARTITION_TYPE_DATA 1
#define ESP_PARTITION_SUBTYPE_DATA_SPIFFS 130
typedef struct {size_t size;} esp_partition_t;
const esp_partition_t *esp_partition_find_first(int, int, const char *);
esp_err_t esp_partition_read(const esp_partition_t *, size_t, void *, size_t);
''',
    'nvs.h': '''#pragma once
#include <stddef.h>
#include "esp_err.h"
typedef unsigned nvs_handle_t;
#define NVS_READONLY 0
#define NVS_READWRITE 1
esp_err_t nvs_open(const char *, int, nvs_handle_t *);
void nvs_close(nvs_handle_t);
esp_err_t nvs_get_blob(nvs_handle_t, const char *, void *, size_t *);
esp_err_t nvs_set_blob(nvs_handle_t, const char *, const void *, size_t);
esp_err_t nvs_erase_key(nvs_handle_t, const char *);
esp_err_t nvs_commit(nvs_handle_t);
''',
    'nvs_flash.h': '''#pragma once
#include "esp_err.h"
esp_err_t nvs_flash_init(void);
''',
    'mbedtls/sha256.h': '''#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __APPLE__
#include <CommonCrypto/CommonDigest.h>
static inline int mbedtls_sha256(const uint8_t *p,size_t n,uint8_t out[32],int is224) {
    if(is224 || n>UINT32_MAX) return -1;
    return CC_SHA256(p,(CC_LONG)n,out) ? 0 : -1;
}
#else
#include <openssl/sha.h>
static inline int mbedtls_sha256(const uint8_t *p,size_t n,uint8_t out[32],int is224) {
    if(is224) return -1;
    return SHA256(p,n,out) ? 0 : -1;
}
#endif
''',
}


def package(metadata=None, *, role=1, arena=1048576, elf=None, metadata_bytes=None, version=1):
    if metadata is None:
        metadata = {'name': 'Portable patch', 'source_sha256': 'a' * 64, 'initial_volume': 50}
    if metadata_bytes is None:
        metadata_bytes = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).encode()
    # Envelope-only fixture. It is deliberately not an executable module.
    if elf is None:
        elf = b'\x7fELF\x01\x01\x01' + bytes(9) + b'not-executable-test-payload'
    header = struct.pack('<8s9I32s32s20s', b'RNBOS3P1', 128, version, 1, role, 44100,
                         256, arena, len(metadata_bytes), len(elf), hashlib.sha256(elf).digest(),
                         hashlib.sha256(metadata_bytes).digest(), bytes(20))
    assert len(header) == 128
    return header + metadata_bytes + elf


class PlayerStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('cc')
        if not compiler:
            raise unittest.SkipTest('A host C compiler is required')
        idf = Path(os.environ.get('IDF_PATH', str(Path.home() / 'esp/esp-idf')))
        cjson = idf / 'components/json/cJSON'
        if not (cjson / 'cJSON.c').is_file():
            raise unittest.SkipTest('Real cJSON source is required from an installed ESP-IDF')
        cls.temporary = tempfile.TemporaryDirectory(prefix='rnbo-player-store-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.storage = cls.directory / 'storage'
        cls.storage.mkdir()
        includes = cls.directory / 'include'
        for name, text in STUBS.items():
            p = includes / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        cls.executable = cls.directory / 'test-player-store'
        command = [compiler, '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-Wno-deprecated-declarations', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                   '-Dfsync=player_test_fsync', f'-DPLAYER_STORE_PATH="{cls.storage}"',
                   '-I', str(includes), '-I', str(COMPONENT / 'include'), '-I', str(cjson),
                   str(COMPONENT / 'player_store.c'), str(ROOT / 'tests/player/host_store_test.c'),
                   str(cjson / 'cJSON.c'), '-o', str(cls.executable), '-lm']
        if sys.platform != 'darwin':
            command += ['-lcrypto']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.counter = 0

    def setUp(self):
        for p in self.storage.iterdir():
            p.unlink()

    def fixture(self, raw):
        type(self).counter += 1
        p = self.directory / f'package-{self.counter}.rnbopkg'
        p.write_bytes(raw)
        return p

    def run_native(self, *arguments):
        result = subprocess.run([str(self.executable), *map(str, arguments)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_package_hashes_roles_fields_utf8_and_metadata_bounds(self):
        valid = [package(), package(role=1, arena=4096), package(arena=4194304),
                 package({'name': 'é' * 31 + 'x', 'source_sha256': 'b' * 64, 'initial_volume': 0,
                          'visual': {'available': False}, 'unknown': [1, 2, 3]}),
                 package({'name': 'x', 'source_sha256': 'c' * 64, 'initial_volume': 100})]
        for raw in valid:
            with self.subTest(length=len(raw)):
                self.assertEqual(self.run_native('parse', self.fixture(raw), 'yes'), hashlib.sha256(raw).hexdigest())
        for role in (0, 2, 3, 0xffffffff):
            self.run_native('parse', self.fixture(package(role=role)), 'no')
        for arena in (0, 4095, 4194305, 0xffffffff):
            self.run_native('parse', self.fixture(package(arena=arena)), 'no')
        base = {'name': 'x', 'source_sha256': 'a' * 64, 'initial_volume': 50}
        for key, values in {'name': ['', 'x' * 64, 'é' * 32, 10, 'x\0hidden'],
                            'source_sha256': ['A' * 64, 'a' * 63, 'z' * 64, None],
                            'initial_volume': [True, -1, 101, 1.5, float('inf')]}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.run_native('parse', self.fixture(package({**base, key: value})), 'no')
        for visual in (None, [], 'not-an-object'):
            raw = package({**base, 'visual': visual})
            self.assertEqual(self.run_native('parse', self.fixture(raw), 'yes'), hashlib.sha256(raw).hexdigest())
        duplicate_visual = b'{"name":"x","source_sha256":"' + b'a' * 64 + b'","initial_volume":50,"visual":{},"visual":[]}'
        raw = package(metadata_bytes=duplicate_visual)
        self.assertEqual(self.run_native('parse', self.fixture(raw), 'yes'), hashlib.sha256(raw).hexdigest())
        for field in base:
            self.run_native('parse', self.fixture(package({k: v for k, v in base.items() if k != field})), 'no')

    def test_physical_input_envelope_cannot_be_silently_ignored(self):
        base={'name':'Inputs','source_sha256':'a'*64,'initial_volume':50}
        metadata=dict(base,physical_inputs={'version':1,'board':'xiao','bindings':[]})
        # Envelope admission only; load_slot then checks actual bindings/IDs.
        raw=package(metadata,version=2)
        self.assertEqual(self.run_native('parse',self.fixture(raw),'yes'),hashlib.sha256(raw).hexdigest())
        self.run_native('parse',self.fixture(package(metadata,version=1)),'no')
        self.run_native('parse',self.fixture(package(base,version=2)),'no')
        duplicate=json.dumps(metadata).replace('"physical_inputs":', '"physical_inputs":{},"physical_inputs":').encode()
        self.run_native('parse',self.fixture(package(metadata_bytes=duplicate,version=2)),'no')

    def test_touchscreen_envelope_cannot_be_downgraded_or_mixed(self):
        base={'name':'Touch','source_sha256':'a'*64,'initial_volume':50}
        meta=dict(base,touchscreen_inputs={'version':1,'board':'amoled','area':'patch','bindings':[]})
        raw=package(meta,version=3)
        self.assertEqual(self.run_native('parse',self.fixture(raw),'yes'),hashlib.sha256(raw).hexdigest())
        for version in (1,2):self.run_native('parse',self.fixture(package(meta,version=version)),'no')
        self.run_native('parse',self.fixture(package(base,version=3)),'no')
        self.run_native('parse',self.fixture(package(dict(meta,physical_inputs={}),version=3)),'no')
        duplicate=json.dumps(meta).replace('"touchscreen_inputs":','"touchscreen_inputs":{},"touchscreen_inputs":').encode()
        self.run_native('parse',self.fixture(package(metadata_bytes=duplicate,version=3)),'no')

    def test_reject_corruption_reserved_trailing_json_and_length_overflows(self):
        raw = package()
        for offset in (0, 8, 12, 16, 24, 28, 44, 76, 108, 127, 128, len(raw) - 1):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset):
                self.run_native('parse', self.fixture(changed), 'no')
        for offset, value in ((36, 0xffffffff), (40, 0xffffffff), (36, 65537), (40, 524289)):
            changed = bytearray(raw)
            struct.pack_into('<I', changed, offset, value)
            self.run_native('parse', self.fixture(changed), 'no')
        for changed in (raw[:127], raw[:-1], raw + b'\0'):
            self.run_native('parse', self.fixture(changed), 'no')
        for metadata in (b'[]', b'{}{}', b'{"name":"\xff"}',
                         b'{"name":"x","name":"y","source_sha256":"' + b'a' * 64 + b'","initial_volume":50}'):
            self.run_native('parse', self.fixture(package(metadata_bytes=metadata)), 'no')
        nested = b'{"unknown":' + b'[' * 33 + b'0' + b']' * 33 + b'}'
        self.run_native('parse', self.fixture(package(metadata_bytes=nested)), 'no')
        metadata = json.dumps({'name': 'x', 'source_sha256': 'a' * 64, 'initial_volume': 50}).encode()
        padded = metadata + b' ' * (65536 - len(metadata))
        maximum = package(metadata_bytes=padded, elf=b'\x7fELF\x01\x01\x01' + bytes(524288 - 7))
        self.assertEqual(len(maximum), 589952)
        self.assertEqual(self.run_native('parse', self.fixture(maximum), 'yes'), hashlib.sha256(maximum).hexdigest())

    def test_blank_mount_requires_every_partition_byte_erased(self):
        self.run_native('init-blank')
        self.run_native('init-dirty')
        self.run_native('init-existing')

    def test_inactive_stage_commit_previous_hash_binding_and_main_only(self):
        a = self.fixture(package())
        b = self.fixture(package({'name': 'Second patch', 'source_sha256': 'b' * 64, 'initial_volume': 25}))
        self.run_native('store', a, b)

    def test_sync_selector_failure_and_changed_staging_preserve_active(self):
        a = self.fixture(package())
        b = self.fixture(package({'name': 'Second patch', 'source_sha256': 'b' * 64, 'initial_volume': 25}))
        self.run_native('failures', a, b)


if __name__ == '__main__':
    unittest.main()
