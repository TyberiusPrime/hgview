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
from mercurial import util

from PyQt4 import QtCore, QtGui, Qsci
Qt = QtCore.Qt
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

from hgviewlib.decorators import timeit
from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgfileviewer import FileViewer, FileDiffViewer, ManifestViewer
from hgviewlib.qt4.quickbar import QuickBar
from hgviewlib.qt4.lexers import get_lexer

class HgFileView(Qsci.QsciScintilla):
    def __init__(self, parent=None):
        Qsci.QsciScintilla.__init__(self, parent)
        self.setMarginLineNumbers(1, True)
        self.setMarginWidth(1, '000')
        self.setReadOnly(True)
        #self.setFont(self.font)

        self.SendScintilla(self.SCI_INDICSETSTYLE, 8, self.INDIC_ROUNDBOX)
        self.SendScintilla(self.SCI_INDICSETUNDER, 8, True)
        self.SendScintilla(self.SCI_INDICSETFORE, 8, 0xBBFFFF)
        self.SendScintilla(self.SCI_INDICSETSTYLE, 9, self.INDIC_PLAIN)
        self.SendScintilla(self.SCI_INDICSETUNDER, 9, False)
        self.SendScintilla(self.SCI_INDICSETFORE, 9, 0x0000FF)

        self.SendScintilla(self.SCI_SETSELEOLFILLED, True)

        self._model = None
        self._ctx = None
        self._filename = None
        self._find_text = None
        self._mode = "diff" # can be 'diff' or 'file' 

    def setMode(self, mode):
        assert mode in ('diff', 'file')
        if mode != self._mode:
            self._mode = mode
            self.displayFile(self._filename)
        
    def setModel(self, model):
        # XXX we really need only the "Graph" instance 
        self._model = model
        self.clear()
        
    def setContext(self, ctx):
        self._ctx = ctx
        self.clear()

    def rev(self):
        return self._ctx.rev()

    def filename(self):
        return self._filename
    
    def displayFile(self, filename):
        self._filename = filename
        self.clear()
        if filename is None:
            return
        if self._mode == 'file':
            flag = "+"            
            data = self._ctx.filectx(filename).data()
            if util.binary(data):
                data = "binary file"
        else:
            flag, data = self._model.graph.filedata(filename, self._ctx.rev())
        lexer = None
        if flag == "+":
            lexer = get_lexer(filename, data)
            nlines = data.count('\n')
            self.setMarginWidth(1, str(nlines)+'0')            
        elif flag == "=":
            lexer = Qsci.QsciLexerDiff()
            self.setMarginWidth(1, 0)
        if lexer:
            lexer.setDefaultFont(self.font())
            lexer.setFont(self.font())
        self.setLexer(lexer)
        self._cur_lexer = lexer

        self.setText(data)
        if self._find_text:
            self.highlightSearchString(self._find_text)
        
    def searchString(self, text):
        self._find_text = text
        self.clearHighlights()
        if self._find_text:
            for pos in self.highlightSearchString(self._find_text):
                if not self._find_text: # XXX is this required to handle "cancellation"?
                    break                
                self.highlightCurrentSearchString(pos, self._find_text)
                yield self._ctx.rev(), self._filename, pos
                
    def clearHighlights(self):
        n = self.length()
        self.SendScintilla(self.SCI_SETINDICATORCURRENT, 8) # highlight
        self.SendScintilla(self.SCI_INDICATORCLEARRANGE, 0, n)
        self.SendScintilla(self.SCI_SETINDICATORCURRENT, 9) # current found occurrence
        self.SendScintilla(self.SCI_INDICATORCLEARRANGE, 0, n)

    def highlightSearchString(self, text):
        data = unicode(self.text())
        self.SendScintilla(self.SCI_SETINDICATORCURRENT, 8)
        pos = [data.find(text)]
        n = len(text)
        while pos[-1] > -1:
            self.SendScintilla(self.SCI_INDICATORFILLRANGE, pos[-1], n)
            pos.append(data.find(text, pos[-1]+1))
        pos = [x for x in pos if x > -1]
        return pos
        
    def highlightCurrentSearchString(self, pos, text):
        line = self.SendScintilla(self.SCI_LINEFROMPOSITION, pos)
        #line, idx = w.lineIndexFromPosition(nextpos)
        self.ensureLineVisible(line)
        self.SendScintilla(self.SCI_SETINDICATORCURRENT, 9)
        self.SendScintilla(self.SCI_INDICATORCLEARRANGE, 0, pos)
        self.SendScintilla(self.SCI_INDICATORFILLRANGE, pos, len(text))

        
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

    def selectFile(self, filename):
        self.setCurrentIndex(self.model().indexFromFile(filename))

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
        col_width = max(col_width, 50)
        self.setColumnWidth(0, col_width)

    def sectionResized(self, idx, oldsize, newsize):
        if idx == 1:
            self.model().setDiffWidth(newsize)
