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
    def qall(mf):
        """
        usage: quall
        alias: qa

        Quit the program
        """
        raise urwid.ExitMainLoop()
    qa = qall

    @staticmethod
    def quit(mf):
        """
        usage: quit
        alias: q

        Close the current buffer
        """
        try:
            mf.remove_body()
        except StopIteration: # last body => quit program
            CommandsList.qall(mf)
    q = quit

    @staticmethod
    def help(mf, command=None):
        """
        usage: edit [command]
        alias: h

        Show the help massage of the ``command``

        :param command: a command name for which to display the help.
                        If omited, the overall program help is displayed.
        """
        # XXX
        from hgviewlib.curses import helpviewer
        from textwrap import dedent
        doc = None
        if command:
            try:
                doc = dedent(getattr(mf.get_body().commands, command).func_doc)
                mf.set_focus('footer')
                mf.footer.set('default', '', doc)
            except AttributeError:
                raise CommandError('Could not find help for "%s"' % command)
        else:
            helpbody = helpviewer.HelpViewer(doc)
            helpbody.title = 'main help'
            mf.append_body(helpbody)
    h = help

class BodyMixin(object):
    commands = CommandsList
    title = ''
    name = None
    def __init__(self):
        self.mainframe = None
    def __eq__(self, body):
        return self.name == body.name

class MainFrame(urwid.Frame):
    """Main console frame that mimic the vim interface.
    """
    def __init__(self, body, *args, **kwargs):
        header = W(urwid.Text(body.title), 'banner')
        footer = Footer(self)
        self.bodies = {body.name:body}
        self.__super.__init__(body=body, header=header, footer=footer,
                              *args, **kwargs)

    def append_body(self, body):
        """ add a body buffer to the mainframe and focus on it"""
        self.set_body(body)
        self.banner.set_text(body.title)
        self.bodies[body.name] = body
        body.mainframe = self

    def remove_body(self, body=None):
        """Remove the body buffer (default to current) and focus on the last"""
        if body is None:
            body = self.body
        del self.bodies[body.name]
        self.append_body(self.bodies.iteritems().next()[1])

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
            self.footer.set('default', '', '')
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

