# Implementation status — 3 November 2026

The **Waveshare ESP32-S3 Touch AMOLED 1.8 V2** has been qualified running the supplied
`3sawsDrone3` patch with an FM1-style graph, a 40 ms comb limit and optional
float32 delay storage/audio arithmetic. The user confirmed audio and touch
parameter control. The current
[AMOLED interface](amoled-controls.md) provides a single Pause/Resume button,
a Patch/Params page switch, eight wide vertical parameter bars with continuous cross-bar
dragging, a thicker volume slider and a post-volume output meter. The user
confirmed the continuous gesture works well. See [patch qualification](drone3-qualification.md)
and [the numerical choices](float32-audio.md). The original firmware has a
private full-flash backup, and earlier readback
verified that the original bootloader, partition table, NVS and PHY bytes below
the application are unchanged.

The earlier compact drone build completed 300 continuously playing status polls
over 303 seconds, with the output volume set to zero for the timing test.
Average render work was 3,879.3 µs (66.83% of one audio core), peak 4,967 µs,
against a 5,805 µs block period. There were no render overruns, DMA/write/module
errors, non-finite samples or late audio-owner allocations. Its arena uses
361,240 of 393,216 reserved bytes, freeing 655,360 bytes compared with the
earlier 1 MiB reservation. This is measured workload evidence, not a hard
worst-case bound or a Wi-Fi qualification.

That earlier measurement used firmware ELF
`f64cdf654598d72955e9ec5cca6fd9cd3eaa7230def4d95590347826ff9d9ac3`.
It is historical evidence for that build, rather than a timing qualification
of the newer interface.

The latest verified installation is the wide-bar GUI with a single playback
button, ELF
`722047477ce7dd2d46c1531e1c3de1ab70f0b4c2b7bf20f35fede45467fef78c`.
It retains the qualified optimised drone export, including unused-table
omission: the arena uses 99,088 of 131,072 reserved bytes. The installation
check captured silence → signal → silence at volume 0 → 5 → 0, restored all
eight parameter values, volume and Pause state, and observed no render
deadline overruns or allocation/module/DMA/write faults. The subsequent user
trial of the preceding wide-bar build confirmed easier continuous dragging.
The newer single-button installation restored the freshly saved 25% volume,
paused state and all eight parameter values, with no observed faults. This is
the last verified RNBO snapshot, not a guarantee of current live settings.
Work is now computer-only; the board may run other firmware. Future hardware
work needs fresh identification and recovery evidence for the then-current
image. Cold startup uses zero speaker volume; controls remain RAM state. The preceding
GUIv3 image and its recovery observations remain historical evidence.
See [the current GUI installation evidence](../evidence/amoled-gui-v4.json) and
[the table-omission review](unused-mtof-table.md).

## Hardware qualification

The board reports ESP32-S3 revision 0.2, 16 MiB flash and 8 MiB PSRAM. Firmware
and module source identities are recorded in every capture and qualification.

| Check | Recorded result |
| --- | --- |
| Strict oscillator: volume, actual/normalized pitch, Panic/resume | 8 cases passed |
| Optimized oscillator: same controls and capture checks | 8 cases passed |
| Strict and optimized four-voice MIDI | 19 cases passed per profile, including four simultaneous voices, independent release, sustain, stealing and stale note-off |
| Five-minute MIDI stress per profile | 2,400 acknowledged events, nine concurrent periodic captures, no missed render deadlines or late allocations |
| Ten detached reconstructions after each stress run | Free internal RAM and PSRAM totals unchanged |
| Allocation guard negative test | One intentional 16-byte audio-task allocation detected; output became exact digital silence; clean operation restored |
| Host versus target oscillator PCM | 44,100 samples matched exactly in both comparisons after integer-vector alignment, without gain or fractional phase fitting |
| Native ELF loader fixture | 32 measured cycles with two simultaneous images, constructor/finalizer/callback checks and exact heap recovery passed |
| Real RNBO dynamic modules | 132 loads/unloads, 32 lifecycle rounds, 378,368 exact float/PCM comparisons, stereo FX and four distinct MIDI notes; free memory recovered |
| FM1-style patch view | Actual 58-object/70-connection graph; native LVGL touch simulation and user-confirmed audio/parameter control |

