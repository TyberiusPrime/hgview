
import os
from mercurial import hg, ui, patch
from mercurial.node import short as short_hex, bin as short_bin
from mercurial.node import nullid
from buildtree import RevGraph
from StringIO import StringIO
import textwrap
import time


class RevNode(object):
    __slots__ = "rev author_id desc gmtime files tags".split()
    def __init__(self,rev, author_id, desc, date,
                 files, tags):
        self.rev = rev
        self.author_id = author_id
        self.desc = desc.strip()+"\n"
        self.gmtime = date
        self.files = tuple(files)
        self.tags = tags

    def get_short_log( self ):
        """Compute a short log from the full revision log"""
        offs = self.desc.find('\n')
        if offs>0:
            text = self.desc[:offs]
        else:
            text = "*** no log"
        return text
    short = property(get_short_log)

    def get_date( self ):
        date_ = time.strftime( "%F %H:%M", self.gmtime )
        return date_
    date = property(get_date)

class Repository(object):
    """Abstract interface for a repository"""
    def __init__(self, path):
        """path : path of repository"""
        self.dir = self.find_repository( path )
        # The list of authors names
        self.authors = []
        # colors for the authors (need to get out of here)
        self.colors = []
        # the list of nodes
        self.nodes = []

    def find_repository(cls, path):
        """finds the root repository or raises
        its a class method so one can use it to find
        the best (closest to path) repo for a given
        type of repository
        """
        raise NotImplementedError()
    find_repository = classmethod( find_repository )


    def read_node( self, nodeid ):
        """Returns the node's attributes as RevNode instance"""
        raise NotImplementedError()

    def parents( self, node ):
        """Returns a list of parents' ids for the node"""
        raise NotImplementedError()

    def children( self, node ):
        """Returns a list of children's ids for the node"""
        raise NotImplementedError()

    def diff( self, node1, node2, files ):
        """Returns a diff between node1 and node2 for the
        files listed in files"""
        raise NotImplementedError()

    def count( self ):
        """Returns the number of nodes"""
        raise NotImplementedError()

    def graph( self, nodes ):
        """Returns a graph object allowing representation
        of the tree of revisions reduced to 'nodes'
        """

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
        self._cache = {}

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
    find_repository = classmethod( find_repository )

    def read_nodes(self):
        """Read the nodes of the changelog"""
        changelog = self.repo.changelog
        cnt = changelog.count()
        self.nodes = [ changelog.node(i) for i in xrange(cnt) ]
        self._cache = {}
        self.authors = []
        self.colors = []
        self.authors_dict = {}
    read_nodes = timeit(read_nodes)


    def read_node( self, node ):
        """Gather revision information from mercurial"""
        nodeinfo = self._cache
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
        date_ = time.gmtime(date[0])
        taglist = self.repo.nodetags(node)
        tags = ", ".join(taglist)
        _node = RevNode(rev, author_id, log, date_, filelist, tags)
        nodeinfo[node] = _node
        return _node

    def graph( self, todo_nodes ):
        return RevGraph( self.repo, todo_nodes, self.nodes )

    def parents( self, node ):
        parents = [ n for n in self.repo.changelog.parents(node) if n!=nullid ]
        if not parents:
            parents = [nullid]
        return parents

    def children( self, node ):
        return [ n for n in self.repo.changelog.children( node ) if n!=nullid ]
    
    def diff( self, node1, node2, files ):
        out = StringIO()
        patch.diff( self.repo, node1=node1,
                    node2=node2, files=files, fp=out )
        return out.getvalue()

    def count( self ):
        return self.repo.changelog.count()
