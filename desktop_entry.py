"""PyInstaller entry. The default opens the UI; CLI commands remain available."""
import sys
from ultimate2c_ring.__main__ import main

if __name__=='__main__':
    # A console build can still report errors and support documented CLI commands.
    raise SystemExit(main(sys.argv[1:] or ['gui']))
