# buildtree.py - the graph algorithm inherited from gitk
#
# Copyright (C) 2007 Logilab. All rights reserved.
# Copyright (C) 2005 Tristan Wibberley <tristan at wibberley.com>. All rights reserved.
# Copyright (C) 2005 Paul Mackerras.  All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

# This was translated by Tristan from tcl/tk (gitk) to python
# and then reworked and pruned
# I got it from : http://www.selenic.com/pipermail/mercurial/2005-August/003585.html


from mercurial import hg, ui
from mercurial.node import hex as binhex
from itertools import *

nullid = "\x00"*20

def parents_of(repo, node):
    return [ p for p in repo.changelog.parents(node) if p != nullid ]

# TODO : make it work with a partial set of nodes ?
COLORS = [ "blue", "darkgreen", "darkred", "green", "darkblue", "purple",
           "cyan", "magenta" ]

class RevGraph(object):
    def __init__(self, repo, nodes, allnodes):
        self.repo = repo
        self.nextcolor = 0
        start = repo.heads()
        
        # number of children left to do for a given node
        ncleft = {}

        # for a given node
        self.x = {}

        # mapping of node to row
        self.idrow = {}        

        # mapping of row to list of lines
        self.rowlines = [ set() for i in xrange(len(allnodes)) ] 
        
        # mapping of row to number of lines
        self.rownlines = [None]*len(allnodes) 
        self.rows = [None]*len(allnodes)
        
        # calculate initial ncleft for each node
        ncleft = dict( izip( nodes, repeat(0) ) )
        ncleft[nullid] = 0
        
        # build parent mapping
        _parents = {}
        for p in allnodes:
            _parents[p] = _p = parents_of(repo, p)
        if len(nodes) == len(allnodes):
            todo = start[:] # None is a blank column
            parents = _parents
        else:
            # this path is ... approximative at best
            children = {}
            parents = {}
            todo = allnodes
            _nodes = set(nodes)
            while todo:
                print "*"
                next = set()
                for node in todo:
                    par = _parents[node]
                    npar = set()
                    for p in par:
                        if p not in _nodes:
                            npar.update( _parents[p] )
                            next.add( node )
                        else:
                            npar.add(p)
                    for p in set(npar):
                        for k in _parents[p]:
                            if k in npar:
                                npar.remove(p)
                                break
                    _parents[node] = npar
                todo = next
            for n in nodes:
                par = _parents[n]
                parents[n] = list(par)
                for p in par:
                    children[p] = n
            todo = []
            for p in nodes:
                if p not in children:
                    todo.append( p )
            del children

        for node in nodes:
            ps = parents[node]
            for p in ps:
                ncleft[p] += 1

        level = len(todo) - 1 # column of the node being worked with
        # next column to be eradicate when it is determined that one should be
        nullentry = -1 

        todo.reverse()
        
        rowno = -1
        linestarty = {}
        self.datemode = False
        
        self.todo = todo
        self.colors = {}
        self.rowno = rowno
        self.level = level
        self.parents = parents
        self.ncleft = ncleft
        self.nchildren = ncleft.copy()
        self.linestarty = linestarty
        self.nullentry = nullentry
        self.done = False
        #print "START", [binhex(n) for n in todo]

    def assigncolor(self, p, color = None):
        while len(self.parents[p]) == 1:
            p = self.parents[p][0]
            if self.nchildren[p] != 1:
                break
        if p in self.colors:
            return p
        if color is None:
            n = self.nextcolor
            color = COLORS[n]
            n += 1
            if n == len(COLORS):
                n = 0
            self.nextcolor = n
        self.colors[p] = color
        return p
    
    def build(self, NMAX = 500 ):
        datemode = self.datemode
        todo = self.todo
        rowno = self.rowno
        level = self.level
        parents = self.parents
        ncleft = self.ncleft
        linestarty = self.linestarty
        nullentry = self.nullentry

        rowmax = rowno + NMAX
        # each node is treated only once
        while todo:
            if rowno == rowmax:
                break
            rowno += 1
            self.rownlines[rowno] = len(todo)
            id = todo[level]
            self.idrow[id] = rowno
            self.rows[rowno] = id
            idcolor = self.assigncolor(id)
            actualparents = parents[id]

            # for each parent reduce the number of
            # childs not handled by 1
            for p in actualparents:
                ncleft[p] -= 1

            self.x[id] = level

            level_linestart = linestarty.get( level, rowno )
            # linestarty is top of line at each level
            # and thus should always be <= rowno
            assert level_linestart <= rowno
            if level_linestart < rowno:
                # add line from (x, linestarty[level]) to (x, rowno)
                # XXX: shouldn't we have added the ones <rowno already ??
                for r in xrange(level_linestart, rowno + 1 ):
                    self.rowlines[r].add( (idcolor, level,
                        level_linestart, level, rowno) )
            linestarty[level] = rowno # starting a new line

            # if only one parent and last child,
            # replace with parent in todo
            if (not datemode) and (len(actualparents) == 1):
                p = actualparents[0]
                if (ncleft[p] == 0) and (p not in todo):
                    todo[level] = p
                    continue

            # otherwise obliterate a sensible gap choice
            oldtodo = todo[:]
            oldlevel = level
            lines = []
            oldstarty = {}
            
            for i in xrange(self.rownlines[rowno]):
                if todo[i] is None:
                    continue
                if i in linestarty:
                    oldstarty[i] = linestarty[i]
                    del linestarty[i]
                if i != level:
                    lines.append((i, todo[i]))
            if nullentry >= 0:
                del todo[nullentry]
                if nullentry < level:
                    level -= 1

            # delete the done id
            del todo[level]
            if nullentry > level:
                nullentry -= 1
            # and insert the parents
            i = level
            for p in actualparents:
                if p not in todo:
                    todo.insert(i, p)
                    if nullentry >= i:
                        nullentry += 1
                    i += 1
                lines.append((oldlevel, p))

            # then choose a new level
            todol = len(todo)
            level = -1
            latest = None

            for k in xrange(todol -1, -1, -1):
                p = todo[k]
                if p is None:
                    continue

                if ncleft[p] == 0:
                    if datemode:
                        if (latest is None) or (cdate[p] > latest):
                            level = k
                            latest = cdate[p]
                    else:
                        level = k
                        break

            if level < 0:
                if todo != []:
                    print "ERROR: none of the pending commits can be done yet"
                    for p in todo:
                        print "  " + binhex(p)
                break

            # if we are reducing, put in a null entry
            if todol < self.rownlines[rowno]:
                if nullentry >= 0:
                    i = nullentry
                    while (i < todol and oldtodo[i] == todo[i]):
                        i += 1
                else:
                    i = oldlevel
                    if level >= i:
                        i += 1
                if i >= todol:
                    nullentry = -1
                else:
                    nullentry = i
                    todo.insert(nullentry, None)
                    if level >= i:
                        level += 1
            else:
                nullentry = -1

            # j is x at the bottom of a horizontalish line
            # i is x at the top of a horizontalish
            for (i, dst) in lines:
                j = todo.index(dst)
                colordst = self.assigncolor( dst )
                if i == j:
                    if i in oldstarty:
                        linestarty[i] = oldstarty[i]
                    continue
                coords = []
                if (i in oldstarty) and (oldstarty[i] < rowno):
                    coords.append((i, oldstarty[i]))
                coords.append((i, rowno))
                if j < i - 1:
                    coords.append((j + 1, rowno))
                elif j > i + 1:
                    coords.append((j - 1, rowno))
                coords.append((j, rowno + 1))


                # add line from (x1, y1) to (x2, y2)
                (x1, y1) = coords[0]
                for (x2, y2) in coords[1:]:
                    for r in xrange(min(y1, y2), max(y1, y2) + 1):
                        self.rowlines[r].add((colordst, x1, y1, x2, y2))
                    (x1, y1) = (x2, y2)

                if j not in linestarty:
                    linestarty[j] = rowno + 1

        self.todo = todo
        self.rowno = rowno
        self.level = level
        self.parents = parents
        self.ncleft = ncleft
        self.linestarty = linestarty
        self.nullentry = nullentry

