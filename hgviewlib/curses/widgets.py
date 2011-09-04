
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
"""
from urwid import Frame, Text, AttrWrap

# XXX
from pygments import lex, lexers
from pygments.util import ClassNotFound

__all__ = ['Body', 'SelectableText', 'SourceText']


class SelectableText(Text):
    """A seletable Text widget"""
    _selectable = True
    def keypress(self, size, key):
        return key

class Body(Frame):
    """A suitable widget that shall be used as a body for the mainframe.

    +------------------+
    |                  |
    |       Body       |
    |                  |
    +------------------+
    |  Text with title |
    +------------------+

    Use the ``title`` property to chage the footer text.

    """
    def __init__(self, body):
        footer = AttrWrap(Text(''), 'banner')
        super(Body, self).__init__(body=body, footer=footer, header=None,
                                   focus_part='body')

    def _get_title(self):
        return self._footer.text
    def _set_title(self, title):
        self._footer.set_text(title)
    def _clear_title(self):
        self._footer.set_title('')
    title = property(_get_title, _set_title, _clear_title, 'Body title')

    def register_commands(self):
        """register commands"""
        pass

    def unregister_commands(self):
        """unregister commands"""
        pass

class SourceText(SelectableText):
    def __init__(self, text, filename=None, lexer=None, *args, **kwargs):
        self._lexer = lexer
        self.filename = filename
        self.__super.__init__(text, *args, **kwargs)

    def get_lexer(self):
        """Return the current lexer"""
        return self._lexer
    def update_lexer(self, lexer=None):
        """
        Update highlighting using the given lexer or by inspecting filename
        or text content if lexer is None.
        """
        if not self.text:
            return
        text = self.text
        if lexer is None and self.filename: # try to get lexer from filename
            try:
                lexer = lexers.get_lexer_for_filename(self.filename, text)
            except ClassNotFound:
                pass
        if lexer is None and text: # try to get lexer from text
            try:
               lexer = lexers.guess_lexer(text)
            except ClassNotFound:
                pass
        self._lexer = lexer
        if lexer == None: # No lexer found => finish
            return
        self.set_text(list(lex(text, self._lexer)))
    def clear_lexer(self):
        """Remove highlighting"""
        self.set_text(self.text)
    lexer = property(get_lexer, update_lexer, clear_lexer, 'hihglight lexer')

