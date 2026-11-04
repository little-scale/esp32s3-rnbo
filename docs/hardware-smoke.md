# Fast hardware functionality checks

Coverage now starts with a short device check. Each object gets a small input
vector with known expected outputs, a few warmup calls, and 16 timed callbacks.
Multiple modules share one firmware upload. An output mismatch is recorded and
the batch continues; a loader, process or memory fault stops the run.

These results mean **checked on hardware in the listed scenario**, not complete
mode/domain qualification. Deeper investigation is reserved for failures and
CPU-review flags. Existing, more extensive qualification records remain separate.

The test firmware stays installed between batches. It is quiet after completion
and does not run I²S audio, a display or networking. The drone can be reinstalled
when needed; it is not automatically restored after each batch.

## RNBO parameter-driven event batch

**All 35 exact event spellings pass on XIAO**, with 735 ordered parameter
updates/readbacks and **358,400 output checks**. No parser/compiler failures,
processing-time CPU flags or memory/allocation failures occur. These are
non-tilde event objects; signal and Gen results do not transfer to them.

| Exact event form | Result | Callback median µs | Total 21 event calls µs | Event peak µs |
| --- | --- | ---: | ---: | ---: |
| `abs` | Pass | 76.0 | 157 | 34 |
| `neg` | Pass | 75.0 | 161 | 35 |
| `floor` | Pass | 76.0 | 160 | 35 |
| `ceil` | Pass | 76.0 | 157 | 34 |
| `trunc` | Pass | 76.0 | 156 | 35 |
| `round` | Pass | 76.0 | 203 | 44 |
| `fract` | Pass | 76.0 | 162 | 35 |
| `sign` | Pass | 75.0 | 159 | 35 |
| `boolnum` | Pass | 76.0 | 167 | 34 |
| `not` | Pass | 76.0 | 164 | 34 |
| `!` | Pass | 76.0 | 164 | 34 |
| `add` | Pass | 76.0 | 171 | 33 |
| `+` | Pass | 76.0 | 173 | 33 |
| `sub` | Pass | 76.0 | 168 | 33 |
| `-` | Pass | 76.0 | 169 | 33 |
| `mul` | Pass | 76.0 | 171 | 37 |
| `*` | Pass | 76.0 | 169 | 33 |
| `div` | Pass | 76.0 | 166 | 35 |
| `/` | Pass | 76.0 | 161 | 35 |
| `mod` | Pass | 75.5 | 156 | 31 |
| `%` | Pass | 76.0 | 157 | 31 |
| `minimum` | Pass | 75.0 | 165 | 34 |
| `min` | Pass | 76.0 | 161 | 34 |
| `maximum` | Pass | 75.5 | 164 | 34 |
| `max` | Pass | 75.0 | 162 | 35 |
| `eq` | Pass | 75.5 | 157 | 35 |
| `==` | Pass | 75.0 | 157 | 35 |
| `gt` | Pass | 76.0 | 156 | 34 |
| `>` | Pass | 75.5 | 156 | 34 |
| `lt` | Pass | 76.0 | 156 | 34 |
| `<` | Pass | 76.0 | 158 | 34 |
| `and` | Pass | 76.0 | 162 | 34 |
| `&&` | Pass | 75.5 | 157 | 34 |
| `or` | Pass | 76.0 | 154 | 36 |
| `xor` | Pass | 75.0 | 159 | 36 |

Each original patch has one ordinary numeric `drive` parameter, initially 0,
with range [-8,8], exponent 1 and no steps. It drives the event object's hot
inlet; its value output drives `sig~` and the left output. Binary operands are
literal 2, except `or 0` so both Boolean outcomes occur. `round 2` uses base 2.
Minimum/maximum observe value outlet 0 only; their index outlets are untested.
The independent right input goes directly to the right output.

The 21 authored updates include signed/fractional values, range endpoints,
unchanged resends, holds, and multiple ordered updates before one callback.
Per-model sequences make last-write ordering observable. Stable parameter IDs
are resolved against each loaded runtime schema; actual/normalized readbacks
match the independent linear mapping. All twenty callbacks have their own
expected blocks, including four checked manual warmups and sixteen timed calls.
There is no automatic zero-input preparation processing.

Every nonzero numeric left value matches exactly. The 2,816 left zero-sign
word differences are retained as allowed numeric-zero diagnostics. The right
observer is **raw-bit exact** over all 179,200 values, including both zero signs,
subnormal values and finite extremes; strict zero-sign failures are counted
separately and remain zero. Parameter readbacks allow only numeric ±0
equivalence while preserving their raw words in the result.

