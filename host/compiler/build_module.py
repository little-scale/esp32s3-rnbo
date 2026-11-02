#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and audit one native Xtensa RNBO ELF module; never touches a device.

The pinned project_elf flow supplies relocation/call flags. State is supplied by
the loader host through the dynamic handshake. No package/storage/UI is implied.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import sys

from build import verify_prepared
from inspect_module import inspect_module
from prepare import ExportError,canonical,read_json,read_regular

ROOT=Path(__file__).resolve().parents[2]


def normalize_zero_relocations(data: bytes) -> tuple[bytes,dict]:
    """Remove only exact zeroed Xtensa linker relocation tombstones.

    The pinned loader rejects R_XTENSA_NONE, including its unmapped destination
    zero. Compact RELA payloads and reduce their section sizes; every code/data
    byte, section address, file offset and remaining relocation stays unchanged.
    Full module admission runs on the result, never on a broadened loader.
    """
    if not isinstance(data,bytes) or len(data)<52 or data[:7]!=b"\x7fELF\x01\x01\x01":
        raise ExportError("Cannot normalize a non-ELF32 little-endian artifact")
    header=struct.unpack_from("<16sHHIIIIIHHHHHH",data)
    if header[1]!=3 or header[2]!=94 or header[11]!=40 or not 0<header[13]<header[12]:
        raise ExportError("Relocation normalization requires the pinned Xtensa ET_DYN section profile")
    shoff=header[6];count=header[12]
    if shoff>len(data) or count>(len(data)-shoff)//40:raise ExportError("Truncated ELF section table")
    rows=[struct.unpack_from("<10I",data,shoff+i*40) for i in range(count)]
    names_row=rows[header[13]]
    if names_row[1]!=3 or names_row[4]>len(data) or names_row[5]>len(data)-names_row[4]:raise ExportError("Invalid ELF section-name table")
    names=data[names_row[4]:names_row[4]+names_row[5]]
    normalized=bytearray(data);removed=[]
    for index,row in enumerate(rows):
        if row[1]!=4:continue
        if row[0]>=len(names) or names.find(b"\0",row[0])<0:raise ExportError("Invalid ELF section name")
        name=names[row[0]:names.find(b"\0",row[0])].decode()
        if name not in (".rela.dyn",".rela.plt") or row[4]>len(data) or row[5]>len(data)-row[4] or row[5]%12 or row[9] not in (0,12):
            raise ExportError("Unsupported relocation table for zero-record normalization")
        start,end=row[4],row[4]+row[5]
        protected=[(0,52),(shoff,shoff+count*40)]
        if header[10]:
            protected.append((header[5],header[5]+header[9]*header[10]))
        protected.extend((other[4],other[4]+other[5]) for other_index,other in enumerate(rows)
                         if other_index!=index and other[1] not in (0,8) and other[5])
        if row[2]&4 or any(start<right and left<end for left,right in protected):
            raise ExportError("Relocation normalization overlaps protected ELF code/data/metadata")
        kept=[];dropped=0
        for offset in range(row[4],row[4]+row[5],12):
            record=data[offset:offset+12]
            destination,info,addend=struct.unpack("<IIi",record)
            if (info&255)==0:
                if (destination,info,addend)!=(0,0,0):raise ExportError("Nonzero R_XTENSA_NONE record cannot be normalized")
                dropped+=1
            else:kept.append(record)
        if dropped:
            payload=b"".join(kept)
            normalized[row[4]:row[4]+row[5]]=payload+bytes(row[5]-len(payload))
            struct.pack_into("<I",normalized,shoff+index*40+20,len(payload))
            removed.append({"section":name,"records":dropped,"original_bytes":row[5],"normalized_bytes":len(payload)})
    result=bytes(normalized)
    return result,{"name":"xtensa-zero-relocation-tombstones-v1","removed":removed,
                   "removed_records":sum(item["records"] for item in removed),
                   "raw_sha256":hashlib.sha256(data).hexdigest(),"normalized_sha256":hashlib.sha256(result).hexdigest(),
                   "code_data_and_remaining_relocations_unchanged":True}


