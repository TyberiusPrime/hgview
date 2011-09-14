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

import urwid
from urwid import AttrWrap
from mercurial import ui, hg

from hgviewlib.util import choose_viewer, find_repository
from hgviewlib.curses.exceptions import CommandError
from hgviewlib.curses.graphlog import RevisionsList
from hgviewlib.curses.mainframe import (MainFrame, BodyMixin,
                                        CommandsList as _CommandsList)

class CommandsList(_CommandsList):
    """List of available commands for this body"""
    @staticmethod
    def refresh(mainframe):
        """
        usage: refresh
        alias: r

        Refresh the repository content
        """
        lstbx = mainframe.get_body()
        walker = lstbx.body
        repo = lstbx.body.repo
        walker.repo = hg.repository(repo.ui, repo.root)
        walker._data_cache = {}
        walker.setRepo(walker.repo)
        urwid.canvas.CanvasCache.invalidate(lstbx)
        lstbx.render(lstbx.size, True)
    r = refresh

    @staticmethod
    def edit(mainframe, reporoot=None):
        """
        usage: edit [reporoot]
        alias: e

        Change repository root directory

        :param reporoot: the new repository root directory
        """
        if reporoot is None:
            reporoot = mainframe.get_body().body.repo.root
        if not os.path.exists(reporoot):
            raise CommandError('Repository not found: %s' % reporoot)
        _reporoot = find_repository(reporoot)
        if _reporoot is None:
            raise CommandError('Folder not under hg control: %s' % reporoot)
        repo = hg.repository(ui.ui(), _reporoot)
        body = HgRepoViewer(repo)
        mainframe.append_body(body)
    e = edit

class HgRepoViewer(RevisionsList, BodyMixin):
    """Main body for this view"""
    commands = CommandsList
    name = 'hgrepoview'

    def __init__(self, repo, *args, **kwargs):
        self.size = 0
        self.title = repo.root
        self.__super.__init__(repo, *args, **kwargs)

# __________________________________________________________________ functions


def main():
    '''main entry point'''

    class MissingViewer:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
            'This feature has not yet been implemented. Comming soon ...')

    palette = [
        ('default','white','default'),
        ('warn','white','dark red', 'bold'),
        ('body','default','default', 'standout'),
        ('banner','black','light gray', 'bold'),
        ('focus','black','dark cyan', 'bold'),

        ('ID', 'brown', 'default', 'standout'),
        ('Log', 'default', 'default'),
        ('GraphLog', 'white', 'default', 'bold'),
        ('Author', 'dark blue', 'default', 'bold'),
        ('Date', 'dark green', 'default', 'bold'),
        ('Tags', 'yellow', 'dark red', 'bold'),
        ('Branch', 'yellow', 'default', 'bold'),
        ('Filename', 'white', 'default', 'bold'),

        ]

    body = choose_viewer(MissingViewer, MissingViewer, MissingViewer, 
                         HgRepoViewer)
    body = AttrWrap(body, 'body')
    frame = MainFrame(body)
    screen = urwid.raw_display.Screen()
    urwid.MainLoop(frame, palette, screen).run()

if __name__ == '__main__':
    main()
