#!/usr/bin/env python
# gui.py - gui classes for mercurial
#
# Copyright (C) 2005 Tristan Wibberley <tristan at wibberley.com>. All rights reserved.
# Copyright (C) 2005 Paul Mackerras.  All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

# This was translated from tcl/tk (gitk) to python

from mercurial import hg, ui
from itertools import *
nullid = "\x00"*20

def parents_of(repo, node):
    (p1,p2) = repo.changelog.parents(node)
    if (p1 != nullid) and (p2 == nullid):
        return [p1]
    if (p2 != nullid) and (p1 == nullid):
        return [p2]
    if (p2 == nullid) and (p1 == nullid):
        return []
    return [p1,p2]

def parents_of_rev(repo,rev):
    return map(repo.changelog.rev,parents_of(repo,repo.changelog.node(rev)))

class RevGraph(object):
    
    def __init__(self, repo):        
        self.repo = repo

        start = repo.heads()
        ncleft = {} # number of children left to do for a given node
        self.nchildren = {} # total number of children for a given node
        self.nparents = {} # total number of parents for a given node
        self.x = {} # for a given node
        self.rowid = {} # mapping of row to node
        self.idrow = {} # mapping of node to row
        self.rowlines = {} # mapping of row to list of lines
        self.rownlines = {} # mapping of row to number of lines
        self.rowtext = {} # mapping of row to text

        # calculate nparents and nchildren for each node
        for rev in xrange(repo.changelog.count()):

            node = repo.changelog.node(rev)
            ps = repo.changelog.parents(node)
            for p in ps:
                if p not in self.nchildren:
                    self.nchildren[p] = 0
                self.nchildren[p] += 1
            self.nparents[node] = len(ps)

        # initialise ncleft for each node
        for rev in xrange(repo.changelog.count()):
            node = repo.changelog.node(rev)
            if node not in self.nchildren:
                self.nchildren[node] = 0
            ncleft[node] = self.nchildren[node]
            
        todo = start[:] # None is a blank column
        level = len(todo) - 1 # column of the node being worked with
        nullentry = -1 # next column to be eradicate when it is determined that one should be
        rowno = -1
        numcommits = 0
        linestarty = {}
        datemode = False

        while(todo != []):

            numcommits += 1
            rowno += 1

            self.rownlines[rowno] = len(todo)
            id = todo[level]
            self.rowid[rowno] = id
            self.idrow[id] = rowno
            (_,_,_,_,text,_) = repo.changelog.read(id)
            self.rowtext[rowno] = text.splitlines()[0]
            actualparents = []

            for p in parents_of(repo,id):
                ncleft[p] -= 1
                actualparents.append(p)
            
            self.x[id] = level

            # linestarty is top of line at each level
            if level in linestarty and linestarty[level] < rowno:
                # add line from (x, linestarty[level]) to (x, rowno)
                for r in xrange(min(linestarty[level],rowno),max(linestarty[level],rowno)+1):
                    if r not in self.rowlines:
                        self.rowlines[r] = set()
                    self.rowlines[r].update([((level,linestarty[level],level,rowno))])
            linestarty[level] = rowno # starting a new line

            # TODO tags
            #

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
                if todo[i] == None: continue
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
                    #assigncolor(p)
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
                if p == None:
                    continue

                if ncleft[p] == 0:
                    if datemode:
                        if (latest == None) or (cdate[p] > latest):
                            level = k
                            latest = cdate[p]
                    else:
                        level = k
                        break
                        
            if level < 0:
                if todo != []:
                    print "ERROR: none of the pending commits can be done yet"
                    for p in todo:
                        print "  " + revlog.hex(p)
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
                        if r not in self.rowlines:
                            self.rowlines[r] = set()
                        self.rowlines[r].update([(x1,y1,x2,y2)])
                    (x1,y1) = (x2,y2)

                if j not in linestarty:
                    linestarty[j] = rowno + 1



    def show(self):
        pass

    def paint(self, area, event):
        
        size = 5
        
        ctx = area.window.cairo_create()
	(x,y,w,h) = event.area
	ctx.rectangle(x,y,w,h)
	ctx.clip()

        (w,h) = area.window.get_size()

        stop = int(self.top)
        
        lines = set()

        for srow in xrange(0, h / (size * 4) + 1):
            row = srow + stop

            if row in self.rowlines:
                lines.update(self.rowlines[row])

        ctx.set_line_width(size / 5.0)

        for ((x1,y1),(x2,y2)) in lines:
            x1 = size * 4 * x1 + size * 2
            x2 = size * 4 * x2 + size * 2
            y1 = size * 4 * (y1 - stop) + size * 2
            y2 = size * 4 * (y2 - stop) + size * 2
            
            if x1 < 0: x1 = 0
            if x2 < 0: x2 = 0
            if y1 < 0: y1 = 0
            if y2 < 0: y2 = 0
            if x1 > w: x1 = w
            if x2 > w: x2 = w
            if y1 > h: y1 = h
            if y2 > h: y2 = h
            
            ctx.move_to(x1, y1)
            ctx.line_to(x2, y2)
            ctx.stroke()

        for srow in xrange(0, h / (size * 4) + 1):
            row = srow + stop

            if row not in self.rowid:
                continue
            id = self.rowid[row]
            ctx.arc(size * 4 * self.x[id] + size * 2,
                    size * 4 * srow + size * 2, size, 0, 2*3.1415)
            ctx.set_source_rgba(1,1,1,1)
            ctx.fill_preserve()
            ctx.set_source_rgba(0,0,0,1)
            ctx.stroke()
            
            ctx.move_to(size * 4 * self.rownlines[row] + size * 2,
                        size * 4 * srow + size * 2)
            ctx.text_path(self.rowtext[row])
            ctx.stroke()
            
    

if __name__ == '__main__':
    ui_ = ui.ui()
    repo = hg.repository(ui.ui())

    revlog = RevGraph(repo)
