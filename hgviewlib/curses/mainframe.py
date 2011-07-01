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
Module that contains the curses main frame, using urwid, that mimics the 
vim/emacs interface.

+------------------------------------------------+
|                                                |
|                                                |
| body                                           |
|                                                |
|                                                |
+------------------------------------------------+
| banner                                         |
+------------------------------------------------+
| footer                                         |
+------------------------------------------------+

* *body* display the main contant
* *banner* display some short information on the current program state
* *footer* display program logs and it is used as input area

"""

import urwid
import urwid.raw_display
from urwid import AttrWrap as W
from urwid.decoration import Filler, CanvasCombine

from hgviewlib.curses.exceptions import CommandError

class CommandsList(object):
    "basic commands list"
    @staticmethod
    def quit(mainframe):
        "Quit the program"
        raise urwid.ExitMainLoop()
    q = quit

class MainFrame(urwid.Frame):
    """Main console frame that mimic the vim interface.
    """
    def __init__(self, body, title='', *args, **kwargs):
        header = W(urwid.Text(title), 'banner')
        footer = Footer(self)
        body.mainframe = body.parent = self
        self.__super.__init__(body, header=header, footer=footer,
                              *args, **kwargs)

    def keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        key = self.__super.keypress(size, key)
        if key:
            self.unhandled_key(size, key)
        return key

    def unhandled_key(self, size, key):
        """Override this method to intercept keystrokes in subclasses.
        Default behavior: run command from ':xxx'
        """
        if key == ':':
            self.set_focus('footer')
            self.footer.unhandled_key(size, ':')
        elif key == 'enter':
            self.set_focus('body')
        elif key == 'esc':
            self.set_focus('body')

    def call_command(self):
        '''Call the command that corresponds to the string given in the edit area
        '''
        cmd = self.footer.get_edit_text().strip()
        if not cmd:
            self.set('default', '', '')
            return
        try:
            cmds = cmd.split()
            name = cmds[0]
            args = cmds[1:]
            getattr(self.body.commands, name)(self, *args)
        except urwid.ExitMainLoop: # exit, so do not catch this
            raise
        except AttributeError:
            self.footer.set('warn', 'unknown command: ', name)
        except Exception, err:
            self.footer.set('warn', err.__class__.__name__ +': ', str(err))

    # better name for header as we use it as banner
    banner = property(urwid.Frame.get_header, urwid.Frame.set_header, None,
                      'banner widget')

    def render(self, size, focus=False):
        """Render frame and return it."""
        # Copy the original method code to put the header at bottom :?
        # (vim-like banner)
        maxcol, maxrow = size
        (htrim, ftrim),(hrows, frows) = self.frame_top_bottom(
                                                        (maxcol, maxrow), focus)

        combinelist = []

        if ftrim+htrim < maxrow:
            body = self.body.render((maxcol, maxrow-ftrim-htrim),
                                    focus and self.focus_part == 'body')
            combinelist.append((body, 'body', self.focus_part == 'body'))

        bann = None
        if htrim and htrim < hrows:
            bann = Filler(self.banner, 'bottom').render(
                    (maxcol, htrim), focus and self.focus_part == 'banner')
        elif htrim:
            bann = self.banner.render(
                    (maxcol,), focus and self.focus_part == 'banner')
            assert bann.rows() == hrows, "rows, render mismatch"
        if bann:
            combinelist.append((bann, 'banner', self.focus_part == 'banner'))

        foot = None
        if ftrim and ftrim < frows:
            foot = Filler(self.footer, 'bottom').render((maxcol, ftrim),
                focus and self.focus_part == 'footer')
        elif ftrim:
            foot = self.footer.render(
                    (maxcol,), focus and self.focus_part == 'footer')
            assert foot.rows() == frows, "rows, render mismatch"
        if foot:
            combinelist.append((foot, 'footer', self.focus_part == 'footer'))

        return CanvasCombine(combinelist)

class Footer(urwid.AttrWrap):
    """Footer widget used to display message and for inputs.
    """
    def __init__(self, mainframe, *args, **kwargs):
        self.mainframe = mainframe
        self.__super.__init__(
            urwid.Edit('type ":help<Enter>" for information'),
            'footer_style', *args, **kwargs)

    def keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        key = self.__super.keypress(size, key)
        if key:
            self.unhandled_key(size, key)
        return key

    def set(self, style=None, caption=None, edit=None):
        '''Set the footer content.

        :param style: a string that corresponds to a palette entry name
        :param caption: a string to display in caption
        :param edit: a string to display in the edit area
        '''
        if style is not None:
            self.set_attr(style)
        if caption is not None:
            self.set_caption(caption)
        if edit is not None:
            self.set_edit_text(edit)

    def unhandled_key(self, size, key):
        """Overwrite this method to intercept keystrokes in subclasses.
        Default behavior: run command from ':xxx'
        """
        if key == ':':
            self.set('default', ':', '')
        if key == 'enter':
            self.set('default')
            self.mainframe.call_command()
        elif key == 'esc':
            self.set('default', '', '')

if __name__ == '__main__':

    from urwid import AttrWrap, Padding, Text, SimpleListWalker, ListBox
    from hgviewlib.util import find_repository
    from mercurial import hg, ui
    PALETTE = [
        ('default','default','default', 'bold'),
        ('warn','white','dark red', 'bold'),
        ('body','white','black', 'standout'),
        ('banner','black','light gray', 'bold'),
        ('focus','black','dark green', 'bold'),
        ('entry', 'dark blue', 'default', 'bold')
        ]

    class Body(AttrWrap):
        commands = CommandsList
        def __init__(self, *args, **kwargs):
            # XXX: just for trying, shall be removed
            repo = hg.repository(ui.ui(), find_repository('.'))
            def description(rev):
                desc = repo.changectx(rev).description().splitlines()[0]
                return '%i> %s' % (rev, desc)
            lines = [AttrWrap(Padding(Text(('entry', description(rev))),
                                      ('fixed left', 2), ('fixed right', 2),20),
                              'default','focus')
                      for rev in repo.changelog]
            self.__super.__init__(ListBox(SimpleListWalker(lines)), 'body',
                                  *args, **kwargs)
    frame = MainFrame(Body(), 'Type ":q<enter>" to quit')
    screen = urwid.raw_display.Screen()
    urwid.MainLoop(frame, PALETTE, screen).run()

