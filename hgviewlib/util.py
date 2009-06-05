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
        
        
    
