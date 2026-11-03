# XIAO object qualification

The active goal is to test every inventoried RNBO object, operation and structure
on the XIAO ESP32-S3 and record compatibility, resource use and performance.
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

The filter comparison changes duration-conversion hoisting only. Both modules
retain Float64 delay storage and the same strict numerical profile. This is a
matched measurement of the complete comb/allpass test graph, including its
excitation code. It is not a separate cost for either filter, or an improvement
measurement for the live drone. The oscillator control measures repeatability;
its timing difference is not an optimisation gain.

Both runs loaded and finalised four module images, recovered internal RAM and
PSRAM to the recorded baselines, and reported no callback heap operations or
late module allocations. These are dynamic Main-module observations on XIAO.
FX, MIDI, live replacement and the other object/mode combinations still need
separate qualification.

These first Main tests compare complete on-device reference/candidate outputs
and check finite values, PCM differences, lifecycle and resources. They do
**not** run an independent waveform model on the board: both logs explicitly
record zero semantic-oracle checks. Existing native mathematical tests remain
separate evidence. The next batches add independent target output models,
external stereo FX inputs, arithmetic/comparison spellings, codebox state and
language structures. A matching pair alone cannot establish that both outputs
are mathematically correct.

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

The [main dashboard](https://little-scale.github.io/esp32s3-rnbo/) retains the
existing AMOLED/native evidence. Its prior percentages are not XIAO results;
this board's observations remain separate until the dashboard can express
board-specific qualification without merging measurements.
