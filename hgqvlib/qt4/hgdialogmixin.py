# -*- coding: utf-8 -*-
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

#
# make sur the Qt rc files are converted into python modules, then load them
# this must be done BEFORE other hgqv qt4 modules are loaded.
import os
import os.path as osp
import sys

from PyQt4 import QtCore
from PyQt4 import QtGui, uic
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
Qt = QtCore.Qt

from hgqvlib.config import HgConfig

    
class HgDialogMixin(object):
    """
    Mixin for QDialogs defined from a .ui file, wich automates the
    setup of the UI from the ui file, and the loading of user
    preferences.
    The main class must define a '_ui_file' class attribute.
    """
    def __init__(self):
        # self.repo must be defined in actual class before calling __init__
        assert self.repo is not None
        self.load_config()
        self.load_ui()
        
    def load_ui(self):
        # load qt designer ui file
        for _path in [osp.dirname(__file__),
                      osp.join(sys.exec_prefix, 'share/hgqv'),
                      osp.expanduser('~/share/hgqv'),
                      osp.join(osp.dirname(__file__), "../../../../../share/hgqv"),
                      ]:
            ui_file = osp.join(_path, self._uifile)
            if osp.isfile(ui_file):
                break
        else:
            raise ValueError("Unable to find hgqv.ui\n"
                             "Check your installation.")
        uifile = osp.join(osp.dirname(__file__), ui_file)
        self.ui = uic.loadUi(uifile, self)

        # we explicitely create a QShortcut so we can disable it
        # when a "helper context toolbar" is activated (which can be
        # closed hitting the Esc shortcut)
        self.esc_shortcut = QtGui.QShortcut(self)
        self.esc_shortcut.setKey(Qt.Key_Escape)
        connect(self.esc_shortcut, SIGNAL('activated()'),
                self.close)
        self._quickbars = []

    def attachQuickBar(self, qbar):
        qbar.setParent(self)
        self._quickbars.append(qbar)
        connect(qbar, SIGNAL('escShortcutDisabled(bool)'),
                self.esc_shortcut.setEnabled)
        self.addToolBar(Qt.BottomToolBarArea, qbar)
        connect(qbar, SIGNAL('visible'),
                self.ensureOneQuickBar)

    def ensureOneQuickBar(self):
        tb = self.sender()
        for w in self._quickbars:
            if w is not tb:
                w.hide()
        
    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        fontstr = cfg.getFont()
        font = QtGui.QFont()
        try:
            if not font.fromString(fontstr):
                raise Exception
        except:
            print "bad font name '%s'" % fontstr
            font.setFamily("Monospace")
            font.setFixedPitch(True)
            font.setPointSize(10)
        self._font = font

        self.rowheight = cfg.getRowHeight()
        self.users, self.aliases = cfg.getUsers()
        return cfg

    def accept(self):
        self.close()
    def reject(self):
        self.close()

        
