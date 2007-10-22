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

import gtk
import gtk.glade
import gobject
import pango

import hgview.fixes

from graphrenderer import RevGraphRenderer
from diffstatrenderer import DiffStatRenderer
from hgview.hgrepo import HgHLRepo, short_hex, short_bin

GLADE_FILE_NAME = "hgview.glade"

def load_glade(root=""):
    """Try several paths in which the glade file might be found"""
    for _path in [dirname(__file__),
                  join(sys.exec_prefix, 'share/hgview'),
                  os.path.expanduser('~/share/hgview'),
                  join(dirname(__file__), "../../../../../share/hgview"),
                  ]:
        glade_file = join(_path, GLADE_FILE_NAME)
        if isfile(glade_file):
            break
    else:
        raise ValueError("Unable to find hgview.glade."
                         "Check your installation.")
    return gtk.glade.XML(glade_file, root)

#import hotshot
#PROF = hotshot.Profile("/tmp/hgview.prof")

DIFFHDR = "=== %s ===\n"
M_ID = 0
M_NODE = 1
M_NODEX = 2
M_EDGES = 3


def make_texttag( name, **kwargs ):
    """Helper function generating a TextTag"""
    tag = gtk.TextTag(name)
    for key, value in kwargs.items():
        key = key.replace("_","-")
        try:
            tag.set_property( key, value )
        except TypeError:
            print "Warning the property %s is unsupported in this version of pygtk" % key
    return tag

