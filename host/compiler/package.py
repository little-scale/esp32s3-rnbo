#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create/read checked player packages. Never opens a device.

Envelope v2 uses the same layout, but requires physical_inputs v1 support. Old
players reject it instead of silently running an input-bound patch unbound.
Ordinary packages retain the original v1 envelope byte for byte.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

try:
    from .inspect_module import inspect_module
    from .physical_inputs import checked_plan
except ImportError:
    from inspect_module import inspect_module
    from physical_inputs import checked_plan

MAGIC = b'RNBOS3P1'
HEADER = struct.Struct('<8s9I32s32s20s')
MAX_METADATA, MAX_ELF = 65536, 524288
ROLES = {'main': 1}
HASH = re.compile(r'[0-9a-f]{64}')


def trial_checked(value):
    keys = {'version','profile','qualification','audit_sha256','trial_method_count','reviewed_method_count','skipped_method_count'}
    if (type(value) is not dict or set(value) != keys or type(value['version']) is not int or value['version'] != 1
            or value['profile'] != 'float32-trial-v1' or value['qualification'] != 'unverified'
            or not isinstance(value['audit_sha256'], str) or not HASH.fullmatch(value['audit_sha256'])
            or any(type(value[k]) is not int or not 0 <= value[k] <= 65536
                   for k in ('trial_method_count','reviewed_method_count','skipped_method_count'))):
        raise ValueError('Invalid experimental Float32 trial summary')
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata_checked(value):
    if type(value) is not dict:
        raise ValueError('Package metadata must be an object')
    name, source, volume = (value.get(key) for key in ('name', 'source_sha256', 'initial_volume'))
    if (not isinstance(name, str) or not 1 <= len(name.encode('utf-8')) <= 63 or '\0' in name
            or not isinstance(source, str) or not HASH.fullmatch(source)
            or type(volume) is not int or not 0 <= volume <= 100):
        raise ValueError('Invalid package name, source identity or initial volume')
    if 'physical_inputs' in value:
        checked_plan(value['physical_inputs'])
    if 'float32_trial' in value:
        trial_checked(value['float32_trial'])
    if 'midi_input_ports' in value and (type(value['midi_input_ports']) is not int or value['midi_input_ports']!=1):
        raise ValueError('MIDI input packages must declare exactly one port')
    return value


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('Duplicate package metadata key')
            result[key] = value
        return result
    def nonfinite(_value):
        raise ValueError('Nonfinite package JSON')
    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            nonfinite(value)
        return parsed
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=nonfinite, parse_float=number)


