# Local Gen Data and indexed storage

Eight original GenExpr programs use a local `Data memory(7, 2)` declaration
and independently modeled array operations. The declaration is distinct from
a standalone lowercase `data(...)` call or a visual Gen object. Sources are
separately authored for the named dimension/channel queries, reads and writes;
helper calls do not inherit their own qualification.

| Program | Predeclared behavior |
| --- | --- |
| Data dimensions | Observe length 7 and channel count 2. |
| `dim` | Observe length 7 and a copied right input. |
| `channels` | Observe channel count 2 and a copied right input. |
| `peek` ring | Read both cells before writing the current input pair; independent seven-sample FIFO. |
| `poke` readback | Write the current pair, read the current left cell and the next right cell; current left plus six-sample right FIFO. |
| `nearest` | Read asymmetric initialized channel tables at integer sample indices 0–6, with no interpolation. Fractional nearest rounding is not tested. |
| `sample` | Linear interpolation of the same tables at quarter-sample positions 0–6, clamped boundaries. |
| Data feedback | Independent seven-sample feedback convolutions, gains 0.5/0.25 and bounded inputs. |

Reads explicitly use sample units and zero-based channel offsets 0/1. All
content-dependent programs initialize the fourteen cells only on the first
sample through a supported History flag. Ring programs then write two cells
per sample. Initial table values come from literal source values; the reference
does not assume allocator-zeroed memory or a physical interleaving layout.
The read's auxiliary returned index is not observed, so only sample outputs
are claimed. Poke's overdub 0 preserves none of the old sample.

Each normal FX graph has two declared inputs and outputs, no parameters and
no external Buffer. The source keeps the original producer storage type and
allocation policy unchanged. Primary Gen metadata describes Data as 64-bit;
this RNBO producer instead lowers local Data to `SampleBuffer<SampleValue>`.
Under the ordinary Float32 target ABI its cells are therefore Float32: seven
frames and two channels have 56 logical payload bytes, before metadata/alignment.
That type is the original backend default, not an optional storage-narrowing
profile. The selected dyadic copies/tables are exact in either width; the
feedback reference remains the independently declared ideal equation with its
unchanged 2e-6 limit. Actual allocated bytes and lifecycle health still require
target observation; generic 64-bit Gen storage equivalence is not claimed.

References cover twenty continuous 256-frame callbacks: fresh preparation with
no automatic warmup, four checked manual callbacks, then sixteen timed calls.
Seven cells do not divide 256, so ring state crosses callback boundaries. The
fixed-256 production ABI is unchanged; this is not a one-frame host API.

Metadata and exact copies use zero numeric tolerance. Linear interpolation and
feedback use predeclared 2e-6. Feedback references are fresh 64-term input
convolutions, with omitted tails at most 2^-65 and 2^-128/3. Operation signed
zeros remain diagnostics. Models, sources and limits are frozen before output;
frontend/prepare failures stay in the ledger without a substitute API.

Run `generate.py --check` against installed primary metadata; portable tests use
`python3 -m unittest tools.test_smoke_gen_data_indexed_reference`.
