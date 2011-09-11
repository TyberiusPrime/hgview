# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
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

from cStringIO import StringIO
import difflib
from itertools import chain

from mercurial.node import nullrev
from mercurial import patch, util, match, error, hg

import hgviewlib # force apply monkeypatches
from hgviewlib.util import tounicode, isbfile
from hgviewlib.config import HgConfig

def diff(repo, ctx1, ctx2=None, files=None):
    """
    Compute the diff of files between 2 changectx
    """
    if ctx2 is None:
        ctx2 = ctx1.parents()[0]
    if files is None:
        m = match.always(repo.root, repo.getcwd())
    else:
        m = match.exact(repo.root, repo.getcwd(), files)
    # try/except for the sake of hg compatibility (API changes between
    # 1.0 and 1.1)
    try:
        out = StringIO()
        patch.diff(repo, ctx2.node(), ctx1.node(), match=m, fp=out)
        diffdata = out.getvalue()
    except:
        diffdata = '\n'.join(patch.diff(repo, ctx2.node(), ctx1.node(),
                                        match=m))
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
        if rev is None:
            return [x.rev() for x in repo.changectx(None).parents() if x]
        return [x for x in repo.changelog.parentrevs(rev) if x != nullrev]
    if rev is None:
        return [x.rev() for x in repo.changectx(None).parents() \
                if x and repo.changectx(rev).branch() == branch]
    return [x for x in repo.changelog.parentrevs(rev) \
            if (x != nullrev and repo.changectx(rev).branch() == branch)]

def getlog(model, ctx, gnode):
    if ctx.rev() is not None:
        msg = tounicode(ctx.description())
        if msg:
            msg = msg.splitlines()[0]
    else:
        msg = "WORKING DIRECTORY (locally modified)"
    return msg

def gettags(model, ctx, gnode):
    if ctx.rev() is None:
        return ""
    mqtags = ['qbase', 'qtip', 'qparent']
    tags = ctx.tags()
    if model.hide_mq_tags:
        tags = [t for t in tags if t not in mqtags]
    return ",".join(tags)

def ismerge(ctx):
    """
    Return True if the changecontext ctx is a merge mode (should work
    with hg 1.0 and 1.2)
    """
    if ctx:
        return len(ctx.parents()) == 2 and ctx.parents()[1]
    return False

def revision_grapher(repo, start_rev=None, stop_rev=0, branch=None, follow=False):
    """incremental revision grapher

    This generator function walks through the revision history from
    revision start_rev to revision stop_rev (which must be less than
    or equal to start_rev) and for each revision emits tuples with the
    following elements:

      - current revision
      - column of the current node in the set of ongoing edges
      - color of the node (?)
      - lines; a list of (col, next_col, color) indicating the edges between
        the current row and the next row
      - parent revisions of current revision

    If follow is True, only generated the subtree from the start_rev head.

    If branch is set, only generated the subtree for the given named branch.
    """
    if start_rev is None and repo.status() == ([],)*7:
        start_rev = len(repo.changelog)
    assert start_rev is None or start_rev >= stop_rev
    curr_rev = start_rev
    revs = []
    rev_color = {}
    nextcolor = 0
    while curr_rev is None or curr_rev >= stop_rev:
        # Compute revs and next_revs.
        if curr_rev not in revs:
            if branch:
                ctx = repo.changectx(curr_rev)
                if ctx.branch() != branch:
                    if curr_rev is None:
                        curr_rev = len(repo.changelog)
                    else:
                        curr_rev -= 1
                    yield None
                    continue

            # New head.
            if start_rev and follow and curr_rev != start_rev:
                curr_rev -= 1
                continue
            revs.append(curr_rev)
            rev_color[curr_rev] = curcolor = nextcolor
            nextcolor += 1
            p_revs = __get_parents(repo, curr_rev, branch)
            while p_revs:
                rev0 = p_revs[0]
                if rev0 < stop_rev or rev0 in rev_color:
                    break
                rev_color[rev0] = curcolor
                p_revs = __get_parents(repo, rev0, branch)
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
        if curr_rev is None:
            curr_rev = len(repo.changelog)
        else:
            curr_rev -= 1


