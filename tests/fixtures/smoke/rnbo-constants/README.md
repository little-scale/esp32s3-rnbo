# Autonomous signal constants

These 21 original stereo FX fixtures each name one RNBO spelling explicitly.
The 18 mathematical-constant spellings ignore the two declared inputs.
`samplerate~` and `vectorsize~` are checked only under the fixed 44,100 Hz /
256-frame configuration. `sig~` uses initial values 0.25 (left) and -0.5 (right);
message updates and impulse modes are outside this scenario.

`reference.py` derives mathematical values independently, rounds once to
binary32 and predeclares zero absolute error. Every alias has its own authored
fixture. Compilation and subsequent device outcomes are separate; this catalog
by itself claims no execution, optimisation gain or complete object coverage.

The [XIAO run](../../../../evidence/xiao-smoke-rnbo-constants.json) passes all 21 cases with zero bit differences across 215,040 output values. There are no CPU-review flags or allocation failures. These results cover the declared initial values and configuration; see the [hardware record](../../../../docs/hardware-smoke.md) for timings.
