# RNBO envelopes, logical edges and event clocks

The batch retains **31 scenarios across 9 exact spellings**. **21 pass**, **8 retain timing-screen differences**, and **2 fault on target**. The **29 completed runs check 296,960 output words and 638 control actions**. Raw right captures match throughout completed runs, with no nonfinite outputs. There are 24,546 within-limit differences and 5,268 observational left zero-sign differences. No new CPU flag triggers; the review queue stays **164**.

Every source uses one arm and 21 ordered signed drive events, including repeats, same-callback updates and quiet holds. There are four manual warm plus sixteen timed 256-frame callbacks at 44,100 Hz, and zero automatic warm callbacks. The signal stimulus varies every sixteen samples and includes zero, positive and negative levels. The independent raw right pilot includes signed zero, subnormals and finite extrema.

Logical references count events or sign transitions independently. Envelope references evaluate segment age in closed form, including the primary implementation's one-step attack/release transition and minimum one-sample durations. Curve references use an independent normalized exponential basis and the installed argument-to-curvature mapping. Limits are fixed before execution: logical/delayed values exact, envelopes/event line 2e-5, signal curves 3e-5. All original expected streams and limits remain unchanged.

The event-clock screen asks for deadlines relative to the intended next callback boundary, rounded to the nearest sample. The edge observer asks for one-block latency with original within-block offsets retained. These are explicit timing-policy probes. Their differences do not by themselves establish eight broken arithmetic objects; host-time origin and signal-to-event delivery need separate interpretation.

