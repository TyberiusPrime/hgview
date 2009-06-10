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
import difflib

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
from hgviewlib.qt4.blockmatcher import BlockList

qsci = Qsci.QsciScintilla
class HgFileView(QtGui.QFrame):
    def __init__(self, parent=None):
        QtGui.QFrame.__init__(self, parent)
        l = QtGui.QHBoxLayout(self)        
        l.setContentsMargins(0,0,0,0)
        self.sci = Qsci.QsciScintilla(self)
        l.addWidget(self.sci)
        
        self.sci.setMarginLineNumbers(1, True)
        self.sci.setMarginWidth(1, '000')
        self.sci.setReadOnly(True)
        #self.setFont(self.font)

        self.sci.SendScintilla(qsci.SCI_INDICSETSTYLE, 8, qsci.INDIC_ROUNDBOX)
        self.sci.SendScintilla(qsci.SCI_INDICSETUNDER, 8, True)
        self.sci.SendScintilla(qsci.SCI_INDICSETFORE, 8, 0xBBFFFF)
        self.sci.SendScintilla(qsci.SCI_INDICSETSTYLE, 9, qsci.INDIC_ROUNDBOX)
        self.sci.SendScintilla(qsci.SCI_INDICSETUNDER, 9, True)
        self.sci.SendScintilla(qsci.SCI_INDICSETFORE, 9, 0x58A8FF)

        self.sci.SendScintilla(qsci.SCI_SETSELEOLFILLED, True)

        # hide margin 0 (markers)
        self.sci.SendScintilla(qsci.SCI_SETMARGINTYPEN, 0, 0)
        self.sci.SendScintilla(qsci.SCI_SETMARGINWIDTHN, 0, 0)

        # define markers for colorize zones of diff
        self.markerplus = self.sci.markerDefine(Qsci.QsciScintilla.Background)
        self.sci.SendScintilla(qsci.SCI_MARKERSETBACK, self.markerplus, 0xB0FFA0)
        self.markerminus = self.sci.markerDefine(Qsci.QsciScintilla.Background)
        self.sci.SendScintilla(qsci.SCI_MARKERSETBACK, self.markerminus, 0xA0A0FF)
        self.markertriangle = self.sci.markerDefine(Qsci.QsciScintilla.Background)
        self.sci.SendScintilla(qsci.SCI_MARKERSETBACK, self.markertriangle, 0xFFA0A0)

        self.blk = BlockList(self)
        self.blk.linkScrollBar(self.sci.verticalScrollBar())
        l.insertWidget(0, self.blk)

        self._model = None
        self._ctx = None
        self._filename = None
        self._find_text = None
        self._mode = "diff" # can be 'diff' or 'file' 
        self.filedata = None

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(False)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.idle_fill_files)

    def setMode(self, mode):
        if isinstance(mode, bool):
            mode = ['file', 'diff'][mode]
        assert mode in ('diff', 'file')
        if mode != self._mode:
            self._mode = mode
            self.blk.setVisible(self._mode == 'file')
            self.displayFile(self._filename)
        
    def setModel(self, model):
        # XXX we really need only the "Graph" instance 
        self._model = model
        self.sci.clear()
        
    def setContext(self, ctx):
        self._ctx = ctx
        self.sci.clear()

    def rev(self):
        return self._ctx.rev()

    def filename(self):
        return self._filename
    
    def displayFile(self, filename):
        self._filename = filename
        self.sci.clear()
        if filename is None:
            return
        flag, data = self._model.graph.filedata(filename, self._ctx.rev(), self._mode)
        lexer = None
        if flag == "+":
            lexer = get_lexer(filename, data)
            nlines = data.count('\n')
            self.sci.setMarginWidth(1, str(nlines)+'0')            
        elif flag == "=":
            lexer = Qsci.QsciLexerDiff()
            self.sci.setMarginWidth(1, 0)
        if lexer:
            lexer.setDefaultFont(self.font())
            lexer.setFont(self.font())
        self.sci.setLexer(lexer)
        self._cur_lexer = lexer
        if data not in ('file too big', 'binary file'):
            self.filedata = data
        else:
            self.filedata = None
        
        self.sci.setText(data)
        if self._find_text:
            self.highlightSearchString(self._find_text)
        self.updateDiff()
        
    def updateDiff(self):
        """
        Recompute the diff, display files and starts the timer
        responsible for filling diff markers
        """
        self.blk.clear()
        if self._mode == 'file' and self.filedata is not None:
            if self.timer.isActive():
                self.timer.stop()

            parent = self._model.graph.fileparent(self._filename, self._ctx.rev())
            _, parentdata = self._model.graph.filedata(self._filename,
                                                       parent, 'file')
            filedata = self.filedata.splitlines()
            parentdata = parentdata.splitlines()
            self._diff = difflib.SequenceMatcher(None, filedata,
                                                 parentdata)
            self._diffs = []
            self.blk.syncPageStep()
            self.timer.start()

    def nextDiff(self):
        if self._mode == 'file':
            row, column = self.sci.getCursorPosition()
            for i, (lo, hi) in enumerate(self._diffs):
                if lo > row:
                    last = (i == (len(self._diffs)-1))
                    break
            else:
                return False
            self.sci.setCursorPosition(lo, 0)
            self.sci.verticalScrollBar().setValue(lo)
            return not last
        
    def prevDiff(self):
        if self._mode == 'file':
            row, column = self.sci.getCursorPosition()
            for i, (lo, hi) in enumerate(reversed(self._diffs)):
                if hi < row:
                    first = (i == (len(self._diffs)-1))
                    break
            else:
                return False
            self.sci.setCursorPosition(lo, 0)
            self.sci.verticalScrollBar().setValue(lo)
            return not first
        
    def nDiffs(self):
        return len(self._diffs)

    def diffMode(self):
        return self._mode == 'diff'
    def fileMode(self):
        return self._mode == 'file'
        
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
        n = self.sci.length()
        self.sci.SendScintilla(qsci.SCI_SETINDICATORCURRENT, 8) # highlight
        self.sci.SendScintilla(qsci.SCI_INDICATORCLEARRANGE, 0, n)
        self.sci.SendScintilla(qsci.SCI_SETINDICATORCURRENT, 9) # current found occurrence
        self.sci.SendScintilla(qsci.SCI_INDICATORCLEARRANGE, 0, n)

    def highlightSearchString(self, text):
        data = unicode(self.sci.text())
        self.sci.SendScintilla(qsci.SCI_SETINDICATORCURRENT, 8)
        pos = [data.find(text)]
        n = len(text)
        while pos[-1] > -1:
            self.sci.SendScintilla(qsci.SCI_INDICATORFILLRANGE, pos[-1], n)
            pos.append(data.find(text, pos[-1]+1))
        pos = [x for x in pos if x > -1]
        self.emit(SIGNAL('showMessage'),
                  "Found %d occurrences of '%s' in current file or diff" % (len(pos), text),
                  2000)
        return pos
        
    def highlightCurrentSearchString(self, pos, text):
        line = self.sci.SendScintilla(qsci.SCI_LINEFROMPOSITION, pos)
        #line, idx = w.lineIndexFromPosition(nextpos)
        self.sci.ensureLineVisible(line)
        self.sci.SendScintilla(qsci.SCI_SETINDICATORCURRENT, 9)
        self.sci.SendScintilla(qsci.SCI_INDICATORCLEARRANGE, 0, pos)
        self.sci.SendScintilla(qsci.SCI_INDICATORFILLRANGE, pos, len(text))

    def verticalScrollBar(self):
        return self.sci.verticalScrollBar()


    def idle_fill_files(self):
        # we make a burst of diff-lines computed at once, but we
        # disable GUI updates for efficiency reasons, then only
        # refresh GUI at the end of the burst
        self.sci.setUpdatesEnabled(False)
        self.blk.setUpdatesEnabled(False)
        for n in range(30): # burst pool
            if self._diff is None or not self._diff.get_opcodes():
                self._diff = None
                self.timer.stop()
                self.emit(SIGNAL('filled'))
                break

            tag, alo, ahi, blo, bhi = self._diff.get_opcodes().pop(0)
            if tag == 'replace':
                self._diffs.append([blo, bhi])
                self.blk.addBlock('x', blo, bhi)
                for i in range(blo, bhi):
                    self.sci.markerAdd(i, self.markertriangle)

            elif tag == 'delete':
                pass
