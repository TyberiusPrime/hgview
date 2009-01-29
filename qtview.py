# qtview: viual graphlog browser in PyQt4
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

def start_qtview(ui, repo, *args, **kwargs):
    """start qtview log viewer
    
    This command will launch the qtview log navigator, allowing to
    visually browse in the hg graph log, search in logs, and display
    diff between arbitrary revisions of a file.

    Keyboard shortcuts:

    Up/Down     - go to next/previous revision
    Left/Right  - display previous/next files of the current changeset
    Ctrl+F or / - display the search bar
    Esc         - exit
    Enter       - run the diff viewer for the currently selected file
                  (display diff between revisions)
    Ctrl+R      - reread repo

    Configuration:

    Configuration statements goes under the section [qtview] of the
    hgrc config file. The 'users' config statement should the path of
    a file describing users, like:

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

    Use 'qtview-options' command to display list of all configuration options.
    """
    rundir = repo.root

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
        import hgview.qt4.hgview_rc
        from hgview.qt4 import hgview_qt4 as qtview
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
        mainwindow = qtview.HgMainWindow(repo)
        mainwindow.show()
        return app.exec_()

def display_options(ui, repo, *args, **kwargs):
    """display qtview full list of configuration options
    """
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from hgview.config import get_option_descriptions
    options = get_option_descriptions()
    msg = """\nConfiguration options available for qtview.
    These should be set under the [qtview] section.\n\n"""
    ui.status(msg + '\n'.join(["  - " + v for v in options]) + '\n')
    
cmdtable = {
    "^qtview|qtv|qv": (start_qtview,
                       [],
                       "hg qtview [options] [.]"),
    "^qtview-options|qtview-config|qv-config|qv-cfg": (display_options,
                        [],
                        "")
}
    
