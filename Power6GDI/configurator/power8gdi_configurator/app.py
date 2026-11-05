"""R2 ECU Studio: offline calibration and clearly separated display simulation.

This is offline software: no connection, burn, engine control or ECU protocol
is implied by its windows or by edits made to JSON calibration documents.
"""
from __future__ import annotations
import sys
from collections import deque
from pathlib import Path
from .project import default_project,CalibrationProject,CalibrationTable4D
from .simulator import DisplaySimulator, CHANNELS
from .can_preview import CANPreview, load_can_preview

try:
    from PyQt6.QtCore import Qt,QSignalBlocker,QTimer,QPointF
    from PyQt6.QtGui import QColor,QAction,QKeySequence,QUndoCommand,QUndoStack,QPainter,QPen
    from PyQt6.QtWidgets import (
       QApplication,QMainWindow,QWidget,QSplitter,QTreeWidget,QTreeWidgetItem,
       QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
       QToolBar,QFileDialog,QMessageBox,QStatusBar,QPushButton,QFrame,
       QAbstractItemView,QLineEdit,QHeaderView,QComboBox,QDockWidget,
       QDialog,QDialogButtonBox,QPlainTextEdit,QInputDialog)
except ImportError as exc:
    raise SystemExit('PyQt6 is required for the GUI. Install: pip install -e .') from exc

STYLE='''
QMainWindow,QWidget { background:#0d141c;color:#d7e5f1;font:12px "Segoe UI"; }
QTreeWidget,QTableWidget { background:#121e29;alternate-background-color:#162431;
 color:#e0ebf3;border:1px solid #283a47;gridline-color:#2b4656;selection-background-color:#237b8d; }
QTreeWidget::item {padding:6px;} QTreeWidget::item:selected {background:#164e64;}
QHeaderView::section {background:#192a38;color:#c9e2ee;border:1px solid #2b4555;
 padding:6px;font-weight:600;}
QToolBar {background:#0e1c27;border-bottom:1px solid #264351;spacing:8px;padding:7px;}
QToolButton {background:#213342;border:1px solid #36505f;border-radius:5px;
 color:#dcecf5;padding:7px 12px;}QToolButton:hover {background:#2b5468;}
QLabel#headline {font-size:22px;font-weight:700;color:#f0f7fa;}
QLabel#section {font-size:15px;font-weight:600;color:#73cad5;}
QLabel#muted {color:#809aac;}
QLabel#warning {color:#e8b77a;font-weight:600;}
QLineEdit {background:#142330;color:white;border:1px solid #3a5262;
 border-radius:5px;padding:7px;}
QStatusBar {background:#142331;color:#83a9bb;border-top:1px solid #273f4e;}
QPushButton {background:#214b60;color:#e7f5fc;border:1px solid #36788b;
 border-radius:5px;padding:7px;}QPushButton:hover{background:#27758b;}
'''

class CellEdit(QUndoCommand):
    def __init__(self,window,name,x,y,z,old,new):
        super().__init__(f'{name} [{z},{y},{x}]')
        self.window=window;self.name=name;self.x=x;self.y=y;self.z=z
        self.old=old;self.new=new
    def redo(self):self.window._set_cell(self.name,self.x,self.y,self.z,self.new)
    def undo(self):self.window._set_cell(self.name,self.x,self.y,self.z,self.old)


