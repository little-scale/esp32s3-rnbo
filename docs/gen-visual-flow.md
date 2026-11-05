# Visual Gen range, state and multiple-output checks

The batch covers **42 scenarios across 33 exact visual spellings**. **39 pass**, **1 retains an outside-screen result**, and **2 fail target C++ compilation**. The **40 completed XIAO runs check 409,600 output words**, with exact independently hashed right captures and no nonfinite outputs. There are 16,907 within-limit differences and 1,300 observational left zero-sign differences. **2 callbacks** join CPU review, now **164**.

The production importer now lowers fully connected range/conversion and implicit stateful calls, and routes multiple outputs from a single call. Counter has three outputs; cartopol/poltocar have two. A selected output may feed a history. Missing/extra/stale ports, unknown options, disconnected operands and algebraic cycles still fail closed. Historical core/maths snapshots retain their identities: all 122 earlier graph lowerings are unchanged. The new flow snapshot is separately immutable.

Each source is an original embedded dsp.gen graph, without authored/cached GenExpr. Four manual warm and sixteen timed 256-frame callbacks run continuously at 44,100 Hz, with zero automatic warmup or host resets between blocks. Authored signal reset inputs remain active in their own cases. Stateful inputs change per sample, and late controls/data differ from the next block's first values, exposing incorrect block resets. This checks sample-by-sample state within the fixed 256-frame module ABI, not a one-frame I²S deadline.

