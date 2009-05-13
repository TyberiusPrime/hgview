# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# main.py - qt4-based hg rev log browser
#
# Copyright (C) 2007-2009 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Main Qt4 application for hgqv
"""
import sys, os
import time
import re

from PyQt4 import QtCore, QtGui, Qsci

from mercurial import ui, hg, patch
from mercurial.node import hex, short as short_hex, bin as short_bin

from hgqvlib.qt4.hgrepomodel import HgRepoListModel, HgFileListModel
from hgqvlib.qt4.hgfileviewer import FileViewer, FileDiffViewer, ManifestViewer
from hgqvlib.hggraph import diff as revdiff
from hgqvlib.decorators import timeit
from hgqvlib.config import HgConfig
from hgqvlib.qt4.lexers import get_lexer
from hgqvlib.qt4 import HgDialogMixin
from hgqvlib.qt4 import hgrepoview

# dirty hack to please PyQt4 uic
sys.modules['hgrepoview'] = hgrepoview

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
normal = QtGui.QFont.Normal
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL

class HgRepoViewer(QtGui.QMainWindow, HgDialogMixin):
    _uifile = 'hgqv.ui'
    """hg repository viewer/browser application"""
    def __init__(self, repo, filerex = None):
        self.repo = repo
        QtGui.QMainWindow.__init__(self)
        HgDialogMixin.__init__(self)

        self.setWindowTitle('hgqv: %s' % os.path.abspath(self.repo.root))

        self.setup_statusbar()
        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)
        connect(self.splitter_2, SIGNAL('splitterMoved (int, int)'),
                self.resize_filelist_columns)

        self.setup_main_actions()
        # text viewer
        self.setup_diffview()
        # filter frame
        self.setup_filterframe()

        # required due to a probable bug in uic module
        self._icons = {}
        self._icons['closebtn'] = QtGui.QIcon(':/icons/close.png')
        self._icons['back'] = QtGui.QIcon(':/icons/back.svg')
        self._icons['forward'] = QtGui.QIcon(':/icons/forward.svg')
        self.setup_frame_find()
        self.setup_navigation_buttons()

        self.init_variables()        
        # setup tables and views
        self.setup_header_textview()

        self.setup_branch_combo()
        self.setup_models()

        self.setup_revision_table()
        self.setup_filelist_table()

        self.refresh_revision_table()

    def init_variables(self):
        self._find_text = None
        
    def setup_branch_combo(self):
        branches = sorted(self.repo.branchtags().keys())
        if len(branches) == 1:
            self.branch_comboBox.setEnabled(False)
        else:
            self.branchesmodel = QtGui.QStringListModel([''] + branches)
            self.branch_comboBox.setModel(self.branchesmodel)

    def setup_navigation_buttons(self):
        for act in ('back', 'forward'):
            action = self.tableView_revisions._actions[act]
            action.setIcon(self._icons[act])
            self.toolBar_edit.addAction(action)
            self.menu_Edit.addAction(action)
            
    def setup_frame_find(self):
        self.frame_find.hide()
        # XXX don't know why I have to do this, the icon is affected
        # in designer, but it does not work here...
        self.close_find_toolButton.setIcon(self._icons['closebtn'])
        self.actionFind.setShortcuts([self.actionFind.shortcut(), "/"])
        self.actionFindNext.setShortcuts([self.actionFindNext.shortcut(), "Ctrl+N"])

        connect(self.actionFindNext, SIGNAL('triggered()'),
                self.on_find)
        connect(self.button_find, SIGNAL('clicked(bool)'),
                self.on_find)
        connect(self.button_cancelsearch, SIGNAL('clicked(bool)'),
                self.on_cancelsearch)
        connect(self.close_find_toolButton, SIGNAL('clicked(bool)'),
                lambda: self.actionFind.setChecked(False))
        connect(self.entry_find, SIGNAL('returnPressed()'),
                self.on_find)
        connect(self.entry_find, SIGNAL('textChanged(const QString &)'),
                self.on_find_text_changed)

        self._frame_find_timer = QtCore.QTimer(self)
        self._frame_find_timer.setInterval(self.hidefinddelay)
        connect(self._frame_find_timer, SIGNAL('timeout()'),
                lambda: self.actionFind.setChecked(False))
        connect(self.actionFind, SIGNAL('toggled(bool)'),
                self.on_find_toggled)
        self.actionFind.setChecked(False)

    def setup_main_actions(self):
        # main window actions
        connect(self.actionRefresh, SIGNAL('triggered()'),
                self.reload_repository)
        connect(self.actionAbout, SIGNAL('triggered()'),
                self.on_about)
        connect(self.actionQuit, SIGNAL('triggered()'),
                self.close)
        # we explicitely create a QShortcut so we can disable it
        # when a "helper context toolbar" is activated (which can be
        # closed hitting the Esc shortcut)
        self.esc_shortcut = QtGui.QShortcut(self)
        self.esc_shortcut.setKey(Qt.Key_Escape)
        connect(self.esc_shortcut, SIGNAL('activated()'),
                self.close)
        
    def setup_statusbar(self):
        # setup the status bar, with a progress bar in it
        self.pb = QtGui.QProgressBar(self.statusBar())
        self.pb.setTextVisible(False)
        self.pb.hide()
        self.statusBar().addPermanentWidget(self.pb)

    def setup_diffview(self):
        lay = QtGui.QHBoxLayout(self.textview_frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        sci = Qsci.QsciScintilla(self.textview_frame)
        lay.addWidget(sci)
        sci.setMarginLineNumbers(1, True)
        sci.setMarginWidth(1, '000')
        sci.setReadOnly(True)
        sci.setFont(self.font)

        sci.SendScintilla(sci.SCI_INDICSETSTYLE, 8, sci.INDIC_ROUNDBOX)
        sci.SendScintilla(sci.SCI_INDICSETUNDER, 8, True)
        sci.SendScintilla(sci.SCI_INDICSETFORE, 8, 0xBBFFFF)
        sci.SendScintilla(sci.SCI_INDICSETSTYLE, 9, sci.INDIC_PLAIN)
        sci.SendScintilla(sci.SCI_INDICSETUNDER, 9, False)
        sci.SendScintilla(sci.SCI_INDICSETFORE, 9, 0x0000FF)

        sci.SendScintilla(sci.SCI_SETSELEOLFILLED, True)
        self.textview_status = sci

    def load_config(self):
        cfg = HgDialogMixin.load_config(self)
        self.hidefinddelay = cfg.getHideFindDelay()

    def setup_filterframe(self):
        connect(self.branch_comboBox, SIGNAL('activated(const QString &)'),
                self.refresh_revision_table)
        self.frame_branch_action = self.toolBar_treefilters.addWidget(self.frame_branch)
        self.frame_revrange_action = self.toolBar_treefilters.addWidget(self.frame_revrange)
        self.frame_filter_action = self.toolBar_treefilters.addWidget(self.frame_filter)

        self.frame_revrange_action.setVisible(False)
        self.frame_filter_action.setVisible(False)

    def create_models(self):
        self.repomodel = HgRepoListModel(self.repo)
        connect(self.repomodel, SIGNAL('filling(int)'),
                self.start_filling)
        connect(self.repomodel, SIGNAL('filled(int)'),
                self.on_filled)
        connect(self.repomodel, SIGNAL('fillingover()'),
                self.pb.hide)

        self.filelistmodel = HgFileListModel(self.repo)

    def setup_models(self):
        self.create_models()
        self.tableView_revisions.setModel(self.repomodel)
        self.tableView_filelist.setModel(self.filelistmodel)

        filetable = self.tableView_filelist
        connect(filetable.selectionModel(),
                SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                self.file_selected)
        connect(filetable,
                SIGNAL('doubleClicked (const QModelIndex &)'),
                self.file_activated)
        connect(filetable.horizontalHeader(),
                SIGNAL('sectionResized(int, int, int)'),
                self.file_section_resized)        

    def setup_revision_table(self):
        view = self.tableView_revisions
        view.installEventFilter(self)        
        connect(view, SIGNAL('revisionSelected'), self.revision_selected)
        connect(view, SIGNAL('revisionActivated'), self.revision_activated)
        connect(self.textview_header, SIGNAL('revisionSelected'), view.goto)
        connect(view, SIGNAL('escShortcutDisabled(bool)'),
                self.esc_shortcut.setEnabled)
        view.goto_toolbar.setParent(self)
        self.addToolBar(Qt.BottomToolBarArea, view.goto_toolbar)
        
    def setup_filelist_table(self):
        filetable = self.tableView_filelist
        filetable.setFocusPolicy(QtCore.Qt.NoFocus)

        self._setup_table(filetable)

    def _setup_table(self, table):
        table.setTabKeyNavigation(False)
        table.verticalHeader().setDefaultSectionSize(self.rowheight)
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)

    def setup_header_textview(self):
        self.header_diff_format = QtGui.QTextCharFormat()
        self.header_diff_format.setFont(self.font)
        self.header_diff_format.setFontWeight(bold)
        self.header_diff_format.setForeground(Qt.black)
        self.header_diff_format.setBackground(Qt.gray)

    # Qt methods
    def closeEvent(self, event):
        if not self.frame_find.isHidden():
            self.on_cancelsearch()
            self.actionFind.setChecked(False)
            event.ignore()
        else:
            event.accept()

    def resizeEvent(self, event):
        # we catch this event to resize smartly tables' columns
        QtGui.QMainWindow.resizeEvent(self, event)
        self.resize_filelist_columns()

    def eventFilter(self, watched, event):
        if watched == self.tableView_revisions:
            if event.type() == event.KeyPress:
                model = self.filelistmodel
                table = self.tableView_filelist
                row = table.currentIndex().row()
                if event.key() == Qt.Key_Left:
                    table.setCurrentIndex(model.index(max(row-1, 0), 0))
                    return True
                elif event.key() == Qt.Key_Right:
                    table.setCurrentIndex(model.index(min(row+1, model.rowCount()-1), 0))
                    return True
                elif event.key() in [Qt.Key_Return, Qt.Key_Enter]:
                    self.file_activated(table.currentIndex())
                    return True
        return QtGui.QMainWindow.eventFilter(self, watched, event)

    def start_filling(self, nmax):
        self.pb.setValue(0)
        self.pb.setRange(0, nmax)
        self.pb.show()

    def on_filled(self, nfilled):
        # callback called each time the revisions model filling has progressed
        selectfirst = self.pb.value() == 0
        self.pb.setValue(nfilled)
        if selectfirst:
            # if this is the first time the model is filled, we select
            # the first available revision
            tv = self.tableView_revisions
            tv.setCurrentIndex(tv.model().index(0, 0))

    def revision_activated(self, rev):
        """
        Callback called when a revision is double-clicked in the revisions table        
        """
        ManifestViewer(self.repo, rev).show()
    
    def revision_selected(self, rev):
        """
        Callback called when a revision is selected in the revisions table
        """
        if self.repomodel.graph:
            ctx = self.repomodel.repo.changectx(rev)
            self.textview_header.displayRevision(ctx)            
            self.filelistmodel.setSelectedRev(ctx)
            if len(self.filelistmodel):
                self.tableView_filelist.selectRow(0)
                self.file_selected(self.filelistmodel.createIndex(0, 0, None), None)
            else:
                self.textview_status.clear()

    #@timeit
    def file_selected(self, index=None, index_from=None):
        """
        Callback called when a filename is selected in the file list
        """
        w = self.textview_status
        w.clear()
        ctx = self.filelistmodel.current_ctx
        if ctx is None:
            return
        if index is None:
            index = self.tableView_filelist.currentIndex()
        row = index.row()
        sel_file = ctx.files()[row]
        flag, data = self.get_file_data(sel_file)
        lexer = None
        if flag == "M":
            lexer = Qsci.QsciLexerDiff()
            self.textview_status.setMarginWidth(1, 0)
        elif flag == "A":
            lexer = get_lexer(sel_file, data)
            nlines = data.count('\n')
            self.textview_status.setMarginWidth(1, str(nlines)+'0')            
        if lexer:
            lexer.setDefaultFont(self.font)
            lexer.setFont(self.font)
        w.setLexer(lexer)
        self._cur_lexer = lexer

        self.textview_status.setText(data)
        self.highlight_search_string()

    def file_activated(self, index):
        sel_file = self.filelistmodel.fileFromIndex(index)
        if sel_file is not None and len(self.repo.file(sel_file))>1:
            dlg = FileDiffViewer(self.repo, sel_file)
            dlg.setWindowTitle('Hg file log viewer')
            dlg.show()

    def file_section_resized(self, idx, oldsize, newsize):
        if idx == 2:
            self.filelistmodel.setDiffWidth(newsize)

    #@timeit
    def get_file_data(self, filename, ctx=None):
        if ctx is None:
            ctx = self.filelistmodel.current_ctx
        data = ""
        flag = self.filelistmodel.fileflag(filename, ctx)
        if flag in ('M', 'A'):
            fc = ctx.filectx(filename)
            if fc.size() > 100000:
                data = "File too big"
                return flag, data
            if flag == "M":
                # return the diff but the 3 first lines
                data = revdiff(self.repo, ctx, files=[filename])
                data = u'\n'.join(data.splitlines()[3:])
            elif flag == "A":
                # return the whole file
                data = unicode(fc.data(), errors='ignore') # XXX
        return flag, data

    def reload_repository(self):
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self.init_variables()
        self.setup_branch_combo()
        self.setup_models()        
        self.refresh_revision_table()

    #@timeit
    def refresh_revision_table(self, branch=None):
        """Starts the process of filling the HgModel"""
        if branch is None:
            branch = self.branch_comboBox.currentText()
        branch = str(branch)
        self.repomodel.setRepo(self.repo, branch=branch)
        self.tableView_revisions.setCurrentIndex(self.tableView_revisions.model().index(0,0))

    def resize_filelist_columns(self, *args):
        # resize columns the smart way: the first column holding file
        # names is resized according to the total widget size.
        self.tableView_filelist.resizeColumnToContents(1)
        vp_width = self.tableView_filelist.viewport().width()
        col_widths = [self.tableView_filelist.columnWidth(i) \
                      for i in range(1, self.filelistmodel.columnCount())]
        col_width = vp_width - sum(col_widths)
        self.tableView_filelist.setColumnWidth(0, col_width)

    def on_find_toggled(self, checked):
        if checked:
            self.entry_find.setFocus()
            self.entry_find.selectAll()
            self._frame_find_timer.start()
        else:
            self._frame_find_timer.stop()
            
    # methods to manage searching
    def highlight_search_string(self):
        if not self.frame_find.isHidden() and self._find_text is not None and self._find_text.strip():
            w = self.textview_status
            data = unicode(self.textview_status.text())
            w.SendScintilla(w.SCI_SETINDICATORCURRENT, 8)
            pos = data.find(self._find_text)
            found = pos > -1
            n = len(self._find_text)
            while pos > -1:
                w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos, n)
                pos = data.find(self._find_text, pos+1)
            return found
        return False

    def clear_highlights(self):
        w = self.textview_status
        n = w.length()
        w.SendScintilla(w.SCI_SETINDICATORCURRENT, 8) # highlight
        w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, n)
        w.SendScintilla(w.SCI_SETINDICATORCURRENT, 9) # current found occurrence
        w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, n)

    def find_in_repo(self, fromrev, fromfile=None):
        """
        Find self._find_text in the whole repo from rev 'fromrev'
        """
        for rev in xrange(fromrev, 0, -1):
            ctx = self.repo.changectx(rev)
            pos = 0
            files = ctx.files()
            if fromfile is not None and fromfile in files:
                files = files[files.index(fromfile):]
                fromfile=None
            for filename in files:
                flag, data = self.get_file_data(filename, ctx)
                while True:
                    newpos = data.find(self._find_text, pos)
                    if newpos > -1:
                        pos = newpos + 1
                        yield rev, filename, newpos
                    else:
                        pos = 0
                        yield None
                        break

    def on_cancelsearch(self, *args):
        self._find_iter = None
        self.statusBar().showMessage('Search cancelled!', 2000)

    def on_find(self, *args):
        """
        callback called when 'Find' button is pushed
        """
        self._frame_find_timer.stop() # prevent find frame from hiding while searching
        if self._find_iter is None:
            curfile = self.filelistmodel.fileFromIndex(self.tableView_filelist.currentIndex())
            currev = self.current_ctx.rev()
            self._find_iter = self.find_in_repo(currev, curfile)
        self.find_next()

    def find_next(self, step=0):
        """
        to be called from 'on_find' callback (or recursively). Try to
        find the next occurrence of self._find_text (as a 'background'
        process, so the GUI is not frozen, and as a cancellable task).
        """
        if self._find_iter is None:
            return
        for next_find in self._find_iter:
            if next_find is None:
                if (step % 20) == 0:
                    self.statusBar().showMessage('Searching'+'.'*(step/20))
                step += 1
                QtCore.QTimer.singleShot(0, lambda self=self, step=(step % 80): self.find_next(step))
            else:
                self.statusBar().clearMessage()
                rev, filename, pos = next_find
                if self.current_ctx.rev() != rev:
                    idx = self.repomodel.indexFromRev(rev)
                    if idx is not None:
                        self.tableView_revisions.setCurrentIndex(idx)

                if filename != self.filelistmodel.fileFromIndex(self.tableView_filelist.currentIndex()):
                    self.tableView_filelist.keyboardSearch(filename)
                    self.highlight_search_string()

                w = self.textview_status
                line = w.SendScintilla(w.SCI_LINEFROMPOSITION, pos)
                #line, idx = w.lineIndexFromPosition(nextpos)
                w.ensureLineVisible(line)
                w.SendScintilla(w.SCI_SETINDICATORCURRENT, 9)
                w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, pos)
                w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos, len(self._find_text))
                self._frame_find_timer.start()
            return
        self.statusBar().showMessage('No more matches found in repository', 2000)
        self._find_iter = None
        self._frame_find_timer.start()

    def on_find_text_changed(self, newtext):
        """
        Callback called when the content of the find text entry is changed
        """
        newtext = unicode(newtext)
        if not newtext.strip():
            self._find_text = None
            self._find_iter = None
            self.clear_highlights()
        if self._find_text != newtext:
            self._find_text = newtext
            self._find_iter = None
            self.clear_highlights()
            if not self.highlight_search_string():
                self.statusBar().showMessage('Search string not found in current diff. '
                                             'Hit "Find next" button to start searching '
                                             'in the repository', 2000)
        self._frame_find_timer.start()


    def on_about(self, *args):
        """ Display about dialog """
        from hgqvlib.__pkginfo__ import modname, version, short_desc, long_desc
        try:
            from mercurial.version import get_version
            hgversion = get_version()
        except:
            from mercurial.__version__ import version as hgversion
            
        QtGui.QMessageBox.about(self, self.tr("About hgqv"),
                                "<h2>About hgqv %s</h2> (using hg %s)" % (version, hgversion) +
                                "<p><i>%s</i></p>" % short_desc.capitalize() +
                                "<p>%s</p>" % long_desc)

def find_repository(path):
    """returns <path>'s mercurial repository

    None if <path> is not under hg control
    """
    path = os.path.abspath(path)
    while not os.path.isdir(os.path.join(path, ".hg")):
        oldpath = path
        path = os.path.dirname(path)
        if path == oldpath:
            return None
    return path

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-R', '--repository', dest='repo',
                       help='location of the repository to explore')
    parser.add_option('-f', '--file', dest='filename',
                       help='filter revisions which touch FILE', metavar="FILE")
    parser.add_option('-g', '--regexp', dest='filerex',
                       help='filter revisions which touch FILE matching regexp')

    opt, args = parser.parse_args()
    dir_ = None
    if opt.repo:
        dir_ = opt.repo
    else:
        dir_ = os.getcwd()
    dir_ = find_repository(dir_)
    filerex = None
    if opt.filename:
        filerex = "^" + re.escape(opt.filename) + "$"
    elif opt.filerex:
        filerex = opt.filerex

    try:
        u = ui.ui()
        repo = hg.repository(u, dir_)
    except:
        print "You are not in a repo, are you?"
        sys.exit(1)

    app = QtGui.QApplication(sys.argv)
    mainwindow = HgRepoViewer(repo, filerex)
    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # remove current dir from sys.path
    while sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
