# SPDX-License-Identifier: MIT
"""Portable RNBO player firmware bundles; parsing never opens a device."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import stat
import struct
import zipfile

FORMAT = 'rnbo-player-firmware-v1'
FLASH_BYTES = {'xiao': 0x800000, 'amoled': 0x1000000}
APP_OFFSET, APP_CAPACITY = 0x10000, 0x300000
MAX_ZIP = 4 * 1048576
LIMITS = {'firmware.json': 16384, 'application.bin': APP_CAPACITY, 'partition-table.bin': 4096, 'bootloader.bin': 0x8000}
REQUIRED = {'firmware.json', 'application.bin', 'partition-table.bin'}
HASH = re.compile(r'[0-9a-f]{64}')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def metadata(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate firmware metadata field')
            value[key] = item
        return value
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite firmware metadata')))
    except (UnicodeError, RecursionError) as error:
        raise ValueError('Invalid firmware metadata') from error
    keys = {'format', 'player', 'board', 'sample_rate', 'block_frames', 'player_api_version',
            'usb_midi_host', 'firmware_elf_sha256', 'files'}
    if (type(value) is not dict or set(value) != keys or value['format'] != FORMAT
            or value['player'] is not True or type(value['board']) is not str or value['board'] not in FLASH_BYTES
            or type(value['usb_midi_host']) is not bool
            or any(type(value[k]) is not int or value[k] != n for k, n in
                   [('sample_rate', 44100), ('block_frames', 256), ('player_api_version', 1)])
            or not isinstance(value['firmware_elf_sha256'], str)
            or not HASH.fullmatch(value['firmware_elf_sha256'])
            or type(value['files']) is not dict
            or set(value['files']) not in ({'application.bin', 'partition-table.bin'}, {'application.bin', 'partition-table.bin', 'bootloader.bin'})):
        raise ValueError('Choose an RNBO player firmware ZIP made by this project')
    for name, row in value['files'].items():
        if (type(row) is not dict or set(row) != {'bytes', 'sha256'}
                or type(row['bytes']) is not int or not 0 < row['bytes'] <= LIMITS[name]
                or not isinstance(row['sha256'], str) or not HASH.fullmatch(row['sha256'])):
            raise ValueError('Invalid firmware file inventory')
    return value


def image_info(raw, board, *, application=True):
    if (not (288 if application else 32) <= len(raw) <= (APP_CAPACITY if application else 0x8000) or raw[0] != 0xe9 or not 1 <= raw[1] <= 16
            or raw[3] >> 4 != (3 if board == 'xiao' else 4)
            or struct.unpack_from('<H', raw, 12)[0] != 9 or raw[23] != 1):
        raise ValueError('Firmware image must be ESP32-S3 with the matching board flash size')
    if application and struct.unpack_from('<I', raw, 32)[0] != 0xabcd5432:
        raise ValueError('Firmware application descriptor is missing')
    project = raw[80:112].split(b'\0', 1)[0]
    if application and project != ('rnbo_s3_' + board).encode():
        raise ValueError('Firmware image is not for the selected RNBO player board')
    position, checksum = 24, 0xef
    for index in range(raw[1]):
        if position + 8 > len(raw):
            raise ValueError('Truncated firmware segment header')
        _, size = struct.unpack_from('<II', raw, position)
        position += 8
        if not size or position + size > len(raw) or application and index == 0 and size < 256:
            raise ValueError('Truncated or invalid firmware segment')
        for byte in raw[position:position + size]:
            checksum ^= byte
        position += size
    end = ((position + 16) // 16) * 16 - 1
    if (end + 33 != len(raw) or raw[end] != checksum
            or any(raw[position:end]) or hashlib.sha256(raw[:end + 1]).digest() != raw[end + 1:]):
        raise ValueError('Firmware image checksum or appended hash does not match')
    return {'firmware_elf_sha256': raw[176:208].hex()} if application else {}


def partition_info(raw, board):
    if not 32 <= len(raw) <= 4096 or len(raw) % 32:
        raise ValueError('Invalid firmware partition table size')
    factory, regions = [], []
    ended = False
    for offset in range(0, len(raw), 32):
        magic, kind, subtype, address, size, _, _ = struct.unpack_from('<HBBII16sI', raw, offset)
        if magic == 0xebeb:
            if hashlib.md5(raw[:offset]).digest() != raw[offset + 16:offset + 32]:
                raise ValueError('Partition table checksum differs')
            ended = True
            break
        if magic == 0xffff:
            ended = True
            break
        if (magic != 0x50aa or size == 0 or address < 0x9000
                or address + size > FLASH_BYTES[board]
                or any(address < end and start < address + size for start, end in regions)):
            raise ValueError('Invalid or overlapping firmware partition geometry')
        regions.append((address, address + size))
        if kind == 0:
            factory.append((subtype, address, size))
    if not ended or factory != [(0, APP_OFFSET, APP_CAPACITY)]:
        raise ValueError('Firmware requires the reviewed factory application partition')


def check(files):
    if not REQUIRED <= set(files) <= set(LIMITS):
        raise ValueError('Firmware ZIP needs firmware.json, application.bin and partition-table.bin')
    value = metadata(files['firmware.json'])
    if set(value['files']) != set(files) - {'firmware.json'}:
        raise ValueError('Firmware file inventory differs from the archive')
    for name, record in value['files'].items():
        if len(files[name]) != record['bytes'] or digest(files[name]) != record['sha256']:
            raise ValueError('Firmware file hash or size differs: ' + name)
    if image_info(files['application.bin'], value['board'])['firmware_elf_sha256'] != value['firmware_elf_sha256']:
        raise ValueError('Firmware identity differs from its application descriptor')
    partition_info(files['partition-table.bin'], value['board'])
    if 'bootloader.bin' in files:
        image_info(files['bootloader.bin'], value['board'], application=False)
    return value


def unpack(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ZIP:
        raise ValueError('Choose a player firmware ZIP up to 4 MiB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            names = {e.filename for e in entries}
            if len(entries) != len(names) or not REQUIRED <= names <= set(LIMITS):
                raise ValueError('Choose a project player firmware ZIP, rather than a raw BIN or source ZIP')
            files = {}
            for entry in entries:
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if (entry.orig_filename != entry.filename or entry.flag_bits & 1 or mode not in (0, stat.S_IFREG)
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or not 0 < entry.file_size <= LIMITS[entry.filename]):
                    raise ValueError('Linked, encrypted or oversized firmware file')
                with archive.open(entry) as source:
                    data = source.read(LIMITS[entry.filename] + 1)
                if len(data) != entry.file_size:
                    raise ValueError('Firmware file expands beyond its limit')
                files[entry.filename] = data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError('Invalid player firmware ZIP') from error
    return files, check(files)


def create(build, board):
    from tools.run_hardware_test import artifacts
    from tools.build_firmware import source_inventory
    checked = artifacts(Path(build).resolve(), board)
    report = checked['report']
    if report.get('player') is not True or report.get('player_api_version') != 1:
        raise ValueError('Build a supported RNBO player before bundling firmware')
    if report.get('integration_files_sha256') != source_inventory():
        raise ValueError('Player build is older than the current sources; rebuild the player before making its firmware ZIP')
    if 'player_network' not in report.get('components', []):
        raise ValueError('Rebuild the current player with its Wi-Fi component before making a firmware ZIP')
    files = {'application.bin': checked['app'].read_bytes(), 'partition-table.bin': checked['partition'].read_bytes()}
    settings = json.loads((Path(build) / 'flasher_args.json').read_bytes())
    if settings.get('flash_files') != {'0x0':'bootloader/bootloader.bin', '0x10000':str(checked['app'].relative_to(Path(build).resolve())), '0x8000':'partition_table/partition-table.bin'}:
        raise ValueError('Expected the reviewed ESP32-S3 bootloader/partition/application offsets')
    bootloader = Path(build) / 'bootloader/bootloader.bin'
    if bootloader.is_symlink() or not bootloader.is_file() or not 0 < bootloader.stat().st_size <= 0x8000:
        raise ValueError('Missing or invalid player bootloader')
    files['bootloader.bin'] = bootloader.read_bytes()
    value = dict(format=FORMAT, player=True, board=board, sample_rate=44100, block_frames=256,
        player_api_version=1, usb_midi_host=report.get('usb_midi_host', False), firmware_elf_sha256=checked['elf_sha256'],
        files={name: dict(bytes=len(data), sha256=digest(data)) for name, data in files.items()})
    files['firmware.json'] = encoded(value)
    check(files)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return output.getvalue()


def stage(raw, directory):
    files, _ = unpack(raw)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name, data in files.items():
        path = directory / name
        path.write_bytes(data)
        path.chmod(0o400)
    return verify_staged(directory)


def verify_staged(directory, board=None):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('The staged firmware is missing or linked')
    files = {}
    names = {p.name for p in directory.iterdir()}
    if not REQUIRED <= names <= set(LIMITS):
        raise ValueError('Unexpected staged firmware files')
    for name in names:
        limit = LIMITS[name]
        path = directory / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise ValueError('The staged firmware file is missing, linked or oversized')
        files[name] = path.read_bytes()
    value = check(files)
    if board is not None and value['board'] != board:
        raise ValueError('Firmware does not match the selected board')
    return dict(report=value, report_sha256=digest(files['firmware.json']),
        app=directory / 'application.bin', partition=directory / 'partition-table.bin',
        bootloader=directory / 'bootloader.bin' if 'bootloader.bin' in files else None,
        elf_sha256=value['firmware_elf_sha256'])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--board', required=True, choices=tuple(FLASH_BYTES))
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    raw = create(args.build, args.board)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    print(json.dumps(dict(bytes=len(raw), sha256=digest(raw))))
