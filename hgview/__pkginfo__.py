# pylint: disable-msg=W0622,C0103
# Copyright (c) 2003-2007 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""hgview packaging information"""

modname = 'hgview'

numversion = (0, 3, 0)
version = '.'.join([str(num) for num in numversion])

license = 'GPL'
copyright = '''Copyright (c) 2003-2007 Ludovic Aubry (ludovic.aubry@logilab.fr).
Copyright (c) 2003-2007 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr'''

short_desc = "a mercurial interactive history viewer"
long_desc = """\
 Hgview is a mercurial interactive history viewer, written in
 Python/GTK and PyQt. Its purpose is similar to the hgk tool of
 mercurial. It has been written with efficiency in mind when dealing
 with big repositories (it can happily be used to browse Linux kernel
 source code repository).
"""

author = "Ludovic Aubry"
author_email = "ludovic.aubry@logilab.fr"

web = "http://www.logilab.org/project/name/%s" % modname
ftp = "ftp://ftp.logilab.org/pub/%s" % modname
mailinglist = "mailto://python-projects@logilab.org"

from os.path import join
scripts = [join('bin', filename)
           for filename in ('hgview',)]

data_files = [('share/hgview', ['hgview/gtk/hgview.glade',
                                 'hgview/qt4/hgview.ui']),
              ('share/man/man1', ['hgview.1',
                                 ]),]

## include_dirs = [join('test', 'input'),
##                 join('test', 'messages'),
##                 join('test', 'rpythonmessages'),
##                 join('test', 'regrtest_data')]

pyversions = ["2.3", "2.4", "2.5"]

debian_uploader = 'Alexandre Fayolle <afayolle@debian.org>'

