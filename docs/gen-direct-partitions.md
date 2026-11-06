# Direct Gen one-sample and partition checks on XIAO

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

**All 78 hardware renders pass** for three exact original GenExpr programs:
zero-initialised feedback, two histories initially 1/2 that swap using explicit
old-state temporaries, and three histories initially 1/2/3 that rotate. Both a
seven-sample dyadic stimulus and sparse boundary impulses run through each graph.

This is a dedicated **direct variable-frame producer** application using the
original licensed RNBO 1.4.4 runtime, Float32 samples and Double scheduler time.
The qualification exporter requests fixedblocksize=0; the public player's
export/prepare/module ABI remains fixed at 256. These results do not make arbitrary
player packages accept one-frame calls, or qualify other Gen/visual/resource APIs.

## What is compared

Each program/stimulus runs one initial 1-frame baseline plus two independently
constructed repeats of nominal 1/2/7/255/256-frame and mixed partitions. The mixed
pattern is 1,2,7,255,256,3,17. Every instance processes 4,096 frames, with no hidden
automatic warmup. Calls shorten at the end or to reach the same absolute control
samples; nominal 256 therefore includes 13 full 256 calls and six shorter calls,
not a pure uniform 256-frame timing benchmark.

- Reset goes through the actual authored RNBO param reset → set reset → Gen
  initializer route before samples 513,1024,2051,3001. Values remain 1 for repeated
  identical retriggers. Readback and 312 action invocations are checked.
- Forced prepareToProcess(44100,256,true) runs before samples 257 and1300, for 156
  total calls. Expected state continues through those prepares.
- Four guarded input/output planes check both outer bounds and all inactive
  slots after every call. All 638,976 input words retain their original bits.
- Independent expected streams check 638,976 output words. Subsequent renders
  also compare 589,824 output words bit for bit against the same-device 1-frame
  baseline. All 78 full-capture hashes additionally agree with host captures.
- A nonzero impulse appears at every interior 256-frame boundary and its two
  neighbours. The three-state period does not divide 256, exposing false
  block-boundary reconstruction.

The feedback oracle is a 64-term input convolution, not a copy of the recursive
producer update; its omitted tail is below 2^-64. The fixed 2e-6 feedback limit is
unchanged from the prior history qualification. Swap/rotation require numeric
equality. Startup values, reset epochs and current/old-history observation are
explicitly declared. The complete input/reference cache SHA-256 hashes are
recomputed on-device before execution and matched by the collector.

Reset witnesses distinguish actions from observable state changes: **234 of 312
reset actions have independent output separation greater than four times the
limit**. Other reset positions can coincide with the same phase or negligible
history and supply no individual reset proof. All actions are counted, but those
invisible events are not promoted into extra semantic evidence. Prepare/state
continuity is assessed over the supplied full traces, not every possible graph.

## Results and limits

| Check | Observed result |
| --- | ---: |
| Constructed and destroyed instances |78 /78 |
| Process calls with input/output guards |106,536 |
| Independent numerical output checks |638,976 |
| Outside-limit differences |0 |
| Within-limit differences |62,036 |
| Largest absolute feedback error |7.450580596923828e-9 |
| Partition bit differences |0 /589,824 |
| Native/device identical full-capture hashes |78 /78 |
| Processing heap allocations /frees |0 /0 |
| Observed reset/prepare heap allocations /frees |0 /0 |
| PSRAM free before /after |8,320,764 /8,320,764 bytes |
| Internal free before /after |326,027 /325,739 bytes |

The partition equivalence is bit-exact; the independent ideal feedback comparison
has the 62,036 retained within-limit differences. These are different assertions.
The standalone application is quiet and does not run I²S, display or networking.
It does not establish per-sample I²S scheduling deadlines, actual Max/DAC output,
all history algorithms, arbitrary feedback gains, nonfinite domains or visual Gen.

**Memory follow-up:** internal free memory ends 288 bytes lower across 78
constructions/destructions. First-use/lifecycle retention has not been isolated.
The task heap observer brackets process and the actual set/prepare methods;
constructor/destructor allocations are outside those brackets. No claim of
unchanged total heaps or a module-arena high-water measurement is made.

## Direct-route CPU costs

The core is pinned to CPU0 at 240MHz. Elapsed cycle brackets enclose process,
including counter-wrapper cost and possible interrupts/preemption. Input filling,
reference comparisons, guard scans, control actions and capture hashing are
outside the process timer. A main-translation-unit empty read pair measures 1
cycle; it does not remove cross-unit wrapper overhead, and **no overhead is
subtracted**. This statically linked direct producer has different dispatch/linking
from a dynamically loaded player module; its costs are not player CPU predictions.

CPU%=elapsed process cycles / (4,096 frames ×240MHz /44,100Hz) ×100.
The table uses the median of two full render ratios for each nominal partition,
or three for nominal 1 including the baseline. It is a short budget screen, not
an isolated opcode benchmark or matched optimisation comparison.

