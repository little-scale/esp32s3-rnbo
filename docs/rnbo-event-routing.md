# RNBO numeric and list routing checks

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The full source ledger contains **62 scenarios across 30 exact spellings**. **58 complete their XIAO output checks**, **one original positive-rotation case faults in a target event**, and **three literal-message forms fail target C++ compilation**. The completed cases check **593,920 output words** and **1,276 control actions**. Every completed right-channel capture matches; no nonfinite output or outside-limit word occurs. The CPU review queue reaches **157**, with 0 new callback flags.

This is functionality coverage with explicit gaps, not 62 hardware passes or full mode qualification. Each alias has its own source. `pak` is checked through a non-left inlet as well as all inputs; `routepass` retains the selector while `route` removes it. The sources cover all gate outlets, switch inputs/closed state, split/select routes, swap outlet order, packing/unpacking, list rotations/slices/extraction/replacement/sorting/intersection and message-box controls.

One arm action opens an initially closed input gate, followed by 21 drive actions with repeats and ordered same-callback updates. The drive encodes an integer tag 0…3 and an independent 3-bit fractional payload. Lists are deliberately unsorted and include duplicates. Actual and normalised parameter readbacks are checked by ID. Four manual warm and sixteen timed 256-frame callbacks are all compared, with no automatic warm callbacks. All numeric limits are zero.

List output uses `length × 32768 + Σ(item[i] × 8ⁱ)`. For up to five items in 0…7 this is injective, distinguishes trailing zeros and list length, and is exact in binary32. Numeric and emitted-bang-count outputs are checked directly. A separately hashed raw right pilot includes signed zeros, subnormals and finite extrema. The five message controls pass native checks; only the two shorter controls compile for XIAO. Five-element lists are also checked through other target list transformations.

| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Setter total / peak µs |
| --- | --- | --- | ---: | ---: | ---: |
| [`append`](../tests/fixtures/smoke/rnbo-event-routing/append-two-values.rnbopat) | append-two-values | Pass | 75.5 / 80 | 1.30% | 298 / 31 |
| [`prepend`](../tests/fixtures/smoke/rnbo-event-routing/prepend-two-values.rnbopat) | prepend-two-values | Pass | 76 / 80 | 1.31% | 302 / 37 |
| [`join`](../tests/fixtures/smoke/rnbo-event-routing/join-two-inputs.rnbopat) | join-two-inputs | Pass | 75.5 / 76 | 1.30% | 318 / 38 |
| [`list.join`](../tests/fixtures/smoke/rnbo-event-routing/list-join-two-values.rnbopat) | list-join-two-values | Pass | 75.5 / 80 | 1.30% | 301 / 32 |
| [`list.rev`](../tests/fixtures/smoke/rnbo-event-routing/list-reverse.rnbopat) | list-reverse | Pass | 76 / 76 | 1.31% | 280 / 40 |
| [`list.rot`](../tests/fixtures/smoke/rnbo-event-routing/list-rotate-left.rnbopat) | list-rotate-left | Pass | 76 / 76 | 1.31% | 339 / 45 |
| [`list.rot`](../tests/fixtures/smoke/rnbo-event-routing/list-rotate-right.rnbopat) | list-rotate-right | Target event fault | — | — | — |
| [`list.slice`](../tests/fixtures/smoke/rnbo-event-routing/list-slice-out0.rnbopat) | list-slice-out0 | Pass | 75 / 76 | 1.29% | 304 / 38 |
| [`list.slice`](../tests/fixtures/smoke/rnbo-event-routing/list-slice-out1.rnbopat) | list-slice-out1 | Pass | 76 / 76 | 1.31% | 305 / 37 |
| [`list.ecils`](../tests/fixtures/smoke/rnbo-event-routing/list-ecils-out0.rnbopat) | list-ecils-out0 | Pass | 75.5 / 76 | 1.30% | 308 / 40 |
| [`list.ecils`](../tests/fixtures/smoke/rnbo-event-routing/list-ecils-out1.rnbopat) | list-ecils-out1 | Pass | 75 / 76 | 1.29% | 310 / 41 |
| [`list.sub`](../tests/fixtures/smoke/rnbo-event-routing/list-sub-out0.rnbopat) | list-sub-out0 | Pass | 76 / 76 | 1.31% | 265 / 37 |
| [`list.sub`](../tests/fixtures/smoke/rnbo-event-routing/list-sub-out1.rnbopat) | list-sub-out1 | Pass | 75 / 76 | 1.29% | 218 / 32 |
| [`list.sect`](../tests/fixtures/smoke/rnbo-event-routing/list-intersection.rnbopat) | list-intersection | Pass | 76 / 80 | 1.31% | 268 / 35 |
| [`list.swap`](../tests/fixtures/smoke/rnbo-event-routing/list-swap-zero-two.rnbopat) | list-swap-zero-two | Pass | 76 / 80 | 1.31% | 320 / 40 |
| [`list.sort`](../tests/fixtures/smoke/rnbo-event-routing/list-sort-ascending.rnbopat) | list-sort-ascending | Pass | 76 / 76 | 1.31% | 388 / 62 |
| [`list.sort`](../tests/fixtures/smoke/rnbo-event-routing/list-sort-descending.rnbopat) | list-sort-descending | Pass | 75 / 76 | 1.29% | 378 / 60 |
| [`list.median`](../tests/fixtures/smoke/rnbo-event-routing/list-median.rnbopat) | list-median | Pass | 76 / 76 | 1.31% | 295 / 50 |
| [`list.sum`](../tests/fixtures/smoke/rnbo-event-routing/list-sum.rnbopat) | list-sum | Pass | 76 / 81 | 1.31% | 199 / 32 |
| [`list.len`](../tests/fixtures/smoke/rnbo-event-routing/list-len.rnbopat) | list-len | Pass | 76 / 76 | 1.31% | 184 / 31 |
| [`list.nth`](../tests/fixtures/smoke/rnbo-event-routing/list-nth-element.rnbopat) | list-nth-element | Pass | 75.5 / 76 | 1.30% | 241 / 38 |
| [`list.nth`](../tests/fixtures/smoke/rnbo-event-routing/list-nth-replacement.rnbopat) | list-nth-replacement | Pass | 76 / 76 | 1.31% | 315 / 50 |
| [`list.mth`](../tests/fixtures/smoke/rnbo-event-routing/list-mth-out0.rnbopat) | list-mth-out0 | Pass | 76 / 80 | 1.31% | 239 / 37 |
| [`list.mth`](../tests/fixtures/smoke/rnbo-event-routing/list-mth-out1.rnbopat) | list-mth-out1 | Pass | 76 / 81 | 1.31% | 314 / 54 |
| [`list.index`](../tests/fixtures/smoke/rnbo-event-routing/list-index-out0.rnbopat) | list-index-out0 | Pass | 75 / 76 | 1.29% | 239 / 37 |
| [`list.index`](../tests/fixtures/smoke/rnbo-event-routing/list-index-out1.rnbopat) | list-index-out1 | Pass | 76 / 77 | 1.31% | 314 / 53 |
| [`pak`](../tests/fixtures/smoke/rnbo-event-routing/pak-all-inputs.rnbopat) | pak-all-inputs | Pass | 76 / 80 | 1.31% | 381 / 41 |
| [`pak`](../tests/fixtures/smoke/rnbo-event-routing/pak-cold-input.rnbopat) | pak-cold-input | Pass | 75.5 / 76 | 1.30% | 246 / 33 |
| [`unpack`](../tests/fixtures/smoke/rnbo-event-routing/unpack-out0.rnbopat) | unpack-out0 | Pass | 75.5 / 76 | 1.30% | 188 / 33 |
| [`unpack`](../tests/fixtures/smoke/rnbo-event-routing/unpack-out1.rnbopat) | unpack-out1 | Pass | 76 / 76 | 1.31% | 189 / 37 |
| [`unpack`](../tests/fixtures/smoke/rnbo-event-routing/unpack-out2.rnbopat) | unpack-out2 | Pass | 76 / 80 | 1.31% | 188 / 33 |
| [`unjoin`](../tests/fixtures/smoke/rnbo-event-routing/unjoin-single-out0.rnbopat) | unjoin-single-out0 | Pass | 75 / 76 | 1.29% | 208 / 31 |
| [`unjoin`](../tests/fixtures/smoke/rnbo-event-routing/unjoin-single-out1.rnbopat) | unjoin-single-out1 | Pass | 76 / 76 | 1.31% | 208 / 32 |
| [`unjoin`](../tests/fixtures/smoke/rnbo-event-routing/unjoin-single-out2.rnbopat) | unjoin-single-out2 | Pass | 76 / 80 | 1.31% | 287 / 44 |
| [`unjoin`](../tests/fixtures/smoke/rnbo-event-routing/unjoin-pair-out0.rnbopat) | unjoin-pair-out0 | Pass | 75.5 / 79 | 1.30% | 279 / 40 |
| [`unjoin`](../tests/fixtures/smoke/rnbo-event-routing/unjoin-pair-out1.rnbopat) | unjoin-pair-out1 | Pass | 75.5 / 81 | 1.30% | 278 / 37 |
| [`message`](../tests/fixtures/smoke/rnbo-event-routing/message-observer-1.rnbopat) | message-observer-1 | Pass | 75.5 / 80 | 1.30% | 229 / 33 |
| [`message`](../tests/fixtures/smoke/rnbo-event-routing/message-observer-2.rnbopat) | message-observer-2 | Pass | 75 / 76 | 1.29% | 230 / 32 |
| [`message`](../tests/fixtures/smoke/rnbo-event-routing/message-observer-3.rnbopat) | message-observer-3 | C++ failure | — | — | — |
| [`message`](../tests/fixtures/smoke/rnbo-event-routing/message-observer-4.rnbopat) | message-observer-4 | C++ failure | — | — | — |
| [`message`](../tests/fixtures/smoke/rnbo-event-routing/message-observer-5.rnbopat) | message-observer-5 | C++ failure | — | — | — |
| [`route`](../tests/fixtures/smoke/rnbo-event-routing/route-out0.rnbopat) | route-out0 | Pass | 76 / 80 | 1.31% | 278 / 32 |
| [`route`](../tests/fixtures/smoke/rnbo-event-routing/route-out1.rnbopat) | route-out1 | Pass | 76 / 76 | 1.31% | 287 / 40 |
| [`route`](../tests/fixtures/smoke/rnbo-event-routing/route-out2.rnbopat) | route-out2 | Pass | 76 / 80 | 1.31% | 295 / 36 |
| [`routepass`](../tests/fixtures/smoke/rnbo-event-routing/routepass-out0.rnbopat) | routepass-out0 | Pass | 76 / 80 | 1.31% | 257 / 32 |
| [`routepass`](../tests/fixtures/smoke/rnbo-event-routing/routepass-out1.rnbopat) | routepass-out1 | Pass | 76 / 80 | 1.31% | 241 / 32 |
| [`routepass`](../tests/fixtures/smoke/rnbo-event-routing/routepass-out2.rnbopat) | routepass-out2 | Pass | 76 / 81 | 1.31% | 278 / 42 |
| [`gate`](../tests/fixtures/smoke/rnbo-event-routing/gate-out0.rnbopat) | gate-out0 | Pass | 76 / 80 | 1.31% | 171 / 32 |
| [`gate`](../tests/fixtures/smoke/rnbo-event-routing/gate-out1.rnbopat) | gate-out1 | Pass | 76 / 80 | 1.31% | 167 / 31 |
| [`gate`](../tests/fixtures/smoke/rnbo-event-routing/gate-out2.rnbopat) | gate-out2 | Pass | 76 / 80 | 1.31% | 171 / 35 |
| [`switch`](../tests/fixtures/smoke/rnbo-event-routing/switch-three-inputs.rnbopat) | switch-three-inputs | Pass | 75 / 80 | 1.29% | 175 / 33 |
| [`split`](../tests/fixtures/smoke/rnbo-event-routing/split-out0.rnbopat) | split-out0 | Pass | 77 / 81 | 1.33% | 159 / 31 |
| [`split`](../tests/fixtures/smoke/rnbo-event-routing/split-out1.rnbopat) | split-out1 | Pass | 77 / 81 | 1.33% | 168 / 33 |
| [`select`](../tests/fixtures/smoke/rnbo-event-routing/select-out0.rnbopat) | select-out0 | Pass | 75.5 / 80 | 1.30% | 167 / 32 |
| [`select`](../tests/fixtures/smoke/rnbo-event-routing/select-out1.rnbopat) | select-out1 | Pass | 76 / 81 | 1.31% | 174 / 33 |
| [`select`](../tests/fixtures/smoke/rnbo-event-routing/select-out2.rnbopat) | select-out2 | Pass | 76 / 80 | 1.31% | 172 / 33 |
| [`sel`](../tests/fixtures/smoke/rnbo-event-routing/sel-out0.rnbopat) | sel-out0 | Pass | 76 / 80 | 1.31% | 167 / 31 |
| [`sel`](../tests/fixtures/smoke/rnbo-event-routing/sel-out1.rnbopat) | sel-out1 | Pass | 75 / 76 | 1.29% | 172 / 33 |
| [`sel`](../tests/fixtures/smoke/rnbo-event-routing/sel-out2.rnbopat) | sel-out2 | Pass | 76 / 80 | 1.31% | 178 / 41 |
| [`swap`](../tests/fixtures/smoke/rnbo-event-routing/swap-out0.rnbopat) | swap-out0 | Pass | 77 / 82 | 1.33% | 171 / 32 |
| [`swap`](../tests/fixtures/smoke/rnbo-event-routing/swap-out1.rnbopat) | swap-out1 | Pass | 77 / 81 | 1.33% | 173 / 31 |
| [`swap`](../tests/fixtures/smoke/rnbo-event-routing/swap-right-before-left.rnbopat) | swap-right-before-left | Pass | 75.5 / 76 | 1.30% | 180 / 31 |

