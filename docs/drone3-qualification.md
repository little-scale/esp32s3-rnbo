# 3sawsDrone3 hardware qualification

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The authored `3sawsDrone3` patch runs as a static RNBO instrument on the Waveshare
ESP32-S3 Touch AMOLED 1.8 V2. The final build completed a continuous silent DSP
observation: **300 playing status samples over 303.020 seconds of
source-frame advancement**, with no render overruns, DMA/write/module errors,
non-finite samples, late Platform allocations or successful audio-task heap
allocations/frees. I2S and the touch display stayed active; networking was inactive.
Volume was zero during this observation, while the instrument DSP kept running.

Final controls were restored to the user's **12% volume, Panic latched, ready to
Resume**, including the selected vibrato depth of approximately 0.432. The runner
verified all eight parameter readbacks as float32 values. DSP phase was not
preserved across reconstruction. Controls are RAM state: after reset this build
starts at volume 0 and the source parameter defaults.

## Identified profile

The editable source SHA256 is
`b8b47ad0fa60cde08ea86cef58e851b3fc8431c7f7c391489b2acee5de38f0f5`.
The display preserves its 58 objects and 70 cords, with eight exported controls.
Execution uses 44,100 Hz, 256-frame planar float32 stereo, averaged once into the
mono int16 I2S sink with fixed 0.5 headroom. The selected adaptations are the
explicit 40 ms comb/allpass cap, float32 internal ring storage and
`float32-audio-v1` arithmetic. Scheduler time remains double; warmup is four
blocks with seed `0x12345678`.

The final firmware ELF SHA256 is
`f64cdf654598d72955e9ec5cca6fd9cd3eaa7230def4d95590347826ff9d9ac3`.
Its build report is
`build/firmware-amoled-rnbo-drone3-f32audio-compact/build-report.json`.
The prepared DSP SHA256 is
`84fd64ab3428929c3101d324959cabf09456d053032cfd7600b74da986330f3c`.
Artifact, log, runner, prepared-source and comparison hashes are recorded in
[evidence/drone3.json](../evidence/drone3.json). Raw build products and captures
remain in the ignored local build tree.

## Observed timing and memory

The mean owner-through-PCM render time was **3879.277 microseconds**,
66.827% of the nominal 5804.989-microsecond vector period.
The observed lifetime peak was **4967 microseconds**.
These elapsed measurements exclude blocking driver waits and post-write capture;
they are neither a hard worst-case bound nor complete audio-task CPU accounting.

The explicit PSRAM arena is 393,216 bytes (384 KiB), with 361,240 bytes used and 31,976 bytes
unused. Reducing the earlier 1 MiB reservation releases exactly 655,360 bytes:
reported free PSRAM rises from 7,210,684 to 7,866,044 bytes. Arena usage covers RNBO
Platform allocations; other initialization allocations are separate. The task
heap guard observes successful audio-task heap operations, not every task or ISR.

## Earlier trials and interaction

The double-arithmetic cap40 trial exceeded the render budget: 13,605 microseconds
observed peak and eight overruns. It was rejected and the previous instrument
restored. Memory use alone did not establish real-time viability.

The first float32 trial had zero overruns and a 4,928-microsecond peak, but its
runner incorrectly classified the user's Panic button test as a failure. The
user confirmed testing the controls. The corrected interaction run accepted
Panic as a valid state: 300 polls over 305.010 seconds, with 27 polls playing and the
rest muted. This supplies interaction/Panic coverage rather than five minutes
of continuous DSP.

That interaction run captured 44,100 mono PCM frames while playing at 12% volume.
The capture peak was 0.0977783 and RMS 0.0239238. Its WAV and PCM hashes were
independently verified against the capture sidecar. This is a post-volume device
buffer capture; the user separately confirmed audio and parameter operation.
It is not an external analog or electrical measurement.

## Numerical scope

The original large-ring source and cap40 double-ring variant were compared
separately: three host workloads had maximum absolute sample difference
0.00571084. Float32 storage alone was float/PCM bit-identical in the observed
workloads. Full float32 processing was compared with the cap40 double reference,
not described as identical to the original patch. In the independent three-case
run using the target seed and warmup, maximum absolute difference was 0.003439665;
error RMS/reference RMS was at most 0.030172%, and total RMS level change was at
most 0.00011269%.

An inverse source audit restores the cap40 reference exactly after undoing six
constructor/reference pairs, 64 literal suffix edits and two local float32 duration
conversions. Runtime headers and the shared scheduler/time methods are unchanged.
See [bounded-filters.md](bounded-filters.md) and
[float32-audio.md](float32-audio.md) for the separate choices and comparisons.
These figures describe selected host cases, not a general numerical error bound.

This hardware result concerns this static build and observed settings. The
isolated loader's separate qualification is in
[evidence/dynamic-loader.json](../evidence/dynamic-loader.json); dynamic execution
of this drone, arbitrary RNBO/Gen graphs, network stress and persistent module
installation are not established by this observation.
