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

# Standalone version of hgview built with py2exe use they how version
# of mercurial. Using configuration from the global Mercurial.ini will be
# ill-advised as the installed version of Mercurial itself may be
# different than the one we ship.
#
# this will lay aside Mercurial.ini
path = pos.join(os.path.expanduser('~'), 'hgview.ini')
os.environ['HGRCPATH'] = path

from hgviewlib.application import main

main()
