# Gen feedback Float32 profile

`float32-gen-feedback-v1` is an optional, changed-rounding profile for the exact
original [history-feedback GenExpr program](../tests/fixtures/gen/history-feedback.genexpr).
It changes one literal from `0.5` to `0.5f`. The generated program otherwise
retains its history state, reset action, input/output layout and scheduler clock.
Other Gen programs and option combinations are rejected by this profile.

```sh
python3 host/compiler/prepare.py \
  --export build/hardware/gen-history-target-inputs-v1/raw/history-feedback \
  --class-name rnbos3patch --role fx \
  --numerical-profile float32-gen-feedback-v1 \
  --out build/prepared/gen-feedback-float32
```

This example uses a local licensed export. The normal preparation default
remains `float32-strict`. Admission pins the original graph, generated source,
description, complete 41-file preconfiguration map and corrected runtime. A
one-character inverse reconstructs the original source exactly. The generated
type include requires binary32 sample/state types, no excess evaluation
precision, the reviewed ABI and binary64 scheduler time. The standard build
commands disable fast math and contraction; these flags are part of the
qualified compiler configuration.

## Measured XIAO result

The fresh reference and candidate use the same compiler, `-O2` flags, SDK,
libraries, allocation policy and raw export. Three cases exercise continuous
processing, six boundary resets and a repeated reset at every block. Each case
runs three times per profile, with alternating comparison order and the first
32 rendered blocks excluded from timing.

| Whole stereo callback, 256 frames | Reference | Float32 candidate |
| --- | ---: | ---: |
| Mean process time | 304.22 µs | 48.86 µs |
| Observed peak process time | 316 µs | 56 µs |
| Timed callbacks | 288 | 288 |
| ELF `.text` bytes | 31,675 | 31,243 |
| Opaque context bytes | 12,736 | 12,736 |

This is **83.94% less measured callback time**, about 6.23× faster for the
complete authored test graph. It includes its ordinary wrapper and clock work.
Input generation, independent oracle construction, output analysis, preparation,
event dispatch, I²S, display and networking are outside the process timer. This
does not measure an isolated multiplication, a worst-case deadline, another
Gen graph or a change to the live drone's utilisation.

All 294,912 pair comparisons have zero numerical, PCM and raw-word differences.
All 589,824 independent-model checks pass the unchanged 2e-6 gate; the largest
conservative model-error bound is 2.236e-8. There are 420 dispatched reset
commands, 414 independently predicted observable reset witnesses and 828 checks
of their first output pair, with zero failures. All four loaded images are
finalised, internal RAM and PSRAM return exactly to baseline, and callback heap
and late-allocation counters remain zero. The test restores the original drone
unpaused at 50% with its compiled parameter defaults.

The machine-code audit checks all three compiler copies of the Gen loop,
including the live module callback and prepare warmup. Each original loop
invokes five known binary64 helpers per sample. Each candidate loop instead
uses separate Float32 multiply/add instructions and has no helper invocations
inside the sample loop. Binary64 scheduler arithmetic remains outside it.
The 1,280 original helper invocations per full vector are a static derivation,
rather than an independently measured per-helper cost. Text shrinks by 432
bytes; total ELF file size, state layout and arena capacity are unchanged.

See [the complete saved target observations](../evidence/gen-feedback-float32.json).

## Precision limits

The profile is explicitly changed-rounding. Actual public-prepared native
execution covers nine programs across reference/candidate and O3/UBSan builds:
36 case-builds, 72 constructed contexts and 2,359,296 model comparisons. The
largest observed model error is 4.68e-8 against the same 2e-6 gate. The three
original device cases are bit-exact between variants, while adversarial native
inputs expose subnormal, signed-zero and normal-output midpoint differences.

For example, from zero state, two inputs equal to the smallest positive
subnormal produce different second samples: the original double intermediate
rounds to twice that input, while the Float32 product rounds to zero before
the addition. A sequence beginning with its negative also exposes a zero-sign
difference. These examples are retained and do not grant bit or floating-
environment identity to the profile.

For finite inputs with absolute value at most 0.5 and initial/reset state zero,
state magnitude stays at most 1 under round-to-nearest binary32 operations.
Under gradual underflow, no traps and disabled contraction, the candidate's
recurrence roundoff is bounded by `2^-23 + 2^-149`. The independent model's
omitted convolution tail (`2^-64`) and evaluation allowance (`2^-45`) are
separate. This is a conditional numerical argument; it does not establish
the XIAO's subnormal/floating-environment behaviour or all finite input
amplitudes. Device execution is qualified for the three authored dyadic cases.
The wider inventory, visual Gen forms and target sample-offset event dispatch
remain [separate pending work](gen-qualification.md).
