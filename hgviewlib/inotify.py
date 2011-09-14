#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
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
"""
inotify support for hgview
"""

from os import read, path as osp
from time import sleep
from array import array
from fcntl import ioctl
from termios import FIONREAD

from pyinotify import WatchManager

class Inotify(object):
    """Use inotify to get a file descriptor that shall be used into a main 
    loop.

    Constructor arguments:
    * repo - a mercurial repository object to watch
    * callback - callable called while processing events

    Use the ``process()`` method to update the display
    """

    def __init__(self, repo, callback=None):
        self.watchmanager = WatchManager()
        self.repo = repo
        self.callback = callback

    def update(self):
        '''update watchers'''
        # sorry :P. Import them here to reduce stating time
        from pyinotify import (IN_MODIFY, IN_ATTRIB, IN_MOVED_FROM, IN_MOVED_TO,
                               IN_DELETE_SELF, IN_MOVE_SELF)
        mask = (IN_MODIFY | IN_ATTRIB | IN_MOVED_FROM | IN_MOVED_TO 
                | IN_DELETE_SELF | IN_MOVE_SELF)
        # Watch for events from the repository root directory and subdirs
        # (take into account excluded patterns)
        self.watchmanager.add_watch(
                self.repo.root, mask, rec=True, auto_add=True,
                exclude_filter=self.repo.dirstate._dirignore)
        # Watch for events from .hg/dirstate that occur while manipulating the
        # repository. Note that we shall add a watch on to the .hg directory
        # as Hg build the new .hg/dirstate file from a temporary file and move
        # it the the right name (instead of modifying the original file)
        hgdir = osp.join(self.repo.root, '.hg')
        self.watchmanager.add_watch(hgdir, mask)
        self.watchmanager.add_watch(osp.join(hgdir, 'dirstate'), mask)
        # why not to look for mqueues patches ?
        if osp.exists(osp.join(hgdir, 'patches')):
            self.watchmanager.add_watch(osp.join(hgdir, 'patches'), mask)


    def get_fd(self):
        """Return assigned inotify's file descriptor."""
        return self.watchmanager.get_fd()

    def read_events(self):
        """Read event from events device"""
        buf_ = array('i', [0])
        # get event queue size
        if ioctl(self.watchmanager.get_fd(), FIONREAD, buf_, 1) == -1:
            return
        queue_size = buf_[0]
        # Read content from file
        return read(self.watchmanager.get_fd(), queue_size)

    def process(self):
        '''process events'''
        # Many events are raised for each modification on the repository
        # files or history (many files processed while committing, each file
        # processing may raises many event, e.g.IN_MODIFY and IN_ATTRIB.
        # We don't have to update the repository at each event. So, it may be a
        # good idea to put a delay during which the events are consumed, before
        # processing the callback.

        # Note: not implemented here, use the application mainloop to do so.

        # Note: I've try some other solutions, for instance: watching for
        # .hg/wlock or focusing on the manifests). But it seems that they
        # require a much more complicated implementation (update watched
        # files, fine watchers handling).
        # Finally, the current solution is simple, robust, and the end-user
        # interface seems to be good enough.

        # .hg/wlock means that some process is currently running on the
        # repository, so we have to sleep more. We can just return as another
        # event will be sent.
        if osp.exists(osp.join(self.repo.root or '', '.hg', 'wlock')):
            return
        # refresh viewer
        if self.callback:
            self.callback()

