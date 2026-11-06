#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and measure original object fixtures in a fresh, identity-bound directory.

No board access. Unsupported optional generated forms are reported explicitly;
they never weaken preparation guards or count as a successful comparison.
"""
from __future__ import annotations
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

from prepare import ExportError, NUMERICAL_PROFILES, prepare

ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition: raise ValueError(message)


def channels(path: Path, frames: int) -> tuple[list[float], list[float]]:
    require(path.stat().st_size == frames * 8, "Truncated/oversized stereo float render")
    values = array.array("f"); values.frombytes(path.read_bytes())
    if sys.byteorder != "little": values.byteswap()
    require(all(math.isfinite(x) for x in values), "Non-finite render")
    return list(values[::2]), list(values[1::2])


def rms(values):
    return math.sqrt(sum(x*x for x in values) / len(values)) if values else 0.0


def projection(values, frequency, rate=44100):
    omega = 2 * math.pi * frequency / rate
    sine = sum(x*math.sin(omega*i) for i,x in enumerate(values))
    cosine = sum(x*math.cos(omega*i) for i,x in enumerate(values))
    return 2*math.hypot(sine, cosine)/len(values)


def stimulus(fixture, case, frames):
    settings = fixture["stimulus"] | case.get("stimulus",{})
    kind = settings["kind"]; left = []; right = []
    for i in range(frames):
        t = i/44100
        if kind in ("midi-stereo-v1","frequency-stereo-v1"):
            base = settings["base"] if kind == "midi-stereo-v1" else settings["frequency"]
            left.append(base+settings["depth"]*math.sin(2*math.pi*settings["rate"]*t))
            right.append(settings["pilot_amplitude"]*math.sin(2*math.pi*settings["pilot_frequency"]*t))
        elif kind == "reson-stereo-v1":
            left.append(settings["level"]*math.sin(2*math.pi*settings["excitation"]*t))
            right.append(settings["center"]+settings["depth"]*math.sin(2*math.pi*settings["rate"]*t))
        else: raise ValueError(f"Unknown external stimulus: {kind}")
    return array.array("f",left),array.array("f",right)


def semantic_checks(fixture, case, audio, inputs=None):
    s = fixture["semantic"]; kind = s["kind"]; params = case["parameters"]
    result = {"kind": kind, "channels": [{"minimum": min(v), "maximum": max(v),
                "mean": sum(v)/len(v), "rms": rms(v), "peak": max(map(abs,v))} for v in audio]}
    if kind.endswith("-fx"):
        require(inputs is not None,"FX semantics need their explicit input capture")
        settings = fixture["stimulus"] | case.get("stimulus",{})
        result["input_channels"] = [{"minimum":min(v),"maximum":max(v),"rms":rms(v)} for v in inputs]
        if kind == "mtof-fx":
            error = max(abs(y-s["tuning"]*math.exp(.057762265*(pitch-69))*s["frequency_scale"]) for pitch,y in zip(inputs[0],audio[s["frequency_channel"]]))
            pilot_error = max(abs(a-b) for a,b in zip(inputs[1],audio[s["pilot_output_channel"]]))
            result.update(analytic_maximum_absolute_error=error,pilot_maximum_absolute_error=pilot_error)
            require(error <= s["analytic_maximum_absolute_error"] and pilot_error == 0,"FX mtof analytic/pilot mismatch")
            if settings["depth"]:
                transitions = sum(a != b for a,b in zip(inputs[0],inputs[0][1:]))
                result["varying_pitch_sample_transitions"] = transitions
                require(transitions > len(inputs[0])*.9,"FX mtof input is mostly cached")
        elif kind == "saw-fx":
            values = audio[s["audio_channel"]]
            require(all(a == b for a,b in zip(inputs[1],audio[s["pilot_output_channel"]])),"FX saw pilot mismatch")
            level = params.get("level",s["level_default"])
            if level == 0: require(max(map(abs,values)) == 0,"FX saw silence mismatch")
            else:
                require(rms(values) > level*.05,"FX saw audio missing")
                if settings["depth"] == 0:
                    frequency = settings["frequency"]; fundamental = projection(values,frequency)
                    require(fundamental > level*.05,"FX saw fundamental missing")
                    result["fundamental_amplitude"] = fundamental
                    if frequency <= 440:
                        second = projection(values,2*frequency)/fundamental; third = projection(values,3*frequency)/fundamental
                        require(.35 < second < .65 and .2 < third < .45,"FX saw harmonic mismatch")
                        result.update(second_to_fundamental_ratio=second,third_to_fundamental_ratio=third)
        elif kind == "reson-fx":
            require(all(a == b for a,b in zip(inputs[0],audio[s["input_channel"]])),"FX resonator input channel mismatch")
            filtered = audio[s["output_channel"]]
            require(max(map(abs,filtered)) < s["maximum_peak"],"FX resonator stability bound exceeded")
            if settings["level"] == 0: require(max(map(abs,filtered[4096:])) < 1e-7,"FX resonator silence mismatch")
            else: require(rms(filtered) > 1e-6,"FX resonator output missing")
            if settings["depth"] == 0:
                frequency = settings["excitation"];center = settings["center"]
                r = math.exp(-2*math.pi*center/(44100*.95));c1 = 2*r*math.cos(2*math.pi*center/44100)
                z = complex(math.cos(-2*math.pi*frequency/44100),math.sin(-2*math.pi*frequency/44100))
                expected = abs((1-r)*(1-r*z*z)/(1-c1*z+r*r*z*z))
                measured = projection(filtered[4096:],frequency)/projection(inputs[0][4096:],frequency)
                result.update(expected_static_magnitude=expected,measured_static_magnitude=measured)
                require(abs(measured-expected) < .002,"FX resonator static transfer mismatch")
        else: raise ValueError(f"Unknown object semantic kind: {kind}")
    elif kind == "mtof":
        pitch = [v/s["pitch_scale"] for v in audio[s["pitch_channel"]]]
        expected = [s["tuning"]*math.exp(.057762265*(v-69))*s["frequency_scale"] for v in pitch]
        error = max(abs(a-b) for a,b in zip(expected,audio[s["frequency_channel"]]))
        result.update(analytic_maximum_absolute_error=error, minimum_pitch=min(pitch), maximum_pitch=max(pitch),
                      varying_pitch_sample_transitions=sum(a != b for a,b in zip(pitch,pitch[1:])))
        require(error <= s["analytic_maximum_absolute_error"], "mtof analytic error exceeds declared limit")
        if params.get("depth",12) != 0: require(result["varying_pitch_sample_transitions"] > len(pitch)*.9, "mtof input is mostly cached rather than continuously varying")
    elif kind == "scale":
        expected = [(s["low_out"]+(x-s["low_in"])/(s["high_in"]-s["low_in"])*(s["high_out"]-s["low_out"]))*s["output_scale"] for x in audio[s["input_channel"]]]
        error = max(abs(a-b) for a,b in zip(expected,audio[s["output_channel"]]))
        result["analytic_maximum_absolute_error"] = error
        require(error <= s["analytic_maximum_absolute_error"], "scale analytic mismatch")
    elif kind == "arithmetic":
        settings = s["defaults"] | params
        expected = (settings["a"]*settings["b"]+settings["c"])/settings["divisor"] if settings["divisor"] else 0.0
        error = max(abs(v-expected) for v in audio[s["output_channel"]])
        result.update(expected_dc=expected, analytic_maximum_absolute_error=error)
        require(error <= s["analytic_maximum_absolute_error"], "Arithmetic/DC mismatch")
    elif kind == "cycle":
        phase = audio[s["phase_channel"]]
        require(all(0 <= x <= 1 for x in phase), "Cycle phase outside unit interval")
        error = max(abs(y-math.cos(2*math.pi*p)) for y,p in zip(audio[s["wave_channel"]],phase))
        result["cosine_from_phase_maximum_absolute_error"] = error
        require(error <= s["analytic_maximum_absolute_error"], "Cycle phase/table mismatch")
    elif kind == "saw":
        phase = audio[s["phase_channel"]]; values = audio[s["audio_channel"]]
        increments = [(b-a) % 1 for a,b in zip(phase,phase[1:])]
        measured = sum(increments)/len(increments)*44100
        expected = params.get("frequency",s["frequency_default"])
        require(abs(measured-expected)/expected <= s["phase_frequency_relative_tolerance"], "Saw phase frequency mismatch")
        amplitude = projection(values,expected)
        result.update(phase_frequency_hz=measured, fundamental_amplitude=amplitude)
        level = params.get("level",s["level_default"])
        if level == 0: require(max(map(abs,values)) == 0, "Saw silence case is not silent")
        else:
            require(amplitude > level*.05 and rms(values) > level*.05, "Saw fundamental/audio is missing")
            require(abs(sum(values)/len(values)) < level*.1, "Saw DC exceeds declared level fraction")
            if expected <= 440:
                second = projection(values,2*expected)/amplitude
                third = projection(values,3*expected)/amplitude
                result.update(second_to_fundamental_ratio=second,third_to_fundamental_ratio=third)
                require(.35 < second < .65 and .2 < third < .45,"Saw harmonic proportions do not match its waveform")
    elif kind == "reson":
        source = audio[s["input_channel"]]; filtered = audio[s["output_channel"]]
        require(max(map(abs,filtered)) < s["maximum_peak"], "Resonator output exceeds fixture stability bound")
        if params.get("level",.2) == 0:
            tail = max(map(abs,filtered[4096:]))
            result["settled_silence_peak"] = tail
            require(tail < 1e-7, "Resonator state did not decay after silence event")
        else: require(rms(filtered) > 1e-6, "Resonator output is missing")
        if params.get("depth",2000) == 0:
            frequency = params.get("excitation",100); center = params.get("center",4000)
            r = math.exp(-2*math.pi*center/(44100*.95)); c1 = 2*r*math.cos(2*math.pi*center/44100)
            z = complex(math.cos(-2*math.pi*frequency/44100),math.sin(-2*math.pi*frequency/44100))
            expected = abs((1-r)*(1-r*z*z)/(1-c1*z+r*r*z*z))
            measured = projection(filtered[4096:],frequency)/projection(source[4096:],frequency)
            result.update(expected_static_magnitude=expected, measured_static_magnitude=measured)
            require(abs(measured-expected) < .002, "Resonator static transfer magnitude mismatch")
    elif kind == "filters":
        for index,values in enumerate(audio):
            energy = sum(x*x for x in values)
            require(0 < energy < 100 and max(map(abs,values)) < s["maximum_peak"], "Filter impulse missing or unstable")
            require(rms(values[-len(values)//4:]) < max(1e-7,rms(values[:len(values)//4:])*.01), "Filter impulse tail did not decay")
            result["channels"][index]["impulse_energy"] = energy
    elif kind == "delay":
        source = audio[s["input_channel"]]; delayed = audio[s["output_channel"]]
        lag = int(params.get("delay",s["delay_default"])); begin = s["settle_samples"]
        error = max(abs(delayed[i]-source[i-lag]) for i in range(begin,len(source)))
        result.update(expected_delay_samples=lag, steady_delay_maximum_absolute_error=error)
        require(error <= s["analytic_maximum_absolute_error"], "Ordinary delay steady-state sample offset mismatch")
        result["crossfade_prefix_rms"] = rms(delayed[:2205])
    else:
        raise ValueError(f"Unknown object semantic kind: {kind}")
    return result


def compare(reference, candidate, reference_wav, candidate_wav, tolerance):
    a = [v for channel in reference for v in channel]; b = [v for channel in candidate for v in channel]
    require(len(a) == len(b) and a, "Comparison size mismatch")
    errors = [x-y for x,y in zip(a,b)]; maximum = max(map(abs,errors)); error_rms = rms(errors)
    reference_rms = rms(a); candidate_rms = rms(b)
    pcm = []
    for path in (reference_wav,candidate_wav):
        with wave.open(str(path),"rb") as stream:
            require(stream.getnchannels() == 2 and stream.getsampwidth() == 2, "Invalid stereo PCM proof")
            require(stream.getframerate() == 44100 and stream.getnframes()*2 == len(a),"Invalid PCM rate/frame header")
            words = array.array("h"); words.frombytes(stream.readframes(stream.getnframes()))
            if sys.byteorder != "little": words.byteswap()
            pcm.append(words)
    require(len(pcm[0]) == len(pcm[1]) == len(a), "Incomplete PCM proof")
    delta = [abs(x-y) for x,y in zip(*pcm)]
    level_error = abs(candidate_rms/reference_rms-1) if reference_rms else (0 if candidate_rms == 0 else math.inf)
    report = {"maximum_absolute_error":maximum,"rms_error":error_rms,
              "relative_rms_level_difference":level_error,"maximum_pcm_lsb_error":max(delta),
              "different_pcm_sample_words":sum(d != 0 for d in delta),"float_bit_identical":a == b,
              "reference_headroom_exceeded_words":sum(abs(x)>2 for x in a),
              "candidate_headroom_exceeded_words":sum(abs(x)>2 for x in b),"tolerances":tolerance}
    report["passed"] = (maximum <= tolerance["maximum_absolute_error"] and max(delta) <= tolerance["maximum_pcm_lsb_error"] and level_error <= tolerance["relative_rms_level_difference"])
    return report


def build_fx_probe(native, built):
    source = ROOT/"tests/fixtures/objects/fx_probe.cpp"
    libraries = [native/"librnbo_static.a",native/"libpcm_output.a"]
    snapshot = {str(p):sha(p) for p in [source,*libraries]}
    output = native/"fx_probe"
    command = [built["compiler"],"-std=c++17","-O3","-fno-fast-math","-ffp-contract=off","-fno-strict-aliasing",
               "-I"+str(ROOT/"module-sdk/include"),"-I"+str(ROOT/"firmware/components/pcm_output/include"),
               str(source),*[str(p) for p in libraries],"-o",str(output)]
    subprocess.run(command,check=True,capture_output=True,text=True)
    require(snapshot == {str(p):sha(p) for p in [source,*libraries]},"FX probe sources/libraries changed while linking")
    report = {"command":command,"compiler_version":built["compiler_version"],"input_sha256":snapshot,
              "artifact_sha256":sha(output),"native_build_report_sha256":sha(native/"host-build.json")}
    (native/"fx-probe-build.json").write_text(json.dumps(report,indent=2)+"\n")
    return output,report


def render(renderer, directory, fixture, case, blocks):
    directory.mkdir(parents=True,exist_ok=True); pcm = directory/(case["id"]+".wav"); floats = pcm.with_suffix(".f32")
    command = [str(renderer),"--output",str(pcm),"--float-output",str(floats),"--blocks",str(blocks),
               "--warmup",str(fixture["warmup_blocks"]),"--seed",str(fixture["seed"]),"--arena-bytes","1048576"]
    for identity,value in case["parameters"].items(): command += ["--parameter",identity,str(value)]
    input_audio = None; input_evidence = {}
    if fixture["role"] == "fx":
        input_audio = stimulus(fixture,case,blocks*256)
        words = array.array("f",(v for pair in zip(*input_audio) for v in pair))
        if sys.byteorder != "little": words.byteswap()
        path = directory/(case["id"]+"-input.f32");path.write_bytes(words.tobytes())
        command += ["--input-float",str(path)]
        input_evidence = {"input_float_sha256":sha(path),"stimulus":fixture["stimulus"] | case.get("stimulus",{})}
    completed = subprocess.run(command,check=True,capture_output=True,text=True)
    stats = json.loads(completed.stdout)
    require(stats["blocks"] == blocks, "Incomplete render")
    for field in ("late_platform_allocations","errors","invalid_samples"): require(stats[field] == 0,f"Unhealthy render: {field}")
    audio = channels(floats,blocks*256)
    return audio,pcm,{"statistics":stats,"semantics":semantic_checks(fixture,case,audio,input_audio),**input_evidence,
                      "wav_sha256":sha(pcm),"float_sha256":sha(floats),"command":command}


def qualify(out, names, profiles, blocks_override=None, catalog_path=None):
    require(not out.exists(), "Output directory must be fresh")
    catalog_path = catalog_path or ROOT/"tests/fixtures/objects/catalog.json"; catalog = json.loads(catalog_path.read_text())
    fixtures = [f for f in catalog["fixtures"] if not names or f["id"] in names]
    require(fixtures and (not names or {f["id"] for f in fixtures} == names), "Unknown fixture selection")
    out.mkdir(parents=True); identities = {str(Path(__file__).resolve()):sha(Path(__file__)),str(catalog_path):sha(catalog_path)}
    (out/"qualification-tool.py").write_bytes(Path(__file__).read_bytes())
    (out/"catalog-source.json").write_bytes(catalog_path.read_bytes())
    identities.update({str(catalog_path.parent/f["patch"]):sha(catalog_path.parent/f["patch"]) for f in fixtures})
    if any(f["role"] == "fx" for f in fixtures): identities[str(ROOT/"tests/fixtures/objects/fx_probe.cpp")] = sha(ROOT/"tests/fixtures/objects/fx_probe.cpp")
    report = {"format":"rnbo-object-host-qualification-v1","hardware_executed":False,"target_performance_qualified":False,
              "identity_sha256":identities,"sample_rate":44100,"block_frames":256,"fixtures":[],"passed":True,"completed":False}
    for fixture in fixtures:
        name = fixture["id"]; raw = out/"exports"/name; log = out/(name+"-build.log")
        record = {"fixture":fixture,"variants":[],"raw_export":str(raw)}; report["fixtures"].append(record)
        with log.open("w") as stream:
            subprocess.run(["node",str(ROOT/"archive/importer/export.mjs"),str(catalog_path.parent/fixture["patch"]),"--out",str(raw)],check=True,stdout=stream,stderr=subprocess.STDOUT)
        variants = [("strict","float32-strict",False)] + [(p,p,False) for p in profiles]
        if fixture["float32_delay_storage"]: variants += [("float32-delays","float32-strict",True),("float32-audio-and-delays","float32-audio-v1",True)]
        if fixture["float32_delay_storage"] and "float32-audio-v2" in profiles:
            variants.append(("float32-audio-v2-and-delays","float32-audio-v2",True))
        references = {}; reference_build = None
        for variant,profile,storage in variants:
            prepared = out/"prepared"/name/variant; native = out/"native"/name/variant
            item = {"variant":variant,"numerical_profile":profile,"float32_delays":storage,"prepared":str(prepared),"cases":[]}; record["variants"].append(item)
            try:
                manifest = prepare(raw,prepared,"rnbos3patch",fixture["role"],numerical_profile=profile,
                    filter_delay_max_ms=fixture.get("filter_delay_max_ms"),float32_delay_storage=storage)
            except ExportError as exc:
                if variant == "strict": raise
                item.update(status="unsupported-form",reason=str(exc)); continue
            with log.open("a") as stream:
                subprocess.run(["cmake","-S",str(ROOT),"-B",str(native),"-DCMAKE_BUILD_TYPE=Release","-DRNBO_S3_EXPORT_DIR="+str(prepared)],check=True,stdout=stream,stderr=subprocess.STDOUT)
                subprocess.run([sys.executable,str(ROOT/"host/compiler/build.py"),"--export",str(prepared),"--build-dir",str(native)],check=True,stdout=stream,stderr=subprocess.STDOUT)
            renderer = native/"rnbo_render"; built = json.loads((native/"host-build.json").read_text())
            require(sha(renderer) == built["artifact_sha256"], "Renderer identity mismatch")
            if variant == "strict": reference_build = built
            else:
                for key in ("integration_files_sha256","compiler_tools_sha256","compiler","compiler_version","cmake_build_type","cmake_build_settings"):
                    require(built[key] == reference_build[key],f"Mismatched integration/compiler: {key}")
            item.update(status="passed",manifest=manifest,build_report=str(native/"host-build.json"),
                        build_report_sha256=sha(native/"host-build.json"),
                        prepared_manifest_sha256=sha(prepared/"manifest.json"),
                        prepared_provenance_sha256=sha(prepared/"provenance.json"),
                        artifact_sha256=built["artifact_sha256"])
            if fixture["role"] == "fx":
                renderer,probe_report = build_fx_probe(native,built)
                item.update(fx_probe=probe_report,fx_probe_build_report_sha256=sha(native/"fx-probe-build.json"))
            for case in fixture["cases"]:
                blocks = blocks_override or fixture["blocks"]
                audio,pcm,evidence = render(renderer,out/"renders"/name/variant,fixture,case,blocks)
                case_report = {"case":case,**evidence}; item["cases"].append(case_report)
                if variant == "strict": references[case["id"]] = (audio,pcm)
                else:
                    reference_audio,reference_pcm = references[case["id"]]
                    if input_audio := case_report.get("input_float_sha256"):
                        strict_case = next(c for c in record["variants"][0]["cases"] if c["case"]["id"] == case["id"])
                        require(input_audio == strict_case["input_float_sha256"],"Reference/candidate FX inputs differ")
                    metrics = compare(reference_audio,audio,reference_pcm,pcm,fixture["comparison_tolerance"])
                    case_report["comparison"] = metrics
                    if not metrics["passed"]: item["status"] = "comparison-failed";report["passed"] = False
            print(json.dumps({"fixture":name,"variant":variant,"status":item["status"]}),flush=True)
        (out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
    require(all(sha(Path(path)) == value for path,value in identities.items()),"Fixture/catalog/qualifier changed during qualification")
    report["completed"] = True
    (out/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--only",help="Comma-separated fixture IDs; default all12")
    parser.add_argument("--catalog",type=Path,default=ROOT/"tests/fixtures/objects/catalog.json")
    parser.add_argument("--profiles",default="float32-cycle-v1,float32-cycle-v2,float32-audio-v1")
    parser.add_argument("--blocks",type=int,help="Override frames256 per block,64..4096blocks")
    args = parser.parse_args(); names = set(args.only.split(",")) if args.only else set(); profiles = args.profiles.split(",") if args.profiles else []
    require(len(profiles) == len(set(profiles)) and all(p in NUMERICAL_PROFILES and p != "float32-strict" for p in profiles),"Invalid optional profile list")
    require(args.blocks is None or 64 <= args.blocks <= 4096,"blocks must be64..4096")
    destination = args.out.resolve(); fresh = not destination.exists()
    try:
        report = qualify(destination,names,profiles,args.blocks,args.catalog.resolve())
    except (ValueError,ExportError,OSError,subprocess.CalledProcessError) as exc:
        if fresh and destination.is_dir():
            path = destination/"report.json"
            failed = json.loads(path.read_text()) if path.is_file() else {}
            failed.update(passed=False,completed=False,failure={"type":type(exc).__name__,"message":str(exc)})
            path.write_text(json.dumps(failed,indent=2,sort_keys=True,allow_nan=False)+"\n")
        raise
    print(json.dumps({"report":str(args.out.resolve()/"report.json"),"fixtures":len(report["fixtures"]),"passed":report["passed"]}))
    if not report["passed"]: raise SystemExit(1)


if __name__ == "__main__": main()
