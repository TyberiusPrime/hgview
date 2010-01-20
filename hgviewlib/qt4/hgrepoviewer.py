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
from hgviewlib.util import rootpath, find_repository
from hgviewlib.hggraph import diff as revdiff
from hgviewlib.decorators import timeit

from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgrepomodel import HgRepoListModel, HgFileListModel
from hgviewlib.qt4.hgfiledialog import FileViewer, FileDiffViewer
from hgviewlib.qt4.hgmanifestdialog import ManifestViewer
from hgviewlib.qt4.hgdialogmixin import HgDialogMixin
from hgviewlib.qt4.quickbar import FindInGraphlogQuickBar
from hgviewlib.qt4.helpviewer import HelpViewer

try:
    from mercurial.error import RepoError
except ImportError: # old API
    from mercurial.repo import RepoError

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL


class HgRepoViewer(QtGui.QMainWindow, HgDialogMixin):
    """hg repository viewer/browser application"""
    _uifile = 'hgqv.ui'
    def __init__(self, repo, fromhead=None):
        self.repo = repo
        self._closed_branch_supp = has_closed_branch_support(self.repo)

        # these are used to know where to go after a reload
        self._reload_rev = None
        self._reload_file = None

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
        connect(self.textview_status, SIGNAL('fileDisplayed'),
                self.file_displayed)
        self.setupBranchCombo()
        self.setupModels(fromhead)
        if fromhead:
            self.startrev_entry.setText(str(fromhead))
        self.setupRevisionTable()

        self._repodate = self._getrepomtime()
        self._watchrepotimer = self.startTimer(500)

    def timerEvent(self, event):
        if event.timerId() == self._watchrepotimer:
            mtime = self._getrepomtime()
            if mtime > self._repodate:
                self.statusBar().showMessage("Repository has been modified, "
                                             "reloading...", 2000)
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
        self.find_toolbar.attachHeaderView(self.textview_header)
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

        self.toolBar_treefilters.layout().setSpacing(3)
        self.branch_checkBox_action = self.toolBar_treefilters.addWidget(self.branch_checkBox)
        self.toolBar_treefilters.addSeparator()

        self.branch_label_action = self.toolBar_treefilters.addWidget(self.branch_label)
        self.branch_comboBox_action = self.toolBar_treefilters.addWidget(self.branch_comboBox)
        self.toolBar_treefilters.addSeparator()

        self.startrev_label = QtGui.QLabel("Start rev.")
        self.startrev_entry = QtGui.QLineEdit()
        self.startrev_follow = QtGui.QCheckBox("Follow")

        self.revscompl_model = QtGui.QStringListModel(['tip'])
        self.revcompleter = QtGui.QCompleter(self.revscompl_model, self)
        self.startrev_entry.setCompleter(self.revcompleter)

        connect(self.startrev_entry, SIGNAL('editingFinished()'),
                self.refreshRevisionTable)
        connect(self.startrev_entry, SIGNAL('returnPressed()'),
                self.refreshRevisionTable)
        connect(self.startrev_follow, SIGNAL('stateChanged(int)'),
                self.refreshRevisionTable)
        self.startrev_label_action = self.toolBar_treefilters.addWidget(self.startrev_label)
        self.startrev_entry_action = self.toolBar_treefilters.addWidget(self.startrev_entry)
        self.startrev_follow_action = self.toolBar_treefilters.addWidget(self.startrev_follow)

        self.toolBar_diff.addAction(self.actionDiffMode)
        self.toolBar_diff.addAction(self.actionAnnMode)
        self.toolBar_diff.addAction(self.actionNextDiff)
        self.toolBar_diff.addAction(self.actionPrevDiff)

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

        self.actionDiffMode = QtGui.QAction('Diff mode', self)
        self.actionDiffMode.setCheckable(True)
        connect(self.actionDiffMode, SIGNAL('toggled(bool)'),
                self.setMode)

        self.actionAnnMode = QtGui.QAction('Annotate', self)
        self.actionAnnMode.setCheckable(True)
        connect(self.actionAnnMode, SIGNAL('toggled(bool)'),
                self.textview_status.setAnnotate)

        self.actionHelp.setShortcut(Qt.Key_F1)
        self.actionHelp.setIcon(geticon('help'))
        connect(self.actionHelp, SIGNAL('triggered()'),
                self.on_help)
        
        # Next/Prev diff (in full file mode)
        self.actionNextDiff = QtGui.QAction(geticon('down'), 'Next diff', self)
        self.actionNextDiff.setShortcut('Alt+Down')
        self.actionPrevDiff = QtGui.QAction(geticon('up'), 'Previous diff', self)
        self.actionPrevDiff.setShortcut('Alt+Up')
        connect(self.actionNextDiff, SIGNAL('triggered()'),
                self.nextDiff)
        connect(self.actionPrevDiff, SIGNAL('triggered()'),
                self.prevDiff)
        self.actionDiffMode.setChecked(True)

        # Next/Prev file
        self.actionNextFile = QtGui.QAction('Next file', self)
        self.actionNextFile.setShortcut('Right')
        connect(self.actionNextFile, SIGNAL('triggered()'),
                self.tableView_filelist.nextFile)
        self.actionPrevFile = QtGui.QAction('Prev file', self)
        self.actionPrevFile.setShortcut('Left')
        connect(self.actionPrevFile, SIGNAL('triggered()'),
                self.tableView_filelist.prevFile)
        self.addAction(self.actionNextFile)
        self.addAction(self.actionPrevFile)
        self.disab_shortcuts.append(self.actionNextFile)
        self.disab_shortcuts.append(self.actionPrevFile)

        # Next/Prev rev
        self.actionNextRev = QtGui.QAction('Next revision', self)
        self.actionNextRev.setShortcut('Down')
        connect(self.actionNextRev, SIGNAL('triggered()'),
                self.tableView_revisions.nextRev)
        self.actionPrevRev = QtGui.QAction('Prev revision', self)
        self.actionPrevRev.setShortcut('Up')
        connect(self.actionPrevRev, SIGNAL('triggered()'),
                self.tableView_revisions.prevRev)
        self.addAction(self.actionNextRev)
        self.addAction(self.actionPrevRev)
        self.disab_shortcuts.append(self.actionNextRev)
        self.disab_shortcuts.append(self.actionPrevRev)

        # navigate in file viewer
        self.actionNextLine = QtGui.QAction('Next line', self)
        self.actionNextLine.setShortcut(Qt.SHIFT + Qt.Key_Down)
        connect(self.actionNextLine, SIGNAL('triggered()'),
                self.textview_status.nextLine)
        self.addAction(self.actionNextLine)
        self.actionPrevLine = QtGui.QAction('Prev line', self)
        self.actionPrevLine.setShortcut(Qt.SHIFT + Qt.Key_Up)
        connect(self.actionPrevLine, SIGNAL('triggered()'),
                self.textview_status.prevLine)
        self.addAction(self.actionPrevLine)
        self.actionNextCol = QtGui.QAction('Next column', self)
        self.actionNextCol.setShortcut(Qt.SHIFT + Qt.Key_Right)
        connect(self.actionNextCol, SIGNAL('triggered()'),
                self.textview_status.nextCol)
        self.addAction(self.actionNextCol)
        self.actionPrevCol = QtGui.QAction('Prev column', self)
        self.actionPrevCol.setShortcut(Qt.SHIFT + Qt.Key_Left)
        connect(self.actionPrevCol, SIGNAL('triggered()'),
                self.textview_status.prevCol)
        self.addAction(self.actionPrevCol)

        # Activate file (file diff navigator)
        self.actionActivateFile = QtGui.QAction('Activate file', self)
        self.actionActivateFile.setShortcuts([Qt.Key_Return, Qt.Key_Enter])
        def enterkeypressed():
            w = QtGui.QApplication.focusWidget()
            if not isinstance(w, QtGui.QLineEdit):
                self.tableView_filelist.fileActivated(self.tableView_filelist.currentIndex(),)
            else:
                w.emit(SIGNAL('editingFinished()'))
        connect(self.actionActivateFile, SIGNAL('triggered()'),
                enterkeypressed)

        self.actionActivateFileAlt = QtGui.QAction('Activate alt. file', self)
        self.actionActivateFileAlt.setShortcuts([Qt.ALT+Qt.Key_Return, Qt.ALT+Qt.Key_Enter])
        connect(self.actionActivateFileAlt, SIGNAL('triggered()'),
                lambda self=self:
                self.tableView_filelist.fileActivated(self.tableView_filelist.currentIndex(),
                                                      alternate=True))
        self.actionActivateRev = QtGui.QAction('Activate rev.', self)
        self.actionActivateRev.setShortcuts([Qt.SHIFT+Qt.Key_Return, Qt.SHIFT+Qt.Key_Enter])
        connect(self.actionActivateRev, SIGNAL('triggered()'),
                self.revision_activated)
        self.addAction(self.actionActivateFile)
        self.addAction(self.actionActivateFileAlt)
        self.addAction(self.actionActivateRev)
        self.disab_shortcuts.append(self.actionActivateFile)
        self.disab_shortcuts.append(self.actionActivateRev)

        self.actionStartAtRev = QtGui.QAction('Start at rev.', self)
        self.actionStartAtRev.setShortcuts([Qt.Key_Backspace,])
        connect(self.actionStartAtRev, SIGNAL('triggered()'),
                self.startAtCurrentRev)
        self.addAction(self.actionStartAtRev)

        self.actionClearStartAtRev = QtGui.QAction('Clear start at rev.', self)
        self.actionClearStartAtRev.setShortcuts([Qt.SHIFT + Qt.Key_Backspace,])
        connect(self.actionClearStartAtRev, SIGNAL('triggered()'),
                self.clearStartAtRev)
        self.addAction(self.actionClearStartAtRev)

    def startAtCurrentRev(self):
        crev = self.tableView_revisions.current_rev
        if crev:
            self.startrev_entry.setText(str(crev))
            self.refreshRevisionTable()

    def clearStartAtRev(self):
        self.startrev_entry.setText("")
        self._reload_rev = self.tableView_revisions.current_rev
        self._reload_file = self.tableView_filelist.currentFile()
        self.refreshRevisionTable()

    def setMode(self, mode):
        self.textview_status.setMode(mode)
        self.actionAnnMode.setEnabled(not mode)
        self.actionNextDiff.setEnabled(not mode)
        self.actionPrevDiff.setEnabled(not mode)

    def nextDiff(self):
        notlast = self.textview_status.nextDiff()
        self.actionNextDiff.setEnabled(self.textview_status.fileMode() and notlast and self.textview_status.nDiffs())
        self.actionPrevDiff.setEnabled(self.textview_status.fileMode() and self.textview_status.nDiffs())

    def prevDiff(self):
        notfirst = self.textview_status.prevDiff()
        self.actionPrevDiff.setEnabled(self.textview_status.fileMode() and notfirst and self.textview_status.nDiffs())
        self.actionNextDiff.setEnabled(self.textview_status.fileMode() and self.textview_status.nDiffs())

    def load_config(self):
        cfg = HgDialogMixin.load_config(self)
        self.hidefinddelay = cfg.getHideFindDelay()

    def create_models(self, fromhead=None):
        self.repomodel = HgRepoListModel(self.repo, fromhead=fromhead)
        connect(self.repomodel, SIGNAL('filled'),
                self.on_filled)
        connect(self.repomodel, SIGNAL('showMessage'),
                self.statusBar().showMessage,
                Qt.QueuedConnection)

        self.filelistmodel = HgFileListModel(self.repo)

    def setupModels(self, fromhead=None):
        self.create_models(fromhead)
        self.tableView_revisions.setModel(self.repomodel)
        self.tableView_filelist.setModel(self.filelistmodel)
        self.textview_status.setModel(self.repomodel)
        self.find_toolbar.setModel(self.repomodel)

        filetable = self.tableView_filelist
        connect(filetable, SIGNAL('fileSelected'),
                self.textview_status.displayFile)
        connect(self.textview_status, SIGNAL('revForDiffChanged'),
                self.textview_header.setDiffRevision)

    def setupRevisionTable(self):
        view = self.tableView_revisions
        view.installEventFilter(self)
        connect(view, SIGNAL('revisionSelected'), self.revision_selected)
        connect(view, SIGNAL('revisionActivated'), self.revision_activated)
        connect(self.textview_header, SIGNAL('revisionSelected'), view.goto)
        connect(self.textview_header, SIGNAL('parentRevisionSelected'), self.textview_status.displayDiff)
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

    def on_filled(self):
        # called the first time the model is filled, so we select
        # the first available revision
        tv = self.tableView_revisions
        if self._reload_rev is not None:
            torev = self._reload_rev
            self._reload_rev = None
            try:
                tv.goto(torev)
                self.tableView_filelist.selectFile(self._reload_file)
                self._reload_file = None
                return
            except IndexError:
                pass
        tv.setCurrentIndex(tv.model().index(0, 0))

    def revision_activated(self, rev=None):
        """
        Callback called when a revision is double-clicked in the revisions table
        """
        if rev is None:
            rev = self.tableView_revisions.current_rev
        self._manifestdlg = ManifestViewer(self.repo, rev)
        self._manifestdlg.show()

    def file_displayed(self, filename):
        self.actionPrevDiff.setEnabled(False)
        connect(self.textview_status, SIGNAL('filled'),
                lambda self=self: self.actionNextDiff.setEnabled(self.textview_status.fileMode() \
                                                                 and self.textview_status.nDiffs()))

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

    def goto(self, rev):
        if len(self.tableView_revisions.model().graph):
            self.tableView_revisions.goto(rev)
        else:
            # store rev to show once it's available (when graph
            # filling is still running)
            self._reload_rev = rev
            
    def _getrepomtime(self):
        """Return the last modification time for the repo"""
        watchedfiles = [(self.repo.root, ".hg", "store", "00changelog.i"),
                        (self.repo.root, ".hg", "dirstate")]
        watchedfiles = [os.path.join(*wf) for wf in watchedfiles]
        mtime = [os.path.getmtime(wf) for wf in watchedfiles \
                 if os.path.isfile(wf)]
        if mtime:
            return max(mtime)
        # humm, directory has probably been deleted, exiting...
        self.close()

    def reload(self):
        """Reload the repository"""
        self._reload_rev = self.tableView_revisions.current_rev
        self._reload_file = self.tableView_filelist.currentFile()
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self._repodate = self._getrepomtime()
        self.setupBranchCombo()
        self.setupModels()
        self.refreshRevisionTable()

    #@timeit
    def refreshRevisionTable(self, *args):
        """Starts the process of filling the HgModel"""
        branch = self.branch_comboBox.currentText()
        branch = str(branch)
        startrev = str(self.startrev_entry.text()).strip()
        if not startrev:
            startrev = None

        if self.sender() is self.startrev_follow and startrev is None:
            return
            
        startrev = self.repo.changectx(startrev).rev()
        follow = self.startrev_follow.checkState() == Qt.Checked
        self.revscompl_model.setStringList(self.repo.tags().keys())

        self.repomodel.setRepo(self.repo, branch=branch, fromhead=startrev,
                               follow=follow)

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

    def on_help(self, *args):
        w = HelpViewer(self.repo, self)
        w.show()
        w.raise_()
        w.activateWindow()
        

