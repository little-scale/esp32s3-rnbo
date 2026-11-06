# Native export compilation

The only supported patch frontend is Cycling ’74’s **C++ Minimal Export in Max**.
Follow the [export settings](../docs/native-export.md), then use Studio or these
commands. All output directories must be fresh:

```sh
python3 host/native_export.py /path/to/MaxExport --out build/native-source
# The preceding command prints class_name; use that actual name below.
python3 host/compiler/prepare.py --export build/native-source \
  --class-name rnbomatic --role main --numerical-profile float32-strict \
  --out build/native-prepared
python3 host/compiler/build.py --export build/native-prepared --build-dir build/native-host
build/native-host/rnbo_render --output build/native.wav --blocks 8 --warmup 4
python3 host/compiler/build_module.py --export build/native-prepared --build-dir build/native-module
python3 host/compiler/package.py --help
```

`native_export.py` accepts a folder or ZIP, keeps generated C++/runtime bytes,
normalises the header filename to `rnbo_source.h`, detects its class and adds the
pinned runtime MIT notice if absent. `prepare.py` validates runtime 1.4.4,
44100/256 assertions, channel/parameter/service limits and records raw/prepared
hashes and adaptations. The wrapper defines `RNBO_USE_FLOAT32`; this does not
promise every internal variable is Float32.

Main is zero audio inputs and stereo outputs. The player admits at most 32
ordinary numeric input parameters, one MIDI input port and no external data,
signal parameters or arbitrary message ports. The lower-level FX role remains a
qualification harness; Studio loads Main only. MIDI output rejects by default;
`--midi-output discard` is an explicit lower-level policy, not MIDI transmission.
Set polyphony and delay capacities in Max before exporting.

The native renderer is a startup/allocation screen, not proof of every parameter,
event sequence, numerical result or ESP32 deadline. Native C++ remains trusted
local executable input. No board is flashed by the commands above.

Historical optimisation switches remain for reproducing old studies; they are
not supported Studio profiles or qualified on arbitrary native Max exports.
The [retired importer](../archive/README.md) is research-only. No compiler step
runs it for a normal native export.
