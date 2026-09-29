# Bundled Windows application

Original Ultimate 2C Ring code is MIT licensed; see LICENSE.

The Windows application bundles Python, Tcl/Tk and these separately licensed libraries. Their licenses apply to their components, not vendor controller firmware.

- Python: Python Software Foundation license. See <https://docs.python.org/3/license.html>.
- Tcl/Tk: BSD-style Tcl/Tk licenses. See <https://www.tcl-lang.org/software/tcltk/license.html>.
- HIDAPI / Python hidapi: see the package's BSD license and the HIDAPI library's BSD/GPLv3/original HIDAPI license options at <https://github.com/trezor/cython-hidapi> and <https://github.com/libusb/hidapi>.
- PyInstaller: GPL with a bootloader exception permitting distribution of bundled applications. See <https://pyinstaller.org/en/stable/license.html>.

Dependency license files are included under `_internal/licenses`; Python and Tcl/Tk license text is also included with the Windows package. `BUILD-DEPENDENCIES.json` lists the build environment's package versions. Build tools listed there are not necessarily runtime dependencies.

No 8BitDo firmware, flash backup, pairing data or calibration data is included.
