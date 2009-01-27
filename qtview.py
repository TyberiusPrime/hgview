# Qt4 version of hgview 
#
# Copyright 2008-2009 Logilab
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.

from mercurial import hg, commands, dispatch

import os

# every command must take a ui and and repo as arguments.
# opts is a dict where you can find other command line flags
#
# Other parameters are taken in order from items on the command line that
# don't start with a dash.  If no default value is given in the parameter list,
# they are required.

def start_hgview(ui, repo, *args, **kwargs):
    rundir = repo.root
    if '.' in args:
        rundir = '.'
    os.chdir(rundir)

    # If this user has a username validation hook enabled,
    # it could conflict with Qct because both will try to
    # allocate a QApplication, and PyQt doesn't deal well
    # with two app instances running under the same context.
    # To prevent this, we run the hook early before Qct
    # allocates the app
    try:
        from hgconf.uname import hook
        hook(ui, repo)
    except ImportError:
        pass

    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from PyQt4 import QtGui
        from hgview.qt4 import hgview_qt4 as hgview
    except ImportError:
        # If we're unable to import Qt4 and qctlib, try to
        # run the application directly
        # You can specificy it's location in ~/.hgrc via
        #   [qtview]
        #   path=
        cmd = ui.config("qtview", "path", "qtview") 
        os.system(cmd)
    else:
        app = QtGui.QApplication(sys.argv)
        mainwindow = hgview.HgMainWindow(repo)
        mainwindow.show()
        return app.exec_()

cmdtable = {
    "^qtview": (start_hgview,
        [],
        "hg qtview [options] [.]")
}
    