##                 self.block['left'].addBlock('-', alo, ahi)
##                 self.diffblock.addBlock('-', alo, ahi, blo, bhi)
##                 w = self.viewers['left']
##                 for i in range(alo, ahi):
##                     w.markerAdd(i, self.markerminus)

            elif tag == 'insert':
                self._diffs.append([blo, bhi])
                self.blk.addBlock('+', blo, bhi)
                for i in range(blo, bhi):
                    self.sci.markerAdd(i, self.markerplus)

            elif tag == 'equal':
                pass

            else:
                raise ValueError, 'unknown tag %r' % (tag,)

        # ok, let's enable GUI refresh for code viewers and diff-block displayers
        self.sci.setUpdatesEnabled(True)
        self.blk.setUpdatesEnabled(True)

        
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
        self.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)        

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

    def fileActivated(self, index, alternate=False):
        sel_file = self.model().fileFromIndex(index)
        if alternate:
            self.navigate(sel_file)
        else:
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
        vp_width = self.viewport().width()
        col_widths = [self.columnWidth(i) \
                      for i in range(1, self.model().columnCount())]
        col_width = vp_width - sum(col_widths)
        col_width = max(col_width, 50)
        self.setColumnWidth(0, col_width)
        QtGui.QTableView.resizeEvent(self, event)

    def sectionResized(self, idx, oldsize, newsize):
        if idx == 1:
            self.model().setDiffWidth(newsize)
