#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated, catalog-bound strict/optimized RNBO object comparator.

No device access. Both native modules must already have verified build reports.
The default inputs are the milestone-2 object qualification artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from build_rnbo_loader_test import module_input
from build_loader_spike import inventory, tree_digest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host/compiler"))
from prepare import ExportError, read_json, read_regular


def require(condition, message):
    if not condition: raise ExportError(message)


def sha(path):
    return hashlib.sha256(read_regular(path, 32*1024*1024)).hexdigest()


def c_string(value):
    require(isinstance(value, str) and "\0" not in value, "Invalid C string")
    # Every byte uses a separate literal: no hexadecimal escape continuation.
    return "".join('"\\x%02x"' % x for x in value.encode("utf-8")) or '""'


def finite(value):
    require(isinstance(value, (int,float)) and not isinstance(value, bool) and math.isfinite(value), "Expected finite number")
    return float(value)


def f32(value):
    try: result = struct.unpack("<f", struct.pack("<f", finite(value)))[0]
    except (OverflowError, struct.error) as exc: raise ExportError("Float32 value overflow") from exc
    require(math.isfinite(result), "Nonfinite Float32 value")
    return result


def c_float(value):
    return f32(value).hex() + "f"


def integer(value, minimum, maximum, name):
    require(type(value) is int and minimum <= value <= maximum, "Invalid " + name)
    return value


