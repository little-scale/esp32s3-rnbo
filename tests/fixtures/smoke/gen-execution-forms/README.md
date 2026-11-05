# Gen execution screens and compound assignments

Twenty-four original source scenarios close named/context and grammar gaps after
existing Gen arithmetic, data, constants and state batches. Every `.genexpr`
is embedded verbatim in its own RNBO `gen~` patch. The installed RNBO 1.4.4
operator metadata and the official [GenExpr guide](https://docs.cycling74.com/userguide/gen/gen_genexpr/)
provide the source-form contracts. RNBO codebox, visual Gen and named stateful
operator constructors remain separate surfaces.

## Predeclared checks

- `noise()` emits a range flag for each sample (`-1 <= n <= 1`) and a rolling
  status requiring at least one adjacent change in each 32-sample window.
  Expected flags are one; no RNG algorithm or emitted sequence supplies the
  reference. This is a basic finite/range/variation screen, not a distribution,
  exact sequence, seed/reset or independent-instance test. Equality of native
  and target flag words does **not** imply equal random sequences.
- Eight bare FFT globals (`FFTSIZE`, `fftsize`, `FFTOFFSET`, `fftoffset`,
  `FFTHOP`, `ffthop`, `FFTFULLSPECT`, `fftfullspect`) and three five-result
  `fftinfo()` programs attempt basic finite, integer, nonnegative screens with
  an engineering bound of 1,048,576; full-spectrum flags must be zero or one.
  That bound is a test screen, not a documented FFT limit. No numeric default is
  guessed or fitted. Cycling '74 documents [FFT defaults outside pfft~](https://docs.cycling74.com/reference/gen_dsp_fftinfo/)
  without specifying their values. These programs all fail C++ here, so no FFT
  screen, default value, pfft context or transform is hardware-qualified.
- Ten local compound assignments test `+=`, `*=`, `-=`, `/=`, `%=`, `&=`, `|=`,
  `^=`, `<<=` and `>>=` on a bounded finite grid. Modulus/bitwise operands are
  nonnegative; divisors are nonzero and shift counts are 0–3. The reference
  uses independent arithmetic and final binary32 rounding, never native output.
  A local compound-assignment result does not qualify the similarly spelled
  stateful `plusequals`/`mulequals` constructor, reset or range attributes.
- Two History compound updates read old output state before adding one impulse
  or multiplying one negative factor per host block. Absolute prefix-count and
  parity references would expose resets at 256-frame boundaries. Both sources
  fail C++, so they provide no executed state result; earlier explicit History
  assignments retain their separate passing evidence.

Sources, inputs and references are frozen before target execution. The builder
and collector bind the complete 24-source ledger and recompute all twenty
continuous reference blocks, with zero automatic preparation blocks, four
checked manual warmups, sixteen timed callbacks and a 4 KiB arena ceiling.
Tolerance is zero. There are no host parameter events, one-frame production
ABI calls, changed math libraries or DSP optimisations in this batch.

## XIAO results — 5 November 2026

**Five programs pass 51,200 output-word checks:** four local arithmetic forms
and the basic noise screen. All observed flag/arithmetic words match their
references bit for bit. All five images finalise; no host/local late allocation
or free occurs, arena high-water is zero, and free PSRAM/internal memory is
unchanged at completion. These are quiet offline callbacks without I²S/UI/network.

| Complete authored program | Median µs | Peak µs | Median / audio period |
| --- | ---: | ---: | ---: |
| Noise range/32-sample variation screen | 115 | 120 | 1.98% |
| Local `+=` | 45 | 45 | 0.78% |
| Local `*=` | 44 | 45 | 0.76% |
| Local `-=` | 44.5 | 45 | 0.77% |
| Local `/=` | 95 | 99 | 1.64% |

Neither CPU rule triggers; the existing review queue remains **111 contexts**.
These are complete scenario costs, including the noise checker, not isolated
opcode benchmarks or optimisation percentages.

**Nineteen source scenarios do not execute:**

| Forms | Count | Stage and observed reason |
| --- | ---: | --- |
| Eight bare FFT globals | 8 | C++: exact global identifier is undeclared |
| `fftinfo()` size/hop/flag/offset screens | 3 | C++: lowered FFT globals are undeclared |
| Local `%=` | 1 | C++: emits native `%` with floating operands |
| History `+=`, `*=` | 2 | C++: bare History name is emitted instead of its bound state field |
| Local `&=`, `\|=`, `^=`, `<<=`, `>>=` | 5 | Gen frontend: parser rejects the compound `=` token |

These are exact form/route failures, not blanket claims about the corresponding
ordinary arithmetic operators, all Gen histories or actual Max pfft processing.
The unchanged native preflight agrees with target arithmetic/flag diagnostics;
source identities and compiler/frontend log hashes are retained for every reject.

Evidence: [hardware](../../../../evidence/xiao-smoke-gen-execution-forms.json)
and [native plus complete rejection ledger](../../../../evidence/gen-execution-forms-native.json).
The hardware collector records which smoke app was left at its own checkpoint;
the [normal player restoration](../../../../evidence/xiao-gen-execution-player-restoration.json)
checks the same saved Main, control values, advancing frames and healthy USB
status after the batch, so Studio remains usable.

```sh
python3 tests/fixtures/smoke/gen-execution-forms/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_gen_execution_reference.py
```
