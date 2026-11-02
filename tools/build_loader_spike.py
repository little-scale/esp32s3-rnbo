#!/usr/bin/env python3
"""Build an isolated Xtensa loader fixture and ESP32-S3 qualification firmware.

Never flashes hardware. Dependencies are content-locked, staged into build/,
and resolved offline with IDF Component Manager disabled.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def inventory(path: Path) -> dict:
    result = {}
    for file in sorted(path.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"Dependency contains a symbolic link: {file}")
        if file.is_file():
            result[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result

def tree_digest(files: dict) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(files.items()):
        digest.update(name.encode() + b"\0")
        digest.update(bytes.fromhex(value))
    return digest.hexdigest()

def sources() -> dict:
    files = {"tools/build_loader_spike.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for directory in ("loader-spike", "tests/loader"):
        files.update({directory + "/" + name: value for name, value in inventory(ROOT / directory).items()
                      if "__pycache__" not in Path(name).parts})
    return files

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader-dir", type=Path, required=True, help="Pinned elf_loader component directory")
    parser.add_argument("--cmake-utilities-dir", type=Path, required=True, help="Pinned cmake_utilities 0.5.3")
    parser.add_argument("--idf-path", type=Path, default=Path(os.environ.get("IDF_PATH", str(Path.home() / "esp/esp-idf"))))
    parser.add_argument("--board", choices=("amoled", "xiao"), default="amoled")
    parser.add_argument("--host-tests", action="store_true", help="Also run the pinned upstream host regression suite")
    parser.add_argument("--module-only", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "loader-spike/dependencies.json").read_text())
    dependencies = {"elf_loader": args.loader_dir.expanduser().resolve(),
                    "cmake_utilities": args.cmake_utilities_dir.expanduser().resolve()}
    verified = {}
    for name, path in dependencies.items():
        files = inventory(path)
        if files != lock["components"][name]["files_sha256"]:
            raise ValueError(f"Missing or changed locked dependency: {name}")
        verified[name] = {"source_tree_sha256": tree_digest(files), "files": len(files)}
    stage = ROOT / "build/vendor-loader-spike"
    stage.mkdir(parents=True, exist_ok=True)
    for name, path in dependencies.items():
        target = stage / name
        if target.exists() and inventory(target) != lock["components"][name]["files_sha256"]:
            shutil.rmtree(target)
        if not target.exists():
            shutil.copytree(path, target)
    idf = args.idf_path.expanduser().resolve()
    if not (idf / "tools/idf.py").is_file():
        parser.error("ESP-IDF not found; supply --idf-path")
    environment = dict(os.environ, IDF_PATH=str(idf), IDF_COMPONENT_MANAGER="0", PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates = sorted((Path.home() / ".espressif/python_env").glob("idf5.5_py*_env"))
        candidates = [path for path in candidates if (path / "bin/python").is_file()]
        if not candidates:
            parser.error("Set IDF_PYTHON_ENV_PATH to an installed ESP-IDF 5.5 environment")
        environment["IDF_PYTHON_ENV_PATH"] = str(candidates[-1])
    before = sources()
    command_prefix = ["bash", "-e", "-c", 'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"', "loader-spike", str(idf)]

    def build(project: Path, directory: Path, definitions: list[str], target: str):
        directory.mkdir(parents=True, exist_ok=True)
        command = command_prefix + ["-B", str(directory), "-D", "IDF_TARGET=esp32s3", "-D", f"SDKCONFIG={directory / 'sdkconfig'}", "-D", f"SPIKE_DEPENDENCIES_DIR={stage}"]
        for definition in definitions:
            command += ["-D", definition]
        command += [target]
        with (directory / "build.log").open("w") as log:
            process = subprocess.Popen(command, cwd=project, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            assert process.stdout
            for line in process.stdout:
                sys.stdout.write(line); sys.stdout.flush()
                log.write(line); log.flush()
            if process.wait():
                raise ValueError(f"Build failed; see {directory / 'build.log'}")

    module_project = ROOT / "loader-spike/module"
    module_dirs = [ROOT / "build/loader-spike-module", ROOT / "build/loader-spike-module-bad-import"]
    module_paths = []
    for bad, directory in enumerate(module_dirs):
        build(module_project, directory, [f"SDKCONFIG_DEFAULTS={module_project / 'sdkconfig.defaults'}", f"SPIKE_BAD_IMPORT={'ON' if bad else 'OFF'}", "ELF_LOADER_KEEP_DEBUG_ELF=ON"], "elf")
        module_paths.append(directory / "rnbo_loader_fixture.app.elf")
    spec = importlib.util.spec_from_file_location("spike_artifact", ROOT / "tests/loader/check_artifact.py")
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    module_reports = [inspector.inspect(path, bool(bad)) for bad, path in enumerate(module_paths)]
    report = {"loader_version": "2.0.0", "source_commit": lock["components"]["elf_loader"]["commit"], "board": args.board,
              "dependencies": verified, "source_files_sha256": before, "modules": module_reports,
              "host_regressions": "not run", "hardware_executed": False, "dynamic_rnbo_qualified": False}
    module_description = json.loads((module_dirs[0] / "project_description.json").read_text())
    compiler = Path(module_description["c_compiler"])
    report["compiler"] = {"path": str(compiler), "version": subprocess.run([str(compiler), "--version"], check=True, capture_output=True, text=True).stdout}
    report["module_compile_commands_sha256"] = [hashlib.sha256((directory / "compile_commands.json").read_bytes()).hexdigest() for directory in module_dirs]
    if args.host_tests:
        suite = dependencies["elf_loader"] / "tests/host"
        environment["PATH"] = str(compiler.parent) + os.pathsep + environment.get("PATH", "")
        with (module_dirs[0] / "upstream-host-tests.log").open("w") as log:
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(suite), "-p", "test_elf_validate.py", "-v"], env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f"Upstream host tests failed; see {module_dirs[0] / 'upstream-host-tests.log'}")
        report["host_regressions"] = {"passed": True, "log_sha256": hashlib.sha256((module_dirs[0] / "upstream-host-tests.log").read_bytes()).hexdigest()}
        environment["RNBO_S3_LOADER_COMPONENT"] = str(stage / "elf_loader")
        with (module_dirs[0] / "fixture-host-tests.log").open("w") as log:
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests/loader"), "-p", "test_validation.py", "-v"], env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f"Compiled fixture host tests failed; see {module_dirs[0] / 'fixture-host-tests.log'}")
        report["fixture_host_regressions"] = {"passed": True, "log_sha256": hashlib.sha256((module_dirs[0] / "fixture-host-tests.log").read_bytes()).hexdigest()}
    if not args.module_only:
        project = ROOT / "loader-spike/firmware"
        directory = ROOT / f"build/loader-spike-{args.board}"
        build(project, directory, [f"SDKCONFIG_DEFAULTS={project / 'sdkconfig.defaults'};{project / ('sdkconfig.' + args.board + '.defaults')}", f"SPIKE_MODULE_ELF={module_paths[0]}", f"SPIKE_BAD_MODULE_ELF={module_paths[1]}"], "build")
        config = (directory / "sdkconfig").read_text()
        required = ["CONFIG_ELF_LOADER=y", "CONFIG_ELF_LOADER_LOAD_PSRAM=y", "CONFIG_ELF_LOADER_CACHE_OFFSET=y", "CONFIG_SPIRAM_MODE_OCT=y", f"CONFIG_ESPTOOLPY_FLASHSIZE_{'16MB' if args.board == 'amoled' else '8MB'}=y"]
        forbidden = ["CONFIG_ELF_LOADER_LIBC_SYMBOLS=y", "CONFIG_ELF_LOADER_ESPIDF_SYMBOLS=y", "CONFIG_ELF_LOADER_CUSTOMER_SYMBOLS=y", "CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT=y"]
        if any(value not in config for value in required) or any(value in config for value in forbidden):
            raise ValueError("Resolved loader profile failed PSRAM/narrow-import checks")
        description = json.loads((directory / "project_description.json").read_text())
        report.update(idf_version=description["git_revision"], components=description["build_components"], sdkconfig_sha256=hashlib.sha256(config.encode()).hexdigest(),
                      firmware={name: {"bytes": (directory / name).stat().st_size, "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest()}
                                for name in (description["app_elf"], description["app_bin"], "partition_table/partition-table.bin")})
        report_directory = directory
    else:
        report_directory = module_dirs[0]
    if sources() != before:
        raise ValueError("Spike source changed during build; rerun for an accurate artifact identity")
    (report_directory / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Build verified; no hardware execution: {report_directory / 'build-report.json'}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Loader spike failed: {error}", file=sys.stderr)
        raise SystemExit(1)
