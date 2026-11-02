#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Identity-bound source and Xtensa precision inventory, never a timing claim.

This is a conservative diagnostic, not a C++ type checker or complete call
graph. It does not rewrite source, execute target code, or infer that every
decimal literal needs changing. Clock and scheduler precision stays separate.
"""
from __future__ import annotations
import argparse
from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from build import verify_prepared
from prepare import cpp_code_mask

ROOT = Path(__file__).resolve().parents[2]
FAMILY = re.compile(r"\b((?:[a-z][a-z0-9]*_tilde|delaytilde|dspexpr|signaladder|signalmultiplier)_\d+)_")
DECIMAL = re.compile(r"(?<![\w.])(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)(?![\w.])")
CLOCK_NAMES = {"updateTime", "advanceTime", "getCurrentTime", "processClockEvent", "processParamInitEvents", "scheduleParamInit"}
TIME_CONVERSIONS = {"sampstoms", "msToSamps", "mstosamps", "sampsToMs"}
SETUP_NAMES = {"initialize", "initializeObjects", "prepareToProcess", "assign_defaults", "allocateDataRefs",
               "allocateSignals", "deallocateSignals", "destroy", "applyState", "extractState"}
EVENT_NAMES = {"processMidiEvent", "processNumMessage", "processListMessage", "processBangMessage",
               "setParameterValue", "setParameterValueNormalized", "processOutletEvent"}
FLOAT64_MATH = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
                "exp", "exp2", "expm1", "log", "log2", "log10", "log1p", "pow", "sqrt", "cbrt",
                "floor", "ceil", "trunc", "round", "fmod", "remainder", "hypot"}


def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def family(name: str) -> str | None:
    match = FAMILY.search(name)
    if not match: return None
    prefix = match[1]
    return "arithmetic" if prefix.startswith(("dspexpr_", "signaladder_", "signalmultiplier_")) else prefix.split("_", 1)[0].replace("delaytilde", "delay")


def method_name(symbol: str) -> str:
    matches = re.findall(r"::([A-Za-z_]\w*)\s*\(", symbol)
    return matches[-1] if matches else symbol.partition("(")[0].strip()


@dataclass(frozen=True)
class Method:
    name: str
    signature: str
    start: int
    end: int
    line: int
    body: str


def source_methods(masked: str) -> list[Method]:
    # The reviewed generator puts method definitions at line starts. Nested
    # C++/Gen functions outside this layout remain unclassified, not guessed.
    pattern = re.compile(r"^(?:template\s*<[^\n]+>\s*)?(?P<signature>(?:[\w:&*<> ,]+\s+)?(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?)\{", re.M)
    methods = []
    for match in pattern.finditer(masked):
        name = match["name"]
        if name in {"if", "for", "while", "switch", "catch"}: continue
        cursor = match.end(); depth = 1
        while cursor < len(masked) and depth:
            if masked[cursor] == "{": depth += 1
            elif masked[cursor] == "}": depth -= 1
            cursor += 1
        if depth: raise ValueError(f"Unterminated generated method {name}")
        methods.append(Method(name, " ".join(match["signature"].split()), match.start(), cursor,
                              masked.count("\n", 0, match.start()) + 1, masked[match.start():cursor]))
    return methods


def domain(name: str, signature: str = "", *, audio=False, setup=False, event=False) -> str:
    if name in CLOCK_NAMES:
        return "clock_or_scheduler"
    if name in TIME_CONVERSIONS:
        return "shared_time_conversion_needs_review"
    if name in SETUP_NAMES or name.endswith(("_init", "_dspsetup", "_getPresetValue", "_setPresetValue")):
        return "setup_or_state"
    if name == "process" or name.endswith("_perform") or audio:
        return "audio_reachable"
    if event or name in EVENT_NAMES: return "event_reachable"
    if setup: return "setup_or_state"
    return "unknown"


def audit_source(source: bytes, provenance: dict | None = None) -> dict:
    source_text = source.decode()
    masked = cpp_code_mask(source_text)
    methods = source_methods(masked)
    by_name = {m.name: m for m in methods}
    calls = {m.name: set(re.findall(r"\bthis\s*->\s*([A-Za-z_]\w*)\s*\(", m.body)) & by_name.keys() for m in methods}

    def reachable(roots):
        seen = set(); pending = list(roots)
        while pending:
            current = pending.pop()
            if current in seen: continue
            seen.add(current); pending.extend(calls.get(current, ()))
        return seen

    audio = reachable({"process"})
    setup = reachable(SETUP_NAMES & by_name.keys())
    event = reachable(EVENT_NAMES & by_name.keys())
    adaptations = (provenance or {}).get("adaptations", [])
    covered = {}
    storage = {}
    for adaptation in adaptations:
        for item in adaptation.get("methods", []): covered.setdefault(item["method"], []).append(adaptation["name"])
        for name in adaptation.get("kernels", []): covered.setdefault(name, []).append(adaptation["name"])
        for item in adaptation.get("objects", []): covered.setdefault(item["object"] + "_perform", []).append(adaptation["name"])
        for item in adaptation.get("rings", []): storage[item["name"]] = item
    records = []
    for m in methods:
        literals = [{"value": t[0], "line": m.line + m.body.count("\n", 0, t.start())} for t in DECIMAL.finditer(m.body)]
        records.append({"name": m.name, "family": family(m.name), "signature": m.signature,
                        "line": m.line, "end_line": m.line + m.body.count("\n"),
                        "method_sha256": digest(source_text[m.start:m.end].encode()),
                        "domain": domain(m.name, m.signature, audio=m.name in audio, setup=m.name in setup, event=m.name in event),
                        "direct_audio_graph_reachable": m.name in audio,
                        "direct_setup_graph_reachable": m.name in setup,
                        "unsuffixed_decimal_literals": literals,
                        "explicit_double_tokens": len(re.findall(r"\bdouble\b", m.body)),
                        "clock_type_tokens": len(re.findall(r"\b(?:MillisecondTime|SampleTime)\b", m.body)),
                        "clock_type_signature_needs_context": bool(re.search(r"\b(?:MillisecondTime|SampleTime)\b", m.signature)),
                        "uint32_trunc_source_uses": [m.line + m.body.count("\n", 0, t.start()) for t in re.finditer(r"\buint32_trunc\s*\(", m.body)],
                        "direct_generated_calls": sorted(calls[m.name]),
                        "recorded_adaptations": sorted(covered.get(m.name, []))})
    rings = []
    for match in re.finditer(r"\b(Float(?:32|64)BufferRef)\s+([A-Za-z_]\w*)_buffer\s*;", masked):
        rings.append({"name": match[2], "family": family(match[2] + "_"), "storage_type": match[1],
                      "sample_bytes": 8 if "64" in match[1] else 4,
                      "line": masked.count("\n", 0, match.start()) + 1,
                      "allocation_provenance": storage.get(match[2]),
                      "classification": "internal_audio_ring" if re.fullmatch(r"(?:(?:comb|allpass)_tilde_\d+_(?:feedForward|feedBack)|delaytilde_\d+_del)", match[2]) else "unknown"})
    families = {}
    for record in records:
        if record["family"] is None: continue
        info = families.setdefault(record["family"], {"objects": set(), "audio_methods": 0, "adapted_methods": 0,
                                                     "audio_decimal_candidates": 0, "float64_rings": 0, "float32_rings": 0})
        prefix = FAMILY.search(record["name"])
        if prefix: info["objects"].add(prefix[1])
        if record["domain"] == "audio_reachable":
            info["audio_methods"] += 1
            info["audio_decimal_candidates"] += len(record["unsuffixed_decimal_literals"])
        if record["recorded_adaptations"]: info["adapted_methods"] += 1
    for ring in rings:
        if ring["family"] in families:
            families[ring["family"]]["float64_rings" if ring["sample_bytes"] == 8 else "float32_rings"] += 1
    for item in families.values(): item["objects"] = sorted(item["objects"])
    return {"source_sha256": digest(source), "methods": records, "rings": rings, "families": families,
            "classification_limit": "Direct this-> generated-call reachability; callbacks, virtual dispatch and external code may add paths. Decimal literals are candidates, not proof of runtime double arithmetic."}


def precision_kind(target: str) -> str:
    name = target.split("@", 1)[0]
    if name in FLOAT64_MATH: return "float64_math"
    if name.endswith("f") and name[:-1] in FLOAT64_MATH: return "float32_math"
    if re.fullmatch(r"__(?:add|sub|mul|div|neg|powi)df[23]", name): return "float64_arithmetic"
    if re.fullmatch(r"__(?:eq|ne|lt|le|gt|ge|unord)df2", name): return "float64_comparison"
    if re.fullmatch(r"__(?:extend\w*df|truncdf\w*|fix(?:uns)?df(?:si|di)|float(?:un)?[sd]idf)\d?", name): return "float64_conversion"
    if name in {"__fixsfdi", "__fixunssfdi", "__floatdisf", "__floatundisf"}: return "float32_int64_conversion"
    if re.fullmatch(r"__(?:add|sub|mul|div|neg)sf[23]", name): return "float32_software_arithmetic"
    if re.fullmatch(r"__(?:u?div|u?mod|mul|ashl|ashr|lshr)di3", name): return "int64_arithmetic"
    return "other"


@dataclass(frozen=True)
class Symbol:
    address: int
    size: int
    name: str


def parse_symbols(text: str) -> list[Symbol]:
    result = []
    for line in text.splitlines():
        match = re.match(r"^([0-9a-fA-F]+)\s+(?:([0-9a-fA-F]+)\s+)?([tTwWaA])\s+(.+)$", line)
        # libgcc assembly routines often have no ST_SIZE. Retain their exact
        # symbol addresses as call targets, but never invent disassembly spans.
        if match and (match[3] not in {'a','A'} or precision_kind(match[4]) != 'other'):
            result.append(Symbol(int(match[1], 16), int(match[2], 16) if match[2] else 0, match[4]))
    return sorted(result, key=lambda s: (s.address, s.name))


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    arguments: str


def parse_instructions(text: str) -> list[Instruction]:
    result = []
    for line in text.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+([A-Za-z][\w.]*)\s*(.*)$", line)
        if match: result.append(Instruction(int(match[1], 16), match[2], match[3].strip()))
    return result


def _register(argument: str) -> str | None:
    match = re.fullmatch(r"a(?:[0-9]|1[0-5])", argument.strip())
    return match[0] if match else None


def _destination(instruction: Instruction) -> int | None:
    match = re.search(r"(?:^|,)\s*([0-9a-fA-F]+)\s*<.*>\s*$", instruction.arguments)
    return int(match[1], 16) if match else None


def resolve_calls(instructions: list[Instruction], symbols: list[Symbol]) -> list[dict]:
    """Forward dataflow keeps a target only when all incoming paths agree.

    Tracks immutable literal loads, register copies and local stack spills.
    Unknown writes kill facts. Calls kill outgoing window registers. Known
    numeric compiler/libm helpers preserve caller stack spills; other calls
    kill them. Ambiguous paths remain unresolved. This deliberately undercounts.
    """
    if not instructions: return []
    known = {s.address: s.name for s in symbols}
    lookup = {i.address: n for n, i in enumerate(instructions)}
    successors = [[] for _ in instructions]; loops = []
    for n, instruction in enumerate(instructions):
        op = instruction.mnemonic; target = _destination(instruction)
        fall = n + 1 if n + 1 < len(instructions) else None
        if op.startswith(("ret", "jx")): continue
        if op == "j":
            if target in lookup: successors[n].append(lookup[target])
        elif op.startswith("b"):
            if target in lookup: successors[n].append(lookup[target])
            if fall is not None: successors[n].append(fall)
        else:
            if fall is not None: successors[n].append(fall)
            if op.startswith("loop") and target in lookup:
                # Hardware loop end branches back without an explicit opcode.
                end = lookup[target] - 1
                if end >= n + 1: successors[end].append(n + 1)
                if op != "loop": successors[n].append(lookup[target])
        if target in lookup and target < instruction.address and (op.startswith("b") or op == "j"):
            loops.append({"kind": "backward_branch_span", "start": target, "end": instruction.address+1,
                          "branch_address": instruction.address})
        if op.startswith("loop") and target in lookup and fall is not None:
            loops.append({"kind": "hardware_loop_span", "start": instructions[fall].address, "end": target,
                          "branch_address": instruction.address})
    incoming: list[dict | None] = [None for _ in instructions]
    incoming[0] = {}; pending = deque([0])

    def transfer(instruction, state):
        result = dict(state); op = instruction.mnemonic
        args = [a.strip() for a in instruction.arguments.split(",")]
        dest = _register(args[0]) if args else None
        if op == "l32r" and dest:
            literal = re.search(r"\(([0-9a-fA-F]+) <(.+)>\)\s*$", instruction.arguments)
            if literal and int(literal[1], 16) in known: result[dest] = known[int(literal[1], 16)]
            else: result.pop(dest, None)
        elif op in {"mov", "mov.n"} and dest:
            if len(args) == 2 and args[1] in state: result[dest] = state[args[1]]
            else: result.pop(dest, None)
        elif op == "or" and dest:
            if len(args) == 3 and args[1] == args[2] and args[1] in state: result[dest] = state[args[1]]
            else: result.pop(dest, None)
        elif op in {"s32i", "s32i.n"}:
            if len(args) == 3 and args[1] == "a1":
                key = "stack:" + args[2]
                if args[0] in state: result[key] = state[args[0]]
                else: result.pop(key, None)
            else: result = {k: v for k, v in result.items() if not k.startswith("stack:")}
        elif op in {"l32i", "l32i.n"} and dest:
            key = "stack:" + args[2] if len(args) == 3 and args[1] == "a1" else ""
            if key in state: result[dest] = state[key]
            else: result.pop(dest, None)
        elif op.startswith("call"):
            called = state.get(instruction.arguments) if op.startswith("callx") else known.get(_destination(instruction))
            numeric_helper = precision_kind(called or "") != "other"
            kill = {f"a{i}" for i in range(8 if op in {"call8", "callx8"} else 2, 16)}
            result = {k: v for k, v in result.items() if k not in kill and (numeric_helper or not k.startswith("stack:"))}
        elif op.startswith(("s8i", "s16i", "ssi", "s32e", "s32c1i")):
            if len(args) == 3 and args[1] == "a1" and op.startswith(("s8i", "s16i", "ssi")):
                # Float/partial stores at one stack offset must not kill an
                # unrelated literal spill. Handle overlapping byte spans.
                try:
                    offset = int(args[2], 0)
                    width = 1 if op.startswith("s8i") else 2 if op.startswith("s16i") else 4
                    result = {k: v for k, v in result.items() if not (k.startswith("stack:") and
                              offset < int(k[6:], 0)+4 and int(k[6:], 0) < offset+width)}
                except ValueError: result = {k: v for k, v in result.items() if not k.startswith("stack:")}
            else: result = {k: v for k, v in result.items() if not k.startswith("stack:")}
        elif not op.startswith(("b", "j", "loop")) and dest:
            result.pop(dest, None)
            if dest == "a1": result = {k: v for k, v in result.items() if not k.startswith("stack:")}
        return result

    # The finite meet lattice only loses facts at joins; new literal facts are
    # generated by instructions. A hard bound prevents malformed-input loops.
    iterations = 0
    while pending:
        n = pending.popleft(); iterations += 1
        if iterations > max(1000, len(instructions) * 128): raise ValueError("Disassembly dataflow did not converge")
        output = transfer(instructions[n], incoming[n])
        for nxt in set(successors[n]):
            old = incoming[nxt]
            merged = dict(output) if old is None else {k: v for k, v in old.items() if output.get(k) == v}
            if old != merged: incoming[nxt] = merged; pending.append(nxt)
    calls = []
    for n, instruction in enumerate(instructions):
        is_tail = (instruction.mnemonic == "jx" or
                   (instruction.mnemonic == "j" and _destination(instruction) not in lookup))
        if not instruction.mnemonic.startswith("call") and not is_tail: continue
        target = None; proof = "unresolved"
        if instruction.mnemonic.startswith("callx") or instruction.mnemonic == "jx":
            target = (incoming[n] or {}).get(instruction.arguments)
            if target: proof = "literal_register_dataflow"
        else:
            address = _destination(instruction)
            target = known.get(address)
            if target: proof = "direct_symbol"
        calls.append({"address": hex(instruction.address), "target": target, "precision": precision_kind(target or ""), "tail_jump": is_tail,
                      "resolution": proof, "reachable_in_function_cfg": incoming[n] is not None,
                      "enclosing_structural_loop_spans": [{k: hex(v) if isinstance(v,int) else v for k,v in loop.items()}
                                                          for loop in loops if loop['start'] <= instruction.address < loop['end']]})
    return calls


def parse_locations(text: str) -> dict[int, list[dict]]:
    results = {}; current = None; lines = []
    def finish():
        if current is not None:
            results[current] = [{"function": lines[i], "location": lines[i+1]} for i in range(0, len(lines)-1, 2)]
    for line in text.splitlines():
        if re.fullmatch(r"0x[0-9a-fA-F]+", line):
            finish(); current = int(line, 16); lines = []
        else: lines.append(line)
    finish(); return results


def elf_identity(data: bytes) -> dict:
    if len(data) < 52 or data[:7] != b"\x7fELF\x01\x01\x01": raise ValueError("Expected Xtensa ELF32 little-endian input")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    if header[2] != 94 or header[1] not in (2, 3): raise ValueError("Expected Xtensa ET_EXEC or ET_DYN")
    shoff, size, count, strings_index = header[6], header[11], header[12], header[13]
    if size != 40 or not 0 < strings_index < count or shoff > len(data) or count > (len(data)-shoff)//40:
        raise ValueError("Invalid ELF section table")
    rows = [struct.unpack_from("<10I", data, shoff+i*40) for i in range(count)]
    def payload(row):
        if row[4] > len(data) or row[5] > len(data)-row[4]: raise ValueError("ELF section outside file")
        return data[row[4]:row[4]+row[5]]
    strings = payload(rows[strings_index]); allocated = {}; relocations = {}
    for row in rows:
        if row[0] >= len(strings) or strings.find(b"\0", row[0]) < 0: raise ValueError("Invalid ELF section name")
        name = strings[row[0]:strings.index(b"\0", row[0])].decode()
        if row[1] in (4, 9) and name in (".rela.dyn", ".rela.plt", ".rel.dyn", ".rel.plt"):
            entry = 12 if row[1] == 4 else 8
            contents = payload(row)
            if len(contents) % entry: raise ValueError("Invalid runtime relocation table")
            # The official build removes exact zero NONE tombstones. Preserve
            # every other record when binding its retained debug companion.
            kept = b"".join(contents[i:i+entry] for i in range(0, len(contents), entry) if contents[i:i+entry] != bytes(entry))
            relocations[name] = {"entry_bytes": entry, "sha256": digest(kept), "records": len(kept)//entry}
        if row[2] & 2 and row[1] not in (4, 9):
            allocated[name] = {"address": row[3], "bytes": row[5], "kind": row[1], "flags": row[2],
                               "sha256": None if row[1] == 8 else digest(payload(row))}
    mapped_names = {".text", ".data", ".rodata", ".bss", ".data.rel.ro", ".got.loc", ".ctors", ".dtors",
                    ".preinit_array", ".init_array", ".fini_array"}
    return {"sha256": digest(data), "bytes": len(data), "type": header[1], "entry": header[4],
            "allocated_sections_without_relocations": allocated,
            "mapped_code_data_sections": {k: v for k, v in allocated.items() if k in mapped_names},
            "runtime_relocations_without_zero_tombstones": relocations}


def _run(command, **options):
    result = subprocess.run([str(x) for x in command], check=True, capture_output=True, text=True, timeout=120, **options)
    if len(result.stdout) > 128*1024*1024: raise ValueError("Tool output exceeds audit limit")
    return result.stdout


def audit(prepared: Path, elf: Path | None, compiler: Path | None, build_report: Path | None, out: Path) -> dict:
    if out.exists(): raise ValueError("Use a new audit output directory")
    provenance, manifest, prepared_snapshot = verify_prepared(prepared)
    source_path = prepared / "rnbo_source.h"; source = source_path.read_bytes()
    source_report = audit_source(source, provenance)
    signal_header = prepared / "common/RNBO_AudioSignal.h"
    signal_text = cpp_code_mask(signal_header.read_text())
    macro = re.search(r"^\s*#\s*define\s+uint32_trunc\(x\)\s+([^\n]+)", signal_text, re.M)
    source_report["phase_macro"] = {"runtime_header_sha256": digest(signal_header.read_bytes()),
                                     "recognized_int64_route": bool(macro and re.sub(r"\s+", "", macro[1]) == "((UBinOpInt)((int64_t)(x)))"),
                                     "source_uses": sum(len(m["uint32_trunc_source_uses"]) for m in source_report["methods"])}
    report = {"format": "rnbo-esp32s3-precision-audit", "format_version": 1, "evidence_kind": "conservative-static-analysis",
              "auditor_sha256": digest(Path(__file__).read_bytes()),
              "dependencies_sha256": {name: digest(Path(__file__).with_name(name).read_bytes()) for name in ("build.py", "prepare.py")},
              "prepared": {"path": str(prepared.resolve()), "manifest": manifest,
                           "manifest_sha256": digest((prepared/"manifest.json").read_bytes()),
                           "provenance_sha256": digest((prepared/"provenance.json").read_bytes())},
              "source": source_report, "measured_cost": False, "hardware_executed": False,
              "limits": ["Callsites count compiled instruction locations, not execution frequency or cycle cost.",
                         "Direct source graph and selected MinimalEngine symbols do not prove whole-program reachability.",
                         "Indirect targets require conservative literal/register/stack dataflow; unresolved calls remain visible. Known numeric helpers are assumed not to mutate caller-owned stack data.",
                         "Clock/setup classification is a review aid; no automatic precision rewrite is authorized."]}
    disassembly = None
    if elf:
        data = elf.read_bytes(); identity = elf_identity(data); build = None
        if build_report:
            build_bytes = build_report.read_bytes()
            build = json.loads(build_bytes)
            expected = build.get("prepared_export", {}).get("provenance", {}).get("prepared_files_sha256", {}).get("rnbo_source.h")
            if expected != digest(source): raise ValueError("Build report source differs from prepared input")
            artifacts = ([build["artifact"]] if "artifact" in build else
                         [{"path": str(ROOT/name), **value} for name, value in build.get("artifacts", {}).items() if name.endswith(".elf")])
            if len(artifacts) != 1: raise ValueError("Build report must identify one reference ELF")
            reference = artifacts[0]; reference_path = Path(reference["path"])
            reference_data = reference_path.read_bytes()
            if digest(reference_data) != reference["sha256"]: raise ValueError("Reference build ELF changed")
            reference_identity = elf_identity(reference_data)
            if (identity["entry"] != reference_identity["entry"] or
                identity["mapped_code_data_sections"] != reference_identity["mapped_code_data_sections"] or
                identity["runtime_relocations_without_zero_tombstones"] != reference_identity["runtime_relocations_without_zero_tombstones"]):
                raise ValueError("ELF/debug companion code/data differs from build artifact")
            report["build_binding"] = {"report": str(build_report.resolve()), "report_sha256": digest(build_bytes),
                                       "reference_elf": str(reference_path), "reference_sha256": reference["sha256"],
                                       "exact_elf_match": digest(reference_data) == digest(data), "mapped_code_data_and_runtime_relocations_match": True,
                                       "ignored_metadata_policy": "Unmapped linker/debug metadata may differ; exact zero runtime NONE tombstones are ignored as in the recorded build normalization"}
            if compiler is None: compiler = Path(build["compiler"]["path"])
        if compiler is None: raise ValueError("ELF audit needs --compiler or a build report compiler path")
        prefix = compiler.name.removesuffix("gcc").removesuffix("g++")
        tools = {name: compiler.with_name(prefix+name) for name in ("nm", "objdump", "addr2line")}
        report["tools"] = {name: {"path": str(path.resolve()), "sha256": digest(path.read_bytes()),
                                  "version": _run([path, "--version"]).splitlines()[0]} for name, path in tools.items()}
        symbols = parse_symbols(_run([tools["nm"], "-S", "-C", "--defined-only", elf]))
        selected = [s for s in symbols if s.size and (
                    ("RNBO::" in s.name and "MinimalEngine<" in s.name and
                     (f'::{manifest["class_name"]}<' in s.name or s.name.startswith("RNBO::MinimalEngine<"))) or
                    # The pinned GCC's $isra$ clones are not demangled by nm.
                    (s.name.startswith('_ZN4RNBO') and 'MinimalEngine' in s.name and
                     (manifest['class_name'] in s.name or s.name.startswith('_ZN4RNBO13MinimalEngine'))))]
        if not selected: raise ValueError("ELF has no named active MinimalEngine functions; supply its debug companion")
        disassembly = _run([tools["objdump"], "-d", "-C", "-l", elf])
        instructions = parse_instructions(disassembly); calls = []; functions = []
        for symbol in selected:
            body = [i for i in instructions if symbol.address <= i.address < symbol.address+symbol.size]
            functions.append({"name": symbol.name, "address": hex(symbol.address), "bytes": symbol.size})
            for call in resolve_calls(body, symbols): call["outer"] = symbol.name; calls.append(call)
        unique = {int(call["address"], 16): call for call in calls}; calls = [unique[key] for key in sorted(unique)]
        locations = parse_locations(_run([tools["addr2line"], "-a", "-f", "-C", "-i", "-e", elf], input="".join(call["address"]+"\n" for call in calls)))
        source_by_name = {m["name"]: m for m in source_report["methods"]}
        for call in calls:
            stack = locations.get(int(call["address"], 16), [])
            call["inline_stack"] = stack
            generated = [source_by_name[method_name(f["function"])] for f in stack
                         if re.search(r"(?:^|/)rnbo_source\.h:\d", f["location"]) and method_name(f["function"]) in source_by_name]
            # Prefer a clock-bearing inner helper over its audio caller.
            chosen = next((m for m in generated if m["domain"] == "clock_or_scheduler"), generated[0] if generated else None)
            call["source_method"] = chosen["name"] if chosen else method_name(call["outer"])
            call["family"] = chosen["family"] if chosen else family(call["outer"])
            call["domain"] = chosen["domain"] if chosen else domain(method_name(call["outer"]))
            clock_frame = next((f for f in stack if method_name(f["function"]) in CLOCK_NAMES), None)
            if clock_frame:
                call.update(source_method=method_name(clock_frame["function"]), family=None, domain="clock_or_scheduler")
            if chosen:
                source_frame = next((f for f in stack if method_name(f['function']) == chosen['name'] and
                                     re.search(r'(?:^|/)rnbo_source\.h:\d',f['location'])), None)
                line = re.search(r'rnbo_source\.h:(\d+)',source_frame['location']) if source_frame else None
                call['generated_source_line'] = int(line[1]) if line else None
                call['uint32_trunc_source_candidate'] = bool(line and int(line[1]) in chosen['uint32_trunc_source_uses'])
            if call['domain'] == 'shared_time_conversion_needs_review' and any(m['domain']=='audio_reachable' for m in generated):
                call['domain'] = 'audio_time_conversion_needs_review'
        binding = {}
        for stack in locations.values():
            for frame in stack:
                location = re.match(r"(.+rnbo_source\.h):(\d+)", frame["location"])
                if location:
                    path = Path(location[1])
                    if path.is_file():
                        actual = digest(path.read_bytes())
                        if actual != digest(source): raise ValueError("DWARF generated source no longer matches prepared input")
                        binding[str(path)] = actual
        report["compiled"] = {"elf": str(elf.resolve()), "elf_identity": identity,
                               "selection": "Named RNBO patch and MinimalEngine functions for the MinimalEngine specialization; EXTERNALENGINE duplicates excluded",
                               "functions": functions, "calls": calls, "dwarf_source_bindings": binding,
                               "calls_by_precision": dict(Counter(c["precision"] for c in calls)),
                               "calls_by_domain_precision": {d: dict(Counter(c["precision"] for c in calls if c["domain"] == d)) for d in sorted({c["domain"] for c in calls})},
                               "unresolved_calls": sum(c["target"] is None for c in calls),
                               "unresolved_audio_calls": sum(c["target"] is None and c["domain"] == "audio_reachable" for c in calls),
                               "resolved_audio_float64_calls": sum(c["precision"].startswith("float64") and c["domain"] in {"audio_reachable", "audio_time_conversion_needs_review"} for c in calls)}
    if verify_prepared(prepared)[2] != prepared_snapshot or digest(source_path.read_bytes()) != digest(source):
        raise ValueError("Prepared source or metadata changed during audit")
    if digest(Path(__file__).read_bytes()) != report['auditor_sha256']:
        raise ValueError("Auditor source changed during audit")
    for name, expected in report['dependencies_sha256'].items():
        if digest(Path(__file__).with_name(name).read_bytes()) != expected:
            raise ValueError("Auditor dependency changed during audit")
    if elf:
        if digest(elf.read_bytes()) != identity['sha256']: raise ValueError("ELF changed during audit")
        for name, path in tools.items():
            if digest(path.read_bytes()) != report['tools'][name]['sha256']: raise ValueError("GNU tool changed during audit")
    if build_report and elf:
        if (digest(build_report.read_bytes()) != report['build_binding']['report_sha256'] or
            digest(reference_path.read_bytes()) != report['build_binding']['reference_sha256']):
            raise ValueError("Reference build report or artifact changed during audit")
    out.mkdir(parents=True)
    if disassembly is not None:
        (out/"disassembly.txt").write_text(disassembly)
        report["compiled"]["disassembly_sha256"] = digest(disassembly.encode())
    (out/"audit.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--build-report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try: report = audit(args.prepared, args.elf, args.compiler, args.build_report, args.out)
    except (ValueError, OSError, subprocess.SubprocessError) as exc: parser.exit(1, f"Precision audit failed: {exc}\n")
    print(json.dumps({"report": str((args.out/"audit.json").resolve()), "families": sorted(report["source"]["families"]),
                      "compiled_calls_by_precision": report.get("compiled", {}).get("calls_by_precision"), "measured_cost": False}))


if __name__ == "__main__": main()