## Compatibility gaps

- **`list.rot 1`:** the original source is tested alone on XIAO. Arming succeeds; the first drive event (0.125) returns `RNBO_S3_FAULT` (-4), while parameter readback succeeds. Native preflight records the same event stage/status. No output callback completes, so no numerical pass, raw-right result, normal callback CPU or finalisation/memory claim is made for this source. Its fault is separate from the passing negative rotation. The cause still needs investigation.

- **Three longer literal-message forms:** `[0 0 0]`, `[1 2 3 0]` and `[7 0 1 4 5]` reach a target compiler array-bounds error in the RNBO variadic list constructor. The original warnings are not disabled. They execute correctly in native preflight, which does not qualify target execution or prove the target diagnostic is harmless. Two shorter literal controls pass XIAO output checks.

The initially flagged `list.sect` and `list.sub` comparisons were **fixture observation mistakes**: the original graphs watched only the data outlet and assumed an empty list would arrive on no match. The documented intersection no-match bang and sub-list zero-count outlet are now observed explicitly to supply code 0. Only those two observation graphs change. **All 62 expected streams and all zero-error limits remain unchanged.** Original graphs/catalogs, native observations and three initial hardware partitions are archived; their two initial comparison differences are not object defects.

## Performance and remaining work

List/routing work runs in setters; their totals and peaks cover all 22 actions, including arming and observer work. The timed audio callback mainly renders the held code/scalar and raw pilot. These are whole compiled contexts, not isolated operation costs or matched optimisation gains. Optimisation remains unassessed; no saving percentage is claimed. The fault response timing is a separate single failed event and is not normal callback CPU.

All 58 completed images finalise and pass allocation/memory gates. The fault probe aborts at the recorded event check and makes no finalisation claim. The normal player, saved Main and controls are restored afterwards; USB audio-frame progress and zero runtime faults are checked. Other lengths/types/options, larger or negative list domains, within-block host offsets and remaining RNBO/Gen forms keep the full qualification goal active.

Evidence: [machine-readable report](../evidence/rnbo-event-routing-status.json), [native](../evidence/rnbo-event-routing-native.json), [build ledger](../evidence/rnbo-event-routing-builds.json), [target fault](../evidence/xiao-event-routing-rotation-fault.json), [initial observation screens](../evidence/rnbo-event-routing-initial-screens.json), [restoration](../evidence/xiao-smoke-rnbo-event-routing-player-restoration.json).