| Program | Stimulus | Nominal frames | Renders | Median CPU | Largest call µs | Budget review |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `history-feedback` | dyadic | 1 | 3 | 20.22% | 48.14 | yes |
| `history-feedback` | dyadic | 2 | 2 | 13.26% | 11.90 | yes |
| `history-feedback` | dyadic | 7 | 2 | 8.26% | 18.93 | no |
| `history-feedback` | dyadic | 255 | 2 | 6.30% | 367.43 | no |
| `history-feedback` | dyadic | 256 | 2 | 6.27% | 368.99 | no |
| `history-feedback` | dyadic | mixed | 2 | 6.41% | 365.62 | no |
| `history-feedback` | boundary-impulses | 1 | 3 | 19.12% | 10.59 | yes |
| `history-feedback` | boundary-impulses | 2 | 2 | 12.14% | 11.92 | yes |
| `history-feedback` | boundary-impulses | 7 | 2 | 7.14% | 18.27 | no |
| `history-feedback` | boundary-impulses | 255 | 2 | 5.20% | 306.51 | no |
| `history-feedback` | boundary-impulses | 256 | 2 | 5.18% | 307.60 | no |
| `history-feedback` | boundary-impulses | mixed | 2 | 5.30% | 300.91 | no |
| `two-history-swap` | dyadic | 1 | 3 | 14.16% | 43.22 | yes |
| `two-history-swap` | dyadic | 2 | 2 | 7.34% | 10.83 | no |
| `two-history-swap` | dyadic | 7 | 2 | 2.48% | 10.26 | no |
| `two-history-swap` | dyadic | 255 | 2 | 0.59% | 39.35 | no |
| `two-history-swap` | dyadic | 256 | 2 | 0.59% | 38.27 | no |
| `two-history-swap` | dyadic | mixed | 2 | 0.70% | 33.02 | no |
| `two-history-swap` | boundary-impulses | 1 | 3 | 14.15% | 10.72 | yes |
| `two-history-swap` | boundary-impulses | 2 | 2 | 7.33% | 9.70 | no |
| `two-history-swap` | boundary-impulses | 7 | 2 | 2.48% | 11.39 | no |
| `two-history-swap` | boundary-impulses | 255 | 2 | 0.59% | 38.16 | no |
| `two-history-swap` | boundary-impulses | 256 | 2 | 0.58% | 39.50 | no |
| `two-history-swap` | boundary-impulses | mixed | 2 | 0.70% | 31.95 | no |
| `three-history-rotation` | dyadic | 1 | 3 | 14.22% | 44.83 | yes |
| `three-history-rotation` | dyadic | 2 | 2 | 7.42% | 10.32 | no |
| `three-history-rotation` | dyadic | 7 | 2 | 2.54% | 11.68 | no |
| `three-history-rotation` | dyadic | 255 | 2 | 0.64% | 41.46 | no |
| `three-history-rotation` | dyadic | 256 | 2 | 0.64% | 41.50 | no |
| `three-history-rotation` | dyadic | mixed | 2 | 0.75% | 36.23 | no |
| `three-history-rotation` | boundary-impulses | 1 | 3 | 14.23% | 9.62 | yes |
| `three-history-rotation` | boundary-impulses | 2 | 2 | 7.43% | 9.74 | no |
| `three-history-rotation` | boundary-impulses | 7 | 2 | 2.53% | 10.37 | no |
| `three-history-rotation` | boundary-impulses | 255 | 2 | 0.64% | 41.38 | no |
| `three-history-rotation` | boundary-impulses | 256 | 2 | 0.63% | 41.58 | no |
| `three-history-rotation` | boundary-impulses | mixed | 2 | 0.75% | 35.16 | no |

Eight nominal 1/2 contexts exceed the 10% aggregate budget screen, taking the
review queue from 143 to **151**. Per-call dispatch cost is expected to matter
for short partitions; these flags do not prove an expensive Gen opcode or a
required DSP rewrite. Mixed-length peak maxima are not classified as isolated
spikes because their call sizes differ. No CPU-saving percentage is claimed.

## Reproduction and provenance

The original graph/code files stay in tests/fixtures/gen. The new
[closed catalog and reference](../tests/fixtures/gen/partitions/catalog.json)
are generated/checked by
[generate.py](../tests/fixtures/gen/partitions/generate.py). The separate
[qualification exporter](../tools/export_gen_partition_probe.mjs) writes only a
fresh private build directory, uses the licensed frontend and records unique
class/source/runtime identities. It cannot create a player package. The
[builder](../tools/build_gen_partition_probe.py) runs the same harness on the
host first, then builds the standalone target; the
[collector](../tools/collect_gen_partition_probe.py) independently reconstructs
all call histograms, controls, reference caches, numerical counts and hashes.

Integration attempts before the recorded hardware cohort stopped at harness
formatter/configuration checks. The frozen graph/export/reference/partition plan
remained identical; those stops are not DSP object failures. Their
[log fingerprints](../evidence/gen-direct-partitions-build-stops.json) remain
separate from the successful target run.

- [Hardware results, full per-render counters and timings](../evidence/xiao-gen-direct-partitions.json)
- [Native capture verification](../evidence/gen-direct-partitions-native.json)
- [Normal-player restoration](../evidence/xiao-gen-direct-partitions-player-restoration.json)

The same saved Main and live controls are restored after the experiment. USB
frame progress and zero player fault counters are checked. The RNBO dashboard
stays 869 scoped entries, and the 212-entry Gen source-route ledger is not changed
into a claim that every Gen operation supports one-frame target processing.
The full RNBO/Gen qualification goal remains incomplete.
