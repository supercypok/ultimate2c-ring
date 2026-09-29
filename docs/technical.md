# Technical notes

## Accepted images

The supported builds report firmware 1.06 or 1.09 and firmware product ID `301B`. Their application starts at flash `0x6000`, and the guard fingerprints bytes `0x6000:0x20000`. Bootloader and later configuration bytes are excluded from the public compatibility hash, and are preserved from the current device. Different data in those excluded regions does not require a different user's dump.

| State | Application SHA-256 |
| --- | --- |
| Stock | `c46f985385bb53bf45627241976562fb4e7ed05f35a73baf343d28b68c1094f7` |
| Off | `42ca333ce003aa056303b9d600bb844b7eec75838a1a97618ba7ed0dfe137b0e` |
| Timed | `bd48e6bcaf402f249102aeecbd0f3268a04d677e5df6785f53531360a7f899af` |
| Dim 1% | `436416dfef851f5b3954545416286e853daa8c18e782221d97ce16e22f87df96` |
| Dim 0.1% | `2d6d5efbd8c2c7e8e683277beece2ecb311d27e1f12d58909b55d74322256f22` |

I obtained these hashes from the exact factory application and the installed ring profiles after full readback. There are no filename, version-only or prefix-only compatibility fallbacks. Modified padding also causes rejection. The tool accepts another unit with the exact same application, but I have not tested a second controller.

### Firmware 1.09

| State | Application SHA-256 | Physical validation |
| --- | --- | --- |
| Stock | `ec248491efd44b6fd98867aee171159f5d73e718312518baa19ddfdb0194481a` | I checked controls and vibration over cable/receiver |
| Dim 1% | `d70fd8644dd1f4e04ed959cc1556deab89d9a2d9a2786396300be691c5071b30` | I checked illumination and controller operation |
| Dim 0.1% | `08e9f61008c13e14c35b56b5b5d2309c9e2e9248b209ba968d0cd1ef599316b2` | I checked illumination and controller operation |
| Off | `6e8bc20c7eb172f8a9d23133a710c9afb5caed5ca4fac47b2e0fc095518885db` | I ran offline checks only |
| Timed | `e824d07b45411c74a5f51ee616b831636190de6da4a6464f781908a1dd027272` | I ran offline checks only |
| Earlier private 0.01% trial | `86f6bf565ea15d96880f3df3e26872fac0cccb556e41a17013f2ae89ef0d9d5a` | Too faint; recognized as a source, not selectable |

I installed Stock 1.09, tested recovery entry/exit, restored the exact prior 1.06 image, then reinstalled Stock 1.09 before testing Dim and Dim 0.1%. I performed all these checks on the same controller using a private development procedure. I do not distribute those images; the public app has no version migration operation.

## Memory changes

All offsets below are absolute flash addresses unless specified otherwise.

- Startup Home-ring level: byte `0xA4A2`, originally 1, patched to 0.
- Off profile: branch byte `0xD48A`, originally `0x19`, patched to `0x0D`, skipping the channel-4 state setter.
- Timed/dim: the PB7-only driver call at `0xD598` changes from the original driver to a helper at `0x18400`.
- Original application checksum trailer: `0x18310:0x18314`. The original CRC residue is preserved using the XOR delta between original and modified application CRC32 values.
- Helper area: original erased padding at `0x18400:0x18478`. Timed helper is 40 bytes; dim helper including literals is 120 bytes.
- Allowed erase/write sectors: **only `0xA000`, `0xD000`, `0x18000`**, each 4096 bytes. Unchanged sectors are skipped. Timed to dim changes only sector `0x18000`.

Helpers are outside the original application's declared checksum region. I confirmed their execution on my controller, and their bytes are covered by the tool's full-flash readback and application fingerprint. The original application-size header is retained. No bootloader, receiver firmware or configuration sector is written.

Stock restoration reverses only known patches, recomputes the checksum by CRC delta, then verifies the exact stock application hash. Every target retains the current device's own bytes in all protected sectors. The CLI does not accept an external firmware file for flashing, so another user's bootloader or settings cannot be supplied to it.

