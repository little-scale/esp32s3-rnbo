#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build small strict FX modules from an unchanged qualified IDF module cache.

Only the export-dependent wrapper is compiled per module. Four unchanged SDK
objects and private libm/libgcc are reused. No firmware or device is accessed.
Compile failures are recorded and the batch continues; any failure returns 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host/compiler"))
from build import verify_prepared
from build_module import inventory, normalize_zero_relocations, sources
from inspect_module import inspect_module
from prepare import ExportError, canonical, read_json, read_regular

ADAPTATIONS = [
    "rnbo-1.4.4-list-copy-bounds-v1",
    "rnbo-1.4.4-list-move-inline-storage-v1",
    "rnbo-1.4.4-list-cross-capacity-assignment-v1",
    "rnbo-1.4.4-nested-clock-target-v1",
    "rnbo-1.4.4-defined-imul-v1",
]
ARENA_CHOICES = (4096, 1048576, 2097152)
ARENA_MACRO = "RNBO_S3_DYNAMIC_MAX_ARENA_BYTES"
MEMBERS = ["rnbo_s3_dynamic.cpp.obj", "arena.cpp.obj", "lifecycle.cpp.obj",
           "support.cpp.obj", "integer_abs.cpp.obj"]
LINK_FLAGS = ["-nostartfiles", "-nostdlib", "-fPIC", "-shared", "-e", "app_main",
              "-fdata-sections", "-ffunction-sections", "-Wl,--gc-sections",
              "-fvisibility=hidden", "-g", "-Wl,--strip-discarded", "-Dmain=app_main"]
STRIP_FLAGS = ["--strip-unneeded", "--remove-section=.comment", "--remove-section=.dynamic",
               "--remove-section=.xt.lit", "--remove-section=.xt.prop", "--remove-section=.xtensa.info"]
MANIFEST_KEYS = {
    "adaptations", "audio_inputs", "audio_outputs", "block_frames", "class_name",
    "defined_int32_wrap", "editable_source_sha256", "execution", "format", "format_version",
    "midi_output_policy", "midi_output_ports", "numerical_profile", "parameter_count",
    "parameter_schema_sha256", "required_host_services", "rnbo_version", "role", "sample_rate",
    "scheduler_time", "source_tree_sha256", "voice_topology", "voices",
}


DBTOA_PROFILE = 'float32-dbtoa-v1'
DBTOA_PATCH = '5c4fc8729b6fc245d6613cca27922cd323ffc59530ca68e4317a62419975ca8d'
DBTOA_SOURCE_TREE = '7b15ac0016ce18a4031e5bb8133c3ab77a094ec9d0f6ec491fd0df843039e08a'
DBTOA_CONTRACT = {'absolute_error_limit': 2e-06, 'audio': 'binary32', 'bit_identity_claimed': False, 'build_requirements': ['no-fast-math', 'no-excess-evaluation-precision', 'fp-contract-off', 'standard-math'], 'context': 'dbtoa-signal', 'errno_identity_claimed': False, 'floating_environment_equivalence_claimed': False, 'floating_trap_identity_claimed': False, 'input_domain_db': [-24, 6], 'math_runtime': 'unchanged', 'mathematical_reference': '10^(input/20)', 'nonfinite_qualified': False, 'operation': 'powf(10.0f, binary32(input * 0.05f))', 'rounding': 'nearest-even', 'scheduler_time': 'unchanged-binary64', 'state_layout_and_callers': 'unchanged', 'version': 1}
DBTOA_MAPS = {'float32-strict': '75c2085d7b91b4b798507d87bbc6f271cd23b26e556095b0c0f5a4887780fb37', 'float32-dbtoa-v1': '5b3a50c6ec5ff5b8c6b7eb8a4e710a5d080b66546611d7cbe0f575147884b8c4'}
DBTOA_ADAPTATION_SHA256 = 'e8f45323c798fad983037752ec39f3d15a2fc6c95cb94a6df2884b69a4992cb5'
DBTOA_RAW_SOURCE = '36e3b6f7cfc220ff98783591bf65164aaad2661a01858409f07e331ca0d18b22'


