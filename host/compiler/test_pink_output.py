# SPDX-License-Identifier: MIT
"""Bounded precision proof and failure-atomic admission for pink output scaling."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from pink_output import float32_pink_output
from prepare import ExportError, prepare

ROOT=Path(__file__).resolve().parents[2]


class PinkOutputDomainTests(unittest.TestCase):
    def test_complete_masked_sum_domain_has_identical_output_bits(self):
        compiler=shutil.which("c++")
        if not compiler:self.skipTest("C++ compiler required for independent rounding proof")
        # Explicit stores stop the compiler from collapsing the reference's
        # binary64 operations into binary32. This is a bounded arithmetic proof,
        # independent of the source replacement and generated RNBO algorithm.
        source=r'''
#include <cstdint>
#include <cstdio>
#include <cstring>
__attribute__((noinline)) float reference(float x) {
    volatile double wide=x,scaled=wide*2.0,shifted=scaled-1.0;
    return static_cast<float>(shifted);
}
__attribute__((noinline)) float candidate(float x) {
    volatile float scaled=x*2.0f,shifted=scaled-1.0f;
    return shifted;
}
int main() {
    const float divisor=8388607.0f*16.0f;
    unsigned long long checked=0;
    for(uint32_t sum=0;sum<=17u*8388607u;++sum) {
        float ratio=static_cast<float>(sum)/divisor;
        float a=reference(ratio),b=candidate(ratio);
        if(std::memcmp(&a,&b,sizeof(a)))return 1;
        ++checked;
    }
    std::printf("checked=%llu\n",checked);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/"proof.cpp").write_text(source)
            subprocess.run([compiler,"-std=c++17","-O2","-fno-fast-math","-ffp-contract=off",
                            str(path/"proof.cpp"),"-o",str(path/"proof")],check=True,capture_output=True)
            result=subprocess.run([str(path/"proof")],check=True,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.stdout,"checked=142606320\n")

    def test_invalid_file_maps_reject_without_mutation(self):
        for files in (None,[],{"rnbo_source.h":"text"},{"rnbo_source.h":b"unknown"}):
            before=copy.deepcopy(files)
            with self.assertRaises(ValueError):float32_pink_output(files,{})
            self.assertEqual(files,before)


class PinkOutputAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export=ROOT/"build/object-qualification/wave2-final/exports/noise-colour"
        if not (cls.export/"rnbo_source.h").is_file():
            raise unittest.SkipTest("Generate the authorized local noise-colour export first")
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.prepared=Path(cls.temp.name)/"fixed"
        prepare(cls.export,cls.prepared,"rnbos3patch","main")
        provenance=json.loads((cls.prepared/"provenance.json").read_text())
        cls.files={name:(cls.prepared/name).read_bytes() for name in provenance["prepared_files_sha256"]}
        cls.description=json.loads(cls.files["description.json"])

    def test_source_is_identical_to_independently_measured_candidate(self):
        before=dict(self.files);updated,record=float32_pink_output(self.files,self.description)
        self.assertEqual(self.files,before);self.assertIsNot(updated,self.files)
        self.assertEqual([name for name in updated if updated[name]!=before[name]],["rnbo_source.h"])
        self.assertEqual(hashlib.sha256(updated["rnbo_source.h"]).hexdigest(),
                         "7372566a3620815d7c7db0e3cf5f8acfd27bdb62ab903f19c828379784eb9758")
        self.assertEqual(record["literal_suffix_count"],2);self.assertTrue(record["inverse_byte_identity"])
        self.assertEqual(record["normalization_sum_domain"]["maximum"],142606319)
        private=ROOT/"build/research/noise-float32/prepared/candidate/rnbo_source.h"
        if private.is_file():self.assertEqual(updated["rnbo_source.h"],private.read_bytes())

    def test_source_state_alias_and_partial_or_repeat_changes_reject_atomically(self):
        original=self.files["rnbo_source.h"]
        mutations=[original.replace(b"pink_tilde_01_numRows = 16",b"pink_tilde_01_numRows = 8"),
                   original.replace(b"0x007fffff",b"0x00ffffff",1),
                   original+b"\nvoid foreign(){pink_tilde_01_runningSum=1;}\n",
                   original+b"\nauto alias=&rnbos3patch<ENGINE>::pink_tilde_01_rows;\n",
                   original.replace(b"* 2. - 1.;",b"* 2.f - 1.;"),
                   float32_pink_output(self.files,self.description)[0]["rnbo_source.h"]]
        for source in mutations:
            self.assertNotEqual(source,original)
            files=dict(self.files);files["rnbo_source.h"]=source;before=dict(files)
            with self.assertRaises(ValueError):float32_pink_output(files,self.description)
            self.assertEqual(files,before)

    def test_description_and_runtime_changes_reject(self):
        description=copy.deepcopy(self.description);description["numParameters"]=1
        with self.assertRaises(ValueError):float32_pink_output(self.files,description)
        for action in ("description","runtime-change","runtime-add","runtime-remove"):
            files=dict(self.files)
            if action=="description":files["description.json"]+=b"\n"
            elif action=="runtime-change":files["common/RNBO_Types.h"]+=b"\n"
            elif action=="runtime-add":files["common/unknown.h"]=b"extra"
            else:del files["common/RNBO_Types.h"]
            before=dict(files)
            with self.assertRaises(ValueError):float32_pink_output(files,self.description)
            self.assertEqual(files,before)

    def test_pipeline_metadata_and_helper_inventories(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"candidate"
            manifest=prepare(self.export,out,"rnbos3patch","main",float32_pink_output=True)
            provenance=json.loads((out/"provenance.json").read_text())
            self.assertTrue(manifest["float32_pink_output"])
            self.assertEqual(manifest["numerical_profile"],"float32-strict")
            self.assertEqual(provenance["compiler_helpers_sha256"]["pink_output.py"],
                             hashlib.sha256((ROOT/"host/compiler/pink_output.py").read_bytes()).hexdigest())
            self.assertEqual(provenance["adaptations"][-1]["name"],"rnbo-1.4.4-float32-pink-output-authored16-v1")
            self.assertEqual((out/"rnbo_source.h").read_bytes(),float32_pink_output(self.files,self.description)[0]["rnbo_source.h"])

    def test_incompatible_options_reject_before_output(self):
        options=[{"apply_fixes":False},{"numerical_profile":"float32-audio-v2"},
                 {"float32_pink_output":1}]
        with tempfile.TemporaryDirectory() as tmp:
            for index,extra in enumerate(options):
                out=Path(tmp)/str(index)
                with self.assertRaises(ExportError):
                    prepare(self.export,out,"rnbos3patch","main",**({"float32_pink_output":True}|extra))
                self.assertFalse(out.exists())
            out=Path(tmp)/"fx"
            with self.assertRaises(ExportError):prepare(self.export,out,"rnbos3patch","fx",float32_pink_output=True)
            self.assertFalse(out.exists())


if __name__=="__main__":unittest.main()
