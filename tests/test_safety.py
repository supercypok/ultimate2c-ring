import contextlib
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from ultimate2c_ring import patches
from ultimate2c_ring import app
from ultimate2c_ring.device import Boot,Normal,Link,crc16

def fixtures():
    # Synthetic images only; no controller dump or device identity is shipped.
    original=bytearray(patches.FLASH_SIZE)
    original[0xA4A2]=1
    original[0xD48A]=0x19
    original[0xD598:0xD59C]=bytes.fromhex('ff973c9f')
    original[patches.CAVE_START:patches.CAVE_END]=b'\xff'*120
    struct.pack_into('<I',original,patches.CRC_AT,0x12345678)
    result={'original':bytes(original)}
    for profile in ('off','timed','dim','ultradim'):
        image=bytearray(original)
        image[0xA4A2]=0
        if profile=='off': image[0xD48A]=13
        else:
            image[0xD598:0xD59C]=bytes.fromhex('0a90329f')
            code=patches.TIMED_HELPER if profile=='timed' else patches.DIM_HELPER
            if profile=='ultradim':
                code=code.replace(bytes.fromhex('0a00e803'),bytes.fromhex('0100e803'))
            image[patches.CAVE_START:patches.CAVE_START+len(code)]=code
        checksum=0x12345678 ^ __import__('zlib').crc32(original[0x6000:patches.CRC_AT]) ^ __import__('zlib').crc32(image[0x6000:patches.CRC_AT])
        struct.pack_into('<I',image,patches.CRC_AT,checksum)
        result[profile]=bytes(image)
    fingerprints={p:patches.sha256(b[patches.APP_START:patches.APP_END]) for p,b in result.items()}
    return result,fingerprints

class PatchSafety(unittest.TestCase):
    def setUp(self):
        self.images,self.fingerprints=fixtures()
        self.guard=patch.dict(patches.FINGERPRINTS,self.fingerprints,clear=True)
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_all_profile_transitions_preserve_identity_and_settings(self):
        for source in self.images.values():
            unit=bytearray(source)
            unit[:0x6000]=bytes(range(256))*96
            unit[0x20000:]=bytes(reversed(range(256)))*1536
            unit=bytes(unit)
            for profile,expected in self.images.items():
                with self.subTest(source=patches.recognize(unit),target=profile):
                    target=patches.make_target(unit,profile)
                    self.assertEqual(target[0x6000:0x20000],expected[0x6000:0x20000])
                    self.assertEqual(target[:0x6000],unit[:0x6000])
                    self.assertEqual(target[0x20000:],unit[0x20000:])
                    self.assertTrue(set(patches.changed_sectors(unit,target))<=set(patches.SECTORS))

    def test_unknown_or_corrupt_app_is_rejected(self):
        bad=bytearray(self.images['original']);bad[0x9000]^=1
        with self.assertRaises(patches.UnsupportedFirmware): patches.make_target(bad,'dim')
        with self.assertRaises(patches.UnsupportedFirmware): patches.make_target(bad[:100],'off')

    def test_timed_to_dim_changes_one_sector(self):
        self.assertEqual(patches.changed_sectors(self.images['timed'],self.images['dim']),[0x18000])

    def test_106_ultradim_changes_only_pwm_compare_byte(self):
        dim,ultra=self.images['dim'],self.images['ultradim']
        literal=patches.CAVE_START+patches.DIM_HELPER.index(bytes.fromhex('0a00e803'))
        self.assertEqual([i for i,(a,b) in enumerate(zip(dim,ultra)) if a!=b],[literal])
        self.assertEqual(patches.changed_sectors(dim,ultra),[0x18000])

