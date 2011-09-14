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
"""
Main curses application for hgview
"""

import os
import threading
import logging

from pygments import lexers

import urwid
from urwid import (AttrWrap, Pile, Columns, ListBox, SolidFill, Filler,
                   connect_signal, emit_signal)
from mercurial import ui, hg, cmdutil

from hgviewlib.hggraph import HgRepoListWalker

from hgviewlib.util import choose_viewer, find_repository
from hgviewlib.curses.graphlog import RevisionsWalker, AppliedItem, UnappliedItem
from hgviewlib.curses.manifest import ManifestWalker
from hgviewlib.curses import (connect_logging, Body, MainFrame,
                              register_command, unregister_command,
                              connect_command, emit_command, CommandArg as CA,
                              hg_command_map,
                              PALETTE, Screen,
                              SourceText)

class GraphlogViewer(Body):
    """Graphlog body"""

    def __init__(self, walker, *args, **kwargs):
        self.walker = walker
        self.graphlog_walker = RevisionsWalker(walker=walker)
        body = ListBox(self.graphlog_walker)
        self.__super.__init__(body=body, *args, **kwargs)
        self.title = walker.repo.root
        connect_signal(self.graphlog_walker, 'focus changed', self.update_title)

    def update_title(self, ctx):
        """update title depending on the given context ``ctx``."""
        try:
            hex = ctx.hex()
        except TypeError:
            hex = 'WORKING DIRECTORY'
        self.title = '%s [%s]' % (self.walker.repo.root, hex)

    def register_commands(self):
        '''Register commands and connect commands for bodies'''
        register_command(
                ('goto', 'g'), 'Set focus on a particular revision',
                CA('revision', int,
                'The revision number to focus on (default to last)'))
        self.graphlog_walker.connect_commands()

    def unregister_commands(self):
        '''Unregister commands'''
        unregister_command('goto')
        unregister_command('g')

    def render(self, size, focus=True):
        '''Render the widget. Always use the focus style.'''
        return self.__super.render(size, True)

    def mouse_event(self, size, event, button, col, row, focus):
        """Scroll content and show context"""
        if urwid.util.is_mouse_press(event):
            if button == 1:
                emit_command('show-context')
            elif button == 4:
                self.keypress(size, 'page up')
                return
            elif button == 5:
                self.keypress(size, 'page down')
                return
        self.__super.mouse_event(size, event, button, col, row, focus)

class ManifestViewer(Body):
    """Manifest viewer"""

    def __init__(self, walker, ctx, *args, **kwargs):
        self.manifest_walker = ManifestWalker(walker=walker, ctx=ctx,
                                              manage_description=True,
                                              *args, **kwargs)
        body = ListBox(self.manifest_walker)
        self.__super.__init__(body=body, *args, **kwargs)
        self.title = 'Manifest'

    def render(self, size, focus=True):
        '''Render the manifest viewer. Always use the focus style.'''
        return self.__super.render(size, True)

    def mouse_event(self, size, event, button, col, row, focus):
        """Scroll content"""
        if urwid.util.is_mouse_press(event):
            if button == 4:
                self.keypress(size, 'page up')
                return
            elif button == 5:
                self.keypress(size, 'page down')
                return
        self.__super.mouse_event(size, event, button, col, row, focus)

class SourceViewer(Body):
    """Source Viewer"""
    def __init__(self, text, *args, **kwargs):
        self._source = SourceText(text, wrap='clip')
        body = ListBox([self._source])
        self.__super.__init__(body=body)

    def mouse_event(self, size, event, button, col, row, focus):
        """Scroll content"""
        if urwid.util.is_mouse_press(event):
            if button == 4:
                self.keypress(size, 'page up')
                return
            elif button == 5:
                self.keypress(size, 'page down')
                return
        self.__super.mouse_event(size, event, button, col, row, focus)

