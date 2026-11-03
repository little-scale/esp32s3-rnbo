#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile a prepared trusted Minimal Export into the native host render tool.

This development route deliberately produces neither an Xtensa ELF module nor
an uploadable package. ESP-IDF static firmware builds use tools/build_firmware.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from prepare import ExportError, canonical, read_json, read_regular


def verify_prepared(export: Path) -> tuple[dict, dict, dict]:
    provenance_data = read_regular(export / "provenance.json", 8 * 1024 * 1024)
    provenance = read_json(provenance_data, "provenance.json")
    hashes = provenance.get("prepared_files_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise ExportError("Missing prepared file hashes")
    for name, expected in hashes.items():
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ExportError("Invalid prepared path in provenance")
        actual = hashlib.sha256(read_regular(export / name, 16 * 1024 * 1024)).hexdigest()
        if actual != expected:
            raise ExportError(f"Prepared export changed after review: {name}")
    manifest_data = read_regular(export / "manifest.json", 1024 * 1024)
    manifest = read_json(manifest_data, "manifest.json")
    if hashlib.sha256(canonical(manifest)).hexdigest() != provenance.get("manifest_sha256"):
        raise ExportError("Prepared manifest changed after review")
    snapshot = {"prepared_files_sha256": hashes,
                "manifest_file_sha256": hashlib.sha256(manifest_data).hexdigest(),
                "provenance_file_sha256": hashlib.sha256(provenance_data).hexdigest()}
    return provenance, manifest, snapshot


def snapshot_files(root: Path, paths: list[Path]) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(read_regular(p, 16 * 1024 * 1024)).hexdigest()
            for p in paths}


def build(export: Path, build_dir: Path, cmake: str = "cmake") -> Path:
    export = export.resolve()
    provenance, manifest, prepared_snapshot = verify_prepared(export)
    root = Path(__file__).resolve().parents[2]
    integration_files = [root / "CMakeLists.txt", root / "module-sdk/include/rnbo_s3_module.h",
                         root / "module-sdk/wrapper/rnbo_s3_static.cpp",
                         root / "firmware/components/pcm_output/pcm_output.c",
                         root / "firmware/components/pcm_output/include/pcm_output.h",
                         root / "tests/native/render.cpp"]
    compiler_tool_files = [root / "host/compiler/build.py", root / "host/compiler/prepare.py",
                           root / "host/compiler/bounded_filters.py", root / "host/compiler/float32_delays.py",
                           root / "host/compiler/float32_audio.py", root / "host/compiler/omit_mtof_table.py",
                           root / "host/compiler/int32_wrap.py", root / "host/compiler/hoist_cycles.py",
                           root / "host/compiler/compact_average.py", root / "host/compiler/pink_output.py",
                           root / "host/compiler/wrap_finite.py", root / "host/compiler/wrap_finite.h",
                           root / "host/compiler/scalar_powers.py", root / "host/compiler/exact_delay44100.py",
                           root / "host/compiler/exact_delay44100.h", root / "host/compiler/hoist_filter_durations.py",
                           root / "host/compiler/hoist_train_reciprocal.py", root / "host/compiler/bounded_line_ramps.py",
                           root / "host/compiler/onepole_clamp.py", root / "host/compiler/stable_onepole.py",
                           root / "host/compiler/onepole_graphs.py", root / "host/compiler/regenerated_export.py",
                           root / "host/export/export.mjs", root / "host/export/patcher.mjs",
                           root / "host/export/inspect_onepole_graph.mjs",
                           root / "host/compiler/onepole_stable.h"]
    integration_hashes = snapshot_files(root, integration_files)
    compiler_tool_hashes = snapshot_files(root, compiler_tool_files)
    build_dir = build_dir.resolve()
    subprocess.run([cmake, "-S", str(root), "-B", str(build_dir), f"-DRNBO_S3_EXPORT_DIR={export}"], check=True)
    subprocess.run([cmake, "--build", str(build_dir), "--target", "rnbo_render", "--parallel"], check=True)
    if verify_prepared(export)[2] != prepared_snapshot:
        raise ExportError("Prepared source/metadata changed during compilation; discard this artifact")
    if snapshot_files(root, integration_files) != integration_hashes:
        raise ExportError("Integration sources changed during compilation; discard this artifact")
    if snapshot_files(root, compiler_tool_files) != compiler_tool_hashes:
        raise ExportError("Compiler tools changed during compilation; discard this artifact")
    executable = build_dir / "rnbo_render"
    if not executable.is_file():
        raise ExportError("Host build completed without the expected rnbo_render executable")
    cache = (build_dir / "CMakeCache.txt").read_text()
    compiler_lines = [line for line in cache.splitlines() if line.startswith("CMAKE_CXX_COMPILER:FILEPATH=")]
    compiler = compiler_lines[0].partition("=")[2] if compiler_lines else None
    compiler_version = subprocess.run([compiler, "--version"], check=True, capture_output=True, text=True).stdout if compiler else "unavailable"
    commands_path = build_dir / "compile_commands.json"
    commands_data = commands_path.read_bytes() if commands_path.is_file() else None
    commands = json.loads(commands_data) if commands_data is not None else []
    def command_source(entry):
        filename = Path(entry.get("file", ""))
        return (filename if filename.is_absolute() else Path(entry.get("directory", build_dir)) / filename).resolve()
    wrapper_commands = [entry for entry in commands if command_source(entry) == integration_files[2].resolve()]
    if len(wrapper_commands) > 1:
        raise ExportError("Expected one static wrapper compile command")
    build_type_lines = [line for line in cache.splitlines() if line.startswith("CMAKE_BUILD_TYPE:STRING=")]
    report = {"format_version": 1, "artifact": "native-host-render-tool",
              "artifact_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "manifest_sha256": provenance["manifest_sha256"],
              "prepared_manifest": manifest,
              "source_tree_sha256": manifest["source_tree_sha256"],
              "integration_files_sha256": integration_hashes,
              "compiler_tools_sha256": compiler_tool_hashes,
              "prepared_snapshot": prepared_snapshot,
              "preparer_sha256": provenance.get("preparer_sha256"),
              "compiler": compiler, "compiler_version": compiler_version,
              "cmake_build_type": build_type_lines[0].partition("=")[2] if build_type_lines else None,
              "compile_commands_sha256": hashlib.sha256(commands_data).hexdigest() if commands_data is not None else None,
              "wrapper_compile_command": wrapper_commands[0] if wrapper_commands else None,
              "cmake_cache_sha256": hashlib.sha256(cache.encode()).hexdigest(),
              "cmake_build_settings": {line.partition(":")[0]: line.partition("=")[2]
                                       for line in cache.splitlines()
                                       if line.startswith(("CMAKE_BUILD_TYPE:", "CMAKE_CXX_FLAGS", "CMAKE_C_FLAGS", "CMAKE_GENERATOR:")) and "=" in line},
              "cmake_version": subprocess.run([cmake, "--version"], check=True, capture_output=True, text=True).stdout,
              "hardware_qualified": False, "dynamic_loader_qualified": False}
    (build_dir / "host-build.json").write_bytes(canonical(report))
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--cmake", default="cmake")
    args = parser.parse_args()
    try:
        executable = build(args.export, args.build_dir, args.cmake)
    except (ExportError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")
    print(json.dumps({"host_renderer": str(executable)}))


if __name__ == "__main__":
    main()
