# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

"""helper functions and classes to ease hg revision graph building

Based on graphlog's algorithm, with insipration stolen to TortoiseHg
revision grapher.
"""

from StringIO import StringIO

from mercurial.node import nullrev
from mercurial import patch, util

import hgview # force apply monkeypatches

#from hgview.decorators import timeit

def diff(repo, ctx1, ctx2=None, files=None):
    """
    Compute the diff of files between 2 changectx
    """
    if ctx2 is None:
        ctx2 = ctx1.parents()[0]
    if files is None:
        match = util.always
    else:
        def match(fn):
            return fn in files
    # try/except for the sake of hg compatibility (API changes between
    # 1.0 and 1.1)
    try:
        out = StringIO()        
        patch.diff(repo, ctx2.node(), ctx1.node(), match=match, fp=out)
        diffdata = out.getvalue()
    except:
        diffdata = '\n'.join(patch.diff(repo, ctx2.node(), ctx1.node(),
                                        match=match))
    # XXX how to deal diff encodings?
    try:
        diffdata = unicode(diffdata, "utf-8")
    except UnicodeError:
        # XXX use a default encoding from config?
        diffdata = unicode(diffdata, "iso-8859-15", 'ignore')
    return diffdata


def __get_parents(repo, rev, branch=None):
    """
    Return non-null parents of `rev`. If branch is given, only return
    parents that belongs to names branch `branch` (beware that this is
    much slower).
    """
    if not branch:
        return [x for x in repo.changelog.parentrevs(rev) if x != nullrev]
    return [x for x in repo.changelog.parentrevs(rev) \
            if (x != nullrev and repo.changectx(rev).branch() == branch)]
    

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
        start_rev = len(repo.changelog)
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
                    yield None
                    continue
            # New head.
            revs.append(curr_rev)
            rev_color[curr_rev] = curcolor = nextcolor
            nextcolor += 1
            r = __get_parents(repo, curr_rev, branch)
            while r:
                r0 = r[0]
                if r0 < stop_rev or r0 in rev_color:
                    break
                rev_color[r0] = curcolor
                r = __get_parents(repo, r0, branch)
        curcolor = rev_color[curr_rev]            
        rev_index = revs.index(curr_rev)
        next_revs = revs[:]

        # Add parents to next_revs.
        parents = __get_parents(repo, curr_rev, branch)
        parents_to_add = []
        if len(parents) > 1:
            preferred_color = None
        else:            
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
            preferred_color = None
                
        # parents_to_add.sort()
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

def filelog_grapher(repo, path):
    '''
    Graph the ancestry of a single file (log).  Deletions show
    up as breaks in the graph.
    '''
    filerev = len(repo.file(path)) - 1
    revs = []
    rev_color = {}
    nextcolor = 0
    while filerev >= 0:
        fctx = repo.filectx(path, fileid=filerev)

        # Compute revs and next_revs.
        if filerev not in revs:
            revs.append(filerev)
            rev_color[filerev] = nextcolor ; nextcolor += 1
        curcolor = rev_color[filerev]
        index = revs.index(filerev)
        next_revs = revs[:]

        # Add parents to next_revs.
        parents = [f.filerev() for f in fctx.parents() if f.path() == path]
        parents_to_add = []
        for parent in parents:
            if parent not in next_revs:
                parents_to_add.append(parent)
                if len(parents) > 1:
                    rev_color[parent] = nextcolor ; nextcolor += 1
                else:
                    rev_color[parent] = curcolor
        parents_to_add.sort()
        next_revs[index:index + 1] = parents_to_add

        lines = []
        for i, rev in enumerate(revs):
            if rev in next_revs:
                color = rev_color[rev]
                lines.append( (i, next_revs.index(rev), color) )
            elif rev == filerev:
                for parent in parents:
                    color = rev_color[parent]
                    lines.append( (i, next_revs.index(parent), color) )

        pcrevs = [pfc.rev() for pfc in fctx.parents()]
        yield (fctx.rev(), index, curcolor, lines, pcrevs)
        revs = next_revs
        filerev -= 1


class GraphNode(object):
    """
    Simple class to encapsulate e hg node in the revision graph. Does
    nothing but declaring attributes.
    """
    def __init__(self, rev, xposition, color, lines, parents, ncols=None):
        self.rev = rev
        self.x = xposition
        self.color = color
        if ncols is None:
            ncols = len(lines)
        self.cols = ncols
        self.parents = parents
        self.bottomlines = lines
        self.toplines = []
        
class Graph(object):
    """
    Graph object to ease hg repo navigation. The Graph object
    instanciate a `revision_grapher` generator, and provide a `fill`
    method to build the graph progressively.
    """
    #@timeit
    def __init__(self, repo, grapher):
        self.repo = repo
        self.maxlog = len(self.repo.changelog)
        self.grapher = grapher
        self.nodes = []
        self.nodesdict = {}
        self.max_cols = 0
        
    def _build_nodes(self, nnodes):
        """Internal method.
        Build `nnodes` more nodes in our graph. 
        """
        if self.grapher is None:
            return False
        
        stopped = False
        mcol = [self.max_cols]
        for _ in xrange(nnodes):
            try:
                v = self.grapher.next()
                if v is None:
                    continue
                nrev, xpos, color, lines, parents = v
                if nrev >= self.maxlog:
                    continue
                gnode = GraphNode(nrev, xpos, color, lines, parents)
                if self.nodes:
                    gnode.toplines = self.nodes[-1].bottomlines
                self.nodes.append(gnode)
                self.nodesdict[nrev] = gnode
                mcol.append(gnode.cols)
            except StopIteration:                
                self.grapher = None
                stopped = True
                break
            
        self.max_cols = max(mcol)
        return not stopped

    def fill(self, step=100):
        """
        Return a generator that fills the graph by bursts of `step`
        more nodes at each iteration.
        """
        while self._build_nodes(step):
            yield len(self)
        yield len(self)
        
    def __getitem__(self, idx):
        if idx >= len(self.nodes):
            # build as many graph nodes as required to answer the
            # requested idx
            self._build_nodes(idx)
        if idx > len(self):
            print "ARGHH, ", idx, len(self)
            import traceback
            traceback.print_stack()
            return self.nodes[-1]
            return None
        return self.nodes[idx]

    def __len__(self):
        # len(graph) is the number of actually built graph nodes
        return max(len(self.nodes), 0)

        
if __name__ == "__main__":
    # pylint: disable-msg=C0103
    import sys
    from mercurial import ui, hg
    u = ui.ui()
    r = hg.repository(u, sys.argv[1])
    if len(sys.argv) == 3:
        rg = filelog_grapher(r, sys.argv[2])
    else:
        rg = revision_grapher(r)
    g = Graph(r, rg)
    
