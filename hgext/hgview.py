# hgview: visual mercurial graphlog browser in PyQt4
#
# Copyright 2008-2010 Logilab
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

'''browse the repository in a(n other) graphical way

The hgview extension allows browsing the history of a repository in a
graphical way. It requires PyQt4 with QScintilla.
'''

import os
from mercurial import hg, commands, dispatch, error
    
# every command must take a ui and and repo as arguments.
# opts is a dict where you can find other command line flags
#
# Other parameters are taken in order from items on the command line that
# don't start with a dash.  If no default value is given in the parameter list,
# they are required.



def start_hgview(ui, repo, *pats, **opts):
    # WARNING, this docstring is superseeded programatically 
    """
start hgview log viewer
=======================

    This command will launch the hgview log navigator, allowing to
    visually browse in the hg graph log, search in logs, and display
    diff between arbitrary revisions of a file.

    If a filename is given, launch the filelog diff viewer for this file, 
    and with the '-n' option, launch the filelog navigator for the file.

    With the '-r' option, launch the manifest viexer for the given revision.

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
        from hgviewlib.util import rootpath
        from hgviewlib.qt4.hgrepoviewer import HgRepoViewer
        from hgviewlib.qt4.hgfiledialog import FileDiffViewer, FileViewer
        from hgviewlib.qt4.hgmanifestdialog import ManifestViewer
        from hgviewlib.qt4 import setup_font_substitutions

    except ImportError, e:
        print e
        # If we're unable to import Qt4 or hgviewlib, try to
        # run the application directly.
        # You can specificy it's location in ~/.hgrc via
        #   [hgview]
        #   path=
        cmd = ui.config("hgview", "path", "hgview") 
        os.system(cmd + " " + " ".join(pats))

    else:
        # make Ctrl+C works
        import signal
        signal.signal(signal.SIGINT, signal.SIG_DFL)        
        app = QtGui.QApplication(sys.argv)
        setup_font_substitutions()
        if len(pats) == 1:
            filename = rootpath(repo, opts.get("rev"), pats[0])
            if filename is None:
                raise(error.Abort("%s is not a tracked file" % pats[0]))
            
            # should be a filename of a file managed in the repo
            if opts.get('navigate'):
                mainwindow = FileViewer(repo, filename)
            else:
                mainwindow = FileDiffViewer(repo, filename)
        else:
            rev = opts.get('rev')
            if rev:
                rev = int(rev)
                mainwindow = ManifestViewer(repo, rev)
            else:
                head = None
                if opts.get('start'):
                    head = int(opts.get('start'))
                mainwindow = HgRepoViewer(repo, head)
        mainwindow.show()
        return app.exec_()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import hgviewlib.hgviewhelp as hghelp

start_hgview.__doc__ = hghelp.long_help_msg
    
cmdtable = {
    "^hgview|hgv|qv": (start_hgview,
                       [('n', 'navigate', False, '(with filename) start in navigation mode'),
                        ('r', 'rev', '', 'start in manifest navigation mode at rev R'),
                        ('s', 'start', '', 'show only graph from rev S'),
                        ],
            "hg hgview [options] [filename]"),
}
    
