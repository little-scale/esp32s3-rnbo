#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original eight-program Gen state-boundary source/catalog generator."""
import argparse
import hashlib
import json
from pathlib import Path
import reference

HERE = Path(__file__).resolve().parent
RECIPES = (
    ('phasor-free-dyadic', 'phasor', 'call',
     'out1 = phasor(129.19921875, 0) + 0*in1;\nout2 = phasor(107.666015625, 0) + 0*in2;\n'),
    ('phasor-signal-reset', 'phasor', 'call',
     'out1 = phasor(129.19921875, in1, phase=0.125);\nout2 = phasor(107.666015625, in2, phase=0.375);\n'),
    ('train-odd-periods', 'train', 'call',
     'out1 = train(7, 0.5, 0) + 0*in1;\nout2 = train(11, 0.5, 0) + 0*in2;\n'),
    ('train-onset-variable-width', 'train', 'call',
     'out1 = train(7, in1, 0.25);\nout2 = train(11, in2, 0.25);\n'),
    ('rate-sync-off', 'rate', 'call',
     'out1 = rate(in1, 8, sync="off");\nout2 = rate(in2, 16, sync="off");\n'),
    ('mulequals-nonzero-init-post-reset', 'mulequals', 'call',
     'out1 = mulequals(in1, in2, init=1, min=1, resetmode="post");\nout2 = mulequals(1/in1, in2, init=1, min=1, resetmode="post");\n'),
    ('delay-one-and-three-samples', 'delay', 'declaration-and-methods',
     'Delay leftDelay(16);\nDelay rightDelay(16);\nout1 = leftDelay.read(1, interp="none");\nout2 = rightDelay.read(3, interp="none");\nleftDelay.write(in1);\nrightDelay.write(in2);\n'),
    ('delay-three-sample-feedback', 'delay', 'declaration-and-methods',
     'Delay feedbackDelay(16);\nprevious = feedbackDelay.read(3, interp="none");\ncurrent = in1 + 0.5*previous;\nout1 = current;\nout2 = in2;\nfeedbackDelay.write(current);\n'),
)


def encoded(obj):
    return (json.dumps(obj,indent=2,sort_keys=True)+'\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def graph(code):
    boxes = []
    for n,(identity,text) in enumerate((('left','in~ 1'),('right','in~ 2'),('gen','gen~'),
                                        ('out-left','out~ 1'),('out-right','out~ 2'))):
        b = {'id':identity,'rnbo_uniqueid':identity,'maxclass':'newobj','text':text,
             'patching_rect':[30+n*170,30,150,24]}
        if identity == 'gen':
            b['rnbo_extra_attributes'] = {'expr':code,'geninlets':2,'genoutlets':2}
        boxes.append({'box':b})
    links = [(('left',0),('gen',0)),(('right',0),('gen',1)),
             (('gen',0),('out-left',0)),(('gen',1),('out-right',0))]
    return {'patcher':{'classnamespace':'rnbo','fileversion':1,'rect':[0,0,1000,300],
                       'boxes':boxes,'lines':[{'patchline':{'source':list(a),'destination':list(b)}} for a,b in links]}}


def artifacts(package):
    registry_path = Path('server/node_modules/@rnbo/genexpr_js/operators.json')
    registry_bytes = (package/registry_path).read_bytes()
    registry = {r['op']:r for r in json.loads(registry_bytes)}
    outputs = {}
    cases = []
    for model,(identity,name,syntax,code) in enumerate(RECIPES,820):
        assert name in registry and registry[name]['stateful']
        outputs[identity+'.genexpr'] = code.encode()
        outputs[identity+'.rnbopat'] = encoded(graph(code))
        inputs = reference.case_input_words(model)
        domains = [[min(reference.value(w) for w in inputs[ch::2]),
                    max(reference.value(w) for w in inputs[ch::2])] for ch in (0,1)]
        cases.append({'id':identity,'exact_name':name,'canonical_name':name,
            'registry_lookup':name,'syntax':syntax,'surface':'genexpr','role':'fx','model':model,
            'patch':identity+'.rnbopat','genexpr':identity+'.genexpr',
            'patch_sha256':sha(outputs[identity+'.rnbopat']),'genexpr_sha256':sha(code.encode()),
            'maximum_absolute_error':reference.ABSOLUTE_TOLERANCES[model],
            'input_domains':domains,'reference_policy':'predeclared-gen-continuous-state-boundaries',
            'reference_sources':[{'local_package_path':registry_path.as_posix(),
                'sha256':sha(registry_bytes),'reference_url':'https://docs.cycling74.com/reference/gen_dsp_'+name+'/'}],
            'scope':'Exact original source/argument form; fresh state,20 continuous callbacks with initial/reset capture ordering declared before output. Delay.read/write are methods of the shown Delay declaration, not standalone read/write owner qualification. No alternate APIs, aliases, arbitrary modes or variable-block production ABI claim.'})
    outputs['catalog.json'] = encoded({'format':'rnbo-hardware-smoke-catalog-v1',
        'family':'gen-state-boundaries','surface':'genexpr','sample_rate':44100,'block_frames':256,
        'automatic_warmup_blocks':0,'manual_warmup_blocks':4,'timed_blocks':16,
        'requested_module_max_arena_bytes':4096,'license':'MIT; original source and independent references',
        'reference_sha256':sha((HERE/'reference.py').read_bytes()),
        'generator_sha256':sha(Path(__file__).read_bytes()),'cases':cases,
        'scope':'Eight small phase/reset/product/delay scenarios with full20block references; documented ambiguities retain declared policy mismatches. Compilation is not execution; no DSP optimisation or gain claimed.'})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--rnbo-package',type=Path,default=Path.home()/'Documents/Max 9/Packages/RNBO')
    args = parser.parse_args()
    for name,data in artifacts(args.rnbo_package).items():
        p = HERE/name
        if args.check:
            if not p.is_file() or p.read_bytes() != data:
                raise SystemExit('Generated source differs: '+name)
        else:
            p.write_bytes(data)
    print(('Checked' if args.check else 'Wrote')+' eight Gen state-boundary programs and catalog')


if __name__ == '__main__':
    main()
