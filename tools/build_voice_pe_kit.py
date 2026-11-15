#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package checked local Voice PE test builds. No USB, network or flashing."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host.voice_pe_firmware import build_plan
from host.compiler.package import parse

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(rate,out_root):
    profile=f'voice-pe-{rate}-256-v1';firmware=ROOT/f'build/firmware-voice-pe-player-{rate}'
    plan=build_plan(firmware,profile)
    identity_inputs=[firmware/'build-report.json',ROOT/'docs/voice-pe.md',Path(__file__),
                     ROOT/f'build/private/voice-pe-native/sine-{rate}.rnbopkg',
                     ROOT/f'build/private/voice-pe-composite/controls-{rate}.rnbopkg',
                     *[ROOT/'host/max'/name for name in ('voice-pe-controls.maxpat','rnbo.studio.maxpat','rnbo-studio.js','rnbo-studio-client.js')]]
    led_package=ROOT/f'build/private/voice-pe-led/led-{rate}.rnbopkg'
    identity_inputs += [ROOT/'docs/voice-pe-leds.md',ROOT/'host/max/voice-pe-led.maxpat']
    if led_package.is_file():identity_inputs.append(led_package)
    identity=hashlib.sha256(''.join(digest(p) for p in identity_inputs).encode()).hexdigest()
    folder=out_root/f'voice-pe-{rate}-hardware-test-{plan["app_sha256"][:10]}-{identity[:6]}'
    if folder.exists():raise ValueError('Use a fresh output root or retain the existing checked kit')
    folder.mkdir(parents=True)
    sources={
        'rnbo_s3_voice-pe.bin':Path(plan['app']),
        'partition_table/partition-table.bin':Path(plan['table']),
        'build-report.json':firmware/'build-report.json',
        'sine.rnbopkg':ROOT/f'build/private/voice-pe-native/sine-{rate}.rnbopkg',
        'controls.rnbopkg':ROOT/f'build/private/voice-pe-composite/controls-{rate}.rnbopkg',
        'VOICE-PE.md':ROOT/'docs/voice-pe.md',
        'GPL-3.0.txt':ROOT/'LICENSES/Voice-PE-GPL-3.0.txt',
        'LED-RING.md':ROOT/'docs/voice-pe-leds.md',
        'max/voice-pe-led.maxpat':ROOT/'host/max/voice-pe-led.maxpat',
    }
    if led_package.is_file():sources['led.rnbopkg']=led_package
    for name in ('voice-pe-controls.maxpat','rnbo.studio.maxpat','rnbo-studio.js','rnbo-studio-client.js'):
        sources['max/'+name]=ROOT/'host/max'/name
    for name in ('sine.rnbopkg','controls.rnbopkg',*(['led.rnbopkg'] if led_package.is_file() else [])):
        package=parse(sources[name].read_bytes())
        if package['profile']!=profile or package['metadata']['initial_volume']!=0:
            raise ValueError('Test packages must match the selected native profile and start at zero volume')
    for name,source in sources.items():
        target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    readme=f'''Voice PE RNBO hardware-test kit: {profile}

NOT HARDWARE QUALIFIED. Matching XMOS clocks/image are required.
Never use idf.py flash, erase_flash or the generic AMOLED/XIAO installer.
No bootloader image or flash backup is included here.

From the matching source checkout, review the offline protected plan:
python3 host/voice_pe_firmware.py --build-dir "{folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder}" --profile {profile}

The explicit flash form additionally needs --flash --port <exact-port>
--mac <12-digit-mac> --confirm-xmos-profile {profile}.
Confirm the separately verified XMOS pair before using it. This writes ESP only.

After installation, inspect player-info and clocks before testing sound.
Open sine.rnbopkg or controls.rnbopkg in a freshly restarted Studio.
Both start at 0% volume. If paused, Resume; start at 5% master for the listening check.
For controls: hold the centre button to gate audio; dial changes frequency;
microphone-mute is read separately. Ordinary patches keep the board-owned ring.
The LED example uses outport led_rgb; see LED-RING.md. If included, led.rnbopkg
is silent and its test parameter selects shared/indexed/full-frame updates.
Saved packages restore paused. See VOICE-PE.md for the complete hardware checklist.
'''
    (folder/'README.txt').write_text(readme)
    files={p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in folder.rglob('*') if p.is_file()}
    receipt=dict(format='rnbo-voice-pe-hardware-test-kit-v1',profile=profile,sample_rate=rate,block_frames=256,
                 hardware_qualified=False,source_profile_checked=True,files=files,
                 initial_volume=0,requires_matching_xmos=True,installation='protected-esp-only')
    (folder/'kit.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    archive=folder.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(folder))
    # Validate the staged app/table again, not only their original paths.
    build_plan(folder,profile)
    return dict(directory=str(folder.relative_to(ROOT)),zip=str(archive.relative_to(ROOT)),
                zip_sha256=digest(archive),zip_bytes=archive.stat().st_size,profile=profile)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'build/dist')
    a=p.parse_args();print(json.dumps([build(rate,a.out.resolve()) for rate in (16000,48000)],indent=2))
