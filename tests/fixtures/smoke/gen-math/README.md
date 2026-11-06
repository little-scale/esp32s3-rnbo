# Original GenExpr mathematical smoke fixtures

> **Recorded development material.** The supported intake is now [Max Minimal C++ Export](../../../../docs/native-export.md). Any importer commands or qualification results below are historical, not native-export qualification.

This batch contains 34 MIT-authored GenExpr programs and self-contained RNBO wrapper patches. Each patch is fixed at 44.1 kHz/256 frames, FX with two inputs and outputs, and has no parameters or events. Unary functions process the two planes independently. Binary functions and operators use reversed operands on the right output.

| Models | Authored forms |
| --- | --- |
| 76–80 | `div(a,b)`, `a / b`, `rdiv(a,b)`, `a !/ b`, `mod(a,b)`, `a % b`, `rmod(a,b)`, `a !% b`, `rsub(a,b)`, `a !- b` |
| 81–87 | `sqrt`, `exp`, `exp2`, `log`, `ln`, `log2`, `log10`, `pow` calls |
| 88–95 | `sin`, `cos`, `tan`, `tanh`, `asin`, `acos`, `atan`, `atan2` calls |
| 96–103 | `sinh`, `cosh`, `asinh`, `acosh`, `atanh`, `hypot`, `degrees`, `radians` calls |

Every spelling and syntax has its own source and outcome. Registry membership does not establish parser acceptance, C++ compilation or execution. RNBO signal-object results do not transfer to GenExpr.

`reference.py` independently defines per-case 256-frame finite input vectors and mathematical expectations. Divisors are nonzero in both operand orders; logarithms, roots, powers and inverse functions stay in valid bounded domains. Degree/radian conversion has dedicated vectors. Approximate outputs stay within magnitude 8 and use a fixed absolute tolerance of `2e-6`, chosen before hardware execution. Models 76–80 use exact numerical comparison. Signed-zero differences remain visible as diagnostics.

The initial unmodified RNBO 1.4.4 pipeline exported/prepared 31 programs. The three attempted reverse infix forms (`!/`, `!%`, `!-`) failed GenExpr parsing. Four further forms failed target C++ compilation: `mod` and `rmod` emitted an undeclared `safemod`; `rdiv` emitted an ambiguous `div`; `rsub` emitted an undeclared `sub`. All sources and failure logs are retained. The remaining 27 modules compiled with zero imports. These statements describe frontend and compiler outcomes; hardware execution is recorded separately.

The hardware smoke plan uses zero automatic zero-input preparation blocks,
four checked warmups with each valid-domain vector, and sixteen timed calls.
This avoids invalid zero-input pre-roll for `acosh`. It does not qualify the
runtime's default zero-preroll behaviour.

No fallback expressions, DSP fixes or optimisation adapters replace failed forms. These short checks do not establish arbitrary input domains, nonfinite handling, all overloads, aliases, stateful structures or real-time headroom. Callback timing belongs to the whole fixture and wrapper.

Example preparation with an authorized RNBO 1.4.4 installation:

```sh
node host/export/export.mjs tests/fixtures/smoke/gen-math/div-call.rnbopat --out build/smoke-genmath/raw/div-call
python3 host/compiler/prepare.py --export build/smoke-genmath/raw/div-call --out build/smoke-genmath/prepared/div-call --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke-genmath/prepared --base-build PATH_TO_REVIEWED_MODULE_CACHE --out build/smoke-genmath/modules
```

Generated RNBO C++ and runtime headers remain in ignored build directories with their upstream notices. `catalog.json`, `.genexpr` and `.rnbopat` files contain only original fixture source and compact metadata.
