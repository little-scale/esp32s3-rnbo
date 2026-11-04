# RNBO codebox character constants

These 85 original programs exercise the remaining printable ASCII named values
from RNBO 1.4.4. They exclude `CHAR_0` through `CHAR_9`, which have separate
earlier evidence. Every exact name has its own patch and embedded/standalone
RNBO codebox source. Uppercase and lowercase names remain distinct, including
on filesystems that ignore filename case.

The installed `characterconstants.json` describes these as numeric ASCII values
and excludes them from patcher-object publication. Each program uses the bare
name on the left output, with the second input copied to the right output.
It does not test a quoted string, zero-argument call or GenExpr substitution.
Expected left values are independently defined by the corresponding character
and Python `ord()`: printable ASCII 32–126, excluding the ten digit values.
All are exactly representable in binary32. There is no DSP-output-derived model.

The right pilot varies across finite values in −4 to +4, including both zero
signs and minimum-subnormal, maximum-subnormal and minimum-normal boundaries.
Its expected words are copied unchanged. Zero numerical tolerance and a strict
right-channel zero-sign mask are declared before execution; a future hardware
record must enforce both before claiming a raw-word pilot pass. XAM exposes only
the referenced `in2` variable as a physical codebox inlet, at ordinal 0. The right
outer input connects there; the declared left input remains unused. Both outputs
flow through the codebox, giving the family's exact five-box, three-edge route.

`catalog.json` records all 85 scenarios. The two exact, disjoint device batches
are `catalog-part1.json` (43) and `catalog-part2.json` (42). Each uses zero
automatic prepare callbacks, four checked manual warm callbacks and sixteen
checked timed callbacks, all at 44100 Hz and 256 frames. This is not an arbitrary
one-sample host ABI, an alias inference or an optimisation comparison. Large
ASCII output values are functional numbers, not normalized audio amplitudes.

Run `generate.py --check` to compare the original fixtures with the pinned local
primary metadata. Portable tests are in
`tools/test_smoke_rnbo_character_constants_reference.py`. Frontend, preparation,
compilation, resources and device results are separate observations; failures
must remain attached to the exact source form rather than replaced silently.

The first four preflight attempts used an incorrect sparse-inlet wiring
assumption. They stopped at frontend port validation, before export. Their
original sources and logs remain private history; the correction changed only
the connections, with identical constant bodies, references and limits.
