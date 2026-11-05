# RNBO codebox phase, ramps, transitions and pitch members

All **36 original sources compile and execute on XIAO: 28 pass, eight retain
comparison mismatches**, across **368,640 output-word checks**. There are 52,125
outside-limit differences, no within-limit differences and no signed-zero
differences. Passing checks are bit-exact for these bounded vectors. This is
short functional qualification of exact programs, not every domain or API.

Two fixed 18-source partitions use strict Float32 modules with unchanged runtime
and storage, a 2 MiB arena ceiling and zero automatic preparation callbacks.
Four checked manual warmups precede sixteen timed callbacks. Every one of the
twenty 256-frame blocks is compared as a continuous stream; references do not
reset at block boundaries. Lossless pools of 140/122 unique reference blocks
reconstruct the same full streams. All images finalise, heap free space is
unchanged, and no host/late allocation or nonfinite-output gate fails.

## Original contracts and domains

- Phasor uses exact dyadic increments with 512/1024-sample periods. The primary
  policy observes current/pre-increment phase in [0,1), including positive and
  negative frequencies, explicit .reset and a separate reset-input source.
- Train uses 512/1024-sample intervals, widths 1/4 and 1/2, and pulse phases 0
  and 1/4; independent modular phase inequalities define its expected gates.
- Rampsmooth and bline primary references use 8/16-step linear trajectories,
  first output after the first increment. Targets change on 1021/1031-sample
  schedules. Bline observes tuple output 0 only; its .set source uses ±1/2.
- Default gatetotrig detects binary rising edges. The edge=1 primary policy
  expects falling detection one sample later, following the public reference;
  the actual same-sample observation remains a mismatch. On/off alternates per
  authored .next call, which is inside the sample loop here.
- Threshold checks exercise low/high equality boundaries and hysteresis held
  across callbacks; the separate equal-threshold form tests x>=1/2.
- Switch-and-ramp uses 8/16-sample ramps, correction from the last-input
  difference on trigger and ideal linear decay. Triggers repeat every 73/91
  samples; explicit reset schedules are independent between instances.
- Pitch members use only seven octave positions around MIDI 69 and tuning
  440/432 Hz. Mtof's limit is 5e-4 Hz; ftom's is 2e-5 MIDI notes. Fractional
  pitches, nonpositive frequencies, tuning changes and other options are not
  qualified. Default storage, including the mtof table, is preserved.
- Ease/easexfade use only linear curve 0 with syncupdate zero. Xfademul uses
  explicit numeric channel-position/clip/linear options and channels 0/1.
  Those numeric enum forms do not qualify string enum spellings or other modes.

Other checks have zero numeric tolerance except the three linear-map classes,
which predeclare 2e-6. All limits and histories were frozen before outputs.
Reset actions occur at 255/256 and 511/512 plus 257/263-sample schedules including
adjacent calls. Zero-history reset, input-reset ordering and finite bline ramp
ordering are explicit policies where documentation is terse; disagreement does
not establish an operator defect.

## Results

| Exact original source | Target status | Median µs | Peak µs | Outside-limit words | Maximum error |
| --- | --- | ---: | ---: | ---: | ---: |
| `phasor-next` | output_mismatch | 89.5 | 90 | 13 | 1 |
| `phasor-reset` | pass | 176 | 181 | 0 | 0 |
| `train-next` | pass | 97 | 99 | 0 | 0 |
| `train-reset` | pass | 188 | 193 | 0 | 0 |
| `rampsmooth-next` | pass | 190.5 | 198 | 0 | 0 |
| `rampsmooth-reset` | pass | 282.5 | 290 | 0 | 0 |
| `gatetotrig-next` | pass | 68 | 72 | 0 | 0 |
| `gatetotrig-reset` | pass | 149 | 154 | 0 | 0 |
| `onoff-next` | pass | 58 | 63 | 0 | 0 |
| `onoff-reset` | pass | 143 | 148 | 0 | 0 |
| `thresh-next` | pass | 68 | 72 | 0 | 0 |
| `thresh-reset` | pass | 164 | 169 | 0 | 0 |
| `mtof-next` | pass | 2661 | 2661 | 0 | 0 |
| `mtof-reset` | pass | 2757 | 2759 | 0 | 0 |
| `ftom-next` | pass | 1027 | 1028 | 0 | 0 |
| `ftom-reset` | pass | 1128 | 1133 | 0 | 0 |
| `ease-next` | pass | 308 | 312 | 0 | 0 |
| `ease-reset` | pass | 438.5 | 439 | 0 | 0 |
| `easexfade-next` | pass | 627 | 628 | 0 | 0 |
| `easexfade-reset` | pass | 737 | 738 | 0 | 0 |
| `xfademul-next` | pass | 111 | 115 | 0 | 0 |
| `xfademul-reset` | pass | 111 | 115 | 0 | 0 |
| `bline-next` | output_mismatch | 169 | 180 | 10238 | 0.534110978 |
| `bline-reset` | output_mismatch | 169.5 | 181 | 10238 | 0.937491775 |
| `swanramp-next` | pass | 129 | 134 | 0 | 0 |
| `swanramp-reset` | pass | 222 | 227 | 0 | 0 |
| `phasor-negative` | pass | 89 | 90 | 0 | 0 |
| `phasor-input-reset` | output_mismatch | 93 | 97 | 10112 | 0.969726562 |
| `gatetotrig-falling` | output_mismatch | 68 | 72 | 1119 | 1 |
| `thresh-equal` | pass | 68.5 | 74 | 0 | 0 |
| `bline-set` | output_mismatch | 264.5 | 275 | 10154 | 0.534110978 |
| `phasor-constructor` | output_mismatch | 89 | 90 | 13 | 1 |
| `train-constructor` | pass | 96.5 | 102 | 0 | 0 |
| `onoff-constructor` | pass | 58 | 63 | 0 | 0 |
| `bline-constructor` | output_mismatch | 169.5 | 180 | 10238 | 0.534110978 |
| `swanramp-constructor` | pass | 129 | 134 | 0 | 0 |

