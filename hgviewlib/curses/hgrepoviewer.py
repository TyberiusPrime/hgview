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
Main curses application for hgview
"""

import os
import threading
import logging

import urwid
from urwid import AttrWrap, signals
from mercurial import ui, hg, cmdutil

from hgviewlib.util import choose_viewer, find_repository
from hgviewlib.curses.graphlog import RevisionsList, AppliedItem, UnappliedItem
from hgviewlib.curses import (connect_logging, Body, MainFrame,
                              register_command, unregister_command,
                              emit_command, CommandArg as CA)

class HgRepoViewer(Body):
    """Main body for this view"""

    def __init__(self, repo, *args, **kwargs):
        body = RevisionsList(repo=repo)
        self.repo = repo
        self.size = 0
        self.__super.__init__(body=body, *args, **kwargs)
        self.title = repo.root

    def register_commands(self):
        register_command(
                ('goto', 'g'), 'Set focus on a particular revision',
                CA('revision', int,
                'The revision number to focus on (default to last)'))
        self.body.connect_commands()

    def unregister_commands(self):
        unregister_command('goto')
        unregister_command('g')

# __________________________________________________________________ functions

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

def main():
    '''main entry point'''

    class MissingViewer:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
            'This feature has not yet been implemented. Comming soon ...')

    palette = [
        ('default','white','default'),
        ('body','default','default', 'standout'),
        ('banner','black','light gray', 'bold'),
        ('focus','black','dark cyan', 'bold'),

        # logging
        ('DEBUG', 'yellow', 'default'),
        ('INFO', 'dark gray', 'default'),
        ('WARNING', 'brown', 'default'),
        ('ERROR', 'dark red', 'default'),
        ('CRITICAL', 'light red', 'default'),

        # graphlog
        ('ID', 'brown', 'default', 'standout'),
        ('Log', 'default', 'default'),
        ('GraphLog', 'white', 'default', 'bold'),
        ('Author', 'dark blue', 'default', 'bold'),
        ('Date', 'dark green', 'default', 'bold'),
        ('Tags', 'yellow', 'dark red', 'bold'),
        ('Branch', 'yellow', 'default', 'bold'),
        ('Filename', 'white', 'default', 'bold'),
        ('Unapplied', 'light cyan', 'black'),
        ('Current', 'black', 'dark green'),
        ('Modified', 'black', 'dark red'),

        ]

    body = choose_viewer(MissingViewer, MissingViewer, MissingViewer, 
                         HgRepoViewer)
    body = AttrWrap(body, 'body')
    mainframe = MainFrame('repoviewer', body)
    screen = urwid.raw_display.Screen()
    mainloop = urwid.MainLoop(mainframe, palette, screen)

    enable_inotify = True # XXX config
    optimize_inotify = True # XXX config
    if enable_inotify:
        if optimize_inotify:
            import ctypes.util
            orig = ctypes.util.find_library
            ctypes.util.find_library = lambda lib: None # durty optim
        inotify(mainloop)
        if optimize_inotify:
            ctypes.util.find_library = orig

    connect_logging(mainloop, level=logging.DEBUG)
    mainframe.register_commands()
    mainloop.run()
    mainframe.unregister_commands()

if __name__ == '__main__':
    main()