Processing medians range from 75 to 76 µs per stereo 256-frame callback. Event
API calls are measured separately, before processing and without readback/logging
inside their timer: 154–203 µs total per 21 updates, individual observations 5–44 µs.
These event times include the SDK setter and downstream routing, not an isolated
arithmetic instruction. The callback cost mostly represents held-signal/pilot
processing; it is not an event-operator speed comparison. No optimisation gain
or peak-latency guarantee is claimed.

The existing API dispatches at `RNBO::TimeNow` between complete 256-frame calls.
This run establishes the supplied **block-boundary** changes and ordering,
not within-block timestamps, nonlinear/stepped parameter normalization, arbitrary
cold operands, multiple-control interactions or counter/reset semantics.
The fast compiler now admits 0–32 ordinary numeric parameters; this hardware
batch exercises one control per fixture, not the full count limit. No production
SDK or event ABI was changed.

To retain all checks in one upload, exact repeated 512-word reference blocks
are shared: 700 logical callback references use 36 stored blocks. Each case
keeps its full stream hash and ordered block indices. An initial unflashed
build's expanded 8.5MiB report exceeded the existing 8 MiB preflight limit; the
uploader stopped before writing. The revised report is 1,327,267 bytes, with
the generated case data byte-identical except for the plan-identity string.
The size guard and numerical/word checks were not relaxed. Both build versions
remain saved locally; only the compact-report firmware was uploaded.

See [the complete event/readback result](../evidence/xiao-smoke-rnbo-events.json)
and [the original patches and independent reference](../tests/fixtures/smoke/rnbo-events/README.md).

## RNBO functions and conversions batch

**35 forms execute on XIAO: 34 pass their declared checks, and `fasttan~`
exceeds the chosen ideal-reference limit.** All export and compile; eleven
cases trigger CPU review. Memory/allocation gates pass and all images finalise.

| Exact form | Short result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `sin~` | Pass | 281.0 | 286 | No flag |
| `cos~` | Pass | 285.5 | 290 | No flag |
| `tan~` | Pass | 419.5 | 424 | No flag |
| `tanh~` | Pass | 645.0 | 646 | Queued |
| `asin~` | Pass | 532.0 | 533 | No flag |
| `acos~` | Pass | 485.0 | 487 | No flag |
| `atan~` | Pass | 344.0 | 347 | No flag |
| `atan2~` | Pass | 681.0 | 682 | Queued |
| `sinh~` | Pass | 694.0 | 695 | Queued |
| `cosh~` | Pass | 643.5 | 646 | Queued |
| `asinh~` | Pass | 756.5 | 757 | Queued |
| `acosh~` | Pass | 828.0 | 828 | Queued |
| `atanh~` | Pass | 772.0 | 772 | Queued |
| `hypot~` | Pass | 224.0 | 229 | No flag |
| `degrees~` | Pass | 50.0 | 50 | No flag |
| `radians~` | Pass | 50.0 | 54 | No flag |
| `radtodeg~` | Pass | 37.0 | 37 | No flag |
| `RADTODEG~` | Pass | 37.0 | 42 | No flag |
| `degtorad~` | Pass | 37.0 | 41 | No flag |
| `DEGTORAD~` | Pass | 37.0 | 42 | No flag |
| `mtof~` | Pass | 2392.0 | 2397 | Queued |
| `ftom~` | Pass | 667.5 | 668 | Queued |
| `atodb~` | Pass | 4875.0 | 4876 | Queued |
| `dbtoa~` | Pass | 14659.0 | 14660 | Queued |
| `mstosamps~` | Pass | 349.0 | 351 | No flag |
| `sampstoms~` | Pass | 154.0 | 159 | No flag |
| `hztoms~` | Pass | 157.0 | 157 | No flag |
| `mstohz~` | Pass | 157.0 | 161 | No flag |
| `hztosamps~` | Pass | 142.0 | 147 | No flag |
| `sampstohz~` | Pass | 142.0 | 146 | No flag |
| `fastsin~` | Pass | 147.0 | 148 | No flag |
| `fastcos~` | Pass | 158.0 | 161 | No flag |
| `fasttan~` | Exceeds declared test limit | 306.0 | 311 | No flag |
| `cosT8~` | Pass | 492.0 | 495 | No flag |
| `cosT8safe~` | Pass | 429.0 | 434 | No flag |

