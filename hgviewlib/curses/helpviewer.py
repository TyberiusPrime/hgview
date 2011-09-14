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

import urwid
from urwid import AttrWrap, Text, Padding, ListBox, SimpleListWalker, Divider
import logging
from textwrap import wrap

from hgviewlib.hgviewhelp import long_help_msg

from hgviewlib.curses import Body, emit_command, utils, hg_command_map

class HelpViewer(Body):
    """A body to display a help message (or the global program help)"""

    def __init__(self, messages=None, *args, **kwargs):
        # cut line ?
        if messages is not None:
            contents = [Text(messages)]
        else:
            contents = []
            #keybindings
            contents.extend(title('Keybindings'))
            messages = []
            keys = hg_command_map._command_defaults.keys()
            longest = max(len(key) for key in keys)
            for name, cmd in hg_command_map._command_defaults.iteritems():
                messages.append(('ERROR', name.rjust(longest)))
                messages.append(('WARNING', ' | '))
                messages.append(cmd)
                messages.append('\n')
            contents.append(Text(messages))
            # mouse
            contents.extend(title('Mouse'))
            messages = [('ERROR', 'button 1'), ('WARNING', ' | '),
                         'Show context\n',
                         ('ERROR', 'button 3'), ('WARNING', ' | '),
                         'Hide context\n',
                         ('ERROR', 'button 4'), ('WARNING', ' | '),
                         'Scroll up\n',
                         ('ERROR', 'button 5'), ('WARNING', ' | '),
                         'Scroll down\n',
            ]
            contents.append(Text(messages))
            # commands
            contents.extend(title('Commands List'))
            messages = []
            for name, help in utils.help_commands():
                messages.append(('ERROR', '\ncommand: "%s"\n'%name))
                messages.extend(help)
            contents.append(Text(messages))


        listbox = ListBox(SimpleListWalker(contents))
        self.__super.__init__(body=listbox, *args, **kwargs)

    def _keypress(self, size, key):
        "allow subclasses to intercept keystrokes"
        key = self.__super.keypress(size, key)
        if key:
            self.unhandled_key(size, key)
        return key

    def unhandled_key(self, size, key):
        """Overwrite this method to intercept keystrokes in subclasses.
        Default behavior: run command from ':xxx'
        """
        if key in (':', 'esc', 'q'):
            emit_command('quit')
            logging.info('')
        else:
            return key

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

def title(title):
    contents = []
    contents.append(Divider('-'))
    contents.append(AttrWrap(Padding(Text(title), 'center'), 'CRITICAL'))
    contents.append(Divider('-'))
    return contents

