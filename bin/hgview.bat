@echo off
rem = """-*-Python-*- script
rem -------------------- DOS section --------------------
rem You could set PYTHONPATH or GTK environment variables here
python -x %~f0 %*
goto exit
 
"""
# -------------------- Python section --------------------
import sys
from hgview import hgview
hgview.main()
 

DosExitLabel = """
:exit
rem """
