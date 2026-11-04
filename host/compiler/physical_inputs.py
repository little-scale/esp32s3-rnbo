# SPDX-License-Identifier: MIT
"""Versioned physical-control metadata. This module never opens a device.

Pin aliases describe the standard XIAO carrier, not ESP32 GPIO numbers. The
player repeats admission against its real board and configured audio pins.
"""
import math
import re

XIAO_GPIO = (1, 2, 3, 4, 5, 6, 43, 44, 7, 8, 9)
MAX_BINDINGS = 16


def gpio_for_pin(pin):
    if not isinstance(pin, str):
        raise ValueError('Physical input pin must be a XIAO A/D label or GPIO<number>')
    if re.fullmatch(r'A(?:[0-5]|[89]|10)', pin):
        return XIAO_GPIO[int(pin[1:])]
    if re.fullmatch(r'D(?:[0-9]|10)', pin):
        return XIAO_GPIO[int(pin[1:])]
    if re.fullmatch(r'GPIO(?:[1-9]|43|44)', pin):
        return int(pin[4:])
    raise ValueError(f'Unknown XIAO physical input pin: {pin}')


def checked_binding(value):
    if type(value) is not dict:
        raise ValueError('esp32 physical input metadata must be an object')
    kind = value.get('type')
    options = {'type', 'pin', 'invert'}
    if kind == 'analog':
        options |= {'raw_min', 'raw_max', 'smooth_ms', 'deadband'}
    elif kind == 'digital':
        options |= {'pull', 'active_low', 'debounce_ms'}
    elif kind == 'touch':
        options |= {'threshold', 'hysteresis', 'debounce_ms'}
    else:
        raise ValueError('esp32 type must be analog, digital or touch')
    unknown = set(value) - options
    if unknown:
        raise ValueError('Unknown esp32 input option(s): ' + ', '.join(sorted(unknown)))
    gpio = gpio_for_pin(value.get('pin'))
    if gpio == 3:
        raise ValueError('D2/A2/GPIO3 is reserved by this profile because it is a boot strapping pin')
    if gpio in (7, 8, 9):
        raise ValueError('D8..D10/GPIO7..9 are reserved for the XIAO I2S audio DAC')
    if kind in ('analog', 'touch') and not 1 <= gpio <= 6:
        raise ValueError(f'{value["pin"]} does not support {kind} in the XIAO input profile')
    result = dict(type=kind, pin=value['pin'], invert=value.get('invert', False))
    if type(result['invert']) is not bool:
        raise ValueError('esp32 invert must be true or false')

    def number(key, default, low, high, integer=False):
        n = value.get(key, default)
        if (type(n) not in ((int,) if integer else (int, float))
                or not low <= n <= high or not math.isfinite(n)):
            raise ValueError(f'esp32 {key} must be {"an integer" if integer else "a number"} from {low} to {high}')
        result[key] = n
        return n

    if kind == 'analog':
        low = number('raw_min', 0, 0, 4094, True)
        high = number('raw_max', 4095, 1, 4095, True)
        if low >= high:
            raise ValueError('esp32 raw_min must be below raw_max')
        number('smooth_ms', 10, 0, 1000)
        number('deadband', 0.002, 0, 0.1)
    else:
        number('debounce_ms', 8 if kind == 'digital' else 12, 0, 1000, True)
        if kind == 'digital':
            result['pull'] = value.get('pull', 'up')
            result['active_low'] = value.get('active_low', True)
            if result['pull'] not in ('up', 'down', 'none') or type(result['active_low']) is not bool:
                raise ValueError('esp32 digital pull must be up/down/none and active_low must be true/false')
        else:
            threshold = number('threshold', 0.08, 0.001, 1)
            hysteresis = number('hysteresis', 0.02, 0, 0.99)
            if hysteresis >= threshold:
                raise ValueError('esp32 touch hysteresis must be below threshold')
    return result


def extract(parameters):
    bindings, pins = [], set()
    for parameter in parameters:
        meta = parameter.get('meta')
        if not isinstance(meta, dict) or 'esp32' not in meta:
            # Do not silently discard a malformed inline mapping.
            if isinstance(meta, str) and 'esp32' in meta:
                raise ValueError('Cannot parse esp32 @meta; use @meta "{\'esp32\':{\'type\':\'analog\',\'pin\':\'A0\'}}"')
            continue
        try:
            binding = checked_binding(meta['esp32'])
            gpio = gpio_for_pin(binding['pin'])
            if gpio in pins:
                raise ValueError('Each physical pin can drive only one parameter; aliases share the same pin')
            pins.add(gpio)
            identity = parameter['paramId']
            if not isinstance(identity, str) or not 1 <= len(identity.encode()) <= 191 or '\0' in identity:
                raise ValueError('Invalid physical input parameter ID')
            bindings.append(dict(parameter_id=identity, **binding))
        except ValueError as error:
            raise ValueError(f'Parameter {parameter.get("name", parameter.get("paramId"))}: {error}') from error
    if len(bindings) > MAX_BINDINGS:
        raise ValueError(f'At most {MAX_BINDINGS} physical input bindings are supported')
    return dict(version=1, board='xiao', bindings=bindings) if bindings else None


def checked_plan(value):
    if (type(value) is not dict or set(value) != {'version', 'board', 'bindings'}
            or type(value['version']) is not int or value['version'] != 1 or value['board'] != 'xiao'
            or type(value['bindings']) is not list or not 1 <= len(value['bindings']) <= MAX_BINDINGS):
        raise ValueError('Invalid physical_inputs v1 XIAO plan')
    parameters = []
    ids = set()
    for row in value['bindings']:
        if (type(row) is not dict or not isinstance(row.get('parameter_id'), str)
                or row['parameter_id'] in ids):
            raise ValueError('Physical input parameter IDs must be unique')
        ids.add(row['parameter_id'])
        parameters.append(dict(paramId=row['parameter_id'], meta={'esp32': {k: v for k, v in row.items() if k != 'parameter_id'}}))
    if extract(parameters) != value:
        raise ValueError('Physical input plan must contain canonical options')
    return value
