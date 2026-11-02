#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the experimental conversion microbenchmark; never flash a device."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():
    paths=[Path(__file__),ROOT/'runtime/phase_trunc.h']
    paths += [p for p in (ROOT/'phase-benchmark').rglob('*') if p.is_file()]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}

def main():
    idf=Path(os.environ.get('IDF_PATH',Path.home()/'esp/esp-idf')).resolve()
    before=inventory();directory=ROOT/'build/phase-benchmark-amoled';directory.mkdir(parents=True,exist_ok=True)
    version=(idf/'tools/cmake/version.cmake').read_text()
    import re
    if tuple(int(re.search(r'set\(IDF_VERSION_'+k+r' (\d+)\)',version)[1]) for k in ('MAJOR','MINOR','PATCH'))!=(5,5,0):
        raise ValueError('ESP-IDF 5.5.0 required')
    env=dict(os.environ,IDF_PATH=str(idf),IDF_COMPONENT_MANAGER='0',PYTHONDONTWRITEBYTECODE='1')
    if not env.get('IDF_PYTHON_ENV_PATH'):
        env['IDF_PYTHON_ENV_PATH']=str(sorted(p for p in (Path.home()/'.espressif/python_env').glob('idf5.5_py*_env') if (p/'bin/python').is_file())[-1])
    command=['bash','-e','-c','source "$1/export.sh" >/dev/null; shift; exec "$IDF_PYTHON_ENV_PATH/bin/python" "$IDF_PATH/tools/idf.py" "$@"',
        'phase-benchmark',str(idf),'-B',str(directory),'-D','IDF_TARGET=esp32s3','-D',f'SDKCONFIG={directory/"sdkconfig"}',
        '-D',f'SDKCONFIG_DEFAULTS={ROOT/"phase-benchmark/sdkconfig.defaults"}','build']
    with (directory/'build.log').open('w') as log:subprocess.run(command,cwd=ROOT/'phase-benchmark',env=env,check=True,stdout=log,stderr=subprocess.STDOUT)
    if inventory()!=before:raise ValueError('Benchmark source changed during build')
    description=json.loads((directory/'project_description.json').read_text());compiler=Path(description['c_compiler'])
    config=(directory/'sdkconfig').read_text()
    for required in ('CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y','CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y','CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240=y'):
        if required not in config:raise ValueError('Unexpected benchmark configuration')
    report={'format':'rnbo-phase-conversion-microbenchmark-build','format_version':1,'board':'amoled',
        'source_files_sha256':before,'artifacts':{},'sdkconfig_sha256':sha(directory/'sdkconfig'),
        'compiler':{'path':str(compiler),'version':subprocess.run([str(compiler),'--version'],capture_output=True,text=True,check=True).stdout},
        'idf_commit':subprocess.run(['git','-C',str(idf),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
        'scope':'Native firmware indirect-function conversion microbenchmark; no RNBO render or speed claim until observed',
        'expected_pass_prefix':'RNBO_PHASE_BENCHMARK PASS ','hardware_executed':False}
    for name in (description['app_elf'],description['app_bin'],'partition_table/partition-table.bin'):
        p=directory/name;report['artifacts'][str(p.relative_to(ROOT))]={'bytes':p.stat().st_size,'sha256':sha(p)}
    (directory/'build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(directory/'build-report.json')}))

if __name__=='__main__':main()
