#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce two native Max ramp faults and compare private research candidates.

Inputs are trusted, baseline Float32 prepared exports of the authored line-ramp
and curve-compound fixtures. No installed runtime, export or production wrapper
is modified. The output directory must be fresh. No target timing is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'tests/fixtures/smoke/rnbo-envelopes-clocks/reference.py'
WRAPPER = ROOT / 'module-sdk/wrapper/rnbo_s3_static.cpp'
HARNESS = ROOT / 'tests/native/export_parity_event_test.cpp'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(actual, expected, tolerance):
    if len(actual) > len(expected) or len(actual) % 4:
        raise ValueError('Invalid captured output size')
    bits = outside = within = zeros = 0
    maximum = 0.0
    for index, (a, b) in enumerate(zip(struct.iter_unpack('<I', actual), struct.iter_unpack('<I', expected))):
        if a == b:
            continue
        bits += 1
        x, y = (struct.unpack('<f', struct.pack('<I', value[0]))[0] for value in (a, b))
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Nonfinite captured output')
        if index % 2 == 0 and (a[0] | b[0]) & 0x7fffffff == 0:
            zeros += 1
            continue
        difference = abs(x - y)
        maximum = max(maximum, difference)
        if index % 2 == 0 and difference <= tolerance:
            within += 1
        else:
            outside += 1
    return dict(words=len(actual) // 4, bit_differences=bits, outside_tolerance_words=outside,
                within_tolerance_words=within, left_zero_sign_differences=zeros, maximum_error=maximum)


def run(line, curve, out):
    out.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('ramp_reference', REFERENCE)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    rows = []
    for identity, prepared, model in (('line-ramp', line, 3430), ('curve-compound', curve, 3422)):
        manifest = json.loads((prepared / 'manifest.json').read_bytes())
        if any(manifest.get(key) != value for key, value in
               dict(numerical_profile='float32-strict', role='fx', sample_rate=44100, block_frames=256).items()):
            raise ValueError('Use baseline Float32 FX preparations of the exact authored fixtures')
        inputs = reference.input_words()
        expected_words = [w for block in reference.reference_blocks(model, inputs) for w in block]
        events = reference.parameter_events(model)
        if len(events) != 22 or len(expected_words) != 10240:
            raise ValueError('The authored reference contract changed')
        captures = []
        for candidate in (False, True):
            label = identity + ('-candidate' if candidate else '-baseline')
            directory = out / label
            shutil.copytree(prepared, directory)
            header = directory / 'rnbo_source.h'
            if candidate and identity == 'line-ramp':
                source = header.read_text()
                needle = 'number nextTime = currentTime + this->line_01_grain;'
                if source.count(needle) != 1:
                    raise ValueError('Expected the exact line-ramp clock probe')
                header.write_text(source.replace(needle, 'MillisecondTime nextTime = currentTime + this->line_01_grain;'))
            wrapper = WRAPPER.read_text()
            wrapper = wrapper.replace('static void printErrorMessage(const char *) { if (allocation) ++allocation->errors; }',
                'static void printErrorMessage(const char *message) { if (allocation) ++allocation->errors; std::fprintf(stderr,"PLATFORM_ERROR %s\\n",message); }')
            wrapper = wrapper.replace('if (allocation->running) ++allocation->late;',
                'if (allocation->running) { ++allocation->late; std::fprintf(stderr,"LATE_ALLOC bytes=%zu\\n",n); }')
            wrapper = wrapper.replace('Context *c = new(std::nothrow) Context;',
                'std::fprintf(stderr,"WRAPPER_CONTEXT bytes=%zu\\n",sizeof(Context)); Context *c = new(std::nothrow) Context;')
            if candidate and identity == 'curve-compound':
                wrapper = wrapper.replace('#define RNBO_FIXEDLISTSIZE 16', '#define RNBO_FIXEDLISTSIZE 32')
            wrapper_file = directory / 'probe_wrapper.cpp'
            wrapper_file.write_text(wrapper)
            (directory / 'inputs.u32').write_bytes(struct.pack('<512I', *inputs))
            expected = struct.pack('<10240I', *expected_words)
            (directory / 'expected.u32').write_bytes(expected)
            (directory / 'events.u32').write_bytes(struct.pack('<66I', *(w for e in events for w in
                (e['before_call'], 0 if e['id'] == 'drive' else 1, reference.word(e['value'])))))
            command = ['c++', '-std=c++17', '-O2', '-fno-fast-math', '-ffp-contract=off', '-fno-strict-aliasing',
                '-I' + str(ROOT / 'module-sdk/include'), '-I' + str(directory), '-I' + str(directory / 'common'),
                str(HARNESS), str(wrapper_file), '-o', str(directory / 'probe')]
            compiled = subprocess.run(command, capture_output=True, timeout=60)
            (directory / 'compile.log').write_bytes(compiled.stdout + compiled.stderr)
            compiled.check_returncode()
            tolerance = reference.ABSOLUTE_TOLERANCES[model]
            observed = subprocess.run([str(directory / 'probe'), str(directory / 'inputs.u32'),
                str(directory / 'expected.u32'), str(directory / 'events.u32'), str(tolerance),
                str(directory / 'output.u32')], capture_output=True, timeout=20)
            (directory / 'run.log').write_bytes(observed.stdout + observed.stderr)
            actual = (directory / 'output.u32').read_bytes()
            captures.append(actual)
            trace = observed.stderr.decode()
            size = re.search(r'WRAPPER_CONTEXT bytes=(\d+)', trace)
            row = dict(case=identity, candidate=candidate, returncode=observed.returncode,
                diagnostic=json.loads(observed.stdout), trace=trace.splitlines(),
                host_context_bytes=int(size[1]) if size else None,
                source_header_sha256=sha(prepared / 'rnbo_source.h'), prepared_header_sha256=sha(header),
                prepared_manifest_sha256=sha(prepared / 'manifest.json'),
                runtime_sha256={p.name: sha(p) for p in sorted((prepared / 'common').glob('*')) if p.is_file()},
                probe_wrapper_sha256=sha(wrapper_file), output_sha256=sha(directory / 'output.u32'),
                oracle=compare(actual, expected, tolerance), complete_output=len(actual) == len(expected))
            if candidate:
                prefix = actual[:len(captures[0])]
                row['baseline_prefix'] = compare(prefix, captures[0], 0)
                row['baseline_prefix']['bit_identical'] = prefix == captures[0]
            rows.append(row)
    result = dict(format='rnbo-native-ramp-diagnosis-v1',
        scope='Exact authored native Max FX exports, 22 events and 20 callbacks. Private research candidates only; production remains unchanged.',
        sample_rate=44100, block_frames=256, arena_bytes=1048576,
        production_changed=False, target_tested=False, cpu_savings_claimed=False,
        tool_sha256=sha(Path(__file__)), wrapper_sha256=sha(WRAPPER), harness_sha256=sha(HARNESS),
        reference_sha256=sha(REFERENCE), cases=rows)
    (out / 'report.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--line', required=True, type=Path)
    parser.add_argument('--curve', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.line.resolve(), args.curve.resolve(), args.out.resolve())
    print(json.dumps([dict(case=r['case'], candidate=r['candidate'], complete=r['complete_output'],
        outside=r['oracle']['outside_tolerance_words']) for r in result['cases']]))
