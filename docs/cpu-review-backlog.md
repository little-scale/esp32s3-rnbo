# CPU review backlog

The fast hardware runs record typical (median), mean and observed peak callback
time. A case is queued for later investigation if either:

- Its median exceeds 10% of the 256-frame block period at 44.1 kHz (about 580 µs).
- Its peak exceeds both three times its median and its median plus 100 µs.

These are screening rules, not proof that an object needs changing. A flagged
case should be repeated and investigated when optimisation work resumes.
Functional coverage continues first.

The [36-form RNBO arithmetic/logic batch](hardware-smoke.md#rnbo-arithmetic-and-logic-batch)
has **no triggered CPU flags**: medians 41–89.5 µs, largest observed peak 93 µs.

The [first numeric smoke batch](hardware-smoke.md#first-numeric-batch) also has **no triggered CPU flags**.
Its five output mismatches and one compilation failure are correctness/support
outcomes, recorded separately. Other untested objects remain unassessed.

Machine-readable follow-ups are in each result's `cpu_review_backlog` field.