Each fixture checks 10,240 output values over twenty callbacks, totalling
**358,400 output checks**. Sixteen callbacks supply timing. Binary `atan2~` and
`hypot~` reverse operands across the two lanes. The four `radtodeg~`/`degtorad~`
spellings are zero-input constants (180/π and π/180), with declared but unused
FX inputs; they are not converters. Constants and integer-rounded default
`ftom~` outputs compare exactly. The aliases have separate source/device records.

Limits and domains were chosen before execution. Ordinary mathematical cases
use `2e-6` absolute error. MIDI conversion includes practical notes 36–84,
quarter tones and A4=440 Hz, with a `5e-4` Hz limit for `mtof~`. Time/frequency
conversions include ordinary block/sample counts, milliseconds and musical
frequencies, using `5e-4` in the output units. Decibels use unity=0 dB.
The fast sine/cosine/tangent cases use a declared `1e-3` ideal-math threshold;
first-party prose does not promise that numerical accuracy.

`fasttan~` returns finite values, but its maximum deviation from `tan(x)` on
these inputs is about 0.01409, above the selected 0.001 threshold. This is a
retained approximation-quality result, not a claim that the object universally
malfunctions or violates a documented accuracy guarantee. Fast sine/cosine
stay within their same predeclared threshold. Taylor-cosine checks use the
listed small-angle and small-after-wrap domains, not all possible angles.

The default converter resources are preserved. The fast compiler has an
explicit one-MiB arena tier, changing only the wrapper's advertised maximum;
its original four-KiB cache control still reproduces the entire reference ELF.
Each fixture reserves 1,048,576 arena bytes for this run, which does not mean
it consumes that amount. `mtof~` peaks at **262,416 bytes** (one shared 65,536
Float32 lookup payload of 262,144 bytes, plus overhead); `ftom~` peaks at
**160 bytes**. The other 33 cases use zero arena bytes in this scenario.
These measurements do not establish minimum viable arena sizes for all modes.
All resource initialization precedes audio processing, with no table omission,
precision-profile change or DSP optimisation. Zero automatic audio warm-up
blocks are followed by four checked valid-domain warmups and sixteen timed calls.

Eleven costs are retained in [the CPU-review queue](cpu-review-backlog.md).
The `dbtoa~` two-instance stereo fixture takes 14.659 ms median, about 2.53 times
the 5.805 ms block period. `atodb~` takes 4.875 ms and `mtof~` 2.392 ms. These
are whole-fixture costs, not isolated node timings or optimisation gains.
Existing AMOLED optimisation percentages remain separate from these XIAO
baseline observations.

See [the compact results](../evidence/xiao-smoke-rnbo-functions.json) and
[the original sources/reference](../tests/fixtures/smoke/rnbo-functions/README.md).

## Gen stateful and per-sample batch

**All 12 programs pass on XIAO**, covering nine exact GenExpr spellings:
`delta`, `change`, `latch`, `dcblock`, `sah`, `slide`, `accum`, `plusequals` and
`counter`. Every program exports, compiles and executes; no CPU-review flags
trigger. Module/global memory checks pass and all twelve images finalise.

| Program / left-lane form | Result | Median µs | Peak µs | Maximum error |
| --- | --- | ---: | ---: | ---: |
| `delta(in1)` | Pass | 50.0 | 55 | 0 |
| `change(in1)` | Pass | 67.0 | 68 | 0 |
| `latch(in1, in2)` | Pass | 56.0 | 56 | 0 |
| `dcblock(in1)` | Pass | 551.0 | 552 | 1.55e-06 |
| `sah(in1, in2)` | Pass | 70.0 | 75 | 0 |
| `sah(in1, in2, 0.5)` | Pass | 72.0 | 77 | 0 |
| `sah(in1, in2, in1)` | Pass | 67.0 | 71 | 0 |
| `slide(in1, 2, 4)` | Pass | 374.0 | 378 | 5.96e-08 |
| `slide(in1, 4, 2)` | Pass | 373.0 | 378 | 5.96e-08 |
| `accum(in1, 0)` | Pass | 52.0 | 56 | 0 |
| `plusequals(in1, 0)` | Pass | 52.0 | 57 | 0 |
| `counter(1, 0, 7); right maximum 5` | Pass | 63.0 | 67 | 0 |

