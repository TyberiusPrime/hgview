
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

__all__ = ['Body']

class Body(Frame):
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
