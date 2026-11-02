# Target checks against independent object models

The original biquad and nonlinear FX fixtures passed on the AMOLED V2 at
44,100 Hz with 256-frame vectors. Each run compared two copies of the **same
strict module artifact**. These are controls for the inputs, mathematical
models, loader lifecycle and measurements. No optimisation gain is claimed.

The [sealed evidence](../evidence/wave2-target-oracles.json) records the actual
firmware/module identities, raw log and report hashes, all cases, model
parameters, cache fingerprints and observed memory. The fixture catalogue is
[target-oracles.json](../tests/fixtures/objects/wave2/target-oracles.json).

| Fixture | Cases | Pairwise float words | Largest model error bound | Unchanged model limit |
|---|---|---:|---:|---:|
| Biquad | default, identity, slow pole | 2,359,296 | 1.415575225927057e-7 | 3e-6 |
| Nonlinear chain | square, fractional exponent 0.25, fourth power | 2,359,296 | 2.8797920270662303e-8 | 2e-6 |

Both controls had zero pairwise float difference and exact PCM output. Each
also checked 4,718,592 scalar outputs against its independent model. All samples
were checked, including the vectors excluded from timing. Three alternating
rounds used 512 vectors per case, four detached zero-input warmup vectors and
seed `0x12345678`. The first 32 rendered vectors of each pass were excluded
from process timing.

## Model and input policy

The biquad model evaluates the difference equation with Float64 history and
the original **Float64 catalogue coefficients**. It deliberately retains the
existing native mathematical reference: the module itself receives Float32
parameters and uses Float32 state. Four zero-input warmup vectors leave the
history zero; the three scalar cases apply at the first rendered block. The
input is the authored impulse/step signal: left impulses at frames 0 and
4,096, and right `+0.25` before frame 8,192 followed by `-0.125`.

The nonlinear fixture checks the authored `tanh`, wrap to `[-1,1)`, clip to
`[0,1]`, and positive-power chain. Its independently varying stereo grids hold
each input for 64 samples. The tested left domain is `[-4,4]`, the right grid
is within `[-3,3]`, and exponents are 2, 0.25 and 4. This is a qualification of
that bounded graph and those cases; it does not establish every primitive's
full input domain.

The portable C models generate one Float32 oracle cache from Float64 model
results outside the process timer. Their measured cache-rounding error is
charged within the original semantic limit:

```
maximum output/cache error + maximum cache/model rounding error <= model limit
```

Both input and oracle cache SHA values are checked around every pass: 27
checks of each cache per fixture. Model cases use both output channels and
therefore have separate semantic counters rather than reference-channel pilot
checks. Host and target library implementations are not assumed to produce
identical transcendental bytes; the target records its actual oracle cache.

The biquad additionally checks the Float64 mean of the final 1,024 right-channel
samples of each pass against
`-0.125 * ((a0+a1+a2)/(1+b1+b2))`, computing the gain first with the original
Float64 coefficients. All 18 means passed the unchanged `3e-6` limit. The
largest observed DC error was `6.705522527516994e-8`.

The public reusable catalogue retains the original pairwise limits of `2e-6`,
one PCM LSB and relative RMS `1e-4`. The separate sealed control catalogue used
for these physical runs tightens all three pairwise limits to zero. Its patch
copies are byte-identical to the authored public fixtures. Independent model
limits remain `3e-6` and `2e-6` in both catalogues.

## Observed process time and memory

These timings measure the complete authored process callback. Input/oracle
generation, cache copies, events, preparation and output analysis are outside
the timer. I2S, display and networking are inactive. The two columns are copies
of the same module and provide control observations.

| Case | Copy A mean µs/vector | Copy B mean µs/vector |
|---|---:|---:|
| Biquad default | 84.31 | 84.28 |
| Biquad identity | 84.17 | 84.29 |
| Biquad slow pole | 84.55 | 84.67 |
| Nonlinear square | 541.79 | 541.34 |
| Nonlinear fractional | 669.53 | 669.17 |
| Nonlinear fourth power | 675.63 | 675.25 |

| Per-image observation | Biquad | Nonlinear |
|---|---:|---:|
| Caller-owned context | 12,848 B | 14,800 B |
| Reserved arena | 4,096 B | 4,096 B |
| Observed arena high-water | 0 B | 0 B |
| Aligned `.text` reported by the loader | 34,004 B | 33,540 B |
| Text mapping span upper bound, including loader layout | 34,584 B | 34,136 B |

Zero arena use is separate from context, mapped code/data, loader overhead and
the persistent input/reference/oracle caches. Mapping and allocator alignment
can reserve more than the recorded text span. Each oracle cache occupies 1 MiB
at 512 vectors. The conservative build budget includes those buffers and both
image states. Both runs recovered the observed free PSRAM and internal memory
after unloading, finalized all four loaded images, and observed zero guarded
host heap operations or module-local late allocations. Instrument recovery
passed after both runs.

## Precision audit and limits

The audit classifies no resolved FP64 helper calls in the inspected generated
object-kernel paths, while retaining two unresolved parent engine calls and
separately classified Double clock/configuration/event work. For the exact linked
nonlinear module, an additional static audit follows the `tanhf`/`powf` library
closure through 14 functions and 32 callsites. It resolves every call in that
closure and observes zero FP64 helpers there, including the inspected error
paths. The complete module still contains Double clock/configuration/event
work. This audit does not establish whole-program absence of Double, execution
frequency or a timing bound.

The recorded offline validation includes 201 compiler tests and 62 tools tests,
with hashed logs. The portable tests cover the six mathematical cases, cache
rounding, chunk continuity, invalid domains, a regression for the actual C
DC-mean loop, and sanitizer stress. Physical callback observations remain
separate from those tests and from full instrument deadline qualification.
