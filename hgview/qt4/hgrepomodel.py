import sys
import mx.DateTime as dt
import itertools
import re

from PyQt4 import QtCore, QtGui
connect = QtCore.QObject.connect

COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", "magenta", "darkred", "darkmagenta"]
#COLORS = [str(color) for color in QtGui.QColor.colorNames()]
def get_color(n):
    return COLORS[n % len(COLORS)]

def cvrt_date(date):
    date, tzdelay = date
    return QtCore.QDateTime.fromTime_t(int(date)).toString(QtCore.Qt.ISODate)
    return dt.DateTimeFromTicks(date) + tzdelay/dt.oneHour

from hgview.hggraph import Graph, diff as revdiff
from hgview.config import HgConfig

from hgview.decorators import timeit

# in following lambdas, ctx is a hg changectx 
_columnmap = {'ID': lambda ctx: ctx.rev(),
              'Log': lambda ctx: ctx.description(),
              'Author': lambda ctx: ctx.user(),
              'Date': lambda ctx: cvrt_date(ctx.date()),
              'Tags': lambda ctx: ",".join(ctx.tags()),
              'Branch': lambda ctx: ctx.branch(),
              }

# in following lambdas, r is a hg repo 
_maxwidth = {'ID': lambda r: str(hasattr(r.changelog, "count") and r.changelog.count() or len(r.changelog)),
             'Date': lambda r: cvrt_date(r.changectx(0).date()),
             'Tags': lambda r: sorted(r.tags().keys(), cmp=lambda x,y: cmp(len(x), len(y)))[-1],
             'Branch': lambda r: sorted(r.branchtags().keys(), cmp=lambda x,y: cmp(len(x), len(y)))[-1],
             }

