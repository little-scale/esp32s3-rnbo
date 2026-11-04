# Float32 dbtoa experiment

`float32-dbtoa-v1` is an explicit, changed-rounding experiment for the exact
original stereo [`dbtoa~` signal fixture](../tests/fixtures/smoke/dbtoa-f32-comparison/dbtoa-signal.rnbopat).
It changes the local power base from integer `10` to `10.0f` and the exponent
coefficient from `0.05` to `0.05f`. Both changes are needed: the integer base
otherwise keeps the generic double-precision power overload. Shared math,
scheduler time, state, callers and buffer storage are unchanged.

The profile admits a pinned source/runtime/configuration map and exact complete
audio-method fingerprints. Four literal replacements in the stereo fixture
have a checked inverse that reconstructs every original source byte. A prepared
wrapper checks binary32 audio, binary64 scheduler time, standard math and the
reviewed ABI. The build retains disabled fast math and contraction.

The normal CLI default remains `float32-strict`, and Studio's automatic profile
is unchanged. Other graphs, codebox/Gen forms, optional adapter combinations,
nonfinite inputs and values outside the tested range remain unqualified.

```sh
node host/export/export.mjs \
  tests/fixtures/smoke/dbtoa-f32-comparison/dbtoa-signal.rnbopat \
  --out build/dbtoa-example/raw
python3 host/compiler/prepare.py --export build/dbtoa-example/raw \
  --class-name rnbos3patch --role fx \
  --numerical-profile float32-dbtoa-v1 --out build/dbtoa-example/prepared
```

An authorised local RNBO 1.4.4 installation is required; generated code stays
in ignored local build directories.

## Numerical observations

Four frozen vectors contain 2,048 input words, including 705 distinct finite
binary32 values from -24 to +6 dB. They include the previously used musical
grid, endpoints and neighbouring words, signed zero and subnormal inputs,
a sixteenth-dB grid and independent output-midpoint neighbourhoods. The oracle
evaluates `10^(input/20)` at 80 and 120 decimal digits and rounds directly to
nearest/even binary32; both precisions agree on every supplied expected word.
The predeclared absolute limit remains 2e-6.

Actual prepared SDK execution in O3 and UBSan builds passes **327,680
independent output checks**. The strict output equals the supplied rounded
reference; the candidate differs by at most 1.1920928955078125e-7 and two ULP.
Each candidate build has 23,440 changed output words in its repeated corpus.
There is no bit-identity claim.

The **163,840 strict/candidate pair comparisons** have the same maximum float
difference. Production 16-bit PCM conversion is identical at 100% volume with
0.5 headroom, without clipping. O3/UBSan and two reconstructed contexts per case
have identical outputs within each profile. Native lifecycle counters are
stubs; this is not device ELF finalisation or global-heap restoration evidence.
Host libm also does not establish target math-library behaviour or CPU cost.

## Matched XIAO measurement

All **48 target runs pass**, checking **491,520 output values** against the
same independent caches. Each vector runs three A–B–B–A rounds, with four
checked warmups and sixteen timed callbacks per run. Both modules use the
same compiler, SDK/support objects, ABI, graph and 1 MiB arena ceiling. Separate
cache controls reproduce the original complete ELF before either batch is used.

| Whole stereo 256-frame callback | Strict | Float32 experiment |
| --- | ---: | ---: |
| Mean across four equally weighted vectors | 15,869.50 µs | 1,326.51 µs |
| Mean / audio block period | 273.38% | 22.85% |
| Observed peak | 16,708 µs | 1,415 µs |
| Timed callbacks | 384 | 384 |
| Complete module ELF bytes | 38,700 | 34,604 |

This is **91.64% less measured callback time**, about 11.96× faster for this
complete test graph. The twelve individual round comparisons save 91.43–92.03%.
Preparation, input/oracle copying, events, I²S, display and networking are outside
the timer. The strict fixture exceeds the audio period; these quiet diagnostic
runs have no live audio deadline. Other patches and full-player headroom are
not measured by this comparison.

Target strict outputs equal the rounded reference. The candidate has 77,160
within-limit word differences and maximum absolute error
1.1920928955078125e-7. Direct target A/B float and PCM captures are not compared;
the pairwise PCM result above is native only. All 48 images finalise and pass
the memory/allocation checks, with unchanged 12,736-byte context size and zero
arena high-water use. Reserved capacity is distinct from measured consumption.

The decoded live callback, named process and preparation-warm sample loops
confirm the mechanism: each strict lane extends to double, multiplies in double,
calls `pow` and narrows back. Each candidate lane uses a Float32 multiply and
`powf`. Binary64 scheduler work outside the sample loop remains. This is not a
claim that every path inside the math library or whole module uses only Float32.

See [the combined numerical and timing record](../evidence/dbtoa-float32.json)
and [all raw target case timings](../evidence/xiao-smoke-dbtoa-f32-comparison.json).
The candidate still exceeds the 10% CPU-review screen. Its repeated benchmark
flags do not add 48 new object contexts to the existing `dbtoa~` follow-up queue.
