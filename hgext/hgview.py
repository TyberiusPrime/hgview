# hgview: visual mercurial graphlog browser in PyQt4
#
# Copyright 2008-2009 Logilab
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

import os
from mercurial import hg, commands, dispatch
    
# every command must take a ui and and repo as arguments.
# opts is a dict where you can find other command line flags
#
# Other parameters are taken in order from items on the command line that
# don't start with a dash.  If no default value is given in the parameter list,
# they are required.

def get_options_helpmsg():
    """display hgview full list of configuration options
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from hgviewlib.config import get_option_descriptions
    options = get_option_descriptions()
    msg = """
Configuration options available for hgview
==========================================

    These should be set under the [hgview] section of the hgrc config file.\n\n"""
    msg += '\n'.join(["  - " + v for v in options]) + '\n'
    msg += """
    The 'users' config statement should be the path of a file
    describing users, like:

    -----------------------------------------------
    # file ~/.hgusers
    id=david
    alias=david.douard@logilab.fr
    alias=david@logilab.fr
    alias=David Douard <david.douard@logilab.fr>
    color=#FF0000
    
    id=ludal
    alias=ludovic.aubry@logilab.fr
    alias=ludal@logilab.fr
    alias=Ludovic Aubry <ludovic.aubry@logilab.fr>
    color=#00FF00
    -----------------------------------------------
    
    This allow to make several 'authors' under the same name, with the
    same color, in the graphlog browser.
    """
    return msg

def start_hgview(ui, repo, *args, **kwargs):
    """
start hgview log viewer
=======================

    This command will launch the hgview log navigator, allowing to
    visually browse in the hg graph log, search in logs, and display
    diff between arbitrary revisions of a file.

    If a filename is given, launch the filelog diff viewer for this file, 
    and with the '-n' option, launch the filelog navigator for the file.

    With the '-r' option, launch the manifest viexer for the given revision.

    Keyboard shortcuts
    ------------------

    Up/Down     - go to next/previous revision
    Left/Right  - display previous/next files of the current changeset
    Ctrl+F or / - display the search bar
    Ctrl+G      - displa the 'goto rev' bar
    Esc         - exit
    Enter       - run the diff viewer for the currently selected file
                  (display diff between revisions)
    Ctrl+R      - reread repo

    
    """
    rundir = repo.root

    # If this user has a username validation hook enabled,
    # it could conflict with hgview because both will try to
    # allocate a QApplication, and PyQt doesn't deal well
    # with two app instances running under the same context.
    # To prevent this, we run the hook early before hgview
    # allocates the app
    try:
        from hgconf.uname import hook
        hook(ui, repo)
    except ImportError:
        pass

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    try:
        from PyQt4 import QtGui
        import hgviewlib.qt4.hgqv_rc
        from hgviewlib.qt4.hgrepoviewer import HgRepoViewer
        from hgviewlib.qt4.hgfileviewer import FileDiffViewer, FileViewer
        from hgviewlib.qt4.hgfileviewer import ManifestViewer
    except ImportError, e:
        print e
        # If we're unable to import Qt4 and qctlib, try to
        # run the application directly
        # You can specificy it's location in ~/.hgrc via
        #   [hgview]
        #   path=
        cmd = ui.config("hgview", "path", "hgview") 
        os.system(cmd + " " + " ".join(args))
    else:
        # make Ctrl+C works
        import signal
        signal.signal(signal.SIGINT, signal.SIG_DFL)        
        app = QtGui.QApplication(sys.argv)
        if len(args) == 1:
            # should be a filename of a file managed in the repo
            if kwargs.get('navigate'):
                mainwindow = FileViewer(repo, args[0])
            else:
                mainwindow = FileDiffViewer(repo, args[0])
        else:
            rev = kwargs.get('rev')
            if rev:
                rev = int(rev)
                mainwindow = ManifestViewer(repo, rev)
            else:
                mainwindow = HgRepoViewer(repo)
        mainwindow.show()
        return app.exec_()

start_hgview.__doc__ += get_options_helpmsg()

    
cmdtable = {
    "^hgview|hgv|qv": (start_hgview,
                       [('n', 'navigate', False, '(with filename) start in navigation mode'),
                        ('r', 'rev', '', 'start in maifest navigation mode at rev R'),
                        ],
            "hg hgview [options] [filename]"),
}
    
