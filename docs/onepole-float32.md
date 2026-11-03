# Onepole Float32 comparisons and numerical study

The later [stable onepole profile](stable-onepole.md) implements a guarded
descendant of the numerical study below. It adds finite recovery and is now an
experimental option for three exact FX graphs. The unguarded prototype and its
counterexample below remain historical evidence, not the admitted algorithm.

The experimental, default-off `--float32-onepole-clamp` compiler option removes Double
comparisons from exact generated onepole clamp statements. It preserves the
stored result for every finite binary32 operand under nearest-even rounding.
Coefficient evaluation, recurrence, state layout and scheduling are unchanged.
It **does not repair** the five recorded onepole accuracy failures.

A separate private study finds a more accurate Float32 coefficient/recurrence,
but also a valid-input counterexample outside its bounded audio tests. That
candidate is not available through a compiler option.

## Use the comparison option

Export normally, then prepare a strict Main or FX export with:

```sh
python3 host/compiler/prepare.py --export build/exports/my-patch \
  --out build/prepared/my-patch-clamp --class-name rnbos3patch --role fx \
  --float32-onepole-clamp
```

Use a fresh output directory and the export's actual class name and role. The
option requires normal runtime fixes, RNBO 1.4.4, the strict base profile and no
other optional adapters. The default remains unchanged. It rejects an export
without the exact generated clamp statement. Listing an object or accepting an
export does not establish every mode or composition's semantic accuracy.

Unlike the earlier loop-hoisting passes, this operation's proof is local to a
single assignment. It can match generated onepole statements in other graphs;
it does not use whole-graph identity as a substitute for the type proof. Each
emitted statement has a compile-time assertion that its actual operand is an
ordinary `float`, excluding Double, references and volatile operands. The
compile contract requires strict binary32/binary64 and no extended evaluation.
Fixed runtime nearest-even rounding is a separate execution contract.

Each replacement is one compound statement, so unbraced `if/else`, loops,
`do/while` and switch cases keep their original execution. No runtime object is
introduced. Operand/type-guard macros, line-spliced or trigraph source, custom
line directives and source counters are rejected. The lexical mask excludes
comments and strings. Ordinary source line numbers are restored with `#line`;
compile-only guards can be removed to recover the private comparison candidate
byte for byte in all three reviewed headers.

## Exact stored-value proof and limits

Both original binary64 constants lie strictly between their rounded-down
binary32 value and that value's successor:

| Bound | Rounded binary32 word | Where comparison predicates differ |
| --- | --- | --- |
| `0.00001` | `0x3727c5ac` | Only at this exact word: the original lower comparison is true and the typed comparison is false. Both assignments store this word. |
| `0.99999` | `0x3f7fff58` | Nowhere on the finite binary32 lattice. |

The independent partition argument covers all 4,278,190,080 finite encodings,
including both zero signs. A compiled O3/UBSan check samples 408,069 finite
encodings, including exponent strata and threshold neighbours. This is a
mathematical partition proof plus sampled execution, not exhaustive execution
of every encoding.

Floating-environment equivalence is **false**, rather than merely untested:
the independent native probe observes different inexact flags at some clamped
values. Signalling NaN outputs also differ in that probe: the original can
quiet a NaN through Float32→Double→Float32 conversion while the typed form keeps
the signalling word. Traps, flags, NaN payload/signalling behaviour and
non-default rounding are outside this option's contract. These host
observations do not establish ESP32 NaN payload behaviour.

## Native compatibility and compiled scope

Fresh public exports and actual CLI preparations cover fixed stereo, scalar
cutoff and signal cutoff/observer forms. Their 15 actual production-C-ABI
programs retain the strict baseline's Float32 output, PCM, parameter traces,
statistics and independent mathematical results exactly. O3/UBSan captures and
fresh reconstructions agree; all programs remain runtime healthy with no
processing allocation. The five mathematical failures remain visible under
the original `3e-6` absolute limit.

The private comparison-only target builds remove three resolved Double helper
sites per coefficient-update instance: extension plus upper/lower comparisons.
Double exponential/argument work remains. The complete module size reductions
are 264 bytes for fixed stereo, 288 for scalar stereo and 152 for signal cutoff.
These are compiled file sizes, not RAM savings, executed instruction counts or
CPU percentages. Fixed and steady scalar coefficients rarely update; removing
update work need not materially change their steady audio cost.

All three fresh public candidate modules reproduce the complete private
comparison-only ELF bytes. The [sealed evidence](../evidence/onepole-float32-clamp.json)
binds the exact prepared maps, compiler/runtime epochs, mathematical proof,
native compatibility, linked inspection and reference/candidate identities.

No module in this study has executed on the ESP32-S3. The selected 4,096-byte
arena is structural, not a measured target high-water mark. Native host libc
and constructor/finalizer stubs do not establish target math, ELF lifecycle or
whole-instrument resource/deadline behaviour.

## Separate stable-coefficient and compensation study

The actual RNBO helper is important: generic `rnbo_exp(Double)` returns
`RNBO::number`, already Float32. The source then subtracts that rounded result
from 1. This loses small coefficients even though the exponential itself used
Double. The filtering recurrence's separately rounded `a` and `1-a` can also
introduce DC bias, while slow Float32 histories can stop advancing.

Four private alternatives separate these effects. All use the unchanged 15
programs and independent `3e-6` gate, with no input fitting or relaxed limit:

| Alternative | Accuracy failures | Largest ideal error |
| --- | ---: | ---: |
| Typed clamp only | 5 | `0.00035225` |
| Compensated difference update, original coefficient | 1 | `0.00003422` |
| Stable Float32 coefficient, original recurrence | 5 | `0.00025505` |
| Stable coefficient plus compensated difference update | 0 | `0.0000001093` |

The combined form computes `-rnbo_expm1(Float32 negative argument)` and uses a
Float32 correction for addition rounding in `y += a*(x-y)`. It reuses the old
feedback-coefficient word for that correction, retaining zero initial/reset
state and preserving the correction across cutoff changes and vector
boundaries. It adds no state member. Reusing storage reproduces the first
combined candidate's Float32, PCM, traces and oracle results exactly.

Twelve additional independently authored bounded programs cover long low-alpha
sign reversals, cutoff neighbours, near-unity alternating inputs, tiny-signal
recovery, same-block control bursts and vector boundaries. Their 48 lifecycles
are healthy; O3/UBSan and reconstruction agree across 11,534,336 paired channel
words. Maximum ideal error is `0.0000001675`, below the unchanged gate.

Actual compiled target contexts and every patch member offset are unchanged:
12,768 bytes fixed, 12,784 scalar and 12,736 signal. The linked `expm1f` closure
has no Double helper, including its Float32 division and local math-error path.
This result comes from the actual linked code and pinned archive, not its
function suffix: the same library's `fmaf` uses Double helpers. The generic
signal-call auditor's spill ambiguity remains recorded separately.

The compensated sample recurrence has four subtractions, one multiply and one
addition versus the original two multiplies and one addition. It may cost more
for steady coefficients even while coefficient updates become cheaper. No
CPU gain is inferred; those workloads need separate target measurements.

Most importantly, finite inputs alone are insufficient. An actual C ABI probe
at cutoff zero feeds `-FLT_MAX`, then `+FLT_MAX`: the baseline stays finite,
while `x-y` overflows in the combined candidate, faults the module and produces
fail-closed silence. This counterexample is retained separately from the
passing bounded programs. General admission needs a proved overflow-safe
update or a suitable enforced input contract. The corrected candidate remains
private until that work is done.
