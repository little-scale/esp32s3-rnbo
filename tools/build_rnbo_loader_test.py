#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated real-RNBO native loader qualification app; never flash.

Build the three modules first with host/compiler/build_module.py. This helper
checks their bytes, zero-import admission and prepared-source identities, then
embeds them beside a statically linked reference of the very same sine export.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from build_loader_spike import inventory,tree_digest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"host/compiler"))
from build import verify_prepared
from inspect_module import inspect_module
from prepare import ExportError,read_json,read_regular

def sources() -> dict:
    paths=[Path(__file__).resolve(),ROOT/"tools/build_loader_spike.py",ROOT/"loader-spike/dependencies.json",
           ROOT/"host/compiler/build.py",ROOT/"host/compiler/prepare.py",ROOT/"host/compiler/inspect_module.py"]
    for directory in (ROOT/"rnbo-loader-test",ROOT/"module-sdk"):
        paths.extend(p for p in sorted(directory.rglob("*")) if p.is_file() and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(read_regular(p,16*1024*1024)).hexdigest() for p in paths}

def module_input(artifact: Path,export: Path,role: str) -> dict:
    artifact=artifact.expanduser().resolve();export=export.expanduser().resolve()
    data=read_regular(artifact,524288)
    report_data=read_regular(artifact.parent/"build-report.json",16*1024*1024)
    report=read_json(report_data,"module build report")
    provenance,manifest,prepared_snapshot=verify_prepared(export)
    digest=hashlib.sha256(data).hexdigest()
    if report.get("format")!="rnbo-esp32s3-dynamic-module-build" or report.get("format_version")!=1:
        raise ExportError("Missing compatible native-module build report")
    if report.get("artifact",{}).get("sha256")!=digest or report["artifact"].get("bytes")!=len(data):
        raise ExportError(f"Module artifact changed after compilation: {artifact}")
    if report.get("prepared_export")!={"manifest":manifest,"provenance":provenance} or report.get("prepared_snapshot")!=prepared_snapshot:
        raise ExportError(f"Module/reference prepared identity mismatch: {artifact}")
    if manifest.get("role")!=role or manifest.get("sample_rate")!=44100 or manifest.get("block_frames")!=256:
        raise ExportError(f"Wrong module role/audio profile: {artifact}")
    inspection=inspect_module(data,allowed_imports=set())
    if report.get("imports")!=[] or inspection["imports"]!=[]:
        raise ExportError("This qualification requires privately resolved helpers and zero imports")
    for name,expected in report.get("source_files_sha256",{}).items():
        if name.startswith("module-sdk/"):
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ExportError("Invalid SDK source path in module report")
            if hashlib.sha256(read_regular(ROOT/name,16*1024*1024)).hexdigest()!=expected:
                raise ExportError(f"Module SDK changed after module compilation: {name}")
    return {"artifact_path":str(artifact),"artifact_sha256":digest,"artifact_bytes":len(data),
            "report_sha256":hashlib.sha256(report_data).hexdigest(),"report":report,
            "export_path":str(export),"prepared_snapshot":prepared_snapshot,"inspection":inspection}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sine-module",type=Path,default=ROOT/"build/modules/sine/rnbo_s3_dynamic.app.elf")
    parser.add_argument("--fx-module",type=Path,default=ROOT/"build/modules/fx/rnbo_s3_dynamic.app.elf")
    parser.add_argument("--midi-module",type=Path,default=ROOT/"build/modules/midi4/rnbo_s3_dynamic.app.elf")
    parser.add_argument("--sine-export",type=Path,default=ROOT/"build/prepared/sine-v2")
    parser.add_argument("--fx-export",type=Path,default=ROOT/"build/prepared/fx-pass-through-v2")
    parser.add_argument("--midi-export",type=Path,default=ROOT/"build/prepared/midi4")
    parser.add_argument("--skip-midi",action="store_true",help="Build an explicitly smaller sine/FX-only test")
    parser.add_argument("--loader-dir",type=Path,default=ROOT/"build/vendor-loader-spike/elf_loader")
    parser.add_argument("--cmake-utilities-dir",type=Path,default=ROOT/"build/vendor-loader-spike/cmake_utilities")
    parser.add_argument("--idf-path",type=Path,default=Path(os.environ.get("IDF_PATH",str(Path.home()/"esp/esp-idf"))))
    parser.add_argument("--board",choices=("amoled","xiao"),default="amoled")
    args=parser.parse_args()
    fixtures={"sine":module_input(args.sine_module,args.sine_export,"main"),
              "fx":module_input(args.fx_module,args.fx_export,"fx")}
    if not args.skip_midi:fixtures["midi"]=module_input(args.midi_module,args.midi_export,"main")
    lock=read_json(read_regular(ROOT/"loader-spike/dependencies.json",1024*1024),"loader dependencies")
    dependencies={"elf_loader":args.loader_dir.expanduser().resolve(),"cmake_utilities":args.cmake_utilities_dir.expanduser().resolve()}
    stage=ROOT/"build/vendor-rnbo-loader-test";stage.mkdir(parents=True,exist_ok=True)
    verified={}
    for name,path in dependencies.items():
        actual=inventory(path)
        if actual!=lock["components"][name]["files_sha256"]:raise ExportError(f"Locked dependency differs: {name}")
        verified[name]={"source_tree_sha256":tree_digest(actual),"files":len(actual),"version":lock["components"][name]["version"]}
        destination=stage/name
        if destination.exists() and inventory(destination)!=actual:shutil.rmtree(destination)
        if not destination.exists():shutil.copytree(path,destination)
    idf=args.idf_path.expanduser().resolve()
    if not (idf/"tools/idf.py").is_file():parser.error("Supply the installed IDF 5.5 checkout")
    version_source=(idf/"tools/cmake/version.cmake").read_text()
    version=tuple(int(re.search(r"set\(IDF_VERSION_"+part+r" (\d+)\)",version_source).group(1)) for part in ("MAJOR","MINOR","PATCH"))
    if version!=(5,5,0):parser.error("This qualification requires ESP-IDF 5.5.0")
    environment=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER="0",PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates=sorted(p for p in (Path.home()/".espressif/python_env").glob("idf5.5_py*_env") if (p/"bin/python").is_file())
        if not candidates:parser.error("Set IDF_PYTHON_ENV_PATH to the installed IDF 5.5 environment")
        environment["IDF_PYTHON_ENV_PATH"]=str(candidates[-1])
    project=ROOT/"rnbo-loader-test";directory=ROOT/f"build/rnbo-loader-test-{args.board}"
    directory.mkdir(parents=True,exist_ok=True)
    definitions=["IDF_TARGET=esp32s3",f"SDKCONFIG={directory/'sdkconfig'}",
        f"SDKCONFIG_DEFAULTS={project/'sdkconfig.defaults'};{project/f'sdkconfig.{args.board}.defaults'}",
        f"RNBO_TEST_DEPENDENCIES_DIR={stage}",f"RNBO_TEST_BOARD={args.board}",
        f"RNBO_TEST_SINE_EXPORT={args.sine_export.expanduser().resolve()}",
        f"RNBO_TEST_SOURCE_SHA256={fixtures['sine']['report']['prepared_export']['manifest']['source_tree_sha256']}",
        f"RNBO_TEST_PROFILE={fixtures['sine']['report']['prepared_export']['manifest']['numerical_profile']}",
        f"RNBO_TEST_HAVE_MIDI={0 if args.skip_midi else 1}"]
    for kind in ("sine","fx","midi"):
        definitions.extend([f"RNBO_TEST_{kind.upper()}_ELF={fixtures[kind]['artifact_path'] if kind in fixtures else ''}",
                            f"RNBO_TEST_{kind.upper()}_SHA256={fixtures[kind]['artifact_sha256'] if kind in fixtures else 'none'}"])
    command=["bash","-e","-c",'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',
             "rnbo-loader-test",str(idf),"-B",str(directory)]
    for definition in definitions:command.extend(["-D",definition])
    command.append("build");before=sources()
    with (directory/"build.log").open("w") as log:
        process=subprocess.Popen(command,cwd=project,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        assert process.stdout
        for line in process.stdout:
            print(line,end="",flush=True);log.write(line);log.flush()
        if process.wait():raise ExportError(f"Qualification build failed: {directory/'build.log'}")
    if sources()!=before:raise ExportError("Qualification/SDK sources changed during compilation; rebuild for an accurate identity")
    for kind,fixture in fixtures.items():
        if module_input(Path(fixture["artifact_path"]),Path(fixture["export_path"]),"fx" if kind=="fx" else "main")!=fixture:
            raise ExportError(f"Module/reference changed during compilation: {kind}")
    config=(directory/"sdkconfig").read_text()
    required=["CONFIG_ELF_LOADER=y","CONFIG_ELF_LOADER_LOAD_PSRAM=y","CONFIG_ELF_LOADER_CACHE_OFFSET=y","CONFIG_HEAP_USE_HOOKS=y",
              "CONFIG_SPIRAM_MODE_OCT=y",f"CONFIG_ESPTOOLPY_FLASHSIZE_{'16MB' if args.board=='amoled' else '8MB'}=y"]
    forbidden=["CONFIG_ELF_LOADER_LIBC_SYMBOLS=y","CONFIG_ELF_LOADER_ESPIDF_SYMBOLS=y","CONFIG_ELF_LOADER_CUSTOMER_SYMBOLS=y","CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT=y"]
    if any(x not in config for x in required) or any(x in config for x in forbidden):raise ExportError("Resolved loader/import/heap profile mismatch")
    description=read_json(read_regular(directory/"project_description.json",8*1024*1024),"project description")
    compiler=Path(description["c_compiler"])
    nm=compiler.with_name(compiler.name.removesuffix("gcc")+"nm")
    hook_object=directory/"esp-idf/main/CMakeFiles/__idf_main.dir/allocation_probe.c.obj"
    undefined=subprocess.run([str(nm),"-u",str(hook_object)],check=True,capture_output=True,text=True).stdout
    if any(word in undefined for word in ("__atomic","malloc","calloc","realloc","printf","semaphore","spinlock")):
        raise ExportError("Heap observation hook contains an unexpected allocating/locking helper")
    artifacts={}
    for name in (description["app_elf"],description["app_bin"],"partition_table/partition-table.bin"):
        path=directory/name;data=path.read_bytes();artifacts[path.relative_to(ROOT).as_posix()]={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
    report={"format":"rnbo-esp32s3-dynamic-qualification-build","format_version":1,"board":args.board,
            "artifacts":artifacts,"modules":fixtures,"dependencies":verified,"source_files_sha256":before,
            "compiler":{"path":str(compiler),"version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout},
            "idf_version":json.loads((directory/"config.env").read_text())["IDF_VERSION"],"idf_git_revision":description["git_revision"],
            "sdkconfig_sha256":hashlib.sha256(config.encode()).hexdigest(),"components":description["build_components"],
            "compile_commands_sha256":hashlib.sha256((directory/"compile_commands.json").read_bytes()).hexdigest(),
            "allocation_hook_undefined_symbols":undefined,"comparison_policy":{"float_absolute_tolerance":0,"pcm_lsb_tolerance":0,"warmup_blocks":4,"seed":0x12345678},
            "qualification_scope":"offline target execution; no I2S/display/network/flash writes; no full audio deadline claim",
            "expected_pass_prefix":"RNBO_DYNAMIC_LOADER_TEST PASS ","hardware_executed":False,"dynamic_rnbo_qualified":False}
    (directory/"build-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Build verified; no hardware access: {directory/'build-report.json'}")
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ExportError,ValueError,OSError,subprocess.CalledProcessError) as error:
        print(f"RNBO loader qualification rejected: {error}",file=sys.stderr);raise SystemExit(1)
