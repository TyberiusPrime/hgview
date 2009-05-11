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
"""Qt4 widgets to display hg revisions of a file
"""

import sys, os
import os.path as osp

import difflib
import math
import numpy

from mercurial.node import hex, short as short_hex
from mercurial.revlog import LookupError

from PyQt4 import QtGui, QtCore, uic, Qsci
from PyQt4.QtCore import Qt
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

from hgqvlib.config import HgConfig
from hgqvlib.qt4 import HgDialogMixin
from hgqvlib.qt4.hgrepomodel import FileRevModel, ManifestModel
from hgqvlib.qt4.blockmatcher import BlockList, BlockMatch
from hgqvlib.qt4.lexers import get_lexer

sides = ('left', 'right')
otherside = {'left': 'right', 'right': 'left'}


class FileViewer(QtGui.QDialog, HgDialogMixin):
    _uifile = 'fileviewer.ui'
    def __init__(self, repo, filename, noderev=None):
        self.repo = repo
        QtGui.QDialog.__init__(self)
        HgDialogMixin.__init__(self)

        # hg repo
        self.filename = filename

        lay = QtGui.QHBoxLayout(self.frame)
        lay.setSpacing(0)

        lay.setContentsMargins(0, 0, 0, 0)
        sci = Qsci.QsciScintilla(self.frame)
        sci.setFrameShape(QtGui.QFrame.NoFrame)
        sci.setMarginLineNumbers(1, True)
        sci.setFont(self.font)
        sci.setReadOnly(True)
        sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
        self.textBrowser_filecontent = sci
        self.markerplus = self.textBrowser_filecontent.markerDefine(Qsci.QsciScintilla.Plus)
        self.markerminus = self.textBrowser_filecontent.markerDefine(Qsci.QsciScintilla.Minus)
        lay.addWidget(self.textBrowser_filecontent)

        self.filerevmodel = FileRevModel(self.repo, self.filename, noderev)
        self.tableView_revisions.setModel(self.filerevmodel)
        self.connect(self.tableView_revisions,
                     SIGNAL('revisionSelected'),
                     self.revisionSelected)

    def revisionSelected(self, rev):
        filectx = self.repo.filectx(self.filename, changeid=rev)
        data = filectx.data()

        lexer = get_lexer(self.filename, data)
        if lexer:
            lexer.setDefaultFont(self.font)
            lexer.setFont(self.font)
            self.textBrowser_filecontent.setLexer(lexer)
        self.lexer = lexer

        nlines = data.count('\n')
        self.textBrowser_filecontent.setMarginWidth(1, str(nlines)+'00')
        self.textBrowser_filecontent.setText(data)

        #self.textBrowser_filecontent.markerDeleteAll()
        #self.textBrowser_filecontent.markerAdd(1, self.markerplus)
        #self.textBrowser_filecontent.markerAdd(2, self.markerminus)


        
