# Explicit comb/allpass delay cap

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

`prepare.py --filter-delay-max-ms 40` is an optional, separately recorded
adaptation for the reviewed RNBO 1.4.4 comb~/allpass~ kernels. The default
preparation preserves the generated DSP source. The cap applies to every
supported comb/allpass in the export; ordinary delay~ is unchanged. Positive,
finite caps up to 1,000 ms are accepted. Unknown kernels or allocation paths stop
preparation, and requesting a cap on an export without these filters fails.

The initial implementation deliberately retains `Float64Buffer<double>`, the
original `mstosamps(MillisecondTime)` call, fractional readers, sample rate and
double scheduler. It adds an upper limit to the input of that conversion and
changes the rings' generated capacity expressions. Each ring requests
`ceil(maximum_ms * 44.1) + 2` samples and retains the generated power-of-two
rounding. 40 ms therefore requests 1,766 samples and allocates 2,048 double frames,
16,384 bytes per ring. Each filter has two rings.

The source bounds are a user-selected contract. This implementation does not
infer bounds from patch coordinates, parameters or the first comb argument.
In RNBO that first argument is the initial delay time
([RNBO comb~ reference](https://rnbo.cycling74.com/objects/ref/comb~?v=1.3.0)). An explicit cap can
change sound when its input exceeds the cap. Even within the cap, smaller ring
indices change fractional-delay rounding, so bit identity is not claimed.

Full normalized kernel hashes guard fixed, scalar and signal-rate inputs.
Normalization permits generated names and direct source argument values, while
retaining the rest of each algorithm. Separately guarded capacity, allocation,
initialization, reset, constructor and reference layouts ensure that the
reported frames still describe the actual generated allocation path. Originals
remain in the prepared tree. Provenance records source/transformer/output
hashes, cap, storage and conversion policy, and every affected ring's frames and
payload bytes. The helper is also covered by compiler build source inventories.

The concept and explicit setting were reviewed against FM1's
`rnbo/tools/bounded-filters.cjs` and `rnbo-loader/BOUNDED-FILTERS.md`. This is a
separate Python implementation for ESP32. It does not apply FM1's float32
buffer conversion, float32 duration conversion, or reader integer-cast changes.

## Local 3sawsDrone3 evidence

The authorized editable source SHA256 is
`b8b47ad0fa60cde08ea86cef58e851b3fc8431c7f7c391489b2acee5de38f0f5`.
The original source, message values, loadbang serials and controls are preserved.
The fresh large-ring prepared baseline and explicit cap40 prepared tree are
under ignored `build/user-patches/3sawsDrone3/`. The original desktop file was
read only.

Two modulated combs use four generated 65,536-frame double rings by default:
2,097,152 payload bytes. The 40 ms variant uses 65,536 payload bytes across these four
rings. The measured host RNBO Platform arena consumption falls from 2,426,136 to
394,520 bytes, including lookup tables and allocation metadata. This is RNBO
Platform arena consumption, not complete heap or target initialization peak.

`compare_filter_cap.py` renders three deterministic cases, each 4,096 blocks:
2,097,152 interleaved float sample words, 23.778 seconds at 44,100 Hz, seed 12,345 and
one warm-up block. The unchanged baseline uses a 4 MiB arena; cap40 uses 1 MiB.
All cases complete with zero late Platform allocations, runtime errors or
non-finite samples.

| Case | Maximum absolute sample difference | RMS sample error | Relative total RMS level difference |
| --- | ---: | ---: | ---: |
| Defaults | 0.00344825 | 0.000161359 | 0.00008563% |
| Fast, full modulation | 0.00168046 | 0.000163674 | 0.00006348% |
| High feedback | 0.00571084 | 0.000918891 | 0.00005211% |

The error RMS relative to reference RMS is at most 0.07489% across these cases.
These are observations on this patch and host compiler, not a general error
bound or ESP32 performance result. The full report, parameter settings, build
identities and raw renders are in
`build/user-patches/3sawsDrone3/cap40-comparison/comparison.json`.

The patch's own output exceeds unity at the supplied defaults and reaches
approximately 7.45 in the high-feedback diagnostic. At fixed 0.5 PCM headroom,
the default comparison has 38 sample words above the clipping threshold at
volume 100%. Playback volume is a separate final-sink control; it should remain
conservative without changing the authored DSP. Reducing buffer capacity does
not provide gain limiting.

Reproduce preparation and comparison with fresh output directories:

```sh
python3 host/compiler/prepare.py --export build/user-patches/3sawsDrone3/export \
  --out build/user-patches/3sawsDrone3/prepared-cap40-new \
  --class-name rnbos3patch --role main --filter-delay-max-ms 40
python3 -m unittest discover -s host/compiler -p test_bounded_filters.py -v
python3 host/compiler/compare_filter_cap.py \
  --reference-renderer build/user-patches/3sawsDrone3/host-original/rnbo_render \
  --bounded-renderer build/user-patches/3sawsDrone3/host-cap40/rnbo_render \
  --out build/user-patches/3sawsDrone3/cap40-comparison-new
```

The raw editable file is not needed for comparison once its identified prepared
baseline and host binaries exist. Loader, allocation and DSP hardware evidence
are tracked separately from this host comparison.

The independent fixed/scalar/signal input regression graph is provided as
`tests/fixtures/bounded-filters.rnbopat`. Generate its local test export with
`node host/export/export.mjs tests/fixtures/bounded-filters.rnbopat --out build/bounded-filter-fixtures/export`.
Its six filters exercise both comb and allpass kernels. The ordinary cap tests
also compile with the original `float32-strict` profile. Optional float32 ring
storage and audio arithmetic have separate controls and evidence in
[float32-audio.md](float32-audio.md); the measurements above retain the original
double ring storage and duration conversion.
