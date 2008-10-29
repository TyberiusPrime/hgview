# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# hgview_qt4.py - qt4-based hgk
#
# Copyright (C) 2007 Logilab. All rights reserved.
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

from PyQt4 import QtCore, QtGui, uic

import hgview.fixes

from hgrepomodel import HgRepoListModel, HgFileListModel
from hgview.hgrepo import HgHLRepo, short_hex, short_bin

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
normal = QtGui.QFont.Normal

diff_styles = {'+': (normal, Qt.darkGreen),
               '-': (normal, Qt.red),
               '@': (bold, Qt.blue),
               }
               

class HgMainWindow(QtGui.QMainWindow):
    """Main hg view application"""
    def __init__(self, repo, filerex = None ):

        QtGui.QMainWindow.__init__(self)
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
        
        self.repo = repo

        self.filerex = filerex
        if filerex:
            self.filter_files_reg = re.compile( filerex )
        else:
            self.filter_files_reg = None
        self.filter_noderange = None

        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)
        self.connect(self.splitter_2, QtCore.SIGNAL('splitterMoved ( int, int)'),
                     self.resize_filelist_columns)
        
        self.pb = QtGui.QProgressBar(self.statusBar())
        self.pb.setTextVisible(False)
        self.pb.hide()
        self.statusBar().addPermanentWidget(self.pb)

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(False)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.idle_fill_model)        

        self.graph = None
        self.setup_diff_textview()
        self.setup_revision_table()
        self.setup_filelist_treeview()
        self.init_filter()
        self.find_text = None
        self.connect(self.actionRefresh, QtCore.SIGNAL('triggered ()'),
                     self.refresh_revision_table)
        self.connect(self.actionAbout, QtCore.SIGNAL('triggered ()'),
                     self.on_about)
        self.connect(self.actionQuit, QtCore.SIGNAL('triggered ()'),
                     self.close)

        self.connect(self.button_filter, QtCore.SIGNAL('clicked ()'),
                     self.on_filter)
        self.connect(self.button_find, QtCore.SIGNAL('clicked ()'),
                     self.on_find)
        
        QtGui.qApp.flush()        
        self.refresh_revision_table()

    def resizeEvent(self, event):
        # we catch this event to resize tables' columns
        QtGui.QMainWindow.resizeEvent(self, event)
        if self.graph is None: # do not resize if we are loading a reporsitory
            self.resize_revisiontable_columns()
            self.resize_filelist_columns()        
        
    def setup_revision_table(self):
        self.repomodel = HgRepoListModel(self.repo)
        repotable = self.tableView_revisions
        
        repotable.setShowGrid(False)
        repotable.verticalHeader().hide()
        repotable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        repotable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        repotable.setAlternatingRowColors(True)
        repotable.setModel(self.repomodel)
        
        repotable.show()
        self.resize_revisiontable_columns()

    def setup_filelist_treeview(self):
        self.filelistmodel = HgFileListModel(self.repo, self.repomodel.graph)

        filetable = self.tableView_filelist
        filetable.setShowGrid(False)
        filetable.verticalHeader().hide()
        filetable.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        filetable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        filetable.setAlternatingRowColors(True)
        filetable.setModel(self.filelistmodel)

        self.connect(self.tableView_filelist.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged ( const QModelIndex & , const QModelIndex &  )'),
                     self.file_selected)
        self.connect(self.tableView_filelist,
                     QtCore.SIGNAL('doubleClicked ( const QModelIndex & )'),
                     self.file_activated)
        self.connect(self.tableView_revisions.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged ( const QModelIndex & , const QModelIndex &  )'),
                     self.revision_selected)

    def file_activated(self, index):
        print 'activated file at ', index.row(), index.column()
        if index.row() == 0:
            return
        
        node = self.current_node
        rnode = self.repo.read_node(node)
        sel_file = rnode.files[index.row()-1]
        patch = self.current_diff_contents[index.row()-1]

        print "should reverse apply", patch
        
        
    def setup_diff_textview(self):
        editor = self.textview_status
        font = QtGui.QFont()
        font.setFamily("Monospace")
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.font = font
        d = {'+': QtGui.QTextCharFormat(),
             '-': QtGui.QTextCharFormat(),
             '@': QtGui.QTextCharFormat(),
             }
        for k, v in d.items():
            v.setFont(self.font)
            v.setFontWeight(diff_styles[k][0])
            v.setForeground(diff_styles[k][1])
            
        self.diff_formats = d
        self.default_diff_format = QtGui.QTextCharFormat()
        self.default_diff_format.setFont(self.font)

        self.header_diff_format = QtGui.QTextCharFormat()
        self.header_diff_format.setFont(self.font)
        self.header_diff_format.setFontWeight(bold)
        self.header_diff_format.setForeground(Qt.black)
        self.header_diff_format.setBackground(Qt.gray)
        
        editor.setFont(font)
        editor.setReadOnly(True)
        self.connect(editor,
                     QtCore.SIGNAL('anchorClicked( const QUrl &)'),
                     self.on_anchor_clicked)
        
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

    def revision_selected(self, index, index_from):
        """
        Callback called when a revision os selected in the revisions table
        """
        row = index.row()
        if self.repomodel.graph:
            node = self.repomodel.graph.rows[row]
            self.current_node = node
            rev_node = self.repo.read_node(node)
            # We *need* to use a new document, since rendering in a displayed
            # QTextDocument (in a QTextEdit or so) is soooo sloooow
            # Note that set the QTextDocument's parent argument to the
            # QTextEdit widget to which it will be rattached afterward seems
            # mandatory, or a crash occur :-(
            doc = QtGui.QTextDocument(self.textview_status)
            
            if rev_node.files:
                self.fill_revlog_header(node, rev_node, doc)
                
                stats = self.fill_diff_richtext(node, rev_node, doc)
                #timeit()
            else:
                stats = []
            self.textview_status.setDocument(doc)
            self.filelistmodel.setSelectedNode(node, stats)

            if stats:
                self.tableView_filelist.selectRow(0)
                self.filelistmodel.stats = stats
                self.file_selected(self.filelistmodel.createIndex(0,0,None), None)
                self.resize_filelist_columns()

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
        for c in [0,2,3]:
            self.tableView_revisions.resizeColumnToContents(c)
            col1_width -= self.tableView_revisions.columnWidth(c)
        self.tableView_revisions.setColumnWidth(1, col1_width)

    def file_selected(self, index, index_from):
        """
        Callback called when a filename is selected in the file list
        """
        node = self.filelistmodel.current_node
        if node is None:
            return
        rev_node = self.repo.read_node(node)
        row = index.row()
        if row == 0:
            self.textview_status.setSource(QtCore.QUrl("")) # go home
        else:
            sel_file = rev_node.files[row-1]
            # don't know why this does not work...
            #self.textview_status.scrollToAnchor("#%s"%sel_file)
            # but this works fine!
            self.textview_status.setSource(QtCore.QUrl("#%s"%sel_file))
        
    def revpopup_add_tag(self, item):
        path, col = self.revpopup_path
        if path is None or col is None:
            return
        print "ADD TAG", path, col
        self.revisions
        #self.repo.add_tag( 2, "toto" )
        
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
                        keepnodes.append( n )
                        break
        return keepnodes

    def on_about(self, *args):
        """ Display about dialog """
        from hgview.__pkginfo__ import modname, version, short_desc, long_desc
        QtGui.QMessageBox.about(self, self.tr("About hgview_qt4"),
                                "<h2>About hgview_qt4 %s</h2>" % version + 
                                "<p><i>%s</i></p>" % short_desc.capitalize() +
                                "<p>%s</p>" % long_desc)

    def refresh_revision_table(self):
        """Starts the process of filling the HgModel"""
        self.repo.refresh()
        self.repo.read_nodes()
        if self.filter_files_reg or self.filter_noderange:
            todo_nodes = self.filter_nodes()
        else:
            todo_nodes = self.repo.nodes
        graph = self.repo.graph(todo_nodes)
        self.filelistmodel.setSelectedNode(None, [])
        self.repomodel.clear()        
        self.repomodel.set_graph(graph)
        self.last_node = 0
        self.graph = graph
        self.pb.setRange(0,len(self.graph.rows))
        self.pb.show()
        QtGui.qApp.flush()        
        # we use a QTimer with no delay time, so
        # it the repo loading process will let the application
        # react and the window update its content quite smoothly
        self.timer.start()

    def idle_fill_model(self):
        """Idle task filling the ListStore model chunks by chunks"""
        NMAX = 100  # Max number of entries we process each time
        graph = self.graph
        N = self.last_node
        graph.build(NMAX)
        rowselected = self.graph.rows
        last_node = min(len(rowselected), N + NMAX)
        self.last_node = last_node
        self.repomodel.notify_data_changed()
        self.resize_revisiontable_columns()
        QtGui.qApp.flush()

        self.pb.setValue(self.last_node)
        if self.last_node == len(rowselected):
            self.graph = None
            self.rowselected = None
            self.timer.stop()
            self.pb.hide()
            return False
        return True


    def fill_diff_richtext2(self, node, rev_node, doc):
        diff = self.repo.diff(self.repo.parents(node), node, rev_node.files)
        
        try:
            diff = unicode(diff, "utf-8")
        except UnicodeError:
            # XXX use a default encoding from config
            diff = unicode(diff, "iso-8859-15", 'ignore')

        
        cursor = QtGui.QTextCursor(doc)#self.textview_status.document())        
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor) 

        diff_formats = self.diff_formats
        default_diff_fmt = self.default_diff_format
        
        diff_file = None
        stats = {}
        for i,l in enumerate(diff.splitlines()):
            if l.startswith('+++') or l.startswith('---'):
                continue
            if l.startswith('diff'):
                if diff_file:
                    stats[diff_file] = (l_p, l_m)
                    
                diff_file = l.strip().split(' ',5)[-1]
                cursor.insertHtml(u'\n<a name="%s"></a>\n' % diff_file)
                cursor.insertText(u'\n === %s === \n' % (diff_file),
                                  self.header_diff_format)
                l_p = 0
                l_m = 0
            else:
                l0 = l[0]
                cursor.insertText(l+'\n', diff_formats.get(l0, default_diff_fmt))
                if l0 == "+":
                    l_p += 1
                elif l0 == "-":
                    l_m += 1
                
        if diff_file:
            stats[diff_file] = (l_p, l_m)
        return stats
    
    def fill_diff_richtext(self, node, rev_node, doc):
        diff = self.repo.diff(self.repo.parents(node), node, rev_node.files)
        
        try:
            diff = unicode(diff, "utf-8")
        except UnicodeError:
            # XXX use a default encoding from config
            diff = unicode(diff, "iso-8859-15", 'ignore')


        cursor = QtGui.QTextCursor(doc)
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor) 

        diff_formats = self.diff_formats
        default_diff_fmt = self.default_diff_format
        
        diff_file = None
        stats = {}

        regsplit =  re.compile('^diff.*$', re.M)
        difflines = [ (m.start(), m.end()) for m in regsplit.finditer(diff)]
        reg = re.compile(r'^diff *-r *(?P<from>[a-fA-F0-9]*) *-r *(?P<to>[a-fA-F0-9]*) *(?P<file>.*) *$')        

        added_line_reg = re.compile(r"^[+][^+].*$", re.M)
        rem_line_reg = re.compile(r"^-[^-].*$", re.M)

        diffsize = diff.count('\n')

        self.current_diff_contents = []        

        diff_formats = self.diff_formats
        default_diff_fmt = self.default_diff_format
        for i, (st, end) in enumerate(difflines):
            m = reg.match(diff[st:end])
            diff_file = m.group('file')
            diff_st = end+1
            try:
                diff_end = difflines[i+1][0]
            except:
                diff_end = -1
            diff_content = diff[diff_st:diff_end]
            self.current_diff_contents.append(diff_content)

            stats[diff_file] = (len(added_line_reg.findall(diff_content)),
                                len(rem_line_reg.findall(diff_content)))

            cursor.insertHtml(u'\n<a name="%s"></a>\n' % diff_file)
            cursor.insertText(u'\n === %s [+%s -%s] === \n' % (diff_file, stats[diff_file][0],stats[diff_file][1] ),
                              self.header_diff_format)
            
            for l in diff_content.splitlines():
                if l.startswith('+++') or l.startswith('---'):
                    continue
                cursor.insertText(l+'\n', diff_formats.get(l[0], default_diff_fmt))

            cursor.insertText('\n')
            
        return stats
            
        
    def fill_revlog_header(self, node, rnode, doc):
        """Build the revision log header"""
        cursor = QtGui.QTextCursor(doc)
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor) 
        repo = self.repo
        buf = "<table>\n"
        buf += '<tr><td class="label">Revision:</td>'\
               '<td><span class="rev_number">%d</span>:'\
               '<span class="rev_hash">%s</span></td></tr>'\
               '\n' % (rnode.rev, short_hex(node)) 
        #buf += short_hex(node) + '\n' #, "link" )
        buf += '<tr><td class="label">Author:</td>'\
               '<td class="auth_id">%s</td></tr>'\
               '\n' %  repo.authors[rnode.author_id] 
        #buf.create_mark( "begdesc", buf.get_start_iter() )

        for p in repo.parents(node):
            pnode = repo.read_node(p)
            short = short_hex(p)
            buf += '<tr><td class="label">Parent:</td>'\
                   '<td><span class="rev_number">%d</span>:'\
                   '<a href="%s" class="rev_hash">%s</a>&nbsp;'\
                   '<span class="short_desc">(%s)</span></td></tr>'\
                   '\n' % (pnode.rev, pnode.rev, short, pnode.short)
            #buf += short #, "link" )
        for p in repo.children(node):
            pnode = repo.read_node(p)
            short = short_hex(p)
            buf += '<tr><td class="label">Child:</td>'\
                   '<td><span class="rev_number">%d</span>:'\
                   '<a href="%s" class="rev_hash">%s</a>&nbsp;'\
                   '<span class="short_desc">(%s)</span></td></tr>'\
                   '\n' % (pnode.rev, pnode.rev, short, pnode.short)

        buf += "</table>\n"

        buf += '<div class="diff_desc"><p>%s</p></div>\n' % rnode.desc.replace('\n', '<br/>\n')
        cursor.insertHtml(buf)


    def hilight_search_string( self ):
        # Highlight the search string
        textwidget = self.xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        if not self.find_text:
            return

        rexp = re.compile(self.find_text)
        sob, eob = text_buffer.get_bounds()
        mark = text_buffer.get_mark( "enddesc" )
        enddesc = text_buffer.get_iter_at_mark(mark)
        txt = text_buffer.get_slice(sob, enddesc, True )
        m = rexp.search( txt )
        while m:
            _b = text_buffer.get_iter_at_offset( m.start() )
            _e = text_buffer.get_iter_at_offset( m.end() )
            text_buffer.apply_tag_by_name("yellowbg", _b, _e )
            m = rexp.search( txt, m.end() )

    def on_filter1_activate( self, *args ):
        self.filter_dialog.show()

    def init_filter(self):
        file_filter = self.entry_file_filter
        node_low = self.spinbutton_rev_low
        node_high = self.spinbutton_rev_high

        cnt = self.repo.count()
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

    def on_find(self, *args):
        print "Find not yet implemented... Sorry."
        QtGui.QMessageBox.warning(self, self.tr("Noy yet implemented"),
                                  "<p><b>Find</b> functionality has nit yet been implemented... Sorry</p>"
                                  )
        
        

def main():
    parser = OptionParser()
    parser.add_option( '-R', '--repository', dest='repo',
                       help='location of the repository to explore' )
    parser.add_option( '-f', '--file', dest='filename',
                       help='filter revisions which touch FILE', metavar="FILE")
    parser.add_option( '-g', '--regexp', dest='filerex',
                       help='filter revisions which touch FILE matching regexp')
    
    opt, args = parser.parse_args()
    dir_ = None
    if opt.repo:
        dir_ = opt.repo
    else:
        dir_ = os.getcwd()

    filerex = None
    if opt.filename:
        filerex = "^" + re.escape( opt.filename ) + "$"
    elif opt.filerex:
        filerex = opt.filerex

    try:
        repo = HgHLRepo( dir_ )
    except:
        print "You are not in a repo, are you?"
        sys.exit(1)

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
