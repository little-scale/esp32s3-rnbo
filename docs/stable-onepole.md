# Experimental stable Float32 onepole

`--stable-onepole` replaces the coefficient and recurrence in eligible
RNBO 1.4.4 graphs. The original three-form native implementation fixes all five
previously failing onepole accuracy programs, uses Float32 signal math and
reuses an existing state word. A checked fallback prevents finite inputs and
finite private state from producing a nonfinite filter result under the stated
floating-point contract.

This is an experimental, default-off numerical profile. Outputs intentionally
differ from the strict baseline. No target execution or CPU improvement is
claimed. The ordinary strict route and its five known onepole failures remain
unchanged; the earlier comparison-only option remains separate.

## Use and reproduce

The original closed admission remains available for these reviewed graphs:

- `tests/fixtures/objects/wave3/onepole-fixed-stereo.rnbopat`
- `tests/fixtures/objects/wave3/onepole-scalar-stereo.rnbopat`
- `tests/fixtures/objects/wave3/onepole-signal-cutoff.rnbopat`

For example:

```sh
node host/export/export.mjs tests/fixtures/objects/wave3/onepole-signal-cutoff.rnbopat \
  --out build/exports/stable-onepole
python3 host/compiler/prepare.py --export build/exports/stable-onepole \
  --out build/prepared/stable-onepole --class-name rnbos3patch --role fx \
  --stable-onepole
```

An authorised local RNBO 1.4.4 installation is required. Use fresh output
directories. Changed runtime/configuration and other optional adapters are
rejected.

Other Main/FX graphs use a separate regeneration gate. The compiler re-exports
the editable patch locally, applies the ordinary strict runtime fixes, and
requires byte identity for **all 42 prepared files**, including description,
configuration, runtime, patch and generator metadata. A JSON assertion of
successful generation is insufficient. The original exporter and installed
package are not modified. Manually edited C++ requires separate review.

This first broader route admits flat, single-voice graphs at 44,100 Hz and
256 frames, with stereo output and either no audio inputs (Main) or two (FX).
Its object-class policy permits `in~`, `out~`, `param`, `sig~`, `cycle~`,
`phasor~`, `noise~`, `onepole~`, `feedback~`, `loadbang`,
`message`, `number`, and builtin `+`, `-`, `*`, `/` operations with their signal
forms. This is a class policy, not a list of individual patch hashes. Admission
does not confer numerical qualification on the surrounding objects.

Each Hz filter must independently match a reviewed generated implementation,
private state/default/reset roles and a 256-frame caller. Only signal-data
forms with fixed, scalar or signal frequency are supported. Read-only sharing
of data and cutoff is permitted; writable-plane aliases are rejected. Scalar
data, linear onepole implementations, codebox/explicit expressions, nested
patchers, dependencies, MIDI, host services, polyphony and combinations with
other optional optimisations remain outside this route. A graph containing
an unreviewed filter form is rejected as a whole. Vector `feedback~` preserves
its generated vector scheduling; this does not add single-sample feedback.

Use a positional cutoff such as `onepole~ 1234.5`, or the exact saved
`rnbo_extra_attributes.freqInHz` key. The pinned parser lowercases text
`@freqInHz` to an unknown property and silently uses the default cutoff; this
route explicitly rejects that spelling. Custom parameter normalisation
expressions, parameter MIDI-controller attributes and explicit `@id` overrides
are also excluded; ordinary positional parameter names remain supported.

The installed authorised RNBO producer and compiler process are trusted. Fresh
generation plus the local implementation checks establishes this admission
boundary; it is not a sandbox for hostile C++, a modified generator package or
arbitrary Python callers. Unsupported graphs retain the ordinary strict route.

To reproduce the original 15 onepole accuracy programs through fresh exports,
actual preparation and the production native C ABI:

```sh
python3 host/compiler/qualify_wave3.py --onepole-only --stable-onepole \
  --out build/qualify-stable-onepole
```

The recorded corrected run passes and exits 0. Run the same explicit selection
without `--stable-onepole` to reproduce the strict baseline: it is runtime
healthy, retains five accuracy failures and exits 1 with a complete report.
Exit 2 means setup/integrity failed. Neither option is implicit: without
`--onepole-only`, the tool selects all 45 original programs; the profile flag
changes only the three onepole forms. Unrelated objects and failures remain
part of that wider run.

