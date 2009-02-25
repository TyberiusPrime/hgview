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
"""Qt4 model for hg repo changelogs and filelogs

"""
import sys
import mx.DateTime as dt
import re

from mercurial.node import nullrev
from mercurial.revlog import LookupError

from hgview.hggraph import Graph, diff as revdiff
from hgview.hggraph import revision_grapher, filelog_grapher
from hgview.config import HgConfig
from hgview.decorators import timeit

from PyQt4 import QtCore, QtGui
connect = QtCore.QObject.connect
nullvariant = QtCore.QVariant()

COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", "magenta", "darkred", "darkmagenta"]
#COLORS = [str(color) for color in QtGui.QColor.colorNames()]
def get_color(n):
    """
    Return a color at index 'n' rotating in the available colors
    """
    return COLORS[n % len(COLORS)]

def cvrt_date(date):
    """
    Convert a date given the hg way, ie. couple (date, tz), into a
    formatted QString
    """
    date, tzdelay = date
    return QtCore.QDateTime.fromTime_t(int(date)).toString(QtCore.Qt.ISODate)

# in following lambdas, ctx is a hg changectx
_columnmap = {'ID': lambda ctx: ctx.rev(),
              'Log': lambda ctx: ctx.description(),
              'Author': lambda ctx: ctx.user(),
              'Date': lambda ctx: cvrt_date(ctx.date()),
              'Tags': lambda ctx: ",".join(ctx.tags()),
              'Branch': lambda ctx: ctx.branch(),
              }

# in following lambdas, r is a hg repo
_maxwidth = {'ID': lambda r: str(len(r.changelog)),
             'Date': lambda r: cvrt_date(r.changectx(0).date()),
             'Tags': lambda r: sorted(r.tags().keys(),
                                      cmp=lambda x,y: cmp(len(x), len(y)))[-1],
             'Branch': lambda r: sorted(r.branchtags().keys(),
                                        cmp=lambda x,y: cmp(len(x), len(y)))[-1],
             }

def datacached(meth):
    """
    decorator used to cache 'data' method of Qt models
    """
    def data(self, index, role):
        if not index.isValid():
            return nullvariant
        row = index.row()
        col = index.column()
        if (row, col, role) in self._datacache:
            return self._datacache[(row, col, role)]
        result = meth(self, index, role)
        self._datacache[(row, col, role)] = result
        return result
    return data

