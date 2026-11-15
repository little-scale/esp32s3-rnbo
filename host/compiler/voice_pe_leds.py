# SPDX-License-Identifier: MIT
"""Deliberately narrow native outport contract; no source-code rewriting."""
PLAN={'version':1,'board':'voice-pe','port':'led_rgb'}
def checked_plan(value):
    if (type(value) is not dict or set(value)!=set(PLAN) or
        type(value.get('version')) is not int or value!=PLAN):
        raise ValueError('Invalid Voice PE LED output contract')
    return dict(PLAN)
def extract(description):
    ports=description.get('outports',[])
    if ports==[]:return None
    if (type(ports) is not list or len(ports)!=1 or type(ports[0]) is not dict or
        set(ports[0])-{'tag','meta'} or ports[0].get('tag')!='led_rgb'):
        raise ValueError('Only the Voice PE outport led_rgb output is supported')
    return dict(PLAN)


def fixed_constructor_bounds(files):
    """Use the immutable variadic argument count in the reviewed list constructor.

    RNBO's length proxy defeats GCC14 bounds reasoning at the exact 36-value
    inline capacity. These loop bounds equal the constructor's initialized
    length; the generated DSP and runtime list growth rules remain unchanged.
    """
    import hashlib
    name='common/RNBO_List.h';raw=files[name];text=raw.decode()
    start=text.index('\t\ttemplate<typename... Ts> listbase(Ts ... args)')
    end=text.index('\n        // declaration of array constructor',start)
    block=text[start:end]
    if hashlib.sha256(block.encode()).hexdigest()!='45617e9f5b90fd1c6e595ba0401cc1e9c097d5cbf0c63af7c0522dd8feebf14e' or block.count('i < length')!=2:
        raise ValueError('RNBO list variadic constructor differs from the reviewed LED runtime')
    fixed=block.replace('i < length','i < sizeof...(args)')
    files[name]=(text[:start]+fixed+text[end:]).encode()
    return {'name':'rnbo-1.4.4-list-variadic-constant-bounds-v1','file':name,
        'input_sha256':hashlib.sha256(raw).hexdigest(),'prepared_sha256':hashlib.sha256(files[name]).hexdigest(),
        'purpose':'Use immutable argument count for both variadic-constructor copy bounds; no DSP algorithm changes'}
