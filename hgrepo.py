
import os
from mercurial import hg, ui, patch
from mercurial.node import short as short_hex, bin as short_bin
from mercurial.node import nullid
from buildtree import RevGraph
from StringIO import StringIO
import textwrap
import time

# A default changelog_cache node
EMPTY_NODE = (-1,  # REV num
              "",  # short desc
              -1,  # author ID
              "",  # full log
              "",  # Date
              (),  # file list
              [],  # tags
              )

def timeit( f ):
    """Decorator used to time the execution of a function"""
    def timefunc( *args, **kwargs ):
        """wrapper"""
        t1 = time.time()
        t2 = time.clock()
        res = f(*args, **kwargs)
        t3 = time.clock()
        t4 = time.time()
        print f.func_name, t3 - t2, t4 - t1
        return res
    return timefunc

COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", "magenta" ]

class HgHLRepo(object):
    """high level operation on a mercurial repo
    """
    def __init__(self, path):
        self.dir = self.find_repository( path )
        self.ui = ui.ui()
        self.repo = hg.repository( self.ui, self.dir )
        # cache and indexing of changelog
        self.changelog_cache = {}
        self.authors = []
        self.logs = []
        self.files = []
        self.colors = []
        self.nodes = []

    def find_repository(self, path):
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


    def read_nodes(self):
        """Read the nodes of the changelog"""
        changelog = self.repo.changelog
        cnt = changelog.count()
        self.nodes = [ changelog.node(i) for i in xrange(cnt) ]
        self.changelog_cache = {}
        self.authors = []
        self.colors = []
        self.authors_dict = {}
    read_nodes = timeit(read_nodes)

    def get_short_log( self, log ):
        """Compute a short log from the full revision log"""
        lines = log.strip().splitlines()
        if lines:
            text = lines[0].strip()
        else:
            text = "*** no log"
        return text

    def read_node( self, node ):
        """Gather revision information from mercurial"""
        nodeinfo = self.changelog_cache
        if node in nodeinfo:
            return nodeinfo[node]
        NCOLORS = len(COLORS)
        changelog = self.repo.changelog
        _, author, date, filelist, log, _ = changelog.read( node )
        rev = changelog.rev( node )
        aid = len(self.authors)
        author_id = self.authors_dict.setdefault( author, aid )
        if author_id == aid:
            self.authors.append( author )
            self.colors.append( COLORS[aid%NCOLORS] )
        filelist = [ intern(f) for f in filelist ]
        text = self.get_short_log( log )
        date_ = time.strftime( "%F %H:%M", time.gmtime(date[0]) )
        taglist = self.repo.nodetags(node)
        tags = ", ".join(taglist)
        filelist = tuple(filelist)
        _node = (rev, text, author_id, date_, log, filelist, tags)
        nodeinfo[node] = _node
        return _node

    def graph( self, todo_nodes ):
        return RevGraph( self.repo, todo_nodes, self.nodes )

    def parents( self, node ):
        return [ n for n in self.repo.changelog.parents(node) if n!=nullid ]

    def children( self, node ):
        return [ n for n in self.repo.changelog.children( node ) if n!=nullid ]
    def diff( self, node1, node2, files ):
        out = StringIO()
        patch.diff( self.repo, node1=node1,
                    node2=node2, files=files, fp=out )
        return out.getvalue()

    def count( self ):
        return self.repo.changelog.count()
