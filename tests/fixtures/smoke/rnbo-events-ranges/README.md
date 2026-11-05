# RNBO numeric events: ranges, pass comparisons and event state

These 22 original flat RNBO patchers test the exact spellings listed in
`catalog.json`, using the unmodified Float32-sample/Double-time preparation.
Each declares two signal inputs; input1 is unused, while input2 is an independent
raw-word pilot. A real `param drive` feeds the tested hot inlet, then `sig~`
holds its output on channel1. Cold operands are source literals.

The six pass predicates each have an independently exported symbol spelling.
They output the left **value** when their comparison with 2 is true, otherwise0.
Clamp/clip, wrap and fold use bounds[-1,1]. Wrap's oracle is half-open; fold's
includes both endpoints. Conditional spellings select +2 or -2. Linear interpolation
uses endpoints -1,+1. Triangle uses duty 0.5 and box-to-triangle shape 1; these three
use only dyadic inputs in[0,1]. Delta subtracts the previous **event** value.
The references are mathematical/document-based; generated DSP bodies are never
used as the oracle. Catalog entries bind the local RNBO1.4.4 primary references.

Each fresh module has zero automatic warmup. There are 21 authored actual-value
parameter actions and 20 full256-frame calls (manual warm 4, timed 16). The schedule
covers signs, zero, equality, repeated values, multi-period crossings, endpoint
values, hold gaps and ordered multiple events before one callback. Delta updates
its state after every event, so dropping intermediate events changes its answer.
No within-block timestamps, arbitrary cold-inlet changes, reset modes or
one-sample player behavior are covered. The signed-zero convention on the left
is diagnostic; the raw right pilot requires exact words, including signed zeros,
subnormals and extreme finite binary32 values. Every numerical tolerance is 0.

`generate.py --check` reproduces the source graphs/catalog. Portable tests check
range endpoints, ordering/state, source admission and collector mutations. The
parent catalog and reference are hash-pinned; the collector independently
reconstructs the whole expected stream and authored controls. A changed source,
schedule, domain, tolerance or incomplete ledger rejects. Original build,
native preflight and target outputs stay under ignored `build/`.

The XIAO run passes all 22 scenarios and 225,280 output-word comparisons.
The wrap/fold cases each have 256 left signed-zero word differences; all numeric
values and all right-pilot words agree. Each module finalises, with runtime
allocation/memory gates passed. Median complete FX callbacks are 75–76µs and the
largest observed callback is80µs; no CPU flag triggers. Event setters are timed
separately (21-action totals 155–197µs; per-action peak31–41µs), including wrapper
and routing overhead. These are not isolated object costs or optimisation gains.

[Target evidence](../../../../evidence/xiao-smoke-rnbo-events-ranges.json),
[secondary native preflight](../../../../evidence/rnbo-events-ranges-native.json),
and [player restoration](../../../../evidence/xiao-smoke-rnbo-events-ranges-player-restoration.json)
retain their separate scopes. Native tests also pass numerically with the same
512 left zero-sign differences; they do not predict target timing.
