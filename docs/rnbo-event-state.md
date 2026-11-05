# RNBO ordered event-state checks

The XIAO executes **36 scenarios across 15 exact spellings**: **36 pass** their fixed output screens; **0 retain outside-screen differences**. The batch checks **368,640 output words**, **756 drive events** and **36 arm actions**. Every raw right-channel capture matches and no nonfinite output occurs. The CPU review queue remains at 157 before this batch and reaches **157** afterwards.

The sources cover additive/multiplicative prefixes and neutral resets, closed/open/switched latches, changed-value sums and zero/nonzero transition counts, four bounded counter directions/ranges and immediate/next resets, all peak/trough numeric outlets, asymmetric slide/rampsmooth state, sample-and-hold threshold edges, and right-before-left trigger ordering. Each alias has its own authored graphs and executions. Only these forms and domains are qualified.

Each graph has two parameters: `drive` (-8…8, initial 0) and `arm` (0…1, initial 0). A closed `gate 1 0` blocks startup drive notifications. The first controlled action sets arm to 1; its right-to-left trigger seeds counter/peak/trough cold inputs before opening the gate. The following 21 drive actions include repeats, held callbacks and three ordered changes before callback 10. This makes the initial state explicit and independent of startup notification order. All actual/normalised readbacks are checked by parameter ID. Auxiliary gate/observer objects gain no inferred qualification.

References use independent prefix sums/products, bounded index sequences, event-change/edge predicates and exact rational smoothing trajectories. Only slide/rampsmooth allow a predeclared 2e-6 absolute output difference; all other numeric limits are zero. Additive resets use hot input 0, multiplicative resets use hot input 1, so reset/input precedence cannot obscure reset-state checks. Counter reset-next values include values outside its bounds, as documented. Four manual warm callbacks and sixteen timed callbacks are all checked, with no automatic warmup. The right pilot has a separate hash over 5,120 raw words, including signed zeros, subnormals and finite extrema.

| Exact spelling | Scenario | Outlet | Output screen | Median / peak µs | Callback CPU | Setter total / peak µs |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| [`accum`](../tests/fixtures/smoke/rnbo-event-state/accum-prefix.rnbopat) | prefix | 0 | Pass | 76 / 80 | 1.31% | 169 / 34 |
| [`accum`](../tests/fixtures/smoke/rnbo-event-state/accum-neutral-reset.rnbopat) | neutral-reset | 0 | Pass | 76 / 80 | 1.31% | 166 / 36 |
| [`plusequals`](../tests/fixtures/smoke/rnbo-event-state/plusequals-prefix.rnbopat) | prefix | 0 | Pass | 75 / 80 | 1.29% | 165 / 34 |
| [`plusequals`](../tests/fixtures/smoke/rnbo-event-state/plusequals-neutral-reset.rnbopat) | neutral-reset | 0 | Pass | 76 / 80 | 1.31% | 164 / 34 |
| [`+=`](../tests/fixtures/smoke/rnbo-event-state/plus-assign-prefix.rnbopat) | prefix | 0 | Pass | 76 / 80 | 1.31% | 163 / 34 |
| [`+=`](../tests/fixtures/smoke/rnbo-event-state/plus-assign-neutral-reset.rnbopat) | neutral-reset | 0 | Pass | 75 / 76 | 1.29% | 165 / 34 |
| [`mulequals`](../tests/fixtures/smoke/rnbo-event-state/mulequals-prefix.rnbopat) | prefix | 0 | Pass | 76 / 81 | 1.31% | 163 / 34 |
| [`mulequals`](../tests/fixtures/smoke/rnbo-event-state/mulequals-neutral-reset.rnbopat) | neutral-reset | 0 | Pass | 76 / 76 | 1.31% | 165 / 33 |
| [`*=`](../tests/fixtures/smoke/rnbo-event-state/multiply-assign-prefix.rnbopat) | prefix | 0 | Pass | 76.5 / 81 | 1.32% | 163 / 33 |
| [`*=`](../tests/fixtures/smoke/rnbo-event-state/multiply-assign-neutral-reset.rnbopat) | neutral-reset | 0 | Pass | 75.5 / 80 | 1.30% | 165 / 33 |
| [`latch`](../tests/fixtures/smoke/rnbo-event-state/latch-closed.rnbopat) | closed | 0 | Pass | 75 / 76 | 1.29% | 163 / 34 |
| [`latch`](../tests/fixtures/smoke/rnbo-event-state/latch-open.rnbopat) | open | 0 | Pass | 75 / 80 | 1.29% | 164 / 34 |
| [`latch`](../tests/fixtures/smoke/rnbo-event-state/latch-positive-control.rnbopat) | positive-control | 0 | Pass | 76 / 76 | 1.31% | 163 / 33 |
| [`change`](../tests/fixtures/smoke/rnbo-event-state/change-changed-value-sum.rnbopat) | changed-value-sum | 0 | Pass | 75 / 80 | 1.29% | 164 / 32 |
| [`change`](../tests/fixtures/smoke/rnbo-event-state/change-rise-count.rnbopat) | rise-count | 1 | Pass | 76 / 80 | 1.31% | 164 / 34 |
| [`change`](../tests/fixtures/smoke/rnbo-event-state/change-fall-count.rnbopat) | fall-count | 2 | Pass | 75.5 / 80 | 1.30% | 158 / 33 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-up.rnbopat) | up | 0 | Pass | 77 / 77 | 1.33% | 167 / 33 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-down.rnbopat) | down | 0 | Pass | 76 / 81 | 1.31% | 169 / 34 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-bounce.rnbopat) | bounce | 0 | Pass | 77 / 81 | 1.33% | 167 / 33 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-negative-up.rnbopat) | negative-up | 0 | Pass | 77 / 77 | 1.33% | 167 / 34 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-reset-next.rnbopat) | reset-next | 0 | Pass | 75 / 80 | 1.29% | 168 / 34 |
| [`counter`](../tests/fixtures/smoke/rnbo-event-state/counter-reset-now.rnbopat) | reset-now | 0 | Pass | 75 / 80 | 1.29% | 167 / 34 |
| [`peak`](../tests/fixtures/smoke/rnbo-event-state/peak-value.rnbopat) | value | 0 | Pass | 77 / 77 | 1.33% | 169 / 39 |
| [`peak`](../tests/fixtures/smoke/rnbo-event-state/peak-new-flag.rnbopat) | new-flag | 1 | Pass | 77 / 77 | 1.33% | 172 / 39 |
| [`peak`](../tests/fixtures/smoke/rnbo-event-state/peak-not-new-flag.rnbopat) | not-new-flag | 2 | Pass | 76 / 77 | 1.31% | 170 / 39 |
| [`trough`](../tests/fixtures/smoke/rnbo-event-state/trough-value.rnbopat) | value | 0 | Pass | 77 / 77 | 1.33% | 179 / 39 |
| [`trough`](../tests/fixtures/smoke/rnbo-event-state/trough-new-flag.rnbopat) | new-flag | 1 | Pass | 77 / 77 | 1.33% | 173 / 39 |
| [`trough`](../tests/fixtures/smoke/rnbo-event-state/trough-not-new-flag.rnbopat) | not-new-flag | 2 | Pass | 76 / 77 | 1.31% | 170 / 39 |
| [`slide`](../tests/fixtures/smoke/rnbo-event-state/slide-up2-down4.rnbopat) | up2-down4 | 0 | Pass | 76 / 80 | 1.31% | 188 / 37 |
| [`slide`](../tests/fixtures/smoke/rnbo-event-state/slide-up4-down8.rnbopat) | up4-down8 | 0 | Pass | 76 / 80 | 1.31% | 181 / 36 |
| [`rampsmooth`](../tests/fixtures/smoke/rnbo-event-state/rampsmooth-up2-down4.rnbopat) | up2-down4 | 0 | Pass | 76 / 80 | 1.31% | 181 / 39 |
| [`rampsmooth`](../tests/fixtures/smoke/rnbo-event-state/rampsmooth-up4-down8.rnbopat) | up4-down8 | 0 | Pass | 75 / 76 | 1.29% | 179 / 38 |
| [`sah`](../tests/fixtures/smoke/rnbo-event-state/sah-threshold-zero.rnbopat) | threshold-zero | 0 | Pass | 75 / 76 | 1.29% | 162 / 32 |
| [`sah`](../tests/fixtures/smoke/rnbo-event-state/sah-threshold-half.rnbopat) | threshold-half | 0 | Pass | 76 / 76 | 1.31% | 164 / 32 |
| [`t`](../tests/fixtures/smoke/rnbo-event-state/t-right-before-left.rnbopat) | right-before-left | 0 | Pass | 76 / 77 | 1.31% | 166 / 38 |
| [`trigger`](../tests/fixtures/smoke/rnbo-event-state/trigger-right-before-left.rnbopat) | right-before-left | 0 | Pass | 77 / 77 | 1.33% | 175 / 44 |

