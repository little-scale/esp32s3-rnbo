# RNBO codebox lists and fixed arrays

Original, bounded RNBO 1.4.4 `codebox~` programs: the eleven documented list
members and all seventeen installed fixed-array constructor spellings. These
are supplemental member/type inventory entries, not top-level objects or Gen.
The [official codebox guide](https://rnbo.cycling74.com/codebox) supplies the
list-method contracts, explicit `list` return typing, typed indices and array
constructor syntax. `FixedUIntArray` and `FixedTimeArray` additionally appear in
the installed registry; their guide-coverage caveat remains on the dashboard.

## Sources and independent expectations

Each list starts as `[in1, 2, 3, 2, 5]`. The current-sample dependency is
deliberate: an input-independent literal is created once per vector by this
producer. A simple weighted checksum exposes the returned list and the original
list after mutation, or the returned scalar and the mutated list. An authored
custom function and bounded typed `for` loop compute the checksum. List-returning
variables have explicit `list` types; no generated code is manually repaired.

Each fixed array starts as `[1, 2, 3, 4, 5]`. An independent persistent typed
cursor writes the current left input into one cell, returns that cell and reads
the next cell before advancing. The next cell holds its explicit initializer
for the first four samples and thereafter the value written four samples ago.
Twenty continuous 256-frame callbacks expose state across all callback edges.
The Python model uses absolute sample age rather than replaying the cursor.

Unsigned arrays use small nonnegative integers. Other arrays receive bounded
quarter-step values; integer writes truncate toward zero within range. Every
expected value is exactly representable in binary32. Float64/Double/Time array
storage is preserved, as are all explicit integer types. No narrowing profile,
overflow assumption, arbitrary dimension, growth, empty-list or out-of-range
index claim is made. The two outputs observe values, not physical storage bytes.

The source/independent-reference catalog is pinned by the builder and collector.
The collector recomputes every full reference stream and requires zero numeric
tolerance. Signed-zero differences remain separately counted. Every executable
module uses the ordinary strict FX profile, zero automatic preparation blocks,
four checked manual warmups, sixteen timed callbacks and a 4 KiB arena ceiling.

## Results, 5 November 2026

All **26 executable programs pass on XIAO**, checking **266,240 output values**,
with zero bit or numeric differences. The native preflight independently passes
the same vectors and expected streams, with zero observed late C++ allocations.
All seventeen constructors and nine list methods have scoped device evidence.
All images finalise; the measured arena high-water is zero, with fixed arrays
stored in their opaque contexts. This is not a zero-total-memory claim.

`push` and `unshift` export and prepare, but their generated C++ cannot assign
the documented returned length: the runtime methods return `void`. Both exact
source forms remain compile failures, not executed failures or CPU observations.
Mutation-only use and a potential compatibility repair remain later work.

| List method | Median µs / 256 frames | Peak µs | Median / block period | CPU review |
| --- | ---: | ---: | ---: | --- |
| `pop` | 58 | 63 | 1.00% | No |
| `shift` | 865.5 | 866 | 14.91% | Yes |
| `concat` | 737 | 738 | 12.70% | Yes |
| `fill` | 669 | 670 | 11.52% | Yes |
| `splice` | 673 | 674 | 11.59% | Yes |
| `slice` | 372 | 377 | 6.41% | No |
| `includes` | 150 | 155 | 2.58% | No |
| `indexOf` | 161 | 161 | 2.77% | No |
| `reverse` | 668 | 668 | 11.51% | Yes |

Fixed-array medians span 97–258.5 µs, peaks 101–263 µs. Float32/Sample/Number/
Float contexts measure 97 µs; Float64/Double/Time contexts measure 258–258.5 µs.
These are complete authored callbacks, including list construction/copies,
checksum functions or array indexing/state. They are not isolated method costs,
an optimisation comparison or a measured speedup. The five list contexts join
the CPU backlog for later investigation; no exceptional peak-spike flag triggers.

Earlier native-only experiments with a constant list literal exposed exhaustion
under repeated removals, including a fault when repeatedly shifting an empty
list. They were not flashed. Their sources and observations remain in the
[native evidence](../../../../evidence/codebox-containers-native.json), separately
from the sample-dependent fixtures and their passing device results. Likewise,
implicit scalar typing of list-returning variables is a fixture typing error,
not a supported-form failure; the explicit types above follow the guide.

Results: [XIAO](../../../../evidence/xiao-smoke-rnbo-codebox-containers.json),
[native preflight](../../../../evidence/codebox-containers-native.json),
[CPU backlog](../../../../docs/cpu-review-backlog.md).

Regenerate or check the original source corpus with:

```sh
python3 tests/fixtures/smoke/rnbo-codebox-containers/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_rnbo_codebox_containers_reference.py
```

The reusable `rnbo_smoke_stream_test` native executable is built whenever a
prepared export is supplied to the root CMake project. Its two file arguments
are a 512-word little-endian binary32 input vector and a 10,240-word expected
stream. It checks twenty callbacks, finite outputs, wrapper statistics and late
C++ allocations; finite mismatches are reported rather than turned into claims
about target execution.
