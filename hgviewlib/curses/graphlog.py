#! /usr/bin/env python
# -*- coding: utf-8 -*-
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
'''
Contains a listbox definition that walk the repo log and display an ascii graph
'''

from itertools import izip
from time import strftime, localtime

from urwid import AttrMap, Text, ListWalker, Columns, ListBox, WidgetWrap

from hgext.graphlog import (fix_long_right_edges, get_nodeline_edges_tail,
                            draw_edges, get_padding_line)

from hgviewlib.util import tounicode
from hgviewlib.hggraph import (HgRepoListWalker, getlog, gettags)

# __________________________________________________________________ constants

COLORS = ["brown", "dark red", "dark magenta", "dark blue", "dark cyan",
          "dark green", "yellow", "light red", "light magenta", "light blue",
          "light cyan", "light green"]

DATE_FMT = '%F %R'

_COLUMNMAP = {
    'ID': lambda m, c, g: c.rev() is not None and str(c.rev()) or "",
    'Log': getlog,
    'Author': lambda m, c, g: tounicode(c.user().split('<',1)[0]),
    'Date': lambda m, c, g: strftime(DATE_FMT, localtime(int(c.date()[0]))),
    'Tags': gettags,
    'Branch': lambda m, c, g: c.branch() != 'default' and c.branch(),
    'Filename': lambda m, c, g: g.extra[0],
    }
GRAPH_MIN_WIDTH = 6

# ____________________________________________________________________ classes

class RevisionItem(Text):
    """A custom widget to display a revision entry"""
    selectable = lambda self: True
    keypress = lambda self, size, key: key

class AppliedItem(WidgetWrap):
    def __init__(self, w, gnode, ctx, *args, **kwargs):
        self.gnode = gnode
        self.ctx = ctx
        self.__super.__init__(w, *args, **kwargs)

class UnappliedItem(WidgetWrap):
    def __init__(self, w, idx, name, *args, **kwargs):
        self.idx = idx
        self.name = name
        self.__super.__init__(w, *args, **kwargs)

