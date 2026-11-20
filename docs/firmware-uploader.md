# Player firmware in RNBO ESP32 Studio

Open [RNBO ESP32 Studio](http://127.0.0.1:8788/) and choose a task at the top of the
**Instrument** panel. Use **First install** for a new board or to replace other
firmware, **Update player** for an existing RNBO player, or **Load & play** to load
a patch package. Both firmware paths use the ESP32-S3 ROM bootloader over USB.

## Choose the current player

Use **Current player firmware** to choose **XIAO ESP32-S3 · 16 kHz / 256**,
**XIAO ESP32-S3 · 44.1 kHz / 256**, or the Waveshare AMOLED
1.8 V2 player directly. All include USB, Wi-Fi, OSC parameters and web controls; the current
AMOLED player also includes patch-area touchscreen parameter bindings. Selection
prepares a checked bundle and displays its build date and firmware identity;
press the separate **Update player firmware** or **Erase & install player** button to flash it.

“Current” means the normal `player-v1` build matching the sources in this local
checkout, rather than a downloaded GitHub release. **Refresh** rechecks the
three board/rate builds. Missing, changed or stale builds appear as **build
required**, with a reason. You can use **Build player from source** to build and
flash the default 44.1 kHz player in one step. Experimental USB-host firmware is not a default option. **Open firmware ZIP** remains
available for supplied files.

Listing and selection do not compile, connect to or flash a board. Selection
checks the displayed bundle's hash again and asks you to refresh if it changed.
Refreshing to a different build clears any earlier current selection and erase
acknowledgement. The existing USB identity, backup and readback checks still
apply when you explicitly start installation.

For an ordinary single-runtime XIAO already running RNBO, select **Update player →
Current player firmware → XIAO ESP32-S3 · 16 kHz / 256**. Then click
**Update player firmware**. This preserves the factory partition layout, Wi-Fi
settings and stored files. Load a matching 16 kHz package afterwards; an old
44.1 kHz package cannot run at the new rate. Selecting a patch audio profile alone
does not flash firmware. For a commissioned SC/RNBO pair, use **SC / RNBO →
Update RNBO slot** instead; the ordinary updater rejects paired layouts.

## First install or a unit running another project

1. Connect the XIAO ESP32-S3 or Waveshare AMOLED 1.8 V2 by USB.
2. Choose **First install**, then select the USB device in step 1. The firmware
   path is ready once USB detects the board, even if its existing firmware is blank or unrelated.
3. In step 2, choose your board under **Current player firmware** or use
   **Open firmware ZIP** to select a supplied full RNBO player ZIP.
4. In step 3, confirm that the selected device will be erased and click
   **Erase & install player**. For a local build instead, select the board under
   **Build player from source**, confirm the erase, and click **Build, erase & install player**.
5. Leave the unit connected through the full backup, erase, writing, readback
   and startup checks. The complete backup can take several minutes.
6. Once the player is verified and running, choose **Load & play** to connect and load your `.rnbopkg` Main patch.
   Set up and pair Wi-Fi again if you want wireless package uploads.

**First install erases all existing firmware and stored data**, including
previous patches and Wi-Fi settings. The acknowledgement resets after changing
the USB target, board, installation mode or firmware file, and after submission.
Nothing is flashed just by opening a file or selecting this mode.

If the device does not appear, hold **BOOT**, tap **RESET**, then release BOOT
and refresh the USB list. Holding BOOT while connecting USB is another option.
See the [Seeed XIAO instructions](https://wiki.seeedstudio.com/noport_upload_fails/)
and [Espressif's ESP32-S3 boot-mode guide](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/advanced-topics/boot-mode-selection.html).
For the AMOLED board, also see [Waveshare's flashing guide](https://docs.waveshare.com/ESP32-S3-Touch-AMOLED-1.8/Firmware-Flashing).

## Updating an existing RNBO player

Choose **Update player**, select your USB device and firmware, then click
**Update player firmware** or use **Build & update player**. This mode requires the
existing RNBO partition table to match. It backs up and writes only the factory
application; bootloader, layout, saved Main and Wi-Fi storage stay in place.
Use first install when switching from a different partition layout.

Use **Load & play** to load a patch package after firmware installation.

## Making a portable firmware ZIP

Build a player using `tools/build_firmware.py` or Studio's local-build option.
Then package the completed build:

```sh
python3 -m host.studio.firmware \
  --build build/firmware-xiao-player-player-v1 \
  --board xiao --out build/dist/xiao-player-firmware.zip

python3 -m host.studio.firmware \
  --build build/firmware-amoled-player-player-v1 \
  --board amoled --out build/dist/amoled-player-firmware.zip
```

The recipient needs Studio, pyserial and esptool for flashing; a C++ compiler,
Max and RNBO are not required for a supplied ZIP. Studio's launcher uses the
installed ESP-IDF Python environment when available. Building firmware locally
still needs the existing ESP-IDF/compiler dependencies and AMOLED components.

The ZIP builder rejects builds whose source inventory differs from the current
checkout, and requires the player's Wi-Fi component. Rebuild before packaging
an older cached build. Importing a previously supplied ZIP remains independent
of the recipient's source checkout.

A full ZIP contains `firmware.json`, `bootloader.bin`, `partition-table.bin` and
`application.bin`. The builder verifies the existing build report and ELF hash,
then records portable file sizes/hashes and the embedded application identity.
Earlier three-file bundles without a bootloader work for updates only. Raw BINs,
Max export ZIPs and `.rnbopkg` patch files are different formats and are rejected.
Use trusted project firmware; integrity hashes do not authenticate its publisher.

## Backup and verification

The physical USB MAC, ESP32-S3 chip and 8 MiB XIAO / 16 MiB AMOLED flash capacity
are checked before destructive work and again after backup. Update makes a
3 MiB application backup. First install makes an 8/16 MiB complete backup before
erase and writes only bootloader `0x0`, partition table `0x8000` and player
application `0x10000`. The board stays in download mode until image readbacks
finish, so a missing or broken old application need not boot between operations.

Private backups, bounded tool logs and receipts are retained beneath
`build/private/studio/uploads/<operation-id>/`. Full backups can contain
credentials and other previous project data: keep them private. The operation's
output identifies its receipt and backup. Failed erase/write operations are not
automatically retried or labelled successful; an automatic rollback is not run.

Success requires byte-hash readback verification, the expected running player
firmware identity, advancing audio frames and clean runtime counters. First
install checks all three written images; update checks the application. These
checks do not establish DAC output or listening quality.

Both modes are covered by real bridge code with simulated ROM/serial devices,
including both flash capacities, non-RNBO old firmware, short backups, device
replacement, corrupt readback and failed erase. Real project images for both
boards pass the bundle parser. A user-initiated physical AMOLED first install
also passed: a complete 16 MiB backup preceded erase; bootloader, partition table
and application readbacks matched; the expected player booted with advancing
audio frames and clean runtime counters. The new player has no Main patch loaded.
Physical XIAO first install and DAC/listening confirmation remain pending. See the
[hardware receipt](../evidence/studio-firmware-uploader.json).

### Installing the OSC/browser-capable player

If installation reports **USB port in use**, disconnect the board in SynthDef
Studio, Max or any serial monitor before retrying. Only one application can own
its USB serial port. RNBO Studio releases its own USB session before flashing;
it does not close other applications' connections automatically. A failure at
the initial `flash_id` step happens before erase/write; the private receipt
records whether any later write was attempted.

The current XIAO/AMOLED selector uses the normal `build/firmware-<board>-player`
builds, including OSC input and the lightweight board parameter page when rebuilt
from current sources. Generated ZIPs still require explicit USB installation.
For a commissioned XIAO SynthDef/RNBO pair, Studio's [SC / RNBO section](xiao-dual-boot-studio.md)
uses the companion guarded updater at 16 or 44.1 kHz. Other paired boards use
the companion tools directly, with the exact board/rate image instead of a
factory/erase installation. In particular,
AMOLED's smaller paired application slot is close to capacity; retain the updater's
exact-size/provenance checks. See the [OSC/web guide](osc-parameters.md).
