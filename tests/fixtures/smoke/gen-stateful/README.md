# Original GenExpr sample-state smoke fixtures

> **Recorded development material.** The supported intake is now [Max Minimal C++ Export](../../../../docs/native-export.md). Any importer commands or qualification results below are historical, not native-export qualification.

These 12 MIT-authored programs cover nine exact GenExpr spellings: `delta`, `change`, `latch`, `dcblock`, `sah`, `slide`, `accum`, `plusequals` and `counter`. Each self-contained RNBO patch has two signal inputs and outputs, no parameters or events, and uses the normal strict 44.1 kHz/256-frame module profile. History was tested earlier and is not counted as a new object here.

| Model | Program scope |
| --- | --- |
| 104 | `delta` independently on both planes, previous input initially 0 |
| 105 | `change` independently on both planes, previous input initially 0 |
| 106 | `latch` with reversed input/control lanes, initially holding 0 |
| 107 | `dcblock` independently on both planes |
| 108–110 | `sah` with default threshold 0, fixed threshold 0.5, and signal threshold equal to the data input |
| 111–112 | `slide` with fixed up/down rates 2/4 and 4/2 |
| 113 | Separate `accum(input, 0)` and `plusequals(input, 0)` fixtures, initially 0 |
| 114 | Two `counter(1, 0, maximum)` instances with maxima 7 and 5; count outputs only |

The `gen-stateful` harness must use **zero automatic SDK warm-up blocks**. It compares four manual warm-up callbacks followed by sixteen timed callbacks, carrying state continuously across all 20 calls. Inputs repeat every 256 frames. `reference_blocks()` supplies the complete 20-block expectation; repeating only its first block is incorrect.

The independent input vectors place zero controls at frame 0 and meaningful held values near the block end. Delta, change, latch and sampling tests therefore observe history across the 255/256 boundary. Accumulator increments are small exact dyadics with a nonzero sum per block. Counter periods 7 and 5 do not divide 256. The reference uses declared increment-before-output counter ordering; primary prose does not explicitly settle first-frame ordering, so a discrepancy remains visible rather than being fitted to the implementation.

`reference.py` derives the mathematical state equations independently of generated DSP. DCblock and slide have fixed absolute tolerance `2e-6`, selected before execution. Other models use exact numerical comparisons, with signed-zero differences reported separately. These programs do not cover reset modes, nonzero initial attributes, counter carry outputs, arbitrary rates or external resources. Accumulator reset stays at literal 0; multiplication accumulation with default initial 0 was omitted because its output would be trivial.

All 12 original programs exported, prepared and compiled with zero imports in the initial build. Compilation alone does not establish sample-state execution or real-time performance; hardware records are separate. Each spelling and argument form retains its own result, with no alias inheritance or DSP fixes.

Example module preparation with an authorized RNBO 1.4.4 installation:

```sh
node host/export/export.mjs tests/fixtures/smoke/gen-stateful/delta-call.rnbopat --out build/smoke-stateful/raw/delta-call
python3 host/compiler/prepare.py --export build/smoke-stateful/raw/delta-call --out build/smoke-stateful/prepared/delta-call --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke-stateful/prepared --base-build PATH_TO_REVIEWED_MODULE_CACHE --out build/smoke-stateful/modules
```

Only the original `.genexpr`, `.rnbopat` and compact metadata are public. Generated RNBO C++ and runtime headers remain in ignored build directories with their upstream notices.
