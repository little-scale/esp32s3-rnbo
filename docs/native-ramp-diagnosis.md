# Native ramp fault diagnosis

The 6 November checks use the actual Max 9.1.4 / RNBO 1.4.4 exports of the
authored `line-ramp` and `curve-compound` fixtures. Each receives the original
22 boundary events over 20 callbacks at 44,100 Hz / 256 frames in a 1 MiB arena.
The existing independent references and tolerances are unchanged. This is a
computer diagnosis; the research candidates are not enabled in Studio or the
production wrappers.

## Event-rate `line`: a clock endpoint rounds backwards

The earlier callback-13 platform error is **Queue overflow**. The generated
event-rate `line` uses a Float32 `number nextTime` even though its start time,
duration and scheduler use binary64. In the traced failure:

| Clock value | Milliseconds |
| --- | ---: |
| Ramp start | 63.854877471923828 |
| Duration | 12 |
| Exact endpoint | 75.854877471923828 |
| Float32 endpoint actually scheduled | 75.854873657226562 |

At that scheduled instant, the ramp's completion test is still false. The next
endpoint rounds to the same instant, so processing schedules another identical
clock. Repetition consumes the queue's slots and raises the platform error.
Increasing the queue capacity would postpone this loop's failure.

A private candidate changes only this function's `nextTime` local to
`MillisecondTime`. It completes all 10,240 interleaved output words with zero
late allocations or platform errors. Against the 6,656-word baseline prefix,
88 words differ by at most **1.1920928955078125e-7**. The independent timeline
reference still has 4,625 outside-tolerance words, maximum error **5.613509**;
the original partial run already had 3,072 such words with the same maximum.
Completing the run therefore does not establish timeline parity. A matched
Max-side timing reference and longer-duration/retrigger checks remain necessary
before adopting a production precision adaptation.

This finding concerns the event object **`line`**. The previous handover prose
incorrectly labelled this fixture `line~`; it does not establish a new result
for signal-rate `line~`.

## Compound `curve~`: inline list capacity is exceeded

Event 13, before callback 10, grows the generated active-ramp list beyond the
wrapper's 16 inline elements. The recorded request is a **32-byte RNBO platform
allocation**, with a traced call path through list `push` and `curve_01_dest_set`.
The wrapper deliberately faults on allocation after preparation.

A private 32-element inline-list candidate completes all 10,240 words without
late allocation or platform errors. It preserves the entire 5,120-word baseline
prefix bit-for-bit. All output remains within the original **3e-5** tolerance;
maximum error is **2.86102294921875e-6**. Host context size increases from
15,336 to 15,720 bytes (**384 bytes**); target layout and CPU costs are unmeasured.

This candidate changes the capacity of every list in that compiled wrapper.
Larger messages or more same-block retriggers can still exceed a fixed reserve.
Production needs an explicit reservation policy and tested bounds for those
cases. Runtime allocation checks remain enforced.

## Reproduce and inspect

Prepare the native Max exports of the two source fixtures as baseline Float32
FX modules, then supply those trusted preparations to:

```sh
python3 tools/diagnose_native_ramps.py \
  --line build/research/max-export-parity-v3/prepared/max/line-ramp \
  --curve build/research/max-export-parity-v3/prepared/max/curve-compound \
  --out build/research/native-ramp-diagnosis-repeat
```

The destination must be new. The tool copies each preparation, applies each
research change only to its private copy, and records complete/partial capture
lengths, errors, allocation faults, context sizes, reference differences, prefix
differences and source hashes. Generated code stays in the ignored build tree.
The [frozen receipt](../evidence/native-ramp-diagnosis.json) records this run.
Neither candidate has a hardware or CPU-improvement qualification.
