# GenExpr range, routing and functions

These 30 original exact registered call forms use GenExpr in `gen~`, separately
from RNBO patcher/codebox objects. Every finite input vector, literal argument
and tolerance is declared before execution. The catalog retains rejected forms;
compilation is not a device pass.

Range bounds are explicit. Linear scale is unclamped; fold reflects inclusive
endpoints, while wrap uses a half-open range. Routes use integer choices only.
Cartesian/polar operations observe both returned coordinates. Pitch conversion
uses tuning 440 and fractional MIDI notes; T60 is amplitude decay to 0.001 over
a number of samples. Configuration is 44,100 Hz / 256 frames.

Exact dyadic checks use zero tolerance. Ordinary mathematics uses 2e-6; selected
unit conversions use 5e-4 in their output units. Fast-function comparisons use
an ideal-math 1e-3 screening threshold, not a documented accuracy guarantee.
`fixnan` and `isnan` receive finite inputs only and do not qualify nonfinite
repair/detection. Other domains, aliases, argument forms and optimisations are
not inferred.

The [XIAO hardware run](../../../../evidence/xiao-smoke-gen-range.json) completes 29 programs: 25 pass, three fast functions exceed the declared ideal-math threshold, and `ftom` returns integer-rounded notes against the continuous-note reference. The selected `gate` source is rejected by the exporter and is not executed. Six callback costs are queued for CPU review; all memory/allocation gates pass.

The default `mtof` resource is retained: two buffer views share one 65,536-element Float32 table. All modules reserve a 1 MiB arena ceiling in this run; measured `mtof` arena high-water is 262,256 bytes. The initial 4 KiB module cohort was saved and was never flashed, because resource inspection found the table before execution. Program bodies, test vectors and numerical limits are unchanged between those cohorts.
