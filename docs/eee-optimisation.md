# EEE: fixed-resonance `lores~` Float32 review

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The supplied `eee.rnbopat` now runs on the connected XIAO using the existing
player. The previous Auto package was rejected by the detached startup screen
at **5,993 µs**. The candidate passed admission and its live render observations
are recorded in [the evidence manifest](../evidence/eee-lores-float32.json).
The audio block period is **5,804.99 µs**; the player deliberately reserves sink
time and admits startup callbacks only up to **5,224 µs**. Merely reaching 5.8 ms
would therefore leave insufficient admission headroom.

## What consumed the time

Auto recognized 13 of the patch's 16 candidate methods, including both signal
`mtof~` exponential methods. It left the `lores~` method unchanged because its
fixed **0.9 resonance** generated a different whole-method fingerprint from the
previously reviewed zero-resonance form. That retained a software double cosine,
double coefficient expressions and conversions inside the audio loop.

The target disassembly audit attributes **19 double-related call sites** to that
method before the change, and **zero** after. The candidate uses `expf` and
`cosf`. Call-site counts describe compiled code, not runtime invocation counts
or a per-object percentage benchmark.

The specific scalar `saw~` and linear `scale~` forms in EEE remain unreviewed and
unchanged by Auto. Their presence does not prevent this independently reviewed
filter method from being optimized. The two `mtof~` methods already use the
reviewed Float32 path and were not changed in this experiment.

## Exact change and limits

The compiler now admits one additional full-method fingerprint in the Auto/v3
catalog. Eight decimal literals acquire `f` suffixes inside `lores_01_perform`.
All generated DSP bytes **outside that method are identical** to the previous
Auto build. The resonance comparison also becomes Float32, matching its stored
state instead of comparing a double 0.9 to the rounded float representation.

The supplied patch file is untouched. Wiring, its authored 10,000-sample delay,
delay storage precision, filter state layout, phase algorithms and scheduler
precision stay as authored. This is an arithmetic-rounding change, not a
bit-identity claim. Other coefficients, resonances and edited methods do not
match the fingerprint and remain unchanged in Auto; the earlier explicit v1/v2
profiles do not inherit this method.

## Native numerical comparison

The previous Auto renderer and candidate rendered the same six note settings:
**0, 12, 24, 39, 48, 60**, each for **4,096 × 256 stereo frames**, about 23.8 s.
Both used the same seed, four warmup blocks and identical controls. This checks
**12,582,912 individual Float32 samples** across the six comparisons.

- Maximum absolute sample difference: **3.829598426818848e-6**.
- Highest error RMS across cases: **3.465616822989369e-7**.
- Maximum converted PCM difference: **1 int16 LSB**, with 100% conversion volume
  and fixed 0.5 headroom.
- Both variants remained finite, with zero render errors and zero late platform
  allocations. Native arena usage remained **458,992 bytes**.

The existing strict diagnostic **2e-6 sample-error gate failed in all six cases**;
the **1 PCM LSB gate passed in all six**. These results are retained separately
from speed and do not establish bit identity, universal accuracy, inaudibility
or target/host floating-point identity. Native wall-clock time is not used as
an ESP32 speed measurement.

## Hardware observation

The candidate was loaded as an ordinary package into the existing XIAO player;
the physical-input firmware was **not flashed**. USB control and saved Wi-Fi
remained available. The user's existing **17% volume** was retained.

The on-device sweep visited notes **0, 12, 24, 39, 48, 60, then 39**, taking 16
live status observations per setting. It checked stable generation/package
identity, advancing frames, playing state and fault counters. Note 39 was restored
at the end. The package remains active for listening.

Across **112 observations**, the overall median is **2,246.5 µs (38.70% audio
CPU)** and observed peak is **2,585 µs (44.53%)**. All checked deadline, nonfinite,
clipping, I/O, module, queue and audio-allocation counters remain **zero**. Saved
Wi-Fi reports connected during this USB-controlled check. Full per-setting
timings and all fault counters are in the evidence manifest. Render time includes the callback and PCM sink
work before the I²S wait; its percentage is of one audio block's time budget,
not total usage of both CPU cores. No actual-audio capture or listening verdict
is claimed by these checks.

The baseline number is a rejected **startup** observation; the candidate numbers
are **running** observations. They demonstrate successful admission and useful
headroom but are not a matched before/after throughput benchmark. No exact
speedup percentage or universal worst-case timing guarantee is assigned.

## Using the change

Recompile the original EEE file in Studio with **Automatic Float32 audio
(reviewed kernels)**, the default. No patch edits or extra settings are needed.
Standard arithmetic remains available. A new compilation is required: an old
saved `.rnbopkg` keeps its already compiled arithmetic.

An original minimal RNBO fixture and three regression tests verify the new form,
preservation outside the method and rejection of changed coefficients/recurrences.
The full compiler suite passes **517 tests**, including the earlier Auto and DDD
profile checks; DDD's reviewed output is unchanged.
