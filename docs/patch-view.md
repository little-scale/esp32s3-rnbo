# Patch view

The AMOLED interface follows the FM1 RNBO player: black background, bright blue
RNBO object outlines (`#40a0ff`), white patch cords and status text, square boxes,
small inlet/outlet notches and Barlow Semi Condensed lettering. Gen containers
use white. The original FM1 layout/rendering concepts are MIT; the bundled
Barlow fonts are SIL OFL 1.1. Content hashes and changes are in
[`host/visual/UPSTREAM.json`](../host/visual/UPSTREAM.json).

The host compiles the actual editable `.rnbopat` plus the matching RNBO
description into immutable metadata. The graph uses a 336 × 232 pixel region
on the 368 × 448 display. It preserves object anchors and explicit cord
midpoints, fits compact labels and resolves collisions deterministically.
The report retains source coordinates and the exact source/description hashes.
Comments and panels are decoration; subpatchers remain boxes.

There are at most 96 objects and 384 wire segments. Unsupported, invalid or
unreadable layouts select a paginated parameter list and report the reason.
Connections are never silently omitted to make a graph fit. A manual Minimal
Export without editable source also uses the parameter list.

Tap a parameter box to highlight it and open the dedicated parameter page,
or use **Params**. The eight drone parameters have wide multislider bars that
can be edited with one continuous drag; current
values and units come from RNBO's exported schema. **Patch** returns to the
graph. Volume, **Pause** and **Resume** remain available on both pages, with a
post-volume output meter. See [AMOLED controls](amoled-controls.md).
Touch and USB send bounded owner events; the display
never calls a running patch. The audio owner publishes parameter readbacks with
32-bit atomics after accepted events. Rendering uses an LVGL draw callback,
without allocating an object for each box/wire or doing display work on the
audio core.

```sh
python3 tools/build_firmware.py amoled \
  --components-from /path/to/pinned/managed_components \
  --export-dir build/prepared/my-patch --patch-title 'My Patch' \
  --initial-volume 28
```

The build report includes generated layout hashes. USB `status` reports
`visual_nodes`, `visual_segments` and `visual_source_sha256`;
`parameter-values` reads the owner's cached actual/normalized values.

To preview the **same firmware widgets and font bitmaps** on the computer:

```sh
python3 tools/render_patch_view.py --prepared build/prepared/my-patch \
  --title 'My Patch' --out build/previews/my-patch
```

This uses the locked LVGL source staged under `build/vendor-amoled/`, a native
C compiler and mocked board functions. It produces PNGs for the graph,
parameter page and paused state, simulates the navigation and Pause/Resume buttons, and checks LVGL
heap integrity. It is a renderer preview; physical touch/display checks are
separate. The font generator needs Pillow 13.0.0 only for regeneration; normal
builds use the checked-in C font data.
