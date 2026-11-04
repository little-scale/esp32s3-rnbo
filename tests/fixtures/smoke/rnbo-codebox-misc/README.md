# RNBO codebox miscellaneous finite smoke fixtures

These 22 original five-box FX fixtures exercise exact RNBO codebox names. The
two output lanes expose complex real/imaginary results, asymmetric interpolation
controls, or separate finite scalar inputs. The maximum-number fixture is
autonomous; its declared input objects are intentionally unwired.

The reference fixes each interpolation convention: four-point Lagrange,
full-neighbor-slope Hermite, half-slope Catmull-Rom, and six-point quintic
B-spline. Safe and unsigned operations use the listed small finite domains.
The `ease` and `easexfade` classes select `In_quadratic` (enum 7) with sync
disabled, so these selected outputs are pointwise. `xfademul` uses the default
two-channel phase/wrap/equal-power mode on 0 through 1. Other state, reset,
direction, resource and time-generator modes are outside this scenario.

The fixed 256-frame vector runs repeatedly in the smoke harness. Zero tolerance
is declared for exact selected operations; the other models use an absolute
2e-6 screen. Export and module compilation establish preparation only. Device
output, allocation and timing outcomes are recorded separately by the hardware
run; aliases and other surfaces do not inherit results.

[XIAO hardware evidence](../../../../evidence/xiao-smoke-rnbo-codebox-misc.json)
records 22 passing cases across 225,280 checked output values. The `safepow`,
`cubicinterp` and `easexfade` workloads enter the CPU review backlog. These are
functional and timing observations for the declared modes, with no optimisation
gain claimed.
