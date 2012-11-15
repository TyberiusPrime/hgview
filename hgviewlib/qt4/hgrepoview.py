# Copyright (c) 2009-2012 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Qt4 high level widgets for hg repo changelogs and filelogs
"""
import sys
from collections import namedtuple, defaultdict
from operator import le, ge, lt, gt

from mercurial import cmdutil, ui
from mercurial.node import hex, short as short_hex, bin as short_bin

from mercurial.error import RepoError, ParseError, LookupError, RepoLookupError

from PyQt4 import QtCore, QtGui
Qt = QtCore.Qt
connect = QtCore.QObject.connect
disconnect = QtCore.QObject.disconnect
SIGNAL = QtCore.SIGNAL
nullvariant = QtCore.QVariant()

from hgviewlib.decorators import timeit
from hgviewlib.config import HgConfig
from hgviewlib.hgpatches.scmutil import revrange
from hgviewlib.util import format_desc, xml_escape, tounicode
from hgviewlib.util import first_known_precursors, first_known_successors
from hgviewlib.qt4 import icon as geticon
from hgviewlib.qt4.hgmanifestdialog import ManifestViewer
from hgviewlib.qt4.quickbar import QuickBar
from hgviewlib.qt4.helpviewer import HgHelpViewer

# Re-Structured Text support
raw2html = lambda x: u'<pre>%s</pre>' % xml_escape(x)
try:
    from docutils.core import publish_string
    import docutils.utils
    def rst2html(text):
        try:
            # halt_level allows the parser to raise errors
            # report_level cleans the standard output
            out = publish_string(text, writer_name='html', settings_overrides={
                'halt_level':docutils.utils.Reporter.WARNING_LEVEL,
                'report_level':docutils.utils.Reporter.SEVERE_LEVEL + 1})
        except:
            # docutils is not always reliable (or reliably packaged)
            out = raw2html(text)
        if not isinstance(out, unicode):
            # if the docutils call did not fail, we likely got an str ...
            out = tounicode(out)
        return out
except ImportError:
    rst2html = None


class GotoQuery(QtCore.QThread):
    """A dedicated thread that queries a revset to the repo related to
    the model"""
    def __init__(self):
        super(GotoQuery, self).__init__()
        self.rows = None
        self.revexp = None
        self.model = None

    def __del__(self):
        self.terminate()

    def run(self):
        revset = None
        try:
            revset = revrange(self.model.repo, [self.revexp.encode('utf-8')])
        except (RepoError, ParseError, LookupError, RepoLookupError), err:
            self.rows = None
            self.emit(SIGNAL('failed_revset'), err)
            return
        if revset is None:
            self.rows = ()
            self.emit(SIGNAL('new_revset'), self.rows, self.revexp)
            return
        rows = (idx.row() for idx in
                (self.model.indexFromRev(rev) for rev in revset)
                if idx is not None)
        self.rows = tuple(sorted(rows))
        self.emit(SIGNAL('new_revset'), self.rows, self.revexp)

    def perform(self, revexp, model):
        self.terminate()
        self.revexp = revexp
        self.model = model
        self.start()

    def perform_now(self, revexp, model):
        self.revexp = revexp
        self.model = model
        self.run()

    def get_last_results(self):
        return self.rows

class CompleterModel(QtGui.QStringListModel):
    def add_to_string_list(self, *values):
        strings = self.stringList()
        for value in values:
            if value not in strings:
                strings.append(value)
        self.setStringList(strings)


class QueryLineEdit(QtGui.QLineEdit):
    """Special LineEdit class with visual marks for the revset query status"""
    FORGROUNDS = {'normal':Qt.color1,
                  'valid':Qt.color1,
                  'failed':Qt.darkRed,
                  'query':Qt.darkGray}
    ICONS = {'valid':'valid', 'query':'loading'}
    def __init__(self, parent):
        self._parent = parent
        self._status = None # one of the keys of self.FORGROUNDS and self.ICONS
        QtGui.QLineEdit.__init__(self, parent)
        self.setTextMargins(0,0,-16,0)
        self.valide = True
        self.textEdited.connect(self.on_text_edited)
        self.previous_text = ''

    def set_status(self, status=None):
        self._status = status
        color = self.FORGROUNDS.get(status, None)
        if color is not None:
            palette = self.palette()
            palette.setColor(QtGui.QPalette.Text, color)
            self.setPalette(palette)
    def get_status(self):
        return self._status
    status = property(get_status, set_status, None, "query status")

    def paintEvent(self, event):
        QtGui.QLineEdit.paintEvent(self, event)
        icn = geticon(self.ICONS.get(self._status))
        if icn is None:
            return
        painter = QtGui.QPainter(self)
        icn.paint(painter, self.width() - 18, (self.height() - 18) / 2, 16, 16)

    def on_text_edited(self):
        current_text = unicode(self.text()).strip()
        if  current_text == self.previous_text:
            return
        self.previous_text = current_text
        self.emit(SIGNAL('text_edited_no_blank'), current_text)


class GotoQuickBar(QuickBar):
    def __init__(self, parent):
        self._parent = parent
        self._goto_query = None
        self.compl_model = None
        self.completer = None
        self.row_before = 0
        self._standby_revexp = None # revexp that requires an action from user
        QuickBar.__init__(self, "Goto", "Ctrl+G", "Goto", parent)

    def createActions(self, openkey, desc):
        QuickBar.createActions(self, openkey, desc)
        # goto next
        act = QtGui.QAction("Goto Next", self)
        act.setIcon(geticon('forward'))
        act.setStatusTip("Goto next found revision")
        act.triggered.connect(lambda: self.goto(forward=True))
        self._actions['next'] = act
        # goto prev
        act = QtGui.QAction("Goto Previous", self)
        act.setIcon(geticon('back'))
        act.setStatusTip("Goto previous found revision")
        act.triggered.connect(lambda: self.goto(forward=False))
        self._actions['prev'] = act
        # help
        act = QtGui.QAction("help about revset", self)
        act.setIcon(geticon('help'))
        act.setStatusTip("Display documentation about 'revset'")
        act.triggered.connect(self.show_help)
        self._actions['help'] = act

    def createContent(self):
        QuickBar.createContent(self)
        # completer
        self.compl_model = CompleterModel(['tip'])
        self.completer = QtGui.QCompleter(self.compl_model, self)
        cb = lambda text: self.search(unicode(text))
        self.completer.activated[str].connect(cb)
        # entry
        self.entry = QueryLineEdit(self)
        self.entry.setCompleter(self.completer)
        self.entry.setStatusTip("Enter a 'revset' to query a set of revisions")
        self.addWidget(self.entry)
        connect(self.entry, SIGNAL('text_edited_no_blank'), self.auto_search)
        self.entry.returnPressed.connect(lambda: self.goto(True))
        # actions
        self.addAction(self._actions['prev'])
        self.addAction(self._actions['next'])
        self.addAction(self._actions['help'])
        # querier (threaded)
        self._goto_query = GotoQuery()
        connect(self._goto_query, SIGNAL('failed_revset'), self.on_failed)
        connect(self._goto_query, SIGNAL('new_revset'), self.on_queried)

    def setVisible(self, visible=True):
        QuickBar.setVisible(self, visible)
        if visible:
            self.entry.setFocus()
            self.entry.selectAll()

    def __del__(self):
        #  QObject::startTimer: QTimer can only be used with threads
        #  started with QThread
        self.entry.setCompleter(None)

    def show_help(self):
        w = HgHelpViewer(self._parent.model().repo, 'revset', self)
        w.show()
        w.raise_()
        w.activateWindow()

    def auto_search(self, revexp):
        # Do not automatically search for revision nimber.
        # The problem is that the auto search system will
        # query for lower revision number: users may type the revision
        # number by hand which induce that the first numeric char will be
        # querined alone.
        # But the first found revision is automatically selected, so to much
        # revision tree will be loaded.
        if revexp.isdigit():
            self.entry.status = 'normal'
            self._actions['next'].setEnabled(True)
            self._actions['prev'].setEnabled(True)
            self.show_message(
                'Hit [Enter] because '
                'revision number is not automaically queried '
                'for optimmization purpose.')
            self._standby_revexp = revexp
            return
        self.search(revexp)

    def goto(self, forward=True):
        # returnPressed from the `entry` also call this slot
        # We check if the main corresponding action is enabled
        if not self._actions['next'].isEnabled():
            if self.entry.status == 'failed':
                self.show_message("Invalid revset expression.")
            else:
                self.show_message("Quering, please wait (or edit to cancel).")
            return
        if self._standby_revexp is not None:
            self.search(self._standby_revexp, threaded=False)
        rows = self._goto_query.get_last_results()
        if rows is None:
            self.entry.status = 'failed'
            return
        if forward:
            signal = 'goto_strict_next_from'
        else:
            signal = 'goto_strict_prev_from'
        self.emit(SIGNAL(signal), rows)
        # usecase: enter a nodeid and hit enter to go on,
        #          so the goto tool bar is no more required and may be
        #          annoying
        if rows and len(rows) == 1:
            self.setVisible(False)

    def search(self, revexp, threaded=True):
        if revexp is None:
            revexp = self._standby_revexp
        self._standby_revexp = None
        if not revexp:
            self.emit(SIGNAL('new_set'), None)
            self.emit(SIGNAL('goto_next_from'), (self.row_before,))
            return
        self.show_message("Quering ... (edit the entry to cancel)")
        self._actions['next'].setEnabled(False)
        self._actions['prev'].setEnabled(False)
        self.entry.status = 'query'
        if threaded:
            self._goto_query.perform(revexp, self._parent.model())
        else:
            self._goto_query.perform_now(revexp, self._parent.model())

    def show_message(self, message, delay=-1):
        self.parent().statusBar().showMessage(message, delay)

    def on_queried(self, rows=None, revexp=''):
        """Slot to handle new revset."""
        self.entry.status = 'valid'
        self.emit(SIGNAL('new_set'), rows)
        self.emit(SIGNAL('goto_next_from'), rows)
        self._actions['next'].setEnabled(True)
        self._actions['prev'].setEnabled(True)
        if rows and revexp:
            self.compl_model.add_to_string_list(revexp)

    def on_failed(self, err):
        self.entry.status = 'failed'
        self.show_message(unicode(err))
        self._actions['next'].setEnabled(False)
        self._actions['prev'].setEnabled(False)


class HgRepoView(QtGui.QTableView):
    """
    A QTableView for displaying a FileRevModel or a HgRepoListModel,
    with actions, shortcuts, etc.
    """
    def __init__(self, parent=None):
        QtGui.QTableView.__init__(self, parent)
        self.init_variables()
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(20)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)

        self.createActions()
        self.createToolbars()
        connect(self,
                SIGNAL('doubleClicked (const QModelIndex &)'),
                self.revisionActivated)

        self._autoresize = True
        connect(self.horizontalHeader(),
                SIGNAL('sectionResized(int, int, int)'),
                self.disableAutoResize)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        if event.button() == Qt.MidButton:
            self.gotoAncestor(index)
            return
        QtGui.QTableView.mousePressEvent(self, event)

    def createToolbars(self):
        self.goto_toolbar = GotoQuickBar(self)
        goto = self.goto_next_from
        connect(self.goto_toolbar, SIGNAL('goto_strict_next_from'),
                lambda revs: goto(revs, strict=True, forward=True))
        connect(self.goto_toolbar, SIGNAL('goto_strict_prev_from'),
                lambda revs: goto(revs, strict=True, forward=False))
        connect(self.goto_toolbar, SIGNAL('goto_next_from'),
                lambda revs: goto(revs))
        connect(self.goto_toolbar, SIGNAL('new_set'),
                self.highlight_rows)

    def _action_defs(self):
        class ActDef(object):
            def __init__(self, name, desc, icon, tip, keys, cb):
                self.name = name
                self.desc = desc
                self.icon = icon
                self.tip  = tip
                self.keys = keys
                self.cb   = cb
            def __iter__(self):
                yield self.name
                yield self.desc
                yield self.icon
                yield self.tip
                yield self.keys
                yield self.cb
            def __repr__(self):
                out = super(ActDef, self).__repr__()
                return out[:-1] + 'name=%r' % self.name + out[-1:]

        return [
            ActDef(name="copycs",
                   desc=self.tr("Export to clipboard"),
                   icon=None,
                   tip=self.tr("Export changeset metadata the window manager clipboard [see configuration entry 'exporttemplate']"),
                   keys=None, # XXX shall be specified after general shortcuts refactorization
                   cb=self.copy_cs_to_clipboard),
            ActDef(name="back",
                   desc=self.tr("Previous visited"),
                   icon='back',
                   tip=self.tr("Barward to the previous visited changeset"),
                   keys=[QtGui.QKeySequence(QtGui.QKeySequence.Back)],
                   cb=self.back),
            ActDef(name="forward",
                   desc=self.tr("Next visited"),
                   icon='forward',
                   tip=self.tr("Forward to the next visited changeset"),
                   keys=[QtGui.QKeySequence(QtGui.QKeySequence.Forward)],
                   cb=self.forward),
            ActDef(name="manifest",
                   desc=self.tr("Manifest"),
                   icon=None,
                   tip=self.tr("Show the manifest at selected revision"),
                   keys=[Qt.SHIFT + Qt.Key_Enter, Qt.SHIFT + Qt.Key_Return],
                   cb=self.showAtRev),
            ActDef(name="start",
                   desc=self.tr("Hide higher revisions"),
                   icon=None,
                   tip=self.tr("Start graph from this revision"),
                   keys=[Qt.Key_Backspace],
                   cb=self.startFromRev),
            ActDef(name="follow",
                   desc=self.tr("Focus on ancestors"),
                   icon=None,
                   tip=self.tr("Follow revision history from this revision"),
                   keys=[Qt.SHIFT + Qt.Key_Backspace],
                   cb=self.followFromRev),
            ActDef(name="unfilter",
                   desc=self.tr("Show all changesets"),
                   icon="unfilter",
                   tip=self.tr("Remove filter and show all changesets"),
                   keys=[Qt.ALT + Qt.CTRL + Qt.Key_Backspace],
                   cb=self.removeFilter),
             ]

    def createActions(self):
        self._actions = {}
        for name, desc, icon, tip, key, cb in self._action_defs():
            self._actions[name] = QtGui.QAction(desc, self)
        QtCore.QTimer.singleShot(0, self.configureActions)

    def configureActions(self):
        for name, desc, icon, tip, keys, cb in self._action_defs():
            act = self._actions[name]
            if icon:
                act.setIcon(geticon(icon))
            if tip:
                act.setStatusTip(tip)
            if keys:
                act.setShortcuts(keys)
            if cb:
                connect(act, SIGNAL('triggered()'), cb)
            self.addAction(act)
        self._actions['unfilter'].setEnabled(False)
        connect(self, SIGNAL('startFromRev'), self.update_filter_action)

    def update_filter_action(self, rev=None, follow=None):
        self._actions['unfilter'].setEnabled(rev is not None)

    def copy_cs_to_clipboard(self):
        """ Copy changeset metada into the window manager clipboard."""
        repo = self.model().repo
        ctx = repo[self.current_rev]
        u = ui.ui(repo.ui)
        template = HgConfig(u).getExportTemplate()
        u.pushbuffer()
        cmdutil.show_changeset(u, repo, {'template':template}, False).show(ctx)
        QtGui.QApplication.clipboard().setText(u.popbuffer())

    def showAtRev(self):
        self.emit(SIGNAL('revisionActivated'), self.current_rev)

    def startFromRev(self):
        self.emit(SIGNAL('startFromRev'), self.current_rev, False)

    def followFromRev(self):
        self.emit(SIGNAL('startFromRev'), self.current_rev, True)

    def removeFilter(self):
        self.emit(SIGNAL('startFromRev'))

    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        for act in ['copycs', None,
                    'manifest', None,
                    'start', 'follow', 'unfilter', None,
                    'back', 'forward']:
            if act:
                menu.addAction(self._actions[act])
            else:
                menu.addSeparator()
        menu.exec_(event.globalPos())

    def init_variables(self):
        # member variables
        self.current_rev = None
        # rev navigation history (manage 'back' action)
        self._rev_history = []
        self._rev_pos = -1
        self._in_history = False # flag set when we are "in" the
        # history. It is required cause we cannot known, in
        # "revision_selected", if we are crating a new branch in the
        # history navigation or if we are navigating the history

    def setModel(self, model):
        self.init_variables()
        QtGui.QTableView.setModel(self, model)
        connect(self.selectionModel(),
                QtCore.SIGNAL('currentRowChanged (const QModelIndex & , const QModelIndex & )'),
                self.revisionSelected)
        tags = model.repo.tags().keys()
        self.goto_toolbar.compl_model.add_to_string_list(*tags)
        col = list(model._columns).index('Log')
        self.horizontalHeader().setResizeMode(col, QtGui.QHeaderView.Stretch)

    def enableAutoResize(self, *args):
        self._autoresize =  True

    def disableAutoResize(self, *args):
        self._autoresize =  False
        QtCore.QTimer.singleShot(100, self.enableAutoResize)

    def resizeEvent(self, event):
        # we catch this event to resize smartly tables' columns
        QtGui.QTableView.resizeEvent(self, event)
        if self._autoresize:
            self.resizeColumns()

    def resizeColumns(self, *args):
        # resize columns the smart way: the column holding Log
        # is resized according to the total widget size.
        model = self.model()
        if not model:
            return
        col1_width = self.viewport().width()
        fontm = QtGui.QFontMetrics(self.font())
        tot_stretch = 0.0
        for c in range(model.columnCount()):
            if model._columns[c] in model._stretchs:
                tot_stretch += model._stretchs[model._columns[c]]
                continue
            w = model.maxWidthValueForColumn(c)
            if w is not None:
                w = fontm.width(unicode(w) + 'w')
                self.setColumnWidth(c, w)
            else:
                w = self.sizeHintForColumn(c)
                self.setColumnWidth(c, w)
            col1_width -= self.columnWidth(c)
        col1_width = max(col1_width, 100)
        for c in range(model.columnCount()):
            if model._columns[c] in model._stretchs:
                w = model._stretchs[model._columns[c]] / tot_stretch
                self.setColumnWidth(c, col1_width * w)

    def revFromindex(self, index):
        if not index.isValid():
            return
        model = self.model()
        if model and model.graph:
            row = index.row()
            gnode = model.graph[row]
            return gnode.rev

    def revisionActivated(self, index):
        rev = self.revFromindex(index)
        if rev is not None:
            self.emit(SIGNAL('revisionActivated'), rev)

    def revisionSelected(self, index, index_from):
        """
        Callback called when a revision is selected in the revisions table
        """
        rev = self.revFromindex(index)
        if True:#rev is not None:
            model = self.model()
            if self.current_rev is not None and self.current_rev == rev:
                return
            if not self._in_history:
                del self._rev_history[self._rev_pos+1:]
                self._rev_history.append(rev)
                self._rev_pos = len(self._rev_history)-1

            self._in_history = False
            self.current_rev = rev

            self.emit(SIGNAL('revisionSelected'), rev)
            self.set_navigation_button_state()

    def gotoAncestor(self, index):
        rev = self.revFromindex(index)
        if rev is not None and self.current_rev is not None:
            repo = self.model().repo
            ctx = repo[self.current_rev]
            ctx2 = repo[rev]
            ancestor = ctx.ancestor(ctx2)
            self.emit(SIGNAL('showMessage'),
                      "Goto ancestor of %s and %s"%(ctx.rev(), ctx2.rev()),
                      5000)
            self.goto(ancestor.rev())

    def set_navigation_button_state(self):
        if len(self._rev_history) > 0:
            back = self._rev_pos > 0
            forw = self._rev_pos < len(self._rev_history)-1
        else:
            back = False
            forw = False
        self._actions['back'].setEnabled(back)
        self._actions['forward'].setEnabled(forw)

    def back(self):
        if self._rev_history and self._rev_pos>0:
            self._rev_pos -= 1
            idx = self.model().indexFromRev(self._rev_history[self._rev_pos])
            if idx is not None:
                self._in_history = True
                self.setCurrentIndex(idx)
        self.set_navigation_button_state()

    def forward(self):
        if self._rev_history and self._rev_pos<(len(self._rev_history)-1):
            self._rev_pos += 1
            idx = self.model().indexFromRev(self._rev_history[self._rev_pos])
            if idx is not None:
                self._in_history = True
                self.setCurrentIndex(idx)
        self.set_navigation_button_state()

    def goto(self, rev):
        """
        Select revision 'rev'.
        It can be anything understood by repo.changectx():
          revision number, node or tag for instance.
        """
        if isinstance(rev, basestring) and ':' in rev:
            rev = rev.split(':')[1]
        repo = self.model().repo
        try:
            rev = repo.changectx(rev).rev()
        except RepoError:
            self.emit(SIGNAL('showMessage'),
                      "Can't find revision '%s'" % rev, 2000)
        else:
            idx = self.model().indexFromRev(rev)
            if idx is not None:
                self.goto_toolbar.setVisible(False)
                self.setCurrentIndex(idx)

    def goto_next_from(self, rows, strict=False, forward=True):
        """Select the next row available in rows."""
        if not rows:
            return
        currow = self.currentIndex().row()
        if strict:
            greater, less = gt, lt
        else:
            greater, less = ge, le
        if forward:
            comparer, _rows = greater, rows
        else:
            comparer, _rows = less, reversed(rows)
        try:
            row = (row for row in _rows if comparer(row, currow)).next()
        except StopIteration:
            self.visual_bell()
            row = rows[0 if forward else -1]
        self.setCurrentIndex(self.model().index(row, 0))
        pos = rows.index(row) + 1
        self.emit(SIGNAL('showMessage'),
                  "revision #%i of %i" % (pos, len(rows)),
                  -1)

    def nextRev(self):
        row = self.currentIndex().row()
        self.setCurrentIndex(self.model().index(min(row+1,
                             self.model().rowCount() - 1), 0))
    def prevRev(self):
        row = self.currentIndex().row()
        self.setCurrentIndex(self.model().index(max(row - 1, 0), 0))

    def highlight_rows(self, rows):
        if rows is None:
            self.visual_bell()
            self.emit(SIGNAL('showMessage'), 'Revision set cleared.', 2000)
        else:
            self.emit(SIGNAL('showMessage'),
                      '%i revisions found.' % len(rows),
                      2000)
        self.model().highlight_rows(rows or ())
        self.refresh_display()

    def refresh_display(self):
        for item in self.children():
            try:
                item.update()
            except AttributeError:
                pass

    def visual_bell(self):
        self.hide()
        QtCore.QTimer.singleShot(0.01, self.show)


TROUBLE_EXPLANATIONS = defaultdict(lambda:'unknown trouble')
TROUBLE_EXPLANATIONS['unstable']  = "Based on obsolete ancestor"
TROUBLE_EXPLANATIONS['bumped']    = "Hopeless successors of a public changeset"
TROUBLE_EXPLANATIONS['divergent'] = "Another changeset are also a successors "\
                                    "of one of your precursor"
# temporary compat with older evolve version
TROUBLE_EXPLANATIONS['latecomer'] = TROUBLE_EXPLANATIONS['bumped']
TROUBLE_EXPLANATIONS['conflicting'] = TROUBLE_EXPLANATIONS['divergent']
class RevDisplay(QtGui.QTextBrowser):
    """
    Display metadata for one revision (rev, author, description, etc.)
    """
    def __init__(self, parent=None):
        QtGui.QTextBrowser.__init__(self, parent)
        self.excluded = ()
        self.descwidth = 60 # number of chars displayed for parent/child descriptions

        if rst2html:
            self.rst_action = QtGui.QAction(self.tr('Fancy Display'), self)
            self.rst_action.setCheckable(True)
            self.rst_action.setChecked(True)
            self.rst_action.setToolTip(self.tr('Interpret ReST comments'))
            self.rst_action.setStatusTip(self.tr('Interpret ReST comments'))

            connect(self.rst_action, SIGNAL('triggered()'),
                    self.refreshDisplay)
        else:
            self.rst_action = None
        connect(self,
                SIGNAL('anchorClicked(const QUrl &)'),
                self.anchorClicked)

    def anchorClicked(self, qurl):
        """
        Callback called when a link is clicked in the text browser
        """
        rev = str(qurl.toString())
        diff = False
        if rev.startswith('diff_'):
            rev = int(rev[5:])
            diff = True

        try:
            rev = self.ctx._repo.changectx(rev).rev()
        except RepoError:
            QtGui.QDesktopServices.openUrl(qurl)
            self.refreshDisplay()

        if diff:
            self.diffrev = rev
            self.refreshDisplay()
            # TODO: emit a signal to recompute the diff
            self.emit(SIGNAL('parentRevisionSelected'), self.diffrev)
        else:
            self.emit(SIGNAL('revisionSelected'), rev)

    def setDiffRevision(self, rev):
        if rev != self.diffrev:
            self.diffrev = rev
            self.refreshDisplay()

    def displayRevision(self, ctx):
        self.ctx = ctx
        self.diffrev = ctx.parents()[0].rev()
        if hasattr(self.ctx._repo, "mq"):
            self.mqseries = self.ctx._repo.mq.series[:]
            self.mqunapplied = [x[1] for x in self.ctx._repo.mq.unapplied(self.ctx._repo)]
            mqpatch = set(self.ctx.tags()).intersection(self.mqseries)
            if mqpatch:
                self.mqpatch = mqpatch.pop()
            else:
                self.mqpatch = None
        else:
            self.mqseries = []
            self.mqunapplied = []
            self.mqpatch = None

        self.refreshDisplay()

    def selectNone(self):
        cursor = self.textCursor()
        cursor.clearSelection()
        cursor.setPosition(0)
        self.setTextCursor(cursor)
        self.setExtraSelections([])

    def searchString(self, text):
        self.selectNone()
        if text in unicode(self.toPlainText()):
            clist = []
            while self.find(text):
                eselect = self.ExtraSelection()
                eselect.cursor = self.textCursor()
                eselect.format.setBackground(QtGui.QColor('#ffffbb'))
                clist.append(eselect)
            self.selectNone()
            self.setExtraSelections(clist)
            def finditer(self, text):
                if text:
                    while True:
                        if self.find(text):
                            yield self.ctx.rev(), None
                        else:
                            break
            return finditer(self, text)

    def refreshDisplay(self):
        ctx = self.ctx
        rev = ctx.rev()
        cfg = HgConfig(ctx._repo.ui)
        buf = "<table width=100%>\n"
        if self.mqpatch:
            buf += '<tr bgcolor=%s>' % cfg.getMQFGColor()
            buf += '<td colspan=4 width=100%><b>Patch queue:</b>&nbsp;'
            for p in self.mqseries:
                if p in self.mqunapplied:
                    p = "<i>%s</i>" % p
                elif p == self.mqpatch:
                    p = "<b>%s</b>" % p
                buf += '&nbsp;%s&nbsp;' % (p)
            buf += '</td></tr>\n'

        buf += '<tr>'
        if rev is None:
            buf += "<td><b>Working Directory</b></td>\n"
        else:
            buf += '<td title="Revision"><b>'\
                   '<span class="rev_number">%s</span>:'\
                   '<span class="rev_hash">%s</span>'\
                   '</b></td>\n' % (ctx.rev(), short_hex(ctx.node()))

        user = tounicode(ctx.user()) if ctx.node() else u''
        buf += '<td title="Author">%s</td>\n' % user
        buf += '<td title="Branch name">%s</td>\n' % ctx.branch()
        buf += '<td title="Phase name">%s</td>\n' % ctx.phasestr()
        buf += '</tr>'
        buf += "</table>\n"

        buf += "<table width=100%>\n"
        parents = [p for p in ctx.parents() if p]
        for p in parents:
            if p.rev() > -1:
                buf += self._html_ctx_info(p, 'Parent', 'Direct ancestor of this changeset')
        if len(parents) == 2:
            p = parents[0].ancestor(parents[1])
            buf += self._html_ctx_info(p, 'Ancestor', 'Direct ancestor of this changeset')

        for p in ctx.children():
            r = p.rev()
            if r > -1 and r not in self.excluded:
                buf += self._html_ctx_info(p, 'Child', 'Direct descendant of this changeset')
        for prec in first_known_precursors(ctx, self.excluded):
            buf += self._html_ctx_info(prec, 'Precursor',
                'Previous version obsolete by this changeset')
        for suc in first_known_successors(ctx, self.excluded):
            buf += self._html_ctx_info(suc, 'Successors',
                'Updated version that make this changeset obsolete')
        bookmarks = ', '.join(ctx.bookmarks())
        if bookmarks:
            buf += '<tr><td width=50 class="label"><b>Bookmarks:</b></td>'\
                   '<td colspan=5>&nbsp;'\
                   '<span class="short_desc">%s</span></td></tr>'\
                   '\n' % bookmarks
        troubles = ctx.troubles()
        if troubles:
            span = '<span title="%s"  style="color: red;">%s</span>'
            content = ', '.join([span % (TROUBLE_EXPLANATIONS[troub], troub)
                                for troub in troubles])
            buf += '<tr><td width=50 class="label"><b>Troubles:</b></td>'\
                   '<td colspan=5>&nbsp;'\
                   '<span class="short_desc" >%s</span></td></tr>'\
                   '\n' % ''.join(content)
        buf += "</table>\n"
        desc = tounicode(ctx.description())
        if self.rst_action is not None  and self.rst_action.isChecked():
            replace = cfg.getFancyReplace()
            if replace:
                desc = replace(desc)
            desc = rst2html(desc)
        else:
            desc = raw2html(desc)
        buf += '<div class="diff_desc">%s</div>\n' % desc
        self.setHtml(buf)

    def contextMenuEvent(self, event):
        _context_menu = self.createStandardContextMenu()
        _context_menu.addAction(self.rst_action)
        _context_menu.exec_(event.globalPos())

    def _html_ctx_info(self, ctx, title, tooltip=None):
        isdiffrev = ctx.rev() == self.diffrev
        if not tooltip:
            tooltip = title
        short = short_hex(ctx.node()) if getattr(ctx, 'applied', True) else ctx.node()
        descr = format_desc(ctx.description(), self.descwidth)
        rev = ctx.rev()
        out = '<tr>'\
              '<td width=60 class="label" title="%(tooltip)s"><b>%(title)s:</b></td>'\
              '<td colspan=5>' % locals()
        if isdiffrev:
            out += '<b>'
        out += '<span class="rev_number">'\
               '<a href="diff_%(rev)s" class="rev_diff" title="display diff from there">%(rev)s</a>'\
               '</span>:'\
               '<a title="go to there" href="%(rev)s" class="rev_hash">%(short)s</a>&nbsp;'\
               '<span class="short_desc"><i>%(descr)s</i></span>' % locals()
        if isdiffrev:
            out += '</b>'
        out += '</td></tr>\n'
        return out
