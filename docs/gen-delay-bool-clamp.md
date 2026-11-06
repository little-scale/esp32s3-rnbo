# Gen Delay compilation and per-sample checks

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

Normal preparation now makes an existing boolean-to-integer conversion explicit
in two recognised RNBO 1.4.4 Gen delay reader forms. This resolves GCC's
`-Werror=bool-compare` build failure for the tested integer taps 1/3. No compiler
warning is disabled, and no numerical profile, state, buffer, scheduler or
allocator setting changes.

The generated clamp compares a positive integer tap with `reader != writer`.
That boolean already promotes to integer 0/1 in the original comparison.
`static_cast<Int>` makes the same conversion explicit. The comparison result,
evaluation count, outer maximum-delay branch and second ternary occurrence
remain unchanged. Complete-method fingerprints, primitive nonvolatile field
declarations and the runtime type-header hash guard each insertion. A byte
inverse reconstructs the original source; unknown forms remain untouched.

The two original delay graphs are prepared again from their saved originals.
Only `rnbo_source.h` changes among the 42 prepared files: two insertions for
the dual delay and one for the feedback delay. The named adaptation is recorded
in provenance. Other graphs remain byte-identical; the ordinary SDK base ELF
also matches the previous base image. No new user option or firmware feature
is required.

## XIAO rerun

Both original programs now pass **20,480 independent output checks**. Their
source graphs, inputs, numerical limits and full twenty-block reference streams
are unchanged. Zero automatic preparation warm blocks precede four checked
manual warmups and sixteen timed callbacks. State continues across 5,120 frames
per program, including 256-frame boundaries and repeated ring-buffer wraps.

| Exact authored program | Output result | Median / peak µs | Arena high-water |
| --- | --- | ---: | ---: |
| Two `Delay(16)` instances, read-before-write taps 1/3 | All 10,240 output words exact, including zero signs | 318 / 320 | 384 bytes |
| `Delay(16)` tap 3, feedback 0.5, copied right input | Passes 2e-6; maximum error 7.450580596923828e-9, with 946 within-limit word differences | 411 / 415 | 192 bytes |

Both modules use a 4 KiB arena ceiling, preserve their original Float64 delay
storage, finalise and pass memory/allocation checks. Neither callback triggers
CPU review. These are absolute fixture timings, with no matched speedup claim.

The one-sample result validates per-sample delay semantics inside the current
fixed-256 production callback. It does not expose a one-frame host API or
qualify visual Gen import, standalone `delay`/`read`/`write` operators, arbitrary
delay configurations or other interpolation modes. The feedback pilot uses
the common 2e-6 comparison; it has no separate raw-bit observer gate.

The [original compile failures and phase/pulse mismatches](../evidence/xiao-smoke-gen-state-boundaries.json)
remain unchanged. This [marked two-program rerun](../evidence/xiao-smoke-gen-delay-boolcast.json)
adds successful evidence for the repaired declaration/method route; it does
not replace the original eight-program record. See also
[the source transformation and compiled identities](../evidence/gen-delay-bool-clamp.json).
