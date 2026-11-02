# Local export and static compilation

This first compiler route uses the installed RNBO 1.4.4 generator or a manually
exported **Minimal C++ Export**. It prepares trusted C++ for a native host render
tool and for static ESP-IDF builds. Dynamic `.rnbos3` packages and device uploads
are not implemented by these tools.

From the repository root:

```sh
node host/export/export.mjs examples/sine/sine.rnbopat --out build/exports/sine
python3 host/compiler/prepare.py --export build/exports/sine \
  --class-name rnbos3patch --role main --out build/prepared/sine
python3 host/compiler/build.py --export build/prepared/sine --build-dir build/host-sine
python3 -m unittest discover -s host/compiler -p 'test_*.py' -v
```

The generator discovers an authorized RNBO package in the standard Max 9 user
package directory or Max application. Override it with `--rnbo-dir` or `RNBO_DIR`.
It checks version 1.4.4 before using internal APIs and leaves the package alone.
Each output directory must be new. Generated C++ and runtime headers stay inside
ignored `build/` directories with their original notices.

The first `.rnbopat` importer supports **flat, self-contained RNBO graphs** made
of `newobj` boxes, comments, and panels. Embedded subpatches, Gen, external
abstractions, presets, external sample assets, and arbitrary Max `.maxpat` input
are not admitted. This is a deliberately narrower input route than the upstream
FM1 converter. The original example patch designs in `examples/` use this route.

For a manual export, select a fixed sample rate of **44100**, fixed vector of
**256**, and Minimal Export in RNBO. Supply the following directory contents:

```text
rnbo_source.h          generated Minimal C++ header with its license notice
description.json       matching RNBO export description
common/                unmodified matching RNBO runtime headers
RNBO-runtime-LICENSE   MIT notice from the runtime source directory's LICENSE
```

Use its generated class name with `--class-name` (often `rnbomatic`). Main exports
require zero inputs and stereo outputs; `--role fx` requires two inputs and two
outputs. The initial adapter admits up to 128 ordinary numeric parameters and
one MIDI input port, and explicitly rejects signal parameters,
message ports, and external data dependencies. Runtime channels and parameter
metadata are also checked by the wrapper; a prepared manifest is not proof that
native C++ is safe or that it meets an ESP32 timing budget.

MIDI transmission is not implemented. Exports declaring a MIDI output port are
rejected by default. RNBO's polyphonic exporter inserts such a port even for the
MIDI-envelope example, so that route requires an explicit `--midi-output discard`
when preparing it. The manifest and native descriptor report that discarded
output policy. This does not change the complete MIDI messages delivered to the
patch's input.

Use `--voices 1`, `--voices 2`, or `--voices 4` on `export.mjs` to select RNBO's
single or polyphonic export topology. The local generator records the selected
voice count; a manual export's topology remains unspecified until reviewed.
To build the fixture-specific MIDI tests:

```sh
node host/export/export.mjs examples/midi-envelope/midi-envelope.rnbopat \
  --voices 2 --out build/exports/midi2
python3 host/compiler/prepare.py --export build/exports/midi2 \
  --class-name rnbos3patch --midi-output discard --out build/prepared/midi2
python3 host/compiler/build.py --export build/prepared/midi2 --build-dir build/host-midi2
cmake -S . -B build/host-midi2 -DRNBO_S3_MIDI_TEST_VOICES=2
cmake --build build/host-midi2
ctest --test-dir build/host-midi2 --output-on-failure
```

These tests cover the authored fixture's note/release behavior. The polyphonic
export's generated allocator adds sustain and oldest-voice replacement. It
reuses a repeated pitch and uses a shared sustain policy by default. The simple
single-voice graph implements direct `notein` behavior and has no pedal logic or
mono note-priority policy. General MPE and arbitrary patch MIDI behavior remain
additional qualification work.

Preparation preserves source and runtime bytes under `originals/`, records every
raw/prepared file hash and parameter-schema identity, and emits `patch_config.h`.
It applies independently recorded, exact-pattern RNBO 1.4.4 correctness fixes:
bounded list copies, inline-storage move ownership, cross-capacity assignment
return types, and nested clock target dispatch. A changed upstream pattern
stops preparation. `--no-runtime-fixes` creates an explicitly unmodified-runtime
reference build. The default `float32-strict` profile does not perform float-literal rewriting, buffer narrowing,
approximate math, FM1 processor changes, or broad source substitutions. Signal
processing uses float32 and the wrapper retains double scheduler time.

`build.py` verifies the prepared files and manifest against provenance before
calling CMake. `host-build.json` identifies the resulting **native host** executable
and source manifest. Host output is comparison evidence; it is not an Xtensa
artifact, target performance measurement, or qualification of a dynamic loader.

## Optional oscillator optimization

`--numerical-profile float32-cycle-v1` enables a separately recorded optimization
for the reviewed RNBO 1.4.4 scalar-frequency, fixed-256 `cycle~` kernel. It adds
an `f` suffix to exactly two coefficients used inside that sample loop, avoiding
software double multiplication on ESP32-S3. Integer phase wrapping, truncation,
lookup/interpolation, buffer formats and double scheduler time remain unchanged.
It does not enable fast-math. A different kernel or source layout is rejected by
this profile; use the strict profile for unqualified forms.

```sh
python3 host/compiler/prepare.py --export build/exports/sine \
  --class-name rnbos3patch --role main \
  --numerical-profile float32-cycle-v1 --out build/prepared/sine-cycle-f32
```

The manifest and provenance identify the profile, affected kernels, exact raw
and prepared hashes, and literal count. Original generated notices and source
remain preserved. Host qualification covered 36 authored sine/MIDI cases and
observed identical final float32/PCM samples. An exhaustive coefficient-domain
check also found 192 differing intermediate fraction values out of 262,144,
with a maximum difference of `5.96e-8`; this is not a universal bit-identity
promise, particularly for arbitrary feedback graphs. Keep the strict profile as
the comparison reference and qualify each supported target form.
