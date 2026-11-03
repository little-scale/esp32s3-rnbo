# Local export and static compilation

`--float32-onepole-clamp` is an experimental, default-off local comparison
option for exact generated onepole clamps. It preserves finite stored values
under nearest-even rounding, while excluding floating flags/traps and NaN
payload equivalence. Coefficients, recurrence, clocks and the known accuracy
failures remain unchanged. See the [proof, use and separate numerical study](../docs/onepole-float32.md).

The [wave3 stateful qualification driver](../tests/fixtures/objects/wave3/native/README.md)
reproduces the 45 native `onepole~`, `slide~`, `delta~` and `sah~` programs through
the production dynamic C ABI. Its current complete baseline intentionally exits
with a qualification failure because six mathematical accuracy gates fail;
runtime health and compiler admission are recorded separately. See the
[results and precision audit](../docs/wave3-stateful.md). It requires no board.

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
return types, nested clock target dispatch, and defined 32-bit multiply/pink RNG
arithmetic. A changed upstream pattern
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

## Optional finite wrap correction

`--correct-finite-wrap` is a default-off correctness option for two exact
RNBO 1.4.4 exports: the authored `nonlinear-domains` fixture and
`wrap-finite-stereo`. Both use fixed `wrap~ -1 1` kernels, Float32 samples,
44100 Hz and 256-frame blocks. Complete source, description, kernel and corrected
runtime hashes are pinned. Other intervals, source layouts, widths and versions
are rejected. This first admission does not support arbitrary patches containing
`wrap~`.

For finite binary32 values with magnitude at least `2^24`, every representable input
is an even integer. The inserted guard returns the exact wrapped result `+0`
before the original integer conversion. This corrects known large-finite wrong
results and out-of-range conversion/overflow paths. Every original branch below
that threshold, including the input `-0` branch, remains byte-identical.
NaN/Infinity bypass the guard: their inherited route remains unqualified and can
contain undefined conversions. The option requires finite audio input; it is
not a nonfinite-safety or generic modulo API.

```sh
python3 host/compiler/prepare.py \
  --export build/object-optimisation/wrap-target-v1/raw/wrap-finite-stereo \
  --class-name rnbos3patch --role fx --correct-finite-wrap \
  --out build/prepared/wrap-finite-stereo-corrected
```

The option requires normal runtime fixes and FX role. It accepts either the
`float32-strict` base profile or the separately reviewed
`float32-scalar-powers-v1` composition below. Other optional adapters are
rejected. The wrap correction itself does not change the numerical-profile
label or enable fast-math.
The manifest records the finite-input contract and guard count; provenance
records all original/prepared hashes, exact methods, helper/transformer hashes
and inverse checks. A generated thin source include rejects Float64 compilation.
The corrected nonlinear header and internal `private_finite_wrap.h` support file
are byte-identical to the independently proved private even24 candidate. Its
historical filename preserves that comparison and denotes no public API.

The independent private proof covers all 4,278,190,080 finite binary32 encodings;
new adapter tests also check the actual generated Int32-width kernel against a
raw-bit oracle under undefined-behavior instrumentation, rejection guards and
Float32/Float64 compilation. Original protected exports stay in ignored build
directories. The [subsequent S3 qualification](../docs/wrap-finite-target.md)
checks the admitted contexts on the board: bounded output preservation and
6,291,456 direct raw-bit checks over 4,080 distinct finite values. The bounded
whole-chain measurement observes 0.276% extra CPU, with unchanged context and
arena costs. This is a correctness repair; it establishes no CPU saving.

## Experimental bounded line ramps

`--bounded-line-ramps` replaces timestamp and cancellation state in the exact
reviewed `line-timing` Main graph. It keeps Float32 audio, uses integer/relative
timing and bounded replacement state, and retains the original Double event
conversion and completion-clock policy. It requires normal fixes,
`float32-strict`, ABI 1.0 and fixed-list capacity 16, with no other options.

Native checks cover the original fault programs, long prefixes, additional
parameter combinations and focused actual clocks. The complete public target
module reproduces the reviewed prototype, but has not run on ESP32-S3. The
option is experimental; no CPU percentage is claimed. See
[use, changed rounding and qualification scope](../docs/bounded-line-ramps.md).

## Optional train reciprocal hoisting

