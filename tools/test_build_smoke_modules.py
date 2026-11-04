# SPDX-License-Identifier: MIT
"""Fail-closed smoke-cache/profile and output protection; no devices/RNBO required."""
import copy
import importlib.util
import io
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke_modules", ROOT / "tools/build_smoke_modules.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def manifest():
    return {"format": "rnbo-esp32s3-prepared-export", "format_version": 1,
            "rnbo_version": "1.4.4", "class_name": "rnbos3patch", "role": "fx",
            "sample_rate": 44100, "block_frames": 256, "audio_inputs": 2, "audio_outputs": 2,
            "parameter_count": 0, "voices": 1, "voice_topology": "single-export",
            "numerical_profile": "float32-strict", "scheduler_time": "float64",
            "defined_int32_wrap": True, "required_host_services": [], "midi_output_ports": 0,
            "midi_output_policy": "reject", "adaptations": smoke.ADAPTATIONS.copy(), "execution": "static-development",
            "editable_source_sha256": "a" * 64, "parameter_schema_sha256": "b" * 64, "source_tree_sha256": "c" * 64}


class SmokeModuleTests(unittest.TestCase):
    def test_other_profiles_services_and_boolean_integer_fields_reject(self):
        smoke.validate_manifest(manifest())
        for field, value in (("role", "main"), ("parameter_count", 1), ("block_frames", 128),
                             ("voices", True), ("numerical_profile", "float32-audio-v2"),
                             ("required_host_services", ["dataref"]), ("adaptations", [])):
            changed = manifest()
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(smoke.ExportError):
                smoke.validate_manifest(changed)
        changed = manifest()
        changed["optional_adapter"] = True
        with self.assertRaises(smoke.ExportError):
            smoke.validate_manifest(changed)

    def test_wrapper_changes_only_exact_export_paths_and_output(self):
        command = ["compiler", "-I/old", "-I/old/common", "-DNAME=/old", "-o", "old.o", "-c", "wrapper.cpp"]
        result = smoke.rewrite_wrapper(command, Path("/old"), Path("/new"), Path("/new.o"))
        self.assertEqual(result, ["compiler", "-I/new", "-I/new/common", "-DNAME=/old", "-o", "/new.o", "-c", "wrapper.cpp"])
        self.assertEqual(command[1], "-I/old")
        with self.assertRaises(smoke.ExportError):
            smoke.rewrite_wrapper(command + ["-I/old"], Path("/old"), Path("/new"), Path("/new.o"))

    def test_arena_tier_rewrites_only_one_wrapper_macro_and_never_the_input(self):
        command=['compiler','-O2','-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u','-DOTHER=4096u','-c','wrapper.cpp']
        original=command.copy()
        self.assertEqual(smoke.rewrite_arena_limit(command,4096),command)
        changed=smoke.rewrite_arena_limit(command,1048576)
        self.assertEqual(changed,[*command[:2],'-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=1048576u',*command[3:]])
        self.assertEqual(command,original)
        for bad in (True,0,8192,4194304,'1048576'):
            with self.subTest(value=bad),self.assertRaises(smoke.ExportError):smoke.rewrite_arena_limit(command,bad)
        for bad_command in (command[:2]+command[3:],command+['-DRNBO_S3_DYNAMIC_MAX_ARENA_BYTES=4096u'],
                            [v.replace('=4096u','=1048576u')for v in command]):
            with self.assertRaises(smoke.ExportError):smoke.rewrite_arena_limit(bad_command,1048576)

    def test_cli_exposes_only_the_two_reviewed_tiers(self):
        args=['tool','--prepared-root','/prepared','--base-build','/cache','--out','/new']
        for choice in (None,4096,1048576):
            argv=args+([]if choice is None else['--max-arena-bytes',str(choice)])
            with mock.patch('sys.argv',argv),mock.patch.object(smoke,'build_batch',return_value={'result':'passed','built':1,'failed':0})as build,redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit)as exit:smoke.main()
                self.assertEqual(exit.exception.code,0);self.assertEqual(build.call_args.args[-1],4096 if choice is None else choice)
        with mock.patch('sys.argv',args+['--max-arena-bytes','8192']),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit)as exit:smoke.main()
            self.assertEqual(exit.exception.code,2)

    def test_large_candidate_batch_keeps_original_4k_control_and_support_cache(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);prepared=root/'prepared';prepared.mkdir();(prepared/'candidate').mkdir()
            base=root/'cache';base.mkdir();(base/'build-report.json').write_bytes(b'cached report')
            artifact=base/'original.elf';artifact.write_bytes(b'unchanged control image')
            snapshot={'prepared_files_sha256':{'rnbo_source.h':'a'*64}}
            cache={'report':{'artifact':{'path':str(artifact)}},'source_files_sha256':{},'binding':{},
                'compiler':Path('/compiler'),'compiler_version':'same','archives':{},'old_export':root/'original-export',
                'old_prepared_snapshot':snapshot,'dependency_files':{},'dependencies_dir':root/'dependencies'}
            outputs=[{'id':'cache-control','status':'built','artifact':{'path':str(artifact)}},
                     {'id':'candidate','status':'built','artifact':{'path':'unused'}}]
            with mock.patch.object(smoke,'verify_prepared',return_value=({},manifest(),snapshot)),                 mock.patch.object(smoke,'inspect_cache',return_value=cache),                 mock.patch.object(smoke,'sources',return_value={}),                 mock.patch.object(smoke,'build_one',side_effect=outputs)as build,redirect_stdout(io.StringIO()):
                result=smoke.build_batch(prepared,base,root/'out',1048576)
            self.assertTrue(result['cache_control_whole_ELF_equal'])
            self.assertEqual(result['max_arena_bytes'],1048576);self.assertEqual(result['cache_control_max_arena_bytes'],4096)
            self.assertEqual([call.args[-1]for call in build.call_args_list],[4096,1048576])
            self.assertTrue(all(call.args[3]is cache for call in build.call_args_list))
            self.assertEqual(artifact.read_bytes(),b'unchanged control image')

    def test_unknown_link_or_strip_flag_cannot_enter_replay(self):
        gcc, strip = Path("/tool/gcc"), Path("/tool/strip")
        archives = {"libm": {"path": "/tool/libm.a"}, "libgcc": {"path": "/tool/libgcc.a"}}
        link = [str(gcc), *smoke.LINK_FLAGS, "esp-idf/main/libmain.a", "-Wl,-Bsymbolic", "-Wl,--exclude-libs,ALL",
                "-Wl,--start-group", "/tool/libm.a", "/tool/libgcc.a", "-Wl,--end-group", "-o", "rnbo_s3_dynamic.app.elf"]
        stripping = [str(strip), *smoke.STRIP_FLAGS, "rnbo_s3_dynamic.app.elf"]
        text = "  COMMAND = cd /cache && " + " ".join(link) + " && cmake copy a b && " + " ".join(stripping)
        self.assertEqual(smoke.link_recipe(text, gcc, strip, archives), (link, stripping))
        for changed in (text.replace("/tool/libm.a", "/other/libm.a"), text.replace("-fPIC", "-ffast-math"),
                        text.replace("--strip-unneeded", "--strip-all")):
            with self.assertRaises(smoke.ExportError):
                smoke.link_recipe(changed, gcc, strip, archives)

    def test_reused_file_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cache.a"
            path.write_bytes(b"original")
            records = {str(path): smoke.sha(path)}
            smoke.assert_hashes(records)
            path.write_bytes(b"tampered")
            with self.assertRaises(smoke.ExportError):
                smoke.assert_hashes(records)

    def test_existing_output_and_linked_input_are_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "old"
            out.mkdir()
            sentinel = out / "keep"
            sentinel.write_bytes(b"unchanged")
            with self.assertRaises(smoke.ExportError):
                smoke.build_batch(root / "missing", root / "cache", out)
            self.assertEqual(sentinel.read_bytes(), b"unchanged")
            prepared = root / "prepared"
            prepared.mkdir()
            (prepared / "linked").symlink_to(out, target_is_directory=True)
            fresh = root / "new"
            with self.assertRaises(smoke.ExportError):
                smoke.build_batch(prepared, root / "cache", fresh)
            self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main()
