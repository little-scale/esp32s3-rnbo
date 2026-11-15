#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline Float32 delay-storage trial for the native SawSAHArpy export.

Uses the existing fingerprint-guarded converter. Neither Studio defaults nor
the input export are changed. Output must be new; trusted local exports only.
Generated source and audio stay in the ignored output directory.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host/compiler'))
from prepare import prepare, canonical
from build import verify_prepared, snapshot_files

PROBE = ROOT / 'tests/native/delay_storage_probe.cpp'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(left, right):
    if left.stat().st_size != right.stat().st_size or not left.stat().st_size or left.stat().st_size % 4:
        raise ValueError('Incomplete or unequal captures')
    maximum = squares = energy = peak = 0.0
    different = words = 0
    with left.open('rb') as a, right.open('rb') as b:
        while data := a.read(65536):
            other = b.read(len(data))
            x, y = array.array('f'), array.array('f')
            x.frombytes(data); y.frombytes(other)
            if sys.byteorder != 'little':
                x.byteswap(); y.byteswap()
            for p, q in zip(x, y):
                if not math.isfinite(p) or not math.isfinite(q):
                    raise ValueError('Nonfinite output')
                delta = abs(p-q)
                maximum = max(maximum, delta)
                squares += delta*delta; energy += p*p; peak = max(peak, abs(p))
            different += sum(data[i:i+4] != other[i:i+4] for i in range(0,len(data),4))
            words += len(x)
    return dict(words=words, bit_different_words=different,
                bit_identical=different == 0, maximum_absolute_error=maximum,
                rms_error=math.sqrt(squares/words), reference_peak=peak,
                reference_rms=math.sqrt(energy/words))


