# helper functions to ease hg revision graph building
from itertools import izip, count as icount
from StringIO import StringIO

from mercurial.node import nullrev
from mercurial import patch, util
from decorators import timeit

def diff(repo, ctx1, ctx2=None, files=None):
    out = StringIO()
    if ctx2 is None:
        ctx2 = ctx1.parents()[0]
    if files is None:
        match = util.always
    else:
        def match(fn):
            return fn in files
    diff = patch.diff(repo, ctx1.node(), ctx2.node(), match=match, fp=out)
    diff = out.getvalue()
    try:
        diff = unicode(diff, "utf-8")
    except UnicodeError:
        # XXX use a default encoding from config
        diff = unicode(diff, "iso-8859-15", 'ignore')
    return diff

def revision_grapher(repo, start_rev, stop_rev):
    """incremental revision grapher

    This generator function walks through the revision history from
    revision start_rev to revision stop_rev (which must be less than
    or equal to start_rev) and for each revision emits tuples with the
    following elements:

      - Current revision.
      - Current node.
      - Column of the current node in the set of ongoing edges.
      - Edges; a list of (col, next_col) indicating the edges between
        the current node and its parents.
      - Number of columns (ongoing edges) in the current revision.
      - The difference between the number of columns (ongoing edges)
        in the next revision and the number of columns (ongoing edges)
        in the current revision. That is: -1 means one column removed;
        0 means no columns added or removed; 1 means one column added.
    """

    assert start_rev >= stop_rev
    curr_rev = start_rev
    revs = []
    while curr_rev >= stop_rev:
        node = repo.changelog.node(curr_rev)

        # Compute revs and next_revs.
        if curr_rev not in revs:
            # New head.
            revs.append(curr_rev)
        rev_index = revs.index(curr_rev)
        next_revs = revs[:]

        # Add parents to next_revs.
        parents = get_rev_parents(repo, curr_rev)
        parents_to_add = []
        for parent in parents:
            if parent not in next_revs:
                parents_to_add.append(parent)
        parents_to_add.sort()
        next_revs[rev_index:rev_index + 1] = parents_to_add

        edges = []
        for parent in parents:
            edges.append((rev_index, next_revs.index(parent), curr_rev, parent))

        n_columns_diff = len(next_revs) - len(revs)
        yield (curr_rev, node, rev_index, edges, len(revs), n_columns_diff)

        revs = next_revs
        curr_rev -= 1

def get_rev_parents(repo, rev):
    return [x for x in repo.changelog.parentrevs(rev) if x != nullrev]


def build_children(repo):
    """
    Function that builds 2 lists of lists:

    - the list of children
    - the list of parents

    Lists indexes are revisions.
    """
    children = []
    parents = []
    nnodes = repo.changelog.count()
    children = [[] for i in xrange(nnodes)]
    parents = [get_rev_parents(repo, i) for i in xrange(nnodes)]
    for i, prts in enumerate(parents):
        for p in prts:
            children[p].append(i)
    return children, parents

def nodes_of_graph(children, parents):
    """
    Function that extracts nodes of the revision graph that are 'real'
    graph nodes (ie nodes that do have more than one child or parent).

    Returns list of revisions that are real nodes/
    """
    revs = []
    for i, p, c in izip(icount(), parents, children):
        if len(p) != 1 or len(c) != 1:
            revs.append(i)
    return revs

@timeit
def build_graph(repo=None, children=None, parents=None):
    """
    Extract the revision graph.

    The graph is a list of couples (key, value) which keys are couples of revision
    (from, to), and values are lists of nodes belonging to the branch
    defined by the key.
    """
    if parents is None:        
        children, parents = build_children(repo)
    revs = nodes_of_graph(children, parents)
    graph = []
    for rev in revs:
        for p in parents[rev]:
            br = []
            while p not in revs:
                br.append(p)
                if not parents[p]:
                    break
                p = parents[p][0]
            br.reverse()
            graph.append(((p, rev), br))
            #graph.setdefault((p, rev), []).append(br)
    return graph

class GraphNode(object):
    def __init__(self, rev, xposition, edges, ncols, delta):
        self.rev = rev
        self.x = xposition
        self.cols = ncols
        self.dx = delta
        self.edges = set(edges)
        self.lines = set([])
        self.color = {}
        
class Graph(object):
    @timeit
    def __init__(self, repo):
        self.repo = repo
        self.children, self.parents = build_children(self.repo)
        self.graph = _build_graph(self.repo)
        rawgraph = build_graph(self.repo, self.children, self.parents)
        self.rawgraph = rawgraph
        self.revrawgraph = _build_revgraph(rawgraph)
        self.nodes = []
        self.nodesdict = {}
        for rev, _, x, edges, ncols, delta in self.graph:
            self.nodes.append(GraphNode(rev, x, edges, ncols, delta))
            self.nodesdict[rev] = self.nodes[-1]
        self._brcolor = 0
        self._built = 0

    def _build_lines(self, torev=None):
        torev = min(torev, len(self.nodes)-2)
        for i in range(self._built+1, torev+1):
            gn0 = self.nodes[i-1]
            gn = self.nodes[i]
            gn1 = self.nodes[i+1]

            for col, colnext, srcrev, dstrev in gn.edges:
                if (col, colnext) in gn.color:
                    color = gn.color[(col, colnext)]
                else:
                    if col == gn.x and gn.rev not in self.revrawgraph:
                        self._brcolor += 1
                        color = self._brcolor
                    else:
                        for (c1, c2), color2 in gn0.color.items():
                            if c2 == col:
                                color = color2
                                break
                    gn.color[(col, colnext)] = color
                gn.lines.add((col, 0, colnext, 1, color))
                gn1.lines.add((col, -1, colnext, 0, color))
                if (col + gn.dx) == colnext:
                    if col < gn1.x:
                        gn1.edges.add((colnext, colnext, None, None))
                        gn1.color[(colnext, colnext)] = color
                    elif colnext != gn1.x:
                        gn1.edges.add((colnext, colnext + gn1.dx, None, None))
                        gn1.color[(colnext, colnext + gn1.dx)] = color
                elif colnext < gn1.x:
                    gn1.edges.add((colnext, colnext, None, None))
                    gn1.color[(colnext, colnext)] = color
                elif colnext > gn1.x:
                    gn1.edges.add((colnext, colnext + gn1.dx, None, None))
                    gn1.color[(colnext, colnext + gn1.dx)] = color
        self._built = torev

    def __getitem__(self, idx):
        if idx > self._built:
            # build lines by burst of 10 revisions
            self._build_lines(idx+10)
        return self.nodes[idx]
        
@timeit
def _build_graph(repo, start_rev=None, stop_rev=0):
    if start_rev is None:
        start_rev = repo.changelog.count()
    graph = list(revision_grapher(repo, start_rev, stop_rev))
    return graph

def _build_revgraph(rawgraph):
    revg = {}
    for i, (branchendings, branchrevs) in enumerate(rawgraph):
        for rev in branchrevs:
            revg[rev] = i#branchendings
    return revg

if __name__ == "__main__":
    import sys
    from mercurial import ui, hg
    u = ui.ui()
    r = hg.repository(u, sys.argv[1])
    g = Graph(r)
    
