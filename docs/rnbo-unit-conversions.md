# RNBO event and signal unit conversions

The XIAO executes **36 exact spellings**: **35 pass** their predeclared rational output screen and **1 retains a numerical difference**. The batch checks **368,640 output words** and **756 ordered parameter actions**. Every raw right-channel capture matches; no nonfinite output occurs. The CPU review queue reaches **157**, with 1 added by this batch.

The 21 numeric-event forms use `param → conversion → sig~`. The 15 signal forms use `in~ 1 +~ sig~(param) → conversion~`, with 16 distinct left-input levels inside each block. Four manual warm callbacks and sixteen timed callbacks are all checked; there are no automatic warm callbacks. Repeats, held values and three ordered actions before one callback are included. Actual and normalised readbacks are checked. No source spelling inherits another spelling’s result.

References use exact rational dimensional conversions at **44,100 Hz, 120 BPM, 480 ticks per quarter note and stopped 4/4 transport**, rounded once to binary32 at the output. Reciprocal inputs exclude zero. Other linear forms include negative inputs. The separate right pilot covers signed zeros, finite extrema and subnormals; its 5,120 captured words per case are hashed independently of left-channel tolerance.

Limits are fixed in output units before compilation: the largest is 0.008 **samples**, less than 0.2 microseconds at this sample rate. The existing event families retain their original ceilings. The initial hardware harness stopped before its seventh case because it still had the old 0.001 ceiling; the corrected generated header permits this new family’s declared limits. No per-object limit or expected output changed. Original attempt hashes are retained.

| Exact spelling | Output screen | Optimisation | CPU saved | Median / peak µs | Callback CPU | Review |
| --- | --- | --- | --- | ---: | ---: | --- |
| [`beatstohz`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstohz-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`beatstoms`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstoms-event.rnbopat) | Pass | Unassessed | — | 76 / 81 | 1.31% | — |
| [`beatstosamps`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstosamps-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`beatstoticks`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstoticks-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`hztobeats`](../tests/fixtures/smoke/rnbo-unit-conversions/hztobeats-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`hztoms`](../tests/fixtures/smoke/rnbo-unit-conversions/hztoms-event.rnbopat) | Pass | Unassessed | — | 75.5 / 80 | 1.30% | — |
| [`hztosamps`](../tests/fixtures/smoke/rnbo-unit-conversions/hztosamps-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`hztoticks`](../tests/fixtures/smoke/rnbo-unit-conversions/hztoticks-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`mstobeats`](../tests/fixtures/smoke/rnbo-unit-conversions/mstobeats-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`mstohz`](../tests/fixtures/smoke/rnbo-unit-conversions/mstohz-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`mstosamps`](../tests/fixtures/smoke/rnbo-unit-conversions/mstosamps-event.rnbopat) | Pass | Unassessed | — | 76 / 81 | 1.31% | — |
| [`mstoticks`](../tests/fixtures/smoke/rnbo-unit-conversions/mstoticks-event.rnbopat) | Pass | Unassessed | — | 76 / 81 | 1.31% | — |
| [`sampstobeats`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstobeats-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`sampstohz`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstohz-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`sampstoms`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstoms-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`sampstoticks`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstoticks-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`tickstobeats`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstobeats-event.rnbopat) | Pass | Unassessed | — | 75.5 / 80 | 1.30% | — |
| [`tickstohz`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstohz-event.rnbopat) | Pass | Unassessed | — | 76 / 81 | 1.31% | — |
| [`tickstoms`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstoms-event.rnbopat) | Pass | Unassessed | — | 76 / 76 | 1.31% | — |
| [`tickstosamples`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstosamples-event.rnbopat) | Pass | Unassessed | — | 76 / 80 | 1.31% | — |
| [`tickstosamps`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstosamps-event.rnbopat) | Pass | Unassessed | — | 75.5 / 76 | 1.30% | — |
| [`beatstohz~`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstohz-signal.rnbopat) | Pass | Unassessed | — | 403 / 407 | 6.94% | — |
| [`beatstoms~`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstoms-signal.rnbopat) | Pass | Unassessed | — | 406 / 410 | 6.99% | — |
| [`beatstosamps~`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstosamps-signal.rnbopat) | Outside screen | Unassessed | — | 410 / 414 | 7.06% | — |
| [`beatstoticks~`](../tests/fixtures/smoke/rnbo-unit-conversions/beatstoticks-signal.rnbopat) | Pass | Unassessed | — | 91 / 95 | 1.57% | — |
| [`hztobeats~`](../tests/fixtures/smoke/rnbo-unit-conversions/hztobeats-signal.rnbopat) | Pass | Unassessed | — | 408 / 413 | 7.03% | — |
| [`hztoticks~`](../tests/fixtures/smoke/rnbo-unit-conversions/hztoticks-signal.rnbopat) | Pass | Unassessed | — | 552 / 553 | 9.51% | — |
| [`mstobeats~`](../tests/fixtures/smoke/rnbo-unit-conversions/mstobeats-signal.rnbopat) | Pass | Unassessed | — | 1111.5 / 1129 | 19.15% | Queued |
| [`mstoticks~`](../tests/fixtures/smoke/rnbo-unit-conversions/mstoticks-signal.rnbopat) | Pass | Unassessed | — | 499.5 / 500 | 8.60% | — |
| [`sampstobeats~`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstobeats-signal.rnbopat) | Pass | Unassessed | — | 441 / 446 | 7.60% | — |
| [`sampstoticks~`](../tests/fixtures/smoke/rnbo-unit-conversions/sampstoticks-signal.rnbopat) | Pass | Unassessed | — | 398 / 403 | 6.86% | — |
| [`tickstobeats~`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstobeats-signal.rnbopat) | Pass | Unassessed | — | 135 / 141 | 2.33% | — |
| [`tickstohz~`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstohz-signal.rnbopat) | Pass | Unassessed | — | 499.5 / 502 | 8.60% | — |
| [`tickstoms~`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstoms-signal.rnbopat) | Pass | Unassessed | — | 453 / 457 | 7.80% | — |
| [`tickstosamples~`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstosamples-signal.rnbopat) | Pass | Unassessed | — | 455 / 457 | 7.84% | — |
| [`tickstosamps~`](../tests/fixtures/smoke/rnbo-unit-conversions/tickstosamps-signal.rnbopat) | Pass | Unassessed | — | 453 / 457 | 7.80% | — |

