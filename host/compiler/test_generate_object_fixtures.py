# SPDX-License-Identifier: MIT
"""Original fixture identity, mathematical adversaries and actual export smoke."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from generate_object_fixtures import DEFAULT_RECIPES, ROOT, generate, render, validate_recipes

WAVE = ROOT / "tests/fixtures/objects/wave4"


def module(name):
    spec = importlib.util.spec_from_file_location("wave4_" + name, WAVE / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


models = module("models")
inputs = module("inputs")


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.recipes = json.loads(DEFAULT_RECIPES.read_text())

    def test_exact_spelling_surface_identity_and_reproducible_original_graphs(self):
        before = copy.deepcopy(self.recipes)
        files = render(self.recipes)
        self.assertEqual(self.recipes, before)
        self.assertEqual(len(files), 14)
        self.assertEqual({p.name for p in WAVE.glob("*.rnbopat")}, {p for p in files if p.endswith(".rnbopat")})
        for name, data in files.items():
            self.assertEqual((WAVE / name).read_bytes(), data)
        catalog = json.loads(files["catalog.json"])
        self.assertFalse(catalog["hardware_qualified"])
        self.assertFalse(catalog["performance_measured"])
        patcher = [f for f in catalog["fixtures"] if f["surface"] == "patcher"]
        self.assertEqual(len(patcher), 11)
        names = {f["source"]["spelling"] for f in patcher}
        self.assertEqual(names, {"abs~", "minimum~", "min~", "maximum~", "max~", "sub~", "-~", "eq~", "==~", "lt~", "<~"})
        self.assertTrue(all(f["aliases_inherit_qualification"] is False for f in catalog["fixtures"]))
        self.assertEqual(sum(len(f["cases"]) for f in catalog["fixtures"]), 39)
        # Canonical and alias graphs really contain their separate exact text.
        for f in patcher:
            graph = json.loads(files[f["patch"]])["patcher"]
            operators = [x["box"]["text"] for x in graph["boxes"] if x["box"]["id"].startswith("operator-")]
            self.assertEqual(operators, [f["source"]["spelling"]] * 2)

    def test_invalid_ports_domains_models_and_sources_are_atomic(self):
        changes = [
            lambda r: r.update(audio_inputs=True),
            lambda r: r.update(audio_outputs=3),
            lambda r: r["domain"].update(minimum=-2.0),
            lambda r: r["domain"].update(finite=1),
            lambda r: r["domain"].update(minimum=float("nan")),
            lambda r: r["source"].update(arity=2),
            lambda r: r["source"].update(spelling="onepole~"),
            lambda r: r["source"].update(canonical="minimum~"),
            lambda r: r["source"].update(wiring="in-place"),
            lambda r: r["source"].update(code="out1 = in1;"),
            lambda r: r["model"].update(kind="minimum"),
            lambda r: r["model"].update(maximum_absolute_error=2e-6),
            lambda r: r["cases"][0].update(blocks=True),
            lambda r: r["cases"][0].update(events=[{"block": 0, "id": "fake", "value": 1}]),
            lambda r: r.update(id="../outside"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "missing-parent" / "output"
            for change in changes:
                bad = copy.deepcopy(self.recipes)
                change(bad["recipes"][0])
                before = copy.deepcopy(bad)
                with self.subTest(change=change), self.assertRaises(ValueError):
                    generate(bad, output)
                self.assertEqual(bad, before)
                self.assertFalse(output.parent.exists())
            for key, value in [("sample_rate", 48000), ("block_frames", 256.0), ("format_version", True)]:
                bad = copy.deepcopy(self.recipes); bad[key] = value
                with self.assertRaises(ValueError): generate(bad, output)
                self.assertFalse(output.parent.exists())

    def test_codebox_unknown_members_programs_and_duplicate_selections_reject(self):
        for patch in ({"program": "arbitrary"}, {"wrapper_spelling": "expr~"}, {"exact_entries": ["codebox:delta"]}):
            bad = copy.deepcopy(self.recipes); bad["recipes"][-1]["source"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError): render(bad)
        duplicate = copy.deepcopy(self.recipes)
        other = copy.deepcopy(duplicate["recipes"][0]); other["id"] = "different-id"
        duplicate["recipes"].append(other)
        with self.assertRaises(ValueError): render(duplicate)
        for selection in ([], ["unknown"], ["absolute-signal-stereo"] * 2, [True], "absolute-signal-stereo"):
            with self.subTest(selection=selection), self.assertRaises(ValueError): render(self.recipes, selection)

    def test_cli_fresh_selection_existing_output_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); output = root / "generated"
            command = [sys.executable, str(ROOT / "host/compiler/generate_object_fixtures.py"), "--out", str(output), "--fixture", "codebox-delta-state"]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(set(p.name for p in output.iterdir()), {"catalog.json", "codebox-delta-state.rnbopat"})
            snapshot = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(snapshot, {p.name: p.read_bytes() for p in output.iterdir()})
            bad = root / "bad.json"; bad.write_text('{"format": "wrong"}')
            missing = root / "must-not-exist"
            run = subprocess.run(command[:2] + ["--recipes", str(bad), "--out", str(missing)], capture_output=True)
            self.assertNotEqual(run.returncode, 0); self.assertFalse(missing.exists())


class IndependentModelTests(unittest.TestCase):
    def test_noncommutative_operands_equality_and_complement_foils(self):
        left = (1.0, -0.5, 0.0, 0.5)
        right = (-1.0, 0.25, -0.0, 0.5)
        expected = {
            "absolute": ((1.0, 0.5, 0.0, 0.5), (1.0, 0.25, 0.0, 0.5)),
            "minimum": ((-1.0, -0.5, 0.0, 0.5), (-1.0, -0.5, 0.0, 0.5)),
            "maximum": ((1.0, 0.25, 0.0, 0.5), (1.0, 0.25, 0.0, 0.5)),
            "subtract": ((2.0, -0.75, 0.0, 0.0), (-2.0, 0.75, 0.0, 0.0)),
            "equal": ((0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)),
            "less": ((0.0, 1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)),
            "sum-and-difference": ((0.0, -0.25, 0.0, 1.0), (2.0, -0.75, 0.0, 0.0)),
        }
        for kind, truth in expected.items():
            self.assertEqual(models.expected_outputs(kind, left, right)[0], truth)
            self.assertTrue(models.analyse(kind, (left, right), truth)["accuracy_pass"])
            bad = [list(p) for p in truth]; bad[0][0] += 0.125
            self.assertFalse(models.analyse(kind, (left, right), bad)["accuracy_pass"])
        # A wrong > versus < implementation and swapped subtraction must fail.
        self.assertFalse(models.analyse("less", (left, right), expected["less"][::-1])["accuracy_pass"])
        self.assertFalse(models.analyse("subtract", (left, right), expected["subtract"][::-1])["accuracy_pass"])

    def test_delta_previous_input_vector_crossing_and_reconstruction(self):
        left, right = inputs.generate("vector-boundaries-v1", 1024)
        whole, state = models.expected_outputs("delta-left-observer-right", left, right)
        accumulated = [[], []]; previous = 0.0
        for begin in range(0, 1024, 256):
            block, previous = models.expected_outputs("delta-left-observer-right", left[begin:begin+256], right[begin:begin+256], previous=previous)
            for channel in range(2): accumulated[channel].extend(block[channel])
        self.assertEqual(whole, tuple(tuple(x) for x in accumulated)); self.assertEqual(state, previous)
        self.assertEqual(whole[0][255], 0.75)
        self.assertEqual(whole[0][256], 0.0)  # adjacent equal inputs, across vectors
        self.assertEqual(whole[0][257], -0.75)
        rebuilt, _ = models.expected_outputs("delta-left-observer-right", left, right)
        self.assertEqual(whole, rebuilt)
        wrong = (tuple(left), right)  # missing history/subtraction
        self.assertFalse(models.analyse("delta-left-observer-right", (left, right), wrong)["accuracy_pass"])

    def test_input_programs_are_binary32_bounded_and_chunk_invariant(self):
        for kind in inputs.KINDS:
            whole = inputs.generate(kind, 1024)
            pieces = [inputs.generate(kind, 256, start_frame=start) for start in range(0, 1024, 256)]
            chunked = tuple(tuple(x for p in pieces for x in p[c]) for c in range(2))
            self.assertEqual(tuple(struct.pack('<1024f', *p) for p in whole), tuple(struct.pack('<1024f', *p) for p in chunked))
            self.assertTrue(all(math.isfinite(x) and -1 <= x <= 1 and models.f32(x) == x for p in whole for x in p))
            self.assertNotEqual(whole[0], whole[1])
        grid = inputs.generate("signed-grid-v1", 256)
        self.assertTrue(any(struct.pack('<f', x) == struct.pack('<I', 0x80000000) for p in grid for x in p))
        self.assertTrue(any(abs(x) == 2**-149 for p in grid for x in p))

    def test_delta_direct_observer_rejects_signed_zero_bit_mutation(self):
        # Operation zero signs stay diagnostic, while the untouched wire has
        # an exact bit-copy contract independent of numerical equality.
        kind = "delta-left-observer-right"
        signal = ((0.0,), (-0.0,))
        good = models.analyse(kind, signal, ((-0.0,), (-0.0,)))
        self.assertTrue(good["accuracy_pass"])
        self.assertEqual(good["direct_observer_bit_errors"], 0)
        self.assertEqual(good["zero_sign_differences"], 1)
        bad = models.analyse(kind, signal, ((0.0,), (0.0,)))
        self.assertEqual(bad["maximum_absolute_error"], 0.0)
        self.assertEqual(bad["direct_observer_bit_errors"], 1)
        self.assertTrue(bad["direct_observer_bit_exact_required"])
        self.assertFalse(bad["accuracy_pass"])

    def test_domain_ports_nonfinite_and_rounding_are_not_silently_admitted(self):
        for bad in (True, 1, 0.1, 1.01, float('nan'), float('inf')):
            with self.subTest(input=bad), self.assertRaises(ValueError): models.expected_outputs("absolute", [bad], [0.0])
        for kind, left, right in [("typo", [0.0], [0.0]), ("absolute", [], []), ("absolute", [0.0], [0.0, 1.0])]:
            with self.assertRaises(ValueError): models.expected_outputs(kind, left, right)
        for kind, frames, values in [("typo", 1, {}), ("signed-grid-v1", True, {}), ("dense-binary32-v1", 1, {"seed": True}), ("vector-boundaries-v1", 1, {"start_frame": -1})]:
            with self.assertRaises(ValueError): inputs.generate(kind, frames, **values)
        # Adjacent Float32 inputs, not rounded decimal approximations.
        adjacent = struct.unpack('<f', struct.pack('<I', 0x3f000001))[0]
        truth, _ = models.expected_outputs("subtract", [adjacent], [0.5])
        self.assertEqual(truth[0][0], 2**-24)
        signed = models.analyse("absolute", ((-0.0,), (0.0,)), ((-0.0,), (0.0,)))
        self.assertTrue(signed["accuracy_pass"]); self.assertEqual(signed["zero_sign_differences"], 1)


class LicensedExportTests(unittest.TestCase):
    def test_all_thirteen_actual_export_normal_prepare_and_dynamic_wrapper_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node and an authorised local RNBO1.4.4 installation required")
        from build import verify_prepared
        from prepare import prepare
        compiler = shutil.which("clang++") or shutil.which("c++")
        if not compiler: self.skipTest("A native C++ compiler is required")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = generate(json.loads(DEFAULT_RECIPES.read_text()), root / "authored")
            for name in sorted(files):
                if not name.endswith('.rnbopat'): continue
                id = Path(name).stem; raw = root / (id + "-raw")
                result = subprocess.run(["node", str(ROOT / "archive/importer/integer-ui/export.mjs"), str(root / "authored" / name), "--out", str(raw)], capture_output=True, text=True)
                if result.returncode and "Set --rnbo-dir or RNBO_DIR" in result.stderr:
                    self.skipTest("Authorised local RNBO1.4.4 installation unavailable")
                self.assertEqual(result.returncode, 0, id + ': ' + result.stderr)
                prepared = root / (id + "-prepared")
                prepare(raw, prepared, "rnbos3patch", "fx")
                _, manifest, _ = verify_prepared(prepared)
                self.assertEqual((manifest["audio_inputs"], manifest["audio_outputs"]), (2, 2))
                self.assertEqual(manifest["parameter_count"], 0)
                self.assertEqual(manifest["numerical_profile"], "float32-strict")
                result = subprocess.run([compiler, "-std=c++17", "-fsyntax-only", "-fno-fast-math", "-ffp-contract=off", "-fno-strict-aliasing", "-I" + str(ROOT / "module-sdk/include"), "-I" + str(ROOT / "module-sdk/dynamic"), "-I" + str(prepared), "-I" + str(prepared / "common"), str(ROOT / "module-sdk/dynamic/rnbo_s3_dynamic.cpp")], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, id + ': ' + result.stderr)


if __name__ == "__main__":
    unittest.main()