DBTOA_CATALOG_SHA = '873485039077ad60e4b1a7fd82ceb207d5d8c4057e30e00306e50ccd1087ced4'
DBTOA_REFERENCE_SHA = '9b18e7971a3fb25239a7bc452a063f4e0fe3a32628241314ec2f2d806ce48729'
DBTOA_PROFILE_PROOFS = {'A': {'numerical_profile': 'float32-strict', 'prepared_map_sha256': '75c2085d7b91b4b798507d87bbc6f271cd23b26e556095b0c0f5a4887780fb37', 'source_tree_sha256': '7b15ac0016ce18a4031e5bb8133c3ab77a094ec9d0f6ec491fd0df843039e08a', 'editable_source_sha256': '5c4fc8729b6fc245d6613cca27922cd323ffc59530ca68e4317a62419975ca8d', 'adaptation_sha256': None}, 'B': {'numerical_profile': 'float32-dbtoa-v1', 'prepared_map_sha256': '5b3a50c6ec5ff5b8c6b7eb8a4e710a5d080b66546611d7cbe0f575147884b8c4', 'source_tree_sha256': '7b15ac0016ce18a4031e5bb8133c3ab77a094ec9d0f6ec491fd0df843039e08a', 'editable_source_sha256': '5c4fc8729b6fc245d6613cca27922cd323ffc59530ca68e4317a62419975ca8d', 'adaptation_sha256': 'e8f45323c798fad983037752ec39f3d15a2fc6c95cb94a6df2884b69a4992cb5'}}

GEN_DELAY_ADAPTATION = 'rnbo-1.4.4-gen-delay-bool-clamp-v1'
GEN_DELAY_CATALOG_SHA = 'eb8c190c5f1a59b58ddd12b5157479c6a9b47d64c558fbb83715f76536c544d4'
GEN_DELAY_REFERENCE_SHA = 'c8f36e97add54e70dc51e71fa0b15482dfdc69fdc55c1013f89ca748cbce55a7'
GEN_DELAY_RERUN = {'kind': 'gen-delay-boolcast-v1', 'original_catalog_sha256': GEN_DELAY_CATALOG_SHA}
GEN_DELAY_PROOFS = {
    'delay-one-and-three-samples': {
        'prepared_map_sha256': 'ce3db80b6c1f3044969ca11e0035f9357f9340402005f91d142a98519ba7bcdf',
        'raw_map_sha256': '1ae0fe3feb5af1de4e8ad7f39d4226d67efb68879f061be14b9a03850aded7d9',
        'manifest_sha256': '0a6125c08918fb4f1a21321b180f1855547b29cf14ae555a0b5f0c7147d1e6bb',
        'adaptation_sha256': '746d9119add985db6e535ca9987e6a3ebe9a542419c85134eb7c582a4ae0c038'},
    'delay-three-sample-feedback': {
        'prepared_map_sha256': 'c068c04ac465df34aa856b9da616f0460706a072ec2533ebad50ba1fb578e944',
        'raw_map_sha256': '49e92702330fd2a55cb290b7e83aeaaefa72e7a7adc5b2c1c67e95615f31e698',
        'manifest_sha256': '67443342bcf9036deb60f5c0f8e98fde097f0de4cdbbad02e237f17e5bc942e8',
        'adaptation_sha256': 'eef77ad99ad3306d16554a8da1f2218011ce8c577daa4383deb530c0c571fea0'}}
GEN_DELAY_REFERENCE_PROOFS = {
    'delay-one-and-three-samples': {
        'input_words_sha256': '23117b0cba0cb6ad1a52153e5c08b9df92ad5c6403c9edc8a133c51875923ff6',
        'expected_words_sha256': '0e285664198e2ed0ff5e04a8c788d786725ef7d23c4d3d5e8fe54e2ba9e4f9f7',
        'expected_stream_sha256': 'a6c8f2285b477cc40a09e292253b8243ebf839d8c8db3cd6cdfb90ed946094d9'},
    'delay-three-sample-feedback': {
        'input_words_sha256': '23117b0cba0cb6ad1a52153e5c08b9df92ad5c6403c9edc8a133c51875923ff6',
        'expected_words_sha256': 'f4ca70acedd11e90f3a49b8838cb2a0063a719ba6b6d2922d7a8b34e0ad8e4d8',
        'expected_stream_sha256': 'ce2111a76a2728510724e684ca2f62c2f9143f8b28437bb49c5fe3ad486f91ed'}}


