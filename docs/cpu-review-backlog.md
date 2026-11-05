# CPU review backlog

The fast hardware runs record typical (median), mean and observed peak callback
time. A case is queued for later investigation if either:

- Its median exceeds 10% of the 256-frame block period at 44.1 kHz (about 580 µs).
- Its peak exceeds both three times its median and its median plus 100 µs.

These are screening rules, not proof that an object needs changing. A flagged
case should be repeated and investigated when optimisation work resumes.
Functional coverage continues first.

## Analysis/oscillator/noise members: twelve queued contexts

All twelve authored average scenarios trigger the median rule; no peak-spike
rule triggers. The queue grows from 111 to **123 contexts**. Three window-change
scenarios retain source-scheduling mismatches; their CPU observations remain
useful but do not qualify their outputs.

| Complete callback | Median µs | Peak µs | Median / audio period | Output |
| --- | ---: | ---: | ---: | --- |
| `average-next` | 587 | 593 | 10.11% | pass |
| `average-reset` | 637.5 | 638 | 10.98% | pass |
| `average-input-reset` | 653 | 655 | 11.25% | pass |
| `average_absolute-next` | 621 | 624 | 10.70% | pass |
| `average_absolute-reset` | 683 | 687 | 11.77% | pass |
| `average_absolute-input-reset` | 678 | 679 | 11.68% | pass |
| `average_rms-next` | 758.5 | 763 | 13.07% | pass |
| `average_rms-reset` | 815 | 818 | 14.04% | pass |
| `average_rms-input-reset` | 820 | 825 | 14.13% | pass |
| `average-window-change-named-list` | 604.5 | 620 | 10.41% | output_mismatch |
| `average_absolute-window-change-named-list` | 645 | 662 | 11.11% | output_mismatch |
| `average_rms-window-change-named-list` | 764 | 781 | 13.16% | output_mismatch |

Every averaging pair observes 705,760 bytes arena high-water: two default
44,101-sample Float64 buffers plus overhead, despite logical windows of 3–16
samples. Review explicit capacity bounds and Float32 storage when optimisation
resumes. Preserve startup, reset, changed-window and odd-window numerical
behaviour. Existing patcher `average~` optimisation does not qualify codebox
members by inheritance. The selector hoisting mismatch is a separate source/
scheduling follow-up, not an output model to fit away.

The four cycle scenarios measure 433–550 µs median; the three noise screens
measure 155–287 µs. Neither group triggers a rule. These are complete offline
callbacks including test logic, without I²S/UI/network work; no optimisation
percentage is claimed. See the [member batch](../tests/fixtures/smoke/rnbo-codebox-analysis-members/README.md)
and [target evidence](../evidence/xiao-smoke-rnbo-codebox-analysis-members.json).

## Gen execution forms: no new CPU flags

Five arithmetic/noise-screen programs measure 44–115 µs median and 45–120 µs
peak per 256-frame offline callback. No rule triggers; the queue remains **111**.
Noise's 115 µs includes range and variation checks, not isolated RNG cost.
Fourteen C++ and five frontend failures have no device CPU measurement.
See the [target record](../evidence/xiao-smoke-gen-execution-forms.json).

## Extended Gen data: one queued context

Signal-indexed Gen lookup passes its reference but costs 807 µs median,
811 µs observed peak per 256-frame callback: **13.90%** of the audio period.
It adds one context, bringing the queue from 110 to **111**. Other extended
Gen data/oscillator/boundary medians are 58–563 µs. No peak-spike rule triggers.

The callback includes two independently initialized local-table reads with
signal-to-index mapping and linear interpolation. It is distinct from explicit
sample-index lookup, which measures 150 µs in its own source. These are absolute
costs of different authored programs, not a matched optimisation comparison or
isolated opcode timings. The seven device mismatches and negative-channel
sanitizer/portability issue remain compatibility follow-ups.

