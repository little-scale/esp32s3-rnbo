# `wrap~`: bounded coverage and private finite-input repair

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

**Status: Partial.** The original bounded nonlinear graph passed on the S3.
A separate correction for large finite Float32 inputs has exhaustive native
proof and static Xtensa instruction checks. That correction remains private;
it has no production admission or S3 execution/timing qualification.

The [sealed evidence](../evidence/wrap-finite.json) preserves the original
research report and its 96 artifact records. It contains metadata and hashes;
generated RNBO bodies remain in the local ignored build tree.

## What the original target test establishes

The existing [nonlinear oracle control](object-oracles.md) checks the authored
`tanh`/wrap-to-`[-1,1)`/clip-to-`[0,1]`/positive-power chain, with right input
grid `[-3,3]` and exponents 2, 0.25 and 4. On the S3, two copies of the same
original module matched over 2,359,296 float words and exact PCM, while
4,718,592 scalar model checks stayed within the unchanged `2e-6` limit.

That module contains neither private guard. Its bounded result remains valid
and provides no target test of the correction or of large-input behavior.

## The newly demonstrated gaps

The original fixed-range method uses an integer conversion and a negative
correction. `Int` is `intptr_t`: 32 bits on the S3 and 64 bits on the native
host. Explicit target-width sanitizer tests reproduce:

| Input | Original behavior |
|---|---|
| `+2^32` | Float32-to-Int32 conversion is out of range |
| `-2^32` | Valid conversion to `INT32_MIN`, followed by signed overflow when subtracting one |
| `16,777,218` | Defined arithmetic returns `-2`, outside `[-1,1)` |
| `-33,554,436` | Defined arithmetic returns `+2`, outside `[-1,1)` |

The two `2^32` native `intptr_t64` control runs remain defined and return zero.
Host-width tests therefore do not reproduce those target-width failures on
their own. The two wrong-range results are separate from undefined behavior.

## Private correction and proof

Every finite Float32 number with magnitude at least `2^24` (16,777,216) is an
even integer. Its exact wrap modulo two into `[-1,1)` is zero. The preferred
private candidate returns positive zero for that finite domain, after the
original in-range fast branch. The complete remaining method and runtime stay
unchanged, verified by full source pins and an exact byte inverse.

Release and UBSan/float-cast-overflow builds each compare **all 4,278,190,080
finite Float32 encodings** with an independent raw-bit integer modulo oracle:
zero differences. All **2,533,359,616 safe encodings** below the threshold also
retain the original target-width and host-width outputs bit-for-bit, including
input negative zero. Nonzero even integers produce canonical positive zero.

A Float32 remainder alternative at the same threshold passes 153,083,904
stratified comparisons. Moving its threshold to `2^31` misses the earlier
defined range failures and produces 8,392,704 mismatches on those strata; that
later threshold is rejected.

Both private variants preserve the three original native graph cases exactly
in float and PCM. A separate large-finite grid through signed `FLT_MAX` also
produces the mathematically expected wrap/clip/power result. Across both
variants, bounded comparisons cover 1,572,864 float words and corresponding
PCM; the large-grid campaign checks another 1,572,864 scalar outputs. The native
graph uses the host integer width; the exhaustive target-width source model is
recorded separately.

Standalone Xtensa GCC O2/O3 lowering emits no helper calls or Float64/Int64
helpers for the preferred scalar candidate. Its function is 178 bytes versus
117 bytes for the original. This describes instructions and code size; CPU
benefit remains unmeasured.

The finite guards reject NaN and infinity without writing an output; the
original nonfinite path remains unchanged and unqualified. No new nonfinite
policy, floating-exception behavior, non-default rounding-mode behavior,
arbitrary wrap range or Float64-input admission follows from this proof. Target
execution and timing are required before the correction can advance beyond
its private native/static stage.
