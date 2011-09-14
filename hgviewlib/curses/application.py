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
Application utilities.
"""
import threading
import logging

from urwid import AttrWrap, MainLoop

from hgviewlib.application import HgViewApplication
from hgviewlib.curses.hgrepoviewer import RepoViewer
from hgviewlib.curses import (MainFrame, Screen, PALETTE, connect_logging,
                              emit_command)

class HgViewUrwidApplication(HgViewApplication):
    """
    HgView application using urwid.
    """
    HgRepoViewer = RepoViewer

    def __init__(self, *args, **kwargs):
        super(HgViewUrwidApplication, self).__init__(*args, **kwargs)
        self.viewer = AttrWrap(self.viewer, 'body')
        mainframe = MainFrame('repoviewer', self.viewer)
        screen = Screen()
        self.mainloop = MainLoop(mainframe, PALETTE, screen)
        connect_logging(self.mainloop, level=logging.DEBUG)
        mainframe.register_commands()
        self.enable_inotify()
        self.mainframe = mainframe

    def enable_inotify(self):
        """enable inotify watching"""
        enable_inotify = True # XXX config
        optimize_inotify = True # XXX config
        if enable_inotify:
            if optimize_inotify:
                import ctypes.util
                orig = ctypes.util.find_library
                ctypes.util.find_library = lambda lib: None # durty optim
            inotify(self.mainloop)
            if optimize_inotify:
                ctypes.util.find_library = orig

    def exec_(self):
        '''main entry point'''
        out = self.mainloop.run()
        self.mainframe.unregister_commands()
        return out

def inotify(mainloop):
    """add inotify watcher to the mainloop"""
    try:
        from hgviewlib.inotify import Inotify as Inotify
    except ImportError:
        return

    class UrwidInotify(Inotify):
        def __init__(self, *args, **kwargs):
            super(UrwidInotify, self).__init__(*args, **kwargs)
            self._input_timeout = None

        def process_finally(self):
            """Really process the inotify event"""
            self._input_timeout = None
            super(UrwidInotify, self).process()

        def process_on_any_event(self):
            """Process all inotify events and prevent over-processing"""
            # use the urwid mainloop to schedule the screen refreshing in 0.2s
            # and ignore events received during this time.
            # It prevents over-refreshing (See ../inotify.py comments).
            if self._input_timeout is None:
                self._input_timeout = mainloop.set_alarm_in(
                        0.2, lambda *args: self.process_finally())
            self.read_events()
    try:
        refresh = lambda: emit_command('refresh')
        inot = UrwidInotify(mainloop.widget.get_body().repo, refresh)
    except:
        return
    mainloop.event_loop.watch_file(inot.get_fd(), inot.process_on_any_event)
    # add watchers thought a thread to reduce start duration with a big repo
    threading.Thread(target=inot.update).start()

