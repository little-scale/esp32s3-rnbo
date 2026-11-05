# SPDX-License-Identifier: MIT
"""Secondary native sample witnesses; no replacement references or target capture."""
import argparse,hashlib,importlib.util,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'host/compiler'));from build import verify_prepared
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise SystemExit('Choose a fresh output directory')
a.out.mkdir(parents=True);spec=importlib.util.spec_from_file_location('motion_reference',HERE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();authored={v['id']:v for v in json.loads((HERE/'catalog.json').read_text())['cases']};helper=ROOT/'tests/fixtures/smoke/rnbo-codebox-context-aliases/clock_capture.cpp';rows=[]
for identity in('phasor-next','phasor-input-reset','gatetotrig-falling','bline-next','bline-set','bline-reset'):
 src=authored[identity];prepared=a.prepared_root/identity;_,m,_=verify_prepared(prepared);assert m['editable_source_sha256']==src['patch_sha256']and m['numerical_profile']=='float32-strict';d=a.out/identity;d.mkdir()
 command=['c++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(ROOT/'module-sdk/include'),'-I'+str(prepared),'-I'+str(prepared/'common'),str(helper),str(ROOT/'module-sdk/wrapper/rnbo_s3_static.cpp'),'-o',str(d/'capture')]
 with(d/'compile.log').open('wb')as f:subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT)
 inputs=r.case_input_words(src['model']);(d/'inputs.u32').write_bytes(struct.pack('<512I',*inputs));subprocess.run([str(d/'capture'),str(d/'inputs.u32'),str(d/'actual.f32')],check=True,timeout=15)
 actual=struct.unpack('<10240f',(d/'actual.f32').read_bytes());expected=[r.value(w)for b in r.reference_blocks(src['model'],inputs)for w in b];differences=[i for i,(x,y)in enumerate(zip(actual,expected))if abs(x-y)>src['maximum_absolute_error']];selected=sorted(set([0,1,7,8,15,16,37,38,39,255,256,257,333,511,512,513,701,1023,1024]+[i//2 for i in differences[:8]]))
 rows.append(dict(id=identity,scope='Native SDK sample witnesses only; original primary oracle unchanged, no alternate fitted model, Max or full target capture.',capture_sha256=sha(d/'actual.f32'),source_sha256=src['patch_sha256'],helper_sha256=sha(helper),expected_stream_sha256=hashlib.sha256(struct.pack('<10240I',*(r.word(x)for x in expected))).hexdigest(),outside_original_limit=len(differences),max_error=max(abs(x-y)for x,y in zip(actual,expected)),first_mismatch_word=differences[0]if differences else None,witnesses=[dict(frame=n,actual=list(actual[2*n:2*n+2]),expected=expected[2*n:2*n+2])for n in selected]))
 print(identity,'captured',len(selected),'sample witnesses',flush=True)
(a.out/'summary.json').write_text(json.dumps(rows,sort_keys=True,indent=2)+'\n')