The selected 15 are a subset of the expanded evidence below, not 15 additional
independent programs. The portable tests also exercise the original helper
against arbitrary finite states and frequencies, without requiring RNBO.

## Broader graph validation

Ten additional graph programs exercise cascades, shared scalar and signal
controls, read-only data/cutoff sharing, saved fixed cutoffs, a Main source
observer, vector feedback, and an API parameter identifier that resembles the
filter's private state name. All ten corrected programs pass the unchanged
`3e-6` accuracy gate; the largest observed error is `2.979919794254826e-8`.
Eight strict-reference programs fail that same gate and remain recorded.

The actual public compiler route supplies the candidates. O3 and UBSan builds,
two fresh contexts each, pass 80 lifecycles with exact cross-build and
reconstruction captures, 232 event readbacks and 16,384 block readbacks. Main's
filter oracle uses its byte-preserved source observer; this does not qualify
the oscillator waveform independently. The full compiler suite passes 358
tests. These finite programs do not establish an accuracy bound for arbitrary
graphs or amplitudes.

Four additional ESP32-S3 compilations compare strict/corrected versions of a
six-filter bank and a Main oscillator/filter graph. Their corrected ELF files
are 412 and 472 bytes smaller; these file sizes are not CPU measurements.
The bank's fixed fractional cutoff still retains a Double comparison and
repeated coefficient updates. The coefficient and recurrence are Float32;
unchanged oscillator and clock work may also use Double. Nothing in this
cohort executes on the board or measures its live memory use.

The [graph admission evidence](../evidence/stable-onepole-graphs.json) publishes
the ten authored graphs, declared plans, results, source identities and archived
capture inventories. The complete ten-program capture study is an archived
audit; its generated RNBO implementations are not distributed. Reproduce the
public fresh-graph admission and wrapper-compilation tests separately with:

```sh
python3 -m unittest discover -s host/compiler -p test_onepole_graphs.py -v
```

These nine tests require the authorised local RNBO package for their generated
graph cases; they are separate from the ten audio programs above.

## What changed

The old generic `rnbo_exp(Double)` returns Float32 before the source subtracts
it from 1. Small coefficient cancellation survives the Double exponential.
Separately rounded feedforward/feedback coefficients and slow Float32 history
updates introduce further drift or plateaus. Fixing only one of those effects
did not pass every original gate.

The new coefficient uses `-expm1f(-k * hz)`, with an explicit rounded binary32
scale `k = 0x1.2acb24p-13f` (word `0x39156592`). Independent rational bounds on
π establish that this is the nearest binary32 value to `2π/44100`; it was chosen
mathematically before captures. One multiply replaces the explicit frequency
conversion divide. `expm1f` can still divide internally.

Frequencies at or below zero select the lower coefficient clamp; frequencies
at or above 100,000 Hz select the upper clamp. Only the intervening interval
evaluates the exponential, with an argument inside `[-15,0]`. The final clamp
retains Float32 bounds `0.00001f` and `0.99999f`. This keeps every finite frequency
in range without first overflowing its argument or taking a positive
exponential overflow path.

The sample update uses a Float32 correction for addition rounding:

```text
increment = a * (x - y) - correction
next      = y + increment
newDebt   = (next - y) - increment
```

The previous feedback-coefficient word now stores `correction`. Its constructor
and reset value remain zero; cache/store operations preserve it across vectors
and parameter changes. No state member is added. Equal layout is a memory-cost
observation, not permission to exchange raw live state with the original
profile; fresh construction is required.

## Finite recovery proof and execution contract

A difference can overflow even when both endpoints are finite. The first
compensated prototype faulted on actual C ABI inputs `-FLT_MAX`, then `+FLT_MAX`
at cutoff zero, while the strict baseline stayed finite. That counterexample
is retained, not discarded after adding a guard.

The implemented update checks for an overflowed difference. It also tests the
new correction **before storing either new state value**. With finite old
history, a nonfinite `next` necessarily produces a nonfinite debt; testing the
debt catches either case. Recovery recomputes a finite interpolation from the
old finite history and clears the correction.

