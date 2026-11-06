# Native Max export comparison

The comparison used **Max 9.1.4 / RNBO 1.4.4**, actual Max C++ Minimal Exports,
the same baseline Float32 wrapper, and **44,100 Hz / 256 frames** on both routes.
The older route reconstructed RNBO graphs using internal APIs and additionally
lowered visual Gen. Native export delegates that work to Max.

## Computer output comparison

Eight source programs were exported in Max, without running our visual Gen
lowerer. Canonical UI port metadata and bijective object-ID renaming were used
only to stage the original fixtures inside Max; object texts, line order and
Gen graphs were retained. Five complete output pairs are bit-identical across
**51,200 paired words**: spline constructor, explicit-input spline, gentle curve,
edge outlet and one-sample history. Route agreement does not override the
original independent references: spline constructor and edge retain their
previous outside-screen results.

Compound curve faults at event 13 before callback 10 on both routes, recording a
late allocation. Line ramp records a platform error at callback 13 on both.
Their prior captures match exactly; neither is a complete successful run.
Including those partial prefixes, **62,976 paired words** match bit-for-bit.
The subsequent [diagnosis](native-ramp-diagnosis.md) identifies an event-rate
`line` clock rounding loop that exhausts the queue, and overflow-list storage
for compound `curve~`. Private candidates complete both tests; the original
comparison receipts and production wrapper remain unchanged.

Native visual Gen modulo **compiles and executes** where the custom visual
lowerer produces an undefined `safemod` helper. Against the original zero-limit
reference, native modulo retains 80 rounding differences, maximum
**5.960464477539063e-8**, plus 1,240 additional observational signed-zero
differences. It is a compatibility improvement, not an exact-reference pass.

Evidence: [staging receipt](../evidence/max-export-parity-stage.json),
[complete native comparisons](../evidence/max-export-parity-native.json),
[prepared target identities](../evidence/max-export-parity-preparations.json).
Generated headers and executable artifacts stay in ignored build directories.

## XIAO CPU comparison

Three contexts ran **A–B–B–A** with two fresh images per route. Every image ran
four manual warm callbacks and sixteen timed callbacks in a 1 MiB arena.
All **12 checks pass**, covering **122,880 output words**, with no CPU flags.

| Exact context | Previous route median | Max export median | Audio callback CPU, each | Peak, each |
| --- | ---: | ---: | ---: | ---: |
| Gentle `curve~` | 318 µs | 318 µs | 5.48% | 324 µs |
| Explicit-input spline interpolation | 141 µs | 141 µs | 2.43% | 146 µs |
| Gen one-sample history | 42 µs | 42 µs | 0.72% | 47 µs |

There is **no measured CPU advantage** in these contexts. Times describe full
isolated audio callbacks, excluding I²S, UI and Wi-Fi; they are not total chip
CPU, isolated object costs or universal speed predictions. Each median pools
32 timed callbacks per route. The normal player and saved controls were restored
and its frame counter advanced with zero recorded faults.

Evidence: [XIAO checks](../evidence/xiao-max-export-parity.json),
[player restoration](../evidence/xiao-smoke-max-export-parity-player-restoration.json).
Only these exact native-export contexts have this hardware comparison. The
historical inventory does not automatically gain native-export verification.

## Main package through the migrated Studio

A fresh Max-exported sine Main subsequently passed the actual Studio HTTP build
path: native startup screen, Xtensa module build, zero-import inspection and a
48,862-byte player package. Native export preparation has no importer-helper
dependency. Its source/adaptations and package identity are in the
[intake receipt](../evidence/native-export-intake.json).

On the connected XIAO, 32 telemetry polls over **31.41 seconds** observed
**1,385,472 advancing frames** and zero recorded runtime, allocation, DMA,
queue, nonfinite, clipping or deadline faults. Polled player render median was
**737.5 µs (12.70%)**, reported peak 1,138 µs. This includes PCM conversion and
excludes the I²S wait; polling is not a distribution of every callback and is
not comparable to the isolated three-context table as an object cost.

Four frequency changes (220, 440, 880, 440 Hz), a level change and Pause/Resume
passed actual parameter/module-position readback. Queued control acknowledgement
is distinct from eventual readback; the checks wait for the observed value.
No DAC capture or listening confirmation was available. The exact previous
package and live controls were restored, with advancing frames and zero faults.
See the [player check and restoration receipt](../evidence/xiao-native-export-player.json).
