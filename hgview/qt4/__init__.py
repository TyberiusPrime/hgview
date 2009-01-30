#
# make sur the Qt rc files are converted into python modules, then load them
# this must be done BEFORE other hgview qt4 modules are loaded.
import os
import os.path as osp

curdir = osp.dirname(__file__)
pyfile = osp.join(curdir, "hgview_rc.py")
rcfile = osp.join(curdir, "hgview.qrc")
if not os.path.isfile(pyfile) or osp.getmtime(pyfile) < osp.getmtime(rcfile):
    os.system('pyrcc4 %s -o %s' % (rcfile, pyfile))
import hgview_rc
