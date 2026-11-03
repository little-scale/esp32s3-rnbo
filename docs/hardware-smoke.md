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
  --modules-report build/smoke-modules/batch-01/batch-report.json \
  --build-dir build/smoke/batch-01 \
  --cache-build-dir build/hardware-smoke-cache-xiao
```

Supply normal prepared exports matching the selected catalog. The initial fast
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
