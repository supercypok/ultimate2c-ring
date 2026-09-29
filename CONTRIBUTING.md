# Contributing

Please start with a read-only compatibility report. Include:

- Exact controller model and whether it has a wireless receiver.
- Windows and Python versions.
- Firmware version and application fingerprint reported by the tool, if available.
- Whether the issue occurred over a cable, the receiver, or both.
- The error text and whether the controller is currently in normal or recovery mode.

Do not upload `.bin` or `.dat` files, complete backup folders, device serials, or HID device paths to public issues. Reports do not require a flash dump. You may quote log event names and errors after checking that they contain no private information.

## Changes to patching or USB access

1. Run `python -m unittest discover -s tests -v`.
2. Add tests for a concrete new failure case or compatibility rule.
3. Keep image transformations offline and separate from USB access.
4. Preserve the mandatory full backup, exact application fingerprint, protected-sector allowlist and full readback.
5. Document actual hardware tests and untested limitations separately.

Adding a version number to the allowlist is insufficient. New builds require investigation of pin assignments, call sites, checksum handling, boot protocol and helper space. Do not add a force-flash option or bundle a private/vendor firmware image to bypass these checks.

## Release checklist

- Ship the allowlisted source archive and the Windows package built by `scripts/build_windows.py`.
- Exclude `.venv`, Python caches, local backups, logs and firmware images.
- Run offline tests and confirm the documented compatibility hashes.
- State whether the exact released tool has undergone hardware write testing.
- Keep releases labeled experimental until broader hardware validation exists.
- Confirm the packaged desktop app opens, recognizes HID, handles pre-write cancellation and preserves verified backups.
- Include third-party license texts in the Windows package and publish its SHA-256 checksum.
