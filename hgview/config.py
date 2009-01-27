# -*- coding: utf-8 -*-
import os

_hgconfig = None
def HgConfig(ui):
    global _hgconfig
    if _hgconfig is None:
        _hgconfig = _HgConfig(ui)
    return _hgconfig


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

    