| Exact visual spelling | Scenario / outlet | Output screen | Callback CPU | Median / peak µs | Review |
| --- | --- | --- | ---: | ---: | --- |
| [<code>delta</code>](../tests/fixtures/smoke/gen-visual-flow/visual-delta.rnbopat) | visual-delta / 0 | Pass | 0.78% | 45.5 / 50 | — |
| [<code>change</code>](../tests/fixtures/smoke/gen-visual-flow/visual-change.rnbopat) | visual-change / 0 | Pass | 0.91% | 53 / 53 | — |
| [<code>dcblock</code>](../tests/fixtures/smoke/gen-visual-flow/visual-dcblock.rnbopat) | visual-dcblock / 0 | Pass | 5.13% | 298 / 303 | — |
| [<code>latch</code>](../tests/fixtures/smoke/gen-visual-flow/visual-latch.rnbopat) | visual-latch / 0 | Pass | 0.84% | 49 / 54 | — |
| [<code>sah</code>](../tests/fixtures/smoke/gen-visual-flow/visual-sah-zero.rnbopat) | visual-sah-zero / 0 | Pass | 0.95% | 55 / 59 | — |
| [<code>sah</code>](../tests/fixtures/smoke/gen-visual-flow/visual-sah-half.rnbopat) | visual-sah-half / 0 | Pass | 0.95% | 55 / 60 | — |
| [<code>sah</code>](../tests/fixtures/smoke/gen-visual-flow/visual-sah-signal.rnbopat) | visual-sah-signal / 0 | Pass | 0.98% | 57 / 62 | — |
| [<code>slide</code>](../tests/fixtures/smoke/gen-visual-flow/visual-slide-up2-down4.rnbopat) | visual-slide-up2-down4 / 0 | Pass | 3.63% | 211 / 216 | — |
| [<code>slide</code>](../tests/fixtures/smoke/gen-visual-flow/visual-slide-up4-down2.rnbopat) | visual-slide-up4-down2 / 0 | Pass | 3.63% | 211 / 216 | — |
| [<code>accum</code>](../tests/fixtures/smoke/gen-visual-flow/visual-accum-reset-zero.rnbopat) | visual-accum-reset-zero / 0 | Pass | 0.78% | 45 / 50 | — |
| [<code>accum</code>](../tests/fixtures/smoke/gen-visual-flow/visual-accum-reset-signal.rnbopat) | visual-accum-reset-signal / 0 | Pass | 0.84% | 49 / 53 | — |
| [<code>plusequals</code>](../tests/fixtures/smoke/gen-visual-flow/visual-plusequals-reset-zero.rnbopat) | visual-plusequals-reset-zero / 0 | Pass | 0.79% | 46 / 46 | — |
| [<code>plusequals</code>](../tests/fixtures/smoke/gen-visual-flow/visual-plusequals-reset-signal.rnbopat) | visual-plusequals-reset-signal / 0 | Pass | 0.84% | 49 / 49 | — |
| [<code>counter</code>](../tests/fixtures/smoke/gen-visual-flow/visual-counter-out0.rnbopat) | visual-counter-out0 / 0 | Pass | 0.84% | 49 / 53 | — |
| [<code>counter</code>](../tests/fixtures/smoke/gen-visual-flow/visual-counter-out1.rnbopat) | visual-counter-out1 / 1 | Pass | 0.84% | 49 / 54 | — |
| [<code>counter</code>](../tests/fixtures/smoke/gen-visual-flow/visual-counter-out2.rnbopat) | visual-counter-out2 / 2 | Pass | 0.81% | 47 / 47 | — |
| [<code>clamp</code>](../tests/fixtures/smoke/gen-visual-flow/visual-clamp.rnbopat) | visual-clamp / 0 | Pass | 0.84% | 49 / 53 | — |
| [<code>clip</code>](../tests/fixtures/smoke/gen-visual-flow/visual-clip.rnbopat) | visual-clip / 0 | Pass | 0.84% | 49 / 49 | — |
| [<code>fold</code>](../tests/fixtures/smoke/gen-visual-flow/visual-fold.rnbopat) | visual-fold / 0 | Pass | 0.95% | 55 / 59 | — |
| [<code>wrap</code>](../tests/fixtures/smoke/gen-visual-flow/visual-wrap.rnbopat) | visual-wrap / 0 | Pass | 1.05% | 61 / 62 | — |
| [<code>mix</code>](../tests/fixtures/smoke/gen-visual-flow/visual-mix.rnbopat) | visual-mix / 0 | Pass | 0.91% | 53 / 58 | — |
| [<code>smoothstep</code>](../tests/fixtures/smoke/gen-visual-flow/visual-smoothstep.rnbopat) | visual-smoothstep / 0 | Pass | 1.07% | 62 / 63 | — |
| [<code>scale</code>](../tests/fixtures/smoke/gen-visual-flow/visual-scale.rnbopat) | visual-scale / 0 | Pass | 0.95% | 55 / 56 | — |
| [<code>interp</code>](../tests/fixtures/smoke/gen-visual-flow/visual-interp.rnbopat) | visual-interp / 0 | Pass | 0.90% | 52 / 56 | — |
| [<code>phasewrap</code>](../tests/fixtures/smoke/gen-visual-flow/visual-phasewrap.rnbopat) | visual-phasewrap / 0 | Pass | 1.21% | 70.5 / 75 | — |
| [<code>pass</code>](../tests/fixtures/smoke/gen-visual-flow/visual-pass.rnbopat) | visual-pass / 0 | Pass | 0.72% | 42 / 43 | — |
| [<code>fixnan</code>](../tests/fixtures/smoke/gen-visual-flow/visual-fixnan.rnbopat) | visual-fixnan / 0 | Pass | 0.78% | 45 / 45 | — |
| [<code>isnan</code>](../tests/fixtures/smoke/gen-visual-flow/visual-isnan.rnbopat) | visual-isnan / 0 | Pass | 0.83% | 48 / 52 | — |
| [<code>absdiff</code>](../tests/fixtures/smoke/gen-visual-flow/visual-absdiff.rnbopat) | visual-absdiff / 0 | Pass | 0.78% | 45.5 / 50 | — |
| [<code>mod</code>](../tests/fixtures/smoke/gen-visual-flow/visual-mod.rnbopat) | visual-mod / 0 | C++ failure | — | — | — |
| [<code>%</code>](../tests/fixtures/smoke/gen-visual-flow/visual-mod-symbol.rnbopat) | visual-mod-symbol / 0 | C++ failure | — | — | — |
| [<code>triangle</code>](../tests/fixtures/smoke/gen-visual-flow/visual-triangle.rnbopat) | visual-triangle / 0 | Pass | 2.45% | 142 / 143 | — |
| [<code>cartopol</code>](../tests/fixtures/smoke/gen-visual-flow/visual-cartopol-out0.rnbopat) | visual-cartopol-out0 / 0 | Pass | 7.87% | 457 / 460 | — |
| [<code>cartopol</code>](../tests/fixtures/smoke/gen-visual-flow/visual-cartopol-out1.rnbopat) | visual-cartopol-out1 / 1 | Pass | 7.79% | 452 / 457 | — |
| [<code>poltocar</code>](../tests/fixtures/smoke/gen-visual-flow/visual-poltocar-out0.rnbopat) | visual-poltocar-out0 / 0 | Pass | 5.10% | 296 / 300 | — |
| [<code>poltocar</code>](../tests/fixtures/smoke/gen-visual-flow/visual-poltocar-out1.rnbopat) | visual-poltocar-out1 / 1 | Pass | 5.02% | 291.5 / 296 | — |
| [<code>mtof</code>](../tests/fixtures/smoke/gen-visual-flow/visual-mtof.rnbopat) | visual-mtof / 0 | Pass | 3.41% | 198 / 203 | — |
| [<code>ftom</code>](../tests/fixtures/smoke/gen-visual-flow/visual-ftom.rnbopat) | visual-ftom / 0 | Outside screen | 3.97% | 230.5 / 236 | — |
| [<code>atodb</code>](../tests/fixtures/smoke/gen-visual-flow/visual-atodb.rnbopat) | visual-atodb / 0 | Pass | 5.47% | 317.5 / 324 | — |
| [<code>dbtoa</code>](../tests/fixtures/smoke/gen-visual-flow/visual-dbtoa.rnbopat) | visual-dbtoa / 0 | Pass | 126.77% | 7359 / 7363 | Queued |
| [<code>t60</code>](../tests/fixtures/smoke/gen-visual-flow/visual-t60.rnbopat) | visual-t60 / 0 | Pass | 48.44% | 2812 / 2812 | Queued |
| [<code>t60time</code>](../tests/fixtures/smoke/gen-visual-flow/visual-t60time.rnbopat) | visual-t60time / 0 | Pass | 5.27% | 306 / 311 | — |

