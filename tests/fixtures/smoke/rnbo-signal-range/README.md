# RNBO signal ranges, conditions and shaping

These 37 original flat patcher fixtures use actual RNBO signal objects and
explicit port/literal settings. They are separate from matching codebox/Gen
operations and exclude stateful `tri~` and control/ramp router scenarios.

The two coordinate converters expose both outputs of one operator. Smoothstep
has fixed lower/upper edges -1/1 with phase wired to its third inlet. Comparison
pass-through forms return their left operand, not a boolean. Eight exact log
constant spellings are autonomous sources with unused declared audio inputs.

T60 uses amplitude decay to 0.001 over a number of samples. The inverse case
limits coefficients to 0.125 through 0.5. Box/triangle, kink and quantization use
explicit literal settings; quantization declares upward half ties for this
source. The `step~` reference follows its primary digest `not(in1 < in2)` with a
zero threshold; producer disagreement is retained rather than fitted to pass.

Simple/constant cases use zero tolerance; ordinary math uses 2e-6. Fast functions
and Taylor-based cosine interpolation use an ideal 1e-3 screening threshold,
not a universal accuracy guarantee. Compilation is not hardware execution;
other modes, aliases, domains and optimisation gains remain unqualified.

The [XIAO hardware run](../../../../evidence/xiao-smoke-rnbo-signal-range.json) completes all 37 cases across 378,880 output values: 34 pass, while `step~`, `fastpow~` and `fastexp~` retain their declared-reference mismatches. Six callback costs are queued for CPU review; all memory/allocation gates pass and no numerical limit is changed after execution.
