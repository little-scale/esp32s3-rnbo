#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a trusted RNBO Minimal C++ export and prepare a reproducible copy.

This is source admission for static compilation, not a native-code sandbox or an
ELF loader. The installed RNBO package and original export are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

SUPPORTED_VERSION = "1.4.4"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_COMMON_BYTES = 16 * 1024 * 1024
MAX_PARAMETERS = 128
NUMERICAL_PROFILES = ("float32-strict", "float32-cycle-v1", "float32-cycle-v2", "float32-audio-v1", "float32-audio-v2")


class ExportError(ValueError):
    pass


def canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ExportError(f"Required regular file is missing (or is a symbolic link): {path}")
    if path.stat().st_size > limit:
        raise ExportError(f"File exceeds the {limit}-byte admission limit: {path}")
    data = path.read_bytes()
    if len(data) > limit:
        raise ExportError(f"File grew beyond the admission limit: {path}")
    return data


def read_json(data: bytes, label: str) -> dict:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ExportError(f"Duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    try:
        result = json.loads(data, object_pairs_hook=unique_pairs,
                            parse_constant=lambda s: (_ for _ in ()).throw(ExportError(f"Non-finite JSON in {label}: {s}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"Invalid {label}: {exc}") from exc
    if not isinstance(result, dict):
        raise ExportError(f"{label} must contain a JSON object")
    return result


def integer(description: dict, key: str, low: int, high: int) -> int:
    value = description.get(key)
    if type(value) is not int or not low <= value <= high:
        raise ExportError(f"{key} must be an integer in [{low}, {high}], found {value!r}")
    return value


def validate_description(description: dict, role: str, midi_output_policy: str = "reject") -> list[dict]:
    inputs = integer(description, "numInputChannels", 0, 2)
    outputs = integer(description, "numOutputChannels", 0, 2)
    if (inputs, outputs) != ((0, 2) if role == "main" else (2, 2)):
        raise ExportError(f"{role} requires {'0' if role == 'main' else '2'} inputs and 2 outputs; found {inputs}/{outputs}")
    for key in ("numSignalInParameters", "numSignalOutParameters"):
        if description.get(key, 0) != 0:
            raise ExportError(f"The static adapter does not yet support {key}")
    integer(description, "numMidiInputPorts", 0, 1)
    midi_outputs = integer(description, "numMidiOutputPorts", 0, 1)
    if midi_outputs and midi_output_policy != "discard":
        raise ExportError("MIDI output requires the explicit --midi-output discard policy; transmitting MIDI is not implemented")
    for key in ("externalDataRefs", "inports", "outports"):
        if description.get(key, []) != []:
            raise ExportError(f"The static adapter does not yet support {key}")
    count = integer(description, "numParameters", 0, MAX_PARAMETERS)
    params = description.get("parameters")
    if not isinstance(params, list) or len(params) != count:
        raise ExportError("parameters must match numParameters")
    ids = set()
    for index, param in enumerate(params):
        if not isinstance(param, dict):
            raise ExportError("Each parameter must be an object")
        if param.get("type") != "ParameterTypeNumber":
            raise ExportError("Only ordinary numeric parameters are supported by the static adapter")
        if type(param.get("index")) is not int or param["index"] != index:
            raise ExportError("Parameter indices must be contiguous in exported order")
        identity = param.get("paramId")
        if not isinstance(identity, str) or not identity or len(identity.encode()) > 191 or identity in ids or "\0" in identity:
            raise ExportError("Parameter IDs must be unique nonempty strings of at most 191 UTF-8 bytes without NUL")
        ids.add(identity)
        label = param.get("displayName") or param.get("name")
        unit = param.get("unit", "")
        if not isinstance(label, str) or not label or len(label.encode()) > 95 or "\0" in label:
            raise ExportError(f"Parameter {identity}: label must fit 95 UTF-8 bytes without NUL")
        if not isinstance(unit, str) or len(unit.encode()) > 31 or "\0" in unit:
            raise ExportError(f"Parameter {identity}: unit must fit 31 UTF-8 bytes without NUL")
        for field in ("minimum", "maximum", "initialValue", "exponent"):
            value = param.get(field)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ExportError(f"Parameter {identity}: {field} must be finite")
            try:
                converted = struct.unpack("f", struct.pack("f", value))[0]
            except (OverflowError, struct.error) as exc:
                raise ExportError(f"Parameter {identity}: {field} must fit float32") from exc
            if not math.isfinite(converted):
                raise ExportError(f"Parameter {identity}: {field} must fit float32")
        if not param["minimum"] < param["maximum"] or not param["minimum"] <= param["initialValue"] <= param["maximum"] or param["exponent"] <= 0:
            raise ExportError(f"Parameter {identity}: invalid range/default/exponent")
        to_float = lambda v: struct.unpack("f", struct.pack("f", v))[0]
        if not to_float(param["minimum"]) < to_float(param["maximum"]) or to_float(param["exponent"]) <= 0:
            raise ExportError(f"Parameter {identity}: range/exponent collapses in the float32 ABI")
        if type(param.get("steps")) is not int or not 0 <= param["steps"] <= 0x7fffffff:
            raise ExportError(f"Parameter {identity}: steps must be a nonnegative int32")
    return params


def runtime_fixes(files: dict[str, bytes], *, apply_fixes: bool) -> list[dict]:
    """Exact-pattern fixes from the reviewed RNBO 1.4.4 runtime.

    Neither changes numerical DSP algorithms. Each independently fails closed
    when the expected upstream layout changes. No FM1 CPU-specific fixes apply.
    """
    if not apply_fixes:
        return []
    changes = []
    name = "common/RNBO_List.h"
    original = files[name]
    text = original.decode()
    pattern = r"for \(; i < length; i\+\+\) \{(\s+)_stackValues\[i\] = l\[i\];"
    if len(re.findall(pattern, text)) != 4 or text.count("_values[i] = l[i];") != 4 or text.count("_values[i] = listValues[i];") != 1:
        raise ExportError("RNBO_List.h no longer matches the reviewed 1.4.4 copy fix; use --no-runtime-fixes only for an explicit reference build")
    text = re.sub(pattern, r"for (; i < length && i < FIXED; i++) {\1_stackValues[i] = l[i];", text)
    text = text.replace("_values[i] = l[i];", "(*this)[i] = l[i];")
    text = text.replace("_values[i] = listValues[i];", "(*this)[i] = listValues[i];")
    files[name] = text.encode()
    changes.append({"name": "rnbo-1.4.4-list-copy-bounds-v1", "file": name,
                    "raw_sha256": digest(original), "prepared_sha256": digest(files[name]),
                    "purpose": "Bound inline copies and use checked indexing for overflow storage"})
    original = files[name]
    move = ("\t\tlistbase(listbase&& l)\n\t\t: length(l.length, *this)\n"
            "\t\t, _values(l._values)\n\t\t, _allocatedLength(l._allocatedLength)\n"
            "\t\t{\n\t\t\tl._allocatedLength = 0;\n\t\t\tl._values = nullptr;\n\t\t}")
    if text.count(move) != 1:
        raise ExportError("RNBO_List.h no longer matches the reviewed inline-storage move constructor")
    move_fixed = ("\t\tlistbase(listbase&& l)\n\t\t: length(l.length, *this)\n"
                  "\t\t, _values(l._values)\n\t\t, _allocatedLength(l._allocatedLength)\n"
                  "\t\t{\n\t\t\tfor (size_t i = 0; i < length && i < FIXED; ++i) {\n"
                  "\t\t\t\t_stackValues[i] = l._stackValues[i];\n\t\t\t}\n"
                  "\t\t\tl.length = 0;\n\t\t\tl._allocatedLength = FIXED;\n"
                  "\t\t\tl._values = nullptr;\n\t\t}")
    text = text.replace(move, move_fixed)
    files[name] = text.encode()
    changes.append({"name": "rnbo-1.4.4-list-move-inline-storage-v1", "file": name,
                    "input_sha256": digest(original), "prepared_sha256": digest(files[name]),
                    "purpose": "Copy moved inline elements, transfer overflow storage, and reset moved-from ownership"})
    original = files[name]
    assignment = "template<size_t N1> listbase<T>& operator=(const listbase<T, N1>& l)"
    if text.count(assignment) != 1:
        raise ExportError("RNBO_List.h no longer matches the reviewed cross-capacity assignment return type")
    text = text.replace(assignment, "template<size_t N1> listbase& operator=(const listbase<T, N1>& l)")
    files[name] = text.encode()
    changes.append({"name": "rnbo-1.4.4-list-cross-capacity-assignment-v1", "file": name,
                    "input_sha256": digest(original), "prepared_sha256": digest(files[name]),
                    "purpose": "Return the actual destination list specialization from cross-capacity assignment"})
    name = "common/RNBO_MinimalEngine.h"
    original = files[name]
    text = original.decode()
    needle = "_patcher->processClockEvent(event.time, event.clockId, event.clockHasValue, event.value);"
    if text.count(needle) != 1:
        raise ExportError("RNBO_MinimalEngine.h no longer matches the reviewed 1.4.4 nested clock fix")
    text = text.replace(needle, "(event.eventTarget ? event.eventTarget : _patcher)->processClockEvent(event.time, event.clockId, event.clockHasValue, event.value);")
    files[name] = text.encode()
    changes.append({"name": "rnbo-1.4.4-nested-clock-target-v1", "file": name,
                    "raw_sha256": digest(original), "prepared_sha256": digest(files[name]),
                    "purpose": "Dispatch nested clocks to the recorded event target"})
    return changes


# Fingerprint of the reviewed RNBO 1.4.4 fixed-256 scalar-frequency cycle~
# definition after comments/literals are masked, whitespace is removed, and its
# generated method/field prefix is normalized to CYCLE. Guard the entire known
# algorithm without vendoring generated RNBO source in this integration tool.
_CYCLE_KERNEL_SHA256 = "5c92dc4e550b73067cf581cec82d12ba4a6ea75213c6c1a8721903e23f53997c"


def cpp_code_mask(source: str) -> str:
    """Keep positions/code intact while masking comments and C++ literals.

    A lexical guard, not a C++ parser. Unterminated constructs stop the optional
    transformation. Raw string literals are handled before ordinary quotes.
    """
    result=list(source)
    index=0
    while index<len(source):
        end=None
        if source.startswith("//",index):
            end=source.find("\n",index+2)
            if end<0:end=len(source)
        elif source.startswith("/*",index):
            closing=source.find("*/",index+2)
            if closing<0:raise ExportError("float32-cycle-v1: unterminated C++ comment")
            end=closing+2
        elif source.startswith('R"',index):
            opening=source.find("(",index+2,index+19)
            if opening<0:raise ExportError("float32-cycle-v1: unsupported C++ raw string delimiter")
            delimiter=source[index+2:opening]
            if any(c.isspace() or c in "()\\" for c in delimiter):
                raise ExportError("float32-cycle-v1: unsupported C++ raw string delimiter")
            terminator=")"+delimiter+'"'
            closing=source.find(terminator,opening+1)
            if closing<0:raise ExportError("float32-cycle-v1: unterminated C++ raw string")
            end=closing+len(terminator)
        elif source[index] in "\"'":
            quote=source[index];cursor=index+1
            while cursor<len(source):
                if source[cursor]=="\\":cursor+=2;continue
                if source[cursor]==quote:break
                cursor+=1
            if cursor>=len(source):raise ExportError("float32-cycle-v1: unterminated C++ string/character literal")
            end=cursor+1
        if end is not None:
            for position in range(index,end):
                if source[position]!="\n":result[position]=" "
            index=end
        else:index+=1
    return "".join(result)


def float32_cycle(source: bytes) -> tuple[bytes, dict]:
    text=source.decode()
    masked=cpp_code_mask(text)
    replacements=[]
    kernels=[]
    for match in re.finditer(r"\bvoid\s+(cycle_[A-Za-z0-9_]+_perform)\s*\(",masked):
        name=match[1];prefix=name.removesuffix("_perform")
        cursor=match.end()-1;depth=0
        while cursor<len(masked):
            if masked[cursor]=="(":depth+=1
            elif masked[cursor]==")":
                depth-=1
                if depth==0:break
            cursor+=1
        cursor+=1
        while cursor<len(masked) and masked[cursor].isspace():cursor+=1
        if cursor>=len(masked) or masked[cursor]!="{":
            raise ExportError(f"float32-cycle-v1: unsupported cycle definition {name}")
        opening=cursor;depth=1;cursor+=1
        while cursor<len(masked) and depth:
            if masked[cursor]=="{":depth+=1
            elif masked[cursor]=="}":depth-=1
            cursor+=1
        if depth:raise ExportError(f"float32-cycle-v1: unterminated cycle body {name}")
        definition=masked[match.start():cursor]
        normalized=re.sub(r"\s+","",definition).replace(prefix,"CYCLE")
        if digest(normalized.encode())!=_CYCLE_KERNEL_SHA256:
            raise ExportError(f"float32-cycle-v1: unsupported RNBO 1.4.4 kernel {name}; expected the reviewed fixed-256 scalar-frequency form")
        for coefficient in ("3.81471181759574e-6","0.232830643653869629e-9"):
            positions=list(re.finditer(re.escape(coefficient),masked[opening:cursor]))
            if len(positions)!=1:
                raise ExportError(f"float32-cycle-v1: coefficient pattern changed in {name}")
            replacements.append(opening+positions[0].end())
        kernels.append(name)
    if not kernels:raise ExportError("float32-cycle-v1: no qualified cycle~ perform kernel was found")
    for position in sorted(replacements,reverse=True):text=text[:position]+"f"+text[position:]
    prepared=text.encode()
    return prepared,{"name":"rnbo-1.4.4-float32-cycle-v1","file":"rnbo_source.h",
                     "input_sha256":digest(source),"prepared_sha256":digest(prepared),
                     "kernel_count":len(kernels),"literal_suffix_count":len(replacements),"kernels":kernels,
                     "purpose":"Keep two reviewed cycle~ interpolation/phase-output coefficient multiplications in float32",
                     "unchanged":"phase integer arithmetic, truncation, lookup/interpolation algorithm, buffers, scheduler and double time"}


def prepare(export_dir: Path, output_dir: Path, class_name: str, role: str,
            *, apply_fixes: bool = True, midi_output_policy: str = "reject",
            numerical_profile: str = "float32-strict", filter_delay_max_ms: float | None = None,
            float32_delay_storage: bool = False, omit_unused_mtof_table: bool = False,
            hoist_cycle_conversions: bool = False, compact_average_history: bool = False,
            float32_pink_output: bool = False) -> dict:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name):
        raise ExportError("class-name must be a plain C++ identifier")
    if role not in ("main", "fx"):
        raise ExportError("role must be main or fx")
    if midi_output_policy not in ("reject", "discard"):
        raise ExportError("midi-output must be reject or discard")
    if numerical_profile not in NUMERICAL_PROFILES:
        raise ExportError(f"numerical-profile must be one of {NUMERICAL_PROFILES}")
    if type(float32_delay_storage) is not bool:
        raise ExportError("float32 delay storage must be a boolean")
    if type(omit_unused_mtof_table) is not bool:
        raise ExportError("omit unused mtof table must be a boolean")
    if type(hoist_cycle_conversions) is not bool or type(compact_average_history) is not bool:
        raise ExportError("cycle hoisting and compact average history must be booleans")
    if type(float32_pink_output) is not bool:
        raise ExportError("Float32 pink output must be a boolean")
    if float32_pink_output and (not apply_fixes or role != "main" or numerical_profile != "float32-strict"):
        raise ExportError("Float32 pink output requires normal runtime fixes, Main role and the strict base profile")
    if filter_delay_max_ms is not None and (type(filter_delay_max_ms) not in (int, float) or
            not math.isfinite(filter_delay_max_ms) or not 0 < filter_delay_max_ms <= 1000):
        raise ExportError("filter-delay-max-ms must be positive, finite, and at most1000")
    export_dir = export_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ExportError(f"Output already exists; use a fresh build directory: {output_dir}")
    if export_dir == output_dir or export_dir in output_dir.parents:
        raise ExportError("Output must be outside the original export")
    files = {"rnbo_source.h": read_regular(export_dir / "rnbo_source.h", MAX_SOURCE_BYTES),
             "description.json": read_regular(export_dir / "description.json", 1024 * 1024)}
    common = export_dir / "common"
    if not common.is_dir() or common.is_symlink():
        raise ExportError("A regular common/ runtime directory is required")
    common_bytes = 0
    for path in sorted(common.rglob("*")):
        if path.is_symlink():
            raise ExportError(f"Symbolic links are not accepted in a runtime export: {path}")
        if not path.is_file():
            continue
        # Minimal Export is header-only. Copy headers and runtime notices, not
        # unrelated build products, universal runtime units, or executables.
        if path.suffix not in (".h", ".hpp") and not path.name.lower().startswith(("license", "copying")):
            continue
        data = read_regular(path, MAX_COMMON_BYTES)
        common_bytes += len(data)
        if common_bytes > MAX_COMMON_BYTES:
            raise ExportError("The runtime header tree exceeds its admission limit")
        files[path.relative_to(export_dir).as_posix()] = data
    required = ("RNBO_Common.h", "RNBO_Platform.h", "RNBO_Version.h", "RNBO_List.h", "RNBO_MinimalEngine.h")
    if any(f"common/{name}" not in files for name in required):
        raise ExportError("The common/ runtime header tree is incomplete")
    version_text = files["common/RNBO_Version.h"].decode()
    version = re.search(r'const char \* version = "([^\"]+)";', version_text)
    if not version or version[1] != SUPPORTED_VERSION:
        raise ExportError(f"This adapter accepts only runtime {SUPPORTED_VERSION}")
    for candidate in ("RNBO-runtime-LICENSE", "LICENSE"):
        if (export_dir / candidate).is_file():
            files["RNBO-runtime-LICENSE"] = read_regular(export_dir / candidate, 128 * 1024)
            break
    else:
        raise ExportError("Include RNBO-runtime-LICENSE (the runtime MIT notice) in the export")
    # Preserve optional editable source and generator identity when this export
    # came from the local adapter. These are provenance, never executable input.
    for name in ("generator.json", "source.rnbopat"):
        if (export_dir / name).exists():
            files[name] = read_regular(export_dir / name, 1024 * 1024)
    if "generator.json" in files:
        generated = read_json(files["generator.json"], "generator.json")
        if generated.get("rnbo_version") != SUPPORTED_VERSION or generated.get("generated_sha256") != digest(files["rnbo_source.h"]):
            raise ExportError("Generator identity does not match the source/runtime")
        if "source.rnbopat" in files and generated.get("source_sha256") != digest(files["source.rnbopat"]):
            raise ExportError("Editable patch source does not match generator identity")
        voices = generated.get("voices", 1)
        if type(voices) is not int or voices not in (1, 2, 4):
            raise ExportError("Local generator voice topology is invalid")
    else:
        voices = None  # Manual exports need separate topology qualification.
    source = files["rnbo_source.h"].decode()
    if not re.search(r"template\s*<[^>]*>\s*class\s+" + re.escape(class_name) + r"\s*:", source):
        raise ExportError(f"Source does not declare the Minimal Export template class {class_name}")
    # These assertions and assignments are emitted by the reviewed 1.4.4
    # generator. Merely specifying a rate/vector on this CLI is insufficient.
    for pattern in (r"RNBO_ASSERT\(\s*n\s*==\s*256\s*\)",
                    r"RNBO_ASSERT\(\s*maxBlockSize\s*==\s*256\s*\)",
                    r"RNBO_ASSERT\(\s*sampleRate\s*==\s*44100\s*\)"):
        if not re.search(pattern, source):
            raise ExportError("Export must declare the fixed 44100 Hz / 256-frame Minimal profile")
    description = read_json(files["description.json"], "description.json")
    params = validate_description(description, role, midi_output_policy)
    raw_hashes = {name: digest(data) for name, data in sorted(files.items())}
    raw_files = dict(files)
    changes = runtime_fixes(files, apply_fixes=apply_fixes)
    # This exact-context option reviews the corrected original runtime tree.
    # Apply it before the independent integer-wrap fix changes RNBO_Math.h.
    if compact_average_history:
        from compact_average import compact_average
        try:
            files, average_changes = compact_average(files, description, cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.extend(average_changes)
    if apply_fixes:
        from int32_wrap import define_int32_wrap
        try:
            files, integer_changes = define_int32_wrap(files, code_mask=cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.extend(integer_changes)
    if float32_pink_output:
        from pink_output import float32_pink_output as adapt_pink_output
        try:
            files, pink_change = adapt_pink_output(files, description)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(pink_change)
    if numerical_profile=="float32-cycle-v1":
        files["rnbo_source.h"],cycle_change=float32_cycle(files["rnbo_source.h"])
        changes.append(cycle_change)
    if filter_delay_max_ms is not None:
        from bounded_filters import bound_filter_delays
        try:
            files["rnbo_source.h"],filter_change=bound_filter_delays(
                files["rnbo_source.h"],filter_delay_max_ms,code_mask=cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(filter_change)
    if float32_delay_storage:
        from float32_delays import float32_delays
        try:
            files["rnbo_source.h"], delay_change = float32_delays(files["rnbo_source.h"], code_mask=cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(delay_change)
    if numerical_profile in ("float32-cycle-v2", "float32-audio-v1", "float32-audio-v2"):
        from float32_audio import float32_audio
        try:
            files["rnbo_source.h"], audio_change = float32_audio(files["rnbo_source.h"], code_mask=cpp_code_mask, profile=numerical_profile)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(audio_change)
    if hoist_cycle_conversions:
        from hoist_cycles import hoist_cycles
        if any("common/" + name not in files for name in ("RNBO_AudioSignal.h", "RNBO_Types.h")):
            raise ExportError("Cycle hoisting requires the reviewed audio and type runtime headers")
        try:
            files["rnbo_source.h"], hoist_change = hoist_cycles(
                files["rnbo_source.h"], files["common/RNBO_AudioSignal.h"],
                files["common/RNBO_Types.h"], code_mask=cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(hoist_change)
    if omit_unused_mtof_table:
        from omit_mtof_table import omit_mtof_table
        if "common/RNBO_DataRef.h" not in files:
            raise ExportError("Omitting the mtof table requires common/RNBO_DataRef.h")
        try:
            files["rnbo_source.h"], table_change = omit_mtof_table(
                files["rnbo_source.h"], files["common/RNBO_DataRef.h"],
                files["common/RNBO_MinimalEngine.h"], code_mask=cpp_code_mask)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        changes.append(table_change)
    schema = [{key: p.get(key) for key in ("paramId", "index", "name", "displayName", "unit", "minimum", "maximum", "initialValue", "exponent", "steps")}
              for p in params]
    manifest = {"format": "rnbo-esp32s3-prepared-export", "format_version": 1,
                "rnbo_version": SUPPORTED_VERSION, "class_name": class_name,
                "sample_rate": 44100, "block_frames": 256, "role": role,
                "audio_inputs": description["numInputChannels"], "audio_outputs": 2,
                "midi_output_ports": description["numMidiOutputPorts"], "midi_output_policy": midi_output_policy,
                "voices": voices, "voice_topology": "manual-export-unspecified" if voices is None else ("polyphonic-export" if voices > 1 else "single-export"),
                "parameter_count": len(params), "parameter_schema_sha256": digest(canonical(schema)),
                "required_host_services": [], "execution": "static-development",
                "numerical_profile": numerical_profile, "scheduler_time": "float64",
                "source_tree_sha256": digest(canonical(raw_hashes)),
                "editable_source_sha256": digest(files["source.rnbopat"]) if "source.rnbopat" in files else None,
                "adaptations": [change["name"] for change in changes]}
    if filter_delay_max_ms is not None:
        manifest["filter_delay_max_ms"] = filter_delay_max_ms
    if float32_delay_storage:
        manifest["float32_delay_storage"] = True
    if apply_fixes:
        manifest["defined_int32_wrap"] = True
    if hoist_cycle_conversions:
        manifest["hoist_cycle_conversions"] = True
    if float32_pink_output:
        manifest["float32_pink_output"] = True
    if compact_average_history:
        manifest["compact_average_history"] = True
        manifest["requires_opaque_dataref_abi"] = True
        manifest["modified_internal_resource_semantics"] = {
            "average_history": "reviewed authored window1..64; two65-frame Float32 histories; resource indices and positive update notifications retained"}
    if omit_unused_mtof_table:
        manifest["omit_unused_mtof_table"] = True
        manifest["requires_opaque_dataref_abi"] = True
        manifest.setdefault("modified_internal_resource_semantics", {})["RNBODefaultMtofLookupTable256"] = "zero samples; no allocation/fill/initialization DataRefUpdate notification"
    config = ("// Generated from a validated Minimal Export.\n#pragma once\n"
              f"#define RNBO_S3_PATCH_CLASS {class_name}\n"
              f"#define RNBO_S3_PATCH_ROLE {1 if role == 'main' else 2}\n"
              f"#define RNBO_S3_PATCH_DISCARD_MIDI_OUTPUT {1 if midi_output_policy == 'discard' else 0}\n"
              "#define RNBO_S3_PATCH_RATE 44100\n#define RNBO_S3_PATCH_BLOCK 256\n")
    if omit_unused_mtof_table or compact_average_history:
        config += ("#if !defined(RNBO_S3_ABI_MAJOR) || !defined(RNBO_S3_ABI_MINOR)\n"
                   '#error "Internal resource optimisation requires the SDK ABI header before patch_config.h"\n'
                   "#elif RNBO_S3_ABI_MAJOR != 1u || RNBO_S3_ABI_MINOR != 0u\n"
                   '#error "Internal resource optimisation is reviewed only for opaque module C ABI 1.0"\n'
                   "#endif\n")
    files["patch_config.h"] = config.encode()
    prepared_hashes = {name: digest(data) for name, data in sorted(files.items())}
    provenance = {"format_version": 1, "adapter": "rnbo-s3-minimal-static-v1",
                  "preparer_sha256": digest(Path(__file__).read_bytes()),
                  "compiler_helpers_sha256": {name: digest(Path(__file__).with_name(name).read_bytes())
                                              for name in ("bounded_filters.py", "float32_delays.py", "float32_audio.py", "omit_mtof_table.py", "int32_wrap.py", "hoist_cycles.py", "compact_average.py", "pink_output.py")},
                  "raw_files_sha256": raw_hashes, "prepared_files_sha256": prepared_hashes,
                  "adaptations": changes, "manifest_sha256": digest(canonical(manifest)),
                  "claims": {"host_prepared": True, "xtensa_compiled": False,
                             "hardware_qualified": False, "dynamic_loader_qualified": False}}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".prepare-", dir=output_dir.parent))
    try:
        for name, data in files.items():
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, data in raw_files.items():
            path = temporary / "originals" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_bytes(canonical(manifest))
        (temporary / "provenance.json").write_bytes(canonical(provenance))
        # Output is a new directory only; no replacement of an existing build.
        if output_dir.exists():
            raise ExportError("Output was created concurrently")
        os.rename(temporary, output_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path, dest="export_dir")
    parser.add_argument("--out", required=True, type=Path, dest="output_dir")
    parser.add_argument("--class-name", required=True)
    parser.add_argument("--role", choices=("main", "fx"), default="main")
    parser.add_argument("--midi-output", choices=("reject", "discard"), default="reject",
                        help="Explicitly discard declared MIDI output; transmitting MIDI is unimplemented")
    parser.add_argument("--no-runtime-fixes", action="store_true", help="Explicit unmodified-runtime reference build")
    parser.add_argument("--numerical-profile",choices=NUMERICAL_PROFILES,default="float32-strict",
                        help="Optional exact-guarded cycle~ float32 coefficients; strict stays the default")
    parser.add_argument("--filter-delay-max-ms",type=float,
                        help="Explicit comb/allpass delay input maximum0..1000ms; retains Float64 storage and original conversion")
    parser.add_argument("--float32-delays", action="store_true", help="Explicitly convert reviewed internal comb/allpass/delay rings to float32 storage")
    parser.add_argument("--omit-unused-mtof-table", action="store_true",
                        help="Omit reviewed unread mtof lookup payload; requires opaque C ABI, changes internal resource/notification semantics")
    parser.add_argument("--hoist-cycle-conversions", action="store_true",
                        help="Move reviewed scalar cycle conversions outside sample loops without changing arithmetic")
    parser.add_argument("--compact-average-history", action="store_true",
                        help="Compact the reviewed authored1..64-window average history; requires opaque C ABI1.0")
    parser.add_argument("--float32-pink-output", action="store_true",
                        help="Keep output scaling Float32 in the reviewed authored16-row pink graph; requires strict Main and normal fixes")
    args = parser.parse_args()
    try:
        manifest = prepare(args.export_dir, args.output_dir, args.class_name, args.role,
                           apply_fixes=not args.no_runtime_fixes, midi_output_policy=args.midi_output,
                           numerical_profile=args.numerical_profile,filter_delay_max_ms=args.filter_delay_max_ms,
                           float32_delay_storage=args.float32_delays,omit_unused_mtof_table=args.omit_unused_mtof_table,
                           hoist_cycle_conversions=args.hoist_cycle_conversions,compact_average_history=args.compact_average_history,
                           float32_pink_output=args.float32_pink_output)
    except (ExportError, OSError, UnicodeError) as exc:
        parser.exit(1, f"Export rejected: {exc}\n")
    print(json.dumps({"prepared_export": str(args.output_dir.resolve()), "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
