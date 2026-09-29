# Changelog

## 0.4.2 — 2026-09-28 (pre-release)

- I removed the tagline below the application title and adjusted header spacing.

## 0.4.1 — 2026-09-28 (local candidate)

- Dim 0.1% is now recognized and selectable on the exact supported factory 1.06 build as well as 1.09.
- I tested Dim 0.1% on factory 1.06 with a complete backup, full memory readback and normal-mode application verification. The light was weak and controls worked.
- I added the verified 1.06 application fingerprint; all targets still preserve the installed firmware version and protected data.
- I expanded synthetic 1.06 transition and workflow coverage. All 34 offline tests passed.
- I retained the light design and matching ring/gamepad icon.

## 0.4.0 — 2026-09-28 (local candidate)

- Original ring and gamepad icon embedded in both Windows executables and application windows.
- Light background, teal ring and dark controller match the existing desktop palette.
- I retained the 0.3.1 desktop layout and controls.
- Controller firmware engine and backup safeguards are unchanged.

## 0.3.1 — 2026-09-28 (local candidate)

- I removed the Windows popup tab and Game Bar commands from the application.
- I simplified the desktop to a single screen for controller ring profiles.
- I removed the associated module, tests, screenshot and current usage instructions.
- Firmware transforms and controller backup/write safeguards are unchanged.

## 0.3.0 — 2026-09-28 (local candidate)

- Exact supported 1.09 fingerprints and version-specific ring transforms; no version upgrades or downgrades.
- Dim 0.1% on 1.09, alongside Dim 1%, Timed, Off and Stock.
- Recognition of the earlier private 0.01% trial so it can return to a selectable profile.
- Full double backup before normal-mode recovery entry, full normal/recovery memory comparison and post-reset application verification.
- Full 32-bit identity checks and agreement between firmware identity and application fingerprint.
- Separate Controller ring and Windows popup tabs.
- Per-user Game Bar link inspection, optional silent handler with verified backup, and undo that refuses another program's handler.
- 38 offline tests and byte-for-byte private comparison of 30 firmware 1.09 transitions.
- Actual packaged GUI and hardware validation are recorded in [validation.md](docs/validation.md).

## 0.2.0 — 2026-09-28

- English desktop app with Dim, 5 seconds, Off and Stock profiles.
- Ready-to-run Windows x64 package with a separate command-line entry point.
- Responsive background operations and a review window after the complete backup has been verified.
- Local compatibility reports excluding memory dumps, serials, device paths and logs.
- Clear USB receiver-only and multiple-controller messages.
- GitHub Actions safety tests, Windows builds and a device-free packaged dependency check.
- Bundled dependency licenses and archive SHA-256 checksums.
- 25 offline tests. Real controller validation is recorded in [validation.md](docs/validation.md).

Firmware support remains limited to the exact previously verified factory 1.06 application build. This release does not add support for other Ultimate models or arbitrary corrupted firmware.

## 0.1.0 — 2026-09-28

- Initial reusable source release for the Ultimate 2C Wireless Home ring.
- Dim, timed and off transformations built from each controller's own memory.
- Complete double-read backups, application fingerprint checks, protected-sector guards and full verification.
- Stock reconstruction and rollback of touched sectors after a failed write or verification.
- 18 offline tests and English installation and recovery instructions.
