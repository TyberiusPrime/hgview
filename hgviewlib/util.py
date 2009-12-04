# -*- coding: utf-8 -*-
# util functions
#
# Copyright (C) 2009 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Several helper functions
"""
import os
from mercurial import cmdutil

def tounicode(string):
    """
    Tries to convert s into a unicode string
    """
    for encoding in ('utf-8', 'iso-8859-15', 'cp1252'):
        try:
            return unicode(string, encoding)
        except UnicodeDecodeError:
            pass
    return unicode(string, 'utf-8', 'replace')
        
def has_closed_branch_support(repo):
    """
    Return True is repository have support for closed branches
    """
    # what a hack... 
    return "closed" in repo.heads.im_func.func_code.co_varnames

def isexec(filectx):
    """
    Return True is the file at filectx revision is executable
    """
    if hasattr(filectx, "isexec"):        
        return filectx.isexec()
    return "x" in filectx.flags()
    
def exec_flag_changed(filectx):
    """
    Return True if the file referenced by filectx has changed its exec
    flag
    """
    flag = isexec(filectx)
    parents = filectx.parents()
    if not parents:
        return ""
    
    pflag = isexec(parents[0])
    if flag != pflag:
        if flag:
            return "set"
        else:
            return "unset"
    return ""

def isbfile(filename):
    return filename and filename.startswith('.hgbfiles' + os.sep)

def bfilepath(filename):
    return filename and filename.replace('.hgbfiles' + os.sep, '')

def rootpath(repo, rev, path):
    """return the path name of 'path' relative to repo's root at
    revision rev;
    path is relative to cwd
    """  
    ctx = repo[rev]        
    filenames = list(ctx.walk(cmdutil.match(repo, [path], {})))
    if len(filenames) != 1 or filenames[0] not in ctx.manifest():
        return None
    else:
        return filenames[0]
    
