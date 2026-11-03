#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fresh native qualification of the 13 original wave4 fixtures / 39 cases.

Uses the real production dynamic C ABI wrapper and arena with host libc/libm.
No target/device access or CPU claim. Exit0 passes every gate; exit1 retains
qualification failures; exit2 retains an input/setup/integrity error report.
"""
from __future__ import annotations
import argparse
import array
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from build import verify_prepared
from generate_object_fixtures import DEFAULT_RECIPES, render
from prepare import prepare
import qualify_wave3 as native

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/objects/wave4"
CATALOG = FIXTURES / "catalog.json"
IDS = {"absolute-signal-stereo", "minimum-canonical-signal", "minimum-alias-signal",
       "maximum-canonical-signal", "maximum-alias-signal", "subtract-canonical-signal",
       "subtract-alias-signal", "equal-canonical-signal", "equal-alias-signal",
       "less-canonical-signal", "less-alias-signal", "codebox-arithmetic", "codebox-delta-state"}
QualificationError = native.QualificationError
require, sha, digest, save = native.require, native.sha, native.digest, native.save


def load_catalog(data=None):
    data = CATALOG.read_bytes() if data is None else data
    require(type(data) is bytes, "Catalog must be bytes")
    original = render(json.loads(DEFAULT_RECIPES.read_text()))
    require(data == original["catalog.json"], "Catalog differs from reviewed exact recipes")
    catalog = json.loads(data)
    require({f["id"] for f in catalog["fixtures"]} == IDS and len(catalog["fixtures"]) == 13 and sum(len(f["cases"]) for f in catalog["fixtures"]) == 39, "Expected the initial 13 exact fixtures / 39 cases")
    for f in catalog["fixtures"]:
        require((FIXTURES / f["patch"]).read_bytes() == original[f["patch"]], "Authored graph differs from its reviewed recipe")
    return catalog


class Oracle:
    def __init__(self, model):
        self.model = model

    def analyse(self, fixture, case, inputs, actual):
        # The reused observer passes arrays. Model API deliberately validates
        # actual wire planes; adapt container type without rounding any words.
        require(case["events"] == [] and case["warmup_blocks"] == 4, "Unknown event/warmup model")
        result = self.model.analyse(fixture["semantic"]["kind"],
                                    tuple(tuple(p) for p in inputs),
                                    tuple(tuple(p) for p in actual))
        return {**result, "passed": result["accuracy_pass"]}


def export_fixture(fixture, out, node, rnbo_dir):
    id = fixture["id"]
    command = [node, str(ROOT / "host/export/export.mjs"), str(FIXTURES / fixture["patch"]), "--out", str(out / "raw" / id)]
    if rnbo_dir is not None: command += ["--rnbo-dir", str(rnbo_dir)]
    native.run_logged(command, out / "logs" / (id + "-export.log"))
    prepare(out / "raw" / id, out / "prepared" / id, "rnbos3patch", "fx")
    provenance, manifest, snapshot = verify_prepared(out / "prepared" / id)
    require(manifest["numerical_profile"] == "float32-strict" and manifest["role"] == "fx" and manifest["audio_inputs"] == manifest["audio_outputs"] == 2 and manifest["parameter_count"] == 0, "Unexpected prepared interface/profile")
    require(not manifest.get("stable_onepole", False), "Wave4 requires strict defaults")
    native.emit({"stage": "prepared", "fixture": id, "surface": fixture["surface"]})
    return id, {"command": command, "manifest": manifest, "snapshot": snapshot,
                "raw_files_sha256": provenance["raw_files_sha256"]}


def make_plans(catalog, out, inputs):
    vectors, plans = {}, []
    for fixture in catalog["fixtures"]:
        for case in fixture["cases"]:
            frames = case["blocks"] * 256
            input_id = case["input"]["kind"]
            if input_id not in vectors:
                planes = inputs.generate(input_id, frames, seed=catalog["seed"])
                words = array.array("f", (value for pair in zip(*planes) for value in pair))
                path = out / "inputs" / (input_id + ".f32")
                path.write_bytes(words.tobytes())
                vectors[input_id] = {"path": str(path.relative_to(out)), "sha256": sha(path),
                                     "frames": frames, "channels": 2, "spec": case["input"]}
            record = vectors[input_id]
            require(record["frames"] == frames, "Input ID reused at a different frame count")
            path = out / "plans" / (fixture["id"] + "--" + case["id"] + ".bin")
            # The unchanged original wave3 observer's version1 no-event wire
            # protocol. No private DSP state or alternate runtime is injected.
            path.write_bytes(struct.pack("<8I", 0x57563331, 1, case["blocks"], case["warmup_blocks"], catalog["seed"], 0, case["lifecycles"], 0))
            plans.append({"fixture_id": fixture["id"], "id": case["id"], "blocks": case["blocks"],
                          "warmup_blocks": case["warmup_blocks"], "lifecycles": case["lifecycles"],
                          "parameter_schema": [], "events": [], "plan_file": str(path.relative_to(out)),
                          "plan_sha256": sha(path), "input_file": record["path"],
                          "input_sha256": record["sha256"], "input_spec": case["input"]})
    save(out / "input-index.json", {"format": "wave4-authoritative-input-cache-v1", "vectors": vectors})
    save(out / "plans.json", {"format": "wave4-actual-CABI-no-event-plans-v1", "plans": plans})
    return plans, {r["path"]: r["sha256"] for r in vectors.values()}


def summarize(catalog, builds, out):
    comparisons, reconstruction = native.compare_results(catalog, builds, out)
    expected = sum(len(f["cases"]) for f in catalog["fixtures"])
    require(len(comparisons) == expected, "Missing case comparisons")
    health = all(x["completed"] for x in comparisons) and all(
        not c["stderr"] and c.get("protocol", {}).get("passed", False)
        for b in builds.values() for c in b["cases"].values())
    compatibility = len(reconstruction) == expected * 2 and all(
        x.get("statistics_exact", False) and all(x.get("files_byte_identical", {}).values()) for x in comparisons) and all(
        x["statistics_equal"] and all(x["output_bytes_equal"].values()) for x in reconstruction)
    accuracy = all(x.get("accuracy_evaluated", False) and x.get("accuracy_pass", False) for x in comparisons)
    return {"comparisons": comparisons, "reconstruction": reconstruction,
            "health_passed": health, "compatibility_passed": compatibility,
            "independent_accuracy_passed": accuracy,
            "qualification_passed": health and compatibility and accuracy,
            "failed_accuracy_cases": [{"fixture": x["fixture"], "id": x["id"]} for x in comparisons if not x.get("accuracy_pass", False)],
            "paired_channel_words": sum(x.get("captured_channel_words", 0) for x in comparisons),
            "protocol_counts": {k: sum(c.get("protocol", {}).get(k, 0) for b in builds.values() for c in b["cases"].values()) for k in ("lifecycle_runs", "event_readback_records", "block_readback_records")}}


def qualify(output, rnbo_dir=None, *, jobs=2):
    require(type(jobs) is int and 1 <= jobs <= 4, "jobs must be an integer 1..4")
    out = native.validate_output(Path(output))
    catalog = load_catalog()
    require(sys.byteorder == "little" and struct.calcsize("f") == 4, "Little-endian binary32 host required")
    require(sha(native.NATIVE / "probe.cpp") == native.ORIGINAL_PROBE_SHA256, "Reviewed native observer changed")
    node, cc, cxx = (shutil.which(name) for name in ("node", "cc", "c++"))
    require(node and cc and cxx, "Node and a C/C++ toolchain are required")
    paths = [Path(__file__), DEFAULT_RECIPES, CATALOG, FIXTURES / "models.py", FIXTURES / "inputs.py", native.NATIVE / "probe.cpp", ROOT / "host/export/export.mjs", ROOT / "host/export/patcher.mjs"]
    paths += [FIXTURES / f["patch"] for f in catalog["fixtures"]] + [ROOT / n for n in native.SDK_SOURCES]
    paths += sorted(p for p in (ROOT / "host/compiler").iterdir() if p.suffix in (".py", ".h") and not p.name.startswith("test_"))
    paths = sorted(set(paths)); before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    tools = {p: {"sha256": sha(p), "version": subprocess.check_output([p, "--version"], text=True)} for p in (node, cc, cxx)}
    out.mkdir(parents=True, exist_ok=False)
    report = {"format": "rnbo-wave4-native-qualification-v1", "source_files_sha256": before,
              "tools": tools, "python_version": sys.version, "fixture_count": 13, "case_count": 39,
              "surface_identity": "11 exact patcher spellings and two original codebox programs; no alias inheritance",
              "hardware_executed": False, "target_compiled": False, "target_performance_measured": False,
              "ELF_lifecycle_tested": False, "qualification_passed": False,
              "native_support_policy": "Actual production dynamic wrapper/arena and PCM; host libc/libm; support.cpp/lifecycle.cpp NOT linked. Constructor/finalizer counters are native stubs, not ELF proof.",
              "direct_observer_policy": "Delta right output must copy all raw input words, including signed zero; operation signs diagnostic.",
              "scope": "Strict defaults, FX2in2out,44100/256,finite input[-1,1],no events/params,zero warm4,two reconstructions/case"}
    try:
        for name in ("logs", "inputs", "plans"): (out / name).mkdir()
        for name in before:
            dest = out / "sources" / name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / name, dest)
        tag = digest(str(out).encode())[:12]
        inputs = native.load_module("wave4_inputs_" + tag, out / "sources" / str((FIXTURES / "inputs.py").relative_to(ROOT)))
        model = native.load_module("wave4_models_" + tag, out / "sources" / str((FIXTURES / "models.py").relative_to(ROOT)))
        oracle = Oracle(model)
        with ThreadPoolExecutor(jobs) as pool:
            exports = dict(pool.map(lambda f: export_fixture(f, out, node, rnbo_dir), catalog["fixtures"]))
        report["exports"] = exports
        plans, vectors = make_plans(catalog, out, inputs)
        report["input_vectors_sha256"] = vectors
        fixtures = {f["id"]: {**copy.deepcopy(f), "object_spelling": f["source"].get("spelling", "codebox~")} for f in catalog["fixtures"]}
        with ThreadPoolExecutor(jobs) as pool:
            builds = dict(pool.map(lambda pair: native.compile_and_run(pair, fixtures, plans, out, cc, cxx, oracle), [(id, mode) for id in fixtures for mode in ("O3", "UBSan")]))
        report["builds"] = builds
        report.update(summarize(catalog, builds, out))
        require(before == {str(p.relative_to(ROOT)): sha(p) for p in paths}, "Source cohort changed during execution")
        require(all(sha(p) == info["sha256"] for p, info in tools.items()), "Compiler/Node changed")
        require(all(sha(out / p) == h for p, h in vectors.items()), "Input vectors changed")
        require(all(sha(out / p["plan_file"]) == p["plan_sha256"] for p in plans), "Wire plans changed")
        require(all(verify_prepared(out / "prepared" / id)[2] == item["snapshot"] for id, item in exports.items()), "Prepared inputs changed")
        require(all(sha(out / f["path"]) == f["sha256"] for b in builds.values() for c in b["cases"].values() for f in c.get("files", {}).values()), "Captured files changed")
        report["before_after_hashes_verified"] = True
        report["status"] = "passed" if report["qualification_passed"] else "retained_qualification_failures"
    except Exception as exc:
        report.update(status="setup_or_integrity_error", error=type(exc).__name__ + ": " + str(exc))
        save(out / "report.json", report)
        raise QualificationError(f'{exc}; partial report retained at {out / "report.json"}') from exc
    # Exclude only this top-level report, not nested per-build report.json files.
    report["artifacts"] = {str(p.relative_to(out)): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(out.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p != out / "report.json"}
    save(out / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="Fresh directory below this repository's build/")
    parser.add_argument("--rnbo-dir", type=Path, help="Authorised local RNBO1.4.4 package")
    parser.add_argument("--jobs", type=int, default=2, help="Independent native builds,1..4")
    args = parser.parse_args()
    try:
        report = qualify(args.out, args.rnbo_dir, jobs=args.jobs)
    except (QualificationError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Native qualification rejected: {exc}\n")
    print(json.dumps({"report": str(args.out.resolve() / "report.json"), "status": report["status"], "health_passed": report["health_passed"], "compatibility_passed": report["compatibility_passed"], "independent_accuracy_passed": report["independent_accuracy_passed"], "failed_accuracy_cases": report["failed_accuracy_cases"]}))
    raise SystemExit(0 if report["qualification_passed"] else 1)


if __name__ == "__main__":
    main()
