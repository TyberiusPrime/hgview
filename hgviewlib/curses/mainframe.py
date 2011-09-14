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
import logging
import urwid.raw_display
from urwid import AttrWrap as W

from hgviewlib.curses import helpviewer
from hgviewlib.curses import (CommandError, CommandArg as CA,
                              register_command, unregister_command,
                              emit_command, connect_command,
                              help_command,
                              hg_command_map)

def quitall():
    """
    usage: quall

    Quit the program
    """
    raise urwid.ExitMainLoop()

def quit(mainframe):
    """
    usage: quit

    Close the current buffer
    """
    try:
        mainframe.pop()
    except StopIteration: # last body => quit program
        quitall()

class MainFrame(urwid.Frame):
    """Main console frame that mimic the vim interface.

    You shall *register_commands* at startup then *unregister_commands* at end.

    """
    def __init__(self, name, body, *args, **kwargs):
        footer = Footer()
        self._bodies = {name:body}
        self._visible = name
        self.__super.__init__(body=body, header=None, footer=footer,
                              *args, **kwargs)

    def register_commands(self):
        register_command(('quit','q'), 'Close the current pane.')
        register_command(('quitall', 'qa'), 'Quit the program.')
        register_command(('refresh', 'r'), 'Refresh the display')
        register_command(('help', 'h'), 'Show the help massage.',
                         CA('command', str,
                            ('command name for which to display the help. '
                             'Display the global help if omitted.')))

        connect_command('quit', quit, args=(self,))
        connect_command('quitall', quitall)
        connect_command('help', self.show_command_help)
        self.body.register_commands()


    def unregister_commands(self):
        unregister_command('quit')
        unregister_command('q')
        unregister_command('quitall')
        unregister_command('qa')
        unregister_command('help')
        unregister_command('h')
        self.body.unregister_commands()

    def __del__(self):
        self.unregister_command()

    def _get_visible(self):
        return self._visible
    def _set_visible(self, name):
        self._visible = name
        self.body = self._bodies[self._visible]
    visible = property(_get_visible, _set_visible, None,
                       'name of the visible body')

    def add(self, name, body):
        """Add a body to the mainframe and focus on it"""
        self._bodies[name] = body
        self.visible = name

    def pop(self, name=None):
        """Remove and return a body (default to current). Then focus on the 
        last available or raise StopIteration."""
        if name is None:
            name = self.visible
        ret = self._bodies.pop(name)
        self.visible = self._bodies.__iter__().next()

    def __contain__(self, name):
        return name in self._bodies

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
        if hg_command_map[key] == 'command key':
            self.set_focus('footer')
            self.footer.unhandled_key(size, key)
        elif key == 'enter':
            self.set_focus('body')
        elif hg_command_map[key] == 'escape':
            self.footer.set('default', '', '')
            self.set_focus('body')
        elif hg_command_map[key] == 'close pane':
            emit_command('quit')
        else:
            cmd = hg_command_map[key]
            if cmd and cmd[0] == '@':
                emit_command(hg_command_map[key][1:])

    def show_command_help(self, command=None):
        """
        usage: edit [command]

        Show the help massage of the ``command``.

        :command: a command name for which to display the help.
                  If omited, the overall program help is displayed.
        """
        doc = None
        if command:
            logging.info(help_command(command))
        else:
            helpbody = helpviewer.HelpViewer(doc)
            helpbody.title = 'Main help'
            self.add('help', helpbody)
            logging.info('":q<CR>" to quit.')


    # better name for header as we use it as banner
    banner = property(urwid.Frame.get_header, urwid.Frame.set_header, None,
                      'banner widget')

class Footer(urwid.AttrWrap):
    """Footer widget used to display message and for inputs.
    """
    def __init__(self, *args, **kwargs):
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
        if hg_command_map[key] == 'command key':
            # just for fun
            label = {'f5':'command: ', ':':':', 'meta x':'M-x '}[key]
            self.set('default', label, '')
        if key == 'enter':
            self.set('default')
            self.call_command()
        elif hg_command_map[key] == 'escape':
            self.set('default', '', '')

    def call_command(self):
        '''Call the command that corresponds to the string given in the edit area
        '''
        cmdline = self.get_edit_text()
        if not cmdline:
            self.footer.set('default', '', '')
            return
        try:
            emit_command(cmdline)
            self.set('info')
        except urwid.ExitMainLoop: # exit, so do not catch this
            raise
        except Exception, err:
            logging.warn(err.__class__.__name__ + ': %s', str(err))
            logging.debug('Exception on: "%s"', cmdline, exc_info=True)

