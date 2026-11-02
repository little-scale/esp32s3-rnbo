#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Quantify the optional cycle~ float32 profile against the strict host build.

This is a bounded numerical comparison on known exports, not a target speed
measurement. Original/runtime-correctness adaptations must match across builds.
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

from prepare import ExportError, canonical, read_json, read_regular

FLOAT_MAX_TOLERANCE = 2e-6
PCM_MAX_LSB_TOLERANCE = 1
FRAMES = 173*256


def require(condition,message):
    if not condition:raise ExportError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fraction_domain_check():
    to_float=lambda value:struct.unpack("<f",struct.pack("<f",value))[0]
    double_coefficient=3.81471181759574e-6
    float_coefficient=to_float(double_coefficient)
    changed=0;maximum=0.0
    for fraction_code in range(262144):
        reference=to_float(fraction_code*double_coefficient)
        candidate=to_float(fraction_code*float_coefficient)
        difference=abs(reference-candidate)
        changed+=difference!=0
        maximum=max(maximum,difference)
    return {"fraction_codes_tested":262144,"changed_fraction_results":changed,
            "maximum_absolute_fraction_difference":maximum,
            "double_coefficient":double_coefficient,"float32_coefficient":float_coefficient,
            "scope":"IEEE float32 rounding emulation of the fraction product; does not prove whole-patch invariance"}


def build_report(renderer: Path):
    report=read_json(read_regular(renderer.parent/"host-build.json",8*1024*1024),"host-build.json")
    require(sha(renderer)==report.get("artifact_sha256"),"Renderer artifact changed since its build report")
    manifest=report.get("prepared_manifest")
    require(isinstance(manifest,dict) and hashlib.sha256(canonical(manifest)).hexdigest()==report.get("manifest_sha256"),"Build manifest identity is inconsistent")
    return report


def render(renderer,output,arguments):
    process=subprocess.run([str(renderer.resolve()),"--output",str(output),"--float-output",str(output.with_suffix(".f32")),
                            "--blocks","173","--warmup","4","--seed","305419896",*arguments],
                           check=True,capture_output=True,text=True)
    stats=json.loads(process.stdout)
    require(stats.get("blocks")==173,"Renderer did not process the full comparison length")
    for key in ("late_platform_allocations","errors","invalid_samples"):
        require(stats.get(key)==0,f"Renderer fault: {key}")
    floats=[value[0] for value in struct.iter_unpack("<f",output.with_suffix(".f32").read_bytes())]
    require(len(floats)==FRAMES*2 and all(math.isfinite(v) for v in floats),"Invalid float render length/data")
    with wave.open(str(output),"rb") as audio:
        require((audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes())==(2,2,44100,FRAMES),"Invalid comparison WAV format")
        pcm=array.array("h",audio.readframes(FRAMES))
        if sys.byteorder!="little":pcm.byteswap()
        require(len(pcm)==FRAMES*2,"Truncated comparison PCM data")
    return stats,floats,pcm


def signal_metrics(values,frequencies,expected_each_peak):
    # Ignore the authored ADSR's first 100 ms when asserting steady-state MIDI
    # amplitude. Keep the complete buffer for the actual strict/opt diff.
    samples=values[4410*2::2]
    peak=max(abs(v) for v in samples)
    rms=math.sqrt(sum(v*v for v in samples)/len(samples))
    expected_rms=expected_each_peak*math.sqrt(len(frequencies)/2)
    require(abs(rms-expected_rms)<max(2e-5,expected_rms*0.015),"Steady-state RMS does not match the authored signal")
    result={"steady_state_rms":rms,"expected_steady_state_rms":expected_rms,"steady_state_peak":peak}
    if len(frequencies)==1:
        crossings=[]
        for index in range(1,len(samples)):
            if samples[index-1]<=0<samples[index]:crossings.append(index-1-samples[index-1]/(samples[index]-samples[index-1]))
        require(len(crossings)>3,"Signal does not have enough positive crossings")
        frequency=(len(crossings)-1)*44100/(crossings[-1]-crossings[0])
        require(abs(frequency-frequencies[0])<0.1,"Measured oscillator pitch is outside the comparison policy")
        require(abs(peak-expected_each_peak)<max(2e-5,expected_each_peak*0.005),"Unexpected oscillator peak")
        result["positive_crossing_frequency_hz"]=frequency
    else:
        projections=[]
        for frequency in frequencies:
            real=imaginary=0.0
            for index,value in enumerate(samples):
                phase=2*math.pi*frequency*index/44100
                real+=value*math.cos(phase);imaginary+=value*math.sin(phase)
            amplitude=2*math.hypot(real,imaginary)/len(samples)
            require(abs(amplitude-expected_each_peak)<expected_each_peak*0.05,"Polyphonic partial is missing or outside amplitude policy")
            projections.append({"frequency_hz":frequency,"amplitude":amplitude})
        result["frequency_projections"]=projections
    return result


