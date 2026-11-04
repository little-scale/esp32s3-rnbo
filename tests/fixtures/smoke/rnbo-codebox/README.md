# RNBO codebox arithmetic, comparison and logic smoke fixtures

These 45 original MIT-authored programs test individually inventoried **RNBO `codebox~`** spellings. They are not GenExpr programs. Each authored `.rnbo` body exactly matches its patch's `rnbo_extra_attributes.code`; generated RNBO C++ remains in ignored build directories.

Each flat patch has two audio inputs, one codebox and two outputs. Unary operations act independently on each lane. Binary left output uses `(in1,in2)` and right output uses reversed arguments `(in2,in1)`. Named aliases use function calls; symbolic spellings use actual infix or prefix syntax. A registered alias is not presumed to parse or execute because another spelling works. Prior `+`, `-` and stateful codebox results are not inherited.

`reference.py` defines independent arithmetic and boolean expectations. Inputs are a 16×16 finite dyadic Cartesian grid, including both zero signs, signed fractions and integers. Division/modulo instead use nonzero signed powers of two on both lanes. Signed remainder uses a quotient truncated toward zero. Each mathematical result is rounded once to binary32; the predeclared numerical tolerance is zero. Operation-output signed-zero differences are diagnostic. These are stateless programs: the same 512-word expectation applies to each of twenty callbacks, with the harness's ordinary preparation warmup. No state, parameter, resource, NaN or infinity mode is claimed.

`catalog.json` records exact spellings, syntax, arity, independent model IDs 220–240 and local first-party registry fingerprints. The portable tests are in `tools/test_smoke_rnbo_codebox_reference.py`.

Export, preparation and module compilation are separate stages. Their results are retained under ignored `build/research/rnbo-codebox-smoke-v1` and `build/hardware/rnbo-codebox-smoke-modules-v1`; the merged ledger retains frontend failures without fallback source. Build success alone does not establish hardware compatibility or DSP performance. Hardware runs and publication are separate steps; the 4 KiB module arena is a structural ceiling, not measured use.

The [XIAO hardware run](../../../../evidence/xiao-smoke-rnbo-codebox.json) passes all 43 admitted programs across 440,320 output values. The 2,880 raw-word differences are signed-zero diagnostics; numeric mismatches and CPU-review flags are zero. Named `mod()` fails C++ compilation and the `^^` infix form fails export; neither is executed or replaced by an alias. These are failures of the listed forms, without a claim that every form of either object is unsupported.
