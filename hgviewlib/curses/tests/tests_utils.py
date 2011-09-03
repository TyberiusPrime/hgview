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

from doctest import testmod
from unittest import main, TestCase

import logging

import urwid

from hgviewlib.curses import utils, exceptions

class TestConsoleHandler(TestCase):
    def setUp(self):
        self.redrawed = []
        self.displayed = []
        def redraw():
            self.redrawed.append(True)
        def display(levelname, message):
            self.displayed.append(levelname)
            self.displayed.append(message)

        logger = logging.getLogger()
        handler = utils.ConsoleHandler(display, redraw, logging.CRITICAL)
        logger.addHandler(handler)

    def test_emit_message(self):
        logging.warn('hello world')
        self.assertEqual(['WARNING', 'hello world'], self.displayed)

    def test_redraw_on_critical(self):
        logging.critical("babar")
        self.assertEqual([True], self.redrawed)

class TestConnectLogging(TestCase):
    def setUp(self):
        from urwid import Text, Filler, Text, raw_display, MainLoop
        from hgviewlib.curses import connect_logging, MainFrame, Body
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

class TestCommandsRegister(TestCase):

    def tearDown(self):
        utils.unregister_command('foo')

    def test_unregister_not_registered(self):
        res = utils.unregister_command('babar')
        self.assertEqual(None, res)

    def test_register_multiple_times(self):
        utils.register_command('foo', 'A command')
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.register_command, 'foo', 'Another command')

    def test_register_minimal(self):
        utils.register_command('foo', 'A command')
        res = utils.unregister_command('foo')
        self.assertEqual(('A command', (), []), res)
        utils.register_command('foo', 'Another command') # no exception
        res = utils.unregister_command('foo')
        self.assertEqual(('Another command', (), []), res)

    def test_register_bad_args(self):
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.register_command, 'foo', '', 1)

    def test_register_complete(self):
        args = (utils.CommandArg('arg1', int, 'argument1'),
                utils.CommandArg('arg2', float, 'argument2'),)
        utils.register_command('foo', 'A command', *args)
        res = utils.unregister_command('foo')
        self.assertEqual(('A command', args, []), res)

    def test_help_minimal(self):
        utils.register_command('foo', 'A command')
        ref = ['usage: foo',
               'A command ',
               '          ']
        res = urwid.Text(utils.help_command('foo')).render((10,)).text
        self.assertEqual(ref, res)

    def test_help_complete(self):
        args = (utils.CommandArg('arg1', int, 'argument1'),
                utils.CommandArg('arg2', float, 'argument2'),)
        utils.register_command('foo', 'A command', *args)
        res = urwid.Text(utils.help_command('foo')).render((20,)).text
        ref = ['usage: foo arg1 arg2',
               'A command           ',
               ':arg1: argument1    ',
               ':arg2: argument2    ',
               '                    ',
               ]
        self.assertEqual(ref, res)

    def test_disconnect_not_registered(self):
        callback = lambda: True
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.disconnect_command, 'foo', callback)

    def test_disconnect_not_connected(self):
        utils.register_command('foo', 'A command')
        callback = lambda: True
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.disconnect_command, 'foo', callback)

    def connect_not_registered(self):
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.connect_command, 'foo', callback)

    def test_connects_noargs(self):
        utils.register_command('foo', 'A command')
        func1 = lambda: True
        func2 = lambda: True
        utils.connect_command('foo', func1)
        utils.connect_command('foo', func2)
        ref = ('A command', (), [utils.CommandEntry(func1, (), {}),
                                 utils.CommandEntry(func2, (), {})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_connect_complete(self):
        utils.register_command('foo', 'A command')
        func1 = lambda: True
        func2 = lambda a, b, c, d: True
        utils.connect_command('foo', func1)
        utils.connect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        ref = ('A command', (),
               [utils.CommandEntry(func1, (), {}),
                utils.CommandEntry(func2, (1, 2), {'c':3, 'd':4})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_disconnect(self):
        utils.register_command('foo', 'A command')
        func1 = lambda: True
        func2 = lambda a, b, c, d: True
        utils.connect_command('foo', func1)
        utils.connect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        utils.disconnect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        ref = ('A command', (), [utils.CommandEntry(func1, (), {})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_emit_not_registered(self):
        self.assertRaises(exceptions.RegisterCommandError,
                          utils.emit_command, 'foo')

    def test_emit_not_connected(self):
        utils.register_command('foo', 'A command')
        self.assertEqual(False, utils.emit_command('foo'))

    def test_emit_minimal(self):
        utils.register_command('foo', 'A command')

        func3 = lambda a, b, c, d: a==1 and b==2 and c==3 and d==5
        utils.connect_command('foo', func3, args=(1,2), kwargs={'c':3, 'd':4})
        self.assertEqual(False, utils.emit_command('foo'))

        func1 = lambda: True
        utils.connect_command('foo', func1)
        self.assertEqual(True, utils.emit_command('foo'))
        utils.disconnect_command('foo', func1)

        func2 = lambda a, b, c, d: a==1 and b==2 and c==3 and d==4
        utils.connect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        self.assertEqual(True, utils.emit_command('foo'))

    def test_emit_with_args(self):
        utils.register_command('foo', 'A command')

        func3 = lambda a, b, c, d: a==1 and b==2 and c==3 and d==5
        utils.connect_command('foo', func3, args=(1,), kwargs={'c':3})
        self.assertEqual(False, utils.emit_command('foo', args=(2,), kwargs={'d':4}))

        func1 = lambda a, d: a==2 and d==4
        utils.connect_command('foo', func1)
        self.assertEqual(True, utils.emit_command('foo', args=(2,), kwargs={'d':4}))
        utils.disconnect_command('foo', func1)

        func2 = lambda a, b, c, d: a==1 and b==2 and c==3 and d==4
        utils.connect_command('foo', func3, args=(1,), kwargs={'c':3})
        self.assertEqual(False, utils.emit_command('foo', args=(2,), kwargs={'d':4}))

    def test_emit_convert_cmdargs(self):
        cmd = '1 2 "2 + 1" 4.'
        args = (utils.CommandArg('a', int, 'argument1'),
                utils.CommandArg('b', str, 'argument2'),
                utils.CommandArg('c', eval, 'argument2'),
                utils.CommandArg('d', float, 'argument2'), )
        utils.register_command('foo', 'A command', *args)

        func = lambda a, b, c, d: a==1 and b=="2" and c==3 and d==4.
        utils.connect_command('foo', func)
        self.assertEqual(True, utils.emit_command('foo', cmd))

    def test_emit_convert_mixed(self):
        cmd = '"2 + 1" 4.'
        args = (utils.CommandArg('c', eval, 'argument2'),
                utils.CommandArg('d', float, 'argument2'), )
        utils.register_command('foo', 'A command', *args)

        func3 = lambda a, b, c, d, e, f: (a,b,c,d,e,f) == (1, "2", 3, 4., 5, 6)
        utils.connect_command('foo', func3, args=(1,), kwargs={'e':5})
        self.assertEqual(True, utils.emit_command('foo', cmd, ("2",), {'f':6}))

if __name__ == '__main__':
    testmod(utils)
    main()