Each program processes **5,120 continuous frames per channel**: four checked
manual warm-up callbacks followed by sixteen checked timed callbacks, with no
state reset between them. This is **122,880 output checks** across the batch.
The repeated input vector has an independently calculated output stream for
all twenty callbacks; repeating only the first expected block is insufficient.
Each stream is bound by its own little-endian word hash, and mismatch records
identify both the callback and in-block sample position.

The input design distinguishes a reset at the 256-frame boundary from continuous
state for delta/change, latch/sample-hold, accumulators and counters. Late held
values differ from the next block's first input; accumulator sums have nonzero
block totals; counter periods 7 and 5 do not divide 256. The counter matches the
predeclared increment-before-output sequence in this count-output-only test.
`accum` and alias `plusequals` have separate original programs and device records.

Nine programs use exact numerical comparisons and have **zero raw-word
differences**. DCblock and both slide modes use a predeclared absolute `2e-6`
limit against ideal Float64 mathematical state, rounded to Float32 outputs.
Their raw differences remain visible: 10,197 words for dcblock and 4,467/5,737
for slide. Maximum errors are about 1.55e-6 and 5.96e-8 respectively; these are
bounded-accuracy passes rather than exact-bit claims. The reference's Float64
state is an independent mathematical model, not a change to target DSP storage.

The run has zero automatic zero-input preparation blocks; its fresh-state epoch
and all twenty expected blocks are recorded before execution. Median complete
stereo callbacks range from 50 to 551 µs, with peak 552 µs. DCblock is the
highest cost here at about 9.49% of the 5.805 ms block period, below the existing
CPU-review threshold. No optimisation or percentage improvement is claimed.

These results validate the listed per-sample state updates inside fixed
256-frame callbacks, including the supplied cross-block histories. They do not
exercise one-frame host calls, sample-offset events, nonzero initial attributes,
reset modes, counter carry outputs, arbitrary smoothing rates or all stateful
Gen objects. Those remain part of the full goal.

See [the compact stateful result](../evidence/xiao-smoke-gen-stateful.json) and
[the original programs and reference](../tests/fixtures/smoke/gen-stateful/README.md).

## Gen mathematical batch

There are **34 separately authored GenExpr forms: 27 pass on XIAO, four fail
C++ compilation, and three are rejected by the frontend parser**. Thirteen
executed forms trigger CPU review. The run completes all module/global memory
checks and leaves the quiet test firmware installed.

| Exact form | Short hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `div(in1, in2)` | Pass | 159.0 | 163 | No flag |
| `in1 / in2` | Pass | 159.0 | 159 | No flag |
| `in1 % in2` | Pass | 275.0 | 279 | No flag |
| `sqrt(in1)` | Pass | 199.0 | 203 | No flag |
| `exp(in1)` | Pass | 486.0 | 490 | No flag |
| `exp2(in1)` | Pass | 7499.0 | 7503 | Queued |
| `log(in1)` | Pass | 3684.0 | 3685 | Queued |
| `ln(in1)` | Pass | 3684.0 | 3685 | Queued |
| `log2(in1)` | Pass | 4732.0 | 4733 | Queued |
| `log10(in1)` | Pass | 4297.0 | 4302 | Queued |
| `pow(in1, in2)` | Pass | 1135.0 | 1135 | Queued |
| `sin(in1)` | Pass | 284.0 | 289 | No flag |
| `cos(in1)` | Pass | 289.0 | 294 | No flag |
| `tan(in1)` | Pass | 423.0 | 428 | No flag |
| `tanh(in1)` | Pass | 649.0 | 649 | Queued |
| `asin(in1)` | Pass | 536.0 | 537 | No flag |
| `acos(in1)` | Pass | 491.0 | 492 | No flag |
| `atan(in1)` | Pass | 345.0 | 349 | No flag |
| `atan2(in1, in2)` | Pass | 673.5 | 674 | Queued |
| `sinh(in1)` | Pass | 697.0 | 698 | Queued |
| `cosh(in1)` | Pass | 649.0 | 650 | Queued |
| `asinh(in1)` | Pass | 760.0 | 760 | Queued |
| `acosh(in1)` | Pass | 831.0 | 831 | Queued |
| `atanh(in1)` | Pass | 775.0 | 776 | Queued |
| `hypot(in1, in2)` | Pass | 205.0 | 210 | No flag |
| `degrees(in1)` | Pass | 45.0 | 45 | No flag |
| `radians(in1)` | Pass | 45.0 | 49 | No flag |

The seven unexecuted forms stay in the source catalog and failure records:

