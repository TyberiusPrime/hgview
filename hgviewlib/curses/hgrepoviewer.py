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
from mercurial import ui, hg, cmdutil

from hgviewlib.util import choose_viewer, find_repository
from hgviewlib.curses.exceptions import CommandError
from hgviewlib.curses.graphlog import RevisionsList, AppliedItem, UnappliedItem
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

    @staticmethod
    def qremove(mainframe, *names):
        """
        usage: qremove names
        alias: qdel, qdelete, qrm

        Remove mq patches.

        :param names: a list of mq patches to remove
        """
        from hgext import mq
        args = list(args)
        body = mainframe.get_body().body
        repo = body.repo
        if not names:
            item = body.get_focus()[0]
            if not isinstance(item, UnappliedItem):
                raise CommandError(
         'You shall focus on an unapplied mq patch or provide mq patch names')
            names = [item.name]
        mq.delete(repo.ui, repo, *names)
        CommandsList.refresh(mainframe)
    qdelete = qdel = qrm = qremove

    @staticmethod
    def qpop(mainframe, *args):
        """
        usage: qpop [options] [id|name]

        Pops off patches until the focused, patch is at the top of the  stack.

        :param id|name]: select a diffrent patch than the focusd one.

        :param opsions: any of:

            * all: pop all patches
            * force  forget any local changes to patched files
        """
        from hgext import mq
        body = mainframe.get_body().body
        repo = body.repo
        keys = ('force', 'all', 'name')
        options = dict.fromkeys(keys, False)
        options.update((arg, True) for arg in args if arg in keys)
        idname = None
        if not options['all']:
            idname = (args or None) and args[-1]
            if (idname is None) or (idname in keys):
                item = body.get_focus()[0]
                if not isinstance(item, AppliedItem):
                    raise CommandError(('You shall focus on an applied mq'
                                        ' patch or provide mq patch name|id'))
                ctx = repo.changectx(item.gnode.rev)
                for patch in repo.mq.applied:
                    if patch.node == ctx.node():
                        break
                else:
                    raise CommandError(('You shall focus on an applied mq'
                                        ' patch or provide mq patch name|id'))
                idname = patch.name
        mq.pop(repo.ui, repo, idname, **options)
        CommandsList.refresh(mainframe)

    @staticmethod
    def qpush(mainframe, *args):
        """
        usage: qpop [options] [id|name]

        Push on patches until the focused patch is at the top of the stack.

        :param id|name: select a diffrent patch than the focusd one by its
                        name or id.

        :param options: any of:

            * force: apply on top of local changes
            * exact: apply the target patch to its recorded parent
            * list: list patch name in commit text
            * all: apply all patches
            * move: reorder patch series and apply only the patch
        """
        from hgext import mq
        args = list(args)
        body = mainframe.get_body().body
        repo = body.repo
        if 'move' in args or 'exact' in args:
            args.insert(0, 'move')  # hg 1.6
            args.insert(0, 'exact') # hg 1.8
        keys = ('force', 'exact', 'list', 'all', 'move', 'merge', 'name')
        options = dict.fromkeys(keys, False)
        options.update((arg, True) for arg in args if arg in keys)

        idname = None
        if not options['all']:
            idname = (args or None) and args[-1]
            if (idname is None) or (idname in keys):
                item = body.get_focus()[0]
                if not isinstance(item, UnappliedItem):
                    raise CommandError(
          'You shall focus on an applied mq patch or provide mq patch name|id')
                idname = item.name
        mq.push(repo.ui, repo, idname, **options)
        CommandsList.refresh(mainframe)

    @staticmethod
    def qfinish(mainframe, arg=None):
        """
        usage: qfinish [applied] [id|name]

        Finishes the revisions (corresponding to applied patches) moving thom
        out of the mq control until the focused patch is at the top of the
        regular repository history.

        :param id|name: select a diffrent patch than the focusd one by its
                        name or id.
        :param applied: finish all patches
        """
        from hgext import mq
        body = mainframe.get_body().body
        repo = body.repo
        applied = False
        end = None
        revs = []
        if arg == 'applied':
            applied = True
        elif arg:
            end = int(arg)
        if (end is None) and (not applied):
            item = body.get_focus()[0]
            if not isinstance(item, AppliedItem):
                raise CommandError(
         'You shall focus on an applied mq patch or provide mq patch name|id')
            end = item.gnode.rev
            start = repo.changectx(repo.mq.applied[0].node).rev()
            revrange = '%i%s%i' % (start, cmdutil.revrangesep,end)
        mq.finish(repo.ui, repo, revrange, applied=applied)
        CommandsList.refresh(mainframe)

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

        ('Unapplied', 'light cyan', 'black'),
        ('Current', 'black', 'dark green'),
        ('Modified', 'black', 'dark red'),

        ]

    body = choose_viewer(MissingViewer, MissingViewer, MissingViewer, 
                         HgRepoViewer)
    body = AttrWrap(body, 'body')
    frame = MainFrame(body)
    screen = urwid.raw_display.Screen()
    urwid.MainLoop(frame, palette, screen).run()

if __name__ == '__main__':
    main()