class HgViewApp(object):
    """Main hg view application"""
    def __init__(self, repo, filerex = None ):
        self.xml = load_glade("window_main")
        self.xml.signal_autoconnect( self )
        statusbar = self.xml.get_widget("statusbar1")
        self.progressbar = gtk.ProgressBar()
        self.progressbar.hide()
        statusbar.pack_start( self.progressbar )
        self.repo = repo
        self.filerex = filerex
        if filerex:
            self.filter_files = re.compile( filerex )
        else:
            self.filter_files = None
        self.filter_noderange = None
        # The strings are stored as PYOBJECT when they contain zeros and also
        # to save memory when they are used by the custom renderer
        self.revisions = gtk.ListStore( gobject.TYPE_PYOBJECT, # node id
                                        gobject.TYPE_PYOBJECT, # node
                                        gobject.TYPE_PYOBJECT, # x for the node
                                        gobject.TYPE_PYOBJECT, # lines to draw
                                        )

        self.filelist = gtk.ListStore( gobject.TYPE_STRING, # filename
                                       gobject.TYPE_STRING,  # markname
                                       gobject.TYPE_PYOBJECT, # diffstat
                                       )

        self.create_revision_popup()
        self.setup_tags()
        self.graph = None
        self.setup_tree()
        self.init_filter()
        self.refresh_tree()
        self.find_text = None

    def create_revision_popup(self):
        self.revpopup_path = None, None
        tree = self.xml.get_widget( "treeview_revisions" )
        self.revpopup = gtk.Menu()
        self.revpopup.attach_to_widget( tree, None)
        m1 = gtk.MenuItem("Add tag...")
        m1.show()
        m1.connect("activate", self.revpopup_add_tag )
        self.revpopup.attach(m1, 0, 1, 0, 1)
        m2 = gtk.MenuItem("Update")
        m2.show()
        m2.connect("activate", self.revpopup_update )
        self.revpopup.attach(m2, 0, 1, 1, 2)

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

    def on_about_activate(self, *args):
        """ Display about dialog """
        dlg=gtk.AboutDialog()
        dlg.set_authors([u'Ludovic Aubry, Logilab',
                         u'David Douard, Logilab',
                         u'Aurélien Campéas, Logilab'])
        from __pkginfo__ import modname, version, short_desc, long_desc
        dlg.set_comments(short_desc)
        dlg.set_name(modname)
        dlg.set_version(version)
        #dlg.set_logo(pixbuf)
        dlg.run()
        dlg.destroy()

    def setup_tags(self):
        """Creates the tags to be used inside the TextView"""
        textwidget = self.xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        tag_table = text_buffer.get_tag_table()

        tag_table.add( make_texttag( "mono", family="Monospace" ))
        tag_table.add( make_texttag( "blue", foreground='blue' ))
        tag_table.add( make_texttag( "red", foreground='red' ))
        tag_table.add( make_texttag( "green", foreground='darkgreen' ))
        tag_table.add( make_texttag( "black", foreground='black' ))
        tag_table.add( make_texttag( "greybg",
                                     paragraph_background='grey',
                                     weight=pango.WEIGHT_BOLD ))
        tag_table.add( make_texttag( "yellowbg", background='yellow' ))
        link_tag = make_texttag( "link", foreground="blue",
                                 underline=pango.UNDERLINE_SINGLE )
        link_tag.connect("event", self.link_event )
        tag_table.add( link_tag )


    def link_event( self, tag, widget, event, iter_ ):
        """Handle a click on a 'link' tag in the main TextView"""
        if event.type != gtk.gdk.BUTTON_RELEASE:
            return
        text_buffer = widget.get_buffer()
        beg = iter_.copy()
        while not beg.begins_tag(tag):
            beg.backward_char()
        end = iter_.copy()
        while not end.ends_tag(tag):
            end.forward_char()
        text = text_buffer.get_text( beg, end )

        it = self.revisions.get_iter_first()
        while it:
            node = self.revisions.get_value( it, M_ID )
            hhex = short_hex(node)
            if hhex == text:
                break
            it = self.revisions.iter_next( it )
        if not it:
            return
        tree = self.xml.get_widget("treeview_revisions")
        sel = tree.get_selection()
        sel.select_iter(it)
        path = self.revisions.get_path(it)
        tree.scroll_to_cell( path )


    def author_data_func( self, column, cell, model, iter_, user_data=None ):
        """A Cell datafunction used to provide the author's name and
        foreground color"""
        node = model.get_value( iter_, M_NODE )
        cell.set_property( "text", self.repo.authors[node.author_id] )
        cell.set_property( "foreground", self.repo.colors[node.author_id] )

    def rev_data_func( self, column, cell, model, iter_, user_data=None ):
        """A Cell datafunction used to provide the revnode's text"""
        node = model.get_value( iter_, M_NODE )
        cell.set_property( "text", str(node.rev) )

    def date_data_func( self, column, cell, model, iter_, user_data=None ):
        """A Cell datafunction used to provide the date"""
        node = model.get_value( iter_, M_NODE )
        cell.set_property( "text", node.date )

    def setup_tree(self):
        """Configure the 2 gtk.TreeView"""
        # Setup the revisions treeview
        tree = self.xml.get_widget( "treeview_revisions" )
        tree.get_selection().connect("changed", self.selection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("ID", rend )
        col.set_cell_data_func( rend, self.rev_data_func )
        col.set_resizable(True)
        tree.append_column( col )

        rend = RevGraphRenderer()
        #rend.connect( "activated", self.cell_activated )
        self.graph_rend = rend
        col = gtk.TreeViewColumn("Log", rend, nodex=M_NODEX, edges=M_EDGES,
                                 node=M_NODE)
        col.set_resizable(True)
        col.set_sizing( gtk.TREE_VIEW_COLUMN_FIXED )
        col.set_fixed_width( 400 )
        tree.append_column( col )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Author", rend )
        col.set_cell_data_func( rend, self.author_data_func )
        col.set_resizable(True)
        tree.append_column( col )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Date", rend )
        col.set_cell_data_func( rend, self.date_data_func )
        col.set_resizable(True)
        tree.append_column( col )

        tree.set_model( self.revisions )

        # Setup the filelist treeview
        tree = self.xml.get_widget( "treeview_filelist" )
        tree.set_rules_hint( 1 )
        tree.get_selection().connect("changed", self.fileselection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Files", rend, text=0 )
        col.set_reorderable(True)
        tree.append_column( col )

        rend = DiffStatRenderer()
        col = gtk.TreeViewColumn("Diff Stat", rend, stats=2 )
        col.set_reorderable(True)
        tree.append_column( col )

        tree.set_model( self.filelist )

    def cell_activated(self, *args):
        print "nudge"

    def refresh_tree(self):
        """Starts the process of filling the ListStore model"""
        self.repo.read_nodes()
        #print "Computing graph..."
        t1 = time.clock()
        if self.filter_files or self.filter_noderange:
            todo_nodes = self.filter_nodes()
        else:
            todo_nodes = self.repo.nodes
        graph = self.repo.graph( todo_nodes )
        self.graph_rend.set_colors( graph.colors )
        #print "done in", time.clock()-t1

        self.revisions.clear()
        self.progressbar.show()
        self.last_node = 0
        self.graph = graph
        gobject.idle_add( self.idle_fill_model )
        return

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

    def idle_fill_model(self):
        """Idle task filling the ListStore model chunks by chunks"""
        #t1 = time.time()
        NMAX = 300  # Max number of entries we process each time
        graph = self.graph
        N = self.last_node
        graph.build(NMAX)
        rowselected = self.graph.rows
        add_rev = self.revisions.append
        tree = self.xml.get_widget( "treeview_revisions" )
        tree.freeze_notify()
        last_node = min(len(rowselected), N + NMAX)
        for n in xrange(N, last_node ):
            node = rowselected[n]
            if node is None:
                continue
            rnode = self.repo.read_node( node )
            lines = graph.rowlines[n]
            add_rev( (node, rnode, graph.x[node], (lines,n) ) )
        self.last_node = last_node
        tree.thaw_notify()
        self.progressbar.set_fraction( float(self.last_node) / len(rowselected) )
        #print "batch: %09.6f" % (time.time()-t1)
        #print self.last_node, "/", len(rowselected)
        if self.last_node == len(rowselected):
            self.graph = None
            self.rowselected = None
##             gtk.Container.remove(self.statusbar, self.progressbar )
            self.progressbar.hide()
            return False
        return True

    def set_revlog_header( self, buf, node, rnode ):
        """Put the revision log header in the TextBuffer"""
        repo = self.repo
        eob = buf.get_end_iter()
        buf.insert( eob, "Revision: %d:" % rnode.rev )
        buf.insert_with_tags_by_name( eob, short_hex(node), "link" )
        buf.insert( eob, "\n" )
        buf.insert( eob, "Author: %s\n" %  repo.authors[rnode.author_id] )
        buf.create_mark( "begdesc", buf.get_start_iter() )
        
        for p in repo.parents(node):
            pnode = repo.read_node(p)
            short = short_hex(p)
            buf.insert( eob, "Parent: %d:" % pnode.rev )
            buf.insert_with_tags_by_name( eob, short, "link" )
            buf.insert(eob, "(%s)\n" % pnode.short)
        for p in repo.children(node):
            pnode = repo.read_node(p)
            short = short_hex(p)
            buf.insert( eob, "Child:  %d:" % pnode.rev )
            buf.insert_with_tags_by_name( eob, short, "link" )
            buf.insert(eob, "(%s)\n" % pnode.short)

        buf.insert( eob, "\n" )


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
            self.set_revlog_header( text_buffer, node, rnode )
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
        # RESTRICT TO DESCRIPTION PART : should be conditionalized
        #mark = text_buffer.get_mark( "enddesc" )
        #enddesc = text_buffer.get_iter_at_mark(mark)
        #txt = text_buffer.get_slice(sob, enddesc, True )
        txt = text_buffer.get_slice(sob, eob)
        m = rexp.search( txt )
        while m: # FIXME wrong coloring in diff body
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
            # author_id, log
            author = self.repo.authors[revnode.author_id]
            if ( rexp.search( author ) or
                 rexp.search( revnode.desc ) ):
                break
            # diff
            node = self.revisions.get_value(iter, M_ID)
            rnode = self.repo.read_node(node)
            diff = self.repo.diff(self.repo.parents(node), node, rnode.files)
            if rexp.search(diff):
                break
            # files
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

    app = HgViewApp( repo, filerex )
    gtk.main()


if __name__ == "__main__":
    # remove current dir from sys.path
    if sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
