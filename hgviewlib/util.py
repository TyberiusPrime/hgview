# -*- coding: utf-8 -*-
# util functions
#
# Copyright (C) 2009-2010 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Several helper functions
"""
import os
import sys
import string
from mercurial import cmdutil, ui, hg

def tounicode(string):
    """
    Tries to convert s into a unicode string
    """
    for encoding in ('utf-8', 'iso-8859-15', 'cp1252'):
        try:
            return unicode(string, encoding)
        except UnicodeDecodeError:
            pass
    return unicode(string, 'utf-8', 'replace')

def has_closed_branch_support(repo):
    """
    Return True is repository have support for closed branches
    """
    # what a hack...
    return "closed" in repo.heads.im_func.func_code.co_varnames

def isexec(filectx):
    """
    Return True is the file at filectx revision is executable
    """
    if hasattr(filectx, "isexec"):
        return filectx.isexec()
    return "x" in filectx.flags()

def exec_flag_changed(filectx):
    """
    Return True if the file referenced by filectx has changed its exec
    flag
    """
    flag = isexec(filectx)
    parents = filectx.parents()
    if not parents:
        return ""

    pflag = isexec(parents[0])
    if flag != pflag:
        if flag:
            return "set"
        else:
            return "unset"
    return ""

def isbfile(filename):
    return filename and filename.startswith('.hgbfiles' + os.sep)

def bfilepath(filename):
    return filename and filename.replace('.hgbfiles' + os.sep, '')

def find_repository(path):
    """returns <path>'s mercurial repository

    None if <path> is not under hg control
    """
    path = os.path.abspath(path)
    while not os.path.isdir(os.path.join(path, ".hg")):
        oldpath = path
        path = os.path.dirname(path)
        if path == oldpath:
            return None
    return path

def rootpath(repo, rev, path):
    """return the path name of 'path' relative to repo's root at
    revision rev;
    path is relative to cwd
    """
    ctx = repo[rev]
    filenames = list(ctx.walk(cmdutil.match(repo, [path], {})))
    if len(filenames) != 1 or filenames[0] not in ctx.manifest():
        return None
    else:
        return filenames[0]

# XXX what about functools.partial ?
class Curry(object):
    """Curryfication de fonction (http://fr.wikipedia.org/wiki/Curryfication)"""
    def __init__(self, function, *additional_args, **additional_kwargs):
        self.func = function
        self.additional_args = additional_args
        self.additional_kwargs = additional_kwargs

    def __call__(self, *args, **kwargs):
        args += self.additional_args
        kwarguments = self.additional_kwargs.copy()
        kwarguments.update(kwargs)
        return self.func(*args, **kwarguments)

# XXX duplicates logilab.mtconverter.__init__ code
CONTROL_CHARS = [chr(ci) for ci in range(32)]
TR_CONTROL_CHARS = [' '] * len(CONTROL_CHARS)
for c in ('\n', '\r', '\t'):
    TR_CONTROL_CHARS[ord(c)] = c
TR_CONTROL_CHARS[ord('\f')] = '\n'
TR_CONTROL_CHARS[ord('\v')] = '\n'
ESC_CAR_TABLE = string.maketrans(''.join(CONTROL_CHARS),
                                 ''.join(TR_CONTROL_CHARS))
ESC_UCAR_TABLE = unicode(ESC_CAR_TABLE, 'latin1')

def xml_escape(data):
    """escapes XML forbidden characters in attributes and PCDATA"""
    if isinstance(data, unicode):
        data = data.translate(ESC_UCAR_TABLE)
    else:
        data = data.translate(ESC_CAR_TABLE)
    return (data.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            .replace('"','&quot;').replace("'",'&#39;'))

def format_desc(desc, width):
    """
    Helper function to format a ctx description for oneliner
    representation (summary view)
    """
    desc = xml_escape(unicode(desc, 'utf-8', 'replace').split('\n', 1)[0])
    if len(desc) > width:
        desc = desc[:width] + '...'
    return desc

def choose_viewer(FileViewer, FileDiffViewer, ManifestViewer, 
            HgRepoViewer):
    """Parse the command line to chosse one of the classes passed as argument
    and return an instance of the right class.

    Classes will be instanciated as following::

        FileViewer(repo, filename)
        FileDiffViewer(repo, filename)
        ManifestViewer(repo, rev)
        HgRepoViewer(repo)

    """
    from optparse import OptionParser
    usage = '''%prog [options] [filename]

    Starts a visual hg repository navigator.

    - With no options, starts the main repository navigator.

    - If a filename is given, starts in filelog diff mode (or in
      filelog navigation mode if -n option is set).

    - With -r option, starts in manifest viewer mode for given
      revision.
    '''

    parser = OptionParser(usage)
    parser.add_option('-R', '--repository', dest='repo',
                      help='location of the repository to explore')
    parser.add_option('-r', '--rev', dest='rev', default=None,
                      help='start in manifest navigation mode at rev R')
    parser.add_option('-n', '--navigate', dest='navigate', default=False,
                      action="store_true",
                      help='(with filename) start in navigation mode')

    opts, args = parser.parse_args()

    if opts.navigate and len(args) != 1:
        parser.error("You must provide a filename to start in navigate mode")

    if len(args) > 1:
        parser.error("Provide at most one file name")

    dir_ = None
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
        parser.error("You are not in a repo, are you?")


    if len(args) == 1:
        filename = rootpath(repo, opts.rev, args[0])
        if filename is None:
            parser.error("%s is not a tracked file" % args[0])

        # should be a filename of a file managed in the repo
        if opts.navigate:
            mainwindow = FileViewer(repo, filename)
        else:
            mainwindow = FileDiffViewer(repo, filename)
    else:
        rev = opts.rev
        if rev is not None:
            try:
                repo.changectx(rev)
            except RepoError, e:
                parser.error("Cannot find revision %s" % rev)
            else:
                mainwindow = ManifestViewer(repo, rev)
        else:
            mainwindow = HgRepoViewer(repo)

    return mainwindow

