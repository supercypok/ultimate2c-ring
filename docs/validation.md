# My validation record — updated 2026-09-29

## Desktop 0.4.2 pre-release

- I removed the title tagline and launched the packaged GUI with all controls visible at 150% scaling.
- This appearance update does not change the controller engine. The 0.4.1 firmware validation below still applies.
- The release includes the accumulated 0.4.1 firmware support and matching icon from 0.4.0. I tested the intermediate versions below locally and did not publish them separately.

## Desktop 0.4.1 candidate

- I ran all 34 offline tests successfully, including every transition among the five synthetic 1.06 profiles, the single-byte PWM change and the complete 1.06 Dim 0.1% backup/write/verification workflow.
- On my controller, I used the private fixed-unit procedure to install factory 1.06 with Dim 0.1% directly from the previously verified 1.09 Dim 0.1% state. A complete twice-read backup preceded recovery entry, protected regions were preserved, all 512 KiB matched the prepared target after writing, and normal firmware identity and application bytes passed verification.
- I observed weak illumination and working controls on 1.06. I did not measure optical brightness.
- The public 1.06 Dim 0.1% transformation reproduces that installed private target exactly. No additional flash write is needed for the application update.
- I checked that the packaged 0.4.1 CLI recognized my controller's normal firmware 1.06 and Dim 0.1% application. I launched the packaged light GUI with all controls visible at 150% scaling.
- I prepared this intermediate version locally and did not publish it separately. I have not tested a second controller.

## Desktop 0.4.0 candidate (historical)

- I ran all 33 offline tests successfully.
- I launched the packaged Windows app with the retained 0.3.1 light layout and its new ring/gamepad icon. I checked that all controls and the footer were visible at 150% scaling.
- The icon uses the interface's light background, teal accent and dark text color. It is included in the graphical and command-line executables and the Tk windows.
- The controller engine is unchanged. No new firmware write was performed for this appearance update.
- I prepared this intermediate version locally and did not publish it separately.

## Desktop 0.3.1 candidate

- I ran all 33 remaining offline tests successfully after removing the Windows popup tools.
- The graphical app has a single controller screen. The CLI exposes only controller and device-free validation commands.
- I launched the packaged 0.3.1 GUI on Windows 11 at 150% scaling and checked that all controls and the footer were visible. I checked that the packaged CLI help contains no Game Bar command.
- Firmware transforms and the controller engine are unchanged from 0.3.0. The hardware observations below apply to that engine; no new flash write was performed for this UI change.
- I prepared this intermediate version locally and did not publish it separately.

## Desktop 0.3.0 candidate (historical)

- I ran all 38 offline tests successfully. Added cases cover all synthetic 1.09 transitions, recognition of the earlier private 0.01% state, unknown builds, the whole identity version, application/identity disagreement, unavailable 1.06 brightness, complete backup before recovery and changed protected memory in recovery.
- Game Bar tests cover backup before the command write, repeated apply, owned undo with backup retention, refusal of existing/package/delegated/user-choice handlers, backup or script-engine failure, handler changes during preparation, and refusal of corrupt backups or another program's command during undo. They do not write the real registry or launch a process.
- I checked all 30 transitions from the six known 1.09 source states to the five selectable profiles against the fixed private images byte for byte. The original 1.06 application fingerprints and full Dim image remain unchanged. This comparison reads saved private images locally; none are shipped.
- I tested Stock 1.09, recovery entry/exit, exact return to 1.06, Dim 1% and Dim 0.1% on my controller with the private fixed-image procedure. I ran only offline checks for Timed and Off on 1.09.
- I resolved my popup with the earlier standalone Game Bar workaround. The integrated module uses the same silent handler and state format; its apply/undo logic has the tests above. The packaged GUI successfully recognized the existing fix and enabled Undo while leaving Fix disabled. I did not exercise its integrated registry apply/undo on my real registry.
- I launched the packaged GUI and checked both tabs with all controls visible at 150% scaling. It recognized normal firmware 1.09 and the current Dim 0.1% fingerprint.
- I prepared Dim 1%; the app saved a complete backup twice in normal mode, compared full recovery memory, reconstructed stock and the known Dim target, and showed the review window for one sector. I pressed Escape to cancel before any erase/write and return the controller to normal mode. The saved before/stock/target images matched the known private images byte for byte; the journal has no write-start event. A subsequent normal-mode check confirmed the retained Dim 0.1% application.
- A full flash write using the packaged 0.3.0 tool remains untested. Its targets match the independently installed private trial images, and its write/rollback code has offline failure tests. A final UI adjustment keeps Windows-tab status separate from controller progress; the controller engine is unchanged by that adjustment.

