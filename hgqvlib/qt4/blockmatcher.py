# -*- coding: utf-8 -*-
import sys, os

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt, SIGNAL

class BlockList(QtGui.QWidget):
    """
    A simple widget to be 'linked' to the scrollbar of a diff text
    view.

    It represents diff blocks with coloured rectangles, showing
    currently viewed area by a semi-transparant rectangle sliding
    above them.
    """
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
        
class BlockMatch(BlockList):
    """
    A simpe widget to be linked to 2 file views (text areas),
    displaying 2 versions of a same file (diff).

    It will show graphically matching diff blocks between the 2 text
    areas.
    """
    def __init__(self, *args):
        QtGui.QWidget.__init__(self, *args)
        self._blocks = set()
        self._minimum = {'left': 0, 'right': 0}
        self._maximum = {'left': 100, 'right': 100}
        self.blockTypes = {'+': QtGui.QColor(0xA0, 0xFF, 0xB0, ),#0xa5),
                           '-': QtGui.QColor(0xFF, 0xA0, 0xA0, ),#0xa5),
                           'x': QtGui.QColor(0xA0, 0xA0, 0xFF, ),#0xa5),
                           }
        self._sbar = {}
        self._value =  {'left': 0, 'right': 0}
        self._pagestep =  {'left': 10, 'right': 10}
        self._vrectcolor = QtGui.QColor(0x00, 0x00, 0x55, 0x25)
        self._vrectbordercolor = self._vrectcolor.darker()
        self.sizePolicy().setControlType(QtGui.QSizePolicy.Slider)
        self.setMinimumWidth(20)

    def addBlock(self, typ, alo, ahi, blo=None, bhi=None):
        if bhi is None:
            bhi = ahi
        if blo is None:
            blo = alo
        self._blocks.add((typ, alo, ahi, blo, bhi))
        
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        p = QtGui.QPainter(self)
        p.setRenderHint(p.Antialiasing)
        
        ps_l = float(self._pagestep['left'])
        ps_r = float(self._pagestep['right'])
        v_l = self._value['left']
        v_r = self._value['right']

        # we do integer divisions here cause the pagestep is the
        # integer number of fully displayed text lines
        scalel = self._sbar['left'].height()//ps_l
        scaler = self._sbar['right'].height()//ps_r
        
        ml = v_l
        Ml = v_l + ps_l
        mr = v_r
        Mr = v_r + ps_r
        
        p.setPen(Qt.NoPen)
        for typ, alo, ahi, blo, bhi in self._blocks:
            if not (ml<=alo<=Ml or ml<=ahi<=Ml or mr<=blo<=Mr or mr<=bhi<=Mr):
                continue
            p.save()
            p.setBrush(self.blockTypes[typ])

            path = QtGui.QPainterPath()
            path.moveTo(0, scalel * (alo - ml))
            path.cubicTo(w/3.0, scalel * (alo - ml),
                         2*w/3.0, scaler * (blo - mr),
                         w, scaler * (blo - mr))
            path.lineTo(w, scaler * (bhi - mr) + 2)
            path.cubicTo(2*w/3.0, scaler * (bhi - mr) + 2,
                         w/3.0, scalel * (ahi - ml) + 2,
                         0, scalel * (ahi - ml) + 2)
            path.closeSubpath()
            p.drawPath(path)

            p.restore()

    def setMaximum(self, m, side):
        self._maximum[side] = m
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int, const QString &)'), self._minimum[side], self._maximum[side], side)

    def setMinimum(self, m, side):
        self._minimum[side] = m
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int, const QString &)'), self._minimum[side], self._maximum[side], side)

    def setRange(self, m, M, side=None):
        if side is None:
            if self.sender() == self._sbar['left']:
                side = 'left'
            else:
                side = 'right'
        self._minimum[side] = m
        self._maximum[side] = M
        self.update()
        self.emit(SIGNAL('rangeChanged(int, int, const QString &)'), self._minimum[side], self._maximum[side], side)
        
    def setValue(self, v, side=None):
        if side is None:
            if self.sender() == self._sbar['left']:
                side = 'left'
            else:
                side = 'right'
        if v != self._value[side]:
            self._value[side] = v
            self.update()
            self.emit(SIGNAL('valueChanged(int, const QString &)'), v, side)

    def setPageStep(self, v, side):
        if v != self._pagestep[side]:
            self._pagestep[side] = v
            self.update()
            self.emit(SIGNAL('pageStepChanged(int, const QString &)'), v, side)

    def syncPageStep(self):
        for side in ['left', 'right']:
            self.setPageStep(self._sbar[side].pageStep(), side)

    def resizeEvent(self, event):
        self.syncPageStep()
        
    def linkScrollBar(self, sb, side):
        """
        Make the block list displayer be linked to the scrollbar
        """
        if self._sbar is None:
            self._sbar = {}
        self._sbar[side] = sb
        self.setUpdatesEnabled(False)
        self.setMaximum(sb.maximum(), side)
        self.setMinimum(sb.minimum(), side)
        self.setPageStep(sb.pageStep(), side)
        self.setValue(sb.value(), side)
        self.setUpdatesEnabled(True)
        self.connect(sb, SIGNAL('valueChanged(int)'), self.setValue)
        self.connect(sb, SIGNAL('rangeChanged(int, int)'), self.setRange)

        self.connect(self, SIGNAL('valueChanged(int, const QString &)'), lambda v, s: side==s and sb.setValue(v))
        self.connect(self, SIGNAL('rangeChanged(int, int, const QString )'), lambda v1, v2, s: side==s and sb.setRange(v1, v2))
        self.connect(self, SIGNAL('pageStepChanged(int, const QString )'), lambda v, s: side==s and sb.setPageStep(v))
    
if __name__ == '__main__':
    a = QtGui.QApplication([])
    f = QtGui.QFrame()
    l = QtGui.QHBoxLayout(f)

    sb1 = QtGui.QScrollBar()
    sb2 = QtGui.QScrollBar()
    
    w0 = BlockList()
    w0.addBlock('-', 200, 300)
    w0.addBlock('-', 450, 460)
    w0.addBlock('x', 500, 501)
    w0.linkScrollBar(sb1)

    w1 = BlockMatch()
    w1.addBlock('+', 12, 42)
    w1.addBlock('+', 55, 142)
    w1.addBlock('-', 200, 300)
    w1.addBlock('-', 330, 400, 450, 460)
    w1.addBlock('x', 420, 450, 500, 501)
    w1.linkScrollBar(sb1, 'left')
    w1.linkScrollBar(sb2, 'right')

    w2 = BlockList()
    w2.addBlock('+', 12, 42)
    w2.addBlock('+', 55, 142)
    w2.addBlock('x', 420, 450)
    w2.linkScrollBar(sb2)

    l.addWidget(sb1)
    l.addWidget(w0)
    l.addWidget(w1)
    l.addWidget(w2)
    l.addWidget(sb2)

    w0.setRange(0, 1200)
    w0.setPageStep(100)
    w1.setRange(0, 1200, 'left')
    w1.setRange(0, 1200, 'right')
    w1.setPageStep(100, 'left')
    w1.setPageStep(100, 'right')
    w2.setRange(0, 1200)
    w2.setPageStep(100)

    print "sb1=", sb1.minimum(), sb1.maximum(), sb1.pageStep()
    print "sb2=", sb2.minimum(), sb2.maximum(), sb2.pageStep()
    
    f.show()
    a.exec_()
    
