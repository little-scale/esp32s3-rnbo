# Train reciprocal hoisting

`--hoist-train-reciprocal` is an optional compiler transformation for the
reviewed RNBO 1.4.4 `phase-pulse` Main graph at 44,100 Hz/256 frames. It keeps
`float32-strict` and requires normal runtime fixes. Other profiles and optional
transformations are rejected.

```sh
node host/export/export.mjs tests/fixtures/objects/wave2/phase-pulse.rnbopat \
  --out build/exports/train-hoist-NEW
python3 host/compiler/prepare.py \
  --export build/exports/train-hoist-NEW \
  --class-name rnbos3patch --role main --hoist-train-reciprocal \
  --out build/prepared/train-hoist-NEW
```

The train interval and width arrive by value and stay constant during a render
call. The unchanged Float32 interval clamp and reciprocal are evaluated once
before the active-width loop, then reused by its 256 samples. Width zero and
one still skip the division. The original Double floor expression, pulse/phase
state, event order, output operations and scheduler time stay intact. Phasor
receives no transformation or attributed saving.

Narrowing the conditional floor expression is separate work: an arithmetic
state probe produces floor 2 with the original evaluation and floor 1 after
narrowing. Reachability of that exact state through the public C ABI is not
established, so it is a reason to require a state/domain proof before changing
precision, rather than an observed patch-output failure.

The qualified numerical domain is finite train period 16..2048 samples and
width 0..1, with exclusive process/event ownership, caller buffers separate
from private state, nearest/even rounding and no within-block floating
environment changes. Signal-rate controls, other generated graphs and full
reset/synchronisation modes require separate qualification. Compile assertions
check the sample and clock representations; they do not establish the runtime
rounding mode or floating-environment/trap equivalence.

Admission pins the complete 42-file prepared source map, authored graph,
description, current fixed runtime and baseline configuration. It separately
checks the scalar caller, parameter setters, phase/reset/setup methods, pure
maximum helper and absence of external data references. Unknown files,
symbolic links, aliases, modified bodies and repeated/partial transformations
reject before publishing an output directory. The manifest records an explicit
Boolean flag and versioned execution contract while retaining `float32-strict`;
provenance includes the transformer and full inverse/source identities. Preserve
those records with the ELF identity when comparing implementations.

## Image binding and saved measurements

Fresh export, actual public CLI preparation and two independent module builds
reproduce both complete saved target images byte for byte. Compiler, SDK,
dependencies, private support archives, ABI and the 4,096-byte arena policy
match the saved pair. Compile assertions add no executable operations. The
entire module identities are:

| Module | Entire ELF SHA256 | Bytes |
| --- | --- | ---: |
| Reference | `8b9677154106082d5fd11749cf9828d268c8bf1ee335eae9c71f3eb2bd11fcd1` | 56,208 |
| Optional | `cdc7d6ad0faf94d184a2de6abac0b1576bcad93411e6d47efc3dba75b7731d04` | 56,120 |

The [saved target experiment](train-reciprocal-hoist.md) compares 12 workloads
and 9,437,184 channel words with zero numerical Float32 difference and exact
PCM. Total callback time falls from 2,304,575 to 1,404,446 µs over 17,280 timed
vectors per profile: **39.06% less processing time**. This includes unchanged
phasor, train state and clock work. The width-zero and width-one cases remain
division-free timing controls, with no individual saving claimed.

Both images have a 14,032-byte context and use an explicitly selected 4,096-byte
arena with zero observed high-water. Aligned text shrinks by 64 bytes; total
ELF length shrinks by 88 bytes. Both have zero imports. The saved target record
reports no running allocations and recovery of the observed internal/PSRAM
totals. Preparation, boundary-event delivery, I2S, display and networking are
outside the callback timer. These measurements do not establish a composed
live-player deadline bound or a minimum arena size for other patches.

## Accuracy limits retained

This option preserves an existing warm-start duty-check failure. At the maximum
period and near-full width, the original full-window observation is 0.98892975
against width 0.99999994. Changing period after warmup retains phase and pulse
state. A separately checked stationary suffix, after a source-derived 4,099
sample settling bound, passes the unchanged tolerance. Every startup sample
remains in the strict/candidate comparison.

Native raw-bit/readback comparisons and the saved target numerical/PCM checks
are different evidence levels. The target harness has no independent absolute
phase, duty or reset oracle and no raw IEEE-bit equality gate. Preserving output
does not close those gaps. Train's working status therefore remains partial.
The [historical evidence](../evidence/train-reciprocal-hoist.json) retains the
failure, control cases and historical firmware/control restoration. No new
board execution is performed for this admission.

The [public compiler admission record](../evidence/train-reciprocal-compiler.json)
binds these current sources, fresh public pipeline, compiler tests and
independent review to the unchanged historical measurements. It adds no new
physical observations or wider-mode performance claims.
