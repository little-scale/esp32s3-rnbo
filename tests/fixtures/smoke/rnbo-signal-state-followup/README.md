# Further RNBO signal state checks

Seven original flat signal graphs cover four exact owner spellings. They have
two declared audio inputs and outputs, no parameters, fresh preparation with
zero automatic warmup, four checked manual callbacks and sixteen timed callbacks.
All twenty 256-frame blocks form one continuous reference stream. This is the
fixed-256 production ABI, not a one-frame host API.

| Scenario | Independent reference and primary settings |
| --- | --- |
| `onepole_lin~`, fixed | Two zero-initialized filters with coefficients 0.25/0.5 supplied by explicit `sig~` nodes. Ideal first-order difference equation, evaluated in Float64; 2e-6 output limit. |
| `onepole_lin~`, signal coefficient | Data and coefficients 0.25/0.5 on the actual two inlets, plus a copied coefficient pilot. Ideal continuous filter equation; 2e-6. |
| `onoff~` | Primary prose says one toggle per DSP block; initially false state gives first callback 1, then 0/1 alternation. No signal inputs used. Zero numeric tolerance. |
| `counter~`, count/flag | Amount input 0/1 and reset input 0/1, literal reset default 0 and limit 7. Add before output, reaching 7 wraps to 0 and emits carry flag 1. Reset stops counting and clears count/carry. Zero tolerance. |
| `counter~`, count/carry count | The same settings and inputs, observing the first and third outlets instead. All three documented signal outlets are thus observed across two separate fixtures. Zero tolerance. |
| `normalize~`, fixed max | Separate signed running absolute peaks, primary initial floor RN32(1e-6), target maxima 0.5/1 on the actual second inlet. Inputs use dyadic power-of-two magnitudes; zero tolerance. |
| `normalize~`, signal max | Data and nonnegative dyadic output maximum 0.25/0.5/0.75/1, plus a copied maximum pilot; zero tolerance. |

The counter increments avoid overshooting its limit, so the model does not
assume undocumented multi-wrap handling. Reset controls and late held values
make state across callback boundaries observable in the filter, counter and
normalization cases. Counter carry outputs belong to their respective original
graphs; this is not an arbitrary three-channel host test.

`updown~` is recorded separately as **reference-design-pending**. Its primary
attributes explicitly use milliseconds, but the adaptive estimator has no
sufficiently precise pointwise transient/alignment contract for the proposed
independent waveform comparison. It was removed before export or execution;
the preliminary draft remains private history. It is not replaced by a copied
implementation, a fabricated ideal envelope or a constant-zero generator test.

Numeric limits are fixed before execution. Signed-zero differences remain
diagnostics; pilots have the same numeric gate as their fixture, without an
additional raw-bit observer claim. Default internal storage is not replaced.
Actual generated resources, arena use, CPU flags and memory health require
separate export/build/device observations. No aliases, codebox/Gen forms, other
controls, reset methods or optimisation gains inherit these scenarios.

Run `generate.py --check` against the installed RNBO primary metadata. Portable
tests: `python3 -m unittest tools.test_smoke_rnbo_signal_state_followup_reference`.
