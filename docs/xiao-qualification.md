# XIAO object qualification

## Fast coverage runs

The latest [codebox shaping and stateful checks](hardware-smoke.md#rnbo-codebox-continuous-state-instances)
execute 51 scenarios: 48 pass and three retain mismatches, checking 522,240 output
values. Two bounce curves retain their fixed-limit exceedances; `downsamp`
differs from its declared capture-phase reference. The history class source
fails C++ compilation, while a separate port-invalid autonomous-counter fixture
does not invalidate the passing input-driven counter form. All eleven executed
stateful cases retain full twenty-block continuous references. Eighteen passing
shaping contexts add CPU flags, bringing the queue to 76. Memory/allocation gates
pass. The main table now maps 473 exact entries out of 1,455, preserving previous
records and adding no Gen rows.

The [RNBO codebox shaping batch](hardware-smoke.md#rnbo-codebox-shaping-windows-and-integer-helpers)
executes 40 scalar forms and checks 409,600 values: 38 pass, while two bounce
curves exceed their unchanged 2e-6 reference limit by a small amount. Eighteen
passing contexts trigger CPU review, bringing the queue to 76 before the
separate stateful batch. Blackman and three elastic fixture medians exceed the
block period. Memory/allocation gates pass; no optimisation has been applied.

The earlier [codebox range and Gen constant batches](hardware-smoke.md#rnbo-codebox-range-routing-and-conversion-forms)
execute 72 scenarios: 68 pass and four retain comparison mismatches, checking
737,280 output values. Seven codebox source attempts are rejected before
execution; separate valid `mtof`/`ftom` state-instance forms both pass. Six new
CPU flags bring the queue to 58 contexts. All executed images finalise and
memory/allocation gates pass. These add 45 exact RNBO codebox entries, bringing
the main table to 421 mapped entries out of 1,455; Gen adds no main-table rows.

The [Gen named-constant batch](hardware-smoke.md#gen-named-constants-and-configuration-values)
passes all 32 bare-value scenarios and 327,680 bit-exact output checks. It covers
28 mathematical spellings plus sample-rate/vector-size names at 44,100 Hz/256
frames, with 37 µs medians, peak 42 µs and no CPU-review flags. These separate
Gen results do not add RNBO main-table mappings.

The earlier RNBO codebox numeric and [Gen range checks](hardware-smoke.md#gen-range-routing-and-conversion-calls)
execute 72 scenarios: 65 pass and seven retain comparison mismatches, checking
737,280 output values. One additional Gen `gate` syntax form is rejected before
execution. Twenty new CPU flags bring the separate review queue to 52 contexts.
Gen's three fast-function exceedances are approximation-quality screens, not
universal malfunction findings; `ftom` retains its continuous-pitch mismatch.
All executed images finalise and memory/allocation gates pass. Gen adds no RNBO
main-table entries; the 43 new RNBO codebox entries bring that table to 376
mapped exact spellings out of 1,455.

The [RNBO codebox numeric batch](hardware-smoke.md#rnbo-codebox-numeric-and-mathematical-calls)
adds 43 executed calls and 440,320 output checks: 40 pass and three retain round/
denormal mismatches. Fourteen callback costs are queued for CPU review;
`exp2()` has a 7.499 ms median against the 5.805 ms block period. No optimisation
is applied or saving claimed. These 43 exact codebox entries are separate from
matching patcher and Gen names.

The [RNBO codebox batches](hardware-smoke.md#rnbo-codebox-arithmetic-and-named-constants)
add 83 passing device scenarios and 849,920 output checks: 43 arithmetic/logic
forms and 40 named-value constants. The constants are bit-exact; arithmetic
retains 2,880 allowed operation zero-sign differences. Named `mod(a,b)` and
`^^` infix remain unverified after compilation/frontend rejection respectively,
with no device execution. No CPU-review flags trigger. These add 85 mapped
codebox entries; older patcher, Gen and measured optimisation records are preserved.

Two additional [event/constant batches](hardware-smoke.md#additional-events-and-signal-constants)
execute 61 scenarios: 56 pass, with five retained event mismatches (`isdenorm`,
`fixdenorm`, `rmod`, `!%`, `step`). They add 624,640 output checks and 840 parameter
updates/readbacks, with no CPU-review flags. All 21 constant scenarios are
bit-exact. The main table gains 60 mapped exact spellings; existing `sig~`
composition status is preserved with its separate initial-value evidence.
These short observations do not qualify every mode or within-block scheduling.

The current priority is short hardware functionality checks with CPU timing,
batching many objects into one upload and leaving the test firmware installed
between batches. The [parameter-driven event batch](hardware-smoke.md#rnbo-parameter-driven-event-batch)
passes all 35 exact event spellings,735 updates/readbacks and 358,400 output checks.
It verifies supplied boundary ordering and a raw-bit audio observer, with no new
CPU flags. The [function/conversion batch](hardware-smoke.md#rnbo-functions-and-conversions-batch)
executes 35 RNBO forms: 34 pass their declared limits, `fasttan~` exceeds the
selected approximation threshold, and eleven CPU costs are queued. The default
`mtof~` shared lookup is preserved and peaks at 262,416 arena bytes.
The [earlier numeric batch](hardware-smoke.md#rnbo-numeric-and-maths-batch)
checks 33 RNBO signal forms: 30 pass, three have output mismatches, and eight
trigger CPU review. The previous arithmetic/logic batch checks 36 spellings:
all pass. The earlier numeric Gen batch
records 15 device scenarios (10 pass, 5 output mismatches) and one compilation
rejection.
[CPU outliers are queued](cpu-review-backlog.md) for future optimisation.
The subsequent [Gen mathematical batch](hardware-smoke.md#gen-mathematical-batch)
adds 27 device passes within declared limits, four C++ compilation failures and
three parser rejections, with thirteen CPU-review flags. RNBO and Gen outcomes
remain separate. The [new stateful Gen batch](hardware-smoke.md#gen-stateful-and-per-sample-batch)
passes twelve programs/nine exact names, checking 122,880 values with continuous
state across all twenty callbacks. No additional CPU-review flags trigger.
These smoke checks are distinct from the deeper historical
tests below.

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

## Event and parameter interface limits

The current [event structure](../module-sdk/include/rnbo_s3_module.h) has no
sample timestamp or offset. The [dynamic wrapper](../module-sdk/dynamic/rnbo_s3_dynamic.cpp)
dispatches parameter/MIDI events at `RNBO::TimeNow`, advertises boundary events,
and accepts only 256-frame process calls. Ordinary parameter control exists in
the runtime and older parameterised fixtures. The fast batch compiler now admits
zero to 32 ordinary numeric parameters, and the new event batch verifies a single
linear/unstepped control at full-block boundaries across two batches of75 exact event graphs.

Those facts do not establish within-block host-event accuracy. A timed-event
interface or a separately admitted scheduled-kernel route is required before
such tests can qualify sample-offset controls; splitting this ABI into one-frame
calls would be rejected rather than prove sample accuracy. Further parameter modes and a timed-event extension remain pending work within the goal.
