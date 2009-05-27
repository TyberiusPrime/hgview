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
Qt4 high level widgets for hg repo changelogs and filelogs
"""
import sys

from mercurial.node import hex, short as short_hex, bin as short_bin

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

from hgqvlib.decorators import timeit
from hgqvlib.qt4 import icon as geticon
from hgqvlib.qt4.hgfileviewer import FileViewer, FileDiffViewer, ManifestViewer
from hgqvlib.qt4.quickbar import QuickBar

class HgFileListView(QtGui.QTableView):
    """
    A QTableView for displaying a HgFileListModel
    """
    def __init__(self, parent=None):
        QtGui.QTableView.__init__(self, parent)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(20)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setTextElideMode(Qt.ElideLeft)
        self.horizontalHeader().setToolTip('Double click to toggle merge mode')
        
        self.createActions()
        
        connect(self.horizontalHeader(), SIGNAL('sectionDoubleClicked(int)'),
                self.toggleFullFileList)
        connect(self,
                SIGNAL('doubleClicked (const QModelIndex &)'),
                self.fileActivated)
        
        connect(self.horizontalHeader(),
                SIGNAL('sectionResized(int, int, int)'),
                self.sectionResized)        

    def setModel(self, model):
        QtGui.QTableView.setModel(self, model)
        connect(model, SIGNAL('layoutChanged()'),
                self.fileSelected)
        connect(self.selectionModel(),
                SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                self.fileSelected)

    def currentFile(self):
        index = self.currentIndex()
        return self.model().fileFromIndex(index)
        
    def fileSelected(self, index=None, *args):
        if index is None:
            index = self.currentIndex()
        sel_file = self.model().fileFromIndex(index)
        self.emit(SIGNAL('fileSelected'), sel_file)

    def fileActivated(self, index):
        sel_file = self.model().fileFromIndex(index)
        self.diffNavigate(sel_file)
        
    def toggleFullFileList(self, *args):
        self.model().toggleFullFileList()

    def navigate(self, filename=None):
        if filename is None:
            filename = self.currentFile()
        if  len(self.model().repo.file(filename))>1:
            dlg = FileViewer(self.model().repo, filename)
            dlg.setWindowTitle('Hg file log viewer')
            dlg.show()
            self._dlg = dlg # keep a reference on the dlg

    def diffNavigate(self, filename=None):
        if filename is None:
            filename = self.currentFile()
        if  len(self.model().repo.file(filename))>1:
            dlg = FileDiffViewer(self.model().repo, filename)
            dlg.setWindowTitle('Hg file log viewer')
            dlg.show()
            self._dlg = dlg # keep a reference on the dlg
    
    def _action_defs(self):
        a = [("navigate", self.tr("Navigate"), None , self.tr('Navigate the revision tree of this file'), None, self.navigate),
             ("diffnavigate", self.tr("Diff-mode navigate"), None , self.tr('Navigate the revision tree of this file in diff mode'), None, self.diffNavigate),
             ]
        return a

    def createActions(self):
        self._actions = {}
        for name, desc, icon, tip, key, cb in self._action_defs():
            act = QtGui.QAction(desc, self)
            if icon:
                act.setIcon(geticon(icon))
            if tip:
                act.setStatusTip(tip)
            if key:
                act.setShortcut(key)
            if cb:
                connect(act, SIGNAL('triggered()'), cb)
            self._actions[name] = act
            self.addAction(act)
        
    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        for act in ['navigate', 'diffnavigate']:
            if act:
                menu.addAction(self._actions[act])
            else:
                menu.addSeparator()
        menu.exec_(event.globalPos())
        
    def resizeEvent(self, event):
        QtGui.QTableView.resizeEvent(self, event)
        vp_width = self.viewport().width()
        col_widths = [self.columnWidth(i) \
                      for i in range(1, self.model().columnCount())]
        col_width = vp_width - sum(col_widths)
        self.setColumnWidth(0, col_width)

    def sectionResized(self, idx, oldsize, newsize):
        if idx == 1:
            self.model().setDiffWidth(newsize)