| Form | Rejected at | Observed reason |
| --- | --- | --- |
| `in1 !/ in2` | GenExpr parser | Unexpected `!` token |
| `in1 !% in2` | GenExpr parser | Unexpected `!` token |
| `in1 !- in2` | GenExpr parser | Unexpected `!` token |
| `rdiv(in1, in2)` | Target C++ compiler | Ambiguous emitted `div` call |
| `mod(in1, in2)` | Target C++ compiler | Undeclared emitted `safemod` call |
| `rmod(in1, in2)` | Target C++ compiler | Undeclared emitted `safemod` call |
| `rsub(in1, in2)` | Target C++ compiler | Undeclared emitted `sub` call |

Registry membership alone does not prove parser/compiler support. These are
retained support gaps, without fallback expressions or DSP fixes. In particular,
the successful `%` expression does not qualify the rejected `mod()` call.
RNBO signal-object results remain separate from these GenExpr outcomes.

The 27 loaded forms check **276,480 output values**. `div()`, `/` and `%` use
exact numerical comparison; the other 24 forms use the predeclared absolute
limit `2e-6` against independently computed, once-binary32-rounded references.
Raw differing words remain recorded even when within that limit. The largest
observed error is about 4.77e-7 for `degrees`; these approximate passes are not
claims of exact-bit equality. Both channels and reversed binary operand orders
are exercised using per-model bounded finite input vectors.

This batch uses zero automatic zero-input preparation blocks and four checked
manual warmups with each case's valid-domain vector, then sixteen timed calls.
That configuration is recorded in both the plan and device log; it avoids
feeding a zero pre-roll to functions such as `acosh`, whose real domain starts
at 1. Default zero-preroll behaviour is not qualified by this batch. All calls
remain fixed at 256 frames, 44.1 kHz; single-sample and stateful-feedback coverage
remains limited to the separately documented History tests.

`exp2` takes 7.499 ms median in this two-instance stereo fixture, exceeding the
5.805 ms block period. The thirteen [CPU-review entries](cpu-review-backlog.md)
are retained for future optimisation. Timings are whole-graph absolute costs,
with no optimisation gain or real-time audio headroom claim.

See [the compact device/stage results](../evidence/xiao-smoke-gen-math.json) and
[the original programs and independent reference](../tests/fixtures/smoke/gen-math/README.md).

## RNBO numeric and maths batch

One upload executes **33 exact RNBO signal forms: 30 pass, three have output
mismatches, and eight trigger CPU review**. All compile. The final run completes
all module and global memory checks, and leaves the quiet firmware installed.

| Exact form | Short hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `div~` | Pass | 164.0 | 168 | No flag |
| `/~` | Pass | 164.0 | 168 | No flag |
| `rdiv~` | Pass | 164.0 | 169 | No flag |
| `!/~` | Pass | 164.0 | 169 | No flag |
| `mod~` | Pass | 288.0 | 293 | No flag |
| `%~` | Pass | 288.5 | 293 | No flag |
| `rmod~` | Pass | 288.0 | 293 | No flag |
| `!%~` | Pass | 288.0 | 293 | No flag |
| `floor~` | Pass | 125.0 | 129 | No flag |
| `ceil~` | Pass | 123.0 | 128 | No flag |
| `trunc~` | Pass | 52.0 | 57 | No flag |
| `round~` | Output mismatch | 172.0 | 177 | No flag |
| `fract~` | Pass | 110.0 | 115 | No flag |
| `sign~` | Pass | 56.0 | 61 | No flag |
| `isnan~` | Pass | 52.0 | 57 | No flag |
| `fixnan~` | Pass | 46.0 | 50 | No flag |
| `isdenorm~` | Output mismatch | 41.0 | 46 | No flag |
| `fixdenorm~` | Output mismatch | 41.0 | 46 | No flag |
| `intnum~` | Pass | 52.0 | 56 | No flag |
| `int~` | Pass | 52.0 | 56 | No flag |
| `i~` | Pass | 52.0 | 57 | No flag |
| `sqrt~` | Pass (approximate) | 197.0 | 201 | No flag |
| `cbrt~` | Pass (approximate) | 430.0 | 435 | No flag |
| `exp~` | Pass (approximate) | 483.0 | 487 | No flag |
| `exp2~` | Pass (approximate) | 7494.0 | 7498 | Queued |
| `expm1~` | Pass (approximate) | 418.0 | 423 | No flag |
| `log~` | Pass (approximate) | 3681.0 | 3682 | Queued |
| `ln~` | Pass (approximate) | 3680.5 | 3682 | Queued |
| `log2~` | Pass (approximate) | 4729.0 | 4730 | Queued |
| `log2f~` | Pass (approximate) | 4729.0 | 4730 | Queued |
| `log10~` | Pass (approximate) | 4294.0 | 4299 | Queued |
| `log1p~` | Pass (approximate) | 3979.0 | 3979 | Queued |
| `pow~` | Pass (approximate) | 1141.0 | 1141 | Queued |