class ContextViewer(Columns):
    """Context viewer (manifest and source)"""
    MANIFEST_SIZE = 0.3
    def __init__(self, walker, *args, **kwargs):
        self.walker = walker
        self._manifest = ManifestViewer(walker=walker, ctx=None)
        self._source = SourceViewer('')
        widget_list = [('weight', 1 - self.MANIFEST_SIZE, self._source),
                       ('fixed', 1, AttrWrap(SolidFill(' '), 'banner')),
                       ('weight', self.MANIFEST_SIZE, self._manifest),
                       ]
        self.__super.__init__(widget_list=widget_list, *args, **kwargs)
        connect_signal(self._manifest.body.body, 'focus changed', self.update_source)

    def update_source(self, filename):
        """Update the source content."""
        ctx = self._manifest.body.body.ctx
        if filename is None:
            data = ctx.description()
            lexer = lexers.RstLexer()
        else:
            graph = self.walker.graph
            rev = ctx.rev()
            flag, data = graph.filedata(filename, rev, 'diff')
            lexer = None
            if flag == '=':
                lexer = lexers.DiffLexer() if flag == '=' else None
            elif flag == '-' or flag == '':
                lexer = lexers.DiffLexer()
                data = '- Removed file'
            elif flag == '+':
                lexer = None
        self._source._source.set_text(data or '')
        self._source._source.lexer = lexer

    def keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        widths = self.column_widths(size)
        maxrow = size[1]
        if hg_command_map[key]  == 'manifest up':
            _size = widths[2], maxrow
            self._manifest.keypress(_size, 'up')
        elif hg_command_map[key] == 'manifest down':
            _size = widths[2], maxrow
            self._manifest.keypress(_size, 'down')
        if hg_command_map[key]  == 'source up':
            _size = widths[0], maxrow
            self._source.keypress(_size, 'up')
        elif hg_command_map[key] == 'source down':
            _size = widths[0], maxrow
            self._source.keypress(_size, 'down')

        elif hg_command_map[key]  == 'manifest page up':
            _size = widths[2], maxrow
            self._manifest.keypress(_size, 'page up')
        elif hg_command_map[key] == 'manifest page down':
            _size = widths[2], maxrow
            self._manifest.keypress(_size, 'page down')
        if hg_command_map[key]  == 'source page up':
            _size = widths[0], maxrow
            self._source.keypress(_size, 'page up')
        elif hg_command_map[key] == 'source page down':
            _size = widths[0], maxrow
            self._source.keypress(_size, 'page down')

        else:
            return key

