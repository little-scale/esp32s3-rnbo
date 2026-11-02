# Initial patches

These original, flat RNBO patch graphs use the local RNBO 1.4.4 export route.
Their generated C++ is produced locally under `build/` and retains Cycling '74's
generated-code notices separately from these patch designs.

* `sine/sine.rnbopat`: autonomous stereo oscillator, default 440 Hz and level
  0.2, with stable parameter IDs `frequency` and `level`.
* `fx-pass-through/fx-pass-through.rnbopat`: independent stereo inputs routed
  to corresponding outputs. Prepare with `--role fx`.
* `midi-envelope/midi-envelope.rnbopat`: note-to-frequency oscillator multiplied
  by a 5 ms attack, 20 ms decay, 0.8 sustain, 60 ms release envelope and level
  0.1 parameter. Export with `--voices 1`, `2`, or `4`. Polyphonic exports require
  the explicit `--midi-output discard` preparation policy.

All exports use 44,100 Hz and 256 frames. The pass-through fixture proves the
generated two-input path; complete Main/FX lifecycle qualification follows the
static bring-up and loader gates.
