#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the closed direct-producer Gen partition probe, never a player package."""
import argparse,hashlib,importlib.util,json,os,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/gen/partitions'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def require(v,message):
 if not v:raise ValueError(message)
def load_reference():
 spec=importlib.util.spec_from_file_location('gen_partition_reference',FIXTURE/'reference.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);return r
def catalog():
 value=json.loads((FIXTURE/'catalog.json').read_text())
 require(sha(FIXTURE/'catalog.json')==CATALOG_SHA,'Direct probe catalog differs')
 require(sha(FIXTURE/'reference.py')==value['reference_sha256'],'Independent reference differs')
 for p in value['programs']:
  require(sha(ROOT/p['patch'])==p['patch_sha256']and sha(ROOT/p['genexpr'])==p['genexpr_sha256'],'Original source differs')
 return value
def files(path):
 result={}
 for p in sorted(path.rglob('*')):
  require(not p.is_symlink(),'Linked export files are not admitted')
  if p.is_file():result[p.relative_to(path).as_posix()]=sha(p)
 return result
def validate_exports(exports,c):
 require(exports.is_dir()and not exports.is_symlink(),'Missing direct exports')
 require(set(p.name for p in exports.iterdir())=={p['id']for p in c['programs']},'Exact three direct exports are required')
 records={};common=None
 for p in c['programs']:
  d=exports/p['id'];m=json.loads((d/'generator.json').read_text());desc=json.loads((d/'description.json').read_text())
  require(m.get('format')=='rnbo-gen-direct-partition-export-v1'and m.get('execution_route')=='direct-variable-producer'and m.get('module_abi')is False and m.get('rnbo_version')=='1.4.4'and type(m.get('block_frames'))is int and m['block_frames']==0 and m.get('sample_rate')==44100 and m.get('class_name')==p['class_name']and m.get('source_sha256')==p['patch_sha256']and m.get('generated_sha256')==sha(d/'rnbo_source.h')and m.get('catalog_sha256')==CATALOG_SHA and m.get('adapter_sha256')==sha(ROOT/'tools/export_gen_partition_probe.mjs')and m.get('patcher_adapter_sha256')==sha(ROOT/'host/export/patcher.mjs'),'Variable producer metadata/source differs')
  require(sha(d/'source.rnbopat')==p['patch_sha256'],'Export source differs')
  require(desc.get('numInputChannels')==desc.get('numOutputChannels')==2 and desc.get('numParameters')==1 and desc.get('numMidiInputPorts')==desc.get('numMidiOutputPorts')==0 and desc.get('externalDataRefs')==[] and desc['parameters'][0]['name']=='reset'and desc['parameters'][0]['paramId']=='s3_reset','Port/parameter/resource contract differs')
  current=files(d/'common')
  require(bool(current)and(common is None or common==current),'Shared runtime header maps differ')
  common=current;records[p['id']]=dict(files_sha256=files(d),generator=m)
 return records

def configuration(exports,out):
 c=catalog();r=load_reference();records=validate_exports(exports,c);config=out/'probe-config';config.mkdir()
 plan=dict(format='rnbo-gen-direct-partition-plan-v1',catalog_sha256=CATALOG_SHA,catalog=c,exports=records,reference_source_sha256=sha(FIXTURE/'reference.py'),execution_route='direct-variable-producer',module_abi=False,sample_rate=44100,frames_per_instance=4096,instances=78,program_stimuli=[])
 inputs=[r.input_words(stimulus)for stimulus in c['stimuli']];expected=[]
 for program in c['programs']:
  for stimulus in c['stimuli']:
   words=r.expected_words(program['model'],stimulus);expected.append(words);witnesses=r.reset_witnesses(program['model'],stimulus)
   require(sum(v['observable_at_limit']for v in witnesses)>=2,'Reset schedule lacks independently observable witnesses')
   plan['program_stimuli'].append(dict(model=program['model'],id=program['id'],stimulus=stimulus,input_words_sha256=hashlib.sha256(struct.pack('<8192I',*r.input_words(stimulus))).hexdigest(),expected_stream_sha256=hashlib.sha256(struct.pack('<8192I',*words)).hexdigest(),absolute_tolerance=2e-6 if program['model']==1 else 0,reset_witnesses=witnesses))
 digest=hashlib.sha256(encoded(plan)).hexdigest();header='''/* Generated private configuration, independent reference caches. */
#pragma once
#include <stdint.h>
#define GEN_PROBE_FRAMES 4096u
#define GEN_PROBE_LIMIT 0.000002
#define GEN_PROBE_PLAN_SHA256 '''+json.dumps(digest)+'''
#ifdef __cplusplus
static const unsigned gen_probe_resets[]={513,1024,2051,3001};
static const unsigned gen_probe_prepares[]={257,1300};
static const unsigned gen_probe_mixed[]={1,2,7,255,256,3,17};
static const unsigned gen_probe_partitions[]={1,2,7,255,256,0};
static const char *const gen_probe_names[]={"history-feedback","two-history-swap","three-history-rotation"};
static const char *const gen_probe_stimuli[]={"dyadic","boundary-impulses"};
extern "C" {
#endif
extern const uint32_t gen_probe_inputs[2][8192];
extern const uint32_t gen_probe_expected[6][8192];
#ifdef __cplusplus
}
#endif
''';(config/'gen_plan.h').write_text(header)
 words=lambda rows:',\n'.join('{'+','.join('0x%08xu'%v for v in row)+'}'for row in rows)
 (config/'references.c').write_text('#include "gen_plan.h"\nconst uint32_t gen_probe_inputs[2][8192]={'+words(inputs)+'};\nconst uint32_t gen_probe_expected[6][8192]={'+words(expected)+'};\n')
 programs=[]
 for p in c['programs']:
  path=config/f'program_{p["model"]}.cpp';path.write_text('''#define RNBO_USE_FLOAT32
#define RNBO_NOSTL
#define RNBO_NOTHROW
#define RNBO_NO_PATCHERFACTORY
#define RNBO_FIXEDLISTSIZE 16
#include "RNBO_Common.h"
#include '''+json.dumps(str(exports/p['id']/'rnbo_source.h'))+'''
#undef trunc
#undef autoref
#include "probe_template.h"
extern "C" void gen_partition_program_'''+str(p['model'])+'''(unsigned s,unsigned n,uint32_t*c,const uint32_t*b,gen_probe_result*r){gen_partition_probe::render<RNBO::'''+p['class_name']+'''<>,'''+str(p['model'])+'''>(s,n,c,b,r);}
''');programs.append(path)
 common=exports/c['programs'][0]['id']/'common';(config/'programs.cmake').write_text('set(GEN_PROBE_COMMON_DIR '+json.dumps(str(common))+')\nset(GEN_PROBE_PROGRAM_SOURCES\n'+'\n'.join('  '+json.dumps(str(p))for p in programs)+'\n)\n')
 (out/'probe-plan.json').write_bytes(encoded(plan));return plan,digest,programs,common

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exports',type=Path,required=True);p.add_argument('--build-dir',type=Path,required=True);p.add_argument('--native-only',action='store_true');p.add_argument('--idf-path',type=Path,default=Path.home()/'esp/esp-idf');a=p.parse_args();out=a.build_dir.resolve();exports=a.exports.resolve()
 require(out.is_relative_to(ROOT/'build')and not out.exists(),'Use a fresh private build directory');out.mkdir(parents=True);plan,digest,programs,common=configuration(exports,out);config=out/'probe-config';before=validate_exports(exports,catalog());source_files={p.relative_to(ROOT).as_posix():sha(p)for p in (ROOT/'gen-partition-probe').rglob('*')if p.is_file()};source_files['tools/build_gen_partition_probe.py']=sha(Path(__file__))
 native=out/'native';native.mkdir();captures=native/'captures';captures.mkdir();cmd=['c++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fno-strict-aliasing','-I'+str(config),'-I'+str(common),'-I'+str(ROOT/'gen-partition-probe/main'),str(ROOT/'gen-partition-probe/main/native.cpp'),*(str(p)for p in programs),'-x','c++',str(config/'references.c'),'-o',str(native/'probe')]
 with(native/'compile.log').open('wb')as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
 with(native/'run.log').open('wb')as log:subprocess.run([str(native/'probe'),str(captures)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=60)
 require(validate_exports(exports,catalog())==before,'Exports changed during native execution')
 (native/'report.json').write_bytes(encoded(dict(format='rnbo-gen-direct-partition-native-run-v1',plan_sha256=digest,compile_command=cmd,compile_log_sha256=sha(native/'compile.log'),run_log_sha256=sha(native/'run.log'),captures_sha256=files(captures),CPU_measured=False,heap_allocations_observed=False,hardware=False)))
 if a.native_only:print(json.dumps(dict(native='completed',plan_sha256=digest)));return
 environment=dict(os.environ,IDF_PATH=str(a.idf_path.resolve()),IDF_COMPONENT_MANAGER='0',PYTHONDONTWRITEBYTECODE='1')
 if not environment.get('IDF_PYTHON_ENV_PATH'):
  candidates=sorted(p for p in (Path.home()/'.espressif/python_env').glob('idf5.5_py*_env')if(p/'bin/python').is_file());require(bool(candidates),'ESP-IDF5.5 Python environment is required');environment['IDF_PYTHON_ENV_PATH']=str(candidates[-1])
 command=['bash','-e','-c','source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"','gen-partition-probe',str(a.idf_path.resolve()),'-B',str(out),'-D','IDF_TARGET=esp32s3','-D','SDKCONFIG='+str(out/'sdkconfig'),'-D','SDKCONFIG_DEFAULTS='+str(ROOT/'gen-partition-probe/sdkconfig.defaults'),'-D','GEN_PROBE_CONFIG_DIR='+str(config),'build']
 with(out/'build.log').open('wb')as log:subprocess.run(command,cwd=ROOT/'gen-partition-probe',env=environment,check=True,stdout=log,stderr=subprocess.STDOUT)
 require(validate_exports(exports,catalog())==before,'Exports changed during target build');require(all(sha(ROOT/p)==h for p,h in source_files.items()),'Probe sources changed during target build')
 sdk=(out/'sdkconfig').read_text()
 for option in('CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y','CONFIG_SPIRAM_MODE_OCT=y','CONFIG_SPIRAM_SPEED_80M=y','CONFIG_HEAP_USE_HOOKS=y','CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y','CONFIG_ESP_MAIN_TASK_AFFINITY_CPU0=y'):require(option in sdk,'Resolved direct probe configuration differs: '+option)
 description=json.loads((out/'project_description.json').read_text());artifacts={}
 for name in(description['app_elf'],description['app_bin'],'partition_table/partition-table.bin'):
  path=out/name;artifacts[path.relative_to(ROOT).as_posix()]=dict(bytes=path.stat().st_size,sha256=sha(path))
 report=dict(format='rnbo-hardware-smoke-build-v1',family='gen-direct-partitions',execution_route='direct-variable-producer',module_abi=False,board='xiao',artifacts=artifacts,plan_sha256=digest,plan=plan,source_files_sha256=source_files,configuration_files_sha256=files(config),native_report_sha256=sha(native/'report.json'),idf_version=description.get('idf_ver'),command=command,hardware_executed=False,optimisation_comparison=False)
 (out/'build-report.json').write_bytes(encoded(report));print(json.dumps(dict(build_report=str(out/'build-report.json'),native='completed',instances=78,plan_sha256=digest)))

# The exact original graph/reference ledger is the only admitted experiment.
CATALOG_SHA='9212bb70b2bcbad1f8b0a8d5e0590b53426e2db09630dff0b457cb153db36c8b'
if __name__=='__main__':main()
