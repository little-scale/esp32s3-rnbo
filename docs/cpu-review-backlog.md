# CPU review backlog

The fast hardware runs record typical (median), mean and observed peak callback
time. A case is queued for later investigation if either:

- Its median exceeds 10% of the 256-frame block period at 44.1 kHz (about 580 µs).
- Its peak exceeds both three times its median and its median plus 100 µs.

These are screening rules, not proof that an object needs changing. A flagged
case should be repeated and investigated when optimisation work resumes.
Functional coverage continues first.

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
