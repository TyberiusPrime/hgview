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
try:
    set()
except NameError:
    from sets import Set  as set

nullid = "\x00"*20

def parents_of(repo, node):
    return [ p for p in repo.changelog.parents(node) if p != nullid ]

# TODO : make it work with a partial set of nodes ?
COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", "magenta" ]

class RevGraph(object):
    def __init__(self, repo, nodes, allnodes):
        self.repo = repo
        self.nextcolor = 0
        start = repo.heads()
        ncleft = {} # number of children left to do for a given node
        self.x = {} # for a given node
        self.idrow = {} # mapping of node to row
        self.rowlines = [ set() for i in xrange(len(allnodes)) ] # mapping of row to list of lines
        self.rownlines = [None]*len(allnodes) # mapping of row to number of lines
        self.rows = [None]*len(allnodes)
        
        # calculate initial ncleft for each node
        ncleft = dict( izip( nodes, repeat(0) ) )
        ncleft[nullid] = 0

        _parents = {}
        for p in allnodes:
            _parents[p] = parents_of(repo,p)
        if len(nodes)==len(allnodes):
            todo = start[:] # None is a blank column
            parents = _parents
        else:
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
        nullentry = -1 # next column to be eradicate when it is determined that one should be
        rowno = -1
        linestarty = {}
        self.datemode = False
        
        self.todo = todo
        self.colors = {}
        for p in todo:
            self.assigncolor(p)
        self.rowno = rowno
        self.level = level
        self.parents = parents
        self.ncleft = ncleft
        self.linestarty = linestarty
        self.nullentry = nullentry


    def assigncolor(self, p, color=None):
        if p in self.colors:
            return
        if color is None:
            n = self.nextcolor
            color = COLORS[n]
            n+=1
            if n==len(COLORS):
                n=0
            self.nextcolor = n
        self.colors[p] = color
    
    def build(self, NMAX=500 ):
        datemode = self.datemode
        todo = self.todo
        rowno = self.rowno
        level = self.level
        parents = self.parents
        ncleft = self.ncleft
        linestarty = self.linestarty
        nullentry = self.nullentry

        rowmax = rowno+NMAX
        # each node is treated only once
        while todo:
            if rowno==rowmax:
                break
            rowno += 1
            self.rownlines[rowno] = len(todo)
            id = todo[level]
            self.idrow[id] = rowno
            self.rows[rowno] = id
            actualparents = parents[id]

            # for each parent reduce the number of
            # childs not handled by 1
            for p in actualparents:
                ncleft[p] -= 1

            self.x[id] = level

            level_linestart = linestarty.get( level, rowno )
            # linestarty is top of line at each level
            # and thus should always be <=rowno
            assert level_linestart<=rowno
            if level_linestart < rowno:
                # add line from (x, linestarty[level]) to (x, rowno)
                # XXX: shouldn't we have added the ones <rowno already ??
                for r in xrange(level_linestart, rowno+1 ):
                    self.rowlines[r].add( (id,level,level_linestart,level,rowno) )
            linestarty[level] = rowno # starting a new line

            # if only one parent and last child,
            # replace with parent in todo
            if (not datemode) and (len(actualparents) == 1):
                p = actualparents[0]
                if (ncleft[p] == 0) and (p not in todo):
                    todo[level] = p
                    self.assigncolor(p, self.colors[id] )
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
                    lines.append((i,todo[i]))
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
                    self.assigncolor(p)
                    todo.insert(i,p)
                    if nullentry >= i:
                        nullentry += 1
                    i += 1
                lines.append((oldlevel,p))

            # then choose a new level
            todol = len(todo)
            level = -1
            latest = None

            for k in xrange(todol-1,-1,-1):
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
            for (i,dst) in lines:
                j = todo.index(dst)
                if i == j:
                    if i in oldstarty:
                        linestarty[i] = oldstarty[i]
                    continue
                coords = []
                if (i in oldstarty) and (oldstarty[i] < rowno):
                    coords.append((i,oldstarty[i]))
                coords.append((i, rowno))
                if j < i - 1:
                    coords.append((j + 1, rowno))
                elif j > i + 1:
                    coords.append((j - 1, rowno))
                coords.append((j, rowno + 1))


                # add line from (x1, y1) to (x2, y2)
                (x1,y1) = coords[0]
                for (x2,y2) in coords[1:]:
                    for r in xrange(min(y1,y2),max(y1,y2)+1):
                        self.rowlines[r].add((dst,x1,y1,x2,y2))
                    (x1,y1) = (x2,y2)

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