class HgRepoListModel(QtCore.QAbstractTableModel):
    """
    Model used for displaying the revisions of a Hg *local* repository
    """
    _columns = 'ID','Log','Author','Date','Tags', 'Branch'

    def __init__(self, repo, parent=None):
        """
        repo is a hg repo instance
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.repo = repo
        self.loadConfig()
        
        self._user_colors = {}
        self._branch_colors = {}
        self.graph = Graph(self.repo)
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
        self.gr_fill_timer = QtCore.QTimer()
        self._fill_iter = None
        self.connect(self.gr_fill_timer, QtCore.SIGNAL('timeout()'),
                     self.fillGraph)
        QtCore.QTimer.singleShot(0, self.gr_fill_timer.start) 

    def fillGraph(self):
        if self._fill_iter is None:
            self.emit(QtCore.SIGNAL('filling(int)'), len(self.graph))
            self._fill_iter = self.graph.fill()
        try:
            self.emit(QtCore.SIGNAL('filled(int)'), self._fill_iter.next())
        except StopIteration:
            self.gr_fill_timer.stop()
            self._fill_iter = None
            self.emit(QtCore.SIGNAL('fillingover()'))
        
    def loadConfig(self):
        cfg = HgConfig(self.repo.ui)
        self._users, self._aliases = cfg.getUsers()
        self.dot_radius = cfg.getDotRadius(default=8)
        self.rowheight = cfg.getRowHeight()
        
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
            self._user_colors[user] = COLORS[(len(self._user_colors) % len(COLORS))]
        return self._user_colors[user]

    def user_name(self, user):
        return self._aliases.get(user, user)

    def namedbranch_color(self, branch):
        if branch not in self._branch_colors:
            self._branch_colors[branch] = COLORS[(len(self._branch_colors) % len(COLORS))]
        return self._branch_colors[branch]
    
    def rowCount(self, parent=None):
        try:
            return self.repo.changelog.count()
        except AttributeError:
            return len(self.repo.changelog)

    def columnCount(self, parent=None):
        return len(self._columns)

    def col2x(self, col):
        return (1.2*self.dot_radius + 0) * col + self.dot_radius/2 + 3

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()
        row = index.row() + 1
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
                w = (gnode.cols)*(1*self.dot_radius + 0) + 20
                h = self.rowheight

                dot_x = self.col2x(gnode.x) - self.dot_radius/2
                dot_y = (h/2)
                                
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

                for start, end, color in gnode.lines:
                    lpen = QtGui.QPen(pen)
                    lpen.setColor(QtGui.QColor(get_color(color)))
                    lpen.setWidth(2)
                    painter.setPen(lpen)
                    x1 = self.col2x(start)
                    x2 = self.col2x(end)
                    painter.drawLine(x1, dot_y - h/2, x2, dot_y + h/2)
 
                if gnode.rev in self.heads:
                    dot_color = "yellow"
                else:
                    dot_color = QtGui.QColor(self.namedbranch_color(ctx.branch()))

                dot_y = (h/2)-self.dot_radius/2
                    
                painter.setBrush(QtGui.QColor(dot_color))
                painter.setPen(QtCore.Qt.black)
                painter.drawEllipse(dot_x, dot_y, self.dot_radius, self.dot_radius)
                painter.end()
                ret = QtCore.QVariant(pix)
                return ret
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self._columns[section])
        return QtCore.QVariant()

    def row_from_node(self, node):
        try:
            return self.graph.rows.index(node)
        except ValueError:
            return None

    def indexFromRev(self, rev):
        for row, gnode in enumerate(self.graph):
            if gnode.rev == rev:
                return self.index(row-1, 0)
        return None
                
    def clear(self):
        """empty the list"""
        self.graph = None
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
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._user_colors = {}
        self._branch_colors = {}
        self.repo = repo
        self.filename = filename
        self.loadConfig()
        self.filelog = self.repo.file(filename)
        self.heads = [self.filelog.rev(x) for x in self.filelog.heads()]
        self._ctxcache = {}
        
    def rowCount(self, parent=None):
        try:
            return self.filelog.count()
        except AttributeError:
            return len(self.filelog)

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()
        row = self.rowCount() - index.row() - 1 
        column = self._columns[index.column()]
        if row in self._ctxcache:
            ctx = self._ctxcache[row]
        else:
            ctx = self.repo.filectx(self.filename, fileid=self.filelog.node(row)).changectx()
            self._ctxcache[row] = ctx
            
        if role == QtCore.Qt.DisplayRole:
            if column == 'Author': #author
                return QtCore.QVariant(self.user_name(_columnmap[column](ctx)))
            return QtCore.QVariant(_columnmap[column](ctx))
        elif role == QtCore.Qt.ForegroundRole:
            if column == 'Author': #author
                return QtCore.QVariant(QtGui.QColor(self.user_color(ctx.user())))
            if column == 'Branch': #branch
                return QtCore.QVariant(QtGui.QColor(self.namedbranch_color(ctx.branch())))
        return QtCore.QVariant()

replus = re.compile(r'^[+][^+].*', re.M)
reminus = re.compile(r'^[-][^-].*', re.M)

class HgFileListModel(QtCore.QAbstractTableModel):
    """
    Model used for listing (modified) files of a given Hg revision
    """
    def __init__(self, repo, graph, parent=None):
        """
        data is a HgHLRepo instance
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.repo = repo
        self.loadConfig()
        self.stats = [] # list of couples (n_line_added, n_line_removed),
                        # one for each file 
        self.current_ctx = None
        self.connect(self, QtCore.SIGNAL("dataChanged(const QModelIndex & , const QModelIndex & )"),
                     self.datachangedcalled)
        self.diffwidth = 100

    def loadConfig(self):
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
        self.current_ctx = ctx
        self.changes = self.repo.status(ctx.parents()[0].node(), ctx.node())[:5]
        self.emit(QtCore.SIGNAL("layoutChanged()"))

    def fileflag(self, fn, ctx=None):
        if ctx is not None:
            changes = self.repo.status(ctx.parents()[0].node(), ctx.node())[:5]
        else:
            changes = self.changes
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
        
    def data(self, index, role):
        if not index.isValid() or index.row()>len(self) or not self.current_ctx:
            return QtCore.QVariant()
        row = index.row()
        column = index.column()

        current_file = self.current_ctx.files()[row]
        stats = None

        if column == 2:
            # graph display of the diff
            diff = revdiff(self.repo, self.current_ctx, files=[current_file])
            fdata = self.current_ctx.filectx(current_file).data()
            add = len(replus.findall(diff))
            rem = len(reminus.findall(diff))
            tot = len(fdata.splitlines())
            if tot == 0:
                tot = add + rem
                
            if role == QtCore.Qt.DecorationRole:
                w = self.diffwidth - 20
                h = 20 

                np = int(w*add/tot)
                nm = int(w*rem/tot)
                nd = w-np-nm

                pix = QtGui.QPixmap(w+10, h)
                pix.fill(QtGui.QColor(0,0,0,0))
                painter = QtGui.QPainter(pix)
                #painter.setRenderHint(QtGui.QPainter.Antialiasing)

                for x0,w0, color in ((0, nm, 'red'), (nm, np, 'green'),
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
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['File', 'Flag', 'Diff'][section])

        return QtCore.QVariant()

        
if __name__ == "__main__":
    from mercurial import ui, hg
    root = '.'
    if len(sys.argv)>1:
        root=sys.argv[1]
    u = ui.ui()    
    repo = hg.repository(u, root)
    app = QtGui.QApplication(sys.argv)
    model = HgRepoListModel(repo)
    
    view = QtGui.QTableView()
    #delegate = GraphDelegate()
    #view.setItemDelegateForColumn(1, delegate)
    view.setShowGrid(False)
    view.verticalHeader().hide()
    view.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
    view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
    view.setModel(model)
    view.setWindowTitle("Simple Hg List Model")
    view.show()
    view.setAlternatingRowColors(True)
    view.resizeColumnsToContents()
    print "number of branches:", len(model.graph.rawgraph) 
    sys.exit(app.exec_())
