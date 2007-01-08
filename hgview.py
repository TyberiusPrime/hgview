
import gtk
import gtk.glade
import gobject
import sys, os
import time
from StringIO import StringIO
from mercurial import hg, ui, patch
import textwrap

xml = gtk.glade.XML("hgview.glade")

dir_ = None
if len(sys.argv)>1:
    dir_ = sys.argv[1]
else:
    dir_ = os.getcwd()


class HgViewApp(object):

    def __init__(self, repodir ):
        self.dir = repodir
        self.ui = ui.ui()
        self.repo = hg.repository( self.ui, dir_ )

        self.revisions = gtk.ListStore( gobject.TYPE_INT,
                                        gobject.TYPE_STRING,  # node
                                        gobject.TYPE_STRING,  # description
                                        gobject.TYPE_STRING,  # author
                                        gobject.TYPE_STRING,  # date
                                        )

        self.filelist = gtk.ListStore( gobject.TYPE_STRING, # filename
                                       gobject.TYPE_INT     # idx
                                       )

        self.setup_tags()
        self.setup_tree()
        self.refresh_tree()

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
        tag_table.add( green_tag )

        black_tag = gtk.TextTag("black")
        black_tag.set_property("foreground","black")
        black_tag.set_property("family", "Monospace")
        tag_table.add( black_tag )

        greybg_tag = gtk.TextTag("greybg")
        greybg_tag.set_property("paragraph-background","grey")
        #greybg_tag.set_property("justification", gtk.JUSTIFY_CENTER )
        tag_table.add( greybg_tag )

    def setup_tree(self):
        tree = xml.get_widget( "treeview_revisions" )

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
        changelog = self.repo.changelog
        add_rev = self.revisions.append
        for i in xrange( changelog.count()-1, -1, -1 ):
            node = changelog.node( i )
            id,author,date,filelist,log,unk = changelog.read( node )
            lines = log.strip().splitlines()
            if lines:
                text = "\n".join(textwrap.wrap( lines[0].strip() ))
            else:
                text = "*** no log"
            date_ = time.strftime( "%F %H:%M", time.gmtime( date[0] ) )
            add_rev( (i, node, text, author, date_ ) )


    def selection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        node = model.get_value( it, 1 )
        info = self.repo.changelog.read( node )
        self.update_rev_info( node, info )

    def update_rev_info( self, node, info ):
        fulltext = info[4]
        textwidget = xml.get_widget( "textview_status" )
        text_buffer = textwidget.get_buffer()
        text_buffer.set_text( fulltext+"\n\n" )

        ctx = self.repo.changectx( node )
        parent = self.repo.parents(node)[0].node()
        self.filelist.clear()
        sob, eob = text_buffer.get_bounds()
        for idx,f in enumerate(info[3]):
            self.filelist.append( (f,idx) )
            file_ctx = ctx.filectx( f )

            text_buffer.insert_with_tags_by_name(eob, f + "\n", "greybg" )
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


    def fileselection_changed( self, selection ):
        model, it = selection.get_selected()
        if it is None:
            return
        val = model.get_value( it, 1 )
        markname = "file%d" % val
        tw = xml.get_widget("textview_status" )
        mark = tw.get_buffer().get_mark( markname )
        tw.scroll_to_mark( mark, .2, use_align=True, xalign=1., yalign=0. )

app = HgViewApp( dir_ )

xml.signal_autoconnect( app )

gtk.main()
