"""Power8GDI desktop editor in the visual spirit of EMU Pro / R2 Racing Dash.

This is offline software: no connection, burn, engine control or ECU protocol
is implied by its windows or by edits made to JSON calibration documents.
"""
from __future__ import annotations
import sys
from pathlib import Path
from .project import default_project,CalibrationProject,CalibrationTable4D

try:
    from PyQt6.QtCore import Qt,QSignalBlocker
    from PyQt6.QtGui import QColor,QAction,QKeySequence,QUndoCommand,QUndoStack
    from PyQt6.QtWidgets import (
       QApplication,QMainWindow,QWidget,QSplitter,QTreeWidget,QTreeWidgetItem,
       QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,
       QToolBar,QFileDialog,QMessageBox,QStatusBar,QPushButton,QFrame,
       QAbstractItemView,QLineEdit,QHeaderView,QComboBox)
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project=default_project();self.path:Path|None=None
        self.active_name='Boost / Target';self._in_update=False
        self.undo_stack=QUndoStack(self)
        self.setWindowTitle('R2 Power8GDI Configurator  •  OFFLINE')
        self.resize(1520,910)
        self.setStyleSheet(STYLE)
        self._init_ui()
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
        action('Undo',self.undo_stack.undo,'Ctrl+Z')
        action('Redo',self.undo_stack.redo,'Ctrl+Y')
        toolbar.addSeparator()
        off=action('ECU: disconnected',self.offline_notice)
        off.setEnabled(True)

        split=QSplitter(Qt.Orientation.Horizontal);split.setChildrenCollapsible(False)
        left=QWidget();lv=QVBoxLayout(left);lv.setContentsMargins(10,18,10,10)
        brand=QLabel('POWER8GDI');brand.setObjectName('headline');lv.addWidget(brand)
        desc=QLabel('ECU CALIBRATION STUDIO');desc.setObjectName('muted');lv.addWidget(desc)
        lv.addSpacing(14)
        tree_label=QLabel('CALIBRATION TREE');tree_label.setObjectName('section')
        lv.addWidget(tree_label)
        self.tree=QTreeWidget();self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._tree_clicked)
        self.tree.setIndentation(15)
        lv.addWidget(self.tree)
        note=QLabel('Prototype editor · no ECU connection')
        note.setObjectName('warning');note.setWordWrap(True);lv.addWidget(note)
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
        io=QLabel('HARDWARE STATUS');io.setObjectName('section');rv.addWidget(io)
        for label,value in (
          ('Controller','Power8GDI Rev A'),('MCU','STM32F7 target'),
          ('Injection','8 DI / 8 PI provision'),('Ignition','8 smart coils'),
          ('HPFP','2 channels'),('Knock','2 sensors (planned)'),
          ('ETB / EWG','2 independent bridges'),('Connection','Not connected'),
          ('Burn/Flash','Unavailable'),('Live telemetry','Unavailable')):
            item=QWidget();iv=QVBoxLayout(item);iv.setContentsMargins(0,8,0,5)
            head=QLabel(label.upper());head.setObjectName('muted');iv.addWidget(head)
            val=QLabel(value);val.setWordWrap(True);iv.addWidget(val)
            rv.addWidget(item)
        rv.addStretch(1)
        self.note=QLabel('WARNING: sample tables are not validated engine calibrations.')
        self.note.setObjectName('warning');self.note.setWordWrap(True);rv.addWidget(self.note)
        split.addWidget(right)
        split.setSizes([285,1030,215]);self.setCentralWidget(split)
        status=QStatusBar();self.setStatusBar(status)
        self.statusBar().showMessage('No ECU connection · documents are stored locally as versioned JSON')

    def _rebuild_tree(self):
        self.tree.clear();parents={}
        for name in self.project.tables:
            group,leaf=name.split(' / ',1)
            if group not in parents:
                p=QTreeWidgetItem([group]);self.tree.addTopLevelItem(p);parents[group]=p
            child=QTreeWidgetItem([leaf]);child.setData(0,Qt.ItemDataRole.UserRole,name)
            parents[group].addChild(child)
        self.tree.expandAll()

    def _tree_clicked(self,item,column):
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
                item=QTableWidgetItem(f'{value:.2f}')
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
                    item.setText(f'{value:.2f}')
                    item.setBackground(self._color(value,t.minimum,t.maximum))
            finally:
                self._in_update=False
        self.setWindowModified(True)
        self.statusBar().showMessage(f'Edited {name} [Z={z}, Y={y}, X={x}] = {value:g} {t.value_unit} · OFFLINE',6000)

    def new_project(self):
        self.project=default_project();self.path=None;self.undo_stack.clear()
        self._rebuild_tree();self._select_table('Boost / Target')
        self.setWindowModified(False)

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open project','','Power8GDI (*.json);;All files (*)')
        if not path:return
        try:
            p=CalibrationProject.load(path)
        except (ValueError,KeyError,OSError,TypeError) as exc:
            QMessageBox.critical(self,'Cannot load',str(exc));return
        self.project=p;self.path=Path(path);self.undo_stack.clear()
        self._rebuild_tree();self._select_table(next(iter(p.tables)))
        self.setWindowModified(False)
        self.statusBar().showMessage('Loaded '+path,7000)

    def save_project(self):
        if self.path is None:return self.save_as()
        try:self.project.save(self.path)
        except (OSError,ValueError) as exc:
            QMessageBox.critical(self,'Cannot save',str(exc));return
        self.setWindowModified(False)
        self.statusBar().showMessage('Saved '+str(self.path),7000)

    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'Save project','Power8GDI_Reference.p8gdi.json','Power8GDI (*.json)')
        if path:self.path=Path(path);self.save_project()

    def offline_notice(self):
        QMessageBox.information(self,'Connection unavailable',
             'This revision is an OFFLINE calibration editor.\n'
             'No supported ECU protocol is implemented, and no data can be flashed.\n'
             'Hardware control will only be enabled after protocol and safety tests.')


def main(argv=None):
    argv=sys.argv if argv is None else argv
    app=QApplication(argv);app.setApplicationName('R2 Power8GDI Configurator')
    window=MainWindow();window.show()
    return app.exec()

if __name__=='__main__':raise SystemExit(main())
