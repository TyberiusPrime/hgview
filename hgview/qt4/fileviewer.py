# -*- coding: utf-8 -*-
import sys, os
from os.path import dirname, join, expanduser, isfile
import difflib
import math
import numpy

from PyQt4 import QtGui, QtCore, uic, Qsci
from PyQt4.QtCore import Qt
from hgrepomodel import FileRevModel

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
        #self.frame.setContentsMargins(0,0,0,0)
        lay = QtGui.QHBoxLayout(self.frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        self.textBrowser_filecontent = Qsci.QsciScintilla(self.frame)
        self.textBrowser_filecontent.setFrameShape(QtGui.QFrame.NoFrame)
        self.textBrowser_filecontent.setMarginLineNumbers(1, True)
        self.textBrowser_filecontent.setLexer(Qsci.QsciLexerPython())
        self.textBrowser_filecontent.setReadOnly(True)
        self.markerplus = self.textBrowser_filecontent.markerDefine(Qsci.QsciScintilla.Plus)
        self.markerminus = self.textBrowser_filecontent.markerDefine(Qsci.QsciScintilla.Minus)
        lay.addWidget(self.textBrowser_filecontent)
        # hg repo
        self.repo = repo
        self.filename = filename
        self.filerevmodel = FileRevModel(self.repo, self.filename, noderev)
        self.tableView_revisions.setModel(self.filerevmodel)
        self.connect(self.tableView_revisions.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                     self.revision_selected)
        #self.textBrowser_filecontent.SendScintilla(self.textBrowser_filecontent.SCI_SETVSCROLLBAR, 0)
        
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
        
class FileDiffViewer(QtGui.QDialog):
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
        self.filedata = {'left': None, 'right': None}
        self._previous = None
        
        lex = Qsci.QsciLexerPython()
        lex.setDefaultFont(QtGui.QFont('Courier', 10))

        self.viewers = {}
        for side in ('left', 'right'):
            frame = getattr(self, 'frame_%s' % side)
            lay = QtGui.QHBoxLayout(frame)
            lay.setSpacing(0)
            lay.setContentsMargins(0,0,0,0)
            sci = Qsci.QsciScintilla(frame)
            sci.setFrameShape(QtGui.QFrame.NoFrame)
            sci.setMarginLineNumbers(1, True)
            sci.SendScintilla(sci.SCI_INDICSETSTYLE, 0, sci.INDIC_BOX)
            sci.SendScintilla(sci.SCI_INDICSETSTYLE, 1, sci.INDIC_BOX)
            sci.SendScintilla(sci.SCI_INDICSETFORE, 0, 0xff0000) # light blue
            sci.SendScintilla(sci.SCI_INDICSETFORE, 1, 0x0000ff) # light red
            sci.setLexer(lex)
            sci.setReadOnly(True)
            lay.addWidget(sci)
            self.markerplus = sci.markerDefine(Qsci.QsciScintilla.Plus)
            self.markerminus = sci.markerDefine(Qsci.QsciScintilla.Minus)
            self.viewers[side] = sci

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(False)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.idle_fill_files)        

        # hg repo
        self.repo = repo
        self.filename = filename
        self.filerevmodel = FileRevModel(self.repo, self.filename, noderev, columns=range(4))
        for side in ('left', 'right'):
            table = getattr(self, 'tableView_revisions_%s' % side)
            table.setModel(self.filerevmodel)
            table.verticalHeader().hide()
            self.connect(table.selectionModel(),
                         QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                         getattr(self, 'revision_selected_%s'%side))
                         #lambda index, index2, side=side: self.revision_selected(index, side))
            self.connect(self.viewers[side].verticalScrollBar(),
                         QtCore.SIGNAL('valueChanged(int)'),
                         lambda value, side=side: self.vbar_changed(value, side))
        QtCore.QTimer.singleShot(10, self.resize_columns)
        QtCore.QTimer.singleShot(1, self.set_init_selections)

    def idle_fill_files(self):
        match = self.compute_match(self._diff)
        if match is None:
            self._diff = None
            self.timer.stop()
            # hack
            self.resize_columns()
            return True

        left, right, lm, rm = match
        self.viewers['left'].append('\n'.join(left) + '\n')
        self.viewers['right'].append('\n'.join(right) + '\n')

        for side, r in [('left',lm), ('right', rm)]:
            ll = self.viewers[side].SendScintilla(self.viewers[side].SCI_GETLINECOUNT)
            sci = self.viewers[side]
            sci.SendScintilla(sci.SCI_SETINDICATORCURRENT, 0)
            for i, marks in enumerate(r):
               pos = sci.SendScintilla(sci.SCI_POSITIONFROMLINE,
                                       i + ll)
               for m in marks:
                   sys.stderr.write('- %s\n' % (pos+m))
                   sci.SendScintilla(sci.SCI_INDICATORFILLRANGE, pos+m, 1)
        
        return False

    def compute_match(self, diff):
        if self._previous is None:
            try:
                line = diff.next()
            except StopIteration:
                self._previous = None
                return None
        else:
            line = self._previous
        if line[0] == ' ':
            lines = [line]
            # a block of unchanged values
            for line in diff:
                if line[0] == ' ':
                    lines.append(line)
                else:
                    self._previous = line
                    break
            else:
                self._previous = None
            lines = [line[2:] for line in lines]
            return lines, lines, [], []
        else:
            # a block of different values
            left = []
            lmarks = []
            right = []
            rmarks = []
            if line[0] == '+':
                right.append(line[2:])
            else:
                left.append(line[2:])
            prev = line[0]
            
            for line in diff:
                if line[0] == ' ':
                    self._previous = line
                    break
                else:
                    if line[0] == '+':
                        right.append(line[2:])
                        rmarks.append([])
                        marks = rmarks[-1]
                    elif line[0] == '-':
                        left.append(line[2:])
                        lmarks.append([])
                        marks = lmarks[-1]
                    elif line[0] == '?':
                        for i, c in enumerate(line[2:]):
                            if c != ' ':
                                marks.append(i)
            else:
                self._previous = None
            return left, right, lmarks, rmarks
        
    def set_init_selections(self):
        QtGui.QApplication.processEvents()
        self.tableView_revisions_left.setCurrentIndex(self.filerevmodel.index(0,0))
        self.tableView_revisions_right.setCurrentIndex(self.filerevmodel.index(1,0))
        
    def resize_columns(self):
        QtGui.QApplication.processEvents()
        ncols = self.filerevmodel.columnCount()
        cols = [x for x in range(ncols) if x != 1]
        for c in cols:
            self.tableView_revisions_left.resizeColumnToContents(c)    
            self.tableView_revisions_right.resizeColumnToContents(c)

        vp_width = self.tableView_revisions_left.viewport().width()
        colsum = sum([self.tableView_revisions_left.columnWidth(i) for i in cols])
        self.tableView_revisions_left.setColumnWidth(1, vp_width-colsum)

        vp_width = self.tableView_revisions_right.viewport().width()
        colsum = sum([self.tableView_revisions_right.columnWidth(i) for i in cols])
        self.tableView_revisions_right.setColumnWidth(1, vp_width-colsum)
        
    def vbar_changed(self, value, side):
        vbar = self.viewer[side].verticalScrollBar()
        vbar.setValue(value)

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
        
    def update_diff(self):
        for side in ['left', 'right']:
            self.viewers[side].clear()
        if None not in self.filedata.values():
            if self.timer.isActive():
                self.timer.stop()
            for side in ['left', 'right']:
                self.viewers[side].setMarginWidth(1, "00%s"%len(self.filedata[side]))
                
            self._diff = difflib.Differ().compare(self.filedata['left'], self.filedata['right'])
            self.timer.start()
        
    
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
    
