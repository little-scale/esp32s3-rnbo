# SPDX-License-Identifier: MIT
"""Bind a normal prepared graph to a fresh local RNBO 1.4.4 generation.

This is a compiler correctness gate, not a sandbox for an untrusted generator
or Python caller. The authorised installed package remains a trusted producer.
Certificates exist only in memory and cannot be loaded from export metadata.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
_ISSUER = object()


def _canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _inventory(files):
    if type(files) is not dict or not all(type(n) is str and type(b) is bytes for n, b in files.items()):
        raise ValueError('regenerated graph requires an immutable byte file map')
    return tuple((name, _hash(data)) for name, data in sorted(files.items()))


class RegeneratedGraph:
    """Process-issued whole-map match; persisted JSON is never authority."""
    __slots__ = ('_files', '_role', '_class_name', '_record', '_brand')

    def __init__(self, token=None, *, files=None, role=None, class_name=None, record=None):
        if token is not _ISSUER:
            raise ValueError('RegeneratedGraph must be issued by fresh regeneration')
        object.__setattr__(self, '_files', _inventory(files))
        object.__setattr__(self, '_role', role)
        object.__setattr__(self, '_class_name', class_name)
        object.__setattr__(self, '_record', _canonical(record))
        object.__setattr__(self, '_brand', _ISSUER)

    def __setattr__(self, name, value):
        raise AttributeError('RegeneratedGraph certificates are immutable')

    @property
    def record(self):
        return json.loads(self._record)

    def matches(self, files, role, class_name='rnbos3patch'):
        if (type(self) is not RegeneratedGraph or getattr(self, '_brand', None) is not _ISSUER or
                type(role) is not str or role != self._role or
                type(class_name) is not str or class_name != self._class_name):
            return False
        try:
            return _inventory(files) == self._files
        except (ValueError, TypeError):
            return False


def regenerate(files, role, class_name='rnbos3patch'):
    """Re-export and strictly prepare, comparing every one of the 42 files.

    All work is in a new temporary directory. Original exports and installed
    package files are read only. A mismatch never produces a certificate.
    """
    inventory = _inventory(files)
    if type(role) is not str or role not in ('main', 'fx') or class_name != 'rnbos3patch':
        raise ValueError('regenerated graph requires Main/FX and class rnbos3patch')
    if len(files) != 42 or not {'source.rnbopat', 'generator.json', 'patch_config.h'} <= files.keys():
        raise ValueError('regenerated graph requires the complete normal local export')
    try:
        generator = json.loads(files['generator.json'])
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError('invalid local generator metadata') from exc
    expected = {'generator': 'rnbo-s3-flat-rnbopat-v2', 'rnbo_version': '1.4.4',
                'class_name': class_name, 'sample_rate': 44100, 'block_frames': 256,
                'voices': 1, 'topology': 'single-export'}
    if type(generator) is not dict or any(type(generator.get(key)) is not type(value) or generator[key] != value
           for key, value in expected.items()):
        raise ValueError('regenerated graph requires a single-voice RNBO 1.4.4 flat export')
    if generator.get('source_sha256') != _hash(files['source.rnbopat']):
        raise ValueError('editable graph does not match generator metadata')
    tools = [Path(__file__), ROOT / 'host/compiler/prepare.py',
             ROOT / 'archive/importer/integer-ui/export.mjs', ROOT / 'archive/importer/integer-ui/patcher.mjs',
             ROOT / 'archive/importer/integer-ui/inspect_onepole_graph.mjs']
    before = {str(path.relative_to(ROOT)): _hash(path.read_bytes()) for path in tools}
    commands = []

    def run(command, *, env=None):
        try:
            result = subprocess.run(command, capture_output=True, timeout=120, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f'regenerated graph tool could not complete: {exc}') from exc
        commands.append({'tool': Path(command[0]).name,
                         'script': Path(command[1]).name if len(command) > 1 else None,
                         'returncode': result.returncode,
                         'stdout_sha256': _hash(result.stdout), 'stdout_bytes': len(result.stdout),
                         'stderr_sha256': _hash(result.stderr), 'stderr_bytes': len(result.stderr)})
        if result.returncode:
            raise ValueError('regenerated graph rejected: ' + result.stderr.decode(errors='replace')[-4000:])
        return result.stdout

    # Import locally: prepare invokes this gate after completing the ordinary
    # fixes. The recursive preparation below has every optional adapter OFF.
    from prepare import prepare
    with tempfile.TemporaryDirectory(prefix='rnbo-regenerate-') as temp:
        work = Path(temp)
        patch = work / 'source.rnbopat'
        patch.write_bytes(files['source.rnbopat'])
        inspector = tools[-1]
        try:
            inspection = json.loads(run(['node', str(inspector), str(patch)]))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValueError(f'regenerated graph inspection failed: {exc}') from exc
        if (type(inspection) is not dict or
                type(inspection.get('package_directory')) is not str or
                not inspection['package_directory'] or
                inspection.get('rnbo_version') != '1.4.4' or
                inspection.get('policy') != 'flat-builtin-onepole-v1' or
                type(inspection.get('objects')) is not list):
            raise ValueError('regenerated graph inspector returned incomplete metadata')
        if (inspection.get('source_sha256') != _hash(files['source.rnbopat']) or
                inspection.get('inspector_sha256') != before[str(inspector.relative_to(ROOT))] or
                inspection.get('package_info_sha256') != generator.get('package_info_sha256') or
                inspection.get('generator_package_sha256') != generator.get('generator_package_sha256')):
            raise ValueError('regenerated graph package or inspector identity differs')
        env = dict(os.environ, RNBO_DIR=inspection['package_directory'], BABEL_DISABLE_CACHE='1')
        node_version = run(['node', '--version'], env=env).decode().strip()
        raw = work / 'raw'
        run(['node', str(ROOT / 'archive/importer/integer-ui/export.mjs'), str(patch), '--out', str(raw), '--voices', '1'], env=env)
        normal = work / 'normal'
        manifest = prepare(raw, normal, class_name, role)
        description = json.loads((normal / 'description.json').read_bytes())
        if type(description.get('numMidiInputPorts')) is not int or description['numMidiInputPorts'] != 0:
            raise ValueError('regenerated graph MIDI input is outside this admission envelope')
        provenance = json.loads((normal / 'provenance.json').read_bytes())
        fresh = {name: (normal / name).read_bytes() for name in provenance['prepared_files_sha256']}
        different = sorted(set(files) ^ set(fresh) | {name for name in files.keys() & fresh.keys() if files[name] != fresh[name]})
        if different:
            raise ValueError('fresh regeneration differs in: ' + ', '.join(different[:12]))
        fields = {'rnbo_version': '1.4.4', 'class_name': class_name, 'role': role,
                  'audio_inputs': 2 if role == 'fx' else 0, 'audio_outputs': 2,
                  'sample_rate': 44100, 'block_frames': 256, 'voices': 1,
                  'voice_topology': 'single-export', 'numerical_profile': 'float32-strict',
                  'scheduler_time': 'float64', 'midi_output_ports': 0,
                  'midi_output_policy': 'reject', 'required_host_services': []}
        if any(type(manifest.get(key)) is not type(value) or manifest[key] != value
               for key, value in fields.items()):
            raise ValueError('fresh regeneration has unsupported role, services or execution settings')
        # Repeat inspection to catch changed package metadata/adapter identity
        # during generation. Trust in the installed producer is still required.
        try:
            again = json.loads(run(['node', str(inspector), str(patch)], env=env))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValueError('regenerated graph repeat inspection is invalid') from exc
        if again != inspection:
            raise ValueError('graph inspection changed during regeneration')
    if _inventory(files) != inventory or any(_hash(path.read_bytes()) != before[str(path.relative_to(ROOT))] for path in tools):
        raise ValueError('inputs or compiler tools changed during regeneration')
    public_inspection = {key: value for key, value in inspection.items() if key != 'package_directory'}
    record = {'version': 1, 'method': 'fresh-local-generation-and-normal-prepare',
              'whole_prepared_file_map_sha256': _hash(_canonical(dict(inventory))),
              'prepared_files': len(files), 'every_prepared_byte_equal': True,
              'settings': fields, 'inspection': public_inspection, 'tools_sha256': before,
              'node_version': node_version,
              'commands': commands, 'target_execution': False,
              'trust_boundary': 'authorised installed RNBO producer and compiler process; not an untrusted-code sandbox'}
    return RegeneratedGraph(_ISSUER, files=files, role=role, class_name=class_name, record=record)
