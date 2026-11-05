# Event and signal unit-conversion fixtures

These original MIT graphs cover 36 separately authored RNBO spellings: 21
numeric-event forms and 15 signal forms. See the [target report](../../../../docs/rnbo-unit-conversions.md).
They extend qualification; aliases, event/signal forms and codebox/Gen surfaces
never inherit results from one another.

The numeric path is `param drive → converter → sig~ → out~ 1`. The signal path
is `(in~ 1 +~ sig~(param drive)) → converter~ → out~ 1`. Every graph copies
`in~ 2` directly to `out~ 2`; the captured 5,120 right words are independently
hashed, including signed zeros, subnormals and finite extrema. Signal input
varies across 16 dyadic levels inside each block; numeric outputs hold between
events. The 21 actual-value actions include repeats, holds and three ordered
changes before callback 10. Actual and normalised parameter readbacks are checked.

The reference uses exact rational dimensional equations, with binary32 input
and one final binary32 output rounding. It does not evaluate generated DSP or
use captured output to fit expectations. Conditions are 44,100 Hz, 256 frames,
120 BPM, 480 ticks per quarter note and stopped 4/4 transport. Examples:

| Unit | Equivalent at these settings |
| --- | --- |
| One beat (quarter note) | 500 ms, 22,050 samples, 480 ticks |
| Two hertz | 500 ms per cycle, one beat, 22,050 samples, 480 ticks |
| One second | 44,100 samples, two beats, 960 ticks |

Reciprocal input domains exclude zero. Other linear forms include negative
inputs. The maximum declared error is 0.008 **samples**, less than 0.2 µs at
44,100 Hz; other unit outputs have separate, smaller limits. All limits,
sources, schedules, transport settings and expected streams are pinned before
compilation. An initial generic harness-ceiling stop is preserved separately;
the new family-specific ceiling changes no per-case reference or limit.

Four manually checked warm callbacks and sixteen timed callbacks give 10,240
output-word comparisons per graph. There are no automatic warm callbacks.
Timing includes the full FX callback and raw right pilot; event setter/routing
totals and peaks are separate. Neither measurement is an isolated kernel cost
or an optimisation gain. Changed transport/tempo, resets, constructor options,
reciprocal zero/nonfinite domains and within-block host event offsets remain
unqualified.

`generate.py --check` verifies all original graphs and two 18-source partitions.
The generator binds installed Cycling ’74 RNBO reference-document hashes and
official reference URLs. The public build, native, target, initial-attempt and
player-restoration receipts retain their separate roles.
