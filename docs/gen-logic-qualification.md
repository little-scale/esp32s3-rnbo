# Gen comparison and logic qualification on XIAO

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

Twenty additional exact GenExpr forms pass native and XIAO numerical tests.
One additional form, `step`, runs but disagrees with the documented argument
order. Its failure is retained separately. Each program is an original RNBO
`gen~` graph with two inputs, two outputs and no parameters or external resources.
Aliases and syntax forms have their own source identities and device runs.

| Exact GenExpr form | XIAO output result | Mean callback µs | Optimisation tested | Time saved |
| --- | --- | ---: | --- | --- |
| `neq(in1, in2)` | Pass | 46.81 | No: same-image control | — |
| `in1 != in2` | Pass | 46.82 | No: same-image control | — |
| `gt(in1, in2)` | Pass | 54.07 | No: same-image control | — |
| `in1 > in2` | Pass | 54.06 | No: same-image control | — |
| `gte(in1, in2)` | Pass | 50.20 | No: same-image control | — |
| `in1 >= in2` | Pass | 50.21 | No: same-image control | — |
| `lte(in1, in2)` | Pass | 50.26 | No: same-image control | — |
| `in1 <= in2` | Pass | 50.23 | No: same-image control | — |
| `and(in1, in2)` | Pass | 57.85 | No: same-image control | — |
| `in1 && in2` | Pass | 57.85 | No: same-image control | — |
| `or(in1, in2)` | Pass | 58.43 | No: same-image control | — |
| `in1 \|\| in2` | Pass | 58.42 | No: same-image control | — |
| `xor(in1, in2)` | Pass | 53.20 | No: same-image control | — |
| `in1 ^^ in2` | Pass | 53.20 | No: same-image control | — |
| `not(in1)` | Pass | 52.17 | No: same-image control | — |
| `!in1` | Pass | 52.16 | No: same-image control | — |
| `bool(in1)` | Pass | 52.22 | No: same-image control | — |
| `step(in1, in2)` | Documented-order mismatch | — | No | — |
| `sign(in1)` | Pass; −0 becomes +0 | 60.44 | No: same-image control | — |
| `switch(in1, in2, -in2)` | Pass | 52.17 | No: same-image control | — |
| `in1 ? in2 : -in2` | Pass | 52.15 | No: same-image control | — |

Each timing is the reference slot's mean for the whole stereo callback,
256 frames at 44.1 kHz. Both comparison slots load the same ELF. Small slot or
alias timing differences measure repeatability and claim no optimisation gain.
Input generation, cache copying, independent mathematics, analysis, preparation,
I²S, display and networking are outside the process timer. These are not
isolated-operation costs or worst-case application deadlines.

## Inputs, output checks and resources

Every successful form runs four input programs: a signed grid, dense binary32
values, vector boundaries and finite magnitude boundaries. The last includes
both zero signs and subnormal/normal edges. Inputs are finite binary32 values
in `[-1, 1]`; PCM gain is 0.5. Each reconstructed pass uses four zero warmup
vectors and 64 rendered vectors. Three rounds alternate comparison order, and
timing excludes the first 32 rendered vectors.

The independent references use mathematical comparisons and nonzero truth,
including nonzero subnormals. Unary operations treat each input independently;
binary operations reverse their arguments on the second output. The authored
switch/conditional programs select the other input or its negation. Complete
target input/oracle hashes agree with independently generated computer caches.

Across the 80 successful device case programs, 7,864,320 paired output-word
comparisons have zero numerical, PCM and raw-bit differences. Across both slots,
15,728,640 independent numerical checks and the same number of operation-bit
checks pass with zero differences in this batch. Counts include repeated executions.
Operation zero signs remain separately observed diagnostics; the same-image
pair itself must be bit-exact.

Each successful program has a 12,720-byte opaque context, zero arena use within
a 4 KiB capacity, and zero callback heap/late-allocation counters. All 80 loaded
images are finalised and both heaps return exactly to their baselines. Every
completed test restores the drone unpaused at 50% with its eight compiled
parameter defaults and verified health. See
[the complete device observations and failure records](../evidence/xiao-gen-logic.json).

