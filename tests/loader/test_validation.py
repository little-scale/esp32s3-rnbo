"""Run the actual pinned Xtensa loader validator against our compiled fixtures.

Build the spike first. No module machine code is executed by these host tests.
"""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LOADER = Path(os.environ.get("RNBO_S3_LOADER_COMPONENT", ROOT / "build/vendor-loader-spike/elf_loader"))
MODULE = ROOT / "build/loader-spike-module/rnbo_loader_fixture.app.elf"
BAD_MODULE = ROOT / "build/loader-spike-module-bad-import/rnbo_loader_fixture.app.elf"

@unittest.skipUnless(MODULE.is_file() and BAD_MODULE.is_file() and (LOADER / "src/esp_elf_validate.c").is_file(), "build loader spike fixtures first")
class CompiledFixtureValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rnbo-loader-host-")
        library = Path(cls.temporary.name) / "validator.so"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                        "-DCONFIG_IDF_TARGET_ARCH_XTENSA=1", "-DCONFIG_ELF_LOADER_BUS_ADDRESS_MIRROR=1",
                        "-I", str(LOADER / "tests/host/include"), "-I", str(LOADER / "include"),
                        str(LOADER / "src/esp_elf_validate.c"), "-o", str(library)], check=True)
        cls.library = ctypes.CDLL(str(library))
        cls.library.esp_elf_validate.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
        cls.library.esp_elf_validate.restype = ctypes.c_int
        cls.image = MODULE.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def validate(self, data, misaligned=False):
        buffer = ctypes.create_string_buffer(len(data) + 8)
        pointer = ctypes.addressof(buffer) + (1 if misaligned else 0)
        ctypes.memmove(pointer, bytes(data), len(data))
        return self.library.esp_elf_validate(pointer, len(data))

    def test_compiled_module_is_structurally_admitted(self):
        self.assertEqual(self.validate(self.image), 0)

    def test_unknown_import_requires_later_symbol_resolution(self):
        # The structural validator must not pretend to authenticate or resolve
        # imports. Firmware separately proves its unknown import is rejected.
        self.assertEqual(self.validate(BAD_MODULE.read_bytes()), 0)

    def test_truncation_is_rejected(self):
        for length in (0, 1, 4, 16, 51, len(self.image) - 1):
            with self.subTest(length=length):
                self.assertNotEqual(self.validate(self.image[:length]), 0)

    def test_wrong_machine_and_unaligned_payload_are_rejected(self):
        data = bytearray(self.image)
        struct.pack_into("<H", data, 18, 241) # FM1 pi32v2, deliberately incompatible
        self.assertNotEqual(self.validate(data), 0)
        self.assertNotEqual(self.validate(self.image, misaligned=True), 0)

if __name__ == "__main__":
    unittest.main()
