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

try:
    import pygments
    from pygments import lexers
except ImportError:
    # pylint: enable-msg=C0103
    pygments = None

import urwid
from urwid import AttrWrap, Pile, Columns, SolidFill, signals

from hgviewlib.hggraph import HgRepoListWalker
from hgviewlib.util import exec_flag_changed, isbfile

from hgviewlib.curses.graphlog import RevisionsWalker
from hgviewlib.curses.manifest import ManifestWalker
from hgviewlib.curses import (Body, SourceText, ScrollableListBox,
                              register_command, unregister_command,
                              connect_command, emit_command, CommandArg as CA,
                              hg_command_map)

class GraphlogViewer(Body):
    """Graphlog body"""

    def __init__(self, walker, *args, **kwargs):
        self.walker = walker
        self.graphlog_walker = RevisionsWalker(walker=walker)
        body = ScrollableListBox(self.graphlog_walker)
        super(GraphlogViewer, self).__init__(body=body, *args, **kwargs)
        self.title = walker.repo.root
        signals.connect_signal(self.graphlog_walker, 'focus changed',
                               self.update_title)

    def update_title(self, ctx):
        """update title depending on the given context ``ctx``."""
        if ctx is None:
            hex_ = 'UNAPPLIED MQ PATCH'
        elif ctx.node() is None:
            hex_ = 'WORKING DIRECTORY'
        else:
            hex_ = ctx.hex()
        self.title = '%s [%s]' % (self.walker.repo.root, hex_)

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
        return super(GraphlogViewer, self).render(size, True)

    def mouse_event(self, size, event, button, col, row, focus):
        """Scroll content and show context"""
        if urwid.util.is_mouse_press(event):
            if button == 1:
                emit_command('show-context')
        return super(GraphlogViewer, self).mouse_event(size, event, button,
                                                       col, row, True)

class ManifestViewer(Body):
    """Manifest viewer"""

    def __init__(self, walker, ctx, *args, **kwargs):
        self.manifest_walker = ManifestWalker(walker=walker, ctx=ctx,
                                              manage_description=True,
                                              *args, **kwargs)
        body = ScrollableListBox(self.manifest_walker)
        super(ManifestViewer, self).__init__(body=body, *args, **kwargs)
        signals.connect_signal(self.manifest_walker, 'focus changed',
                               self.update_title)
        self.title = 'Manifest'

    def update_title(self, filename):
        '''update the body title.'''
        tot = len(self.manifest_walker)
        if self.manifest_walker.focus < 0:
            self.title = '%i file%s' % (tot, 's' * (tot > 1))
            return
        cur = self.manifest_walker.focus + 1
        self.title = '%i/%i [%i%%]' % (cur, tot, cur*100/tot)

    def render(self, size, focus=True):
        '''Render the manifest viewer. Always use the focus style.'''
        return super(ManifestViewer, self).render(size, True)

class SourceViewer(Body):
    """Source Viewer"""
    def __init__(self, text, *args, **kwargs):
        self.text = SourceText(text, wrap='clip')
        body = ScrollableListBox([self.text])
        super(SourceViewer, self).__init__(body=body, *args, **kwargs)

class ContextViewer(Columns):
    """Context viewer (manifest and source)"""
    signals = ['update source title']
    MANIFEST_SIZE = 0.3
    def __init__(self, walker, *args, **kwargs):
        self.manifest = ManifestViewer(walker=walker, ctx=None)
        self.manifest_walker = self.manifest.manifest_walker
        self.source = SourceViewer('')
        self.source_text = self.source.text

        widget_list = [('weight', 1 - self.MANIFEST_SIZE, self.source),
                       ('fixed', 1, AttrWrap(SolidFill(' '), 'banner')),
                       ('weight', self.MANIFEST_SIZE, self.manifest),
                       ]
        super(ContextViewer, self).__init__(widget_list=widget_list,
                                            *args, **kwargs)

        signals.connect_signal(self.manifest_walker, 'focus changed',
                               self.update_source)
        signals.connect_signal(self, 'update source title',
                               self.update_source_title)

    def update_source_title(self, filename, flag):
        """
        Display information about the file in the title of the source body.
        """
        ctx = self.manifest_walker.ctx
        title = []
        if filename is None:
            title.append(' Description')
        elif flag == '' or flag == '-':
            title += [' Removed file: ', ('focus', filename)]
        else:
            filectx = ctx.filectx(filename)
            flag = exec_flag_changed(filectx)
            if flag:
                title += [' Exec mode: ', ('focus', flag)]
            if isbfile(filename):
                title.append('bfile tracked')
            renamed = filectx.renamed()
            if renamed:
                title += [' Renamed from: ', ('focus', renamed[0])]
            title += [' File name: ', ('focus', filename)]
        self.source.title = title

    def update_source(self, filename):
        """Update the source content."""
        ctx = self.manifest_walker.ctx
        if ctx is None:
            return
        numbering = False
        flag = ''
        if filename is None: # source content is the changeset description
            wrap = 'space' # Do not cut description and wrap content
            data = ctx.description()
            if pygments:
                lexer = lexers.RstLexer()
        else: # source content is a file
            wrap = 'clip' # truncate lines
            flag, data = self.manifest_walker.filedata(filename)
            lexer = None # default to inspect filename and/or content
            if flag == '=' and pygments: # modified => display diff
                lexer = lexers.DiffLexer() if flag == '=' else None
            elif flag == '-' or flag == '': # removed => just say it
                if pygments:
                    lexer = lexers.DiffLexer()
                data = '- Removed file'
            elif flag == '+': # Added => display content
                numbering = True
                lexer = None
        signals.delay_emit_signal(self, 'update source title', 0.05,
                                  filename, flag)
        self.source_text.set_wrap_mode(wrap)
        self.source_text.set_text(data or '')
        if pygments:
            self.source_text.lexer = lexer
        self.source_text.numbering = numbering
        self.source.body.set_focus_valign('top') # reset offset

    def keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        widths = self.column_widths(size)
        maxrow = size[1]
        if hg_command_map[key]  == 'manifest up':
            _size = widths[2], maxrow
            self.manifest.keypress(_size, 'up')
        elif hg_command_map[key] == 'manifest down':
            _size = widths[2], maxrow
            self.manifest.keypress(_size, 'down')
        if hg_command_map[key]  == 'source up':
            _size = widths[0], maxrow
            self.source.keypress(_size, 'up')
        elif hg_command_map[key] == 'source down':
            _size = widths[0], maxrow
            self.source.keypress(_size, 'down')

        elif hg_command_map[key]  == 'manifest page up':
            _size = widths[2], maxrow
            self.manifest.keypress(_size, 'page up')
        elif hg_command_map[key] == 'manifest page down':
            _size = widths[2], maxrow
            self.manifest.keypress(_size, 'page down')
        if hg_command_map[key]  == 'source page up':
            _size = widths[0], maxrow
            self.source.keypress(_size, 'page up')
        elif hg_command_map[key] == 'source page down':
            _size = widths[0], maxrow
            self.source.keypress(_size, 'page down')

        else:
            return key

    def clear(self):
        """Clear content"""
        self.manifest_walker.clear()
        self.source_text.set_text('')