`--hoist-train-reciprocal` admits only the reviewed `phase-pulse` Main graph
with normal fixes and `float32-strict`. It caches the original Float32 train
reciprocal once per active-width vector while retaining width-endpoint bypass,
Double floor, state and clocks. Other optional adapters and profiles reject.

The saved 12-case target comparison observes 39.06% less complete callback
time; division-free endpoint cases remain controls. The inherited warm-start
duty-check failure remains recorded, so working status stays partial. See
[scope, use and compiler evidence](../docs/train-reciprocal-compiler.md).

## Optional scalar filter-duration hoisting

`--hoist-filter-durations` requires the exact reviewed `filters-scalar` Main
graph, normal fixes, `float32-strict` and `--filter-delay-max-ms 40`. It moves the
original scalar duration declaration, Double conversion and invariant clamp
before each fixed 256-frame loop. The Float32 return, Float64 rings, remaining
per-sample processing and precise clocks are unchanged. Signal/fixed/storage,
other profile/option and current-drone contexts reject preparation.

The [admission review](../docs/filter-duration-hoist-compiler.md) binds fresh
public builds to both complete modules previously measured on target. That
three-case callback comparison used 29.03% less processing time with zero
numerical Float32 difference and exact PCM. Current-runtime native coverage
adds cold and long-tail cases, with no new board execution claimed.

## Optional exact 44.1 kHz audio-delay conversion

`--exact-audio-delay44100` requires the exact reviewed `filters-signal` Main
graph, normal fixes, `float32-strict` and `--filter-delay-max-ms 40`. It consumes
Float32 duration signals each sample and reproduces the original Double
conversion's Float32 result using integer arithmetic on the reviewed fast path.
The original capped Double fallback, Float64 rings and precise clocks remain.
Other options, source edits, rates and caps reject preparation. The new flag
and versioned manifest contract distinguish this default-off selection from
ordinary strict preparation.

The [admission review](../docs/exact-delay44100-compiler.md) binds the actual
public compiler output to the exact entire module already measured on target.
Its historical four-case comparison observed 12.70% less complete callback
time with zero numerical output difference and exact PCM. No new hardware run,
general filter/rate claim or current-drone change is implied.

## Optional scalar-power numerical profile

`--numerical-profile float32-scalar-powers-v1` admits only the exact authored
`nonlinear-domains` FX graph. It dispatches once per vector for scalar exponents
2, 4 and 0.25, using Float32 multiplication or nested square roots. Every output
retains `fixnan`; all other scalar exponents use the original `powf` route.
Complete source, description, runtime and method hashes guard admission, and a
generated include rejects Float64 compilation. Arbitrary `pow~` graphs and the
standalone stereo wrap fixture are rejected.

This profile deliberately changes rounding. It has no bit-identity, signed-zero
or floating-exception identity claim: for example, a quarter power of input
`-0` can retain `-0` where `powf` returns `+0`. Its local base domain is the
authored clip output `[0,1]`; negative bases, nonfinite inputs and general power
semantics are outside admission. Whole-graph qualification retains the reviewed
bounded finite stereo input scope. The strict default remains unchanged.

The only admitted option composition is `--correct-finite-wrap`, applied before
power specialisation in this same nonlinear graph:

```sh
python3 host/compiler/prepare.py \
  --export build/object-qualification/wave2-final/exports/nonlinear-domains \
  --class-name rnbos3patch --role fx \
  --numerical-profile float32-scalar-powers-v1 --correct-finite-wrap \
  --out build/prepared/nonlinear-wrap-and-powers
```

The manifest records the public numerical profile, `float32-strict` base,
changed-rounding identity and exact specialisation/composition contract.
Provenance records input/output/method/runtime/helper hashes and a byte inverse.
Solo output is byte-identical to the previously measured private candidate; its
historical source comment is retained for that comparison. The composed header
has its own pin, with only the power method changed relative to the corrected
baseline. Tests include neighbouring exponents, exact fallback samples,
independent mathematical bounds, failure atomicity and rejected compositions.
The [subsequent native and S3 qualification](../docs/scalar-powers.md) verifies
the public solo module's exact identity with the earlier measured prototype
and separately measures the finite-wrap composition. The three original cases
use 24.10% less callback time with exact output; the expanded 15-case run uses
15.66% less time, retaining changed rounding and signed-zero observations within
unchanged limits. Both target contexts/arenas are unchanged, with 436 more ELF
bytes. These are bounded whole-fixture observations, not general power or
full-player timing claims. No fast-math, clock, buffer or allocator change is
enabled.