## Numerical and startup findings

There are 3,584 within-limit numeric differences, 768 observational left zero-sign differences and 0 outside-limit words. The right observer remains strict. Native preflight has its own separate counts.

The first native-only fixtures omitted the startup parameter event: the initial drive=0 advanced counters and zeroed product accumulators before the measured sequence. Six of 36 original screens consequently differed. Those original sources, references and native results are archived in `startup-exposed-v1` and the startup-attempt receipt. They are fixture-initialisation findings, not six hardware object failures. No original fixture was flashed. The corrected sources add explicit arming and synchronous cold seeding; **all 36 expected output streams and all numerical limits remain unchanged**. No captured outputs were substituted for expectations.


## Performance scope and remaining qualification

The state operations execute in the event setter/routing path; its total and peak cover all 22 actions, including arming, and are not isolated opcode timings. The timed audio callback mainly renders the held output and right pilot. Callback CPU is callback time divided by the 256-frame period, not total chip CPU. Optimisation remains unassessed and no percentage saving is claimed. Any threshold-crossing callback is retained in the CPU review queue.

All images finalise and allocation/memory gates pass. The normal player, saved Main and live controls are restored; USB frame progress and zero runtime faults are checked. There is no new audio capture or loaded-player deadline claim. Other reset/constructor modes, counter carry outlets, lists, bang/data types beyond authored forms, signal/codebox/Gen counterparts and within-block host event offsets remain unqualified. The full RNBO/Gen goal remains active.

Evidence: [part 1](../evidence/xiao-smoke-rnbo-event-state-part1.json), [part 2](../evidence/xiao-smoke-rnbo-event-state-part2.json), [native preflight](../evidence/rnbo-event-state-native.json), [build ledger](../evidence/rnbo-event-state-builds.json), [original startup attempt](../evidence/rnbo-event-state-startup-attempt.json), [player restoration](../evidence/xiao-smoke-rnbo-event-state-player-restoration.json), [machine-readable report](../evidence/rnbo-event-state-status.json).
