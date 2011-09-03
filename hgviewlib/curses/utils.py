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
from hgviewlib.curses.exceptions import UnknownCommand, RegisterCommandError

__all__ = ['connect_logging',
           'register_command', 'unregister_command', 'connect_command',
           'disconnect_command', 'emit_command', 'help_command', 'CommandArg',
          ]

# _____________________________________________________________________ logging
class ConsoleHandler(logging.Handler):
    '''Handler for logging to the footer of a ``MainFrame`` instance.

    You shall prefer to link logging and you application by using the 
    ``connect_logging(...)`` function.
    '''
    def __init__(self, callback, redraw, redraw_levelno=logging.CRITICAL):
        """
        :param callback: A funtion called to display a message as
            ``callback(style, levelname, message)`` where:

            * ``levelname`` is the name of the message level
            * ``message`` is the message to display

            Mostly, it is the ``set`` method of a ``Footer`` instance.

        :param redraw: a function that performe the screen redrawing

        """
        self.callback = callback
        self.redraw = redraw
        self.redraw_levelno = redraw_levelno
        logging.Handler.__init__(self)

    def emit(self, record):
        """emit a record"""
        if isinstance(record.msg, list): # urwid style
            name = 'default'
            msg = record.msg
        else:
            name = record.levelname
            msg = self.format(record)
        self.callback(name, msg)
        if record.levelno >= self.redraw_levelno:
            self.flush()

    def flush(self):
        try:
            self.redraw()
        except AssertionError:
            pass

def connect_logging(mainloop, level=logging.INFO):
    '''Connect logging to the hgview console application.
    (The widget of the mainloop must be a ``MainFrame`` instance)

    You may add 'DEBUG', 'WARNING', 'ERROR' and 'CRITICAL' styles in the 
    palette.
    '''
    logger = logging.getLogger()
    logger.setLevel(level)
    display = lambda style, msg: mainloop.widget.footer.set(style, msg, '')
    handler = ConsoleHandler(display, mainloop.draw_screen)
    logger.addHandler(handler)

# ____________________________________________________________________ commands
CommandEntry = namedtuple('CommandEntry', ('func', 'args', 'kwargs'))
CommandArg = namedtuple('CommandArg', ('name', 'parser', 'help'))
class Commands(object):
    def __init__(self):
        self._args = {}
        self._helps = {}
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

    def emit(self, name, cmd=None, args=None, kwargs=None):
        """Call all callbacks connected to the registered command ``name`` as
        following::

          registered_callback(*args, **kwargs)

        where ``args = connect_args + emit_args + commandline_args``
        and ``kwargs = connect_kwargs.copy(); kwargs.update(emit_kwargs)``

        :return: True is a callback return True, else False

        """
        result = False
        if not name in self:
            raise RegisterCommandError('Command not registered: %s' % name)

        cmdargs = []
        if cmd and self._args[name]:
            data = self._args[name]
            for idx, arg in enumerate(shlex.split(cmd)):
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

