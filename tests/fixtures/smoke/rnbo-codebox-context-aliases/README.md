# RNBO codebox context, units and exact aliases

51 original sources in two frozen 26/25-source partitions: **43 execute on XIAO,
40 pass their declared checks, three retain clock comparison mismatches and eight
are rejected by the frontend**. All 440,320 output words are checked. There are
15,300 outside-limit differences, 16,005 within-limit differences and 7,680
signed-zero differences; this batch is not universally bit-exact.

These are strict Float32 modules with original storage/runtime algorithms,
4 KiB arenas and zero automatic preparation callbacks. Four checked manual
warmups precede sixteen timed 256-frame callbacks at 44,100 Hz. All twenty
blocks form one uninterrupted reference stream: state is not reset between
callbacks. Prefix sums and parity witnesses span multiple blocks. Every loaded
image finalises; all allocation/memory gates pass and arena high-water is zero.
The complete callback includes both outputs and source logic. No DSP
optimisation, isolated operation cost or speed increase is claimed.

## Independent contracts and limits

Arithmetic uses signed dyadic input pairs in both operand orders; reverse
operators use exact rational arithmetic. Constructor aliases use two state
instances with reset held zero. The two lexical compound-assignment programs
are auxiliary language checks, not qualification of `new +=()` or `new *=()`.
Those symbolic constructors are frontend rejections. Exact infix `==p`, `!=p`,
`!-`, `!/`, `!%` and `^^` are also rejected. Other forms remain unqualified.

Fresh context is explicitly stopped, 120 BPM, 4/4, 480 ticks per quarter note.
Voice and voiceindex are checked only outside polyphony (zero); MC queries
check only a finite nonnegative integer in 0..64 in a non-MC patch. The latter
are execution screens, not exact multichannel channel/count semantics. Changed
tempo/meter, transport/MIDI clock events and polyphony remain untested.

Conversions use independent Fraction ratios with positive 1/8..2 input pairs,
including both operand positions. Limits are unit-aware and frozen before
native or target output. Zero output fails every conversion domain by more than
100 times its limit. Clock expectations, including callback-origin samplecount
and per-sample currenttime/sampleoffset/currentsampletime, are also predeclared.
Per-case limits and results appear below; a zero limit means numeric equality,
with signed-zero differences retained separately.

| Original source | Exact spelling/form | Target outcome | Absolute limit | Median µs | Peak µs |
| --- | --- | --- | ---: | ---: | ---: |
| `pass-equal-alias` | `==p` (infix) | frontend rejection | 0 | — | — |
| `pass-not-equal-alias` | `!=p` (infix) | frontend rejection | 0 | — | — |
| `pass-less-alias` | `<p` (infix) | pass | 0 | 50 | 55 |
| `pass-less-equal-alias` | `<=p` (infix) | pass | 0 | 51 | 55 |
| `pass-greater-alias` | `>p` (infix) | pass | 0 | 50 | 55 |
| `pass-greater-equal-alias` | `>=p` (infix) | pass | 0 | 51 | 51 |
| `reverse-subtract-alias` | `!-` (infix) | frontend rejection | 0 | — | — |
| `reverse-divide-alias` | `!/` (infix) | frontend rejection | 0 | — | — |
| `reverse-modulus-alias` | `!%` (infix) | frontend rejection | 0 | — | — |
| `xor-alias` | `^^` (infix) | frontend rejection | 0 | — | — |
| `ternary-alias` | `?` (infix) | pass | 0 | 49 | 53 |
| `minus` | `minus` (call) | pass | 0 | 44 | 45 |
| `plusequals` | `plusequals` (constructor-alias) | pass | 0 | 54 | 59 |
| `mulequals` | `mulequals` (constructor-alias) | pass | 0 | 52 | 52 |
| `add-alias-constructor` | `+=` (constructor-alias) | frontend rejection | 0 | — | — |
| `multiply-alias-constructor` | `*=` (constructor-alias) | frontend rejection | 0 | — | — |
| `compound-add-state` | `compound-add-state` (compound-assignment) | pass | 0 | 48 | 52 |
| `compound-multiply-state` | `compound-multiply-state` (compound-assignment) | pass | 0 | 44.5 | 45 |
| `currenttime` | `currenttime` (named-value) | output_mismatch | 2e-05 | 154 | 164 |
| `samplecount` | `samplecount` (named-value) | pass | 0 | 101 | 106 |
| `sampleoffset` | `sampleoffset` (named-value) | output_mismatch | 0 | 46 | 51 |
| `samplerate` | `samplerate` (named-value) | pass | 0 | 46.5 | 47 |
| `vectorsize` | `vectorsize` (named-value) | pass | 0 | 46 | 47 |
| `mc_channel` | `mc_channel` (named-value) | pass | 0 | 94 | 98 |
| `mc_channelcount` | `mc_channelcount` (named-value) | pass | 0 | 94 | 98 |
| `currentsampletime` | `currentsampletime` (call) | output_mismatch | 0 | 104 | 109 |
| `voice` | `voice` (call) | pass | 0 | 47 | 51 |
| `voiceindex` | `voiceindex` (call) | pass | 0 | 47 | 47 |
| `tempo` | `tempo` (call) | pass | 0 | 305 | 310 |
| `transport` | `transport` (call) | pass | 0 | 306 | 311 |
| `beattime` | `beattime` (call) | pass | 0 | 348 | 353 |
| `timesignature` | `timesignature` (call) | pass | 0 | 45 | 45 |
| `tempoatsample` | `tempoatsample` (call) | pass | 0 | 55 | 56 |
| `transportatsample` | `transportatsample` (call) | pass | 0 | 55 | 60 |
| `beattimeatsample` | `beattimeatsample` (call) | pass | 0 | 484 | 488 |
| `timesignatureatsample` | `timesignatureatsample` (call) | pass | 0 | 45 | 46 |
| `beatstohz` | `beatstohz` (call) | pass | 2e-06 | 665 | 665 |
| `beatstoms` | `beatstoms` (call) | pass | 0 | 664 | 664 |
| `beatstosamps` | `beatstosamps` (call) | pass | 0 | 676 | 677 |
| `beatstoticks` | `beatstoticks` (call) | pass | 0 | 45 | 49 |
| `hztobeats` | `hztobeats` (call) | pass | 2e-06 | 676.5 | 677 |
| `hztoticks` | `hztoticks` (call) | pass | 0.002 | 956 | 956 |
| `mstobeats` | `mstobeats` (call) | pass | 2e-09 | 2104 | 2108 |
| `mstoticks` | `mstoticks` (call) | pass | 5e-07 | 853.5 | 854 |
| `sampstobeats` | `sampstobeats` (call) | pass | 1e-10 | 748 | 749 |
| `sampstoticks` | `sampstoticks` (call) | pass | 2e-08 | 673 | 674 |
| `tickstobeats` | `tickstobeats` (call) | pass | 2e-09 | 143 | 148 |
| `tickstohz` | `tickstohz` (call) | pass | 0.002 | 855 | 855 |
| `tickstoms` | `tickstoms` (call) | pass | 1e-06 | 762 | 763 |
| `tickstosamps` | `tickstosamps` (call) | pass | 2e-05 | 762 | 763 |
| `tickstosamples` | `tickstosamples` (call) | pass | 2e-05 | 762 | 763 |

