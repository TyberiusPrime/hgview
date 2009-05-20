#
# make sur the Qt rc files are converted into python modules, then load them
# this must be done BEFORE other hgqv qt4 modules are loaded.
import os
import os.path as osp
import sys

# automatically load resource module, creating it on the fly if
# required
curdir = osp.dirname(__file__)
pyfile = osp.join(curdir, "hgqv_rc.py")
rcfile = osp.join(curdir, "hgqv.qrc")
if not osp.isfile(pyfile) or osp.isfile(rcfile) and osp.getmtime(pyfile) < osp.getmtime(rcfile):
    if os.system('pyrcc4 %s -o %s' % (rcfile, pyfile)):
        print "ERROR: Cannot convert the resource file '%s' into a python module."
        print "Please check the PyQt 'pyrcc4' tool is installed, or do it by hand running:"
        print "pyrcc4 %s -o %s" % (rcfile, pyfile)

# load icons from resource and store them in a dict, no matter their
# extension (.svg or .png)
from PyQt4 import QtCore
from PyQt4 import QtGui, uic
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL
Qt = QtCore.Qt
import hgqv_rc

_icons = {}
def _load_icons():
    d = QtCore.QDir(':/icons')
    for icn in d.entryList():
        name, ext = osp.splitext(str(icn))
        if name not in _icons or ext == ".svg":
            _icons[name] = QtGui.QIcon(':/icons/%s' % icn)

def icon(name):
    """
    Return a QIcon for the resource named 'name.(svg|png)' (the given
    'name' parameter must *not* provide the extension).
    """
    if not _icons:
        _load_icons()
    return _icons.get(name)

from hgqvlib.config import HgConfig

class HgDialogMixin(object):
    """
    Mixin for QDialogs defined from a .ui file, wich automates the
    setup of the UI from the ui file, and the loading of user
    preferences.
    The main class must define a '_ui_file' class attribute.
    """
    def __init__(self):
        # self.repo must be defined in actual class before calling __init__
        assert self.repo is not None
        self.load_config()
        self.load_ui()
        
    def load_ui(self):
        # load qt designer ui file
        for _path in [osp.dirname(__file__),
                      osp.join(sys.exec_prefix, 'share/hgqv'),
                      osp.expanduser('~/share/hgqv'),
                      osp.join(osp.dirname(__file__), "../../../../../share/hgqv"),
                      ]:
            ui_file = osp.join(_path, self._uifile)
            if osp.isfile(ui_file):
                break
        else:
            raise ValueError("Unable to find hgqv.ui\n"
                             "Check your installation.")
        uifile = osp.join(osp.dirname(__file__), ui_file)
        self.ui = uic.loadUi(uifile, self)

        # we explicitely create a QShortcut so we can disable it
        # when a "helper context toolbar" is activated (which can be
        # closed hitting the Esc shortcut)
        self.esc_shortcut = QtGui.QShortcut(self)
        self.esc_shortcut.setKey(Qt.Key_Escape)
        connect(self.esc_shortcut, SIGNAL('activated()'),
                self.close)
        self._quickbars = []

    def attachQuickBar(self, qbar):
        qbar.setParent(self)
        self._quickbars.append(qbar)
        connect(qbar, SIGNAL('escShortcutDisabled(bool)'),
                self.esc_shortcut.setEnabled)
        self.addToolBar(Qt.BottomToolBarArea, qbar)
        connect(qbar, SIGNAL('visible'),
                self.ensureOneQuickBar)

    def ensureOneQuickBar(self):
        tb = self.sender()
        for w in self._quickbars:
            if w is not tb:
                w.hide()
        
    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        fontstr = cfg.getFont()
        font = QtGui.QFont()
        try:
            if not font.fromString(fontstr):
                raise Exception
        except:
            print "bad font name '%s'" % fontstr
            font.setFamily("Monospace")
            font.setFixedPitch(True)
            font.setPointSize(10)
        self.font = font

        self.rowheight = cfg.getRowHeight()
        self.users, self.aliases = cfg.getUsers()
        return cfg

    def accept(self):
        self.close()
    def reject(self):
        self.close()

        
