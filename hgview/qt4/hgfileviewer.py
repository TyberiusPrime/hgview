# -*- coding: utf-8 -*-
import sys, os
from os.path import dirname, join, expanduser, isfile
import difflib
import math
import numpy

from PyQt4 import QtGui, QtCore, uic, Qsci
from PyQt4.QtCore import Qt
from hgrepomodel import FileRevModel
from blockmatcher import BlockList, BlockMatch
from hgview.config import HgConfig
from hgview.qt4.lexers import get_lexer

sides = ('left', 'right')
otherside = {'left':'right', 'right':'left'}


class Differ(difflib.Differ):
    def _dump(self, tag, x, lo, hi):
        """Generate comparison results for a same-tagged range."""
        for i in xrange(lo, hi):
            yield (tag, x[i])

    def _qformat(self, aline, bline, atags, btags):
        common = min(_count_leading(aline, "\t"),
                     _count_leading(bline, "\t"))
        common = min(common, _count_leading(atags[:common], " "))
        atags = atags[common:].rstrip()
        btags = btags[common:].rstrip()

        yield "- " + aline
        if atags:
            yield "? %s%s\n" % ("\t" * common, atags)

        yield "+ " + bline
        if btags:
            yield "? %s%s\n" % ("\t" * common, btags)
        
