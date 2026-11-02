#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stress the known MIDI4 fixture with concurrent live events and PCM capture.

Uses one serial connection, locks one transaction at a time, and never flashes,
resets or uploads. Require an explicitly known idle baseline and original
actual values for every parameter. Evidence describes submitted PCM and sampled
diagnostics; it does not verify electrical output or establish a hard CPU bound.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import threading
import time

from capture import CaptureError, JsonLineTransport, RATE, integer, open_serial, record, save
from qualify_audio import BLOCK_US, Qualification, canonical, expectations, metrics, require

INITIAL_NOTES = (48, 55, 60, 67)
NOTE_POOL = (48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77)
MEMORY_FIELDS = ("internal_free_bytes", "internal_largest_free_bytes", "psram_free_bytes",
                 "psram_largest_free_bytes", "audio_stack_free", "control_stack_free", "main_stack_free")
TOTAL_FIELDS = ("blocks", "render_busy_total_us", "render_deadline_overruns",
                "driver_elapsed_total_us", "post_write_capture_elapsed_total_us",
                "audio_heap_requested_bytes", "frames", "uptime_us")
SOURCE_SHA256_AT_START = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def due_slot(start: float, now: float, slot: int, rate: float) -> tuple[int, float, int]:
    """Skip expired slots instead of sending catch-up bursts after contention."""
    deadline = start + slot / rate
    skipped = max(0, int(math.floor((now - deadline) * rate + 1e-9)))
    slot += skipped
    return slot, start + slot / rate, skipped