class RepoViewer(Pile):
    """Repository viewer (graphlog and context)"""

    CONTEXT_SIZE = 0.5

    def __init__(self, repo, *args, **kwargs):
        self.repo = repo
        self._show_context = 0 # O:hide, 1:half, 2:maximized

        walker = HgRepoListWalker(repo)
        self.graphlog = GraphlogViewer(walker=walker)
        self.context = ContextViewer(walker=walker)

        widget_list = [('weight', 1 - self.CONTEXT_SIZE, self.graphlog),]

        super(RepoViewer, self).__init__(widget_list=widget_list, focus_item=0,
                                         *args, **kwargs)

    def update_context(self, ctx):
        """Change the current displayed context"""
        if ctx is None: # unapplied patch
            self.context.clear()
            return
        self.context.manifest_walker.ctx = ctx

    def register_commands(self):
        """Register commands and commands of bodies"""
        register_command('hide-context', 'Hide context pane.')
        register_command('show-context', 'Show context pane.',
                         CA('height', float,
                         'Relative height [0-1] of the context pane.'))
        register_command('maximize-context', 'Maximize context pane.')
        self.graphlog.register_commands()
        connect_command('hide-context', self.hide_context)
        connect_command('show-context', self.show_context)
        connect_command('maximize-context', self.maximize_context)

    def unregister_commands(self):
        """Unregister commands and commands of bodies"""
        self.graphlog.unregister_commands()

    def hide_context(self):
        ''' hide the context widget'''
        if self._show_context == 0: # already hidden
            return
        self._deactivate_context()
        self.item_types[:] = [('weight', 1)]
        self.widget_list[:] = [self.graphlog]
        self._show_context = 0

    def maximize_context(self):
        '''hide the graphlog widget'''
        if self._show_context == 2: # already maximized
            return
        self._activate_context()
        self.item_types[:] = [('weight', 1)]
        self.widget_list[:] = [self.context]
        self._show_context = 2

    def show_context(self, height=None):
        '''show context and graphlog widgets'''
        if self._show_context == 1: # already half
            return
        self._activate_context()
        if height is None:
            height = self.CONTEXT_SIZE
        self.item_types[:] = [('weight', 1 - height),
                              ('weight', height),]
        self.widget_list[:] = [self.graphlog, self.context]
        self._show_context = 1

    def _activate_context(self):
        context_walker = self.context.manifest_walker
        graphlog_ctx = self.graphlog.graphlog_walker.get_ctx()
        if context_walker.ctx != graphlog_ctx:
            self.update_context(graphlog_ctx)
        signals.connect_signal(self.graphlog.graphlog_walker, 'focus changed',
                               self.update_context)

    def _deactivate_context(self):
        signals.disconnect_signal(self.graphlog.graphlog_walker,
                                  'focus changed', self.update_context)

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
                self.graphlog.keypress(_size, 'up')
                return
            if hg_command_map[key]  == 'graphlog down':
                _size = self.get_item_size(size, 0, True)
                self.graphlog.keypress(_size, 'down')
                return
            if hg_command_map[key]  == 'graphlog page up':
                _size = self.get_item_size(size, 0, True)
                self.graphlog.keypress(_size, 'page up')
                return
            if hg_command_map[key]  == 'graphlog page down':
                _size = self.get_item_size(size, 0, True)
                self.graphlog.keypress(_size, 'page down')
                return
        if self._show_context > 0:
            idx = 1 if self._show_context == 1 else 0
            _size = self.get_item_size(size, idx, True)
            return self.context.keypress(_size, key)
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        """Hide context"""
        if urwid.util.is_mouse_press(event):
            if button == 3:
                emit_command('hide-context')
                return
        return super(RepoViewer, self).mouse_event(size, event, button, col,
                                                   row, focus)

