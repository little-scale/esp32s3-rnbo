# Finite RNBO codebox numeric constants

These 40 original fixtures use **RNBO `codebox~`**, not GenExpr. Each exact
spelling is authored as a bare named value in both outputs. The two declared
FX inputs vary but remain unused. Aliases have separate fixtures.

Thirty mathematical spellings compare with independently computed values,
rounded once to binary32. `CHAR_0` through `CHAR_9` are numeric ASCII character
codes 48 through 57, not numeric digits 0 through 9 or string-valued globals.
Zero absolute error is declared before execution.

Dynamic clock/channel queries, nonfinite constants, other syntax forms and
complete mode coverage are separate. This catalog alone claims no device
execution or optimisation gain.

The [XIAO hardware run](../../../../evidence/xiao-smoke-rnbo-codebox-constants.json) passes all 40 named-value programs with zero bit differences across 409,600 output values. No CPU-review flags or memory/allocation failures occur. These results apply to the authored bare-value syntax.
