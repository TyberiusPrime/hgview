# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# hgview_qt4.py - qt4-based hgk
#
# Copyright (C) 2007-2009 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Main Qt4 application for hgview
"""
import sys, os
import time
import re

from optparse import OptionParser
from os.path import dirname, join, isfile

from PyQt4 import QtCore, QtGui, Qsci, uic

import hgview.fixes

from mercurial import ui, hg, patch
from mercurial.node import hex, short as short_hex, bin as short_bin

from hgview.qt4.hgrepomodel import HgRepoListModel, HgFileListModel
from hgview.qt4.hgfileviewer import FileViewer, FileDiffViewer
from hgview.hggraph import diff as revdiff
from hgview.decorators import timeit
from hgview.config import HgConfig

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
normal = QtGui.QFont.Normal

diff_styles = {'+': (normal, Qt.darkGreen),
               '-': (normal, Qt.red),
               '@': (bold, Qt.blue),
               }
               

class HgMainWindow(QtGui.QMainWindow):
    """Main hg view application"""
    def __init__(self, repo, filerex = None):
        QtGui.QMainWindow.__init__(self)

        # hg repo
        self.graph = None
        self.repo = repo
        self.loadConfig()

        # load qt designer ui file
        for _path in [dirname(__file__),
                      join(sys.exec_prefix, 'share/hgview'),
                      os.path.expanduser('~/share/hgview'),
                      join(dirname(__file__), "../../../../../share/hgview"),
                      ]:
            ui_file = join(_path, 'hgview.ui')
            
            if isfile(ui_file):
                break
        else:
            raise ValueError("Unable to find hgview.ui\n"
                             "Check your installation.")
        uifile = os.path.join(os.path.dirname(__file__), ui_file)
        self.ui = uic.loadUi(uifile, self)
        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)
        self.connect(self.splitter_2, QtCore.SIGNAL('splitterMoved (int, int)'),
                     self.resize_filelist_columns)
        lay = QtGui.QHBoxLayout(self.textview_frame)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)
        # main window actions
        self.connect(self.actionRefresh, QtCore.SIGNAL('triggered ()'),
                     self.refresh_revision_table)
        self.connect(self.actionAbout, QtCore.SIGNAL('triggered ()'),
                     self.on_about)
        self.connect(self.actionQuit, QtCore.SIGNAL('triggered ()'),
                     self.close)
        self.actionQuit.setShortcuts([self.actionQuit.shortcut(), Qt.Key_Escape])
        
        # text viewer
        sci = Qsci.QsciScintilla(self.textview_frame)
        lay.addWidget(sci)
        sci.setMarginLineNumbers(1, True)
        sci.setReadOnly(True)
        sci.setFont(self.font)
        self.lexers = {"python": Qsci.QsciLexerPython(),
                       "diff": Qsci.QsciLexerDiff(),
                       # ...
                       }
        for lex in self.lexers.values():
            lex.setDefaultFont(self.font)
        sci.SendScintilla(sci.SCI_INDICSETSTYLE, 8, sci.INDIC_ROUNDBOX)
        sci.SendScintilla(sci.SCI_INDICSETUNDER, 8, True)
        sci.SendScintilla(sci.SCI_INDICSETFORE, 8, 0xBBFFFF)
        sci.SendScintilla(sci.SCI_INDICSETSTYLE, 9, sci.INDIC_PLAIN)
        sci.SendScintilla(sci.SCI_INDICSETUNDER, 9, False)
        sci.SendScintilla(sci.SCI_INDICSETFORE, 9, 0x0000FF)
        self.textview_status = sci
        
##         self.pb = QtGui.QProgressBar(self.statusBar())
##         self.pb.setTextVisible(False)
##         self.pb.hide()
##         self.statusBar().addPermanentWidget(self.pb)
        self.statusBar().hide()
        # filter frame
        self.filter_frame.hide() # disabled for now XXX TODO
        self.filerex = filerex
        if filerex:
            self.filter_files_reg = re.compile(filerex)
        else:
            self.filter_files_reg = None
        self.filter_noderange = None

        self.init_filter()
        self.connect(self.button_filter, QtCore.SIGNAL('clicked ()'),
                     self.on_filter)

        # find frame
        self._cur_find_pos = None
        self._find_text = None
        
        self.find_frame.hide()
        self.find_toolButton.setDefaultAction(self.actionCloseFind)
        self.action_Find.setShortcuts([self.action_Find.shortcut(), "Ctrl+F", "/"])
        self.button_find.setDefaultAction(self.action_FindNext)
        self.action_FindNext.setShortcuts([self.action_FindNext.shortcut(), "Ctrl+N"])
        self.connect(self.actionCloseFind, QtCore.SIGNAL('triggered(bool)'),
                     self.find_frame.hide)
        self.connect(self.action_Find, QtCore.SIGNAL('triggered()'),
                     self.show_find_frame)
        self.connect(self.action_FindNext, QtCore.SIGNAL('triggered()'),
                     self.on_find)
        self.connect(self.entry_find, QtCore.SIGNAL('returnPressed()'),
                     self.on_find)
        self.connect(self.entry_find, QtCore.SIGNAL('textChanged(const QString &)'),
                     self.on_find_text_changed)
        self._find_frame_timer = QtCore.QTimer(self)
        self._find_frame_timer.setInterval(self.hidefinddelay)
        self.connect(self._find_frame_timer, QtCore.SIGNAL('timeout()'),
                     self.find_frame.hide)

        # setup tables and views
        self.setup_header_textview()
        self.setup_revision_table()
        self.setup_filelist_table()

        QtGui.qApp.flush()        
        self.refresh_revision_table()

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
        self.hidefinddelay = cfg.getHideFindDelay()
        
    def setup_revision_table(self):
        self.repomodel = HgRepoListModel(self.repo)
        
        repotable = self.tableView_revisions
        repotable.installEventFilter(self)
        repotable.setTabKeyNavigation(False)

        repotable.verticalHeader().setDefaultSectionSize(self.rowheight)
        repotable.setShowGrid(False)
        repotable.verticalHeader().hide()
        repotable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        repotable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        repotable.setAlternatingRowColors(True)
        repotable.setModel(self.repomodel)
        repotable.show()

    def setup_filelist_table(self):
        self.filelistmodel = HgFileListModel(self.repo, self.repomodel.graph)

        filetable = self.tableView_filelist
        filetable.verticalHeader().setDefaultSectionSize(self.rowheight)
        filetable.setTabKeyNavigation(False)
        filetable.setShowGrid(False)
        filetable.verticalHeader().hide()
        filetable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        filetable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        filetable.setAlternatingRowColors(True)
        filetable.setModel(self.filelistmodel)

        self.connect(self.tableView_filelist.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                     self.file_selected)
        self.connect(self.tableView_filelist,
                     QtCore.SIGNAL('doubleClicked (const QModelIndex &)'),
                     self.file_activated)
        self.connect(self.tableView_revisions.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                     self.revision_selected)
        self.connect(filetable.horizontalHeader(),
                     QtCore.SIGNAL('sectionResized(int, int, int)'),
                     self.file_section_resized)
        
    def setup_header_textview(self):
        self.header_diff_format = QtGui.QTextCharFormat()
        self.header_diff_format.setFont(self.font)
        self.header_diff_format.setFontWeight(bold)
        self.header_diff_format.setForeground(Qt.black)
        self.header_diff_format.setBackground(Qt.gray)
        
        self.textview_header.setFont(self.font)
        self.textview_header.setReadOnly(True)

    def resizeEvent(self, event):
        # we catch this event to resize smartly tables' columns
        QtGui.QMainWindow.resizeEvent(self, event)
        if self.graph is None: # do not resize if we are loading a reporsitory
            self.resize_revisiontable_columns()
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
                        
    def revision_selected(self, index, index_from):
        """
        Callback called when a revision os selected in the revisions table
        """
        row = index.row() + 1
        if self.repomodel.graph:
            gnode = self.repomodel.graph[row]
            ctx = self.repo.changectx(gnode.rev)
            self.current_ctx = ctx
            header = self.fill_revlog_header(ctx)
            self.textview_header.setHtml(header)

            self.filelistmodel.setSelectedRev(ctx)
            if len(self.filelistmodel):
                self.tableView_filelist.selectRow(0)
                self.file_selected(self.filelistmodel.createIndex(0,0,None), None)
            else:
                print "empty filelistmodel for", ctx.rev()
                self.textview_status.clear()

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
        
        if flag == "M":
            w.setLexer(self.lexers['diff'])
        elif flag == "A":
            w.setLexer(self.lexers['python']) # XXX
        else:
            w.setLexer(None)

        self.textview_status.setText(data)
        self.highlight_search_string()
        self._cur_find_pos = None

    def file_activated(self, index):
        sel_file = self.filelistmodel.fileFromIndex(index)
        if sel_file is not None:
            FileDiffViewer(self.repo, sel_file).exec_()
                
    def file_section_resized(self, idx, oldsize, newsize):
        if idx == 2:
            self.filelistmodel.setDiffWidth(newsize)

    def resize_filelist_columns(self, *args):
        # resize columns the smart way: the diffstat column is resized
        # according to its content, the one holding file names being
        # resized according to the widget size.
        self.tableView_filelist.resizeColumnToContents(1)
        vp_width = self.tableView_filelist.viewport().width()
        self.tableView_filelist.setColumnWidth(0, vp_width-self.tableView_filelist.columnWidth(1))

    def resize_revisiontable_columns(self, *args):
        # same as before, but for the "Log" column
        col1_width = self.tableView_revisions.viewport().width()
        fontm = QtGui.QFontMetrics(self.tableView_revisions.font())
        for c in range(self.repomodel.columnCount()):
            if c == 1:
                continue
            w = self.repomodel.maxWidthValueForColumn(c)
            if w is not None:
                w = fontm.width(unicode(w) + 'w')
                self.tableView_revisions.setColumnWidth(c, w)
            else:
                self.tableView_revisions.setColumnWidth(c, 140)
            col1_width -= self.tableView_revisions.columnWidth(c)
        self.tableView_revisions.setColumnWidth(1, col1_width)

    def get_file_data(self, filename, ctx=None):
        if ctx is None:
            ctx = self.filelistmodel.current_ctx
        flag = self.filelistmodel.fileflag(filename, ctx)
        if flag == "M":
            # return the diff but the 3 first lines
            data = revdiff(self.repo, ctx, files=[filename])
            data = u'\n'.join(data.splitlines()[3:])
        elif flag == "A":
            # return the whole file
            data = unicode(ctx.filectx(filename).data(), errors='ignore') # XXX
        else:
            data = ""
        return flag, data
                    
    def refresh_revision_table(self):
        """Starts the process of filling the HgModel"""
        # XXX TODO
        self.tableView_revisions.setCurrentIndex(self.tableView_revisions.model().index(0,0))

    def fill_revlog_header(self, ctx):
        """Build the revision log header"""
        repo = self.repo
        buf = "<table>\n"
        buf += '<tr><td class="label">Revision:</td>'\
               '<td><span class="rev_number">%d</span>:'\
               '<span class="rev_hash">%s</span></td></tr>'\
               '\n' % (ctx.rev(), short_hex(ctx.node())) 
        #buf += short_hex(node) + '\n' #, "link")
        buf += '<tr><td class="label">Author:</td>'\
               '<td class="auth_id">%s</td></tr>'\
               '\n' %  ctx.user()
        #buf.create_mark("begdesc", buf.get_start_iter())

        for p in ctx.parents():
            if p.rev() > -1:
                short = short_hex(p.node())
                buf += '<tr><td class="label">Parent:</td>'\
                       '<td><span class="rev_number">%d</span>:'\
                       '<a href="%s" class="rev_hash">%s</a>&nbsp;'\
                       '<span class="short_desc">(%s)</span></td></tr>'\
                       '\n' % (p.rev(), p.rev(), short, p.description())
        for p in ctx.children():
            if p.rev() > -1:
                short = short_hex(p.node())
                buf += '<tr><td class="label">Child:</td>'\
                       '<td><span class="rev_number">%d</span>:'\
                       '<a href="%s" class="rev_hash">%s</a>&nbsp;'\
                       '<span class="short_desc">(%s)</span></td></tr>'\
                       '\n' % (p.rev(), p.rev(), short, p.description())

        buf += "</table>\n"

        buf += '<div class="diff_desc"><p>%s</p></div>\n' % ctx.description().replace('\n', '<br/>\n')
        return buf

    def show_find_frame(self, *args):
        self.find_frame.show()
        self.entry_find.setFocus()
        self.entry_find.selectAll()
        self._find_frame_timer.start()

    def highlight_search_string(self):
        if not self.find_frame.isHidden() and self._find_text.strip():
            w = self.textview_status
            data = unicode(self.textview_status.text())
            w.SendScintilla(w.SCI_SETINDICATORCURRENT, 8)
            pos = data.find(self._find_text)
            n = len(self._find_text)
            while pos > -1:
                w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos, n)
                pos = data.find(self._find_text, pos+1)

    def clear_highlights(self):
        w = self.textview_status
        n = w.length()
        w.SendScintilla(w.SCI_SETINDICATORCURRENT, 8)
        w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, n)
        w.SendScintilla(w.SCI_SETINDICATORCURRENT, 9)
        w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, n)

    def find_in_data(self, data, pos, filename=None, rev=None):
        """
        Find self._find_text in 'data', from 'pos' 
        """
        pos = data.find(self._find_text, pos+1)
        if pos > -1:
            if rev is not None:
                idx = self.repomodel.indexFromRev(rev)
                if idx is not None:
                    self.tableView_revisions.setCurrentIndex(idx)
            if filename is not None:
                self.tableView_filelist.keyboardSearch(filename)
            else:
                filename = self.filelistmodel.fileFromIndex(self.tableView_filelist.currentIndex())
            w = self.textview_status
            line = w.SendScintilla(w.SCI_LINEFROMPOSITION, pos)
            #line, idx = w.lineIndexFromPosition(nextpos)
            w.ensureLineVisible(line)
            w.SendScintilla(w.SCI_SETINDICATORCURRENT, 9)
            w.SendScintilla(w.SCI_INDICATORCLEARRANGE, 0, pos)
            w.SendScintilla(w.SCI_INDICATORFILLRANGE, pos, len(self._find_text))
            self._cur_find_pos = filename, pos
            self._find_frame_timer.start()
            return True
        return False

    def find_in_rev(self, rev=None, curfile=None):
        """
        Find self._find_text in all files of the revision 'rev' (from file 'curfile' if given)
        """
        if rev is None:
            ctx = self.current_ctx
        else:
            ctx = self.repo.changectx(rev)
        pos = 0
        files = ctx.files()
        if curfile is not None:
            files = files[files.index(curfile)+1:]
        for filename in files:
            flag, data = self.get_file_data(filename, ctx)
            if self.find_in_data(data, pos, filename, rev):
                return True
        return False
        
    def find_in_repo(self, fromrev):
        """
        Find self._find_text in the whole repo from rev 'fromrev'
        """
        for rev in xrange(fromrev-1, 0, -1):
            if self.find_in_rev(rev):
                return True
        return False
    
    def on_find(self, *args):
        """
        callback called when 'Find' button is pushed
        """
        self._find_frame_timer.stop()
        if self._cur_find_pos is not None:
            curfile, pos = self._cur_find_pos
        else:
            curfile = self.filelistmodel.fileFromIndex(self.tableView_filelist.currentIndex())
            pos = 0
            self.highlight_search_string()
        if curfile:
            flag, data = self.get_file_data(curfile)
            if self.find_in_data(data, pos):
                return
            if self.find_in_rev(self.current_ctx.rev(), curfile):
                return
        if self.find_in_repo(self.current_ctx.rev()):
            return
        self._cur_find_pos = None
        self._find_frame_timer.start()
        
    def on_find_text_changed(self, newtext):
        """
        Callback called when the content of the find text entry is changed
        """
        newtext = unicode(newtext)
        if not newtext.strip():
            self._find_text = None
            self._cur_find_pos = None
            self.clear_highlights()            
        if self._find_text != newtext:
            self._find_text = newtext
            self._cur_find_pos = None
            self.clear_highlights()
            
        self._find_frame_timer.start()
        
    def on_anchor_clicked(self, qurl):
        """
        Callback called when a link is clicked in the text browser
        displaying the diffs
        """
        rev = int(qurl.toString())

        # forbid Qt to look for a real document at URL
        self.textview_status.setSource(QtCore.QUrl(''))

        node = self.repo.repo.changelog.node(rev)
        row = self.repomodel.row_from_node(node)
        if row is not None:
            self.tableView_revisions.selectRow(row)
        else:
            print "CANNOT find row for node ", self.repo.read_node(node).rev, node
            
    def on_filter1_activate(self, *args):
        self.filter_dialog.show()

    def init_filter(self):
        file_filter = self.entry_file_filter
        node_low = self.spinbutton_rev_low
        node_high = self.spinbutton_rev_high

        cnt = self.repo.changelog.count()
        if self.filter_files_reg:
            file_filter.setText(self.filerex)
        node_low.setRange(0, cnt+1)
        node_high.setRange(0, cnt+1)
        node_low.setValue(0)
        node_high.setValue(cnt)

    def on_filter(self, *args):
        file_filter = self.entry_file_filter
        node_low = self.spinbutton_rev_low
        node_high = self.spinbutton_rev_high
        self.filter_files_reg = re.compile(str(file_filter.text()))
        self.filter_noderange = set(range(node_low.value(), node_high.value()))
        self.refresh_revision_table()

    def revpopup_add_tag(self, item):
        path, col = self.revpopup_path
        if path is None or col is None:
            return
        self.revisions
        
    def revpopup_update(self, item):
        print "UPDATE"
        
    def filter_nodes(self):
        """Filter the nodes according to filter_files and filter_nodes"""
        keepnodes = []
        nodes = self.repo.nodes
        frex = self.filter_files_reg
        noderange = self.filter_noderange or set(range(len(nodes)))
        for n in nodes:
            node = self.repo.read_node(n)
            if node.rev in noderange:
                for f in node.files:
                    if frex.search(f):
                        keepnodes.append(n)
                        break
        return keepnodes

    def on_about(self, *args):
        """ Display about dialog """
        from hgview.__pkginfo__ import modname, version, short_desc, long_desc
        QtGui.QMessageBox.about(self, self.tr("About hgview_qt4"),
                                "<h2>About hgview_qt4 %s</h2>" % version + 
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

    #try:
    if 1:
        u = ui.ui()
        repo = hg.repository(u, dir_)
        #repo = HgHLRepo(dir_)
    #except:
    #    print "You are not in a repo, are you?"
    #    sys.exit(1)

    app = QtGui.QApplication(sys.argv)
    mainwindow = HgMainWindow(repo, filerex)
    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # remove current dir from sys.path
    if sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