## Compatibility and memory findings

**Modulo:** both original `mod` and `%` graphs export and prepare but fail C++ compilation with an undefined `safemod` helper, on native and target compilers. Their original source/lowering and compiler-log identities remain visible. Neither has target execution, output, callback CPU or finalisation evidence.

**Fractional ftom:** the original fractional-note reference is retained. Its two quarter-tone test inputs differ by 0.25 notes in native and XIAO execution. This is a scoped rounding-policy finding, not an ESP32-only failure. No rounded replacement oracle or wider tolerance is introduced.

- `visual-ftom`: 640 outside-screen words, maximum error 0.25, fixed limit 0.000500000024.

**Mtof storage:** the unchanged source completes with an explicit **1,048,576-byte arena**, using **262,208 bytes**. Generated initialization allocates a 65,536-sample lookup buffer, although the selected processing branch computes the exponential directly. The earlier native 4 KiB arena attempt aborts before output; it is retained separately and was not run on target. The extra storage is a future optimisation candidate, not a measured saving. Other completed sources use 4 KiB arenas.

**Declared policies:** counter retains the earlier increment-before-output screen, now separately tested at all three visual outlets with max 7 and reset 0. Other increments, reset/initial-value policies and limits remain unqualified. `fixnan` and `isnan` only receive finite inputs; no NaN-repair guarantee is claimed. Exact input words define the finite vectors; interval metadata describes the values before their binary32 conversion.

The initial port draft omitted explicit scale exponent and MIDI tuning inputs. Those three graphs were corrected against primary Gen references before native/device execution; all 42 intended reference streams and limits are unchanged. The draft sources/lowerer are archived without qualification. Native exact-difference counters and per-source maximum errors are separate from target outside-limit counts.

## Performance and remaining scope

- `visual-dbtoa`: median 7359µs, peak 7363µs, **126.77%** of the 256-frame period.
- `visual-t60`: median 2812µs, peak 2812µs, **48.44%** of the 256-frame period.

These are complete compiled callbacks including the raw pilot, not isolated opcode costs, total chip CPU or optimisation gains. A callback above 100% cannot meet this block period in the measured form; the offline smoke image does not run I²S/UI/Wi-Fi. All completed images finalise and pass runtime allocation/memory gates. Limits and precision are unchanged; optimisation is unassessed.

The normal player, original Main and controls are restored; frames advance and runtime faults remain zero. This separate visual report adds no RNBO inventory rows: the table stays at 1056 scoped outcomes. Other visual operators/attributes, parameters, resources, resets, nested/file/codebox forms, wider domains and remaining RNBO/GenExpr qualification keep the full goal active.

Evidence: [machine-readable report](../evidence/gen-visual-flow-status.json), [native](../evidence/gen-visual-flow-native.json), [build ledger](../evidence/gen-visual-flow-builds.json), [initial attempts](../evidence/gen-visual-flow-initial-attempts.json), [restoration](../evidence/xiao-smoke-gen-visual-flow-player-restoration.json).