def main():
    from optparse import OptionParser
    usage = '''%prog [options] [filename]

    Starts a visual hg repository navigator.

    - With no options, starts the main repository navigator.

    - If a filename is given, starts in filelog diff mode (or in
      filelog navigation mode if -n option is set).

    - With -r option, starts in manifest viewer mode for given
      revision.
    '''
    
    parser = OptionParser(usage)
    parser.add_option('-R', '--repository', dest='repo',
                      help='location of the repository to explore')
    parser.add_option('-r', '--rev', dest='rev', default=None,
                      help='start in manifest navigation mode at rev R')
    parser.add_option('-n', '--navigate', dest='navigate', default=False,
                      action="store_true",
                      help='(with filename) start in navigation mode')

    opts, args = parser.parse_args()

    if opts.navigate and len(args) != 1:
        parser.error("You must provide a filename to start in navigate mode")

    if len(args) > 1:
        parser.error("Provide at most one file name")

    dir_ = None
    if opts.repo:
        dir_ = opts.repo
    else:
        dir_ = os.getcwd()
    dir_ = find_repository(dir_)

    try:
        u = ui.ui()
        repo = hg.repository(u, dir_)
    except:
        parser.error("You are not in a repo, are you?")

    # make Ctrl+C works
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtGui.QApplication(sys.argv)
    from hgviewlib.qt4 import setup_font_substitutions
    setup_font_substitutions()
    
    if len(args) == 1:
        filename = rootpath(repo, opts.rev, args[0])
        if filename is None:
            parser.error("%s is not a tracked file" % args[0])
        
        # should be a filename of a file managed in the repo
        if opts.navigate:
            mainwindow = FileViewer(repo, filename)
        else:
            mainwindow = FileDiffViewer(repo, filename)
    else:
        rev = opts.rev
        if rev is not None:
            try:
                repo.changectx(rev)
            except RepoError, e:
                parser.error("Cannot find revision %s" % rev)
            else:
                mainwindow = ManifestViewer(repo, rev)                
        else:
            mainwindow = HgRepoViewer(repo)

    mainwindow.show()    
    sys.exit(app.exec_())


if __name__ == "__main__":
    # remove current dir from sys.path
    while sys.path.count('.'):
        sys.path.remove('.')
        print 'removed'
    main()