## Step: an observed documentation discrepancy

[Cycling '74's step reference](https://docs.cycling74.com/reference/gen_common_step/)
describes a first-input-greater-or-equal comparison. The installed RNBO 1.4.4
registry description agrees, while its expression metadata and actual generated
code compare the second argument against the first. As a source-level example,
inputs `(0, 1)` imply documented output pair `(0, 1)` and generated pair `(1, 0)`.
Equality still returns one in both orders. The executed input programs below
have their own complete input and oracle hashes.

The native runs fail the unchanged zero-error gate in all four input families,
with maximum error 1. The XIAO run independently fails that same gate in the
first signed-grid case: the strict slot reports 98,304 checked words and error
1 against tolerance 0. Its same-ELF pair is bit/PCM exact, so compatibility
between those slots does not establish agreement with the documented rule.

The runner stops on the failure marker; that final fault line is only partially
captured, while the preceding semantic record is complete. The test does not
complete its other device cases or finalisation/heap/timing summaries. No step
performance or completed-resource qualification is claimed. The drone is
successfully restored afterward. The installed package is unchanged, and the
oracle has not been inverted to turn this discrepancy into a pass.

## Sign and selected payloads

The tested `sign` implementation maps negative zero to positive zero. The
[sign reference](https://docs.cycling74.com/reference/gen_common_sign/)
describes a zero passthrough without an explicit signed-zero policy. Native
execution retains 47,360 negative-zero observations across builds/lifecycles;
all become positive zero. On the target, inputs with either zero sign match
the canonical positive-zero output bits. Numerical zero
passes; preservation of negative zero is not qualified.

Both authored switch forms preserve the selected binary32 payload bits,
including signed zeros, in the tested inputs. The ternary grammar `?:` binds
to registry entry `?`; its source identity is distinct from the function call.
Neither result qualifies arbitrary control-flow programs or resource effects.

## Native and precision evidence

The native cohort covers all 21 forms, four input families, O3 and UBSan builds,
and two fresh lifecycles: 168 case-builds and 336 constructed contexts. All
5,505,024 paired O3/UBSan output words, PCM, traces and statistics agree exactly.
The 11,010,048 independent-model checks include the retained step failures;
80 source/input case programs pass and four step case programs fail. Native
health/ABI compatibility is separate from mathematical agreement and target
loader/finalisation evidence.

The target precision audit individually binds the 21 sources to 12 distinct
ELFs. All 36 named/live-callback/preparation loop copies use Float32 and integer
instructions, with no Float32 or Double helper calls inside those loops.
Binary64 scheduler work remains outside them. Actual build flags, complete
42-file prepared maps, SDK sources, callbacks and relocation ranges are bound.
These static findings establish neither an optimisation percentage nor an
isolated instruction cost.

## Retained recovery failures

The first neq attempt and an earlier less-or-equal attempt pass their DSP checks
but fail restoration verification. They are retained and excluded from the
completed-control totals. A read-only check and three register-only restart
observations confirm the original drone/defaults. Those observations also show
USB availability before application startup messages; the exact cause of the
earlier failed command exchanges remains unproven.

The recovery helper now reads startup output without sending commands for two
seconds before strict status validation. It bounds retained output to 64 KiB,
permits reconnect only during that boot phase, and saves raw boot logs privately.
Identity errors, malformed replies and complete command errors still stop the
run. The nominal boot-connection deadline can be exceeded by an already-running
nested connection wait before rejection; it is not a hard total wall-clock
guarantee. Missing status replies have a separately bounded retry window.
Later successful attempts use new directories and preserve both failed records.

Final checks pass 463 compiler tests, 141 tool tests and 31 recovery-runner tests.
The wider [Gen inventory and single-sample requirements](gen-qualification.md)
remain active. Visual Gen forms, other overloads/arities, nonfinite inputs,
floating environments and a one-frame production module ABI remain unqualified.
