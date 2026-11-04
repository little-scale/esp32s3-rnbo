#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate original signal-only routing fixtures; --check is read-only."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import reference

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IDS = ('gate-two-outlets', 'selector-two-inputs', 'send-signal', 's-signal',
       'receive-signal', 'r-signal', 'cubicinterp-signal', 'fastcubicinterp-signal',
       'splineinterp-signal', 'spline6interp-signal', 'equal-pass-symbol-signal',
       'not-equal-pass-symbol-signal', 'greater-pass-symbol-signal',
       'greater-equal-pass-symbol-signal', 'less-pass-symbol-signal',
       'less-equal-pass-symbol-signal', 'equals-signal', 'lessthan-signal',
       'minus-signal', 'conditional-symbol-signal')


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True)+'\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def box(identity, text, x, y):
    return {'box': {'id': identity, 'rnbo_uniqueid': identity, 'maxclass': 'newobj',
                    'text': text, 'patching_rect': [x, y, 250, 24]}}


def graph(name):
    boxes = [box('left', 'in~ 1', 30, 30), box('right', 'in~ 2', 350, 30)]
    lines = []
    def add(identity, text, x=30, y=140):
        boxes.append(box(identity, text, x, y))
    def wire(src, dest, outlet=0, inlet=0):
        lines.append({'patchline': {'source': [src, outlet], 'destination': [dest, inlet]}})
    if name == 'gate~':
        add('operator', 'gate~ 2 0 0')
        wire('left', 'operator'); wire('right', 'operator', inlet=1)
        wire('operator', 'out-left'); wire('operator', 'out-right', outlet=1)
    elif name == 'selector~':
        add('operator', 'selector~ 2'); add('negated-data', '*~ -1', 350, 95)
        wire('left', 'operator'); wire('right', 'operator', inlet=1)
        wire('right', 'negated-data'); wire('negated-data', 'operator', inlet=2)
        wire('operator', 'out-left'); wire('right', 'out-right')
    elif name in reference.BUSES:
        sender = name if name in ('send~', 's~') else 'send~'
        receiver = name if name in ('receive~', 'r~') else 'receive~'
        for lane, source, target, x in ((0, 'left', 'out-left', 30), (1, 'right', 'out-right', 350)):
            channel = 'routing_left' if lane == 0 else 'routing_right'
            add('sender-'+str(lane), sender+' '+channel, x, 100)
            add('receiver-'+str(lane), receiver+' '+channel, x, 180)
            wire(source, 'sender-'+str(lane)); wire('receiver-'+str(lane), target)
    else:
        for lane, source, other, target, x in ((0, 'left', 'right', 'out-left', 30),
                                                (1, 'right', 'left', 'out-right', 350)):
            identity = 'operator-left' if lane == 0 else 'operator-right'
            text = name
            if name in reference.INTERPOLATORS:
                points = reference.C6[lane] if name == 'spline6interp~' else reference.C4[lane]
                text += ' '+' '.join(format(v, '.12g') for v in points)
            elif name == '?~':
                text += ' 1 -1' if lane == 0 else ' -1 1'
            add(identity, text, x)
            wire(source, identity)
            if name not in reference.INTERPOLATORS and name != '?~':
                wire(other, identity, inlet=1)
            wire(identity, target)
    boxes.extend((box('out-left', 'out~ 1', 30, 280), box('out-right', 'out~ 2', 350, 280)))
    return {'patcher': {'fileversion': 1, 'classnamespace': 'rnbo',
                        'rect': [0, 0, 900, 400], 'boxes': boxes, 'lines': lines}}


def artifacts(package):
    inventory = json.loads((ROOT/'site/data/inventory.json').read_bytes())
    spellings = {row['name']: row for row in inventory['spellings'] if row['registry'] == 'patcher'}
    outputs = {}
    cases = []
    for model, (name, identity) in enumerate(zip(reference.NAMES, IDS), 800):
        canonical = spellings[name]['canonical_id'].split(':', 1)[1]
        filename = identity+'.rnbopat'
        outputs[filename] = encoded(graph(name))
        primary = Path('docs/refpages/rnbo')/('rnbo_'+canonical+'.maxref.xml')
        if name in reference.INTERPOLATORS:
            literals = {'left': reference.C6[0] if name == 'spline6interp~' else reference.C4[0],
                        'right': reference.C6[1] if name == 'spline6interp~' else reference.C4[1]}
            domain = [[0, 1], [0, 1]]
        elif name in ('gate~', 'selector~'):
            literals = {'choices': [0, 1, 2], 'ramptime_ms': 0} if name == 'gate~' else {'choices': [0, 1, 2], 'second_choice': 'negative-right-input'}
            domain = [[0, 2], [-4, 4]]
        elif name in reference.BUSES:
            literals = {'bus_names': ['routing_left', 'routing_right']}
            domain = [[-4, 4], [-4, 4]]
        else:
            literals = {'left': [1, -1], 'right': [-1, 1]} if name == '?~' else {}
            domain = [[-4, 4], [-4, 4]]
        cases.append({'id': identity, 'exact_name': name, 'canonical_name': canonical,
                      'registry_lookup': name, 'surface': 'patcher', 'syntax': 'signal-object',
                      'role': 'fx', 'model': model, 'patch': filename,
                      'patch_sha256': digest(outputs[filename]), 'input_domains': domain,
                      'literal_parameters': literals,
                      'maximum_absolute_error': reference.ABSOLUTE_TOLERANCES[model],
                      'reference_policy': 'documented-bounded-signal-routing',
                      'reference_sources': [{'local_package_path': primary.as_posix(),
                                             'sha256': digest((package/primary).read_bytes()),
                                             'url': 'https://rnbo.cycling74.com/objects/ref/'+quote(name, safe='')+'?v=1.4.4'}],
                      'scope': 'Exact owner spelling in an original local signal graph; canonical bus/negation counterparts are support only. Gate ramptime0; selector integer choices0/1/2 only. No root-Max buses, feedback, ramp changes, alias inheritance or other interpolation modes.'})
    outputs['catalog.json'] = encoded({'format': 'rnbo-hardware-smoke-catalog-v1',
        'family': 'rnbo-signal-routing', 'surface': 'patcher', 'sample_rate': 44100,
        'block_frames': 256, 'automatic_warmup_blocks': 0, 'manual_warmup_blocks': 4,
        'timed_blocks': 16, 'requested_module_max_arena_bytes': 4096,
        'license': 'MIT; original fixtures and independent references',
        'reference_sha256': digest((HERE/'reference.py').read_bytes()),
        'generator_sha256': digest(Path(__file__).read_bytes()), 'cases': cases,
        'scope': 'Twenty separately authored exact signal forms; short fixed-input functional checks and whole-fixture callback observations, not complete qualification or optimisation gains.'})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--rnbo-package', type=Path,
                        default=Path.home()/'Documents/Max 9/Packages/RNBO')
    args = parser.parse_args()
    outputs = artifacts(args.rnbo_package)
    for name, content in outputs.items():
        path = HERE/name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise SystemExit('Generated fixture differs: '+name)
        else:
            path.write_bytes(content)
    print(('Checked' if args.check else 'Wrote')+' twenty original signal-routing fixtures and catalog')


if __name__ == '__main__':
    main()
