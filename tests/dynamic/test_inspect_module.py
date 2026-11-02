"""Adversarial tests of the actual compiler admission path; no target execution."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host/compiler"))
from inspect_module import inspect_module
from build_module import normalize_zero_relocations


def fixture():
    """Small structural ELF, with real relative ctor/dtor and named import
    relocation shapes. Its zero-filled text is never executed."""
    definitions = [
        (".text", 1, 6, 0x1000, bytes(32), 0, 0, 4, 0),
        (".rodata", 1, 2, 0x1020, bytes(16), 0, 0, 4, 0),
        (".data", 1, 3, 0x1030, bytes(16), 0, 0, 4, 0),
        (".bss", 8, 3, 0x1040, 32, 0, 0, 4, 0),
        (".ctors", 1, 3, 0x1060, struct.pack("<I", 0x1004), 0, 0, 4, 0),
        (".dtors", 1, 3, 0x1064, struct.pack("<I", 0x1008), 0, 0, 4, 0),
        (".dynsym", 11, 0, 0, bytes(16) + struct.pack("<IIIBBH", 1, 0, 0, 0x12, 0, 0) + struct.pack("<IIIBBH", 11, 0x1000, 16, 0x12, 0, 1), 8, 1, 4, 16),
        (".dynstr", 3, 0, 0, b"\0host_ping\0entry\0", 0, 0, 1, 0),
        (".rela.dyn", 4, 0, 0, struct.pack("<IIi", 0x1060, 5, 0) + struct.pack("<IIi", 0x1064, 5, 0) + struct.pack("<IIi", 0x1000, 2, 1), 7, 0, 4, 12),
        (".rela.plt", 4, 0, 0, struct.pack("<IIi", 0x1030, 0x104, 0), 7, 3, 4, 12),
    ]
    strings = b"\0"; offsets = {}
    for name in [item[0] for item in definitions] + [".shstrtab"]:
        offsets[name] = len(strings); strings += name.encode() + b"\0"
    definitions.append((".shstrtab", 3, 0, 0, strings, 0, 0, 1, 0))
    count = len(definitions) + 1; shoff = 84
    data = bytearray(shoff + count * 40)
    rows = {}
    for index, (name, kind, flags, address, value, link, info, alignment, entries) in enumerate(definitions, 1):
        while len(data) % max(1, alignment): data.append(0)
        offset = len(data); size = value if isinstance(value, int) else len(value)
        if not isinstance(value, int): data.extend(value)
        struct.pack_into("<10I", data, shoff + index * 40, offsets[name], kind, flags, address, offset, size, link, info, alignment, entries)
        rows[name] = {"header": shoff + index * 40, "offset": offset, "index": index, "bytes": size}
    identity = b"\x7fELF\x01\x01\x01" + bytes(9)
    struct.pack_into("<16sHHIIIIIHHHHHH", data, 0, identity, 3, 94, 1, 0x1000, 52, shoff, 0, 52, 32, 1, 40, count, count - 1)
    file_start = rows[".text"]["offset"]
    struct.pack_into("<8I", data, 52, 1, file_start, 0x1000, 0x1000, len(data) - file_start, len(data) - file_start + 32, 7, 4)
    return data, rows


class DynamicAdmissionTests(unittest.TestCase):
    def inspect(self, data, **options):
        return inspect_module(bytes(data), allowed_imports={"host_ping"}, **options)

    def test_supported_profile_reports_actual_loaded_memory_and_imports(self):
        data, _ = fixture()
        result = self.inspect(data)
        self.assertEqual(result["imports"], ["host_ping"])
        self.assertEqual(result["relocation_counts"], {"5": 2, "2": 1, "4": 1})
        self.assertEqual(result["lifecycle_callbacks"], {".ctors": 1, ".dtors": 1})
        self.assertEqual(result["loaded_text_bytes"], 32)
        self.assertGreaterEqual(result["loaded_data_bytes_upper_bound"], 72)

    def test_wrong_target_type_entry_and_file_boundaries_fail(self):
        original, _ = fixture()
        for label, offset, fmt, value in (("FM1 machine", 18, "H", 241), ("application type", 16, "H", 2), ("entry in BSS", 24, "I", 0x1040), ("section table overflow", 32, "I", 0xfffffff0)):
            data = bytearray(original); struct.pack_into("<" + fmt, data, offset, value)
            with self.subTest(label=label), self.assertRaises(ValueError): self.inspect(data)
        for size in (0, 16, 51, len(original) - 1):
            with self.subTest(truncated=size), self.assertRaises(ValueError): self.inspect(original[:size])

    def test_unexpected_import_and_malformed_symbol_string_fail(self):
        data, rows = fixture()
        with self.assertRaisesRegex(ValueError, "Unexpected undefined"):
            inspect_module(bytes(data), allowed_imports=set())
        struct.pack_into("<I", data, rows[".dynsym"]["offset"] + 16, 0xffffffff)
        with self.assertRaisesRegex(ValueError, "String offset"): self.inspect(data)

    def test_actual_loader_unsupported_relocations_and_outside_writes_fail(self):
        original, rows = fixture(); offset = rows[".rela.dyn"]["offset"]
        for label, field, value in (("unsupported kind", 4, 1), ("outside target", 0, 0x2000), ("unaligned target", 0, 0x1062), ("symbol overflow", 4, 0x1005), ("ignored nonzero addend", 8, 4)):
            data = bytearray(original); struct.pack_into("<I", data, offset + field, value)
            with self.subTest(label=label), self.assertRaises(ValueError): self.inspect(data)

    def test_ctor_dtor_pointer_safety_goes_beyond_structural_array_bounds(self):
        original, rows = fixture()
        for name in (".ctors", ".dtors"):
            data = bytearray(original)
            struct.pack_into("<I", data, rows[name]["offset"], 0x1040) # valid mapped BSS, not code
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "executable .text"): self.inspect(data)
        data = bytearray(original)
        struct.pack_into("<I", data, rows[".rela.dyn"]["offset"], 0x1034) # valid destination, leaves ctor unrelocated
        with self.assertRaisesRegex(ValueError, "missing its relocation"): self.inspect(data)

    def test_overlap_tls_and_resource_budgets_fail(self):
        original, rows = fixture()
        data = bytearray(original); struct.pack_into("<I", data, rows[".data"]["header"] + 12, 0x1028)
        with self.assertRaisesRegex(ValueError, "Overlapping"): self.inspect(data)
        data = bytearray(original); struct.pack_into("<I", data, rows[".data"]["header"] + 8, 0x403)
        with self.assertRaisesRegex(ValueError, "TLS"): self.inspect(data)
        with self.assertRaisesRegex(ValueError, "container budget"): self.inspect(original, max_elf_bytes=len(original) - 1)
        with self.assertRaisesRegex(ValueError, "Loaded code/data"): self.inspect(original, max_loaded_bytes=32)

    def test_zero_relocation_normalization_cannot_rewrite_code_or_elf_metadata(self):
        original, rows = fixture()
        relocation_header = rows[".rela.dyn"]["header"]
        # Text is all zero, so a naive tombstone pass could otherwise accept it
        # as NONE and corrupt code while changing a different section's size.
        for label, destination in (("code", rows[".text"]["offset"]), ("ELF header", 0), ("section table", 84)):
            data = bytearray(original)
            struct.pack_into("<I", data, relocation_header + 16, destination)
            struct.pack_into("<I", data, relocation_header + 20, 12)
            with self.subTest(overlap=label), self.assertRaisesRegex(ValueError, "overlaps protected ELF"):
                normalize_zero_relocations(bytes(data))
        data = bytearray(original)
        struct.pack_into("<I", data, relocation_header + 8, 4)
        with self.assertRaisesRegex(ValueError, "overlaps protected ELF"):
            normalize_zero_relocations(bytes(data))

    def test_real_qualified_spike_artifact_still_matches_pinned_loader_profile(self):
        path = ROOT / "build/loader-spike-module/rnbo_loader_fixture.app.elf"
        if not path.is_file(): self.skipTest("Build the isolated loader fixture first")
        report = inspect_module(path.read_bytes(), allowed_imports={"rnbo_spike_host_marker"})
        self.assertEqual(report["machine"], 94)
        self.assertEqual(report["imports"], ["rnbo_spike_host_marker"])
        self.assertGreater(sum(report["lifecycle_callbacks"].values()), 0)

    def test_real_rnbo_linker_tombstones_are_normalized_without_changing_code_or_data(self):
        directory = ROOT / "build/modules/sine"
        raw_path = directory / "rnbo_s3_dynamic.app.raw.elf"
        if not raw_path.is_file(): self.skipTest("Build the dynamic sine module first")
        raw = raw_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Unsupported Xtensa runtime relocation"):
            inspect_module(raw, allowed_imports=set())
        prepared, changes = normalize_zero_relocations(raw)
        self.assertGreater(changes["removed_records"], 0)
        admitted = inspect_module(prepared, allowed_imports=set())
        self.assertEqual(admitted["imports"], [])
        self.assertEqual(prepared, (directory / "rnbo_s3_dynamic.app.elf").read_bytes())
        for section in admitted["sections"].values():
            if section["flags"] & 2 and section["type"] not in (4, 8):
                start = section["offset"]; end = start + section["bytes"]
                self.assertEqual(raw[start:end], prepared[start:end])
        shoff = struct.unpack_from("<I", raw, 32)[0]
        shcount = struct.unpack_from("<H", raw, 48)[0]
        malformed = bytearray(raw)
        for index in range(shcount):
            row = struct.unpack_from("<10I", raw, shoff + index * 40)
            if row[1] != 4: continue
            for position in range(row[4], row[4] + row[5], 12):
                if raw[position:position + 12] == bytes(12):
                    struct.pack_into("<I", malformed, position, 4)
                    with self.assertRaisesRegex(ValueError, "Nonzero R_XTENSA_NONE"):
                        normalize_zero_relocations(bytes(malformed))
                    return
        self.fail("Raw module lacked its reported all-zero tombstone")


if __name__ == "__main__": unittest.main()
