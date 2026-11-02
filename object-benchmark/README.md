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
fixtures run autonomously. This initial target revision admits Main fixtures
only. The legacy generic FX generator in the source cannot stand in for the
pitch/frequency contracts declared by the new FX catalog, so the builder rejects
FX pending explicit generator integration. Analytical response/spectral checks
and the direct-input FX host tests remain in the host qualification tool.

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
