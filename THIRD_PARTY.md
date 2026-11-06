# Source and license inventory

The integration has mixed licenses. Each original source file carries an SPDX
identifier; the root license does not relicense imported code.

| Material | Source and license | Treatment |
| --- | --- | --- |
| Host exporter/compiler, module C ABI/wrapper, original patch designs and native tests | Original MIT integration; reviewed FM1 MIT exporter/runtime adaptation design | Source included; MIT text in `LICENSES/MIT.txt` |
| Board audio drivers, PCM volume behavior, board profiles and firmware shell | ESP32 SynthDef baseline `59e19441408a4df14cf2f5b6e8ba527929e74d9b`, GPL-3.0-or-later | Notices preserved; imported and derived paths in `UPSTREAM.json` |
| Waveshare BSP, codec, display, LVGL and related components | Exact component collection in `firmware/dependencies.amoled.json`; per-component licenses | Staged locally under ignored `build/vendor-amoled/`, with original notices |
| ESP-IDF and Xtensa toolchain | Existing local ESP-IDF 5.5 installation and GCC 14.2.0 | External build prerequisites; actual toolchain/config recorded by each build |
| RNBO runtime | Installed RNBO 1.4.4 `source/rnbo`, MIT with per-file additional notices | Copied only into local ignored exports; runtime license and original headers preserved |
| RNBO-generated C++ | Cycling '74 Max-Generated Code for Export / GPLv3 dual notice | Original generated notice retained, including on prepared copies; not relicensed MIT |
| Espressif ELF loader | `esp-iot-solution` commit `d2d935d0ee3e78deffa3981cc8c39ac8f534932b`, Apache-2.0 | Separate loader spike and pinned local source; no loader qualification inferred from compilation |
| Patch layout and FM1 visual design | FM1 RNBO player, MIT, Copyright (c) 2026 Sebastian Tomczak and contributors | Adapted for AMOLED/LVGL; original MIT notice in `LICENSES/FM1-RNBO-visual-MIT.txt`, file hashes in `host/visual/UPSTREAM.json` |
| Barlow Semi Condensed fonts | FM1 bundled Barlow assets, SIL OFL 1.1 | Original font files and OFL retained in `firmware/components/board_display/fonts/`; generated 1-bit LVGL fonts |

Combined firmware includes the GPL board integration. Component license and
corresponding-source requirements remain attached to that combined work.
Generated patches, installed applications, credentials and compiler downloads
are not committed as original integration source. There are no copied system
font files or generated Arial assets in this project.

The source baseline's [licensing inventory](https://github.com/little-scale/fm1-rnbo/blob/3b46afcd022f10a7f82be99a613bdc98b875c209/LICENSING.md)
and [Cycling '74 export terms](https://support.cycling74.com/hc/en-us/articles/10730637742483-RNBO-Export-Licensing-FAQ)
describe the distinct generated-code and runtime terms. Local build artifacts
are development evidence, not a prepared binary distribution.

## Native Max export intake

The supported frontend is Cycling ’74 C++ Minimal Export. Generated source retains
its original licence notice. `LICENSES/RNBO-runtime-LICENSE` is the unmodified MIT
notice from installed RNBO 1.4.4 `source/rnbo/LICENSE`, used when a complete Max
export omits a separate runtime notice. Runtime headers remain supplied by the
user’s export. Retired importer/FM1-derived work remains under `archive/importer`
and in the historical visual implementation; existing notices still apply.
