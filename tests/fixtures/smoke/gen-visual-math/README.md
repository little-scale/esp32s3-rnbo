# Visual Gen maths, comparisons, logic and constants

These 101 original embedded `dsp.gen` graphs exercise exact source spellings,
including separately exported aliases. Each graph has one tested operation and
an independent raw right signal pilot. The original source contains no cached
or authored GenExpr. `generate.py --check` regenerates the graphs and four fixed
partitions; `reference.py` defines finite domains and mathematical expectations
independently of the compiler and emitted code.

Each module receives the same 256-frame input vector for 20 calls (manual warm 4,
timed 16), with zero automatic warmup at 44.1kHz. The left lane sweeps 16 dyadic
values and the right 16 for each left, covering all 256 pairs. Division and atan2
avoid zero divisors/ambiguous origins; logs, roots and powers use positive
inputs; inverse trig, atanh and tangent have bounded valid inputs. Named
constants output their mathematical value; literal `constant 3.5` is exact.
The catalog records both domains and each original spelling.

Exact arithmetic, logic, integer-like numeric and min/max cases use zero numeric
tolerance. Ordinary maths uses 2e-6 absolute error, power 2e-5, radian-to-degree
constants 8e-6, and the four fast functions a separately declared 1e-3 ideal-function
screen. Signed fraction is an explicit convention. Left zero signs are recorded
separately; every raw right word is independently checked by capture SHA256,
so a left mathematical tolerance cannot mask a corrupted pilot. Invalid domains,
NaN/subnormal handling and broader default/argument modes are unqualified.

The frontend currently requires connected operands for the new math functions.
In particular, cold constructors for atan2/hypot are rejected because their
argument/inlet layouts need separate implementation and tests. Data/resources,
parameter/reset paths, codeboxes, nested/file forms and other operators remain
active work. Existing explicit GenExpr and initial core graphs continue to work.

The immutable `qualified_lowerer.mjs` is the original MIT compiler source used
by this batch. Historical receipts resolve this snapshot by hash, rather than
requiring the production compiler to stay unchanged. The earlier 21 core graphs
have their own snapshot, and their emitted lowerings remain byte-identical.
Unknown source snapshots, changed domains/limits, altered visual spellings and
incomplete ledgers reject. The producer bridge and numeric oracle stay separate.

All 101 scenarios execute; 99 pass, while `fasttan` and `fastexp` exceed the declared
screen. These are retained accuracy differences, not general execution failures.
Five logarithm/exponential callback contexts join the CPU review queue. All images
finalise and runtime memory/allocation checks pass. The normal player and saved
controls are restored. See the [individual operator table](../../../../docs/gen-visual-math.md)
for exact outcomes, CPU costs and evidence. No optimisation saving is claimed.
