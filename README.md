# RNBO for ESP32-S3

An initial native compilation toolchain and runtime shell for RNBO 1.4.4.
The primary board is **Waveshare ESP32-S3 Touch AMOLED 1.8 V2**, with 16 MiB
flash, 8 MiB PSRAM and the ES8311 mono speaker path. The **XIAO ESP32S3 headless
profile** uses the same core runtime with stereo I²S and has initial hardware
validation with 3sawsDrone. See the [headless guide](docs/headless.md).

See [implementation status and validation](docs/STATUS.md) for the completed
builds, test evidence and remaining physical gates.
The original technical handover is a historical starting point; implementation
status records the current results.

The searchable [object and operation status page](https://little-scale.github.io/esp32s3-rnbo/)
lists the complete pinned inventory, verification scope, available and experimental
optimisations, and measured CPU time saved. Each qualified row links to its evidence.

The AMOLED V2 now runs the oscillator and four-voice MIDI fixtures on hardware.
Two five-minute MIDI stress runs passed with no render overruns or late
allocations. The optional `float32-cycle-v1` profile reduced average render load
from 57.0% to 34.5% of one audio core in that workload. The small ELF-loader
fixture passed, followed by real RNBO native modules: 132 image loads/unloads
across 32 target cycles, exact sine float/PCM comparisons, stereo FX and four
MIDI notes. See [dynamic loader evidence](docs/dynamic-loader.md).

RNBO generates C++, which is compiled into native Xtensa code. The first working
route statically links one patch into the firmware. Independent ELF loading has
passed isolated lifecycle tests; integration with live audio replacement and
persistent uploadable packages is still under development. No SynthDef
interpreter is in this render path.

The shared profile is **44,100 Hz / 256 frames / planar float32 stereo**.
The final sink applies a 20 ms volume ramp, explicit 0.5 headroom, finite checks
and saturation. AMOLED averages left and right at the mono boundary; XIAO keeps
the channels separate. Autonomous patches run without a touch gate.

The supplied `3sawsDrone3` now plays on the AMOLED board with its actual graph
and touch parameters. Its explicit 40 ms comb cap and optional float32 audio
profile reduce resource cost; original source and strict reference variants are
retained. See [patch qualification](docs/drone3-qualification.md),
[bounded filters](docs/bounded-filters.md) and
[float32 choices and numerical comparisons](docs/float32-audio.md).

The [AMOLED controls](docs/amoled-controls.md) include Pause/Resume, a page with
eight parameter sliders, and a post-volume output meter.

## Build and verify on the computer

Prerequisites: an authorized local RNBO **1.4.4** installation, Node, Python 3,
CMake and a C++17 compiler. Nothing installs into or modifies Max/RNBO.

```sh
python3 tools/qualify_host.py
```

This creates a fresh `build/qualification/` directory, genuinely exports the
original oscillator, FX and 1/2/4-voice MIDI fixtures, prepares raw and adapted runtimes, compiles
native host renderers, and checks admission, lifecycle, parameters, allocation
observations, PCM and float samples. It records numerical comparisons and source
identities. `--rnbo-dir /path/to/RNBO` selects a nonstandard installation.
It also tests the capture client with simulated device replies. Host timings do
not establish ESP32 performance.

For individual builds:

```sh
node host/export/export.mjs examples/sine/sine.rnbopat --out build/exports/sine
python3 host/compiler/prepare.py --export build/exports/sine \
  --class-name rnbos3patch --role main --out build/prepared/sine
python3 host/compiler/build.py --export build/prepared/sine --build-dir build/host-sine
build/host-sine/rnbo_render --output build/sine.wav --float-output build/sine.f32
```

Output directories must be new. See [host/README.md](host/README.md) for manual
Minimal C++ imports, the supported flat `.rnbopat` route, polyphony options,
explicit MIDI-output policy, and provenance. Explicit GenExpr in `gen~` is
admitted; visual Gen patchers, arbitrary Max projects, external assets and a
full browser converter remain later work.

## Build for the AMOLED V2

Use ESP-IDF **5.5.0** and the reviewed Xtensa **14.2.0** toolchain. The helper
uses separate board build/config directories and verifies the exact dependency
source collection before staging it inside this project.

```sh
python3 tools/build_firmware.py amoled \
  --components-from /path/to/pinned/managed_components \
  --export-dir build/prepared/sine
```

`--idf-path /path/to/esp-idf` selects another installation. The component collection
must match `firmware/dependencies.amoled.json`; the original SynthDef checkout's
reviewed `firmware/managed_components` is a read-only source for this initial
offline route. The build script never changes that checkout. Display/codec
components are excluded from the XIAO graph:

```sh
python3 tools/build_firmware.py xiao --export-dir build/prepared/sine
```

XIAO builds start automatically, unpaused at **50% volume** by default. The
AMOLED default remains 100%; `--initial-volume` selects another startup level.

Omit `--export-dir` for the independent stereo tone bring-up fixture. Static RNBO
and tone builds use separate directories. Build reports record board, actual
compiler, resolved config, component inventory, source hashes and artifacts.
Build helpers do not flash the board.

`--patch-title` names the graph, `--initial-volume 0` starts quietly, and
`--arena-bytes` sets an explicit 4 KiB–4 MiB arena budget (default 1 MiB).
The original compact drone uses 393,216 reserved bytes with 361,240 bytes used.
The later [table-omitted build](docs/unused-mtof-table.md) reserves 131,072 bytes
with 99,088 bytes used.
The arena budget must cover the admitted patch; exhaustion intentionally stops
unchecked native allocation instead of falling back to the firmware heap.

The AMOLED shell includes an [FM1-style patch view](docs/patch-view.md): black,
blue RNBO objects, white wires and Barlow text. Tap a parameter box to edit it;
volume, a single Pause/Resume button, Params and battery indication remain
available. It reuses the pinned board power/display/touch initialization.
Post-volume PCM capture works on both profiles. See
[the hardware bring-up procedure](docs/bringup.md) and
[the capture client](host/clients/README.md).

The separate [loader spike](docs/loader-spike.md) builds a small native module
and standalone test firmware for constructors, narrow imports, PSRAM, two
independent images and repeated unloading. It remains separate from audio
firmware. Its small-fixture physical tests passed on the AMOLED V2; RNBO loading
has now passed its separate RNBO allocation, import, lifecycle and offline DSP
qualification in [the RNBO loader test](docs/dynamic-loader.md).

## Runtime boundaries

The C ABI admits one generated image and one context in the initial static
application. The audio task owns processing and events. It receives bounded
control events; UI and USB code do not mutate the patch concurrently. RNBO
platform allocations use a bounded arena; normal C++ allocation remains available
to the system. A separate task-aware heap guard observes audio-owner allocations.
No process-wide allocator override is installed in the firmware.

Events currently arrive at block boundaries. The shell checks a uint64 frame
position; long-uptime sample-accurate RNBO scheduling remains unqualified. Panic
has an independent final mute path. The shell parks the audio owner, reconstructs
the patch on core 0, restores parameters and requires an explicit matching Resume
before attaching it again. Audio continues submitting zeros during maintenance.
Old events and stale Resume requests cannot start a replacement instance.

A live Main-to-FX pipeline, persistent modules and remote deployment remain
separate milestones. See
[docs/architecture-review.md](docs/architecture-review.md),
[UPSTREAM.json](UPSTREAM.json), and the original
[technical handover](RNBO_ESP32S3_TECHNICAL_HANDOVER.md).

Systematic XIAO object testing is under way: [results and remaining scope](docs/xiao-qualification.md). Board measurements remain separate from AMOLED results.

Gen/`gen~` operators and single-sample behaviour are explicitly in scope. See [Gen qualification](docs/gen-qualification.md) for native sample/partition tests, the first three XIAO history programs and the remaining operator work.
The optional [Gen feedback Float32 profile](docs/gen-feedback-float32.md) now measures 83.94% less callback time in its matched XIAO test; broader Gen optimisation remains pending.
Fifteen [GenExpr arithmetic spellings](docs/gen-arithmetic-qualification.md) also pass individual XIAO output, timing and memory checks; their identical-module controls claim no optimisation gain.
The separate [Gen abs intrinsic comparison](docs/gen-abs-intrinsic.md) now measures 36.19% less callback time with exact finite magnitude bits in four XIAO cases.
Twenty additional [Gen comparison/logic forms](docs/gen-logic-qualification.md) pass individual XIAO checks; `step` retains a documented-order mismatch and `sign(-0)` is observed as `+0`.
Coverage now prioritises [fast hardware smoke batches](docs/hardware-smoke.md): one upload checks multiple forms, records pass/fail and CPU timing, and queues unusual CPU costs for later optimisation. The latest numeric batch checks 33 RNBO signal forms: 30 pass, three have output mismatches, and eight are queued for CPU review. The earlier arithmetic/logic batch passes all 36 forms. The separate Gen mathematical batch adds 27 device passes, four C++ compilation failures and three parser rejections, with thirteen CPU-review entries. Test firmware can remain installed between batches.
