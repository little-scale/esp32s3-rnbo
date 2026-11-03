# Gen arithmetic qualification on XIAO

Fifteen exact GenExpr spellings now pass native execution and XIAO execution.
Each is an original program inside an RNBO `gen~` box, with two signal inputs,
two outputs and no parameters or external resources. The second output applies
the same operation with reversed arguments; `abs` instead treats each input
separately. Each spelling has its own source identity and actual device run,
including aliases that lower to identical code.

| Exact GenExpr form | XIAO output checks | Mean callback µs | Optimisation comparison | Gain |
| --- | --- | ---: | --- | --- |
| `abs(in1)` | Pass | 71.56 | Not yet | — |
| `min(in1, in2)` | Pass | 48.88 | Not yet | — |
| `minimum(in1, in2)` | Pass | 48.89 | Not yet | — |
| `max(in1, in2)` | Pass | 49.02 | Not yet | — |
| `maximum(in1, in2)` | Pass | 49.08 | Not yet | — |
| `sub(in1, in2)` | Pass | 45.67 | Not yet | — |
| `in1 - in2` | Pass | 45.66 | Not yet | — |
| `eq(in1, in2)` | Pass | 46.89 | Not yet | — |
| `in1 == in2` | Pass | 46.84 | Not yet | — |
| `lt(in1, in2)` | Pass | 54.43 | Not yet | — |
| `in1 < in2` | Pass | 54.48 | Not yet | — |
| `add(in1, in2)` | Pass | 45.71 | Not yet | — |
| `in1 + in2` | Pass | 45.70 | Not yet | — |
| `mul(in1, in2)` | Pass | 45.68 | Not yet | — |
| `in1 * in2` | Pass | 45.70 | Not yet | — |

Times are the reference slot's mean for the complete authored stereo callback,
256 frames at 44.1 kHz on the XIAO ESP32-S3. Each comparison uses the same ELF
in both slots. The small timing differences between slots are repeatability
observations, with no optimisation gain claimed. Input generation, mathematical
cache construction, preparation, analysis, I²S, display and networking are not
inside the process timer. These are not isolated-operation costs or application
deadline guarantees.

## What was checked

All programs use `float32-strict`, the five normal runtime fixes and the fixed
256-frame production module ABI. Each runs three input programs: a signed grid,
a dense binary32 stream, and samples around vector boundaries. Inputs are
finite binary32 values in `[-1, 1]`. Four zero-input warmup vectors precede
each freshly reconstructed pass; three rounds alternate the comparison order,
and timing excludes the first 32 of 64 rendered vectors.

Across 45 case programs, all 4,423,680 pair comparisons and 8,847,360 independent
model checks pass with exactly zero numerical and PCM differences. The same
8,847,360 output words also have zero observed operation-bit or zero-sign
differences. Zero signs remain operation diagnostics rather than an inferred
general tie-selection rule; the same-image pair itself must be bit-exact.

The references evaluate the original input values, rather than generated DSP.
Binary64 represents both binary32 operands and their at-most-48-bit product
exactly before one binary32 output rounding. Addition/subtraction are separately
rounded to binary32, while comparisons and min/max use numerical value rules.
The target C reference and independent computer reference agree on every
complete input/oracle cache hash. A canonical first-argument tie rule fixes
min/max cache zero signs without prescribing undocumented Gen behaviour.

Every program reports a 12,720-byte opaque context and zero arena use within
its explicit 4 KiB capacity. That capacity is a structural ceiling, not a
measured allocation requirement. Callback heap operations and late module
allocations are zero. All 60 loaded images are finalised and both heaps recover
exactly. After each test, the original drone is restored unpaused at 50% with
its compiled parameter defaults and verified health.

The separate native run covers O3 and UBSan builds, 90 case-builds and 180 fresh
contexts. All 5,898,240 independent-model comparisons have zero error; O3/UBSan
outputs, PCM, traces, statistics and reconstructed runs agree. Native execution
does not contribute to the XIAO totals or establish a variable-block module API.
The complete [device observations](../evidence/xiao-gen-arithmetic.json) retain
source, build, input, oracle, output, timing and recovery identities.

The machine-code audit binds all fifteen source contexts to eight distinct
ELFs. Their Gen sample loops contain no Double helpers. Named processing, the
live module callback and preparation warmup are checked separately. Abs uses
two Float32 `fabsf` calls per frame, or 512 entries per 256-frame invocation;
the other seven operation loops have no helper calls. Binary64 clock arithmetic
remains outside those loops. These static counts do not measure a helper's
cost or establish an optimisation gain. Replacing the abs calls with an exact,
guarded intrinsic is a subsequent candidate to test.

## Compile failures kept separate

Three additional original probes call `subtract(in1, in2)`, `equal(in1, in2)`
or `less(in1, in2)` without defining those functions. These names are absent
from the pinned RNBO 1.4.4 GenExpr operator registry. All three pass frontend
export and normal preparation, but actual C++ wrapper instantiation fails with
an undeclared function call. They are recorded as compile failures and were
never executed or flashed. A program defining a user function with one of
those names is a different source context and remains untested.

## Remaining scope

These results apply to the exact authored function/infix programs, input
families, arities and numerical profile. They do not qualify other overloads,
scalar forms, user functions, nonfinite inputs, floating environments, visual
Gen patchers, RNBO patcher/codebox objects or untested aliases. The
[separate Gen inventory and requirements](gen-qualification.md) remain active.
The earlier [feedback Float32 optimisation](gen-feedback-float32.md) is a
different source-specific comparison and does not transfer its percentage to
any arithmetic row above.
