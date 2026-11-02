#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Layout concepts adapted from FM1 RNBO tools/layout.py.
# Copyright (c) 2026 Sebastian Tomczak and contributors.
"""Compile a bounded AMOLED patch view from editable RNBO source and description.

Source anchors and patch-cord midpoints are retained in the JSON report. The
device receives immutable C data; it does not parse arbitrary source or JSON.
Subpatchers remain boxes. No DSP source or patch coordinates are rewritten.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

WIDTH, HEIGHT = 336, 232
MAX_NODES, MAX_SEGMENTS, MAX_PARAMETERS = 96, 384, 128
NO_PARAMETER, NODE_GEN = 255, 1
FONT_METRICS=json.loads(Path(__file__).with_name('graph_font_metrics.json').read_text())


def ascii_text(value, limit):
    return str(value or '').encode('ascii', 'replace').decode().replace('\0','?')[:limit]


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e9


def text_width(text):
    # Exactly the advances emitted in the bundled 12 px LVGL font; six pixels
    # reserve side bearings, padding and the one-pixel border.
    return 6 + sum((FONT_METRICS.get(c,FONT_METRICS['?'])+8)//16 for c in text)


def compile_layout(patch, description, title='RNBO Patch'):
    parameters = description.get('parameters', [])
    if not isinstance(parameters,list) or len(parameters)>MAX_PARAMETERS:
        raise ValueError('Invalid visual parameter description')
    identities = {}
    labels = []
    for index, p in enumerate(parameters):
        if not isinstance(p,dict) or p.get('index')!=index or not isinstance(p.get('paramId'),str):
            raise ValueError('Visual parameters require contiguous exported indices and IDs')
        if p['paramId'] in identities:
            raise ValueError('Duplicate parameter ID')
        identities[p['paramId']] = index
        labels.append({'id':p['paramId'], 'name':ascii_text(p.get('displayName') or p.get('name') or p['paramId'],95),
                       'unit':ascii_text(p.get('unit'),31)})
    report = {'format':'rnbo-s3-visual-v1', 'width':WIDTH, 'height':HEIGHT,
              'title':ascii_text(title,63), 'parameters':labels, 'available':False,
              'nodes':[], 'segments':[], 'source_coordinates':[]}

    def fallback(reason):
        report.update(available=False,reason=reason,nodes=[],segments=[])
        return report

    if patch is None:
        return fallback('Editable patch source unavailable')
    patcher = patch.get('patcher')
    if not isinstance(patcher,dict) or not isinstance(patcher.get('boxes'),list) or not isinstance(patcher.get('lines'),list):
        return fallback('Unsupported patch source')
    if len(patcher['boxes'])>2048 or len(patcher['lines'])>8192:
        return fallback('Source graph exceeds visual admission limits')
    boxes, identifiers = [], set()
    for entry in patcher['boxes']:
        b = entry.get('box') if isinstance(entry,dict) else None
        if not isinstance(b,dict) or not isinstance(b.get('id'),str) or not b['id'] or b['id'] in identifiers:
            return fallback('Invalid or duplicate object identity')
        identifiers.add(b['id'])
        if b.get('maxclass') not in ('comment','panel'):
            boxes.append(b)
    if not boxes:
        return fallback('No visible objects')
    if len(boxes)>MAX_NODES:
        return fallback('More than 96 objects')
    entries, lookup = [], {}
    for b in boxes:
        rect = b.get('patching_rect')
        if not isinstance(rect,list) or len(rect)!=4 or not all(finite_number(v) for v in rect) or min(rect[2:])<=0:
            return fallback('Object positions unavailable or invalid')
        text = b.get('text') or b.get('rnbo_classname') or b.get('maxclass') or '?'
        words = str(text).split() or ['?']
        parameter = identities.get(words[1],NO_PARAMETER) if words[0]=='param' and len(words)>1 else NO_PARAMETER
        label = labels[parameter]['name'].title() if parameter!=NO_PARAMETER else words[0]
        flags = NODE_GEN if words[0] in ('gen','gen~') or patcher.get('classnamespace')=='dsp.gen' else 0
        if b.get('patcher'):
            label = 'gen~' if b['patcher'].get('classnamespace')=='dsp.gen' else 'Subpatch'
            if label=='gen~': flags=NODE_GEN
        if words[0] in ('in~','out~') and len(words)>1:
            label += ' '+words[1]
        if words[0]=='expr' and '440.' in str(text) and '69.' in str(text): label='MIDI > Hz'
        label=ascii_text(label,31)
        while len(label)>1 and text_width(label)>134: label=label[:-1]
        node={'id':b['id'],'label':label,'parameter':parameter,'flags':flags,
              'width':max(22,text_width(label)),'height':18,'inlets':b.get('numinlets',0),'outlets':b.get('numoutlets',0)}
        for key in ('inlets','outlets'):
            if type(node[key]) is not int or not 0<=node[key]<=32: return fallback('Unsupported port count')
        lookup[b['id']]=node
        entries.append((node,rect))
        report['source_coordinates'].append({'id':b['id'],'patching_rect':rect})
    cords=[]
    for entry in patcher['lines']:
        line=entry.get('patchline') if isinstance(entry,dict) else None
        if not isinstance(line,dict): return fallback('Invalid patch cord')
        for key,portkey in (('source','outlets'),('destination','inlets')):
            endpoint=line.get(key)
            if not isinstance(endpoint,list) or len(endpoint)!=2 or endpoint[0] not in lookup or type(endpoint[1]) is not int or not 0<=endpoint[1]<32:
                return fallback('Unsupported patch cord endpoint')
            node=lookup[endpoint[0]]
            node[portkey]=max(node[portkey],endpoint[1]+1)
        mids=line.get('midpoints',[])
        if not isinstance(mids,list) or len(mids)%2 or len(mids)>2*MAX_SEGMENTS or not all(finite_number(v) for v in mids):
            return fallback('Invalid patch cord midpoints')
        cords.append(line)
    xmin,ymin=min(r[0] for _,r in entries),min(r[1] for _,r in entries)
    xmax,ymax=max(r[0] for _,r in entries),max(r[1] for _,r in entries)
    # Reserve the widest compact label, rather than squeezing labels to source
    # rectangles containing long @attribute declarations.
    xscale=(WIDTH-8-max(n['width'] for n,_ in entries))/max(1,xmax-xmin)
    yscale=(HEIGHT-24)/max(1,ymax-ymin)
    def project(x,y):
        return [max(0,min(WIDTH-1,round(4+(x-xmin)*xscale))),
                max(0,min(HEIGHT-1,round(2+(y-ymin)*yscale)))]
    nodes=[]
    for node,rect in entries:
        node['x'],node['y']=project(rect[0],rect[1]);nodes.append(node)
    anchors={n['id']:(n['x'],n['y']) for n in nodes}
    def place(expanded):
        placed=[]
        for n in sorted(nodes,key=lambda n:(anchors[n['id']][1],anchors[n['id']][0],n['id'])):
            x0,y0=anchors[n['id']]
            xs={x0};ys={y0}
            if expanded: xs.update((0,WIDTH-n['width']));ys.update((0,HEIGHT-n['height']))
            for b in placed:
                xs.add(b['x']+b['width']+3);ys.add(b['y']+b['height']+3)
                if expanded: xs.add(b['x']-n['width']-3);ys.add(b['y']-n['height']-3)
            candidates=sorted(((x,y) for x in xs for y in ys if 0<=x<=WIDTH-n['width'] and 0<=y<=HEIGHT-n['height']),
                              key=lambda p:(abs(p[0]-x0)+abs(p[1]-y0),p[1],p[0]))
            for x,y in candidates:
                if all(x+n['width']+2<=b['x'] or b['x']+b['width']+2<=x or y+n['height']+2<=b['y'] or b['y']+b['height']+2<=y for b in placed):
                    n['x'],n['y']=x,y;placed.append(n);break
            else: return False
        return True
    placement='source anchors'
    if not place(False):
        if not place(True): return fallback('Object labels cannot fit legibly')
        placement='expanded placement'
    def port(n,index,count):
        return n['x']+min(n['width']-4,4+round(index*(n['width']-8)/max(1,count-1)))
    segments=[]
    for line in cords:
        src,dst=lookup[line['source'][0]],lookup[line['destination'][0]]
        points=[[port(src,line['source'][1],src['outlets']),src['y']+src['height']-1]]
        mids=line.get('midpoints',[])
        points.extend(project(mids[i],mids[i+1]) for i in range(0,len(mids),2))
        points.append([port(dst,line['destination'][1],dst['inlets']),dst['y']])
        segments.extend(a+b for a,b in zip(points,points[1:]))
        if len(segments)>MAX_SEGMENTS: return fallback('More than 384 wire segments')
    report.update(available=True,placement=placement,nodes=nodes,segments=segments)
    report['source_cords']=cords
    return report


def c_string(text):
    # Fixed ASCII labels, octal escapes cannot run into following hex digits.
    return '"'+''.join(c if 32<=ord(c)<127 and c not in '\\"' else '\\%03o'%ord(c) for c in text)+'"'


def write_layout(source,description,out,title='RNBO Patch'):
    raw=Path(source).read_bytes() if source else None
    if raw and len(raw)>1024*1024: raise ValueError('Visual source exceeds 1 MiB')
    desc_raw=Path(description).read_bytes() if description else b'{"parameters":[]}'
    if len(desc_raw)>1024*1024: raise ValueError('Visual description exceeds 1 MiB')
    report=compile_layout(json.loads(raw) if raw else None,json.loads(desc_raw),title)
    report.update(source_sha256=hashlib.sha256(raw).hexdigest() if raw else None,
                  description_sha256=hashlib.sha256(desc_raw).hexdigest(),
                  compiler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    nodes,segments,params=report['nodes'],report['segments'],report['parameters']
    lines=['/* Generated by host/visual/layout.py. */','#include "patch_layout.h"',
           'static const patch_node nodes[] = {']
    lines.extend('    {'+','.join(str(n[k]) for k in ('x','y','width','height','parameter','inlets','outlets','flags'))+','+c_string(n['label'])+'},' for n in nodes)
    if not nodes: lines.append('    {0},')
    lines+=['};','static const patch_segment segments[] = {']
    lines.extend('    {'+','.join(map(str,s))+'},' for s in segments)
    if not segments: lines.append('    {0},')
    lines+=['};','static const patch_parameter parameters[] = {']
    lines.extend('    {'+c_string(p['name'])+','+c_string(p['unit'])+'},' for p in params)
    if not params: lines.append('    {0},')
    lines+=['};','const patch_layout rnbo_patch_layout = {',
            '    .title='+c_string(report['title'])+',.fallback_reason='+c_string(report.get('reason',''))+',',
            '    .source_sha256='+c_string(report['source_sha256'] or 'none')+',',
            f'    .node_count={len(nodes)},.segment_count={len(segments)},.parameter_count={len(params)},',
            '    .nodes=nodes,.segments=segments,.parameters=parameters','};','']
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'patch_layout.c').write_text('\n'.join(lines))
    (out/'visual.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--description',type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--title',default='RNBO Patch')
    args=parser.parse_args()
    print(json.dumps(write_layout(args.source,args.description,args.out,args.title)))
