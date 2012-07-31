# -*- coding: iso-8859-1 -*-
# main.py - qt4-based hg rev log browser
#
# Copyright (C) 2007-2010 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Help window for hgview
"""
import sys, os
import re

from PyQt4 import QtCore, QtGui, Qsci

from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgdialogmixin import HgDialogMixin
from hgviewlib.hgviewhelp import help_msg, get_options_helpmsg

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL

try:
    from docutils.core import publish_string
except:
    def publish_string(s, *args, **kwargs):
        return s

class HelpViewer(QtGui.QDialog, HgDialogMixin):
    """hgview simple help viewer"""
    _uifile = 'helpviewer.ui'
    def __init__(self, repo, parent=None):
        self.repo = repo
        QtGui.QDialog.__init__(self, parent)
        HgDialogMixin.__init__(self)
        data = help_msg + get_options_helpmsg(rest=True)

        formated_text = publish_string(data, writer_name='html')
        self.textBrowser.setText(formated_text)

    # must be redefined cause it's a QDialog
    def accept(self):
        QtGui.QDialog.accept(self)

    def reject(self):
        QtGui.QDialog.reject(self)


