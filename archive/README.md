# Historical importer route

On 6 November 2026 the supported frontend changed to **Cycling ’74 C++ Minimal
Export from Max**. See the [current workflow](../docs/native-export.md).

`importer/` contains the retired `.rnbopat` adapter, internal XAM generator calls
and visual Gen-to-expression translator. It is kept solely for reproducing
historical tests, not as a supported alternate frontend. Historical qualification
tools explicitly point here; production Studio does not call these files.
The importer-era numerical rewrites remain opt-in research tools in
`host/compiler`, outside Studio's native-export workflow.

`docs/` preserves replaced top-level documentation. Original commands there may
refer to old paths. For a complete unchanged checkout, use the pinned
[`fcef6af` checkpoint](https://github.com/little-scale/esp32s3-rnbo/tree/fcef6af). That checkpoint also preserves the completed envelope/clock
batch and native Max side-by-side evidence before migration.

Do not reinterpret old inventory statuses, optimisation percentages or broad
frontend rejection counts as qualification of current native exports. Keep
source, runtime version, wrapper settings, arithmetic and event domain attached
to every result. Raw evidence JSON is retained without migration edits.

`importer/integer-ui/` is a byte-identical snapshot of the earlier producer used
by the exact-map optimisation tests. Those tests intentionally use their own
recorded producer rather than broadening hashes to accept later visual-lowering
metadata. `snapshot.json` records the original commit and all source hashes.