## Retained mismatch witnesses

Positive phasor next/constructor each retain 13 differences at exact wraps,
maximum 1: at frame 512 the left output is 1 rather than the declared 0, followed
by the expected 1/512 at frame 513. Explicit method reset and negative-frequency
programs pass their separate references. The input-reset source retains 10,112
differences; at frame 37 its left output continues at 37/512 rather than resetting
to zero. This is specific to the authored option/argument/context, not a verdict
on every phasor reset form.

The falling-edge source has 1,119 differences, maximum 1. For example its right
trigger is at frame 38, while the predeclared delayed policy expects frame 39.
Default rising-edge next/reset sources pass. See the [gatetotrig reference](https://rnbo.cycling74.com/codebox/ref/gatetotrig)
for the documented negative-edge delay that motivated the primary expectation.

Bline next/constructor/reset each retain 10,238 differences; .set has 10,154.
The default first two left outputs are 0.125 and 0.234375, versus the original
linear model's 0.125 and 0.25. The output gradually approaches the target; the
reset source does not show the assumed zero-history restart. The public
[bline reference](https://rnbo.cycling74.com/codebox/ref/bline) is terse about its
trajectory/reset details, so this remains a policy comparison, not a claimed
producer defect. No alternative recurrence is fitted into the primary oracle.

[`capture_witnesses.py`](capture_witnesses.py) reuses the previously published
native SDK word-capture helper. It saves selected actual/expected native samples
and full-capture hashes for six diagnostic sources. That is secondary native
evidence, not actual Max or a full target-output capture. Native comparison
counts/max errors agree with device observations for all 36 programs.

## CPU, memory and coverage

Six complete callback scenarios trigger the median-budget rule; none triggers
the peak-spike rule. The CPU queue increases from 136 to **142**. Mtof next/reset
measure 2,661/2,757 µs median, ftom 1,027/1,128 µs, and easexfade 627/737 µs.
These strict-profile timings include two instances and test logic, without
I²S/UI/network work; they are not isolated operation costs or optimisation
gains. Reviewed patcher optimisations do not qualify these codebox members.

Mtof observes **262,256 bytes arena high-water** in each case; all other programs
observe zero. All reserve the declared 2 MiB ceiling during their own lifecycle;
reserved capacity and observed use are different measurements. No storage or
precision optimisation is applied by this batch.

There are **32 new exact RNBO rows**, taking the dashboard to **869 scoped
entries**. Repeated scenarios bind to the same exact member row, retaining all
outcomes. Five separate constructor programs bind owner rows explicitly; member
passes do not automatically qualify constructors, aliases or other APIs. No Gen
or patcher status is inherited. Gen visual forms, event/resource/mode cases,
one-frame calls and remaining RNBO qualification are still incomplete.

The normal player and saved Main/controls are restored, with USB frame progress
and zero runtime counters verified. No new DAC capture is claimed.

- [Target part 1](../../../../evidence/xiao-smoke-rnbo-codebox-motion-members-part1.json)
- [Target part 2](../../../../evidence/xiao-smoke-rnbo-codebox-motion-members-part2.json)
- [Native preflight and selected sample witnesses](../../../../evidence/rnbo-codebox-motion-members-native.json)
- [Player restoration](../../../../evidence/xiao-motion-members-player-restoration.json)

Run `python3 generate.py --check` to verify original fixture reproducibility.
Licensed RNBO exports/toolchains and hardware are also required to reproduce
compilation/device execution. These public fixtures contain original source
programs and independent references, without licensed generated implementations.
