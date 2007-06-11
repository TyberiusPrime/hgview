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

import fixes

from hgrepomodel import HgRepoListModel, HgFileListModel

#from diffstatrenderer import DiffStatRenderer
from hgrepo import HgHLRepo, short_hex, short_bin


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
        font = QtGui.QFont()
        font.setFamily("Courier")
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.textview_status.setFont(font)
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
        rev = index.model().getData(index.row(), 0)
        if self.repomodel.graph:
            self.filelistmodel.setSelectedNode(self.repomodel.graph.rows[index.row()])
            self.tableView_filelist.selectRow(0)
            self.file_selected(self.filelistmodel.createIndex(0,0,None), None)

    def file_selected(self, index, index_from):
        node = self.filelistmodel.current_node
        #self.diff_text_document = QtGui.QTextDocument()
        #self.textview_status.setDocument(self.diff_text_document)
        if node is None:
            return
        rev_node = self.repo.read_node(node)
        try:
            sel_file = rev_node.files[index.row()]
            
            buff = self.get_revlog_header(node, rev_node) + self.repo.diff(self.repo.parents(node), node, rev_node.files )
        except IndexError:
            buff = ""
        self.textview_status.setHtml(buff)
        
    def revpopup_add_tag(self, item):
        path, col = self.revpopup_path
        if path is None or col is None:
            return
        print "ADD TAG", path, col
        self.revisions
        self.repo.add_tag( 2, "toto" )
        
    def revpopup_update(self, item):
        print "UPDATE"

    def on_refresh_activate(self, arg):
        #print "REFRESH", arg
        self.repo.refresh()
        self.refresh_tree()
        
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
        NMAX = 300  # Max number of entries we process each time
        graph = self.graph
        N = self.last_node
        graph.build(NMAX)
        rowselected = self.graph.rows
        last_node = min(len(rowselected), N + NMAX)
        self.last_node = last_node
        self.repomodel.notify_data_changed()
        self.tableView_revisions.resizeColumnsToContents()

        self.pb.setValue(self.last_node)
        if self.last_node == len(rowselected):
            self.graph = None
            self.rowselected = None
            self.timer.stop()
            self.pb.hide()
            return False
        return True


    def on_treeview_revisions_button_press_event(self, treeview, event):
        if event.button==3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                self.revpopup_path = path, col
                self.revpopup.popup( None, None, None, event.button, time)
            return 1


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


    def prepare_diff( self, difflines, offset ):
        idx = 0
        outlines = []
        tags = []
        filespos = []
        def addtag( name, offset, length ):
            if tags and tags[-1][0] == name and tags[-1][2]==offset:
                tags[-1][2] += length
            else:
                tags.append( [name, offset, offset+length] )
        #print "DIFF:", len(difflines)
        stats = [0,0]
        statmax = 0
        for i,l in enumerate(difflines):
            if l.startswith("diff"):
                f = l.split()[-1]
                txt = DIFFHDR % f
                addtag( "greybg", offset, len(txt) )
                outlines.append(txt)
                markname = "file%d" % idx
                idx += 1
                statmax = max( statmax, stats[0]+stats[1] )
                stats = [0,0]
                filespos.append(( f, markname, offset, stats ))
                offset += len(txt)
                continue
            elif l.startswith("+++"):
                continue
            elif l.startswith("---"):
                continue
            elif l.startswith("+"):
                tag = "green"
                stats[0] += 1
            elif l.startswith("-"):
                stats[1] += 1
                tag = "red"
            elif l.startswith("@@"):
                tag = "blue"
            else:
                tag = "black"
            l = l+"\n"
            length = len(l)
            addtag( tag, offset, length )
            outlines.append( l )
            offset += length
        statmax = max( statmax, stats[0]+stats[1] )
        return filespos, tags, outlines, statmax

    def selection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        node, rnode = model.get( it, M_ID, M_NODE )
        textwidget = self.xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        textwidget.freeze_child_notify()
        text_buffer.set_text( "" )

        try:
            self.get_revlog_header( text_buffer, node, rnode )
            eob = text_buffer.get_end_iter()
            text_buffer.insert( eob, rnode.desc+"\n\n" )
            self.filelist.clear()
            enddesc = text_buffer.get_end_iter()
            enddesc.backward_line()
            text_buffer.create_mark( "enddesc", enddesc )
            self.filelist.append( ("Content", "begdesc", None ) )
            buff = self.repo.diff( self.repo.parents(node), node, rnode.files )
            try:
                buff = unicode( buff, "utf-8" )
            except UnicodeError:
                # XXX use a default encoding from config
                buff = unicode( buff, "iso-8859-1", 'ignore' )
            difflines = buff.splitlines()
            del buff
            eob = text_buffer.get_end_iter()
            
            offset = eob.get_offset()
            fileoffsets, tags, lines, statmax = self.prepare_diff( difflines, offset )
            txt = u"".join(lines)

            # XXX debug : sometime gtk complains it's not valid utf-8 !!!
            text_buffer.insert( eob, txt.encode('utf-8') )

            # inserts the tags
            for name, p0, p1 in tags:
                i0 = text_buffer.get_iter_at_offset( p0 )
                i1 = text_buffer.get_iter_at_offset( p1 )
                txt = text_buffer.get_text( i0, i1 )
                text_buffer.apply_tag_by_name( name, i0, i1 )
                
            # inserts the marks
            for f, mark,offset, stats in fileoffsets:
                pos = text_buffer.get_iter_at_offset( offset )
                text_buffer.create_mark( mark, pos )
                self.filelist.append( (f, mark, (stats[0],stats[1],statmax) ) )
        finally:
            textwidget.thaw_child_notify()
        sob, eob = text_buffer.get_bounds()
        text_buffer.apply_tag_by_name( "mono", sob, eob )

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

    def select_row( self, itr ):
        if itr is None:
            self.find_text = None
            return
        else:
            self.find_text = self.xml.get_widget( "entry_find" ).get_text()

        tree = self.xml.get_widget( "treeview_revisions" )
        sel = tree.get_selection()
        sel.select_iter( itr )
        path = self.revisions.get_path( itr )
        tree.scroll_to_cell( path, use_align=True, row_align=0.2 )


    def get_selected_rev(self):
        sel = self.xml.get_widget( "treeview_revisions" ).get_selection()
        model, it = sel.get_selected()
        if it is None:
            it = model.get_iter_first()
        return model, it

    def on_button_find_clicked( self, *args ):
        """callback: clicking on the find button
        makes the search start at the row after the
        next row
        """
        model, it = self.get_selected_rev()
        it = self.revisions.iter_next( it )
        start_it = it
        res = self.find_next_row( it )
        if res is None:
            self.find_next_row( self.revisions.get_iter_first(), start_it )

    def on_entry_find_changed( self, *args ):
        """callback: each keypress triggers a lookup
        starting at the current row which allows the
        highlight string to grow without changing rows"""
        model, it = self.get_selected_rev()
        start_it = it
        res = self.find_next_row( it )
        if res is None:
            self.find_next_row( self.revisions.get_iter_first(), start_it )

    def on_entry_find_activate( self, *args ):
        """Pressing enter in the entry_find field does the
        same as clicking on the Find button"""
        self.on_button_find_clicked()


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
