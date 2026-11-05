# Original no-match observation screens

This immutable archive preserves the original reference, generator snapshot,
catalogs/partitions and the two original graphs whose observation was incomplete.
Do not run the historical generator here. Use the current parent generator.

The first fixtures watched the list data outlet only and expected code 0 when
there were no matches. RNBO documents a separate no-match bang for `list.sect`
and a match-count outlet for `list.sub`. The current two graphs explicitly watch
those notifications to reset the held code to 0. All 62 expected output streams
and all zero-error limits stay unchanged. The original comparison differences
are fixture findings, not two object defects.

`source-locations.json` resolves every original graph: the two changed graphs
are stored here; the other 60 remain byte-identical in the parent directory.
The original singleton rotation probe keeps its archived catalog identity;
the positive-rotation graph itself is unchanged by this correction.

Initial native observations and three completed original target partitions are
bound by the [initial-screen ledger](../../../../../evidence/rnbo-event-routing-initial-screens.json).
The fourth original partition was built but never flashed before the observation
correction. Final target results are separately regenerated and executed.
