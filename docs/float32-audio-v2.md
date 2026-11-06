# Reviewed float32 audio profile v2

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

`--numerical-profile float32-audio-v2` is an explicit optional profile for
reviewed RNBO1.4.4 generated methods. Strict remains the default. V2 adds nine
whole-method fingerprints to v1's catalogue: scalar-frequency `cycle~` with an
active scalar phase input, fixed/scalar/signal cap40 comb and allpass methods,
and scalar addition/safe division expression methods. Other forms still fail
admission. This is not blanket float32 conversion of a generated patch.

V1's admission sets are unchanged. V2 copies those sets before adding forms.
Independent review compared the previous committed helper with the revised
helper on the drone cap40 source and seven previously admitted fixture sources:
previous-v1, current-v1 and current-v2 produced identical generated source bytes.
Compiler/provenance hashes change when the helper changes; historical prepared
trees and qualification reports remain intact.

The new filter forms retain their existing `mstosamps(MillisecondTime)` call.
Its result was already `number`/float32, but its intermediate calculations use
double precision. Comb's reviewed scalar initializers were already assigned
to float, and its clamp result rounds to the same float. In allpass, multiplication
by -1 itself is exact negation, but the unsuffixed literal also promotes the
surrounding audio multiply/add expression to double. V2 deliberately changes
that expression's rounding to float32. The current fixtures use gain 0.5, for
which the observed output remains bit-identical; that result does not establish
bit identity for arbitrary scalar gains. The exactly representable 40ms cap
does not change the argument passed to the retained duration conversion.

An initial experiment also replaced those local duration calculations with
float32 arithmetic. It failed the existing filter tolerances: maximum absolute
errors were 0.0000538528 for fixed, 0.0001884103 for scalar and 0.0002563596 for
signal filters; the largest PCM difference was four LSB. A 16ms conversion can
move from 705.5999756 to 705.6000366 samples, changing fractional interpolation
and repeated echoes. That experiment was rejected. Tolerances were not widened.
V1's previously qualified comb fingerprint retains its existing explicit
float32 local conversion in both profiles; the new filter hashes do not.
Provenance records `retained_double_ms_to_samples` separately from
`local_float32_ms_to_samples` for each method.

The new cycle method retains unsigned integer phase accumulation and the
original truncation macro. Multiplication of the fixture's finite float phase
values in [0,1] by exactly 2^32 preserves their integer conversion; fractional table
interpolation is still subject to the profile's float expression rounding.
The addition method has no decimal literal to change. Safe division's quotient
already used float operands; suffixing its zero literals removes conditional
promotion while preserving its explicit zero-divisor branch. These statements
describe the reviewed bodies and finite supported controls, not arbitrary
exceptional floating-point inputs.

Scheduler methods, frame counters, clock types, buffer ownership and ring
interpolation methods are outside the edits. Float32 delay storage remains a
separate option with its own paired-buffer guards. V2 does not remove every
audio double calculation, and no target speedup is claimed for its new forms.

## Admitted additional method identities

Fingerprints normalize comments, whitespace and the generated object prefix.
They cover the complete signature and body, including the explicit 40ms cap.

| Method form | SHA256 |
| --- | --- |
| cycle scalar frequency and active scalar phase | `1dbcc6178f4628491e85c1a2c54289819d118cd5ff26ab44fda7acefe8390cc5` |
| comb fixed | `c4b12e4afc5e96e32aa8f6d95eea1dd1d51aca5eb22e8649c89d3cec84ef4542` |
| comb scalar | `9d75ec01d3f3ab5473e7ef87c4973dc9d899d40b4a7101d83a56758f2fe9e348` |
| comb signal | `47fd9c5b7b393e5deae3dde5408dac3986502ae5ef20a9a28b26d1e581243166` |
| allpass fixed | `be98f0a867d8027e45f9448b1c1e35abd8ac9193b28f66f4beea1d43ed8388fc` |
| allpass scalar | `40937256b1dd5e79b82582326fcae8938839c2d73edc13d2b50098ae931878b0` |
| allpass signal | `07d2fb4ef43c20463acf1c3ebfb6735dd30a2f10756243fa94b17e9df1162ef8` |
| scalar addition | `b49df46a014c8593fbf091762f70754a8849a4e261d3afbcaf7df01a42ce2e73` |
| scalar safe division | `c635d90b32a2b751d534a876cffa2598133f384ad0fcb6f8eec2927ba2db9848` |

## Native numerical evidence

The sealed report `build/object-qualification/audio-v2-qualified/report.json`
completed and passed all twelve v2 fixtures and their 39 cases, using 512
vectors of 256 frames per case, four warmup vectors and seed 0x12345678. Its
32 variant records include 94 rendered cases and three explicit unsupported
legacy v1 audio-plus-storage combinations. Unsupported combinations are not
successful qualifications. Each native comparison checks the declared semantic,
float/PCM limits and finite output, with no render errors or late Platform
allocations.