def gen_delay_catalog(catalog: dict) -> dict | None:
    """Only a marked exact subset can rerun the two original rejected programs."""
    if 'rerun' not in catalog:
        return None
    path = ROOT / 'tests/fixtures/smoke/gen-state-boundaries/catalog.json'
    if sha(path) != GEN_DELAY_CATALOG_SHA:
        raise ExportError('Original Gen state-boundary catalog changed')
    original = read_json(read_regular(path, 1024 * 1024), 'original Gen catalog')
    expected = dict(original, cases=original['cases'][-2:], rerun=GEN_DELAY_RERUN)
    if canonical(catalog) != canonical(expected):
        raise ExportError('Gen Delay rerun requires exactly the two unchanged original rows')
    return expected


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(manifest: dict, *, numerical_profile: str = "float32-strict", manual_max_comparison: bool = False) -> None:
    """Initial smoke subset; optional adapters/profiles need separate review."""
    if numerical_profile not in ("float32-strict", DBTOA_PROFILE):
        raise ExportError("Unsupported explicit smoke numerical profile")
    candidate = numerical_profile == DBTOA_PROFILE
    keys = MANIFEST_KEYS | {"base_numerical_profile", "numerical_identity", "dbtoa_contract"} if candidate else MANIFEST_KEYS
    if type(manifest) is not dict or set(manifest) != keys:
        raise ExportError("Smoke modules require the normal strict manifest without optional adapters")
    expected = {
        "format": "rnbo-esp32s3-prepared-export", "format_version": 1,
        "rnbo_version": "1.4.4", "class_name": "rnbos3patch", "role": "fx",
        "sample_rate": 44100, "block_frames": 256, "audio_inputs": 2, "audio_outputs": 2,
        "voices": None if manual_max_comparison else 1, "voice_topology": "manual-export-unspecified" if manual_max_comparison else "single-export",
        "numerical_profile": numerical_profile, "scheduler_time": "float64",
        "defined_int32_wrap": True, "required_host_services": [], "midi_output_ports": 0,
        "midi_output_policy": "reject", "adaptations": ADAPTATIONS + (["rnbo-1.4.4-" + DBTOA_PROFILE] if candidate else []), "execution": "static-development",
    }
    for key, value in expected.items():
        if type(manifest.get(key)) is not type(value) or manifest[key] != value:
            raise ExportError(f"Unsupported smoke-module profile field: {key}")
    if candidate and (manifest.get("base_numerical_profile") != "float32-strict" or
            manifest.get("numerical_identity") != "changed-rounding-float32-dbtoa-v1" or
            canonical(manifest.get("dbtoa_contract")) != canonical(DBTOA_CONTRACT) or
            type(manifest.get("parameter_count")) is not int or manifest["parameter_count"] != 0):
        raise ExportError("Unsupported closed dbtoa profile contract")
    if type(manifest["parameter_count"]) is not int or not 0 <= manifest["parameter_count"] <= 32:
        raise ExportError("Smoke modules require an integer parameter_count from 0 through 32")
    for key in ("editable_source_sha256", "parameter_schema_sha256", "source_tree_sha256"):
        if type(manifest[key]) is not str or not re.fullmatch("[0-9a-f]{64}", manifest[key]):
            raise ExportError(f"Invalid prepared identity: {key}")