For 1.09, the corresponding startup address is `0xA3FA`, branch is `0xD3E2`, driver hook is `0xD4F0` (application PC `0x74F0`), and checksum is `0x18270`. The original hook bytes are `FF 97 3C 9F`. Timed uses original driver PC `0x736C` and RAM counter `0x843452`. Helper space and the three sector allowlist entries are unchanged. On both supported versions, Dim 0.1% changes only the PWM1 compare literal from 10 to 1 at period 1000; it retains the shared clock and other channels.

## Ring and PWM

LED state channel 4 controls PB7, GPIO output `0x80050B` bit7. The existing LED scheduler runs about every 200 ms. Channel 13/PF1 and channel 1/PD5 use their original driver calls; I identified the other visible LEDs as mapping and power indicators.

The timed helper only illuminates connected state 1. It uses the original per-ring counter at RAM `0x843459`, saturating at 25 intervals. The original state-change setter resets the counter on a new connection. Repeated same-state events do not restart it.

The dim helper uses Telink B80 PWM1:

| Register | Operation |
| --- | --- |
| `0x800798` | PWM1 TCMP=10 (1%) or 1 (0.1%) / TMAX=1000 |
| `0x800780` bit1 | PWM1 enabled in connected state 1, disabled otherwise |
| `0x800784` / `0x800786` bit1 | PWM1 inversion/polarity cleared |
| `0x8007B0` bit3 | PWM1 frame interrupt masked |
| `0x800557` | PB7 mux selector 4 (PWM1) |
| `0x80050E` bit7 | Cleared for peripheral output; set for GPIO when disconnected |
| `0x80050B` bit7 | GPIO output latch kept low |

The factory vibration code uses PWM4/PD2 and PWM5/PD3. A separate calibration routine uses PWM0. The dim helper does not change the shared PWM clock divider or the motor channels. Register writes preserve unrelated bits. The helper is a leaf and leaves callee-saved registers and the stack untouched.

I derived this mapping from the live factory image and cross-checked it against [Telink's B80 GPIO/PWM/register headers](https://github.com/telink-semi/tc_platform_sdk/tree/master/chip/B80/drivers). The [Telink PWM handbook](https://doc.telink-semi.cn/doc/en/software/res/sdk/driver/platform_sdk_handbook_en/#duty-cycle) defines TCMP as high duration and TMAX as the full period. Actual brightness, flicker, power consumption and different hardware revisions require device testing; they are not inferred from the duty setting.

## HID protocol

- Normal device: VID `2DC8`, PID `310A`, usage page `FF7A`, interface 2. The identity reply must report the complete 32-bit version value 106 or 109 and firmware PID `301B`. The exact application fingerprint must agree with that version.
- Normal identity packet: `81 05 00 21 01`, padded to 64 bytes.
- Software boot entry: `81 05 00 51 00`, padded to 64 bytes; used only after application fingerprint validation and a complete twice-read, disk-verified normal-mode backup. Recovery memory must match that complete backup before writing.
- Bootloader: VID `2DC8`, PID `3208`, usage page `008C`, interface 0, product name `8BitDo Boot`.
- Bootloader reports have no report ID; HIDAPI needs a leading zero, giving a 65-byte write buffer for a 64-byte payload.
- Commands used: 5 read, 4 erase, 3 write, 7 return to application. Writes are 32-byte aligned chunks with CRC16/Modbus; erased `FF` chunks are skipped.
- Read chunks are at most 46 bytes. Lengths 4, 6 and 12 are avoided because the firmware contains additional special dispatch paths for them.
- Erase and every written sector are read back. The entire 512 KiB target is verified before normal reset.
- After reset, both normal identity and the exact application bytes are read and verified. A failure at this stage is reported with the retained backup; arbitrary damaged applications cannot be rescued by this tool.

Backups are saved and verified on disk before any erase. A write failure, interrupted operation or full-readback mismatch triggers rollback of all touched sectors, including a partially erased/written one. A failed rollback retains recovery mode. If disk logging fails during recovery, the tool still attempts the flash rollback.