if __name__ == '__main__':
    ui_ = ui.ui()
    repo = hg.repository(ui.ui())

    revlog = RevGraph(repo)




def dfs( g ): # recursive version
    """g : dict node->deps"""
    d = {} # discovery time
    f = {} # finishing time
    pi = {}
    topo_sort = []
    dfs_color = {}
    for u in g:
        dfs_color[u] = 0
    time = [0]
    def dfs_visit( u ):
        dfs_color[u] = 1
        time[0] += 1
        d[u] = time[0]
        for v in g[u]:
            if dfs_color[v] == 0:
                pi[v] = u
                dfs_visit(v)
        dfs_color[u] = 2
        time[0] += 1
        f[u] = time[0]
        topo_sort.append( u )

    for u in g:
        if dfs_color[u] == 0:
            dfs_visit( u )
    return pi, d, f, topo_sort

def dfs( g ):
    """g : dict node->deps"""
    d = {} # discovery time
    f = {} # finishing time
    pi = {}
    topo_sort = []
    dfs_color = {}
    for u in g:
        dfs_color[u] = 0
    time = [0]

    def dfs_visit( todo ):
        while todo:
            u = todo[-1]
            color = dfs_color[u]
            if color == 0:
                dfs_color[u] = 1
                time[0] += 1
                d[u] = time[0]
                for v in g[u]:
                    if dfs_color[v] == 0:
                        pi[v] = u
                        todo.append(v)
            elif color == 1:
                todo.pop(-1)
                dfs_color[u] = 2
                time[0] += 1
                f[u] = time[0]
                topo_sort.append( u )
            else:
                todo.pop(-1) # ignore, visited already

    dfs_visit(g.keys())
    return pi, d, f, topo_sort