def validate_dbtoa_prepared(provenance: dict, manifest: dict, snapshot: dict) -> dict:
    """Exact prepared-source identity, not an assertion of DSP output identity."""
    profile=manifest.get('numerical_profile')
    validate_manifest(manifest,numerical_profile=profile)
    files=snapshot.get('prepared_files_sha256',{})
    digest=lambda value:hashlib.sha256(canonical(value)).hexdigest()
    raw=provenance.get('raw_files_sha256',{})
    if (profile not in DBTOA_MAPS or type(manifest.get('parameter_count'))is not int or manifest['parameter_count']!=0 or
            manifest.get('editable_source_sha256')!=DBTOA_PATCH or manifest.get('source_tree_sha256')!=DBTOA_SOURCE_TREE or
            raw.get('rnbo_source.h')!=DBTOA_RAW_SOURCE or digest(raw)!=DBTOA_SOURCE_TREE or
            files!=provenance.get('prepared_files_sha256') or digest(files)!=DBTOA_MAPS[profile]):
        raise ExportError('Unknown dbtoa source/metadata/runtime/configuration composition')
    records=[r for r in provenance.get('adaptations',[])if r.get('name')=='rnbo-1.4.4-'+DBTOA_PROFILE]
    if (profile==DBTOA_PROFILE and (len(records)!=1 or digest(records[0])!=DBTOA_ADAPTATION_SHA256) or
            profile=='float32-strict' and records):
        raise ExportError('Unknown dbtoa four-literal/inverse adaptation')
    return {'numerical_profile':profile,'prepared_map_sha256':DBTOA_MAPS[profile],
            'source_tree_sha256':DBTOA_SOURCE_TREE,'editable_source_sha256':DBTOA_PATCH,
            'adaptation_sha256':DBTOA_ADAPTATION_SHA256 if profile==DBTOA_PROFILE else None}


def validate_smoke_prepared(provenance: dict, manifest: dict, snapshot: dict, *,
                            numerical_profile: str = 'float32-strict') -> dict | None:
    """Keep the normal manifest closed; admit only two exact repaired Delay maps."""
    if manifest.get('voices') is None:
        from export_parity_contract import validate_manual_prepared
        validate_manual_prepared(provenance,manifest,snapshot)
        validate_manifest(manifest,numerical_profile=numerical_profile,manual_max_comparison=True)
        return None
    records = [r for r in provenance.get('adaptations', [])
               if r.get('name') == GEN_DELAY_ADAPTATION]
    if GEN_DELAY_ADAPTATION not in manifest.get('adaptations', []) and not records:
        validate_manifest(manifest, numerical_profile=numerical_profile)
        if numerical_profile == DBTOA_PROFILE:
            validate_dbtoa_prepared(provenance, manifest, snapshot)
        return None
    if (numerical_profile != 'float32-strict' or len(records) != 1 or
            manifest.get('adaptations') != ADAPTATIONS + [GEN_DELAY_ADAPTATION] or
            type(manifest.get('parameter_count')) is not int or manifest['parameter_count'] != 0):
        raise ExportError('Gen Delay repair requires its exact strict zero-parameter context')
    normal = dict(manifest, adaptations=ADAPTATIONS)
    validate_manifest(normal)
    digest = lambda value: hashlib.sha256(canonical(value)).hexdigest()
    files = snapshot.get('prepared_files_sha256', {})
    raw = provenance.get('raw_files_sha256', {})
    observed = {'prepared_map_sha256': digest(files), 'raw_map_sha256': digest(raw),
                'manifest_sha256': digest(manifest), 'adaptation_sha256': digest(records[0])}
    if (files != provenance.get('prepared_files_sha256') or
            observed['raw_map_sha256'] != manifest['source_tree_sha256'] or
            observed not in GEN_DELAY_PROOFS.values()):
        raise ExportError('Unknown Gen Delay repair source/metadata/runtime/inverse composition')
    return dict(observed)


def assert_hashes(records: dict[str, str]) -> None:
    for name, expected in records.items():
        if sha(Path(name)) != expected:
            raise ExportError(f"Cached build input changed: {name}")


def rewrite_wrapper(command: list[str], old_export: Path, export: Path, output: Path) -> list[str]:
    replacements = {"-I" + str(old_export): "-I" + str(export),
                    "-I" + str(old_export / "common"): "-I" + str(export / "common")}
    if any(command.count(key) != 1 for key in replacements) or command.count("-o") != 1:
        raise ExportError("Cached wrapper command does not have the exact two export paths/output")
    result = [replacements.get(argument, argument) for argument in command]
    result[result.index("-o") + 1] = str(output)
    return result


def checked_arena_bytes(value: int) -> int:
    if type(value) is not int or value not in ARENA_CHOICES:
        raise ExportError("Smoke arena ceiling must be 4096, 1048576 or 2097152 bytes")
    return value


