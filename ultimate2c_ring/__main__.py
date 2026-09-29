import argparse
import json
from pathlib import Path
import sys
from . import __version__
from . import app
from .patches import make_target,recognize,changed_sectors,sha256

def menu(data_dir):
    print(f'Ultimate 2C Ring {__version__}\n')
    print('Ultimate 2C Wireless only; connect the controller by USB data cable.')
    print('Support requires exact supported 1.06/1.09 builds, checked automatically.')
    choices = {'3':'dim','4':'timed','5':'off','6':'original','7':'ultradim'}
    while True:
        print('\n1. Check controller\n2. Make a read-only backup\n3. Dim 1%\n4. Ring on for 5 seconds\n5. Ring always off\n6. Restore stock ring behavior\n7. Dim 0.1%\n0. Exit')
        choice = input('Choose: ').strip()
        if choice=='0': return
        try:
            if choice=='1': app.status()
            elif choice=='2': app.backup(data_dir)
            elif choice in choices: app.apply(choices[choice],data_dir)
            else: print('Choose one of the listed options.')
        except (RuntimeError,ValueError,OSError) as error:
            print(f'\nError: {error}\nSee README.md for recovery steps.')

def main(argv=None):
    parser = argparse.ArgumentParser(description='Ultimate 2C Wireless Home-ring firmware profiles. Windows 11 / Python 3.12 tested.')
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--data-dir',type=Path,default=app.default_data_dir(),help='Private local backup directory; keep it out of public repositories.')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('menu',help='Open the English menu.')
    sub.add_parser('gui',help='Open the English desktop application.')
    sub.add_parser('doctor',help='Verify packaged HID and Tcl/Tk libraries without opening a controller.')
    sub.add_parser('status',help='Read identity and exact application fingerprint.')
    sub.add_parser('backup',help='Read all 512 KiB twice; do not change device mode or flash.')
    apply = sub.add_parser('apply',help='Back up, prepare, review, then install a profile.')
    apply.add_argument('profile',choices=['ultradim','dim','timed','off'])
    apply.add_argument('--yes',action='store_true',help='Skip the final typed confirmation after backup and validation.')
    restore = sub.add_parser('restore',help='Restore stock application using only the current device data.')
    restore.add_argument('--yes',action='store_true')
    preview = sub.add_parser('preview',help='Offline validation and patch plan; never connects to a device.')
    preview.add_argument('profile',choices=list(app.PROFILES))
    preview.add_argument('--backup',required=True,type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command=='doctor':
            import tkinter as tk
            from .device import hid_module
            hid_module()
            root=tk.Tk()
            root.withdraw()
            try:
                print(json.dumps({'version': __version__, 'hid_loaded': True,
                                  'tk_version': root.tk.call('info','patchlevel'),
                                  'device_accessed': False}))
            finally:
                root.destroy()
        elif args.command=='gui':
            from .gui import launch
            launch(args.data_dir)
        elif args.command=='menu': menu(args.data_dir)
        elif args.command=='status': app.status()
        elif args.command=='backup': app.backup(args.data_dir)
        elif args.command in ('apply','restore'):
            app.apply('original' if args.command=='restore' else args.profile,args.data_dir,args.yes)
        else:
            current=args.backup.read_bytes()
            target=make_target(current,args.profile)
            print(json.dumps({'current_profile':recognize(current),'target_profile':args.profile,
                'application_sectors':[hex(a) for a in changed_sectors(current,target)],
                'current_sha256':sha256(current),'target_sha256':sha256(target),
                'device_accessed':False},indent=2))
        return 0
    except (RuntimeError,ValueError,OSError) as error:
        print(f'Error: {error}',file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted. Check the saved operation log before retrying.',file=sys.stderr)
        return 130

if __name__=='__main__': sys.exit(main())
