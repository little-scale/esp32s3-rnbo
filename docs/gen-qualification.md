# Gen and single-sample qualification

Gen/`gen~` is explicitly part of the active XIAO qualification goal. Its names,
language constructs and evidence remain separate from RNBO objects and RNBO
`codebox~`. A matching name does not transfer a result between those contexts.
See the [full requirements](qualification-scope.md).

Coverage now also uses [short batched hardware checks](hardware-smoke.md).
The latest [range/routing/conversion batch](hardware-smoke.md#gen-range-routing-and-conversion-calls)
executes 29 GenExpr calls: 25 pass, three fast approximations exceed the fixed
1e-3 ideal-math screen, and `ftom` differs from the declared continuous-pitch
reference at quarter tones. The separate tuple `gate` source is rejected before
execution. There are 296,960 output checks and six CPU-review flags. All executed
images finalise with memory/allocation gates passing. Only `mtof` consumes arena
storage (262,256-byte high-water mark including its original lookup table);
1 MiB is reserved per image, not consumed by every call. Fast screens are not
documented accuracy promises, and the results do not extend to every mode,
alias or single-sample host API. See [the complete evidence](../evidence/xiao-smoke-gen-range.json).

The [stateful batch](hardware-smoke.md#gen-stateful-and-per-sample-batch) passes
all twelve programs covering nine exact spellings, with 122,880 output checks
across twenty continuous callbacks each. Its vectors expose per-sample updates
and block-boundary state; no CPU-review flags trigger. These are still fixed
256-frame calls, with one-frame host calls and sample-offset events separate.
The [earlier mathematical batch](hardware-smoke.md#gen-mathematical-batch) has
27 device passes within declared comparison limits, four C++ compilation
failures and three frontend parser rejections from 34 authored forms.
Thirteen executed forms are queued for CPU review; stereo `exp2` exceeds the
block period. These fixed-256-frame checks do not extend single-sample or
stateful-feedback qualification.
The first numeric batch adds 15 executed scenarios and one compiler rejection,
with round/denormal mismatches retained. These basic checks do not inherit the
broader guarantees of the older native/target qualification batches below.

## What works so far

The public exporter now admits authored GenExpr code in a `gen~` box, using the
installed RNBO 1.4.4 frontend. It validates expression/port metadata and rejects
parse failures instead of exporting the frontend's empty error fallback.
Eleven frontend tests pass, including the existing importer tests, fixed-256
history export/preparation, autonomous Main 0→2 constant/noise export, and
atomic rejection of unsupported external Buffer resources. Noise execution is
not qualified by export acceptance.

Two [original History programs](../tests/fixtures/gen/README.md) also pass actual
native execution in both O3 and UBSan builds:

| Program | Independent model | Largest observed error |
| --- | --- | ---: |
| One-history feedback, initial/reset state 0 | `y[n] = x[n] + 0.5*y[n-1]`; weighted input convolution independent of the recursive implementation | 1.49e-8 |
| Two histories initially 1 and 2 | Exact alternating states, with explicitly authored old-state temporaries | 0 |

Each program/build processes the same 4,096-frame input using one-sample,
2-, 7-, 255- and 256-sample calls and a mixed partition pattern. The partitions
are shortened at explicit event boundaries. Per build, 13 constructed instances
produce 98,304 exact partition/reconstruction comparisons, 52 post-start reset
actions and 26 additional prepare calls. Across both programs and builds this
is 52 instances, 208 resets and 393,216 partition comparisons. The two retained
O3/UBSan captures also match over 16,384 channel words.

Reset travels through the authored parameter → `set reset` → Gen reset action;
it restores declared initial values. Repeated identical parameter values still
retrigger reset. Reset points include samples 513, 1,024, 2,051 and 3,001;
additional prepares occur before samples 257 and 1,300. The model checks state
continuity through those prepares and fresh initialization after reconstruction.
The swap program's explicit temporaries avoid assuming that two imperative
assignments have simultaneous semantics.

The feedback reference uses a bounded convolution, not a copy of the generated
recursive state update. The omitted tail is bounded by 2^-64; a conservative
binary64 model allowance is 2^-45. The supplied bounded recurrence has a
conditional recursive Float32 roundoff bound of 2^-23 + 2^-45. The fixed 2e-6
acceptance gate was not widened from the observed error. These bounds concern
the supplied input and feedback coefficient, not arbitrary Gen algorithms.

These native calls use a separately tagged **variable-block producer**. The
production module C ABI remains fixed at 256 frames. No one-frame module ABI,
Gen device execution, CPU saving, allocation-free execution or hardware memory
qualification follows from this host test. The native runtime uses
`RNBO_USE_FLOAT32`; other floating-point modes and nonfinite inputs are not
qualified. Full data, source/capture hashes and limits are in
[the native single-sample evidence](../evidence/gen-single-sample-native.json).

## First XIAO history batch

Three original GenExpr programs now pass actual XIAO execution through the
production fixed-256 module ABI. Each runs continuous, six boundary-reset and
every-block retrigger cases, with three reconstructed passes per comparison
slot. The input and independent expected-output caches are generated outside
the process timer; their complete SHA-256 identities are independently checked
on the computer. This is separate from the variable-block native test above.

| Program | Mean callback, reference slot | Observable reset witnesses, both slots |
| --- | ---: | ---: |
| One-history feedback | 304.15 µs | 414 |
| Two-history swap | 54.16 µs | 0 |
| Three-history rotation, initially 1, 2 and 3 | 55.16 µs | 414 |

The batch passes 884,736 pair comparisons and 1,769,472 independent-model
checks. Pair numerical, PCM and raw-word differences are zero. The largest
conservative feedback-model error bound is 2.236e-8 against the predeclared
2e-6 gate; both periodic models have zero error. The bound separately includes
cache rounding, the omitted convolution tail and binary64 model evaluation.
There are 1,260 dispatched reset commands, 828 observable reset witnesses and
1,656 checks of their first output pair, with no witness failures. Counts
include repeated executions, rather than distinct test values.

The two-history swap repeats every two samples, so a reset at a 256-frame
boundary leaves its phase unchanged. Its zero witnesses are deliberately not
reported as functional reset validation. The three-history rotation avoids
that blind spot: four warmup vectors advance its initial phase, and a block-0
reset observably restores `(1, 2)` from the continuous `(2, 3)` start. Some
later boundary resets also coincide with its existing phase and are excluded
from the witness count by a separately predicted counterfactual mask.

All 12 module images are finalised, both heaps return exactly to their recorded
baselines, and callback heap/late-allocation counters remain zero. After each
application-only test the drone is restored unpaused at 50% with its compiled
parameter defaults. The declared module profile is `float32-strict`; the
independent offline model intentionally uses binary64. Whole-program timings
compare identical ELFs and claim no optimisation gain or isolated-operator cost.
See [the complete target observations](../evidence/xiao-gen-history.json).

The precision audit found a real limitation in this baseline: the generated
feedback expression `in1[i] + 0.5 * z` uses an unsuffixed double literal. State
and outputs are Float32, but actual Xtensa disassembly shows two Float32-to-double
conversions, a double multiply/add and a conversion back per sample. This is
1,280 double-helper calls per 256-frame vector. The swap and rotation sample
loops contain no corresponding double-helper calls; scheduler clock arithmetic
remains separate. A separately identified
[Float32 feedback profile](gen-feedback-float32.md) now removes this promotion:
the fresh matched XIAO comparison uses 83.94% less callback time with exact
output in the three authored cases. That result is separate from this retained
baseline; changed-rounding native counterexamples remain explicit.

These device tests establish the authored per-sample feedback/history ordering
inside 256-frame callbacks and the listed block-boundary resets. They do not
establish a one-frame module API, sample-offset event dispatch on XIAO, arbitrary
feedback algorithms, visual Gen import or complete Gen operator coverage.

The target evidence preserves an earlier compiler-suite failure discovered
during publication. The [separate admission follow-up](../evidence/producer-metadata-admission.json)
resolves it: seven existing optimisation contexts now admit the Gen-aware
importer's exact provenance fingerprint alongside the historical one. Their
other 41 input files and generated guarded DSP headers are unchanged. The final
417 compiler tests and 124 tool tests pass; the target binaries retain their
archived original build epoch.

## Comparison and logic batch

Twenty additional exact forms now pass native and XIAO tests, covering
comparisons, Boolean logic, sign and conditional selection. Their 80 device
case programs pass 7,864,320 exact pair comparisons and 15,728,640 independent
numerical/bit checks, with full memory recovery and drone restoration. A
separate `step` test fails the documented argument-order model on both native
and XIAO execution; it remains a recorded discrepancy. `sign(-0)` becomes `+0`.
The [per-form output and timing table](gen-logic-qualification.md) records
these limits, the precision audit and two retained recovery-check failures.
Same-image controls claim no optimisation gain. This does not extend the
one-frame production module ABI or visual Gen qualification.

## Inventory and remaining work

Fifteen [exact GenExpr arithmetic spellings](gen-arithmetic-qualification.md)
now also pass their own native and XIAO runs: abs, min/minimum, max/maximum,
sub/`-`, eq/`==`, lt/`<`, add/`+` and mul/`*`. The 45 device case programs pass
8,847,360 numerical model and operation-bit checks with zero observed error.
These same-image controls record absolute callback costs, with no optimisation
gain. Three additional unbound function-call probes fail C++ compilation;
frontend/prepare acceptance is explicitly kept separate from execution.

The separate [abs intrinsic option](gen-abs-intrinsic.md) now passes a matched
four-case XIAO comparison: 71.46 → 45.60 µs, or 36.19% less whole-callback time.
Both profiles have exact numerical, PCM and raw magnitude bits, including
subnormal and signed-zero boundaries. This removes Float32 library calls;
it does not change the clock precision or qualify other Gen operations.

The [metadata inventory](../site/data/gen-inventory.json) records:

- 164 audio-capable names from installed Max common/DSP Gen references.
- 212 exact spellings from the installed RNBO GenExpr registry, including
  57 aliases across 155 canonical operators.
- 216 unique names in their combined documented/registry union, with surfaces
  kept distinguishable. Registry membership is not proof of export support.
- Separately listed 28 named constants, 16 globals and five declaration forms.
  These do not exhaust GenExpr grammar or arbitrary user-defined functions.
- Jitter reference context, kept separate from the requested `gen~` DSP scope.

The exact GenExpr `History` declaration has scoped native and XIAO evidence
in its three programs (target initial values 0, 1, 2 and 3); the fifteen arithmetic
spellings above have separate source-specific evidence. Neither qualifies a
visual `history` box, another syntax/arity, an untested alias or a complete Gen
object family. Inventory pending labels are metadata, not a qualification join.
The comparison/logic batch has its own exact source identities and observed
step/sign limits; it does not qualify visual boxes or other overloads.
The remaining operator/form outcomes
and the remaining Gen XIAO execution/performance tests remain pending.

The initial importer route requires explicit GenExpr. Visual embedded Gen
patchers, `.gendsp` file/title forms, converted `gencode`, `exposeparams`, unknown
Gen box options and zero-output side-effect-only forms remain unadmitted.
They stay in the remaining scope. A saved input count of zero is allowed for
autonomous generators; RNBO metadata still retains a base control inlet.
External Buffer declarations remain visible to normal prepared-module admission
and are rejected there until their host/resource contract is implemented.

Next tests extend the same input/model/precision and resource discipline to
the remaining Gen operators on XIAO, visual forms, delays, data/resources, control flow,
sample-accurate events and the remaining named inventory. Single-sample feedback
and block-boundary behaviour must be observed directly, alongside numerical
truth and resource measurements. Cycling '74 describes the underlying semantics
in its [Gen overview](https://docs.cycling74.com/userguide/gen/_gen_overview/) and
[`history` reference](https://docs.cycling74.com/reference/gen_dsp_history/).