def rewrite_arena_limit(command: list[str], maximum: int) -> list[str]:
    """Only this wrapper macro changes; cached support objects are untouched."""
    maximum = checked_arena_bytes(maximum)
    prefix = "-D" + ARENA_MACRO + "="
    flags = [argument for argument in command if argument.startswith(prefix)]
    if flags != [prefix + "4096u"]:
        raise ExportError("Cached wrapper must have exactly the original 4096-byte arena macro")
    return [prefix + str(maximum) + "u" if argument == flags[0] else argument for argument in command]


def link_recipe(ninja: str, compiler: Path, strip: Path, archives: dict) -> tuple[list[str], list[str]]:
    lines = [line.strip()[len("COMMAND = "):]
             for line in ninja.splitlines()
             if "COMMAND = cd " in line and " -o rnbo_s3_dynamic.app.elf && " in line]
    if len(lines) != 1:
        raise ExportError("Missing or ambiguous pinned project_elf link command")
    tokens = shlex.split(lines[0])
    try:
        start = tokens.index(str(compiler))
        link = tokens[start:tokens.index("&&", start)]
        stripping = tokens[tokens.index(str(strip)):]
    except ValueError as exc:
        raise ExportError("Unsupported cached linker/strip command") from exc
    expected = [str(compiler), *LINK_FLAGS, "esp-idf/main/libmain.a", "-Wl,-Bsymbolic",
                "-Wl,--exclude-libs,ALL", "-Wl,--start-group", archives["libm"]["path"],
                archives["libgcc"]["path"], "-Wl,--end-group", "-o", "rnbo_s3_dynamic.app.elf"]
    if link != expected or stripping != [str(strip), *STRIP_FLAGS, "rnbo_s3_dynamic.app.elf"]:
        raise ExportError("Cached final link differs from the reviewed private project_elf recipe")
    return link, stripping


def cache_value(text: str, name: str) -> Path:
    values = [line.split("=", 1)[1] for line in text.splitlines()
              if re.match(re.escape(name) + r":[^=]+=", line)]
    if len(values) != 1:
        raise ExportError(f"Missing or ambiguous cached setting: {name}")
    return Path(values[0]).resolve()


