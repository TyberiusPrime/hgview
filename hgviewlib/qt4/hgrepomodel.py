# Copyright (c) 2009 LOGILAB S.A. (Paris, FRANCE).
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
Qt4 model for hg repo changelogs and filelogs
"""
import sys
import mx.DateTime as dt
import re
import os.path as osp

from mercurial.node import nullrev
from mercurial.node import hex, short as short_hex
from mercurial.revlog import LookupError

from hgviewlib.hggraph import Graph, ismerge, diff as revdiff
from hgviewlib.hggraph import revision_grapher, filelog_grapher
from hgviewlib.config import HgConfig
from hgviewlib.util import tounicode
from hgviewlib.qt4 import icon as geticon
from hgviewlib.decorators import timeit

from PyQt4 import QtCore, QtGui
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

# XXX make this better than a poor hard written list...
COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", QtCore.Qt.darkYellow, "magenta", "darkred", "darkmagenta",
           "darkcyan", "gray", "yellow", ]
COLORS = [str(QtGui.QColor(x).name()) for x in COLORS]
#COLORS = [str(color) for color in QtGui.QColor.colorNames()]

def get_color(n, ignore=()):
    """
    Return a color at index 'n' rotating in the available
    colors. 'ignore' is a list of colors not to be chosen.
    """
    ignore = [str(QtGui.QColor(x).name()) for x in ignore]
    colors = [x for x in COLORS if x not in ignore]
    if not colors: # ghh, no more available colors...
        colors = COLORS
    return colors[n % len(colors)]

def cvrt_date(date):
    """
    Convert a date given the hg way, ie. couple (date, tz), into a
    formatted QString
    """
    date, tzdelay = date
    return QtCore.QDateTime.fromTime_t(int(date)).toString(QtCore.Qt.LocaleDate)

# in following lambdas, ctx is a hg changectx
_columnmap = {'ID': lambda ctx, gnode: ctx.rev(),
              'Log': lambda ctx, gnode: tounicode(ctx.description()),
              'Author': lambda ctx, gnode: tounicode(ctx.user()),
              'Date': lambda ctx, gnode: cvrt_date(ctx.date()),
              'Tags': lambda ctx, gnode: ",".join(ctx.tags()),
              'Branch': lambda ctx, gnode: ctx.branch(),
              'Filename': lambda ctx, gnode: gnode.extra[0],
              }

def auth_width(model, repo):
    auths = model._aliases.values()
    if not auths:
        return None
    return sorted(auths, cmp=lambda x,y: cmp(len(x), len(y)))[-1]


# in following lambdas, r is a hg repo
_maxwidth = {'ID': lambda self, r: str(len(r.changelog)),
             'Date': lambda self, r: cvrt_date(r.changectx(0).date()),
             'Tags': lambda self, r: sorted(r.tags().keys(),
                                            key=lambda x: len(x))[-1][:10],
             'Branch': lambda self, r: sorted(r.branchtags().keys(),
                                              key=lambda x: len(x))[-1],
             'Author': lambda self, r: 'author name',
             'Filename': lambda self, r: self.filename,
             }

def datacached(meth):
    """
    decorator used to cache 'data' method of Qt models. It will *not*
    cache nullvariant return values (so costly non-null values
    can be computed and filled as a background process)
    """
    def data(self, index, role):
        if not index.isValid():
            return nullvariant
        row = index.row()
        col = index.column()
        if (row, col, role) in self._datacache:
            return self._datacache[(row, col, role)]
        result = meth(self, index, role)
        if result is not nullvariant:
            self._datacache[(row, col, role)] = result
        return result
    return data

class HgRepoListModel(QtCore.QAbstractTableModel):
    """
    Model used for displaying the revisions of a Hg *local* repository
    """
    _allcolumns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _columns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _stretchs = {'Log': 1, }
    _getcolumns = "getChangelogColumns"

    def __init__(self, repo, branch='', parent=None):
        """
        repo is a hg repo instance
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._datacache = {}
        self._required = None
        self.wd_rev = None
        self.gr_fill_timer = QtCore.QTimer()
        connect(self.gr_fill_timer, SIGNAL('timeout()'),
                self.fillGraph)
        self.setRepo(repo, branch)

    def setRepo(self, repo, branch=''):
        self.repo = repo
        self._datacache = {}
        self.load_config()

        self.wd_rev = self.repo.changectx(None).parents()[0].rev()
        self._user_colors = {}
        self._branch_colors = {}
        grapher = revision_grapher(self.repo, branch=branch)
        self.graph = Graph(self.repo, grapher, self.max_file_size)
        self.nmax = len(self.repo.changelog)
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
        self._fill_iter = None
        self._required = self.fill_step
        self.gr_fill_timer.start()

    def fillGraph(self):
        step = self.fill_step
        if self._fill_iter is None:
            self.emit(SIGNAL('showMessage'), 'filling...')            
            self._fill_iter = self.graph.fill(step=step)
            self.emit(SIGNAL('layoutChanged()'))
            QtGui.QApplication.processEvents()
        try:
            n = len(self.graph)
            nm = min(n+step, self.nmax)
            self.beginInsertRows(QtCore.QModelIndex(), n, nm)
            nfilled = self._fill_iter.next()
            if n == 0:
                self.emit(SIGNAL('filled'))                
            if self._required and len(self.graph) > self._required:
                self._requiredss = None
                self.gr_fill_timer.stop()
                self.emit(SIGNAL('showMessage'), '')            
        except StopIteration:
            self.gr_fill_timer.stop()
            self._fill_iter = None
            self.emit(SIGNAL('showMessage'), '')            
        finally:
            self.endInsertRows()
            self.emit(SIGNAL('layoutChanged()'))

    def ensureBuilt(self, row=None, rev=None):
        if self._fill_iter is not None and not self.gr_fill_timer.isActive():
            if row is not None and (len(self.graph) - row) < self.fill_step:
                self._required = len(self.graph) + self.fill_step
            elif rev is not None and self.graph[-1].rev > rev:
                self._required = len(self.graph) + self.fill_step + self.graph[-1].rev - rev
            if self._required is not None:
                self.gr_fill_timer.start()
                self.emit(SIGNAL('showMessage'), 'filling...')            

    def rowCount(self, parent=None):
        return len(self.graph)

    def columnCount(self, parent=None):
        return len(self._columns)

    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        self._users, self._aliases = cfg.getUsers()
        self.dot_radius = cfg.getDotRadius(default=8)
        self.rowheight = cfg.getRowHeight()
        self.fill_step = cfg.getFillingStep()
        self.max_file_size = cfg.getMaxFileSize()
        
        cols = getattr(cfg, self._getcolumns)()
        if cols is not None:
            validcols = [col for col in cols if col in self._allcolumns]
            if len(validcols) != len(cols):
                wrongcols = [col for col in cols if col not in self._allcolumns]
                print "WARNING! %s are not valid column names. Check your configuration." % ','.join(wrongcols)
                print "         reverting to default columns configuration"
            elif 'Log' not in validcols or 'ID' not in validcols:
                print "WARNING! 'Log' and 'ID' are mandatory. Check your configuration."
                print "         reverting to default columns configuration"

            else:
                self._columns = tuple(validcols)

    def maxWidthValueForColumn(self, column):
        column = self._columns[column]
        if column in _maxwidth:
            return _maxwidth[column](self, self.repo)
        return None

    def user_color(self, user):
        if user in self._aliases:
            user = self._aliases[user]
        if user in self._users:
            try:
                color = self._users[user]['color']
                color = QtGui.QColor(color).name()
                self._user_colors[user] = color
            except:
                pass
        if user not in self._user_colors:
            self._user_colors[user] = get_color(len(self._user_colors),
                                                self._user_colors.values())
        return self._user_colors[user]

    def user_name(self, user):
        return self._aliases.get(user, user)

    def namedbranch_color(self, branch):
        if branch not in self._branch_colors:
            self._branch_colors[branch] = get_color(len(self._branch_colors))
        return self._branch_colors[branch]

    def col2x(self, col):
        return (1.2*self.dot_radius + 0) * col + self.dot_radius/2 + 3

    @datacached
    def data(self, index, role):
        if not index.isValid():
            return nullvariant
        row = index.row()
        self.ensureBuilt(row=row)
        column = self._columns[index.column()]
        gnode = self.graph[row]
        ctx = self.repo.changectx(gnode.rev)
        if role == QtCore.Qt.DisplayRole:
            if column == 'Author': #author
                return QtCore.QVariant(self.user_name(_columnmap[column](ctx, gnode)))
            elif column == 'Log':
                msg = _columnmap[column](ctx, gnode)
                if gnode.rev in self.heads:
                    msg = "[%s] " % ctx.branch() + msg
                return QtCore.QVariant(msg)
            return QtCore.QVariant(_columnmap[column](ctx, gnode))
        elif role == QtCore.Qt.ToolTipRole:
            msg = "<b>[%s]</b><br>\n" % ctx.branch()
            msg += _columnmap[column](ctx, gnode)
            return QtCore.QVariant(msg)
        elif role == QtCore.Qt.ForegroundRole:
            if column == 'Author': #author
                return QtCore.QVariant(QtGui.QColor(self.user_color(ctx.user())))
            if column == 'Branch': #branch
                return QtCore.QVariant(QtGui.QColor(self.namedbranch_color(ctx.branch())))
        elif role == QtCore.Qt.DecorationRole:
            if column == 'Log':
                radius = self.dot_radius
                w = (gnode.cols)*(1*radius + 0) + 20
                h = self.rowheight

                dot_x = self.col2x(gnode.x) - radius / 2
                dot_y = h / 2

                pix = QtGui.QPixmap(w, h)
                pix.fill(QtGui.QColor(0,0,0,0))
                painter = QtGui.QPainter(pix)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)

                pen = QtGui.QPen(QtCore.Qt.blue)
                pen.setWidth(2)
                painter.setPen(pen)

                lpen = QtGui.QPen(pen)
                lpen.setColor(QtCore.Qt.black)
                painter.setPen(lpen)

                for y1, y2, lines in ((0, h, gnode.bottomlines),
                                      (-h, 0, gnode.toplines)):
                    for start, end, color in lines:
                        lpen = QtGui.QPen(pen)
                        lpen.setColor(QtGui.QColor(get_color(color)))
                        lpen.setWidth(2)
                        painter.setPen(lpen)
                        x1 = self.col2x(start)
                        x2 = self.col2x(end)
                        painter.drawLine(x1, dot_y + y1, x2, dot_y + y2)

                dot_color = QtGui.QColor(self.namedbranch_color(ctx.branch()))
                dotcolor = QtGui.QColor(dot_color)
                if gnode.rev in self.heads:
                    penradius = 2
                    pencolor = dotcolor.darker()
                else:
                    penradius = 1
                    pencolor = QtCore.Qt.black

                dot_y = (h/2) - radius / 2

                painter.setBrush(dotcolor)
                pen = QtGui.QPen(pencolor)
                pen.setWidth(penradius)
                painter.setPen(pen)
                if gnode.rev == self.wd_rev:
                    painter.drawRect(dot_x, dot_y, radius, radius)
                else:
                    painter.drawEllipse(dot_x, dot_y, radius, radius)
                painter.end()
                ret = QtCore.QVariant(pix)
                return ret
        return nullvariant

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self._columns[section])
        return nullvariant

    def rowFromRev(self, rev):
        row = self.graph.index(rev)
        if row == -1:
            row = None
        return row

    def indexFromRev(self, rev):
        self.ensureBuilt(rev=rev)
        row = self.rowFromRev(rev)
        if row is not None:
            return self.index(row, 0)
        return None

    def clear(self):
        """empty the list"""
        self.graph = None
        self._datacache = {}
        self.notify_data_changed()

    def notify_data_changed(self):
        self.emit(SIGNAL("layoutChanged()"))

