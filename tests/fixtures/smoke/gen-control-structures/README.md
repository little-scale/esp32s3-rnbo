# Gen control, declarations and language structures

Twenty-six original GenExpr programs target gaps beyond the earlier arithmetic,
logic and sample-state batches. They are embedded as explicit `gen~` expressions
in RNBO and exported with the local RNBO 1.4.4 toolchain. RNBO codebox and visual
Gen are separate surfaces; no spelling inherits another's result.

Primary contracts: the installed Gen operator metadata supplies pass-gate
predicates, declaration/global descriptions and exact aliases. The official
[GenExpr guide](https://docs.cycling74.com/userguide/gen/gen_genexpr/) describes
functions, multiple returns, parameters, branching and bounded looping.
The [elapsed reference](https://docs.cycling74.com/reference/gen_dsp_elapsed/)
defines a sample count since DSP start/reset. No generated algorithm is used
as the output model.

## Reference and execution policy

- Twelve independently authored programs cover `eqp`, `neqp`, `ltp`, `ltep`,
  `gtp`, `gtep` and their `==p`, `!=p`, `<p`, `<=p`, `>p`, `>=p` infix spellings.
  Both operand orders use a finite 16×16 dyadic grid with ties and signed zeros.
  The independent model multiplies the first operand by the predicate.
- `Param`/`param`, elapsed/voice names and a `constant(...)` call test their exact
  authored forms. Parameter checks use a default gain of 0.25, with no host
  controls; voice expectations are for a non-polyphonic context only.
- Lowercase `history` declares two nonzero initial values. A separate custom
  function with local `History` is called twice with different inputs; each
  call must retain independent state. Sample-age references check the previous
  sample across all twenty host callbacks.
- Bounded `for`, `while`, and `for` with `break`/`continue` use trip counts 0–5.
  References use closed-form triangular/square sums, with the skipped term
  removed for `continue`. A multiple-return function and an if/else-if history
  program retain their own frontend outcomes.

Every executable module uses the unchanged strict profile, zero automatic
preparation blocks, four checked manual warmups, sixteen timed callbacks and a
4 KiB arena ceiling. The collector pins all original sources and recomputes
the twenty-block references. Numeric tolerance is zero; zero-sign differences
are separately counted. There are no within-block host parameter events or
one-frame production ABI calls in this batch.

## XIAO results, 5 November 2026

**19 programs pass**, with **194,560 numeric output checks**, zero finite
numerical error and no nonfinite output. The twelve pass-gate spellings,
uppercase `Param` defaults, lowercase `elapsed`, lowercase `history`,
independent function-local histories and three bounded-loop programs pass.
All 19 images finalise and pass memory/allocation checks, with zero measured
arena high-water and unchanged free internal/PSRAM totals.

There are **33,360 signed-zero word differences**, with the same per-case counts
in native and target execution. They are primarily the difference between
passing/multiplying a signed zero and selecting an explicit zero; loop sum
initialisation also contributes. This is numeric equality in the declared
screen, **not bit identity or general signed-zero equivalence**. No tolerance
or input was changed after target output was observed.

| Executable group | Cases | Median µs / 256 frames | Observed peak µs |
| --- | ---: | ---: | ---: |
| Pass-gate names and infix spellings | 12 | 50–51 | 50–55 |
| `Param` default gain | 1 | 45 | 49 |
| `elapsed` sample count | 1 | 49 | 53 |
| Lowercase `history` declaration | 1 | 42 | 46 |
| Function-local `History`, two instances | 1 | 42 | 43 |
| Bounded `for` | 1 | 77 | 81 |
| Bounded `while` | 1 | 83 | 88 |
| Bounded `for` with `break`/`continue` | 1 | 94.5 | 99 |

All medians are below 1.63% of the audio period and all observed peaks below
1.71%. Neither CPU-review rule triggers; the existing backlog remains 99
contexts. These timings cover complete authored callbacks, without I²S, UI or
network work. No isolated opcode cost, optimisation gain or hard latency bound
is claimed. All original storage and scheduler precision are preserved.

Seven programs are **not executed**:

| Exact source form | Stage | Recorded rejection |
| --- | --- | --- |
| `param gain(...)` | C++ | Lowercase declaration lowers to unavailable `new param(...)` type |
| `ELAPSED` | C++ | Identifier is not declared |
| `voice`, `VOICE` | C++, separate sources | Identifiers are not declared |
| `constant(...)` | C++ | No declared `constant` helper |
| Multiple-return custom function | Gen frontend | Parser rejects this exact function form |
| `if`/`else if` updating `History` | Gen frontend | AST `BlockStatement` body construction fails |

These are scoped spelling/form failures, not evidence against all parameters,
constants, function definitions, branching or visual Gen. The passing scalar
function with local history remains distinct from the rejected multiple-return
function. Sources and failure-log hashes are retained. External Gen parameter
updates/reset, polyphonic voice context, visual operators, arbitrary bounds,
other function/branch forms and one-frame production callbacks remain pending.

Evidence: [target results](../../../../evidence/xiao-smoke-gen-control-structures.json)
and [native checks plus rejection diagnostics](../../../../evidence/gen-control-structures-native.json).

```sh
python3 tests/fixtures/smoke/gen-control-structures/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_gen_control_structures_reference.py
```
