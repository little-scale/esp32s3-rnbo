# Numeric and list-routing fixtures

These original MIT graphs cover 62 scenarios across 30 exact spellings. The
[report](../../../../docs/rnbo-event-routing.md) separates completed target output
checks, the isolated positive-rotation target fault and C++ literal-message
failures. Aliases and auxiliary observers inherit no qualification.

Each graph uses an explicit `arm` parameter to open a closed gate before 21
ordered `drive` actions. The drive value contains a tag 0…3 plus an independent
3-bit fractional payload. Lists contain deliberately unsorted values and
duplicates. Repeats, held callbacks and three ordered actions before callback 10
are included; all actual/normalised parameter readbacks are checked by ID.

For 0…5 list items in 0…7, the observation code is:

`length * 32768 + sum(item[i] * 8**i)`

This is injective, preserves list length/trailing zeros and is exact in binary32.
The test exhaustively checks all 37,449 valid lists for uniqueness and decoding.
Scalar/count outputs are observed directly. `list.sect` no-match bangs and
`list.sub` zero-count notifications explicitly supply no-match code 0; an empty
list is not assumed to arrive on the data outlet. Five literal-message controls
check lengths and digit positions natively; three retain target C++ failures.
Other five-element list transformations provide target observer coverage.

Four manual warm and sixteen timed 256-frame callbacks give 10,240 output-word
checks per completed graph at 44,100 Hz. There is no automatic warmup. The
independent right pilot includes finite extrema, signed zeros and subnormals;
all 5,120 raw right words are captured and hashed. Every numerical limit is zero.

State work occurs in setters/routing. Their 22-action total and peak include arm
and observer work; the timed process callback mainly emits the held value and
pilot. Neither metric is an isolated operation cost or an optimisation saving.

`generate.py --check` verifies current graphs and four 16/14-source partitions.
The original singleton `part0.json` fault probe is immutable and remains bound
to its original catalog parent. The
[`unobserved-no-match-v1`](unobserved-no-match-v1/README.md) archive preserves the
initial two observation omissions and all original reference streams. Only two
observation graphs change; all 62 expected streams and zero-error limits remain
unchanged. Larger lists, other types/options, reset modes, within-block host
events and other RNBO/Gen forms remain unqualified.