class RevisionsWalker(ListWalker, HgRepoListWalker):
    """ListWalker-compatible class for browsing log changeset.
    """

    _allfields = (('Branch', 'Tags', 'Log'), ())
    _allcolumns = (('Date', 16), ('Author', 20), ('ID', 6),)

    def __init__(self, repo, branch='', fromhead=None, follow=False,
                 *args, **kwargs):
        self._data_cache = {}
        self.focus = 0L
        super(RevisionsWalker, self).__init__(repo, branch, fromhead, follow,
                                              *args, **kwargs)
        if self._hasmq:
            self.focus = -len(self._get_unapplied())
        self.asciistate = [0, 0]#graphlog.asciistate()

    def _get_unapplied(self):
        return self.repo.mq.unapplied(self.repo)

    def _modified(self):
        if self.focus >= len(self._data_cache):
            self.focus = max(0, len(self._data_cache)-1)
        super(RevisionsWalker, self)._modified()

    notify_data_changed = _modified

    def setRepo(self, *args, **kwargs):
        super(RevisionsWalker, self).setRepo(*args, **kwargs)
        self._modified()

    def _invalidate(self):
        self.clear()
        self._data_cache.clear()

    @staticmethod
    def get_color(idx, ignore=()):
        """
        Return a color at index 'n' rotating in the available
        colors. 'ignore' is a list of colors not to be chosen.
        """
        colors = [x for x in COLORS if x not in ignore]
        if not colors: # ghh, no more available colors...
            colors = COLORS
        return colors[idx % len(colors)]

    def data(self, pos):
        """Return a widget and the position passed."""
        # cache may be very hudge on very big repo
        # (cpython for instance: >1.5GB)
        if pos in self._data_cache: # speed up rendering
            return self._data_cache[pos], pos
        if pos < 0:
            widget = self.get_unapplied_widget(pos)
        else:
            widget = self.get_applied_widget(pos)
        if widget is None:
            return None, None
        self._data_cache[pos] = widget
        return widget, pos

    def get_unapplied_widget(self, pos):
        """return a widget for unapplied patch"""
        # blank columns
        idx, name = self._get_unapplied()[-pos - 1]
        info = {'Branch':'[Unapplied patches]', 'ID':str(idx),'Log':name}
        # prepare the last columns content
        txts = ['.' + ' ' * GRAPH_MIN_WIDTH] # mock graph log
        for fields in self._allfields:
            if not fields:
                continue
            for field in fields:
                if field not in info:
                    continue
                txts.append(('Unapplied', info.get(field)))
                txts.append(('default', ' '))
            txts.append('\n')
        txt = RevisionItem(txts[:-1])
        # prepare other columns
        columns = [('fixed', sz, Text(('Unapplied', info.get(col, '')),
                                      align='right'))
                   for col, sz in self._allcolumns if col in self._columns]
        txt = Columns(columns + [txt], 1)
        txt = AttrMap(txt, {}, {'Unapplied':'focus'})
        txt = UnappliedItem(txt, idx, name)
        return txt

    def get_applied_widget(self, pos):
        """Return a widget for changeset, applied patches and working
        directory state"""
        if pos in self._data_cache: # speed up rendering
            return self._data_cache[pos], pos

        try:
            self.ensureBuilt(row=pos)
        except ValueError:
            return None
        gnode = self.graph[pos]
        ctx = self.repo.changectx(gnode.rev)
        # prepare the last columns content
        txts = []
        for graph, fields in izip(self.graphlog(gnode, ctx), self._allfields):
            txts.append(('GraphLog', graph.ljust(GRAPH_MIN_WIDTH)))
            txts.append(' ')
            for field in fields:
                if field not in self._columns:
                    continue
                txt = _COLUMNMAP[field](self, ctx, gnode)
                if not txt:
                    continue
                txts.append((field, txt))
                txts.append(('default', ' '))
            txts.pop() # remove pendding space
            txts.append('\n')
        txts.pop() # remove pendding newline
        txt = RevisionItem(txts)
        # prepare other columns
        txter = lambda col, sz: Text(
                 (col, _COLUMNMAP[col](self, ctx, gnode)[:sz]), align='right')
        columns = [('fixed', sz, txter(col, sz))
                   for col, sz in self._allcolumns
                   if col in self._columns] + [txt]
        # highlight some revs
        style = None
        if gnode.rev is None:
            style = 'Modified' # pending changes
        elif gnode.rev in self.wd_revs:
            style = 'Current'
        spec_style = style and dict.fromkeys(['GraphLog'], style) or {}
        # highlight focused
        style = style or 'focus'
        foc_style = dict.fromkeys(self._columns + ('GraphLog', None), style)
        # build widget with style modifier
        widget = AttrMap(Columns(columns, 1), spec_style, foc_style)
        widget = AppliedItem(widget, gnode, ctx)
        return widget

    def graphlog(self, gnode, ctx):
        """Return a generator that get lines of graph log for the node
        """
        # define node symbol
        char = 'o'
        if gnode.rev is None:
            char = '!' # pending changes
        elif len(ctx.parents()) > 1:
            char = 'M' # merge
        elif set(ctx.tags()).intersection(self.mqueues):
            char = '*' # applied patch from mq
        elif gnode.rev in self.wd_revs:
            char = '@'
        # build the column data for the graphlogger from data given by hgview
        curcol = gnode.x
        curedges = [(start, end) for start, end, _ in gnode.bottomlines
                    if start == curcol]
        try:
            prv, nxt, _ = zip(*gnode.bottomlines)
            prv, nxt = len(set(prv)), len(set(nxt))
        except ValueError: # last
            prv, nxt = 1, 0
        coldata = (curcol, curedges, prv, nxt - prv)
        self.asciistate = self.asciistate or [0, 0]
        return hgview_ascii(self.asciistate, char, 1, coldata)

    def get_focus(self):
        """Get focused widget"""
        try:
            return self.data(self.focus)
        except IndexError:
            if self.focus > 0:
                self.focus = 0
            else:
                self.focus = -len(self._get_unapplied())
        try:
            return self.data(self.focus)
        except:
            return None, None

    def set_focus(self, focus):
        """change focused widget"""
        self.focus = focus
        self._modified()

    def get_next(self, start_from):
        """get the next widget to display"""
        focus = start_from + 1
        try:
            return self.data(focus)
        except IndexError:
            return None, None

    def get_prev(self, start_from):
        """get the previous widget to display"""
        focus = start_from - 1
        try:
            return self.data(focus)
        except IndexError:
            return None, None

