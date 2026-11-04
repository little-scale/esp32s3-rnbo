#!/usr/bin/env python3
"""Build one board profile without modifying another checkout or any device.

AMOLED can build offline from an exact, locally cached dependency collection:
  python3 tools/build_firmware.py amoled --components-from PATH/managed_components
The sources are content-verified and copied into this project's ignored build/.
XIAO requires only the selected ESP-IDF 5.5 installation and toolchain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def verify_prepared(path: Path) -> dict:
    # Use the same strict file reader and canonical manifest as the importer.
    sys.path.insert(0,str(ROOT/"host/compiler"))
    from prepare import canonical, read_json, read_regular
    provenance = read_json(read_regular(path/"provenance.json",8*1024*1024),"provenance.json")
    manifest = read_json(read_regular(path/"manifest.json",1024*1024),"manifest.json")
    hashes = provenance.get("prepared_files_sha256")
    if not isinstance(hashes,dict) or not hashes:
        raise ValueError("Prepared export has no file integrity inventory")
    for name, expected in hashes.items():
        if not isinstance(name,str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Invalid prepared path in provenance")
        if hashlib.sha256(read_regular(path/name,16*1024*1024)).hexdigest()!=expected:
            raise ValueError(f"Prepared export changed after review: {name}")
    if hashlib.sha256(canonical(manifest)).hexdigest()!=provenance.get("manifest_sha256"):
        raise ValueError("Prepared export manifest changed after review")
    if manifest.get("role")!="main":
        raise ValueError("Initial static shell requires a Main export with zero signal inputs")
    if manifest.get("physical_inputs"):
        raise ValueError("Physical input bindings require a package-based player; static shells do not read inputs")
    return {"manifest":manifest,"provenance":provenance}

def source_inventory() -> dict[str,str]:
    files = [ROOT/"tools/build_firmware.py"]
    files += [p for p in (ROOT/"firmware").rglob("*") if p.is_file()]
    files += [p for p in (ROOT/"module-sdk").rglob("*") if p.is_file()]
    files += [p for p in (ROOT/"runtime").rglob("*") if p.is_file()]
    files += [p for p in (ROOT/"host/visual").rglob("*") if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def variant_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}",value):
        raise argparse.ArgumentTypeError("Variant must use 1..48 letters, digits, underscores or hyphens")
    return value

def digest_tree(path: Path) -> str:
    sha = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"Dependency symlinks are unsupported: {file}")
        if file.is_file():
            sha.update(file.relative_to(path).as_posix().encode()+b"\0")
            sha.update(hashlib.sha256(file.read_bytes()).digest())
    return sha.hexdigest()

def prepare_components(source: Path, destination: Path) -> list[str]:
    lock = json.loads((ROOT/"firmware/dependencies.amoled.json").read_text())["components"]
    for name, info in lock.items():
        component = source/name
        if not component.is_dir() or digest_tree(component) != info["source_tree_sha256"]:
            raise ValueError(f"Missing or changed pinned dependency: {component}")
    # Verify the whole input collection before copying any component.
    destination.mkdir(parents=True, exist_ok=True)
    names = {name: name.split("__",1)[1] if "__" in name and not name.startswith("waveshare__") else name for name in lock}
    for path in destination.iterdir():
        if path.is_dir() and path.name not in names.values():
            shutil.rmtree(path)
    for name, info in lock.items():
        target = destination/names[name]
        if target.exists() and digest_tree(target) != info["source_tree_sha256"]:
            shutil.rmtree(target)
        if not target.exists():
            shutil.copytree(source/name, target)
    return sorted(names.values())

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", choices=("xiao", "amoled"))
    parser.add_argument("--idf-path", type=Path, default=Path(os.environ.get("IDF_PATH", str(Path.home()/"esp/esp-idf"))))
    parser.add_argument("--components-from", type=Path)
    parser.add_argument("--export-dir", type=Path, help="Validated prepared Main export from host/compiler/prepare.py")
    parser.add_argument('--player', action='store_true', help='Build the stable Main patch player, without embedding a patch')
    parser.add_argument('--usb-midi-host',action='store_true',help='Experimental XIAO player USB-host build; replaces USB console, needs external host power and Wi-Fi setup')
    parser.add_argument("--variant", type=variant_name, help="Safe label for an independent generated build directory")
    parser.add_argument("--patch-title",default="RNBO Patch",help="Title for the AMOLED patch view")
    parser.add_argument("--arena-bytes",type=int,default=1048576,help="Explicit RNBO arena budget (4096..4194304; default 1 MiB)")
    parser.add_argument('--initial-volume',type=int,default=None,
                        help='Startup volume percent (0..100; default XIAO50, AMOLED100)')
    parser.add_argument("--clean", action="store_true", help="Remove only this board's generated build/config")
    args = parser.parse_args()
    if args.player and args.export_dir:
        parser.error('--player and --export-dir are mutually exclusive')
    if args.usb_midi_host and (not args.player or args.board!='xiao' or not args.variant):
        parser.error('--usb-midi-host requires xiao --player and an explicit --variant; do not replace the normal console build')
    if args.initial_volume is None:
        args.initial_volume = 50 if args.player or args.board == 'xiao' else 100
    if args.player and args.initial_volume!=50:
        parser.error('The empty player starts at 50%; patch metadata supplies its startup volume')
    if not 4096<=args.arena_bytes<=4194304:
        parser.error('--arena-bytes must be between 4096 and 4194304')
    if not 0<=args.initial_volume<=100:
        parser.error('--initial-volume must be between 0 and 100')
    build = ROOT/"build"/(f"firmware-{args.board}"+("-player" if args.player else "-rnbo" if args.export_dir else "")+(f"-{args.variant}" if args.variant else ""))
    if args.clean and build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True, exist_ok=True)
    idf = args.idf_path.expanduser().resolve()
    if not (idf/"tools/idf.py").is_file():
        parser.error("ESP-IDF not found; supply --idf-path or IDF_PATH")
    version_source=(idf/"tools/cmake/version.cmake").read_text()
    version=tuple(int(re.search(r"set\(IDF_VERSION_"+part+r" (\d+)\)",version_source).group(1)) for part in ("MAJOR","MINOR","PATCH"))
    if version!=(5,5,0):
        parser.error("This bring-up profile requires ESP-IDF 5.5.0")
    environment = dict(os.environ)
    environment.update(IDF_PATH=str(idf), IDF_COMPONENT_MANAGER="0", PYTHONDONTWRITEBYTECODE="1")
    if not environment.get("IDF_PYTHON_ENV_PATH"):
        candidates = sorted((Path.home()/".espressif/python_env").glob("idf5.5_py*_env"))
        candidates = [path for path in candidates if (path/"bin/python").is_file()]
        if not candidates:
            parser.error("Set IDF_PYTHON_ENV_PATH to an installed ESP-IDF 5.5 Python environment")
        environment["IDF_PYTHON_ENV_PATH"] = str(candidates[-1])
    definitions = ["-D", "IDF_TARGET=esp32s3", "-D", f"RNBO_S3_BOARD={args.board}",
                   '-D',f'RNBO_S3_PLAYER={"ON" if args.player else "OFF"}',
                   '-D',f'RNBO_S3_ARENA_BYTES={args.arena_bytes}',
                   '-D',f'RNBO_S3_INITIAL_VOLUME={args.initial_volume}',
                   "-D", f"SDKCONFIG={build/'sdkconfig'}", "-D",
                   f"SDKCONFIG_DEFAULTS={ROOT/'firmware'/f'sdkconfig.{args.board}.defaults'}"]
    if args.player:
        from build_loader_spike import inventory
        lock = json.loads((ROOT/'loader-spike/dependencies.json').read_text())['components']
        loader_stage = ROOT/'build/vendor-player'
        for name in ('elf_loader','cmake_utilities'):
            source = ROOT/'build/vendor-loader-spike'/name
            if not source.is_dir() or inventory(source) != lock[name]['files_sha256']:
                parser.error('Stable player needs the pinned loader cache; run tools/build_loader_spike.py first')
            target = loader_stage/name
            if target.exists() and inventory(target) != lock[name]['files_sha256']:
                shutil.rmtree(target)
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copytree(source,target)
        definitions += ['-D',f'RNBO_S3_PLAYER_DEPENDENCIES_DIR={loader_stage}']
        # Preserve each board's normal settings and append the loader contract.
        for i,value in enumerate(definitions):
            if str(value).startswith('SDKCONFIG_DEFAULTS='):
                definitions[i]=str(value)+';'+str(ROOT/'firmware/sdkconfig.player.defaults')
                if args.usb_midi_host:definitions[i]+=';'+str(ROOT/'firmware/sdkconfig.usb-midi-host.defaults')
    if args.player and (build/'sdkconfig').is_file():
        # Older player caches enabled PHY calibration persistence. Radio setup
        # must not write flash behind the audio maintenance owner.
        cached_config = (build/'sdkconfig').read_text()
        cached_config = cached_config.replace('CONFIG_ESP_PHY_CALIBRATION_AND_DATA_STORAGE=y',
                                              '# CONFIG_ESP_PHY_CALIBRATION_AND_DATA_STORAGE is not set')
        cached_config = re.sub(r'^CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE=\d+$',
                               'CONFIG_ESP_SYSTEM_EVENT_TASK_STACK_SIZE=8192', cached_config, flags=re.MULTILINE)
        (build/'sdkconfig').write_text(cached_config)
    prepared = None
    if args.export_dir:
        args.export_dir=args.export_dir.expanduser().resolve()
        prepared=verify_prepared(args.export_dir)
        definitions += ["-D", f"RNBO_S3_EXPORT_DIR={args.export_dir}"]
    else:
        definitions += ["-D", "RNBO_S3_EXPORT_DIR="]
    components = []
    visual = None
    if args.board == "amoled":
        sys.path.insert(0,str(ROOT/'host/visual'))
        from layout import write_layout
        source=args.export_dir/'source.rnbopat' if args.export_dir and (args.export_dir/'source.rnbopat').is_file() else None
        visual=write_layout(source,args.export_dir/'description.json' if args.export_dir else None,
                            build/'visual','RNBO Player' if args.player else args.patch_title)
        definitions += ['-D',f'RNBO_S3_VISUAL_DIR={build/"visual"}']
        if not args.components_from:
            parser.error("AMOLED requires --components-from with the pinned component collection; see firmware/dependencies.amoled.json")
        stage = ROOT/"build/vendor-amoled"
        components = prepare_components(args.components_from.expanduser().resolve(), stage)
        environment["LVGL_VERSION"] = "8.4.0"
        definitions += ["-D", f"RNBO_S3_COMPONENTS_DIR={stage}", "-D", "RNBO_S3_VENDOR_COMPONENTS="+";".join(components)]
    shell = 'source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"'
    command = ["bash", "-e", "-c", shell, "rnbo-s3-build", str(idf), "-B", str(build), *definitions, "build"]
    integration_hashes=source_inventory()
    with (build/"build.log").open("w") as log:
        proc = subprocess.Popen(command, cwd=ROOT/"firmware", env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
            sys.stdout.flush()
            log.flush()
        result = proc.wait()
    if result:
        return result
    if source_inventory()!=integration_hashes:
        raise ValueError("Integration source changed during build; run again for an accurate artifact identity")
    if args.player:
        for name in ('elf_loader','cmake_utilities'):
            if inventory(loader_stage/name)!=lock[name]['files_sha256']:
                raise ValueError('Pinned player loader changed during compilation')
    if prepared and verify_prepared(args.export_dir)!=prepared:
        raise ValueError("Prepared export changed during build")
    description = json.loads((build/"project_description.json").read_text())
    config = (build/"sdkconfig").read_text()
    actual_host='CONFIG_RNBO_S3_USB_MIDI_HOST=y' in config
    if actual_host!=args.usb_midi_host:
        raise ValueError('Cached USB host selection differs; use a fresh variant or --clean')
    if actual_host and 'CONFIG_ESP_CONSOLE_NONE=y' not in config:
        raise ValueError('USB MIDI host must not share the internal PHY with a console')
    expected_flash = "8MB" if args.board == "xiao" else "16MB"
    if f"CONFIG_ESPTOOLPY_FLASHSIZE_{expected_flash}=y" not in config:
        raise ValueError("Resolved flash configuration does not match requested board")
    component_names = description.get("build_components", [])
    if args.board == "xiao" and any(any(key in name for key in ("lvgl", "waveshare", "codec", "lcd_touch")) for name in component_names):
        raise ValueError("Display/codec dependency leaked into XIAO build")
    report = {"board":args.board, "variant":args.variant,"sample_rate":44100, "block_frames":256,
              'initial_volume_percent':args.initial_volume,
              "signal_format":"planar-float32", "sink_channels":2 if args.board=="xiao" else 1,
              "sink_format":"signed-16bit-Philips-I2S", "default_source":"dynamic-rnbo-player" if args.player else "static-rnbo" if prepared else "engine-neutral-stereo-tone",
              "idf_version":json.loads((build/"config.env").read_text()).get("IDF_VERSION"),
              "idf_git_revision":description.get("git_revision"), "components":component_names,
              "sdkconfig_sha256":hashlib.sha256(config.encode()).hexdigest(),
              "integration_files_sha256":integration_hashes,
              "hardware_qualified":False,"dynamic_loader_qualified":False,
              "artifacts":{}}
    if args.player:
        report['player']=True
        report['usb_midi_host']=actual_host
        report['midi_input_version']=1
        report['player_api_version']=1
        report['loader_dependencies']=json.loads((ROOT/'loader-spike/dependencies.json').read_text())
    compiler=description.get("c_compiler")
    if not compiler:
        cache=(build/"CMakeCache.txt").read_text()
        compiler=next(line.partition("=")[2] for line in cache.splitlines() if line.startswith("CMAKE_C_COMPILER:FILEPATH="))
    report["compiler"]={"path":compiler,"version":subprocess.run([compiler,"--version"],check=True,capture_output=True,text=True).stdout}
    idf_commit=subprocess.run(["git","-C",str(idf),"rev-parse","HEAD"],capture_output=True,text=True)
    report["idf_git_commit"]=idf_commit.stdout.strip() if idf_commit.returncode==0 else None
    nm_tool=str(Path(compiler).with_name(Path(compiler).name.removesuffix("gcc")+"nm"))
    hook_object=build/"esp-idf/main/CMakeFiles/__idf_main.dir/allocation_watch.c.obj"
    undefined=subprocess.run([nm_tool,"-u",str(hook_object)],check=True,capture_output=True,text=True).stdout
    if any(word in undefined for word in ("__atomic", "malloc", "calloc", "realloc", "printf", "semaphore", "spinlock")):
        raise ValueError("Allocation watch hook depends on an unexpected blocking/allocating helper")
    report["allocation_watch_undefined_symbols"]=undefined
    elf=build/description["app_elf"]
    size_tool=str(Path(compiler).with_name(Path(compiler).name.removesuffix("gcc")+"size"))
    report["elf_sections"]=subprocess.run([size_tool,"-A",str(elf)],check=True,capture_output=True,text=True).stdout
    report["compile_commands_sha256"]=hashlib.sha256((build/"compile_commands.json").read_bytes()).hexdigest()
    if args.board=="amoled":
        report["dependency_lock"]=json.loads((ROOT/"firmware/dependencies.amoled.json").read_text())
        report['visual']={'report':visual,'generated_files_sha256':{
            name:hashlib.sha256((build/'visual'/name).read_bytes()).hexdigest() for name in ('patch_layout.c','visual.json')}}
    if prepared:
        report["prepared_export"]=prepared
        report["allocation_coverage"]={"rnbo":"module platform hooks",
            "heap":"successful heap operations by detached preparation task and running audio owner; ISR/other tasks excluded",
            "heap_guard_enabled":"CONFIG_RNBO_S3_ALLOCATION_WATCH=y" in config,
            "hardware_observed":False,"initialization_peak_measured":False}
        report["initialization"]={"arena_bytes":args.arena_bytes,"arena_placement":"PSRAM","warmup_blocks":4,"seed":0x12345678}
    for file in [build/description["app_elf"], build/description["app_bin"], build/"partition_table/partition-table.bin"]:
        report["artifacts"][str(file.relative_to(ROOT))] = {"bytes":file.stat().st_size, "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
    (build/"build-report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(f"Build verified: {build/'build-report.json'}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
