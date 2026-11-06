# Explicit float32 audio and delay profiles

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The default remains `float32-strict`. These options change audio precision and
are recorded independently from the delay-range cap and runtime correctness
fixes. Original generated files remain in `originals/`.

```sh
python3 host/compiler/prepare.py \
  --export build/user-patches/3sawsDrone3/export \
  --out build/user-patches/3sawsDrone3/prepared-NEW \
  --class-name rnbos3patch --filter-delay-max-ms 40 \
  --float32-delays --numerical-profile float32-audio-v1
```

`--float32-delays` changes only matching constructor/reference pairs for internal
comb, allpass and ordinary delay rings. Every reader, writer, size calculation,
initializer, reset and step method must match a reviewed RNBO1.4.4 fingerprint;
the DataRef must explicitly be internal. External/data buffers and lookup tables
are excluded. Ring size and interpolation algorithms stay the same. Resource
provenance reports requested samples, allocated power-of-two frames and payload
bytes for each selected ring.

`float32-cycle-v2` admits a catalog of reviewed fixed/scalar/signal frequency and
phase forms. It suffixes decimal coefficients inside whole, fingerprinted
`cycle~` methods. The initial catalog includes the authored sine/MIDI scalar
form, the user's fixed .009/.01 forms, and the original
`tests/fixtures/cycle-signal.rnbopat` signal-frequency/phase fixture. Other
constants or generated forms require a new review. The earlier
`float32-cycle-v1` gate is unchanged.

`float32-audio-v1` extends that catalog to the actual cap40 drone's 30 reviewed
audio methods: five cycles, three saws, four scales, nine arithmetic methods,
two resonators, two combs, two ordinary delays and three pitch conversions.
There are 64 decimal suffix edits. In particular, the pitch conversion now
selects `expf` instead of `exp`. Two comb audio callsites replace the shared
double millisecond conversion with an explicitly local float32 conversion,
adding two `0.001f` constants. Shared `mstosamps(MillisecondTime)`, scheduling,
setup and time methods are byte-identical to the cap40 reference. No integer
phase/truncation algorithm or frame-counter type changes. These profiles do not
promise identical phase increments or output rounding.

Unknown/modified methods, coefficients and already transformed audio input stop
preparation. Fingerprints, per-method edits and before/after source hashes are
saved in provenance. The tools retain only fingerprints, not generated RNBO
method bodies. Tests use actual local exports and skip when those are absent.

The authorized `3sawsDrone3` host comparison used matching Release compilers,
44.1kHz/256 frames, seed12345, one warmup block and three 4096-block workloads.
The reference retained cap40, Float64 rings and strict arithmetic.

| Variant | Platform arena | Maximum float error | Maximum PCM error |
| --- | ---: | ---: | ---: |
| Float32 rings only | 361,240B | 0 in all three workloads | 0LSB |
| Float32 rings and audio, default | 361,240B | 0.00158008 | 25LSB |
| Float32 rings and audio, fast/full modulation | 361,240B | 0.00132750 | 21LSB |
| Float32 rings and audio, high feedback | 361,240B | 0.00308955 | 51LSB |

The cap40 reference used 394,520B. Float32 ring payloads save 33,280B (8.44% of
that arena). All cases were finite and completed without errors or late RNBO
Platform allocations. Audio RMS errors were approximately 0.0000824, 0.0000876
and 0.0003469; RMS level changes were at most 0.0001115%. Storage-only identity
is an observation for these fixtures and workloads, not a universal guarantee.
Full audio clearly exceeds the older cycle-only 2e-6/1LSB comparison limits; it
is a separately named numerical choice.

The authored high-feedback settings can exceed the renderer's PCM headroom;
the float report records those sample counts. Clipping is present in the
reference too, so judge numerical changes from the float companion output.

Evidence is in `build/user-patches/3sawsDrone3/f32delays-comparison/` and
`f32audio-comparison/`. An independent run with seed0x12345678 and four warmup
blocks also found storage identity, no late allocations and full-audio maximum
error0.003439665, with RMS level changes at most0.00011269%.
`independent-float32/audit.json` records its source inverse audit and metrics.

The dynamic full-audio module compiled with a 1MiB maximum arena, zero imported
symbols and a 122,036B normalized ELF. Its report is
`build/modules/3sawsDrone3-cap40-f32audio/build-report.json`. These are host and
compile results. Board timing, listening and display behavior are documented
separately in [the patch qualification](drone3-qualification.md); host timings
do not predict the target's CPU cost.
