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
A Module that contains usefull utilities.
"""

import logging
from inspect import getdoc
import shlex
from itertools import izip_longest
from collections import namedtuple
try:
    from collections import OrderedDict as container # better for help
except ImportError:
    container = dict

import urwid
from urwid.command_map import CommandMap
from hgviewlib.curses.exceptions import UnknownCommand, RegisterCommandError

__all__ = ['register_command', 'unregister_command', 'connect_command',
           'disconnect_command', 'emit_command', 'help_command', 'CommandArg',
           'hg_command_map',
          ]


# ____________________________________________________________________ commands
CommandEntry = namedtuple('CommandEntry', ('func', 'args', 'kwargs'))
CommandArg = namedtuple('CommandArg', ('name', 'parser', 'help'))
class Commands(object):
    def __init__(self):
        self._args = {}
        self._helps = container()
        self._calls = {}

    def register(self, names, help, *args):
        """Register a command to make it available for connecting/emitting.

        ``names`` is the command name or a list of aliases.

        >>> from hgviewlib.curses import utils
        >>> import urwid
        >>> args = (utils.CommandArg('arg1', int, 'argument1'),
        ...         utils.CommandArg('arg2', float, 'argument2'),)
        >>> utils.register_command('foo', 'A command', *args)
        >>> out = utils.unregister_command('foo')

        """
        if isinstance(names, str):
            names = [names]
        for name in names:
            if name in self._helps:
                raise RegisterCommandError(
                        'Command "%s" already registered' % name)
        for arg in args:
            if not isinstance(arg, CommandArg):
                raise RegisterCommandError(
                    'Command arguments description type must be a CommandArg')
        calls = []
        # all points to the same values
        for name in names:
            self._args[name] = args
            self._helps[name] = help
            self._calls[name] = calls

    def __contains__(self, name):
        """Do not use"""
        return name in self._helps

    def unregister(self, name):
        """Unregister a command."""
        if name not in self:
            return
        help = self._helps.pop(name)
        args = self._args.pop(name)
        calls = self._calls.pop(name)
        return help, args, calls

    def connect(self, name, callback, args=None, kwargs=None):
        """Disconnect the ``callback`` assiciated to the givent ``args`` and
        ``kwargs`` from the command ``name``.

        See documentation of ``emit_command`` for details about ``args`` and
        ``kwarg``.
        """
        if name not in self:
            raise RegisterCommandError(
            'You must register the command "%s" before connecting a callback.'
            % name)
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        data = CommandEntry(callback, args, kwargs)
        self._calls[name].append(data)

    def disconnect(self, name, callback, args=None, kwargs=None):
        """Disconnect the ``callback`` assiciated to the givent ``args`` and
        ``kwargs`` from the command ``name``.

        >>> from hgviewlib.curses import utils
        >>> utils.register_command('foo', 'A command')
        >>> func = lambda *a, **k: True
        >>> utils.connect_command('foo', func, (1,2), {'a':0})
        >>> utils.disconnect_command('foo', func, (1,2), {'a':0})
        >>> out = utils.unregister_command('foo')

        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        try:
            self._calls[name].remove(CommandEntry(callback, args, kwargs))
        except KeyError:
            raise RegisterCommandError('Command not registered: %s' % name)
        except ValueError:
            raise RegisterCommandError('Callbacks not connected.')

    def emit(self, cmdline, args=None, kwargs=None):
        """Call all callbacks connected to the command previously registred.

        Callbacks are processed as following::

          registered_callback(*args, **kwargs)

        where ``args = connect_args + emit_args + commandline_args``
        and ``kwargs = connect_kwargs.copy(); kwargs.update(emit_kwargs)``

        :cmdline: a string that contains the complete command line.

        :return: True is a callback return True, else False

        """
        result = False
        name, rawargs = (cmdline.strip().split(None, 1) + [''])[:2]
        if not name in self:
            raise UnknownCommand(name)

        cmdargs = []
        if rawargs and self._args[name]:
            data = self._args[name]
            for idx, arg in enumerate(shlex.split(rawargs)):
                try:
                    parser = data[idx].parser
                except IndexError:
                    parser = str
                cmdargs.append(parser(arg))
        cmdargs = tuple(cmdargs)

        result = False
        for data in self._calls[name]:
            ags = data.args + (args or ()) + cmdargs
            kws = data.kwargs.copy()
            kws.update(kwargs or {})
            result |= bool(data.func(*ags, **kws))
        return result

    def help(self, name):
        """Return help for command ``name`` suitable for urwid.Text.

        >>> from hgviewlib.curses import utils
        >>> import urwid
        >>> args = (utils.CommandArg('arg1', int, 'argument1'),
        ...         utils.CommandArg('arg2', float, 'argument2'),)
        >>> utils.register_command('foo', 'A command', *args)
        >>> data = urwid.Text(utils.help_command('foo')).render((20,)).text
        >>> print '|%s|' % '|\\n|'.join(data)
        |usage: foo arg1 arg2|
        |A command           |
        |:arg1: argument1    |
        |:arg2: argument2    |
        |                    |
        >>> out = utils.unregister_command('foo')

        """
        if name not in self._helps:
            raise RegisterCommandError(
            'You must register the command "%s" before connecting a callback.'
            % name)
        help = self._helps[name]
        args = self._args[name]
        message = [('default', 'usage: '), ('WARNING', name)] \
                + [('DEBUG', ' ' + a.name) for a in args] \
                + [('default', '\n%s\n' % help)]
        for arg in args:
            message.append(('default', ':'))
            message.append(('DEBUG', arg.name))
            message.append(('default', ': '))
            message.append(arg.help + '\n')
        return message

