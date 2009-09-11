# -*- coding: iso-8859-1 -*-
#!/usr/bin/env python
# main.py - qt4-based hg rev log browser
#
# Copyright (C) 2007-2009 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Main Qt4 application for hgview
"""
import sys, os
import re

from PyQt4 import QtCore, QtGui, Qsci

from mercurial import ui, hg
from mercurial import util

from hgviewlib.util import tounicode, has_closed_branch_support
from hgviewlib.hggraph import diff as revdiff
from hgviewlib.decorators import timeit

from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgrepomodel import HgRepoListModel, HgFileListModel
from hgviewlib.qt4.hgfileviewer import ManifestViewer
from hgviewlib.qt4.hgdialogmixin import HgDialogMixin
from hgviewlib.qt4.quickbar import FindInGraphlogQuickBar

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL


class HgRepoViewer(QtGui.QMainWindow, HgDialogMixin):
    """hg repository viewer/browser application"""
    _uifile = 'hgqv.ui'
    def __init__(self, repo, filerex = None):
        self.repo = repo
        self._closed_branch_supp = has_closed_branch_support(self.repo)
        
        QtGui.QMainWindow.__init__(self)
        HgDialogMixin.__init__(self)

        self.setWindowTitle('hgview: %s' % os.path.abspath(self.repo.root))
        self.menubar.hide()

        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)

        self.createActions()
        self.createToolbars()

        self.textview_status.setFont(self._font)
        connect(self.textview_status, SIGNAL('showMessage'),
                self.statusBar().showMessage)
        connect(self.tableView_revisions, SIGNAL('showMessage'),
                self.statusBar().showMessage)
                
        # setup tables and views
        self.setupHeaderTextview()
        self.tableView_filelist.setFocusPolicy(QtCore.Qt.NoFocus)
        self.textview_header.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setupBranchCombo()
        self.setupModels()

        self.setupRevisionTable()

        self._repodate = self._getrepomtime()
        self._watchrepotimer = self.startTimer(500)

    def timerEvent(self, event):
        if event.timerId() == self._watchrepotimer:
            mtime = self._getrepomtime()
            if mtime > self._repodate:
                self.reload()
                
    def setupBranchCombo(self, *args):
        allbranches = sorted(self.repo.branchtags().items())
        if self._closed_branch_supp:
            openbr = []
            for branch, brnode in allbranches:
                openbr.extend(self.repo.branchheads(branch, closed=False))
            clbranches = [br for br, node in allbranches if node not in openbr]
            branches = [br for br, node in allbranches if node in openbr]
            self.branch_checkBox_action.setVisible(len(clbranches)>0)
            if self.branch_checkBox.isChecked():
                branches = branches + clbranches
        else:
            self.branch_checkBox_action.setVisible(False)
            branches = [br for br, node in allbranches] # open branches
            
        if len(branches) == 1:
            self.branch_label_action.setVisible(False)
            self.branch_comboBox_action.setVisible(False)
        else:
            self.branchesmodel = QtGui.QStringListModel([''] + branches)
            self.branch_comboBox.setModel(self.branchesmodel)
            self.branch_label_action.setVisible(True)
            self.branch_label_action.setEnabled(True)
            self.branch_comboBox_action.setVisible(True)
            self.branch_comboBox_action.setEnabled(True)

    def createToolbars(self):
        self.find_toolbar = FindInGraphlogQuickBar(self)
        self.find_toolbar.attachFileView(self.textview_status)
        connect(self.find_toolbar, SIGNAL('revisionSelected'),
                self.tableView_revisions.goto)
        connect(self.find_toolbar, SIGNAL('fileSelected'),
                self.tableView_filelist.selectFile)
        connect(self.find_toolbar, SIGNAL('showMessage'),
                self.statusBar().showMessage,
                Qt.QueuedConnection)
                
        self.attachQuickBar(self.find_toolbar)

        self.toolBar_edit.addAction(self.tableView_revisions._actions['back'])
        self.toolBar_edit.addAction(self.tableView_revisions._actions['forward'])

        self.branch_label = QtGui.QLabel("Branch")
        self.branch_comboBox = QtGui.QComboBox()
        self.branch_checkBox = QtGui.QCheckBox("Display closed branches")
        connect(self.branch_comboBox, SIGNAL('activated(const QString &)'),
                self.refreshRevisionTable)
        connect(self.branch_checkBox, SIGNAL('toggled(bool)'),
                self.setupBranchCombo)
        
        self.branch_checkBox_action = self.toolBar_treefilters.addWidget(self.branch_checkBox)
        self.toolBar_treefilters.addSeparator()
        self.branch_label_action = self.toolBar_treefilters.addWidget(self.branch_label)
        self.branch_comboBox_action = self.toolBar_treefilters.addWidget(self.branch_comboBox)

    def createActions(self):
        # main window actions (from .ui file)
        connect(self.actionRefresh, SIGNAL('triggered()'),
                self.reload)
        connect(self.actionAbout, SIGNAL('triggered()'),
                self.on_about)
        connect(self.actionQuit, SIGNAL('triggered()'),
                self.close)
        self.actionQuit.setIcon(geticon('quit'))
        self.actionRefresh.setIcon(geticon('reload'))

    def load_config(self):
        cfg = HgDialogMixin.load_config(self)
        self.hidefinddelay = cfg.getHideFindDelay()

    def create_models(self):
        self.repomodel = HgRepoListModel(self.repo)
        connect(self.repomodel, SIGNAL('filled'),
                self.on_filled)
        connect(self.repomodel, SIGNAL('showMessage'),
                self.statusBar().showMessage,
                Qt.QueuedConnection)                

        self.filelistmodel = HgFileListModel(self.repo)
        
    def setupModels(self):
        self.create_models()
        self.tableView_revisions.setModel(self.repomodel)
        self.tableView_filelist.setModel(self.filelistmodel)
        self.textview_status.setModel(self.repomodel)
        self.find_toolbar.setModel(self.repomodel)

        filetable = self.tableView_filelist
        connect(filetable, SIGNAL('fileSelected'),
                self.textview_status.displayFile)

    def setupRevisionTable(self):
        view = self.tableView_revisions
        view.installEventFilter(self)
        connect(view, SIGNAL('revisionSelected'), self.revision_selected)
        connect(view, SIGNAL('revisionActivated'), self.revision_activated)
        connect(self.textview_header, SIGNAL('revisionSelected'), view.goto)
        self.attachQuickBar(view.goto_toolbar)

    def _setup_table(self, table):
        table.setTabKeyNavigation(False)
        table.verticalHeader().setDefaultSectionSize(self.rowheight)
        table.setShowGrid(False)
        table.verticalHeader().hide()
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)

    def setupHeaderTextview(self):
        self.header_diff_format = QtGui.QTextCharFormat()
        self.header_diff_format.setFont(self._font)
        self.header_diff_format.setFontWeight(bold)
        self.header_diff_format.setForeground(Qt.black)
        self.header_diff_format.setBackground(Qt.gray)

    def eventFilter(self, watched, event):
        if watched == self.tableView_revisions:
            if event.type() == event.KeyPress:
                model = self.filelistmodel
                table = self.tableView_filelist
                row = table.currentIndex().row()
                if event.key() == Qt.Key_Left:
                    table.setCurrentIndex(model.index(max(row-1, 0), 0))
                    return True
                elif event.key() == Qt.Key_Right:
                    table.setCurrentIndex(model.index(min(row+1, model.rowCount()-1), 0))
                    return True
                elif event.key() in [Qt.Key_Return, Qt.Key_Enter]:
                    table.fileActivated(table.currentIndex(),
                                        alternate=event.modifiers() & Qt.AltModifier)
                    return True
        return QtGui.QMainWindow.eventFilter(self, watched, event)

    def on_filled(self):
        # called the first time the model is filled, so we select
        # the first available revision
        tv = self.tableView_revisions
        tv.setCurrentIndex(tv.model().index(0, 0))

    def revision_activated(self, rev):
        """
        Callback called when a revision is double-clicked in the revisions table
        """
        self._manifestdlg = ManifestViewer(self.repo, rev)
        self._manifestdlg.show()

    def revision_selected(self, rev):
        """
        Callback called when a revision is selected in the revisions table
        """
        if self.repomodel.graph:
            ctx = self.repomodel.repo.changectx(rev)
            self.textview_status.setContext(ctx)
            self.textview_header.displayRevision(ctx)
            self.filelistmodel.setSelectedRev(ctx)
            if len(self.filelistmodel):
                self.tableView_filelist.selectRow(0)

    def _getrepomtime(self):
        """Return the last modification time for the repo""" 
        dirstate = os.path.join(self.repo.root, ".hg", "dirstate")
        return os.path.getmtime(dirstate)
        
    def reload(self):
        """Reload the repository"""
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self._repodate = self._getrepomtime()
        self.setupBranchCombo()
        self.setupModels()
        self.refreshRevisionTable()

    #@timeit
    def refreshRevisionTable(self, branch=None):
        """Starts the process of filling the HgModel"""
        if branch is None:
            branch = self.branch_comboBox.currentText()
        branch = str(branch)
        self.repomodel.setRepo(self.repo, branch=branch)
        self.tableView_revisions.setCurrentIndex(self.tableView_revisions.model().index(0, 0))

    def on_about(self, *args):
        """ Display about dialog """
        from hgviewlib.__pkginfo__ import modname, version, short_desc, long_desc
        try:
            from mercurial.version import get_version
            hgversion = get_version()
        except:
            from mercurial.__version__ import version as hgversion

        msg = "<h2>About %(appname)s %(version)s</h2> (using hg %(hgversion)s)" % \
              {"appname": modname, "version": version, "hgversion": hgversion}
        msg += "<p><i>%s</i></p>" % short_desc.capitalize()
        msg += "<p>%s</p>" % long_desc
        QtGui.QMessageBox.about(self, "About %s" % modname, msg)

def find_repository(path):
    """returns <path>'s mercurial repository

    None if <path> is not under hg control
    """
    path = os.path.abspath(path)
    while not os.path.isdir(os.path.join(path, ".hg")):
        oldpath = path
        path = os.path.dirname(path)
        if path == oldpath:
            return None
    return path

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-R', '--repository', dest='repo',
                       help='location of the repository to explore')
    parser.add_option('-f', '--file', dest='filename',
                       help='filter revisions which touch FILE', metavar="FILE")
    parser.add_option('-g', '--regexp', dest='filerex',
                       help='filter revisions which touch FILE matching regexp')

    opt, args = parser.parse_args()
    dir_ = None
    if opt.repo:
        dir_ = opt.repo
    else:
        dir_ = os.getcwd()
    dir_ = find_repository(dir_)
    filerex = None
    if opt.filename:
        filerex = "^" + re.escape(opt.filename) + "$"
    elif opt.filerex:
        filerex = opt.filerex

    try:
        u = ui.ui()
        repo = hg.repository(u, dir_)
    except:
        print "You are not in a repo, are you?"
        sys.exit(1)

    # make Ctrl+C works
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtGui.QApplication(sys.argv)
    mainwindow = HgRepoViewer(repo, filerex)
    mainwindow.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # remove current dir from sys.path
    while sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
