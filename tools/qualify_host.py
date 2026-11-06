#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild real RNBO fixtures and run host admission, runtime and signal checks.

Uses the caller's authorized RNBO 1.4.4 installation. Writes only a new output
directory. No device access or flashing. Host timings are not ESP32 timings.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def run(arguments: list[str], log_dir: Path, name: str, environment=None):
    with (log_dir / f"{name}.log").open("w") as log:
        result = subprocess.run(arguments, cwd=ROOT, env=environment,
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        sys.stderr.write((log_dir / f"{name}.log").read_text())
        raise RuntimeError(f"{name} failed; see {log_dir / (name + '.log')}")
    print(f"Passed: {name}", flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rnbo-dir", type=Path)
    args=parser.parse_args()
    out=(args.out or ROOT/"build"/"qualification"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).resolve()
    if out.exists(): parser.error("Use a new output directory to preserve earlier evidence")
    out.mkdir(parents=True)
    logs=out/"logs";logs.mkdir()
    environment=dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if args.rnbo_dir: environment["RNBO_DIR"]=str(args.rnbo_dir.expanduser().resolve())
    renderers={}
    for name,role in (("sine","main"),("fx-pass-through","fx")):
        raw=out/"exports"/name
        run(["node",str(ROOT/"archive/importer/export.mjs"),str(ROOT/"examples"/name/f"{name}.rnbopat"),"--out",str(raw)],logs,f"export-{name}",environment)
        for reference in ((False,True) if name=="sine" else (False,)):
            label=name+("-reference" if reference else "")
            prepared=out/"prepared"/label
            prepare=[sys.executable,str(ROOT/"host/compiler/prepare.py"),"--export",str(raw),"--out",str(prepared),"--class-name","rnbos3patch","--role",role]
            if reference: prepare.append("--no-runtime-fixes")
            run(prepare,logs,f"prepare-{label}",environment)
            build=out/"host"/label
            run(["cmake","-S",str(ROOT),"-B",str(build),f"-DRNBO_S3_EXPORT_DIR={prepared}","-DCMAKE_BUILD_TYPE=Release"],logs,f"configure-{label}",environment)
            run([sys.executable,str(ROOT/"host/compiler/build.py"),"--export",str(prepared),"--build-dir",str(build)],logs,f"build-{label}",environment)
            renderers[label]=build/"rnbo_render"
            if not reference:
                run(["cmake","--build",str(build),"--parallel"],logs,f"build-tests-{label}",environment)
                run(["ctest","--test-dir",str(build),"--output-on-failure"],logs,f"contracts-{label}",environment)
    for voices in (1,2,4):
        label=f"midi{voices}"
        raw=out/"exports"/label
        prepared=out/"prepared"/label
        build=out/"host"/label
        run(["node",str(ROOT/"archive/importer/export.mjs"),str(ROOT/"examples/midi-envelope/midi-envelope.rnbopat"),
             "--voices",str(voices),"--out",str(raw)],logs,f"export-{label}",environment)
        prepare=[sys.executable,str(ROOT/"host/compiler/prepare.py"),"--export",str(raw),"--out",str(prepared),
                 "--class-name","rnbos3patch","--role","main"]
        if voices>1:prepare.extend(["--midi-output","discard"])
        run(prepare,logs,f"prepare-{label}",environment)
        run(["cmake","-S",str(ROOT),"-B",str(build),f"-DRNBO_S3_EXPORT_DIR={prepared}",
             f"-DRNBO_S3_MIDI_TEST_VOICES={voices}","-DCMAKE_BUILD_TYPE=Release"],logs,f"configure-{label}",environment)
        run([sys.executable,str(ROOT/"host/compiler/build.py"),"--export",str(prepared),"--build-dir",str(build)],logs,f"build-{label}",environment)
        run(["cmake","--build",str(build),"--parallel"],logs,f"build-tests-{label}",environment)
        run(["ctest","--test-dir",str(build),"--output-on-failure"],logs,f"contracts-{label}",environment)
    environment["RNBO_S3_TEST_EXPORT"]=str(out/"exports/sine")
    run([sys.executable,"-m","unittest","discover","-s","host/compiler","-p","test_*.py","-v"],logs,"admission",environment)
    run([sys.executable,"-m","unittest","discover","-s","host/clients","-p","test_*.py","-v"],logs,"capture-client",environment)
    run([sys.executable,str(ROOT/"host/compiler/test_pipeline.py"),"--sine-renderer",str(renderers["sine"]),
         "--reference-renderer",str(renderers["sine-reference"]),"--fx-renderer",str(renderers["fx-pass-through"]),
         "--out",str(out/"numerical")],logs,"numerical",environment)
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for base in ("host","module-sdk","runtime","tests/native","tools","firmware/components/audio_lifecycle","firmware/components/pcm_output")
            for p in sorted((ROOT/base).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    hashes["CMakeLists.txt"]=hashlib.sha256((ROOT/"CMakeLists.txt").read_bytes()).hexdigest()
    report={"format_version":1,"evidence_kind":"host-qualification","completed_utc":datetime.now(timezone.utc).isoformat(),
            "result":"passed","integration_files_sha256":hashes,
            "numerical_report":"numerical/numerical-comparison.json",
            "host_contracts":["pcm_output","pcm_capture","audio_lifecycle","rnbo_contract","rnbo_runtime"],
            "midi_fixture_voice_counts":[1,2,4],
            "capture_client_adversarial_tests":True,
            "target_execution_tested":False,"target_timing_tested":False,"dynamic_loader_qualified":False}
    (out/"qualification.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(f"Host qualification complete: {out / 'qualification.json'}")

if __name__=="__main__":
    try: main()
    except (RuntimeError,OSError) as exc:
        sys.exit(str(exc))
