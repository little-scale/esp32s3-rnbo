# RNBO signal-analysis and sample-clock checks

The batch covers **23 scenarios across 16 exact spellings**. **19 pass**, and **4 retain report/clock timing differences** against the original screen. Checks cover **235,520 output words and 506 control actions**. All raw right captures match, and no nonfinite or zero-sign differences occur. There are 5 within-limit differences. No new callback CPU flag triggers; **164 contexts** remain queued.

One arm precedes 21 ordered signed drive events, including repeated values, three updates before one callback, and quiet holds. Every source runs four manual warm and sixteen timed full 256-frame callbacks at 44,100 Hz, with zero automatic warm callbacks. Signal inputs vary every sample within blocks. The right pilot independently checks signed zero, subnormals and finite extrema. Parameter IDs, actual values and normalised readbacks are checked.

References use independent mean/absolute/RMS window definitions, sign changes, threshold hysteresis and elapsed sample ordinals. Averages begin with the populated partial window. Zero is nonnegative for crossing detection. Equal thresholds reset strictly below the threshold; unequal thresholds reset at or below the low threshold. Seven-value event averages, 2/3/7-event crossing windows and manual reports remain distinct. Empty mean/peak report windows produce zero; snapshot retains the previous last sample.

The timing screen deliberately asks for a report to be visible in the first rendered block after a bang, for signal clocks to advance each sample from origin zero, and for event clocks to reflect the next callback boundary. Limits were fixed before compilation: exact dyadic/state/ordinal checks 0, means/RMS 2e-6, millisecond clocks 2e-5 ms. All 23 original expected streams and limits remain unchanged. These particular latency/origin requirements require the interpretation below; full compatibility remains unproven for the four differing forms.

| Exact spelling | Scenario | Outcome | Median / peak µs | Callback CPU | Arena high-water bytes |
| --- | --- | --- | ---: | ---: | ---: |
| [`avg~`](../tests/fixtures/smoke/rnbo-analysis-timing/avg-manual.rnbopat) | avg-manual | Timing screen differs | 121 / 125 | 2.08% | 0 |
| [`peakamp~`](../tests/fixtures/smoke/rnbo-analysis-timing/peakamp-manual.rnbopat) | peakamp-manual | Pass | 145 / 150 | 2.50% | 0 |
| [`snapshot~`](../tests/fixtures/smoke/rnbo-analysis-timing/snapshot-manual.rnbopat) | snapshot-manual | Pass | 91 / 96 | 1.57% | 0 |
| [`thresh`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-hysteresis.rnbopat) | thresh-hysteresis | Pass | 75.5 / 80 | 1.30% | 0 |
| [`thresh`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-equal-zero.rnbopat) | thresh-equal-zero | Pass | 76 / 80 | 1.31% | 0 |
| [`thresh`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-equal-positive.rnbopat) | thresh-equal-positive | Pass | 76 / 76 | 1.31% | 0 |
| [`thresh~`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-signal-hysteresis.rnbopat) | thresh-signal-hysteresis | Pass | 98 / 100 | 1.69% | 0 |
| [`thresh~`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-signal-equal-zero.rnbopat) | thresh-signal-equal-zero | Pass | 100 / 105 | 1.72% | 0 |
| [`thresh~`](../tests/fixtures/smoke/rnbo-analysis-timing/thresh-signal-equal-positive.rnbopat) | thresh-signal-equal-positive | Pass | 98 / 104 | 1.69% | 0 |
| [`zerox`](../tests/fixtures/smoke/rnbo-analysis-timing/zerox-events.rnbopat) | zerox-events | Pass | 75.5 / 80 | 1.30% | 0 |
| [`zerox_count`](../tests/fixtures/smoke/rnbo-analysis-timing/zerox-count-2.rnbopat) | zerox-count-2 | Pass | 75 / 76 | 1.29% | 0 |
| [`zerox_count`](../tests/fixtures/smoke/rnbo-analysis-timing/zerox-count-3.rnbopat) | zerox-count-3 | Pass | 75 / 80 | 1.29% | 0 |
| [`zerox_count`](../tests/fixtures/smoke/rnbo-analysis-timing/zerox-count-7.rnbopat) | zerox-count-7 | Pass | 76 / 80 | 1.31% | 0 |
| [`average`](../tests/fixtures/smoke/rnbo-analysis-timing/average-seven.rnbopat) | average-seven | Pass | 75 / 76 | 1.29% | 352,880 |
| [`average_absolute`](../tests/fixtures/smoke/rnbo-analysis-timing/average_absolute-seven.rnbopat) | average_absolute-seven | Pass | 75 / 80 | 1.29% | 352,880 |
| [`average_rms`](../tests/fixtures/smoke/rnbo-analysis-timing/average_rms-seven.rnbopat) | average_rms-seven | Pass | 75.5 / 80 | 1.30% | 352,880 |
| [`samplecount~`](../tests/fixtures/smoke/rnbo-analysis-timing/samplecount-signal.rnbopat) | samplecount-signal | Pass | 76 / 80 | 1.31% | 0 |
| [`currentsampletime`](../tests/fixtures/smoke/rnbo-analysis-timing/currentsampletime.rnbopat) | currentsampletime | Pass | 76 / 77 | 1.31% | 0 |
| [`currentsampletime~`](../tests/fixtures/smoke/rnbo-analysis-timing/currentsampletime-signal.rnbopat) | currentsampletime-signal | Timing screen differs | 122 / 126 | 2.10% | 0 |
| [`currenttime`](../tests/fixtures/smoke/rnbo-analysis-timing/currenttime.rnbopat) | currenttime | Timing screen differs | 76 / 76 | 1.31% | 0 |
| [`currenttime~`](../tests/fixtures/smoke/rnbo-analysis-timing/currenttime-signal.rnbopat) | currenttime-signal | Timing screen differs | 104 / 109 | 1.79% | 0 |
| [`elapsed~`](../tests/fixtures/smoke/rnbo-analysis-timing/elapsed-free.rnbopat) | elapsed-free | Pass | 77.5 / 79 | 1.34% | 0 |
| [`elapsed~`](../tests/fixtures/smoke/rnbo-analysis-timing/elapsed-reset.rnbopat) | elapsed-reset | Pass | 78 / 82 | 1.34% | 0 |

