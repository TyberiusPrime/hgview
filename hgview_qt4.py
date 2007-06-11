# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# hgview.py - gtk-based hgk
#
# Copyright (C) 2007 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Main gtk application for hgview
"""
import sys, os
import time
import re
from optparse import OptionParser
from os.path import dirname, join, isfile

from PyQt4 import QtCore, QtGui, uic

import pygments
from pygments import lexers, formatters

import fixes

from hgrepomodel import HgRepoListModel, HgFileListModel

#from diffstatrenderer import DiffStatRenderer
from hgrepo import HgHLRepo, short_hex, short_bin

default_CSS = """
.label { font-weight: bold }
.diff_title {
  background-color: #f0f0f0;
  margin: 5px;
  padding-left: 40px;
  font-weight: bold;
  }

td.linenos { background-color: #f0f0f0; padding-right: 10px; }
.c { color: #008800; font-style: italic } /* Comment */
.err { border: 1px solid #FF0000 } /* Error */
.k { color: #AA22FF; font-weight: bold } /* Keyword */
.o { color: #666666 } /* Operator */
.cm { color: #008800; font-style: italic } /* Comment.Multiline */
.cp { color: #008800 } /* Comment.Preproc */
.c1 { color: #008800; font-style: italic } /* Comment.Single */
.gd { color: #A00000 } /* Generic.Deleted */
.ge { font-style: italic } /* Generic.Emph */
.gr { color: #FF0000 } /* Generic.Error */
.gh { color: #000080; font-weight: bold } /* Generic.Heading */
.gi { color: #00A000 } /* Generic.Inserted */
.go { color: #808080 } /* Generic.Output */
.gp { color: #000080; font-weight: bold } /* Generic.Prompt */
.gs { font-weight: bold } /* Generic.Strong */
.gu { color: #800080; font-weight: bold } /* Generic.Subheading */
.gt { color: #0040D0 } /* Generic.Traceback */
.kc { color: #AA22FF; font-weight: bold } /* Keyword.Constant */
.kd { color: #AA22FF; font-weight: bold } /* Keyword.Declaration */
.kp { color: #AA22FF } /* Keyword.Pseudo */
.kr { color: #AA22FF; font-weight: bold } /* Keyword.Reserved */
.kt { color: #AA22FF; font-weight: bold } /* Keyword.Type */
.m { color: #666666 } /* Literal.Number */
.s { color: #BB4444 } /* Literal.String */
.na { color: #BB4444 } /* Name.Attribute */
.nb { color: #AA22FF } /* Name.Builtin */
.nc { color: #0000FF } /* Name.Class */
.no { color: #880000 } /* Name.Constant */
.nd { color: #AA22FF } /* Name.Decorator */
.ni { color: #999999; font-weight: bold } /* Name.Entity */
.ne { color: #D2413A; font-weight: bold } /* Name.Exception */
.nf { color: #00A000 } /* Name.Function */
.nl { color: #A0A000 } /* Name.Label */
.nn { color: #0000FF; font-weight: bold } /* Name.Namespace */
.nt { color: #008000; font-weight: bold } /* Name.Tag */
.nv { color: #B8860B } /* Name.Variable */
.ow { color: #AA22FF; font-weight: bold } /* Operator.Word */
.mf { color: #666666 } /* Literal.Number.Float */
.mh { color: #666666 } /* Literal.Number.Hex */
.mi { color: #666666 } /* Literal.Number.Integer */
.mo { color: #666666 } /* Literal.Number.Oct */
.sb { color: #BB4444 } /* Literal.String.Backtick */
.sc { color: #BB4444 } /* Literal.String.Char */
.sd { color: #BB4444; font-style: italic } /* Literal.String.Doc */
.s2 { color: #BB4444 } /* Literal.String.Double */
.se { color: #BB6622; font-weight: bold } /* Literal.String.Escape */
.sh { color: #BB4444 } /* Literal.String.Heredoc */
.si { color: #BB6688; font-weight: bold } /* Literal.String.Interpol */
.sx { color: #008000 } /* Literal.String.Other */
.sr { color: #BB6688 } /* Literal.String.Regex */
.s1 { color: #BB4444 } /* Literal.String.Single */
.ss { color: #B8860B } /* Literal.String.Symbol */
.bp { color: #AA22FF } /* Name.Builtin.Pseudo */
.vc { color: #B8860B } /* Name.Variable.Class */
.vg { color: #B8860B } /* Name.Variable.Global */
.vi { color: #B8860B } /* Name.Variable.Instance */
.il { color: #666666 } /* Literal.Number.Integer.Long */
"""

class HgMainWindow(QtGui.QMainWindow):
    """Main hg view application"""
    def __init__(self, repo, filerex = None ):

        QtGui.QMainWindow.__init__(self)
        self.ui = uic.loadUi('hgview.ui', self)
        
        self.repo = repo

        self.filerex = filerex
        if filerex:
            self.filter_files = re.compile( filerex )
        else:
            self.filter_files = None
        self.filter_noderange = None

        self.difflexer = lexers.get_lexer_by_name('diff')
        self.htmlformatter = formatters.HtmlFormatter(full=False)

        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)

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
        #self.init_filter()
        self.refresh_revision_table()
        #self.find_text = None
        self.connect(self.actionRefresh, QtCore.SIGNAL('triggered ()'),
                     self.refresh_revision_table)
        self.connect(self.actionAbout, QtCore.SIGNAL('triggered ()'),
                     self.on_about)

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
        repotable.resizeColumnsToContents()

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
        self.connect(self.tableView_revisions.selectionModel(),
                     QtCore.SIGNAL('currentRowChanged ( const QModelIndex & , const QModelIndex &  )'),
                     self.revision_selected)

    def setup_diff_textview(self):
        doc = self.textview_status.document()
        doc.setDefaultStyleSheet(default_CSS)
        self.textview_status.setReadOnly(True)
        self.connect(self.textview_status,
                     QtCore.SIGNAL('anchorClicked( const QUrl &)'),
                     self.on_anchor_clicked)
        
    def on_anchor_clicked(self, qurl):
        rev = int(qurl.toString())
        self.textview_status.setSource(QtCore.QUrl('')) # forbid Qt to look for a real document at URL
        node = self.repo.repo.changelog.node(rev)
        row = self.repomodel.row_from_node(node)
        if row is not None:
            self.tableView_revisions.selectRow(row)
        else:
            print "CANNOT find row for node ", self.repo.read_node(node).rev, node
    def revision_selected(self, index, index_from):
        row = index.row()
        #rev = index.model().getData(row, 0)
        if self.repomodel.graph:
            node = self.repomodel.graph.rows[row]
            self.filelistmodel.setSelectedNode(node)
            rev_node = self.repo.read_node(node)
            if rev_node.files:
                buff = self.get_revlog_header(node, rev_node)
                buff += self.get_diff_richtext(node, rev_node) 
            else:
                buff = ""
            self.textview_status.setHtml(buff)
            if buff:
                self.tableView_filelist.selectRow(0)
                self.file_selected(self.filelistmodel.createIndex(0,0,None), None)

    def file_selected(self, index, index_from):
        node = self.filelistmodel.current_node
        if node is None:
            return
        rev_node = self.repo.read_node(node)
        row = index.row()
        if row == 0:
            self.textview_status.setSource(QtCore.QUrl(""))#home()
        else:
            sel_file = rev_node.files[row-1]
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
        frex = self.filter_files
        noderange = self.filter_noderange or set(range(len(nodes)))
        for n in nodes:
            node = self.repo.read_node(n)
            if node.rev in noderange:
                for f in node.files:
                    if frex.search(f):
                        keepnodes.append( n )
                        break
        return keepnodes

    def on_window_main_delete_event( self, win, evt ):
        """Bye"""
        gtk.main_quit()

    def on_quit1_activate( self, *args ):
        """Bye"""
        gtk.main_quit()

    def on_about(self, *args):
        """ Display about dialog """
        from __pkginfo__ import modname, version, short_desc, long_desc
        QtGui.QMessageBox.about(self, self.tr("About hgview_qt4"),
                                "<h2>About hgview_qt4 %s</h2>" % version + 
                                "<p><i>%s</i></p>" % short_desc.capitalize() +
                                "<p>%s</p>" % long_desc)

    def refresh_revision_table(self):
        """Starts the process of filling the HgModel"""
        self.repo.refresh()
        self.repo.read_nodes()
        if self.filter_files or self.filter_noderange:
            todo_nodes = self.filter_nodes()
        else:
            todo_nodes = self.repo.nodes
        graph = self.repo.graph( todo_nodes )
        self.filelistmodel.setSelectedNode(None)
        self.repomodel.clear()        
        self.repomodel.graph = graph
        self.last_node = 0
        self.graph = graph
        self.pb.setRange(0,len(self.graph.rows))
        self.pb.show()
        self.timer.start()

    def idle_fill_model(self):
        """Idle task filling the ListStore model chunks by chunks"""
        NMAX = 200  # Max number of entries we process each time
        graph = self.graph
        N = self.last_node
        graph.build(NMAX)
        QtGui.qApp.processEvents()
        rowselected = self.graph.rows
        last_node = min(len(rowselected), N + NMAX)
        self.last_node = last_node
        self.repomodel.notify_data_changed()
        QtGui.qApp.processEvents()
        self.tableView_revisions.resizeColumnsToContents()

        self.pb.setValue(self.last_node)
        if self.last_node == len(rowselected):
            self.graph = None
            self.rowselected = None
            self.timer.stop()
            self.pb.hide()
            return False
        return True


    def get_diff_richtext(self, node, rev_node):
        diff = self.repo.diff(self.repo.parents(node), node, rev_node.files)

        regsplit =  re.compile('^diff.*$', re.M)
        difflines = [ (m.start(), m.end()) for m in regsplit.finditer(diff)]
        reg = re.compile(r'^diff *-r *(?P<from>[a-fA-F0-9]*) *-r *(?P<to>[a-fA-F0-9]*) *(?P<file>.*) *$')        

        buf = ""
        for i, (st, end) in enumerate(difflines):
            m = reg.match(diff[st:end])
            diff_file = m.group('file')
            buf += '<a name="%s"></a>' % diff_file
            buf += '<p class="diff_title">== %s ==</p>\n' % (diff_file)
            
            diff_st = end+1
            try:
                diff_end = difflines[i+1][0]
            except:
                diff_end = -1
            diff_content = diff[diff_st:diff_end]

            buf += pygments.highlight(diff_content,
                                      self.difflexer,
                                      self.htmlformatter)
            buf += '<br/>\n'
        return buf
            
        
    def get_revlog_header(self, node, rnode):
        """Build the revision log header"""
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

        buf += "</table><br/>\n"
        return buf


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

    def fileselection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        markname = model.get_value( it, 1 )
        tw = self.xml.get_widget("textview_status" )
        mark = tw.get_buffer().get_mark( markname )
        tw.scroll_to_mark( mark, .2, use_align=True, xalign=1., yalign=0. )

    def find_next_row( self, iter, stop_iter=None ):
        """Find the next revision row based on the content of
        the 'entry_find' widget"""
        txt = self.xml.get_widget( "entry_find" ).get_text()
        rexp = re.compile( txt )
        while iter != stop_iter and iter!=None:
            revnode = self.revisions.get( iter, M_NODE ) [0]
            # author_id, log, files
            author = self.repo.authors[revnode.author_id]
            if ( rexp.search( author ) or
                 rexp.search( revnode.desc ) ):
                break
            for f in revnode.files:
                if rexp.search( f ):
                    break
            else:
                iter = self.revisions.iter_next( iter )
                continue
            break
        if iter==stop_iter or iter is None:
            return None
        self.select_row( iter )
        self.hilight_search_string()
        return iter

    def on_filter1_activate( self, *args ):
        self.filter_dialog.show()

    def init_filter(self):
        file_filter = self.xml.get_widget("entry_file_filter")
        node_low = self.xml.get_widget("spinbutton_rev_low")
        node_high = self.xml.get_widget("spinbutton_rev_high")

        cnt = self.repo.count()
        if self.filter_files:
            file_filter.set_text( self.filerex )
        node_low.set_range(0, cnt+1 )
        node_high.set_range(0, cnt+1 )
        node_low.set_value( 0 )
        node_high.set_value( cnt )

    def on_button_filter_apply_clicked( self, *args ):
        file_filter = self.xml.get_widget("entry_file_filter")
        node_low = self.xml.get_widget("spinbutton_rev_low")
        node_high = self.xml.get_widget("spinbutton_rev_high")
        self.filter_files = re.compile(file_filter.get_text())
        self.filter_noderange = set(range( node_low.get_value_as_int(), node_high.get_value_as_int() ))
        self.refresh_tree()


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
        print "You are not in a repo, are you ?"
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
