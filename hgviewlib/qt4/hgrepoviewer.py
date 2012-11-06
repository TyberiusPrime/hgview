# -*- coding: iso-8859-1 -*-
# main.py - qt4-based hg rev log browser
#
# Copyright (C) 2007-2010 Logilab. All rights reserved.
#
# This software may be used and distributed according to the terms
# of the GNU General Public License, incorporated herein by reference.
"""
Main Qt4 application for hgview
"""
import sys, os
import re
import errno

from PyQt4 import QtCore, QtGui, Qsci

from mercurial import ui, hg
from mercurial import util
from mercurial.error import RepoError


from hgviewlib.application import HgRepoViewer as _HgRepoViewer
from hgviewlib.util import tounicode, find_repository, rootpath
from hgviewlib.hggraph import diff as revdiff
from hgviewlib.decorators import timeit
from hgviewlib.config import HgConfig

from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgrepomodel import HgRepoListModel, HgFileListModel
from hgviewlib.qt4.hgfiledialog import FileViewer, FileDiffViewer
from hgviewlib.qt4.hgmanifestdialog import ManifestViewer
from hgviewlib.qt4.hgdialogmixin import HgDialogMixin
from hgviewlib.qt4.quickbar import FindInGraphlogQuickBar
from hgviewlib.qt4.helpviewer import HgviewHelpViewer

from mercurial.error import RepoError

Qt = QtCore.Qt
bold = QtGui.QFont.Bold
connect = QtCore.QObject.connect
SIGNAL = QtCore.SIGNAL


