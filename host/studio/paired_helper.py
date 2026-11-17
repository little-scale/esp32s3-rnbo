# SPDX-License-Identifier: MIT
"""Isolated adapter to the companion's guarded XIAO pairing tools.

The two projects both use a `host` namespace, so imports live in a separate
process. No commissioning, partition migration or rate conversion is exposed.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def checked_probe(dual, target, rate=None):
    reply = dual.probe(target['mac'], target['port'])
    if not reply:
        raise ValueError('The selected firmware did not answer the safe runtime probe. Connect a commissioned, runtime-aware XIAO pair; no restart or write was attempted.')
    if reply.get('model') != dual.MODELS['xiao']:
        raise ValueError('The selected device reports '+str(reply.get('model','an unknown board'))+'; choose a XIAO ESP32-S3 pair')
    if reply.get('rate') not in (16000,44100) or (rate is not None and reply['rate'] != rate):
        raise ValueError('The installed XIAO pair rate differs; use matching packages/builds or the guarded pair updater to change rates')
    if reply.get('busy'):
        raise ValueError('The selected runtime is busy or faulted; no switch attempted')
    dual.installed_pair('xiao', target['mac'], reply['rate'])
    return reply


def wait_ready(dual, target, engine, rate):
    deadline = time.monotonic()+35
    while True:
        reply = dual.probe(target['mac'], target['port'])
        if reply:
            if (reply.get('model') != dual.MODELS['xiao'] or reply.get('rate') != rate
                    or reply.get('engine') != engine):
                raise ValueError('The requested runtime/rate did not return; inspect before retrying')
            if not reply.get('busy'):
                dual.installed_pair('xiao', target['mac'], reply['rate'])
                return reply
        if time.monotonic() >= deadline:
            raise ValueError('Runtime startup did not become ready; no mutation was retried')
        time.sleep(.2)


def perform(dual, apps, action, target, rnbo_build, synth_build, *, expected_engine=None,
            app_sha256=None, package=None, package_sha256=None, rate=16000, runner=subprocess.run):
    if type(rate) is not int or rate not in (16000,44100):
        raise ValueError('Choose 16000 or 44100 Hz for the XIAO pair')
    if action == 'options':
        _, image = apps.load_targets('xiao', synth_build, rnbo_build)
        return dict(available=True, rate=rate, application_bytes=len(image),
                    app_sha256=hashlib.sha256(image).hexdigest())
    if action == 'inspect':
        reply = checked_probe(dual, target)
        return dict(engine=reply['engine'], rate=reply['rate'], board='xiao',
                    device_id=target['mac'], ready=True)
    if action == 'upload':
        # Full package validation and pinning precede all USB access.
        raw = Path(package).read_bytes()
        if hashlib.sha256(raw).hexdigest() != package_sha256:
            raise ValueError('The reviewed package changed; no upload started')
        artifact = dual.prepare(Path(package), rate, 'xiao', '')
        current = checked_probe(dual, target, rate)
        if current['engine'] != expected_engine:
            raise ValueError('The running engine changed; inspect the pair again')
        # After the initial pinned-port check, allow this same MAC to re-enumerate
        # under another port name during the reboot.
        result = dual.route(artifact, 'xiao', target['mac'], rate)
        if result.get('verified') is not True or result.get('package_sha256') != package_sha256:
            raise ValueError('RNBO package activation was not verified; inspect before retrying')
        return dict(engine='rnbo', rate=rate, device_id=target['mac'],
                    package_sha256=package_sha256, verified=True)
    if action not in ('rnbo', 'synthdef', 'update'):
        raise ValueError('Unsupported paired action')
    # Firmware bytes must still match the browser's review before any USB query.
    if action == 'update':
        _, image = apps.load_targets('xiao', synth_build, rnbo_build)
        if hashlib.sha256(image).hexdigest() != app_sha256:
            raise ValueError('The RNBO build changed; refresh its review before updating')
    with dual.device_lock(target['mac']):
        current = checked_probe(dual, target, rate)
        if current['engine'] != expected_engine:
            raise ValueError('The running engine changed; inspect the pair again')
        if action == current['engine']:
            return dict(engine=action, rate=rate, device_id=target['mac'], switched=False)
        dual.fade(target['mac'], current['engine'], target['port'])
        if action == 'update':
            # Reuse the complete existing updater: app1 backup/readback, protected
            # regions, other-slot recovery and prior boot-selection restoration.
            command = [sys.executable, str(apps.ROOT/'host/dual_apps.py'), 'update',
                       '--engine', 'rnbo', '--board', 'xiao', '--mac', target['mac'],
                       '--port', target['port'], '--synthdef-build', str(synth_build),
                       '--rnbo-build', str(rnbo_build)]
            result = runner(command, capture_output=True, text=True, timeout=240)
            if result.returncode:
                raise ValueError('Paired update stopped; retain its recovery receipts: ' + result.stderr[-3000:])
            expected = current['engine']
        else:
            dual.boot('xiao', action, target['mac'], target['port'])
            expected = action
        port = dual.wait_port(target['mac'])
        wait_ready(dual, dict(target, port=port), expected, rate)
        return dict(engine=expected, rate=rate, device_id=target['mac'],
                    switched=action != 'update', updated=action == 'update')


if __name__ == '__main__':
    try:
        project, rnbo_root = map(Path, sys.argv[1:3])
        request = json.loads(sys.argv[3])
        sys.path.insert(0, str(project/'host'))
        import dual_upload
        import dual_apps
        rate = request.get('rate',16000)
        result = perform(dual_upload, dual_apps, request.pop('action'), request.pop('target', None),
                         rnbo_root/('build/firmware-xiao-player-dual-native16' if rate==16000 else 'build/firmware-xiao-player'),
                         project/('firmware/build-xiao-native16' if rate==16000 else 'firmware/build-xiao'), **request)
        print(json.dumps(result))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
