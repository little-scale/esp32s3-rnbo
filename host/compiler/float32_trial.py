# SPDX-License-Identifier: MIT
"""Opt-in literal conversion for unreviewed generated DSP, never qualification.

This is a conservative source experiment, not a C++ type checker. Roots must
have signal-buffer signatures. Shared event/setup helpers and visible time or
explicit double state are excluded. Every edit and exclusion is auditable.
"""
from __future__ import annotations
from collections import Counter
import hashlib
from pathlib import Path
import re

from float32_audio import _DECIMAL, float32_audio

PROFILE = 'float32-trial-v1'
_METHOD = re.compile(r'^(?:template\s*<[^\n]+>\s*)?(?P<signature>(?:[\w:&*<> ,]+\s+)?(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?)\{', re.M)
_SENSITIVE = re.compile(r'\b(?:double|long\s+double|Float64\w*|MillisecondTime|SampleTime|TimeValue|TimeMs|Int64|UInt64|u?int64_t|_currentTime|_sampleOffset|_sampleTime|currentTime|getCurrentTime|updateTime|advanceTime|schedule\w*|processClockEvent|clock\w*|mstosamps|sampstoms|msToSamps|sampsToMs)\b', re.I)
_PROTECTED = re.compile(r'(?:^(?:process|initialize\w*|prepare\w*|destroy|assign_defaults|allocate\w*|deallocate\w*|applyState|extractState|get\w*|set\w*|updateTime|advanceTime|schedule\w*|process\w*|mstosamps|sampstoms|msToSamps|sampsToMs)$|_(?:init|reset|dspsetup|set|get|setter|getter)$)')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _methods(masked):
    methods = []
    for m in _METHOD.finditer(masked):
        if m['name'] in ('if', 'while', 'for', 'switch', 'catch'):
            continue
        cursor, depth = m.end(), 1
        while cursor < len(masked) and depth:
            if masked[cursor] == '{': depth += 1
            elif masked[cursor] == '}': depth -= 1
            cursor += 1
        if depth:
            raise ValueError('Float32 trial: unterminated generated method ' + m['name'])
        methods.append(dict(name=m['name'], signature=m['signature'], start=m.start(), end=cursor,
                            body_start=m.end(), body=masked[m.end():cursor]))
    # Nested definitions are not part of the generator layout handled here.
    for a, b in zip(methods, methods[1:]):
        if a['end'] > b['start']:
            raise ValueError('Float32 trial: nested generated methods are not classified')
    return methods


def _reachable(roots, calls):
    pending, seen = list(roots), set()
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name); pending.extend(calls.get(name, ()))
    return seen


