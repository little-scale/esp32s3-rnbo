# RNBO extended list and storage checks

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The batch covers **32 scenarios across 17 exact spellings**. **27 complete output checks pass**, **1 retains a union-policy difference**, and **4 growing FIFO/LIFO scenarios fault in target events**. The completed checks cover **286,720 output words** and **616 control actions**. All completed raw right captures match; no nonfinite output occurs. The CPU queue reaches **157**, with 0 new callback flags.

One arm action opens a startup gate, then 21 ordered drives encode an integer tag and fractional digit. Repeated identical lists exercise suppression/comparison; three drives share callback 10 and two share callback 16. Four manual warm and sixteen timed full 256-frame callbacks are checked at 44,100 Hz, with zero automatic warm callbacks. Parameters are resolved by ID with actual and normalised readbacks. All numerical limits are zero.

List code `length*32768 + sum(item[i]*8**i)` is exact for up to five digits in 0…7 and distinguishes lengths and trailing zeros. Iteration, funnel and changed-list emission observers accumulate bounded code sums below 2^24. Those sums check emitted content totals and suppression; they do not encode arbitrary event order without collisions. Storage-before-bang order is explicit. Auxiliary objects gain no inherited qualification.

| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |
| --- | --- | --- | ---: | ---: | ---: |
| [`list.thin`](../tests/fixtures/smoke/rnbo-list-extended/list-thin.rnbopat) | list-thin | Pass | 76 / 76 | 1.31% | 291 / 41 |
| [`list.unique`](../tests/fixtures/smoke/rnbo-list-extended/list-unique.rnbopat) | list-unique | Pass | 76 / 76 | 1.31% | 318 / 40 |
| [`list.union`](../tests/fixtures/smoke/rnbo-list-extended/list-union.rnbopat) | list-union | Policy difference | 76 / 80 | 1.31% | 335 / 37 |
| [`list.lace`](../tests/fixtures/smoke/rnbo-list-extended/list-lace.rnbopat) | list-lace | Pass | 76 / 76 | 1.31% | 297 / 35 |
| [`list.delace`](../tests/fixtures/smoke/rnbo-list-extended/list-delace-out0.rnbopat) | list-delace-out0 | Pass | 76 / 80 | 1.31% | 312 / 41 |
| [`list.filter`](../tests/fixtures/smoke/rnbo-list-extended/list-filter-out0.rnbopat) | list-filter-out0 | Pass | 76 / 80 | 1.31% | 356 / 49 |
| [`list.compare`](../tests/fixtures/smoke/rnbo-list-extended/list-compare-out0.rnbopat) | list-compare-out0 | Pass | 75 / 76 | 1.29% | 239 / 33 |
| [`list.delace`](../tests/fixtures/smoke/rnbo-list-extended/list-delace-out1.rnbopat) | list-delace-out1 | Pass | 75 / 76 | 1.29% | 302 / 37 |
| [`list.filter`](../tests/fixtures/smoke/rnbo-list-extended/list-filter-out1.rnbopat) | list-filter-out1 | Pass | 76 / 80 | 1.31% | 348 / 48 |
| [`list.compare`](../tests/fixtures/smoke/rnbo-list-extended/list-compare-out1.rnbopat) | list-compare-out1 | Pass | 75 / 80 | 1.29% | 298 / 40 |
| [`list.change`](../tests/fixtures/smoke/rnbo-list-extended/list-change-emission-sum.rnbopat) | list-change-emission-sum | Pass | 76 / 80 | 1.31% | 270 / 32 |
| [`list.change`](../tests/fixtures/smoke/rnbo-list-extended/list-change-flag.rnbopat) | list-change-flag | Pass | 75 / 76 | 1.29% | 215 / 41 |
| [`list.reg`](../tests/fixtures/smoke/rnbo-list-extended/list-reg-hot.rnbopat) | list-reg-hot | Pass | 76 / 80 | 1.31% | 269 / 36 |
| [`list.reg`](../tests/fixtures/smoke/rnbo-list-extended/list-reg-cold-store-bang.rnbopat) | list-reg-cold-store-bang | Pass | 76 / 80 | 1.31% | 278 / 36 |
| [`list.indexmap`](../tests/fixtures/smoke/rnbo-list-extended/list-indexmap.rnbopat) | list-indexmap | Pass | 76 / 80 | 1.31% | 296 / 41 |
| [`list.lookup`](../tests/fixtures/smoke/rnbo-list-extended/list-lookup.rnbopat) | list-lookup | Pass | 75.5 / 80 | 1.30% | 293 / 43 |
| [`list.group`](../tests/fixtures/smoke/rnbo-list-extended/list-group-three.rnbopat) | list-group-three | Pass | 76 / 80 | 1.31% | 242 / 39 |
| [`list.stream`](../tests/fixtures/smoke/rnbo-list-extended/list-stream-forward.rnbopat) | list-stream-forward | Pass | 76 / 76 | 1.31% | 335 / 37 |
| [`list.stream`](../tests/fixtures/smoke/rnbo-list-extended/list-stream-reverse.rnbopat) | list-stream-reverse | Pass | 75 / 76 | 1.29% | 343 / 41 |
| [`list.stream`](../tests/fixtures/smoke/rnbo-list-extended/list-stream-ready.rnbopat) | list-stream-ready | Pass | 76 / 76 | 1.31% | 290 / 35 |
| [`list.queue`](../tests/fixtures/smoke/rnbo-list-extended/list-queue-out0.rnbopat) | list-queue-out0 | Growth event fault | — | — | — |
| [`list.queue`](../tests/fixtures/smoke/rnbo-list-extended/list-queue-out1.rnbopat) | list-queue-out1 | Growth event fault | — | — | — |
| [`list.stack`](../tests/fixtures/smoke/rnbo-list-extended/list-stack-out0.rnbopat) | list-stack-out0 | Growth event fault | — | — | — |
| [`list.stack`](../tests/fixtures/smoke/rnbo-list-extended/list-stack-out1.rnbopat) | list-stack-out1 | Growth event fault | — | — | — |
| [`iter`](../tests/fixtures/smoke/rnbo-list-extended/iter-chunk1.rnbopat) | iter-chunk1 | Pass | 76 / 81 | 1.31% | 446 / 60 |
| [`iter`](../tests/fixtures/smoke/rnbo-list-extended/iter-chunk2.rnbopat) | iter-chunk2 | Pass | 76 / 81 | 1.31% | 380 / 58 |
| [`listfunnel`](../tests/fixtures/smoke/rnbo-list-extended/listfunnel-offset0.rnbopat) | listfunnel-offset0 | Pass | 76 / 81 | 1.31% | 380 / 41 |
| [`listfunnel`](../tests/fixtures/smoke/rnbo-list-extended/listfunnel-offset2.rnbopat) | listfunnel-offset2 | Pass | 76 / 80 | 1.31% | 390 / 49 |
| [`list.queue`](../tests/fixtures/smoke/rnbo-list-extended/list-queue-bounded-out0.rnbopat) | list-queue-bounded-out0 | Pass | 76 / 76 | 1.31% | 244 / 37 |
| [`list.queue`](../tests/fixtures/smoke/rnbo-list-extended/list-queue-bounded-out1.rnbopat) | list-queue-bounded-out1 | Pass | 76 / 80 | 1.31% | 240 / 33 |
| [`list.stack`](../tests/fixtures/smoke/rnbo-list-extended/list-stack-bounded-out0.rnbopat) | list-stack-bounded-out0 | Pass | 75.5 / 80 | 1.30% | 221 / 32 |
| [`list.stack`](../tests/fixtures/smoke/rnbo-list-extended/list-stack-bounded-out1.rnbopat) | list-stack-bounded-out1 | Pass | 76 / 80 | 1.31% | 228 / 32 |