I prepared this experimental candidate locally and did not publish it separately. I have not tested a second controller.

## My controller

I fully backed up and verified the original factory 1.06 image. I installed each of these profiles with the original development tool and verified all 512 KiB by readback:

- Off: I checked that the Home ring went dark and controls worked.
- Timed: I checked that illumination ended after approximately 5 seconds and controls worked.
- Dim: I confirmed working illumination, controls, vibration and shutdown.

I verified software entry to the bootloader, return to normal USB, and physical recovery entry with L1 + R1. I backed up the receiver without modifying it. I did not test recovery from a deliberately damaged application.

## Published 0.1.0 tool

I used the source downloaded from the public repository on the same controller, with Windows 11 and Python 3.12:

- I ran a read-only backup that read all 512 KiB twice and verified the saved file on disk. The current dim image matched the previously verified complete image byte for byte.
- I reconstructed the stock target from that backup and checked that it reproduced my original complete factory backup byte for byte.
- I restored Stock and verified all 512 KiB against the prepared target, then checked the controller's normal USB model and firmware identity after reset.

I made these observations on one controller. I have not established compatibility with a second unit or another factory build.

## Desktop 0.2.0

- The packaged Windows x64 GUI launches directly without using the user's Python installation. Its bundled HID library checks the real controller and recognizes the supported stock application.
- I checked that all controls, including report saving and instructions, were visible in the Windows 11 layout at 150% display scaling.
- I prepared Stock-to-Dim and checked two complete backup reads, the saved target, and the review window before writing. I pressed Escape and checked that cancellation kept the backup and returned to normal mode without erasing or writing memory.
- I prepared the profile again and selected Apply profile to install Dim through the packaged GUI. All three changed application sectors verified, the complete 512 KiB readback matched the prepared target, and normal USB identity passed after reset. I did not record a separate physical controls, vibration and receiver check for this particular packaged installation.
- Public tests use synthetic memory. All 25 tests pass, including the desktop operation lock, the pre-write review handshake, cancellation without erase, observer failures, and the compatibility report's privacy whitelist.
- The Windows package includes separate graphical and command-line entry points, bundled dependency license texts, and a SHA-256 checksum. It is unsigned.
- The packaged `doctor` command checks HID and Tcl/Tk without opening a controller. Its local terminal check is blocked by this development environment's Tcl initialization restriction; native GUI launch works. The independent GitHub Windows runner passed all tests, built the package, and passed its bundled dependency check: [successful run](https://github.com/supercypok/ultimate2c-ring-history/actions/runs/36405877811).
- In the original repository, I checked all 34 source files downloaded from public commit `4ca6dd5f2a452fe9e73685057b6d85508bc55506` against the locally validated source byte for byte before updating this validation record.

## Reusable source project

- I checked all 16 transitions between Stock, Off, Timed and Dim against the previously installed or backed-up images byte for byte.
- I checked that a second set of simulated per-device bootloader and settings bytes remained unchanged when building targets.
- I use synthetic memory in public tests, never my firmware dump.
- The safety tests cover all profile transitions, unknown/corrupt image rejection, protected-sector write guards, protocol CRC and packet layout, avoiding special read lengths, receiver identity rejection, rollback after a partial write and after a full verification mismatch, failed rollback retaining boot mode, successful verification before reset, and disk-log failure not preventing rollback. Workflow tests also verify that backup and target preparation precede every write, disk failure or mismatched backup reads prevent erasing, unknown firmware never triggers software boot entry, and cancellation after preparation leaves memory untouched.
- I checked the offline CLI preview and successfully parsed all Python sources and both Windows PowerShell launchers.
- I checked the 120-byte Dim helper by executing its actual encoded instructions for 2048 state-transition calls with randomized peripheral register values. This checks encoding and preservation; it does not measure optical behavior.

I have not tested a second controller. The supported scope is the exact application fingerprints documented in [technical.md](technical.md).
