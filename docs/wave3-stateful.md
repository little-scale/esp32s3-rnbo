# Stateful-object qualification: wave 3

Ten original graphs extend the native corpus to the exact spellings
`onepole~`, `slide~`, `delta~` and `sah~`. Fixed, scalar and signal-controlled
forms are separate records. All 45 programs run without ABI faults, invalid
samples or running allocations. **Six exceed their independent mathematical
accuracy limits** and remain recorded. All ten target modules compile with
zero imports after the private integer-helper fix described below.

These are computer-side output, allocation and linked-code observations. No
new ESP32-S3 execution, target CPU saving or complete object-family support is
claimed. In particular, `sah~` is tested as authored; its registry alias metadata
does not qualify canonical `sah`, other aliases or codebox forms.

## Reproduce the checks

With an authorised local RNBO 1.4.4 installation and a native C/C++ toolchain:

```sh
python3 host/compiler/qualify_wave3.py --out build/wave3-qualification
```

Choose a fresh output directory. Generated RNBO code and notices stay in
ignored build output. The [public catalogue](../tests/fixtures/objects/wave3/catalog.json)
defines the original graphs, fixed limits and ordered events; the
[runner instructions](../tests/fixtures/objects/wave3/native/README.md) describe
the source snapshots and captures.

The current strict baseline intentionally returns **exit status 1**, with a
complete `report.json` preserving the six numerical failures. Exit 0 means all
qualification gates passed; exit 2 means setup/integrity failed. Runtime health,
cross-build agreement and mathematical accuracy are distinct results.
Incomplete or truncated oracle results are marked unevaluated and cannot pass
accuracy checks.

The fresh public pipeline reproduces every private input vector, ordered binary
plan, Float32/PCM capture, parameter trace, statistic and mathematical result
case by case. A subsequent classifier-only fix prevents a vacuous accuracy
pass on missing results. Reclassifying the saved complete runs retains exactly
39 passes and six failures; it changes neither DSP output nor the execution
epoch. Both source versions and the first reports remain archived.

## Mathematical and mode contracts

| Exact spelling | Tested forms | Independent reference and boundaries |
| --- | --- | --- |
| `onepole~` | Fixed 1,000 Hz stereo; scalar cutoff; signal cutoff plus input observer | Zero-history single-pole exponential with `a=clip(1-exp(-2πf/Fs),1e-5,.99999)`. Closed-form constant spans and weighted convolution use Float64 mathematical history, preserving coefficient-clamp and low-frequency observations. |
| `slide~` | Fixed 8/32 stereo; scalar rise/fall; mixed scalar/signal controls | Exponential approach with `1/max(1,abs(rate))`; direction is chosen against the previous **output**, not previous input. Signed, fractional, zero/unit and large rates, interruptions and preserved history are checked. |
| `delta~` | Stereo signal inputs | Current input minus previous input, initial history zero, including the 255→256 vector boundary. |
| `sah~` | Fixed, scalar and signal threshold | Select the latest source sample satisfying `previousTrigger <= currentThreshold < currentTrigger`. Sustained high/equality holds; a threshold-only change with unchanged trigger cannot cross. Held values and observers must copy the exact source words. |

The pinned primary documentation has misleading prose for slide and sample/hold.
The reviewed formula policy and actual generated callers resolve those
ambiguities. The sample/hold model compares both trigger samples against the
**current** threshold; it does not cache a boolean computed with the previous
threshold. Its zero initial history is separate from the inlet's default-value
metadata. These source-derived details are documented policy, rather than a
claim that the prose alone defines every discrete behaviour.

All vectors are cached Float32 stereo inputs. Actual scalar events retain their
authored boundary order and wire values; histories survive control changes.
The signal-threshold graph uses the data input itself as the threshold, avoiding
an ambiguous extra threshold calculation. Zero-input warmup and two fresh
lifecycles distinguish history continuity from reconstruction. Direct reset,
additional messages, arbitrary graphs and wider numeric domains remain open.

## Results retained

