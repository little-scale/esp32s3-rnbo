# Original arithmetic and codebox breadth fixtures

These 13 MIT-authored FX graphs preserve **11 exact patcher spellings** and
two separately authored codebox programs. Aliases and canonical names have
separate graphs. No qualification transfers between them or between patcher
and codebox surfaces.

`recipes.json` is the reviewed construction catalog. Reproduce all graphs and
the execution catalog in a fresh directory with:

```sh
python3 host/compiler/generate_object_fixtures.py --out build/wave4-original
```

Select one or more exact fixture IDs with repeated `--fixture ID`. The generator
checks every recipe before writing anything and rejects unknown operations,
ports, surfaces, domains, model identities and case policies. It writes original
editable patch graphs and metadata only. It does not export RNBO C++, run a
module, or access a device.

The initial contract is 44.1 kHz / 256 frames, FX with two binary32 input/output
planes, no parameters/events, and finite input values in `[-1,1]`. Binary
patcher graphs perform the operation on `(left,right)` and `(right,left)`.
Absolute value uses independent planes. Codebox arithmetic emits sum/difference;
the codebox delta program emits the left previous-input difference and a direct
right-plane observer. Constructors start with zero previous input. Four
zero-input warmup vectors and two fresh lifecycles are declared for each case.
Explicit reset and event-rate codebox are separate pending modes.

`inputs.py` supplies three output-independent programs: signed/adjacent and
subnormal values, dense deterministic binary32 words, and vector-edge
transitions at 255/256 and later boundaries. `models.py` supplies independent
mathematical operations and explicit previous-input history. Finite binary32
output values must match their mathematical rounded results exactly; this
does not claim an unspecified signed-zero tie rule for operation outputs.
The delta fixture's untouched right-plane observer must copy every input bit,
including signed zero; an observer bit mismatch fails qualification even when
its numerical error is zero. Zero-sign and other operation bit differences
are separate diagnostics. No NaN/infinity, fenv, arbitrary-domain,
other-rate, signal/control overload or memory-growth claim is made.

The unit suite verifies regeneration, invalid-input failure atomicity,
noncommutative and wrong-model rejection, vector history/reconstruction and
input chunk invariance. With an authorised local RNBO1.4.4 installation it also
freshly exports all 13 graphs, prepares them with normal strict fixes and syntax
checks the actual production dynamic wrapper. Generated RNBO implementation
files remain in temporary/ignored build directories.

```sh
python3 -m unittest discover -s host/compiler -p test_generate_object_fixtures.py -v
```

These sources, recipes and models are **not execution results**. Actual native
execution, Xtensa module admission, XIAO lifecycle/outputs, CPU and memory must
be recorded separately with exact input/profile/module identities. Static
syntax checks do not establish ELF execution. Any CPU time belongs to the
whole authored fixture and its operation count, not an inferred isolated
operator saving.
