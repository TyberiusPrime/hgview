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

from hgviewlib.curses import utils, exceptions

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
        ref = ('A command', (), [(func1, (), {}),
                                 (func2, (), {})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_connect_complete(self):
        utils.register_command('foo', 'A command')
        func1 = lambda: True
        func2 = lambda a, b, c, d: True
        utils.connect_command('foo', func1)
        utils.connect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        ref = ('A command', (),
               [(func1, (), {}),
                (func2, (1, 2), {'c':3, 'd':4})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_disconnect(self):
        utils.register_command('foo', 'A command')
        func1 = lambda: True
        func2 = lambda a, b, c, d: True
        utils.connect_command('foo', func1)
        utils.connect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        utils.disconnect_command('foo', func2, args=(1,2), kwargs={'c':3, 'd':4})
        ref = ('A command', (), [(func1, (), {})])
        res = utils.unregister_command('foo')
        self.assertEqual(ref, res)

    def test_emit_not_registered(self):
        self.assertRaises(exceptions.UnknownCommand,
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
        cmd = 'foo 1 2 2+1 4.'
        args = (utils.CommandArg('a', int, 'argument1'),
                utils.CommandArg('b', str, 'argument2'),
                utils.CommandArg('c', eval, 'argument2'),
                utils.CommandArg('d', float, 'argument2'), )
        utils.register_command('foo', 'A command', *args)

        func = lambda a, b, c, d: a==1 and b=="2" and c==3 and d==4.
        utils.connect_command('foo', func)
        self.assertEqual(True, utils.emit_command(cmd))

    def test_emit_convert_mixed(self):
        cmd = 'foo "2 + 1" 4.'
        args = (utils.CommandArg('c', eval, 'argument2'),
                utils.CommandArg('d', float, 'argument2'), )
        utils.register_command('foo', 'A command', *args)

        func3 = lambda a, b, c, d, e, f: (a,b,c,d,e,f) == (1, "2", 3, 4., 5, 6)
        utils.connect_command('foo', func3, args=(1,), kwargs={'e':5})
        self.assertEqual(True, utils.emit_command(cmd, ("2",), {'f':6}))

if __name__ == '__main__':
    testmod(utils)
    main()
