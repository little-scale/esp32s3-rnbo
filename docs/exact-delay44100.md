# Exact fixed-rate audio delay conversion experiment

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

A private comb/allpass prototype converts already-materialized Float32 audio
durations into sample counts using 32-bit integer arithmetic. At 44,100Hz and
0..40ms it reproduces the original Double calculation's Float32 return, including
rounding. Other inputs and rates retain the original capped Double fallback.
Signal durations are still read and converted every sample. Shared scheduler
time conversion, ring storage, interpolation and feedback are untouched.

On the ESP32-S3, four authored signal-modulated filter cases passed 3,145,728
numeric float comparisons with zero difference and exact PCM. Total callback
time fell from 13,005,048 to 11,353,630 microseconds over 5,760 timed vectors per
variant, about 12.7%. This is the complete Main fixture, including its excitation
objects, in an offline harness without I2S/UI/networking. All four images were
finalized, measured heap baselines recovered, and the drone and live controls
were restored. It does not establish a universal deadline or a live-player gain.

The candidate module grows by 304 bytes. Its inlined fast spans contain no
helper calls; the standalone O2 integer core is 190 bytes. Original Double work
remains in fallback, rings, coefficients and clock paths. Static instruction and
file-size observations are separate from the measured callback improvement.

The arithmetic uses the Float32 significand `M` and exponent. The exact scale is
`441/10`; `q = 88*M + M/5` and `r = M%5` represent `441*M/5` as `q + r/5`.
Both fit 32 bits. Integer shifts, remainder checks and explicit nearest/even
packing handle normal, subnormal, tie and carry cases. The original Double
literal's small positive bias cannot cross non-tie Float32 midpoints; at exact
ties the intermediate Double rounding preserves the exact midpoint.

Independent native Release and sanitizer runs each enumerate all 1,109,393,409
nonnegative Float32 bit patterns through 40ms. All match both an explicitly
stored original Double pipeline and an independent widened-integer rational
oracle. Additional rate/fallback and edge cases pass. Four real native patch
cases compare 8,388,608 float/PCM words exactly. The mathematical/source proof
and inverse substitutions were independently reviewed before the board run.

This remains a **private prototype**, pending production source/domain admission
and further mode coverage. Its proof assumes nearest/even rounding and Float32
audio inputs; arbitrary Double scheduler values and floating exception status
are outside that claim. The [sealed evidence](../evidence/exact-delay44100.json)
binds the original native reports, source/module identities and subsequent target
observations, superseding only their earlier pending-target status.
