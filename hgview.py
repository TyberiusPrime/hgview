
import gtk
import gtk.glade
import gobject
import pango
import sys, os
import time
from StringIO import StringIO
from mercurial import hg, ui, patch
import textwrap
import re
from buildtree import RevGraph
from graphrenderer import RevGraphRenderer

GLADE_FILE_NAME = "hgview.glade"
GLADE_FILE_LOCATIONS = [ '/usr/share/hgview' ]

# monkeypatch hg.util.tolocal since we really want utf-8 for gtk
def tolocal(s):
    return s
import mercurial.util
mercurial.util.tolocal = tolocal

def load_glade():
    """Try several paths in which the glade file might be found"""
    mod = sys.modules[__name__]
    # Try this module's dir first (dev case)
    _basedir = os.path.dirname(mod.__file__)

    test_dirs = [_basedir] + GLADE_FILE_LOCATIONS
    for dirname in test_dirs:
        glade_file = os.path.join(dirname, GLADE_FILE_NAME)
        if os.path.exists(glade_file):
            return gtk.glade.XML( glade_file )

    raise ImportError("Couldn't find %s in (%s)" % (GLADE_FILE_NAME,
                                                    ",".join( "'%s'" % f for f in dirname ) ) )

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


DIFFHDR = "=== %s ===\n"

M_NODE = 1
M_SHORTDESC = 2
M_AUTHOR = 3
M_DATE = 4
M_FILELIST = 5
M_NODEX = 6
M_EDGES = 7
M_TAGS = 8

COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple", "cyan", "magenta" ]

def make_texttag( name, **kwargs ):
    """Helper function generating a TextTag"""
    tag = gtk.TextTag(name)
    for key, value in kwargs.items():
        key=key.replace("_","-")
        tag.set_property( key, value )
    return tag


