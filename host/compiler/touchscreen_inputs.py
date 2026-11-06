# SPDX-License-Identifier: MIT
"""Inline RNBO metadata for the AMOLED patch-area touchscreen; no device IO."""
import math

MAX_BINDINGS = 16


def checked_binding(value):
    if type(value) is not dict or set(value) - {'type', 'axis', 'invert', 'deadband'} or value.get('type') != 'touchscreen':
        raise ValueError('Use esp32 type touchscreen with axis x, y or pressed; only invert and deadband are optional')
    axis = value.get('axis')
    if type(axis) is not str or axis not in ('x', 'y', 'pressed'):
        raise ValueError('Touchscreen axis must be x, y or pressed')
    invert, deadband = value.get('invert', False), value.get('deadband', 0.002)
    if type(invert) is not bool or type(deadband) not in (int, float) or not math.isfinite(deadband) or not 0 <= deadband <= .1:
        raise ValueError('Touchscreen invert must be boolean and deadband must be 0–0.1')
    return dict(axis=axis, invert=invert, deadband=deadband)


def extract(parameters):
    bindings, ids = [], set()
    for parameter in parameters:
        meta = parameter.get('meta')
        if not isinstance(meta, dict) or not isinstance(meta.get('esp32'), dict) or meta['esp32'].get('type') != 'touchscreen':
            continue
        try:
            value = checked_binding(meta['esp32'])
            identity = parameter.get('paramId')
            if not isinstance(identity, str) or not 1 <= len(identity.encode()) <= 191 or '\0' in identity or identity in ids:
                raise ValueError('Touchscreen parameter IDs must be bounded and unique')
            ids.add(identity); bindings.append(dict(parameter_id=identity, **value))
        except ValueError as error:
            raise ValueError(f'Parameter {parameter.get("name", parameter.get("paramId"))}: {error}') from error
    if len(bindings) > MAX_BINDINGS:
        raise ValueError(f'At most {MAX_BINDINGS} touchscreen bindings are supported')
    return dict(version=1, board='amoled', area='patch', bindings=bindings) if bindings else None


def checked_plan(value):
    if (type(value) is not dict or set(value) != {'version','board','area','bindings'} or type(value['version']) is not int
            or value['version'] != 1 or value['board'] != 'amoled' or value['area'] != 'patch'
            or type(value['bindings']) is not list or not 1 <= len(value['bindings']) <= MAX_BINDINGS):
        raise ValueError('Invalid touchscreen_inputs v1 AMOLED patch-area plan')
    parameters = []
    for row in value['bindings']:
        if type(row) is not dict or set(row) != {'parameter_id','axis','invert','deadband'}:
            raise ValueError('Invalid canonical touchscreen binding')
        parameters.append(dict(paramId=row['parameter_id'], meta={'esp32':dict(type='touchscreen', **{k:v for k,v in row.items() if k!='parameter_id'})}))
    if extract(parameters) != value:
        raise ValueError('Touchscreen plan must contain canonical options')
    return value