def filelog_grapher(repo, path):
    '''
    Graph the ancestry of a single file (log).  Deletions show
    up as breaks in the graph.
    '''
    filerev = len(repo.file(path)) - 1
    fctx = repo.filectx(path, fileid=filerev)
    rev = fctx.rev()

    flog = fctx.filelog()
    heads = [repo.filectx(path, fileid=flog.rev(x)).rev() for x in flog.heads()]
    assert rev in heads
    heads.remove(rev)

    revs = []
    rev_color = {}
    nextcolor = 0
    _paths = {}

    while rev >= 0:
        # Compute revs and next_revs
        if rev not in revs:
            revs.append(rev)
            rev_color[rev] = nextcolor ; nextcolor += 1
        curcolor = rev_color[rev]
        index = revs.index(rev)
        next_revs = revs[:]

        # Add parents to next_revs
        fctx = repo.filectx(_paths.get(rev, path), changeid=rev)
        for pfctx in fctx.parents():
            _paths[pfctx.rev()] = pfctx.path()
        parents = [pfctx.rev() for pfctx in fctx.parents()]# if f.path() == path]
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
        for i, nrev in enumerate(revs):
            if nrev in next_revs:
                color = rev_color[nrev]
                lines.append( (i, next_revs.index(nrev), color) )
            elif nrev == rev:
                for parent in parents:
                    color = rev_color[parent]
                    lines.append( (i, next_revs.index(parent), color) )

        pcrevs = [pfc.rev() for pfc in fctx.parents()]
        yield (fctx.rev(), index, curcolor, lines, pcrevs,
               _paths.get(fctx.rev(), path))
        revs = next_revs

        if revs:
            rev = max(revs)
        else:
            rev = -1
        if heads and rev <= heads[-1]:
            rev = heads.pop()

class GraphNode(object):
    """
    Simple class to encapsulate e hg node in the revision graph. Does
    nothing but declaring attributes.
    """
    def __init__(self, rev, xposition, color, lines, parents, ncols=None,
                 extra=None):
        self.rev = rev
        self.x = xposition
        self.color = color
        if ncols is None:
            ncols = len(lines)
        self.cols = ncols
        self.parents = parents
        self.bottomlines = lines
        self.toplines = []
        self.extra = extra

