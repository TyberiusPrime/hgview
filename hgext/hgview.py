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
from optparse import Values
from mercurial import error
    
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

    try:
        from hgviewlib.application import start
        def fnerror(text):
            """process errors"""
            raise(error.Abort(text))
        options = Values(opts)
        start(repo, options, pats, fnerror)
    except Exception, e:
        if ui.config('ui', 'traceback'):
            raise
        # If we're unable to start hgviewlib from here, try to
        # run the application directly.
        # You can specificy it's location in ~/.hgrc via
        #   [hgview]
        #   path=
        cmd = [ui.config("hgview", "path", "hgview")]
        cmd += ['--%s %s' % (name, value)
                for name, value in opts.iteritems() if value]
        cmd += ['-R %s' % repo.root]
        if pats:
            cmd += list(pats)
        if ui.configlist('ui', 'debug'):
            sys.stdout.write('Enable to run Hg extension: ')
            sys.stdout.write(str(e))
            sys.stdout.write('\n')
            sys.stdout.write('-> starting alternative command:')
            sys.stdout.write('\n')
            sys.stdout.write(' '.join(cmd))
            sys.stdout.write('\n')
            sys.stdout.flush()
        os.system(' '.join(cmd))

import hgviewlib.hgviewhelp as hghelp

start_hgview.__doc__ = hghelp.long_help_msg

cmdtable = {
    "^hgview|hgv|qv": (start_hgview,
                       [('n', 'navigate', False, '(with filename) start in navigation mode'),
                        ('r', 'rev', '', 'start in manifest navigation mode at rev R'),
                        ('s', 'start', '', 'show only graph from rev S'),
                        ('I', 'interface', '', 'GUI interface to use (among "qt", "raw" and "curses"')
                        ],
            "hg hgview [options] [filename]"),
}

