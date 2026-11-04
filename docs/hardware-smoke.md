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

Supply normal prepared exports matching the selected catalog. The numeric Gen, RNBO stateless and RNBO numeric catalogs have separate
independent references. Numeric cases carry their own input-vector hashes and
predeclared tolerances; older catalogs keep the original exact gate.
The initial fast
builder supports strict, self-contained two-input/two-output FX modules without
parameters; additional object shapes will be added as coverage expands. The
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