class Graph(object):
    """
    Graph object to ease hg repo navigation. The Graph object
    instanciate a `revision_grapher` generator, and provide a `fill`
    method to build the graph progressively.
    """
    #@timeit
    def __init__(self, repo, grapher, maxfilesize=100000):
        self.maxfilesize = maxfilesize
        self.repo = repo
        self.maxlog = len(self.repo.changelog)
        self.grapher = grapher
        self.nodes = []
        self.nodesdict = {}
        self.max_cols = 0

    def build_nodes(self, nnodes=None, rev=None):
        """
        Build up to `nnodes` more nodes in our graph, or build as many
        nodes required to reach `rev`.

        If both rev and nnodes are set, build as many nodes as
        required to reach rev plus nnodes more.
        """
        if self.grapher is None:
            return False
        stopped = False
        mcol = [self.max_cols]
        for vnext in self.grapher:
            if vnext is None:
                continue
            nrev, xpos, color, lines, parents = vnext[:5]
            if nrev >= self.maxlog:
                continue
            gnode = GraphNode(nrev, xpos, color, lines, parents,
                              extra=vnext[5:])
            if self.nodes:
                gnode.toplines = self.nodes[-1].bottomlines
            self.nodes.append(gnode)
            self.nodesdict[nrev] = gnode
            mcol.append(gnode.cols)
            if rev is not None and nrev <= rev:
                rev = None # we reached rev, switching to nnode counter
            if rev is None:
                if nnodes is not None:
                    nnodes -= 1
                    if not nnodes:
                        break
                else:
                    break
        else:
            self.grapher = None
            stopped = True

        self.max_cols = max(mcol)
        return not stopped

    def isfilled(self):
        return self.grapher is None

    def fill(self, step=100):
        """
        Return a generator that fills the graph by bursts of `step`
        more nodes at each iteration.
        """
        while self.build_nodes(step):
            yield len(self)
        yield len(self)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            # XXX TODO: ensure nodes are built
            return self.nodes.__getitem__(idx)
        if idx >= len(self.nodes):
            # build as many graph nodes as required to answer the
            # requested idx
            self.build_nodes(idx)
        if idx > len(self):
            return self.nodes[-1]
        return self.nodes[idx]

    def __len__(self):
        # len(graph) is the number of actually built graph nodes
        return len(self.nodes)

    def index(self, rev):
        if len(self) == 0: # graph is empty, let's build some nodes
            self.build_nodes(10)
        if rev is not None and rev < self.nodes[-1].rev:
            self.build_nodes(self.nodes[-1].rev - rev)
        if rev in self.nodesdict:
            return self.nodes.index(self.nodesdict[rev])
        return -1

    def fileflags(self, filename, rev, _cache={}):
        """
        Return a couple of flags ('=', '+', '-' or '?') depending on the nature
        of the diff for filename between rev and its parents.
        """
        if rev not in _cache:
            ctx = self.repo.changectx(rev)
            _cache.clear()
            _cache[rev] = (ctx,
                           [self.repo.status(p.node(), ctx.node())[:5]
                           for p in ctx.parents()])
        ctx, allchanges = _cache[rev]
        flags = []
        for changes in allchanges:
            # changes = modified, added, removed, deleted, unknown
            for flag, lst in zip(["=", "+", "-", "-", "?"], changes):
                if filename in lst:
                    if flag == "+":
                        renamed = ctx.filectx(filename).renamed()
                        if renamed:
                            flags.append(renamed)
                            break
                    flags.append(flag)
                    break
            else:
                flags.append('')
        return flags

    def fileflag(self, filename, rev):
        """
        Return a flag (see fileflags) between rev and its first parent (may be
        long)
        """
        return self.fileflags(filename, rev)[0]

    def filename(self, rev):
        return self.nodesdict[rev].extra[0]

    def filedata(self, filename, rev, mode='diff', flag=None):
        """XXX written under dubious encoding assumptions

        The modification flag is computed using *fileflag* if ``flag`` is None.
        """
        # XXX This really begins to be a dirty mess...
        data = ""
        if flag is None:
            flag = self.fileflag(filename, rev)
        ctx = self.repo.changectx(rev)
        try:
            fctx = ctx.filectx(filename)
        except LookupError:
            fctx = None # may happen for renamed files?

        if isbfile(filename):
            data = "[bfile]\n"
            if fctx:
                data = fctx.data()
                data += "footprint: %s\n" % data
            return "+", data
        if flag not in ('-', '?'):
            if fctx is None:# or fctx.node() is None:
                return '', None
            if fctx.size() > self.maxfilesize:
                data = "file too big"
                return flag, data
            if flag == "+" or mode == 'file':
                flag = '+'
                # return the whole file
                data = fctx.data()
                if util.binary(data):
                    data = "binary file"
                else: # tries to convert to unicode
                    data = tounicode(data)
            elif flag == "=" or isinstance(mode, int):
                flag = "="
                if isinstance(mode, int):
                    parentctx = self.repo.changectx(mode)
                else:
                    parent = self.fileparent(filename, rev)
                    parentctx = self.repo.changectx(parent)
                # return the diff but the 3 first lines
                data = diff(self.repo, ctx, parentctx, files=[filename])
                data = u'\n'.join(data.splitlines()[3:])
            elif flag == '':
                data = ''
            else: # file renamed
                oldname, node = flag
                newdata = fctx.data().splitlines()
                olddata = self.repo.filectx(oldname, fileid=node)
                olddata = olddata.data().splitlines()
                data = list(difflib.unified_diff(olddata, newdata, oldname,
                                                 filename))[2:]
                if data:
                    flag = "="
                else:
                    data = newdata
                    flag = "+"
                data = u'\n'.join(tounicode(elt) for elt in data)
        return flag, data

    def fileparent(self, filename, rev):
        if rev is not None:
            node = self.repo.changelog.node(rev)
        else:
            node = self.repo.changectx(rev).node()
        for parent in self.nodesdict[rev].parents:
            pnode = self.repo.changelog.node(parent)
            changes = self.repo.status(pnode, node)[:5]
            allchanges = []
            [allchanges.extend(e) for e in changes]
            if filename in allchanges:
                return parent
        return None

