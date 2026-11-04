# CPU review backlog

The fast hardware runs record typical (median), mean and observed peak callback
time. A case is queued for later investigation if either:

- Its median exceeds 10% of the 256-frame block period at 44.1 kHz (about 580 µs).
- Its peak exceeds both three times its median and its median plus 100 µs.

These are screening rules, not proof that an object needs changing. A flagged
case should be repeated and investigated when optimisation work resumes.
Functional coverage continues first.

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