def create(elf, metadata, role, arena_bytes):
    metadata_checked(metadata)
    if role not in ROLES or type(arena_bytes) is not int or not 4096 <= arena_bytes <= 4194304:
        raise ValueError('Package role/arena is outside the v1 contract')
    inspection = inspect_module(elf, allowed_imports=set())
    if inspection['imports']:
        raise ValueError('Player modules must have zero imports')
    raw = json.dumps(metadata, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_METADATA or len(elf) > MAX_ELF:
        raise ValueError('Package payload exceeds the v1 limits')
    version = 2 if 'physical_inputs' in metadata else 1
    return HEADER.pack(MAGIC, 128, version, 1, ROLES[role], 44100, 256, arena_bytes,
                       len(raw), len(elf), hashlib.sha256(elf).digest(), hashlib.sha256(raw).digest(), bytes(20)) + raw + elf


def parse(raw):
    if not isinstance(raw, bytes) or len(raw) < 128:
        raise ValueError('Truncated package')
    magic, header, version, abi, role, rate, frames, arena, meta_len, elf_len, elf_hash, meta_hash, padding = HEADER.unpack_from(raw)
    if (magic != MAGIC or (header, abi, rate, frames) != (128, 1, 44100, 256) or version not in (1, 2)
            or role not in ROLES.values() or not 4096 <= arena <= 4194304 or padding != bytes(20)
            or not 0 < meta_len <= MAX_METADATA or not 0 < elf_len <= MAX_ELF
            or len(raw) != 128 + meta_len + elf_len):
        raise ValueError('Invalid package header or payload lengths')
    meta_raw, elf = raw[128:128+meta_len], raw[128+meta_len:]
    if hashlib.sha256(meta_raw).digest() != meta_hash or hashlib.sha256(elf).digest() != elf_hash:
        raise ValueError('Package checksum mismatch')
    metadata = metadata_checked(strict_json(meta_raw))
    if (version == 2) != ('physical_inputs' in metadata):
        raise ValueError('Physical-input packages require envelope v2; ordinary packages require v1')
    inspection = inspect_module(elf, allowed_imports=set())
    if inspection['imports']:
        raise ValueError('Player modules must have zero imports')
    return dict(role=next(key for key, value in ROLES.items() if value == role), arena_bytes=arena,
                metadata=metadata, elf=elf, elf_sha256=elf_hash.hex(), package_sha256=digest(raw))


def build(build_dir, output, name, initial_volume=50, visual=None):
    directory = Path(build_dir).resolve()
    report = json.loads((directory / 'build-report.json').read_text())
    if (report.get('format') != 'rnbo-esp32s3-dynamic-module-build' or report.get('format_version') != 1
            or report.get('imports') != [] or report.get('dynamic_abi', {}).get('major') != 1
            or (report.get('sample_rate'), report.get('block_frames')) != (44100, 256)):
        raise ValueError('Not a zero-import ABI1 module build')
    artifact = report['artifact']
    supplied = Path(artifact['path'])
    path = supplied.resolve()
    if not path.is_relative_to(directory) or supplied.is_symlink():
        raise ValueError('Module artifact is outside its build')
    elf = path.read_bytes()
    if type(artifact.get('bytes')) is not int or artifact['bytes'] != len(elf) or artifact.get('sha256') != digest(elf):
        raise ValueError('Module artifact changed after compilation')
    manifest = report['prepared_export']['manifest']
    role = report['role']
    if (role not in ROLES or manifest.get('role') != role or manifest.get('sample_rate') != 44100
            or manifest.get('block_frames') != 256 or type(manifest.get('audio_inputs')) is not int
            or manifest['audio_inputs'] != (0 if role == 'main' else 2) or manifest.get('audio_outputs') != 2):
        raise ValueError('Module dimensions do not match the requested player role')
    metadata = dict(name=name, source_sha256=manifest['source_tree_sha256'], initial_volume=initial_volume)
    if manifest.get('midi_input_ports'):
        if type(manifest['midi_input_ports']) is not int or manifest['midi_input_ports']!=1:
            raise ValueError('Only MIDI input port0 is supported')
        metadata['midi_input_ports']=1
    if 'physical_inputs' in manifest:
        metadata['physical_inputs'] = checked_plan(manifest['physical_inputs'])
    if manifest.get('numerical_profile') == 'float32-trial-v1':
        metadata['float32_trial'] = trial_checked(manifest.get('float32_trial'))
        suffix = ' [Float32 trial]'
        metadata['name'] = name.encode('utf-8')[:63-len(suffix)].decode('utf-8', 'ignore') + suffix
    elif 'float32_trial' in manifest:
        raise ValueError('Trial metadata requires the Float32 trial profile')
    if visual is not None:
        metadata['visual'] = visual
    arena = report['state_policy']['maximum_arena_bytes']
    raw = create(elf, metadata, role, arena)
    output = Path(output)
    output.write_bytes(raw)
    return dict(format='rnbo-player-package-v2' if 'physical_inputs' in metadata else 'rnbo-player-package-v1', path=str(output.resolve()), bytes=len(raw),
                sha256=digest(raw), elf_sha256=digest(elf), role=role, arena_bytes=arena,
                metadata=metadata, module_report_sha256=digest((directory / 'build-report.json').read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--initial-volume', type=int, default=50)
    args = parser.parse_args()
    try:
        result = build(args.build_dir, args.out, args.name, args.initial_volume)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