def inspect_cache(base: Path) -> dict:
    report = read_json(read_regular(base / "build-report.json", 8 * 1024 * 1024), "base module report")
    if (report.get("format") != "rnbo-esp32s3-dynamic-module-build" or report.get("imports") != [] or
            report.get("state_policy", {}).get("maximum_arena_bytes") != 4096):
        raise ExportError("Use an admitted zero-import module cache with the same 4096-byte arena ceiling")
    current = sources()
    if report.get("source_files_sha256") != current:
        raise ExportError("The cached SDK/compiler source epoch differs from the current files")
    if sha(base / "compile_commands.json") != report["compile_commands_sha256"]:
        raise ExportError("Cached compile commands changed")
    if sha(Path(report["artifact"]["path"])) != report["artifact"]["sha256"]:
        raise ExportError("Cached admitted module changed")
    validate_manifest(report["prepared_export"]["manifest"])
    if report["dynamic_abi"] != {"major": 1, "minor": 0,
                                "entry": "app_main argc1 request pointer in argv[0]", "explicit_result": True}:
        raise ExportError("Unreviewed cached dynamic ABI")
    description = read_json(read_regular(base / "project_description.json", 8 * 1024 * 1024), "cached project")
    compiler = Path(report["compiler"]["path"])
    if description.get("target") != "esp32s3" or description.get("c_compiler") != str(compiler):
        raise ExportError("Cached compiler/target mismatch")
    version = subprocess.check_output([str(compiler), "--version"], text=True, timeout=10)
    if version != report["compiler"]["version"]:
        raise ExportError("Compiler version differs from the cache")
    stem = compiler.name.removesuffix("gcc")
    tools = {name: compiler.with_name(stem + name) for name in ("ar", "strip", "nm")}
    commands = json.loads(read_regular(base / "compile_commands.json", 32 * 1024 * 1024))
    if type(commands) is not list or any(type(row) is not dict for row in commands):
        raise ExportError("Cached compile commands must be an array of command records")
    rows = [row for row in commands if row["file"] == str(ROOT / "module-sdk/dynamic/rnbo_s3_dynamic.cpp")]
    if len(rows) != 1:
        raise ExportError("Missing or ambiguous cached wrapper translation unit")
    row = rows[0]
    command = shlex.split(row["command"])
    if (command[0] != str(compiler.with_name(stem + "g++")) or
            command[-2:] != ["-c", row["file"]] or
            any(flag not in command for flag in ("-O2", "-fno-fast-math", "-ffp-contract=off",
                                                "-fno-strict-aliasing", "-fno-builtin",
                                                "-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u"))):
        raise ExportError("Unsupported cached wrapper compiler or strict flags")
    settings = (base / "CMakeCache.txt").read_text()
    old_export = cache_value(settings, "RNBO_S3_EXPORT_DIR")
    dependency_dir = cache_value(settings, "RNBO_S3_DEPENDENCIES_DIR")
    provenance, manifest, snapshot = verify_prepared(old_export)
    validate_manifest(manifest)
    if manifest != report["prepared_export"]["manifest"] or snapshot != report["prepared_snapshot"]:
        raise ExportError("Cached original export changed")
    lock = read_json(read_regular(ROOT / "loader-spike/dependencies.json", 1024 * 1024), "loader dependencies")
    for name, value in lock["components"].items():
        if inventory(dependency_dir / name) != value["files_sha256"]:
            raise ExportError(f"Cached pinned loader dependency changed: {name}")
        metadata = {key: value[key] for key in ("version", "source_tree_sha256", "source")}
        if report["dependencies"].get(name) != metadata:
            raise ExportError(f"Cached dependency report differs: {name}")
    archives = report["private_support_archives"]
    if set(archives) != {"libm", "libgcc"}:
        raise ExportError("Unexpected private support archives")
    for name, value in archives.items():
        if sha(Path(value["path"])) != value["sha256"]:
            raise ExportError(f"Private support archive changed: {name}")
    link, stripping = link_recipe((base / "build.ninja").read_text(), compiler, tools["strip"], archives)
    archive = base / "esp-idf/main/libmain.a"
    if subprocess.check_output([str(tools["ar"]), "t", str(archive)], text=True, timeout=10).splitlines() != MEMBERS:
        raise ExportError("Unexpected main archive members")
    files = [base / name for name in ("build-report.json", "compile_commands.json", "CMakeCache.txt",
                                    "project_description.json", "build.ninja", "sdkconfig", "config/sdkconfig.h")]
    files += [archive, compiler, Path(command[0]), *tools.values(), *[Path(x["path"]) for x in archives.values()],
              Path(report["artifact"]["path"])]
    for member in MEMBERS:
        members = [entry for entry in commands if Path(entry["file"]).name + ".obj" == member]
        if len(members) != 1:
            raise ExportError(f"Missing SDK object: {member}")
        obj = Path(members[0]["output"])
        if hashlib.sha256(subprocess.check_output([str(tools["ar"]), "p", str(archive), member], timeout=10)).hexdigest() != sha(obj):
            raise ExportError(f"Cached archive member differs from object: {member}")
        files.append(obj)
    binding = {str(path): sha(path) for path in files}
    return {"base": base, "report": report, "source_files_sha256": current, "binding": binding,
            "tools": tools, "compiler": compiler, "compiler_version": version, "command": command,
            "old_export": old_export, "old_prepared_snapshot": snapshot, "archives": archives,
            "link": link, "strip": stripping, "archive": archive,
            "dependencies_dir": dependency_dir, "dependency_files": {name: value["files_sha256"] for name, value in lock["components"].items()}}


