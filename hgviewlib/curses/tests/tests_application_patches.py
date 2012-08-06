# -*- coding: utf-8 -*-
# Copyright (c) 2003-2012 LOGILAB S.A. (Paris, FRANCE).
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
# this program.  If not, see <http://www.gnu.org/licenses/>.

from doctest import testmod
from unittest import main, TestCase

import logging

import urwid

from hgviewlib.curses.application import *

class TestConnectLogging(TestCase):
    def setUp(self):
        from urwid import Text, Filler, Text, raw_display, MainLoop
        from hgviewlib.curses.application import connect_logging
        from hgviewlib.curses import MainFrame, Body
        import logging
        PALETTE = [('default','default','default'),
                   ('edit', 'white', 'default'),
                   ('banner','black','light gray'),
                   ('DEBUG', 'yellow', 'default'),
                   ('INFO', 'dark gray', 'default'),
                   ('WARNING', 'brown', 'default'),
                   ('ERROR', 'light red', 'default'),
                   ('CRITICAL', 'white', 'dark red'),
                  ]
        self.mainframe = MainFrame('', Body(Filler(Text('Hello world'))))
        screen = raw_display.Screen()
        mainloop = MainLoop(self.mainframe, PALETTE, screen)
        connect_logging(mainloop, logging.DEBUG)

    def test_simple_info(self):
        logging.info('noo')
        res = self.mainframe.render((15, 2), False).text
        self.assertEqual('noo', self.mainframe.footer.get_text()[0])
        self.assertEqual('INFO', self.mainframe.footer.attr)

    def test_display_traceback(self):
        try:
            1/0
        except:
            logging.debug('hello world', exc_info=True)
        res = self.mainframe.footer.get_text()[0].splitlines()
        ref = ['hello world', 'Traceback (most recent call last):']
        self.assertEqual(ref, res[:2])

