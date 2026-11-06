# Player firmware in RNBO ESP32 Studio

Open [RNBO ESP32 Studio](http://127.0.0.1:8788/) and use **Player firmware** in
the instrument panel. Firmware flashing uses USB and the ESP32-S3 ROM bootloader.
It does not require the unit's previous firmware to answer RNBO commands.

## First install or a unit running another project

1. Connect the XIAO ESP32-S3 or Waveshare AMOLED 1.8 V2 by USB.
2. Select its USB device. You do **not** need to press **Connect USB** first.
3. Choose **First install / replace other firmware**.
4. For a prebuilt bundle, choose **Open firmware ZIP**, then select the full
   RNBO player ZIP for that board. Alternatively expand **Build player firmware
   on this computer**, select the board and use the local build tools.
5. Check the acknowledgement that the selected unit's firmware and data will
   be erased. Press **Erase & install…**, or **Build, erase & install player**.
6. Leave the unit connected through the full backup, erase, writing, readback
   and startup checks. The complete backup can take several minutes.
7. Once the player is verified and running, load your `.rnbopkg` Main patch.
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

Keep **Update RNBO player · keep saved data** selected. Open a firmware ZIP and
press **Update…**, or use **Build & update player**. This mode requires the
existing RNBO partition table to match. It backs up and writes only the factory
application; bootloader, layout, saved Main and Wi-Fi storage stay in place.
Use first install when switching from a different partition layout.

Patch package loading above this section remains separate. Firmware installation
does not compile or automatically load the export selected in the source panel.

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
