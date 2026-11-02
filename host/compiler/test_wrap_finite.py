# SPDX-License-Identifier: MIT
"""Closed-context guards, private-candidate identity and independent finite truth."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bounded_filters import _method
from prepare import ExportError, cpp_code_mask, prepare
from wrap_finite import correct_finite_wrap

ROOT = Path(__file__).resolve().parents[2]
SHA = lambda value: hashlib.sha256(value).hexdigest()


class FileMapTests(unittest.TestCase):
    def test_invalid_inputs_fail_without_mutation(self):
        for files in (None, [], {}, {"rnbo_source.h": "text"}, {1: b"text"}, {"rnbo_source.h": b"unknown"}):
            before = copy.deepcopy(files)
            with self.assertRaises(ValueError):
                correct_finite_wrap(files, {}, code_mask=cpp_code_mask)
            self.assertEqual(files, before)


class FiniteWrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exports = {
            "nonlinear-domains": Path(os.environ.get("RNBO_S3_TEST_WRAP_EXPORT", ROOT / "build/object-qualification/wave2-final/exports/nonlinear-domains")),
            "wrap-finite-stereo": Path(os.environ.get("RNBO_S3_TEST_WRAP_STEREO_EXPORT", ROOT / "build/object-optimisation/wrap-target-v1/raw/wrap-finite-stereo")),
        }
        if not (cls.exports["nonlinear-domains"] / "rnbo_source.h").is_file():
            raise unittest.SkipTest("Generate the authorized local nonlinear-domains export first")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.files = {}
        for name, export in cls.exports.items():
            if not (export / "rnbo_source.h").is_file():
                continue
            prepared = Path(cls.temp.name) / name
            prepare(export, prepared, "rnbos3patch", "fx")
            provenance = json.loads((prepared / "provenance.json").read_text())
            cls.files[name] = {key: (prepared / key).read_bytes() for key in provenance["prepared_files_sha256"]}

    def adapted(self, name="nonlinear-domains"):
        if name not in self.files:
            self.skipTest("Generate the authorized local stereo wrap export first")
        files = self.files[name]
        return correct_finite_wrap(files, json.loads(files["description.json"]), code_mask=cpp_code_mask)

    def assert_rejected(self, files, description=None, code_mask=cpp_code_mask):
        before = copy.deepcopy(files)
        if description is None:
            description = json.loads(self.files["nonlinear-domains"]["description.json"])
        before_description = copy.deepcopy(description)
        with self.assertRaises(ValueError):
            correct_finite_wrap(files, description, code_mask=code_mask)
        self.assertEqual(files, before)
        self.assertEqual(description, before_description)

    def test_exact_source_and_helper_equal_private_proven_candidate(self):
        before = dict(self.files["nonlinear-domains"])
        updated, record = self.adapted()
        self.assertEqual(self.files["nonlinear-domains"], before)
        self.assertIsNot(updated, self.files["nonlinear-domains"])
        self.assertEqual(SHA(updated["rnbo_source.h"]), "cb3034efc572a29b2d3e9cc82e733035a12b6907b6213c9c3af9ee01ab64cbfd")
        self.assertEqual(SHA(updated["private_finite_wrap.h"]), "5120c1152ed007ac389bef310ac6e83fd6b32c3be9862d9c6615a365f30492fd")
        private = ROOT / "build/research/wrap-finite-v1/prepared/even24"
        if private.is_dir():
            for name in ("rnbo_source.h", "private_finite_wrap.h"):
                self.assertEqual(updated[name], (private / name).read_bytes())
        self.assertEqual([key for key in before if updated[key] != before[key]], ["rnbo_source.h"])
        self.assertEqual(set(updated) - set(before), {"private_finite_wrap.h", "rnbo_s3_finite_wrap_source.h"})
        self.assertEqual(record["guard_count"], 1)
        self.assertTrue(record["inverse_byte_identity"])
        self.assertFalse(record["target_qualified"] or record["cpu_gain_claimed"])

    def test_second_closed_context_has_exact_two_reviewed_kernels(self):
        updated, record = self.adapted("wrap-finite-stereo")
        self.assertEqual(SHA(updated["rnbo_source.h"]), "50e01c6d9b2a854ff872b6ccbaf1c9e5077975ae36cc959d0bd1d20c69516110")
        self.assertEqual(record["guard_count"], 2)
        self.assertEqual([m["method"] for m in record["methods"]], ["wrap_tilde_01_perform", "wrap_tilde_02_perform"])
        self.assertEqual(len({m["kernel_sha256"] for m in record["methods"]}), 1)

    def test_unknown_ranges_loops_widths_comments_strings_and_partial_inputs_reject(self):
        source = self.files["nonlinear-domains"]["rnbo_source.h"]
        replacements = [(b"lo = -1;", b"lo = -2;"), (b"hi = 1;", b"hi = 2;"),
                        (b"i < 256", b"i < 128"), (b"number range = hi - lo;", b"double range = hi - lo;"),
                        (b"Int numWraps", b"int16_t numWraps"), (b"range <= 0.000000001", b"range <= 0.001"),
                        (b"#define trunc(x) ((Int)(x))", b"#define trunc(x) ((int64_t)(x))")]
        for old, new in replacements:
            self.assertIn(old, source)
            files = dict(self.files["nonlinear-domains"]); files["rnbo_source.h"] = source.replace(old, new, 1)
            self.assert_rejected(files)
        for suffix in (b"\n// wrap_tilde_02_perform fake range[-1,1)\n", b'\nconst char* near_match="wrap_tilde_01_perform";\n', b"\n/* unclosed"):
            files = dict(self.files["nonlinear-domains"]); files["rnbo_source.h"] += suffix
            self.assert_rejected(files)
        for name in ("private_finite_wrap.h", "rnbo_s3_finite_wrap_source.h"):
            files = dict(self.files["nonlinear-domains"]); files[name] = b"collision"
            self.assert_rejected(files)
        self.assert_rejected(self.adapted()[0])

    def test_description_and_whole_runtime_version_type_inventory_reject(self):
        description = json.loads(self.files["nonlinear-domains"]["description.json"])
        description["parameters"][0]["maximum"] = 8
        self.assert_rejected(dict(self.files["nonlinear-domains"]), description)
        for action in ("description", "version", "types", "math", "runtime-add", "runtime-remove"):
            files = dict(self.files["nonlinear-domains"])
            if action == "description": files["description.json"] += b"\n"
            elif action == "version": files["common/RNBO_Version.h"] += b"//1.4.5\n"
            elif action == "types": files["common/RNBO_Types.h"] = files["common/RNBO_Types.h"].replace(b"using number = float;", b"using number = double;")
            elif action == "math": files["common/RNBO_Math.h"] += b"\n"
            elif action == "runtime-add": files["common/new.h"] = b"extra"
            else: del files["common/RNBO_AudioSignal.h"]
            self.assert_rejected(files)

    def test_bad_lexical_masks_reject_without_partial_mutation(self):
        for mask in (lambda text: text + " ", lambda text: " " * len(text),
                     lambda text: cpp_code_mask(text).replace("hi = 1", "hi = 2")):
            self.assert_rejected(dict(self.files["nonlinear-domains"]), code_mask=mask)

    def test_pipeline_records_contract_provenance_and_default_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "candidate"
            manifest = prepare(self.exports["nonlinear-domains"], out, "rnbos3patch", "fx", correct_finite_wrap=True)
            provenance = json.loads((out / "provenance.json").read_text())
            self.assertTrue(manifest["correct_finite_wrap"])
            self.assertEqual(manifest["numerical_profile"], "float32-strict")
            self.assertEqual(manifest["finite_wrap_contract"]["guard_count"], 1)
            self.assertIn(b'RNBO_S3_PATCH_SOURCE "rnbo_s3_finite_wrap_source.h"', (out / "patch_config.h").read_bytes())
            self.assertEqual((out / "rnbo_source.h").read_bytes(), self.adapted()[0]["rnbo_source.h"])
            self.assertEqual((out / "originals/rnbo_source.h").read_bytes(), (self.exports["nonlinear-domains"] / "rnbo_source.h").read_bytes())
            for name in ("wrap_finite.py", "wrap_finite.h"):
                self.assertEqual(provenance["compiler_helpers_sha256"][name], SHA((ROOT / "host/compiler" / name).read_bytes()))
            self.assertEqual(provenance["adaptations"][-1]["name"], "rnbo-1.4.4-finite-wrap-even24-v1")
        self.assertNotIn(b"private_wrap_even_large", self.files["nonlinear-domains"]["rnbo_source.h"])

    def test_unreviewed_option_compositions_reject_before_output(self):
        options = [{"apply_fixes": False}, {"numerical_profile": "float32-audio-v2"},
                   {"midi_output_policy": "discard"}, {"filter_delay_max_ms": 40},
                   {"float32_delay_storage": True}, {"omit_unused_mtof_table": True},
                   {"hoist_cycle_conversions": True}, {"compact_average_history": True},
                   {"float32_pink_output": True}, {"correct_finite_wrap": 1}]
        with tempfile.TemporaryDirectory() as tmp:
            for index, extra in enumerate(options):
                out = Path(tmp) / str(index)
                with self.assertRaises(ExportError):
                    prepare(self.exports["nonlinear-domains"], out, "rnbos3patch", "fx", **({"correct_finite_wrap": True} | extra))
                self.assertFalse(out.exists())
            out = Path(tmp) / "main"
            with self.assertRaises(ExportError):
                prepare(self.exports["nonlinear-domains"], out, "rnbos3patch", "main", correct_finite_wrap=True)
            self.assertFalse(out.exists())

    def test_compile_contract_accepts_float32_and_rejects_float64(self):
        compiler = shutil.which("c++")
        if not compiler: self.skipTest("C++ compiler required")
        updated, _ = self.adapted()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name, value in updated.items():
                target = directory / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
            source = directory / "probe.cpp"; source.write_text('#include "rnbo_s3_finite_wrap_source.h"\n')
            command = [compiler, "-std=c++17", "-fsyntax-only", "-I" + str(directory / "common"), str(source)]
            good = subprocess.run(command + ["-DRNBO_USE_FLOAT32"], capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            bad = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("Finite wrap correction requires binary32", bad.stderr)

    def test_actual_generated_target_width_kernel_against_raw_bit_oracle_ubsan(self):
        compiler = shutil.which("c++")
        if not compiler: self.skipTest("C++ compiler required")
        updated, _ = self.adapted()
        source = updated["rnbo_source.h"].decode(); start, stop = _method(cpp_code_mask(source), "wrap_tilde_01_perform")
        notice = source[:source.index("*/") + 2]
        kernel = notice + '\n#include "private_finite_wrap.h"\n#include <cassert>\n#include <cstdio>\n'
        kernel += '#define RNBO_UNUSED(x) (void)(x)\n#define RNBO_RESTRICT __restrict__\n#define trunc(x) ((Int)(x))\n'
        kernel += 'using Int=int32_t;using Index=uint32_t;using number=float;using Sample=float;using SampleValue=float;\nstruct Kernel {\n' + source[start:stop] + '\n};\n'
        # Raw-bit modulo2 truth is independent of generated arithmetic and the
        # new threshold branch. No FP32/FP64 arithmetic or cast is used here.
        kernel += r'''
static uint32_t oracle(uint32_t bits) {
    uint32_t magnitude=bits&0x7fffffffu,sign=bits>>31;
    assert(magnitude<0x7f800000u);
    if(magnitude<0x3f800000u)return bits;
    unsigned exponent=magnitude>>23;
    if(exponent>=151)return 0;
    uint32_t mantissa=(magnitude&0x7fffffu)|0x800000u;
    unsigned fractional=150u-exponent;
    uint32_t denominator=1u<<fractional,period=denominator*2u;
    uint32_t remainder=mantissa&(period-1u);
    int32_t numerator=sign ? (remainder>denominator ? (int32_t)(period-remainder) : -(int32_t)remainder)
                           : (remainder>=denominator ? (int32_t)remainder-(int32_t)period : (int32_t)remainder);
    if(!numerator)return 0;
    uint32_t negative=numerator<0,absolute=(uint32_t)(negative?-numerator:numerator);
    unsigned leading=31u-(unsigned)__builtin_clz(absolute);
    return (negative<<31)|((127u+leading-fractional)<<23)|((absolute<<(23u-leading))&0x7fffffu);
}
int main() {
    Kernel kernel;float input[256],output[256];uint32_t state=0x12345678u;unsigned long long count=0;
    for(unsigned exponent=0;exponent<255;++exponent)for(unsigned batch=0;batch<8;++batch) {
        for(unsigned i=0;i<256;++i) {
            state=state*1664525u+1013904223u;
            uint32_t bits=(i&1u?0x80000000u:0u)|(exponent<<23)|(state&0x7fffffu);
            input[i]=private_wrap_float(bits);
        }
        kernel.wrap_tilde_01_perform(input,0,0,output,256);
        for(unsigned i=0;i<256;++i){assert(private_wrap_bits(output[i])==oracle(private_wrap_bits(input[i])));++count;}
    }
    const uint32_t edges[]={0,1,0x7fffff,0x800000,0x3f7fffff,0x3f800000,0x3f800001,0x40000000,
        0x4b7fffff,0x4b800000,0x4b800001,0x4c000001,0x4f000000,0x4f800000,0x7f7fffff};
    for(uint32_t edge:edges)for(uint32_t sign:{0u,0x80000000u}) {
        for(float &value:input)value=private_wrap_float(edge|sign);
        kernel.wrap_tilde_01_perform(input,0,0,output,256);
        assert(private_wrap_bits(output[0])==oracle(edge|sign));++count;
    }
    float sentinel=123.f;
    for(uint32_t bits:{0x7f800000u,0xff800000u,0x7fc12345u,0xffc12345u})
        assert(!private_wrap_even_large(private_wrap_float(bits),&sentinel)&&sentinel==123.f);
    std::printf("finite_checks=%llu nonfinite_guard_only=4\n",count);
}
'''
        # The original notice stays attached to the local extracted method.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); (directory / "private_finite_wrap.h").write_bytes(updated["private_finite_wrap.h"])
            path = directory / "proof.cpp"; path.write_text(kernel)
            build = subprocess.run([compiler, "-std=c++17", "-O3", "-fno-fast-math", "-ffp-contract=off", "-UNDEBUG",
                                    "-include", "initializer_list", "-fsanitize=undefined,float-cast-overflow",
                                    "-fno-sanitize-recover=all", str(path), "-o", str(directory / "proof")], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            ran = subprocess.run([str(directory / "proof")], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, "finite_checks=522270 nonfinite_guard_only=4\n")


if __name__ == "__main__": unittest.main()