Both O3 and UBSan builds are runtime-healthy for all 45 programs. Their Float32,
PCM, normal traces and statistics match byte for byte, with 90 exact
reconstruction comparisons and 180 lifecycle executions. The paired output
count is 5,242,880 channel words. All recorded event and block parameter
readbacks are checked. No guarded Platform/C++ allocation, module error,
invalid sample or PCM clip is observed in those runs.

The fixed absolute limits are `3e-6` for onepole/slide and `2e-6` for delta;
sample/hold and direct observers require exact source-word copies. Limits and
inputs were fixed before captures, with no output fitting.

| Retained numerical failure | Maximum absolute ideal error | Limit |
| --- | ---: | ---: |
| Scalar onepole, 0 Hz long DC | 0.00025505 | 0.000003 |
| Scalar onepole, 0.05 Hz long DC | 0.00025505 | 0.000003 |
| Scalar onepole, 1 Hz long DC | 0.00035225 | 0.000003 |
| Scalar onepole, ordered frequency events | 0.00000697 | 0.000003 |
| Signal onepole, slow cutoff grid | 0.00001120 | 0.000003 |
| Scalar slide, large signed rates | 0.00000763 | 0.000003 |

Eleven first-failure channel witnesses were checked independently with
high-precision convolution or closed forms and actual capture words. These
are numerical accuracy failures, not ABI or allocation faults. Rounded
onepole feedforward/feedback coefficients can sum to less than one, and slow
Float32 histories can stop advancing near a steady value. The reference does
not adopt that plateau as mathematical truth. Delta and all tested `sah~`
forms pass their declared gates. Matching compiler builds alone is not the
independent accuracy check.

## Actual target paths and private runtime closure

Linked Xtensa code distinguishes coefficient work from the sample recurrence:

- Onepole retains Double multiply/divide/exp and clamp comparisons on coefficient
  updates. Fixed coefficients are prepared outside the sample loop; scalar
  updates remain conditional within it, while signal controls may update every
  sample. The filtering recurrence itself is hardware Float32.
- Slide reciprocals are Float32. Fixed/scalar rates prepare them outside the
  loop; signal rates can divide within it.
- Delta and sample/hold DSP paths have no resolved helper calls or Double work.
  Clock/control paths and unresolved virtual calls remain separately recorded.

The original fixed-integer slide graph initially failed target module admission
because `rnbo_abs(8)`/`rnbo_abs(32)` selected an undefined C `abs` symbol. The
native host's libc had masked this target closure gap. The fixture was retained
unchanged; no broad import permission or `.0` literal workaround was used.

The private SDK now supplies a hidden integer-only `abs` entry in its own
translation unit. It uses unsigned magnitude arithmetic, checks 32-bit integer
representations and avoids signed overflow. The unrepresentable `INT_MIN`
magnitude has an explicit private extension returning `INT_MIN`; this is not
a positive-magnitude claim or a claim that standard C defines `abs(INT_MIN)`.
Current fixed slide literals are 8 and 32. Release and sanitizer tests each
check 131,260 inputs against an independent widened reference.

An initial same-source-file addition changed 33 bytes of unrelated `strcmp`
layout. That cohort is retained. Moving the helper into its own file restores
complete byte identity for all nine formerly admitted graphs and eight
representative published modules. The original `support.cpp` is byte-identical;
no allocator, clock or firmware namespace was added. Fixed slide now links with
zero imports; its 17-byte helper is a call-free integer leaf with no allocation
or floating-point operations. This is a module support fix, not a DSP speedup.

Compiled target contexts range from 12,736 to 12,784 bytes, with a selected
4,096-byte structural arena. Loaded text spans range from 27,240 to 35,232 bytes
and include the private wrapper/runtime. Native zero arena use is not a target
heap measurement; these layouts are not isolated object costs or a complete
live-instrument memory/deadline envelope.

The [sealed record](../evidence/wave3-stateful.json) binds the native and public
execution epochs, independent reviews, target cohorts, helper source/tests and
compatibility images. It preserves the missing-import rejection, intermediate
layout drift and numerical failures. No performance measurement is added to
the status table. Onepole's Double coefficient/clamp path is a candidate for
further proof and optimisation; its observed accuracy failures must remain
visible throughout that work.
