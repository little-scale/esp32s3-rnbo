# Signal-driven cycle fixture

`cycle-signal.rnbopat` is an original MIT-licensed qualification patch. It sends
ordinary frequency/phase parameters through `sig~` objects into both `cycle~`
signal inlets, then sends the sine output to both output channels. Parameter
stable IDs are `freq` and `phase`.

The compiler guard tests read its actual local RNBO1.4.4 export from
`build/exports/cycle-signal`, rather than embedding generated code in tests.
Export it with `host/export/export.mjs` before running the corresponding test.
