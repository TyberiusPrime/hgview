#!/usr/bin/env python
# hgview: visual mercurial graphlog browser in PyQt4
#
# Copyright 2008-2010 Logilab
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

"""
Hg repository log browser.

This is a standalone version of the application built using py2exe.

See README file included.
"""

import sys, os
import os.path as pos

# Standalone version of hgview built with py2exe use its own version
# of Mercurial. Using configuration from the global Mercurial.ini will be
# ill-advised as the installed version of Mercurial itself may be
# different than the one we ship.
#
# this will be found next to Mercurial.ini
path = pos.join(os.path.expanduser('~'), 'hgview.ini')
os.environ['HGRCPATH'] = path


# We could not import the module that defines the original class because
# of sys._Messagebox missing error (see py2exe.boot_common.py). So, we
# introspect to get access to the original class.
LOGPATH = pos.join(pos.expanduser('~'), 'hgview.log') 
class Stderr(sys.stderr.__class__):
    def write(self, *args, **kwargs):
        kwargs['fname'] =  LOGPATH
	super(Stderr, self).write(*args[:2], **kwargs)
sys.stderr = Stderr() # open(pos.join(pos.expanduser('~'), 'hgview.log'), 'a')
# clean log
if pos.exists(LOGPATH):
    try:
        os.remove(LOGPATH)
    except EnvironmentError: # could not be remove if 2 hgview are opened
        pass

from hgviewlib.application import main

main()
