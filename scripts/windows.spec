# Two entry points share one interpreter and the same application code.
from pathlib import Path

root=Path(SPECPATH).resolve()
if root.name=='scripts': root=root.parent
a=Analysis([str(root/'desktop_entry.py')],pathex=[str(root)],
           binaries=[],datas=[(str(root/'ultimate2c_ring/assets'), 'ultimate2c_ring/assets')],hiddenimports=['hid'],
           hookspath=[str(root/'scripts'/'pyinstaller-hooks')],
           runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Ultimate2CRing',
        debug=False,strip=False,upx=False,console=False,icon=str(root/'ultimate2c_ring/assets/app.ico'))
cli=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Ultimate2CRingCLI',
        debug=False,strip=False,upx=False,console=True,icon=str(root/'ultimate2c_ring/assets/app.ico'))
coll=COLLECT(gui,cli,a.binaries,a.datas,strip=False,upx=False,name='Ultimate2CRing')
