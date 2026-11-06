#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bundle the Max helper without copying local builds, exports or credentials."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
NAME = 'esp32s3-rnbo'
VERSION = '0.1.0'
SOURCES = ('rnbo.studio.maxpat', 'rnbo-studio.js', 'rnbo-studio-client.js', 'embedded-sine.maxpat')

README = """# RNBO ESP32 Studio for Max

Unzip this archive and put the esp32s3-rnbo folder in your Max 9/Packages folder.
On macOS that is ~/Documents/Max 9/Packages. Restart Max after installation.
Launch the package's embedded-sine.maxpat, or Alt/Option-click rnbo.studio for help.

Requires Max with RNBO and Node for Max, plus the separate local RNBO Studio
server and its compiler dependencies. Tested with Max 9.1.4 / RNBO 1.4.4 on macOS.
Start Studio from the project checkout with ./host/studio.sh before building.

Name your rnbo~ object instrument in its Inspector and enable @dumpoutlet 1.
Place rnbo.studio instrument in its surrounding Max patch. Send build to export
the live embedded patch and compile it. Unsaved edits can be included.

upload usb / upload wifi loads this helper's last successful build.
build_upload usb / build_upload wifi builds and then loads on success.
An optional USB port or paired Wi-Fi device ID selects one of several boards.
Wi-Fi must be set up and paired in Studio first. Upload replaces the saved Main
package; player installation remains a separate Studio operation.

The helper's status outlet reports progress and errors. Open displays that exact
job in Studio. Plain build never uploads. Keep Studio running in the background.

Full setup and qualifications:
https://github.com/little-scale/esp32s3-rnbo/blob/main/host/max/README.md

Package layout reference:
https://docs.cycling74.com/userguide/packages/
"""


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def collect(root=ROOT):
    files = {}
    for name in SOURCES:
        source = root / 'host/max' / name
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 2 * 1048576:
            raise ValueError('Expected bounded regular helper source: ' + name)
        files['patchers/' + name] = source.read_bytes()
    license_path = root / 'LICENSES/MIT.txt'
    if license_path.is_symlink() or not license_path.is_file():
        raise ValueError('The integration MIT license is required')
    files['license.txt'] = license_path.read_bytes()
    help_patch = json.loads(files['patchers/embedded-sine.maxpat'])
    for row in help_patch['patcher']['boxes']:
        if row['box']['id'] == 'title':
            row['box']['text'] = 'rnbo.studio — embedded build and upload'
    files['help/rnbo.studio.maxhelp'] = encoded(help_patch)
    files['readme.md'] = README.encode()
    files['package-info.json'] = encoded(dict(name=NAME, displayname='RNBO ESP32 Studio',
        version=VERSION, author='little-scale',
        description='Build embedded RNBO patches and upload packages through local RNBO Studio. Requires RNBO and Studio.',
        tags=['RNBO', 'ESP32', 'USB', 'Wi-Fi'],
        website='https://github.com/little-scale/esp32s3-rnbo',
        max_version_min='9.1.4', max_version_max='none', homepatcher='embedded-sine.maxpat'))
    files['bundle-manifest.json'] = encoded(dict(format='rnbo-max-helper-bundle-v1', version=VERSION,
        files_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}))
    return files


def build(destination, root=ROOT):
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError('The archive destination cannot be a symbolic link')
    files = collect(root)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(NAME + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw, compresslevel=9)
    raw = output.getvalue()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.rnbo-max-', delete=False) as f:
            temporary = Path(f.name)
            f.write(raw)
        temporary.chmod(0o644)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), files=len(files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/dist/esp32s3-rnbo-max.zip')
    args = parser.parse_args()
    print(json.dumps(build(args.out)))
