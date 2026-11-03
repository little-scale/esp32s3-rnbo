# Original stateful RNBO fixtures

These MIT-authored flat graphs exercise exactly `onepole~`, `slide~`, `delta~`
and `sah~`. Tests do not transfer to canonical names, aliases or codebox forms.

`catalog.json` declares the input/output channel mapping, fixed/scalar/signal
controls, ordered actual parameter events, zero-input warmup and reconstruction
policy. Events retain their listed order at each 256-frame boundary. Inputs
and wire parameters are rounded once to binary32 before execution.

The signal forms use two direct FX input planes. Onepole uses input2 as cutoff;
slide tests signal up/down on separate output states; sample/hold uses input1
as both sampled data and signal threshold. The latter is an intentional
read-only relationship, not an arbitrary three-input qualification.

The independent accuracy limits are fixed before rendering: onepole/slide
`3e-6`, delta `2e-6`, and sample/hold exact source-word copies. Runtime health,
strict-versus-sanitised compatibility, ideal accuracy and target admission are
separate results. Existing accuracy failures must remain visible.

Explicit operator reset attributes, arbitrary messages, other spellings and
hardware execution are outside this fixture wave. Fresh-instance
reconstruction does not qualify those reset modes.
