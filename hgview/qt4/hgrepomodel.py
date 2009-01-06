import sys
import mx.DateTime as dt
import itertools

from PyQt4 import QtCore, QtGui
connect = QtCore.QObject.connect

COLORS = [ "blue", "darkgreen", "red", "green", "darkblue", "purple",
           "cyan", "magenta", "darkred", "darkmagenta"]

def get_color(n):
    return COLORS[n % len(COLORS)]

def cvrt_date(date):
    date, tzdelay = date
    return QtCore.QDateTime.fromTime_t(int(date))
    return dt.DateTimeFromTicks(date) + tzdelay/dt.oneHour

    

from hgext.graphlog import revision_grapher, fix_long_right_edges
from hgext.graphlog import get_nodeline_edges_tail, get_padding_line
from hgext.graphlog import draw_edges, get_rev_parents
from mercurial.node import nullrev
from hgview.hggraph import Graph

class HgRepoListModel(QtCore.QAbstractTableModel):
    _columnmap = [lambda ctx: ctx.rev(),
                  lambda ctx: ctx.description(),
                  lambda ctx: ctx.user(),
                  lambda ctx: cvrt_date(ctx.date()),
                  lambda ctx: ",".join(ctx.tags()),
                  lambda ctx: ctx.branch(),
                  ]
    def __init__(self, repo, parent=None):
        """
        repo is a hg repo instance
        """
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.repo = repo
        self.__len = 0
        self.__cache = {} 
        self.dot_radius = 8
        self._user_colors = {}
        self._branch_colors = {}
        self.graph = Graph(self.repo)
        self.heads = [self.repo.changectx(x).rev() for x in self.repo.heads()]
        
    def user_color(self, user):
        if user not in self._user_colors:
            self._user_colors[user] = COLORS[(len(self._user_colors) % len(COLORS))]
        return self._user_colors[user]

    def namedbranch_color(self, branch):
        if branch not in self._branch_colors:
            self._branch_colors[branch] = COLORS[(len(self._branch_colors) % len(COLORS))]
        return self._branch_colors[branch]
    
    def rowCount(self, parent=None):
        return self.repo.changelog.count()

    def columnCount(self, parent=None):
        return 6

    def col2x(self, col):
        return (1.2*self.dot_radius + 0) * col + self.dot_radius/2 + 3

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()
        row = index.row() + 1
        column = index.column()
        gnode = self.graph[row]
        ctx = self.repo.changectx(gnode.rev)
        if role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(self._columnmap[column](ctx))
        elif role == QtCore.Qt.ForegroundRole:
            if column == 2: #author
                return QtCore.QVariant(QtGui.QColor(self.user_color(ctx.user())))
            if column == 5: #branch
                return QtCore.QVariant(QtGui.QColor(self.namedbranch_color(ctx.branch())))
        elif role == QtCore.Qt.DecorationRole:
            if column == 1:
                w = (gnode.cols)*(1*self.dot_radius + 0) + 20
                h = 30 # ? how to get it

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
                inc = int(gnode.dx>0)
                dec = int(gnode.dx<0)
                    
                for x1, y1, x2, y2, color in gnode.lines:
                    lpen = QtGui.QPen(pen)
                    lpen.setColor(QtGui.QColor(get_color(color)))
                    lpen.setWidth(3)
                    painter.setPen(lpen)

                    x1 = self.col2x(x1)
                    x2 = self.col2x(x2)                    
                    painter.drawLine(x1, dot_y + y1*h, x2, dot_y + y2*h)
 
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
##                 self.__cache[idx] = ret
                return ret
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['ID','Log','Author','Date','Tags', 'Branch'][section])
        return QtCore.QVariant()

    def getData(self, row, column):
        #print "gatData", row, column
        rev_node = self.repo.read_node(self.graph.rows[row])
        if column == 0:
            data = rev_node.rev
        elif column == 1:
            data = rev_node.short
        elif column == 2:
            data = self.repo.authors[rev_node.author_id]
        elif column == 3:
            data = rev_node.date
        else:
            data = ""
        return data

    def row_from_node(self, node):
        try:
            return self.graph.rows.index(node)
        except ValueError:
            return None
    
    def clear(self):
        """empty the list"""
        self.graph = None
        self.__len = 0
        self.__cache = {}
        self.notify_data_changed()

    def notify_data_changed(self):
        self.compute_len()
        self.emit(QtCore.SIGNAL("layoutChanged()"))

class HgFileListModel(QtCore.QAbstractTableModel):
    def __init__(self, repo, graph, parent=None):
        """
        data is a HgHLRepo instance
        """
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.repo = repo
        self.stats = [] # list of couples (n_line_added, n_line_removed),
                        # one for each file 
        self.current_node = None
        self.connect(self, QtCore.SIGNAL("dataChanged(const QModelIndex & , const QModelIndex & )"),
                     self.datachangedcalled)

    def __len__(self):
        if self.current_node:
            rev_node = self.repo.read_node(self.current_node)
            n = len(rev_node.files)
            if n > 0:
                return n+1
        return 0
    
    def datachangedcalled(self, fr, to):
        print "datachangedcalled"
    def rowCount(self, parent):
        return len(self)

    def columnCount(self, parent):
        return 2

    def setSelectedNode(self, node, stats):
        self.current_node = node
        #assert len(self.repo.read_node(node).files) == len(stats)
        self.stats = stats
        if self.stats:
            self.statmax = max([sum(x) for x in self.stats.values()])
        else:
            self.statmax = 0
        
        self.emit(QtCore.SIGNAL("layoutChanged()"))

    def data(self, index, role):
        if not index.isValid() or index.row()>len(self) or not self.current_node:
            return QtCore.QVariant()
        row = index.row()
        column = index.column()

        current_file = self.repo.read_node(self.current_node).files[index.row()-1]
        stats = self.stats.get(current_file)
        if role == QtCore.Qt.DisplayRole:
            if column == 0:
                if row == 0:
                    return QtCore.QVariant("Content")
                else:
                    return QtCore.QVariant(current_file)
            elif column == 1:
                if row == 0 or stats is None:
                    return QtCore.QVariant("")
                else:
                    return QtCore.QVariant("+%s | -%s"%tuple(stats))
                
        if role == QtCore.Qt.DecorationRole:
            if column == 1:
                if row == 0 or stats is None:
                    return QtCore.QVariant()

                w = 100 # ? how to get it
                h = 20 

                np = int(w*stats[0]/self.statmax)
                nm = int(w*stats[1]/self.statmax)
                nd = w-np-nm

                pix = QtGui.QPixmap(w+10, h)
                pix.fill(QtGui.QColor(0,0,0,0))
                painter = QtGui.QPainter(pix)
                #painter.setRenderHint(QtGui.QPainter.Antialiasing)

                for x0,w0, color in ((0,nm, 'red'), (nm,np, 'green'),
                                    (nm+np, nd, 'gray')):
                    color = QtGui.QColor(color)
                    painter.setBrush(color)
                    painter.setPen(color)
                    painter.drawRect(x0+5,5,w0, h-5)
                painter.setBrush(QtGui.QColor(0,0,0,0))
                pen = QtGui.QPen(QtCore.Qt.black)
                pen.setWidth(0)
                painter.setPen(pen)
                painter.drawRect(5,5,w+2,h-6)
                painter.end()
                return QtCore.QVariant(pix)
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['File','Diff'][section])

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