## Clock diagnosis stays separate

The primary per-sample model retains 5,100 outside-limit differences for each
of currenttime, sampleoffset and currentsampletime. Samplecount passes its
callback-origin model. A separately labelled native SDK capture agrees with a
callback-held interpretation: sampleoffset stays zero and the other two queries
report the callback origin. Its maximum differences are zero for the two sample
queries and 7.63e-6 milliseconds for currenttime, within the original 2e-5 ms
limit. This explains the mismatch without asserting a broken RNBO clock or
replacing the primary oracle. It is not an actual Max engine or full target
capture. [`clock_diagnostic.py`](clock_diagnostic.py) and
[`clock_capture.cpp`](clock_capture.cpp) retain that secondary experiment.

## Harness stop and identical-plan rerun

The initial second-partition run stopped after 15 complete cases, immediately
before processing hztoticks. The device-side harness guard still imposed 0.001,
whereas that case had already declared a 0.002 output-unit limit. This was a
harness validation stop, not an object DSP crash. Its report/log/ELF hashes are
retained in the native evidence; incomplete-run CASE lines are not promoted.

The repaired harness preserves the 0.001 default for existing families and emits
a 0.002 ceiling only for this pinned family. The successful rerun uses the same
plan, modules, source, input, references and per-case limits. Its plan hash equals
the stopped run's. No primary tolerance was loosened after observation.

Both partitions store references as lossless pools of 512-word blocks (90 and
15 unique blocks). Per-case indices reconstruct all twenty original blocks;
the collector independently verifies every value and hash against reference.py.
Pooling changes neither streams nor comparisons.

## Performance and publication

Thirteen conversion contexts trigger the median-budget review rule; none
triggers a peak-spike rule. mstobeats is highest at 2,104 µs median / 2,108 µs
peak, about 36.25% of a 5.805 ms block. The complete queue reaches **136**.
Review scalar conversion/runtime context work and Float32 arithmetic later;
keep numerical comparisons separate from speed claims.

The RNBO dashboard gains 48 exact rows, reaching **837 scoped entries**.
Existing `^^` rejection evidence is preserved and extended. Auxiliary lexical
compound assignments do not create registered object rows; passing canonical
spellings do not qualify rejected aliases. No Gen or patcher status is inherited.
The full RNBO/Gen object, mode, event, resource and one-frame-call qualification
goal remains incomplete.

The normal player, saved Main and live controls are restored after this batch.
USB frame progress and zero runtime fault counters are checked; no new DAC
output capture is claimed.

- [Target part 1](../../../../evidence/xiao-smoke-rnbo-codebox-context-aliases-part1.json)
- [Target part 2](../../../../evidence/xiao-smoke-rnbo-codebox-context-aliases-part2.json)
- [Native, clock diagnosis and stopped-harness record](../../../../evidence/rnbo-codebox-context-aliases-native.json)
- [Player restoration](../../../../evidence/xiao-context-aliases-player-restoration.json)

Reproduce original fixture checks with `python3 generate.py --check`. Licensed
RNBO exports, toolchains and actual hardware are additionally required to repeat
compilation and device execution. Public fixtures contain only original programs,
references and harness helpers, with no licensed generated implementation.
