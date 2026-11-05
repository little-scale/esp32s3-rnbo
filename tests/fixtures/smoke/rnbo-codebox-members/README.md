# Explicit stateful members

Thirty-six original RNBO `codebox~` programs address explicit member calls,
separately from their owner constructors, aliases and Gen operators. The
two fixed eighteen-source partitions fit complete reference streams inside
the hardware test application. Sources and both partitions are hash-bound.

Each of sixteen owners has a continuous `.next()` case and a separate
`.reset()` case: delta, change, latch, sah, slide, dcblock, accum, counter,
deltaclip, downsamp, zerox, zerox_count, onepole, onepole_lin, biquad and elapsed.
Three additional cases call filter `.clear()`; the final case calls
`history.reset()`. The official per-owner codebox method references are listed
in the catalog. Installed RNBO 1.4.4 reference pages also describe reset/default
state and elapsed sample count. No generated implementation supplies reference
outputs.

## Reference scope

Two independent instances process bounded dyadic vectors, including both zero
signs. Counter uses unit increments and observes only the count output. Reset
and clear occur before the sample's step, on separate channel schedules:

- Left: absolute sample index modulo 257 equals 37 or 38, plus indices 255/256.
- Right: index modulo 263 equals 91 or 92, plus indices 511/512.

This tests repeated/consecutive resets, independence and host block boundaries.
The reference explicitly declares default zero history/phase after reset/clear,
downsample capture at age zero, increment-before-output counter ordering,
strict opposite-nonzero crossings and completed-window held crossing reports.
Some method pages list only signatures; these boundary policies are screening
contracts, not claims that terse prose resolves every convention. Differences
remain recorded without changing inputs, tolerances or references after output.

Signal-state references use mathematical recurrences. Filter and slide models
use ideal Float64 history with one binary32 output conversion, and a predeclared
2e-6 absolute tolerance; other models use zero tolerance. This does not change
the production module's original precision. Every module uses the unchanged
strict profile, zero automatic warmups, four checked manual warmups, sixteen
timed 256-frame callbacks at 44.1 kHz, and a 4 KiB arena ceiling.

## XIAO results, 5 November 2026

**35 programs execute: 27 pass and eight retain output mismatches**, across
**358,400 output checks**. `history.reset()` fails C++ compilation and is not
executed. There are 43,712 numerical mismatches, 42,569 within-tolerance word
differences and 1,292 signed-zero differences, all recorded separately.
Native and target input/reference hashes, aggregate difference counts and
maximum errors agree; that is not proof of identical full output streams.

Part 1 passes all eighteen programs. Part 2 passes nine, retains eight output
mismatches and one compilation rejection:

| Exact forms | Recorded limitation |
| --- | --- |
| `downsamp.next()` / `.reset()` | Capture/hold phase differs from declared capture-at-age-zero model; first left discrepancy at frame 2, actual 0.25 versus expected 0 |
| `zerox.next()` / `.reset()` | Zero-containing vector differs from strict opposite-nonzero policy; first right discrepancy follows negative zero to -1, actual crossing 1 versus expected 0 |
| `zerox_count.next()` / `.reset()` | Corresponding zero-boundary/window counts differ; first right report is 1 versus expected 0 |
| `onepole.reset()` / `.clear()` | Unchanged cutoff after reset/clear leaves zero output; first left numerical discrepancy at frame 38, maximum error about 0.67885 |
| `history.reset()` | Generated C++ references missing left/right history instance fields; no device timing |

Source inspection explains the one-pole failure: reset zeros its history and
both coefficients, while cached frequency and coefficient-update flag remain
unchanged. Clear delegates to reset. The next step recomputes coefficients only
if frequency changes or that flag is set. This explains the native and device
zero output at unchanged cutoff. A repair and a separate frequency-change
recovery check remain follow-up; no exported implementation is published here.
The reference and module remain unchanged so this failure stays reproducible.

Whole-callback medians range from 56 to 500.5 µs, about 0.96–8.62% of the block
period; maximum observed peak is 503 µs. Neither CPU-review rule triggers and
the queue remains 101 contexts. Reset cases include sample counters, remainder
operations, branches and occasional reset calls: their costs are not isolated
reset instruction timings or optimisation comparisons. All 35 images finalise,
with no late-allocation or memory-finalisation fault and zero arena high-water.
The second quiet smoke firmware remains installed.

The dashboard gains 35 scoped member entries, reaching 765 total mappings.
`delta.next()` already had detailed device evidence, which remains alongside
this new screen. Constructor, alias and Gen status does not propagate.
Other parameters/rates/vector sizes, arbitrary call ordering, reset/clear return
values, all counter outputs, host-level reconstruction/reset and complete
object semantics remain outside these bounded checks.

Evidence: [part 1](../../../../evidence/xiao-smoke-rnbo-codebox-members-part1.json),
[part 2](../../../../evidence/xiao-smoke-rnbo-codebox-members-part2.json),
[native diagnostics and first mismatch words](../../../../evidence/rnbo-codebox-members-native.json).

```sh
python3 tests/fixtures/smoke/rnbo-codebox-members/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_rnbo_codebox_members_reference.py
```