class RepoViewer(Pile):
    """Repository viewer (graphlog and context)"""

    CONTEXT_SIZE = 0.5

    def __init__(self, repo, *args, **kwargs):
        self.repo = repo
        self._show_context = 0 # O:hide, 1:half, 2:maximized
        walker = HgRepoListWalker(repo)
        self._graphlog = GraphlogViewer(walker=walker)
        self._context = ContextViewer(walker=walker)
        widget_list = [('weight', 1 - self.CONTEXT_SIZE, self._graphlog),
                       #('weight', self.CONTEXT_SIZE, self._context),
                       ]
        self.__super.__init__(widget_list=widget_list, focus_item=0)
        connect_signal(self._graphlog.body.body, 'focus changed',
                       self._context._manifest.body.body.set_ctx)
        self._graphlog.body.body.set_focus(0) # ensure first focus signal

    def register_commands(self):
        """Register commands and commands of bodies"""
        register_command('hide-context', 'Hide context pane.')
        register_command('show-context', 'Show context pane.',
                         CA('height', float,
                         'Relative height [0-1] of the context pane.'))
        register_command('maximize-context', 'Maximize context pane.')
        self._graphlog.register_commands()
        connect_command('hide-context', self.hide_context)
        connect_command('show-context', self.show_context)
        connect_command('maximize-context', self.maximize_context)

    def unregister_commands(self):
        """Unregister commands and commands of bodies"""
        self._graphlog.unregister_commands()

    def hide_context(self):
        ''' hide the context widget'''
        if self._show_context == 0: # already hidden
            return
        self.item_types[:] = [('weight', 1)]
        self.widget_list[:] = [self._graphlog]
        self._show_context = 0

    def maximize_context(self):
        '''hide the graphlog widget'''
        if self._show_context == 2: # already maximized
            return
        self.item_types[:] = [('weight', 1)]
        self.widget_list[:] = [self._context]
        self._show_context = 2

    def show_context(self, height=None):
        '''show context and graphlog widgets'''
        if self._show_context == 1: # already half
            return
        if height is None:
            height = self.CONTEXT_SIZE
        self.item_types[:] = [('weight', 1 - height),
                              ('weight', height),]
        self.widget_list[:] = [self._graphlog, self._context]
        self._show_context = 1

    def keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        if self._show_context == 0 and hg_command_map[key] == 'validate':
            self.show_context()
            return
        if hg_command_map[key] == 'close pane' and self._show_context > 0:
            # allows others to catch 'close pane'
            self.hide_context()
            return
        if  self._show_context < 2:
            if hg_command_map[key]  == 'graphlog up':
                _size = self.get_item_size(size, 0, True)
                self._graphlog.keypress(_size, 'up')
                return
            if hg_command_map[key]  == 'graphlog down':
                _size = self.get_item_size(size, 0, True)
                self._graphlog.keypress(_size, 'down')
                return
            if hg_command_map[key]  == 'graphlog page up':
                _size = self.get_item_size(size, 0, True)
                self._graphlog.keypress(_size, 'page up')
                return
            if hg_command_map[key]  == 'graphlog page down':
                _size = self.get_item_size(size, 0, True)
                self._graphlog.keypress(_size, 'page down')
                return
        if self._show_context > 0:
            idx = 1 if self._show_context == 1 else 0
            _size = self.get_item_size(size, idx, True)
            return self._context.keypress(_size, key)
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        """Hide context"""
        if urwid.util.is_mouse_press(event):
            if button == 3:
                emit_command('hide-context')
                return
        self.__super.mouse_event(size, event, button, col, row, focus)

# __________________________________________________________________ functions

def inotify(mainloop):
    """add inotify watcher to the mainloop"""
    try:
        from hgviewlib.inotify import Inotify as Inotify
    except ImportError:
        return

    class UrwidInotify(Inotify):
        def __init__(self, *args, **kwargs):
            super(UrwidInotify, self).__init__(*args, **kwargs)
            self._input_timeout = None

        def process_finally(self):
            """Really process the inotify event"""
            self._input_timeout = None
            super(UrwidInotify, self).process()

        def process_on_any_event(self):
            """Process all inotify events and prevent over-processing"""
            # use the urwid mainloop to schedule the screen refreshing in 0.2s
            # and ignore events received during this time.
            # It prevents over-refreshing (See ../inotify.py comments).
            if self._input_timeout is None:
                self._input_timeout = mainloop.set_alarm_in(
                        0.2, lambda *args: self.process_finally())
            self.read_events()
    try:
        refresh = lambda: emit_command('refresh')
        inot = UrwidInotify(mainloop.widget.get_body().repo, refresh)
    except:
        return
    mainloop.event_loop.watch_file(inot.get_fd(), inot.process_on_any_event)
    # add watchers thought a thread to reduce start duration with a big repo
    threading.Thread(target=inot.update).start()

def main():
    '''main entry point'''

    class MissingViewer:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
            'This feature has not yet been implemented. Comming soon ...')

    body = choose_viewer(MissingViewer, MissingViewer, MissingViewer, 
                         RepoViewer)
    body = AttrWrap(body, 'body')
    mainframe = MainFrame('repoviewer', body)
    screen = Screen()
    mainloop = urwid.MainLoop(mainframe, PALETTE, screen)

    enable_inotify = True # XXX config
    optimize_inotify = True # XXX config
    if enable_inotify:
        if optimize_inotify:
            import ctypes.util
            orig = ctypes.util.find_library
            ctypes.util.find_library = lambda lib: None # durty optim
        inotify(mainloop)
        if optimize_inotify:
            ctypes.util.find_library = orig

    connect_logging(mainloop, level=logging.DEBUG)
    mainframe.register_commands()
    mainloop.run()
    mainframe.unregister_commands()

if __name__ == '__main__':
    main()
