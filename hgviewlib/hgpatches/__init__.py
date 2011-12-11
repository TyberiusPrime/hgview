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
# this program.  If not, see <http://www.gnu.org/licenses/>.
"""
This modules contains monkey patches for Mercurial allowing hgview to support
older versions
"""

from functools import partial
from mercurial import changelog, filelog, patch, context

if not hasattr(changelog.changelog, '__len__'):
    changelog.changelog.__len__ = changelog.changelog.count
if not hasattr(filelog.filelog, '__len__'):
    filelog.filelog.__len__ = filelog.filelog.count

# mercurial ~< 1.8.4
if patch.iterhunks.func_code.co_varnames[0] == 'ui':
    iterhunks_orig = patch.iterhunks
    ui = type('UI', (), {'debug':lambda *x: None})()
    iterhunks = partial(iterhunks_orig, ui)
    patch.iterhunks = iterhunks

#  mercurial ~< 1.8.3
if not hasattr(context.filectx, 'p1'):
    context.filectx.p1 = lambda self: self.parents()[0]