| V2 fixture | Cases | Maximum absolute difference from strict | Maximum PCM LSB |
| --- | ---: | ---: | ---: |
| mtof varying | 3 | 5.96046448e-8 | 1 |
| saw signal | 4 | 0 | 0 |
| reson modulated | 4 | 0 | 0 |
| cycle fixed | 2 | 0 | 0 |
| cycle scalar | 4 | 2.91038305e-11 | 0 |
| cycle signal | 4 | 2.91038305e-11 | 0 |
| scale linear | 3 | 0 | 0 |
| comb/allpass fixed | 1 | 0 | 0 |
| comb/allpass scalar | 3 | 0 | 0 |
| comb/allpass signal | 4 | 0 | 0 |
| delay crossfade | 4 | 1.49011612e-8 | 0 |
| arithmetic DC | 3 | 0 | 0 |

The revised filters and arithmetic were float-bit-identical in these cases.
A separate `audio-v2-storage` run passed all four filter/delay fixtures with
the combined v2 audio and float32 delay-storage options. Its filter comparisons
were also bit-identical; ordinary delay's maximum difference was 1.49011612e-8
with no PCM difference. That report has 20 variant records, 52 rendered cases
and the same three explicit unsupported legacy v1 combinations. The
[public host evidence](../evidence/float32-audio-v2.json) retains both successful
runs and the rejected conversion experiment with their source/build identities.
Eleven audio/storage admission tests passed, including the three new v2 tests:
v1 rejection of new forms, preservation of all bytes outside admitted methods,
mutated algorithm/coefficient rejection, retention of double filter conversion,
and identical v1/v2 bytes for previously admitted fixture forms.

Evidence SHA256 values:

| Item | SHA256 |
| --- | --- |
| revised helper `host/compiler/float32_audio.py` | `f968ac63014532e82e67bb880765e70c2fefe80ed24b3a54e8c0cf89c88211c3` |
| new v2 admission tests | `dba03f26b41c89c61dfe7dc5d85e24f1d6ecf3322718019652c7a5dc650cd79c` |
| qualified native report | `ef3f764d561d8924f6578929d9d40d6beb83decd01bb64d04129548b951f291a` |
| combined-storage native report | `eec4262bd261a3ccefcf0ec0aeaa08ed32e8d005fdefeac473405bfe9f3dff82` |
| rejected initial native report | `9a955943ad13578a44fb45f85a3e798bca6c4cefa91692df6ecb374a0631f6db` |
| qualifier copied into both report directories | `4d095781e51d7dbc9e7ac3c2e477dbf7977525b52a39d3544c796f9d362bbde7` |
| authored fixture catalogue | `fd6f1bfff3fdb10607c227d090a6efc44d45da8ebb893d8728e20d025d2fc73a` |

The reports also bind each prepared manifest/provenance, native build report,
renderer and raw float/PCM output. Original generated bodies remain local build
artifacts. Neither this native run nor earlier target v1 object benchmarks
establishes v2 target execution or timing for the newly admitted forms.

## Further numerical workloads

The current filter semantic check establishes nonzero finite impulse energy,
bounded peak and decay; it does not independently verify echo position or the
transfer function. Useful next checks are the first echoes and recurrence at
10ms/441 samples and 40ms/1764 samples, followed through ring wraps. At those
integer delays, compare a unit impulse with the independently derived comb
and allpass recurrences using the fixture gains. For fractional delays, test
values immediately below/above one sample, half a sample and the 40ms cap,
then compare interpolation weights and frequency response with an independent
fractional-delay reference. Signal-delay steps and modulation should cross
those boundaries and vector boundaries. The admitted allpass scalar-gain form
also needs direct coverage with non-binary gains and fractional input values,
as well as near zero and the 0.99 clamp, with a suitably long decay measurement.
Current authored fixtures use gain 0.5. Those additional cases must measure the
float32-versus-double multiply/add rounding under the existing numerical-profile
contract rather than assume the present fixture's bit identity generalizes.

Cycle's current analytic check compares cosine against its emitted phase. Add
an independent phase-increment/frequency check so a shared phase error cannot
pass both channels. Include phase 0, the float immediately below 1, phase 1 and
block-boundary phase/frequency changes across wrap. Arithmetic's current cases
mostly use exactly representable binary fractions. Add non-binary controls,
cancellation, small positive divisors and signed zero while keeping a separate
expected-fault case for finite inputs whose quotient overflows. These are
coverage proposals, not unrecorded successful tests.
