#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate seven original RNBO signal-state followups; --check is read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import reference

HERE=Path(__file__).resolve().parent
ROWS=(('onepole-linear-fixed','onepole_lin~'),('onepole-linear-signal-cutoff','onepole_lin~'),
      ('onoff-block-toggle','onoff~'),('counter-count-and-flag','counter~'),
      ('counter-count-and-carry-count','counter~'),('normalize-fixed-max','normalize~'),
      ('normalize-signal-max','normalize~'))


def encoded(x):return(json.dumps(x,indent=2,sort_keys=True)+'\n').encode()
def sha(x):return hashlib.sha256(x).hexdigest()


def graph(model):
    name=ROWS[model-900][1]
    boxes=[];lines=[]
    def box(identity,text,x=30,y=120):
        boxes.append({'box':{'id':identity,'rnbo_uniqueid':identity,'text':text,
                             'maxclass':'newobj','patching_rect':[x,y,300,24]}})
    def wire(source,target,outlet=0,inlet=0):
        lines.append({'patchline':{'source':[source,outlet],'destination':[target,inlet]}})
    box('left','in~ 1',30,30);box('right','in~ 2',380,30)
    if model in(903,904):
        box('operator','counter~ 0 7')
        wire('left','operator');wire('right','operator',inlet=1)
        wire('operator','out-left');wire('operator','out-right',outlet=1 if model==903 else 2)
    elif model in(901,906):
        box('operator',name)
        wire('left','operator');wire('right','operator',inlet=1)
        wire('operator','out-left');wire('right','out-right')
    else:
        for ch,source,target,x in((0,'left','out-left',30),(1,'right','out-right',380)):
            text=name
            identity='operator-'+str(ch);box(identity,text,x)
            if model!=902:wire(source,identity)
            if model in(900,905):
                literal=(.25,.5)[ch] if model==900 else(.5,1.)[ch]
                box('fixed-'+str(ch),'sig~ '+str(literal),x,75)
                wire('fixed-'+str(ch),identity,inlet=1)
            wire(identity,target)
    box('out-left','out~ 1',30,240);box('out-right','out~ 2',380,240)
    return{'patcher':{'fileversion':1,'classnamespace':'rnbo','rect':[0,0,1000,400],
                      'boxes':boxes,'lines':lines}}


def artifacts(package):
    outputs={};cases=[]
    for model,(identity,name) in enumerate(ROWS,900):
        patch=identity+'.rnbopat';outputs[patch]=encoded(graph(model))
        xml=Path('docs/refpages/rnbo')/('rnbo_'+name+'.maxref.xml')
        primary=[xml]
        if name in('onepole_lin~','onoff~','counter~'):
            primary.append(Path('source/operators')/(name[:-1]+'.js'))
        elif name=='normalize~':
            primary.append(Path('server/node_modules/@rnbo/xam/objects/normalize.js'))
        vector=reference.case_input_words(model)
        cases.append({'id':identity,'exact_name':name,'canonical_name':name,'registry_lookup':name,
            'surface':'patcher','syntax':'signal-object','role':'fx','model':model,'patch':patch,
            'patch_sha256':sha(outputs[patch]),'maximum_absolute_error':reference.ABSOLUTE_TOLERANCES[model],
            'input_domains':[[min(reference.value(w)for w in vector[ch::2]),max(reference.value(w)for w in vector[ch::2])]for ch in(0,1)],
            'reference_policy':'independent-continuous-signal-state',
            'reference_sources':[{'local_package_path':p.as_posix(),'sha256':sha((package/p).read_bytes()),
                                  'url':'https://rnbo.cycling74.com/objects/ref/'+name+'?v=1.4.4'}for p in primary],
            'scope':'Original configured exact signal owner;20continuous256-frame callbacks,prepare0. Independent initial/capture/reset equations are declared before output. Other surfaces/aliases/modes, arbitrary phase/controls and reset methods are not inferred.'})
    outputs['catalog.json']=encoded({'format':'rnbo-hardware-smoke-catalog-v1','family':'rnbo-signal-state-followup',
        'surface':'patcher','sample_rate':44100,'block_frames':256,'automatic_warmup_blocks':0,
        'manual_warmup_blocks':4,'timed_blocks':16,'requested_module_max_arena_bytes':4096,
        'reference_sha256':sha((HERE/'reference.py').read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes()),
        'license':'MIT; original graphs and independent references','cases':cases,
        'deferred_reference_design':[{'exact_name':'updown~','status':'reference-design-pending',
            'reason':'Milliseconds are explicit, but exact transient alignment of the adaptive estimator is not specified sufficiently for a meaningful pointwise oracle. No fabricated ideal transient or constant-zero generator reference.'}],
        'scope':'Seven short continuous signal-state scenarios for four exact owners. Compilation alone is not hardware qualification; predeclared mismatches are retained, no DSP changes or optimisation gains claimed.'})
    return outputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--rnbo-package',type=Path,default=Path.home()/'Documents/Max 9/Packages/RNBO')
    args=p.parse_args()
    for name,data in artifacts(args.rnbo_package).items():
        file=HERE/name
        if args.check:
            if not file.is_file()or file.read_bytes()!=data:raise SystemExit('Generated source differs: '+name)
        else:file.write_bytes(data)
    print(('Checked'if args.check else'Wrote')+' seven original signal-state followup fixtures and catalog')


if __name__=='__main__':main()