def inventory(directory: Path):
    result={}
    for path in sorted(directory.rglob("*")):
        if "__pycache__" in path.parts:continue
        if path.is_symlink():raise ExportError(f"Linked source/dependency is not admitted: {path}")
        if path.is_file():result[path.relative_to(directory).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def sources():
    paths=[ROOT/"module-sdk/include/rnbo_s3_module.h",ROOT/"module-sdk/include/rnbo_s3_dynamic.h",
           ROOT/"host/compiler/build_module.py",ROOT/"host/compiler/build.py",
           ROOT/"host/compiler/prepare.py",ROOT/"host/compiler/inspect_module.py",
           ROOT/"loader-spike/dependencies.json"]
    for name in ("bounded_filters.py", "float32_delays.py", "float32_audio.py", "omit_mtof_table.py", "int32_wrap.py", "hoist_cycles.py", "compact_average.py", "pink_output.py", "wrap_finite.py", "wrap_finite.h", "scalar_powers.py", "exact_delay44100.py", "exact_delay44100.h"):
        helper=ROOT/"host/compiler"/name
        if helper.is_file():paths.append(helper)
    for directory in (ROOT/"module-sdk/dynamic",ROOT/"module-sdk/cmake/dynamic"):
        paths.extend(path for path in sorted(directory.rglob("*")) if path.is_file() and "__pycache__" not in path.parts)
    return {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def build_module(export: Path,build_dir: Path,idf: Path,dependencies: Path,*,max_arena_bytes:int=1048576):
    if type(max_arena_bytes) is not int or not 4096<=max_arena_bytes<=4194304:
        raise ExportError("Explicit module max-arena-bytes must be 4096..4194304 (default 1 MiB)")
    export=export.resolve();build_dir=build_dir.resolve();idf=idf.expanduser().resolve();dependencies=dependencies.resolve()
    provenance,manifest,prepared_snapshot=verify_prepared(export)
    lock=read_json(read_regular(ROOT/"loader-spike/dependencies.json",1024*1024),"loader dependencies")
    dependency_report={}
    for name,info in lock["components"].items():
        path=dependencies/name
        if inventory(path)!=info["files_sha256"]:raise ExportError(f"Missing or modified pinned module-build dependency: {name}")
        dependency_report[name]={"version":info["version"],"source_tree_sha256":info["source_tree_sha256"],"source":info["source"]}
    if not (idf/"tools/idf.py").is_file():raise ExportError("Supply an installed ESP-IDF 5.5 checkout with --idf-path")
    environment=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER="0",PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates=sorted(p for p in (Path.home()/".espressif/python_env").glob("idf5.5_py*_env") if (p/"bin/python").is_file())
        if not candidates:raise ExportError("Set IDF_PYTHON_ENV_PATH to the installed ESP-IDF 5.5 Python environment")
        environment["IDF_PYTHON_ENV_PATH"]=str(candidates[-1])
    before=sources()
    build_dir.mkdir(parents=True,exist_ok=True)
    artifact=build_dir/"rnbo_s3_dynamic.app.elf"
    # Force the project_elf custom link step even for an incremental rebuild;
    # otherwise a previous normalized ELF could be mislabeled as raw linker output.
    artifact.unlink(missing_ok=True)
    project=ROOT/"module-sdk/cmake/dynamic"
    command=["bash","-e","-c",'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',
             "rnbo-module",str(idf),"-B",str(build_dir),"-D","IDF_TARGET=esp32s3",
             "-D",f"SDKCONFIG={build_dir/'sdkconfig'}","-D",f"SDKCONFIG_DEFAULTS={project/'sdkconfig.defaults'}",
             "-D",f"RNBO_S3_DEPENDENCIES_DIR={dependencies}","-D",f"RNBO_S3_EXPORT_DIR={export}",
             "-D",f"RNBO_S3_MAX_ARENA_BYTES={max_arena_bytes}",
             "-D","ELF_LOADER_KEEP_DEBUG_ELF=ON","elf"]
    with (build_dir/"build.log").open("w") as log:
        process=subprocess.Popen(command,cwd=project,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        assert process.stdout
        for line in process.stdout:
            print(line,end="",flush=True);log.write(line);log.flush()
        if process.wait():raise ExportError(f"Module compilation failed; see {build_dir/'build.log'}")
    if sources()!=before:raise ExportError("Dynamic SDK/compiler sources changed during compilation; discard this artifact")
    if verify_prepared(export)[2]!=prepared_snapshot:raise ExportError("Prepared export changed during module compilation")
    raw_data=read_regular(artifact,524288)
    raw_artifact=build_dir/"rnbo_s3_dynamic.app.raw.elf"
    raw_artifact.write_bytes(raw_data)
    data,normalization=normalize_zero_relocations(raw_data)
    inspection=inspect_module(data,allowed_imports=set())
    artifact.write_bytes(data)
    description=read_json(read_regular(build_dir/"project_description.json",8*1024*1024),"project description")
    compiler=Path(description["c_compiler"])
    nm=compiler.with_name(compiler.name.removesuffix("gcc")+"nm")
    readelf=compiler.with_name(compiler.name.removesuffix("gcc")+"readelf")
    imports=subprocess.run([str(nm),"-D","--undefined-only",str(artifact)],check=True,capture_output=True,text=True).stdout
    dynamic_symbols=subprocess.run([str(readelf),"-Ws",str(artifact)],check=True,capture_output=True,text=True).stdout
    if imports.strip():raise ExportError(f"Final module has unapproved undefined symbols:\n{imports}")
    (build_dir/"symbols.txt").write_text(dynamic_symbols)
    support_archives={}
    for name,flag in (("libgcc","-print-libgcc-file-name"),("libm","-print-file-name=libm.a")):
        path=Path(subprocess.run([str(compiler),flag],check=True,capture_output=True,text=True).stdout.strip())
        support_archives[name]={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    report={"format":"rnbo-esp32s3-dynamic-module-build","format_version":1,
            "artifact":{"path":str(artifact),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()},
            "raw_artifact":{"path":str(raw_artifact),"bytes":len(raw_data),"sha256":hashlib.sha256(raw_data).hexdigest()},
            "elf_compatibility_normalization":normalization,
            "prepared_export":{"manifest":manifest,"provenance":provenance},"prepared_snapshot":prepared_snapshot,
            "dynamic_abi":{"major":1,"minor":0,"entry":"app_main argc1 request pointer in argv[0]","explicit_result":True},
            "sample_rate":44100,"block_frames":256,"role":manifest["role"],
            "state_policy":{"caller_owned":True,"alignment":16,"minimum_arena_bytes":4096,"maximum_arena_bytes":max_arena_bytes,
                            "context_bytes":"reported by allocation-free DESCRIBE","minimum_arena_is_structural_not_measured":True},
            "allocation_accounting":{"rnbo_platform":"base statistics hook counters","cpp_and_total":"dynamic statistics extension",
                                     "allocator":"module-private monotonic lifetime arena","out_of_memory":"native trap; no firmware allocator fallback"},
            "imports":inspection["imports"],"inspection":inspection,"dependencies":dependency_report,
            "source_files_sha256":before,"compiler":{"path":str(compiler),"version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout},
            "private_support_archives":support_archives,
            "compile_commands_sha256":hashlib.sha256((build_dir/"compile_commands.json").read_bytes()).hexdigest(),
            "symbols_sha256":hashlib.sha256(dynamic_symbols.encode()).hexdigest(),
            "hardware_executed":False,"dynamic_rnbo_qualified":False}
    (build_dir/"build-report.json").write_bytes(canonical(report))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export",type=Path,required=True)
    parser.add_argument("--build-dir",type=Path,required=True)
    parser.add_argument("--idf-path",type=Path,default=Path(os.environ.get("IDF_PATH",str(Path.home()/"esp/esp-idf"))))
    parser.add_argument("--dependencies-dir",type=Path,default=ROOT/"build/vendor-loader-spike")
    parser.add_argument("--max-arena-bytes",type=int,default=1048576,
                        help="Explicit per-module ceiling; defaults to 1 MiB, maximum 4 MiB; no buffer rewriting")
    args=parser.parse_args()
    try:report=build_module(args.export,args.build_dir,args.idf_path,args.dependencies_dir,max_arena_bytes=args.max_arena_bytes)
    except (ExportError,ValueError,OSError,subprocess.CalledProcessError) as exc:parser.exit(1,f"Module build rejected: {exc}\n")
    print(json.dumps({"module":report["artifact"],"imports":report["imports"],"report":str((args.build_dir/"build-report.json").resolve())}))


if __name__=="__main__":main()
