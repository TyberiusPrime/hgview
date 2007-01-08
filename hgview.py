
import gtk
import gtk.glade
import gobject
import sys, os
import time
from StringIO import StringIO
from mercurial import hg, ui, patch
import textwrap
import re

xml = gtk.glade.XML("hgview.glade")

dir_ = None
if len(sys.argv)>1:
    dir_ = sys.argv[1]
else:
    dir_ = os.getcwd()

filrex = None
if len(sys.argv)>2:
    filrex = sys.argv[2]

DIFFHDR = "-"*10 + " %s " + "-"*10 + "\n"

M_NODE = 1
M_SHORT_DESC = 2
M_AUTHOR = 3
M_DATE = 4
M_FULLDESC = 5
M_FILELIST = 6
class HgViewApp(object):

    def __init__(self, repodir, filerex = None ):
        self.dir = repodir
        self.ui = ui.ui()
        self.repo = hg.repository( self.ui, dir_ )
        if filerex:
            self.filerex = re.compile( filerex )
        else:
            self.filerex = None

        self.revisions = gtk.ListStore( gobject.TYPE_INT,
                                        gobject.TYPE_STRING,  # node
                                        gobject.TYPE_STRING,  # short description
                                        gobject.TYPE_STRING,  # author
                                        gobject.TYPE_STRING,  # date
                                        gobject.TYPE_STRING,  # full desc
                                        gobject.TYPE_PYOBJECT,  # file list
                                        )

        self.filelist = gtk.ListStore( gobject.TYPE_STRING, # filename
                                       gobject.TYPE_INT     # idx
                                       )

        self.setup_tags()
        self.setup_tree()
        self.refresh_tree()
        self.find_text = None

    def on_window_main_delete_event( self, win, evt ):
        print "BYE"
        gtk.main_quit()

    def on_quit1_activate( self, *args ):
        print "BYE", args
        gtk.main_quit()

    def setup_tags(self):
        textwidget = xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        tag_table = text_buffer.get_tag_table()
        
        blue_tag = gtk.TextTag("blue")
        blue_tag.set_property("foreground","blue")
        blue_tag.set_property("family", "Monospace")
        tag_table.add( blue_tag )
        
        red_tag = gtk.TextTag("red")
        red_tag.set_property("foreground","red")
        red_tag.set_property("family", "Monospace")
        tag_table.add( red_tag )

        green_tag = gtk.TextTag("green")
        green_tag.set_property("foreground","green")
        green_tag.set_property("family", "Monospace")
        tag_table.add( green_tag )

        black_tag = gtk.TextTag("black")
        black_tag.set_property("foreground","black")
        black_tag.set_property("family", "Monospace")
        tag_table.add( black_tag )

        greybg_tag = gtk.TextTag("greybg")
        greybg_tag.set_property("paragraph-background","grey")
        greybg_tag.set_property("family", "Monospace")
        #greybg_tag.set_property("justification", gtk.JUSTIFY_CENTER )
        tag_table.add( greybg_tag )

        yellowbg_tag = gtk.TextTag("yellowbg")
        yellowbg_tag.set_property("background", "yellow")
        tag_table.add( yellowbg_tag )

    def setup_tree(self):
        tree = xml.get_widget( "treeview_revisions" )
        tree.set_enable_search( True )
        tree.set_search_column( M_FULLDESC )
        tree.get_selection().connect("changed", self.selection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("ID", rend, text=0 )
        col.set_resizable(True)
        tree.append_column( col )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Log", rend, text=2 )
        col.set_resizable(True)
        tree.append_column( col )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Author", rend, text=3 )
        col.set_resizable(True)
        tree.append_column( col )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Date", rend, text=4 )
        col.set_resizable(True)
        tree.append_column( col )

        tree.set_model( self.revisions )

        # file tree
        tree = xml.get_widget( "treeview_filelist" )
        tree.set_rules_hint( 1 )
        tree.get_selection().connect("changed", self.fileselection_changed )

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Files", rend, text=0 )
        tree.append_column( col )

        tree.set_model( self.filelist )

    def refresh_tree(self):
        tree = xml.get_widget( "treeview_revisions" )
        tree.freeze_child_notify()
        self.revisions.clear()
        changelog = self.repo.changelog
        add_rev = self.revisions.append
        cnt = changelog.count()
        bar = cnt/10 or 1
        for i in xrange( cnt-1, -1, -1 ):
            node = changelog.node( i )
            id,author,date,filelist,log,unk = changelog.read( node )
            lines = log.strip().splitlines()
            if lines:
                text = "\n".join(textwrap.wrap( lines[0].strip() ))
            else:
                text = "*** no log"
            date_ = time.strftime( "%F %H:%M", time.gmtime( date[0] ) )

            if self.filerex:
                for f in filelist:
                    if self.filerex.search( f ):
                        break
                else:
                    continue
            add_rev( (i, node, text, author, date_, log, filelist ) )
            if (cnt-i) % bar == 0:
                print ".",
        tree.thaw_child_notify()

    def selection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        node = model.get_value( it, 1 )
#        info = self.repo.changelog.read( node )
        fulltext = model.get_value( it, M_FULLDESC )
        filelist = model.get_value( it, M_FILELIST )
        textwidget = xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        text_buffer.set_text( fulltext+"\n\n" )

        ctx = self.repo.changectx( node )
        parent = self.repo.parents(node)[0].node()
        self.filelist.clear()
        sob, eob = text_buffer.get_bounds()
        for idx,f in enumerate(filelist):
            self.filelist.append( (f,idx) )
            text_buffer.insert_with_tags_by_name(eob, DIFFHDR % f, "greybg" )
            pos = eob.copy()
            pos.backward_char()
            mark = text_buffer.create_mark( "file%d" % idx, pos )

            out = StringIO()
            patch.diff( self.repo, node1=node, node2=parent, files=[f], fp=out )
            for l in out.getvalue().splitlines():
                if l.startswith("+"):
                    tag="green"
                elif l.startswith("-"):
                    tag="red"
                else:
                    tag="black"
                text_buffer.insert_with_tags_by_name(eob, l+"\n", tag )

        if self.find_text:
            rexp = re.compile(self.find_text)
            sob, eob = text_buffer.get_bounds()
            txt = text_buffer.get_slice(sob, eob, True )
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
        val = model.get_value( it, 1 )
        markname = "file%d" % val
        tw = xml.get_widget("textview_status" )
        mark = tw.get_buffer().get_mark( markname )
        tw.scroll_to_mark( mark, .2, use_align=True, xalign=1., yalign=0. )

    def find_next_row( self, iter, rexp ):
        while iter:
            author, log, files = self.revisions.get( iter, M_AUTHOR, M_FULLDESC, M_FILELIST )
            if ( rexp.search( author ) or
                 rexp.search( log ) ):
                return iter
            for f in files:
                if rexp.search( f ):
                    return iter
            iter = self.revisions.iter_next( iter )


    def select_row( self, itr ):
        if itr is None:
            self.find_text = None
            return
        else:
            self.find_text = xml.get_widget( "entry_find" ).get_text()

        tree = xml.get_widget( "treeview_revisions" )
        sel = tree.get_selection()
        sel.select_iter( itr )
        path = self.revisions.get_path( itr )
        tree.scroll_to_cell( path, use_align=True, row_align=0.2 )

    def on_button_find_clicked( self, *args ):
        import re
        txt = xml.get_widget( "entry_find" ).get_text()
        sel = xml.get_widget( "treeview_revisions" ).get_selection()
        model, it = sel.get_selected()
        it = self.revisions.iter_next( it )
        it = self.find_next_row( it, re.compile( txt ) )
        self.select_row( it )
        
    def on_entry_find_changed( self, *args ):
        print "CHANGED", args
        import re
        txt = xml.get_widget( "entry_find" ).get_text()
        sel = xml.get_widget( "treeview_revisions" ).get_selection()
        model, it = sel.get_selected()
        it = self.find_next_row( it, re.compile( txt ) )
        self.select_row( it )

    def on_entry_find_activate( self, *args ):
        print "DONE"
        self.on_button_find_clicked()

app = HgViewApp( dir_, filrex )

xml.signal_autoconnect( app )

gtk.main()