_commands = Commands()
register_command = _commands.register
unregister_command = _commands.unregister
connect_command = _commands.connect
disconnect_command = _commands.disconnect
emit_command = _commands.emit
help_command = _commands.help

# _________________________________________________________________ command map


class HgCommandMap(CommandMap):
    _command_defaults = container((

        ('f1', '@help'),
        ('enter', 'validate'),
        ('m', '@maximize-context'),

        # Qt interface
        ('f5', 'command key'),
        ('esc', 'escape'),
        ('ctrl l', '@refresh'),
        ('ctrl w', 'close pane'),

        ('up', 'graphlog up'),
        ('down', 'graphlog down'),
        ('left', 'manifest up'),
        ('right', 'manifest down'),
        ('meta up', 'source up'),
        ('meta down', 'source down'),

        ('page up', 'graphlog page up'),
        ('page down', 'graphlog page down'),
        ('home', 'manifest page up'),
        ('end', 'manifest page down'),
        ('insert', 'source page up'),
        ('delete', 'source page down'),

        # vim interface
        (':', 'command key'),
        #'esc','escape', already set in Qt interface
        ('r', '@refresh'),
        ('q', 'close pane'),

        ('k', 'graphlog up'),
        ('j', 'graphlog down'),
        ('h', 'manifest up'),
        ('l', 'manifest down'),
        ('p', 'source up'),
        ('n', 'source down'),

        ('K', 'graphlog page up'),
        ('J', 'graphlog page down'),
        ('H', 'manifest page up'),
        ('L', 'manifest page down'),
        ('P', 'source page up'),
        ('N', 'source page down'),

        # emacs interface
        ('meta x', 'command key'),
        ('ctrl g', 'escape'),
        ('ctrl v', '@refresh'),
        ('ctrl k', 'close pane'),

        ('ctrl p', 'graphlog up'),
        ('ctrl n', 'graphlog down'),
        ('ctrl b', 'manifest up'),
        ('ctrl f', 'manifest down'),
        ('ctrl a', 'source up'),
        ('ctrl e', 'source down'),

        ('meta p', 'graphlog page up'),
        ('meta n', 'graphlog page down'),
        ('meta b', 'manifest page up'),
        ('meta f', 'manifest page down'),
        ('meta a', 'source page up'),
        ('meta e', 'source page down'),
    ))

hg_command_map = HgCommandMap()

