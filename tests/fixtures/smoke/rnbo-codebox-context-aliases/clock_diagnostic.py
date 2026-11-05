# SPDX-License-Identifier: MIT
"""Secondary native callback-held clock diagnosis; primary oracle is unchanged."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'host/compiler'))
from build import verify_prepared
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh diagnostic output directory')
a.out.mkdir(parents=True)
spec=importlib.util.spec_from_file_location('clock_ref',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={v['id']:v for v in json.loads((HERE/'catalog.json').read_bytes())['cases']};rows=[]
for identity in('currenttime','sampleoffset','currentsampletime'):
 src=sources[identity];model=src['model'];prepared=a.prepared_root/identity;_,manifest,_=verify_prepared(prepared);assert manifest['editable_source_sha256']==src['patch_sha256']and manifest['numerical_profile']=='float32-strict'
 d=a.out/identity;d.mkdir();command=['c++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(ROOT/'module-sdk/include'),'-I'+str(prepared),'-I'+str(prepared/'common'),str(HERE/'clock_capture.cpp'),str(ROOT/'module-sdk/wrapper/rnbo_s3_static.cpp'),'-o',str(d/'capture')]
 with(d/'compile.log').open('wb')as f:subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT)
 inputs=r.case_input_words(model);(d/'inputs.u32').write_bytes(struct.pack('<512I',*inputs));subprocess.run([str(d/'capture'),str(d/'inputs.u32'),str(d/'actual.f32')],check=True,timeout=10)
 actual=struct.unpack('<10240f',(d/'actual.f32').read_bytes());primary=[r.value(w)for b in r.reference_blocks(model,inputs)for w in b];secondary=[]
 for call in range(20):
  # Alternative diagnostic, explicitly not substituted for the fixed primary.
  value=call*256*1000/44100 if identity=='currenttime'else 0 if identity=='sampleoffset'else call*256
  for frame in range(256):secondary.extend((r.value(r.word(value)),r.value(inputs[2*frame+1])))
 errors=[abs(x-y)for x,y in zip(actual,secondary)];old_errors=[abs(x-y)for x,y in zip(actual,primary)];limit=src['maximum_absolute_error']
 rows.append(dict(id=identity,scope='Secondary native SDK capture: compare callback-held interpretation, not a replacement primary oracle or actual Max/target capture.',frames=5120,capture_sha256=sha(d/'actual.f32'),source_sha256=src['patch_sha256'],prepared_source_sha256=sha(prepared/'rnbo_source.h'),input_words_sha256=sha(d/'inputs.u32'),helper_sha256=sha(HERE/'clock_capture.cpp'),original_per_sample_max_error=max(old_errors),original_per_sample_numeric_mismatches=sum(e>limit for e in old_errors),callback_held_max_error=max(errors),callback_held_outside_original_limit=sum(e>limit for e in errors)))
 print(json.dumps(rows[-1]),flush=True)
(a.out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