## Findings and limits

**Growing queues/stacks:** the original scenarios push three values and pop one on each drive. Both observed outlets of each object fault on drive eight, before callback seven, with `RNBO_S3_FAULT` (-4) and positive late-platform-allocation statistics. Seven callbacks execute first, but these aborted probes make no completed output, raw-capture or finalisation claim. Four separately authored controls push three and pop three, keeping storage bounded; their normal output checks remain separate from the growth faults. Native preflight finds the same fault stage. These are capacity-growth compatibility gaps to investigate, not callback CPU measurements.

**Union policy:** the installed help says right-list items already present in the left list are omitted. This screen preserves duplicates already inside the left list. The reference XML also describes duplicate removal more broadly. The unchanged screen retains the measured difference in both native and XIAO execution; it is a documented-policy ambiguity to resolve, not proof of an ESP32-only numerical defect. No output-derived oracle replacement or tolerance change is made.

- `list-union`: 1,536 outside-screen words, maximum code difference 47680, original limit 0.

Event/routing/observer work is measured in setters separately from callbacks rendering held outputs and the raw pilot. The table reports complete fixture costs, not isolated object costs or optimisation gains. All completed images finalise and pass memory/allocation gates. The normal player, saved Main and controls are restored after all probes, with frame progress and zero runtime faults checked.

Other list lengths/types, reset modes, empty/invalid indexing, larger storage, random list operations, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.

Evidence: [machine-readable report](../evidence/rnbo-list-extended-status.json), [native preflight](../evidence/rnbo-list-extended-native.json), [build ledger](../evidence/rnbo-list-extended-builds.json), [player restoration](../evidence/xiao-smoke-rnbo-list-extended-player-restoration.json).
