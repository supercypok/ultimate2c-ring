"""Build only our app, interpreter and declared libraries; no workspace scan."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ultimate2c_ring import __version__


def main():
    if sys.platform!='win32': raise SystemExit('Build the Windows app on Windows.')
    output=ROOT/'dist'
    output.mkdir(exist_ok=True)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean',
             '--distpath',str(output),'--workpath',str(ROOT/'build'),
             str(ROOT/'scripts'/'windows.spec')]
    environment=dict(os.environ)
    environment['PYINSTALLER_CONFIG_DIR']=str(ROOT/'build'/'pyinstaller-cache')
    if '--package-only' not in sys.argv[1:]:
        subprocess.run(command,cwd=ROOT,check=True,env=environment)
    folder=output/'Ultimate2CRing'
    if '--package-only' in sys.argv[1:]:
        built_version=subprocess.check_output([str(folder/'Ultimate2CRingCLI.exe'),'--version'],text=True).strip()
        if built_version != __version__:
            raise RuntimeError('Existing executable does not match the source version.')
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','CHANGELOG.md'):
        shutil.copy2(ROOT/name,folder/name)
    (folder/'docs').mkdir(exist_ok=True)
    for name in ('technical.md','validation.md','app.jpg'):
        shutil.copy2(ROOT/'docs'/name,folder/'docs'/name)
    licenses=folder/'_internal'/'licenses'
    licenses.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python-LICENSE.txt')
    tk_license=Path(sys.base_prefix)/'tcl'/'tk8.6'/'license.terms'
    if not tk_license.exists(): raise RuntimeError('Tcl/Tk license text was not found.')
    shutil.copy2(tk_license,licenses/'Tk-license.terms')
    shutil.copy2(ROOT/'licenses'/'Tcl-license.terms',licenses/'Tcl-license.terms')
    for package in ('hidapi','pyinstaller'):
        distribution=importlib.metadata.distribution(package)
        found=False
        for file in distribution.files:
            if 'licenses/' in str(file).replace('\\','/'):
                target=licenses/package/Path(file).name
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(distribution.locate_file(file),target)
                found=True
        if not found: raise RuntimeError(f'Missing licenses for {package}')
    dependencies={name:importlib.metadata.version(name) for name in (
        'hidapi','pyinstaller','pyinstaller-hooks-contrib','altgraph','packaging',
        'pefile','pywin32-ctypes','setuptools')}
    (folder/'BUILD-DEPENDENCIES.json').write_text(json.dumps(dependencies,indent=2)+'\n',encoding='utf-8')
    archive=output/f'ultimate2c-ring-{__version__}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if not path.is_file(): continue
            assert path.suffix not in ('.bin','.dat','.jsonl'),path
            if path.suffix=='.zip': assert path.name=='base_library.zip',path
            assert 'backups' not in path.parts and 'private' not in path.parts,path
            z.write(path,path.relative_to(output).as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(f'Windows package: {archive}\nSHA-256: {digest}')


if __name__=='__main__': main()