def configuration(args, modules):
    data = read_regular(args.catalog, 4*1024*1024)
    catalog = read_json(data, "object fixture catalog")
    require(catalog.get("sample_rate")==44100 and catalog.get("block_frames")==256, "Wrong catalog audio profile")
    matches = [f for f in catalog.get("fixtures",[]) if f.get("id")==args.fixture_id]
    require(len(matches)==1, "Fixture ID must occur exactly once")
    fixture = matches[0]
    require(re.fullmatch(r"[A-Za-z0-9_-]+", args.fixture_id), "Unsafe fixture ID")
    manifest = modules["strict"]["report"]["prepared_export"]["manifest"]
    candidate = modules["optimized"]["report"]["prepared_export"]["manifest"]
    role = fixture.get("role")
    require(role in ("main","fx") and manifest["role"]==candidate["role"]==role, "Catalog/module role differs")
    require(role=="main", "This benchmark revision admits Main fixtures only; declared FX stimulus generators are not implemented")
    for key in ("parameter_schema_sha256", "source_tree_sha256", "editable_source_sha256", "parameter_count", "audio_inputs", "audio_outputs"):
        require(manifest[key]==candidate[key], "Strict/optimized source or schema identity differs: " + key)
    require(manifest["numerical_profile"]=="float32-strict", "Reference must use float32-strict")
    patch=Path(fixture["patch"])
    require(not patch.is_absolute() and ".." not in patch.parts, "Unsafe catalog patch path")
    patch=args.catalog.parent/patch
    require(sha(patch)==manifest["editable_source_sha256"], "Module source differs from catalog patch")
    require(not manifest["required_host_services"] and not candidate["required_host_services"], "Host services unsupported")
    description_path = Path(modules["strict"]["export_path"])/"description.json"
    description = read_json(read_regular(description_path, 4*1024*1024), "prepared description")
    parameters = sorted(description["parameters"], key=lambda p:p["index"])
    require(len(parameters)==manifest["parameter_count"]<=128, "Parameter count mismatch")
    by_id = {}
    for i,p in enumerate(parameters):
        require(p["index"]==i and p["paramId"] not in by_id, "Invalid parameter indices/IDs")
        require(len(p["paramId"].encode("utf-8"))<192, "Oversize parameter ID")
        lo,hi,initial = (f32(p[k]) for k in ("minimum","maximum","initialValue"))
        require(lo<=initial<=hi, "Invalid parameter bounds")
        f32(p["exponent"]);integer(p["steps"],0,0xffffffff,"parameter steps")
        by_id[p["paramId"]]=p
    blocks = integer(args.blocks or fixture["blocks"], 33, 1024, "blocks")
    warmup = integer(fixture["warmup_blocks"],0,64,"warmup")
    seed = integer(fixture["seed"],0,0xffffffff,"seed")
    require(args.timing_exclude_blocks<blocks, "Timing exclusion consumes entire pass")
    cases = fixture["cases"]
    require(isinstance(cases,list) and 1<=len(cases)<=16, "Expected 1..16 cases")
    events=[]; case_rows=[]; case_ids=set()
    for case in cases:
        name=case["id"];require(isinstance(name,str) and name not in case_ids,"Invalid/duplicate case ID");case_ids.add(name)
        current=[]
        require(isinstance(case.get("parameters",{}),dict), "Parameters must be a map")
        source=[{"block":0,"id":identity,"form":"actual","value":value} for identity,value in case.get("parameters",{}).items()]
        source += case.get("events",[])
        seen=set()
        for event in source:
            block=integer(event["block"],0,blocks-1,"event block");identity=event["id"]
            require(identity in by_id and (block,identity) not in seen,"Unknown/duplicate parameter event")
            seen.add((block,identity));p=by_id[identity];form=event.get("form","actual")
            require(form in ("actual","normalized"), "Unsupported event form")
            value=f32(event["value"])
            require((f32(p["minimum"])<=value<=f32(p["maximum"])) if form=="actual" else 0<=value<=1,"Event exceeds declared bounds")
            current.append({"block":block,"index":p["index"],"kind":1 if form=="actual" else 2,"value":value,"id":identity})
        require(len(current)<=256, "Too many events per case")
        current.sort(key=lambda e:(e["block"],e["index"]))
        case_rows.append((name,len(events),len(current)));events.extend(current)
    tolerance=fixture["comparison_tolerance"]
    maximum=finite(tolerance["maximum_absolute_error"]);relative=finite(tolerance["relative_rms_level_difference"])
    require(maximum>=0 and relative>=0,"Negative comparison tolerance")
    pcm=integer(tolerance["maximum_pcm_lsb_error"],0,65535,"PCM tolerance")
    lines=["/* Generated by tools/build_object_benchmark.py; do not edit. */", "#pragma once",
           f"#define BENCH_FIXTURE {c_string(args.fixture_id)}",f"#define BENCH_ROLE {1 if role=='main' else 2}u",
           f"#define BENCH_BLOCKS {blocks}u", f"#define BENCH_WARMUP {warmup}u",f"#define BENCH_SEED {seed}u",
           f"#define BENCH_ROUNDS {args.rounds}u",f"#define BENCH_TIMING_EXCLUDE {args.timing_exclude_blocks}u",
           f"#define BENCH_ARENA_BYTES {args.arena_bytes}u",f"#define BENCH_CASE_COUNT {len(cases)}u",f"#define BENCH_PARAMETER_COUNT {len(parameters)}u",
           f"#define BENCH_MAX_ABS {maximum.hex()}",f"#define BENCH_MAX_RELATIVE_RMS {relative.hex()}",f"#define BENCH_MAX_PCM_LSB {pcm}u",
           f"#define BENCH_STRICT_SHA256 {c_string(modules['strict']['artifact_sha256'])}",
           f"#define BENCH_OPTIMIZED_SHA256 {c_string(modules['optimized']['artifact_sha256'])}",
           "static const bench_parameter bench_parameters[]={"]
    for p in parameters:
        lines.append("{%s,%s,%s,%s,%s,%su}," % (c_string(p["paramId"]),c_float(p["minimum"]),c_float(p["maximum"]),c_float(p["initialValue"]),c_float(p["exponent"]),p["steps"]))
    if not parameters: lines.append('{"",0,0,0,0,0},')
    lines += ["};", "static const bench_event bench_events[]={"]
    for e in events: lines.append("{%su,%su,%su,%s},"%(e["block"],e["index"],e["kind"],c_float(e["value"])))
    if not events:lines.append("{0,0,0,0},")
    lines += ["};", "static const bench_case bench_cases[]={"]
    for name,start,count in case_rows:lines.append("{%s,%su,%su},"%(c_string(name),start,count))
    lines += ["};", ""]
    return "\n".join(lines), {"catalog_path":str(args.catalog),"catalog_sha256":hashlib.sha256(data).hexdigest(),
        "fixture":fixture,"patch_sha256":sha(patch),"blocks":blocks,"rounds":args.rounds,"timing_exclude_blocks":args.timing_exclude_blocks,
        "arena_bytes":args.arena_bytes,"events":events,"description_sha256":sha(description_path),
        "comparison_policy":{"pcm_gain":0.5,"pcm_scale":32767,"pcm_rounding":"lrintf; symmetric saturation",
        "case_gate":"all declared tolerances per independently reset case, combined channels and rounds",
        "timing":"process callback only; excludes first N rendered blocks of each pass; events/preparation separate"}}


