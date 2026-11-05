# Embedded visual Gen core on XIAO

Studio's `.rnbopat` importer now reads embedded `genpatcher.patcher` graphs in
the `dsp.gen` namespace. This is a new, explicitly limited frontend route, not
inherited qualification from earlier authored GenExpr programs. Cycling '74's
[Gen in RNBO guide](https://rnbo.cycling74.com/learn/gen-rnbo) describes embedded
visual Gen, file loading and single-sample feedback; the broader documented
feature set remains part of our qualification goal.

The current core admits `in`, `out`, `+`, `-`, `*`, `/`, `abs`, `neg` and `history`.
Binary operators take two connected inputs or one connected input and one fixed
numeric argument. Port ordinals must be dense. Named histories retain their
names and initial values. Histories are snapshotted before graph computations;
all next-state assignments follow the computations. This preserves previous-
sample reads, fanout and simultaneous coupled-state updates across callbacks.
Negative-zero literals retain their sign in emitted code; their wider runtime
semantics remain unqualified by this batch.

Unknown nodes/options, implicit disconnected arithmetic defaults, multiple
connections to one inlet, algebraic loops, shared history names, nested graphs,
external files/assets, exposed parameters and visual codeboxes reject. A graph
cannot be overridden by a stale saved `expr` or `file` attribute. Existing
explicit authored GenExpr imports continue to work. These restrictions describe
current implementation boundaries; they are not claims that RNBO lacks those
features. Remaining visual operators, attributes, parameter/reset paths,
resources, codeboxes and file-based graphs still need implementation and tests.

The adapter lowers a validated visual graph to GenExpr, then uses the installed
RNBO1.4.4 generator. The original source file is retained unchanged. Generator
metadata binds the source graph, emitted GenExpr, lowerer, operators and history
count; both native and target build inventories include the new helper.
Collectors reconstruct this bridge and independently check all expected sample
streams. No generated RNBO DSP body is used as a numerical oracle. The immutable
[fixture catalog](../tests/fixtures/smoke/gen-visual-core/catalog.json) contains
21 original embedded graphs with no authored or cached GenExpr.

All 21 scenarios pass on the XIAO: arithmetic, fixed operands, negation/absolute
value, one- and two-sample histories, fanout, unconnected initialized history,
closed two-state swaps, three-state rotation, bounded feedback and coupled
feedback. There are **215,040 output-word checks** over four checked manual warm
callbacks and sixteen timed full256-frame callbacks, with zero automatic warmup.
The histories demonstrably advance per sample inside each fixed256 callback;
this does not create a variable-frame or one-sample production module ABI.

Arithmetic/delay/permutation oracles use independent dyadic formulas. Feedback
uses bounded finite convolutions and matrix powers, with a predeclared2e-6
absolute limit. Differences within that limit are recorded separately, alongside
exact word differences and first outside-limit witnesses. The strict
Float32-sample/Double-time profile is unchanged; no optional DSP optimisation
or CPU saving is claimed. Original build/measurement artifacts remain private
under `build/`, with public hash-bound receipts.

The final target run records **5,422 within-limit feedback differences**, maximum
**1.1920929e-7**, with no outside-limit, nonfinite or zero-sign differences.
Complete callback medians are **40–100µs (0.69–1.72% of the block period)**,
peak 104µs. The wired divide callback is 100µs; coupled feedback 48µs and the
single feedback loop 44µs. These are complete compiled graph callbacks, not
isolated opcode timings or matched optimisation savings. No CPU screen triggers;
the queue stays 151 contexts. All 21 images finalise and runtime allocation/memory
gates pass. The normal player and original controls are restored afterward,
with advancing audio frames and zero runtime fault counters checked.

The final audit fixed negative-zero literal serialization, with a pure frontend
regression check. Both full target runs pass. For these 21 unchanged source graphs,
generated DSP and normalized module ELFs are byte-identical across that fix;
the final run binds the fresh frontend hashes. Native preflight retains exact
numeric differences separately: the same 5,422 feedback words remain within the
predeclared limits. Native times do not establish target performance.

The [target results](../evidence/xiao-smoke-gen-visual-core.json),
[secondary native preflight](../evidence/gen-visual-core-native.json),
[build/bridge ledger](../evidence/gen-visual-core-builds.json) and
[player restoration](../evidence/xiao-smoke-gen-visual-core-player-restoration.json)
retain separate scopes. The RNBO dashboard adds only the exact `gen~` row,
bringing it to **936/1,455 scoped entries**. The 212-entry GenExpr source-route
ledger stays separate and does not inherit visual-graph outcomes. The full
RNBO/Gen qualification goal remains active.
