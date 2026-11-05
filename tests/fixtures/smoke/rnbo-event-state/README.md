# Ordered event-state fixtures

These original MIT sources cover 36 state scenarios across 15 exact spellings.
See the [hardware report](../../../../docs/rnbo-event-state.md). Aliases, auxiliary
objects and signal/codebox/Gen counterparts inherit no qualification.

Each source has `drive` (-8…8, initial 0) and `arm` (0…1, initial 0) parameters.
The drive passes through a closed `gate 1 0`. The first controlled action sets
arm to 1, synchronously seeding counter/peak/trough cold inputs before opening
the gate. This isolates the test from RNBO startup parameter notifications.
Twenty-one drive actions then include repetitions, holds and three ordered
updates before callback 10. Both actual and normalised readbacks are checked.
Parameter IDs, rather than a presumed metadata index order, bind controls.

Scenarios include additive/multiplicative prefixes and neutral resets, three
latch states, all change/peak/trough numeric outlets, four counter sequences,
next/immediate counter resets, asymmetric slide/rampsmooth trajectories,
sample-and-hold edges and right-to-left trigger ordering. Change uses sum/count
observers so duplicate-event suppression is observable. Accumulator reset inputs
are neutral: 0 for sums, 1 for products. Counter carry outlets remain separate
future work.

The independent reference uses prefix sums/products, bounded index sequences,
edge/change predicates and rational smoothing trajectories. Only slide and
rampsmooth have a 2e-6 absolute limit; all other numerical limits are zero. At
44,100 Hz/256 frames, four manual warm and sixteen timed callbacks give 10,240
word checks per source, with zero automatic warm callbacks. The independent
right pilot copies signed zeros, finite extrema and subnormals; all 5,120 raw
right words are captured and hashed outside process timing.

State work runs in setters/routing; its 22-action total and peak include the arm
action. The timed process callback mainly emits the held value and pilot. Neither
measurement is an isolated opcode cost or a matched optimisation gain.

`generate.py --check` checks current graphs and two 18-source partitions against
installed Cycling ’74 reference/help hashes. The historical
[`startup-exposed-v1`](startup-exposed-v1/README.md) archive is immutable and is
not used to build current tests. All 36 expected output streams and numerical
limits are unchanged by the explicit arming correction. Other modes, reset
attributes, constructor options, lists, transport/clock behaviour and within-block
host event offsets remain unqualified.
