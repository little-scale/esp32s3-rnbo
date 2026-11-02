# SPDX-License-Identifier: MIT
"""Offline schedule/diagnostic/actual-dispatch checks; no port is opened."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from capture import CaptureError, JsonLineTransport
from soak_audio import Audit, AuditedTransport, AuditStream, EventPlan, Soak, diagnostics, due_slot


class SoakTests(unittest.TestCase):
    def test_schedule_keeps_four_distinct_notes_and_only_releases_stolen_notes(self):
        plan = EventPlan(3)
        previous = set(plan.active)
        for sequence in range(2400):
            row = plan.event(sequence)
            active = row["active_notes"]
            self.assertEqual(len(active), 4)
            self.assertEqual(len(set(active)), 4)
            if row["kind"] == "note-on-steal":
                note = int(row["command"].split()[2])
                self.assertNotIn(note, previous)
                self.assertEqual(len(set(active) & previous), 3)
            elif row["kind"] == "stale-note-off":
                self.assertNotIn(int(row["command"].split()[2]), active)
            previous = set(active)
        slot, deadline, skipped = due_slot(100, 101.05, 0, 8)
        self.assertEqual((slot, deadline, skipped), (8, 101.0, 8))
        self.assertEqual(due_slot(100, 100.1, 1, 8), (1, 100.125, 0))

    def test_diagnostics_use_counter_deltas_and_preserve_timing_scopes(self):
        before = {"blocks": 100, "render_busy_total_us": 200000, "render_deadline_overruns": 2,
                  "driver_elapsed_total_us": 300000, "peak_us": 9000}
        after = {"blocks": 110, "render_busy_total_us": 220000, "render_deadline_overruns": 2,
                 "driver_elapsed_total_us": 340000, "peak_us": 9000,
                 "render_timing_scope": "owner through PCM", "driver_timing_scope": "includes wait"}
        measured = diagnostics(before, after, [{"render_us": 1800, "internal_free_bytes": 100}, {"render_us": 2100, "internal_free_bytes": 120}])
        self.assertEqual(measured["average_owner_through_pcm_us"], 2000)
        self.assertEqual(measured["counter_deltas"]["render_deadline_overruns"], 0)
        self.assertEqual(measured["largest_sampled_latest_render_us"], 2100)
        self.assertEqual(measured["lifetime_peak_render_us_after"], 9000)
        self.assertFalse(measured["driver_elapsed_is_cpu_busy_time"])
        with self.assertRaises(CaptureError):
            diagnostics(before, {**after, "blocks": 99}, [])

    def test_dispatch_observation_occurs_at_actual_stream_write_and_omits_bulk_hex(self):
        class Clock:
            value = 10.0
            def __call__(self):
                self.value += 0.001
                return self.value
        class Stream:
            response = bytearray()
            @property
            def in_waiting(self): return len(self.response)
            def write(self, data):
                self.response.extend(b'{"capture_id":1,"offset":0,"data":"0000"}\n')
                return len(data)
            def read(self, size):
                data = bytes(self.response[:size]); del self.response[:size]; return data
        with tempfile.TemporaryDirectory() as directory:
            clock = Clock(); audit = Audit(Path(directory), clock=clock)
            transport = AuditedTransport(JsonLineTransport(AuditStream(Stream(), audit), clock=clock), audit)
            event = {"command": "capread 1 0 2"}; audit.local.event = event
            self.assertEqual(transport.request(event["command"])["data"], "0000")
            audit.close()
            row = json.loads((Path(directory) / "transactions.jsonl").read_text())
            self.assertGreater(row["dispatch_monotonic"], row["requested_monotonic"])
            self.assertGreater(row["completed_monotonic"], row["dispatch_monotonic"])
            self.assertNotIn("data", row["response"])
            self.assertEqual(row["response_hex_characters"], 4)
            self.assertEqual(event["dispatch_monotonic"], row["dispatch_monotonic"])

    def test_failure_stops_producer_before_restoring_known_controls(self):
        from test_qualify_audio import expected
        with tempfile.TemporaryDirectory() as directory:
            active = threading.Event()
            stopped = threading.Event()
            class Q:
                def __init__(self):
                    self.expected = expected("midi4"); self.idle_midi_baseline = True
                    self.restore = {"level": 0.1, "poly/level": 0.1}; self.out = Path(directory)
                    self.clock = time.monotonic; self.sleep = lambda _: None
                    self.eligible_to_restore = False; self.snapshots = []; self.cases = []
                    self.failed = False; self.restored = False
                def status(self, **_):
                    if active.is_set() and not self.failed:
                        self.failed = True
                        raise CaptureError("injected diagnostic failure")
                    result = {"frames": 1024, "audio_stack_free": 4000, "volume": 81, "panic": False}
                    self.snapshots.append(result); return result
                def wait(self, *_): return self.status()
                def volume(self, *_): pass
                def parameter(self, *_): pass
                def midi(self, *_): pass
                def capture(self, *_args, **_kwargs): pass
                def capture_projected(self, *_args, **_kwargs): pass
                def restore_original(self):
                    self.assert_stopped = stopped.is_set() and not active.is_set()
                    self.restored = True
                    return {"result": "restored"}
            q = Q(); audit = Audit(Path(directory))
            soak = Soak(q, audit, duration=1, reconstruction_cycles=0)
            def producer(_start):
                active.set()
                try: soak.stop.wait(2)
                finally: active.clear(); stopped.set()
            with mock.patch.object(soak, "produce", producer):
                report = soak.run()
            audit.close()
            self.assertEqual(report["result"], "failed")
            self.assertIn("injected diagnostic failure", report["error"])
            self.assertTrue(q.restored and q.assert_stopped)
            self.assertFalse(soak.thread.is_alive())
            self.assertTrue((Path(directory) / "soak.json").is_file())


if __name__ == "__main__":
    unittest.main()
