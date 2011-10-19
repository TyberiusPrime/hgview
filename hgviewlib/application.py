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
Application utilities.
"""

import os, sys
from optparse import OptionParser

from mercurial import hg, ui
from mercurial.error import RepoError

from hgviewlib.util import find_repository, rootpath
from hgviewlib.config import HgConfig

class Viewer(object):
    """Base viewer class interface."""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'This feature has not yet been implemented. Comming soon ...')

class FileViewer(Viewer):
    """Single file revision graph viewer."""
    def __init__(self, repo, filename, **kwargs):
        super(FileDiffViewer, self).__init__(**kwargs)

class FileDiffViewer(Viewer):
    """Viewer that displays diffs between different revisions of a file."""
    def __init__(self, repo, filename, **kwargs):
        super(FileDiffViewer, self).__init__(**kwargs)

class HgRepoViewer(Viewer):
    """hg repository viewer."""
    def __init__(self, repo, **kwargs):
        super(HgRepoViewer, self).__init__(**kwargs)

class ManifestViewer(Viewer):
    """Viewer that displays all files of a repo at a given revision"""
    def __init__(self, repo, rev, **kwargs):
        super(ManifestViewer, self).__init__(**kwargs)

class ApplicationError(ValueError):
    """Exception that may occures while lunching the application"""

class HgViewApplication(object):
    # class that must be instancied
    FileViewer = FileViewer
    FileDiffViewer = FileDiffViewer
    HgRepoViewer = HgRepoViewer
    ManifestViewer = ManifestViewer

    def __init__(self, repo, opts, args, **kawrgs):
        self.viewer = None

        if opts.navigate and len(args) != 1:
            ApplicationError(
                    "you must provide a filename to start in navigate mode")

        if len(args) > 1:
            ApplicationError("provide at most one file name")

        self.opts = opts
        self.args = args
        self.repo = repo
        self.choose_viewer()

    def choose_viewer(self):
        """Choose the right viewer"""
        if len(self.args) == 1:
            filename = rootpath(self.repo, self.opts.rev, self.args[0])
            if not filename:
                ApplicationError("%s is not a tracked file" % self.args[0])

            # should be a filename of a file managed in the repo
            if self.opts.navigate:
                viewer = self.FileViewer(self.repo, filename)
            else:
                viewer = self.FileDiffViewer(self.repo, filename)
        else:
            rev = self.opts.rev
            if rev:
                try:
                    self.repo.changectx(rev)
                except RepoError, e:
                    ApplicationError("Cannot find revision %s" % rev)
                else:
                    viewer = self.ManifestViewer(self.repo, rev)
            else:
                viewer = self.HgRepoViewer(self.repo)
        self.viewer = viewer

    def exec_(self):
        raise NotImplementedError()

def start(repo, opts, args, fnerror):
    """
    start hgview
    """

    config = HgConfig(repo.ui)
    if not opts.interface:
        opts.interface = config.getInterface()

    try:
        if opts.interface in ('raw', 'curses'):
            from hgviewlib.curses.application import HgViewUrwidApplication as Application
        elif opts.interface == 'qt':
            from hgviewlib.qt4.application import HgViewQtApplication as Application
        else:
            fnerror('Unknown interface: "%s"' % opts.interface)
        app = Application(repo, opts, args)
    except ApplicationError, err:
        fnerror(str(err))
    except ImportError:
        fnerror('Interface is not available: %s' % opts.interface)

    sys.exit(app.exec_())

def main():
    """
    Main application acces point.
    """

    usage = '''%prog [options] [filename]

    Starts a visual hg repository navigator.

    - With no options, starts the main repository navigator.

    - If a filename is given, starts in filelog diff mode (or in
      filelog navigation mode if -n option is set).

    - With -r option, starts in manifest viewer mode for given
      revision.
    '''

    parser = OptionParser(usage)
    parser.add_option('-I', '--interface', dest='interface',
                      help=('which GUI interface to use (among "qt", "raw"'
                             ' and "curses")'),
                      )
    parser.add_option('-R', '--repository', dest='repo',
                      help='location of the repository to explore')
    parser.add_option('-r', '--rev', dest='rev', default=None,
                      help='start in manifest navigation mode at rev R')
    parser.add_option('-n', '--navigate', dest='navigate', default=False,
                      action="store_true",
                      help='(with filename) start in navigation mode')

    opts, args = parser.parse_args()

    if opts.repo:
        dir_ = opts.repo
    else:
        dir_ = os.getcwd()
    dir_ = find_repository(dir_)

    try:
        u = ui.ui()
        repo = hg.repository(u, dir_)
    except RepoError, e:
        parser.error(e)
    except:
        parser.error("There is no Mercurial repository here (.hg not found)!")
    start(repo, opts, args, parser.error)


if __name__ == "__main__":
    main()