class FileViewer(QtGui.QDialog):
    def __init__(self, repo, filename, noderev=None):
        QtGui.QDialog.__init__(self)
        for _path in [dirname(__file__),
                      join(sys.exec_prefix, 'share/hgview'),
                      expanduser('~/share/hgview'),
                      join(dirname(__file__), "../../../../../share/hgview"),
                      ]:
            ui_file = join(_path, 'fileviewer.ui')
            
            if isfile(ui_file):
                break
        else:
            raise ValueError("Unable to find fileviewer.ui\n"
                             "Check your installation.")

        # load qt designer ui file
        #uifile = join(ui_file)
        self.ui = uic.loadUi(ui_file, self)
        # hg repo
        self.repo = repo
        self.filename = filename
        self.loadConfig()
        
        lay = QtGui.QHBoxLayout(self.frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
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
            self.textBrowser_filecontent.setLexer(lexer)

        self.tableView_revisions.verticalHeader().setDefaultSectionSize(self.rowheight)
        self.filerevmodel = FileRevModel(self.repo, self.filename, noderev)
        self.tableView_revisions.setModel(self.filerevmodel)
        self.connect(self.tableView_revisions.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                     self.revision_selected)
        
    def revision_selected(self, index, oldindex):
        row = index.row() 
        filectx = self.repo.filectx(self.filename, fileid=self.filerevmodel.filelog.node(row))
        ctx = filectx.changectx()
        data = self.filerevmodel.filelog.revision(self.filerevmodel.filelog.node(row))
        nlines = data.count('\n')
        self.textBrowser_filecontent.setMarginWidth(1, str(nlines)+'00')
        self.textBrowser_filecontent.setText(data)
        
        self.textBrowser_filecontent.markerDeleteAll()
        self.textBrowser_filecontent.markerAdd(1, self.markerplus)
        self.textBrowser_filecontent.markerAdd(2, self.markerminus)

    def loadConfig(self):
        cfg = HgConfig(self.repo.ui)
        fontstr = cfg.getFont()
        font = QtGui.QFont()
        try:
            if not font.fromString(fontstr):
                raise Exception
        except:
            print "bad font name '%s'"%fontstr
            font.setFamily("Monospace")
            font.setFixedPitch(True)
            font.setPointSize(10)
        self.font = font

        self.rowheight = cfg.getRowHeight()
        self.users, self.aliases = cfg.getUsers()
        
class FileDiffViewer(QtGui.QDialog):
    """
    Qt4 dialog to display diffs between different mercurial revisions of a file.  
    """
    def __init__(self, repo, filename, noderev=None):
        QtGui.QDialog.__init__(self)
        for _path in [dirname(__file__),
                      join(sys.exec_prefix, 'share/hgview'),
                      expanduser('~/share/hgview'),
                      join(dirname(__file__), "../../../../../share/hgview"),
                      ]:
            ui_file = join(_path, 'filediffviewer.ui')
            
            if isfile(ui_file):
                break
        else:
            raise ValueError("Unable to find fileviewer.ui\n"
                             "Check your installation.")

        # load qt designer ui file
        self.ui = uic.loadUi(ui_file, self)
        self.connect(self.actionClose, QtCore.SIGNAL('triggered(bool)'),
                     self.close)
        # hg repo
        self.repo = repo
        self.filename = filename
        self.loadConfig()
        
        self.filedata = {'left': None, 'right': None}
        self._previous = None
        self._invbarchanged=False

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

        # viewers are Scintilla editors
        self.viewers = {}
        # block are diff-block displayers
        self.block = {}
        self.diffblock = BlockMatch(self.frame)
        lay = QtGui.QHBoxLayout(self.frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
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

##             sci.SendScintilla(sci.SCI_INDICSETSTYLE, 8, sci.INDIC_ROUNDBOX)
##             sci.SendScintilla(sci.SCI_INDICSETSTYLE, 9, sci.INDIC_ROUNDBOX)
##             sci.SendScintilla(sci.SCI_INDICSETSTYLE, 10, sci.INDIC_ROUNDBOX)
##             sci.SendScintilla(sci.SCI_INDICSETUNDER, 8, True)
##             sci.SendScintilla(sci.SCI_INDICSETUNDER, 9, True)
##             sci.SendScintilla(sci.SCI_INDICSETUNDER, 10, True)
##             sci.SendScintilla(sci.SCI_INDICSETFORE, 8, 0xB0FFA0) # light green (+)
##             sci.SendScintilla(sci.SCI_INDICSETFORE, 9, 0xA0A0FF) # light red (-)
##             sci.SendScintilla(sci.SCI_INDICSETFORE, 10, 0xFFA0A0) # light blue (x)

            #sci.setLexer(lexer)
            #print "required for lexer", sci.SendScintilla(sci.SCI_GETSTYLEBITSNEEDED)
            #sci.SendScintilla(sci.SCI_SETSTYLEBITS, 7)
            sci.SendScintilla(sci.SCI_STYLESETEOLFILLED, 0x10, True)
            sci.SendScintilla(sci.SCI_STYLESETBACK, 0x10, 0xB0FFA0)
            sci.SendScintilla(sci.SCI_STYLESETEOLFILLED, 0x08, True)
            sci.SendScintilla(sci.SCI_STYLESETBACK, 0x08, 0xA0A0FF)
            sci.SendScintilla(sci.SCI_STYLESETEOLFILLED, 0x04, True)
            sci.SendScintilla(sci.SCI_STYLESETBACK, 0x04, 0xFFA0A0)

            sci.setReadOnly(True)
            lay.addWidget(sci)
            self.markerplus = sci.markerDefine(Qsci.QsciScintilla.Plus)
            self.markerminus = sci.markerDefine(Qsci.QsciScintilla.Minus)
            self.markertriangle = sci.markerDefine(Qsci.QsciScintilla.RightTriangle)
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
        for side in sides:
            table = getattr(self, 'tableView_revisions_%s' % side)
            table.verticalHeader().setDefaultSectionSize(self.rowheight)
            table.setTabKeyNavigation(False)
            table.setModel(self.filerevmodel)
            table.verticalHeader().hide()
            self.connect(table.selectionModel(),
                         QtCore.SIGNAL('currentRowChanged(const QModelIndex &, const QModelIndex &)'),
                         getattr(self, 'revision_selected_%s'%side))
                         #lambda idx, oldidx, side=side: self.revision_selected(idx, side))
            self.connect(self.viewers[side].verticalScrollBar(),
                         QtCore.SIGNAL('valueChanged(int)'),
                         lambda value, side=side: self.vbar_changed(value, side))
        self.setTabOrder(table, self.viewers['left']) 
        self.setTabOrder(self.viewers['left'], self.viewers['right']) 
        self.setup_columns_size()
        self.set_init_selections()

    def eventFilter(self, watched, event):
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.actionClose.trigger()
                return True
        return QtGui.QDialog.eventFilter(self, watched, event)
        
    def loadConfig(self):
        cfg = HgConfig(self.repo.ui)
        fontstr = cfg.getFont()
        font = QtGui.QFont()
        try:
            if not font.fromString(fontstr):
                raise Exception
        except:
            print "bad font name '%s'"%fontstr
            font.setFamily("Monospace")
            font.setFixedPitch(True)
            font.setPointSize(10)
        self.font = font

        self.rowheight = cfg.getRowHeight()
        self.users, self.aliases = cfg.getUsers()
        
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
                pos0 = w.SendScintilla(w.SCI_POSITIONFROMLINE, alo)
                pos1 = w.SendScintilla(w.SCI_POSITIONFROMLINE, ahi)
                #w.SendScintilla(w.SCI_SETINDICATORCURRENT, 10)
                #w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos0, pos1-pos0)
                w.SendScintilla(w.SCI_STARTSTYLING, pos0, 0x04)
                w.SendScintilla(w.SCI_SETSTYLING, pos1-pos0, 0x04)

                w = self.viewers['right']
                for i in range(blo, bhi):
                    w.markerAdd(i, self.markertriangle)
                pos0 = w.SendScintilla(w.SCI_POSITIONFROMLINE, blo)
                pos1 = w.SendScintilla(w.SCI_POSITIONFROMLINE, bhi)
                #w.SendScintilla(w.SCI_SETINDICATORCURRENT, 10)
                #w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos0, pos1-pos0)
                w.SendScintilla(w.SCI_STARTSTYLING, pos0, 0x04)
                w.SendScintilla(w.SCI_SETSTYLING, pos1-pos0, 0x04)

            elif tag == 'delete':
                self.block['left'].addBlock('-', alo, ahi)
                self.diffblock.addBlock('-', alo, ahi, blo, bhi)

                w = self.viewers['left']
                for i in range(alo, ahi):            
                    w.markerAdd(i, self.markerminus)
                pos0 = w.SendScintilla(w.SCI_POSITIONFROMLINE, alo)
                pos1 = w.SendScintilla(w.SCI_POSITIONFROMLINE, ahi)
                #w.SendScintilla(w.SCI_SETINDICATORCURRENT, 9)
                #w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos0, pos1-pos0)
                w.SendScintilla(w.SCI_STARTSTYLING, pos0, 0x08)
                w.SendScintilla(w.SCI_SETSTYLING, pos1-pos0, 0x08)

            elif tag == 'insert':
                self.block['right'].addBlock('+', blo, bhi)
                self.diffblock.addBlock('+', alo, ahi, blo, bhi)

                w = self.viewers['right']
                for i in range(blo, bhi):
                    w.markerAdd(i, self.markerplus)
                pos0 = w.SendScintilla(w.SCI_POSITIONFROMLINE, blo)
                pos1 = w.SendScintilla(w.SCI_POSITIONFROMLINE, bhi)
                #w.SendScintilla(w.SCI_SETINDICATORCURRENT, 8)
                #w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos0, pos1-pos0)
                w.SendScintilla(w.SCI_STARTSTYLING, pos0, 0x10)
                w.SendScintilla(w.SCI_SETSTYLING, pos1-pos0, 0x10)
                

            elif tag == 'equal':
                pass

            else:
                raise ValueError, 'unknown tag %r' % (tag,)
            #self.viewers['left'].SendScintilla(w.SCI_STARTSTYLING, cposl, 0x1F)
            #self.viewers['right'].SendScintilla(w.SCI_STARTSTYLING, cposr, 0x1F)
            
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
                self.viewers[side].setMarginWidth(1, "00%s"%len(self.filedata[side]))
                
            self._diff = difflib.SequenceMatcher(None, self.filedata['left'], self.filedata['right'])
            blocks = self._diff.get_opcodes()[:]
            
            self._diffmatch = {'left': [x[1:3] for x in blocks],
                               'right': [x[3:5] for x in blocks]}
            for side in sides:
                self.viewers[side].setText('\n'.join(self.filedata[side]))
            self.timer.start()
        
    def set_init_selections(self):
        self.tableView_revisions_left.setCurrentIndex(self.filerevmodel.index(0,0))
        self.tableView_revisions_right.setCurrentIndex(self.filerevmodel.index(1,0))
        
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
        self._invbarchanged=True
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
        self._invbarchanged=False

    def revision_selected_left(self, index, oldindex):
        self.revision_selected(index, 'left')
    def revision_selected_right(self, index, oldindex):
        self.revision_selected(index, 'right')

    def revision_selected(self, index, side):
        row = index.row() 
        filectx = self.repo.filectx(self.filename, fileid=self.filerevmodel.filelog.node(row))
        ctx = filectx.changectx()
        self.filedata[side] = self.filerevmodel.filelog.read(self.filerevmodel.filelog.node(row)).splitlines()
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
    options, args = opt.parse_args()
    if len(args)!=1:
        opt.print_help()
        sys.exit(1)
    filename = args[0]
        
    u = ui.ui()    
    repo = hg.repository(u, options.repo)
    app = QtGui.QApplication([])

    if options.diff:
        dview = FileDiffViewer(repo, filename)
        dview.show()
    else:
        view = FileViewer(repo, filename)
        view.show()
    sys.exit(app.exec_())
    
