# Scalar RNBO codebox shaping

These 40 original scalar `codebox~` call fixtures are separate from GenExpr and
RNBO patcher objects. Thirty easing functions use the pinned primary equations,
not an assumed Penner variant. The independent mathematical reference expresses
in/out symmetry and bounce through parabolic vertices. Input phase stays in
[0,1], including endpoints and Float32 neighbors of the bounce boundaries.

Four windows, factor-first interpolation and four bounded integer APIs complete
the batch. Integer operands are small; remainder divisors are nonzero. Overflow,
arbitrary numeric conversions and resource/list/stateful APIs are excluded.

Math uses a predeclared 2e-6 limit; simple interpolation/integers use zero.
`cosineinterp` uses a Taylor cosine internally, so its ideal-cosine 1e-3 screen
is explicitly not a documented universal accuracy guarantee. Rejected sources
and observed mismatches remain outcomes, not reasons to fit the reference.
This catalog alone claims no hardware execution or optimisation gain.

The [XIAO hardware run](../../../../evidence/xiao-smoke-rnbo-codebox-shaping.json) completes all 40 programs across 409,600 output values. Thirty-eight pass. `ease_in_bounce` and `ease_out_bounce` exceed the unchanged 2e-6 mathematical limit, with maximum difference 2.4437904357910156e-6. Eighteen callback costs are queued for CPU review; all memory/allocation gates pass.