Each form checks 10,240 output values over twenty callbacks, for **337,920
output checks**. Sixteen callbacks provide the timings above. Cases have their
own predeclared input vectors: division/remainder use nonzero operands in both
lanes; logarithms, roots, exponentials and powers use bounded valid domains.
Basic functions use a 77-word finite edge set, including subnormal signs,
half-way neighbours and safe signed-32-bit conversion endpoints.

Basic functions use exact numerical comparison with separate zero-sign
counts. Roots/exponentials/logarithms/powers use an absolute error limit of
`2e-6` (stored as binary32) against independently computed, once-rounded
mathematical outputs. Raw differences remain visible: `expm1~` has 640 and
`pow~` has 400 differing output words, all within that predeclared limit; their
largest errors are about 1.19e-7 and 2.38e-7. This is not an exact-bit pass for
those two functions. No comparison limit was changed after device execution.

Retained discrepancies:

- `round~` outputs 1 for input `0x3effffff` (just below 0.5), where the declared
  nearest-integer, ties-away reference expects 0. Its short object prose does
  not define every tie rule; this witness is below the tie itself.
- `isdenorm~` returns a normal input value such as 4,194,304 instead of predicate 0.
- `fixdenorm~` retains the smallest subnormal instead of replacing it with zero.

The `fract~` pass uses the explicitly selected signed-fraction convention.
`isnan~` and `fixnan~` use finite inputs only; NaN/infinity handling is untested.
The denormal discrepancies are consistent with the currently disabled denormal
handling already seen in Gen; no runtime or DSP adapter was changed here.

The eight CPU flags are retained in [the review queue](cpu-review-backlog.md).
The `exp2~` two-instance stereo fixture takes 7.494 ms median, exceeding the
5.805 ms block period at 44.1 kHz. These absolute graph costs include the wrapper
and two operator instances; they are not isolated object costs, optimisation
gains or proof of audio headroom. Coverage continues before optimisation.

The first attempt reached all 33 case records but failed its final global
internal-memory check: decimal error formatting retained 104 bytes between
case records, while each module's own memory baseline recovered. That attempt,
its exact source and artifacts remain saved locally. Logging error/tolerance
as raw IEEE words removes that formatter allocation; the repeated run uses
the same modules, input vectors and comparison limits and passes all memory
gates. The gates were not relaxed.

See [the compact result](../evidence/xiao-smoke-rnbo-numeric.json) and
[the original patches and independent reference](../tests/fixtures/smoke/rnbo-numeric/README.md).

## RNBO arithmetic and logic batch

A single upload checks **36 exact RNBO signal spellings: all 36 pass**, with no
output mismatches, compilation failures or CPU-review flags. Aliases have their
own authored patches and device records; status does not transfer by alias.

| Exact form | Basic hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `add~` | Pass | 54.0 | 59 | No flag |
| `+~` | Pass | 54.0 | 59 | No flag |
| `mul~` | Pass | 54.0 | 55 | No flag |
| `*~` | Pass | 54.0 | 55 | No flag |
| `times~` | Pass | 54.0 | 59 | No flag |
| `rsub~` | Pass | 54.0 | 58 | No flag |
| `!-~` | Pass | 54.0 | 55 | No flag |
| `rminus~` | Pass | 54.0 | 55 | No flag |
| `absdiff~` | Pass | 89.5 | 93 | No flag |
| `neg~` | Pass | 43.0 | 48 | No flag |
| `fabs~` | Pass | 67.0 | 67 | No flag |
| `pass~` | Pass | 41.0 | 42 | No flag |
| `neq~` | Pass | 54.0 | 55 | No flag |
| `!=~` | Pass | 54.0 | 55 | No flag |
| `notequals~` | Pass | 54.0 | 59 | No flag |
| `gt~` | Pass | 54.0 | 59 | No flag |
| `>~` | Pass | 54.0 | 59 | No flag |
| `greaterthan~` | Pass | 54.0 | 59 | No flag |
| `gte~` | Pass | 54.0 | 55 | No flag |
| `>=~` | Pass | 54.0 | 59 | No flag |
| `greaterthaneq~` | Pass | 54.0 | 59 | No flag |
| `lte~` | Pass | 54.0 | 59 | No flag |
| `<=~` | Pass | 54.0 | 59 | No flag |
| `lessthaneq~` | Pass | 54.0 | 55 | No flag |
| `and~` | Pass | 66.0 | 70 | No flag |
| `&&~` | Pass | 66.0 | 70 | No flag |
| `logand~` | Pass | 66.0 | 66 | No flag |
| `or~` | Pass | 58.0 | 62 | No flag |
| `\|\|~` | Pass | 58.0 | 62 | No flag |
| `xor~` | Pass | 67.0 | 71 | No flag |
| `^^~` | Pass | 67.0 | 71 | No flag |
| `not~` | Pass | 52.0 | 53 | No flag |
| `!~` | Pass | 52.0 | 56 | No flag |
| `boolnum~` | Pass | 52.0 | 53 | No flag |
| `bool~` | Pass | 52.0 | 57 | No flag |
| `b~` | Pass | 52.0 | 52 | No flag |

