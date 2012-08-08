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
"""
Exceptions classes used by hgview curses
"""

class HgviewCursesException(Exception):
    """Base class for all hgview curses exception """

class CommandError(ValueError, HgviewCursesException):
    """Error that occures while calling a command"""

class UnknownCommand(StopIteration, HgviewCursesException):
    """Error that occures when not callback found"""

class RegisterCommandError(KeyError, HgviewCursesException):
    """Error that occures when a conflict occures while registering a comand"""
