import sys
from PyQt4 import QtCore, QtGui
from hgrepo import HgHLRepo, short_hex, short_bin
connect = QtCore.QObject.connect

    
class HgRepoListModel(QtCore.QAbstractTableModel):
    def __init__(self, data, parent=None):
        """
        data is a HgHLRepo instance
        """
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.repo = data
        self.graph = None
        self.__cache = {} 
        #self.graph = self.repo.graph(self.repo.nodes)
        #self.graph.build()
        self.dot_radius = 8
        
    def __len__(self):
        if self.graph:
            return len(self.graph.rows)
        return 0
    
    def rowCount(self, parent):
        return len(self)

    def columnCount(self, parent):
        return 4

    def data(self, index, role):
        if not index.isValid() or self.graph is None:
            return QtCore.QVariant()
        row = index.row()
        column = index.column()
        node = self.graph.rows[row]
        
        if node is None:
            return  QtCore.QVariant()
        idx = (row, column, role)
        if idx in self.__cache:
            return self.__cache[idx]

        rev_node = self.repo.read_node(node)

        if role == QtCore.Qt.DisplayRole:
            item = QtCore.QVariant(self.getData(row, index.column()))
            self.__cache[idx] = item
            return item
        elif role == QtCore.Qt.ForegroundRole:
            if column == 2: #author
                color = self.repo.colors[rev_node.author_id]
                color = QtCore.QVariant(QtGui.QColor(color))
                self.__cache[idx]=color
                return color
            
        elif role == QtCore.Qt.DecorationRole:
            if column == 1:
                
                node_x = self.graph.x[node]
                lines = self.graph.rowlines[row]

                xmax = self.graph.rownlines[row]
                w = (xmax)*(1*self.dot_radius + 0) + 2
                h = 30 # ? how to get it
                
                dot_x = (1*self.dot_radius + 0) * node_x + self.dot_radius/2
                dot_y = (h/2)-self.dot_radius/2
                tags = rev_node.tags
                if isinstance(tags, (list, tuple)):
                    tags = ", ".join(tags)
                tags = tags.strip()
                font = QtGui.QFont()
                font.setPointSize(font.pointSize()*0.8)
                fontmetric = QtGui.QFontMetrics(font)
                tag_rect = fontmetric.boundingRect(tags)
                tag_w = tag_rect.width()
                tag_h = tag_rect.height()
                
                pix = QtGui.QPixmap(w+tag_w+4, h)
                pix.fill(QtGui.QColor(0,0,0,0))
                painter = QtGui.QPainter(pix)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)

                pen = QtGui.QPen(QtCore.Qt.blue)
                pen.setWidth(2)
                painter.setPen(pen)
                
                for color_src_node, x1, y1, x2, y2 in lines:
                    # x y are expressed here in terms of colums (in the graph)
                    # and row (in the list)
                    color = self.graph.colors.get(color_src_node, "black")
                    lpen = QtGui.QPen(pen)
                    lpen.setColor(QtGui.QColor(color))
                    painter.setPen(lpen)
                    x1 = (1*self.dot_radius + 0) * x1  + self.dot_radius
                    x2 = (1*self.dot_radius + 0) * x2  + self.dot_radius
                    y1 = (y1 - row)*h + h/2
                    y2 = (y2 - row)*h + h/2
                    painter.drawLine(x1, y1, x2, y2)

                painter.setBrush(QtGui.QColor(self.graph.colors.get(node, 'black')))
                painter.setPen(QtCore.Qt.black)
                painter.drawEllipse(dot_x, dot_y, self.dot_radius, self.dot_radius)
                if tags:
                    painter.setBrush(QtCore.Qt.yellow)
                    painter.drawRect(w, 2, tag_w+4, tag_h+2)
                    
                    painter.setFont(font)
                    painter.drawText(w+2, tag_h-1, tags)
                
                painter.end()
                ret = QtCore.QVariant(pix)
                self.__cache[idx] = ret
                return ret
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['ID','Log','Author','Date'][section])

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
        self.__cache = {}
        self.notify_data_changed()

    def notify_data_changed(self):
        self.emit(QtCore.SIGNAL("layoutChanged()"))

class HgFileListModel(QtCore.QAbstractTableModel):
    def __init__(self, repo, graph, parent=None):
        """
        data is a HgHLRepo instance
        """
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.repo = repo
        self.graph = graph
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

    def setSelectedNode(self, node):
        self.current_node = node
        self.emit(QtCore.SIGNAL("layoutChanged()"))
    
    def data(self, index, role):
        if not index.isValid() or index.row()>len(self):
            return QtCore.QVariant()

        if index.column() == 0 and role == QtCore.Qt.DisplayRole:
            if self.current_node:
                if index.row() == 0:
                    return QtCore.QVariant("Content")
                else:
                    return QtCore.QVariant(self.repo.read_node(self.current_node).files[index.row()-1])
        return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return QtCore.QVariant(['File','Diff'][section])

        return QtCore.QVariant()

        
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)

    repo = HgHLRepo(".")
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
    sys.exit(app.exec_())