Each graph has two operator instances, with reversed inputs for binary objects
and independent lanes for unary objects. The common vector covers all 256
ordered pairs of sixteen small binary fractions/integers in [-4,4], including
both zero signs. Twenty callbacks compare 10,240 output words per module:
**368,640 output checks** in this batch. Numeric-zero sign differences are
diagnostic, so `pass~` is a short numerical check rather than a separate
bit-exact copy qualification.

The 16 timed callbacks per graph have median costs from 41 to 89.5 µs, with a
largest observed peak of 93 µs. These are complete stereo graph costs for
256 frames at 44.1 kHz, not per-instance timings or optimisation gains.
All 36 images finalise successfully; the test firmware stays installed and
quiet after completion. Other modes, message-rate forms and domains remain
untested by this batch.

See [the compact device result](../evidence/xiao-smoke-rnbo-stateless.json) and
[the original test patches and reference](../tests/fixtures/smoke/rnbo-stateless/README.md).

## First numeric batch

One upload executes 15 original GenExpr forms: **10 pass and 5 have output
mismatches**. A sixteenth form, `f()`, fails compilation and is not executed.
These are 16 authored scenarios, including three variants of `round` and a
unary-minus form; they are not 16 additional unique inventory names.

| Exact form | Basic hardware result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `floor(in1)` | Pass | 129.0 | 133 | No flag |
| `ceil(in1)` | Pass | 127.0 | 132 | No flag |
| `trunc(in1)` | Pass | 48.0 | 52 | No flag |
| `round(in1)` | Output mismatch | 172.0 | 177 | No flag |
| `round(in1, 1)` | Output mismatch | 172.0 | 176 | No flag |
| `round(in1, 0.5)` | Output mismatch | 184.0 | 189 | No flag |
| `fract(in1)` | Pass (signed-fraction convention) | 114.0 | 119 | No flag |
| `neg(in1)` | Pass | 44.5 | 45 | No flag |
| `-in1` | Pass | 44.0 | 49 | No flag |
| `absdiff(in1, in2)` | Pass | 47.0 | 47 | No flag |
| `int(in1)` | Pass | 48.0 | 52 | No flag |
| `i(in1)` | Pass | 48.0 | 52 | No flag |
| `float(in1)` | Pass | 42.0 | 47 | No flag |
| `f(in1)` | Compile failure; not executed | — | — | — |
| `isdenorm(in1)` | Output mismatch | 42.0 | 43 | No flag |
| `fixdenorm(in1)` | Output mismatch | 42.0 | 47 | No flag |

Times are measured complete stereo callbacks, 256 frames at 44.1 kHz. They
are absolute costs in this short harness, not optimisation percentages or
isolated instruction costs. The batch uses a 75-word binary32 edge set repeated
across the input vector: both zero signs, subnormals, half-way neighbours,
large integer boundaries and the common safe Int32 endpoints. All 20 checked
calls per module use that same vector; zero-sign differences are recorded
separately and do not fail a numerical-zero check. There is no PCM stage.

Specific findings:

- Default/unit `round` returns 1 for `0x3effffff` (just below 0.5), where the
  half-away-from-zero reference expects 0. The half-unit variant similarly
  returns 0.5 for `0x3e7fffff` (just below 0.25), where 0 is expected.
