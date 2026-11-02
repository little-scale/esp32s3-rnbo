#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify a known static sine or MIDI4 fixture through post-volume PCM capture.

Root/operator must own the device exclusively. This tool changes live controls
and runs Panic/Resume, but never flashes or uploads. Original parameter values
must be supplied because the bring-up shell has no live parameter getter.
"""
from __future__ import annotations

import argparse
import array
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

from capture import (BOARDS, CaptureError, JsonLineTransport, RATE, Transport,
                     decode_response, integer, open_serial, record, save,
                     validate_status)

COUNTERS = ("nonfinite", "clipped", "write_errors", "dma_errors", "queue_errors",
            "module_errors", "audio_heap_allocations", "audio_heap_frees",
            "late_platform_allocations")
BLOCK_US = 256 * 1000000 / RATE


def require(condition, message):
    if not condition:raise CaptureError(message)


def read_json(path: Path, limit=8*1024*1024):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=limit,
            f"Missing, linked, or oversized evidence input: {path}")
    return decode_response(path.read_bytes())


def canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+"\n").encode()


def expectations(firmware_report: Path, prepared: Path, fixture: str) -> dict:
    report = read_json(firmware_report)
    manifest = read_json(prepared/"manifest.json")
    description_data = (prepared/"description.json").read_bytes()
    require(len(description_data)<=1024*1024,"Parameter description is too large")
    description = decode_response(description_data)
    embedded = report.get("prepared_export",{})
    require(embedded.get("manifest")==manifest,"Prepared manifest differs from firmware build report")
    expected_description_hash = embedded.get("provenance",{}).get("prepared_files_sha256",{}).get("description.json")
    require(hashlib.sha256(description_data).hexdigest()==expected_description_hash,
            "Parameter schema differs from the firmware build's admitted source")
    require(report.get("board") in BOARDS,"Unknown board in firmware report")
    require(report.get("sample_rate")==RATE and report.get("block_frames")==256 and report.get("default_source")=="static-rnbo",
            "Firmware report is not the static 44100/256 RNBO profile")
    require(manifest.get("audio_inputs")==0 and manifest.get("audio_outputs")==2 and manifest.get("role")=="main",
            "Expected a Main oscillator/instrument module")
    source_hash = manifest.get("source_tree_sha256")
    require(isinstance(source_hash,str) and re.fullmatch(r"[0-9a-f]{64}",source_hash),"Missing module source identity")
    elf = [(name,info) for name,info in report.get("artifacts",{}).items() if name.endswith(".elf")]
    require(len(elf)==1,"Firmware report must identify exactly one application ELF")
    elf_hash = elf[0][1].get("sha256")
    require(isinstance(elf_hash,str) and re.fullmatch(r"[0-9a-f]{64}",elf_hash),"Missing firmware ELF digest")
    params = {}
    for item in description.get("parameters",[]):
        identity = item.get("paramId")
        require(isinstance(identity,str) and identity not in params,"Invalid or duplicate stable parameter ID")
        integer(item.get("index"),"Parameter index",0,127)
        params[identity]=item
    if fixture=="sine":
        require(set(params)=={"frequency","level"},"Sine fixture requires frequency and level stable IDs only")
        require((params["frequency"].get("minimum"),params["frequency"].get("maximum"),params["frequency"].get("exponent"),params["frequency"].get("steps"))==(20,10000,1,0),
                "Sine frequency conversion differs from the authored fixture")
    elif fixture=="midi4":
        require(set(params)=={"level","poly/level"},"MIDI4 fixture requires the known level/poly/level schema")
        require(manifest.get("voices")==4,"MIDI4 requires an explicitly recorded four-voice export")
    else:raise CaptureError("Fixture must be sine or midi4")
    require(params["level"].get("minimum")==0 and params["level"].get("maximum")==1,"Unexpected fixture level range")
    return {"board":report["board"],"fixture":fixture,"firmware_elf_sha256":elf_hash,
            "module_source_sha256":source_hash,"parameters":params,
            "firmware_report_sha256":hashlib.sha256(firmware_report.read_bytes()).hexdigest(),
            "prepared_manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest(),
            "parameter_description_sha256":expected_description_hash}


def metrics(pcm: bytes, channels: int) -> list[dict]:
    values = array.array("h",pcm)
    if sys.byteorder!="little":values.byteswap()
    result = []
    for channel in range(channels):
        samples = values[channel::channels]
        require(len(samples)>4,"Capture contains too few samples")
        squares = sum(float(v)*v for v in samples)
        crossings=[]
        for i in range(1,len(samples)):
            if samples[i-1]<=0<samples[i]:
                crossings.append(i-1-samples[i-1]/(samples[i]-samples[i-1]))
        frequency = (len(crossings)-1)*RATE/(crossings[-1]-crossings[0]) if len(crossings)>3 else None
        result.append({"peak":max(abs(v) for v in samples)/32767,
                       "rms":math.sqrt(squares/len(samples))/32767,
                       "mean":sum(samples)/len(samples)/32767,
                       "positive_crossing_frequency_hz":frequency,
                       "nonzero_samples":sum(v!=0 for v in samples)})
    return result


def projected_notes(pcm: bytes,channels: int,present: list[int],absent: list[int],expected_amplitude: float) -> list[dict]:
    """Measure each known partial independently; polyphonic pitch is not a
    zero-crossing rate. One-second windows keep cross-partial leakage small.
    Bounds deliberately allow quantization, finite-window leakage and phase.
    """
    values=array.array("h",pcm)
    if sys.byteorder!="little":values.byteswap()
    require(channels in (1,2) and len(values)%channels==0,"Invalid projection channel/sample length")
    frames=len(values)//channels
    require(frames==RATE,"Projection qualification requires exactly one second")
    notes=sorted(set(present+absent))
    require(not set(present)&set(absent) and len(notes)>0,"Projection note sets overlap or are empty")
    result=[]
    for channel in range(channels):
        samples=[v/32767 for v in values[channel::channels]]
        partials=[]
        for note in notes:
            integer(note,"MIDI projection note",0,127)
            hz=440*2**((note-69)/12)
            real=imaginary=0.0
            for i,sample in enumerate(samples):
                phase=2*math.pi*hz*i/RATE
                real+=sample*math.cos(phase);imaginary+=sample*math.sin(phase)
            amplitude=2*math.hypot(real,imaginary)/frames
            require(math.isfinite(amplitude),"Non-finite projected amplitude")
            is_present=note in present
            if is_present:
                require(expected_amplitude*0.8<=amplitude<=expected_amplitude*1.2,
                        f"MIDI note {note}: expected partial is missing or has wrong amplitude ({amplitude:.9g})")
            else:
                require(amplitude<max(expected_amplitude*0.15,3/32767),
                        f"MIDI note {note}: released/stolen partial is still present ({amplitude:.9g})")
            partials.append({"midi_note":note,"frequency_hz":hz,"amplitude":amplitude,"expected_present":is_present})
        result.append({"channel":channel,"partials":partials})
    return result


class Qualification:
    def __init__(self,transport: Transport,expected: dict,out: Path,restore: dict,
                 *,idle_midi_baseline=False,clock=time.monotonic,sleep=time.sleep):
        self.transport=transport;self.expected=expected;self.out=out;self.restore=restore
        self.clock=clock;self.sleep=sleep;self.idle_midi_baseline=idle_midi_baseline
        self.snapshots=[];self.cases=[];self.commands=[]
        self.original=None;self.eligible_to_restore=False

    def status(self, *,healthy=True):
        status=validate_status(self.transport.request("status"),self.expected["board"])
        require(status.get("source")=="static-rnbo","Expected a statically linked RNBO fixture")
        for key in ("firmware_elf_sha256","module_source_sha256"):
            require(status.get(key)==self.expected[key],f"Device {key} does not match the expected build")
        for key in COUNTERS:
            integer(status.get(key),key,0,0xffffffffffffffff)
            if healthy:require(status[key]==0,f"Observed audio fault counter {key}={status[key]}")
        for key in ("panic","allocation_fault","rebuilding","ready_to_resume","reconstruction_failed"):
            require(type(status.get(key)) is bool,f"Missing boolean status {key}")
        if healthy:
            require(not status["allocation_fault"] and not status["reconstruction_failed"],"Device reports an allocation/reconstruction fault")
        integer(status.get("volume"),"Volume",0,100)
        integer(status.get("frames"),"Audio-owner frames",0,0xffffffffffffffff)
        integer(status.get("audio_stack_free"),"Audio stack free",0,0xffffffff)
        integer(status.get("render_us"),"Latest render time",0,0xffffffff)
        integer(status.get("peak_us"),"Lifetime peak render time",0,0xffffffff)
        snapshot=dict(status)
        snapshot["latest_render_period_percent"]=status["render_us"]/BLOCK_US*100
        snapshot["lifetime_peak_render_period_percent"]=status["peak_us"]/BLOCK_US*100
        self.snapshots.append(snapshot)
        return status

    def wait(self,predicate,label,timeout=5):
        deadline=self.clock()+timeout
        while self.clock()<deadline:
            status=self.status()
            if predicate(status):return status
            self.sleep(0.025)
        raise CaptureError(f"Timed out waiting for {label}")

    def control(self,command,ack):
        # Recheck identity before mutations, including recovery. A replaced
        # device/module must never receive this run's restoration commands.
        self.status(healthy=False)
        response=self.transport.request(command)
        require(ack(response),f"Unexpected acknowledgement for {command.split()[0]}")
        self.commands.append({"command":command,"response":response})

    def volume(self,value):
        self.control(f"volume {value}",lambda r:r.get("accepted") is True and r.get("volume")==value)
        self.wait(lambda s:s["volume"]==value,f"volume {value}")
        self.sleep(0.08) # complete the declared 20 ms gain ramp plus vector boundary

    def parameter(self,identity,value,normalized=False):
        info=self.expected["parameters"][identity]
        require(math.isfinite(value),"Parameter value must be finite")
        require((0<=value<=1) if normalized else info["minimum"]<=value<=info["maximum"],"Parameter value outside fixture bounds")
        command=f"{'normalized' if normalized else 'param'} {info['index']} {value:.9g}"
        self.control(command,lambda r:r.get("queued") is True)

    def midi(self,status,a,b):
        self.control(f"midi {status} {a} {b}",lambda r:r.get("queued") is True)

    def ready(self):
        return self.wait(lambda s:s["panic"] and s["ready_to_resume"] and not s["rebuilding"],"detached Panic reconstruction")

    def resume(self):
        self.control("resume",lambda r:r.get("resume_requested") is True)
        self.wait(lambda s:not s["panic"] and not s["rebuilding"] and not s["ready_to_resume"],"running module")
        self.sleep(0.08)

    def capture(self,name,*,frequency=None,peak=None,silent=False):
        self.status()
        result=record(self.transport,board=self.expected["board"],frames=RATE,
                      clock=self.clock,sleep=self.sleep)
        measured=metrics(result.pcm,result.metadata["channels"])
        output,sidecar=save(result,self.out/f"{name}.wav")
        case={"name":name,"wav":output.name,"evidence":sidecar.name,
              "pcm_sha256":result.metadata["pcm_sha256"],"measurements":measured,
              "expected_frequency_hz":frequency,"expected_peak":peak,"expected_silent":silent}
        self.cases.append(case)
        for channel in measured:
            if silent:require(channel["nonzero_samples"]==0,f"{name}: expected exact PCM silence")
            else:
                require(channel["positive_crossing_frequency_hz"] is not None and abs(channel["positive_crossing_frequency_hz"]-frequency)<0.1,
                        f"{name}: measured pitch differs from {frequency} Hz")
                require(abs(channel["peak"]-peak)<max(2/32767,peak*0.005),f"{name}: PCM peak differs from declared headroom/gain")
                require(abs(channel["rms"]-peak/math.sqrt(2))<max(3/32767,peak*0.01),f"{name}: unexpected RMS")
        self.status()
        return case

    def volume_cases(self,frequency,full_peak):
        by_volume={}
        for volume in (25,100,50,0):
            self.volume(volume)
            by_volume[volume]=self.capture(f"volume-{volume}",frequency=frequency,
                                          peak=full_peak*volume/100,silent=volume==0)
        reference=by_volume[100]["measurements"]
        for volume in (25,50):
            ratios=[]
            for value,full in zip(by_volume[volume]["measurements"],reference):
                ratio=value["rms"]/full["rms"]
                require(abs(ratio-volume/100)<0.005,f"Volume {volume}: wrong amplitude ratio to unity volume")
                ratios.append(ratio)
            by_volume[volume]["rms_ratio_to_volume_100"]=ratios
        self.volume(25)

    def run_sine(self):
        self.parameter("frequency",440);self.parameter("level",0.2);self.sleep(0.08)
        self.volume_cases(440,0.1)
        self.parameter("frequency",880);self.sleep(0.08)
        self.capture("frequency-actual-880",frequency=880,peak=0.025)
        self.parameter("frequency",(1320-20)/(10000-20),normalized=True);self.sleep(0.08)
        self.capture("frequency-normalized-1320",frequency=1320,peak=0.025)
        self.control("panic",lambda r:r.get("panic") is True);self.ready()
        self.capture("panic",silent=True)
        self.resume()
        self.capture("resumed",frequency=1320,peak=0.025)

    def run_midi4(self):
        require(self.idle_midi_baseline,"MIDI4 qualification requires an explicitly known idle/no-held-note baseline")
        self.capture("initial-idle",silent=True)
        self.parameter("level",0.1);self.parameter("poly/level",0.1);self.sleep(0.08)
        self.midi(0x90,69,100);self.sleep(0.12)
        full_peak=0.1*(100/127)*0.8*0.5
        self.volume_cases(440,full_peak)
        self.midi(0x90,69,0);self.sleep(0.12)
        self.capture("velocity-zero-release",silent=True)
        self.midi(0x90,81,100);self.sleep(0.12)
        self.capture("note-81",frequency=880,peak=full_peak*0.25)
        self.midi(0x80,81,64);self.sleep(0.12)
        self.capture("note-off",silent=True)
        self.midi(0x90,69,100);self.sleep(0.12)
        self.midi(0xb0,64,127);self.midi(0x80,69,64);self.sleep(0.12)
        self.capture("sustain-held",frequency=440,peak=full_peak*0.25)
        self.midi(0xb0,64,0);self.sleep(0.12)
        self.capture("sustain-released",silent=True)
        self.run_midi4_chord(full_peak*0.25)
        self.midi(0x90,69,100);self.sleep(0.12)
        self.control("panic",lambda r:r.get("panic") is True);self.ready()
        self.capture("panic",silent=True)
        self.resume();self.capture("resumed-idle",silent=True)
        self.midi(0x90,69,100);self.sleep(0.12)
        self.capture("resumed-note",frequency=440,peak=full_peak*0.25)
        self.midi(0x80,69,64);self.sleep(0.12)

    def capture_projected(self,name,*,present,absent,amplitude):
        before=self.status()
        result=record(self.transport,board=self.expected["board"],frames=RATE,
                      clock=self.clock,sleep=self.sleep)
        output,sidecar=save(result,self.out/f"{name}.wav")
        measured=metrics(result.pcm,result.metadata["channels"])
        for channel in measured:channel.pop("positive_crossing_frequency_hz",None)
        case={"name":name,"wav":output.name,"evidence":sidecar.name,
              "pcm_sha256":result.metadata["pcm_sha256"],"measurements":measured,
              "measurement_policy":"independent sine/cosine projections; no zero-crossing pitch assertion for polyphonic audio",
              "expected_active_voices":len(present),"expected_present_notes":present,"expected_absent_notes":absent,
              "expected_partial_amplitude":amplitude,"present_amplitude_bounds":[amplitude*0.8,amplitude*1.2],
              "absent_amplitude_ceiling":max(amplitude*0.15,3/32767),"status_before":before}
        self.cases.append(case)
        case["projections"]=projected_notes(result.pcm,result.metadata["channels"],present,absent,amplitude)
        case["status_after"]=self.status()
        return case

    def run_midi4_chord(self,amplitude):
        chord=[60,64,67,71]
        for note in chord:
            self.midi(0x90,note,100);self.sleep(0.04) # distinct note ages for oldest-voice policy
        self.sleep(0.12)
        self.capture_projected("four-voice-chord",present=chord,absent=[74],amplitude=amplitude)
        self.midi(0x80,60,64);self.sleep(0.12)
        self.capture_projected("chord-release-60",present=[64,67,71],absent=[60,74],amplitude=amplitude)
        # Rebuild all four in original order. Re-triggering only 60 would make
        # it newest, so the following fifth note would correctly steal 64.
        for note in chord:self.midi(0x80,note,64)
        self.sleep(0.12)
        for note in chord:
            self.midi(0x90,note,100);self.sleep(0.04)
        self.sleep(0.12)
        self.capture_projected("four-voice-restored-chord",present=chord,absent=[74],amplitude=amplitude)
        self.midi(0x90,74,100);self.sleep(0.12)
        self.capture_projected("fifth-note-oldest-steal",present=[64,67,71,74],absent=[60],amplitude=amplitude)
        self.midi(0x80,60,64);self.sleep(0.12)
        self.capture_projected("stale-stolen-note-off",present=[64,67,71,74],absent=[60],amplitude=amplitude)
        for note in chord+[74]:self.midi(0x80,note,64)
        self.sleep(0.12)
        self.capture("chord-all-released",silent=True)

    def restore_original(self):
        current=self.status(healthy=False)
        require(not current["allocation_fault"] and not current["reconstruction_failed"],"Device fault prevents restoration")
        if current["panic"]:
            self.ready();self.resume()
        if self.expected["fixture"]=="midi4":
            self.midi(0xb0,64,0);self.midi(0xb0,123,0);self.sleep(0.12)
        for identity in self.expected["parameters"]:
            self.parameter(identity,self.restore[identity])
        self.sleep(0.08)
        self.volume(self.original["volume"])
        if self.original["panic"]:
            self.control("panic",lambda r:r.get("panic") is True);self.ready()
        final=self.status()
        require(final["volume"]==self.original["volume"] and final["panic"]==self.original["panic"],"Volume/running state restoration did not complete")
        return {"result":"restored","requested_actual_parameters":self.restore,
                "original_volume":self.original["volume"],"original_panic":self.original["panic"],
                "final_status":final,"parameter_readback_available":False,
                "parameter_verification":"setter acknowledgements and settled audio-owner processing; no live parameter getter",
                "instance_phase_and_effect_state_restored":False}

    def run(self):
        require(not self.out.exists(),"Use a new qualification output directory")
        require(set(self.restore)==set(self.expected["parameters"]),"Supply exact known original actual values for every fixture parameter")
        for identity,value in self.restore.items():
            info=self.expected["parameters"][identity]
            require(type(value) in (int,float) and math.isfinite(value) and info["minimum"]<=value<=info["maximum"],f"Invalid original actual value for {identity}")
        self.out.mkdir(parents=True)
        error=None;restoration={"result":"not-needed-no-controls-sent"}
        try:
            # An early shell response can precede the first telemetry snapshot
            # and contain default zero volume/frames. Never restore that as if
            # it were the running device's settled original volume.
            self.original=self.wait(lambda s:s["frames"]>=512 and s["audio_stack_free"]>0,
                                    "initial settled audio-owner telemetry")
            if self.expected["fixture"]=="midi4":
                require(self.idle_midi_baseline,"MIDI4 requires --idle-midi-baseline")
            self.eligible_to_restore=True
            # First live mutation deliberately reduces output to 25 percent.
            self.volume(25)
            if self.original["panic"]:self.ready();self.resume()
            if self.expected["fixture"]=="sine":self.run_sine()
            else:self.run_midi4()
        except (CaptureError,OSError,ValueError) as exc:
            error=str(exc)
        finally:
            if self.eligible_to_restore:
                try:restoration=self.restore_original()
                except (CaptureError,OSError,ValueError) as exc:
                    restoration={"result":"failed","error":str(exc)}
                    if error is None:error="Qualification completed, but original controls could not be restored"
        report={"format":"rnbo-esp32s3-target-audio-qualification","format_version":1,
                "result":"failed" if error else "passed","error":error,"expected":self.expected,
                "fixture":self.expected["fixture"],"sample_rate":RATE,"block_frames":256,
                "capture_frames_per_case":RATE,"physical_sink_channels":BOARDS[self.expected["board"]][1],
                "pcm_headroom":0.5,"cases":self.cases,"commands":self.commands,
                "status_snapshots":self.snapshots,"restoration":restoration,
                "audio_stack_free_units":"raw firmware status; units not advertised by protocol",
                "render_timing_scope":"latest vector and lifetime observed peak; no overrun counter advertised",
                "baseline_scope":"first settled status on the supplied connection; no pre-open device state inferred",
                "cpu_overrun_absence_proven":False,"external_audio_or_listening_verified":False,
                "display_or_touch_verified":False,"wifi_stress_qualified":False,
                "completed_at_utc":datetime.now(timezone.utc).isoformat(),
                "qualification_tool_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (self.out/"qualification.json").write_bytes(canonical(report))
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",required=True)
    parser.add_argument("--firmware-report",type=Path,required=True)
    parser.add_argument("--prepared",type=Path,required=True)
    parser.add_argument("--fixture",choices=("sine","midi4"),required=True)
    parser.add_argument("--restore",action="append",default=[],metavar="STABLE_ID=ACTUAL_VALUE")
    parser.add_argument("--idle-midi-baseline",action="store_true")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--command-timeout",type=float,default=2)
    args=parser.parse_args()
    stream=None
    try:
        expected=expectations(args.firmware_report,args.prepared,args.fixture)
        restored={}
        for item in args.restore:
            identity,separator,value=item.partition("=")
            require(separator and identity not in restored,"--restore must contain unique STABLE_ID=ACTUAL_VALUE entries")
            restored[identity]=float(value)
        require(not args.out.exists(),"Use a new output directory")
        require(set(restored)==set(expected["parameters"]),"--restore must supply every fixture parameter's known original actual value")
        stream=open_serial(args.port,115200,args.command_timeout)
        report=Qualification(JsonLineTransport(stream,args.command_timeout),expected,args.out.resolve(),restored,
                             idle_midi_baseline=args.idle_midi_baseline).run()
    except (CaptureError,OSError,ValueError) as exc:
        parser.exit(1,f"Qualification failed: {exc}\n")
    finally:
        if stream is not None:stream.close()
    print(json.dumps({"result":report["result"],"report":str((args.out/"qualification.json").resolve()),
                      "error":report["error"],"restoration":report["restoration"]["result"]}))
    if report["result"]!="passed":raise SystemExit(1)


if __name__=="__main__":main()