def float32_trial(source: bytes, *, code_mask):
    # The reviewed pass remains the exact implementation of Auto. Trial adds
    # no whole-method hash to that catalog and never revisits its edited bodies.
    base, reviewed = float32_audio(source, code_mask=code_mask, profile='float32-auto-v1')
    text = base.decode(); masked = code_mask(text)
    if not isinstance(masked, str) or len(masked) != len(text):
        raise ValueError('Float32 trial: invalid C++ lexical mask')
    methods = _methods(masked)
    counts = Counter(m['name'] for m in methods)
    by_name = {m['name']: m for m in methods if counts[m['name']] == 1}
    called = {name: set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', m['body'])) for name,m in by_name.items()}
    calls = {name: names & by_name.keys() for name,names in called.items()}
    ambiguous = {name for name,count in counts.items() if count != 1}
    roots = {name for name, m in by_name.items() if name.endswith('_perform') and
             re.search(r'\b(?:Sample|SampleValue|Signal)\b[^,()]*\*', m['signature'])}
    audio = _reachable(roots, calls)
    # The process wrapper calls BOTH DSP and clock/event dispatch; it is never
    # edited, but cannot be an event root or it would exclude every DSP method.
    protected = _reachable({name for name in by_name if name != 'process' and _PROTECTED.search(name)}, calls)
    # Member references can hide a double behind an `auto` local. Conservatively
    # identify declarations outside method bodies, not just explicit locals.
    declarations = list(masked)
    for m in methods:
        declarations[m['start']:m['end']] = ' ' * (m['end'] - m['start'])
    fields = set()
    for declaration in re.finditer(r'\b(?:double|Float64\w*|MillisecondTime|SampleTime|TimeValue|Int64|UInt64|u?int64_t)\s+[^;{}]+;', ''.join(declarations)):
        fields.update(re.findall(r'\b[A-Za-z_]\w*\b', declaration[0]))
    field_reads = {name: fields & set(re.findall(r'\bthis\s*->\s*([A-Za-z_]\w*)', m['body'])) for name,m in by_name.items()}
    hazardous = {name for name,m in by_name.items() if _SENSITIVE.search(masked[m['start']:m['end']]) or field_reads[name]}
    while True:
        expanded=hazardous|{name for name,callees in calls.items() if callees & hazardous}
        if expanded==hazardous:break
        hazardous=expanded
    known = {m['method'] for m in reviewed['methods']}
    changed, skipped, edits = [], [], []
    for m in methods:
        name = m['name']
        # Report perform-shaped exclusions too, even when the signature/root
        # cannot be classified. Unreachable ordinary event methods are untouched.
        if name in known or (name not in audio and not name.endswith('_perform')):
            continue
        fragment = masked[m['start']:m['end']]
        prefix = re.match(r'.*?_\d+(?=_|$)', name)
        normalized = re.sub(r'\s+', '', fragment)
        if prefix: normalized = normalized.replace(prefix[0], 'OBJECT')
        row = dict(method=name, signature=' '.join(m['signature'].split()),
                   line=masked.count('\n', 0, m['start']) + 1,
                   kernel_sha256=digest(normalized.encode()),
                   input_method_sha256=digest(text[m['start']:m['end']].encode()),
                   qualification='unverified')
        reason = None
        if counts[name] != 1: reason = 'ambiguous-or-overloaded-method'
        elif name not in audio: reason = 'no-classified-signal-buffer-root'
        elif prefix is None: reason = 'shared-generated-helper-not-object-specific'
        elif _PROTECTED.search(name): reason = 'lifecycle-event-or-shared-time-method'
        elif name in protected: reason = 'also-reachable-from-lifecycle-or-event'
        elif called.get(name,set()) & ambiguous: reason = 'calls-ambiguous-generated-helper'
        elif _SENSITIVE.search(fragment): reason = 'explicit-double-or-time-sensitive-code'
        elif field_reads.get(name):
            reason = 'references-explicit-double-or-time-state'
        elif calls.get(name,set()) & hazardous: reason = 'calls-double-or-time-sensitive-helper'
        if reason:
            skipped.append(dict(row, reason=reason)); continue
        replacements = []
        for token in _DECIMAL.finditer(masked[m['body_start']:m['end']]):
            position = m['body_start'] + token.start()
            replacements.append(dict(line=masked.count('\n', 0, position) + 1,
                                     literal=token[0], replacement=token[0] + 'f'))
            edits.append((m['body_start'] + token.end(), 'f'))
        if not replacements:
            skipped.append(dict(row, reason='no-unsuffixed-decimal-literals')); continue
        local = text[m['start']:m['end']]
        for token in reversed(list(_DECIMAL.finditer(masked[m['body_start']:m['end']]))):
            at=m['body_start']-m['start']+token.end();local=local[:at]+'f'+local[at:]
        changed.append(dict(row, prepared_method_sha256=digest(local.encode()), literal_changes=replacements))
    for at, suffix in sorted(edits, reverse=True):
        text = text[:at] + suffix + text[at:]
    output = text.encode()
    report = dict(name='rnbo-1.4.4-' + PROFILE, version=1, file='rnbo_source.h',
                  profile=PROFILE, qualification='unverified', experimental=True,
                  input_sha256=digest(source), reviewed_source_sha256=digest(base),
                  prepared_sha256=digest(output), transformer_sha256=digest(Path(__file__).read_bytes()),
                  reviewed_pass=reviewed, reviewed_method_count=len(reviewed['methods']),
                  methods=changed, trial_method_count=len(changed), literal_suffix_count=len(edits),
                  skipped_methods=skipped, skipped_method_count=len(skipped),
                  source_changed=output!=source, all_double_removed_claimed=False,
                  native_functional_qualified=False, hardware_qualified=False,
                  unchanged='No type, state/storage, integer literal, shared math runtime, setup/event/clock method or scheduler-clock rewrite in the trial pass',
                  numerical_change='Unreviewed decimal-literal rounding and overload selection; compilation and smoke tests do not establish equivalence',
                  classification_limit='Signal-buffer perform roots and named generated-call reachability only; shared helpers, virtual dispatch and remaining double operations are not converted')
    return output, report