class HgRepoListModel(QtCore.QAbstractTableModel):
    """
    Model used for displaying the revisions of a Hg *local* repository
    """
    _columns = 'ID','Log','Author','Date','Tags', 'Branch'

    def __init__(self, repo, branch='', parent=None):
        """
        repo is a hg repo instance
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._datacache = {}
        self.gr_fill_timer = QtCore.QTimer()
        self.connect(self.gr_fill_timer, QtCore.SIGNAL('timeout()'),
                     self.fillGraph)
        self.setRepo(repo, branch)

    #@timeit
    def setRepo(self, repo, branch=''):
        self.repo = repo
        self._datacache = {}
        self.load_config()

        self._user_colors = {}
        self._branch_colors = {}
        grapher = revision_grapher(self.repo, branch=branch)
        self.graph = Graph(self.repo, grapher)
        self.nmax = len(self.repo.changelog)
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
        self._fill_iter = None
        self.gr_fill_timer.start()

    def fillGraph(self):
        step = self.fill_step
        if self._fill_iter is None:
            self.emit(QtCore.SIGNAL('filling(int)'), self.nmax)
            self._fill_iter = self.graph.fill(step=step)
            self.emit(QtCore.SIGNAL('layoutChanged()'))
            QtGui.QApplication.processEvents()
        try:
            n = len(self.graph)
            nm = min(n+step, self.nmax)
            self.beginInsertRows(QtCore.QModelIndex(), n, nm)
            nfilled = self._fill_iter.next()
            self.emit(QtCore.SIGNAL('filled(int)'), nfilled)
        except StopIteration:
            self.gr_fill_timer.stop()
            self._fill_iter = None
            self.emit(QtCore.SIGNAL('fillingover()'))
            self.emit(QtCore.SIGNAL('layoutChanged()'))
        finally:
            self.endInsertRows()

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

    def maxWidthValueForColumn(self, column):
        column = self._columns[column]
        if column in _maxwidth:
            return _maxwidth[column](self.repo)
        return None

    def user_color(self, user):
        if user in self._aliases:
            user = self._aliases[user]
        if user in self._users:
            try:
                return QtGui.QColor(self._users[user]['color'])
            except:
                pass
        if user not in self._user_colors:
            self._user_colors[user] = get_color(len(self._user_colors))
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
        column = self._columns[index.column()]
        gnode = self.graph[row]
        ctx = self.repo.changectx(gnode.rev)
        if role == QtCore.Qt.DisplayRole:
            if column == 'Author': #author
                return QtCore.QVariant(self.user_name(_columnmap[column](ctx)))
            return QtCore.QVariant(_columnmap[column](ctx))
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

                color = "black"
                lpen = QtGui.QPen(pen)
                lpen.setColor(QtGui.QColor(color))
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
                if gnode.rev in self.heads:
                    dot_color = "yellow"
                else:
                    dot_color = QtGui.QColor(self.namedbranch_color(ctx.branch()))

                dot_y = (h/2) - radius / 2

                painter.setBrush(QtGui.QColor(dot_color))
                painter.setPen(QtCore.Qt.black)
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
        for row, gnode in enumerate(self.graph):
            if gnode.rev == rev:
                return row
        return None

    def indexFromRev(self, rev):
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
        self.emit(QtCore.SIGNAL("layoutChanged()"))

class FileRevModel(HgRepoListModel):
    """
    Model used to manage the list of revisions of a file, in file
    viewer of in diff-file viewer dialogs.
    """
    _columns = ('ID', 'Log', 'Author', 'Date')

    def __init__(self, repo, filename, noderev=None, parent=None):
        """
        data is a HgHLRepo instance
        """
        HgRepoListModel.__init__(self, repo, parent=parent)
        self.filelog = self.repo.file(filename)
        self.setFilename(filename)

    def setRepo(self, repo, branch=''):
        self.repo = repo
        self._datacache = {}
        self.load_config()

    def setFilename(self, filename):
        self.filename = filename
        self.filelog = self.repo.file(filename)
        self.nmax = len(self.filelog)
        grapher = filelog_grapher(self.repo, self.filename)

        self._user_colors = {}
        self._branch_colors = {}
        self.graph = Graph(self.repo, grapher)
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
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
        self.connect(self, QtCore.SIGNAL("dataChanged(const QModelIndex & , const QModelIndex & )"),
                     self.datachangedcalled)
        self.diffwidth = 100

    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        self._flagcolor = {}
        self._flagcolor['M'] = cfg.getFileModifiedColor(default='blue')
        self._flagcolor['R'] = cfg.getFileRemovedColor(default='red')
        self._flagcolor['D'] = cfg.getFileDeletedColor(default='red')
        self._flagcolor['A'] = cfg.getFileAddedColor(default='green')
        self._flagcolor['?'] = "black"

    def setDiffWidth(self, w):
        if w != self.diffwidth:
            self.diffwidth = w
            self._datacache = {}
            self.emit(QtCore.SIGNAL('dataChanged(const QModelIndex &, const QModelIndex & )'),
                      self.index(2, 0),
                      self.index(2, self.rowCount()))

    def __len__(self):
        if self.current_ctx:
            return len(self.current_ctx.files())
        return 0

    def datachangedcalled(self, fr, to):
        print "datachangedcalled"

    def rowCount(self, parent=None):
        return len(self)

    def columnCount(self, parent=None):
        return 3

    def setSelectedRev(self, ctx):
        if ctx != self.current_ctx:
            self.current_ctx = ctx
            self._datacache = {}
            self.changes = [self.repo.status(ctx.parents()[0].node(), ctx.node())[:5], None]
            # XXX will we need this?
            #if ctx.parents()[1]:
            #    self.changes[1] = self.repo.status(ctx.parents()[1].node(), ctx.node())[:5]
            self.emit(QtCore.SIGNAL("layoutChanged()"))

    def fileflag(self, fn, ctx=None):
        if ctx is not None and ctx != self.current_ctx:
            changes = self.repo.status(ctx.parents()[0].node(), ctx.node())[:5]
        else:
            changes = self.changes[0]
        modified, added, removed, deleted, unknown = changes
        for fl, lst in zip(["M","A","R","D","?"],
                           [modified, added, removed, deleted, unknown]):
            if fn in lst:
                return fl
        return ''

    def fileFromIndex(self, index):
        if not index.isValid() or index.row()>len(self) or not self.current_ctx:
            return None
        row = index.row()
        return self.current_ctx.files()[row]

    @datacached
    def data(self, index, role):
        if not index.isValid() or index.row()>len(self) or not self.current_ctx:
            return nullvariant
        row = index.row()
        column = index.column()

        current_file = self.current_ctx.files()[row]
        if column == 2:
            if role == QtCore.Qt.DecorationRole:
                # graph display of the diff
                diff = revdiff(self.repo, self.current_ctx, files=[current_file])
                try:
                    fdata = self.current_ctx.filectx(current_file).data()
                    tot = len(fdata.splitlines())
                except LookupError:
                    tot = 0
                add = len(replus.findall(diff))
                rem = len(reminus.findall(diff))
                if tot == 0:
                    tot = max(add + rem, 1)

                w = self.diffwidth - 20
                h = 20

                np = int(w*add/tot)
                nm = int(w*rem/tot)
                nd = w-np-nm

                pix = QtGui.QPixmap(w+10, h)
                pix.fill(QtGui.QColor(0,0,0,0))
                painter = QtGui.QPainter(pix)
                #painter.setRenderHint(QtGui.QPainter.Antialiasing)

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
        else:
            if role == QtCore.Qt.DisplayRole:
                if column == 0:
                    return QtCore.QVariant(current_file)
                elif column == 1:
                    return QtCore.QVariant(self.fileflag(current_file))
            elif role == QtCore.Qt.ForegroundRole:
                if column == 0:
                    color = self._flagcolor.get(self.fileflag(current_file), 'black')
                    if color is not None:
                        return QtCore.QVariant(QtGui.QColor(color))
        return nullvariant

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['File', 'Flag', 'Diff'][section])

        return nullvariant


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
