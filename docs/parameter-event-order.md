# Preserve authored parameter-event order

The benchmark compiler now groups events by block while preserving their
authored order within each block. The recorded policy is
`stable-block-source-order-v1`. Initial parameter-map entries retain their
authored insertion order and precede explicit events at block zero. Parameter
IDs still resolve to the exported descriptor indices; index values do not
determine delivery order.

This matters when a setter changes the state consumed by a following setter.
For example, the authored line fixture can set `milliseconds=0` and then
`target=1`. Its schema gives `target` index 0 and `milliseconds` index 1.
Sorting the commands by index reverses that authored sequence and supplies the
target using the earlier duration. Intentionally setting the target first must
also remain possible.

The [sealed native evidence](../evidence/parameter-event-order.json) checks five
actual RNBO cases using the static wrapper and the parameter dispatcher. Each
case renders 33 vectors of 256 stereo frames at 44,100 Hz, after four warmup
vectors with seed `0x12345678`.

| Case | Authored/generated float and PCM | Old index sort changes output |
|---|---|---|
| Zero duration before target | Exact | Yes |
| Five milliseconds before target | Exact | Yes |
| Target intentionally first | Exact | No |
| Changed duration at the next block | Exact | Yes |
| Source events listed in unsorted block order | Exact | Yes |

All **84,480 channel sample words** and corresponding PCM bytes match between
the authored commands and the generated table. The old index sort changes both
float and PCM output in four cases. The deliberately reversed case verifies
that preservation follows the authored sequence rather than imposing a
preferred parameter order. Every native render reports finite output, zero
errors and zero late RNBO platform allocations.

A separate test extracts the actual C benchmark dispatcher and verifies that
it consumes the generated table in order. The recorded 62-test tools run
contains this regression, same-block ordering in both directions, stable
grouping of unsorted blocks, and initial-map/explicit-event ordering. This is
separate evidence from execution of the native RNBO graph.

The public seal binds the proof script, cases, generated policy/header, probe
source and executable, `native/probe-build.json`, **both linked static RNBO and
PCM archives**, host build report, compile commands, prepared source hashes,
and every authored/generated/old-sort float and PCM capture. The associated
Xtensa module was compiled as an input to fixture admission; this event-order
proof did not execute it on the board.

This establishes preservation of the tested authored command sequence. It
does not qualify S3 line timing, a full independent line-ramp model, long ramps,
arbitrary event graphs, or normalized-value parity between the native and
target drivers. Those remain separate checks. The C dispatcher test likewise
does not replace native or hardware validation of parameter semantics.
