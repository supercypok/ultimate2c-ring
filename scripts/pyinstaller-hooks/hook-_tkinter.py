"""Bundle Tcl/Tk script trees from the Python used for this Windows build."""
import os
from pathlib import Path
import sys
import _tkinter

base=Path(sys.base_prefix)/'tcl'
trees=(
    (Path(os.environ.get('TCL_LIBRARY',str(base/f'tcl{_tkinter.TCL_VERSION}'))),'_tcl_data','init.tcl'),
    (Path(os.environ.get('TK_LIBRARY',str(base/f'tk{_tkinter.TK_VERSION}'))),'_tk_data','tk.tcl'),
)
datas=[]
for source,destination,required in trees:
    if not (source/required).is_file():
        raise RuntimeError(f'Python Tcl/Tk installation is incomplete: missing {required}')
    for path in source.rglob('*'):
        if path.is_file():
            datas.append((str(path),str(Path(destination)/path.relative_to(source).parent)))
