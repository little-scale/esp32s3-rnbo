# SPDX-License-Identifier: MIT
"""Exact local-source admission for the compact authored-window candidate."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from compact_average import compact_average
from prepare import cpp_code_mask


class CompactAverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]
        cls.prepared=Path(os.environ.get("RNBO_S3_TEST_AVERAGE_PREPARED",cls.root/"build/object-qualification/wave2-final/prepared/average-window/float32-strict"))
        provenance=cls.prepared/"provenance.json"
        if not provenance.is_file():raise unittest.SkipTest("Prepare the actual original wave2 average fixture first")
        inventory=json.loads(provenance.read_text())["prepared_files_sha256"]
        cls.files={name:(cls.prepared/name).read_bytes() for name in inventory}
        cls.description=json.loads(cls.files["description.json"])

    def apply(self,files=None,description=None):
        return compact_average(self.files if files is None else files,
                               self.description if description is None else description,cpp_code_mask)

    def test_exact_profile_copies_input_and_changes_only_generated_header(self):
        before=dict(self.files);updated,records=self.apply()
        self.assertIsNot(updated,self.files)
        self.assertEqual(self.files,before)
        self.assertEqual(set(updated),set(before))
        self.assertEqual([k for k in updated if updated[k]!=before[k]],["rnbo_source.h"])
        record=records[0]
        self.assertEqual(record["prepared_sha256"],"c843b9f0a14a53e8c792c6e7a857bb9dda2d7df488c3282db4a0b16f36023ab0")
        self.assertEqual(record["payload_bytes_saved"],705096)
        self.assertEqual(record["requires_opaque_dataref_abi"],{"major":1,"minor":0})
        self.assertFalse(record["observed_native_high_water_bytes"]["hardware_qualified"])

    def test_initial_capacity_and_dsp_regrowth_use_maximum_plus_one(self):
        updated,records=self.apply();source=updated["rnbo_source.h"].decode()
        for index in (1,2):
            prefix=f"average_tilde_{index:02d}"
            self.assertIn(f"{prefix}_buffer->requestSize(65, 1)",source)
            self.assertIn(f"if (65 > this->{prefix}_buffer->getSize())",source)
            self.assertIn(f"{prefix}_buffer->setSize(65)",source)
            self.assertIn(f"new Float32Buffer(this->{prefix}_bufferobj)",source)
            self.assertIn(f"Float32BufferRef {prefix}_buffer;",source)
        self.assertEqual(len(records[0]["resources"]),2)
        self.assertTrue(all(r["after_frames"]==r["maximum_window_samples"]+1 for r in records[0]["resources"]))

    def test_known_native_byte_comparison_and_lifecycle_proofs_are_bound(self):
        _,records=self.apply();record=records[0]
        self.assertEqual((record["evidence_comparisons"],record["evidence_workloads"]),(39,13))
        found=0
        for relative,expected in record["evidence_sha256"].items():
            path=self.root/relative
            if path.is_file():
                found+=1;self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected)
        if not found:self.skipTest("Local sealed private evidence is optional outside the development workspace")

    def test_candidate_header_matches_independently_measured_private_variant(self):
        reference=self.root/"build/research/average-window/prepared/cap-f32/rnbo_source.h"
        if not reference.is_file():self.skipTest("Generate the independent private variant first")
        updated,_=self.apply();self.assertEqual(updated["rnbo_source.h"],reference.read_bytes())

    def test_unknown_partial_and_already_transformed_source_fail_closed(self):
        original=self.files["rnbo_source.h"]
        alternatives=[original.replace(b"requestSize(this->sr + 1, 1)",b"requestSize(65, 1)",1),
                      original.replace(b"new Float64Buffer",b"new Float32Buffer",1),
                      original.replace(b"setSize(44100 + 1)",b"setSize(65)",1),
                      self.apply()[0]["rnbo_source.h"]]
        for source in alternatives:
            files=dict(self.files);files["rnbo_source.h"]=source
            with self.assertRaisesRegex(ValueError,"context"):self.apply(files)

    def test_extra_caller_alias_or_accumulator_change_fails_closed(self):
        for extra in (b"\nvoid bypass(){this->average_tilde_01_windowSize_set(1000);}\n",
                      b"\nauto accessor=&rnbos3patch<ENGINE>::getDataRef;\n"):
            files=dict(self.files);files["rnbo_source.h"]+=extra
            with self.assertRaises(ValueError):self.apply(files)
        files=dict(self.files)
        files["rnbo_source.h"]=files["rnbo_source.h"].replace(b"_accum += x",b"_accum -= x")
        self.assertNotEqual(files["rnbo_source.h"],self.files["rnbo_source.h"])
        with self.assertRaises(ValueError):self.apply(files)

    def test_range_service_and_description_file_changes_rejected(self):
        for mutation in ("maximum","minimum","initialValue"):
            description=copy.deepcopy(self.description);description["parameters"][0][mutation]=1000
            with self.assertRaisesRegex(ValueError,"description"):self.apply(description=description)
        description=copy.deepcopy(self.description);description["numInputChannels"]=0
        with self.assertRaises(ValueError):self.apply(description=description)
        files=dict(self.files);files["description.json"]+=b"\n"
        with self.assertRaisesRegex(ValueError,"description file"):self.apply(files)

    def test_unknown_added_or_missing_runtime_files_are_rejected(self):
        for action in ("change","add","remove"):
            files=dict(self.files)
            if action=="change":files["common/RNBO_DataRef.h"]+=b"\n"
            elif action=="add":files["common/unreviewed.h"]=b"// unknown runtime\n"
            else:del files["common/RNBO_DataRef.h"]
            with self.assertRaisesRegex(ValueError,"runtime tree"):self.apply(files)

    def test_mutable_file_values_and_invalid_code_mask_rejected(self):
        files=dict(self.files);files["rnbo_source.h"]=bytearray(files["rnbo_source.h"])
        with self.assertRaisesRegex(ValueError,"immutable"):self.apply(files)
        with self.assertRaisesRegex(ValueError,"code mask"):
            compact_average(self.files,self.description,lambda text:"")

    def test_audit_preserves_baseline_accuracy_limitation_and_separate_resource_semantics(self):
        _,records=self.apply();record=records[0]
        self.assertIn("no accuracy correction",record["accuracy"])
        self.assertIn("indices",record["resource_semantics"])
        self.assertEqual(record["callgraph"]["average_tilde_01_windowSize_set"],["param_01_value_set"])
        self.assertIn("processDataViewUpdate",record["method_code_sha256"])


if __name__=="__main__":unittest.main()