def compare(strict_renderer: Path,optimized_renderer: Path,out: Path,fixture: str):
    require(not out.exists(),"Comparison output must be a new directory")
    strict=build_report(strict_renderer);optimized=build_report(optimized_renderer)
    left_manifest=strict["prepared_manifest"];right_manifest=optimized["prepared_manifest"]
    require(left_manifest.get("numerical_profile")=="float32-strict","Reference must be the strict numerical profile")
    require(right_manifest.get("numerical_profile")=="float32-cycle-v1","Candidate must be the optional float32-cycle-v1 profile")
    require(right_manifest.get("adaptations")==left_manifest.get("adaptations",[])+["rnbo-1.4.4-float32-cycle-v1"],"Profiles differ in transformations other than the cycle coefficients")
    for field in ("source_tree_sha256","parameter_schema_sha256","scheduler_time","class_name","role","voices"):
        require(left_manifest.get(field)==right_manifest.get(field),f"Profiles have different {field}")
    require(left_manifest.get("scheduler_time")=="float64","Scheduler precision changed")
    for field in ("compiler","compiler_version","cmake_build_type","cmake_build_settings","compiler_tools_sha256","integration_files_sha256"):
        require(strict.get(field)==optimized.get(field),f"Comparison build configuration differs: {field}")
    source_hashes=strict["prepared_snapshot"]["prepared_files_sha256"]
    candidate_hashes=optimized["prepared_snapshot"]["prepared_files_sha256"]
    require(source_hashes.keys()==candidate_hashes.keys(),"Profile file inventories differ")
    changed=[name for name in source_hashes if source_hashes[name]!=candidate_hashes[name]]
    require(changed==["rnbo_source.h"],f"Unexpected files differ between prepared profiles: {changed}")
    out.mkdir(parents=True)
    cases=[]
    if fixture=="sine":
        for frequency in (20,40,440,880,1320,10000):
            cases.append((f"hz-{frequency}",["--parameter","frequency",str(frequency)],[float(frequency)],0.2))
        cases.append(("normalized-880",["--normalized","--parameter","frequency",str((880-20)/9980)],[880.0],0.2))
    else:
        voices=int(fixture.removeprefix("midi"))
        require(voices in (1,2,4) and left_manifest.get("voices")==voices,"Fixture voice count differs from prepared manifest")
        for note in (24,69,96):
            for velocity in (1,100,127):
                frequency=440*2**((note-69)/12)
                cases.append((f"note-{note}-vel-{velocity}",["--midi","144",str(note),str(velocity)],
                              [frequency],0.1*(velocity/127)*0.8))
        if voices>1:
            notes=[60,67] if voices==2 else [60,64,67,71]
            arguments=[item for note in notes for item in ("--midi","144",str(note),"100")]
            cases.append(("all-voices",arguments,[440*2**((note-69)/12) for note in notes],0.1*(100/127)*0.8))
    results=[]
    for name,arguments,frequencies,peak in cases:
        strict_file=out/f"{name}-strict.wav";opt_file=out/f"{name}-cycle.wav"
        strict_stats,reference,reference_pcm=render(strict_renderer,strict_file,arguments)
        optimized_stats,candidate,candidate_pcm=render(optimized_renderer,opt_file,arguments)
        differences=[abs(a-b) for a,b in zip(reference,candidate)]
        max_difference=max(differences)
        rms_difference=math.sqrt(sum(v*v for v in differences)/len(differences))
        pcm_differences=[abs(a-b) for a,b in zip(reference_pcm,candidate_pcm)]
        require(max_difference<=FLOAT_MAX_TOLERANCE,f"{name}: float maximum difference {max_difference} exceeds {FLOAT_MAX_TOLERANCE}")
        require(max(pcm_differences)<=PCM_MAX_LSB_TOLERANCE,f"{name}: PCM differs by more than one LSB")
        results.append({"case":name,"arguments":arguments,"expected_frequencies_hz":frequencies,
                        "float_max_abs_difference":max_difference,"float_rms_difference":rms_difference,
                        "changed_float_samples":sum(v!=0 for v in differences),
                        "float_bit_identical":strict_file.with_suffix(".f32").read_bytes()==opt_file.with_suffix(".f32").read_bytes(),
                        "pcm_max_lsb_difference":max(pcm_differences),"changed_pcm_samples":sum(v!=0 for v in pcm_differences),
                        "pcm_bit_identical":reference_pcm==candidate_pcm,
                        "strict_metrics":signal_metrics(reference,frequencies,peak),
                        "optimized_metrics":signal_metrics(candidate,frequencies,peak),
                        "strict_stats":strict_stats,"optimized_stats":optimized_stats,
                        "strict_float_sha256":sha(strict_file.with_suffix(".f32")),"optimized_float_sha256":sha(opt_file.with_suffix(".f32")),
                        "strict_wav_sha256":sha(strict_file),"optimized_wav_sha256":sha(opt_file)})
    report={"format":"rnbo-numerical-profile-comparison","format_version":1,"result":"passed",
            "fixture":fixture,"profile":"float32-cycle-v1","reference":"float32-strict",
            "float_max_abs_tolerance":FLOAT_MAX_TOLERANCE,"pcm_max_lsb_tolerance":PCM_MAX_LSB_TOLERANCE,
            "observed_float_max_abs_difference":max(c["float_max_abs_difference"] for c in results),
            "observed_float_max_rms_difference":max(c["float_rms_difference"] for c in results),
            "observed_pcm_max_lsb_difference":max(c["pcm_max_lsb_difference"] for c in results),
            "all_float_bit_identical":all(c["float_bit_identical"] for c in results),
            "all_pcm_bit_identical":all(c["pcm_bit_identical"] for c in results),
            "fraction_domain_check":fraction_domain_check(),
            "cases":results,"build_reports":{"strict":strict,"optimized":optimized},
            "qualified_forms":"RNBO 1.4.4 authored fixtures, fixed256 scalar-frequency cycle~ kernel only",
            "target_performance_qualified":False,"reference_clock_precision":"float64 unchanged",
            "comparison_tool_sha256":sha(Path(__file__))}
    (out/"comparison.json").write_bytes(canonical(report))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-renderer",required=True,type=Path)
    parser.add_argument("--optimized-renderer",required=True,type=Path)
    parser.add_argument("--fixture",choices=("sine","midi1","midi2","midi4"),required=True)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try:report=compare(args.strict_renderer,args.optimized_renderer,args.out,args.fixture)
    except (ExportError,OSError,subprocess.CalledProcessError) as exc:parser.exit(1,f"Comparison failed: {exc}\n")
    print(json.dumps({"fixture":args.fixture,"cases":len(report["cases"]),"report":str((args.out/"comparison.json").resolve()),
                      "float_max_abs_difference":report["observed_float_max_abs_difference"],
                      "pcm_max_lsb_difference":report["observed_pcm_max_lsb_difference"]}))


if __name__=="__main__":main()
