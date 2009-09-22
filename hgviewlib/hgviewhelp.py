# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
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
help messages for hgview
"""

help_msg = """
hgview: a visual hg log viewer
==============================

This command will launch the hgview log navigator, allowing to
visually browse in the hg graph log, search in logs, and display
diff between arbitrary revisions of a file.

If a filename is given, launch the filelog diff viewer for this file, 
and with the '-n' option, launch the filelog navigator for the file.

With the '-r' option, launch the manifest viewer for the given revision.

Keyboard shortcuts
------------------

::

  Up/Down     - go to next/previous revision
  Left/Right  - display previous/next files of the current changeset
  Ctrl+F or / - display the search 'quickbar'
  Ctrl+G      - display the goto 'quickbar'
  Esc         - exit or kill the visible 'quickbar' 
  Enter       - run the diff viewer for the currently selected file
                (display diff between revisions)
  Alt+Enter   - run the filelog navigator
  Shift+Enter - run the manifest viewer for the displayed revision
  
  Ctrl+R      - reread repo; note that by default, repo will be automatically
                reloaded if it is modified (due to a commit, a pull, etc.)
  
  Alt+Up/Down    - display previous/next diff block
  Alt+Left/Right - go to previous/next visited revision (in navigation history)
  
Revision metadata display
-------------------------

The area where current revision's metadata are displayed
(description, parents revisions, etc.) may contain two kinds of hyperlink:

- when the hyperlink is the changeset ID, it allows you to
  directly go to the given revision,
  
- when the hyperlink is the revision number (on merge nodes only),
  it means that you can change the other revision used to comput
  the diff. This allows you to compare the merged node with each
  of its parents, or even with the common ancestor of these 2
  nodes.

Revision's modified file list
-----------------------------

The file list diplay the list of modified files. The diff
displayed is the one of the selected file, between the selected
revision and its parent revision.

On a merge node, by default, only files which are different from
both its parents are listed here. However, you can display the
list of all modified files by double-clickig the file list column
header.

    """

def get_options_helpmsg(rest=False):
    """display hgview full list of configuration options
    """
    from config import get_option_descriptions
    options = get_option_descriptions(rest)
    msg = """
Configuration options
=====================

These should be set under the [hgview] section of the hgrc config file.

"""
    msg += '\n'.join(["- " + v for v in options]) + '\n'
    msg += """
The 'users' config statement should be the path of a file
describing users, like::

    --8<-------------------------------------------
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
    --8<-------------------------------------------
    
This allow to make several 'authors' under the same name, with the
same color, in the graphlog browser.
    """
    return msg

long_help_msg = help_msg + get_options_helpmsg()
