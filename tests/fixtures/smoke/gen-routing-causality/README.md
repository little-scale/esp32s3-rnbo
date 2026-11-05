# Gen routing forms and causal state structures

26 original sources: **15 compile/execute on XIAO and all 15 pass**, ten routing
function forms fail C++ compilation, and the final-if conditional-history source
fails the Gen frontend. There are **153,600 output-word checks**, zero
outside-limit, 8,610 within-limit and zero signed-zero differences. Eleven
programs are bit-exact; four convolution-based programs differ within their
predeclared 2e-6 limits, maximum 1.1920928955078125e-7.

All successful programs use strict Float32 modules, unchanged runtime/storage,
a 4 KiB arena and zero automatic preparation calls. Four checked manual warmups
precede sixteen timed 256-frame calls. All twenty streams remain continuous,
covering 5,120 frames per source. Every image finalises, all memory/allocation
gates pass, free heaps are unchanged and arena high-water is zero. This checks
per-sample state inside fixed blocks, not a one-frame production module ABI.

## Source contracts

All references were frozen before output. They use direct input delays, the
most recent qualifying update index, closed state permutations or finite impulse
convolutions, independently of generated runtime algorithms. Coupled state uses
A=[[0,1/2],[1/4,0]], so A²=I/8; its pre-update state is the sum of A-power input
impulses and the decaying declared initial condition. At most64 terms leave a
tail below 2^-90 for the supplied bounded inputs. Scalar feedback uses gain1/4,
function-local histories use gain1/2, and the three-iteration local loop has
combined history gain1/8 and input gain7/32. Their finite convolution tails are
below the fixed 2e-6 comparison limit. Output rounding differences remain explicit.

Three-stage history startup seeds and n-3 outputs cross every host boundary.
Fanout and repeated reads observe the same old history value before one update.
The explicit three-state rotation has period3, so restarting each256 samples
changes the expected stream. The separately authored imperative rotation uses
its declared sequential read/write hypothesis; it passes here without inheriting
that outcome to every ordering. Internal reset-before-read and final write,
conditional hold/update, and257/263-sample impulses have their own source IDs.
These program-level actions do not establish host reset events or external
sample-offset scheduling.

## Results

| Original source | Outcome | Median µs | Peak µs | Within-limit words |
| --- | --- | ---: | ---: | ---: |
| `in-call` | C++ rejection | — | — | — |
| `out-call` | C++ rejection | — | — | — |
| `gen-call` | C++ rejection | — | — | — |
| `expr-call` | C++ rejection | — | — | — |
| `send-call` | C++ rejection | — | — | — |
| `s-call` | C++ rejection | — | — | — |
| `receive-call` | C++ rejection | — | — | — |
| `r-call` | C++ rejection | — | — | — |
| `setparam-symbol` | C++ rejection | — | — | — |
| `setparam-name` | C++ rejection | — | — | — |
| `lexical-ports` | pass | 42 | 43 | 0 |
| `local-variable-copy` | pass | 42 | 43 | 0 |
| `history-chain3` | pass | 54 | 59 | 0 |
| `history-fanout` | pass | 50 | 50 | 0 |
| `history-cross-feedback` | pass | 524 | 526 | 3189 |
| `history-read-twice` | pass | 45 | 49 | 0 |
| `history-conditional-update` | frontend rejection | — | — | — |
| `history-impulse-age` | pass | 109 | 113 | 0 |
| `history-reset-before-read` | pass | 47 | 47 | 0 |
| `history-rotate-temporaries` | pass | 54 | 58 | 0 |
| `history-rotate-imperative` | pass | 53 | 57 | 0 |
| `history-feedback-convolution` | pass | 512 | 512 | 1276 |
| `function-history-independent` | pass | 516.5 | 519 | 3506 |
| `loop-history-feedback` | pass | 742.5 | 743 | 639 |
| `history-conditional-tail` | pass | 45 | 45 | 0 |
| `history-conditional-ternary` | pass | 45 | 49 | 0 |

## Rejected routes remain separate

The ten function sources cover exact in/out/gen/expr/send/s/receive/r spellings
and two setparam call forms. They are exploratory closed GenExpr routes for
registry entries primarily described as graph/patcher forms. Registry membership
is not a callable-function API promise. These C++ failures do not reject visual
send/receive, subpatchers or parent-to-child parameter control, and have no
hardware timing/output observations. In particular the paired send/receive
sources do not isolate which helper would work in another context. See the
[send](https://docs.cycling74.com/reference/gen_common_send/),
[receive](https://docs.cycling74.com/reference/gen_common_receive/) and
[setparam](https://docs.cycling74.com/reference/gen_common_setparam/) references
for the documented graph scope.

The original conditional source ends in an if block and is rejected by the
frontend. A separately retained source with out2 assigned after that block,
and a separate ternary update source, both compile and pass the same
last-qualifying-update reference. The original failed source/hash/log remain
unchanged; neither valid form erases that rejection. This is a source/grammar
boundary observation, not a general conditional-history failure.

## Performance and remaining coverage

The loop-feedback program measures742.5µs median /743µs peak, **12.79%** of the
block period, adding one median-budget flag and bringing the global queue to
**143**. No peak-spike rule triggers. Other callback medians range42–524µs.
These are whole authored offline callbacks, including loop/test logic and all
outputs, without I²S/UI/network work. No optimisation or measured gain is claimed.

The new [registry source-route ledger](../../../../docs/gen-registry-routes.md)
contains source scenarios for 212/212 RNBO 1.4.4 GenExpr registry entries. That is
source-route coverage, not 212 hardware passes, mode/domain coverage, visual Gen
or one-frame target-call qualification. Short-smoke observations are matched by
exact case/source identities; separate long qualification evidence stays separate.
This Gen batch adds no rows to the 869-entry RNBO dashboard.

The normal player, saved Main and live controls are restored; USB frame progress
and zero runtime fault counters are checked. No new DAC or actual Max capture
is claimed.

- [Target results](../../../../evidence/xiao-smoke-gen-routing-causality.json)
- [Native preflight and retained rejections](../../../../evidence/gen-routing-causality-native.json)
- [Normal-player restoration](../../../../evidence/xiao-gen-routing-causality-player-restoration.json)

Run `python3 generate.py --check` to verify original sources/catalogs. Licensed
RNBO frontend/toolchain and XIAO hardware are also needed to reproduce device
execution. Public sources contain no licensed generated implementation.
