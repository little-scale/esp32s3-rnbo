#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Author original bare-value codebox graphs after checking primary metadata."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import reference

HERE = Path(__file__).resolve().parent
PRIMARY = 'source/operators/characterconstants.json'
PRIMARY_SHA256 = 'eb17d1aea665bcf01b03930d1c20dcf55a1c2918dc355a266254a8fe7c0652e0'


def encoded(value):
    return (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()


def identity(name):
    suffix = name[len('CHAR_'):]
    if len(suffix)==1 and suffix.isalpha():
        return 'char-'+('upper-' if suffix.isupper() else 'lower-')+suffix.lower()+'-value'
    return 'char-'+suffix.lower().replace('_','-')+'-value'


def box(name,text,position,code=None):
    result={'id':name,'maxclass':'newobj','text':text,'rnbo_uniqueid':name,
            'patching_rect':position+[220,22]}
    if code is not None:result['rnbo_extra_attributes']={'code':code}
    return {'box':result}


def patch(code):
    boxes=[box('left','in~ 1',[20,25]),box('right','in~ 2',[260,25]),
           box('program','codebox~',[500,25],code),
           box('out-left','out~ 1',[20,115]),box('out-right','out~ 2',[260,115])]
    # Only the referenced variable in2 appears in XAM's physical inlet list.
    # Its ordinal is zero; unused in1 is not a reserved physical inlet slot.
    edges=[(('right',0),('program',0)),
           (('program',0),('out-left',0)),(('program',1),('out-right',0))]
    return {'patcher':{'fileversion':1,'classnamespace':'rnbo','rect':[0,0,1024,720],
                       'boxes':boxes,'lines':[{'patchline':{'source':list(a),'destination':list(b)}} for a,b in edges]}}


def primary(package):
    if json.loads((package/'package-info.json').read_text())['version']!='1.4.4':
        raise ValueError('Character fixtures require authorized RNBO1.4.4 primary metadata')
    data=(package/PRIMARY).read_bytes()
    if hashlib.sha256(data).hexdigest()!=PRIMARY_SHA256:
        raise ValueError('Character primary metadata changed')
    metadata=json.loads(data)
    if len(metadata)!=95:raise ValueError('Expected printable ASCII primary namespace')
    for name,char in reference.CHARACTERS.items():
        entry=metadata[name]
        if entry['exprtext']!=str(ord(char)) or entry['meta'].get('publishAsObject') is not False:
            raise ValueError('Primary numeric character definition differs: '+name)
    return metadata


def files():
    result={};cases=[]
    for model,name in reference.MODEL_NAMES.items():
        slug=identity(name);body='out1 = '+name+';\nout2 = in2;\n'
        program=encoded(patch(body));result[slug+'.rnbopat']=program;result[slug+'.rnbo']=body.encode()
        cases.append({'id':slug,'model':model,'exact_name':name,'canonical_name':name,
            'registry_lookup':name,'syntax':'named-value','surface':'codebox','role':'fx',
            'arity':0,'signal_inputs_per_instance':0,'patch':slug+'.rnbopat','codebox':slug+'.rnbo',
            'patch_sha256':hashlib.sha256(program).hexdigest(),'maximum_absolute_error':0,
            'strict_zero_sign_channels':2,'raw_pilot_channel':1,
            'codebox_inlet_names':['in2'],'codebox_pilot_inlet_ordinal':0,
            'reference_policy':'independent-ascii-ord-and-right-input-word-copy',
            'ascii_character':reference.CHARACTERS[name],'ascii_decimal':ord(reference.CHARACTERS[name]),
            'reference_sources':[{'local_package_path':PRIMARY,'sha256':PRIMARY_SHA256,
                                  'url':'https://rnbo.cycling74.com/codebox/ref/'+name}],
            'wiring':'constant-left-and-codebox-input2-word-copy-right',
            'scope':'One exact RNBO codebox bare numeric character name. Left ASCII value, right input-word pilot; no patcher-object, call-syntax, GenExpr or alias qualification inferred.'})
    if len(cases)!=85 or len({r['id'].casefold()for r in cases})!=85:
        raise ValueError('Exact character spelling/filename collision')
    catalog={'format':'rnbo-hardware-smoke-catalog-v1','family':'rnbo-character-constants',
        'surface':'codebox','sample_rate':44100,'block_frames':256,
        'automatic_warmup_blocks':0,'manual_warmup_blocks':4,'timed_blocks':16,
        'requested_module_max_arena_bytes':4096,'maximum_absolute_error':0,
        'reference_sha256':hashlib.sha256((HERE/'reference.py').read_bytes()).hexdigest(),
        'strict_zero_sign_channels':2,'scope':'85 separate printable ASCII codebox names excluding the ten prior digit scenarios; bounded functional checks only.',
        'cases':cases}
    data=encoded(catalog);result['catalog.json']=data
    parent=hashlib.sha256(data).hexdigest()
    for index,subset in enumerate((cases[:43],cases[43:]),1):
        part=dict(catalog);part['cases']=subset
        part['partition']={'index':index,'total':2,'case_count':len(subset),'parent_catalog_sha256':parent}
        result['catalog-part'+str(index)+'.json']=encoded(part)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rnbo-dir',type=Path,default=Path(os.environ.get('RNBO_DIR',str(Path.home()/'Documents/Max 9/Packages/RNBO'))))
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    primary(args.rnbo_dir)
    for name,data in files().items():
        path=HERE/name
        if args.check:
            if not path.is_file()or path.read_bytes()!=data:raise ValueError('Authored fixture changed: '+name)
        else:path.write_bytes(data)
    print('PASS:85 exact numeric characters; two partitions43/42; primary metadata and original sources agree')


if __name__=='__main__':main()
