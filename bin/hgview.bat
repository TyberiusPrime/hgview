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

if getattr(sys, 'frozen', None) == "windows_exe":
    # Standalone version of hgview built with py2exe use its own version
    # of Mercurial. Using configuration from the global Mercurial.ini will be
    # ill-advised as the installed version of Mercurial itself may be
    # different than the one we ship.
    #
    # this will be found next to Mercurial.ini
    path = pos.join(os.path.expanduser('~'), 'hgview.ini')
    os.environ['HGRCPATH'] = path

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

from hgviewlib.application import main
main()

DosExitLabel = """
:exit
rem """
