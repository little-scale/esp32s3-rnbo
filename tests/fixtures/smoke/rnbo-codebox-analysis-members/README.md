# RNBO codebox analysis, oscillator and noise members

Twenty-two original source scenarios exercise eleven exact member names:
`average.next/reset`, `average_absolute.next/reset`, `average_rms.next/reset`,
`cycle.next/reset` and `noise.next/reset/seed`. These are RNBO codebox calls;
Gen and related patcher objects keep separate identities and evidence.

Contracts come from the installed RNBO 1.4.4 operator declarations and official
[absolute-average](https://rnbo.cycling74.com/codebox/ref/average_absolute),
[RMS-average](https://rnbo.cycling74.com/codebox/ref/average_rms),
[cycle](https://rnbo.cycling74.com/codebox/ref/cycle) and
[noise](https://rnbo.cycling74.com/codebox/ref/noise) member references.
All programs use two instances and a finite signed/dyadic stereo vector.

## Predeclared mathematical and screening policies

- Moving means use independent `fsum` of the available history, not a copied
  generated running-sum algorithm. Fixed windows are 8/16 samples. Absolute
  means apply `abs`; RMS means square, average and take the square root.
  Startup uses the number of available samples, with no zero-padding divisor.
- Explicit `reset()` calls follow different left/right schedules, including
  consecutive calls and sample ordinals 255/256 and 511/512. Isolated pulses
  separately exercise `next`'s reset argument; no held-gate convention is guessed.
- Window-change programs request 8→5→3 samples on the left every 73 samples and
  16→7→4 on the right every 91 samples. Their frozen reference starts a fresh
  available-history epoch at each changed window. Three directly indexed list
  literals fail C++; three separately authored named-list versions execute and
  retain mismatches. No failed source or per-sample reference is replaced.
- Oscillator checks compare ideal cosine and the current/pre-increment phase
  over 512/1024-sample periods, both longer than the host block. Separate sources
  cover audio output, phase output, reset and phase-index mode. The second audio
  instance has a quarter-cycle offset. External tables and other interpolation
  modes remain outside the check.
- Noise checks emit finite/range flags for both streams and require variation
  in each 32-sample window. The seed program additionally checks equality of two
  streams seeded with 12345 at the same authored points. It does not compare an
  independently known RNG sequence or establish distribution/independence.
  The reset program checks healthy output after actual reset calls; it does not
  prove a particular entropy source or random-state transition.

Every executable source uses the unchanged strict Float32 arithmetic profile,
original buffer storage, zero automatic preparation blocks, four checked manual
warmups and sixteen timed callbacks. Means/cosines use the predeclared 2e-6
absolute limit; noise flags use zero. Each image has a 2 MiB **ceiling**, not a
claim that it consumes 2 MiB. Source/reference hashes, the full 22-source ledger
and all twenty continuous blocks are checked by the builder and collector.

## XIAO results — 6 November 2026

**Nineteen programs execute: sixteen pass and three retain output mismatches**,
with **194,560 output-word checks**. The mismatches are the three named-list
window-change scenarios. All nine fixed/reset/input-reset averaging programs,
four oscillator programs and three noise screens pass their declared limits.
All nineteen images finalise with no late/host allocation or free, and the
completion free internal/PSRAM totals are unchanged.

There are 20,270 outside-limit differences and 1,524 within-limit differences,
with no zero-sign-only differences. Native SDK preflight and XIAO share every
input/reference hash and their per-case aggregate difference counts/errors.
This is not a full target output capture or equality of random sequences.
The largest error in a passing program is 5.96e-8. The three RMS variants account
for 90 within-limit differences; oscillator cosine/phase-index scenarios account
for 1,306, and the mismatching RMS window program has another 128.

| Complete authored group | Scenarios | Median µs | Peak µs | Arena high-water |
| --- | ---: | ---: | ---: | ---: |
| Fixed/reset/input-reset arithmetic mean | 3 | 587–653 | 593–655 | 705,760 B |
| Fixed/reset/input-reset absolute mean | 3 | 621–683 | 624–687 | 705,760 B |
| Fixed/reset/input-reset RMS mean | 3 | 758.5–820 | 763–825 | 705,760 B |
| Named-list window-change scenarios, mismatching | 3 | 604.5–764 | 620–781 | 705,760 B |
| Cycle audio/reset/phase/phase-index | 4 | 433–550 | 444–552 | 65,648 B |
| Noise range/variation/reset/paired-seed screens | 3 | 155–287 | 160–291 | 0 B |

All twelve average scenarios trigger the median CPU rule (about 10.11–14.13%
of the audio period), bringing the review queue from 111 to **123 contexts**.
No peak-spike rule triggers. Each averaging pair retains two original Float64
buffers of 44,101 samples, despite its short logical windows. A later compact/
Float32 implementation needs its own limits and output proof; the existing
patcher optimisation does not transfer automatically to these member methods.
These are whole offline callback costs, not isolated opcode timings or gains.

## Window-selector scheduling diagnosis

The direct-list sources emit invalid C++ before `[`; they never execute.
The named-list sources compile, but the producer places the state-only `wl`
and `wr` selector expressions **before** its 256-sample loop, while incrementing
`ordinal` **inside** the loop. Therefore their windows change on callback
boundaries rather than the requested 73/91-sample boundaries.

The first mismatch is at sample ordinal 73, interleaved output word 146.
The original reference expects 0.875. Arithmetic/absolute means return 0.4375;
RMS returns approximately 0.5229. This is a source-scheduling scenario mismatch,
not an isolated failure of the averagers' fixed-window arithmetic.

A separate native direct-producer capture is compared with a **secondary**
callback-held-selector model. Arithmetic and absolute means match that model
exactly; RMS differs by at most 5.96e-8. Captures also reproduce the original
primary mismatch counts and errors. The original per-sample reference, limits
and all three target mismatches remain unchanged. The secondary model explains
observations; it does not become a passing hardware oracle. The helper and
capture/source hashes are retained in the native diagnostic record.

## Remaining scope and device restoration

Only 5,120 samples per program are checked: default 44,101-sample physical
buffer wrap is not reached. Arbitrary window sizes, interpolation/external
resources, nonfinite domains, one-frame host calls, host parameter events and
full RNG semantics remain unqualified. No DSP optimisation is claimed.

Evidence: [XIAO results](../../../../evidence/xiao-smoke-rnbo-codebox-analysis-members.json),
[native and scheduling diagnostics](../../../../evidence/rnbo-codebox-analysis-members-native.json),
and [normal-player restoration](../../../../evidence/xiao-analysis-members-player-restoration.json).
The smoke record describes its own completion checkpoint. The normal player is
subsequently restored with the same saved Main and live controls, healthy USB
replies, advancing audio frames and zero runtime fault counters.

```sh
python3 tests/fixtures/smoke/rnbo-codebox-analysis-members/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_analysis_members_reference.py
# With this exact batch prepared locally, a fresh secondary diagnostic:
python3 tests/fixtures/smoke/rnbo-codebox-analysis-members/window_diagnostic.py \
  --prepared-root build/research/codebox-analysis-members-v1/prepared \
  --out build/research/codebox-analysis-members-v1/diagnostic-new
```
