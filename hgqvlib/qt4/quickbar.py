# Copyright (c) 2009 LOGILAB S.A. (Paris, FRANCE).
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
"""
Qt4 QToolBar-based class for quick bars XXX
"""

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
from hgqvlib.qt4 import icon as geticon

class QuickBar(QtGui.QToolBar):
    def __init__(self, name, key, desc=None, parent=None):
        self.original_parent = parent
        self._focusw = None
        QtGui.QToolBar.__init__(self, name, parent)
        self.setIconSize(QtCore.QSize(16,16))
        self.setFloatable(False)
        self.setMovable(False)
        self.setAllowedAreas(Qt.BottomToolBarArea)
        self.createActions(key, desc)
        self.createContent()
        if parent:
            parent = parent.window()            
        if isinstance(parent, QtGui.QMainWindow):
            parent.addToolBar(Qt.BottomToolBarArea, self)
        self.setVisible(False)
        
    def createActions(self, openkey, desc):
        parent = self.parentWidget()
        self._actions = {}

        if not desc:
            desc = "Open"
        openact = QtGui.QAction(desc, parent)
        openact.setCheckable(True)        
        openact.setChecked(False)
        openact.setShortcut(QtGui.QKeySequence(openkey))
        connect(openact, SIGNAL('toggled(bool)'),
                self.setVisible)
        self.open_shortcut = QtGui.QShortcut(parent)
        self.open_shortcut.setKey(QtGui.QKeySequence(openkey))
        connect(self.open_shortcut, SIGNAL('activated()'),
                self.setVisible)

        closeact = QtGui.QAction('Close', self)
        closeact.setIcon(geticon('close'))
        connect(closeact, SIGNAL('triggered()'),
                lambda self=self: self.setVisible(False))
                
        self._actions = {'open': openact,
                         'close': closeact,}

        self.esc_shortcut = QtGui.QShortcut(self)
        self.esc_shortcut.setKey(Qt.Key_Escape)
        self.esc_shortcut.setEnabled(False)
        connect(self.esc_shortcut, SIGNAL('activated()'),
                self._actions['close'].trigger)

    def setVisible(self, visible=True):
        if visible and not self.isVisible():
            self.emit(SIGNAL('visible'))
            self._focusw = QtGui.QApplication.focusWidget()
        QtGui.QToolBar.setVisible(self, visible)
        self.esc_shortcut.setEnabled(visible)
        self.emit(SIGNAL('escShortcutDisabled(bool)'), not visible)
        if not visible and self._focusw:
            self._focusw.setFocus()
            self._focusw = None

    def createContent(self):
        self.addAction(self._actions['close'])

    def hide(self):
        self.setVisible(False)

if __name__ == "__main__":
    import sys
    import hgqvlib.qt4 # to force importation of resource module w/ icons
    app = QtGui.QApplication(sys.argv)
    root = QtGui.QMainWindow()
    w = QtGui.QFrame()
    root.setCentralWidget(w)
    
    qbar = QuickBar("test", "Ctrl+G", "toto", w)
    root.show()
    app.exec_()
    
