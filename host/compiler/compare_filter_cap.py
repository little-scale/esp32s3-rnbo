#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the authorized3sawsDrone3 cap40 profile against its large-ring source.

Native host evidence only. Output differences are measured, never described as
bit-identical or as ESP32 performance. The editable patch is not changed.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition: raise ValueError(message)


def read_audio(path, words):
    audio = array.array("f"); audio.frombytes(path.read_bytes())
    if sys.byteorder != "little": audio.byteswap()
    require(len(audio) == words and all(math.isfinite(x) for x in audio), "Incomplete or non-finite float render")
    return audio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-renderer", required=True, type=Path)
    parser.add_argument("--bounded-renderer", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--blocks", default=4096, type=int)
    args = parser.parse_args()
    require(1 <= args.blocks <= 100000, "blocks must be1..100000")
    args.out.mkdir(parents=True, exist_ok=True)
    reports = {}
    renderers = {"reference": args.reference_renderer.resolve(), "bounded": args.bounded_renderer.resolve()}
    for name, renderer in renderers.items():
        reports[name] = json.loads((renderer.parent / "host-build.json").read_text())
        require(digest(renderer) == reports[name]["artifact_sha256"], f"{name} executable changed since compilation")
    reference = reports["reference"]["prepared_manifest"]; bounded = reports["bounded"]["prepared_manifest"]
    for field in ("editable_source_sha256", "source_tree_sha256", "numerical_profile", "parameter_schema_sha256", "sample_rate", "block_frames", "scheduler_time"):
        require(reference[field] == bounded[field], f"Source/profile mismatch: {field}")
    require(reference["numerical_profile"] == "float32-strict", "Comparison expects the unchanged strict numerical profile")
    require(reference.get("filter_delay_max_ms") is None and bounded.get("filter_delay_max_ms") == 40, "Comparison requires original and explicit cap40 variants")
    for field in ("integration_files_sha256", "compiler", "compiler_version", "cmake_build_type", "cmake_build_settings"):
        require(reports["reference"][field] == reports["bounded"][field], f"Native integration/compiler mismatch: {field}")
    cases = []
    for name, settings in (
        ("default", {}),
        ("fast-full-modulation", {"lfo-rate": 1, "lfo-depth": 1, "vib-rate": 20, "vib-depth": 2}),
        ("high-feedback", {"lfo-rate": 0.7, "lfo-depth": 1, "comb-ff": 0.98, "comb-fb": 0.98, "delay-time": 40, "delay-fb": 0.9}),
    ):
        audio = {}; statistics = {}; artifacts = {}
        for variant, renderer in renderers.items():
            pcm = args.out / f"{name}-{variant}.wav"; floats = pcm.with_suffix(".f32")
            command = [str(renderer), "--output", str(pcm), "--float-output", str(floats),
                       "--blocks", str(args.blocks), "--warmup", "1", "--seed", "12345",
                       "--arena-bytes", str(4194304 if variant == "reference" else 1048576)]
            for identity, value in settings.items(): command += ["--parameter", identity, str(value)]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            stats = json.loads(result.stdout)
            for field in ("late_platform_allocations", "errors", "invalid_samples"):
                require(stats[field] == 0, f"Unhealthy {variant}/{name}: {field}")
            require(stats["blocks"] == args.blocks, "Renderer did not finish requested work")
            statistics[variant] = stats
            audio[variant] = read_audio(floats, args.blocks * 256 * 2)
            artifacts[variant] = {"wav_sha256": digest(pcm), "float_sha256": digest(floats)}
        left, right = audio["reference"], audio["bounded"]
        square_a = sum(x*x for x in left); square_b = sum(x*x for x in right)
        error_square = sum((a-b)**2 for a, b in zip(left, right))
        maximum = max(abs(a-b) for a, b in zip(left, right))
        peak = max(map(abs, left))
        cases.append({"case": name, "parameters": settings, "sample_words": len(left),
                      "maximum_absolute_error": maximum,
                      "maximum_error_relative_reference_peak": maximum/peak if peak else None,
                      "rms_error": math.sqrt(error_square/len(left)),
                      "error_rms_relative_reference_rms": math.sqrt(error_square/square_a) if square_a else None,
                      "relative_rms_level_difference": abs(math.sqrt(square_b/square_a)-1) if square_a else None,
                      "bit_identical": left == right,
                      "pcm_headroom_exceeded_sample_words": {variant: sum(abs(x)>2 for x in values) for variant, values in audio.items()},
                      "statistics": statistics, "artifacts": artifacts})
    report = {"evidence_kind": "native-host-bounded-filter-numerical-comparison",
              "claim": "Measured source-preserving Float64 small-ring differences; no bit-identity claim",
              "source_sha256": reference["editable_source_sha256"], "maximum_delay_ms": 40,
              "conversion": "original generated mstosamps, unchanged", "storage": "double, unchanged",
              "sample_rate": 44100, "block_frames": 256, "blocks_per_case": args.blocks,
              "seed": 12345, "warmup_blocks": 1, "cases": cases,
              "build_reports": reports, "hardware_executed": False, "target_performance_qualified": False}
    destination = args.out / "comparison.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"report": str(destination.resolve()), "cases": len(cases),
                      "maximum_absolute_error": max(case["maximum_absolute_error"] for case in cases),
                      "maximum_relative_rms_level_difference": max(case["relative_rms_level_difference"] for case in cases)}))


if __name__ == "__main__": main()
