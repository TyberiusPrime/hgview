# helper functions to ease hg revision graph building
from itertools import izip, count as icount
from StringIO import StringIO

from mercurial.node import nullrev
from mercurial import patch, util
from decorators import timeit

def diff(repo, ctx1, ctx2=None, files=None):
    if ctx2 is None:
        ctx2 = ctx1.parents()[0]
    if files is None:
        match = util.always
    else:
        def match(fn):
            return fn in files
    try:
        out = StringIO()        
        patch.diff(repo, ctx2.node(), ctx1.node(), match=match, fp=out)
        diff = out.getvalue()
    except:
        diff = '\n'.join(patch.diff(repo, ctx2.node(), ctx1.node(), match=match))
        
    try:
        diff = unicode(diff, "utf-8")
    except UnicodeError:
        # XXX use a default encoding from config
        diff = unicode(diff, "iso-8859-15", 'ignore')
    return diff

def __get_parents(repo, rev):
    return [x for x in repo.changelog.parentrevs(rev) if x != nullrev]

def revision_grapher(repo, start_rev=None, stop_rev=0, branch=None):
    """incremental revision grapher

    This generator function walks through the revision history from
    revision start_rev to revision stop_rev (which must be less than
    or equal to start_rev) and for each revision emits tuples with the
    following elements:

      - Current revision.
      - Column of the current node in the set of ongoing edges.
      - color of the node (?)
      - lines; a list of (col, next_col, color) indicating the edges between
        the current row and the next row
      - parent revisions of current revision

    """

    if start_rev is None:
        start_rev = repo.changelog.count()
        
    assert start_rev >= stop_rev
    curr_rev = start_rev
    revs = []
    rev_color = {}
    nextcolor = 0    
    while curr_rev >= stop_rev:
        # Compute revs and next_revs.
        if curr_rev not in revs:
            if branch:
                ctx = repo.changectx(curr_rev)
                if ctx.branch() != branch:
                    curr_rev -= 1
                    continue
            # New head.
            revs.append(curr_rev)
            rev_color[curr_rev] = curcolor = nextcolor
            nextcolor += 1
            r = __get_parents(repo, curr_rev)
            while r:
                r0 = r[0]
                if r0 < stop_rev: break
                if r0 in rev_color: break
                rev_color[r0] = curcolor
                r = __get_parents(repo, r0)
        curcolor = rev_color[curr_rev]            
        rev_index = revs.index(curr_rev)
        next_revs = revs[:]

        # Add parents to next_revs.
        parents = __get_parents(repo, curr_rev)
        parents_to_add = []
        preferred_color = curcolor
        for parent in parents:
            if parent not in next_revs:
                parents_to_add.append(parent)
                if parent not in rev_color:
                    if preferred_color:
                        rev_color[parent] = preferred_color
                        preferred_color = None
                    else:
                        rev_color[parent] = nextcolor
                        nextcolor += 1

        #parents_to_add.sort()
        next_revs[rev_index:rev_index + 1] = parents_to_add

        lines = []
        for i, rev in enumerate(revs):
            if rev in next_revs:
                color = rev_color[rev]
                lines.append( (i, next_revs.index(rev), color) )
            elif rev == curr_rev:
                for parent in parents:
                    color = rev_color[parent]
                    lines.append( (i, next_revs.index(parent), color) )

        yield (curr_rev, rev_index, curcolor, lines, parents)
        revs = next_revs
        curr_rev -= 1


class GraphNode(object):
    def __init__(self, rev, xposition, color, lines, parents, ncols=None):
        self.rev = rev
        self.x = xposition
        self.color = color
        if ncols is None:
            ncols = len(lines)
        self.cols = ncols
        self.parents = parents
        self.lines = lines
        
class Graph(object):
    @timeit
    def __init__(self, repo):
        self.repo = repo
        self.grapher = revision_grapher(self.repo)
        self.nodes = []
        self.nodesdict = {}
        self.max_cols = 0
        
    def _build_nodes(self, idx):
        if idx < len(self.nodes):
            return
        if self.grapher is None:
            return
        
        stopped = False
        mcol = [self.max_cols]
        while not stopped and len(self.nodes) <= idx:
            try:
                nrev, xpos, color, lines, parents = self.grapher.next()
                gnode = GraphNode(nrev, xpos, color, lines, parents)
                self.nodes.append(gnode)
                self.nodesdict[nrev] = gnode
                mcol.append(gnode.cols)
            except StopIteration:
                self.grapher = None
                stopped = True
        self.max_cols = max(mcol)
        return not stopped

    def fill(self, step=10):
        i = 0
        while self._build_nodes(i+step):
            i += step
            yield i
        yield len(self)
        
    def __getitem__(self, idx):
        if idx >= len(self.nodes):
            self._build_nodes(idx)
        return self.nodes[idx]

    def __len__(self):
        try:
            return self.repo.changelog.count()
        except AttributeError:
            return len(self.repo.changelog)
        

if __name__ == "__main__":
    import sys
    from mercurial import ui, hg
    u = ui.ui()
    r = hg.repository(u, sys.argv[1])
    g = Graph(r)
    
