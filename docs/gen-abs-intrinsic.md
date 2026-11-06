# Gen abs intrinsic

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The optional `--gen-abs-intrinsic` preparation flag replaces two Float32
absolute-value calls with explicit Float32 compiler builtins in the exact
original [abs GenExpr program](../tests/fixtures/gen/arithmetic/abs-call.genexpr).
Its matched XIAO test uses **36.19% less callback time**, with exact output bits
in all four device cases. The default remains `float32-strict` without this flag.

```sh
python3 host/compiler/prepare.py \
  --export build/hardware/gen-arithmetic-target-inputs-v1/raw/abs-call \
  --class-name rnbos3patch --role fx --gen-abs-intrinsic \
  --out build/prepared/gen-abs-intrinsic
```

This command requires the local licensed export. The flag admits only the
reviewed graph, generated source, description and complete runtime/input file
map, with the normal fixes and no other optional adapters. It retains the
`float32-strict` numerical profile and records a separate versioned adaptation
contract. An inverse check reconstructs the original source exactly. A generated
type include requires binary32 sample types, the reviewed ABI, binary64 clock
types and no fast math or excess evaluation precision.

## Measured XIAO result

The reference and candidate use the same compiler, strict `-O2` configuration,
SDK, libraries, allocation policy and original export. Four input families
exercise a signed grid, dense binary32 values, vector boundaries and exact
finite magnitude boundaries. The last includes both zero signs, the smallest
and largest subnormals, and the smallest normal values. Device inputs stay in
`[-1, 1]`; PCM gain is 0.5. Each case runs three times per profile, alternating
comparison order, with four zero warmup vectors and the first 32 of 64 rendered
vectors excluded from timing.

| Whole stereo callback, 256 frames | Reference | Intrinsic candidate |
| --- | ---: | ---: |
| Mean process time | 71.46 µs | 45.60 µs |
| Observed peak process time | 78 µs | 53 µs |
| Timed callbacks | 384 | 384 |
| ELF `.text` bytes | 26,667 | 26,495 |
| Complete ELF bytes | 32,980 | 32,796 |
| Opaque context bytes | 12,720 | 12,720 |

The observed ratio is about 1.57× for the complete authored callback. Input
generation, oracle construction, cache copying, analysis, preparation, I²S,
display and networking are outside the process timer. This measures neither
an isolated instruction nor the live drone's utilisation or worst-case deadline.

All 393,216 paired output-word comparisons have zero numerical, PCM and raw-bit
differences. Both profiles also pass 786,432 independent numerical checks and
786,432 raw magnitude-bit checks, including the required positive-zero result.
Counts include repeated executions. All four loaded images are finalised,
internal RAM and PSRAM recover exactly, and callback heap and late-allocation
counters remain zero. Both contexts use zero arena bytes within a 4 KiB capacity.
The test restores the drone unpaused at 50% with its compiled parameter defaults.
See [the saved observations and proof identities](../evidence/gen-abs-intrinsic.json).

## Precision and scope

This removes Float32 library calls; the original abs loop already uses Float32.
The machine-code audit checks the named processing function, live module
callback and preparation warmup. Each original loop makes two `fabsf` calls per
frame; each candidate loop has two `abs.s` instructions and no calls. Scheduler
binary64 arithmetic remains outside those loops and is unchanged.

The actual public-preparation native replay covers five input programs across
O3 and UBSan reference/candidate builds and two lifecycles: 40 healthy contexts,
1,048,576 exact paired output words and PCM comparisons, and 2,097,152 independent
raw magnitude checks with zero errors. The wider finite input includes both
signs, all finite exponent fields, subnormals and selected mantissa boundaries;
it is a sampled corpus rather than enumeration of every binary32 word. Expected
PCM saturation for large finite native inputs is checked separately. The public
target ELFs also match the independently reviewed prototype ELFs byte for byte.

For a finite binary32 input, absolute magnitude is exactly its input word with
the sign bit cleared. This preserves subnormal magnitude and maps negative zero
to positive zero without a rounding step. The option's finite-bit contract is
separate from nonfinite values, NaN payloads, floating exceptions, traps and
`errno`, which are not qualified. It does not qualify other abs overloads,
arities, visual Gen boxes, arbitrary graphs or the remaining Gen inventory.
The [full Gen and single-sample requirements](qualification-scope.md) remain active.

The final local checks pass 454 compiler tests (including 140 collector tests)
and 135 tool tests. Generated licensed DSP and private device/recovery identifiers remain
outside the public repository.