Sources: [part 1](../evidence/xiao-smoke-gen-data-extended-part1.json),
[part 2](../evidence/xiao-smoke-gen-data-extended-part2.json) and
[native/diagnostic record](../evidence/gen-data-extended-native.json).

## Delay resources: nine queued contexts

The delay/member batch adds nine contexts, taking the queue from 101 to **110**.
All trigger the median-budget rule; no additional peak-spike rule triggers.

| Complete authored callback | Median µs | Peak µs | Median / audio period | Output status |
| --- | ---: | ---: | ---: | --- |
| `comb-next-integer` | 753 | 757 | 12.97% | pass |
| `comb-clear-integer` | 43960.5 | 43963 | 757.29% | pass |
| `comb-reset-integer` | 43971 | 43973 | 757.47% | pass |
| `allpass-next-integer` | 984.5 | 989 | 16.96% | pass |
| `allpass-clear-integer` | 44187 | 44193 | 761.19% | pass |
| `allpass-reset-integer` | 44189 | 44194 | 761.22% | pass |
| `delay-read-cosine-numeric-enum` | 1418 | 1422 | 24.43% | pass |
| `delay-read-cubic-numeric-enum` | 1454 | 1454 | 25.05% | output_mismatch |
| `delay-read-spline-numeric-enum` | 1533 | 1537 | 26.41% | output_mismatch |

Default comb/allpass each observe 1,048,704 bytes arena high-water. The reset/
clear programs usually clear roughly 1 MiB twice in a 256-frame callback under
unchanged strict storage; their 43.96–44.19 ms medians exceed the 5.805 ms period.
This known repeated resource work should be separated from isolated next cost.
Review bounded delay capacities and reset scheduling first. A lazy-clear or
other changed implementation would require its own output/state proof.

The interpolation costs are complete read/write/step callbacks. Cubic/spline
alignment mismatches remain compatibility follow-ups even though their CPU
cost is measured. Cosine passes its reference. None of these contexts has a
matched optimisation comparison or a performance-gain claim.

Source: [delay/member results](../evidence/xiao-smoke-rnbo-codebox-delay-members.json).

## Explicit stateful members: no new CPU flags

Thirty-five executed next/reset/clear scenarios measure 56–500.5 µs median,
with maximum observed peak 503 µs. Neither rule triggers; the queue remains
**101 contexts**. Reset cases include sample-counter/remainder/branch overhead
and occasional member calls, so these costs do not isolate reset or clear.
The eight output mismatches and history member C++ rejection are compatibility
follow-ups, with no DSP repair or performance-gain claim in this batch.

Source: [member part 1](../evidence/xiao-smoke-rnbo-codebox-members-part1.json)
and [part 2](../evidence/xiao-smoke-rnbo-codebox-members-part2.json).

## Codebox structures and lifecycle: no new flags

All 24 passing language/lifecycle programs measure 41.5–86 µs median per 256-frame
callback, with maximum observed peak 91 µs. Neither screening rule triggers;
the cumulative queue remains **101 contexts**. These are whole authored
programs, including bounded loops and observable state, without I²S/UI/network.
Signed-zero differences are tracked separately; no optimisation gain is claimed.

Source: [structure/lifecycle results](../evidence/xiao-smoke-rnbo-codebox-structures.json).

## Global list functions: two queued contexts

The list-function batch adds two passing contexts, bringing the queue from 99
to **101**. Both trigger the median-cost rule; no peak-spike flag triggers.

| Whole codebox callback | Median µs | Peak µs | Median / block period |
| --- | ---: | ---: | ---: |
| `listswap` | 917 | 917 | 15.80% |
| `listunion` | 861 | 861 | 14.83% |

These global-function scenarios include sample-dependent list construction,
copies and length-sensitive weighted fingerprints. They are separate from the
earlier list-member and Gen cases. Investigate those surrounding costs before
attributing time to a primitive operation. The intersection output mismatch,
seven C++ rejections, frontend call-form rejections and native-only rotation
fault are compatibility follow-ups; the excluded rotation case has no device
CPU measurement. No optimisation gain is claimed.

