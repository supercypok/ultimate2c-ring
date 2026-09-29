"""English desktop UI. USB access happens only on the operation worker."""
import json
import os
import platform
from pathlib import Path
from queue import Empty
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from . import __version__, app
from .controller import Operations

PROJECT_URL = 'https://github.com/supercypok/ultimate2c-ring'
PROFILE_DETAILS = {
    'ultradim': ('Dim 0.1%', 'Soft illumination on the supported 1.06 and 1.09 builds.'),
    'dim': ('Dim 1%', 'Constant illumination at 1% PWM duty.'),
    'timed': ('5 seconds', 'Lights up on connection, then goes dark.'),
    'off': ('Off', 'Keeps the Home ring dark while playing.'),
    'original': ('Stock', 'Restores the original ring behavior.'),
}

def set_window_icon(window):
    folder = Path(__file__).parent / 'assets'
    try:
        if sys.platform == 'win32':
            window.iconbitmap(str(folder / 'app.ico'))
        window._ring_icon = tk.PhotoImage(file=str(folder / 'app.png'))
        window.iconphoto(True, window._ring_icon)
    except tk.TclError:
        pass


def profile_title(profile):
    if profile == 'microdim':
        return 'Very dim 0.01% (previous trial)'
    return PROFILE_DETAILS.get(profile, ('Unknown', ''))[0]


def diagnostics(status=None, error_type=None):
    # Intentionally do not export the UI log, full-memory hashes, HID paths,
    # backup locations, exception messages, serials, hostname or pairing data.
    safe = {key: (status or {}).get(key) for key in (
        'model', 'firmware_version', 'mode', 'profile', 'compatible', 'application_sha256')}
    return {'app_version': __version__, 'operating_system': platform.system(),
            'os_release': platform.release(), 'python_version': platform.python_version(),
            'controller': safe, 'last_error_type': error_type,
            'privacy': 'No memory dumps, device paths, serials or local logs included.'}


