# Finite Float32 `wrap~` correction on the S3

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

**Status: Partial, with a qualified finite-input correction.**
`--correct-finite-wrap` is optional and off by default. It accepts only two
pinned RNBO 1.4.4 strict FX contexts: the authored `nonlinear-domains` chain
and a direct stereo `wrap-finite-stereo` fixture. Unknown source, runtime,
type or option combinations reject. The numerical profile stays
`float32-strict`.

The correction covers finite Float32 samples and the fixed interval `[-1,1)`,
at 44,100 Hz in 256-frame blocks. At magnitude `2^24` and above, every finite
Float32 value is an even integer, so its exact modulo-two result is positive
zero. Below that threshold, the original method stays unchanged, including
input negative zero. The [original proof](wrap-finite.md) explains the
target-width undefined conversions and the separate defined wrong-range
results this repairs.

## Measured target results

Both isolated tests ran on the Waveshare ESP32-S3 AMOLED 1.8 V2. Each case
started from a fresh context, used four zero-input warmup blocks, seed
`0x12345678`, 512 rendered blocks and three rounds.

| Test | Result | Interpretation |
|---|---|---|
| Original versus corrected bounded `tanh`/wrap/clip/power chain | 2,359,296 float words and PCM matched exactly; 4,718,592 independent model checks passed the unchanged `2e-6` limit | Preserves the three authored bounded cases |
| Two copies of the corrected direct stereo wrap module | 3,145,728 pairwise float words and PCM matched; 6,291,456 raw-bit oracle checks had zero differences | Direct wrap correctness, including signed zero; identical artifact control |

The direct test covers **4,080 distinct finite values**, repeated across
channels, module copies and rounds. It includes both signs, all 255 finite
exponent fields, eight mantissa strata, signed zero, values near `±1`, `±2^24`
and `±2^32`, and signed `FLT_MAX`. Independent channel offsets catch channel
mixing. Input and integer modulo-two oracle cache hashes are independently
recomputed on the host and checked around every target pass. The unsafe
original direct module is never executed on this grid.

On the bounded graph, total processing time was 2,717,251 µs originally and
2,724,754 µs with the correction over 4,320 timed vectors per profile:
**0.276% observed extra CPU**. These are whole-chain callback measurements.
The direct same-artifact run establishes no CPU saving. Linked `.text` grows
by 120 bytes for the chain and 300 bytes for direct stereo; the compared data
sections are unchanged.

Both runs reported zero observed late/module-local or benchmark-owner heap
operations, recovered internal RAM and PSRAM exactly after unload, and
finalized all four loaded images. Each image reserved a 4,096-byte arena and
used none of it. The working instrument was restored after each run.
The measured chain context is 14,800 bytes, with aligned mapped code growing
from 33,540 to 33,660 bytes. Each direct image reports a 12,736-byte context
and 26,692 bytes of aligned code. Context, arena reservation and code are
separate costs; arena high-water is not a whole-board memory peak.

## Proof and remaining scope

The [new evidence seal](../evidence/wrap-finite-target.json) binds the optional
compiler admission, prepared sources, module and firmware identities, native
proofs, complete collected target records, independent cache review and test
logs: 221 compiler tests and 80 tool tests passed. It retains all 96 artifacts
from the original exhaustive proof. Release and sanitizer builds each checked
all **4,278,190,080 finite encodings**, including preservation of
**2,533,359,616** safe original encodings. That exhaustive coverage is native;
the S3 coverage is the representative grid above.

NaN and infinity still take the unchanged upstream route and remain
unqualified. Arbitrary wrap ranges, Float64 input, floating exception flags
and other rounding modes are outside this admission. The target harness has
no I2S, UI or network workload and establishes no full-application deadline
bound. The earlier private-stage document remains an immutable historical
record; this page records the later compiler and target qualification.
