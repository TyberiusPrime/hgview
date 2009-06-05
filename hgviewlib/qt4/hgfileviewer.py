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
"""
Qt4 dialogs to display hg revisions of a file
"""

import sys, os
import os.path as osp

import difflib

from mercurial import ui, hg
from mercurial.node import hex, short as short_hex
from mercurial.revlog import LookupError

from PyQt4 import QtGui, QtCore, Qsci
from PyQt4.QtCore import Qt

from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgdialogmixin import HgDialogMixin
from hgviewlib.qt4.hgrepomodel import FileRevModel, ManifestModel
from hgviewlib.qt4.blockmatcher import BlockList, BlockMatch
from hgviewlib.qt4.lexers import get_lexer
from hgviewlib.qt4.quickbar import FindInGraphlogQuickBar

connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

sides = ('left', 'right')
otherside = {'left': 'right', 'right': 'left'}


class FileViewer(QtGui.QMainWindow, HgDialogMixin):
    _uifile = 'fileviewer.ui'
    def __init__(self, repo, filename, noderev=None):
        self.repo = repo
        self.rev = noderev
        QtGui.QMainWindow.__init__(self)
        HgDialogMixin.__init__(self)

        # hg repo
        self.filename = filename
        self.createActions()
        self.createToolbars()

        self.textView.setFont(self._font)
        self.setupModels()
        
    def createToolbars(self):
        self.find_toolbar = FindInGraphlogQuickBar(self)
        self.find_toolbar.attachFileView(self.textView)
        connect(self.find_toolbar, SIGNAL('revisionSelected'),
                self.tableView_revisions.goto)
        connect(self.find_toolbar, SIGNAL('showMessage'),
                self.statusBar().showMessage)
        self.attachQuickBar(self.find_toolbar)

        self.toolBar_edit.addAction(self.tableView_revisions._actions['back'])
        self.toolBar_edit.addAction(self.tableView_revisions._actions['forward'])

        self.attachQuickBar(self.tableView_revisions.goto_toolbar)
        
    def setupModels(self):
        self.filerevmodel = FileRevModel(self.repo, self.filename, self.rev)
        self.tableView_revisions.setModel(self.filerevmodel)
        self.connect(self.tableView_revisions,
                     SIGNAL('revisionSelected'),
                     self.revisionSelected)
        self.textView.setMode('file')
        self.textView.setModel(self.filerevmodel)
        self.find_toolbar.setModel(self.filerevmodel)
        self.find_toolbar.setFilterFiles([self.filename])
        self.find_toolbar.setMode('file')
        
    def createActions(self):
        connect(self.actionClose, SIGNAL('triggered()'),
                self.close)
        connect(self.actionReload, SIGNAL('triggered()'),
                self.reload)
        self.actionClose.setIcon(geticon('quit'))
        self.actionReload.setIcon(geticon('reload'))

    def reload(self):
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self.setupModels()        
        
    def revisionSelected(self, rev):
        pos = self.textView.verticalScrollBar().value()
        ctx = self.filerevmodel.repo.changectx(rev)
        self.textView.setContext(ctx)
        self.textView.displayFile(self.filename)
        self.textView.verticalScrollBar().setValue(pos)

        
