"""Back up first, build from this device, verify, then return to normal USB."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
from . import device
from .reporting import message, progress
from .patches import (APP_START, APP_END, FLASH_SIZE, make_target,
                      original_image, recognize, recognize_application,
                      recognize_build, image_build, available_profiles,
                      sha256, changed_sectors, UnsupportedFirmware)

PROFILES = {
    'ultradim':'Constant dim ring (0.1% duty)',
    'dim':'Constant dim ring (1% duty)',
    'timed':'Ring on for approximately 5 seconds after connection',
    'off':'Ring always off',
    'original':'Restore the supported stock application',
}

def default_data_dir():
    return Path(os.environ.get('LOCALAPPDATA',Path.home())) / 'Ultimate2CRing' / 'backups'

class Journal:
    def __init__(self, data_dir):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.folder = Path(data_dir).resolve() / f'{stamp}-{uuid.uuid4().hex[:8]}'
        self.folder.mkdir(parents=True,exist_ok=False)

    def log(self,event,**fields):
        item = {'time':datetime.now(timezone.utc).isoformat(),'event':event,**fields}
        with (self.folder/'journal.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(item)+'\n')
            stream.flush()
            os.fsync(stream.fileno())

    def save(self,name,data):
        path = self.folder/name
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes()!=data:
            raise RuntimeError('Backup did not verify on disk. No firmware will be written.')
        self.log('backup_saved',file=name,bytes=len(data),sha256=sha256(data))
        return path

def read_full(link,label):
    message(label)
    return link.read_range(0,FLASH_SIZE,lambda p: progress(label,p))

def best_effort_log(journal,event,**fields):
    # Losing disk access must never prevent a flash rollback or hide its result.
    try:
        journal.log(event,**fields)
    except OSError as error:
        message(f'Could not save the operation log: {error}')

def double_backup(link,journal):
    first = read_full(link,'Reading all controller memory (first pass)...')
    journal.save('before.bin',first)
    second = read_full(link,'Verifying the full backup (second pass)...')
    if second != first:
        journal.log('backup_mismatch')
        raise RuntimeError('The two memory reads differ. No firmware will be written.')
    journal.log('double_read_verified',sha256=sha256(first))
    message(f'Full backup saved and verified: {journal.folder}')
    return first

def backup(data_dir):
    mode,descriptor = device.discover()
    journal = Journal(data_dir)
    link = device.Normal(descriptor) if mode=='normal' else device.Boot(descriptor)
    try:
        if mode=='normal': journal.log('identity',**link.identify())
        image = double_backup(link,journal)
        try:
            profile = recognize(image)
            journal.log('supported_application',profile=profile)
            message(f'Supported application; current profile: {profile}')
        except UnsupportedFirmware as error:
            journal.log('unsupported_application',reason=str(error))
            message(str(error))
        message('Read-only backup complete. The device mode has not been changed.')
        return journal.folder
    finally:
        link.close()

def perform_write(boot,current,target,journal):
    sectors = changed_sectors(current,target)
    touched = []
    try:
        for address in sectors:
            # Include the sector before erasing it so a partial failure rolls back.
            journal.log('sector_write_started',address=hex(address))
            touched.append(address)
            message(f'Writing application sector {address:#x}...')
            boot.sector(address,target[address:address+4096])
            journal.log('sector_verified',address=hex(address))
        after = read_full(boot,'Verifying all memory after the operation...')
        if after != target:
            raise RuntimeError('Full memory verification differs from the target.')
        journal.log('full_flash_verified',sha256=sha256(after))
    except BaseException as error:
        best_effort_log(journal,'write_failed',reason=str(error))
        message('Operation failed. Restoring the changed sectors from the new backup...')
        try:
            for address in touched:
                boot.sector(address,current[address:address+4096])
            if read_full(boot,'Verifying the rollback...') != current:
                raise RuntimeError('Rollback verification differs from the backup.')
            best_effort_log(journal,'rollback_verified')
        except BaseException as rollback_error:
            best_effort_log(journal,'rollback_failed',reason=str(rollback_error))
            raise RuntimeError(f'Rollback failed. Keep the controller connected in recovery mode. Backups: {journal.folder}') from rollback_error
        boot.reset()
        best_effort_log(journal,'rollback_returned_to_application')
        raise
    boot.reset()
    best_effort_log(journal,'reset_sent')

def apply(profile,data_dir,assume_yes=False,*,confirm=None):
    if profile not in PROFILES: raise ValueError('Unknown profile.')
    mode,descriptor = device.discover()
    journal = Journal(data_dir)
    entered_by_us = False
    normal_backup = None
    expected_version = None
    if mode=='normal':
        normal = device.Normal(descriptor)
        try:
            identity = normal.identify()
            journal.log('identity',**identity)
            message('Checking the exact firmware build before entering recovery...')
            app = normal.read_range(APP_START,APP_END-APP_START)
            expected_version, current_profile = recognize_build(app)
            if identity['firmware_version'] != expected_version:
                raise UnsupportedFirmware('Controller version and exact application build disagree. No writes allowed.')
            if profile not in available_profiles(expected_version):
                raise ValueError(f'This profile is not available for firmware {expected_version}.')
            journal.log('preflight_passed',profile=current_profile,firmware_version=expected_version)
            normal_backup = double_backup(normal,journal)
            if normal_backup[APP_START:APP_END] != app:
                raise RuntimeError('Application changed during the backup. Recovery entry cancelled.')
            normal.enter_boot()
            entered_by_us = True
        finally:
            normal.close()
        time.sleep(1)
        mode,descriptor = device.discover()
        if mode!='boot': raise RuntimeError('The verified bootloader did not appear.')
    boot = device.Boot(descriptor)
    writing_started = False
    try:
        if normal_backup is None:
            current = double_backup(boot,journal)
        else:
            current = read_full(boot,'Checking recovery memory against the saved backup...')
            if current != normal_backup:
                raise RuntimeError('Memory changed between normal and recovery mode. No firmware will be written.')
            journal.log('normal_and_recovery_memory_verified')
        version, current_profile = image_build(current)
        if expected_version and version != expected_version:
            raise UnsupportedFirmware('Recovery application version differs from the normal-mode check.')
        original = original_image(current)
        journal.save('stock-application-restored.bin',original)
        # This second image is derived: its application is stock, and its boot,
        # identity and settings come from the current device, not another unit.
        target = make_target(current,profile)
        journal.save(f'target-{profile}.bin',target)
        sectors = changed_sectors(current,target)
        journal.log('plan',source_profile=current_profile,target_profile=profile,
                    sectors=[hex(a) for a in sectors])
        plan = {'source_profile': current_profile, 'target_profile': profile,
                'backup_folder': str(journal.folder), 'sectors': [hex(a) for a in sectors],
                'firmware_version': version,
                'physical_profile_validated': version=='1.06' or profile in ('original','dim','ultradim')}
        message(f'\nSelected: {PROFILES[profile]}')
        message(f'Current profile: {current_profile}')
        message(f'Application sectors to write: {", ".join(plan["sectors"]) or "none (already installed)"}')
        message(f'Your verified backup: {journal.folder}')
        message('Keep the USB data cable connected until completion.')
        if sectors:
            approved = confirm(plan) if confirm is not None else (
                assume_yes or input('Type APPLY to write this prepared profile, or press Enter to cancel: ').strip()=='APPLY')
            if not approved:
                journal.log('cancelled_before_write')
                boot.reset()
                journal.log('cancel_reset_sent')
                message('Cancelled. No memory was erased or written.')
                return {'outcome': 'cancelled', 'backup_folder': str(journal.folder),
                        'profile': current_profile}
        writing_started = True
        perform_write(boot,current,target,journal)
    except BaseException as error:
        best_effort_log(journal,'operation_failed',reason=str(error))
        if not writing_started and entered_by_us:
            # A failed pre-write check cannot have damaged flash. Restore the
            # normal mode we changed; a manually entered boot mode is retained.
            try: boot.reset()
            except (RuntimeError,OSError): pass
        raise
    finally:
        boot.close()
    try:
        identity = device.wait_normal(target=target,expected_version=version)
    except (RuntimeError,OSError) as error:
        best_effort_log(journal,'normal_verification_failed',reason=str(error))
        raise
    journal.log('normal_usb_verified',**identity)
    message('\nCompleted: full memory and normal USB identity/application verification passed.')
    message('Check the ring, controls and vibration over USB and through the receiver.')
    message(f'Backups and operation log: {journal.folder}')
    return {'outcome': 'completed', 'backup_folder': str(journal.folder), 'profile': profile,
            'firmware_version': version}

def status():
    mode,descriptor = device.discover()
    link = device.Normal(descriptor) if mode=='normal' else device.Boot(descriptor)
    try:
        info = link.identify() if mode=='normal' else {
            'model': '8BitDo Boot', 'firmware_version': 'Application fingerprint required'}
        message(f'{info["model"]}; {info["firmware_version"]}; mode: {mode}')
        stage = 'Checking application compatibility...'
        message(stage)
        application = link.read_range(APP_START,APP_END-APP_START,lambda p: progress(stage,p))
        try:
            version, profile = recognize_build(application)
            if mode=='normal' and info['firmware_version'] != version:
                raise UnsupportedFirmware('Controller version and application fingerprint disagree.')
            info['firmware_version'] = version
            compatible = True
            message(f'Supported build. Current profile: {PROFILES[profile]}')
        except UnsupportedFirmware:
            profile, compatible = None, False
            message('Unsupported application build. Installation is disabled; read-only backup is available.')
        return {**info, 'mode': mode, 'profile': profile, 'compatible': compatible,
                'application_sha256': sha256(application),
                'available_profiles': list(available_profiles(info['firmware_version'])) if compatible else []}
    finally:
        link.close()