class ProtocolSafety(unittest.TestCase):
    def test_crc16_reference(self):
        self.assertEqual(crc16(b'123456789'),0x4B37)

    def test_low_level_writes_reject_protected_addresses(self):
        boot=Boot.__new__(Boot)
        for address in (0,0x5000,0x6000,0x9000,0x19000,0x20000,0x7F000):
            with self.subTest(address=address):
                with self.assertRaises(ValueError): boot.sector(address,b'\0'*4096)
                with self.assertRaises(ValueError): boot.request(4,address,extent=4096)
                with self.assertRaises(ValueError): boot.request(3,address,32,b'\0'*32)

    def test_read_chunking_avoids_special_lengths(self):
        class Reader(Link):
            def __init__(self): self.requests=[]
            def read(self,address,count):
                self.requests.append((address,count))
                self.assert_count(count)
                return b'a'*count
            def assert_count(self,count):
                if count in (4,6,12): raise AssertionError('Special count')
        for length in range(1,150):
            reader=Reader()
            self.assertEqual(len(reader.read_range(123,length)),length)
            self.assertEqual(reader.requests[-1][0]+reader.requests[-1][1],123+length)

    def test_boot_write_packet_shape_and_crc(self):
        boot=Boot.__new__(Boot);packets=[]
        boot.send=packets.append
        reply=bytearray(64);reply[:6]=bytes.fromhex('000500000300')
        boot.reply=lambda:bytes(reply)
        data=bytes(range(32));boot.request(3,0x18400,32,data)
        packet=packets[0]
        self.assertEqual(len(packet),65)
        self.assertEqual(packet[:4],bytes.fromhex('00050300'))
        self.assertEqual(struct.unpack_from('<H',packet,8)[0],crc16(data))
        self.assertEqual(struct.unpack_from('<I',packet,14)[0],0x18400)
        self.assertEqual(packet[18:50],data)

    def test_receiver_identity_is_rejected(self):
        normal=Normal.__new__(Normal);normal.send=lambda p:None
        response=bytearray(64);response[:3]=bytes.fromhex('02226a');response[6:8]=bytes.fromhex('1031')
        normal.reply=lambda:bytes(response)
        with self.assertRaises(RuntimeError): normal.identify()

class FakeJournal:
    folder='test-backups'
    def __init__(self): self.events=[]
    def log(self,event,**fields): self.events.append(event)

class FakeBoot:
    def __init__(self,image,fail=False,rollback_fail=False,corrupt_verify=False):
        self.image=bytearray(image);self.fail=fail;self.rollback_fail=rollback_fail
        self.corrupt_verify=corrupt_verify;self.calls=[];self.reset_called=False
    def sector(self,address,data):
        self.calls.append(address)
        self.image[address:address+4096]=data
        if self.fail and len(self.calls)==1:
            self.image[address]=0
            raise RuntimeError('Simulated interrupted sector write')
        if self.rollback_fail and len(self.calls)>1:
            raise RuntimeError('Simulated rollback failure')
    def read_range(self,address,size,progress=None):
        value=bytes(self.image[address:address+size])
        if self.corrupt_verify:
            self.corrupt_verify=False
            value=bytes([value[0]^1])+value[1:]
        return value
    def reset(self): self.reset_called=True

class TransactionSafety(unittest.TestCase):
    def run_write(self,boot,current,target,journal):
        with contextlib.redirect_stdout(io.StringIO()):
            return app.perform_write(boot,current,target,journal)

    def test_partial_sector_failure_restores_snapshot(self):
        images,_=fixtures();current=images['timed'];target=images['dim']
        boot=FakeBoot(current,fail=True);journal=FakeJournal()
        with self.assertRaises(RuntimeError): self.run_write(boot,current,target,journal)
        self.assertEqual(bytes(boot.image),current)
        self.assertTrue(boot.reset_called)
        self.assertIn('rollback_verified',journal.events)

    def test_full_verify_failure_restores_snapshot(self):
        images,_=fixtures();current=images['original'];target=images['off']
        boot=FakeBoot(current,corrupt_verify=True);journal=FakeJournal()
        with self.assertRaises(RuntimeError): self.run_write(boot,current,target,journal)
        self.assertEqual(bytes(boot.image),current)
        self.assertTrue(boot.reset_called)

    def test_failed_rollback_keeps_recovery_mode(self):
        images,_=fixtures();current=images['timed'];target=images['dim']
        boot=FakeBoot(current,fail=True,rollback_fail=True);journal=FakeJournal()
        with self.assertRaisesRegex(RuntimeError,'Keep the controller connected'):
            self.run_write(boot,current,target,journal)
        self.assertFalse(boot.reset_called)
        self.assertIn('rollback_failed',journal.events)

    def test_disk_failure_does_not_prevent_rollback(self):
        class DiskFailureJournal(FakeJournal):
            def log(self,event,**fields):
                if event!='sector_write_started': raise OSError('Disk unavailable')
                super().log(event,**fields)
        images,_=fixtures();current=images['timed'];target=images['dim']
        boot=FakeBoot(current,fail=True);journal=DiskFailureJournal()
        with self.assertRaises(RuntimeError): self.run_write(boot,current,target,journal)
        self.assertEqual(bytes(boot.image),current)
        self.assertTrue(boot.reset_called)

    def test_success_verifies_before_reset(self):
        images,_=fixtures();current=images['timed'];target=images['dim']
        boot=FakeBoot(current);journal=FakeJournal()
        self.run_write(boot,current,target,journal)
        self.assertEqual(bytes(boot.image),target)
        self.assertTrue(boot.reset_called)
        self.assertLess(journal.events.index('full_flash_verified'),journal.events.index('reset_sent'))