| Object | Scenario | Outcome | Median / peak µs | Callback CPU |
| --- | --- | --- | ---: | ---: |
| [`onoff`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onoff-events.rnbopat) | onoff-events | Pass | 77 / 81 | 1.33% |
| [`gatetotrig`](../tests/fixtures/smoke/rnbo-envelopes-clocks/gatetotrig-pos.rnbopat) | gatetotrig-pos | Pass | 76 / 76 | 1.31% |
| [`gatetotrig`](../tests/fixtures/smoke/rnbo-envelopes-clocks/gatetotrig-neg.rnbopat) | gatetotrig-neg | Pass | 76 / 80 | 1.31% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-init0-out0.rnbopat) | onebang-init0-out0 | Pass | 75 / 80 | 1.29% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-init0-out1.rnbopat) | onebang-init0-out1 | Pass | 75.5 / 80 | 1.30% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-init1-out0.rnbopat) | onebang-init1-out0 | Pass | 75.5 / 80 | 1.30% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-init1-out1.rnbopat) | onebang-init1-out1 | Pass | 76 / 80 | 1.31% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-rearm-out0.rnbopat) | onebang-rearm-out0 | Pass | 76 / 80 | 1.31% |
| [`onebang`](../tests/fixtures/smoke/rnbo-envelopes-clocks/onebang-rearm-out1.rnbopat) | onebang-rearm-out1 | Pass | 76 / 80 | 1.31% |
| [`edge~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/edge-out0.rnbopat) | edge-out0 | Timing screen differs | 165 / 168 | 2.84% |
| [`edge~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/edge-out1.rnbopat) | edge-out1 | Timing screen differs | 165 / 170 | 2.84% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-minimum.rnbopat) | env2-minimum | Pass | 152 / 156 | 2.62% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-short-free.rnbopat) | env2-short-free | Pass | 272 / 278 | 4.69% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-long-free.rnbopat) | env2-long-free | Pass | 236 / 258 | 4.07% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-short-held.rnbopat) | env2-short-held | Pass | 283 / 289 | 4.88% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-long-held.rnbopat) | env2-long-held | Pass | 341 / 346 | 5.87% |
| [`env2~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/env2-held-reset.rnbopat) | env2-held-reset | Pass | 283.5 / 288 | 4.88% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-immediate.rnbopat) | curve-immediate | Pass | 70 / 71 | 1.21% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-gentle.rnbopat) | curve-gentle | Pass | 318 / 328 | 5.48% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-rising.rnbopat) | curve-rising | Pass | 345.5 / 352 | 5.95% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-falling.rnbopat) | curve-falling | Pass | 349 / 359 | 6.01% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-steep.rnbopat) | curve-steep | Pass | 361 / 367 | 6.22% |
| [`curve~`](../tests/fixtures/smoke/rnbo-envelopes-clocks/curve-compound.rnbopat) | curve-compound | event fault | — | — |
| [`delay`](../tests/fixtures/smoke/rnbo-envelopes-clocks/delay-2-all0.rnbopat) | delay-2-all0 | Timing screen differs | 83 / 88 | 1.43% |
| [`delay`](../tests/fixtures/smoke/rnbo-envelopes-clocks/delay-2-all1.rnbopat) | delay-2-all1 | Timing screen differs | 84 / 88 | 1.45% |
| [`delay`](../tests/fixtures/smoke/rnbo-envelopes-clocks/delay-10-all0.rnbopat) | delay-10-all0 | Timing screen differs | 90 / 94 | 1.55% |
| [`delay`](../tests/fixtures/smoke/rnbo-envelopes-clocks/delay-10-all1.rnbopat) | delay-10-all1 | Timing screen differs | 90 / 95 | 1.55% |
| [`pipe`](../tests/fixtures/smoke/rnbo-envelopes-clocks/pipe-2.rnbopat) | pipe-2 | Timing screen differs | 83 / 88 | 1.43% |
| [`pipe`](../tests/fixtures/smoke/rnbo-envelopes-clocks/pipe-10.rnbopat) | pipe-10 | Timing screen differs | 89 / 93 | 1.53% |
| [`line`](../tests/fixtures/smoke/rnbo-envelopes-clocks/line-immediate.rnbopat) | line-immediate | Pass | 75 / 76 | 1.29% |
| [`line`](../tests/fixtures/smoke/rnbo-envelopes-clocks/line-ramp.rnbopat) | line-ramp | process fault | — | — |

## Compatibility findings

- All six selected `env2~` signal cases pass: minimum/short/long attack-release, held gates, signed amplitudes and the selected reset sequence. The completion bang is not observed by these signal-outlet cases.
- Five single-segment `curve~` cases pass, including direct assignment and positive/negative/steep curve shapes. The compound retargeting source faults at **event 13 before callback 10**, with **one late platform allocation**. Ten callbacks complete before the fault; it has no completed output/finalisation or steady-state CPU claim.
- Event `line` direct assignment passes. The original 12ms/2ms-grain ramp source faults during **callback 13**, with **one platform error and zero late allocations**. Its sixteen successful parameter actions and thirteen preceding callbacks are retained. The specific platform-error cause remains unproven.
- Both `edge~` selected bang outlets and all four `delay`/two `pipe` cases retain timing-screen differences on native and target runs. Deferred signal-event delivery, observer offsets and the current host-time boundary contract remain investigations. Expected deadlines and limits were not adjusted to captured outputs.
- `onoff`, both event `gatetotrig` directions and all six `onebang` initial/rearm/outlet cases pass. No status transfers to aliases, signal variants or auxiliary observers.

- `edge-out0`: 3,808 outside-screen words; maximum error 6; original limit 0.
- `edge-out1`: 4,080 outside-screen words; maximum error 6; original limit 0.
- `delay-2-all0`: 1,496 outside-screen words; maximum error 1; original limit 0.
- `delay-2-all1`: 1,496 outside-screen words; maximum error 3; original limit 0.
- `delay-10-all0`: 4,679 outside-screen words; maximum error 16; original limit 0.
- `delay-10-all1`: 4,167 outside-screen words; maximum error 3; original limit 0.
- `pipe-2`: 1,320 outside-screen words; maximum error 16; original limit 0.
- `pipe-10`: 3,655 outside-screen words; maximum error 16; original limit 0.

## Initial fixture and execution scope

The first immediate-curve graph supplied a zero-time list, selecting a one-sample ramp rather than a direct scalar assignment. Native preflight retained its sixteen differing words. That single graph is corrected before hardware; all 31 original goldens/limits and the other 30 graphs/modules remain unchanged. Original graphs, initial native results and the rejected existing-directory correction attempt are retained. This is one fixture mistake, separate from the compound-curve and line faults.

Completed callbacks measure 70–361µs median (1.21–6.22%), peak367µs. Setter/routing timing is separate across22 actions. These offline complete-context costs exclude I²S/UI/Wi-Fi work and are not isolated opcode costs or optimisation gains. Failed probes make no complete callback performance claim.

All29 completed images finalise and pass allocation/memory gates. Fault probes terminate at their original failure, with no substitute source or shortened passing schedule. Normal player, saved Main and live controls are restored; frames advance and reported runtime faults are zero. Other durations, dynamic inlet settings, completion outlets, scheduler/transport contracts, RNBO/Gen forms and complete qualification remain active work. A same-version direct Max-export comparison is separate work; no claim is made here that changing export routes fixes these findings.

Evidence: [machine-readable report](../evidence/rnbo-envelopes-clocks-status.json), [native](../evidence/rnbo-envelopes-clocks-native.json), [initial fixture](../evidence/rnbo-envelopes-clocks-initial-fixture.json), [build ledger](../evidence/rnbo-envelopes-clocks-builds.json), [restoration](../evidence/xiao-smoke-rnbo-envelopes-clocks-player-restoration.json).