During both MIDI stress runs, free internal RAM stayed at 190,499 bytes and free
PSRAM at 7,197,948 bytes. Audio stack headroom stayed above 12 KiB. The largest
contiguous PSRAM block decreased once after initial reconstruction, then remained
bounded across the recorded cycles; total free memory did not decrease.

Real RNBO modules also passed the [isolated loader qualification](dynamic-loader.md).
Live replacement in the permanent audio/UI pipeline, independent Main-to-FX
processing and flash maintenance still require separate integration.
External clock/data signals were not measured with
electrical test equipment. Speaker/display observations came from the user;
software PCM capture is a separate evidence category.

## Measured compiler optimization

The optional `float32-cycle-v1` profile changes exactly two coefficients in each
qualified RNBO 1.4.4 oscillator kernel to float32 literals. It retains integer
phase arithmetic, lookup/interpolation, buffers and double scheduler time.
The strict profile remains the default.

The two runs used matching firmware sources, toolchain, configuration and
dependencies. Only the prepared numerical profile differed.

| Five-minute four-voice workload | Strict | Optimized |
| --- | ---: | ---: |
| Average render time per 256-frame block | 3,311.7 µs | 2,003.4 µs |
| Average share of one audio core | 57.0% | 34.5% |
| Highest observed render time | 4,276 µs | 3,082 µs |
| Render deadline overruns | 0 | 0 |
| Observed late audio allocations | 0 | 0 |

Average render work decreased **39.5%**, about **1.65× faster** in this workload.
Render timing covers audio-owner events through final PCM. I²S waiting and
post-write capture are measured separately. The peaks are observations, not
hard timing bounds, and Wi-Fi was inactive.

All 36 authored host comparison cases produced identical final float32 and PCM
samples. An exhaustive intermediate-value check found small fraction differences,
so this is not a general bit-identity promise for arbitrary patches or feedback.
See [the numerical profile documentation](../host/README.md).

## Oscillator recovery image and earlier evidence

The known-good oscillator recovery application is
`build/firmware-amoled-rnbo-sine-cycle-f32/`, with ELF
identity `b14f63ef2f56e30732afec7c893fd68f68d22e584d023689cac524ce5c901ca4`.
It renders the autonomous 440 Hz oscillator, level 0.2. Its earlier read-only
snapshot showed the user's selected **28% volume**, running, with no faults.
Controls are RAM state; startup defaults apply after a reset.

Machine-readable results and links to raw logs/captures are in
[amoled-v2-hardware.json](../evidence/amoled-v2-hardware.json). Detailed local
reports live under `build/hardware/amoled-first/`. The initial host-only snapshot
is retained in [initial-validation.json](../evidence/initial-validation.json);
later hardware results supersede its unqualified status. The loader test was
rebuilt with a short USB-attachment delay for complete log collection.

Software validation also includes 25 compiler/admission tests, 36 client tests,
46 strict/optimized native fixture checks, 34 upstream loader host regressions,
four emitted-loader validation checks, and five earlier UBSan runtime checks.
Generated code and runtime notices remain in ignored local build directories.
Imported source/license identities are in [UPSTREAM.json](../UPSTREAM.json).

The expanded source now passes 39 compiler/admission tests, 16 dynamic host
tests, seven layout tests, three actual-XAM importer tests, three portable
runtime tests and native LVGL interaction checks. The XIAO profile also rebuilds
with the current shell; no XIAO hardware was attached. Local macOS
AddressSanitizer binaries stalled at startup, so this session does not claim a
new ASan pass. The portable tests passed without it; the public Linux workflow
runs the sanitizer configuration separately.

## Remaining implementation gates

The local RNBO 1.4.4 exporter, validated manual import, native compiler route,
static C ABI, caller-owned dynamic SDK, bounded owner events, allocation guards,
capture and FM1-style UI are implemented. The instrument currently compiles a
patch into the application; the separate dynamic loader test runs actual RNBO
images with audited imports and private allocation.

Next comes integration of loaded RNBO images with the live audio/UI lifecycle.
Persistent `.rnbos3` packages,
known-good recovery, independent Main/FX lifecycle, authenticated Wi-Fi/group
deployment, full browser conversion and broader RNBO/Gen coverage remain later
work. XIAO has independent compiled profiles but has not been tested on hardware
in this session.
