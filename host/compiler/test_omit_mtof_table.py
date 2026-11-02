# SPDX-License-Identifier: MIT
"""Use actual local RNBO output to reject unsafe table omission forms."""
import os
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess

from omit_mtof_table import omit_mtof_table
from prepare import cpp_code_mask,prepare
from float32_audio import float32_audio


class OmitMtofTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.export=Path(os.environ.get("RNBO_S3_TEST_MTOF_EXPORT",root/"build/object-qualification/fx-1/exports/mtof-fx"))
        if not (cls.export/"rnbo_source.h").is_file():raise unittest.SkipTest("Export the original local mtof-fx fixture first")
        cls.source=(cls.export/"rnbo_source.h").read_bytes()
        cls.runtime=(cls.export/"common/RNBO_DataRef.h").read_bytes()
        cls.engine=(cls.export/"common/RNBO_MinimalEngine.h").read_bytes()

    def transform(self,source):return omit_mtof_table(source,self.runtime,self.engine,code_mask=cpp_code_mask)

    def test_only_initial_capacity_changes_and_metadata_stays(self):
        source,report=self.transform(self.source)
        self.assertEqual(report["request_count"],1)
        self.assertEqual(report["payload_bytes_saved"],262144)
        self.assertEqual(source.replace(b"->requestSize(0, 1);",b"->requestSize(65536, 1);"),self.source)
        self.assertIn("notification",report["changed"])

    def test_direct_exp_float32_profile_is_also_reviewed(self):
        audio,_=float32_audio(self.source,code_mask=cpp_code_mask,profile="float32-audio-v1")
        _,report=self.transform(audio)
        self.assertEqual(report["request_count"],1)

    def test_sample_read_direct_alias_and_indexed_alias_rejected(self):
        for code in (b"number y=this->mtof_tilde_01_innerMtoF_buffer->getSample(0,0);",
                     b"auto alias=this->mtof_tilde_01_innerMtoF_buffer;",
                     b"auto alias=&this->RNBODefaultMtofLookupTable256;",
                     b"auto alias=this->getDataRef(0);"):
            with self.subTest(code=code):
                with self.assertRaisesRegex(ValueError,"alias|reference"):
                    self.transform(self.source+b"\nvoid unsafe(){"+code+b"}\n")

    def test_lazy_resize_and_nonstandard_internal_metadata_rejected(self):
        for source in (self.source.replace(b"->requestSize(65536, 1);",b"->requestSize(65536, 1); this->mtof_tilde_01_innerMtoF_buffer->requestSize(4, 1);"),
                       self.source.replace(b"->setIndex(0)",b"->setIndex(1)"),
                       self.source.replace(b'tag0 = "buffer~"',b'tag0 = "external"'),
                       self.source.replace(b"true,",b"false,",1)):
            with self.assertRaises(ValueError):self.transform(source)

    def test_changed_exp_algorithm_and_filler_rejected(self):
        for source in (self.source.replace(b"rnbo_exp(",b"rnbo_sin("),
                       self.source.replace(b"bufsize - 1",b"bufsize - 2")):
            with self.assertRaises(ValueError):self.transform(source)

    def test_unknown_runtime_and_already_transformed_rejected(self):
        with self.assertRaisesRegex(ValueError,"runtime"):
            omit_mtof_table(self.source,self.runtime+b"\n",self.engine,code_mask=cpp_code_mask)
        with self.assertRaises(ValueError):self.transform(self.transform(self.source)[0])

    def test_member_pointer_alias_callback_side_effect_and_clock_changes_rejected(self):
        for source in (self.source+b"\nauto accessor=&rnbos3patch<ENGINE>::getDataRef;\n",
                       self.source.replace(b"this->updateTime(time, (ENGINE*)nullptr);",b"this->updateTime(time, (ENGINE*)nullptr); ++this->isMuted;",1),
                       self.source.replace(b"this->_currentTime = time;",b"this->_currentTime = time + 1;")):
            with self.assertRaises(ValueError):self.transform(source)
        with self.assertRaisesRegex(ValueError,"MinimalEngine"):
            omit_mtof_table(self.source,self.runtime,self.engine+b"\n",code_mask=cpp_code_mask)

    def test_metadata_comment_or_quoted_declaration_cannot_supply_trust(self):
        for field,valid,changed in (("tag",b'"buffer~"',b'"external"'),("file",b'""',b'"external.wav"'),
                                    ("name",b'"RNBODefaultMtofLookupTable256"',b'"other"')):
            actual=field.encode()+b"0 = "+valid
            wrong=self.source.replace(actual,field.encode()+b"0 = "+changed)
            self.assertNotEqual(wrong,self.source)
            fake=b"static constexpr auto& "+actual+b";"
            for prefix in (b"// "+fake+b"\n",b'const char *fake=R"tag('+fake+b')tag";\n'):
                with self.assertRaisesRegex(ValueError,"metadata"):self.transform(prefix+wrong)

    def test_comments_and_quoted_alias_text_are_not_code(self):
        prefix=b'// getDataRef(0) mtof_tilde_01_innerMtoF_buffer\nconst char *s="RNBODefaultMtofLookupTable256";\n'
        source,_=self.transform(prefix+self.source)
        self.assertTrue(source.startswith(prefix))

    def test_prepare_default_and_explicit_opaque_abi_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            default=Path(directory)/"default";omitted=Path(directory)/"omitted"
            a=prepare(self.export,default,"rnbos3patch","fx")
            b=prepare(self.export,omitted,"rnbos3patch","fx",omit_unused_mtof_table=True)
            self.assertNotIn("omit_unused_mtof_table",a)
            self.assertTrue(b["omit_unused_mtof_table"] and b["requires_opaque_dataref_abi"])
            self.assertEqual(a["source_tree_sha256"],b["source_tree_sha256"])
            self.assertEqual((default/"rnbo_source.h").read_bytes(),self.source)
            self.assertEqual((omitted/"originals/rnbo_source.h").read_bytes(),self.source)

    def test_generated_config_rejects_missing_or_future_sdk_abi(self):
        compiler=shutil.which(os.environ.get("CXX","c++"))
        if not compiler:self.skipTest("A C++ compiler is required for the ABI admission check")
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"prepared"
            prepare(self.export,output,"rnbos3patch","fx",omit_unused_mtof_table=True)
            config=(output/"patch_config.h").read_text()
            for major,minor,expected in ((1,0,0),(1,1,1),(2,0,1),(None,None,1)):
                prefix="" if major is None else f"#define RNBO_S3_ABI_MAJOR {major}u\n#define RNBO_S3_ABI_MINOR {minor}u\n"
                result=subprocess.run([compiler,"-x","c++","-fsyntax-only","-"],input=prefix+config,capture_output=True,text=True)
                self.assertEqual(result.returncode==0,expected==0,result.stderr)


if __name__=="__main__":unittest.main()
