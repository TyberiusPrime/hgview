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
import fixes
import gtk
import gtk.glade
import gobject
import pango
import sys, os
import time
import re
from graphrenderer import RevGraphRenderer
from diffstatrenderer import DiffStatRenderer
from optparse import OptionParser
from hgrepo import HgHLRepo, short_hex, short_bin

GLADE_FILE_NAME = "hgview.glade"
GLADE_FILE_LOCATIONS = [ '/usr/share/hgview' ]


def load_glade():
    """Try several paths in which the glade file might be found"""
    mod = sys.modules[__name__]
    # Try this module's dir first (dev case)
    _basedir = os.path.dirname(mod.__file__)

    test_dirs = [_basedir] + GLADE_FILE_LOCATIONS
    for _dir in test_dirs:
        glade_file = os.path.join(_dir, GLADE_FILE_NAME)
        if os.path.exists(glade_file):
            return gtk.glade.XML( glade_file )

    raise ImportError("Couldn't find %s in (%s)" %
                      (GLADE_FILE_NAME,
                       ",".join(["'%s'" % f for f in test_dirs]) )
                       )

#import hotshot
#PROF = hotshot.Profile("/tmp/hgview.prof")

DIFFHDR = "=== %s ===\n"

M_NODE = 1
M_SHORTDESC = 2
M_AUTHOR = 3
M_DATE = 4
M_FILELIST = 5
M_NODEX = 6
M_EDGES = 7
M_TAGS = 8


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
        self.xml = load_glade()
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
        self.revisions = gtk.ListStore( gobject.TYPE_INT, # Revision
                                        gobject.TYPE_PYOBJECT, # node
                                        gobject.TYPE_PYOBJECT, # short desc
                                        gobject.TYPE_INT,      # author
                                        gobject.TYPE_STRING,   # date
                                        gobject.TYPE_PYOBJECT, # file list
                                        gobject.TYPE_PYOBJECT, # x for the node
                                        gobject.TYPE_PYOBJECT, # lines to draw
                                        gobject.TYPE_STRING,   # tag
                                        )

        self.filelist = gtk.ListStore( gobject.TYPE_STRING, # filename
                                       gobject.TYPE_STRING,  # markname
                                       gobject.TYPE_PYOBJECT, # diffstat
                                       )

        self.setup_tags()
        self.graph = None
        self.setup_tree()
        self.init_filter()
        self.refresh_tree()
        self.find_text = None


    def filter_nodes(self):
        """Filter the nodes according to filter_files and filter_nodes"""
        keepnodes = []
        nodes = self.repo.nodes
        frex = self.filter_files
        noderange = self.filter_noderange or set(range(len(nodes)))
        for n in nodes:
            rev, text, author_id, date_, log_, filelist, tags = self.read_node( n )
            if rev in noderange:
                for f in filelist:
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
            node = self.revisions.get_value( it, M_NODE )
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
        author_id = model.get_value( iter_, M_AUTHOR )
        cell.set_property( "text", self.repo.authors[author_id] )
        cell.set_property( "foreground", self.repo.colors[author_id] )

    def setup_tree(self):
        """Configure the 2 gtk.TreeView"""
        # Setup the revisions treeview
        tree = self.xml.get_widget( "treeview_revisions" )
        tree.get_selection().connect("changed", self.selection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("ID", rend, text=0 )
        col.set_resizable(True)
        tree.append_column( col )

        rend = RevGraphRenderer()
        #rend.connect( "activated", self.cell_activated )
        self.graph_rend = rend
        col = gtk.TreeViewColumn("Log", rend, nodex=M_NODEX, edges=M_EDGES,
                                 text=M_SHORTDESC,
                                 tags=M_TAGS)
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
        col = gtk.TreeViewColumn("Date", rend, text=4 )
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
        print "Computing graph..."
        t1 = time.clock()
        if self.filter_files or self.filter_noderange:
            todo_nodes = self.filter_nodes()
        else:
            todo_nodes = self.repo.nodes
        graph = self.repo.graph( todo_nodes )
        self.graph_rend.set_colors( graph.colors )
        print "done in", time.clock()-t1

        self.revisions.clear()
        self.progressbar.show()
        self.last_node = 0
        self.graph = graph
        gobject.idle_add( self.idle_fill_model )
        return

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
            rev, text, author_id, date_, log_, filelist, tags = self.repo.read_node(node)
            lines = graph.rowlines[n]
            add_rev( (rev, node, text, author_id, date_, filelist,
                      graph.x[node], (lines,n), tags ) )
        self.last_node = last_node
        tree.thaw_notify()
        self.progressbar.set_fraction( float(self.last_node) / len(rowselected) )
        #print "batch: %09.6f" % (time.time()-t1)
        print self.last_node, "/", len(rowselected)
        if self.last_node == len(rowselected):
            self.graph = None
            self.rowselected = None
##             gtk.Container.remove(self.statusbar, self.progressbar )
            self.progressbar.hide()
            return False
        return True

    def set_revlog_header( self, buf, node ):
        """Put the revision log header in the TextBuffer"""
        repo = self.repo
        eob = buf.get_end_iter()
        rev, text, author_id, date_, log_, filelist, tags = repo.read_node(node)
        buf.insert( eob, "Revision: %d\n" % rev )
        buf.insert( eob, "Author: %s\n" %  repo.authors[author_id] )
        buf.create_mark( "begdesc", buf.get_start_iter() )
        
        for p in repo.parents(node):
            rev, desc, author_id, date_, log_, filelist, tags = repo.read_node(p)
            short = short_hex(p)
            buf.insert( eob, "Parent: %d:" % rev )
            buf.insert_with_tags_by_name( eob, short, "link" )
            buf.insert(eob, "(%s)\n" % desc)
        for p in repo.children(node):
            rev, desc, author_id, date_, log_, filelist, tags = repo.read_node(p)
            short = short_hex(p)
            buf.insert( eob, "Child:  %d:" % rev )
            buf.insert_with_tags_by_name( eob, short, "link" )
            buf.insert(eob, "(%s)\n" % desc)

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
        print "DIFF:", len(difflines)
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
        node, filelist = model.get( it, M_NODE,
                                    M_FILELIST )
        fulltext = self.repo.read_node(node)[4]
        textwidget = self.xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        textwidget.freeze_child_notify()
        text_buffer.set_text( "" )

        try:
            self.set_revlog_header( text_buffer, node )
            eob = text_buffer.get_end_iter()
            text_buffer.insert( eob, fulltext+"\n\n" )
            parent = self.repo.parents(node)[0]
            self.filelist.clear()
            enddesc = text_buffer.get_end_iter()
            enddesc.backward_line()
            text_buffer.create_mark( "enddesc", enddesc )
            self.filelist.append( ("Content", "begdesc", None ) )
            buff = self.repo.diff( parent, node, filelist )
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
            node = self.revisions.get( iter, M_NODE )
            rev, text, author_id, date_, log, files, tags = self.repo.read_node( node )
            author = self.repo.authors[author_id]
            if ( rexp.search( author ) or
                 rexp.search( log ) ):
                break
            for f in files:
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
        if dir_ == None:
            print "You are not in a repo, are you ?"
            sys.exit(1)

    filerex = None
    if opt.filename:
        filerex = "^" + re.escape( opt.filename ) + "$"
    elif opt.filerex:
        filerex = opt.filerex

    repo = HgHLRepo( dir_ )
    app = HgViewApp( repo, filerex )
    gtk.main()


if __name__ == "__main__":
    # remove current dir from sys.path
    if sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