class HgRepoListWalker(object):
    """
    Graph object to ease hg repo revision tree drawing depending on user's
    configurations.
    """
    _allcolumns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _columns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _stretchs = {'Log': 1, }
    _getcolumns = "getChangelogColumns"

    def __init__(self, repo, branch='', fromhead=None, follow=False,
                 parent=None, *args, **kwargs):
        """
        repo is a hg repo instance
        """
        #XXX col radius
        self._datacache = {}
        self._hasmq = False
        self.mqueues = []
        self.wd_revs = []
        self.graph = None
        self.rowcount = 0
        self.repo = repo
        super(HgRepoListWalker, self).__init__()
        self.load_config()
        self.setRepo(repo, branch=branch, fromhead=fromhead, follow=follow)

    def setRepo(self, repo=None, branch='', fromhead=None, follow=False):
        if repo is None:
            repo = hg.repository(self.repo.ui, self.repo.root)
        oldrepo = self.repo
        self.repo = repo
        if oldrepo.root != repo.root:
            self.load_config()
        self._datacache = {}
        try:
            wdctxs = self.repo.changectx(None).parents()
        except error.Abort:
            # might occur if reloading during a mq operation (or
            # whatever operation playing with hg history)
            return
        self._hasmq = hasattr(self.repo, "mq")
        if self._hasmq:
            self.mqueues = self.repo.mq.series[:]
        self.wd_revs = [ctx.rev() for ctx in wdctxs]
        self.wd_status = [self.repo.status(ctx.node(), None)[:4] for ctx in wdctxs]
        self._user_colors = {}
        self._branch_colors = {}
        # precompute named branch color for stable value.
        for branch_name in chain(['default', 'stable'], sorted(repo.branchtags().keys())):
            self.namedbranch_color(branch_name)
        grapher = revision_grapher(self.repo, start_rev=fromhead,
                                   follow=follow, branch=branch)
        self.graph = Graph(self.repo, grapher, self.max_file_size)
        self.rowcount = 0
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
        self.ensureBuilt(row=self.fill_step)

    def ensureBuilt(self, rev=None, row=None):
        """
        Make sure rev data is available (graph element created).

        """
        if self.graph.isfilled():
            return
        required = 0
        buildrev = rev
        n = len(self.graph)
        if rev is not None:
            if n and self.graph[-1].rev <= rev:
                buildrev = None
            else:
                required = self.fill_step / 2
        elif row is not None and row > (n - self.fill_step / 2):
            required = row - n + self.fill_step
        if required or buildrev:
            self.graph.build_nodes(nnodes=required, rev=buildrev)
            self.updateRowCount()
        elif row and row > self.rowcount:
            # asked row was already built, but views where not aware of this
            self.updateRowCount()
        elif rev is not None and rev <= self.graph[self.rowcount].rev:
            # asked rev was already built, but views where not aware of this
            self.updateRowCount()

    def updateRowCount(self):
        self.rowcount = None
        #raise NotImplementedError

    def rowCount(self, parent=None):
        return self.rowcount

    def columnCount(self, parent=None):
        return len(self._columns)

    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        self._users, self._aliases = cfg.getUsers()
        self.dot_radius = cfg.getDotRadius(default=8)
        self.rowheight = cfg.getRowHeight()
        self.fill_step = cfg.getFillingStep()
        self.max_file_size = cfg.getMaxFileSize()
        self.hide_mq_tags = cfg.getMQHideTags()

        cols = getattr(cfg, self._getcolumns)()
        if cols is not None:
            validcols = [col for col in cols if col in self._allcolumns]
            if len(validcols) != len(cols):
                wrongcols = [col for col in cols if col not in self._allcolumns]
                #XXX
                #print "WARNING! %s are not valid column names. Check your configuration." % ','.join(wrongcols)
                #print "         reverting to default columns configuration"
            elif 'Log' not in validcols or 'ID' not in validcols:
                pass
                #print "WARNING! 'Log' and 'ID' are mandatory. Check your configuration."
                #print "         reverting to default columns configuration"
            else:
                self._columns = tuple(validcols)

    @staticmethod
    def get_color(n, ignore=()):
        return []

    def user_color(self, user):
        if user not in self._user_colors:
            self._user_colors[user] = self.get_color(len(self._user_colors),
                                                self._user_colors.values())
        return self._user_colors[user]

    def user_name(self, user):
        return self._aliases.get(user, user)

    def namedbranch_color(self, branch):
        if branch not in self._branch_colors:
            self._branch_colors[branch] = self.get_color(len(self._branch_colors))
        return self._branch_colors[branch]

    def col2x(self, col):
        return (1.2*self.dot_radius + 0) * col + self.dot_radius/2 + 3

    def rowFromRev(self, rev):
        row = self.graph.index(rev)
        if row == -1:
            row = None
        return row

    def indexFromRev(self, rev):
        self.ensureBuilt(rev=rev)
        row = self.rowFromRev(rev)
        if row is not None:
            return self.index(row, 0)
        return None

    def clear(self):
        """empty the list"""
        self.graph = None
        self._datacache = {}
        self.notify_data_changed()

    def notify_data_changed(self):
        pass

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