## Numerical differences

There are 17,712 within-limit output differences, 3,328 observational left zero-sign differences and 128 outside-limit output words. Right-channel zero signs remain strict. Native preflight independently executes all 36 sources and retains its own numerical counts.

- `beatstosamps~`: 128 words exceed the original 0 limit; maximum error 0.015625 output units. Compilation, execution, parameter readbacks and the raw pilot still pass. The native preflight also records this rounding difference; no ESP-specific cause is inferred.

## Performance scope and next work

Callback timing includes the complete compiled FX graph, dispatch, signal addition where authored, and the right pilot. Event forms calculate in their setter/routing path; its 21-action total and peak are recorded separately in the JSON report. Neither measurement is an isolated opcode cost or a matched optimisation gain. Flagged contexts are recorded for later investigation; functional coverage continues first.

All images finalise and allocation/memory checks pass. The normal player, saved Main and live controls are restored; USB audio-frame progress and zero fault counters are checked. This offline timing firmware runs without I²S, UI or Wi-Fi and does not establish a loaded-player deadline. Changed tempo/transport, reset/constructor options, zero/nonfinite reciprocal inputs, MIDI clock and other domains remain unqualified. The full RNBO/Gen goal remains active.

Evidence: [part 1](../evidence/xiao-smoke-rnbo-unit-conversions-part1.json), [part 2](../evidence/xiao-smoke-rnbo-unit-conversions-part2.json), [native preflight](../evidence/rnbo-unit-conversions-native.json), [build ledger](../evidence/rnbo-unit-conversions-builds.json), [initial attempt](../evidence/rnbo-unit-conversions-attempts.json), [player restoration](../evidence/xiao-smoke-rnbo-unit-conversions-player-restoration.json), [machine-readable report](../evidence/rnbo-unit-conversions-status.json).
