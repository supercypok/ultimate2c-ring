"""Pure, offline image transformations. No vendor firmware is distributed."""
import hashlib
import struct
import zlib

FLASH_SIZE = 0x80000
APP_START, APP_END = 0x6000, 0x20000
CRC_AT = 0x18310
CAVE_START, CAVE_END = 0x18400, 0x18478
SECTORS = (0xA000, 0xD000, 0x18000)
FINGERPRINTS = {
    'original':'c46f985385bb53bf45627241976562fb4e7ed05f35a73baf343d28b68c1094f7',
    'off':'42ca333ce003aa056303b9d600bb844b7eec75838a1a97618ba7ed0dfe137b0e',
    'timed':'bd48e6bcaf402f249102aeecbd0f3268a04d677e5df6785f53531360a7f899af',
    'dim':'436416dfef851f5b3954545416286e853daa8c18e782221d97ce16e22f87df96',
    'ultradim':'2d6d5efbd8c2c7e8e683277beece2ecb311d27e1f12d58909b55d74322256f22',
}
FINGERPRINTS_109 = {
    'original': 'ec248491efd44b6fd98867aee171159f5d73e718312518baa19ddfdb0194481a',
    'off': '6e8bc20c7eb172f8a9d23133a710c9afb5caed5ca4fac47b2e0fc095518885db',
    'timed': 'e824d07b45411c74a5f51ee616b831636190de6da4a6464f781908a1dd027272',
    'dim': 'd70fd8644dd1f4e04ed959cc1556deab89d9a2d9a2786396300be691c5071b30',
    'ultradim': '08e9f61008c13e14c35b56b5b5d2309c9e2e9248b209ba968d0cd1ef599316b2',
    # Recognize the earlier private trial so it can return to a selectable profile.
    'microdim': '86f6bf565ea15d96880f3df3e26872fac0cccb556e41a17013f2ae89ef0d9d5a',
}
BUILD_LAYOUTS = {
    '1.06': {'startup': 0xA4A2, 'branch': 0xD48A, 'call': 0xD598,
             'call_pc': 0x7598, 'crc': 0x18310, 'driver': 0x7414, 'counter': 0x843459},
    '1.09': {'startup': 0xA3FA, 'branch': 0xD3E2, 'call': 0xD4F0,
             'call_pc': 0x74F0, 'crc': 0x18270, 'driver': 0x736C, 'counter': 0x843452},
}

def fingerprints(version):
    return FINGERPRINTS if version == '1.06' else FINGERPRINTS_109

def available_profiles(version):
    return ('ultradim', 'dim', 'timed', 'off', 'original')
# Newly written TC32 helper code. These bytes contain no device identity data.
# Timed: saturating 25 x ~200 ms counter, then call the original PB7 driver.
TIMED_HELPER = bytes.fromhex(
    '006501a808c1070b184819a804c201b0184001a00180c04600a0'
    'f497fb9f006dc046c04659348400')
# Dim: leaf handler; PWM1 period1000, high10, PB7 mux4; restore GPIO-low
# on non-connected states. Other PWM/GPIO bits and shared clock are retained.
DIM_HELPER = bytes.fromhex(
    '01a81fc1160b170a1a50170b02a11a498a031a419a498a039a411a480a031a40'
    '120b08a11a488a031a40110b80a1da488a03da400f0b04a21a400d0b9a498a03'
    '9a417007080b02a11a488a031a40080b80a1da488a03da409a490a039a417007'
    '980780000a00e80380078000b00780000805800057058000')

class UnsupportedFirmware(ValueError):
    pass

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def recognize_build(app):
    if len(app) != APP_END-APP_START:
        raise UnsupportedFirmware('Incomplete application read.')
    digest = sha256(app)
    for version in BUILD_LAYOUTS:
        for profile, known in fingerprints(version).items():
            if digest == known:
                return version, profile
    raise UnsupportedFirmware(
        f'Unsupported firmware build (application SHA-256 {digest}). '
        'Only exact supported 1.06/1.09 builds are accepted. No firmware will be written.')

def recognize_application(app):
    return recognize_build(app)[1]

def image_build(image):
    if len(image) != FLASH_SIZE:
        raise UnsupportedFirmware('Expected a complete 512 KiB controller backup.')
    return recognize_build(image[APP_START:APP_END])

def recognize(image):
    return image_build(image)[1]

def update_crc(before, after, crc_at=CRC_AT):
    stored = struct.unpack_from('<I',before,crc_at)[0]
    delta = zlib.crc32(before[APP_START:crc_at]) ^ zlib.crc32(after[APP_START:crc_at])
    struct.pack_into('<I',after,crc_at,stored ^ delta)
    if zlib.crc32(before[APP_START:crc_at+4]) != zlib.crc32(after[APP_START:crc_at+4]):
        raise ValueError('CRC residue preservation failed.')

def branch_link(at, target):
    delta = target-at-4
    if delta % 2 or not -(1 << 22) <= delta < (1 << 22):
        raise ValueError('Invalid TC32 branch.')
    encoded = (delta//2) & ((1<<22)-1)
    return struct.pack('<HH',0x9000 | encoded>>11,0x9800 | encoded & 0x7FF)

def original_image(image):
    version, _ = image_build(image)
    layout = BUILD_LAYOUTS[version]
    original = bytearray(image)
    original[layout['startup']] = 1
    original[layout['branch']] = 0x19
    original[layout['call']:layout['call']+4] = bytes.fromhex('ff973c9f')
    original[CAVE_START:CAVE_END] = b'\xff'*(CAVE_END-CAVE_START)
    update_crc(image,original,layout['crc'])
    if image_build(original) != (version, 'original'):
        raise UnsupportedFirmware('Could not reconstruct the verified stock application.')
    return bytes(original)

def make_target(current, profile):
    version, _ = image_build(current)
    if profile not in available_profiles(version):
        raise ValueError(f'Profile {profile!r} is not available for firmware {version}.')
    layout = BUILD_LAYOUTS[version]
    original = original_image(current)
    target = bytearray(original)
    if profile != 'original':
        target[layout['startup']] = 0
    if profile == 'off':
        target[layout['branch']] = 0x0D
    elif profile in ('timed','dim','ultradim'):
        target[layout['call']:layout['call']+4] = branch_link(layout['call_pc'],0x12400)
        helper = bytearray(TIMED_HELPER if profile == 'timed' else DIM_HELPER)
        if profile == 'timed' and version == '1.09':
            helper[26:30] = branch_link(0x12400+26,layout['driver'])
            struct.pack_into('<I',helper,36,layout['counter'])
        elif profile == 'ultradim':
            literal = helper.index(struct.pack('<I',0x03E8000A))
            struct.pack_into('<I',helper,literal,0x03E80001)
        target[CAVE_START:CAVE_START+len(helper)] = helper
    update_crc(original,target,layout['crc'])
    if image_build(target) != (version, profile):
        raise ValueError('Generated application did not match the verified profile.')
    for sector in range(0,FLASH_SIZE,4096):
        if sector not in SECTORS and current[sector:sector+4096] != target[sector:sector+4096]:
            raise ValueError('Transformation modified a protected sector.')
    return bytes(target)

def changed_sectors(before, after):
    if len(before) != FLASH_SIZE or len(after) != FLASH_SIZE:
        raise ValueError('Incomplete image.')
    changed = [a for a in range(0,FLASH_SIZE,4096) if before[a:a+4096] != after[a:a+4096]]
    if any(a not in SECTORS for a in changed):
        raise ValueError('Write outside the allowed application sectors.')
    return changed
