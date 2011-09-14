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
from textwrap import wrap

from hgviewlib.hgviewhelp import long_help_msg

from hgviewlib.curses.mainframe import BodyMixin

class HelpViewer(urwid.AttrWrap, BodyMixin):
    """A body to display a help message (or the global program help)"""

    title = 'help'

    def __init__(self, messages=None, *args, **kwargs):
        # cut line ?
        if messages is None:
            messages = long_help_msg
        if isinstance(messages, str):
            messages = (messages,)
        pads = [build_pad_text(msg) for msg in messages]
        listbox = urwid.ListBox(urwid.SimpleListWalker(pads))
        self.__super.__init__(listbox, 'body', *args, **kwargs)

def build_pad_text(message):
    """return a pad with a text that contains a message.
    """
    text = urwid.Text(message)
    pad = urwid.Padding(text, ('fixed left', 2), ('fixed right', 2), 20)
    return pad

