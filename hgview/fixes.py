"""This module contains compatibility fixes between python 2.3 and 2.4
and also one monkey patch to speed up some mercurial operations"""

import sys

# some helpful 2.3 -> 2.4 compatibility fixes
if (2,3,0) <= sys.version_info < (2,4,0):
    from sets import Set
    __builtins__['set'] = Set
    def reversed(l):
        for x in l[-1::-1]:
            yield x
    __builtins__['reversed'] = reversed
elif sys.version_info < (2,3,0):
    print "Python version :", sys.version_info, "not supported, you need 2.3 minimum"
    sys.exit(1)


def tolocal(s):
    """monkeypatch hg.util.tolocal since we only want utf-8 for gtk"""
    return s
import mercurial.util
mercurial.util.tolocal = tolocal

