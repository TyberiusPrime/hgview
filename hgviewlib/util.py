# -*- coding: utf-8 -*-
# util functions
#
# Copyright (C) 2009 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

def tounicode(s):
    """
    Tries to convert s into a unicode string
    """
    for encoding in ('utf-8', 'iso-8859-15', 'cp1252'):
        try:
            return unicode(s, encoding)
        except UnicodeDecodeError:
            pass
    return unicode(s, 'utf-8', 'replace')
        
def has_closed_branch_support(repo):
    try:
        repo.heads(closed=True)
        return True
    except:
        return False
    
def exec_flag_changed(filectx):
    flag = filectx.isexec()
    parents = filectx.parents()
    if not parents:
        return ""
    
    pflag = parents[0].isexec()
    if flag != pflag:
        if flag:
            return "set"
        else:
            return "unset"
    return ""