class WorkflowSafety(unittest.TestCase):
    def setUp(self):
        self.images,fingerprints=fixtures()
        self.version='1.06'
        self.requested_profile='dim'
        self.current=self.images['timed']
        self.normal_closed=False
        self.entered=False
        self.reads=0
        self.normal_full_reads=0
        self.backup_failure=False
        self.mismatch=False
        self.journal=FakeJournal()
        self.journal.folder=Path('virtual-backups')
        self.saved={}
        def save(name,data):
            if self.backup_failure: raise OSError('Backup disk full')
            self.saved[name]=bytes(data)
            return name
        self.journal.save=save
        owner=self
        class Normal:
            def __init__(self,descriptor): pass
            def identify(self): return {'model':'Ultimate 2C Wireless','firmware_version':owner.version}
            def read_range(self,address,size,progress=None):
                value=owner.current[address:address+size]
                if address==0 and size==patches.FLASH_SIZE:
                    owner.normal_full_reads+=1
                    if owner.mismatch and owner.normal_full_reads==2:
                        return bytes([value[0]^1])+value[1:]
                return value
            def enter_boot(self):
                if owner.normal_full_reads!=2 or 'before.bin' not in owner.saved:
                    raise AssertionError('Recovery entered before the complete double backup')
                owner.entered=True
            def close(self): owner.normal_closed=True
        class Boot(FakeBoot):
            def __init__(self,descriptor): super().__init__(owner.current)
            def read_range(self,address,size,progress=None):
                owner.reads+=1
                value=super().read_range(address,size,progress)
                return value
            def sector(self,address,data):
                # Enforce the workflow invariant at the simulated erase boundary.
                if owner.reads<1 or owner.normal_full_reads<2 or 'before.bin' not in owner.saved or f'target-{owner.requested_profile}.bin' not in owner.saved:
                    raise AssertionError('Write before mandatory verified backup and target')
                return super().sector(address,data)
            def close(self): pass
        self.boot=Boot({})
        for guard in (
            patch.dict(patches.FINGERPRINTS,fingerprints,clear=True),
            patch.object(app,'Journal',lambda directory:self.journal),
            patch.object(app.device,'discover',side_effect=[('normal',{}),('boot',{})]),
            patch.object(app.device,'Normal',Normal),
            patch.object(app.device,'Boot',lambda descriptor:self.boot),
            patch.object(app.device,'wait_normal',return_value={'firmware_version':'1.06'}),
            patch.object(app.time,'sleep',lambda delay:None),
        ):
            guard.start();self.addCleanup(guard.stop)

    def apply(self,yes=True,profile='dim'):
        self.requested_profile=profile
        with contextlib.redirect_stdout(io.StringIO()):
            return app.apply(profile,Path('unused-data-directory'),yes)

    def test_backup_and_target_are_verified_before_writes(self):
        self.apply()
        self.assertEqual(self.saved['before.bin'],self.current)
        self.assertEqual(self.saved['target-dim.bin'],self.images['dim'])
        self.assertEqual(bytes(self.boot.image),self.images['dim'])
        self.assertEqual(self.reads,2)
        self.assertEqual(self.normal_full_reads,2)
        self.assertIn('normal_usb_verified',self.journal.events)

    def test_unknown_app_never_enters_bootloader(self):
        current=bytearray(self.current);current[0x9000]^=1;self.current=bytes(current)
        with self.assertRaises(patches.UnsupportedFirmware): self.apply()
        self.assertFalse(self.entered)
        self.assertTrue(self.normal_closed)
        self.assertFalse(self.boot.calls)

    def test_version_and_application_mismatch_never_enters_recovery(self):
        self.version='1.09'
        with self.assertRaises(patches.UnsupportedFirmware): self.apply()
        self.assertFalse(self.entered)
        self.assertFalse(self.boot.calls)

    def test_106_ultradim_workflow_backs_up_and_verifies_exact_target(self):
        result=self.apply(profile='ultradim')
        self.assertEqual(result['firmware_version'],'1.06')
        self.assertEqual(self.saved['before.bin'],self.current)
        self.assertEqual(self.saved['target-ultradim.bin'],self.images['ultradim'])
        self.assertEqual(bytes(self.boot.image),self.images['ultradim'])
        self.assertEqual(self.normal_full_reads,2)
        app.device.wait_normal.assert_called_once_with(target=self.images['ultradim'],expected_version='1.06')

    def test_protected_memory_changed_in_recovery_never_erases(self):
        self.boot.image[0x75000]^=1
        with self.assertRaisesRegex(RuntimeError,'Memory changed'): self.apply()
        self.assertFalse(self.boot.calls)
        self.assertTrue(self.boot.reset_called)

    def test_109_workflow_uses_109_target_and_normal_verification(self):
        from test_v109 import fixtures109
        self.images,fingerprints=fixtures109()
        self.current=self.images['dim']
        self.boot.image=bytearray(self.current)
        self.version='1.09'
        with patch.dict(patches.FINGERPRINTS_109,fingerprints,clear=True):
            result=self.apply()
        self.assertEqual(result['firmware_version'],'1.09')
        self.assertEqual(self.saved['target-dim.bin'],self.images['dim'])
        app.device.wait_normal.assert_called_once_with(target=self.images['dim'],expected_version='1.09')

    def test_backup_disk_failure_prevents_erase(self):
        self.backup_failure=True
        with self.assertRaises(OSError): self.apply()
        self.assertFalse(self.boot.calls)
        self.assertFalse(self.entered)
        self.assertFalse(self.boot.reset_called)

    def test_double_read_mismatch_prevents_erase(self):
        self.mismatch=True
        with self.assertRaisesRegex(RuntimeError,'two memory reads differ'): self.apply()
        self.assertIn('before.bin',self.saved)
        self.assertFalse(self.boot.calls)
        self.assertFalse(self.entered)
        self.assertFalse(self.boot.reset_called)

    def test_cancel_after_preparation_never_erases(self):
        with patch('builtins.input',return_value=''):
            self.apply(yes=False)
        self.assertIn('target-dim.bin',self.saved)
        self.assertFalse(self.boot.calls)
        self.assertTrue(self.boot.reset_called)

    def test_gui_confirmation_receives_verified_plan_before_any_write(self):
        def confirm(plan):
            self.assertEqual(plan['source_profile'], 'timed')
            self.assertEqual(plan['target_profile'], 'dim')
            self.assertEqual(plan['sectors'], ['0x18000'])
            self.assertIn('before.bin', self.saved)
            self.assertIn('target-dim.bin', self.saved)
            self.assertFalse(self.boot.calls)
            return True
        with contextlib.redirect_stdout(io.StringIO()):
            result=app.apply('dim',Path('unused'),confirm=confirm)
        self.assertEqual(result['outcome'],'completed')
        self.assertEqual(bytes(self.boot.image),self.images['dim'])

    def test_gui_decline_overrides_yes_and_never_erases(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result=app.apply('dim',Path('unused'),True,confirm=lambda plan:False)
        self.assertEqual(result['outcome'],'cancelled')
        self.assertFalse(self.boot.calls)
        self.assertTrue(self.boot.reset_called)

if __name__=='__main__': unittest.main()