- `isdenorm` returns an input normal value unchanged instead of predicate 0.
- `fixdenorm` retains the smallest subnormal instead of replacing it with zero.
- `fract` passes the explicitly selected signed-fraction convention. This is
  an observed convention; the short reference wording does not establish every
  negative-input policy.
- Registered alias `f()` reaches export/preparation but fails target C++
  compilation as an undeclared function. Canonical `float()` passes.

The numerical failures are retained for later fixes; no DSP optimisation was
made in this batch. All 15 loaded images are finalised. An initial harness
attempt stopped at its final heap baseline because hardware SHA initialisation
had occurred after that baseline. That attempt remains saved locally; the
corrected harness warms SHA before measurement and the new run completes.

See [the compact result data](../evidence/xiao-smoke-gen-numeric.json) and
[the CPU-review queue](cpu-review-backlog.md).

## Repeatable fast path

`tools/build_smoke_modules.py` reuses a verified existing module-build cache.
It recompiles only the export-dependent wrapper, replaces that object in a
private archive copy, and links each module. The original cache is unchanged.
The first batch builds 15 modules in 13.2 seconds, with one compiler rejection;
this is compiler wall time, not DSP performance.
Rebuilding the combined firmware with the SDK cache takes 7.7 seconds in the
measured check, with 19 build steps and the earlier tested artifacts unchanged.

```sh
python3 tools/build_smoke_modules.py \
  --prepared-root build/prepared/smoke-batch \
  --base-build build/hardware/gen-logic-target-inputs-v1/modules/neq-call \
  --out build/smoke-modules/batch-01

python3 tools/build_hardware_smoke.py \
  --catalog tests/fixtures/smoke/rnbo-stateless/catalog.json \
  --modules-report build/smoke-modules/batch-01/batch-report.json \
  --build-dir build/smoke/batch-01 \
  --cache-build-dir build/hardware-smoke-cache-xiao
```

Supply normal prepared exports matching the selected catalog. The Gen numeric, mathematical and stateful catalogs, plus RNBO stateless,
numeric, function/conversion and event catalogs, have separate independent references. Numeric cases carry their own input-vector hashes and
predeclared tolerances; older catalogs keep the original exact gate.
The initial fast
builder supports strict, self-contained two-input/two-output FX modules with zero to 32 ordinary numeric parameters.
The boundary-event reference route currently uses linear, unstepped controls;
other shapes and control modes remain pending. The
firmware SDK cache is reusable, while each completed batch's artifacts are
copied to its own directory. An unfinished build can use `--resume-incomplete`
only with the same plan; completed batch artifacts are not overwritten.
A module compilation failure returns a nonzero exit status, but its batch
report and successfully built modules remain available for the hardware run.

`tools/run_hardware_smoke.py` writes only the application partition after
checking the selected USB identity, original backup, partition table and build
artifacts. Its `DONE` marker means that the batch completed, including any
recorded output mismatches. It does not mean that every case passed.

`tools/collect_hardware_smoke.py` checks the receipt, module identities, case
totals and raw timing samples, then produces the compact result and CPU queue.
The new reference/tool tests and runner tests pass; the actual device run is
the functionality evidence.

Frontend export/preparation rejections can be retained as separate admission
failures in a merged module ledger. Their original source and failure-log hashes
are checked before planning; they are not counted as C++ compilation failures
or embedded as executable modules. The Gen mathematical result retains all
34 authored forms while embedding only the 27 successful modules. The original
fast module report stays unchanged alongside that merged ledger.

Stateful plans can supply a twenty-block expected stream, beginning with fresh
prepared state and carrying state through every warm-up and timed call. The
collector checks the complete stream shape/hash and callback-specific mismatch
witnesses. Reference data and module payloads share a two-MiB embedding budget;
this leaves room for the framework in the application partition.

`tools/build_smoke_modules.py --max-arena-bytes 1048576` builds the optional
one-MiB resource ceiling while the default remains four KiB. The original cache
control always compiles with its original four-KiB maximum and must match the
whole cached ELF; only candidate wrapper compilations select the larger macro.
The host then checks the actual module descriptor against the requested arena,
and the result records reserved capacity separately from observed high-water.

Boundary-event plans contain validated parameter contracts and ordered actual-value
actions. The worker resolves live IDs, verifies initial metadata/readbacks,
applies actions before the next full callback, and logs API timings separately.
Shared reference pools retain complete binary32 blocks and stream hashes; sharing
is exact storage reuse, without lowering sample count or comparison precision.
