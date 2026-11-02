"""Exercise actual dynamic same-block fault closure with generated sine DSP."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DynamicWrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepared = ROOT / "build/prepared/sine-v2"
        if not (prepared / "rnbo_source.h").is_file():
            raise unittest.SkipTest("Prepare the real local sine-v2 fixture first")
        cls.temporary = tempfile.TemporaryDirectory(prefix="rnbo-dynamic-wrapper-")
        directory = Path(cls.temporary.name)
        source = (prepared / "rnbo_source.h").read_text()
        marker = "    RNBO_ASSERT(n == 256);"
        if source.count(marker) != 1:
            raise RuntimeError("Changed generated sine process fixture")
        injection = """
    if (::rnbo_dynamic::allocation && ::rnbo_dynamic::allocation->running) {
        if (::rnbo_test_allocation_mode==1) {
            void *volatile pointer=::operator new(16);
            ::operator delete(pointer);
        } else if (::rnbo_test_allocation_mode==2) {
            void *volatile pointer=::RNBO::Platform::malloc(16);
            ::RNBO::Platform::free(pointer);
        }
    }
"""
        (directory / "injected.h").write_text('extern "C" int rnbo_test_allocation_mode;\n' + source.replace(marker, marker + injection))
        compiler = os.environ.get("CXX", "c++")
        flags = [compiler, "-std=c++17", "-O2", "-fno-builtin", "-fno-exceptions", "-fno-rtti",
                 "-fno-fast-math", "-ffp-contract=off", "-fno-strict-aliasing", "-UNDEBUG",
                 "-I", str(directory), "-I", str(ROOT / "module-sdk/include"),
                 "-I", str(ROOT / "module-sdk/dynamic"), "-I", str(prepared), "-I", str(prepared / "common")]
        wrapper = directory / "wrapper.o"
        subprocess.run([*flags, '-DRNBO_S3_PATCH_SOURCE="injected.h"', "-Dmain=rnbo_test_module_entry",
                        "-c", str(ROOT / "module-sdk/dynamic/rnbo_s3_dynamic.cpp"), "-o", str(wrapper)], check=True)
        cls.executable = directory / "wrapper-test"
        subprocess.run([*flags, str(ROOT / "tests/dynamic/wrapper_test.cpp"), str(wrapper),
                        str(ROOT / "module-sdk/dynamic/arena.cpp"), "-o", str(cls.executable)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_cpp_and_platform_allocations_both_silence_the_triggering_block(self):
        for kind in ("none", "cpp", "platform"):
            with self.subTest(kind=kind):
                subprocess.run([str(self.executable), kind], check=True, timeout=5)


if __name__ == "__main__": unittest.main()
