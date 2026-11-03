# SPDX-License-Identifier: MIT
"""Fail-closed smoke-cache/profile and output protection; no devices/RNBO required."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

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