class RevisionsList(ListBox):
    """ListBox that display the graph log of the repo"""
    def __init__(self, repo, *args, **kwargs):
        self.size = 0
        self.__super.__init__(RevisionsWalker(repo), *args, **kwargs)

# __________________________________________________________________ functions

def hgview_ascii(state, char, height, coldata):
    """prints an ASCII graph of the DAG

    takes the following arguments (one call per node in the graph):

    :param state: Somewhere to keep the needed state in (init to [0, 0])
    :param char: character to use as node's symbol.
    :pram height: minimal line number to use for this node
    :param coldata: (idx, edges, ncols, coldiff)
        * idx: column index for the curent changeset
        * edges: a list of (col, next_col) indicating the edges between
          the current node and its parents.
        * ncols: number of columns (ongoing edges) in the current revision.
        * coldiff: the difference between the number of columns (ongoing edges)
          in the next revision and the number of columns (ongoing edges)
          in the current revision. That is: -1 means one column removed;
          0 means no columns added or removed; 1 means one column added.


    :note: it is a Modified version of Joel Rosdahl <joel@rosdahl.net> 
           graphlog extension for mercurial
    """
    idx, edges, ncols, coldiff = coldata
    assert -2 < coldiff < 2
    assert height > 0
    if coldiff == -1:
        fix_long_right_edges(edges)
    # add_padding_line says whether to rewrite
    add_padding_line = (height > 2 and coldiff == -1 and
                        [x for (x, y) in edges if x + 1 < y])
    # fix_nodeline_tail says whether to rewrite
    fix_nodeline_tail = height <= 2 and not add_padding_line

    # nodeline is the line containing the node character (typically o)
    nodeline = ["|", " "] * idx
    nodeline.extend([char, " "])
    nodeline.extend(get_nodeline_edges_tail(idx, state[1], ncols, coldiff,
                                            state[0], fix_nodeline_tail))
    # shift_interline is the line containing the non-vertical
    # edges between this entry and the next
    shift_interline = ["|", " "] * idx
    if coldiff == -1:
        n_spaces = 1
        edge_ch = "/"
    elif coldiff == 0:
        n_spaces = 2
        edge_ch = "|"
    else:
        n_spaces = 3
        edge_ch = "\\"
    shift_interline.extend(n_spaces * [" "])
    shift_interline.extend([edge_ch, " "] * (ncols - idx - 1))
    # draw edges from the current node to its parents
    draw_edges(edges, nodeline, shift_interline)
    # lines is the list of all graph lines to print
    lines = [nodeline]
    if add_padding_line:
        lines.append(get_padding_line(idx, ncols, edges))
    if not set(shift_interline).issubset(set([' ', '|'])): # compact
        lines.append(shift_interline)
    # make sure that there are as many graph lines as there are
    # log strings
    if len(lines) < height:
        extra_interline = ["|", " "] * (ncols + coldiff)
        while len(lines) < height:
            lines.append(extra_interline)
    # print lines
    indentation_level = max(ncols, ncols + coldiff)
    for line in lines:
        out = "%-*s" % (2 * indentation_level, "".join(line))
        yield out
    # ... and start over
    state[0] = coldiff
    state[1] = idx