class HgViewApp(object):
    def __init__(self, repodir, filerex = None ):
        self.xml = load_glade()
        self.xml.signal_autoconnect( self )
        self.dir = repodir
        self.ui = ui.ui()
        self.repo = hg.repository( self.ui, repodir )
        if filerex:
            self.filerex = re.compile( filerex )
        else:
            self.filerex = None
        # cache and indexing of changelog
        self.changelog_cache = {}
        self.authors = []
        self.logs = []
        self.files = []
        self.colors = []
        self.revisions = gtk.ListStore( gobject.TYPE_INT,
                                        gobject.TYPE_PYOBJECT, # node (stored as python strings)
                                                               # because they can contain zeroes
                                        gobject.TYPE_STRING,   # short description
                                        gobject.TYPE_INT,      # author
                                        gobject.TYPE_STRING,   # date
                                        gobject.TYPE_PYOBJECT, # file list
                                        gobject.TYPE_PYOBJECT, # x for the node
                                        gobject.TYPE_PYOBJECT, # lines for nodes
                                        gobject.TYPE_STRING,   # tag
                                        )

        self.filelist = gtk.ListStore( gobject.TYPE_STRING, # filename
                                       gobject.TYPE_STRING  # markname
                                       )

        self.setup_tags()
        self.graph = None
        self.setup_tree()
        self.read_changelog()
        self.refresh_tree()
        self.find_text = None

    def read_changelog(self):
        aid = 0
        fid = 0
        self.changelog_cache = {}
        authors = {}
        changelog = self.repo.changelog
        nodeinfo = self.changelog_cache
        cnt = changelog.count()
        bar = cnt/10 or 1
        nodes = [None]*cnt
        self.nodes = nodes
        t1 = time.clock()
        print "Retrieving changelog"
        for i in xrange(cnt):
            if (i+1) % bar == 0:
                print ".",
                sys.stdout.flush()
            node = changelog.node( i )
            nodes[i] = node
            id,author,date,filelist,log,unk = changelog.read( node )
            author_id = authors.setdefault( author, aid )
            if author_id == aid:
                aid+=1
            filelist = [ intern(f) for f in filelist ]
            lines = log.strip().splitlines()
            if lines:
                text = lines[0].strip()
            else:
                text = "*** no log"
            date_ = time.strftime( "%F %H:%M", time.gmtime( date[0] ) )
            taglist = self.repo.nodetags( node )
            tags = ", ".join( taglist )
            nodeinfo[node] = (i, text, author_id, date_, log, tuple(filelist), tags )
        # create authors index
        # real plan is to allow the user to configure user groups and assign
        # colors to them; groups, colors & co would be saved in $HOME/.hgviewrc
        # and/or .hg/hgviewrc
        _a = self.authors = [None]*len(authors)
        _c = self.colors =  [None]*len(authors)
        colidx = 0
        for k,v in authors.iteritems():
            _a[v]=k
            _c[v]=COLORS[colidx]
            colidx+=1
            if colidx % len(COLORS)==0:
                colidx = 0
        t2 = time.clock()
        print "done in", t2-t1

    def filter_nodes(self):
        nodeinfo = self.changelog_cache
        if not self.filerex:
            return [ (node,nodeinfo[node][5]) for node in self.nodes ]
        # build set of matching file names
        filelist = set()
        for _id, f in enumerate(self.files):
            if self.filerex.search( f ):
                filelist.add( _id )
        # build list of matching nodes
        keepnodes = []
        for n in self.nodes:
            t = nodeinfo[n]
            nodefiles = set(t[5])
            # matching files in alphabetical order first
            matching = sorted(filelist.intersection(nodefiles),
                              key=lambda v:self.files[v])
            if not matching:
                continue
            notmatching = sorted(nodefiles.difference(filelist),
                              key=lambda v:self.files[v])
            filelist = matching + notmatching
            keepnodes.append( (node,filelist) )
        return keepnodes

    def on_window_main_delete_event( self, win, evt ):
        gtk.main_quit()

    def on_quit1_activate( self, *args ):
        gtk.main_quit()

    def setup_tags(self):
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


    def author_data_func( self, column, cell, model, iter, user_data=None ):
        author_id = model.get_value( iter, M_AUTHOR )
        cell.set_property( "text", self.authors[author_id] )
        cell.set_property( "foreground", self.colors[author_id] )

    def setup_tree(self):
        tree = self.xml.get_widget( "treeview_revisions" )
        tree.get_selection().connect("changed", self.selection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("ID", rend, text=0 )
        #col.set_resizable(True)
        tree.append_column( col )

        rend = RevGraphRenderer()
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

        # file tree
        tree = self.xml.get_widget( "treeview_filelist" )
        tree.set_rules_hint( 1 )
        tree.get_selection().connect("changed", self.fileselection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Files", rend, text=0 )
        tree.append_column( col )

        tree.set_model( self.filelist )

    def refresh_tree(self):
        tree = self.xml.get_widget( "treeview_revisions" )
        nodeinfo = self.changelog_cache
        print "Computing graph..."
        graph = RevGraph( self.repo, self.nodes, self.nodes )
        print "done"        
        rowselected = [None]*len(self.nodes)
        for node, n in graph.idrow.items():
            if node in nodeinfo:
                rowselected[n] = node
        # detaching the model prevents notifications and updates of view
        print "Filling model"
        t1 = time.clock()
        tree.set_model(None)
        self.revisions.clear()
        add_rev = self.revisions.append
        for n, node in enumerate(rowselected):
            if node is None:
                continue
            (i, text, author, date_, log, filelist, tags ) = nodeinfo[node]
            lines = []
            for x1,y1,x2,y2 in graph.rowlines[n]:
                if not rowselected[y1] or not rowselected[y2]:
                    continue
                lines.append( (x1,y1-n,x2,y2-n) )
            add_rev( (i, node, text, author, date_, filelist, graph.x[node], lines, tags ) )
        print "Done in", time.clock()-t1
        tree.set_model(self.revisions)
        tree.set_fixed_height_mode( True )


    def get_revlog_header( self, node ):
        pass

    def selection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        node, filelist = model.get( it, M_NODE,
                                    M_FILELIST )
        fulltext = self.changelog_cache[node][4]
        textwidget = self.xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        textwidget.freeze_child_notify()
        try:
            hdr = self.get_revlog_header( node )
            text_buffer.set_text( fulltext+"\n\n" )
            parent = self.repo.parents(node)[0].node()
            self.filelist.clear()
            sob, eob = text_buffer.get_bounds()
            enddesc = eob.copy()
            enddesc.backward_line()
            text_buffer.create_mark( "enddesc", enddesc )
            text_buffer.create_mark( "begdesc", sob )
            self.filelist.append( ("Content", "begdesc" ) )
            try:
                out = StringIO()
                patch.diff(self.repo, node1=parent, node2=node,
                           files=filelist, fp=out)
                it = iter(out.getvalue().splitlines())
                idx = 0
                for l in it:
                    if l.startswith("diff"):
                        f = l.split()[-1]
                        text_buffer.insert_with_tags_by_name(eob,
                                                             DIFFHDR % f, "greybg")
                        pos = eob.copy()
                        pos.backward_line()
                        markname = "file%d" % idx
                        idx += 1
                        mark = text_buffer.create_mark( markname, pos )
                        self.filelist.append( (f, markname) )
                        it.next()
                        it.next()
                        continue
                    elif l.startswith("+"):
                        tag="green"
                    elif l.startswith("-"):
                        tag="red"
                    elif l.startswith("@@"):
                        tag="blue"
                    else:
                        tag="black"
                    text_buffer.insert_with_tags_by_name(eob, l+"\n", tag )
            except:
                # continue
                raise
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
        enddesc = text_buffer.get_iter_at_mark(text_buffer.get_mark( "enddesc" ))
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
        txt = self.xml.get_widget( "entry_find" ).get_text()
        rexp = re.compile( txt )
        while iter != stop_iter:
            node, author, files = self.revisions.get( iter, M_NODE, M_AUTHOR,
                                                     M_FILELIST )
            log = self.changelog_cache[node][4]
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
        if iter==stop_iter:
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
        model, it = self.get_selected_rev()
        it = self.revisions.iter_next( it )
        start_it = it
        res = self.find_next_row( it )
        if res is None:
            self.find_next_row( self.revisions.get_iter_first(), start_it )

    def on_entry_find_changed( self, *args ):
        model, it = self.get_selected_rev()
        start_it = it
        res = self.find_next_row( it )
        if res is None:
            self.find_next_row( self.revisions.get_iter_first(), start_it )

    def on_entry_find_activate( self, *args ):
        self.on_button_find_clicked()


def main():
    # TODO: either do proper option handling or make
    # this an hg extension
    dir_ = None
    if len(sys.argv)>1:
        dir_ = sys.argv[1]
    else:
        dir_ = find_repository(os.getcwd())
    
    filrex = None
    if len(sys.argv)>2:
        filrex = sys.argv[2]
    
    app = HgViewApp( dir_, filrex )
    
    
    gtk.main()


if __name__ == "__main__":
    main()