class ManifestViewer(QtGui.QMainWindow, HgDialogMixin):
    """
    Qt4 dialog to display all files of a repo at a given revision
    """
    _uifile = 'manifestviewer.ui'
    def __init__(self, repo, noderev):
        self.repo = repo
        QtGui.QMainWindow.__init__(self)
        HgDialogMixin.__init__(self)
        self.setWindowTitle('Hg manifest viewer - %s:%s' % (repo.root, noderev))

        # hg repo
        self.repo = repo
        self.rev = noderev
        self.setupModels()

        self.createActions()        
        self.setupTextview()

    def setupModels(self):
        self.treemodel = ManifestModel(self.repo, self.rev)
        self.treeView.setModel(self.treemodel)
        connect(self.treeView.selectionModel(),
                SIGNAL('currentChanged(const QModelIndex &, const QModelIndex &)'),
                self.fileSelected)
        
    def createActions(self):
        connect(self.actionClose, SIGNAL('triggered()'),
                self.close)
        self.actionClose.setIcon(geticon('quit'))
        
    def setupTextview(self):
        lay = QtGui.QHBoxLayout(self.mainFrame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        sci = Qsci.QsciScintilla(self.mainFrame)
        lay.addWidget(sci)
        sci.setMarginLineNumbers(1, True)
        sci.setMarginWidth(1, '000')
        sci.setReadOnly(True)
        sci.setFont(self._font)

        sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
        self.textView = sci
        
    def fileSelected(self, index, *args):
        if not index.isValid():
            return
        path = self.treemodel.pathFromIndex(index)
        try:
            fc = self.repo.changectx(self.rev).filectx(path)
        except LookupError:
            # may occur when a directory is selected
            self.textView.setMarginWidth(1, '00')
            self.textView.setText('')
            return
        
        if fc.size() > 100000: # XXX how to detect binary files?
            data = "File too big"
        else:
            # return the whole file
            data = unicode(fc.data(), errors='ignore') # XXX
            lexer = get_lexer(path, data)
            if lexer:
                lexer.setFont(self._font)
                self.textView.setLexer(lexer)
            self._cur_lexer = lexer
        nlines = data.count('\n')
        self.textView.setMarginWidth(1, str(nlines)+'00')
        self.textView.setText(data)

    def setCurrentFile(self, filename):
        index = QtCore.QModelIndex()
        path = filename.split(osp.sep)
        for p in path:
            self.treeView.expand(index)
            for row in range(self.treemodel.rowCount(index)):
                newindex = self.treemodel.index(row, 0, index)
                if newindex.internalPointer().data(0) == p:
                    index = newindex
                    break
        self.treeView.setCurrentIndex(index)
                
        
        
    
class FileDiffViewer(QtGui.QMainWindow, HgDialogMixin):
    """
    Qt4 dialog to display diffs between different mercurial revisions of a file.
    """
    _uifile = 'filediffviewer.ui'
    def __init__(self, repo, filename, noderev=None):
        self.repo = repo
        QtGui.QMainWindow.__init__(self)
        HgDialogMixin.__init__(self)
        
        self.createActions()
        # hg repo
        self.filename = filename
        self.findLexer()

        self.setupViews()

        # timer used to fill viewers with diff block markers during GUI idle time
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(False)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.idle_fill_files)
        self.setupModels()
        
    def reload(self):
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self.setupModels()        
        
    def setupModels(self):
        self.filedata = {'left': None, 'right': None}
        self._invbarchanged = False
        self.filerevmodel = FileRevModel(self.repo, self.filename)
        self.connect(self.filerevmodel, QtCore.SIGNAL('fillingover()'),
                     self.modelFilled)
        self.tableView_revisions_left.setModel(self.filerevmodel)
        self.tableView_revisions_right.setModel(self.filerevmodel)

    def findLexer(self):
        # try to find a lexer for our file.
        f = self.repo.file(self.filename)
        head = f.heads()[0]
        if f.size(f.rev(head)) < 1e6:
            data = f.read(head)
        else:
            data = '' # too big
        lexer = get_lexer(self.filename, data)
        if lexer:
            lexer.setDefaultFont(self._font)
            lexer.setFont(self._font)
        self.lexer = lexer
        
    def createActions(self):
        connect(self.actionClose, SIGNAL('triggered()'),
                self.close)
        connect(self.actionReload, SIGNAL('triggered()'),
                self.reload)
        self.actionClose.setIcon(geticon('quit'))
        self.actionReload.setIcon(geticon('reload'))

    def modelFilled(self):
        self.set_init_selections()

    def update_page_steps(self, keeppos=None):
        for side in sides:
            self.block[side].syncPageStep()
        self.diffblock.syncPageStep()
        if keeppos:
            side, pos = keeppos
            self.viewers[side].verticalScrollBar().setValue(pos)

    def idle_fill_files(self):
        # we make a burst of diff-lines computed at once, but we
        # disable GUI updates for efficiency reasons, then only
        # refresh GUI at the end of the burst
        for side in sides:
            self.viewers[side].setUpdatesEnabled(False)
            self.block[side].setUpdatesEnabled(False)
        self.diffblock.setUpdatesEnabled(False)

        for n in range(30): # burst pool
            if self._diff is None or not self._diff.get_opcodes():
                self._diff = None
                self.timer.stop()
                break

            tag, alo, ahi, blo, bhi = self._diff.get_opcodes().pop(0)

            w = self.viewers['left']
            cposl = w.SendScintilla(w.SCI_GETENDSTYLED)
            w = self.viewers['right']
            cposr = w.SendScintilla(w.SCI_GETENDSTYLED)
            if tag == 'replace':
                self.block['left'].addBlock('x', alo, ahi)
                self.block['right'].addBlock('x', blo, bhi)
                self.diffblock.addBlock('x', alo, ahi, blo, bhi)

                w = self.viewers['left']
                for i in range(alo, ahi):
                    w.markerAdd(i, self.markertriangle)

                w = self.viewers['right']
                for i in range(blo, bhi):
                    w.markerAdd(i, self.markertriangle)

            elif tag == 'delete':
                self.block['left'].addBlock('-', alo, ahi)
                self.diffblock.addBlock('-', alo, ahi, blo, bhi)

                w = self.viewers['left']
                for i in range(alo, ahi):
                    w.markerAdd(i, self.markerminus)

            elif tag == 'insert':
                self.block['right'].addBlock('+', blo, bhi)
                self.diffblock.addBlock('+', alo, ahi, blo, bhi)

                w = self.viewers['right']
                for i in range(blo, bhi):
                    w.markerAdd(i, self.markerplus)

            elif tag == 'equal':
                pass

            else:
                raise ValueError, 'unknown tag %r' % (tag,)

        # ok, let's enable GUI refresh for code viewers and diff-block displayers
        for side in sides:
            self.viewers[side].setUpdatesEnabled(True)
            self.block[side].setUpdatesEnabled(True)
        self.diffblock.setUpdatesEnabled(True)
        
    def update_diff(self, keeppos=None):
        """
        Recompute the diff, display files and starts the timer
        responsible for filling diff markers
        """
        if keeppos:
            pos = self.viewers[keeppos].verticalScrollBar().value()
            keeppos = (keeppos, pos)
            
        for side in sides:
            self.viewers[side].clear()
            self.block[side].clear()
        self.diffblock.clear()

        if None not in self.filedata.values():
            if self.timer.isActive():
                self.timer.stop()
            for side in sides:
                self.viewers[side].setMarginWidth(1, "00%s" % len(self.filedata[side]))

            self._diff = difflib.SequenceMatcher(None, self.filedata['left'],
                                                 self.filedata['right'])
            blocks = self._diff.get_opcodes()[:]

            self._diffmatch = {'left': [x[1:3] for x in blocks],
                               'right': [x[3:5] for x in blocks]}
            for side in sides:
                self.viewers[side].setText('\n'.join(self.filedata[side]))
            self.update_page_steps(keeppos)
            self.timer.start()

    def set_init_selections(self):
        self.tableView_revisions_left.setCurrentIndex(self.filerevmodel.index(1, 0))
        self.tableView_revisions_right.setCurrentIndex(self.filerevmodel.index(0, 0))


    def vbar_changed(self, value, side):
        """
        Callback called when the vertical scrollbar of a file viewer
        is changed, so we can update the position of the other file
        viewer.
        """
        if self._invbarchanged:
            # prevent loops in changes (left -> right -> left ...)
            return
        self._invbarchanged = True
        oside = otherside[side]

        for i, (lo, hi) in enumerate(self._diffmatch[side]):
            if lo <= value < hi:
                break
        dv = value - lo

        blo, bhi = self._diffmatch[oside][i]
        vbar = self.viewers[oside].verticalScrollBar()
        if (dv) < (bhi - blo):
            bvalue = blo + dv
        else:
            bvalue = bhi
        vbar.setValue(bvalue)
        self._invbarchanged = False

    def revisionSelected(self, rev):
        if self.sender() is self.tableView_revisions_right:
            side = 'right'
        else:
            side = 'left'
        path = self.filerevmodel.graph.nodesdict[rev].extra[0]
        fc = self.repo.changectx(rev).filectx(path)
        self.filedata[side] = fc.data().splitlines()
        self.update_diff(keeppos=otherside[side])

    def revisionActivated(self, rev):
        """
        Callback called when a revision is double-clicked in the revisions table        
        """
        dlg = ManifestViewer(self.repo, rev)
        dlg.setCurrentFile(self.filename)
        dlg.show()
        self._manifestdlg = dlg

    def setupViews(self):
        # viewers are Scintilla editors
        self.viewers = {}
        # block are diff-block displayers
        self.block = {}
        self.diffblock = BlockMatch(self.frame)
        lay = QtGui.QHBoxLayout(self.frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        for side, idx  in (('left', 0), ('right', 3)):
            sci = Qsci.QsciScintilla(self.frame)
            sci.setFont(self._font)
            sci.verticalScrollBar().setFocusPolicy(Qt.StrongFocus)
            sci.setFocusProxy(sci.verticalScrollBar())
            sci.verticalScrollBar().installEventFilter(self)
            sci.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            sci.setFrameShape(QtGui.QFrame.NoFrame)
            sci.setMarginLineNumbers(1, True)
            sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
            if self.lexer:
                sci.setLexer(self.lexer)

            sci.setReadOnly(True)
            lay.addWidget(sci)
            
            # hide margin 0 (markers)
            sci.SendScintilla(sci.SCI_SETMARGINTYPEN, 0, 0)
            sci.SendScintilla(sci.SCI_SETMARGINWIDTHN, 0, 0)
            # setup margin 1 for line numbers only
            sci.SendScintilla(sci.SCI_SETMARGINTYPEN, 1, 1)
            sci.SendScintilla(sci.SCI_SETMARGINWIDTHN, 1, 20)
            sci.SendScintilla(sci.SCI_SETMARGINMASKN, 1, 0)

            # define markers for colorize zones of diff
            self.markerplus = sci.markerDefine(Qsci.QsciScintilla.Background)
            sci.SendScintilla(sci.SCI_MARKERSETBACK, self.markerplus, 0xB0FFA0)
            self.markerminus = sci.markerDefine(Qsci.QsciScintilla.Background)
            sci.SendScintilla(sci.SCI_MARKERSETBACK, self.markerminus, 0xA0A0FF)
            self.markertriangle = sci.markerDefine(Qsci.QsciScintilla.Background)
            sci.SendScintilla(sci.SCI_MARKERSETBACK, self.markertriangle, 0xFFA0A0)
            
            self.viewers[side] = sci
            blk = BlockList(self.frame)
            blk.linkScrollBar(sci.verticalScrollBar())
            self.diffblock.linkScrollBar(sci.verticalScrollBar(), side)
            lay.insertWidget(idx, blk)
            self.block[side] = blk
        lay.insertWidget(2, self.diffblock)

        for side in sides:
            table = getattr(self, 'tableView_revisions_%s' % side)
            table.setTabKeyNavigation(False)
            #table.installEventFilter(self)        
            connect(table, SIGNAL('revisionSelected'), self.revisionSelected)
            connect(table, SIGNAL('revisionActivated'), self.revisionActivated)

            self.connect(self.viewers[side].verticalScrollBar(),
                         QtCore.SIGNAL('valueChanged(int)'),
                         lambda value, side=side: self.vbar_changed(value, side))
            self.attachQuickBar(table.goto_toolbar)

        self.setTabOrder(table, self.viewers['left'])
        self.setTabOrder(self.viewers['left'], self.viewers['right'])
        
if __name__ == '__main__':
    from mercurial import ui, hg
    from optparse import OptionParser
    opt = OptionParser()
    opt.add_option('-R', '--repo',
                   dest='repo',
                   default='.',
                   help='Hg repository')
    opt.add_option('-d', '--diff',
                   dest='diff',
                   default=False,
                   action='store_true',
                   help='Run in diff mode')
    opt.add_option('-r', '--rev',
                   dest='rev',
                   default=None,
                   help='Run in manifest navigation mode for the given rev')

    options, args = opt.parse_args()
    if len(args)!=1:
        filename = None
    else:
        filename = args[0]

    u = ui.ui()
    repo = hg.repository(u, options.repo)
    app = QtGui.QApplication([])

    if options.diff:
        view = FileDiffViewer(repo, filename)
    elif options.rev is not None:
        view = ManifestViewer(repo, int(options.rev))
    else:
        view = FileViewer(repo, filename)
    view.show()
    sys.exit(app.exec_())

