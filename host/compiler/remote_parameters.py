# SPDX-License-Identifier: MIT
"""Optional native-export metadata for the reduced OSC parameter interface."""
MAX_LABELS = 32

def address(value):
    if (not isinstance(value,str) or not 1 < len(value.encode()) <= 255 or
        not value.startswith('/') or value.endswith('/') or '//' in value or
        any(c in value for c in ' \0\t\r\n*?,[]{}#') or value=='/rnbo' or value.startswith('/rnbo/')):
        raise ValueError('OSC alias must be a literal absolute address outside /rnbo/, at most 255 bytes')
    return value

def extract(parameters):
    rows=[]
    for p in parameters:
        row={'parameter_id':p['paramId']}
        if any(type(p[k]) is not bool for k in ('visible','debug') if k in p):
            raise ValueError('Parameter visibility/debug flags must be booleans')
        if p.get('visible',True) is False or p.get('debug',False) is True:row['visible']=False
        labels=p.get('enumValues') or []
        if labels:
            if (not isinstance(labels,list) or
                any(not isinstance(s,str) or not s or '\0' in s for s in labels) or
                len(set(labels))!=len(labels) or p.get('steps')!=len(labels) or
                p.get('minimum')!=0 or p.get('maximum')!=len(labels)-1):
                raise ValueError('OSC enum labels require unique nonempty labels, steps=count and range 0..count-1')
            if len(labels)>MAX_LABELS or any(len(s.encode())>63 for s in labels):
                # An optional network bound must not reject otherwise valid DSP.
                row['visible']=False
            else:
                row['enum_values']=labels
        meta=p.get('meta')
        if isinstance(meta,str) and 'osc' in meta:
            raise ValueError('Cannot parse OSC metadata; export an OSC JSON object')
        osc=meta.get('osc') if isinstance(meta,dict) else None
        if isinstance(osc,str):row['osc']={'address':address(osc),'normalized':False}
        elif isinstance(osc,dict):
            if set(osc)-{'addr','in','out','norm'} or any(type(osc[k]) is not bool for k in ('in','out','norm') if k in osc):
                raise ValueError('Unsupported OSC metadata options')
            addr=address(osc.get('addr'))
            incoming=osc.get('in',not osc.get('out',False))
            if incoming:row['osc']={'address':addr,'normalized':osc.get('norm',False)}
        elif osc is not None and osc is not False:
            raise ValueError('OSC metadata must be an address, object or false')
        if len(row)>1:rows.append(row)
    if not rows:return None
    return checked_plan({'version':1,'parameters':rows})

def checked_plan(plan):
    if (type(plan) is not dict or set(plan)!={'version','parameters'} or type(plan['version']) is not int or
        plan['version']!=1 or type(plan['parameters']) is not list or not 1<=len(plan['parameters'])<=128):
        raise ValueError('Invalid remote_parameters schema')
    ids=set();aliases=set()
    for row in plan['parameters']:
        if type(row) is not dict or set(row)-{'parameter_id','visible','enum_values','osc'} or len(row)<2:
            raise ValueError('Invalid remote parameter entry')
        identity=row.get('parameter_id')
        if not isinstance(identity,str) or not 1<=len(identity.encode())<=191 or '\0' in identity or identity in ids:
            raise ValueError('Invalid remote parameter ID')
        ids.add(identity)
        if 'visible' in row and row['visible'] is not False:raise ValueError('Only hidden visibility overrides are canonical')
        if 'enum_values' in row:
            labels=row['enum_values']
            if (type(labels) is not list or not 1<=len(labels)<=MAX_LABELS or any(type(s) is not str or not 1<=len(s.encode())<=63 or '\0' in s for s in labels) or len(set(labels))!=len(labels)):
                raise ValueError('Invalid remote enum labels')
        if 'osc' in row:
            a=row['osc']
            if type(a) is not dict or set(a)!={'address','normalized'} or type(a['normalized']) is not bool:
                raise ValueError('Invalid OSC alias')
            addr=address(a['address'])
            if addr in aliases:raise ValueError('Duplicate OSC alias')
            aliases.add(addr)
    return plan
