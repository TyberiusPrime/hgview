# -*- coding: utf-8 -*-
import sys, os

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, SIGNAL

class BlockList(QtGui.QWidget):
    def __init__(self, *args):
        QtGui.QWidget.__init__(self, *args)
        self._blocks = set()
        self._minimum = 0
        self._maximum = 100
        self.blockTypes = {'+': QtGui.QColor(0xA0, 0xFF, 0xB0, ),#0xa5),
                           '-': QtGui.QColor(0xFF, 0xA0, 0xA0, ),#0xa5),
                           'x': QtGui.QColor(0xA0, 0xA0, 0xFF, ),#0xa5),
                           }
        self._sbar = None
        self._value = 0
        self._pagestep = 10
        self._vrectcolor = QtGui.QColor(0x00, 0x00, 0x55, 0x25)
        self._vrectbordercolor = self._vrectcolor.darker()
        self.sizePolicy().setControlType(QtGui.QSizePolicy.Slider)
        #self.sizePolicy().setHorizontalPolicy(0)
        #self.sizePolicy().setVerticalPolicy(QtGui.QSizePolicy.)
        self.setMinimumWidth(20)

    def clear(self):
        self._blocks = set()
        
    def addBlock(self, typ, alo, ahi):
        self._blocks.add((typ, alo, ahi))

    def setMaximum(self, m):
        self._maximum = m
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int)'), self._minimum, self._maximum)

    def setMinimum(self, m):
        self._minimum = m
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int)'), self._minimum, self._maximum)

    def setRange(self, m, M):
        self._minimum = m
        self._maximum = M
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int)'), self._minimum, self._maximum)
        
    def setValue(self, v):
        if v != self._value:
            self._value = v
            self.update()
            self.emit(SIGNAL('valueChanged(int)'), v)

    def setPageStep(self, v):
        if v != self._pagestep:
            self._pagestep = v
            self.update()
            self.emit(SIGNAL('pageStepChanged(int)'), v)

    def linkScrollBar(self, sb):
        """
        Make the block list displayer be linked to the scrollbar
        """
        self._sbar = sb
        self.setUpdatesEnabled(False)
        self.setMaximum(sb.maximum())
        self.setMinimum(sb.minimum())
        self.setPageStep(sb.pageStep())
        self.setValue(sb.value())        
        self.setUpdatesEnabled(True)
        self.connect(sb, SIGNAL('valueChanged(int)'), self.setValue)
        self.connect(sb, SIGNAL('rangeChanged(int, int)'), self.setRange)
        self.connect(self, SIGNAL('valueChanged(int)'), sb.setValue)
        self.connect(self, SIGNAL('rangeChanged(int, int)'), sb.setRange)
        self.connect(self, SIGNAL('pageStepChanged(int)'), sb.setPageStep)

    def syncPageStep(self):
        self.setPageStep(self._sbar.pageStep())
        
    def paintEvent(self, event):
        w = self.width() - 1
        h = self.height()
        p = QtGui.QPainter(self)
        p.scale(1.0, float(h)/(self._maximum - self._minimum + self._pagestep))
        p.setPen(Qt.NoPen)
        for typ, alo, ahi in self._blocks:
            p.save()
            p.setBrush(self.blockTypes[typ])
            p.drawRect(1, alo, w-1, ahi-alo)
            p.restore()

        p.save()
        p.setPen(self._vrectbordercolor)
        p.setBrush(self._vrectcolor)
        p.drawRect(0, self._value, w, self._pagestep)
        p.restore()

        
class BlockMatch(QtGui.QWidget):
    def __init__(self, *args):
        QtGui.QWidget.__init__(self, *args)
        self._blocks = []
        self._minimum = 0
        self._maximum = 100
        self._apos = 0
        self._bpos = 0
        self.blockTypes = {'+': QtGui.QColor(0xFF, 0x00, 0x00, 0x50),
                           '-': QtGui.QColor(0x00, 0xFF, 0x00, 0x50),
                           }
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        p = QtGui.QPainter(self)
        p.scale(1.0, float(h)/(self._maximum-self._minimum))
        p.setPen(Qt.NoPen)
        for typ, alo, ahi, blo, bhi in self._blocks:
            p.save()
            p.setBrush(self.blockTypes[typ])

            path = QtGui.QPainterPath()
            path.moveTo(0, alo)
            path.cubicTo(w/3.0, alo, 2*w/3.0, blo, w, blo)
            path.lineTo(w, bhi)
            path.cubicTo(2*w/3.0, bhi, w/3.0, ahi, 0, ahi)
            path.closeSubpath()
            p.drawPath(path)

            p.restore()

    def addBlock(self, typ, alo, ahi, blo=None, bhi=None):
        if bhi is None:
            bhi = ahi
        if blo is None:
            blo = alo
        self._blocks.append((typ, alo, ahi, blo, bhi))

    def setMaximum(self, m):
        self._maximum = m

    def setMinimum(self, m):
        self._minimum = m
    
if __name__ == '__main__':
    a = QtGui.QApplication([])
    f = QtGui.QFrame()
    l = QtGui.QHBoxLayout(f)
    
    w1 = BlockMatch()
    w1.setMaximum(1200)
    w1.addBlock('+', 12, 42)
    w1.addBlock('+', 55, 142)
    w1.addBlock('-', 200, 300)
    w1.addBlock('-', 330, 400, 450,460)
    l.addWidget(w1)

    w2 = BlockList()
    l.addWidget(w2)

    sb = QtGui.QScrollBar()
    l.addWidget(sb)

    w2.linkScrollBar(sb)

    w2.setRange(0, 1200)
    w2.setPageStep(100)
    w2.addBlock('+', 12, 42)
    w2.addBlock('+', 55, 142)
    w2.addBlock('-', 200, 300)

    print "sb=", sb.minimum(), sb.maximum(), sb.pageStep()
    
    f.show()
    a.exec_()
    
