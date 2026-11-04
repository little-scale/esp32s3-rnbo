# Original RNBO numeric event smoke fixtures

These 35 MIT-authored patches test exact non-tilde RNBO spellings at numeric event rate. They are separate from signal-rate, GenExpr and earlier board results.

Every patch has one numeric parameter, `drive`, default 0, range −8 to 8, exponent 1 and steps 0. It feeds the operator's hot inlet 0. Operator outlet 0 feeds `sig~` and audio output 1. Binary operators have a fixed cold operand of 2, except `or 0`, which allows the hot input to exercise both boolean results. `round 2` tests rounding to a multiple of 2.

Audio input 2 passes directly to output 2 as a raw Float32 observer, including signed zero and subnormals. Audio input 1 is declared and unused. The patches remain FX with two inputs and outputs and use a 4096-byte structural arena ceiling.

| Models | Exact authored spellings |
| --- | --- |
| 148–155 | `abs`, `neg`, `floor`, `ceil`, `trunc`, `round`, `fract`, `sign` |
| 156–157 | `boolnum`, `not`, `!` |
| 158–162 | `add`, `+`, `sub`, `-`, `mul`, `*`, `div`, `/`, `mod`, `%` |
| 163–164 | `minimum`, `min`, `maximum`, `max` |
| 165–167 | `eq`, `==`, `gt`, `>`, `lt`, `<` |
| 168–170 | `and`, `&&`, `or`, `xor` |

Minimum and maximum have two event outlets; only outlet 0's numeric value is observed. Their index outlet is outside the tested scope. Each alias has its own source and outcome, with no inherited qualification.

`reference.py` independently defines ordered actual-value parameter events before each of 20 callbacks: four manual warm calls and sixteen timed calls, with zero automatic SDK warm-up. It includes negative, zero and fractional values, unchanged resends, calls with no new event, and several events in one call. The final ordered event determines the held left output. Fraction and modulo have dedicated ordering witnesses; equal comparison has a separate last-event witness.

Left numeric outputs use exact numerical comparison and separate signed-zero diagnostics. The right observer requires raw-word equality. Fraction uses an explicit signed-fraction convention; nearest-multiple rounding uses declared halfway-away-from-zero behavior. Divisor 2 is always nonzero. These checks do not establish arbitrary cold inputs, normalized events, mid-block scheduling, bang/list modes or every repeated-value notification behavior.

All 35 original patches exported, prepared and compiled with zero imports. Compilation is separate from event execution and callback timing. The hardware harness reports event API timing separately from audio callback timing; neither implies an optimisation gain. No DSP or SDK change is applied.

Example preparation with an authorized RNBO 1.4.4 installation:

```sh
node host/export/export.mjs tests/fixtures/smoke/rnbo-events/absolute-event.rnbopat --out build/smoke-events/raw/absolute-event
python3 host/compiler/prepare.py --export build/smoke-events/raw/absolute-event --out build/smoke-events/prepared/absolute-event --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke-events/prepared --base-build PATH_TO_REVIEWED_MODULE_CACHE --max-arena-bytes 4096 --out build/smoke-events/modules
```

Only original patches and compact metadata are public. Generated RNBO C++ and runtime headers remain under ignored build directories with their upstream notices. Hardware evidence is stored separately.
