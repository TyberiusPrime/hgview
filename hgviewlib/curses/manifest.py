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
Module that contains the help body.
"""

from urwid import (Text, AttrWrap, SimpleListWalker, ListBox, ListWalker,
                   Columns)
from urwid.signals import connect_signal, emit_signal, disconnect_signal
from textwrap import wrap

from hgviewlib.util import isbfile, bfilepath
from hgviewlib.curses import Body, SelectableText

DIFF = 'diff'
FILE = 'file'


class ManifestWalker(ListWalker):
    """
    Walk through modified files.
    """

    signals = ['focus changed']

    def __init__(self, walker, ctx, manage_description=False, *args, **kwargs):
        """
        :ctx: mercurial context instance
        :description: display context description as a file if True
        """
        self._cached_flags = {}
        self._walker = walker
        self._ctx = ctx
        self.manage_description = manage_description
        if manage_description:
            self._focus = -1
        else:
            self._focus = 0
        if self._ctx:
            self._files = tuple(self._ctx.files())
        else:
            self._files = ()
        super(ManifestWalker, self).__init__()

    def get_filename(self):
        if self._focus < 0:
            return
        return self._files[self._focus]
    def set_filename(self, file):
        focus = self._files.index(file)
        self.set_focus(focus)
    filename = property(get_filename, set_filename, None,
                        'File name under focus.')

    def get_ctx(self):
        return self._ctx
    def set_ctx(self, ctx):
        self._cached_flags.clear()
        self._ctx = ctx
        self._files = tuple(self._ctx.files())
        del self.focus
        self._modified()
    ctx = property(get_ctx, set_ctx, None, 'Current changeset context')

    def get_focus(self):
        try:
            return self.data(self._focus), self._focus
        except IndexError:
            return None, None
    def set_focus(self, focus):
        self._focus = focus
        emit_signal(self, 'focus changed', self.filename)
    def reset_focus(self):
        """Reset focus"""
        if self.manage_description:
            self._focus = -1
        else:
            self._focus = 0
        emit_signal(self, 'focus changed', self.filename)
    focus = property(lambda self: self._focus, set_focus, reset_focus, 
                     'focus index')

    def get_prev(self, prev):
        focus = prev - 1
        try:
            return self.data(focus), focus
        except IndexError:
            return None, None

    def get_next(self, next):
        focus = next + 1
        try:
            return self.data(focus), focus
        except IndexError:
            return None, None

    def data(self, focus):
        if self._ctx is None:
            raise IndexError('context is None')
        if (focus < -1) or ((not self.manage_description) and (focus < 0)):
            raise IndexError(focus)

        if focus == -1:
            return AttrWrap(SelectableText('-*- description -*-',
                                           align='right', wrap='clip'),
                            'DEBUG', 'focus')
        filename = self._files[focus]

        # Computing the modification flag may take a long time, so cache it.
        flag = self._cached_flags.get(filename)
        if flag is None:
            flag = self._cached_flags.setdefault(filename,
                    self._walker.graph.fileflag(filename, self._ctx.rev()))
        if not isinstance(flag, str): # I don't know why it could occures :P
            flag = '?'
        return  AttrWrap(SelectableText(filename, align='right', wrap='clip'),
                         flag, 'focus')

    def filedata(self, filename):
        '''return (modification flag, file content)'''
        graph = self._walker.graph
        return graph.filedata(filename, self._ctx.rev(), 'diff',
                              flag=self._cached_flags.get(filename))

