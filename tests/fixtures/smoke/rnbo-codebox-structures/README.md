# RNBO codebox structures and lifecycle

Twenty-four original programs check finite RNBO `codebox~` language forms.
The [official codebox reference](https://rnbo.cycling74.com/codebox) supplies
the language and lifecycle contracts. GenExpr and event-rate codebox are
separate surfaces. References were fixed before export or target execution.

The programs cover `var`/`let`/`const`, explicit `number`/`Int` declarations,
lexical shadowing, multiplication/addition precedence, if/else-if/else,
ternary and logical short-circuit state updates, switch/default/fall-through,
bounded for/nested-for/break/continue/while/do-while, scalar/list-return
functions, sample delay, independent state fields, internal parameter defaults,
and separate `init()`, `startup()`, `dspsetup()` hooks plus their combined counts.

Loop inputs include counts 0–5; do-while includes the mandatory first trip at
zero. Input vectors use finite dyadic numbers and both zero signs. References
use closed-form sums, absolute sample age and prefix counts rather than exported
algorithms. The delay starts with nonzero values and observes the prior sample
across every host block boundary. Short-circuit programs expose branch side
effects in their outputs; simple Boolean output equality alone is insufficient.

Each hook must count one invocation during one fresh initialize/prepare epoch.
The combined hook program also observes that startup sees init's completed
state. This does not establish relative dspsetup/startup ordering, later DSP
restarts, repeated preparation, sample-rate changes, resets or reconstruction.
The `@param` example checks only its internal default gain, without host updates.

On 5 November 2026, all **24 programs pass on XIAO ESP32-S3**, with
**245,760 output checks**, zero finite numerical mismatches and no nonfinite
outputs. Native and target vectors, expected stream hashes and signed-zero
counts agree. There are **3,700 signed-zero differences**, confined to five
loop programs, retained separately from numeric equality. This is not a
bit-identity claim. No reference or tolerance was fitted to target output.

The unchanged strict module profile uses zero automatic warmups, four checked
manual warmups and sixteen timed 256-frame callbacks at 44.1 kHz. Medians span
41.5–86 µs (about 0.71–1.48% of the block period), with maximum observed peak
91 µs. No CPU-review flag triggers. These measure whole authored callbacks,
without I²S, display or network work; no isolated instruction cost or
optimisation gain is claimed. All images finalise, arena high-water is zero,
and free internal RAM/PSRAM totals remain unchanged.

The three individual lifecycle hooks join their exact existing inventory
entries. The other language programs update the structure plan, without
inventing object entries or qualifying arbitrary source programs.

Evidence: [hardware results](../../../../evidence/xiao-smoke-rnbo-codebox-structures.json)
and [native preflight](../../../../evidence/rnbo-codebox-structures-native.json).

```sh
python3 tests/fixtures/smoke/rnbo-codebox-structures/generate.py --check
python3 -m unittest discover -s tools -p test_smoke_rnbo_codebox_structures_reference.py
```
