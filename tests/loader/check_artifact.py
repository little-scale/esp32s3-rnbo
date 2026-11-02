#!/usr/bin/env python3
"""Inspect a compiled spike ELF. This does not execute Xtensa code."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

def inspect(path: Path, bad_import: bool = False) -> dict:
    data = path.read_bytes()
    if len(data) < 52 or data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("Expected little-endian ELF32")
    if len(data) > 512 * 1024:
        raise ValueError("Spike ELF exceeds the experimental 512 KiB container limit")
    kind, machine = struct.unpack_from("<HH", data, 16)
    entry, _, section_offset = struct.unpack_from("<III", data, 24)
    section_size, count, names_index = struct.unpack_from("<HHH", data, 46)
    if kind != 3 or machine != 94 or not entry:
        raise ValueError("Expected an entry-bearing Xtensa ET_DYN image")
    if section_size != 40 or not 0 < names_index < count or section_offset + 40 * count > len(data):
        raise ValueError("Invalid ELF section table")
    sections = [struct.unpack_from("<10I", data, section_offset + i * 40) for i in range(count)]
    def region(offset, length):
        if offset > len(data) or length > len(data) - offset:
            raise ValueError("ELF region outside file")
        return data[offset:offset + length]
    names = region(*sections[names_index][4:6])
    def string(table, offset):
        end = table.find(b"\0", offset)
        if offset >= len(table) or end < 0:
            raise ValueError("Invalid ELF string offset")
        return table[offset:end].decode("ascii")
    named = {}
    imports = set()
    relocations = {}
    relocated_addresses = set()
    for section in sections:
        name = string(names, section[0])
        if name in named and name:
            raise ValueError("Duplicate ELF section name")
        named[name] = section
        if section[1] != 8:
            region(*section[4:6])
        if section[1] == 11:
            if section[6] >= count or section[9] != 16 or section[5] % 16:
                raise ValueError("Invalid dynamic symbols")
            strings = region(*sections[section[6]][4:6])
            for offset in range(section[4], section[4] + section[5], 16):
                name_offset, _, _, _, _, defined = struct.unpack_from("<IIIBBH", data, offset)
                symbol = string(strings, name_offset)
                if not defined and symbol:
                    imports.add(symbol)
        if section[1] == 4:
            if section[9] != 12 or section[5] % 12:
                raise ValueError("Invalid relocation section")
            for offset in range(section[4], section[4] + section[5], 12):
                address, info, _ = struct.unpack_from("<III", data, offset)
                relocation = info & 255
                if relocation not in (2, 3, 4, 5):
                    raise ValueError(f"Unsupported Xtensa runtime relocation {relocation}")
                relocations[str(relocation)] = relocations.get(str(relocation), 0) + 1
                relocated_addresses.add(address)
    expected = {"rnbo_spike_host_marker"}
    if bad_import:
        expected.add("rnbo_spike_unapproved_import")
    if imports != expected:
        raise ValueError(f"Unexpected imports: found {sorted(imports)}, expected {sorted(expected)}")
    for name in (".text", ".rodata", ".data", ".bss"):
        if name not in named or not named[name][5] or not named[name][2] & 2:
            raise ValueError(f"Missing allocated {name}")
    callbacks = {}
    for alternatives in ((".init_array", ".ctors"), (".fini_array", ".dtors")):
        matches = [(name, named[name]) for name in alternatives if name in named and named[name][5]]
        if len(matches) != 1:
            raise ValueError("Missing/ambiguous lifecycle callback array")
        name, section = matches[0]
        if not section[2] & 2 or section[3] % 4 or section[5] % 4:
            raise ValueError("Malformed lifecycle callback array")
        addresses = set(range(section[3], section[3] + section[5], 4))
        if not addresses.issubset(relocated_addresses):
            raise ValueError("Lifecycle pointers lack relocations")
        callbacks[name] = section[5] // 4
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "machine": machine, "elf_type": kind, "entry": entry,
            "imports": sorted(imports), "relocations_by_type": relocations,
            "lifecycle_callbacks": callbacks,
            "allocated_sections": {name: section[5] for name, section in named.items() if section[2] & 2},
            "hardware_executed": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--bad-import", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.image, args.bad_import), indent=2))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"Artifact rejected: {error}\n")
