# Extended Gen data and sample access

Thirty-one original GenExpr sources cover table lookup, oscillator/data forms,
weighted writes, index/channel boundaries, returned read indices and selected
declarations. Two fixed partitions contain sixteen and fifteen sources.
All are embedded as explicit expressions in RNBO `gen~`; visual Gen remains
separate. Helpers used to initialize or observe a table do not acquire blanket
operator qualification.

Primary contracts are the installed RNBO 1.4.4 Gen registry and the official
[wave](https://docs.cycling74.com/reference/gen_dsp_wave/),
[lookup](https://docs.cycling74.com/reference/gen_dsp_lookup/),
[cycle](https://docs.cycling74.com/reference/gen_dsp_cycle/) and
[splat](https://docs.cycling74.com/reference/gen_dsp_splat/) references. Catalog
entries retain primary metadata hashes and source-specific reference links.

## Fixed reference policy

Eight-cell, two-channel local tables are initialized explicitly at the first
sample. Read tests use asymmetric dyadic contents. Stateful weighted writes
start with explicit zeros. The original Float32 Data producer/storage remains
unchanged. A 2 MiB test arena ceiling accommodates the builtin oscillator
tables; it is not measured state use or a storage conversion.

- Wave sample/phase/section and lookup sample/signal forms are separate sources.
  The declared phase period is eight cells, inclusive lookup endpoints map
  -1/+1 to indices 0/7, and section phase maps to sample positions 1..6.
- Builtin cycle phase uses cosine phase origin. Frequency programs declare
  output-before-step. Short periods check regular phase steps; the additional
  512/1024-sample periods expose resets at 256-frame host boundaries.
- Splat checks isolated adjacent-cell weights, exact cumulative overdubbing,
  a half-overdub recurrence and phase-indexed writes. Accumulation references
  are absolute prefix sums across all callbacks. In-program cell writes are
  part of the authored algorithm; the wrapper does not reset contexts.
- Index/channel modes declare ignore, wrap, clamp, fold and mirror behavior.
  Fold excludes duplicated endpoints; mirror includes them. These endpoint
  policies are explicit where the primary prose is less precise.
- Peek exposes an unrounded sample-index return. The phase sample case declares
  an unwrapped converted coordinate as its returned index, preserving any
  discrepancy rather than fitting a wrapped-index interpretation afterwards.
- Standalone read/write use a local Delay. External Buffer probes request no
  real file/data binding; normal adapter admission is expected to reject them.
  A lowercase data declaration observes dimensions only.

Twenty continuous 256-frame callbacks at 44.1 kHz use zero automatic preparation
blocks, four checked manual warmups and sixteen timed calls. The unchanged
strict module profile uses zero tolerance for exact table/boundary/sum models;
selected interpolation, oscillator and recurrence models declare 2e-6 absolute
tolerance. Ideal models round once at binary32 output observation. No input,
reference, tolerance or DSP code is fitted after device output.

## XIAO results, 5 November 2026

**24 programs execute: 17 pass and seven retain output mismatches**, across
**245,760 output checks**. Two frontend failures, three C++ failures and two
adapter-preparation failures remain separate and are not flashed.
The batch records 35,340 numerical mismatches, 8,296 within-tolerance differences
and 1,920 signed-zero differences. The signed-zero differences occur in two
isolated/phase splat cases; they are not numerical failures or bit-identity
qualification. All 17 passing cases satisfy their original error limit.

Passing groups include both builtin oscillator phase/frequency forms, the
long-period cross-block oscillator, lookup signal/sample, four splat programs,
index ignore/wrap/clamp/mirror, channel ignore/wrap on XIAO, peek returned sample
indices and lowercase data dimensions. The seven mismatches are:

| Exact scenario | Retained limitation |
| --- | --- |
| Wave section | Values differ from declared sample section 1..6 |
| Named local-table cycle | Output differs from the authored local wavetable |
| Peek index fold | Endpoint/reflection behavior differs from declared fold policy |
| Peek channel clamp/fold/mirror | Invalid/negative channel behavior differs on XIAO |
| Phase sample returned index | Returned coordinate differs at wrapping boundaries |

Positional local-table cycle fails C++ because a SampleBufferRef reaches a
numeric oscillator argument. The standalone read/write programs emit an
undeclared Delay identifier; write also retains an unreviewed two-sample
bool-compare diagnostic. Explicit wave sample/phase constructors fail frontend
boundmode-property handling. Both Buffer declaration spellings reach normal
preparation but are rejected for externalDataRefs. These are scoped source/
adapter outcomes, not claims against all waves, oscillators or buffer objects.

## Native/device portability finding

Native and XIAO inputs and expected stream hashes match for all 24 executions.
Their diagnostics differ on all five negative-channel programs. For example,
channel ignore/wrap pass on XIAO but differ natively, while channel clamp passes
natively and differs on XIAO. Native output is not the device oracle.

Generated peek takes channelOffset as unsigned Index and receives a floating
channel value before applying its channelmode. A host build with UBSan and
float-cast-overflow stops on -2 converting to unsigned int. This is a concrete
portability issue, consistent with the observed architecture/compiler-dependent
results. The additional sanitizer run is a host diagnostic, not target sanitizer
coverage or a claim that every fold/mirror rule is explained. See the
[Clang check description](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html#available-checks).
The generated source hash, command/log hashes and first diagnostic are saved.

## Cost and memory

Only signal-indexed lookup triggers CPU review: 807 µs median, 811 µs observed peak,
about 13.90% of the block period. It passes its output reference. The queue grows
from 110 to 111 contexts. Other medians range 58–563 µs, with no peak-spike flag.
These complete authored callbacks include initialization checks and helpers;
there is no isolated opcode cost or optimisation comparison.

Local Data cases observe 128 bytes arena high-water. Two builtin cycle instances
observe 65,648 bytes; the named local-table cycle program observes 65,776 bytes.
All 24 images finalise, free internal/PSRAM totals return unchanged, and no
process/late-allocation fault occurs in the ordinary native or target run.
The separate sanitizer stops as described above. Quiet part 2 firmware remains
installed; production Main package storage and settings are preserved.

This Gen evidence does not promote RNBO object-table entries, which remain 778
scoped mappings. Other modes, resource binding, all aliases, visual Gen,
variable-block/one-frame production ABI calls, full oscillator/data binding,
index conventions and portable negative-channel handling remain pending.

Evidence: [part 1](../../../../evidence/xiao-smoke-gen-data-extended-part1.json),
[part 2](../../../../evidence/xiao-smoke-gen-data-extended-part2.json),
[native and sanitizer diagnostics](../../../../evidence/gen-data-extended-native.json).

```sh
python3 tests/fixtures/smoke/gen-data-extended/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_gen_data_extended_reference.py
```