class RevGraph2(RevGraph):
    def build(self, NMAX = 500 ):
        if self.done:
            return
        parents = self.parents
        pi, d, f, topo_sort = dfs(parents)

        self.rows = topo_sort
        self.x = X = {}
        Y = {}
        self.rowlines = []
        s = set()
        K = 0
        links = {}
        for yc, n in enumerate(topo_sort):
            lines = set()
            self.rowlines.append( lines )
            for p in parents[n]:
                if p in s:
                    s.remove(p)
            X[n] = len(s)

            for p in parents[n]:
                colordst = self.assigncolor( n )
                if p in parents[n]:
                    # add a line from parent to here
                    y1 = Y[p]
                    y2 = yc
                    x1 = X[p]
                    x2 = X[n]
                    if y2 - y1 > 1:
                        links[ (p, n) ] = (x1, y1, x2, y2)
                    else:
                        ly = self.rowlines[y1]
                        ly.add( (colordst, x1, y1, x2, y2) )
                        ly = self.rowlines[y2]
                        ly.add( (colordst, x1, y1, x2, y2) )
                        
##                     for y in xrange(y1, yc + 1):
##                         ly = self.rowlines[y]
##                         ly.add( (colordst, x1, y1, x2, y2) )

            Y[n] = yc
            s.add(n)
            if yc % 20 == 0:
                print yc

        POS = [ set() for i in xrange(len(topo_sort)) ]
        for (p, n), (x1, y1, x2, y2) in links.items():
            pass
        
        self.done = True
        return
        #from pprint import pprint
        #pprint( zip([ binhex(n) for n in topo_sort], X) )

        
        
        return _RevGraph.build(self, NMAX)



class RevGraph3(RevGraph):
    def build(self, NMAX = 500 ):
        datemode = self.datemode
        todo = self.todo
        rowno = self.rowno
        level = self.level
        parents = self.parents
        ncleft = self.ncleft
        linestarty = self.linestarty
        nullentry = self.nullentry

        rowmax = rowno + NMAX
        # each node is treated only once
        while todo:
            pass
#_RevGraph = RevGraph
#RevGraph = RevGraph2