class ManifestViewer(QtGui.QDialog, HgDialogMixin):
    """
    Qt4 dialog to display all files of a repo at a given revision
    """
    _uifile = 'manifestviewer.ui'
    def __init__(self, repo, noderev):
        self.repo = repo
        QtGui.QDialog.__init__(self)
        HgDialogMixin.__init__(self)
        self.actionClose.setShortcuts([self.actionClose.shortcut(), Qt.Key_Escape])
        self.connect(self.actionClose, QtCore.SIGNAL('triggered(bool)'),
                     self.close)
        # hg repo
        self.rev = noderev
        self.treemodel = ManifestModel(self.repo, self.rev)
        self.treeView.setModel(self.treemodel)
        self.connect(self.treeView.selectionModel(),
                     QtCore.SIGNAL('currentChanged(const QModelIndex &, const QModelIndex &)'),
                     self.file_selected)
        self.setup_textview()
        self.setWindowTitle('Hg manifest viewer - %s:%s' % (repo.root, self.rev))

    def setup_textview(self):
        lay = QtGui.QHBoxLayout(self.mainFrame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        sci = Qsci.QsciScintilla(self.mainFrame)
        lay.addWidget(sci)
        sci.setMarginLineNumbers(1, True)
        sci.setMarginWidth(1, '000')
        sci.setReadOnly(True)
        sci.setFont(self.font)

        sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
        self.textView = sci
        
    def file_selected(self, index, *args):
        if not index.isValid():
            return
        path = self.treemodel.pathForIndex(index)
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
                lexer.setFont(self.font)
                self.textView.setLexer(lexer)
            self._cur_lexer = lexer
        nlines = data.count('\n')
        self.textView.setMarginWidth(1, str(nlines)+'00')
        self.textView.setText(data)
        
    
class FileDiffViewer(QtGui.QDialog, HgDialogMixin):
    """
    Qt4 dialog to display diffs between different mercurial revisions of a file.
    """
    _uifile = 'filediffviewer.ui'
    def __init__(self, repo, filename, noderev=None):
        self.repo = repo
        QtGui.QDialog.__init__(self)
        HgDialogMixin.__init__(self)
        
        self.connect(self.actionClose, QtCore.SIGNAL('triggered(bool)'),
                     self.close)
        # hg repo
        self.filename = filename

        self.filedata = {'left': None, 'right': None}
        self._previous = None
        self._invbarchanged = False

        # try to find a lexer for our file.
        f = self.repo.file(self.filename)
        head = f.heads()[0]
        if f.size(f.rev(head)) < 1e6:
            data = f.read(head)
        else:
            data = '' # too big
        lexer = get_lexer(self.filename, data)
        if lexer:
            lexer.setDefaultFont(self.font)
            lexer.setFont(self.font)
        self.lexer = lexer
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
            sci.setFont(self.font)
            sci.verticalScrollBar().setFocusPolicy(Qt.StrongFocus)
            sci.setFocusProxy(sci.verticalScrollBar())
            sci.verticalScrollBar().installEventFilter(self)
            sci.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            sci.setFrameShape(QtGui.QFrame.NoFrame)
            sci.setMarginLineNumbers(1, True)
            sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
            if lexer:
                sci.setLexer(lexer)

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

        # timer used to fill viewers with diff block markers during GUI idle time
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(False)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.idle_fill_files)

        self.filerevmodel = FileRevModel(self.repo, self.filename, noderev)
        self.connect(self.filerevmodel, QtCore.SIGNAL('fillingover()'),
                     self.modelFilled)
        for side in sides:
            table = getattr(self, 'tableView_revisions_%s' % side)
            table.verticalHeader().setDefaultSectionSize(self.rowheight)
            table.setTabKeyNavigation(False)
            table.setModel(self.filerevmodel)
            table.verticalHeader().hide()
            self.connect(table.selectionModel(),
                         QtCore.SIGNAL('currentRowChanged(const QModelIndex &, const QModelIndex &)'),
                         getattr(self, 'revision_selected_%s' % side))
            self.connect(self.viewers[side].verticalScrollBar(),
                         QtCore.SIGNAL('valueChanged(int)'),
                         lambda value, side=side: self.vbar_changed(value, side))
        self.setTabOrder(table, self.viewers['left'])
        self.setTabOrder(self.viewers['left'], self.viewers['right'])

    def modelFilled(self):
        self.set_init_selections()
        self.setup_columns_size()

    def eventFilter(self, watched, event):
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.actionClose.trigger()
                return True
        return QtGui.QDialog.eventFilter(self, watched, event)

    def update_page_steps(self):
        for side in sides:
            self.block[side].syncPageStep()
        self.diffblock.syncPageStep()

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
        # force diff-block displayers to recompute their pageStep
        # according the document size (since this cannot be done using
        # signal/slot, since there is no 'pageStepChanged(int)' signal
        # for scroll bars...
        QtCore.QTimer.singleShot(0, self.update_page_steps)

    def update_diff(self):
        """
        Recompute the diff, display files and starts the timer
        responsible for filling diff markers
        """
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
            self.timer.start()

    def set_init_selections(self):
        self.tableView_revisions_left.setCurrentIndex(self.filerevmodel.index(1, 0))
        self.tableView_revisions_right.setCurrentIndex(self.filerevmodel.index(0, 0))

    def setup_columns_size(self):
        """
        Recompute column sizes for rev list ListViews, using
        autoresize for all columns but the 'description' one, and
        making this latter takes the remaining space.
        """
        ncols = self.filerevmodel.columnCount()
        cols = [x for x in range(ncols) if x != 1]
        hleft = self.tableView_revisions_left.horizontalHeader()
        hright = self.tableView_revisions_right.horizontalHeader()
        for c in cols:
            hleft.setResizeMode(c, hleft.ResizeToContents)
            hright.setResizeMode(c, hleft.ResizeToContents)
        hleft.setResizeMode(1, hleft.Stretch)
        hright.setResizeMode(1, hleft.Stretch)

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

    def revision_selected_left(self, index, oldindex):
        self.revision_selected(index, 'left')
    def revision_selected_right(self, index, oldindex):
        self.revision_selected(index, 'right')

    def revision_selected(self, index, side):
        row = index.row()
        rev = self.filerevmodel.graph[row].rev
        # XXX not very nice (probably not robust over hg evolution)
        for i, idx in enumerate(self.filerevmodel.filelog.index):
            if idx[4] == rev:
                break
        else:
            return
        node = self.filerevmodel.filelog.node(i)
        self.filedata[side] = self.filerevmodel.filelog.read(node).splitlines()
        self.update_diff()



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

