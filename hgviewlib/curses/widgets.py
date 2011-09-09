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
A module that contains usefull widgets.
"""
from urwid import Frame, Text, AttrWrap, ListBox
from urwid.util import is_mouse_press

from pygments import lex, lexers
from pygments.util import ClassNotFound

from hgviewlib.curses.canvas import apply_text_layout

__all__ = ['Body', 'ScrollableListBox', 'SelectableText', 'SourceText']


class SelectableText(Text):
    """A seletable Text widget"""
    _selectable = True
    keypress = lambda self, size, key: key

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
        """return the title"""
        return self._footer.get_text()
    def _set_title(self, title):
        """set the title text"""
        self._footer.set_text(title)
    def _clear_title(self):
        """clear the title text"""
        self._footer.set_title('')
    title = property(lambda self: self.footer.text, _set_title, _clear_title, 
                     'Body title')

    def register_commands(self):
        """register commands"""
        pass

    def unregister_commands(self):
        """unregister commands"""
        pass

class ScrollableListBox(ListBox):
    """Scrollable Content ListBox using mouse buttons 4/5"""

    # pylint: disable-msg=R0913
    def mouse_event(self, size, event, button, col, row, focus):
        """Scroll content"""
        if is_mouse_press(event):
            if button == 4:
                self.keypress(size, 'page up')
                return
            elif button == 5:
                self.keypress(size, 'page down')
                return
        return super(ScrollableListBox, self).mouse_event(size, event, button,
                                                          col, row, focus)
    # pylint: enable-msg=R0913

class SourceText(SelectableText):
    """A widget that display source code content.

    It cans number lines and highlight content using pygments
    """
    def __init__(self, text, filename=None, lexer=None, numbering=False,
                 *args, **kwargs):
        self._lexer = lexer
        self.filename = filename
        self.numbering = numbering
        super(SourceText, self).__init__(text, *args, **kwargs)

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
            except (ClassNotFound, TypeError): #TypeError: pygments is confused
                pass
        if lexer is None and text: # try to get lexer from text
            try:
                lexer = lexers.guess_lexer(text)
            except (ClassNotFound, TypeError): #TypeError: pygments is confused
                pass
        self._lexer = lexer
        if lexer == None: # No lexer found => finish
            return
        self.set_text(list(lex(text, self._lexer)))
    def clear_lexer(self):
        """Remove highlighting"""
        self.set_text(self.text)
    lexer = property(get_lexer, update_lexer, clear_lexer, 'hihglight lexer')

    def render(self, size, focus=False):
        """
        Render contents with wrapping, alignment and line numbers.
        """
        (maxcol,) = size
        text, attr = self.get_text()
        trans = self.get_line_translation(maxcol, (text, attr))
        return apply_text_layout(text, attr, trans, maxcol,
                                 numbering=self.numbering)

