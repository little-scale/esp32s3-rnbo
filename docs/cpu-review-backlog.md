# CPU review backlog

The fast hardware runs record typical (median), mean and observed peak callback
time. A case is queued for later investigation if either:

- Its median exceeds 10% of the 256-frame block period at 44.1 kHz (about 580 µs).
- Its peak exceeds both three times its median and its median plus 100 µs.

These are screening rules, not proof that an object needs changing. A flagged
case should be repeated and investigated when optimisation work resumes.
Functional coverage continues first.

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
