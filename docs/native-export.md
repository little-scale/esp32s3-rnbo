# Export from RNBO in Max

**Cycling ’74 C++ Minimal Export is the only supported frontend.** Studio
compiles the exported C++ and packages it for the stable player. It does not
rebuild a `.rnbopat` graph, lower visual Gen or invoke RNBO’s internal generator.

## In Max

Use the RNBO export sidebar, choose the **C++ Source Code** target and configure:

| Setting | Required value |
| --- | --- |
| Minimal Export | On |
| Copy Library | On; include the complete matching `common/` directory |
| Fixed Sample Rate | 44100 |
| Fixed Vector Size | 256 |
| Main audio channels | 0 inputs, 2 outputs |
| Exported class | Any ordinary C++ identifier; Studio detects it |
| Runtime | RNBO 1.4.4 for the currently qualified adapter |
| External assets/services | Not supported by this player yet |

Set voices/polyphony, Gen algorithms, maximum delays and initial parameter values
in Max before export. Include parameter metadata (`@meta`) in the object when
using [physical inputs](physical-inputs.md). MIDI input and parameter metadata
must be present in the generated description, not just a drawing attachment.

Keep the generated header, `description.json`, `dependencies.json` and matching
`common/` together. Studio accepts that **folder or a ZIP containing one export**.
Header names other than `rnbo_source.h` are accepted and normalised without
changing header bytes. Runtime source `.cpp` files copied by Max are accepted;
Minimal compilation uses the header-only runtime units. Preserve generated
licence notices. The pinned runtime MIT notice is supplied if the export lacks it.

## In Studio

Run `./host/studio.sh`, then open [RNBO Studio](http://127.0.0.1:8788).
Choose **Open export folder** or **Open export ZIP**, set startup volume/arena,
and **Compile export**. Optionally attach the same `.rnbopat` using **Add patch
drawing**. Drawings are display-only; changing one cannot change the DSP. They
are not checked for semantic equality with the C++ export. Re-export in Max after
changing the audio patch.

The build records raw and prepared source identities, runs a native startup
screen, builds a board-independent module, and produces `.rnbopkg`. Install a
player once, then upload packages by USB or paired Wi-Fi. Packages from previous
builds remain loadable if their ABI and admission checks still pass.

## Current limits

The adapter supports numeric parameters (Studio/player maximum 32), one MIDI
input port and stereo Main output. External data/files, signal parameters,
arbitrary message ports and MIDI transmission are not implemented. Exporting
successfully in Max does not prove support for those services. Low-level FX
modules remain useful for qualification but are not a separate player patch slot.
MIDI output rejects by default; the low-level preparer has an explicit discard
policy when deliberately required.

Audio uses `RNBO_USE_FLOAT32`; explicit double storage and scheduler time can
remain Float64. Studio uses `float32-strict` and existing recorded compatibility
fixes. Previous Auto/Trial/kernel rewrites, comb caps and source regeneration are
historical research options, not current Studio modes. Their measured benefits
must be requalified on native exports before reintroduction. A patch that needed
Auto/Trial to meet its deadline may be too slow when rebuilt with the baseline;
its existing admitted package remains loadable.

The runtime/allocator/scheduler are still our responsibility. Read the
[wrapper review](native-wrapper.md) and [comparison evidence](native-export-comparison.md).
RNBO upgrades require a separate adapter/version check; do not mix runtime headers
from different exports. Nothing in this migration automatically updates Max.

Primary references: Cycling ’74’s [Minimal Export guide](https://rnbo.cycling74.com/learn/minimal-export)
and [C++ target overview](https://rnbo.cycling74.com/learn/the-cpp-source-code-target-overview).
The complete command-line sequence is in [host tools](../host/README.md).

## Triggering a build from a Max patch

A surrounding Max patch can trigger RNBO's documented `export cpp-export
cpp-code-export <dictionary-name>` message, monitor export status with
`@dumpoutlet 1`, then use `node.script` to read the completed export and call
Studio. The local API is already available: get `/api/status` for the current
session token; post the export to `/api/build` with `X-Studio-Token`; poll
`/api/job?id=...` until `ready` or `failed`. Folder payloads contain `export_files`
entries with `path` and `data_base64`, plus an export `name`. See
`host/native_export.py` and Studio's browser code for the bounded payload contract.
Never submit a folder while Max is still writing it, and never reuse an old
successful export after a failed export attempt.

A dedicated Max build-button helper is not implemented yet. Build and upload
should initially remain separate. Keeping the button in the parent Max patch
avoids exporting a build-only `outport`, which the current player does not
support. RNBO running on the board cannot run the host compiler by itself.

Cycling ’74 documents [RNBO export messages](https://docs.cycling74.com/legacy/max8/refpages/rnbo~)
and [Node for Max file/network access](https://docs.cycling74.com/reference/node.script).
