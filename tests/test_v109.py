"""Synthetic 1.09 memory and version guards; contains no vendor firmware."""
import struct
import unittest
from unittest.mock import patch
from ultimate2c_ring import patches
from ultimate2c_ring.device import Normal


def fixtures109():
    stock = bytearray(patches.FLASH_SIZE)
    stock[0xA3FA] = 1
    stock[0xD3E2] = 0x19
    stock[0xD4F0:0xD4F4] = bytes.fromhex('ff973c9f')
    stock[0x18400:0x18478] = b'\xff'*120
    struct.pack_into('<I',stock,0x18270,0x87654321)
    result = {'original': bytes(stock)}
    import zlib
    for profile in ('off','timed','dim','ultradim','microdim'):
        image = bytearray(stock)
        image[0xA3FA] = 0
        if profile == 'off':
            image[0xD3E2] = 13
        else:
            image[0xD4F0:0xD4F4] = bytes.fromhex('0a90869f')
            helper = bytearray(patches.TIMED_HELPER if profile=='timed' else patches.DIM_HELPER)
            if profile == 'timed':
                helper[26:30] = patches.branch_link(0x1241A,0x736C)
                struct.pack_into('<I',helper,36,0x843452)
            elif profile in ('ultradim','microdim'):
                at = helper.index(bytes.fromhex('0a00e803'))
                helper[at:at+4] = bytes.fromhex('0100e803' if profile=='ultradim' else '01001027')
            image[0x18400:0x18400+len(helper)] = helper
        checksum = 0x87654321 ^ zlib.crc32(stock[0x6000:0x18270]) ^ zlib.crc32(image[0x6000:0x18270])
        struct.pack_into('<I',image,0x18270,checksum)
        result[profile] = bytes(image)
    return result, {key:patches.sha256(image[0x6000:0x20000]) for key,image in result.items()}


class Firmware109Safety(unittest.TestCase):
    def setUp(self):
        self.images, fingerprints = fixtures109()
        guard = patch.dict(patches.FINGERPRINTS_109,fingerprints,clear=True)
        guard.start()
        self.addCleanup(guard.stop)

    def test_all_transitions_preserve_other_sectors_and_version(self):
        for image in self.images.values():
            current = bytearray(image)
            current[:0x6000] = bytes(range(256))*96
            current[0x20000:] = bytes(reversed(range(256)))*1536
            for profile in patches.available_profiles('1.09'):
                target = patches.make_target(current,profile)
                self.assertEqual(target[0x6000:0x20000],self.images[profile][0x6000:0x20000])
                self.assertEqual(target[:0x6000],current[:0x6000])
                self.assertEqual(target[0x20000:],current[0x20000:])
                self.assertEqual(patches.image_build(target),('1.09',profile))
                self.assertLessEqual(set(patches.changed_sectors(current,target)),set(patches.SECTORS))

    def test_corrupt_image_rejected_and_trial_microdim_not_selectable(self):
        bad = bytearray(self.images['original'])
        bad[0x7800] ^= 1
        with self.assertRaises(patches.UnsupportedFirmware): patches.make_target(bad,'ultradim')
        self.assertEqual(patches.image_build(self.images['microdim']),('1.09','microdim'))
        with self.assertRaises(ValueError): patches.make_target(self.images['dim'],'microdim')

    def test_ultradim_changes_only_one_literal_byte_from_dim(self):
        dim, ultra = self.images['dim'], self.images['ultradim']
        at = 0x18400+patches.DIM_HELPER.index(bytes.fromhex('0a00e803'))
        self.assertEqual([i for i,(a,b) in enumerate(zip(dim,ultra)) if a!=b],[at])
        self.assertEqual(patches.changed_sectors(dim,ultra),[0x18000])

    def test_whole_identity_version_checked_and_receiver_refused(self):
        normal = Normal.__new__(Normal)
        normal.send = lambda _:None
        for version,pid in ((106,0x301B),(109,0x301B),(0x100006A,0x301B),(0x100006D,0x301B),(109,0x301C),(110,0x301B)):
            reply = bytearray(64)
            reply[:2] = bytes.fromhex('0222')
            struct.pack_into('<IH',reply,2,version,pid)
            normal.reply = lambda:bytes(reply)
            if version in (106,109) and pid==0x301B:
                self.assertEqual(normal.identify()['firmware_version'], '1.06' if version==106 else '1.09')
            else:
                with self.assertRaises(RuntimeError): normal.identify()
