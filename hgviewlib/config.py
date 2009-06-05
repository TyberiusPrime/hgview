# -*- coding: utf-8 -*-
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
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
#
# pylint: disable-msg=C0103

"""
Module for managing configuration parameters of hgview using Hg's
configuration system
"""
import os

def cached(meth):
    """
    decorator to cache config values once they are read
    """
    name = meth.func_name
    def wrapper(self, *args, **kw):
        if name in self._cache:
            return self._cache[name]
        res = meth(self, *args, **kw)
        self._cache[name] = res
        return res
    wrapper.__doc__ = meth.__doc__
    return wrapper

class HgConfig(object):
    """
    Class managing user configuration from hg standard configuration system (.hgrc) 
    """
    def __init__(self, ui, section="hgview"):
        self.ui = ui
        self.section = section
        self._cache = {}

    @cached
    def getFont(self):
        """
        font: default font used to display diffs and files. Use Qt4 format.
        """
        return self.ui.config(self.section, 'font',
                              'Monospace,10,-1,5,50,0,0,0,1,0')

    @cached
    def getDotRadius(self, default=8):
        """
        dotradius: radius (in pixels) of the dot in the revision graph
        """
        r = self.ui.config(self.section, 'dotradius', default)
        return int(r)

    @cached
    def getUsers(self):
        """
        users: path of the file holding users configurations
        """
        users = {}
        aliases = {}
        usersfile = self.ui.config(self.section, 'users',
                                   os.path.join('~', ".hgusers"))
        cfgfile = None
        if usersfile:
            try:
                cfgfile = open(os.path.expanduser(usersfile))
            except IOError, e:
                #print "Cannot open file %s: please configure the 'users' parameter of the '[hgview]' section in your .hgrc file" % usersfile
                cfgfile = None

        if cfgfile:
            currid = None
            for line in cfgfile:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                cmd, val = line.split('=', 1)
                if cmd == 'id':
                    currid = val
                    if currid in users:
                        print "W: user %s is defined several times" % currid
                    users[currid] = {'aliases': set()}
                elif cmd == "alias":
                    users[currid]['aliases'].add(val)
                    if val in aliases:
                        print "W: alias %s is used in several user definitions" % val
                    aliases[val] = currid
                else:
                    users[currid][cmd] = val
        return users, aliases

    @cached
    def getFileModifiedColor(self, default='blue'):
        """
        filemodifiedcolor: display color of a modified file
        """
        return self.ui.config(self.section, 'filemodifiedcolor', default)
    @cached
    def getFileRemovedColor(self, default='red'):
        """
        fileremovedcolor: display color of a removed file
        """
        return self.ui.config(self.section, 'fileremovededcolor', default)
    @cached
    def getFileDeletedColor(self, default='darkred'):
        """
        filedeletedcolor: display color of a deleted file
        """
        return self.ui.config(self.section, 'filedeletedcolor', default)
    @cached
    def getFileAddedColor(self, default='green'):
        """
        fileaddedcolor: display color of an added file
        """
        return self.ui.config(self.section, 'fileaddedcolor', default)

    @cached
    def getRowHeight(self, default=20):
        """
        rowheight: height (in pixels) on a row of the revision table
        """
        return int(self.ui.config(self.section, 'rowheight', default))

    @cached
    def getHideFindDelay(self, default=10000):
        """
        hidefinddelay: delay (in ms) after which the find bar will disappear
        """
        return int(self.ui.config(self.section, 'hidefindddelay', default))

    @cached
    def getFillingStep(self, default=300):
        """
        fillingstep: number of nodes 'loaded' at a time when updating repo graph log
        """
        return int(self.ui.config(self.section, 'fillingstep', default))

_HgConfig = HgConfig
# HgConfig is instanciated only once (singleton)
#
# this 'factory' is used to manage this (not using heavy guns of
# metaclass or so)
_hgconfig = None
def HgConfig(ui):
    """Factory to instanciate HgConfig class as a singleton
    """
    # pylint: disable-msg=E0102
    global _hgconfig
    if _hgconfig is None:
        _hgconfig = _HgConfig(ui)
    return _hgconfig


def get_option_descriptions():
    options = []
    for attr in dir(_HgConfig):
        if attr.startswith('get'):
            meth = getattr(_HgConfig, attr)
            if callable(meth):
                doc = meth.__doc__
                if doc and doc.strip():
                    options.append(doc.strip())
    return options