class FileRevModel(HgRepoListModel):
    """
    Model used to manage the list of revisions of a file, in file
    viewer of in diff-file viewer dialogs.
    """
    _allcolumns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags', 'Filename')
    _columns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Filename')
    _stretchs = {'Log': 1, }
    _getcolumns = "getFilelogColumns"

    def __init__(self, repo, filename, parent=None):
        """
        data is a HgHLRepo instance
        """
        HgRepoListModel.__init__(self, repo, parent=parent)
        self.setFilename(filename)

    def setRepo(self, repo, branch=''):
        self.repo = repo
        self._datacache = {}
        self.load_config()

    def setFilename(self, filename):
        self.filename = filename
        self.nmax = len(self.repo.changelog)
        self._user_colors = {}
        self._branch_colors = {}

        grapher = filelog_grapher(self.repo, self.filename)
        self.graph = Graph(self.repo, grapher, self.max_file_size)
        fl = self.repo.file(self.filename)
        # we use fl.index here (instead of linkrev) cause
        # linkrev API changed between 1.0 and 1.?. So this
        # works with both versions.
        self.heads = [fl.index[fl.rev(x)][4] for x in fl.heads()]
        self._datacache = {}
        self._fill_iter = None
        self.gr_fill_timer.start()


replus = re.compile(r'^[+][^+].*', re.M)
reminus = re.compile(r'^[-][^-].*', re.M)