def sources():
    paths=[Path(__file__).resolve(),ROOT/"tools/build_rnbo_loader_test.py",ROOT/"tools/build_loader_spike.py",ROOT/"loader-spike/dependencies.json",
           ROOT/"host/compiler/build.py",ROOT/"host/compiler/prepare.py",ROOT/"host/compiler/inspect_module.py"]
    for directory in (ROOT/"object-benchmark", ROOT/"module-sdk"):
        paths.extend(p for p in sorted(directory.rglob("*")) if p.is_file() and "__pycache__" not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-id",required=True)
    parser.add_argument("--catalog",type=Path,default=ROOT/"tests/fixtures/objects/catalog.json")
    parser.add_argument("--qualification-dir",type=Path,default=ROOT/"build/object-qualification/milestone-2")
    for key in ("strict","optimized"):
        parser.add_argument(f"--{key}-module",type=Path)
        parser.add_argument(f"--{key}-export",type=Path)
    parser.add_argument("--rounds",type=int,default=3)
    parser.add_argument("--blocks",type=int)
    parser.add_argument("--timing-exclude-blocks",type=int,default=32)
    parser.add_argument("--arena-bytes",type=int,default=1048576)
    parser.add_argument("--board",choices=("amoled","xiao"),default="amoled")
    parser.add_argument("--variant",default="")
    parser.add_argument("--loader-dir",type=Path,default=ROOT/"build/vendor-loader-spike/elf_loader")
    parser.add_argument("--cmake-utilities-dir",type=Path,default=ROOT/"build/vendor-loader-spike/cmake_utilities")
    parser.add_argument("--idf-path",type=Path,default=Path(os.environ.get("IDF_PATH",str(Path.home()/"esp/esp-idf"))))
    parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args()
    require(re.fullmatch(r"[A-Za-z0-9_-]+",args.fixture_id),"Unsafe fixture ID")
    require(not args.variant or re.fullmatch(r"[A-Za-z0-9_-]+",args.variant),"Unsafe variant")
    integer(args.rounds,1,5,"rounds");integer(args.timing_exclude_blocks,0,1023,"timing exclusion");integer(args.arena_bytes,4096,1048576,"arena")
    args.catalog=args.catalog.expanduser().resolve();base=args.qualification_dir.expanduser().resolve()
    catalog=read_json(read_regular(args.catalog,4*1024*1024),"catalog")
    match=[f for f in catalog.get("fixtures",[]) if f.get("id")==args.fixture_id];require(len(match)==1,"Unknown fixture")
    modules={}
    for key,variant in (("strict","strict"),("optimized","float32-audio-v1")):
        artifact=getattr(args,key+"_module") or base/"modules"/args.fixture_id/variant/"rnbo_s3_dynamic.app.elf"
        export=getattr(args,key+"_export") or base/"prepared"/args.fixture_id/variant
        modules[key]=module_input(artifact,export,match[0]["role"])
    header,policy=configuration(args,modules)
    if args.validate_only:
        print(json.dumps({"validated":True,"policy":policy,"generated_header_sha256":hashlib.sha256(header.encode()).hexdigest()},indent=2));return 0
    lock=read_json(read_regular(ROOT/"loader-spike/dependencies.json",1024*1024),"loader dependencies")
    stage=ROOT/"build/vendor-object-benchmark";stage.mkdir(parents=True,exist_ok=True);dependencies={}
    for name,path in (("elf_loader",args.loader_dir),("cmake_utilities",args.cmake_utilities_dir)):
        path=path.expanduser().resolve();actual=inventory(path)
        require(actual==lock["components"][name]["files_sha256"],"Locked dependency differs: "+name)
        dependencies[name]={"source_tree_sha256":tree_digest(actual),"files":len(actual),"version":lock["components"][name]["version"]}
        destination=stage/name
        if destination.exists() and inventory(destination)!=actual:shutil.rmtree(destination)
        if not destination.exists():shutil.copytree(path,destination)
    idf=args.idf_path.expanduser().resolve();require((idf/"tools/idf.py").is_file(),"Supply installed IDF5.5")
    version_source=(idf/"tools/cmake/version.cmake").read_text()
    version=tuple(int(re.search(r"set\(IDF_VERSION_"+part+r" (\d+)\)",version_source).group(1)) for part in ("MAJOR","MINOR","PATCH"))
    require(version==(5,5,0),"Requires IDF5.5.0")
    environment=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER="0",PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates=sorted(p for p in (Path.home()/".espressif/python_env").glob("idf5.5_py*_env") if (p/"bin/python").is_file())
        require(candidates,"Set IDF_PYTHON_ENV_PATH for IDF5.5");environment["IDF_PYTHON_ENV_PATH"]=str(candidates[-1])
    project=ROOT/"object-benchmark"
    directory=ROOT/f"build/object-benchmark-{args.board}-{args.fixture_id}{'-'+args.variant if args.variant else ''}"
    directory.mkdir(parents=True,exist_ok=True);config_dir=directory/"fixture-config";config_dir.mkdir(exist_ok=True)
    header_path=config_dir/"bench_config.h";header_path.write_text(header)
    definitions=["IDF_TARGET=esp32s3",f"SDKCONFIG={directory/'sdkconfig'}",
        f"SDKCONFIG_DEFAULTS={project/'sdkconfig.defaults'};{project/f'sdkconfig.{args.board}.defaults'}",
        f"OBJECT_BENCH_DEPENDENCIES_DIR={stage}",f"OBJECT_BENCH_CONFIG_DIR={config_dir}",
        f"OBJECT_BENCH_STRICT_ELF={modules['strict']['artifact_path']}",f"OBJECT_BENCH_OPTIMIZED_ELF={modules['optimized']['artifact_path']}"]
    command=["bash","-e","-c",'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',"object-benchmark",str(idf),"-B",str(directory)]
    for definition in definitions:command += ["-D",definition]
    command.append("build");before=sources()
    with (directory/"build.log").open("w") as log:
        process=subprocess.Popen(command,cwd=project,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        assert process.stdout
        for line in process.stdout:print(line,end="",flush=True);log.write(line);log.flush()
        require(process.wait()==0,f"Benchmark build failed: {directory/'build.log'}")
    require(sources()==before,"Benchmark/SDK sources changed during compilation; rebuild")
    for key,record in modules.items():
        require(module_input(Path(record["artifact_path"]),Path(record["export_path"]),match[0]["role"])==record,"Module changed during build")
    header_after,policy_after=configuration(args,modules)
    require(header_after==header and policy_after==policy and header_path.read_text()==header,"Catalog/config changed during build")
    for name in dependencies:require(inventory(stage/name)==lock["components"][name]["files_sha256"],"Dependency changed during build")
    config=(directory/"sdkconfig").read_text()
    required=["CONFIG_ELF_LOADER=y","CONFIG_ELF_LOADER_LOAD_PSRAM=y","CONFIG_ELF_LOADER_CACHE_OFFSET=y","CONFIG_HEAP_USE_HOOKS=y","CONFIG_SPIRAM_MODE_OCT=y",f"CONFIG_ESPTOOLPY_FLASHSIZE_{'16MB' if args.board=='amoled' else '8MB'}=y"]
    forbidden=["CONFIG_ELF_LOADER_LIBC_SYMBOLS=y","CONFIG_ELF_LOADER_ESPIDF_SYMBOLS=y","CONFIG_ELF_LOADER_CUSTOMER_SYMBOLS=y","CONFIG_ELF_DYNAMIC_LOAD_SHARED_OBJECT=y"]
    require(all(x in config for x in required) and not any(x in config for x in forbidden),"Resolved loader/config mismatch")
    description=read_json(read_regular(directory/"project_description.json",8*1024*1024),"project description")
    compiler=Path(description["c_compiler"]);nm=compiler.with_name(compiler.name.removesuffix("gcc")+"nm")
    hook_object=directory/"esp-idf/main/CMakeFiles/__idf_main.dir/allocation_probe.c.obj"
    undefined=subprocess.run([str(nm),"-u",str(hook_object)],check=True,capture_output=True,text=True).stdout
    require(not any(x in undefined for x in ("__atomic","malloc","calloc","realloc","printf","semaphore","spinlock")),"Unexpected helper in allocation hooks")
    artifacts={}
    for name in (description["app_elf"],description["app_bin"],"partition_table/partition-table.bin"):
        path=directory/name;artifacts[path.relative_to(ROOT).as_posix()]={"bytes":path.stat().st_size,"sha256":sha(path)}
    report={"format":"rnbo-esp32s3-object-benchmark-build","format_version":1,"board":args.board,"artifacts":artifacts,
        "modules":modules,"benchmark":policy,"generated_header_sha256":sha(header_path),"dependencies":dependencies,
        "source_files_sha256":before,"compiler":{"path":str(compiler),"version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout},
        "idf_version":json.loads((directory/"config.env").read_text())["IDF_VERSION"],"idf_git_revision":description["git_revision"],
        "sdkconfig_sha256":sha(directory/"sdkconfig"),"components":description["build_components"],"compile_commands_sha256":sha(directory/"compile_commands.json"),
        "allocation_hook_undefined_symbols":undefined,"expected_pass_prefix":"RNBO_OBJECT_BENCHMARK PASS ",
        "qualification_scope":"offline core1 process callbacks; no I2S/UI/network; no full application deadline claim",
        "hardware_executed":False,"target_performance_qualified":False}
    (directory/"build-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Build verified; no device access: {directory/'build-report.json'}");return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ExportError,ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
        print(f"RNBO object benchmark rejected: {error}",file=sys.stderr);raise SystemExit(1)
