#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Temporary silent MIDI monitor test; restore the exact selected Main in finally.

Studio must release USB first. Requires examples/midi-monitor.rnbopat compiled
with the current SDK. No physical MIDI hardware: UART uses internal loopback.
The optional player build is installed through Studio's backup/readback path.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host.studio.device import DeviceBridge,FAULT_COUNTERS
from host.compiler.package import parse

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True)
    p.add_argument('--player-build',type=Path)
    p.add_argument('--monitor-package',type=Path,required=True)
    p.add_argument('--restore-package',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();bridge=DeviceBridge()
    evidence=dict(kind='xiao-midi-internal-loopback-v1',physical_midi_tested=False,
        usb_host_attached_tested=False,checks=[],result='failed')
    restore=parse(a.restore_package.read_bytes())
    monitor=parse(a.monitor_package.read_bytes())
    assert monitor['metadata'].get('midi_input_ports')==1
    original=bridge.connect(a.port);d=original['device']
    assert d['board']=='xiao' and d['main']['package_sha256']==restore['package_sha256']
    saved_uart=(d.get('midi') or {}).get('uart_enabled',False)
    changed=False
    def healthy(snapshot):
        device=snapshot['device']
        assert not device.get('fault') and not device.get('allocation_fault') and not device.get('reconstruction_failed')
        for key in FAULT_COUNTERS:assert device.get(key,0)==0,(key,device.get(key))
        return snapshot
    def wait_for(predicate):
        until=time.monotonic()+4
        while True:
            s=healthy(bridge.snapshot())
            if predicate(s):return s
            if time.monotonic()>until:raise RuntimeError('MIDI readback did not reach expected values')
            time.sleep(.04)
    def values(s):return {v['name']:v['actual'] for v in s['parameters']}
    def check(name):evidence['checks'].append(name);print(name,flush=True)
    try:
        if a.player_build:
            bridge.flash(a.player_build,'xiao',a.port,lambda text:print(text,flush=True),expected_kind='player')
        initial=healthy(bridge.snapshot());assert initial['device']['midi_input_version']==1
        evidence['firmware_elf_sha256']=initial['device']['firmware_elf_sha256']
        evidence['monitor_package_sha256']=monitor['package_sha256']
        changed=True
        bridge.upload_package(a.monitor_package,a.port,lambda text:None,expected_sha256=monitor['package_sha256'])
        bridge.configure_midi('uart')
        wait_for(lambda s:s['device']['midi']['playing'] and not s['device']['midi']['recovery_pending'])
        bridge.midi_stream('903c64f8')
        s=wait_for(lambda s:values(s)['last-note']==60 and values(s)['last-velocity']==100)
        check('software stream reaches RNBO notein and midiin')
        count=values(s)['clock-count']
        bridge.midi_stream('f8'*96)
        wait_for(lambda s:values(s)['clock-count']==count+96)
        check('96 software MIDI clocks counted exactly by RNBO')
        # Actual UART TX/RX peripheral and RX driver, with TX never routed to a pad.
        s=bridge.snapshot();rx=s['device']['midi']['bytes_uart'];count=values(s)['clock-count']
        bridge.midi_stream('923d63f83e62',loopback=True)
        s=wait_for(lambda s:values(s)['last-note']==62 and values(s)['last-velocity']==98
            and values(s)['clock-count']==count+1 and s['device']['midi']['bytes_uart']>=rx+6)
        check('UART1 internal loopback: note, running status and interleaved clock reach RNBO')
        count=values(s)['clock-count']
        bridge.midi_stream('f8'*96,loopback=True)
        wait_for(lambda s:values(s)['clock-count']==count+96)
        check('96 UART MIDI clocks counted exactly by RNBO')
        for status in ('fa','fb','fc','f6','f1'+ '01','f2'+'0102','f3'+'03'):
            bridge.midi_stream(status,loopback=True)
            wait_for(lambda s:values(s)['last-byte']==int(status[-2:],16))
        check('UART transport/start/continue/stop and system-common bytes reach midiin')
        bridge.midi_stream('933f64',loopback=True)
        wait_for(lambda s:values(s)['last-note']==63 and values(s)['last-velocity']==100)
        bridge.control(dict(action='pause'));bridge.control(dict(action='resume'))
        s=wait_for(lambda s:values(s)['last-velocity']==0 and not s['device']['midi']['recovery_pending'])
        check('pause/resume releases tracked held notes')
        bridge.midi_stream('fe',loopback=True)
        s=bridge.snapshot();recoveries=s['device']['midi']['recoveries'];time.sleep(.5)
        s=wait_for(lambda s:s['device']['midi']['recoveries']>recoveries)
        check('UART active-sensing timeout performs recovery')
        evidence['monitor_midi_status']=s['device']['midi']
        evidence['monitor_render_us']=s['device']['render_us'];evidence['monitor_peak_us']=s['device']['peak_us']
        evidence['fault_counters']={k:s['device'].get(k) for k in FAULT_COUNTERS}
        assert s['device']['midi']['uart_errors']==0
        evidence['result']='passed'
    finally:
        try:
            if changed:
                bridge.configure_midi('off')
                bridge.upload_package(a.restore_package,a.port,lambda text:None,expected_sha256=restore['package_sha256'])
                snapshot=bridge.snapshot();gen=snapshot['device']['generation']
                for v in original['parameters']:
                    bridge.control(dict(action='param',role='main',generation=gen,index=v['index'],value=v['normalized']))
                bridge.control(dict(action='volume',value=d['volume']))
                if d['paused']:bridge.control(dict(action='pause'))
                if saved_uart:bridge.configure_midi('uart')
                final=healthy(bridge.snapshot())
                assert final['device']['main']['package_sha256']==restore['package_sha256']
                evidence['restored_package_sha256']=restore['package_sha256']
                evidence['restored_volume']=final['device']['volume']
                evidence['restored_uart_enabled']=final['device']['midi']['uart_enabled']
                check('original Main, volume, parameters and UART setting restored')
        except Exception as error:
            evidence['restore_error']=str(error);evidence['result']='failed';raise
        finally:
            bridge.disconnect();a.evidence.parent.mkdir(parents=True,exist_ok=True)
            a.evidence.write_text(json.dumps(evidence,indent=2)+'\n')

if __name__=='__main__':main()
