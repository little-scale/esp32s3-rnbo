# GenExpr finite math and audio-configuration constants

These 32 original sources use **bare GenExpr values in `gen~`**, not RNBO
patcher or codebox constants. Every exact spelling, including aliases, has its
own fixture. The declared FX inputs remain unused; both outputs hold the value.

Fourteen mathematical constants (28 spellings) use independent ideal values
rounded once to binary32. The separate `samplerate` / `SAMPLERATE` and
`vectorsize` / `VECTORSIZE` fixtures declare the surrounding audio configuration
of 44,100 Hz / 256 frames as their reference. A producer discrepancy remains a
reported mismatch; expected values are not fitted to generated output.

All cases predeclare zero tolerance. Other syntax forms, elapsed/voice/FFT
queries, nonfinite values, other configurations and optimisation gains are
outside this batch. This catalog alone claims no device execution.

The [XIAO hardware run](../../../../evidence/xiao-smoke-gen-constants.json) passes all 32 bare-value programs with zero bit differences across 327,680 output values. Both configuration alias pairs produce 44,100 Hz / 256 frames. There are no CPU-review flags or memory/allocation failures; these are the authored audio Gen configuration tests.
