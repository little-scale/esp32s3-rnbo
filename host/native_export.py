# SPDX-License-Identifier: MIT
"""Admit complete Cycling '74 Minimal C++ exports without translating patches.

Generated C++ is trusted local executable input. Paths and sizes are bounded;
semantic/runtime admission remains the preparer's responsibility.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 32 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_FILES = 1024
GUIDANCE = 'Export C++ from RNBO in Max with Minimal Export, Copy Library, fixed 44100 Hz and 256 frames. Open that folder or ZIP; .rnbopat is optional drawing data only.'


def path_name(value):
    if (not isinstance(value, str) or not value or len(value) > 512 or '\\' in value
            or '\x00' in value or any(part in ('', '.', '..') for part in value.split('/'))
            or PurePosixPath(value).is_absolute() or ':' in value):
        raise ValueError('Invalid export-relative path')
    return value


def decode(value, limit):
    if not isinstance(value, str) or len(value) > 4 * ((limit + 2) // 3):
        raise ValueError('Export encoding exceeds its size limit')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('Invalid export encoding') from error
    if len(raw) > limit:
        raise ValueError('Export file exceeds its size limit')
    return raw


def unpack(data):
    """Return bounded bytes from a browser directory selection or ZIP."""
    files = {}
    total = 0
    def add(name, raw):
        nonlocal total
        name = path_name(name)
        if name in files:
            raise ValueError('Duplicate export path')
        total += len(raw)
        if len(files) >= MAX_FILES or len(raw) > MAX_FILE or total > MAX_BYTES:
            raise ValueError('Export exceeds the 1024-file / 32 MiB limit')
        files[name] = raw
    if 'zip_base64' in data:
        if 'export_files' in data:
            raise ValueError('Choose one export folder or ZIP')
        raw = decode(data['zip_base64'], MAX_BYTES)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist()) > MAX_FILES:
                    raise ValueError('Too many ZIP entries')
                declared = 0
                for entry in archive.infolist():
                    path_name(entry.filename.rstrip('/'))
                    mode = entry.external_attr >> 16
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                        raise ValueError('Linked or special ZIP entries are not accepted')
                    if entry.flag_bits & 1:
                        raise ValueError('Encrypted ZIPs are not accepted')
                    declared += entry.file_size
                    if entry.file_size > MAX_FILE or declared > MAX_BYTES:
                        raise ValueError('Expanded ZIP exceeds its size limit')
                    if not entry.is_dir():
                        add(entry.filename, archive.read(entry))
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, zlib.error) as error:
            raise ValueError('Unreadable export ZIP') from error
    else:
        rows = data.get('export_files')
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES:
            raise ValueError(GUIDANCE)
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'path', 'data_base64'}:
                raise ValueError('Expected export-relative paths and file contents')
            add(row['path'], decode(row['data_base64'], MAX_FILE))
    return files


def normalise(files):
    """Locate one export root; preserve header/common bytes, detect its class."""
    files = {name: raw for name, raw in files.items()
             if not any(part == '__MACOSX' or part.startswith('._') or part == '.DS_Store'
                        for part in PurePosixPath(name).parts)}
    roots = [name[:-len('description.json')] for name in files
             if PurePosixPath(name).name == 'description.json']
    if len(roots) != 1:
        raise ValueError('Choose exactly one Minimal Export folder containing description.json')
    prefix = roots[0]
    if any(not name.startswith(prefix) for name in files):
        raise ValueError('ZIP contains files outside the export folder')
    files = {name[len(prefix):]: raw for name, raw in files.items()}
    headers = []
    for name, raw in files.items():
        if '/' not in name and name.endswith('.h'):
            classes = re.findall(rb'template\s*<[^>]*>\s*class\s+([A-Za-z_][A-Za-z_0-9]*)\s*:', raw)
            if len(classes) == 1:
                headers.append((name, classes[0].decode('ascii')))
    if len(headers) != 1:
        raise ValueError('Expected one generated Minimal Export template header. ' + GUIDANCE)
    header, class_name = headers[0]
    for name in files:
        if (name not in (header, 'description.json', 'dependencies.json', 'source.rnbopat', 'RNBO-runtime-LICENSE', 'LICENSE')
                and not (name.startswith('common/') and (name.endswith(('.h', '.hpp', '.cpp'))
                    or PurePosixPath(name).name.lower().startswith(('license', 'copying'))))):
            raise ValueError('Unsupported export file or external asset: ' + name)
    if json.loads(files.get('dependencies.json', b'[]')) not in ([], {}):
        raise ValueError('External export dependencies are not supported by this player')
    if 'common/RNBO_Version.h' not in files:
        raise ValueError('Missing common/ runtime headers; enable Copy Library in Max')
    if not re.search(rb'const char \* version = "1\.4\.4";', files['common/RNBO_Version.h']):
        raise ValueError('This adapter currently qualifies RNBO runtime 1.4.4 only')
    files['rnbo_source.h'] = files.pop(header)
    if 'RNBO-runtime-LICENSE' not in files and 'LICENSE' not in files:
        files['RNBO-runtime-LICENSE'] = (ROOT / 'LICENSES/RNBO-runtime-LICENSE').read_bytes()
    return files, class_name


def write(files, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        target = destination / path_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path, help='Max Minimal Export directory or ZIP')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.export.is_symlink():
            raise ValueError('Linked input is not accepted')
        if args.export.is_dir():
            rows = []
            total = 0
            for path in sorted(args.export.rglob('*')):
                if path.is_symlink():
                    raise ValueError('Linked export files are not accepted')
                if path.is_file():
                    total += path.stat().st_size
                    if path.stat().st_size > MAX_FILE or total > MAX_BYTES or len(rows) >= MAX_FILES:
                        raise ValueError('Export exceeds its size limit')
                    rows.append(dict(path=path.relative_to(args.export).as_posix(), data_base64=base64.b64encode(path.read_bytes()).decode()))
            payload = {'export_files': rows}
        else:
            if args.export.stat().st_size > MAX_BYTES:
                raise ValueError('ZIP exceeds its size limit')
            payload = {'zip_base64': base64.b64encode(args.export.read_bytes()).decode()}
        files, class_name = normalise(unpack(payload))
        write(files, args.out)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({'export': str(args.out.resolve()), 'class_name': class_name, 'source': 'cycling74-minimal-export'}))


if __name__ == '__main__':
    main()
