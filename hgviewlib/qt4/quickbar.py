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

from mercurial import util

from PyQt4 import QtCore, QtGui

from hgviewlib.qt4 import icon as geticon

Qt = QtCore.Qt
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL


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



class FindQuickBar(QuickBar):
    def __init__(self, parent):
        QuickBar.__init__(self, "Find", "/", "Find", parent)
        self.currenttext = ''
        
    def createActions(self, openkey, desc):
        QuickBar.createActions(self, openkey, desc)
        self._actions['findnext'] = QtGui.QAction("Find next", self)
        self._actions['findnext'].setShortcut(QtGui.QKeySequence("Ctrl+N"))
        connect(self._actions['findnext'], SIGNAL('triggered()'), self.find)
        self._actions['cancel'] = QtGui.QAction("Cancel", self)
        connect(self._actions['cancel'], SIGNAL('triggered()'), self.cancel)

    def find(self, *args):
        text = unicode(self.entry.text())
        if text == self.currenttext:
            self.emit(SIGNAL('findnext'), text)
        else:
            self.currenttext = text
            self.emit(SIGNAL('find'), text)            

    def cancel(self):
        self.emit(SIGNAL('cancel'))

    def setCancelEnabled(self, enabled=True):
        self._actions['cancel'].setEnabled(enabled)
        self._actions['findnext'].setEnabled(not enabled)
        
    def createContent(self):
        QuickBar.createContent(self)
        self.compl_model = QtGui.QStringListModel()
        self.completer = QtGui.QCompleter(self.compl_model, self)
        self.entry = QtGui.QLineEdit(self)
        self.entry.setCompleter(self.completer)
        self.addWidget(self.entry)
        self.addAction(self._actions['findnext'])
        self.addAction(self._actions['cancel'])
        self.setCancelEnabled(False)
        
        connect(self.entry, SIGNAL('returnPressed()'),
                self.find)
        connect(self.entry, SIGNAL('textEdited(const QString &)'),
                self.find)
        
    def setVisible(self, visible=True):
        QuickBar.setVisible(self, visible)
        if visible:
            self.entry.setFocus()
            self.entry.selectAll()

    def text(self):
        if self.isVisible() and self.currenttext.strip():
            return self.currenttext
        

class FindInGraphlogQuickBar(FindQuickBar):
    def __init__(self, parent):
        FindQuickBar.__init__(self, parent)
        self._find_iter = None
        self._fileview = None
        self._cur_pos = None
        self._filter_files = None
        self._mode = 'diff'
        connect(self, SIGNAL('find'),
                self.on_find_text_changed)
        connect(self, SIGNAL('findnext'),
                self.on_findnext)
        connect(self, SIGNAL('cancel'),
                self.on_cancelsearch)

    def setFilterFiles(self, files):
        self._filter_files = files
        
    def setModel(self, model):
        self._model = model

    def setMode(self, mode):
        assert mode in ('diff', 'file')
        self._mode = mode
        
    def attachFileView(self, fileview):
        self._fileview = fileview
        
    def find_in_graphlog(self, text, fromrev, fromfile=None):
        """
        Find text in the whole repo from rev 'fromrev', from file
        'fromfile' (if given) *excluded*
        """
        graph = self._model.graph
        idx = graph.index(fromrev)
        for node in graph[idx:]:
            rev = node.rev
            ctx = self._model.repo.changectx(rev)
            pos = 0            
            files = ctx.files()
            if self._filter_files:
                files = [x for x in files if x in self._filter_files]
            if fromfile is not None and fromfile in files:
                files = files[files.index(fromfile)+1:]
                fromfile = None
            for filename in files:
                if self._mode == 'diff':
                    flag, data = self._model.graph.filedata(filename, rev)
                else:
                    data = ctx.filectx(filename).data()
                    if util.binary(data):
                        data = "binary file"
                if text in data:
                    yield rev, filename
                else:
                    yield None

    def on_cancelsearch(self, *args):
        self._find_iter = None
        self.setCancelEnabled(False)
        self.emit(SIGNAL('showMessage'), 'Search cancelled!', 2000)

    def on_findnext(self, text=None):
        """
        callback called by 'Find' quicktoolbar (on findnext signal)
        """
        if self._find_iter is not None:
            for pos in self._find_iter:
                #self._cur_pos = pos[:2]
                break
            else:
                self._find_iter = None            
        if self._find_iter is None: # start searching in the graphlog
            if self._fileview:
                rev = self._fileview.rev()
                filename = self._fileview.filename()
            else: # XXX does not work
                rev, filename = self._cur_pos
            
            self._find_iter = self.find_in_graphlog(text, rev, filename)
            self.setCancelEnabled(True)
            self.find_next(text)

    def find_next(self, text, step=0):
        """
        to be called from 'on_find' callback (or recursively). Try to
        find the next occurrence of 'text' (as a 'background'
        process, so the GUI is not frozen, and as a cancellable task).
        """
        if self._find_iter is None:
            return
        for next_find in self._find_iter:
            if next_find is None: # not yet found, let's animate a bit the GUI
                if (step % 20) == 0:
                    self.emit(SIGNAL("showMessage"), 'Searching'+'.'*(step/20))
                step += 1
                QtCore.QTimer.singleShot(0, lambda self=self, text=text, step=(step % 80): \
                                         self.find_next(text, step))
            else:
                self.emit(SIGNAL("showMessage"), '')
                self.setCancelEnabled(False)
                
                rev, filename = next_find
                self._cur_pos = next_find
                self.emit(SIGNAL('revisionSelected'), rev)
                self.emit(SIGNAL('fileSelected'), filename)
                if self._fileview:
                    self._find_iter = self._fileview.searchString(text)
                    self.on_findnext()
            return
        self.emit(SIGNAL('showMessage'), 'No more matches found in repository', 2000)
        self.setCancelEnabled(False)
        self._find_iter = None

    def on_find_text_changed(self, newtext):
        """
        callback called by 'Find' quicktoolbar (on find signal)
        """
        newtext = unicode(newtext)
        self._find_iter = None
        if self._fileview:
            self._find_iter = self._fileview.searchString(newtext)
            for pos in self._find_iter:
                self._cur_pos = pos[:2]
                break
            else:
                if newtext.strip():
                    self._find_iter = None
                    self.emit(SIGNAL('showMessage'),
                              'Search string not found in current diff. '
                              'Hit "Find next" button to start searching '
                              'in the repository', 2000)
        

if __name__ == "__main__":
    import sys
    import hgviewlib.qt4 # to force importation of resource module w/ icons
    app = QtGui.QApplication(sys.argv)
    root = QtGui.QMainWindow()
    w = QtGui.QFrame()
    root.setCentralWidget(w)
    
    qbar = QuickBar("test", "Ctrl+G", "toto", w)
    root.show()
    app.exec_()
    
