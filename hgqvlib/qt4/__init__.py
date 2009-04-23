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
import hgqv_rc

from PyQt4 import QtGui, uic
from hgqvlib.config import HgConfig

class HgDialogMixin(object):
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
        
    def load_config(self):
        cfg = HgConfig(self.repo.ui)
        fontstr = cfg.getFont()
        font = QtGui.QFont()
        try:
            if not font.fromString(fontstr):
                raise Exception
        except:
            print "bad font name '%s'"%fontstr
            font.setFamily("Monospace")
            font.setFixedPitch(True)
            font.setPointSize(10)
        self.font = font

        self.rowheight = cfg.getRowHeight()
        self.users, self.aliases = cfg.getUsers()
        return cfg
