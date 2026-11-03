# Experimental stable Float32 onepole

`--stable-onepole` replaces the coefficient and recurrence in three reviewed
RNBO 1.4.4 FX graphs. The selected native implementation fixes all five
previously failing onepole accuracy programs, uses Float32 signal math and
reuses an existing state word. A checked fallback prevents finite inputs and
finite private state from producing a nonfinite filter result under the stated
floating-point contract.

This is an experimental, default-off numerical profile. Outputs intentionally
differ from the strict baseline. No target execution or CPU improvement is
claimed. The ordinary strict route and its five known onepole failures remain
unchanged; the earlier comparison-only option remains separate.

## Use and reproduce

The compiler option currently admits exactly these graphs:

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
directories. Other graphs, changed runtime/configuration or other optional
adapters are rejected. This closed admission is not generic onepole-family,
`onepole_lin~`, codebox, arbitrary composition or reset-mode qualification.

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

Linked signal math, coefficient work and recovery are Float32. DSP update calls
are only `expm1f`; its actual linked closure is Float32, including the internal
division. The explicit caller division is removed. Whole-module clock/control
Double work remains, and original scheduling expressions are unchanged.
Boundary event/readback positions are checked; long-uptime clock accuracy is
not newly qualified by these tests.

Compensation, comparisons and recovery branches add sample work. Fixed or
steady scalar workloads may cost more, while frequently changing coefficients
avoid the old Double work. Static call counts, smaller files and Float32
instructions are not CPU measurements. Real target timing, allocation and
whole-instrument deadline checks remain open until RNBO hardware work resumes.

The [sealed evidence](../evidence/stable-onepole.json) keeps the strict baseline,
failed prototypes, public/private epochs, finite proof, captures, source review
and compiled identities separate. The status page remains partial/native-only
with an experimental option and no performance percentage.
