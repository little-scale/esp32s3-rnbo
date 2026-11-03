# XIAO object qualification

## Fast coverage runs

The current priority is short hardware functionality checks with CPU timing,
batching many objects into one upload and leaving the test firmware installed
between batches. The [latest fast batch](hardware-smoke.md#rnbo-arithmetic-and-logic-batch)
checks 36 exact RNBO signal spellings: all pass. The earlier numeric Gen batch
records 15 device scenarios (10 pass, 5 output mismatches) and one compilation
rejection.
[CPU outliers are queued](cpu-review-backlog.md) for future optimisation.
These smoke checks are distinct from the deeper historical tests below.

The active goal is to test every inventoried RNBO object, operation and structure
on the XIAO ESP32-S3 and record compatibility, resource use and performance.
The user has also explicitly included Gen/`gen~` operators and single-sample
processing; see the [full qualification scope](qualification-scope.md). Gen
hardware qualification is separate: the first three history programs now pass,
and fifteen [GenExpr arithmetic spellings](gen-arithmetic-qualification.md) have
their own output/timing/memory checks. Twenty additional
[comparison/logic forms](gen-logic-qualification.md) pass; `step` has a retained
documented-order mismatch. The broader operator inventory remains pending.
The first hardware batch passed on 4 November 2026. The drone was restored,
unpaused at 50%, with all eight compiled parameter defaults after each run.
A final 4,096-frame internal stereo capture contained nonzero output.

The [complete pending-work snapshot](../evidence/xiao-qualification-plan.json)
maps all 1,455 dashboard entries: 1,209 installed exact spellings, 238 codebox
members/types/hooks, one reference-only name and seven host/editor entries.
It also identifies 22 structure-testing axes. Five host/editor entries are
not applicable to device DSP. Each alias and codebox surface needs its own
execution evidence; whole-drone presence does not qualify an individual object.

## First hardware results

| Authored fixture | Output comparison | Mean callback time per 256 frames | Processing time saved |
| --- | --- | --- | --- |
| `cycle-scalar`, four frequency/phase cases | 3,145,728 samples; zero Float32 and PCM differences | 472.68 / 472.98 µs | Not applicable: identical-module control |
| `filters-scalar`, impulse and 0–40 ms delay cases | 2,359,296 samples; zero Float32 and PCM differences | 1,736.12 / 1,232.09 µs | 29.03% |
| `biquad-response`, three stereo FX cases | 2,359,296 pair comparisons; 4,718,592 independent-model checks | 84.43 / 84.42 µs | Not applicable: identical-module control |

The filter comparison changes duration-conversion hoisting only. Both modules
retain Float64 delay storage and the same strict numerical profile. This is a
matched measurement of the complete comb/allpass test graph, including its
excitation code. It is not a separate cost for either filter, or an improvement
measurement for the live drone. The oscillator control measures repeatability;
its timing difference is not an optimisation gain.

The first two Main runs each loaded and finalised four module images, recovered internal RAM and
PSRAM to the recorded baselines, and reported no callback heap operations or
late module allocations. These are dynamic Main-module observations on XIAO.
Other FX forms, MIDI, live replacement and other object/mode combinations need
separate qualification.

These first Main tests compare complete on-device reference/candidate outputs
and check finite values, PCM differences, lifecycle and resources. They do
**not** run an independent waveform model on the board: both logs explicitly
record zero semantic-oracle checks. Existing native mathematical tests remain
separate evidence. The subsequent biquad FX batch below adds independent target output truth.
Further batches cover arithmetic/comparison spellings, codebox state and
language structures. A matching pair alone cannot establish that both outputs
are mathematically correct.

## Independent biquad FX check

The next hardware batch exercises `biquad~` with disjoint stereo input planes
and default, identity and slow-pole coefficient cases. A fresh Float64 difference
equation generates a separately cached Float32 expected output. Both module
passes are checked against this model, including the cache-rounding error bound.
All 4,718,592 semantic sample checks and 18 settled-level checks pass the declared
3e-6 tolerance. The largest observed conservative model-error bound is
1.416e-7. Reference/candidate output comparisons also have zero numerical and
PCM differences.

The two passes use the same module, so their approximately 84.43 µs callback
time is an absolute fixture measurement, with no optimisation gain claimed.
Four images are finalised, internal RAM/PSRAM return to baseline, and callback
heap/late allocation counters stay zero. The drone is restored at 50%.
This qualifies the declared strict two-channel FX form and three coefficient
cases. Other coefficients, overloads, modes, reset paths and related exact
spellings remain separate pending work. See [the complete model and raw target
observations](../evidence/xiao-biquad-control.json).

## Arithmetic and RNBO codebox results

All 13 [original wave4 fixtures](../tests/fixtures/objects/wave4/README.md)
passed on XIAO: 39 case programs, 3,833,856 exact pair comparisons and
7,667,712 independent model checks. Numerical, PCM and raw-word differences
were all zero. The stateful delta program also passed 294,912 exact raw-bit
checks on its unchanged right-channel observer. Its previous-input state
continues across vector boundaries and is reconstructed fresh per pass.

| Exact authored form | Mean callback µs, reference slot |
| --- | ---: |
| `abs~` | 68.37 |
| `minimum~` | 53.52 |
| `min~` | 53.57 |
| `maximum~` | 53.41 |
| `max~` | 53.41 |
| `sub~` | 55.58 |
| `-~` | 55.55 |
| `eq~` | 55.62 |
| `==~` | 55.57 |
| `lt~` | 55.64 |
| `<~` | 55.61 |
| RNBO codebox `+`, `-` | 45.72 |
| RNBO codebox `delta`, `delta.next` | 46.86 |

These are strict identical-module controls; no optimisation gain is claimed.
Times belong to each complete stereo FX fixture: patcher graphs contain two
operator instances, while codebox arithmetic emits sum/difference and the
delta program contains one stateful operator plus an observer. They are not
isolated per-operator costs. Each case has 64 rendered vectors, four zero-input
warmup vectors and three paired rounds; the first 32 rendered vectors per pass
are excluded from timing. This is a short observed workload, not a deadline or
worst-case bound.

The three shared deterministic input programs cover bounded binary32 values in
`[-1,1]`, subnormals, signed zero, equality/adjacent values and vector edges.
The host independently regenerates complete input and expected-output cache
hashes and matches the actual target hashes. Repeated passes are not millions
of distinct inputs. Zero signs of operation outputs have a separate diagnostic
policy; the unchanged observer and identical-module pair require exact bits.
No unsupported rounding mode, arbitrary domain or overload is established.

All 52 loaded images were finalised, internal RAM/PSRAM recovered, and callback
heap/late allocation counts stayed zero. Each isolated run restored the drone
at 50% with its eight compiled defaults. Full records, per-case timing/resource
profiles and raw serial logs are in [the XIAO wave4 evidence](../evidence/xiao-wave4.json).
The earlier native O3/UBSan corpus separately passed 5,111,808 model checks;
those host checks are not counted as XIAO execution.

RNBO codebox is distinct from GenExpr. See the [separate Gen work](gen-qualification.md)
for the first native single-sample tests and the remaining Gen hardware scope.

## Measurement and recovery method

The device is the identified XIAO ESP32-S3, public label `xiao-test-device-01`, with
8 MiB flash and 8 MiB PSRAM. Firmware uses ESP-IDF 5.5, GCC 14.2, a 240 MHz CPU
and 80 MHz octal PSRAM. Tests use 44.1 kHz, 256-frame blocks, four warmup blocks,
512 blocks per case/pass, three paired rounds and seed `0x12345678`.
Timing excludes the first 32 blocks of each pass. The complete callback is timed;
preparation and event application have separate counters. I²S, display and
network are absent from the isolated benchmark.

The runner verifies the exact USB identity, backup hash, executable flash-size
header, application partition, build artifacts and current drone source/ELF.
It checks live defaults and 50% playback before muting, waits for muted readiness,
then writes only the application partition. Restoration is attempted even after
a failed test or lost acknowledgement. Startup50 recovery verifies the compiled
defaults directly, without replaying parameter changes while audible. A failed
restore verification attempts to mute and reports failure. Oscillator/filter
phase is restarted rather than restored.

The unique device identity and original full-flash backup stay private. Public
records use a stable device label and omit the recovery-backup digest. No bootloader or data partition
was written. The [public batch evidence](../evidence/xiao-object-batch1.json)
contains complete comparator summaries, raw serial logs, recovery records and
artifact hashes. Full float output buffers were compared internally; the
benchmark does not download those complete buffers. The retained final drone
capture checks post-restoration signal presence, not benchmark waveform truth.

The [main dashboard](https://little-scale.github.io/esp32s3-rnbo/) now includes
these 15 exact XIAO working-status entries with their board and mode scope in
the row details. Its prior timing percentages remain AMOLED measurements;
XIAO callback times and controls are recorded here without merging measurements.
Gen has its own inventory and native test record.
