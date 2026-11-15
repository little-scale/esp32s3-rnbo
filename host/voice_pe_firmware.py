# SPDX-License-Identifier: GPL-3.0-or-later
# Adapted from esp32s3-synthdef host/voice_pe_firmware.py; algorithm/protection retained.
"""Guarded Voice PE installation. Never writes bootloader, NVS or XMOS.

A stock-to-project migration first makes a complete, independently MD5-verified
ESP flash backup. Project updates back up only the application region they can
change, preserving the existing partition table and OTA selection.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import sys
from datetime import datetime, timezone
import zlib

FLASH_BYTES=0x1000000
APP_OFFSET=0x10000
APP_BYTES=0x7c0000
STOCK=(('otadata',1,0,0x9000,0x2000),('phy_init',1,1,0xb000,0x1000),
       ('app0',0,0x10,APP_OFFSET,APP_BYTES),('app1',0,0x11,0x7d0000,0x7c0000),
       ('nvs',1,2,0xf90000,0x6d000))
PROJECT=STOCK[:3]+(('app1',0,0x11,0x7d0000,0x3c0000),
                   ('storage',1,0x82,0xb90000,0x400000),)+STOCK[-1:]
# Shipping unit and downloaded official 26.9.0/2026.9.1 factory layouts differ
# only in NVS's final three pages. Preserve the device's complete NVS extent.
STOCK_LATEST=STOCK[:-1]+(('nvs',1,2,0xf90000,0x70000),)
PROJECT_LATEST=PROJECT[:-1]+STOCK_LATEST[-1:]


def encode_partitions(rows):
    raw=b''.join(struct.pack('<HBBII16sI',0x50aa,t,s,o,n,name.encode().ljust(16,b'\0'),0) for name,t,s,o,n in rows)
    return (raw+b'\xeb\xeb'+b'\xff'*14+hashlib.md5(raw).digest()).ljust(0xc00,b'\xff')



def partitions(data):
    """Require an IDF MD5 table, exact labels and unencrypted entries."""
    rows=[]
    for at in range(0,min(len(data),0xc00),32):
        raw=data[at:at+32]
        if len(raw)!=32:break
        if raw[:2]==b'\xeb\xeb':
            if raw[2:16]!=b'\xff'*14 or hashlib.md5(data[:at]).digest()!=raw[16:]:
                raise ValueError('Invalid partition-table checksum.')
            if any(x!=255 for x in data[at+32:]):raise ValueError('Unexpected data after partition table.')
            return tuple(rows)
        magic,kind,sub,offset,size,name,flags=struct.unpack('<HBBII16sI',raw)
        if magic!=0x50aa or flags or b'\0' not in name:break
        label,padding=name.split(b'\0',1)
        if any(padding):break
        try:label=label.decode('ascii')
        except UnicodeError:break
        rows.append((label,kind,sub,offset,size))
    raise ValueError('Unrecognized or unverified Voice PE partition table.')


def project_name(prefix):
    if len(prefix)<0x70 or prefix[0]!=0xe9 or prefix[0x20:0x24]!=struct.pack('<I',0xabcd5432):return ''
    return prefix[0x50:0x70].split(b'\0',1)[0].decode('ascii',errors='replace')


def active_slot(ota):
    if len(ota)!=8192:raise ValueError('Invalid OTA metadata size.')
    valid=[]
    for at in (0,4096):
        seq=struct.unpack_from('<I',ota,at)[0]
        state,crc=struct.unpack_from('<II',ota,at+24)
        if seq not in (0,0xffffffff) and crc==zlib.crc32(ota[at:at+4],0xffffffff) and state not in (3,4):
            valid.append((seq,state))
    if not valid:
        if ota==b'\xff'*8192:return 0
        raise ValueError('OTA metadata is damaged; recover the device before updating.')
    seq,state=max(valid)
    if state==1:raise ValueError('An OTA verification is pending; finish or recover it before updating.')
    return (seq-1)%2


def image_length(chip,offset,limit):
    header=chip.read_flash(offset,24)
    if len(header)!=24 or header[0]!=0xe9 or not 1<=header[1]<=16 or header[23] not in (0,1):
        raise ValueError('Invalid existing application image.')
    cursor=24
    for _ in range(header[1]):
        if cursor+8>limit:raise ValueError('Application exceeds its partition.')
        segment=chip.read_flash(offset+cursor,8)
        if len(segment)!=8:raise ValueError('Incomplete application header.')
        size=struct.unpack_from('<I',segment,4)[0];cursor+=8+size
        if cursor>limit:raise ValueError('Application exceeds its partition.')
    size=((cursor+16)&~15)+(32 if header[23] else 0)
    if size>limit:raise ValueError('Application exceeds its partition.')
    return size


def verified_image(data):
    from esptool.bin_image import ESP32S3FirmwareImage
    image=ESP32S3FirmwareImage(io.BytesIO(data));image.verify()
    if image.chip_id!=9 or not image.append_digest or image.stored_digest!=image.calc_digest:
        raise ValueError('Application is not a verified ESP32-S3 image.')


def save_region(chip,folder,name,offset,size):
    path=folder/name
    sha,md5=hashlib.sha256(),hashlib.md5()
    with path.open('xb') as out:
        os.chmod(path,0o600)
        for at in range(0,size,0x40000):
            count=min(0x40000,size-at);data=chip.read_flash(offset+at,count)
            if len(data)!=count:raise ValueError('Incomplete backup; nothing will be written.')
            out.write(data);sha.update(data);md5.update(data)
        out.flush();os.fsync(out.fileno())
    if chip.flash_md5sum(offset,size)!=md5.hexdigest():
        raise ValueError('Backup verification failed; nothing will be written.')
    return dict(file=path.name,offset=offset,bytes=size,sha256=sha.hexdigest(),md5=md5.hexdigest(),verified=True)


def install(chip,esptool,table,app,table_path,app_path,backup_root,mac):
    if partitions(table)!=PROJECT:raise ValueError('The build does not have the reviewed Voice PE layout.')
    verified_image(app)
    if b'Home Assistant Voice PE' not in app or project_name(app)!='rnbo_s3_voice-pe' or not 0<len(app)<=0x3c0000:
        raise ValueError('Expected the Voice PE application, not another board build.')
    current=chip.read_flash(0x8000,0x1000);layout=partitions(current)
    if layout not in (STOCK,STOCK_LATEST,PROJECT,PROJECT_LATEST):raise ValueError('Unknown device layout. No flash was changed; restore official Voice PE firmware first.')
    boot=chip.read_flash(0,4)
    if len(boot)!=4 or boot[0]!=0xe9 or boot[2]!=2 or boot[3]>>4!=4:
        raise ValueError('Expected the reviewed 16 MB DIO Voice PE bootloader.')
    migration=layout in (STOCK,STOCK_LATEST)
    prefix=chip.read_flash(APP_OFFSET,256)
    if migration:
        other=chip.read_flash(0x7d0000,256)
        names={project_name(prefix),project_name(other)}
        if not names.intersection({'home-assistant-voice','synthdef_voice_pe_probe'}):
            raise ValueError('Cannot identify stock Voice PE firmware. No flash was changed.')
        # Reusing the tail of an OTA slot is permitted only after checking the
        # entire future filesystem region, not merely its first magic bytes.
        for offset in range(0xb90000,0xf90000,0x40000):
            data=chip.read_flash(offset,0x40000)
            if len(data)!=0x40000 or data!=b'\xff'*0x40000:
                raise ValueError('Future RNBO storage is not wholly erased; preserve/recover this device before migration.')
        span=FLASH_BYTES
    else:
        if project_name(prefix) not in ('waveshare_synthdef','rnbo_s3_voice-pe') or active_slot(chip.read_flash(0x9000,8192))!=0:
            raise ValueError('Expected the Voice PE application in app0; recover the device before updating.')
        old_length=image_length(chip,APP_OFFSET,APP_BYTES)
        span=(max(old_length,len(app))+4095)&~4095
    base=Path(backup_root)/mac;base.mkdir(parents=True,exist_ok=True,mode=0o700)
    folder=Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=base))
    os.chmod(folder,0o700)
    print('Creating verified Voice PE recovery backup: '+str(folder),flush=True)
    record=dict(device_mac=mac,installation='stock migration' if migration else 'application update',
                layout_before=layout,nvs_preserved_bytes=layout[-1][-1],
                application_sha256=hashlib.sha256(app).hexdigest(),files=[],status='backing_up')
    manifest=folder/'backup.json'
    def journal():
        manifest.write_text(json.dumps(record,indent=2)+'\n');os.chmod(manifest,0o600)
    journal()
    record['files'].append(save_region(chip,folder,'esp-flash-before.bin' if migration else 'application-before.bin',0 if migration else APP_OFFSET,span))
    if not migration:
        old=(folder/'application-before.bin').read_bytes()[:old_length]
        verified_image(old)
        if b'Home Assistant Voice PE' not in old:
            raise ValueError('The installed application is for a different board; nothing will be written.')
        record['files'].append(save_region(chip,folder,'boot-and-table-before.bin',0,0x10000))
    record['status']='backup_verified';journal()
    print('Recovery backup verified. Bootloader, NVS and XMOS will not be written.',flush=True)
    regions={'bootloader':(0,0x8000),'phy':(0xb000,0x1000),'nvs':(0xf90000,layout[-1][-1]),
             'app1_and_storage':(0x7d0000,0x7c0000)}
    if not migration:regions.update(partition_table=(0x8000,0x1000),ota=(0x9000,0x2000))
    before={name:chip.flash_md5sum(*region) for name,region in regions.items()}
    record['protected_region_md5']=before
    # esptool consumes paths later. Stage the already validated bytes privately
    # so a changed original file cannot replace what was reviewed/backed up.
    staged_app=folder/'rnbo-application-to-install.bin';staged_app.write_bytes(app);os.chmod(staged_app,0o600)
    writes=[(0x10000,str(staged_app),app)]
    if migration:
        if layout==STOCK_LATEST:
            table=encode_partitions(PROJECT_LATEST)
        table_path=folder/'partitions-preserving-nvs.bin';table_path.write_bytes(table);os.chmod(table_path,0o600)
        record['layout_after']=partitions(table)
        ota=folder/'ota-app0.bin';ota.write_bytes(b'\xff'*8192)
        writes=[(0x8000,str(table_path),table),(0x9000,str(ota),b'\xff'*8192)]+writes
    record.update(status='writing',writes=[dict(offset=o,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for o,_,data in writes]);journal()
    chip.sync()
    if not chip.sync_stub_detected:raise ValueError('Flash loader did not remain synchronized.')
    command=['--chip','esp32s3','--baud','3000000','--after','no_reset_stub','write_flash',
             '--flash_mode','keep','--flash_freq','keep','--flash_size','keep']
    for offset,path,_ in writes:command.extend((hex(offset),path))
    esptool.main(command,esp=chip)
    for offset,_,data in writes:
        if chip.flash_md5sum(offset,len(data))!=hashlib.md5(data).hexdigest():raise ValueError('Written image failed independent verification. Use the saved recovery backup.')
    after={name:chip.flash_md5sum(*region) for name,region in regions.items()}
    if before!=after:
        record.update(status='verification_failed',protected_region_md5_after=after);journal()
        raise ValueError('An untouched region changed; use the saved recovery backup.')
    record['protected_region_md5_after']=after
    record.update(status='installed_verified',untouched_regions_verified=list(regions));journal()
    print('PASS: ESP flash bytes verified; bootloader/NVS/XMOS preserved. Inspect player-info before audio. Backup: '+str(folder),flush=True)
    return record


def build_plan(build_dir, profile):
    """Validate existing artifacts without enumerating or opening a device."""
    from host.profiles import checked
    from tools.build_firmware import source_inventory
    directory=Path(build_dir).resolve(); contract=checked(profile,'voice-pe')
    report=json.loads((directory/'build-report.json').read_text())
    if (report.get('board')!='voice-pe' or report.get('player') is not True or
        report.get('profile')!=profile or report.get('sample_rate')!=contract['sample_rate'] or
        report.get('block_frames')!=256 or report.get('integration_files_sha256')!=source_inventory()):
        raise ValueError('Voice PE build/profile is mismatched or stale; rebuild before installing')
    app=directory/'rnbo_s3_voice-pe.bin';table=directory/'partition_table/partition-table.bin'
    for path in (app,table):
        key=next((k for k in report['artifacts'] if Path(k).name==path.name),None)
        row=report['artifacts'].get(key,{})
        if row.get('bytes')!=path.stat().st_size or row.get('sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Voice PE artifact changed after compilation')
    if partitions(table.read_bytes())!=PROJECT or project_name(app.read_bytes())!='rnbo_s3_voice-pe':
        raise ValueError('Wrong Voice PE layout or application identity')
    return dict(board='voice-pe',profile=profile,rate=contract['sample_rate'],app=str(app),table=str(table),
                app_sha256=hashlib.sha256(app.read_bytes()).hexdigest(),table_sha256=hashlib.sha256(table.read_bytes()).hexdigest(),
                erase_chip=False,writes_bootloader=False,writes_nvs=False,writes_xmos=False,
                requires_matching_xmos=True,hardware_verified=False)


def flash_plan(plan,port,expected_mac,backup_root):
    """Explicit protected ESP-only action; never called by Studio's generic installer."""
    import re
    if not re.fullmatch('[0-9a-f]{12}',expected_mac):raise ValueError('Supply the exact expected board MAC')
    app=Path(plan['app']).read_bytes();table=Path(plan['table']).read_bytes()
    if hashlib.sha256(app).hexdigest()!=plan['app_sha256'] or hashlib.sha256(table).hexdigest()!=plan['table_sha256']:
        raise ValueError('Firmware changed after the installation plan; nothing was opened or written')
    import esptool
    import serial
    with serial.Serial(port,baudrate=115200,timeout=5) as link:
        chip=esptool.detect_chip(port=link,connect_mode='usb_reset',connect_attempts=3)
        try:
            if chip.CHIP_NAME!='ESP32-S3' or chip.secure_download_mode or bytes(chip.read_mac()).hex()!=expected_mac:
                raise ValueError('The selected board does not match the expected ESP32-S3 identity')
            security=chip.get_security_info()
            if security['parsed_flags']['SECURE_BOOT_EN'] or security['parsed_flags']['SECURE_DOWNLOAD_ENABLE'] or security['flash_crypt_cnt'].bit_count()%2:
                raise ValueError('Secured/encrypted devices are not supported')
            if not chip.IS_STUB:chip=chip.run_stub()
            chip.flash_set_parameters(FLASH_BYTES)
            if esptool.cmds.detect_flash_size(chip)!='16MB':raise ValueError('Voice PE requires 16 MiB flash')
            chip.change_baud(3000000)
            return install(chip,esptool,table,app,
                           plan['table'],plan['app'],backup_root,expected_mac)
        finally:
            original=sys.exc_info()[0]
            try:
                chip.write_reg(chip.RTC_CNTL_OPTION1_REG,0,chip.RTC_CNTL_FORCE_DOWNLOAD_BOOT_MASK)
                chip.watchdog_reset()
            except Exception as error:
                if original is None:raise ValueError('Verified flash; automatic restart failed. Reconnect the unit normally.') from error


if __name__=='__main__':
    import argparse
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    parser=argparse.ArgumentParser(description='Protected Voice PE ESP player installer. Default is offline plan only; XMOS is never written.')
    parser.add_argument('--build-dir',type=Path,required=True)
    parser.add_argument('--profile',required=True,choices=('voice-pe-16000-256-v1','voice-pe-48000-256-v1'))
    parser.add_argument('--flash',action='store_true')
    parser.add_argument('--port');parser.add_argument('--mac')
    parser.add_argument('--confirm-xmos-profile',help='Explicit acknowledgement of the separately verified matching XMOS image')
    args=parser.parse_args()
    plan=build_plan(args.build_dir,args.profile)
    if args.flash:
        if not args.port or not args.mac or args.confirm_xmos_profile!=args.profile:
            parser.error('Flashing requires the exact port/MAC and --confirm-xmos-profile matching --profile')
        root=Path(__file__).resolve().parents[1]
        flash_plan(plan,args.port,args.mac,root/'build/private/voice-pe-recovery')
    else:print(json.dumps(plan,indent=2))