class SimulationPlot(QWidget):
    """A bounded, read-only RPM trace. No calibration value is updated here."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = deque(maxlen=120)
        self.setMinimumSize(320, 140)
        self.setAccessibleName('Simulated engine speed graph')

    def clear(self):
        self.samples.clear()
        self.update()

    def append(self, time_s, rpm):
        self.samples.append((time_s, rpm))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, top = 55., 25.
        width, height = max(1., self.width()-70.), max(1., self.height()-55.)
        painter.setPen(QPen(QColor('#36505f'), 1))
        for ratio in (0., .5, 1.):
            y = top + height * ratio
            painter.drawLine(QPointF(left, y), QPointF(left+width, y))
            painter.drawText(0, int(y+4), f'{10000*(1-ratio):.0f}')
        painter.setPen(QColor('#83a9bb'))
        painter.drawText(0, 15, 'rpm — SIMULATED')
        painter.drawText(int(left), self.height()-5, 'Simulation time [s]')
        if not self.samples:
            painter.drawText(int(left+15), int(top+height/2), 'No simulated data')
            return
        end = self.samples[-1][0]
        start = max(0., end-24.)
        painter.drawText(self.width()-90, self.height()-5, f'{end:.1f} s')
        painter.setPen(QPen(QColor('#73cad5'), 2))
        points = [QPointF(left+(t-start)/24.*width, top+(1-rpm/10000.)*height)
                  for t, rpm in self.samples]
        for first, second in zip(points, points[1:]):
            painter.drawLine(first, second)


class CANPreviewDialog(QDialog):
    def __init__(self, preview: CANPreview, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'CAN definition preview — {preview.source}')
        self.resize(1100, 620)
        layout = QVBoxLayout(self)
        label = QLabel(f'{len(preview.signals)} signals · OFFLINE PREVIEW · racing_dash importer')
        label.setObjectName('section')
        layout.addWidget(label)
        self.table = QTableWidget(len(preview.signals), 7)
        self.table.setHorizontalHeaderLabels(['Signal', 'Message', 'Bus', 'CAN ID', 'Unit', 'Scale', 'Mux'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for row, signal in enumerate(preview.signals):
            values = (signal.name, signal.message, signal.bus, signal.can_id,
                      signal.unit, signal.scale, 'Yes' if signal.multiplexed else 'No')
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(self.table, stretch=1)
        self.warnings = QPlainTextEdit('\n'.join(preview.warnings))
        self.warnings.setReadOnly(True)
        self.warnings.setMaximumHeight(160)
        layout.addWidget(self.warnings)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project=default_project();self.path:Path|None=None
        self.active_name='Boost / Target';self._in_update=False
        self.simulator = DisplaySimulator()
        self.simulation_timer = QTimer(self)
        self.simulation_timer.setInterval(200)
        self.simulation_timer.timeout.connect(self._simulation_tick)
        self.undo_stack=QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._clean_changed)
        self._update_window_title()
        self.resize(1520,910)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self._refresh_profile()
        self._rebuild_tree()
        self._select_table(self.active_name)

    def _init_ui(self):
        toolbar=QToolBar('Project');toolbar.setMovable(False)
        self.addToolBar(toolbar)
        def action(title,callback,shortcut=None):
            a=QAction(title,self);a.triggered.connect(callback)
            if shortcut:a.setShortcut(QKeySequence(shortcut))
            toolbar.addAction(a);return a
        action('New',self.new_project,'Ctrl+N')
        action('Open',self.open_project,'Ctrl+O')
        action('Save',self.save_project,'Ctrl+S')
        action('Save as',self.save_as)
        toolbar.addSeparator()
        self.undo_action=self.undo_stack.createUndoAction(self,'Undo')
        self.undo_action.setShortcut(QKeySequence('Ctrl+Z'))
        toolbar.addAction(self.undo_action)
        self.redo_action=self.undo_stack.createRedoAction(self,'Redo')
        self.redo_action.setShortcut(QKeySequence('Ctrl+Y'))
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        off=action('ECU: disconnected',self.offline_notice)
        off.setEnabled(True)
        self.simulation_action = action('Start simulator', self.toggle_simulator)
        action('CAN definitions…', self.preview_can_definitions)

        split=QSplitter(Qt.Orientation.Horizontal);split.setChildrenCollapsible(False)
        left=QWidget();lv=QVBoxLayout(left);lv.setContentsMargins(10,18,10,10)
        self.brand=QLabel('R2 SPORT GDI6');self.brand.setObjectName('headline');lv.addWidget(self.brand)
        desc=QLabel('ECU CALIBRATION STUDIO');desc.setObjectName('muted');lv.addWidget(desc)
        lv.addSpacing(14)
        tree_label=QLabel('CALIBRATION TREE');tree_label.setObjectName('section')
        lv.addWidget(tree_label)
        self.map_search=QLineEdit()
        self.map_search.setPlaceholderText('Find map, axis or unit…  Ctrl+F')
        self.map_search.setClearButtonEnabled(True)
        self.map_search.setAccessibleName('Find calibration map')
        lv.addWidget(self.map_search)
        self.tree=QTreeWidget();self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._tree_clicked)
        self.tree.setIndentation(15)
        lv.addWidget(self.tree)
        self.map_search.textChanged.connect(self._filter_tree)
        self.find_action=QAction('Find map',self)
        self.find_action.setShortcut(QKeySequence('Ctrl+F'))
        self.find_action.triggered.connect(self._focus_search)
        self.addAction(self.find_action)
        note=QLabel('Prototype editor · no ECU connection')
        note.setObjectName('warning');note.setWordWrap(True);lv.addWidget(note)
        self.profile_notice=QLabel('');self.profile_notice.setWordWrap(True)
        self.profile_notice.setObjectName('warning');lv.addWidget(self.profile_notice)
        split.addWidget(left)

        center=QWidget();cv=QVBoxLayout(center);cv.setContentsMargins(16,15,16,12)
        top=QHBoxLayout()
        title_block=QVBoxLayout()
        self.title=QLabel('');self.title.setObjectName('headline');title_block.addWidget(self.title)
        self.desc=QLabel('');self.desc.setObjectName('muted');title_block.addWidget(self.desc)
        top.addLayout(title_block,stretch=1)
        tag=QLabel('OFFLINE EDITOR');tag.setObjectName('warning');top.addWidget(tag)
        cv.addLayout(top)
        cv.addSpacing(14)
        self.layer_row=QHBoxLayout()
        self.layer_label=QLabel('Z LAYER');self.layer_label.setObjectName('section')
        self.layer_row.addWidget(self.layer_label)
        self.layer_selector=QComboBox()
        self.layer_selector.currentIndexChanged.connect(self._z_changed)
        self.layer_row.addWidget(self.layer_selector)
        self.layer_row.addStretch(1)
        cv.addLayout(self.layer_row)
        self.grid=QTableWidget();self.grid.setAlternatingRowColors(False)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.grid.itemChanged.connect(self._item_changed)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.grid.verticalHeader().setDefaultSectionSize(34)
        cv.addWidget(self.grid,stretch=1)
        info=QHBoxLayout()
        self.meta=QLabel('');self.meta.setObjectName('muted');info.addWidget(self.meta,stretch=1)
        self.interp=QLabel('');self.interp.setObjectName('section');info.addWidget(self.interp)
        cv.addLayout(info)
        split.addWidget(center)

        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(12,18,12,10)
        io=QLabel('PROJECT TARGET');io.setObjectName('section');rv.addWidget(io)
        self.hardware_labels={}
        for label in ('Controller','Injection','Ignition','HPFP','DBW / EWG',
                      'Sensors','Interfaces','Connection','Burn/Flash'):
            item=QWidget();iv=QVBoxLayout(item);iv.setContentsMargins(0,8,0,5)
            head=QLabel(label.upper());head.setObjectName('muted');iv.addWidget(head)
            val=QLabel('');val.setWordWrap(True);iv.addWidget(val)
            self.hardware_labels[label]=val
            rv.addWidget(item)
        rv.addStretch(1)
        self.note=QLabel('WARNING: sample tables are not validated engine calibrations.')
        self.note.setObjectName('warning');self.note.setWordWrap(True);rv.addWidget(self.note)
        split.addWidget(right)
        split.setSizes([285,1030,215]);self.setCentralWidget(split)
        status=QStatusBar();self.setStatusBar(status)
        self.statusBar().showMessage('No ECU connection · documents are stored locally as versioned JSON')
        dock=QDockWidget('DISPLAY SIMULATOR — artificial data, no hardware connection',self)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        container=QWidget();layout=QHBoxLayout(container)
        self.telemetry=QTableWidget(len(CHANNELS),3)
        self.telemetry.setHorizontalHeaderLabels(['Simulated channel','Value','Unit'])
        self.telemetry.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.telemetry.verticalHeader().hide()
        self.telemetry.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, channel in enumerate(CHANNELS):
            for col, value in enumerate((channel.label, '—', channel.unit)):
                self.telemetry.setItem(row,col,QTableWidgetItem(value))
        self.simulation_plot=SimulationPlot()
        layout.addWidget(self.telemetry,1);layout.addWidget(self.simulation_plot,2)
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,dock)
        self.resizeDocks([dock],[215],Qt.Orientation.Vertical)

    def preview_can_definitions(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Preview CAN definition', '', 'CAN definitions (*.dbc *.canx)')
        if not path:
            return
        choices = ['File default (DBC: CAN1)', 'CAN1', 'CAN2', 'CAN1 + CAN2']
        choice, accepted = QInputDialog.getItem(
            self, 'Preview bus selection', 'Receive bus', choices, 0, False)
        if not accepted:
            return
        bus = [None, 0, 1, 2][choices.index(choice)]
        try:
            preview = load_can_preview(path, bus)
        except (OSError, ValueError, UnicodeError) as exc:
            QMessageBox.warning(self, 'Cannot preview CAN definition', str(exc))
            return
        CANPreviewDialog(preview, self).exec()

    def _refresh_profile(self):
        p=self.project.profile
        self.brand.setText('LEGACY POWER8GDI' if self.project.is_legacy else 'R2 SPORT GDI6')
        values={
            'Controller':p.label,
            'Injection':f'{p.di_channels} DI / {p.pi_channels} PI (optional)',
            'Ignition':f'{p.ignition_channels} channels · coil type unverified',
            'HPFP':f'{p.hpfp_channels} channels',
            'DBW / EWG':f'{p.dbw_channels} DBW / {p.ewg_channels} EWG',
            'Sensors':f'{p.lambda_channels} lambda / {p.knock_channels} knock',
            'Interfaces':f'{p.can_buses} CAN / SENT / LIN',
            'Connection':'No physical ECU connected', 'Burn/Flash':'Unavailable'}
        if self.project.is_legacy:
            values.update({'Injection':'Legacy 8-cylinder calibration',
                           'Ignition':'Unspecified in legacy file',
                           'DBW / EWG':'Unspecified in legacy file',
                           'Sensors':'Unspecified in legacy file',
                           'Interfaces':'Unspecified in legacy file'})
        for label,value in values.items():
            self.hardware_labels[label].setText(value)
        self.profile_notice.setText(
            'Legacy 8-cylinder project preserved. No conversion to 6 cylinders. '
            'Save writes format v3; use Save as to keep the original file.'
            if self.project.is_legacy else
            '6-cylinder target · hardware validation pending')
        self.simulation_action.setEnabled(not self.project.is_legacy)

    def toggle_simulator(self):
        if self.simulator.connected:
            self._stop_simulator()
            return
        try:
            self.project.validate()
            self.simulator.connect(self.project.profile_id)
        except ValueError as exc:
            QMessageBox.warning(self,'Cannot start simulator',str(exc))
            return
        self.simulation_action.setText('Stop simulator')
        self.simulation_timer.start()
        self.statusBar().showMessage('SIMULATED signals only · physical ECU remains disconnected')

    def _simulation_tick(self):
        sample=self.simulator.step(.2)
        for row,value in enumerate(sample.values):
            self.telemetry.item(row,1).setText(f'{value:.3f}')
        self.simulation_plot.append(sample.simulation_time_s,sample.values[0])

    def _stop_simulator(self):
        self.simulation_timer.stop()
        self.simulator.disconnect()
        self.simulation_action.setText('Start simulator')
        self.simulation_plot.clear()
        for row in range(len(CHANNELS)):
            self.telemetry.item(row,1).setText('—')

    def _rebuild_tree(self):
        self.tree.clear();parents={}
        for name in self.project.tables:
            group,separator,leaf=name.partition(' / ')
            if not separator:group,leaf='Calibration',name
            if group not in parents:
                p=QTreeWidgetItem([group]);self.tree.addTopLevelItem(p);parents[group]=p
            child=QTreeWidgetItem([leaf]);child.setData(0,Qt.ItemDataRole.UserRole,name)
            parents[group].addChild(child)
        self.tree.expandAll()
        self._filter_tree(self.map_search.text())

    def _focus_search(self):
        self.map_search.setFocus()
        self.map_search.selectAll()

    def _filter_tree(self,query):
        terms=query.casefold().split()
        # Filtering only changes navigation visibility, never the active map,
        # selected Z layer, values, or document undo history.
        blocker=QSignalBlocker(self.tree)
        for i in range(self.tree.topLevelItemCount()):
            group=self.tree.topLevelItem(i)
            visible=0
            for j in range(group.childCount()):
                child=group.child(j)
                table=self.project.tables[child.data(0,Qt.ItemDataRole.UserRole)]
                text=' '.join((table.name,table.description,table.x_label,
                               table.y_label,getattr(table,'z_label',''),table.value_unit)).casefold()
                matches=all(term in text for term in terms)
                child.setHidden(not matches)
                visible+=matches
            group.setHidden(visible==0)
        del blocker

    def _tree_clicked(self,item,previous):
        if item is None:return
        name=item.data(0,Qt.ItemDataRole.UserRole)
        if name:self._select_table(name)

    def _select_table(self,name):
        self.active_name=name
        t=self.project.tables[name]
        self.title.setText(name)
        self.desc.setText(t.description)
        blocker=QSignalBlocker(self.layer_selector)
        self.layer_selector.clear()
        is4d=isinstance(t,CalibrationTable4D)
        self.layer_selector.setEnabled(is4d)
        self.layer_label.setVisible(is4d)
        self.layer_selector.setVisible(is4d)
        if is4d:
            self.layer_selector.addItems([f'{t.z_label}: {v:g}' for v in t.z_bins])
        del blocker
        self._render_table()

    def _z_changed(self,index):
        if index >= 0 and self.active_name in self.project.tables:
            self._render_table()

    def _current_z(self, table):
        return max(0,self.layer_selector.currentIndex()) if isinstance(table,CalibrationTable4D) else 0

    @staticmethod
    def _format_value(value):
        # The displayed text is also the delegate's edit buffer. Rounding a
        # higher-precision value here makes Enter silently change calibration.
        return f'{value:.2f}' if value==round(value,2) else repr(value)

    @staticmethod
    def _color(value,low,high):
        f=0.5 if high==low else max(0,min(1,(value-low)/(high-low)))
        # green -> amber -> orange; colors are values, not "good/bad" markers.
        if f<.5:
            s=f*2;return QColor(int(48+160*s),int(160+36*s),int(97-50*s))
        s=(f-.5)*2;return QColor(int(208+36*s),int(196-97*s),int(47-24*s))

    def _render_table(self):
        t=self.project.tables[self.active_name]
        blocker=QSignalBlocker(self.grid)
        self.grid.setRowCount(len(t.y_bins));self.grid.setColumnCount(len(t.x_bins))
        self.grid.setHorizontalHeaderLabels([f'{v:g}' for v in t.x_bins])
        self.grid.setVerticalHeaderLabels([f'{v:g}' for v in t.y_bins])
        z=self._current_z(t)
        rows=t.values[z] if isinstance(t,CalibrationTable4D) else t.values
        for row,vals in enumerate(rows):
            for col,value in enumerate(vals):
                item=QTableWidgetItem(self._format_value(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(self._color(value,t.minimum,t.maximum))
                item.setForeground(QColor('#09121b'))
                item.setToolTip(f'{t.x_label}: {t.x_bins[col]:g}\n{t.y_label}: {t.y_bins[row]:g}\nRange: {t.minimum:g}..{t.maximum:g}')
                self.grid.setItem(row,col,item)
        del blocker
        extra=(f'    |    Z: {t.z_label} = {t.z_bins[z]:g} (layer {z+1}/{len(t.z_bins)})'
               if isinstance(t,CalibrationTable4D) else '')
        self.meta.setText(f'X: {t.x_label}    |    Y: {t.y_label}{extra}    |    Unit: {t.value_unit}    |    {len(t.y_bins)} × {len(t.x_bins)}')
        self.interp.setText('SAFETY PARAMETER' if t.safety_class=='safety_critical' else 'OFFLINE MAP')

    def _item_changed(self,item):
        if self._in_update:return
        name=self.active_name;t=self.project.tables[name]
        x=item.column();y=item.row();z=self._current_z(t)
        old=t.values[z][y][x] if isinstance(t,CalibrationTable4D) else t.values[y][x]
        try:
            value=float(item.text())
            # Validate through the model without mutating until an undo command exists.
            if not (t.minimum<=value<=t.maximum) or not __import__('math').isfinite(value):
                raise ValueError('Value out of range')
        except (TypeError,ValueError):
            QMessageBox.warning(self,'Invalid value',f'Allowed range: {t.minimum:g}..{t.maximum:g}')
            self._render_table();return
        if old!=value:self.undo_stack.push(CellEdit(self,name,x,y,z,old,value))

    def _set_cell(self,name,x,y,z,value):
        t=self.project.tables[name]
        if isinstance(t,CalibrationTable4D):
            t.set_value(x,y,z,value)
        else:
            t.set_value(x,y,value)
        # An undo can target a layer that is no longer visible: don't paint
        # its values on the currently selected layer or another table.
        if name==self.active_name and z==self._current_z(t):
            self._in_update=True
            try:
                item=self.grid.item(y,x)
                if item:
                    item.setText(self._format_value(value))
                    item.setBackground(self._color(value,t.minimum,t.maximum))
            finally:
                self._in_update=False
        self.statusBar().showMessage(f'Edited {name} [Z={z}, Y={y}, X={x}] = {value:g} {t.value_unit} · OFFLINE',6000)

    def _clean_changed(self,clean):
        self.setWindowModified(not clean)

    def _update_window_title(self):
        label=self.path.name if self.path else 'Untitled'
        self.setWindowTitle(f'{label}[*] — R2 ECU Studio  •  OFFLINE')

    def _finish_cell_edit(self):
        # File actions can run via a shortcut while a delegate still holds text
        # that has not reached itemChanged/the undo stack. Moving focus commits
        # it through Qt's normal delegate validation before save or discard.
        focus=self.focusWidget()
        if focus is not None and self.grid.isAncestorOf(focus):
            self.grid.setFocus(Qt.FocusReason.OtherFocusReason)

    def _confirm_discard(self):
        self._finish_cell_edit()
        if self.undo_stack.isClean():return True
        choice=QMessageBox.warning(
            self,'Unsaved changes','Save changes to the current project?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
        if choice==QMessageBox.StandardButton.Save:return self.save_project()
        return choice==QMessageBox.StandardButton.Discard

    def new_project(self):
        if not self._confirm_discard():return False
        self._stop_simulator()
        self.project=default_project();self.path=None;self.undo_stack.clear()
        self._refresh_profile()
        self._rebuild_tree();self._select_table('Boost / Target')
        self._update_window_title()
        self.statusBar().showMessage('New offline project',7000)
        return True

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open project','','R2 ECU projects (*.json);;All files (*)')
        if not path:return False
        if not self._confirm_discard():return False
        try:
            p=CalibrationProject.load(path)
            if not p.tables:raise ValueError('Project contains no calibration tables')
            if any(not isinstance(t.description,str) for t in p.tables.values()):
                raise ValueError('Table descriptions must be text')
        except (ValueError,KeyError,OSError,TypeError) as exc:
            QMessageBox.critical(self,'Cannot load',str(exc));return False
        self._stop_simulator()
        self.project=p;self.path=Path(path);self.undo_stack.clear()
        self._refresh_profile()
        self._rebuild_tree();self._select_table(next(iter(p.tables)))
        self._update_window_title()
        self.statusBar().showMessage('Loaded '+path,7000)
        return True

    def save_project(self):
        self._finish_cell_edit()
        if self.path is None:return self.save_as()
        return self._save_to(self.path)

    def _save_to(self,path):
        try:self.project.save(path)
        except (OSError,ValueError) as exc:
            QMessageBox.critical(self,'Cannot save',str(exc));return False
        self.path=Path(path)
        self.undo_stack.setClean()
        self._update_window_title()
        self.statusBar().showMessage('Saved '+str(self.path),7000)
        return True

    def save_as(self):
        self._finish_cell_edit()
        filename='Power8GDI_Legacy.json' if self.project.is_legacy else 'SportGDI6_Project.json'
        path,_=QFileDialog.getSaveFileName(self,'Save project',filename,'R2 ECU projects (*.json)')
        if not path:return False
        return self._save_to(Path(path))

    def closeEvent(self,event):
        if self._confirm_discard():
            self._stop_simulator()
            event.accept()
        else:event.ignore()

    def offline_notice(self):
        QMessageBox.information(self,'Connection unavailable',
             'This revision is an OFFLINE calibration editor.\n'
             'No supported ECU protocol is implemented, and no data can be flashed.\n'
             'Hardware control will only be enabled after protocol and safety tests.')


def main(argv=None):
    argv=sys.argv if argv is None else argv
    app=QApplication(argv);app.setApplicationName('R2 ECU Studio')
    window=MainWindow();window.show()
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
