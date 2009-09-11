@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH
python -x %~f0 %*
goto exit
 
"""
# -------------------- Python section --------------------
from PyQt4 import QtCore, QtGui
import os
import sys
import os.path as pos

try:
    import hgviewlib
except ImportError:
    import stat
    execpath = pos.abspath(__file__)
    # resolve symbolic links
    statinfo = os.lstat(execpath)
    if stat.S_ISLNK(statinfo.st_mode):
        execpath = pos.abspath(pos.join(pos.dirname(execpath),
                                        os.readlink(execpath)))
    sys.path.append(pos.abspath(pos.join(pos.dirname(execpath), "..")))

from hgviewlib.qt4.hgrepoviewer import main 
main()

DosExitLabel = """
:exit
rem """
