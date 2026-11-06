# Original RNBO numeric signal smoke fixtures

> **Recorded development material.** The supported intake is now [Max Minimal C++ Export](../../../../docs/native-export.md). Any importer commands or qualification results below are historical, not native-export qualification.

These 33 MIT-authored flat RNBO 1.4.4 patches provide short XIAO-oriented functional checks. Each is an FX with two signal inputs, two outputs and no parameters or events. Unary operators process each plane independently. Binary operators receive `(left, right)` and reversed operands in separate instances.

| Models | Authored spellings |
| --- | --- |
| 51–54 | `div~`, `/~`, `rdiv~`, `!/~`, `mod~`, `%~`, `rmod~`, `!%~` |
| 55–60 | `floor~`, `ceil~`, `trunc~`, `round~`, `fract~`, `sign~` |
| 61–64 | `isnan~`, `fixnan~`, `isdenorm~`, `fixdenorm~` |
| 65 | `intnum~`, `int~`, `i~` |
| 66–70 | `sqrt~`, `cbrt~`, `exp~`, `exp2~`, `expm1~` |
| 71–74 | `log~`, `ln~`, `log2~`, `log2f~`, `log10~`, `log1p~` |
| 75 | `pow~` |

`round~` keeps its unconnected second inlet at the first-party default of 1. Other binary operators connect both signal inlets. Every exact spelling has its own graph and result; alias metadata does not transfer qualification. Earlier generic board evidence for `/~` or `pow~` does not establish this XIAO signal-input mode.

`reference.py` independently supplies each 256-frame input vector and mathematical expectation. Division and remainder use nonzero operands in both lanes. Roots, logarithms and powers use bounded valid domains; exponentials use inputs from −2 to 2. Approximate functions have a fixed absolute tolerance of `2e-6`, chosen before execution. Basic operations use exact numerical comparison with separate signed-zero diagnostics. Fraction uses an explicit signed-fraction convention. The finite-only `isnan~` and `fixnan~` checks do not establish handling of NaN or infinity.

The default runtime and emitted DSP are preserved. Any disabled denormal behavior, numerical discrepancy or compile failure remains an observation. These short checks do not establish all domains, scalar/event modes, resets or real-time headroom. Callback timing covers the whole two-instance fixture and wrapper. Compilation alone does not establish execution; hardware records are separate.

For an authorized local installation, export and prepare the original patches into ignored build directories, then use the fast builder with a matching reviewed 4096-byte module cache:

```sh
node host/export/export.mjs tests/fixtures/smoke/rnbo-numeric/divide-signal.rnbopat --out build/smoke-numeric/raw/divide-signal
python3 host/compiler/prepare.py --export build/smoke-numeric/raw/divide-signal --out build/smoke-numeric/prepared/divide-signal --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke-numeric/prepared --base-build PATH_TO_REVIEWED_MODULE_CACHE --out build/smoke-numeric/modules
```

Generated RNBO C++ and runtime headers stay under ignored build directories with their upstream notices. This fixture batch contains no DSP fixes or optimisation adapters.