class RingWindow:
    def __init__(self, root, data_dir):
        self.root = root
        self.data_dir = Path(data_dir)
        self.operations = Operations()
        self.checked = None
        self.last_error_type = None
        self.close_when_idle = False
        self.confirm_window = None
        self.profile = tk.StringVar(value='ultradim')
        self.connection = tk.StringVar(value='Ready to connect')
        self.detail = tk.StringVar(value='Connect the controller itself using a USB data cable.')
        self.stage = tk.StringVar(value='Check compatibility to get started.')
        self.percent = tk.DoubleVar(value=0)
        self.summary = tk.StringVar(value='No changes made.')
        root.title(f'Ultimate 2C Ring {__version__}')
        root.geometry('880x780')
        root.minsize(820, 740)
        root.configure(bg='#f3f6f8')
        set_window_icon(root)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self._build()
        self.root.after(80, self._poll)

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), foreground='#172d3b')
        style.configure('TFrame', background='#f3f6f8')
        style.configure('TLabel', background='#f3f6f8')
        style.configure('Card.TFrame', background='white')
        style.configure('Card.TLabel', background='white')
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 20))
        style.configure('Small.TLabel', foreground='#526674', font=('Segoe UI', 9))
        style.configure('Status.TLabel', background='white', font=('Segoe UI Semibold', 14))
        style.configure('TButton', padding=(12, 7))
        style.configure('Accent.TButton', background='#087e83', foreground='white')
        style.map('Accent.TButton', background=[('disabled', '#b8ced0'), ('active', '#05666b')])
        style.configure('TRadiobutton', background='white', padding=4)
        style.configure('Horizontal.TProgressbar', background='#087e83', troughcolor='#dfe8ec')
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Ultimate 2C Ring', style='Title.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(outer, text=f'Experimental {__version__}  ·  Ultimate 2C Wireless  ·  Exact 1.06 / 1.09 builds',
                  style='Small.TLabel').pack(anchor='w', pady=(0, 12))
        card = ttk.Frame(outer, style='Card.TFrame', padding=14)
        card.pack(fill='x')
        ttk.Label(card, textvariable=self.connection, style='Status.TLabel').pack(anchor='w')
        ttk.Label(card, textvariable=self.detail, style='Card.TLabel', wraplength=750).pack(anchor='w', pady=(5, 12))
        row = ttk.Frame(card, style='Card.TFrame')
        row.pack(fill='x')
        self.check_button = ttk.Button(row, text='Check controller', command=self.check)
        self.check_button.pack(side='left')
        self.backup_button = ttk.Button(row, text='Read-only backup', command=self.backup)
        self.backup_button.pack(side='left', padx=8)
        ttk.Button(row, text='Open backups', command=self.open_backups).pack(side='right')

        profiles = ttk.Frame(outer, style='Card.TFrame', padding=14)
        profiles.pack(fill='x', pady=12)
        ttk.Label(profiles, text='Choose ring behavior', style='Status.TLabel').pack(anchor='w', pady=(0, 10))
        self.profile_buttons = []
        self.profile_keys = []
        for key, (title, description) in PROFILE_DETAILS.items():
            line = ttk.Frame(profiles, style='Card.TFrame')
            line.pack(fill='x', pady=1)
            button = ttk.Radiobutton(line, text=title, variable=self.profile, value=key, width=13)
            button.pack(side='left')
            self.profile_buttons.append(button)
            self.profile_keys.append(key)
            ttk.Label(line, text=description, style='Card.TLabel').pack(side='left', padx=8)
        bottom = ttk.Frame(profiles, style='Card.TFrame')
        bottom.pack(fill='x', pady=(12, 0))
        self.apply_button = ttk.Button(bottom, text='Prepare selected profile', style='Accent.TButton',
                                       command=self.apply, state='disabled')
        self.apply_button.pack(side='left')
        ttk.Label(bottom, text='Backup first. Review before writing.', style='Card.TLabel').pack(side='left', padx=12)

        ttk.Label(outer, textvariable=self.stage, wraplength=760).pack(anchor='w', pady=(2, 5))
        ttk.Progressbar(outer, variable=self.percent, maximum=100).pack(fill='x')
        ttk.Label(outer, textvariable=self.summary, style='Small.TLabel', wraplength=760).pack(anchor='w', pady=(6, 10))
        log_frame = ttk.Frame(outer)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, height=3, wrap='word', state='disabled', bg='white',
                           fg='#344b59', font=('Segoe UI', 9), relief='flat', padx=10, pady=8)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        footer = ttk.Frame(outer)
        footer.pack(fill='x', pady=(10, 0))
        ttk.Button(footer, text='Save compatibility report', command=self.save_report).pack(side='left')
        ttk.Button(footer, text='Instructions', command=lambda: webbrowser.open(PROJECT_URL+'#readme')).pack(side='right')

    def _log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', str(text).strip()+'\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _controls(self, busy):
        for button in (self.check_button, self.backup_button):
            button.configure(state='disabled' if busy else 'normal')
        available = (self.checked or {}).get('available_profiles', [])
        for key, button in zip(self.profile_keys, self.profile_buttons):
            button.configure(state='disabled' if busy or (self.checked and key not in available) else 'normal')
        enabled = not busy and self.checked is not None and self.checked['compatible']
        self.apply_button.configure(state='normal' if enabled else 'disabled')

    def _start(self, name, action):
        if self.operations.running:
            return
        self.percent.set(0)
        self.stage.set('Working. Keep the USB cable connected.')
        self.summary.set('The controller is reserved for this operation.')
        self._controls(True)
        self.operations.start(name, action)

    def check(self):
        self.checked = None
        self.connection.set('Checking controller…')
        self._start('check', app.status)

    def backup(self):
        self._start('backup', lambda: app.backup(self.data_dir))

    def apply(self):
        if self.checked is None or not self.checked['compatible']:
            return
        selected = self.profile.get()
        self._start('apply', lambda: app.apply(selected, self.data_dir, confirm=self.operations.confirm))

    def _show_confirmation(self, pending):
        if self.close_when_idle:
            pending.resolve(False)
            return
        plan = pending.plan
        window = self.confirm_window = tk.Toplevel(self.root)
        window.title('Verified backup ready')
        set_window_icon(window)
        window.transient(self.root)
        window.resizable(False, False)
        content = ttk.Frame(window, padding=24)
        content.pack(fill='both', expand=True)
        ttk.Label(content, text='Ready to apply?', style='Title.TLabel').pack(anchor='w')
        ttk.Label(content, text=f'{profile_title(plan["source_profile"])} → {profile_title(plan["target_profile"])}',
                  font=('Segoe UI Semibold', 14)).pack(anchor='w', pady=(10, 12))
        ttk.Label(content, text='Firmware '+plan.get('firmware_version','1.06')).pack(anchor='w', pady=(0,8))
        if not plan.get('physical_profile_validated', True):
            ttk.Label(content, text='This profile on 1.09 has offline checks only. Its physical behavior has not been confirmed.',
                      wraplength=560).pack(anchor='w', pady=(0,12))
        ttk.Label(content, text='Your complete backup was read twice and verified on disk.\nKeep the USB cable connected until verification finishes.',
                  wraplength=560).pack(anchor='w')
        ttk.Label(content, text='Backup folder:', style='Small.TLabel').pack(anchor='w', pady=(16, 3))
        ttk.Label(content, text=plan['backup_folder'], wraplength=560).pack(anchor='w')
        ttk.Label(content, text='Application sectors: '+', '.join(plan['sectors']), style='Small.TLabel').pack(anchor='w', pady=10)
        buttons = ttk.Frame(content)
        buttons.pack(fill='x', pady=(8, 0))

        def answer(approved):
            pending.resolve(approved)
            self.confirm_window = None
            window.destroy()
            self.stage.set('Applying and verifying…' if approved else 'Cancelling. Returning to normal mode…')

        cancel = ttk.Button(buttons, text='Cancel', command=lambda: answer(False))
        cancel.pack(side='left')
        ttk.Button(buttons, text='Apply profile', style='Accent.TButton', command=lambda: answer(True)).pack(side='right')
        window.protocol('WM_DELETE_WINDOW', lambda: answer(False))
        window.bind('<Escape>', lambda event: answer(False))
        window.grab_set()
        cancel.focus_set()

    def _poll(self):
        try:
            while True:
                kind, value = self.operations.events.get_nowait()
                if kind=='message':
                    self._log(value['text'])
                    self.stage.set(value['text'].strip())
                elif kind=='progress':
                    self.stage.set(value['stage'])
                    self.percent.set(value['percent'])
                elif kind=='confirm':
                    self._show_confirmation(value)
                elif kind=='result':
                    self._result(value['name'], value['value'])
                elif kind=='error':
                    self.checked = None
                    self.last_error_type = value['type']
                    self.connection.set('Check needed')
                    self.detail.set(value['text'])
                    self.summary.set('Operation did not complete. Read the message below.')
                    self.stage.set('Operation stopped')
                    self._log(value['text'])
                    messagebox.showerror('Operation stopped', value['text'], parent=self.root)
                elif kind=='finished':
                    self._controls(False)
                    if self.close_when_idle:
                        self.root.destroy()
                        return
        except Empty:
            pass
        self.root.after(80, self._poll)

    def _result(self, name, value):
        if name=='check':
            self.checked = value
            self.last_error_type = None
            profile = profile_title(value['profile'])
            self.connection.set('Compatible controller' if value['compatible'] else 'Unsupported application')
            self.detail.set(f'{value["model"]} · Firmware {value["firmware_version"]} · {value["mode"]} mode · Ring: {profile}')
            if value['compatible'] and self.profile.get() not in value['available_profiles']:
                self.profile.set(value['profile'] if value['profile'] in value['available_profiles'] else value['available_profiles'][0])
            self.summary.set('Choose a profile or make a private backup.' if value['compatible'] else
                             'Installation disabled. A read-only backup is still available.')
        elif name=='backup':
            self.summary.set('Backup saved and verified. Use Open backups to find it.')
        elif name=='apply':
            # Connection and fingerprint must be checked again after any operation.
            self.checked = None
            self.connection.set('Profile installed' if value['outcome']=='completed' else 'Cancelled')
            self.detail.set('Ring: '+profile_title(value['profile'])+'. Check again before preparing another profile.')
            self.summary.set('Full verification passed. Check the ring, controls and vibration.' if value['outcome']=='completed' else
                             'No memory was erased or written. Your backup was kept.')
        self.percent.set(100)
        self.stage.set('Done' if name!='apply' or value['outcome']=='completed' else 'Cancelled safely')

    def open_backups(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform=='win32':
            os.startfile(self.data_dir)
        else:
            webbrowser.open(self.data_dir.resolve().as_uri())

    def save_report(self):
        path = filedialog.asksaveasfilename(parent=self.root, title='Save compatibility report',
            initialfile='ultimate2c-compatibility.json', defaultextension='.json', filetypes=[('JSON report', '*.json')])
        if path:
            try:
                Path(path).write_text(json.dumps(diagnostics(self.checked, self.last_error_type), indent=2)+'\n', encoding='utf-8')
                self._log('Compatibility report saved. No memory dumps or local paths included.')
            except OSError as error:
                messagebox.showerror('Could not save report', str(error), parent=self.root)

    def close(self):
        if self.operations.running:
            if self.operations.pending is not None:
                self.close_when_idle = True
                self.operations.decline_pending()
                if self.confirm_window is not None:
                    self.confirm_window.destroy()
                    self.confirm_window = None
            else:
                messagebox.showinfo('Operation in progress',
                    'Keep this window and the USB cable connected until the operation finishes.\nA prepared profile can be cancelled in its review window.', parent=self.root)
            return
        self.root.destroy()


def launch(data_dir=None):
    root = tk.Tk()
    RingWindow(root, app.default_data_dir() if data_dir is None else data_dir)
    root.mainloop()


if __name__=='__main__':
    launch()
