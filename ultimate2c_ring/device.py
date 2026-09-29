"""Restricted HID protocol, for a USB-cable connected controller only."""
import struct
import time
from .patches import APP_START, APP_END, FLASH_SIZE, SECTORS

def hid_module():
    try:
        import hid
    except ImportError as error:
        raise RuntimeError('HIDAPI is missing. Run Setup.cmd first.') from error
    return hid

def discover():
    hid = hid_module()
    normal, boot = [], []
    devices = hid.enumerate(0x2DC8,0)
    for d in devices:
        if d['product_id']==0x310A and d['usage_page']==0xFF7A and d['interface_number']==2:
            normal.append(d)
        if d['product_id']==0x3208 and d['usage_page']==0x8C and d['interface_number']==0 and (d.get('product_string') or '').strip()=='8BitDo Boot':
            boot.append(d)
    if len(normal)+len(boot) > 1:
        raise RuntimeError('More than one controller is connected. Leave only the controller you want to change.')
    if not normal and not boot:
        if any(d['product_id']==0x301C for d in devices):
            raise RuntimeError('Only the USB receiver was found. Connect the controller itself with a USB data cable.')
        raise RuntimeError('Controller not found. Connect the Ultimate 2C Wireless itself with a USB data cable. Try another cable or USB port.')
    return ('normal',normal[0]) if normal else ('boot',boot[0])

class Link:
    def __init__(self, descriptor):
        self.h = hid_module().device()
        self.h.open_path(descriptor['path'])
        self.h.set_nonblocking(1)
        while self.h.read(64):
            pass
        self.h.set_nonblocking(0)

    def close(self):
        self.h.close()

    def send(self, packet):
        if self.h.write(packet) != len(packet):
            raise RuntimeError('Incomplete USB write.')

    def reply(self):
        value = bytes(self.h.read(64,timeout_ms=3000))
        if len(value) != 64:
            raise RuntimeError('Missing or incomplete USB reply.')
        return value

    def read_range(self, address, size, progress=None):
        if size <= 0 or address < 0 or address+size > FLASH_SIZE:
            raise ValueError('Read outside flash.')
        result = bytearray()
        last = -1
        while len(result) < size:
            count = min(46,size-len(result))
            # Firmware contains special dispatch paths for these short lengths.
            if count in (4,6,12): count -= 1
            result.extend(self.read(address+len(result),count))
            percent = len(result)*100//size
            if progress and percent//10 != last:
                last = percent//10
                progress(percent)
        return bytes(result)

class Normal(Link):
    def identify(self):
        self.send(bytes.fromhex('8105002101').ljust(64,b'\0'))
        reply = self.reply()
        version = struct.unpack_from('<I',reply,2)[0]
        if reply[:2]!=b'\x02\x22' or version not in (106,109) or reply[6:8]!=bytes.fromhex('1b30'):
            raise RuntimeError('Expected an Ultimate 2C Wireless controller with firmware 1.06 or 1.09.')
        return {'model':'Ultimate 2C Wireless','firmware_version':'1.06' if version==106 else '1.09','firmware_product_id':'301B'}

    def read(self, address, count):
        validate_read(address,count)
        packet = bytearray(64)
        packet[:4] = bytes.fromhex('81050500')
        struct.pack_into('<H',packet,6,count)
        struct.pack_into('<I',packet,14,address)
        self.send(packet)
        reply = self.reply()
        if reply[:2]!=b'\x02\x05' or reply[4:6]!=b'\x05\0':
            raise RuntimeError('Unexpected controller read response.')
        return read_data(reply,address,count)

    def enter_boot(self):
        self.send(bytes.fromhex('8105005100').ljust(64,b'\0'))

def validate_read(address,count):
    if address<0 or address+count>FLASH_SIZE or count not in range(1,47) or count in (4,6,12):
        raise ValueError('Invalid flash read.')

def read_data(reply,address,count):
    if struct.unpack_from('<H',reply,6)[0]!=count or struct.unpack_from('<I',reply,14)[0]!=address:
        raise RuntimeError('Read reply address/length mismatch.')
    return reply[18:18+count]

def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value>>1) ^ (0xA001 if value&1 else 0)
    return value

class Boot(Link):
    def request(self, command, address=0, count=0, data=b'', extent=0):
        # No arbitrary commands, erase addresses or external firmware files.
        if command not in (3,4,5,7): raise ValueError('Unsupported command.')
        if command==4 and (address not in SECTORS or extent!=4096):
            raise ValueError('Erase outside the application allowlist.')
        if command==3 and ((address&~0xFFF) not in SECTORS or address%32 or len(data)!=32 or count!=32):
            raise ValueError('Write outside the application allowlist.')
        if command==5: validate_read(address,count)
        packet = bytearray(65)
        packet[1] = 5  # leading zero is HIDAPI's report-ID placeholder
        struct.pack_into('<HHHHII',packet,2,command,0,count,crc16(data) if data else 0,extent,address)
        packet[18:18+len(data)] = data
        self.send(packet)
        if command==7: return b''
        reply = self.reply()
        if reply[:4]!=b'\x00\x05\x00\x00' or reply[4:6]!=command.to_bytes(2,'little'):
            raise RuntimeError('Bootloader rejected the command or returned an unexpected reply.')
        return reply

    def read(self,address,count):
        return read_data(self.request(5,address,count),address,count)

    def sector(self,address,data):
        if address not in SECTORS or len(data)!=4096:
            raise ValueError('Write outside the application allowlist.')
        self.request(4,address,extent=4096)
        if self.read_range(address,4096)!=b'\xff'*4096:
            raise RuntimeError(f'Erase verification failed at {address:#x}.')
        for offset in range(0,4096,32):
            part = data[offset:offset+32]
            if part != b'\xff'*32:
                self.request(3,address+offset,32,part)
        if self.read_range(address,4096)!=data:
            raise RuntimeError(f'Sector verification failed at {address:#x}.')

    def reset(self):
        self.request(7)

def wait_normal(timeout=8, *, target=None, expected_version=None):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            mode,descriptor = discover()
            if mode=='normal':
                link=Normal(descriptor)
                try:
                    identity = link.identify()
                    if expected_version and identity['firmware_version'] != expected_version:
                        raise RuntimeError('Normal USB firmware version differs from the verified image.')
                    if target is not None and link.read_range(APP_START,APP_END-APP_START) != target[APP_START:APP_END]:
                        raise RuntimeError('Normal-mode application differs from the verified image.')
                    return identity
                finally: link.close()
        except (RuntimeError,OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError('Flash readback passed, but normal USB identity/application was not confirmed. Keep the cable connected and retain the backup. See the recovery instructions.')
