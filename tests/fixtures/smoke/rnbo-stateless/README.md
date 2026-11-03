# Original RNBO signal smoke fixtures

These 36 MIT-authored flat patches exercise exact RNBO 1.4.4 signal-object spellings. Each is an FX with two inputs, two outputs and no parameters. Unary operations process each plane independently; binary operations use `(left, right)` for the left output and reversed operands for the right output.

| Model | Operation | Authored spellings |
| --- | --- | --- |
| 35 | Addition | `add~`, `+~` |
| 36 | Multiplication | `mul~`, `*~`, `times~` |
| 37 | Right minus left | `rsub~`, `!-~`, `rminus~` |
| 38 | Absolute difference | `absdiff~` |
| 39 | Opposite sign | `neg~` |
| 40 | Absolute value | `fabs~` |
| 41 | Pass unchanged | `pass~` |
| 42 | Not equal | `neq~`, `!=~`, `notequals~` |
| 43 | Greater than | `gt~`, `>~`, `greaterthan~` |
| 44 | Greater than or equal | `gte~`, `>=~`, `greaterthaneq~` |
| 45 | Less than or equal | `lte~`, `<=~`, `lessthaneq~` |
| 46 | Logical AND | `and~`, `&&~`, `logand~` |
| 47 | Logical OR | `or~`, `\|\|~` |
| 48 | Logical XOR | `xor~`, `^^~` |
| 49 | Logical NOT | `not~`, `!~` |
| 50 | Nonzero to boolean | `boolnum~`, `bool~`, `b~` |

`reference.py` supplies an independent 256-frame Cartesian grid of 16 dyadic values from −4 to 4, including both zero signs. It computes expected results from basic mathematics and nonzero logical truth. The catalog pins primary reference metadata and preserves each exact spelling; results never transfer automatically between aliases or between RNBO and GenExpr.

These are short functional checks with callback timing. They do not establish all inlet modes, resets, event handling, arbitrary inputs or real-time headroom. Compilation alone does not establish execution. Existing composed observations of `+~` and `*~` remain separate from these direct-input tests. Hardware reports are stored separately.

With an authorized local RNBO 1.4.4 installation, export and prepare each patch into ignored build directories. For example:

```sh
node host/export/export.mjs tests/fixtures/smoke/rnbo-stateless/add-signal.rnbopat --out build/smoke/raw/add-signal
python3 host/compiler/prepare.py --export build/smoke/raw/add-signal --out build/smoke/prepared/add-signal --class-name rnbos3patch --role fx
python3 tools/build_smoke_modules.py --prepared-root build/smoke/prepared --base-build PATH_TO_REVIEWED_4096_BYTE_MODULE_CACHE --out build/smoke/modules
```

The fast builder rechecks its cache and records compile failures while continuing the batch. Generated RNBO C++ and runtime files remain under ignored build directories and retain their upstream notices.
