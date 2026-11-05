# RNBO list-function call forms

Thirty-four original programs cover fifteen flattened list-function names and
their separately authored dotted inventory spellings, plus `listcompare`,
`listsect`, `listswapelements` and a `listscramble` invariant-validation program.
The [codebox guide](https://rnbo.cycling74.com/codebox) documents flattening the
period in a list object's name when calling its codebox function. A rejected
`list.len(...)` member-call source does not reject the documented `listlen(...)`
function or the event-patcher `list.len` object.

Each list depends on the current sample, so constant-literal vector hoisting
does not exhaust the input across samples. Small lists remain within sixteen
cells. Models use length-sensitive weighted value/index fingerprints from the
documented contracts, without copying a generated algorithm. The fingerprints
do not prove arbitrary list contents or every mode. Sort inputs have unique
values, so unspecified tie ordering does not determine the expected index map.
Slice/rotation vectors declare zero, ordinary and beyond-length controls before
execution. `ecils` uses the published last-N-right description; inconsistent
installed metadata is not resolved by fitting a reference to target output.

## Results, 5 November 2026

| Outcome | Programs | Scope |
| --- | ---: | --- |
| XIAO pass | 9 | Bounded value/index fingerprints and pilots |
| XIAO output mismatch | 1 | `listsect` duplicate-policy comparison |
| C++ rejection | 7 | Array-bounds warnings treated as errors |
| Frontend rejection | 16 | Fifteen dotted call forms and full scramble validation |
| Native preflight fault, not flashed | 1 | Wide `listrot` vector |

Ten programs execute **102,400 output checks** across twenty callbacks each,
with zero automatic preparation, four checked manual warmups and sixteen timed
callbacks. All target images finalise and pass allocation/memory gates. Native
and target use the same vectors, with the same pass/mismatch outcomes. The
original strict storage/processing profile is preserved; no precision or DSP
optimisation is applied.

| Executed function | Result | Median µs | Peak µs | CPU review |
| --- | --- | ---: | ---: | --- |
| `listindexmap` | Pass | 383 | 387 | No |
| `listjoin` | Pass | 444 | 448 | No |
| `listlace` | Pass | 365 | 370 | No |
| `listlen` | Pass | 40 | 41 | No |
| `listsum` | Pass | 59.5 | 60 | No |
| `listswap` | Pass | 917 | 917 | Yes |
| `listthin` | Pass | 525.5 | 528 | No |
| `listunion` | Pass | 861 | 861 | Yes |
| `listsect` | Reference mismatch | 309.5 | 314 | No |
| `listswapelements` | Pass | 107 | 112 | No |

`listswap` and `listunion` use 15.80% and 14.83% of the 256-frame period in
their authored callbacks. They join the review queue, bringing it from 99 to
**101**; neither peak-spike rule triggers. Timings include list construction,
copies, fingerprints and helper work. They are not isolated function costs,
an optimisation comparison or a worst-case latency bound.

`listsect` differs in all 5,120 left fingerprints; its right pilot matches.
The unchanged reference retains left-list duplicates when they occur in the
comparison list. The first target fingerprint is **208**, versus **314**
expected: consistent with a unique intersection instead of a duplicate-
preserving filtered list. This is an inference from the scalar witness, not a
complete captured-list reconstruction. Clarifying the duplicate policy remains
follow-up. The model is not rewritten after observing output.

## Rejections and preflight protection

`listcompare`, `listdelace`, `listecils`, `listfilter`, `listmedian`, `listslice`
and `listsort` fail target C++ compilation with `-Werror=array-bounds` in
`RNBO_List.h`, identifying a subscript beyond a five-element array. Warning
checks remain enabled; these sources are not executed. A scoped runtime/compiler
investigation is needed before deciding whether a warning is a false positive
or an unsafe copy/access path.

All fifteen dotted member-call programs fail the frontend. The flattened
functions have their own outcomes above; no alias inherits a result. The full
scramble invariant program fails nested-list type/value binding in the
frontend. A separate minimal `listscramble` call exports, so this is not a claim
that every use of the function is unsupported. Its permutation, position-map
and randomness properties remain unqualified on XIAO. The authored invariant
does not require a fixed random sequence or random index dereference.

The five-element rotation vector includes shifts from -8 to +8. In native
preflight its first 256-frame process returns `RNBO_S3_FAULT`, with one platform
error, zero invalid samples and no late allocations. It is **not embedded or
executed** in the shared hardware application. The builder verifies the native
log, original source, vector/reference hashes and diagnostic-harness identity
before excluding it. The result retains a native-preflight failure separately
from frontend/C++ failures and target results. Safe isolated rotation modes and
an eventual device reproduction remain pending; narrowing the vector does not
erase this finding.

Evidence: [target results](../../../../evidence/xiao-smoke-rnbo-codebox-list-functions.json),
[native checks, diagnostics and excluded rotation case](../../../../evidence/rnbo-list-functions-native.json),
[CPU backlog](../../../../docs/cpu-review-backlog.md).

```sh
python3 tests/fixtures/smoke/rnbo-codebox-list-functions/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_rnbo_list_functions_reference.py
```
