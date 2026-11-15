# SPDX-License-Identifier: MIT
"""Voice PE semantic controls, separate from reserved GPIO bindings."""
SOURCES=('dial','button','microphone_mute')

def extract(parameters):
    rows=[];seen=set()
    for p in parameters:
        meta=p.get('meta',{})
        value=meta.get('esp32') if isinstance(meta,dict) else None
        if not isinstance(value,dict) or value.get('type')!='voice_pe':
            continue
        if set(value)!={'type','input'} or value.get('input') not in SOURCES:
            raise ValueError('Voice PE @meta requires type voice_pe and input dial/button/microphone_mute')
        identity=p.get('paramId')
        if not isinstance(identity,str) or not 1<=len(identity.encode())<=191 or '\0' in identity or value['input'] in seen:
            raise ValueError('Voice PE bindings require stable parameter IDs and one binding per physical control')
        seen.add(value['input']);rows.append(dict(parameter_id=identity,input=value['input']))
    return dict(version=1,board='voice-pe',bindings=rows) if rows else None

def checked_plan(value):
    if (type(value) is not dict or set(value)!={'version','board','bindings'} or
        type(value['version']) is not int or value['version']!=1 or value['board']!='voice-pe' or
        type(value['bindings']) is not list or not 1<=len(value['bindings'])<=3):
        raise ValueError('Invalid Voice PE semantic input plan')
    parameters=[];ids=set()
    for row in value['bindings']:
        if type(row) is not dict or set(row)!={'parameter_id','input'}:
            raise ValueError('Invalid Voice PE binding fields')
        identity=row['parameter_id']
        if not isinstance(identity,str) or identity in ids:
            raise ValueError('Voice PE parameter bindings must be unique')
        ids.add(identity)
        parameters.append(dict(paramId=identity,meta={'esp32':dict(type='voice_pe',input=row['input'])}))
    if extract(parameters)!=value:
        raise ValueError('Invalid Voice PE binding plan')
    return value
