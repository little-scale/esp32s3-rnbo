#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render the actual firmware UI with pinned native LVGL and a mocked BSP."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host/visual'))
from layout import write_layout


def png(path,data):
    def chunk(kind,raw):return struct.pack('>I',len(raw))+kind+raw+struct.pack('>I',zlib.crc32(kind+raw))
    raw=b''.join(b'\0'+data[y*368*3:(y+1)*368*3] for y in range(448))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',368,448,8,2,0,0,0))+
                     chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--title',default='RNBO Patch')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    prepared=args.prepared.resolve()
    report=write_layout(prepared/'source.rnbopat' if (prepared/'source.rnbopat').exists() else None,
                        prepared/'description.json',out/'metadata',args.title)
    desc=json.loads((prepared/'description.json').read_text())
    parameters=desc['parameters'];actual=[p['initialValue'] for p in parameters]
    # The parameter picture uses actual defaults. Only a normalized marker is
    # needed for presentation; the real firmware gets normalization from RNBO.
    normalized=[((p['initialValue']-p['minimum'])/(p['maximum']-p['minimum']))**(1/p['exponent']) for p in parameters]
    (out/'metadata/preview_parameters.h').write_text('static float actual_values[] = {'+','.join(map(str,actual or [0]))+'};\n'+
        'static float normalized_values[] = {'+','.join(map(str,normalized or [0]))+'};\n')
    def sources():
        files=[p for directory in ('firmware/components/board_display','host/visual','tests/visual/native')
               for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        files.append(Path(__file__))
        return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    source_hashes=sources()
    with (out/'build.log').open('w') as log:
        for command in (['cmake','-S',str(ROOT/'tests/visual/native'),'-B',str(out/'native'),f'-DRNBO_ROOT={ROOT}',f'-DVISUAL_DIR={out/"metadata"}'],
                        ['cmake','--build',str(out/'native'),'--target','patch_preview','--parallel','4']):
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    result=subprocess.run([str(out/'native/patch_preview'),str(out)],check=True,capture_output=True,text=True)
    if sources()!=source_hashes:raise ValueError('UI source changed during preview build')
    (out/'checks.json').write_text(result.stdout)
    images=[]
    for source in out.glob('*.rgb'):
        data=source.read_bytes()
        if len(data)!=368*448*3:raise ValueError('Preview framebuffer length mismatch')
        target=source.with_suffix('.png');png(target,data);images.append(str(target))
    report['preview_images']=images
    report['sources_sha256']=source_hashes
    report['renderer_sha256']=hashlib.sha256((out/'native/patch_preview').read_bytes()).hexdigest()
    (out/'preview-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'images':images,'checks':json.loads(result.stdout)}))


if __name__=='__main__':main()