## Retained report and clock-policy findings

The same four screens differ in native and XIAO runs. These observations bind the authored observer and module call ordering. They do not establish four DSP defects or an ESP32-only difference.

- `avg~`: the manual-report screen expects the previous sample window to be visible in the immediately following rendered block. The exported scheduling path queues its held report at the end of that block, so the `sig~` observer receives a deferred report. Qualification of this latency contract remains open; the mean-absolute equation and original numerical limits are not substituted with captured outputs.
- `currentsampletime~`: the screen expects an ordinal increment at every sample. The exported expression instead writes the current block sample counter plus the host event offset throughout the block. `samplecount~` passes the separate continuously incrementing signal screen, and event `currentsampletime` passes the boundary screen.
- `currenttime` and `currenttime~`: these screens expect origin-zero sample-position milliseconds. The exported path observes the host block-time field; event delivery before the next process call can observe the preceding block time, and the signal value follows block time rather than each sample. Host-application absolute time, scheduled within-block offsets and alternate report observers remain separate tests.

- `avg-manual`: 3,328 outside-screen words, maximum error 3.375, original limit 1.99999999e-06.
- `currentsampletime-signal`: 5,100 outside-screen words, maximum error 255, original limit 0.
- `currenttime`: 4,864 outside-screen words, maximum error 5.80499267578125, original limit 1.99999995e-05.
- `currenttime-signal`: 5,100 outside-screen words, maximum error 5.7823143005371094, original limit 1.99999995e-05.

## Performance and resource follow-up

Complete callback time includes the compiled fixture and raw pilot; event setters/routing are separately timed across 22 actions. These are offline callback costs without I²S/UI/Wi-Fi work. No isolated opcode cost, whole-chip CPU percentage, loaded-player deadline guarantee or optimisation saving is claimed.

All three seven-value event averages pass, but each consumes **352,880 arena bytes** in the explicit **1 MiB ceiling**. The installed primary operator allocates a sample-rate-sized Float64 buffer, even for the selected small event window. A bounded event-rate storage implementation is a memory optimisation candidate; numerical equivalence, dynamic window/reset behaviour and real-time allocation policy must be checked before changing it. A 4 KiB resource configuration is not qualified by these runs.

All 23 images finalise and pass allocation/memory gates. Normal player, saved Main and live controls are restored; frames advance and runtime faults remain zero. Other window sizes, dynamic windows/resets, periodic reporting, absolute/transport origins, within-block events, other RNBO/Gen forms and complete sample-by-sample qualification remain open. The full goal stays active.

Evidence: [machine-readable report](../evidence/rnbo-analysis-timing-status.json), [native](../evidence/rnbo-analysis-timing-native.json), [build ledger](../evidence/rnbo-analysis-timing-builds.json), [player restoration](../evidence/xiao-smoke-rnbo-analysis-timing-player-restoration.json).
