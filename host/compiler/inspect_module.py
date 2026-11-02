"""Conservative admission for compiled modules using the pinned Xtensa loader.

This accepts this compiler's entry-bearing ELF32 ET_DYN profile, not arbitrary
valid ELF files. It models the loader's named sections and actual relocation
operations. Firmware must still validate relocated lifecycle and ABI pointers
before execution. Native code remains trusted; this is not memory isolation.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import struct

UINT32_MAX = 0xffffffff
SHT_PROGBITS, SHT_SYMTAB, SHT_STRTAB = 1, 2, 3
SHT_RELA, SHT_NOBITS, SHT_DYNSYM = 4, 8, 11
SHF_WRITE, SHF_ALLOC, SHF_EXEC, SHF_TLS = 1, 2, 4, 0x400
LIFECYCLE = {".preinit_array": (16, "preinit"), ".init_array": (14, "init"),
             ".fini_array": (15, "fini"), ".ctors": (1, "init"), ".dtors": (1, "fini")}
MAPPED_DATA = {".data", ".bss", ".rodata", ".data.rel.ro"}


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Section:
    index: int
    name: str
    kind: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_bytes: int

    def contains(self, address: int, count: int = 1) -> bool:
        return address >= self.address and address - self.address <= self.size and count <= self.size - (address - self.address)


def inspect_module(data: bytes, *, allowed_imports: set[str], max_elf_bytes: int = 524288,
                   max_loaded_bytes: int = 2097152) -> dict:
    require(isinstance(data, bytes), "ELF input must be immutable bytes")
    require(type(max_elf_bytes) is int and max_elf_bytes > 0 and type(max_loaded_bytes) is int and max_loaded_bytes > 0,
            "ELF budgets must be positive integers")
    require(isinstance(allowed_imports, (set, frozenset)) and all(isinstance(name, str) and name and "\0" not in name for name in allowed_imports),
            "allowed_imports must contain explicit nonempty symbol names")
    require(52 <= len(data) <= max_elf_bytes, "ELF file is truncated or exceeds its container budget")
    require(data[:7] == b"\x7fELF\x01\x01\x01", "Expected little-endian ELF32 version1")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    _, elf_kind, machine, version, entry, phoff, shoff, _, ehsize, phsize, phcount, shsize, shcount, names_index = header
    require(elf_kind == 3 and machine == 94 and version == 1, "Expected Xtensa ET_DYN version1; FM1/native application files are incompatible")
    require(ehsize == 52 and shsize == 40 and shcount > 0 and 0 < names_index < shcount,
            "Invalid ELF header/section sizes")

    def region(offset: int, count: int) -> bytes:
        require(0 <= offset <= len(data) and 0 <= count <= len(data) - offset, "ELF region extends outside the file")
        return data[offset:offset + count]

    require(shoff % 4 == 0, "Unaligned section table")
    region(shoff, shcount * shsize)
    if phcount:
        require(phsize == 32 and phoff % 4 == 0, "Invalid program header table")
        region(phoff, phcount * phsize)
    load_segments = 0
    for index in range(phcount):
        ptype, offset, virtual, _, file_bytes, memory_bytes, _, _ = struct.unpack_from("<8I", data, phoff + index * 32)
        require(ptype != 7, "TLS program segments are unsupported")
        if ptype == 1:
            load_segments += 1
            region(offset, file_bytes)
            require(file_bytes <= memory_bytes and virtual + memory_bytes <= UINT32_MAX, "Invalid PT_LOAD span")
    require(load_segments > 0, "ELF has no PT_LOAD segment")
    headers = [struct.unpack_from("<10I", data, shoff + index * 40) for index in range(shcount)]
    strings_header = headers[names_index]
    require(strings_header[1] == SHT_STRTAB and strings_header[5] > 0, "Missing section-name string table")
    names = region(strings_header[4], strings_header[5])
    require(names[-1] == 0, "Unterminated section-name string table")

    def string(table: bytes, offset: int) -> str:
        require(0 <= offset < len(table), "String offset outside its table")
        end = table.find(b"\0", offset)
        require(end >= 0, "Unterminated ELF string")
        try:
            return table[offset:end].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("ELF names are not UTF-8") from error

    sections = []
    by_name = {}
    mapped = []
    lifecycle = {}
    for index, row in enumerate(headers):
        section = Section(index, string(names, row[0]), *row[1:])
        sections.append(section)
        if section.name:
            require(section.name not in by_name, "Duplicate ELF section name")
            by_name[section.name] = section
        require(not section.flags & SHF_TLS, "TLS sections are unsupported")
        if section.kind != SHT_NOBITS:
            region(section.offset, section.size)
        if section.alignment > 1:
            require(section.alignment & (section.alignment - 1) == 0, "Section alignment is not a power of two")
        require(section.address + section.size <= UINT32_MAX, "Section virtual range overflows ELF32")
        if section.name in LIFECYCLE:
            expected_kind, group = LIFECYCLE[section.name]
            require(section.kind == expected_kind, "Wrong lifecycle section type")
            if section.size:
                require(section.flags & SHF_ALLOC and section.size % 4 == 0 and section.offset % 4 == 0 and section.address % 4 == 0 and section.entry_bytes in (0, 4),
                        "Invalid allocated lifecycle callback array")
                require(group not in lifecycle, "Competing lifecycle callback arrays")
                lifecycle[group] = section
                mapped.append(section)
        elif section.kind in (14, 15, 16) and section.size:
            raise ValueError("Unnamed/unsupported lifecycle callback array")
        elif section.name in MAPPED_DATA:
            if section.name == ".bss":
                require(section.kind == SHT_NOBITS and section.flags & (SHF_ALLOC | SHF_WRITE) == (SHF_ALLOC | SHF_WRITE), "Invalid .bss section")
            else:
                require(section.kind == SHT_PROGBITS and section.flags & SHF_ALLOC, "Invalid mapped data section")
                if section.name == ".data":
                    require(section.flags & SHF_WRITE, ".data is not writable")
            require(not section.flags & SHF_EXEC, "Executable code in a data section is unsupported")
            mapped.append(section)
        elif section.name == ".text":
            require(section.kind == SHT_PROGBITS and section.flags & (SHF_ALLOC | SHF_EXEC) == (SHF_ALLOC | SHF_EXEC) and section.size > 0,
                    "Missing allocated executable .text")
            mapped.append(section)
        elif section.name == ".got.loc":
            require(section.kind == SHT_PROGBITS and section.flags & SHF_ALLOC and not section.flags & SHF_EXEC,
                    "Invalid Xtensa PLT literal section")
            mapped.append(section)
        elif section.flags & (SHF_ALLOC | SHF_EXEC) == (SHF_ALLOC | SHF_EXEC) and section.size:
            raise ValueError("Executable section is not supported by the named-section loader")
    text = by_name.get(".text")
    require(text is not None and text.contains(entry), "ELF entry is outside file-backed .text")
    for index, left in enumerate(mapped):
        for right in mapped[index + 1:]:
            require(not left.size or not right.size or left.address + left.size <= right.address or right.address + right.size <= left.address,
                    "Overlapping mapped sections")
    got = by_name.get(".got.loc")
    text_span = (text.size + 3) & ~3
    if got is not None and got.size:
        require(got.address >= text.address + text.size and (got.address - text.address) % 4 == 0,
                "Invalid Xtensa .got.loc executable span")
        text_span = (got.address + got.size - text.address + 3) & ~3
    # This mirrors esp_elf_load_section's upper bound, including each section's
    # worst-case alignment padding. Runtime allocation can use fewer bytes.
    data_upper_bound = sum(section.size + max(1, section.alignment) - 1 for section in mapped
                           if section.size and section.name not in (".text", ".got.loc"))
    require(text_span + data_upper_bound <= max_loaded_bytes, "Loaded code/data exceed the admission budget")

    imports = set()
    symbol_tables = {}
    for table in sections:
        if table.kind not in (SHT_SYMTAB, SHT_DYNSYM):
            continue
        require(table.offset % 4 == 0 and table.size % 16 == 0 and table.entry_bytes in (0, 16) and table.link < len(sections),
                "Invalid symbol table")
        require(table.kind != SHT_DYNSYM or table.size // 16 <= 65535, "Too many dynamic symbols")
        strings = sections[table.link]
        require(strings.kind == SHT_STRTAB and strings.size > 0, "Symbol table has no string table")
        table_strings = region(strings.offset, strings.size)
        require(table_strings[-1] == 0, "Unterminated symbol string table")
        symbols = []
        for offset in range(table.offset, table.offset + table.size, 16):
            name_offset, value, count, info, _, defined = struct.unpack_from("<IIIBBH", data, offset)
            name = string(table_strings, name_offset)
            binding, symbol_kind = info >> 4, info & 15
            require(symbol_kind != 6, "TLS symbols are unsupported")
            if defined == 0 and name:
                imports.add(name)
            if table.kind == SHT_DYNSYM and binding == 1 and symbol_kind == 2 and defined != 0:
                require(defined == text.index and text.contains(value, max(1, count)), "Exported function lies outside .text")
            symbols.append({"name": name, "value": value, "size": count, "binding": binding, "kind": symbol_kind, "defined": defined})
        symbol_tables[table.index] = symbols
    require(symbol_tables, "ELF has no symbol table")
    require(imports <= allowed_imports, "Unexpected undefined symbols: " + ", ".join(sorted(imports - allowed_imports)))

    def mapped_section(address: int, count: int = 1):
        return next((section for section in mapped if section.size and section.contains(address, count)), None)

    relocations = {}
    destinations = {}
    for section in sections:
        require(section.kind != 9 or not section.size, "Implicit-addend REL relocations are unsupported")
        if section.kind != SHT_RELA:
            continue
        require(section.offset % 4 == 0 and section.size % 12 == 0 and section.entry_bytes in (0, 12) and section.link in symbol_tables,
                "Invalid RELA relocation table")
        symbols = symbol_tables[section.link]
        for offset in range(section.offset, section.offset + section.size, 12):
            destination, info, addend = struct.unpack_from("<IIi", data, offset)
            relocation, symbol_index = info & 255, info >> 8
            require(relocation in (2, 3, 4, 5), "Unsupported Xtensa runtime relocation kind")
            require(symbol_index < len(symbols), "Relocation symbol index outside its table")
            target = mapped_section(destination, 4)
            require(destination % 4 == 0 and target is not None, "Relocation destination outside a loaded aligned word")
            require(destination not in destinations, "Competing relocations for the same word")
            symbol = symbols[symbol_index]
            if relocation in (3, 4):
                if symbol["defined"]:
                    require(mapped_section(symbol["value"]) is not None, "Defined relocation symbol is not mapped by this loader")
                else:
                    require(symbol["name"] in allowed_imports, "Unapproved relocation import")
            elif relocation == 5:
                require(target.kind != SHT_NOBITS, "RELATIVE relocation cannot read its pointer from BSS")
                pointer = struct.unpack_from("<I", data, target.offset + destination - target.address)[0]
                require(pointer == 0 or mapped_section(pointer) is not None, "RELATIVE pointer is outside loaded sections")
            # RTLD is a deliberate no-op in the pinned Xtensa loader. For
            # RELATIVE/GLOB_DAT/JMP_SLOT it does not apply explicit addends.
            require(relocation == 2 or addend == 0, "Nonzero relocation addends are unsupported by the pinned loader")
            destinations[destination] = (relocation, symbol)
            relocations[str(relocation)] = relocations.get(str(relocation), 0) + 1
    callback_counts = {}
    for group, section in lifecycle.items():
        callback_counts[section.name] = section.size // 4
        for address in range(section.address, section.address + section.size, 4):
            pointer = struct.unpack_from("<I", data, section.offset + address - section.address)[0]
            relocation = destinations.get(address)
            if pointer in (0, UINT32_MAX) and relocation is None:
                continue # documented legacy sentinels
            require(relocation is not None, "Lifecycle callback is missing its relocation")
            kind, symbol = relocation
            if kind == 5:
                require(text.contains(pointer), "Lifecycle callback does not target executable .text")
            elif kind in (3, 4):
                require(symbol["defined"] == text.index and text.contains(symbol["value"]), "Lifecycle callback is not module-owned executable code")
            else:
                raise ValueError("Lifecycle callback uses an unsupported no-op relocation")
    return {"elf_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "architecture": "xtensa-esp32s3",
            "machine": machine, "elf_type": elf_kind, "entry": entry, "text_vaddr": text.address,
            "imports": sorted(imports), "sections": {s.name: {"type": s.kind, "flags": s.flags, "address": s.address,
                                                           "offset": s.offset, "bytes": s.size, "alignment": s.alignment}
                                                      for s in sections if s.name},
            "loaded_text_bytes": text_span, "loaded_data_bytes_upper_bound": data_upper_bound,
            "loaded_bytes_upper_bound": text_span + data_upper_bound,
            "relocation_counts": relocations, "lifecycle_callbacks": callback_counts,
            "profile": "pinned-xtensa-section-loader-entry-module", "hardware_qualified": False}
