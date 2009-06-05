@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH
python -x %~f0 %*
goto exit
 
"""
# -------------------- Python section --------------------
from PyQt4 import QtCore, QtGui
from hgviewlib.qt4 import main as hgview
hgview.main()

DosExitLabel = """
:exit
rem """
