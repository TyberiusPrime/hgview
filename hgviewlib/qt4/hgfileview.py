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
try:
    from mercurial.error import LookupError
except ImportError:
    from mercurial.revlog import LookupError
    
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
from hgviewlib.util import exec_flag_changed
from hgviewlib.config import HgConfig

qsci = Qsci.QsciScintilla
class HgFileView(QtGui.QFrame):
    def __init__(self, parent=None):
        QtGui.QFrame.__init__(self, parent)
        framelayout = QtGui.QVBoxLayout(self)
        framelayout.setContentsMargins(0,0,0,0)
        framelayout.setSpacing(0)

        l = QtGui.QHBoxLayout()
        l.setContentsMargins(0,0,0,0)
        l.setSpacing(0)
        
        self.topLayout = QtGui.QVBoxLayout()
        self.filenamelabel = QtGui.QLabel()
        self.filenamelabel.setWordWrap(True)
        self.execflaglabel = QtGui.QLabel()
        self.execflaglabel.setWordWrap(True)
        self.topLayout.addWidget(self.filenamelabel)
        self.topLayout.addWidget(self.execflaglabel)
        self.execflaglabel.hide()
        framelayout.addLayout(self.topLayout)
        framelayout.addLayout(l, 1)

        self.sci = Qsci.QsciScintilla(self)
        l.addWidget(self.sci)
        self.sci.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        self.sci.setMarginLineNumbers(1, True)
        self.sci.setMarginWidth(1, '000')
        self.sci.setReadOnly(True)

        self.sci.SendScintilla(qsci.SCI_INDICSETSTYLE, 8, qsci.INDIC_ROUNDBOX)
        self.sci.SendScintilla(qsci.SCI_INDICSETUNDER, 8, True)
        self.sci.SendScintilla(qsci.SCI_INDICSETFORE, 8, 0xBBFFFF)
        self.sci.SendScintilla(qsci.SCI_INDICSETSTYLE, 9, qsci.INDIC_ROUNDBOX)
        self.sci.SendScintilla(qsci.SCI_INDICSETUNDER, 9, True)
        self.sci.SendScintilla(qsci.SCI_INDICSETFORE, 9, 0x58A8FF)

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

        ll = QtGui.QVBoxLayout()
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        l.insertLayout(0, ll)

        self.blk = BlockList(self)
        self.blk.linkScrollBar(self.sci.verticalScrollBar())
        ll.addWidget(self.blk)
        self.blk.setVisible(False)
        w = QtGui.QWidget(self)
        ll.addWidget(w)
        self._spacer = w

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

    def resizeEvent(self, event):
        QtGui.QFrame.resizeEvent(self, event)
        h = self.sci.horizontalScrollBar().height()
        self._spacer.setMinimumHeight(h)
        self._spacer.setMaximumHeight(h)

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
        self._p_rev = None
        self.sci.clear()

    def rev(self):
        return self._ctx.rev()

    def filename(self):
        return self._filename

    def displayDiff(self, rev):
        if rev != self._p_rev:
            self.displayFile(self._filename, rev)
        
    def displayFile(self, filename, rev=None):
        self._filename = filename
        if rev is not None:
            self._p_rev = rev
            self.emit(SIGNAL('revForDiffChanged'), rev)
        self.sci.clear()
        self.filenamelabel.clear()
        self.execflaglabel.clear()
        if filename is None:
            return
        try:
            filectx = self._ctx.filectx(self._filename)
        except LookupError: # occur on deleted files
            return
        if self._mode == 'diff' and self._p_rev is not None:
            mode = self._p_rev
        else:
            mode = self._mode
        flag, data = self._model.graph.filedata(filename, self._ctx.rev(), mode)
        if flag == '-':
            return
        if flag == '':
            return
        
        cfg = HgConfig(self._model.repo.ui)
        lexer = get_lexer(filename, data, flag, cfg)
        if flag == "+":
            nlines = data.count('\n')
            self.sci.setMarginWidth(1, str(nlines)+'0')
        self.sci.setLexer(lexer)
        self._cur_lexer = lexer
        if data not in ('file too big', 'binary file'):
            self.filedata = data
        else:
            self.filedata = None

        flag = exec_flag_changed(filectx)
        if flag:
            self.execflaglabel.setText("<b>exec mode has been <font color='red'>%s</font></b>" % flag)
            self.execflaglabel.show()
        else:
            self.execflaglabel.hide()

        labeltxt = "<b>%s</b>" % self._filename
        if self._p_rev is not None:
            labeltxt += ' (diff from rev %s)' % self._p_rev
        renamed = filectx.renamed()
        if renamed:
            labeltxt += ' <i>(renamed from %s)</i>' % renamed[0]
        self.filenamelabel.setText(labeltxt)

        self.sci.setText(data)
        if self._find_text:
            self.highlightSearchString(self._find_text)
        self.emit(SIGNAL('fileDisplayed'), self._filename)
        self.updateDiffDecorations()
        return True

    def updateDiffDecorations(self):
        """
        Recompute the diff and starts the timer
        responsible for filling diff decoration markers
        """
        self.blk.clear()
        if self._mode == 'file' and self.filedata is not None:
            if self.timer.isActive():
                self.timer.stop()

            parent = self._model.graph.fileparent(self._filename, self._ctx.rev())
            m = self._ctx.filectx(self._filename).renamed()
            if m:
                pfilename, pnode = m
            else:
                pfilename = self._filename
            _, parentdata = self._model.graph.filedata(pfilename,
                                                       parent, 'file')
            if parentdata is not None:
                filedata = self.filedata.splitlines()
                parentdata = parentdata.splitlines()
                self._diff = difflib.SequenceMatcher(None,
                                                     parentdata,
                                                     filedata,)
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

    def nextLine(self):
        x, y = self.sci.getCursorPosition()
        self.sci.setCursorPosition(x+1, y)

    def prevLine(self):
        x, y = self.sci.getCursorPosition()
        self.sci.setCursorPosition(x-1, y)

    def nextCol(self):
        x, y = self.sci.getCursorPosition()
        self.sci.setCursorPosition(x, y+1)

    def prevCol(self):
        x, y = self.sci.getCursorPosition()
        self.sci.setCursorPosition(x, y-1)
        
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
                # self.block['left'].addBlock('-', alo, ahi)
                # self.diffblock.addBlock('-', alo, ahi, blo, bhi)
                # w = self.viewers['left']
                # for i in range(alo, ahi):
                #     w.markerAdd(i, self.markerminus)

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
        from_rev = self.model().revFromIndex(index)
        self.emit(SIGNAL('fileSelected'), sel_file, from_rev)

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
        if  len(self.model().repo.file(filename))>0:
            dlg = FileViewer(self.model().repo, filename)
            dlg.setWindowTitle('Hg file log viewer')
            dlg.show()
            self._dlg = dlg # keep a reference on the dlg

    def diffNavigate(self, filename=None):
        if filename is None:
            filename = self.currentFile()
        if filename is not None and len(self.model().repo.file(filename))>0:
            dlg = FileDiffViewer(self.model().repo, filename)
            dlg.setWindowTitle('Hg file log viewer')
            dlg.show()
            self._dlg = dlg # keep a reference on the dlg

    def _action_defs(self):
        a = [("navigate", self.tr("Navigate"), None ,
              self.tr('Navigate the revision tree of this file'), None, self.navigate),
             ("diffnavigate", self.tr("Diff-mode navigate"), None,
              self.tr('Navigate the revision tree of this file in diff mode'), None, self.diffNavigate),
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

    def nextFile(self):
        row = self.currentIndex().row()
        self.setCurrentIndex(self.model().index(min(row+1,
                             self.model().rowCount() - 1), 0))
    def prevFile(self):
        row = self.currentIndex().row()
        self.setCurrentIndex(self.model().index(max(row - 1, 0), 0))
