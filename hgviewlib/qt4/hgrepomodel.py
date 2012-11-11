# Copyright (c) 2009-2012 LOGILAB S.A. (Paris, FRANCE).
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
Qt4 model for hg repo changelogs and filelogs
"""
import sys
import re
import os, os.path as osp

from mercurial.node import nullrev
from mercurial.node import hex, short as short_hex
from mercurial.revlog import LookupError
from mercurial import util, error

from hgviewlib.hggraph import Graph, ismerge, diff as revdiff, HgRepoListWalker
from hgviewlib.hggraph import revision_grapher, filelog_grapher, getlog, gettags
from hgviewlib.config import HgConfig
from hgviewlib.util import tounicode, isbfile, Curry
from hgviewlib.qt4 import icon as geticon
from hgviewlib.decorators import timeit
from hgviewlib.hgpatches import phases

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

# We use two colors, One for even rows and one for odd rows
COLOR_BG_OBSOLETE = [QtGui.QColor(255, 250, 250), QtGui.QColor(243, 230, 230)]
COLOR_BG_TROUBLED = [QtGui.QColor(255, 193,  71), QtGui.QColor(255, 153,  51)]
COLOR_BG_HIGHLIGHT = [QtGui.QColor(127, 199, 175),
                      QtGui.QColor(127, 199, 175).lighter()]



def cvrt_date(date):
    """
    Convert a date given the hg way, ie. couple (date, tz), into a
    formatted QString
    """
    if not date:
        return QtCore.QString(u'')
    date, tzdelay = date
    return QtCore.QDateTime.fromTime_t(int(date)).toString(QtCore.Qt.LocaleDate)


# XXX maybe it's time to make these methods of the model...
# in following lambdas, ctx is a hg changectx
_columnmap = {'ID': lambda model, ctx, gnode: ctx.rev() is not None and str(ctx.rev()) or "",
              'Log': getlog,
              'Author': lambda model, ctx, gnode: tounicode(ctx.user()),
              'Date': lambda model, ctx, gnode: cvrt_date(ctx.date()),
              'Tags': gettags,
              'Branch': lambda model, ctx, gnode: ctx.branch(),
              'Filename': lambda model, ctx, gnode: gnode.extra[0],
              'Phase': lambda model, ctx, gnode: ctx.phasestr(),
              }

_tooltips = {'ID': lambda model, ctx, gnode: ctx.rev() is not None and ctx.hex() or "Working Directory",
             }

def auth_width(model, repo):
    auths = model._aliases.values()
    if not auths:
        return None
    return sorted(auths, cmp=lambda x,y: cmp(len(x), len(y)))[-1]

# in following lambdas, r is a hg repo
_maxwidth = {'ID': lambda self, r: str(len(r.changelog)),
             'Date': lambda self, r: cvrt_date(r.changectx(0).date()),
             'Tags': lambda self, r: sorted(r.tags().keys(), key=len)[-1][:10],
             'Branch': lambda self, r: sorted(r.branchtags().keys(), key=len)[-1]
                                              if r.branchtags().keys() else None,
             'Author': lambda self, r: 'author name',
             'Filename': lambda self, r: self.filename,
             'Phase': lambda self, r: sorted(phases.phasenames, key=len)[-1]
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

class HgRepoListModel(QtCore.QAbstractTableModel, HgRepoListWalker):
    """
    Model used for displaying the revisions of a Hg *local* repository
    """
    _allcolumns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _columns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags',)
    _stretchs = {'Log': 1, }
    _getcolumns = "getChangelogColumns"

    def __init__(self, repo, branch='', fromhead=None, follow=False, parent=None, show_hidden=False, closed=False):
        """
        repo is a hg repo instance
        """
        self._fill_timer = None
        QtCore.QAbstractTableModel.__init__(self, parent)
        HgRepoListWalker.__init__(self, repo, branch, fromhead, follow, closed=closed)
        self.highlights = []

    def setRepo(self, repo, branch='', fromhead=None, follow=False, closed=False):
        HgRepoListWalker.setRepo(self, repo, branch, fromhead, follow, closed=closed)
        self.emit(SIGNAL('layoutChanged()'))
        QtCore.QTimer.singleShot(0, Curry(self.emit, SIGNAL('filled')))
        self._fill_timer = self.startTimer(50)

    def highlight_rows(self, rows):
        """mark ``rows`` to be highlighted."""
        self.highlights[:] = rows
        self._datacache.clear()

    def timerEvent(self, event):
        if event.timerId() == self._fill_timer:
            self.emit(SIGNAL('showMessage'),
                      'filling (%s)' % (len(self.graph)),
                      -1)
            if self.graph.isfilled():
                self.killTimer(self._fill_timer)
                self._fill_timer = None
                self.emit(SIGNAL('showMessage'), '', -1)
            # we only fill the graph data strctures without telling
            # views (until we atually did the full job), to keep
            # maximal GUI reactivity
            elif not self.graph.build_nodes(nnodes=self.fill_step):
                self.killTimer(self._fill_timer)
                self._fill_timer = None
                self.updateRowCount()
                self.emit(SIGNAL('showMessage'), '', -1)

    def updateRowCount(self):
        currentlen = self.rowcount
        newlen = len(self.graph)
        if newlen > self.rowcount:
            self.beginInsertRows(QtCore.QModelIndex(), currentlen, newlen-1)
            self.rowcount = newlen
            self.endInsertRows()

    @staticmethod
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
        return HgRepoListWalker.user_color(self, user)

    def col2x(self, col, pan):
        return (self.dot_radius + pan) * col + 2  # max pen width

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
                user = _columnmap[column](self, ctx, gnode) if ctx.node() else u'' 
                return QtCore.QVariant(self.user_name(user))
            elif column == 'Log':
                msg = _columnmap[column](self, ctx, gnode)
                bookmarks = ctx.bookmarks()
                if bookmarks:
                    msg = '<%s> ~ %s' % (','.join(bookmarks), msg)
                return QtCore.QVariant(msg)
            return QtCore.QVariant(_columnmap[column](self, ctx, gnode))
        elif role == QtCore.Qt.ToolTipRole:
            msg = "<b>Branch:</b> %s<br>\n" % ctx.branch()
            msg += "<b>Phase:</b> %s<br>\n" % ctx.phasestr()
            if gnode.rev in self.wd_revs:
                msg += " <i>Working Directory position"
                states = 'modified added removed deleted'.split()
                status = self.wd_status[self.wd_revs.index(gnode.rev)]
                status = [state for st, state in zip(status, states) if st]
                if status:
                    msg += ' (%s)' % (', '.join(status))
                msg += "</i><br>\n"
            msg += _tooltips.get(column, _columnmap[column])(self, ctx, gnode)
            return QtCore.QVariant(msg)
        elif role == QtCore.Qt.ForegroundRole:
            color = None
            if column == 'Author': #author
                user = ctx.user() if ctx.node() else ''
                color = QtGui.QColor(self.user_color(user))
                if ctx.obsolete():
                    color = color.lighter()
            elif column == 'Branch': #branch
                color = QtGui.QColor(self.namedbranch_color(ctx.branch()))
                if ctx.obsolete():
                    color = color.lighter()
            elif ctx.obsolete():
                color = QtGui.QColor('grey')
            if color is not None:
                return QtCore.QVariant(color)

        elif role == QtCore.Qt.BackgroundRole:
            row = index.row()
            if row in self.highlights:
                return COLOR_BG_HIGHLIGHT[row % 2]
            elif ctx.obsolete():
                return COLOR_BG_OBSOLETE[row % 2]
            elif ctx.troubles():
                return COLOR_BG_TROUBLED[row % 2]

        elif role == QtCore.Qt.DecorationRole:
            if column == 'Log':
                if not getattr(ctx, 'applied', True):
                    return nullvariant
                radius = self.dot_radius
                pan = 2
                w = self.col2x(gnode.cols, pan)
                h = self.rowheight

                dot_x = self.col2x(gnode.x, pan)
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
                    for start, end, color, fill in lines:
                        lpen = QtGui.QPen(pen)
                        color = QtGui.QColor(self.get_color(color))
                        if not fill:
                             lpen.setStyle(QtCore.Qt.DotLine)
                             color.setAlpha(150)
                        lpen.setColor(color)
                        lpen.setWidth(2)
                        painter.setPen(lpen)
                        x1 = self.col2x(start, pan) + radius / 2
                        x2 = self.col2x(end, pan) + radius / 2
                        painter.drawLine(x1, dot_y + y1, x2, dot_y + y2)

                dot_color = QtGui.QColor(self.namedbranch_color(ctx.branch()))
                dotcolor = QtGui.QColor(dot_color)
                if ctx.obsolete():
                    penradius = 1
                    pencolor = dotcolor.setAlpha(150)
                elif gnode.rev in self.heads:
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
                tags = set(ctx.tags())
                icn = None

                modified = False
                atwd = False
                if gnode.rev in self.wd_revs:
                    atwd = True
                    status = self.wd_status[self.wd_revs.index(gnode.rev)]
                    if [True for st in status if st]:
                        modified = True

                phase = ctx.phase()

                if gnode.rev is None:
                    # WD is displayed only if there are local
                    # modifications, so let's use the modified icon
                    icn = geticon('modified')
                elif tags.intersection(self.mqueues):
                    icn = geticon('mqpatch')
                #elif modified:
                #    icn = geticon('modified')
                elif atwd:
                    if phase > phases.public:
                        pen_color = QtCore.Qt.red
                        pen = QtGui.QPen(pen_color)
                        pen.setWidth(penradius)
                        painter.setPen(pen)
                    else:
                        icn = geticon('clean')


                if icn:
                    icn.paint(painter, dot_x-5, dot_y-5, 17, 17)
                elif phase == phases.draft:
                    painter.drawRect(dot_x, dot_y, radius, radius)
                elif phase == phases.secret:
                    P = QtCore.QPointF
                    painter.drawPolygon(
                        P(dot_x + (radius//2), dot_y),
                        P(dot_x, dot_y + radius),
                        P(dot_x + radius, dot_y+radius)
                        )
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

    def maxWidthValueForColumn(self, column):
        column = self._columns[column]
        if column in _maxwidth:
            return _maxwidth[column](self, self.repo)
        return None

    def clear(self):
        """empty the list"""
        self.graph = None
        self._datacache = {}
        self.notify_data_changed()

    def notify_data_changed(self):
        self.emit(SIGNAL("layoutChanged()"))

    def indexFromRev(self, rev):
        self.ensureBuilt(rev=rev)
        row = self.rowFromRev(rev)
        if row is not None:
            return self.index(row, 0)
        return None

class FileRevModel(HgRepoListModel):
    """
    Model used to manage the list of revisions of a file, in file
    viewer of in diff-file viewer dialogs.
    """
    _allcolumns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Tags', 'Filename')
    _columns = ('ID', 'Branch', 'Log', 'Author', 'Date', 'Filename')
    _stretchs = {'Log': 1, }
    _getcolumns = "getFilelogColumns"

    def __init__(self, repo, filename=None, parent=None):
        """
        data is a HgHLRepo instance
        """
        HgRepoListModel.__init__(self, repo, parent=parent)
        self.setFilename(filename)

    def setRepo(self, repo, branch='', fromhead=None, follow=False, closed=False):
        self.repo = repo
        self._datacache = {}
        self.load_config()

    def setFilename(self, filename):
        self.filename = filename

        self._user_colors = {}
        self._branch_colors = {}

        self.rowcount = 0
        self._datacache = {}

        if self.filename:
            grapher = filelog_grapher(self.repo, self.filename)
            self.graph = Graph(self.repo, grapher, self.max_file_size)
            fl = self.repo.file(self.filename)
            # we use fl.index here (instead of linkrev) cause
            # linkrev API changed between 1.0 and 1.?. So this
            # works with both versions.
            self.heads = [fl.index[fl.rev(x)][4] for x in fl.heads()]
            self.ensureBuilt(row=self.fill_step/2)
            QtCore.QTimer.singleShot(0, Curry(self.emit, SIGNAL('filled')))
            self._fill_timer = self.startTimer(500)
        else:
            self.graph = None
            self.heads = []


replus = re.compile(r'^[+][^+].*', re.M)
reminus = re.compile(r'^[-][^-].*', re.M)

class HgFileListModel(QtCore.QAbstractTableModel):
    """
    Model used for listing (modified) files of a given Hg revision
    """

    _description_desc = dict(path='', flag='', desc='Display revision description',
                             bfile=None, parent=None, fromside=None, infiles=False)

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
        self._filesdict = {}
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
        self._flagcolor['='] = cfg.getFileModifiedColor()
        self._flagcolor['-'] = cfg.getFileRemovedColor()
        self._flagcolor['-'] = cfg.getFileDeletedColor()
        self._flagcolor['+'] = cfg.getFileAddedColor()
        self._flagcolor[''] = cfg.getFileDescriptionColor()
        self._displaydiff = cfg.getDisplayDiffStats()
        self._descriptionview = cfg.getFileDescriptionView()

    def setDiffWidth(self, w):
        if w != self.diffwidth:
            self.diffwidth = w
            self._datacache = {}
            self.emit(SIGNAL('dataChanged(const QModelIndex &, const QModelIndex & )'),
                      self.index(1, 0),
                      self.index(1, self.rowCount()))

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
        file_info = self._files[row]
        return self._files[row]['path']

    def revFromIndex(self, index):
        if self._fulllist and ismerge(self.current_ctx):
            if not index.isValid() or index.row()>=len(self) or not self.current_ctx:
                return None
            row = index.row()
            if self._files[row]['fromside'] == 'right':
                return self.current_ctx.parents()[1].rev()
            return self.current_ctx.parents()[0].rev()
        return None

    def indexFromFile(self, filename):
        if filename in self._filesdict:
            row = self._files.index(self._filesdict[filename])
            return self.index(row, 0)
        return QtCore.QModelIndex()

    def _filterFile(self, filename, ctxfiles):
        if self._fulllist:
            return True
        return filename in ctxfiles #self.current_ctx.files()

    def _buildDesc(self, parent, fromside):
        _files = []
        ctx = self.current_ctx
        ctxfiles = ctx.files()
        changes = self.repo.status(parent.node(), ctx.node())[:3]
        modified, added, removed = changes
        for lst, flag in ((added, '+'), (modified, '='), (removed, '-')):
            for f in [x for x in lst if self._filterFile(x, ctxfiles)]:
                desc = f
                bfile = isbfile(f)
                if bfile:
                    desc = desc.replace('.hgbfiles'+os.sep, '')
                _files.append({'path': f, 'flag': flag, 'desc': desc, 'bfile': bfile,
                               'parent': parent, 'fromside': fromside,
                               'infiles': f in ctxfiles})
                # renamed/copied files are handled by background
                # filling process since it can be a bit long
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
        if self._descriptionview == 'asfile':
            self._files.insert(0, self._description_desc)
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
        self._fill_iter = self._fill()
        self._fill_one_step()

    def _fill_one_step(self):
        if self._fill_iter is None:
            return
        try:
            nextfill = self._fill_iter.next()
            if nextfill is not None:
                row, col = nextfill
                idx = self.index(row, col)
                self.emit(SIGNAL('dataChanged(const QModelIndex &, const QModelIndex &)'),
                          idx, idx)
            QtCore.QTimer.singleShot(10, lambda self=self: self._fill_one_step())

        except StopIteration:
            self._fill_iter = None

    def _fill(self):
        # the generator used to fill file stats as a background process
        files = enumerate(self._files)
        if self._descriptionview == 'asfile':
            files.next() # consume description entry
        for row, desc in files:
            filename = desc['path']
            if desc['flag'] == '=' and self._displaydiff:
                try:
                    diff = revdiff(self.repo, self.current_ctx, None, files=[filename])
                    tot = self.current_ctx.filectx(filename).data().count('\n')
                    add = len(replus.findall(diff))
                    rem = len(reminus.findall(diff))
                except (LookupError, TypeError): # unknown revision and mq support
                    tot, add, rem = 0, 0, 0

                if tot == 0:
                    tot = max(add + rem, 1)
                desc['stats'] = (tot, add, rem)
                yield row, 1

            if desc['flag'] == '+':
                m = self.current_ctx.filectx(filename).renamed()
                if m:
                    removed = self.repo.status(desc['parent'].node(),
                                               self.current_ctx.node())[2]
                    oldname, node = m
                    if oldname in removed:
                        # removed.remove(oldname) XXX
                        desc['renamedfrom'] = (oldname, node)
                        desc['flag'] = '='
                        desc['desc'] += '\n (was %s)' % oldname
                    else:
                        desc['copiedfrom'] = (oldname, node)
                        desc['flag'] = '='
                        desc['desc'] += '\n (copy of %s)' % oldname
                    yield row, 0
            yield None

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
                    icn = None
                    if current_file_desc['infiles']:
                        icn = geticon('leftright')
                    elif current_file_desc['fromside'] == 'left':
                        icn = geticon('left')
                    elif current_file_desc['fromside'] == 'right':
                        icn = geticon('right')
                    if icn:
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
        if self.changectx.rev() is not None:
            rootData = ["rev %s:%s" % (self.changectx.rev(),
                                       short_hex(self.changectx.node()))]
        else:
            rootData = ['Working Directory']
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