class EventPlan:
    def __init__(self, level_index: int):
        self.level_index = level_index
        self.active = list(INITIAL_NOTES)
        self.seen = set(self.active)
        self.next_note = 0
        self.stolen = None

    def event(self, sequence: int) -> dict:
        kind = sequence % 4
        if kind == 0:
            value = 0.09 if (sequence // 4) % 2 == 0 else 0.1
            result = {"kind": "level", "command": f"param {self.level_index} {value:.9g}"}
        elif kind == 1:
            value = 16 if (sequence // 4) % 2 == 0 else 112
            result = {"kind": "cc1", "command": f"midi 176 1 {value}"}
        elif kind == 2:
            while NOTE_POOL[self.next_note % len(NOTE_POOL)] in self.active:
                self.next_note += 1
            note = NOTE_POOL[self.next_note % len(NOTE_POOL)]
            self.next_note += 1
            self.stolen = self.active.pop(0)
            self.active.append(note)
            self.seen.add(note)
            result = {"kind": "note-on-steal", "command": f"midi 144 {note} 100", "stolen_note": self.stolen}
        else:
            require(self.stolen is not None and self.stolen not in self.active, "Invalid stale note-off schedule")
            result = {"kind": "stale-note-off", "command": f"midi 128 {self.stolen} 64"}
        result["active_notes"] = list(self.active)
        return result


def diagnostics(before: dict, after: dict, samples: list[dict]) -> dict:
    deltas = {}
    for field in TOTAL_FIELDS:
        if field in before and field in after:
            a = integer(before[field], field, 0, 0xffffffffffffffff)
            b = integer(after[field], field, a, 0xffffffffffffffff)
            deltas[field] = b - a
    blocks = deltas.get("blocks", 0)
    busy = deltas.get("render_busy_total_us")
    average = busy / blocks if blocks and busy is not None else None
    ranges = {}
    for field in MEMORY_FIELDS:
        values = [integer(row[field], field, 0, 0xffffffff) for row in samples if field in row]
        if values:
            ranges[field] = {"minimum": min(values), "maximum": max(values), "first": values[0], "last": values[-1]}
    return {"counter_deltas": deltas, "average_owner_through_pcm_us": average,
            "average_owner_through_pcm_percent": average / BLOCK_US * 100 if average is not None else None,
            "largest_sampled_latest_render_us": max((s["render_us"] for s in samples), default=None),
            "lifetime_peak_render_us_before": before.get("peak_us"), "lifetime_peak_render_us_after": after.get("peak_us"),
            "memory_and_stack_samples": ranges, "stack_units": "raw firmware values; protocol does not advertise units",
            "render_timing_scope": after.get("render_timing_scope", "not advertised"),
            "driver_timing_scope": after.get("driver_timing_scope", "not advertised"),
            "driver_elapsed_is_cpu_busy_time": False,
            "overrun_counter_advertised": "render_deadline_overruns" in deltas,
            "peak_is_observed_not_hard_bound": True}


class Audit:
    def __init__(self, output: Path, *, clock=time.monotonic):
        self.clock = clock
        self.local = threading.local()
        self.lock = threading.Lock()
        self.file = (output / "transactions.jsonl").open("x")

    def close(self):
        self.file.close()

    def record(self, entry):
        with self.lock:
            self.file.write(json.dumps(entry, sort_keys=True, allow_nan=False) + "\n")
            self.file.flush()


class AuditStream:
    """Observe the actual write while JsonLineTransport holds its request lock."""
    def __init__(self, stream, audit: Audit):
        self.stream = stream; self.audit = audit

    @property
    def in_waiting(self):
        return self.stream.in_waiting

    def read(self, size):
        return self.stream.read(size)

    def write(self, payload):
        entry = getattr(self.audit.local, "request", None)
        if entry is not None:
            entry["dispatch_monotonic"] = self.audit.clock()
            entry["dispatch_utc"] = utc_now()
        written = self.stream.write(payload)
        if entry is not None:
            entry["write_completed_monotonic"] = self.audit.clock()
            entry["written_bytes"] = written
        return written


class AuditedTransport:
    def __init__(self, transport, audit: Audit):
        self.transport = transport; self.audit = audit

    def request(self, command):
        entry = {"command": command, "thread": threading.current_thread().name,
                 "requested_monotonic": self.audit.clock()}
        self.audit.local.request = entry
        try:
            response = self.transport.request(command)
            entry["response"] = {key: value for key, value in response.items() if key != "data"}
            if "data" in response:
                entry["response_hex_characters"] = len(response["data"])
            return response
        except Exception as error:
            entry["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            entry["completed_monotonic"] = self.audit.clock()
            self.audit.record(entry)
            event = getattr(self.audit.local, "event", None)
            if event is not None and event["command"] == command:
                event.update({key: entry[key] for key in ("dispatch_monotonic", "dispatch_utc", "write_completed_monotonic", "completed_monotonic", "error") if key in entry})
            self.audit.local.request = None


class SoakQualification(Qualification):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_lock = threading.RLock()
        self.strict = True
        self.last_frames = None
        self.last_device_id = None
        self.status_file = None

    def status(self, *, healthy=True):
        # Serialize status acquisition and monotonic validation together; two
        # threads must not process older replies after a newer reply.
        with self.status_lock:
            status = super().status(healthy=healthy or self.strict)
            if self.last_frames is not None:
                require(status["frames"] >= self.last_frames, "Audio frame clock restarted during soak")
                require(status.get("device_id") == self.last_device_id, "Device identity changed during soak")
            self.last_frames = status["frames"]
            self.last_device_id = status.get("device_id")
            if self.status_file:
                self.status_file.write(json.dumps({"observed_monotonic": self.clock(), "observed_at_utc": utc_now(), **status}, sort_keys=True, allow_nan=False) + "\n")
                self.status_file.flush()
            return status


class CheckedCaptureTransport:
    def __init__(self, qualification):
        self.q = qualification

    def request(self, command):
        status = self.q.status() # identity and fault check before every chunk/control
        return status if command == "status" else self.q.transport.request(command)


class Soak:
    def __init__(self, q: SoakQualification, audit: Audit, *, duration=300.0, event_hz=8.0,
                 capture_interval=30.0, reconstruction_cycles=10):
        self.q = q; self.audit = audit
        self.duration = duration; self.event_hz = event_hz
        self.capture_interval = capture_interval; self.reconstruction_cycles = reconstruction_cycles
        self.plan = EventPlan(q.expected["parameters"]["level"]["index"])
        self.stop = threading.Event(); self.thread_error = None
        self.events = []; self.captures = []; self.probe = []
        self.thread = None
        self.memory_result = None

    def produce(self, start):
        slot = sequence = 0
        fields = ("sequence", "slot", "kind", "command", "scheduled_monotonic", "dispatch_monotonic", "dispatch_utc",
                  "completed_monotonic", "lateness_ms", "transaction_ms", "skipped_slots", "active_notes", "stolen_note", "acknowledged", "error")
        with (self.q.out / "events.csv").open("x", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            try:
                while not self.stop.is_set():
                    slot, deadline, skipped = due_slot(start, self.q.clock(), slot, self.event_hz)
                    if deadline >= start + self.duration:
                        break
                    if self.stop.wait(max(0.0, deadline - self.q.clock())):
                        break
                    entry = {"sequence": sequence, "slot": slot, "scheduled_monotonic": deadline,
                             "skipped_slots": skipped, **self.plan.event(sequence)}
                    self.audit.local.event = entry
                    try:
                        self.q.control(entry["command"], lambda response: response.get("queued") is True)
                        entry["acknowledged"] = True
                    except Exception as error:
                        entry["acknowledged"] = False
                        entry["error"] = f"{type(error).__name__}: {error}"
                        raise
                    finally:
                        self.audit.local.event = None
                        if "dispatch_monotonic" in entry:
                            entry["lateness_ms"] = (entry["dispatch_monotonic"] - deadline) * 1000
                            entry["transaction_ms"] = (entry["completed_monotonic"] - entry["dispatch_monotonic"]) * 1000
                        self.events.append(entry)
                        writer.writerow({**entry, "active_notes": json.dumps(entry["active_notes"])})
                        output.flush()
                    slot += 1; sequence += 1
            except Exception as error:
                self.thread_error = f"{type(error).__name__}: {error}"
                self.stop.set()

    def capture(self, number):
        before = self.q.status()
        result = record(CheckedCaptureTransport(self.q), board=self.q.expected["board"], frames=RATE,
                        clock=self.q.clock, sleep=self.q.sleep)
        wav, evidence = save(result, self.q.out / f"stress-{number:03}.wav")
        measured = metrics(result.pcm, result.metadata["channels"])
        for channel in measured:
            channel.pop("positive_crossing_frequency_hz", None)
        case = {"wav": wav.name, "evidence": evidence.name, "pcm_sha256": result.metadata["pcm_sha256"],
                "measurements": measured, "status_before": before, "status_after": self.q.status(),
                "notes_change_during_capture": True, "fixed_partial_pitch_assertion": False}
        self.captures.append(case)
        require(all(channel["nonzero_samples"] > 0 and channel["rms"] > 0.0001 and channel["peak"] < 1 for channel in measured),
                "Stress capture is silent, too small or saturated")

    def release_notes(self):
        current = self.q.status(healthy=False)
        if current["panic"]:
            self.q.ready(); self.q.resume()
        self.q.midi(0xb0, 64, 0)
        # Include every attempted note-on, so an acknowledged-response failure
        # cannot leave an old or newly stolen note outside the cleanup set.
        for note in sorted(self.plan.seen):
            self.q.midi(0x80, note, 64)
        self.q.sleep(0.2)

    def memory_probe(self):
        before = self.q.status()
        result = {"cycles_requested": self.reconstruction_cycles, "status_before": before,
                  "status_after": None, "samples": self.probe, "separate_from_stress_timing": True}
        self.memory_result = result
        for cycle in range(self.reconstruction_cycles):
            self.q.control("panic", lambda response: response.get("panic") is True)
            self.q.ready(); self.q.resume()
            self.probe.append({"cycle": cycle + 1, "status": self.q.status()})
        after = self.q.status()
        result.update(cycles_completed=len(self.probe), status_after=after)
        for field in ("internal_free_bytes", "psram_free_bytes"):
            if field in before and field in after:
                result[field + "_delta"] = after[field] - before[field]
                require(after[field] >= before[field], f"Reconstruction probe ended with less {field}; inspect heap snapshots")
        return result

    def run(self):
        q = self.q
        require(q.expected["fixture"] == "midi4" and q.idle_midi_baseline, "Soak requires the known MIDI4 fixture and --idle-midi-baseline")
        require(set(q.restore) == set(q.expected["parameters"]), "Supply every known original actual parameter value")
        for identity, value in q.restore.items():
            info = q.expected["parameters"][identity]
            require(math.isfinite(value) and info["minimum"] <= value <= info["maximum"], f"Invalid restore value: {identity}")
        require(math.isfinite(self.duration) and 1 <= self.duration <= 3600, "Duration must be 1..3600 seconds")
        require(math.isfinite(self.event_hz) and 0 < self.event_hz <= 16, "Event rate must be greater than zero and at most 16 Hz")
        require(math.isfinite(self.capture_interval) and self.capture_interval >= 2, "Capture interval must be at least two seconds")
        integer(self.reconstruction_cycles, "Reconstruction cycles", 0, 100)
        error = None; restoration = {"result": "not-needed-no-controls-sent"}
        stress = None; memory = None; started = ended = None
        q.status_file = (q.out / "statuses.jsonl").open("x")
        try:
            q.original = q.wait(lambda status: status["frames"] >= 512 and status["audio_stack_free"] > 0, "settled original telemetry")
            q.eligible_to_restore = True
            q.volume(25) # first mutation reduces output
            if q.original["panic"]:
                q.ready(); q.resume()
            q.capture("baseline-idle", silent=True)
            q.parameter("level", 0.1); q.parameter("poly/level", 0.1)
            for note in INITIAL_NOTES:
                q.midi(0x90, note, 100); q.sleep(0.04)
            q.sleep(0.12)
            q.capture_projected("baseline-four-voice", present=list(INITIAL_NOTES), absent=[74],
                                amplitude=0.1 * (100 / 127) * 0.8 * 0.5 * 0.25)
            before = q.status(); snapshot_start = len(q.snapshots) - 1
            started = q.clock()
            self.thread = threading.Thread(target=self.produce, args=(started,), name="soak-events")
            self.thread.start()
            next_capture = started + self.capture_interval
            while q.clock() < started + self.duration and not self.stop.is_set():
                now = q.clock()
                if now >= next_capture:
                    self.capture(len(self.captures) + 1)
                    while next_capture <= q.clock():
                        next_capture += self.capture_interval
                else:
                    q.status()
                    self.stop.wait(min(1.0, max(0.0, next_capture - now), max(0.0, started + self.duration - now)))
            self.stop.set(); self.thread.join()
            ended = q.clock()
            if self.thread_error:
                raise CaptureError(self.thread_error)
            after = q.status()
            stress = diagnostics(before, after, q.snapshots[snapshot_start:])
            require(stress["counter_deltas"].get("render_deadline_overruns", 0) == 0, "Render deadline overrun counter increased during stress")
            self.release_notes()
            q.capture("stress-released", silent=True)
            if self.reconstruction_cycles:
                memory = self.memory_probe()
        except (Exception, KeyboardInterrupt) as failure:
            error = f"{type(failure).__name__}: {failure}"
        finally:
            self.stop.set()
            if self.thread is not None:
                # Serial request and write timeouts are bounded. Never send
                # restoration controls alongside a still-running producer.
                self.thread.join()
            q.strict = False
            if q.eligible_to_restore:
                try:
                    self.release_notes()
                    restoration = q.restore_original()
                except Exception as failure:
                    restoration = {"result": "failed", "error": f"{type(failure).__name__}: {failure}"}
                    if error is None:
                        error = "Stress completed, but known original controls could not be restored"
            q.status_file.close(); q.status_file = None
        dispatched = [row for row in self.events if "dispatch_monotonic" in row]
        lateness = [row["lateness_ms"] for row in dispatched]
        intervals = [b["dispatch_monotonic"] - a["dispatch_monotonic"] for a, b in zip(dispatched, dispatched[1:])]
        timing = {"requested_hz": self.event_hz, "requested_duration_seconds": self.duration,
                  "requested_schedule_slots": math.ceil(self.duration * self.event_hz),
                  "started_monotonic": started, "finished_observation_monotonic": ended,
                  "observation_seconds": ended - started if ended is not None and started is not None else None,
                  "attempted_events": len(self.events), "dispatched_events": len(dispatched),
                  "unattempted_schedule_slots": max(0, math.ceil(self.duration * self.event_hz) - len(self.events)),
                  "acknowledged_events": sum(bool(row.get("acknowledged")) for row in self.events),
                  "skipped_expired_slots": sum(row["skipped_slots"] for row in self.events),
                  "mean_lateness_ms": statistics.fmean(lateness) if lateness else None,
                  "maximum_lateness_ms": max(lateness, default=None),
                  "late_at_least_one_period": sum(value >= 1000 / self.event_hz for value in lateness),
                  "minimum_dispatch_interval_seconds": min(intervals, default=None),
                  "maximum_dispatch_interval_seconds": max(intervals, default=None),
                  "measured_dispatch_hz": (len(dispatched) - 1) / (dispatched[-1]["dispatch_monotonic"] - dispatched[0]["dispatch_monotonic"]) if len(dispatched) > 1 else None,
                  "timing_measurement": "actual serial write entry inside the per-request transport lock; no exact-rate promise"}
        report = {"format": "rnbo-esp32s3-midi4-soak", "format_version": 1, "result": "failed" if error else "passed", "error": error,
                  "expected": q.expected, "original_status": q.original, "event_timing": timing, "stress_diagnostics": stress,
                  "periodic_captures": self.captures, "setup_and_release_cases": q.cases,
                  "reconstruction_memory_probe": memory or self.memory_result, "restoration": restoration,
                  "producer_error": self.thread_error,
                  "transactions_file": "transactions.jsonl", "events_file": "events.csv", "status_snapshots_file": "statuses.jsonl",
                  "wifi_stress_qualified": False, "external_audio_or_listening_verified": False,
                  "display_or_touch_verified": False, "peak_is_observed_not_hard_bound": True,
                  "completed_at_utc": utc_now(), "soak_tool_sha256": SOURCE_SHA256_AT_START,
                  "soak_source_changed_during_run": hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != SOURCE_SHA256_AT_START}
        (q.out / "soak.json").write_bytes(canonical(report))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--firmware-report", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--restore", action="append", default=[], metavar="STABLE_ID=ACTUAL_VALUE")
    parser.add_argument("--idle-midi-baseline", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--event-hz", type=float, default=8)
    parser.add_argument("--capture-interval", type=float, default=30)
    parser.add_argument("--reconstruction-cycles", type=int, default=10)
    parser.add_argument("--command-timeout", type=float, default=2)
    args = parser.parse_args()
    stream = audit = None
    try:
        expected = expectations(args.firmware_report, args.prepared, "midi4")
        restore = {}
        for item in args.restore:
            identity, separator, value = item.partition("=")
            require(separator and identity not in restore, "--restore requires unique STABLE_ID=ACTUAL_VALUE entries")
            restore[identity] = float(value)
        require(args.idle_midi_baseline, "Supply --idle-midi-baseline for the explicitly known no-held-note state")
        require(set(restore) == set(expected["parameters"]), "Supply every known original actual parameter value")
        require(not args.out.exists() and not args.out.is_symlink(), "Use a new output directory")
        output = args.out.resolve(); output.mkdir(parents=True)
        audit = Audit(output)
        stream = open_serial(args.port, 115200, args.command_timeout)
        transport = AuditedTransport(JsonLineTransport(AuditStream(stream, audit), args.command_timeout), audit)
        q = SoakQualification(transport, expected, output, restore, idle_midi_baseline=True)
        report = Soak(q, audit, duration=args.duration, event_hz=args.event_hz, capture_interval=args.capture_interval,
                      reconstruction_cycles=args.reconstruction_cycles).run()
    except (CaptureError, OSError, ValueError) as failure:
        parser.exit(1, f"Soak failed: {failure}\n")
    finally:
        if audit is not None:
            audit.close()
        if stream is not None:
            stream.close()
    print(json.dumps({"result": report["result"], "error": report["error"], "report": str(output / "soak.json"), "restoration": report["restoration"]["result"]}))
    if report["result"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
