# Original RNBO function and conversion smoke fixtures

> **Recorded development material.** The supported intake is now [Max Minimal C++ Export](../../../../docs/native-export.md). Any importer commands or qualification results below are historical, not native-export qualification.

These 35 MIT-authored patches provide direct XIAO-oriented checks of exact RNBO 1.4.4 spellings. Each declares two inputs and two outputs, with no parameters or events. Unary functions process each input plane independently; `atan2~` and `hypot~` reverse operands on the right output.

| Models | Authored spellings |
| --- | --- |
| 115–128 | `sin~`, `cos~`, `tan~`, `tanh~`, `asin~`, `acos~`, `atan~`, `atan2~`, `sinh~`, `cosh~`, `asinh~`, `acosh~`, `atanh~`, `hypot~` |
| 129–130 | `degrees~`, `radians~` |
| 131–132 | `radtodeg~`, `RADTODEG~`, `degtorad~`, `DEGTORAD~` |
| 133–136 | `mtof~`, `ftom~`, `atodb~`, `dbtoa~` |
| 137–142 | `mstosamps~`, `sampstoms~`, `hztoms~`, `mstohz~`, `hztosamps~`, `sampstohz~` |
| 143–147 | `fastsin~`, `fastcos~`, `fasttan~`, `cosT8~`, `cosT8safe~` |

The four spellings in models 131–132 are **zero-input constants**, not converters. Their declared FX inputs are unused. Their outputs are 180/π or π/180. `mtof~` and `ftom~` connect only their signal-data input and retain default tuning, A4 = 440 Hz; `ftom~` retains its documented default integer rounding.

`reference.py` independently defines per-case finite input vectors. Musical conversion includes practical notes such as MIDI 69 and frequency 440 Hz. Amplitude decibels use unity as 0 dB. Time conversions use 44.1 kHz and practical samples, milliseconds and frequencies. Inverse and logarithmic functions stay within valid domains. Previous AMOLED or GenExpr results do not establish these XIAO forms, and aliases keep separate outcomes.

Limits are fixed before execution: constants and rounded MIDI outputs use exact numerical comparison; MIDI-to-frequency uses `5e-4` Hz; time/frequency conversions use `5e-4` in their output units. Fast sine/cosine/tangent use `1e-3` as a declared smoke threshold, not a library accuracy guarantee. Other functions use `2e-6`. Taylor cosine checks use small angles or small angles after wrapping. Signed-zero diagnostics remain visible; nonfinite and full-domain behavior are outside this batch.

The modules use an explicit **1 MiB arena ceiling**, preserving the original musical-conversion resources. The two `mtof~` instances share one 65,536-sample Float32 lookup allocation: 262,144 bytes of payload plus object/list/arena overhead. Source inspection places this allocation in initialization during preparation, before optional audio warm-up. `ftom~` has no lookup DataRef but performs scale-list initialization. These are source facts; actual arena high-water and health come from execution. The ceiling does not mean every case consumes 1 MiB.

All 35 original patches exported, prepared and compiled with zero imports. Compilation is separate from functional execution and callback timing. No numerical profile, table omission or other DSP optimisation is applied. The harness should use valid per-case manual warm-up vectors rather than zero audio outside an inverse function's domain; resource initialization does not require zero-input audio warm-up.

Example module preparation with an authorized RNBO 1.4.4 installation:

```sh
node host/export/export.mjs tests/fixtures/smoke/rnbo-functions/sin-signal.rnbopat --out build/smoke-functions/raw/sin-signal
python3 host/compiler/prepare.py --export build/smoke-functions/raw/sin-signal --out build/smoke-functions/prepared/sin-signal --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke-functions/prepared --base-build PATH_TO_REVIEWED_4096_BYTE_MODULE_CACHE --max-arena-bytes 1048576 --out build/smoke-functions/modules
```

Only original patches and compact metadata are public. Generated RNBO C++ and runtime headers remain in ignored build directories with their upstream notices. Hardware records and any unexpected CPU costs are recorded separately.
