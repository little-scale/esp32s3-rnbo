# SPDX-License-Identifier: MIT
"""Reproducible secondary native diagnosis; source-only, never a target oracle."""
from pathlib import Path
import json,struct,subprocess,importlib.util,math,hashlib
import argparse,sys
fixture=Path(__file__).resolve().parent
root=fixture.parents[3]
sys.path.insert(0,str(root/'host/compiler'))
from build import verify_prepared
parser=argparse.ArgumentParser(description='Separate native window-selector diagnosis; never replaces the primary per-sample reference.')
parser.add_argument('--prepared-root',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
if args.out.exists():raise SystemExit('Choose a fresh diagnostic output directory')
args.out.mkdir(parents=True)
spec=importlib.util.spec_from_file_location('r',fixture/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
authored={v['id']:v for v in json.loads((fixture/'catalog.json').read_bytes())['cases']}

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for model in(1819,1820,1821):
 owner,variant=r.row(model);identity=owner+'-'+variant;prepared=args.prepared_root/identity;d=args.out/identity;d.mkdir();_,manifest,_=verify_prepared(prepared);assert manifest['editable_source_sha256']==authored[identity]['patch_sha256']and manifest['numerical_profile']=='float32-strict'
 command=['c++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(prepared),'-I'+str(prepared/'common'),str(fixture/'window_diagnostic.cpp'),'-o',str(d/'capture')]
 with(d/'compile.log').open('wb')as f:subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT)
 source=(prepared/'rnbo_source.h').read_text();start=source.index('void codebox_tilde_01_perform(');end=source.index('\nvoid stackprotect_perform',start);body=source[start:end]
 selector_before=(body.index('number wl =')<body.index('for (i = 0; i < 256; i++)') and body.index('number wr =')<body.index('for (i = 0; i < 256; i++)'))
 inputs=r.case_input_words(model);inputfile=d/'inputs.u32';inputfile.write_bytes(struct.pack('<512I',*inputs))
 subprocess.run([str(d/'capture'),str(inputfile),str(d/'actual.f32')],check=True,timeout=10)
 actual=struct.unpack('<10240f',(d/'actual.f32').read_bytes());primary=tuple(r.value(w)for b in r.reference_blocks(model,inputs)for w in b)
 pairs=[tuple(map(r.value,inputs[i:i+2]))for i in range(0,512,2)];epochs=[0,0];previous=[None,None];secondary=[]
 for age in range(5120):
  for ch in(0,1):
   # Diagnostic policy deliberately differs: state-only selector evaluated once
   # at callback entry. It does not replace the frozen per-sample oracle.
   w=r.window_at((age//256)*256,ch,True)
   if w!=previous[ch]:epochs[ch]=age
   previous[ch]=w;values=[pairs[k%256][ch]for k in range(max(epochs[ch],age-w+1),age+1)]
   if owner=='average_absolute':values=[abs(x)for x in values]
   if owner=='average_rms':values=[x*x for x in values]
   v=math.fsum(values)/len(values);secondary.append(r.value(r.word(math.sqrt(v)if owner=='average_rms'else v)))
 differences=[abs(a-b)for a,b in zip(actual,secondary)];primary_differences=[abs(a-b)for a,b in zip(actual,primary)]
 primary_within=sum(0<e<=2e-6 for e in primary_differences);primary_outside=sum(e>2e-6 for e in primary_differences)
 rows.append(dict(id=identity,scope='Secondary native direct-producer diagnostic only; not a replacement target oracle.',capture_sha256=sha(d/'actual.f32'),prepared_source_sha256=sha(prepared/'rnbo_source.h'),input_words_sha256=sha(inputfile),helper_sha256=sha(fixture/'window_diagnostic.cpp'),frames=5120,original_per_sample_max_error=max(primary_differences),original_per_sample_numeric_mismatches=primary_outside,original_per_sample_within_tolerance=primary_within,block_held_selector_max_error=max(differences),block_held_selector_outside_2e6=sum(e>2e-6 for e in differences),selector_in_producer_before_sample_loop=selector_before,perform_method_sha256=hashlib.sha256(body.encode()).hexdigest()))
 print(identity,rows[-1],flush=True)
(args.out/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
