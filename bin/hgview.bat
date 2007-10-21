@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH or GTK environment variables here
python -x %~f0 %*
goto exit
 
"""
# -------------------- Python section --------------------
try:
    from hgview.gtk import hgview_gtk as hgview
except ImportError:    
    from PyQt4 import QtCore, QtGui
    from hgview.qt4 import hgview_qt4 as hgview
hgview.main()

DosExitLabel = """
:exit
rem """
