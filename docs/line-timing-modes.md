# Line timing, cancellation and precision observations

Computer-side checks expose three limitations in the current strict RNBO 1.4.4
`line-timing` Main graph: absolute Float32 ramp timestamps change output as the
sample counter grows, repeated commands can allocate during event delivery,
and a tiny positive duration followed by an immediate replacement can fault.
No new board execution or target performance improvement is claimed.

The authored graph sends `[target, milliseconds]` through `pack` into `line~`.
Target is the hot inlet: every target command emits a ramp, including a repeated
value. Milliseconds is the cold inlet: changing it alone does not interrupt an
active ramp. Authored order matters when both change at one block boundary.
The separate right output observes the current target. These conclusions
combine the pinned generator's actual callers with the primary
[line~ reference](https://rnbo.cycling74.com/objects/ref/line~?v=1.4.4) and pack
contract; they do not qualify arbitrary line lists or within-block external events.

## Expanded native checks

The 43 ordered programs use the actual dynamic C ABI, normal runtime fixes,
44,100 Hz and 256-frame vectors. They cover the five original cases, fractional
durations around sample/vector boundaries, zero and tiny positive durations,
cold duration changes, target replacements, repeated targets, opposite orders
at the same block, cancellation bursts, cold/warm startup and reconstruction.
Silent prefixes advance every vector through the ABI; there is no injected
state or jump to a future sample position. Prefix audio is checked for health
but is not persisted or counted as compared tail output.
The prefix's zero output follows from the default zero target and source state;
the recorded prefix guard counts nonfinite samples, rather than checking every
word for zero. No measured prefix-silence metric is claimed.

The O3 and UBSan builds produce identical Float32, PCM, event/readback traces
and statistics, including the same two faulting programs. Each build captures
3,569,664 channel words. Compiler agreement preserves the observed behaviour;
it does not establish mathematical correctness or target behaviour. Native
constructor/finalizer stubs do not establish ELF loader lifecycle coverage.

The five original catalogue gates still pass unchanged. A separate piecewise
linear oracle uses exact integer event times, relative segment ages and
independently rounded rational durations. Its reviewed discrete convention
holds the old value at the command's first sample and expires after
`ceil(duration)`; that convention is not asserted as a discrete-timing quote
from the object documentation. Target output words are checked separately.
The additional fixed `2e-5` ideal-amplitude observation and one-sample output
settling allowance are never widened to fit the data. Of 41 complete programs,
27 pass that additional observation; two other programs stop after ABI faults.
Some early long-ramp failures are Float32 accumulation/ideal-accuracy
observations, separate from the unequivocal age-translation and allocation
failures below. Output settling is not an internal completion-clock oracle.

## Preserved failures

Ten programs compare an identical event schedule after a silent prefix against
its early counterpart. Every pair exceeds the original `2e-6` comparison
limit. The earliest tested master prefix near `2^23` samples differs by about
0.002652 in one channel word; later cases reach a maximum difference of 1.5.
All startup words remain in the compared captured tails. Prefix processing is
accelerated native execution, rather than a claim about a live instrument's
wall-clock uptime.

The source stores ramp ends in Float32 list entries even though the underlying
sample counter is UInt64. Fractional end positions can round across a sample
boundary before integer sample resolution is lost. Above `2^24` samples
(about 380 seconds), Float32 spacing is two samples; above `2^27` it is sixteen.
Keeping the engine clock in Double does not protect those separate list entries.

The same-block cancellation burst triggers a late Platform allocation of
48 bytes. The running-allocation guard correctly faults the module. Increasing
the arena would not remove this policy violation: replacement storage must be
bounded or reserved before running. The cold tiny-duration replacement reports
one invalid sample and a process fault; the wrapper silences output. Its warm
counterpart completes but does not satisfy the independent ideal observation.
All controls are finite and inside the authored parameter ranges.

## What this means for precision and optimisation

The linked ESP32-S3 sample loop already uses hardware Float32 arithmetic.
Widening every audio value would address neither event storage growth nor the
need to distinguish audio samples from timestamps. The useful comparison is
Double end timestamps versus UInt64 anchors with short relative durations,
while keeping Float32 audio values. Both require a separate bounded replacement
state design and tiny-duration policy. No such adapter is admitted by this record.

The existing event-side Double millisecond conversion is retained. A direct
two-Float32-multiplication replacement changes 10 ms from 441 samples to
441.0000305, changing its ceiling to 442. An independent rational rounding proof
and stratified checks qualify the existing conversion over this graph's
0..100 ms domain; they do not expand the separate public 40 ms delay helper.

The actual strict Xtensa module compiles with zero imports and a 46,892-byte
ELF. Its target DWARF context is 14,048 bytes; the chosen arena descriptor is
4,096 bytes. These are compiled layout/structural facts, not measured target
heap high-water or a healthy resource envelope for the failing programs.

The [sealed evidence](../evidence/line-timing-modes.json) binds native captures,
traces, retained faults, independent oracle/review, duration proof and linked
precision audit. `line~` remains partially qualified. New fixes must preserve
the original gates, pass the expanded observations and be measured separately
on target before claiming a CPU improvement.
