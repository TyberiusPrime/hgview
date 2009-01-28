# -*- coding: utf-8 -*-
"""
Module for managing configuration parameters of qtview using Hg's configuration system
"""
import os

# _HgConfig is instanciated only once (singleton)
# this 'factory' is used to manage this (not using heavy guns of metaclass or so) 
_hgconfig = None
def HgConfig(ui):    
    global _hgconfig
    if _hgconfig is None:
        _hgconfig = _HgConfig(ui)
    return _hgconfig


# decorator to cache config values once they are read
def cached(meth):
    name = meth.func_name
    def wrapper(self, *args, **kw):
        if name in self._cache:
            return self._cache[name]
        res = meth(self, *args, **kw)
        self._cache[name] = res
        return res
    return wrapper
    
class _HgConfig(object):
    def __init__(self, ui, section="qtview"):
        self.ui = ui
        self.section = section
        self._cache = {}

    @cached
    def getFont(self):
        return self.ui.config(self.section, 'font', 'Monospace,10,-1,5,50,0,0,0,1,0')

    @cached
    def getDotRadius(self, default=8):
        r = self.ui.config(self.section, 'dotradius', default)
        return r
    
    @cached
    def getUsers(self):
        users = {}
        aliases = {}
        usersfile = self.ui.config(self.section, 'users', None)
        try:
            f = open(os.path.expanduser(usersfile))
        except:
            f = None
        
        if f:
            currid = None
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                cmd, val = line.split('=', 1)
                if cmd == 'id':
                    currid = val
                    if currid in users:
                        print "Warning, user %s is defined several times" % currid
                    users[currid] = {'aliases': set()}
                elif cmd == "alias":
                    users[currid]['aliases'].add(val)
                    if val in aliases:
                        print "Warning, alias %s is used in several user definitions" % val
                    aliases[val] = currid
                else:
                    users[currid][cmd] = val
        return users, aliases

    @cached
    def getFileModifiedColor(self, default='blue'):
        return self.ui.config(self.section, 'filemodifiedcolor', default)        
    @cached
    def getFileRemovedColor(self, default='red'):
        return self.ui.config(self.section, 'fileremovededcolor', default)        
    @cached
    def getFileDeletedColor(self, default='darkred'):
        return self.ui.config(self.section, 'filedeletedcolor', default)        
    @cached
    def getFileAddedColor(self, default='green'):
        return self.ui.config(self.section, 'fileaddedcolor', default)        

    @cached
    def getRowHeight(self, default=20):
        return int(self.ui.config(self.section, 'rowheight', default))
        
    @cached
    def getHideFindDelay(self, default=10000):
        return int(self.ui.config(self.section, 'hidefindddelay', default))
    