Source: [global list-function results](../evidence/xiao-smoke-rnbo-codebox-list-functions.json).

The subsequent [Gen control/structure batch](hardware-smoke.md#gen-control-declarations-and-language-structures)
adds **no flags**: 19 passing callbacks measure 42–94.5 µs median and at most
99 µs observed peak. These complete programs include bounded looping and
function-local sample state. The cumulative queue remains **99**; rejected
source forms and signed-zero differences are separate compatibility follow-ups.

## Codebox containers: five queued contexts

All 26 executable list/array programs pass their exact output references.
Five list workloads trigger the median-cost rule, bringing the queue from 94
to **99**. No new peak-spike flags trigger.

| Whole codebox callback | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `list.shift()` | 865.5 | 866 | 14.91% | Review copies/mutation/checksum cost |
| `list.concat()` | 737 | 738 | 12.70% | Review construction/copies/checksum cost |
| `list.fill()` | 669 | 670 | 11.52% | Review fill/copies/checksum cost |
| `list.splice()` | 673 | 674 | 11.59% | Review mutation/returned-list/checksum cost |
| `list.reverse()` | 668 | 668 | 11.51% | Review mutation/copies/checksum cost |

These callbacks include the sample-dependent list literal and authored checksum
function. They do not isolate a single method. The fixed-array cases preserve
their original storage, including explicit Float64 types; none triggers a CPU
flag. The two length-return compile failures and native-only empty/constant-list
findings are compatibility follow-ups, not CPU measurements. No optimisation
or speedup is claimed.

Source: [codebox container results](../evidence/xiao-smoke-rnbo-codebox-containers.json).

The exact stereo [`dbtoa~` Float32 experiment](dbtoa-float32.md) now has a
matched XIAO result: **91.64% less callback time**, with explicit changed
rounding. Mean time falls from 15,869.50 to 1,326.51 µs across four bounded
vectors. This is an explicit exact-graph experiment; broader Auto, Main,
codebox and Gen use remain pending. The candidate still uses 22.85% of the
block period, so further review remains useful. Repeated benchmark screens do
not create new object contexts; the queue at that stage remained **93**.

## Local Gen Data: one queued context

All eight local-array programs pass their output limits. The seven-sample
feedback declaration program takes **687 µs median / 688 µs peak**, or
**11.83% / 11.85%** of the 256-frame period. This median-cost flag brings the
recorded queue from 93 to **94**; no peak-spike flag triggers.

The cost includes its complete indexed feedback, History index and copied
pilot context, rather than an isolated Data access. The producer's original
Float32 `SampleBuffer` representation remains; no storage conversion or CPU
saving is claimed. See [the Gen Data results](../evidence/xiao-smoke-gen-data-indexed.json).

## Signal routing and interpolation: one queued context

All 20 supplied signal scenarios pass their output limits. The new flag is
the complete stereo `cubicinterp~` callback: **3,367 µs median, 3,371 µs peak**,
or **58.00%/58.07%** of the 256-frame period at 44.1 kHz. This median-cost flag
brings the queue from 92 to **93**; no peak-spike flag triggers.

The asymmetric fixed-keyframe vector passes its unchanged 2e-6 limit, with
maximum absolute error 5.960464477539063e-8. The similarly named codebox case
remains a separate queued context. No isolated opcode cost, optimisation or
performance gain is claimed.

Source: [signal routing results](../evidence/xiao-smoke-rnbo-signal-routing.json).

## Signal-stateful and miscellaneous codebox: five queued contexts

All five flagged scenarios pass their output limits. These are complete source
callbacks, with signal objects and configured codebox APIs kept distinct.

| Source context | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| Signal `average_absolute~` | 597.0 | 603 | 10.28% | Pending optimisation review |
| Signal `average_rms~` | 743.0 | 748 | 12.80% | Pending optimisation review |
| Codebox `safepow` | 739.0 | 739 | 12.73% | Pending optimisation review |
| Codebox `cubicinterp` | 2,191.5 | 2,196 | 37.75% | Pending optimisation review |
| Codebox `easexfade` | 624.0 | 625 | 10.75% | Pending optimisation review |

These five median-cost flags bring the queue from 87 to **92**; there are no
new peak-spike flags. The downsample first-capture-phase mismatch remains
separate follow-up and does not trigger CPU review. No DSP change, measured
saving, isolated-opcode cost or worst-case latency bound is claimed.

Sources: [signal-stateful](../evidence/xiao-smoke-rnbo-signal-stateful.json) and
[miscellaneous codebox](../evidence/xiao-smoke-rnbo-codebox-misc.json).

## RNBO codebox filters: five queued contexts

All five flagged programs pass their output references. Mono-plus-copy and
dual-instance callbacks are different fixtures, not isolated opcode costs.

| Source context | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `comb` mono + copy | 756.0 | 762 | 13.02% | Pending optimisation review |
| `allpass` mono + copy | 982.0 | 988 | 16.92% | Pending optimisation review |
| `average` dual instances | 582.5 | 587 | 10.03% | Pending optimisation review |
| `average_absolute` dual instances | 612.0 | 616 | 10.54% | Pending optimisation review |
| `average_rms` dual instances | 763.0 | 766 | 13.14% | Pending optimisation review |

These five median-cost flags add to six new signal contexts and 76 earlier
contexts, bringing the queue to **87**. There are no new peak-spike flags. The
2 MiB smoke-only capacity tier preserves original Float64 rings and defaults;
it is not a DSP optimisation or a measured memory-use figure. No CPU saving or
worst-case latency bound is claimed.

Source: [codebox filter results](../evidence/xiao-smoke-rnbo-codebox-filters.json).

## RNBO signal range/windows: six queued contexts

All six flagged signal scenarios pass their output limits. Each row measures
the complete authored callback; matching codebox/Gen names keep separate costs.

| Exact signal form | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `cosineinterp~` | 1,874.0 | 1,874 | 32.28% | Pending optimisation review |
| `hann~` | 4,124.5 | 4,129 | 71.05% | Pending optimisation review |
| `hamming~` | 4,525.0 | 4,528 | 77.95% | Pending optimisation review |
| `blackman~` | 7,763.0 | 7,764 | 133.73% | Pending optimisation review |
| `t60~` | 5,574.0 | 5,575 | 96.02% | Pending optimisation review |
| `triangle~` | 623.0 | 624 | 10.73% | Pending optimisation review |

`blackman~` has a 7.763 ms median, about 1.34 block periods in this fixture.
All six new flags concern median cost rather than peak spikes. They bring the
queue from 76 to 82 before the five separate filter/delay additions. The three output
mismatches remain separate functional/quality follow-up, and none triggers CPU
review. No DSP change, CPU saving or worst-case latency bound is claimed.

Source: [direct signal results](../evidence/xiao-smoke-rnbo-signal-range.json).

## RNBO codebox state instances: no new flags

The eleven executed state-instance scenarios have callback medians 54–379.5 µs
and peak 380 µs; no review rule triggers. The queue remains at **76** after the
eighteen shaping additions. The downsample capture-phase mismatch remains
separate follow-up; the two rejected sources have no hardware timing. These
costs concern the supplied class-instance programs, not similarly named Gen or
patcher operators, and claim no optimisation gain.

Source: [codebox stateful results](../evidence/xiao-smoke-rnbo-codebox-stateful.json).

## RNBO codebox shaping: eighteen queued contexts

All eighteen flagged cases pass their declared output limits. Each measures a
complete stereo scalar-function callback at 44.1 kHz/256 frames, not an isolated
operation or the separate stateful `ease` class.

| Exact codebox call | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `ease_in_out_cubic()` | 808.0 | 809 | 13.92% | Pending optimisation review |
| `ease_in_out_quintic()` | 684.0 | 685 | 11.78% | Pending optimisation review |
| `ease_in_sine()` | 3,573.0 | 3,574 | 61.55% | Pending optimisation review |
| `ease_out_sine()` | 3,465.5 | 3,470 | 59.70% | Pending optimisation review |
| `ease_in_out_sine()` | 4,044.0 | 4,045 | 69.66% | Pending optimisation review |
| `ease_in_exponential()` | 1,364.0 | 1,369 | 23.50% | Pending optimisation review |
| `ease_out_exponential()` | 1,328.0 | 1,332 | 22.88% | Pending optimisation review |
| `ease_in_out_exponential()` | 1,597.0 | 1,598 | 27.51% | Pending optimisation review |
| `ease_in_back()` | 3,951.0 | 3,952 | 68.06% | Pending optimisation review |
| `ease_out_back()` | 3,897.0 | 3,898 | 67.13% | Pending optimisation review |
| `ease_in_out_back()` | 3,759.0 | 3,760 | 64.75% | Pending optimisation review |
| `ease_in_elastic()` | 6,139.0 | 6,143 | 105.75% | Pending optimisation review |
| `ease_out_elastic()` | 6,312.0 | 6,316 | 108.73% | Pending optimisation review |
| `ease_in_out_elastic()` | 6,493.0 | 6,498 | 111.85% | Pending optimisation review |
| `hann()` | 4,365.5 | 4,370 | 75.20% | Pending optimisation review |
| `hamming()` | 4,770.5 | 4,772 | 82.18% | Pending optimisation review |
| `blackman()` | 8,515.0 | 8,519 | 146.68% | Pending optimisation review |
| `cosineinterp()` | 1,913.0 | 1,913 | 32.95% | Pending optimisation review |

`blackman()` has an 8.515 ms median. The in/out/in-out elastic calls measure
6.139/6.312/6.493 ms; all four exceed the 5.805 ms block period in these fixtures.
All new flags are median-cost observations rather than peak spikes. Eighteen
new contexts bring the queue from 58 to **76**; the stateful batch adds no
flags. The two bounce output mismatches remain separate precision follow-up;
neither triggers CPU review. No DSP change, CPU saving or worst-case latency
bound is claimed.

Source: [codebox shaping results](../evidence/xiao-smoke-rnbo-codebox-shaping.json).

## RNBO codebox range/conversions: six queued contexts

All six flagged source forms pass their predeclared references. These are
complete stereo RNBO codebox callbacks, separate from similarly named Gen and
patcher measurements. The converter rows use valid state-instance `.next()`
programs; rejected direct calls have no hardware timing.

| Exact source context | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `log2f()` | 4,876.0 | 4,876 | 84.00% | Pending optimisation review |
| `atodb()` | 591.0 | 592 | 10.18% | Pending optimisation review |
| `dbtoa()` | 14,663.0 | 14,664 | 252.59% | Pending optimisation review |
| `t60()` | 5,569.0 | 5,570 | 95.93% | Pending optimisation review |
| `mtof` instance `.next()` | 2,396.0 | 2,401 | 41.27% | Pending optimisation review |
| `ftom` instance `.next()` | 2,705.0 | 2,706 | 46.60% | Pending optimisation review |

`dbtoa()` takes 14.663 ms median, about 2.53 block periods. All new flags are
median-cost observations, not peak spikes. These six add to the previous 52
contexts, bringing the queue to **58**. The four output mismatches and seven
nonexecuted source forms remain separate follow-up work. No DSP changes, CPU
savings or worst-case latency bounds are claimed.

Source: [RNBO codebox range results](../evidence/xiao-smoke-rnbo-codebox-range.json).

## Gen named constants: no new flags

All 32 bare-value scenarios have callback median 37 µs and peak at most 42 µs.
No review threshold triggers; existing queued contexts remain pending.
Configuration names are observed only at 44,100 Hz/256 frames. No CPU saving or
isolated lookup cost is inferred from these complete callback timings.

Source: [Gen named-constant results](../evidence/xiao-smoke-gen-constants.json).

## Gen range/conversions: six queued cases

These are complete stereo GenExpr callbacks, separate from RNBO patcher and
codebox names. Five cases pass their output limits; `ftom` retains the declared
continuous-pitch mismatch as separate correctness/semantic follow-up.

| Exact Gen call | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `mtof()` | 2,398.5 | 2,401 | 41.32% | Pending optimisation review |
| `ftom()` | 2,703.0 | 2,704 | 46.56% | Pending optimisation review |
| `atodb()` | 591.0 | 592 | 10.18% | Pending optimisation review |
| `dbtoa()` | 14,663.0 | 14,664 | 252.59% | Pending optimisation review |
| `t60()` | 5,569.0 | 5,570 | 95.93% | Pending optimisation review |
| `triangle()` | 635.0 | 636 | 10.94% | Pending optimisation review |

`dbtoa()` takes 14.663 ms median, about 2.53 block periods in this fixture. All
six flags are median-cost observations, with no new peak-spike flags. Together
with fourteen new RNBO codebox contexts and 32 earlier contexts, **52 cases are
queued**. Approximation-screen exceedances for `fastpow`, `fastexp` and `fasttan`
are separate from CPU review; none of those three triggers a CPU flag. No code
has been changed for performance, and these are not worst-case latency bounds.

Source: [Gen range hardware results](../evidence/xiao-smoke-gen-range.json).

## RNBO codebox numeric: fourteen queued cases

All fourteen flagged calls pass their declared output references. Each row is
a complete stereo RNBO codebox callback at 44.1 kHz/256 frames; similarly named
Gen or patcher functions have separate results and queue entries.

| Exact codebox call | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `exp2()` | 7,499.0 | 7,504 | 129.18% | Pending optimisation review |
| `log()` | 3,684.0 | 3,685 | 63.46% | Pending optimisation review |
| `ln()` | 3,684.0 | 3,685 | 63.46% | Pending optimisation review |
| `log2()` | 4,732.0 | 4,733 | 81.52% | Pending optimisation review |
| `log10()` | 4,297.0 | 4,302 | 74.02% | Pending optimisation review |
| `log1p()` | 3,982.0 | 3,983 | 68.60% | Pending optimisation review |
| `pow()` | 1,134.0 | 1,135 | 19.53% | Pending optimisation review |
| `tanh()` | 702.0 | 703 | 12.09% | Pending optimisation review |
| `atan2()` | 690.0 | 690 | 11.89% | Pending optimisation review |
| `sinh()` | 724.0 | 724 | 12.47% | Pending optimisation review |
| `cosh()` | 655.0 | 655 | 11.28% | Pending optimisation review |
| `asinh()` | 779.0 | 780 | 13.42% | Pending optimisation review |
| `acosh()` | 758.0 | 758 | 13.06% | Pending optimisation review |
| `atanh()` | 798.0 | 798 | 13.75% | Pending optimisation review |

`exp2()` exceeds the block period at 7.499 ms median. The 14 flags are median-cost
observations, with no new peak-spike flags. They add to 32 previous mathematical
contexts, bringing the queue to 46 before the separate Gen range batch. No DSP
change, CPU saving or worst-case latency bound follows from these screens.
The three round/denormal output mismatches remain separate correctness work.

Source: [RNBO codebox numeric results](../evidence/xiao-smoke-rnbo-codebox-numeric.json).

## RNBO codebox batches: no new flags

The 43 arithmetic/logic scenarios have callback medians 42–274 µs and peak
279 µs. All 40 named-value constant scenarios have median 37 µs and peak 42 µs.
Both remain below the screening thresholds; no CPU savings are claimed.
The two rejected syntax forms have no hardware cost observation. Existing
mathematical CPU-review entries remain pending.

Sources: [RNBO codebox arithmetic/logic](../evidence/xiao-smoke-rnbo-codebox.json)
and [named constants](../evidence/xiao-smoke-rnbo-codebox-constants.json).

## Extra events and constants: no new flags

The 40 additional event scenarios have callback medians 75–76.5 µs and peak 81 µs;
the 21 constant scenarios have medians 37–50 µs and peak 54 µs. Neither callback
screening rule triggers. The 840 event calls separately total 6,419 µs, peak 43 µs;
these setter/routing observations are not isolated opcode costs or CPU savings.

The five event output mismatches remain correctness/precision follow-up work;
small callback cost does not make them pass. The 32 mathematical CPU-review
entries below remain pending, with no new entries from these two batches.

Sources: [extra events](../evidence/xiao-smoke-rnbo-events-extra.json) and
[constants](../evidence/xiao-smoke-rnbo-constants.json).

## Parameter-driven event batch: no new flags

All35 event forms pass. Processing medians are 75–76 µs per stereo 256-frame
callback; no processing-time screening rule triggers. The 735 actual event API
calls are logged separately: 5–44 µs each,154–203 µs total per 21-update fixture.
They include setter/routing work and are not isolated opcode timings. No event
speed gain or worst-case guarantee is inferred. The 32 earlier mathematical
CPU-review entries remain pending.

Source: [parameter/event hardware results](../evidence/xiao-smoke-rnbo-events.json).

## RNBO functions/conversions: eleven queued cases

All eleven cases pass their output limits but exceed the median-cost threshold.
These are complete two-instance stereo callbacks at 256 frames/44.1 kHz.

| Exact form | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `tanh~` | 645.0 | 646 | 11.11% | Pending optimisation review |
| `atan2~` | 681.0 | 682 | 11.73% | Pending optimisation review |
| `sinh~` | 694.0 | 695 | 11.96% | Pending optimisation review |
| `cosh~` | 643.5 | 646 | 11.09% | Pending optimisation review |
| `asinh~` | 756.5 | 757 | 13.03% | Pending optimisation review |
| `acosh~` | 828.0 | 828 | 14.26% | Pending optimisation review |
| `atanh~` | 772.0 | 772 | 13.30% | Pending optimisation review |
| `mtof~` | 2392.0 | 2397 | 41.21% | Pending optimisation review |
| `ftom~` | 667.5 | 668 | 11.50% | Pending optimisation review |
| `atodb~` | 4875.0 | 4876 | 83.98% | Pending optimisation review |
| `dbtoa~` | 14659.0 | 14660 | 252.52% | Pending optimisation review |

`dbtoa~` exceeds the block period by about 2.53 times in this stereo fixture;
prioritise it alongside the separately measured RNBO/Gen `exp2` cases. Inspect
math overloads/promotions and repeated conversion work when optimisation
resumes. Preserve the default converter resource behaviour during any matched
comparison. No performance change is claimed by the arena-capacity extension.
All new flags are high median cost rather than isolated peaks. There are now
32 queued exact-context cases across the three mathematical batches.

Source: [function/conversion hardware result](../evidence/xiao-smoke-rnbo-functions.json).
The `fasttan~` ideal-threshold exceedance is a separate approximation-quality
outcome and did not trigger CPU review.

## Gen stateful batch: no new flags

All twelve stateful programs pass their declared output limits. Medians range
from 50 to 551 µs, with largest peak 552 µs. DCblock is the highest-cost fixture
at about 9.49% of the block period, below the existing 10% screening threshold.
The earlier twenty-one RNBO/Gen mathematical review entries remain pending.

Source: [stateful Gen results](../evidence/xiao-smoke-gen-stateful.json).

## Gen mathematical batch: thirteen queued cases

All thirteen forms pass their declared output limits, but their median callback
cost exceeds the screening threshold. These are separate GenExpr executions;
RNBO evidence does not transfer to matching names.

| Exact Gen form | Median µs | Peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `exp2()` | 7499.0 | 7503 | 129.18% | Pending optimisation review |
| `log()` | 3684.0 | 3685 | 63.46% | Pending optimisation review |
| `ln()` | 3684.0 | 3685 | 63.46% | Pending optimisation review |
| `log2()` | 4732.0 | 4733 | 81.52% | Pending optimisation review |
| `log10()` | 4297.0 | 4302 | 74.02% | Pending optimisation review |
| `pow()` | 1135.0 | 1135 | 19.55% | Pending optimisation review |
| `tanh()` | 649.0 | 649 | 11.18% | Pending optimisation review |
| `atan2()` | 673.5 | 674 | 11.60% | Pending optimisation review |
| `sinh()` | 697.0 | 698 | 12.01% | Pending optimisation review |
| `cosh()` | 649.0 | 650 | 11.18% | Pending optimisation review |
| `asinh()` | 760.0 | 760 | 13.09% | Pending optimisation review |
| `acosh()` | 831.0 | 831 | 14.32% | Pending optimisation review |
| `atanh()` | 775.0 | 776 | 13.35% | Pending optimisation review |

`exp2` exceeds the block period in the two-instance stereo fixture. Retain it
as a high-priority investigation alongside the separate RNBO `exp2~` result.
Inspect math overloads, binary64 promotions and library costs when optimisation
resumes; no matched optimisation has been performed. All flags in this batch
are high median cost, with no isolated-peak flags.

Source: [Gen mathematical device results](../evidence/xiao-smoke-gen-math.json).

## RNBO numeric batch: eight queued cases

The following entries passed their bounded output checks but exceeded the
median-cost screening threshold. Times are whole two-instance stereo fixtures,
256 frames at 44.1 kHz; the block period is about 5,805 µs.

| Exact form | Median µs | Observed peak µs | Median / block period | Follow-up |
| --- | ---: | ---: | ---: | --- |
| `exp2~` | 7494.0 | 7498 | 129.10% | Pending optimisation review |
| `log~` | 3681.0 | 3682 | 63.41% | Pending optimisation review |
| `ln~` | 3680.5 | 3682 | 63.40% | Pending optimisation review |
| `log2~` | 4729.0 | 4730 | 81.46% | Pending optimisation review |
| `log2f~` | 4729.0 | 4730 | 81.46% | Pending optimisation review |
| `log10~` | 4294.0 | 4299 | 73.97% | Pending optimisation review |
| `log1p~` | 3979.0 | 3979 | 68.54% | Pending optimisation review |
| `pow~` | 1141.0 | 1141 | 19.66% | Pending optimisation review |

`exp2~` exceeds the block period in this stereo fixture. Prioritise it when
optimisation resumes. Investigate binary64 math paths and literal/type
promotions in these functions, then compare any Float32 candidate against the
unchanged reference cases. Those causes have not yet been isolated by a matched
optimisation experiment. No optimisation or percentage gain is claimed here.
The remaining flags are high typical cost rather than isolated peak spikes.

Source: [numeric hardware result](../evidence/xiao-smoke-rnbo-numeric.json).
The three output mismatches (`round~`, `isdenorm~`, `fixdenorm~`) remain separate
correctness outcomes; they did not trigger CPU review.

## Earlier batches

The [36-form RNBO arithmetic/logic batch](hardware-smoke.md#rnbo-arithmetic-and-logic-batch)
has **no triggered CPU flags**: medians 41–89.5 µs, largest observed peak 93 µs.

The [first numeric smoke batch](hardware-smoke.md#first-numeric-batch) also has **no triggered CPU flags**.
Its five output mismatches and one compilation failure are correctness/support
outcomes, recorded separately. Other untested objects remain unassessed.

Machine-readable follow-ups are in each result's `cpu_review_backlog` field.
