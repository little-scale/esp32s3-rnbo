# SPDX-License-Identifier: MIT
"""Admission, actual model adapter and incomplete-result diagnostic guards."""
import array
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import qualify_wave4 as q


class Wave4QualifierTests(unittest.TestCase):
    def test_exact_catalog_does_not_accept_changed_gate_or_surface(self):
        catalog = q.load_catalog()
        self.assertEqual(len(catalog["fixtures"]), 13)
        self.assertEqual(sum(len(f["cases"]) for f in catalog["fixtures"]), 39)
        self.assertEqual(sum(f["surface"] == "codebox" for f in catalog["fixtures"]), 2)
        for change in (lambda c: c["fixtures"].pop(),
                       lambda c: c["fixtures"][0]["semantic"].update(maximum_absolute_error=1e-6),
                       lambda c: c["fixtures"][0]["source"].update(surface="codebox"),
                       lambda c: c["fixtures"][0]["cases"][0].update(warmup_blocks=0)):
            changed = copy.deepcopy(catalog); change(changed)
            with self.assertRaises(q.QualificationError): q.load_catalog(json.dumps(changed).encode())
        for data in (None, bytearray(b"{}"), "{}", b"{}"):
            if data is None: continue  # None intentionally loads the original catalog.
            with self.assertRaises(q.QualificationError): q.load_catalog(data)

    def test_no_output_or_tools_on_invalid_options_or_directory(self):
        with tempfile.TemporaryDirectory(dir=q.ROOT / "build") as temporary:
            path = Path(temporary) / "must-not-exist"
            with mock.patch.object(q.shutil, "which", side_effect=AssertionError("No tool lookup allowed")):
                for jobs in (True, False, 0, 5, 2.0, "2"):
                    with self.subTest(jobs=jobs), self.assertRaises(q.QualificationError): q.qualify(path, jobs=jobs)
                    self.assertFalse(path.exists())
                with self.assertRaises(q.QualificationError): q.qualify(Path(temporary))
                with self.assertRaises(q.QualificationError): q.qualify(q.ROOT / "outside-build")

    def test_model_adapter_preserves_array_words_and_direct_observer_gate(self):
        models = q.native.load_module("wave4_qualifier_test_model", q.FIXTURES / "models.py")
        oracle = q.Oracle(models)
        fixture = {"semantic": {"kind": "delta-left-observer-right"}}
        case = {"events": [], "warmup_blocks": 4}
        source = (array.array('f', [0.0, 0.5]), array.array('f', [-0.0, 1.0]))
        actual = (array.array('f', [-0.0, 0.5]), array.array('f', [-0.0, 1.0]))
        good = oracle.analyse(fixture, case, source, actual)
        self.assertTrue(good["passed"]); self.assertEqual(good["direct_observer_bit_errors"], 0)
        altered = (actual[0], array.array('f', [0.0, 1.0]))
        bad = oracle.analyse(fixture, case, source, altered)
        self.assertEqual(bad["maximum_absolute_error"], 0.0)
        self.assertFalse(bad["passed"]); self.assertEqual(bad["direct_observer_bit_errors"], 1)
        for bad_case in ({"events": [{}], "warmup_blocks": 4}, {"events": [], "warmup_blocks": 0}):
            with self.assertRaises(q.QualificationError): oracle.analyse(fixture, bad_case, source, actual)

    def test_all_wire_plans_bind_same_three_inputs_two_cycles_and_empty_events(self):
        catalog = q.load_catalog()
        inputs = q.native.load_module("wave4_qualifier_test_inputs", q.FIXTURES / "inputs.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "inputs").mkdir(); (root / "plans").mkdir()
            plans, vectors = q.make_plans(catalog, root, inputs)
            self.assertEqual(len(plans), 39); self.assertEqual(len(vectors), 3)
            for plan in plans:
                header = struct.unpack('<8I', (root / plan["plan_file"]).read_bytes())
                self.assertEqual(header, (0x57563331, 1, 64, 4, 305419896, 0, 2, 0))
                self.assertEqual(plan["events"], []); self.assertEqual(plan["parameter_schema"], [])
                self.assertEqual(q.sha(root / plan["input_file"]), plan["input_sha256"])
                self.assertEqual((root / plan["input_file"]).stat().st_size, 64 * 256 * 2 * 4)
                self.assertEqual(plan["plan_sha256"], q.sha(root / plan["plan_file"]))
            self.assertEqual(len({p["input_sha256"] for p in plans}), 3)

    def test_empty_and_truncated_oracles_cannot_pass_accuracy(self):
        fixture = {"id": "one", "cases": [{"id": "one-case", "lifecycles": 2}]}
        catalog = {"fixtures": [fixture]}
        for completed, count in ((False, 0), (True, 0), (True, 1)):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); builds = {}
                for mode in ('O3', 'UBSan'):
                    files = {}
                    for suffix, data in (('.f32', bytes(16)), ('.pcm16', bytes(8))):
                        path = root / (mode + suffix); path.write_bytes(data)
                        files[suffix] = {'path': path.name, 'sha256': hashlib.sha256(data).hexdigest()}
                    record = {'returncode': 0, 'stderr': '', 'completed': completed,
                              'statistics': {'cycles': [{'cycle': i, 'completed': completed, 'captured_blocks': 1} for i in range(2)]},
                              'protocol': {'passed': completed}, 'files': files,
                              'independent_accuracy': [{'passed': True}] * count}
                    builds['one--' + mode] = {'cases': {'one-case': record}}
                result = q.summarize(catalog, builds, root)
                self.assertFalse(result['independent_accuracy_passed'])
                self.assertFalse(result['qualification_passed'])
                self.assertFalse(result['comparisons'][0]['accuracy_evaluated'])

    def test_cli_rejects_invalid_jobs_and_existing_output(self):
        with tempfile.TemporaryDirectory(dir=q.ROOT / 'build') as temporary:
            command = [sys.executable, str(q.ROOT / 'host/compiler/qualify_wave4.py'), '--out', temporary]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Output already exists', result.stderr)
            result = subprocess.run(command + ['--jobs', '0'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('jobs must be', result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
