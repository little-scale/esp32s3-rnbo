# Float32 corner-domain observations on ESP32-S3

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

Two standalone board diagnostics compared Float32 add/subtract/multiply/divide
with separate Double-intermediate paths rounded back to Float32. Each used the
same 3,036 explicit, exponent-stratified and fixed-seed finite operand pairs,
including signed zeros, subnormal and minimum-normal neighbors, and extremes.
The Core1 task's rounding control stayed at its default nearest/even setting.

One diagnostic used ESP-IDF ROM arithmetic helpers. The other privately linked
the exact GCC archive used by the RNBO dynamic modules. Its copied archive had
prefixed symbols and relocations, and the instruction audit confirmed private
helper calls rather than ROM fallback. Hardware Float32 add/subtract/multiply
instructions remained present in both builds.

All tested add, subtract and multiply output words matched in both variants.
Division had no finite-result differences. Two signed-zero invalid divisions
produced NaNs with different sign bits. No tested subnormal input/result mismatch
or rounding-mode change was observed. Floating exception status words differed,
so this does not establish equivalent floating-environment side effects.

Each capture contains all 12,144 ordered result records. The analyzer validates
input words, operation/index coverage, result classes, summary counters,
checksums, firmware identity and rounding controls. The runner's completion
token means the diagnostic finished; it does not mean every output was identical.
The drone and its live controls were restored after both runs.

The [sealed evidence](../evidence/float32-corners.json) retains the two NaN
representation differences and exception-status observations. These bounded
tests support the existing Float32 investigation; they do not prove all operand
pairs, other rounding modes, every RNBO caller or whole-program equivalence.