class HgRepoViewer(QtGui.QMainWindow, HgDialogMixin, _HgRepoViewer):
    """hg repository viewer/browser application"""
    _uifile = 'hgqv.ui'
    def __init__(self, repo, fromhead=None):
        self.repo = repo
        self.cfg = HgConfig(repo.ui)

        # these are used to know where to go after a reload
        self._reload_rev = None
        self._reload_file = None
        QtGui.QApplication.setStyle(QtGui.QStyleFactory.create('Cleanlooks'))
        QtGui.QMainWindow.__init__(self)
        if not self.repo.root:
            repo = self.ask_repository()
            if repo:
                self.repo = repo
        HgDialogMixin.__init__(self)

        self.setWindowTitle('hgview: %s' % os.path.abspath(str(self.repo.root)))
        self.menubar.hide()

        self.splitter_2.setStretchFactor(0, 2)
        self.splitter_2.setStretchFactor(1, 1)

        # hide bottom at startup
        self.frame_maincontent.setVisible(self.cfg.getContentAtStartUp())

        self.createActions()
        self.createToolbars()

        self.textview_status.setFont(self._font)
        connect(self.textview_status, SIGNAL('showMessage'),
                self.statusBar().showMessage)
        connect(self.tableView_revisions, SIGNAL('showMessage'),
                self.statusBar().showMessage)

        # setup tables and views
        if self.repo.root is not None:

            self.setupHeaderTextview()
            self.setupBranchCombo()
            self.setupModels(fromhead)
 
        if fromhead:
            self.startrev_entry.setText(str(fromhead))
        self.setupRevisionTable()

        if self.repo.root is not None:
            self._repodate = self._getrepomtime()
            self._watchrepotimer = self.startTimer(500)

    def timerEvent(self, event):
        if event.timerId() == self._watchrepotimer:
            mtime = self._getrepomtime()
            if mtime > self._repodate:
                self.statusBar().showMessage("Repository has been modified, "
                                             "reloading...", 2000)

                self.reload()

    def setupBranchComboAndReload(self, *args):
        self.setupBranchCombo()
        self.reload()

    def setupBranchCombo(self, *args):
        allbranches = sorted(self.repo.branchtags().items())

        openbr = []
        for branch, brnode in allbranches:
            openbr.extend(self.repo.branchheads(branch, closed=False))
        clbranches = [br for br, node in allbranches if node not in openbr]
        branches = [br for br, node in allbranches if node in openbr]
        if self.branch_checkBox_action.isChecked():
            branches = branches + clbranches

        if len(branches) == 1:
            self.branch_label_action.setEnabled(False)
            self.branch_comboBox_action.setEnabled(False)
        else:
            self.branchesmodel = QtGui.QStringListModel([''] + branches)
            self.branch_comboBox.setModel(self.branchesmodel)
            self.branch_label_action.setEnabled(True)
            self.branch_comboBox_action.setEnabled(True)

    def createToolbars(self):
        # find quickbar
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

        # navigation toolbar
        self.toolBar_edit.addAction(self.actionShowMainContent)
        self.toolBar_edit.addAction(self.tableView_revisions._actions['back'])
        self.toolBar_edit.addAction(self.tableView_revisions._actions['forward'])

        findaction = self.find_toolbar.toggleViewAction()
        findaction.setIcon(geticon('find'))
        self.toolBar_edit.addAction(findaction)

        # tree filters toolbar
        self.toolBar_treefilters.addAction(self.actionShowHidden)
        self.toolBar_treefilters.addAction(self.tableView_revisions._actions['unfilter'])
        self.toolBar_treefilters.addAction(self.actionShowHidden)

        self.branch_label = QtGui.QToolButton()
        self.branch_label.setText("Branch")
        self.branch_label.setStatusTip("Display graph the named branch only")
        self.branch_label.setPopupMode(QtGui.QToolButton.InstantPopup)
        self.branch_menu = QtGui.QMenu()
        cbranch_action = self.branch_menu.addAction("Display closed branches")
        cbranch_action.setCheckable(True)
        self.branch_checkBox_action = cbranch_action
        self.branch_label.setMenu(self.branch_menu)
        self.branch_comboBox = QtGui.QComboBox()
        connect(self.branch_comboBox, SIGNAL('activated(const QString &)'),
                self.refreshRevisionTable)
        connect(cbranch_action, SIGNAL('toggled(bool)'),
                self.setupBranchComboAndReload)

        self.toolBar_treefilters.layout().setSpacing(3)

        self.branch_label_action = self.toolBar_treefilters.addWidget(self.branch_label)
        self.branch_comboBox_action = self.toolBar_treefilters.addWidget(self.branch_comboBox)
        # separator
        self.toolBar_treefilters.addSeparator()

        self.startrev_label = QtGui.QToolButton()
        self.startrev_label.setText("Start rev.")
        self.startrev_label.setStatusTip("Display graph from this revision")
        self.startrev_label.setPopupMode(QtGui.QToolButton.InstantPopup)
        self.startrev_entry = QtGui.QLineEdit()
        self.startrev_entry.setStatusTip("Display graph from this revision")
        self.startrev_menu = QtGui.QMenu()
        follow_action = self.startrev_menu.addAction("Follow mode")
        follow_action.setCheckable(True)
        follow_action.setStatusTip("Follow changeset history from start revision")
        self.startrev_follow_action = follow_action
        self.startrev_label.setMenu(self.startrev_menu)
        callback = lambda *a: self.tableView_revisions.emit(
                    SIGNAL('startFromRev'),
                    self.startrev_entry, self.startrev_follow_action)
        connect(self.startrev_entry, SIGNAL('editingFinished()'), callback)
        connect(self.startrev_follow_action, SIGNAL('toggled(bool)'), callback)

        self.revscompl_model = QtGui.QStringListModel(['tip'])
        self.revcompleter = QtGui.QCompleter(self.revscompl_model, self)
        self.startrev_entry.setCompleter(self.revcompleter)

        self.startrev_label_action = self.toolBar_treefilters.addWidget(self.startrev_label)
        self.startrev_entry_action = self.toolBar_treefilters.addWidget(self.startrev_entry)

        # diff mode toolbar
        actions = self.textview_status.sci._actions
        for action_name in ('diffmode', 'prev', 'next', 'show-big-file'):
            self.toolBar_diff.addAction(actions[action_name])
        self.toolBar_diff.setVisible(self.cfg.getToolBarDiffAtStartup())

        # rev mod toolbar
        if self.textview_header.rst_action is not None:
            self.toolBar_rev.addAction(self.textview_header.rst_action)
        self.toolBar_rev.setVisible(self.cfg.getToolBarRevAtStartup())

    def createActions(self):
        # main window actions (from .ui file)
        connect(self.actionOpen_repository, SIGNAL('triggered()'),
                self.open_repository)
        connect(self.actionRefresh, SIGNAL('triggered()'),
                self.reload)
        connect(self.actionAbout, SIGNAL('triggered()'),
                self.on_about)
        connect(self.actionQuit, SIGNAL('triggered()'),
                self.close)
        self.actionQuit.setIcon(geticon('quit'))
        self.actionRefresh.setIcon(geticon('reload'))

        self.actionHelp.setShortcut(Qt.Key_F1)
        self.actionHelp.setIcon(geticon('help'))
        connect(self.actionHelp, SIGNAL('triggered()'),
                self.on_help)

        self.actionShowHidden = QtGui.QAction(self.tr('Show/Hide Hidden'), self)
        self.actionShowHidden.setIcon(geticon('showhide'))
        self.actionShowHidden.setCheckable(True)
        self.actionShowHidden.setChecked(self.cfg.getShowHidden())
        self.actionShowHidden.setToolTip(self.tr('Show/Hide hidden changeset'))
        self.actionShowHidden.setStatusTip(self.tr('Show/hide hidden changeset'))
        connect(self.actionShowHidden, SIGNAL('triggered()'),
                self.refreshRevisionTable)

        self.actionShowMainContent = QtGui.QAction('Content', self)
        self.actionShowMainContent.setIcon(geticon('content'))
        self.actionShowMainContent.setCheckable(True)
        self.actionShowMainContent.setChecked(self.cfg.getContentAtStartUp())
        tip = self.tr('Show/Hide changeset content')
        self.actionShowMainContent.setToolTip(tip)
        self.actionShowMainContent.setStatusTip(tip)
        self.actionShowMainContent.setShortcut(Qt.Key_Space)
        connect(self.actionShowMainContent, SIGNAL('triggered()'),
                self.toggleMainContent)

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

    def toggleMainContent(self, visible=None):
        if visible is None:
            visible = self.actionShowMainContent.isChecked()
        visible = bool(visible)
        if visible == self.frame_maincontent.isVisible():
            return
        self.actionShowMainContent.setChecked(visible)
        self.frame_maincontent.setVisible(visible)
        if visible:
            self.revision_selected(-1)

    def setMode(self, mode):
        self.textview_status.setMode(mode)

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

        if self.cfg.getFileDescriptionView() == 'asfile':
            fileselcallback = self.displaySelectedFile
        else:
            fileselcallback = self.textview_status.displayFile
        connect(self.tableView_filelist, SIGNAL('fileSelected'),
                fileselcallback)

        connect(self.textview_status, SIGNAL('revForDiffChanged'),
                self.textview_header.setDiffRevision)

    def displaySelectedFile(self, filename=None, rev=None):
        if filename == '':
            self.textview_status.hide()
            self.textview_header.show()
        else:
            self.textview_header.hide()
            self.textview_status.show()
            self.textview_status.displayFile(filename, rev)

    def setupRevisionTable(self):
        view = self.tableView_revisions
        view.installEventFilter(self)
        connect(view, SIGNAL('clicked (const QModelIndex &)'),
                self.toggleMainContent)
        connect(view, SIGNAL('revisionSelected'), self.revision_selected)
        connect(view, SIGNAL('revisionActivated'), self.revision_activated)
        connect(view, SIGNAL('startFromRev'), self.start_from_rev)
        connect(self.textview_header, SIGNAL('revisionSelected'), view.goto)
        connect(self.textview_header, SIGNAL('parentRevisionSelected'),
                self.textview_status.displayDiff)
        self.attachQuickBar(view.goto_toolbar)
        gotoaction = view.goto_toolbar.toggleViewAction()
        gotoaction.setIcon(geticon('goto'))
        self.toolBar_edit.addAction(gotoaction)

    def start_from_rev(self, rev=None, follow=False):
        if rev == self.startrev_entry:
            rev = str(self.startrev_entry.text()).strip() or None
        if follow == self.startrev_follow_action:
            follow = self.startrev_follow_action.isChecked()

        self.startrev_entry.setText(str(rev or ''))
        self.startrev_follow_action.setChecked(follow)

        self.refreshRevisionTable(rev=rev, follow=follow)

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
        wc = self.repo[None]
        idx = tv.model().index(0, 0) # Working directory or tip
        if not wc.dirty() and wc.p1().rev() >= 0:
            # parent of working directory is not nullrev
            idx = tv.model().indexFromRev(wc.p1().rev())
        tv.setCurrentIndex(idx)

    def revision_activated(self, rev=None):
        """
        Callback called when a revision is double-clicked in the revisions table
        """
        if rev is None:
            rev = self.tableView_revisions.current_rev
        self.toggleMainContent(True)
        self._manifestdlg = ManifestViewer(self.repo, rev)
        self._manifestdlg.show()

    def revision_selected(self, rev):
        """
        Callback called when a revision is selected in the revisions table
        if rev == -1: refresh the current selected revision
        """
        if not self.frame_maincontent.isVisible() or not self.repomodel.graph:
            return
        if rev == -1:
            view = self.tableView_revisions
            indexes = view.selectedIndexes()
            if not indexes:
                return
            rev = view.revFromindex(indexes[0])
        ctx = self.repomodel.repo[rev]
        self.textview_status.setContext(ctx)
        if self.repomodel.show_hidden:
            self.textview_header.excluded = ()
        else:
            self.textview_header.excluded = self.repo.hiddenrevs
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
        watchedfiles = [(self.repo.root, ".hg", "store"),
                        (self.repo.root, ".hg", "store", "00changelog.i"),
                        (self.repo.root, ".hg", "dirstate"),
                        (self.repo.root, ".hg", "store", "phasesroots"),]
        watchedfiles = [os.path.join(*wf) for wf in watchedfiles]
        for l in (self.repo.sjoin('lock'), self.repo.join('wlock')):
            try:
                if util.readlock(l):
                    break
            except EnvironmentError, err:
                # depending on platform (win, nix) the "posix file" abstraction
                # defined and used by mercurial may raise one of both subclasses
                # of EnvironmentError
                if err.errno != errno.ENOENT:
                    raise
        else: # repo not locked by an Hg operation
            mtime = [os.path.getmtime(wf) for wf in watchedfiles \
                     if os.path.exists(wf)]
            if mtime:
                return max(mtime)
            # humm, directory has probably been deleted, exiting...
            self.close()

    def ask_repository(self):
        qrepopath = QtGui.QFileDialog.getExistingDirectory(
            self,
            'Select a mercurial repository',
            self.repo.root or os.path.expanduser('~'))
        repopath = find_repository(str(qrepopath))
        if not repopath:
            if not self.repo.root:
                raise RepoError("There is no Mercurial repository here (.hg not found)!")
            else:
                return
        repo = hg.repository(ui.ui(), repopath)
        return repo

    def open_repository(self):
        repo = self.ask_repository()
        if not repo:
            return
        self.repo = repo
        self.cfg = HgConfig(self.repo.ui)
        self.setWindowTitle('hgview: %s' % os.path.abspath(self.repo.root))
        self._finish_load()

    def reload(self):
        """Reload the repository"""
        self._reload_rev = self.tableView_revisions.current_rev
        self._reload_file = self.tableView_filelist.currentFile()
        self.repo = hg.repository(self.repo.ui, self.repo.root)
        self._finish_load()

    def _finish_load(self):
        self._repodate = self._getrepomtime()
        self.setupBranchCombo()
        self.setupModels()

    #@timeit
    def refreshRevisionTable(self, *args, **kw):
        """Starts the process of filling the HgModel"""
        branch = str(self.branch_comboBox.currentText())
        startrev = kw.get('rev', None)
        # XXX workaround: self.sender() may provoque a core dump if
        # this method is called directly (not via a connected signal);
        # the 'sender' keyword is a way to discrimimne that the method
        # has been called directly (thus caller MUST set this kw arg)
        sender = kw.get('sender') or self.sender()
        follow = kw.get('follow', False)
        closed = self.branch_checkBox_action.isChecked()
        startrev = self.repo.changectx(startrev).rev()
        self.repomodel.show_hidden = self.actionShowHidden.isChecked()
        self.repomodel.setRepo(self.repo, branch=branch, fromhead=startrev,
                               follow=follow, closed=closed)

    def on_about(self, *args):
        """ Display about dialog """
        from hgviewlib.__pkginfo__ import modname, version, description
        try:
            from mercurial.version import get_version
            hgversion = get_version()
        except:
            from mercurial.__version__ import version as hgversion

        msg = "<h2>About %(appname)s %(version)s</h2> (using hg %(hgversion)s)" % \
              {"appname": modname, "version": version, "hgversion": hgversion}
        msg += "<p><i>%s</i></p>" % description.capitalize()
        QtGui.QMessageBox.about(self, "About %s" % modname, msg)

    def on_help(self, *args):
        w = HgviewHelpViewer(self.repo, self)
        w.show()
        w.raise_()
        w.activateWindow()

