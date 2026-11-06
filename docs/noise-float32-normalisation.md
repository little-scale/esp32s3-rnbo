# Pink-noise output precision experiment

> **Historical importer-route research.** The supported workflow now uses [Max Minimal C++ Export](native-export.md) only. Results and optimisation settings below describe their recorded builds; they do not establish native-export qualification. The testing goal is paused. Old commands are archival.

The reviewed private RNBO 1.4.4 noise fixture keeps pink's final output scaling
in Float32. Its division already returns Float32; changing the following `2.`
and `1.` literals to `2.f` and `1.f` removes four software Float64 helper calls
per pink sample. White noise, integer random state, row history, seed policy,
setup and scheduler/time arithmetic remain unchanged.

The original and candidate modules passed 786,432 numerical sample comparisons
on the ESP32-S3 with zero float difference and exact PCM. Total callback time
fell from 492,647 to 243,244 microseconds over 1,440 timed vectors per variant,
about 50.6%. This measures the complete authored stereo noise fixture in an
offline harness, without I2S, UI or networking. It is an observed workload result,
not an isolated pink-only timing or universal deadline bound.

Both variants recovered the measured external and internal heap baselines,
performed no observed late allocations and completed four image finalizations.
The runner restored the identified drone instrument and its live controls.

Separate native tests compare three 4,096-block runs, including warm and cold
starts and another create seed. All 6,291,456 float words and corresponding PCM
samples match, with identical random-state and clock snapshots. An exhaustive
normalisation check covers all 142,606,320 possible nonnegative masked sums for
the pinned 16-row algorithm. All output bits match. This domain argument depends
on the reviewed row count, masks and expression.

Pink continues to seed from the module sample clock. The fixture's white seed
is authored explicitly. Preserving these streams does not make pink follow the
create seed or decorrelate different pink objects.

The preparer's default-off `--float32-pink-output` option now admits this exact
authored `tests/fixtures/objects/wave2/noise-colour.rnbopat` graph. It requires
the Main role, `float32-strict` base profile and normal runtime fixes. Whole
generated source, description and corrected-runtime hashes pin the fixed row
count, initialization, all state writers and callers. Changed graphs, row counts,
runtime versions, partial transformations and repeat application reject before
publishing prepared output. Broader pink forms remain outside this option.

```sh
python3 host/compiler/prepare.py \
  --export build/exports/noise-colour-NEW \
  --out build/prepared-noise-f32-output-NEW \
  --class-name rnbos3patch --role main --float32-pink-output
```

The explicit manifest flag and adaptation distinguish the selected output
precision while retaining the base strict profile. No resource, callback or ABI
layout changes. Eight compiler-helper hashes are recorded by preparation and
native/module builders. The integrated preparer reproduces the tested private
module ELF byte for byte. A fresh actual-wrapper build with UBSan also matches
the three original long streams, PCM and random/clock state snapshots.

The [sealed prototype evidence](../evidence/noise-float32-normalisation.json) binds the
immutable private source/native reports, artifact hashes, disassembly review,
target measurements and restored instrument. Its original native report's
pending-target statement predates this subsequent board run. The separate
[compiler integration evidence](../evidence/pink-output-compiler.json) records
the new preparer/build identities and byte-identical tested ELF.
