#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Second-wave semantic probes, separate from production preparation helpers.

Only original flat fixtures are tracked. Generated exports, binaries, input and
output proofs stay in a fresh ignored build directory. This never opens a port.
"""
from __future__ import annotations
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from prepare import ExportError,NUMERICAL_PROFILES,prepare
from qualify_objects import channels,compare,rms,sha
from prepare import cpp_code_mask
from bounded_filters import _method

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"tests/fixtures/objects/wave2"


def require(condition,message):
    if not condition:raise ValueError(message)


def input_signal(kind,frames):
    if kind=="impulse-step-v1":
        left=[1.0 if i==0 else -.5 if i==4096 else 0.0 for i in range(frames)]
        right=[.25 if i<8192 else -.125 for i in range(frames)]
    elif kind=="nonlinear-grid-v1":
        x=(-4,-2,-1,-.5,0,.5,1,2,4);y=(-3,-2,-1,-.5,0,.25,.5,1,1.5,2,3)
        left=[x[(i//64)%len(x)] for i in range(frames)]
        right=[y[(i//64)%len(y)] for i in range(frames)]
    elif kind=="mixed-tone-v1":
        left=[.2*math.sin(2*math.pi*440*i/44100)+.19*math.sin(2*math.pi*441*i/44100) for i in range(frames)]
        right=[.2*math.sin(2*math.pi*660*i/44100)-.2*math.sin(2*math.pi*661*i/44100)+1e-5 for i in range(frames)]
    else:raise ValueError("Unknown second-wave input stimulus")
    return array.array("f",left),array.array("f",right)


def band_power(values,bins):
    """Independent Hann-window DFT probes, averaged over eight4096-frame blocks."""
    size=4096;segments=min(8,len(values)//size)
    require(segments>0,"Noise spectrum needs at least4096frames")
    result=0.0
    for segment in range(segments):
        samples=values[segment*size:(segment+1)*size]
        for bin_index in bins:
            real=imag=0.0
            for i,x in enumerate(samples):
                window=.5-.5*math.cos(2*math.pi*i/(size-1));phase=2*math.pi*bin_index*i/size
                real+=x*window*math.cos(phase);imag-=x*window*math.sin(phase)
            result+=real*real+imag*imag
    return result/(segments*len(bins))


def average_truth(source,window,initial_available):
    """Recompute every mathematical window with fsum; no running accumulator."""
    return [math.fsum(source[max(0,i-window+1):i+1])/min(window,initial_available+i+1)
            for i in range(len(source))]


def source_audit(raw,fixture):
    path=raw/"rnbo_source.h";text=path.read_text();masked=cpp_code_mask(text)
    result={"source":str(path),"source_sha256":sha(path),"methods":[]}
    def method(name):
        try:start,end=_method(masked,name)
        except ValueError:
            matches=list(re.finditer(r"\bIndex\s+"+re.escape(name)+r"\s*\([^{};]*\)\s*\{",masked))
            require(len(matches)==1,"Expected one audited Index method")
            match=matches[0];start=match.start();end=match.end();depth=1
            while depth:
                if masked[end]=="{":depth+=1
                elif masked[end]=="}":depth-=1
                end+=1
        result["methods"].append({"name":name,"line":text.count("\n",0,start)+1,
            "raw_method_sha256":hashlib.sha256(text[start:end].encode()).hexdigest(),
            "code_method_sha256":hashlib.sha256(re.sub(r"\s+","",masked[start:end]).encode()).hexdigest()})
    if fixture["family"]=="average":
        for object_index in (1,2):
            prefix=f"average_tilde_{object_index:02d}"
            for suffix in ("init","doReset","setwindowsize","perform","dspsetup"):
                method(prefix+"_"+suffix)
        result["oracle_policy"]={"basis":"setwindowsize marks changed valid integer window for reset; doReset clears effective count, accumulation and position; perform grows available count until full",
            "independent_truth":"math.fsum over each literal input window, divided by available history count; no generated accumulator implementation copied",
            "warmup":"four detached zero-input blocks fill unchanged default16; a block0 change to1/63/64 resets to no available history",
            "causal_lag":"zero: perform adds the current input to accumulation and writes history before emitting the average",
            "allocation":"init requests samplerate+1 Float64 frames per channel, independent of these authored maximum64 windows"}
    elif fixture["family"]=="noise":
        for name in ("noise_tilde_01_nz_reset","noise_tilde_01_nz_seed","pink_tilde_01_init","pink_tilde_01_generateRandomNumber","pink_tilde_01_perform"):
            method(name)
        result.update(runtime_audio_signal_sha256=sha(raw/"common/RNBO_AudioSignal.h"),
            seed_policy_basis="pink_init assigns systemticks only; generateRandomNumber is affine LCG with nonzero increment, so zero seed is not a constant-state generator; native systemticks wraps C library clock, dynamic private clock is a separate policy")
    return result


def semantics(fixture,case,audio,inputs):
    spec=fixture["semantic"];kind=spec["kind"];params=case["parameters"]
    report={"kind":kind,"passed":True,"channels":[{"peak":max(map(abs,v)),"rms":rms(v),"mean":sum(v)/len(v)} for v in audio]}
    if kind=="average":
        window=int(params.get("window",spec["default_window"]));errors=[]
        initial_available=window if window==spec["default_window"] else 0
        for source,output in zip(inputs,audio):
            expected=average_truth(source,window,initial_available)
            errors.append(max(abs(y-x) for x,y in zip(expected,output)))
        report.update(window_samples=window,history_reset_on_window_change=initial_available==0,
                      expected_causal_output_lag_samples=0,maximum_absolute_errors=errors,
                      declared_maximum_absolute_error=spec["maximum_absolute_error"])
        if max(errors)>spec["maximum_absolute_error"]:
            report.update(passed=False,limitation="Strict running-average output exceeds independent mathematical-window accuracy limit; no tolerance widening")
    elif kind=="biquad":
        coefficients=spec["defaults"]|params;errors=[]
        for source,output in zip(inputs,audio):
            xm1=xm2=ym1=ym2=0.0;maximum=0.0
            for x,y in zip(source,output):
                expected=coefficients["a0"]*x+coefficients["a1"]*xm1+coefficients["a2"]*xm2-coefficients["b1"]*ym1-coefficients["b2"]*ym2
                maximum=max(maximum,abs(expected-y));xm2=xm1;xm1=x;ym2=ym1;ym1=expected
            require(maximum<=spec["maximum_absolute_error"],"Biquad difference-equation response mismatch")
            errors.append(maximum)
        report["maximum_absolute_errors"]=errors
        denominator=1+coefficients["b1"]+coefficients["b2"]
        dc_gain=(coefficients["a0"]+coefficients["a1"]+coefficients["a2"])/denominator
        expected_dc=inputs[1][-1]*dc_gain;observed=sum(audio[1][-1024:])/1024
        require(abs(expected_dc-observed)<=spec["maximum_absolute_error"],"Biquad DC gain mismatch")
        report.update(expected_dc_gain=dc_gain,settled_right_dc=observed)
    elif kind=="phase-pulse":
        phase,pulses=audio;frequency=params.get("frequency",spec["frequency_default"])
        require(all(0<=x<=1 for x in phase),"Phasor outside unit interval")
        increments=[((b-a+.5)%1)-.5 for a,b in zip(phase,phase[1:])]
        measured=sum(increments)/len(increments)*44100
        require(abs(measured-frequency)<=max(.0002,abs(frequency)*spec["phase_frequency_relative_tolerance"]),"Phasor signed phase rate mismatch")
        require(all(x in (0,1) for x in pulses),"Train output is not binary")
        period=params.get("period",spec["period_default"]);width=params.get("width",spec["width_default"])
        duty=sum(pulses)/len(pulses)
        require(abs(duty-width)<=2/period+.001,"Train pulse width/sample-period mismatch")
        edges=[i for i in range(1,len(pulses)) if pulses[i-1]==0 and pulses[i]==1]
        intervals=[b-a for a,b in zip(edges,edges[1:])]
        if 0<width<1:
            require(intervals and all(abs(x-period)<=1 for x in intervals),"Train period is not measured in declared samples")
        report.update(phase_rate_hz=measured,pulse_duty=duty,pulse_rising_edges=len(edges),minimum_interval=min(intervals) if intervals else None,maximum_interval=max(intervals) if intervals else None)
    elif kind=="noise":
        white=audio[spec["white_channel"]];pink=audio[spec["pink_channel"]]
        mean=sum(white)/len(white);variance=sum((x-mean)**2 for x in white)/len(white)
        require(variance>0,"White noise has zero variance")
        correlation=sum((a-mean)*(b-mean) for a,b in zip(white,white[1:]))/((len(white)-1)*variance)
        require(max(map(abs,white))<=1 and abs(mean)<spec["maximum_absolute_mean"],"White noise range/DC mismatch")
        require(spec["white_variance_range"][0]<variance<spec["white_variance_range"][1] and abs(correlation)<.02,"White noise variance/correlation mismatch")
        powers={}
        for label,values in (("white",white),("pink",pink)):
            low=band_power(values,(4,5,6,7));high=band_power(values,(256,320,384,448))
            require(high>0,"Noise high-frequency power missing");powers[label]=low/high
        require(.2<powers["white"]<5 and powers["pink"]>2,"Noise spectral colour mismatch")
        report.update(white_variance=variance,white_lag_one_correlation=correlation,low_to_high_band_power_ratios=powers)
    elif kind=="nonlinear":
        exponent=params.get("exponent",spec["exponent_default"])
        expected_left=[math.tanh(x) for x in inputs[0]]
        expected_right=[max(0,min(1,x-2*math.floor((x+1)/2)))**exponent for x in inputs[1]]
        errors=[max(abs(a-b) for a,b in zip(expected,output)) for expected,output in zip((expected_left,expected_right),audio)]
        require(max(errors)<=spec["maximum_absolute_error"],"Nonlinear tanh/wrap/clip/pow domain mismatch")
        report["maximum_absolute_errors"]=errors
    elif kind=="line":
        ramp,targets=audio;duration=10;commands=[]
        if "milliseconds" in params:duration=params["milliseconds"]
        if "target" in params:commands.append((0,params["target"],duration))
        for event in case["events"]:
            if event["id"]=="milliseconds":duration=event["value"]
            elif event["id"]=="target":commands.append((event["block"]*256,event["value"],duration))
        measurements=[]
        for j,(start,target,milliseconds) in enumerate(commands):
            stop=commands[j+1][0] if j+1<len(commands) else len(ramp)
            prior=ramp[start-1] if start else spec["initial"]
            require(all(abs(x-target)<1e-7 for x in targets[start:stop]),"Target observer missed a boundary event")
            if milliseconds==0:
                require(all(abs(x-target)<2e-6 for x in ramp[start+1:stop]),"Zero-time line did not settle in one sample")
                measurements.append({"start":start,"milliseconds":0,"settled":True});continue
            frames=milliseconds*44.1;expected_step=(target-prior)/frames
            active_end=min(stop,start+max(2,math.floor(frames)-2))
            values=ramp[start:active_end]
            require(len(values)>2,"Line probe has too few active samples")
            slope=(values[-1]-values[0])/(len(values)-1)
            residual=max(abs(v-(values[0]+i*slope)) for i,v in enumerate(values))
            require(residual<=spec["linear_residual_tolerance"],"Line ramp is not affine")
            require(abs(slope-expected_step)<=abs(expected_step)*.01+2e-6,"Line slope disagrees with millisecond duration")
            require(max(abs(ramp[start]-prior),0)<=2*abs(expected_step)+2e-6,"Line jumps at a nonzero-duration event")
            direction=1 if target>=prior else -1
            require(all(direction*(b-a)>=-2e-6 for a,b in zip(ramp[start:stop],ramp[start+1:stop])),"Line direction/overshoot mismatch")
            settled=next((i for i in range(start,stop) if abs(ramp[i]-target)<2e-6),None)
            if stop>=start+math.ceil(frames)+3:
                require(settled is not None and abs(settled-start-frames)<=spec["timing_tolerance_samples"]+1,"Line endpoint timing mismatch")
                require(all(abs(x-target)<2e-6 for x in ramp[start+math.ceil(frames)+2:stop]),"Line does not hold its target")
            measurements.append({"start":start,"milliseconds":milliseconds,"expected_frames":frames,"observed_slope":slope,"maximum_linear_residual":residual,"settled_frame":settled})
        report["segments"]=measurements
    else:raise ValueError("Unknown second-wave semantic model")
    return report


def compile_probe(native,built):
    source=FIXTURES/"probe.cpp";libraries=[native/"librnbo_static.a",native/"libpcm_output.a"]
    snapshot={str(p):sha(p) for p in [source,*libraries]};output=native/"wave2_probe"
    command=[built["compiler"],"-std=c++17","-O3","-fno-fast-math","-ffp-contract=off","-fno-strict-aliasing",
             "-I"+str(ROOT/"module-sdk/include"),"-I"+str(ROOT/"firmware/components/pcm_output/include"),str(source),*[str(p) for p in libraries],"-o",str(output)]
    subprocess.run(command,check=True,capture_output=True,text=True)
    require(snapshot=={str(p):sha(p) for p in [source,*libraries]},"Probe inputs changed during linking")
    result={"source_libraries_sha256":snapshot,"command":command,"artifact_sha256":sha(output),"native_build_report_sha256":sha(native/"host-build.json")}
    (native/"probe-build.json").write_text(json.dumps(result,indent=2)+"\n")
    return output,result


def render(probe,directory,fixture,case,blocks,*,seed=None,label=None):
    directory.mkdir(parents=True,exist_ok=True);stem=label or case["id"];pcm=directory/(stem+".wav");floats=pcm.with_suffix(".f32")
    command=[str(probe),"--output",str(pcm),"--float-output",str(floats),"--blocks",str(blocks),"--warmup",str(fixture["warmup_blocks"]),"--seed",str(fixture["seed"] if seed is None else seed),"--arena-bytes",str(fixture["arena_bytes"])]
    for identity,value in case["parameters"].items():command += ["--parameter",identity,str(value)]
    for event in case["events"]:command += ["--at-parameter",str(event["block"]),event["id"],str(event["value"])]
    inputs=None;input_hash=None
    if fixture["role"]=="fx":
        inputs=input_signal(case.get("stimulus",fixture["stimulus"])["kind"],blocks*256)
        words=array.array("f",(v for pair in zip(*inputs) for v in pair))
        if sys.byteorder!="little":words.byteswap()
        path=directory/(stem+"-input.f32");path.write_bytes(words.tobytes());input_hash=sha(path)
        command += ["--input-float",str(path)]
    completed=subprocess.run(command,check=True,capture_output=True,text=True);stats=json.loads(completed.stdout)
    require(stats["blocks"]==blocks,"Incomplete render")
    require(all(stats[k]==0 for k in ("errors","invalid_samples","late_platform_allocations")),"Unhealthy render")
    audio=channels(floats,blocks*256)
    try:model=semantics(fixture,case,audio,inputs)
    except ValueError as exc:model={"kind":fixture["semantic"]["kind"],"passed":False,"failure":str(exc)}
    return audio,pcm,{"command":command,"statistics":stats,"input_sha256":input_hash,"float_sha256":sha(floats),"pcm_sha256":sha(pcm),"semantics":model}


def qualify(out,names,profiles,blocks):
    require(not out.exists(),"Choose a fresh output directory")
    catalog=json.loads((FIXTURES/"catalog.json").read_text());fixtures=[f for f in catalog["fixtures"] if not names or f["id"] in names]
    require(fixtures and (not names or {f["id"] for f in fixtures}==names),"Unknown second-wave fixture")
    out.mkdir(parents=True)
    identity={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/"host/compiler/qualify_objects.py",ROOT/"host/compiler/bounded_filters.py",FIXTURES/"catalog.json",FIXTURES/"probe.cpp",*[FIXTURES/f["patch"] for f in fixtures]]}
    (out/"qualifier-source.py").write_bytes(Path(__file__).read_bytes());(out/"catalog-source.json").write_bytes((FIXTURES/"catalog.json").read_bytes())
    report={"format":"rnbo-second-wave-host-qualification-v1","identity_sha256":identity,"hardware_executed":False,"target_performance_qualified":False,"completed":False,"passed":True,"fixtures":[]}
    for fixture in fixtures:
        name=fixture["id"];raw=out/"exports"/name;log=out/(name+"-build.log");record={"fixture":fixture,"variants":[]};report["fixtures"].append(record)
        with log.open("w") as stream:subprocess.run(["node",str(ROOT/"host/export/export.mjs"),str(FIXTURES/fixture["patch"]),"--out",str(raw)],check=True,stdout=stream,stderr=subprocess.STDOUT)
        record["source_audit"]=source_audit(raw,fixture)
        references={};reference_build=None
        for profile in ["float32-strict",*profiles]:
            item={"profile":profile,"cases":[]};record["variants"].append(item);prepared=out/"prepared"/name/profile;native=out/"native"/name/profile
            try:manifest=prepare(raw,prepared,"rnbos3patch",fixture["role"],numerical_profile=profile)
            except ExportError as exc:
                if profile=="float32-strict":raise
                item.update(status="unsupported-form",reason=str(exc));continue
            with log.open("a") as stream:
                subprocess.run(["cmake","-S",str(ROOT),"-B",str(native),"-DCMAKE_BUILD_TYPE=Release","-DRNBO_S3_EXPORT_DIR="+str(prepared)],check=True,stdout=stream,stderr=subprocess.STDOUT)
                subprocess.run([sys.executable,str(ROOT/"host/compiler/build.py"),"--export",str(prepared),"--build-dir",str(native)],check=True,stdout=stream,stderr=subprocess.STDOUT)
            built=json.loads((native/"host-build.json").read_text());probe,probe_report=compile_probe(native,built)
            if reference_build is None:reference_build=built
            else:
                for key in ("compiler","compiler_version","compiler_tools_sha256","integration_files_sha256","cmake_build_type","cmake_build_settings"):
                    require(built[key]==reference_build[key],"Mismatched compiler/integration: "+key)
            item.update(status="passed",manifest=manifest,prepared_provenance_sha256=sha(prepared/"provenance.json"),prepared_manifest_sha256=sha(prepared/"manifest.json"),build_report_sha256=sha(native/"host-build.json"),probe=probe_report)
            for case in fixture["cases"]:
                audio,pcm,evidence=render(probe,out/"renders"/name/profile,fixture,case,blocks)
                item["cases"].append({"case":case,**evidence})
                if not evidence["semantics"]["passed"]:
                    item["status"]="baseline-precision-limitation" if profile=="float32-strict" else "semantic-failed"
                    report["passed"]=False
                if profile=="float32-strict":references[case["id"]]=(audio,pcm,evidence)
                else:
                    a,p,e=references[case["id"]];require(e["input_sha256"]==evidence["input_sha256"],"FX comparison inputs differ")
                    metrics=compare(a,audio,p,pcm,fixture["comparison_tolerance"]);item["cases"][-1]["comparison"]=metrics
                    if not metrics["passed"]:item["status"]="comparison-failed";report["passed"]=False
            if fixture["family"]=="noise":
                first=item["cases"][0];case=fixture["cases"][0]
                again,_,repeat=render(probe,out/"renders"/name/profile,fixture,case,blocks,label="repeat")
                other,_,changed=render(probe,out/"renders"/name/profile,fixture,case,blocks,seed=fixture["seed"]+1,label="other-context-seed")
                baseline=references[case["id"]][0] if profile=="float32-strict" else channels(out/"renders"/name/profile/(case["id"]+".f32"),blocks*256)
                same=first["float_sha256"]==repeat["float_sha256"]
                white_same=baseline[0]==again[0] and baseline[0]==other[0]
                item["seed_policy"]={"same_seed_bit_identical":same,"explicit_white_unchanged_other_context_seed":white_same,
                    "pink_same_context_seed_bit_identical":baseline[1]==again[1],
                    "different_context_seed_observation_confounded_by_systemticks":True,
                    "repeat_float_sha256":repeat["float_sha256"],"other_seed_float_sha256":changed["float_sha256"]}
                if not same or not white_same:
                    item["status"]="native-seed-policy-limitation";report["passed"]=False
            print(json.dumps({"fixture":name,"profile":profile,"status":item["status"]}),flush=True)
            (out/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        (out/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    require(all(sha(Path(p))==h for p,h in identity.items()),"Second-wave source changed during qualification")
    report["completed"]=True;(out/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n");return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",required=True,type=Path);parser.add_argument("--only");parser.add_argument("--profiles",default="float32-audio-v2");parser.add_argument("--blocks",type=int,default=512)
    args=parser.parse_args();names=set(args.only.split(",")) if args.only else set();profiles=args.profiles.split(",") if args.profiles else []
    require(64<=args.blocks<=4096,"blocks must be64..4096")
    require(len(profiles)==len(set(profiles)) and all(p in NUMERICAL_PROFILES and p!="float32-strict" for p in profiles),"Unknown optional profile")
    out=args.out.resolve();fresh=not out.exists()
    try:report=qualify(out,names,profiles,args.blocks)
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        if fresh and out.is_dir():
            path=out/"report.json";failed=json.loads(path.read_text()) if path.is_file() else {}
            failed.update(completed=False,passed=False,failure={"type":type(exc).__name__,"message":str(exc)});path.write_text(json.dumps(failed,indent=2)+"\n")
        raise
    print(json.dumps({"report":str(out/"report.json"),"passed":report["passed"],"fixtures":len(report["fixtures"])}))
    if not report["passed"]:raise SystemExit(1)


if __name__=="__main__":main()
