# RNBO event-rate maths on XIAO

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The 44 exact source forms all compile and run. **41 pass their declared
finite-domain mathematical screen; three retain approximation differences.**
There are **450,560 output-word checks**, **924 actual-value parameter actions**,
no nonfinite outputs, and no right-pilot word differences. The full RNBO/Gen
qualification goal remains active; these are scoped short checks.

| Named approximation | Outside-screen words | Maximum absolute error | Screen |
| --- | ---: | ---: | ---: |
| `fastexp` | 5,120 | 0.0767393112 | 0.001 |
| `fastpow` | 5,120 | 1.1512107849 | 0.001 |
| `fasttan` | 2,304 | 0.00209313631 | 0.001 |

All three also differ in the native preflight, with the same outside-screen
counts and maximum errors. These are intentional approximate operations tested
against the exact mathematical functions; an exceeded screen is retained as a
numerical qualification gap, not a general failure to execute or evidence of an
ESP-specific bug. First mismatch call/word witnesses and raw timing are saved.
The other named approximations (`fastsin`, `fastcos`, `cosT8`, `cosT8safe`) pass
only their declared domains. There are **36,608 within-limit target differences**
recorded separately, compared with 25,600 in the native run. No zero-sign-only
differences occur in this batch. Numerical limits were not widened after testing.

Each image receives 21 ordered hot parameter updates before 20 full callbacks,
with fixed arguments, repeated inputs, hold gaps and multi-event callbacks.
Native and target references use the same dyadic input schedule. The
[fixture contract](../tests/fixtures/smoke/rnbo-events-math/README.md) lists the
bounded domains, mathematical definitions, precision and explicit exclusions.
The untouched right signal is independently hashed over all 5,120 words per
scenario, so a left-side tolerance cannot mask right-lane corruption.

Complete audio callbacks measure **75–77 µs median (1.29–1.33% of the block
period)** and at most **81 µs** in these runs. They mostly carry held signal
values and the raw pilot; these numbers are not isolated costs of transcendental
calculations. No callback CPU screen triggers; the queue stays **151 contexts**.
Actual parameter setters/routing are timed separately, including setup overhead:

| Event operation | Total for 21 actions | Largest action |
| --- | ---: | ---: |
| `dbtoa` | 777 µs | 112 µs |
| `blackman` | 573 µs | 80 µs |
| `exp2` | 538 µs | 105 µs |
| `hamming` | 399 µs | 78 µs |
| `log2` | 389 µs | 88 µs |
| `hann` | 378 µs | 73 µs |
| `log10` | 359 µs | 82 µs |

All 44 loaded images finalise. Runtime allocation and memory checks pass in the
completed runs; all case arena high-water values are zero, with image/context
storage accounted separately. The first 20,480-byte checksum call retains
**288 internal bytes before the measurement baseline**, followed by zero further
logging/hash retention in all 44 observed cases. An earlier run failed the final
runtime gate after producing 22 raw output records; those records are not used
as an accepted qualification run. The accepted first partition uses exactly
the same test plan, references, sources and limits. Only the harness observer
is settled before the baseline. Both per-module and global gates are unchanged.
The separate direct-Gen probe's earlier unexplained heap change remains open.

The normal player, saved Main and live controls are restored afterward. The
restoration receipt verifies advancing audio frames and zero runtime faults,
not a new listening comparison. Its test-result digest binds the ordered
concatenation of both target result files. The dashboard records **935/1,455
RNBO entries with scoped outcomes**, including the three new partial numerical
outcomes and earlier failures. Aliases are checked individually; Gen counts
remain separate. No optimisation saving is claimed.

Evidence: [target partition 1](../evidence/xiao-smoke-rnbo-events-math-part1.json),
[target partition 2](../evidence/xiao-smoke-rnbo-events-math-part2.json),
[native preflight](../evidence/rnbo-events-math-native.json),
[setup/failure/observer ledger](../evidence/rnbo-events-math-attempts.json),
and [player restoration](../evidence/xiao-smoke-rnbo-events-math-player-restoration.json).