def run(export, out, blocks=2048, long_blocks=32768, sanitizers=None):
    if not 512 <= blocks <= 100000 or not blocks <= long_blocks <= 100000:
        raise ValueError('Use 512..100000 blocks and long-blocks >= blocks')
    out.mkdir(parents=True, exist_ok=False)
    integration = [PROBE, Path(__file__).resolve(), ROOT/'module-sdk/wrapper/rnbo_s3_static.cpp',
                   ROOT/'module-sdk/include/rnbo_s3_module.h', ROOT/'module-sdk/include/rnbo_s3_midi.h']
    integration_snapshot = snapshot_files(ROOT,integration)
    snapshots = {}
    builds = {}
    for label, candidate in (('baseline', False), ('candidate', True)):
        directory = out / label
        manifest = prepare(export, directory, 'rnbomatic', 'main', float32_delay_storage=candidate,
                           delay_storage_policy='float64')
        if (manifest['parameter_count'] != 2 or manifest['audio_inputs'] != 0 or
                manifest['rnbo_version'] != '1.4.4' or manifest['scheduler_time'] != 'float64'):
            raise ValueError('Expected the authored native SawSAHArpy Main export')
        snapshots[label] = verify_prepared(directory)[2]
        command = ['c++', '-std=c++17', '-O2', '-UNDEBUG', '-fno-fast-math', '-ffp-contract=off',
                   '-fno-strict-aliasing', '-fno-exceptions', '-fno-rtti',
                   '-I'+str(ROOT/'module-sdk/include'), '-I'+str(directory), '-I'+str(directory/'common'),
                   str(PROBE), '-o', str(directory/'probe')]
        if sanitizers:
            command[1:1] = ['-fsanitize='+sanitizers,'-fno-omit-frame-pointer','-fno-sanitize-recover=all']
        compiled = subprocess.run(command, capture_output=True, timeout=120)
        (directory/'compile.log').write_bytes(compiled.stdout+compiled.stderr)
        compiled.check_returncode()
        builds[label] = dict(manifest=manifest, command=command,
                             executable_sha256=digest(directory/'probe'),
                             header_sha256=digest(directory/'rnbo_source.h'),
                             provenance_sha256=digest(directory/'provenance.json'))
    before = (out/'baseline/rnbo_source.h').read_bytes()
    after = (out/'candidate/rnbo_source.h').read_bytes()
    # The probe is deliberately specific to this one ordinary fixed-size ring.
    changes = json.loads((out/'candidate/provenance.json').read_bytes())['adaptations']
    storage = [x for x in changes if x['name']=='rnbo-1.4.4-float32-internal-delays-v1'][0]
    if (storage['constructor_reference_pairs'] != 1 or
            storage['rings'][0]['name'] != 'delaytilde_01_del' or
            storage['rings'][0]['requested_samples'] != 22050 or
            after.replace(b'Float32Buffer',b'Float64Buffer') != before):
        raise ValueError('Expected exactly the two reviewed delay storage type substitutions')
    cases = []
    plan = [(name, blocks) for name in ('default','minimum','maximum','fractional','sweep','jumps')]
    plan += [('long-default',long_blocks), ('reconstruct-default',blocks), ('ring',131072)]
    for name, count in plan:
        mode = 'default' if name in ('long-default','reconstruct-default') else name
        stats = {}; paths = {}
        for label in builds:
            path = out/f'{name}-{label}.f32'; paths[label] = path
            result = subprocess.run([str(out/label/'probe'),mode,str(count),str(path)],
                                    capture_output=True,timeout=120)
            (out/f'{name}-{label}.log').write_bytes(result.stdout+result.stderr)
            result.check_returncode()
            stats[label] = json.loads(result.stdout)
            expected_words = count*(8 if mode=='ring' else 512)
            if stats[label]['words'] != expected_words or path.stat().st_size != expected_words*4:
                raise ValueError('Incomplete capture')
        metrics = compare(paths['baseline'],paths['candidate'])
        if mode != 'ring' and metrics['reference_peak'] == 0:
            raise ValueError('Silent whole-patch test cannot establish useful parity')
        cases.append(dict(case=name, count=count, units='samples per interpolation value' if mode=='ring' else 'blocks',
                          independent_clear_and_integer_impulse_assertions_passed=mode=='ring',
                          comparison=metrics, statistics=stats,
                          captures_sha256={k:digest(v) for k,v in paths.items()}))
    reconstruction = {label: compare(out/f'default-{label}.f32',out/f'reconstruct-default-{label}.f32')
                      for label in builds}
    for label in builds:
        if verify_prepared(out/label)[2] != snapshots[label]:
            raise ValueError('Prepared input changed during investigation')
    if snapshot_files(ROOT,integration) != integration_snapshot:
        raise ValueError('Investigation source changed during compilation or capture')
    report = dict(evidence_kind='native-Max-export-delay-storage-host-research',
                  sample_rate=44100, block_frames=256, compiler_version=subprocess.check_output(['c++','--version'],text=True),
                  probe_sha256=digest(PROBE), script_sha256=digest(Path(__file__)),
                  integration_files_sha256=integration_snapshot, sanitizers=sanitizers,
                  builds=builds,storage=storage,cases=cases,reconstruction=reconstruction,
                  all_captures_bit_identical=all(c['comparison']['bit_identical'] for c in cases),
                  hardware_executed=False,target_cpu_gain_claimed=False,
                  production_defaults_changed=False,
                  limits=['One native RNBO 1.4.4 patch and one fixed-size ordinary delay ring.',
                          'Host comparisons do not establish ESP32 numerical identity or deadline performance.',
                          'No Gen/comb/allpass/external buffers or nonfinite input qualification.',
                          'Fresh-context reconstruction tested; no live package swap or power cycle.'])
    (out/'comparison.json').write_bytes(canonical(report))
    print(json.dumps(dict(report=str(out/'comparison.json'),bit_identical=report['all_captures_bit_identical'],
                          cases=len(cases),buffer_bytes_saved=storage['buffer_data_bytes_saved'])))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True,help='Normalised native Minimal Export directory')
    parser.add_argument('--out',type=Path,required=True,help='Fresh private/ignored research directory')
    parser.add_argument('--blocks',type=int,default=2048)
    parser.add_argument('--long-blocks',type=int,default=32768)
    parser.add_argument('--sanitizers',nargs='?',const='address,undefined',choices=('address,undefined','undefined'),
                        help='Repeat with sanitizers; use undefined if AddressSanitizer cannot start on this host')
    args=parser.parse_args()
    run(args.export.resolve(),args.out.resolve(),args.blocks,args.long_blocks,args.sanitizers)
