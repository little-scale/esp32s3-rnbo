# Gen and single-sample qualification

Gen/`gen~` is explicitly part of the active XIAO qualification goal. Its names,
language constructs and evidence remain separate from RNBO objects and RNBO
`codebox~`. A matching name does not transfer a result between those contexts.
See the [full requirements](qualification-scope.md).

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

## Inventory and remaining work

The [metadata inventory](../site/data/gen-inventory.json) records:

- 164 audio-capable names from installed Max common/DSP Gen references.
- 212 exact spellings from the installed RNBO GenExpr registry, including
  57 aliases across 155 canonical operators.
- 216 unique names in their combined documented/registry union, with surfaces
  kept distinguishable. Registry membership is not proof of export support.
- Separately listed 28 named constants, 16 globals and five declaration forms.
  These do not exhaust GenExpr grammar or arbitrary user-defined functions.
- Jitter reference context, kept separate from the requested `gen~` DSP scope.

Only the exact GenExpr `History` declaration has scoped native evidence for
initial values 0, 1 and 2 in these programs. That does not qualify a visual
`history` box, a differently spelled functional form, another operator, an
alias or a complete Gen object family. The remaining operator/form outcomes
and all Gen XIAO execution/performance tests remain pending.

The initial importer route requires explicit GenExpr. Visual embedded Gen
patchers, `.gendsp` file/title forms, converted `gencode`, `exposeparams`, unknown
Gen box options and zero-output side-effect-only forms remain unadmitted.
They stay in the remaining scope. A saved input count of zero is allowed for
autonomous generators; RNBO metadata still retains a base control inlet.
External Buffer declarations remain visible to normal prepared-module admission
and are rejected there until their host/resource contract is implemented.

Next tests extend the same input/model/precision and resource discipline to
Gen on XIAO, visual/operator forms, delays, data/resources, control flow,
sample-accurate events and the remaining named inventory. Single-sample feedback
and block-boundary behaviour must be observed directly, alongside numerical
truth and resource measurements. Cycling '74 describes the underlying semantics
in its [Gen overview](https://docs.cycling74.com/userguide/gen/_gen_overview/) and
[`history` reference](https://docs.cycling74.com/reference/gen_dsp_history/).