def logged(command: list[str], path: Path, cwd: Path) -> float:
    started = time.monotonic()
    with path.open("w") as log:
        subprocess.run(command, cwd=cwd, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    return time.monotonic() - started


def build_one(identity: str, export: Path, directory: Path, cache: dict, max_arena_bytes: int = 4096, *, numerical_profile: str = "float32-strict") -> dict:
    max_arena_bytes = checked_arena_bytes(max_arena_bytes)
    provenance, manifest, snapshot = verify_prepared(export)
    repair = validate_smoke_prepared(provenance, manifest, snapshot, numerical_profile=numerical_profile)
    directory.mkdir()
    row = {"id": identity, "status": "pending", "imports": None, "commands": [], "timing_seconds": {},
           "prepared": {"path": str(export), "manifest": manifest, "snapshot": snapshot,
                        "provenance_sha256": sha(export / "provenance.json")},
           "arena_bytes_ceiling": max_arena_bytes, "arena_ceiling_is_structural_not_measured": True,
           "wrapper_max_arena_macro_bytes": max_arena_bytes,
           "dynamic_arena_contract": {"minimum_arena_bytes": 4096, "maximum_arena_bytes": max_arena_bytes,
               "maximum_state_bytes": "context_bytes+maximum_arena_bytes",
               "basis": "Exact wrapper compile macro and unchanged DESCRIBE source; runtime module_host checks actual info",
               "descriptor_executed_offline": False}}
    if repair is not None: row['gen_delay_fix_contract'] = repair
    target_archive = directory / "libmain.a"
    shutil.copyfile(cache["archive"], target_archive)
    output = directory / MEMBERS[0]
    command = rewrite_arena_limit(rewrite_wrapper(cache["command"], cache["old_export"], export, output), max_arena_bytes)
    row["commands"].append(command)
    try:
        row["timing_seconds"]["wrapper_compile"] = logged(command, directory / "compile.log", cache["base"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as failure:
        row.update(status="compile_failed", error=str(failure), compile_log_sha256=sha(directory / "compile.log"))
        if verify_prepared(export)[2] != snapshot:
            raise ExportError("Prepared files changed during rejected compilation")
        (directory / "build-report.json").write_bytes(canonical(row))
        return row
    command = [str(cache["tools"]["ar"]), "rD", str(target_archive), str(output)]
    row["commands"].append(command)
    row["timing_seconds"]["archive_replace"] = logged(command, directory / "archive.log", directory)
    artifact = directory / "rnbo_s3_dynamic.app.elf"
    command = [str(target_archive) if argument == "esp-idf/main/libmain.a" else
               str(artifact) if argument == "rnbo_s3_dynamic.app.elf" else argument for argument in cache["link"]]
    row["commands"].append(command)
    row["timing_seconds"]["module_link"] = logged(command, directory / "link.log", directory)
    shutil.copyfile(artifact, directory / "rnbo_s3_dynamic.app.elf.debug")
    command = [str(artifact) if argument == "rnbo_s3_dynamic.app.elf" else argument for argument in cache["strip"]]
    row["commands"].append(command)
    row["timing_seconds"]["strip"] = logged(command, directory / "strip.log", directory)
    raw = artifact.read_bytes()
    (directory / "rnbo_s3_dynamic.app.raw.elf").write_bytes(raw)
    data, normalization = normalize_zero_relocations(raw)
    inspection = inspect_module(data, allowed_imports=set())
    artifact.write_bytes(data)
    imports = subprocess.check_output([str(cache["tools"]["nm"]), "-D", "--undefined-only", str(artifact)], text=True, timeout=10)
    if imports.strip():
        raise ExportError("Final smoke module has unresolved imports")
    if verify_prepared(export)[2] != snapshot:
        raise ExportError("Prepared export changed during compilation")
    row.update(status="built", artifact={"path": str(artifact), "sha256": sha(artifact), "bytes": len(data)},
               imports=inspection["imports"], inspection=inspection, normalization=normalization,
               wrapper_object_sha256=sha(output), libmain_sha256=sha(target_archive),
               reused_support_objects=MEMBERS[1:])
    (directory / "build-report.json").write_bytes(canonical(row))
    return row


def build_batch(prepared_root: Path, base_build: Path, out: Path, max_arena_bytes: int = 4096, *, numerical_profile: str = "float32-strict") -> dict:
    max_arena_bytes = checked_arena_bytes(max_arena_bytes)
    if numerical_profile not in ("float32-strict", DBTOA_PROFILE):
        raise ExportError("Unsupported explicit smoke numerical profile")
    prepared_root, base_build = prepared_root.resolve(), base_build.resolve()
    if out.exists() or out.is_symlink():
        raise ExportError("Use a new output directory")
    out = out.resolve()
    if out.is_relative_to(prepared_root) or out.is_relative_to(base_build):
        raise ExportError("Output must be outside the read-only input and cache trees")
    entries = sorted(prepared_root.iterdir())
    if not entries or any(path.is_symlink() or not path.is_dir() or
                          not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", path.name) for path in entries):
        raise ExportError("Prepared root must contain named export directories only")
    snapshots = {}
    for export in entries:
        provenance, manifest, snapshot = verify_prepared(export)
        validate_smoke_prepared(provenance, manifest, snapshot, numerical_profile=numerical_profile)
        snapshots[export.name] = snapshot
    cache = inspect_cache(base_build)
    out.mkdir(parents=True)
    rows = []
    result = {"format": "rnbo-smoke-modules-v1", "base_build": str(base_build),
              "base_report_sha256": sha(base_build / "build-report.json"),
              "max_arena_bytes": max_arena_bytes, "cache_control_max_arena_bytes": 4096,
              "source_files_sha256": cache["source_files_sha256"],
              "cache_inputs_sha256": cache["binding"], "compiler": {"path": str(cache["compiler"]), "version": cache["compiler_version"]},
              "private_support_archives": cache["archives"], "modules": rows,
              "hardware_executed": False, "DSP_executed": False, "CPU_measured": False,
              "native_or_ELF_lifecycle_qualified": False,
              "tool_source_sha256": sha(Path(__file__)),
              "build_policy": "One wrapper compile/export, reused unchanged SDK objects, exact private project_elf link, existing normalized zero-import admission"}
    if numerical_profile != "float32-strict": result["numerical_profile"] = numerical_profile
    control = build_one("cache-control", cache["old_export"], out / "cache-control", cache, 4096)
    result["cache_control"] = control
    if control["status"] != "built":
        raise ExportError("Cache control wrapper did not compile")
    equal = Path(control["artifact"]["path"]).read_bytes() == Path(cache["report"]["artifact"]["path"]).read_bytes()
    result["cache_control_whole_ELF_equal"] = equal
    if not equal:
        raise ExportError("Recompiled cache control differs; use a new reviewed IDF base build")
    for export in entries:
        try:
            row = build_one(export.name, export, out / export.name, cache, max_arena_bytes, numerical_profile=numerical_profile)
        except (ExportError, ValueError, OSError, subprocess.SubprocessError) as failure:
            row = {"id": export.name, "status": "rejected", "error": f"{type(failure).__name__}: {failure}",
                   "prepared": {"path": str(export), "snapshot": snapshots[export.name]}}
        rows.append(row)
        print(json.dumps({"id": row["id"], "status": row["status"], "artifact": row.get("artifact")}), flush=True)
    if sources() != cache["source_files_sha256"] or sha(Path(__file__)) != result["tool_source_sha256"]:
        raise ExportError("SDK/compiler/tool sources changed during the batch")
    assert_hashes(cache["binding"])
    if verify_prepared(cache["old_export"])[2] != cache["old_prepared_snapshot"]:
        raise ExportError("Cached original export changed during the batch")
    for name, expected in cache["dependency_files"].items():
        if inventory(cache["dependencies_dir"] / name) != expected:
            raise ExportError("Pinned loader dependency changed during the batch")
    if any(verify_prepared(path)[2] != snapshots[path.name] for path in entries):
        raise ExportError("Prepared files changed during the batch")
    result.update(built=sum(row["status"] == "built" for row in rows),
                  failed=sum(row["status"] != "built" for row in rows),
                  source_cache_and_prepared_before_after_unchanged=True)
    result["result"] = "passed" if not result["failed"] else "completed_with_failures"
    (out / "batch-report.json").write_bytes(canonical(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--base-build", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-arena-bytes", type=int, choices=ARENA_CHOICES, default=4096,
                        help="Whole-batch module arena ceiling; cache control always remains 4096")
    parser.add_argument("--numerical-profile", choices=("float32-strict", DBTOA_PROFILE), default="float32-strict",
                        help="Explicit closed dbtoa candidate opt-in; ordinary smoke modules remain strict")
    args = parser.parse_args()
    try:
        report = build_batch(args.prepared_root, args.base_build, args.out, args.max_arena_bytes, numerical_profile=args.numerical_profile)
    except (ExportError, ValueError, OSError, subprocess.SubprocessError) as failure:
        parser.exit(1, f"Smoke module build rejected: {failure}\n")
    print(json.dumps({"result": report["result"], "built": report["built"], "failed": report["failed"],
                      "report": str(args.out.resolve() / "batch-report.json")}))
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()