For same-sign endpoints, recovery uses `y + a*(x-y)`. With
`u = 2^-24` and `a <= 1-168u`, a conservative exact rounding bound is
`(a*(1+u)^2 + u) < 1`: the increment cannot overshoot the exact endpoint
difference. Subnormal differences are handled separately as exact lattice
multiples. For opposite signs, recovery uses `a*x + (1-a)*y`; each product is
finite and their weakly opposite-sign sum cannot overflow. These facts establish
finite output/state by induction from finite initial state, even for an
arbitrary finite correction word. They do not establish an absolute error
bound for arbitrary input amplitudes.

The proof assumes IEEE binary32 including gradual underflow, nearest-even
rounding, no contraction, nontrapping execution, independent private state
words and exclusive callbacks with disjoint audio planes. Type/ABI assertions
check representations and revision; they do not establish the runtime rounding
mode, trap configuration or ownership. Guards can observe overflow/invalid
operations before recovery. Floating flags, enabled traps, signalling NaNs and
payload equivalence are explicitly excluded. This is not target execution
qualification.

## Evidence and limits

The fresh public 27-program pipeline passes the unchanged independent `3e-6`
absolute-error gate and exact observer-copy gates. O3/UBSan, reconstruction and
reviewed private/public captures agree, including Float32, PCM, raw traces,
statistics and mathematical results. The maximum observed ideal error is
`1.67425942e-7` over 14,352,384 paired channel words.

Six additional bounded-data frequency/control programs test huge finite
frequencies, subnormal/normal exponent strata, clamp/prebound neighbours and
legal scalar command bursts. They pass the same accuracy and observer gates.
A separate 27-program extreme-data replay checks finite module output and
resource health through the public objects; it deliberately has no PCM stage
or `3e-6` absolute accuracy claim at `FLT_MAX` amplitudes.

The standalone helper tests include over a million arbitrary finite-state
trials, over a million frequency trials and evolving sequences. Those are
sampled executions alongside the analytical finite proof, not exhaustive
execution of every state. Native host libc/libm and constructor/finalizer stubs
do not establish target library outputs or ELF lifecycle behaviour.

A coefficient-scale experiment changed rounding by at most `5.96046448e-8`
relative to the earlier divided-argument candidate in the declared corpus.
Its initial analysis wrongly demanded raw trace identity even though block
traces contain first/last audio words. That failed analysis and sources remain
archived. Reanalysis of the same captures excludes only those two audio-observer
fields from trace compatibility; complete audio/oracle gates, parameter
readbacks, order, positions and resource fields remain enforced. No native
rerun or tolerance relaxation was used to reclassify it.

All three fresh public candidate modules reproduce their complete reviewed
private ELF bytes; all three fresh default references reproduce the old strict
images. Candidate ELF sizes are 34,688 / 40,052 / 34,604 bytes for fixed / scalar /
signal forms. Actual Context sizes and all patch member offsets are unchanged:
12,768 / 12,784 / 12,736 bytes, with a selected 4,096-byte structural arena.
These are compiled layouts, not target high-water measurements or isolated
object costs.

In the original three compiled forms, linked signal math, coefficient work and
recovery are Float32. DSP update calls are only `expm1f`; its actual linked
closure is Float32, including the internal
division. The explicit caller division is removed. Whole-module clock/control
Double work remains, and original scheduling expressions are unchanged.
Boundary event/readback positions are checked; long-uptime clock accuracy is
not newly qualified by these tests.

The broader graph transform preserves the producer's fixed-frequency cache
predicate. For some fractional literals, comparing cached Float32 with the
original Double literal repeatedly refreshes the coefficient. The new
coefficient and recurrence still use Float32, but this predicate can retain
Double comparison work. Removing it needs a separate cache/reset proof and
measurement; no whole-graph Double-free or speed claim follows from admission.

Compensation, comparisons and recovery branches add sample work. Fixed or
steady scalar workloads may cost more, while frequently changing coefficients
avoid the old Double work. Static call counts, smaller files and Float32
instructions are not CPU measurements. Real target timing, allocation and
whole-instrument deadline checks remain open until RNBO hardware work resumes.

The [sealed evidence](../evidence/stable-onepole.json) keeps the strict baseline,
failed prototypes, public/private epochs, finite proof, captures, source review
and compiled identities separate. The status page remains partial/native-only
with an experimental option and no performance percentage.
