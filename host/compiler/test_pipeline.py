#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare real native host renders against reference builds and known signals.

All renderers must come from the same RNBO 1.4.4 raw fixtures and wrapper. The
reference renderer is prepared with --no-runtime-fixes. This checks numerical
output on the host and deliberately makes no ESP32 performance claim.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def render(renderer: Path, output: Path, settings: list[str]) -> dict:
    result = subprocess.run([str(renderer.resolve()), "--output", str(output), "--float-output", str(output.with_suffix(".f32")),
                             "--blocks", "173", "--warmup", "1", *settings],
                            check=True, capture_output=True, text=True)
    stats = json.loads(result.stdout)
    require(stats["blocks"] == 173, "Renderer did not process the requested blocks")
    for field in ("late_platform_allocations", "errors", "invalid_samples"):
        require(stats[field] == 0, f"Unexpected {field}: {stats[field]}")
    return stats


def samples(path: Path) -> tuple[list[float], list[float]]:
    with wave.open(str(path), "rb") as audio:
        require((audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (2, 2, 44100, 173 * 256),
                "Unexpected PCM channel/sample/rate/frame format")
        values = array.array("h", audio.readframes(audio.getnframes()))
        if sys.byteorder != "little":
            values.byteswap()
    return ([v / 32767.0 for v in values[0::2]], [v / 32767.0 for v in values[1::2]])


def float_samples(path: Path) -> tuple[list[float], list[float]]:
    data = path.with_suffix(".f32").read_bytes()
    require(len(data) == 173 * 256 * 2 * 4, "Float companion has wrong byte length")
    pairs = list(struct.iter_unpack("<ff", data))
    require(all(math.isfinite(a) and math.isfinite(b) for a, b in pairs), "Float output contains non-finite samples")
    return ([a for a, _ in pairs], [b for _, b in pairs])


def measure(values: list[float], expected_hz: float) -> dict:
    crossings = []
    for i in range(1, len(values)):
        if values[i - 1] <= 0 < values[i]:
            crossings.append(i - 1 - values[i - 1] / (values[i] - values[i - 1]))
    require(len(crossings) > 3, "Signal has insufficient positive zero crossings")
    hz = (len(crossings) - 1) * 44100 / (crossings[-1] - crossings[0])
    rms = math.sqrt(sum(v * v for v in values) / len(values))
    sine = cosine = 0.0
    for i, value in enumerate(values):
        phase = 2 * math.pi * expected_hz * i / 44100
        sine += value * math.sin(phase)
        cosine += value * math.cos(phase)
    amplitude = 2 * math.hypot(sine, cosine) / len(values)
    return {"positive_crossing_frequency_hz": hz, "rms": rms,
            "peak": max(abs(v) for v in values), "fundamental_amplitude": amplitude}


def correlation_amplitude(values: list[float], hz: float) -> float:
    return measure(values, hz)["fundamental_amplitude"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sine-renderer", type=Path, required=True)
    parser.add_argument("--reference-renderer", type=Path, required=True)
    parser.add_argument("--fx-renderer", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    build_reports = {label: json.loads((renderer.parent / "host-build.json").read_text())
                     for label, renderer in (("prepared", args.sine_renderer), ("reference", args.reference_renderer), ("fx", args.fx_renderer))}
    for label, renderer in (("prepared", args.sine_renderer), ("reference", args.reference_renderer), ("fx", args.fx_renderer)):
        require(build_reports[label]["artifact_sha256"] == sha(renderer), f"{label} renderer changed after its build report")
        manifest = build_reports[label]["prepared_manifest"]
        encoded = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
        require(hashlib.sha256(encoded).hexdigest() == build_reports[label]["manifest_sha256"], f"{label} build manifest identity is inconsistent")
    require(build_reports["prepared"]["source_tree_sha256"] == build_reports["reference"]["source_tree_sha256"], "Reference uses different raw source/runtime")
    require(build_reports["reference"]["prepared_manifest"]["adaptations"] == [], "Reference is not an unmodified-runtime build")
    fixes = ["rnbo-1.4.4-list-copy-bounds-v1", "rnbo-1.4.4-list-move-inline-storage-v1",
             "rnbo-1.4.4-list-cross-capacity-assignment-v1", "rnbo-1.4.4-nested-clock-target-v1",
             "rnbo-1.4.4-defined-imul-v1"]
    require(build_reports["prepared"]["prepared_manifest"]["adaptations"] == fixes,
            "Prepared oscillator is missing the declared correctness-fix profile")
    require(build_reports["fx"]["prepared_manifest"]["adaptations"] == fixes,
            "Prepared FX is missing the declared correctness-fix profile")
    for label in ("reference", "fx"):
        require(build_reports[label]["integration_files_sha256"] == build_reports["prepared"]["integration_files_sha256"], "Renderer wrapper/integration source revisions differ")
        for field in ("compiler", "compiler_version", "cmake_build_type", "cmake_build_settings", "compiler_tools_sha256"):
            require(build_reports[label][field] == build_reports["prepared"][field], f"Renderer {field} differs between comparison builds")
    cases = []
    for name, parameters, frequency, peak in (
            ("default", [], 440, 0.1),
            ("parameter", ["--parameter", "frequency", "880", "--parameter", "level", "0.1"], 880, 0.05),
            ("normalized", ["--normalized", "--parameter", "level", "0.1", "--parameter", "frequency", str((880-20)/(10000-20))], 880, 0.05)):
        output = args.out / f"sine-{name}.wav"
        reference = args.out / f"reference-{name}.wav"
        stats = render(args.sine_renderer, output, parameters)
        reference_stats = render(args.reference_renderer, reference, parameters)
        require(output.read_bytes() == reference.read_bytes(), f"Prepared/reference PCM differs for {name}")
        require(output.with_suffix(".f32").read_bytes() == reference.with_suffix(".f32").read_bytes(),
                f"Prepared/reference float32 differs for {name}")
        left, right = samples(output)
        require(left == right, f"Unexpected oscillator stereo difference for {name}")
        measurements = measure(left, frequency)
        require(abs(measurements["positive_crossing_frequency_hz"] - frequency) < 0.02, f"Wrong oscillator pitch for {name}: {measurements}")
        require(abs(measurements["peak"] - peak) < 0.00005, f"Wrong PCM amplitude for {name}: {measurements}")
        require(abs(measurements["rms"] - peak / math.sqrt(2)) < 0.0001, f"Wrong RMS for {name}: {measurements}")
        float_left, float_right = float_samples(output)
        require(float_left == float_right, f"Unexpected oscillator stereo float difference for {name}")
        float_measurements = measure(float_left, frequency)
        require(abs(float_measurements["positive_crossing_frequency_hz"] - frequency) < 0.02,
                f"Wrong oscillator float pitch for {name}: {float_measurements}")
        require(abs(float_measurements["peak"] - peak * 2) < 0.000001,
                f"Wrong oscillator float amplitude for {name}: {float_measurements}")
        cases.append({"case": name, "expected_hz": frequency, "expected_pcm_peak": peak,
                      "measurements": measurements, "pcm_sha256": sha(output),
                      "reference_pcm_sha256": sha(reference), "pcm_bit_identical": True,
                      "float_measurements": float_measurements,
                      "float_sha256": sha(output.with_suffix(".f32")),
                      "reference_float_sha256": sha(reference.with_suffix(".f32")), "float_bit_identical": True,
                      "prepared_stats": stats, "reference_stats": reference_stats})
    fx_output = args.out / "fx-stereo.wav"
    fx_stats = render(args.fx_renderer, fx_output, [])
    left, right = samples(fx_output)
    left_measurements = measure(left, 440)
    right_measurements = measure(right, 660)
    require(abs(left_measurements["positive_crossing_frequency_hz"] - 440) < 0.02, "FX left input was not preserved")
    require(abs(right_measurements["positive_crossing_frequency_hz"] - 660) < 0.02, "FX right input was not preserved")
    require(correlation_amplitude(left, 660) < 0.001 and correlation_amplitude(right, 440) < 0.001, "FX stereo channels crossed or mixed")
    require(abs(left_measurements["peak"] - 0.1) < 0.00005 and abs(right_measurements["peak"] - 0.1) < 0.00005, "FX pass-through gain changed")
    fx_float_left, fx_float_right = float_samples(fx_output)
    fx_error = [max(abs(v - 0.2 * math.sin(2 * math.pi * hz * i / 44100)) for i, v in enumerate(channel))
                for channel, hz in ((fx_float_left, 440), (fx_float_right, 660))]
    require(max(fx_error) < 1e-6, "FX float output does not preserve the expected independent input signals")
    report = {"evidence_kind": "native-host-numerical-comparison", "sample_rate": 44100,
              "block_frames": 256, "frames_per_case": 173 * 256, "warmup_blocks": 1,
              "pcm_headroom": 0.5, "comparison": "bit-identical interleaved IEEE float32 little endian plus int16 WAV",
              "reference": "same raw RNBO source and runtime, without the recorded runtime correctness fixes",
              "renderer_sha256": {"prepared": sha(args.sine_renderer), "reference": sha(args.reference_renderer), "fx": sha(args.fx_renderer)},
              "build_reports": build_reports,
              "oscillator_cases": cases,
              "fx_stereo": {"left": left_measurements, "right": right_measurements,
                            "pcm_sha256": sha(fx_output), "float_sha256": sha(fx_output.with_suffix(".f32")),
                            "float_max_error_against_independent_sines": fx_error, "stats": fx_stats},
              "target_performance_qualified": False, "dynamic_loader_qualified": False,
              "comparison_limit": "Known host fixtures only; excludes target code generation and audio hardware"}
    (args.out / "numerical-comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": "passed", "report": str((args.out / "numerical-comparison.json").resolve()),
                      "oscillator_cases": len(cases), "fx_stereo_channels": "passed"}))


if __name__ == "__main__":
    main()
