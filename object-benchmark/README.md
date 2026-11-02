# Offline RNBO object comparator

This separate ESP-IDF project embeds one verified strict module and one verified
optimized module. It runs on core 1 at 44,100 Hz / 256 frames without starting
I2S, display or network services. It never writes flash. The host build helper
never accesses a device.

Build a pair after `host/compiler/qualify_objects.py` and the module compiler
have produced the six milestone-2 artifacts:

```sh
python3 tools/build_object_benchmark.py --fixture-id mtof-varying
python3 tools/build_object_benchmark.py --fixture-id saw-signal
python3 tools/build_object_benchmark.py --fixture-id reson-modulated
```

`--catalog`, `--qualification-dir`, `--strict-export`, `--optimized-export`,
`--strict-module` and `--optimized-module` select other admitted fixture pairs.
Use `--validate-only` for admission/configuration without compiling. Build outputs
and complete source/config/compiler/module identities are recorded under
`build/object-benchmark-amoled-FIXTURE/build-report.json`. The partition table
must match the actual instrument before a hardware runner flashes an app.
Only the root agent operates the board and restores the working instrument.

Each case creates a fresh context with four detached warmup blocks and the same
seed, then applies its catalog parameters as block-zero events. Up to five
rounds are supported (three by default). Strict and optimized passes run
sequentially; the first profile alternates each round. The first 32 rendered
blocks per pass are excluded from process timing, while all rendered samples
participate in comparisons. Parameter events and create/prepare timings are
reported separately. The complete process callback, including its module checks,
is timed; input generation, analysis, copy, yields, reporting and heap probes
around the callback are outside that interval. These measurements do not prove
an application deadline or isolate an individual instruction/object internally.

Catalog tolerances apply separately to each case: maximum absolute float error,
maximum signed-16 PCM difference and relative RMS level difference over both
channels. Error RMS, sample counts, clipped counts and per-case/profile CPU,
peak/RMS and arena usage are also printed. PCM uses gain 0.5, saturation and
symmetric 32767 scaling with `lrintf`, matching the host render comparison. Main
fixtures run autonomously. FX fixtures must declare one of `midi-stereo-v1`,
`frequency-stereo-v1` or `reson-stereo-v1`, with complete settings in the separate
FX catalog. Unknown fields/kinds, unsafe pitch/frequency bounds and ignored Main
stimulus declarations fail host admission. Case overrides replace only known
numeric fields. Absolute rendered time is n/44100 after zero-input warmup;
generation uses Float64 sine and rounds each final input sample to Float32.
The target precomputes one complete case into a caller-owned PSRAM cache,
then copies disjoint planar input buffers before each process callback. Every
strict/optimized pass uses those same cached bytes. Each `INPUT` line records
SHA-256 over the interleaved little-endian stereo Float32 bytes; the target
rehashes before and after passes. The declared pilot/reference output channel
must also pass through its input exactly. Native and target transcendental
rounding need not give identical input hashes across platforms, so no such
identity is assumed. Analytical response/spectral checks remain in the host
qualification tool.

Build the declared FX inputs in fresh variant directories:

```sh
python3 tools/build_object_benchmark.py --fixture-id mtof-fx \
  --catalog tests/fixtures/objects/catalog-fx.json \
  --qualification-dir build/object-qualification/fx-1 --variant declared-input-v1
```

Use `saw-fx` and `reson-fx` for the other pairs. The host rejects a conservative
PSRAM budget exceeding 8 MiB: reference and FX input caches, work buffers, two
selected arenas, the complete admitted one-MiB opaque context bound per image,
inspected image spans and 512 KiB of allocator/loader reserve. The runtime still
requires actual successful PSRAM allocations. A sealed build directory cannot
be overwritten with another producer/module/config identity; select a fresh
`--variant`. Existing Main hardware candidates remain historical artifacts.

The loader and admission checks are adapted from the physically qualified
`rnbo-loader-test`: zero undefined imports, pinned loader, callback/data spans,
constructor/finalizer validation, explicit handshake, caller-owned PSRAM and
exclusive context ownership. Selected arena capacity is at most one MiB per
image. A prewarm load/process/unload precedes heap baselines, but its first event
and process calls are still allocation checked. Every live context must report
zero local late allocations/errors/nonfinite samples. Task-aware IDF hooks
observe successful host heap allocations/frees during every dispatched event
and process call. Detached creation/preparation may allocate within the module
arena and are not subject to that real-time host heap assertion. Both images
must finalize once and unload with exactly restored free PSRAM and no decrease
in free internal heap; this is observed accounting, not proof against arbitrary
native memory corruption.

A full successful run ends with `RNBO_OBJECT_BENCHMARK PASS `, firmware ELF hash,
both module hashes, comparison/timing counts and restored-heap evidence.
`CASE`, `CASE_PROFILE` and `PROFILE` lines carry detailed measurements. Any failed
gate logs `FAIL` and aborts. A 550-second execution budget fails closed before the
hardware runner's 600-second limit. No target success is claimed by a build.