class HgFileListModel(QtCore.QAbstractTableModel):
    """
    Model used for listing (modified) files of a given Hg revision
    """
    def __init__(self, repo, parent=None):
        """
        data is a HgHLRepo instance
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.repo = repo
        self._datacache = {}
        self.load_config()
        self.current_ctx = None
        self._files = []
        self.diffwidth = 100
        self._fulllist = False
        self._fill_iter = None

    def toggleFullFileList(self):
        self._fulllist = not self._fulllist
        self.loadFiles()
        self.emit(SIGNAL('layoutChanged()'))

    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        self._flagcolor = {}
        self._flagcolor['='] = cfg.getFileModifiedColor(default='blue')
        self._flagcolor['-'] = cfg.getFileRemovedColor(default='red')
        self._flagcolor['-'] = cfg.getFileDeletedColor(default='red')
        self._flagcolor['+'] = cfg.getFileAddedColor(default='green')
        self._displaydiff = cfg.getDisplayDiffStats()

    def setDiffWidth(self, w):
        if w != self.diffwidth:
            self.diffwidth = w
            self._datacache = {}
            self.emit(SIGNAL('dataChanged(const QModelIndex &, const QModelIndex & )'),
                      self.index(2, 0),
                      self.index(2, self.rowCount()))

    def __len__(self):
        return len(self._files)

    def rowCount(self, parent=None):
        return len(self)

    def columnCount(self, parent=None):
        return 1 + self._displaydiff

    def file(self, row):
        return self._files[row]['path']

    def fileflag(self, fn):
        return self._filesdict[fn]['flag']

    def fileparentctx(self, fn, ctx=None):
        if ctx is None:
            return self._filesdict[fn]['parent']
        return ctx.parents()[0]

    def fileFromIndex(self, index):
        if not index.isValid() or index.row()>=len(self) or not self.current_ctx:
            return None
        row = index.row()
        return self._files[row]['path']

    def revFromIndex(self, index):
        if self._fulllist and ismerge(self.current_ctx):
            if not index.isValid() or index.row()>=len(self) or not self.current_ctx:
                return None
            row = index.row()
            current_file_desc = self._files[row]
            if current_file_desc['fromside'] == 'right':
                return self.current_ctx.parents()[1].rev()
            else:
                return self.current_ctx.parents()[0].rev()                
        return None
    
    def indexFromFile(self, filename):
        if filename in self._filesdict:
            row = self._files.index(self._filesdict[filename])
            return self.index(row, 0)
        return QtCore.QModelIndex()

    def _filterFile(self, filename):
        if self._fulllist:
            return True
        return filename in self.current_ctx.files()

    def _buildDesc(self, parent, fromside):
        _files = []
        ctx = self.current_ctx
        ctxfiles = ctx.files()
        changes = self.repo.status(parent.node(), ctx.node())[:3]
        modified, added, removed = changes
        for f in [x for x in added if self._filterFile(x)]:
            desc = {'path':f, 'flag': '+', 'desc':f,
                    'parent': parent, 'fromside': fromside,
                    'infiles': f in ctxfiles}
            m = ctx.filectx(f).renamed()
            if m:
                oldname, node = m
                if oldname in removed:
                    removed.remove(oldname)
                    desc['renamedfrom'] = (oldname, node)
                    desc['flag'] = '='
                    desc['desc'] += '\n (was %s)' % oldname
                else:
                    desc['copiedfrom'] = (oldname, node)
                    desc['flag'] = '='
                    desc['desc'] += '\n (copy of %s)' % oldname

            _files.append(desc)
        for f in [x for x in modified if self._filterFile(x)]:
            _files.append({'path':f, 'flag': '=', 'desc':f,
                           'parent': parent, 'fromside': fromside,
                           'infiles': f in ctxfiles})
        for f in [x for x in removed if self._filterFile(x)]:
            _files.append({'path':f, 'flag': '-', 'desc':f,
                           'parent': parent, 'fromside': fromside,
                           'infiles': f in ctxfiles})
        return _files

    def loadFiles(self):
        self._fill_iter = None
        self._files = []
        self._datacache = {}
        self._files = self._buildDesc(self.current_ctx.parents()[0], 'left')
        if ismerge(self.current_ctx):
            _paths = [x['path'] for x in self._files]
            _files = self._buildDesc(self.current_ctx.parents()[1], 'right')
            self._files += [x for x in _files if x['path'] not in _paths]
        self._filesdict = dict([(f['path'], f) for f in self._files])
        self.fillFileStats()

    def setSelectedRev(self, ctx):
        if ctx != self.current_ctx:
            self.current_ctx = ctx
            self._datacache = {}
            self.loadFiles()
            self.emit(SIGNAL("layoutChanged()"))

    def fillFileStats(self):
        """
        Method called to start the background process of computing
        file stats, which are to be displayed in the 'Stats' column
        """
        if self._displaydiff:
            self._fill_iter = self._fill()
            self._fill_one_step()

    def _fill_one_step(self):
        if self._fill_iter is None:
            return
        try:
            row = self._fill_iter.next()
            idx = self.index(row, 2)
            self.emit(SIGNAL('dataChanged(const QModelIndex&, const QModelIndex&)'),
                      idx, idx)
            QtCore.QTimer.singleShot(0, lambda self=self: self._fill_one_step())

        except StopIteration:
            self._fill_iter = None

    def _fill(self):
        # the generator used to fill file stats as a background process
        for row, desc in enumerate(self._files):
            filename = desc['path']
            if desc['flag'] == '=':
                diff = revdiff(self.repo, self.current_ctx, desc['parent'],
                               files=[filename])
                try:
                    tot = self.current_ctx.filectx(filename).data().count('\n')
                except LookupError:
                    tot = 0
                add = len(replus.findall(diff))
                rem = len(reminus.findall(diff))
                if tot == 0:
                    tot = max(add + rem, 1)
                desc['stats'] = (tot, add, rem)
            yield row

    @datacached
    def data(self, index, role):
        if not index.isValid() or index.row()>len(self) or not self.current_ctx:
            return nullvariant
        row = index.row()
        column = index.column()

        current_file_desc = self._files[row]
        current_file = current_file_desc['path']
        stats = current_file_desc.get('stats')
        if column == 1:
            if stats is not None:
                if role == QtCore.Qt.DecorationRole:
                    tot, add, rem = stats
                    w = self.diffwidth - 20
                    h = 20

                    np = int(w*add/tot)
                    nm = int(w*rem/tot)
                    nd = w-np-nm

                    pix = QtGui.QPixmap(w+10, h)
                    pix.fill(QtGui.QColor(0,0,0,0))
                    painter = QtGui.QPainter(pix)

                    for x0,w0, color in ((0, nm, 'red'),
                                         (nm, np, 'green'),
                                         (nm+np, nd, 'gray')):
                        color = QtGui.QColor(color)
                        painter.setBrush(color)
                        painter.setPen(color)
                        painter.drawRect(x0+5, 0, w0, h-3)
                    painter.setBrush(QtGui.QColor(0,0,0,0))
                    pen = QtGui.QPen(QtCore.Qt.black)
                    pen.setWidth(0)
                    painter.setPen(pen)
                    painter.drawRect(5, 0, w+1, h-3)
                    painter.end()
                    return QtCore.QVariant(pix)
                elif role == QtCore.Qt.ToolTipRole:
                    tot, add, rem = stats
                    msg = "Diff stats:<br>"
                    msg += "&nbsp;<b>File:&nbsp;</b>%s lines<br>" % tot
                    msg += "&nbsp;<b>added lines:&nbsp;</b> %s<br>" % add
                    msg += "&nbsp;<b>removed lines:&nbsp;</b> %s" % rem
                    return QtCore.QVariant(msg)

        elif column == 0:
            if role in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
                return QtCore.QVariant(current_file_desc['desc'])
            elif role == QtCore.Qt.DecorationRole:
                if self._fulllist and ismerge(self.current_ctx):
                    if current_file_desc['infiles']:
                        icn = geticon('leftright')
                    elif current_file_desc['fromside'] == 'left':
                        icn = geticon('left')
                    elif current_file_desc['fromside'] == 'right':
                        icn = geticon('right')
                    return QtCore.QVariant(icn.pixmap(20,20))
            elif role == QtCore.Qt.FontRole:
                if self._fulllist and current_file_desc['infiles']:
                    font = QtGui.QFont()
                    font.setBold(True)
                    return QtCore.QVariant(font)
            elif role == QtCore.Qt.ForegroundRole:
                color = self._flagcolor.get(current_file_desc['flag'], 'black')
                if color is not None:
                    return QtCore.QVariant(QtGui.QColor(color))
        return nullvariant

    def headerData(self, section, orientation, role):
        if ismerge(self.current_ctx):
            if self._fulllist:
                header = ('File (all)', 'Diff')
            else:
                header = ('File (merged only)', 'Diff')
        else:
            header = ('File', 'Diff')

        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(header[section])

        return nullvariant



class TreeItem(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)
        return item
    addChild = appendChild

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        return self.itemData[column]

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0

    def __getitem__(self, idx):
        return self.childItems[idx]

    def __len__(self):
        return len(self.childItems)

    def __iter__(self):
        for ch in self.childItems:
            yield ch


class ManifestModel(QtCore.QAbstractItemModel):
    """
    Qt model to display a hg manifest, ie. the tree of files at a
    given revision. To be used with a QTreeView.
    """
    def __init__(self, repo, rev, parent=None):
        QtCore.QAbstractItemModel.__init__(self, parent)

        self.repo = repo
        self.changectx = self.repo.changectx(rev)
        self.setupModelData()

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()

        if role != QtCore.Qt.DisplayRole:
            return QtCore.QVariant()

        item = index.internalPointer()
        return QtCore.QVariant(item.data(index.column()))

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self.rootItem.data(section))
        return QtCore.QVariant()

    def index(self, row, column, parent):
        if row < 0 or column < 0 or row >= self.rowCount(parent) or column >= self.columnCount(parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        childItem = parentItem.child(row)
        if childItem is not None:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()
        return parentItem.childCount()

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def setupModelData(self):
        rootData = ["rev %s:%s" % (self.changectx.rev(),
                                   short_hex(self.changectx.node()))]
        self.rootItem = TreeItem(rootData)

        for path in sorted(self.changectx.manifest()):
            path = path.split(osp.sep)
            node = self.rootItem

            for p in path:
                for ch in node:
                    if ch.data(0) == p:
                        node = ch
                        break
                else:
                    node = node.addChild(TreeItem([p], node))

    def pathFromIndex(self, index):
        idxs = []
        while index.isValid():
            idxs.insert(0, index)
            index = self.parent(index)
        return osp.sep.join([index.internalPointer().data(0) for index in idxs])


if __name__ == "__main__":
    from mercurial import ui, hg
    from optparse import OptionParser
    p = OptionParser()
    p.add_option('-R', '--root', default='.',
                 dest='root',
                 help="Repository main directory")
    p.add_option('-f', '--file', default=None,
                 dest='filename',
                 help="display the revision graph of this file (if not given, display the whole rev graph)")

    opt, args = p.parse_args()

    u = ui.ui()
    repo = hg.repository(u, opt.root)
    app = QtGui.QApplication(sys.argv)
    if opt.filename is not None:
        model = FileRevModel(repo, opt.filename)
    else:
        model = HgRepoListModel(repo)

    view = QtGui.QTableView()
    #delegate = GraphDelegate()
    #view.setItemDelegateForColumn(1, delegate)
    view.setShowGrid(False)
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(20)
    view.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
    view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
    view.setModel(model)
    view.setWindowTitle("Simple Hg List Model")
    view.show()
    view.setAlternatingRowColors(True)
    #view.resizeColumnsToContents()
    sys.exit(app.exec_())
