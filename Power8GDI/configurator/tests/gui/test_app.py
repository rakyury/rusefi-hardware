"""Real Qt widget/delegate regressions; no ECU, display server or pytest-qt needed."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox

from power8gdi_configurator.app import MainWindow
from power8gdi_configurator.project import CalibrationProject, default_project


BUTTON = QMessageBox.StandardButton
MAP = 'Boost / Target'
MAP4D = 'Ignition / Ethanol 4D'


@pytest.fixture(scope='session')
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def dialogs(monkeypatch):
    calls = []

    def warning(parent, title, message, *args):
        calls.append(('warning', title, message))
        return BUTTON.Cancel

    def critical(parent, title, message, *args):
        calls.append(('critical', title, message))
        return BUTTON.Ok

    monkeypatch.setattr(QMessageBox, 'warning', warning)
    monkeypatch.setattr(QMessageBox, 'critical', critical)
    return calls


@pytest.fixture
def window(qapp, dialogs):
    result = MainWindow()
    result.show()
    result.activateWindow()
    qapp.processEvents()
    yield result
    result.undo_stack.clear()
    result.close()
    result.deleteLater()
    qapp.processEvents()


def type_cell(window, text, row=0, column=0, commit=True):
    """Type through QTableWidget's actual delegate, including its commit signal."""
    window.grid.setFocus()
    item = window.grid.item(row, column)
    window.grid.setCurrentItem(item)
    window.grid.editItem(item)
    QApplication.processEvents()
    editor = window.grid.findChild(QLineEdit)
    assert editor is not None
    editor.selectAll()
    QTest.keyClicks(editor, str(text))
    if commit:
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QApplication.processEvents()
    return editor


def choose_save(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(path), ''))


def choose_open(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))


def answer_unsaved(monkeypatch, answer):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: answer)


def assert_clean(window, clean):
    assert window.undo_stack.isClean() is clean
    assert window.isWindowModified() is (not clean)


def test_z_layer_edits_undo_redo_preserve_hidden_layer_and_table(window):
    window._select_table(MAP4D)
    table = window.project.tables[MAP4D]
    window.layer_selector.setCurrentIndex(2)
    type_cell(window, 17.25, row=1, column=2)
    assert table.values[2][1][2] == 17.25
    assert table.values[0][1][2] == 5
    assert_clean(window, False)

    window.layer_selector.setCurrentIndex(0)
    window.undo_action.trigger()
    assert table.values[2][1][2] == 5
    assert window.grid.item(1, 2).text() == '5.00'
    assert_clean(window, True)
    window.redo_action.trigger()
    assert table.values[2][1][2] == 17.25
    assert window.grid.item(1, 2).text() == '5.00'

    window._select_table(MAP)
    window.undo_action.trigger()
    assert table.values[2][1][2] == 5
    assert window.grid.item(1, 2).text() == '100.00'
    window.redo_action.trigger()
    assert table.values[2][1][2] == 17.25
    assert window.grid.item(1, 2).text() == '100.00'
    window._select_table(MAP4D)
    window.layer_selector.setCurrentIndex(2)
    assert window.grid.item(1, 2).text() == '17.25'


def test_clean_checkpoint_follows_undo_and_redo(window, monkeypatch, tmp_path):
    path = tmp_path / 'checkpoint.json'
    choose_save(monkeypatch, path)
    assert_clean(window, True)
    assert not window.undo_action.isEnabled()
    assert not window.redo_action.isEnabled()
    type_cell(window, 123)
    assert window.undo_action.isEnabled()
    assert window.save_project() is True
    assert_clean(window, True)
    assert path.name in window.windowTitle()
    assert '[*]' in window.windowTitle()
    type_cell(window, 124)
    assert_clean(window, False)
    window.undo_action.trigger()
    assert_clean(window, True)
    window.undo_action.trigger()
    assert_clean(window, False)
    window.redo_action.trigger()
    assert_clean(window, True)
    window.redo_action.trigger()
    assert_clean(window, False)


@pytest.mark.parametrize('value', ['nan', 'inf', '-1', '401', 'invalid'])
def test_invalid_delegate_input_preserves_model_and_history(window, dialogs, value):
    type_cell(window, value)
    assert window.project.tables[MAP].values[0][0] == 100
    assert window.grid.item(0, 0).text() == '100.00'
    assert window.undo_stack.count() == 0
    assert_clean(window, True)
    assert dialogs[0][:2] == ('warning', 'Invalid value')


def test_identical_value_does_not_dirty_document(window):
    type_cell(window, 100)
    assert window.undo_stack.count() == 0
    assert_clean(window, True)


@pytest.mark.parametrize('operation', ['new_project', 'open_project', 'close'])
@pytest.mark.parametrize('answer', [BUTTON.Save, BUTTON.Discard, BUTTON.Cancel])
def test_unsaved_lifecycle(window, monkeypatch, tmp_path, operation, answer):
    original = window.project
    saved = tmp_path / 'saved.json'
    target = tmp_path / 'opened.json'
    incoming = default_project()
    incoming.tables[MAP].values[0][0] = 222
    incoming.save(target)
    choose_save(monkeypatch, saved)
    choose_open(monkeypatch, target)
    answer_unsaved(monkeypatch, answer)
    type_cell(window, 123)

    assert getattr(window, operation)() is (answer != BUTTON.Cancel)
    if answer == BUTTON.Cancel:
        assert window.project is original
        assert window.project.tables[MAP].values[0][0] == 123
        assert window.path is None
        assert window.isVisible()
        assert_clean(window, False)
    elif operation != 'close':
        assert window.project is not original
        assert window.project.tables[MAP].values[0][0] == (222 if operation == 'open_project' else 100)
        assert_clean(window, True)
        assert window.undo_stack.count() == 0
        assert window.path == (target if operation == 'open_project' else None)
    else:
        assert not window.isVisible()
    assert saved.exists() is (answer == BUTTON.Save)
    if saved.exists():
        assert CalibrationProject.load(saved).tables[MAP].values[0][0] == 123


@pytest.mark.parametrize('operation', ['new_project', 'open_project', 'close'])
def test_cancelled_save_as_blocks_destructive_action(window, monkeypatch, tmp_path, operation):
    target = tmp_path / 'opened.json'
    default_project().save(target)
    choose_open(monkeypatch, target)
    choose_save(monkeypatch, '')
    answer_unsaved(monkeypatch, BUTTON.Save)
    original = window.project
    type_cell(window, 123)
    assert getattr(window, operation)() is False
    assert window.project is original
    assert window.path is None
    assert window.isVisible()
    assert_clean(window, False)


def test_failed_save_as_keeps_active_path_and_clean_checkpoint(window, monkeypatch, tmp_path, dialogs):
    original_path = tmp_path / 'original.json'
    choose_save(monkeypatch, original_path)
    assert window.save_project()
    old_bytes = original_path.read_bytes()
    type_cell(window, 123)
    title = window.windowTitle()
    # A directory is a deterministic invalid file target on all supported OSes.
    failed_target = tmp_path / 'destination-directory'
    failed_target.mkdir()
    choose_save(monkeypatch, failed_target)
    assert window.save_as() is False
    assert window.path == original_path
    assert window.windowTitle() == title
    assert original_path.read_bytes() == old_bytes
    assert dialogs[-1][:2] == ('critical', 'Cannot save')
    assert_clean(window, False)
    window.undo_stack.undo()
    assert_clean(window, True)


@pytest.mark.parametrize('operation', ['new_project', 'open_project', 'close'])
def test_failed_save_blocks_destructive_action(window, monkeypatch, tmp_path, operation, dialogs):
    target = tmp_path / 'opened.json'
    default_project().save(target)
    choose_open(monkeypatch, target)
    choose_save(monkeypatch, tmp_path)
    answer_unsaved(monkeypatch, BUTTON.Save)
    original = window.project
    type_cell(window, 123)
    assert getattr(window, operation)() is False
    assert window.project is original
    assert window.path is None
    assert window.isVisible()
    assert_clean(window, False)
    assert dialogs[-1][:2] == ('critical', 'Cannot save')


@pytest.mark.parametrize('content', ['invalid JSON', '{"format_version":2,"name":"Empty","cylinders":8,"pumps":2,"tables":{}}'])
def test_invalid_open_preserves_document_path_and_history(window, monkeypatch, tmp_path, dialogs, content):
    target = tmp_path / 'invalid.json'
    target.write_text(content, encoding='utf-8')
    choose_open(monkeypatch, target)
    answer_unsaved(monkeypatch, BUTTON.Discard)
    original = window.project
    type_cell(window, 123)
    assert window.open_project() is False
    assert window.project is original
    assert window.path is None
    assert window.undo_stack.canUndo()
    assert_clean(window, False)
    assert dialogs[-1][:2] == ('critical', 'Cannot load')


def test_open_same_file_after_save_uses_saved_values(window, monkeypatch, tmp_path):
    path = tmp_path / 'same-file.json'
    choose_save(monkeypatch, path)
    assert window.save_project()
    type_cell(window, 123)
    choose_open(monkeypatch, path)
    answer_unsaved(monkeypatch, BUTTON.Save)
    assert window.open_project()
    assert window.project.tables[MAP].values[0][0] == 123
    assert_clean(window, True)


def test_custom_ungrouped_table_opens_and_keyboard_tree_selection_works(window, monkeypatch, tmp_path):
    project = default_project()
    custom = project.tables.pop(MAP)
    custom.name = 'Custom boost'
    project.tables = {'Custom boost': custom, 'Ignition / Ethanol 4D': project.tables[MAP4D]}
    target = tmp_path / 'custom.json'
    project.save(target)
    choose_open(monkeypatch, target)
    assert window.open_project()
    assert window.active_name == 'Custom boost'
    assert window.tree.topLevelItem(0).text(0) == 'Calibration'
    window.tree.setCurrentItem(window.tree.topLevelItem(1))
    window.tree.setFocus()
    QTest.keyClick(window.tree, Qt.Key.Key_Down)
    assert window.active_name == MAP4D
    assert window.layer_selector.isEnabled()


def test_ctrl_s_commits_active_cell_editor(window, monkeypatch, tmp_path):
    target = tmp_path / 'active-editor.json'
    choose_save(monkeypatch, target)
    editor = type_cell(window, 123.75, commit=False)
    assert window.project.tables[MAP].values[0][0] == 100
    QTest.keyClick(editor, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    assert target.exists()
    assert CalibrationProject.load(target).tables[MAP].values[0][0] == 123.75
    assert_clean(window, True)


def test_new_commits_active_editor_before_unsaved_prompt(window, monkeypatch):
    answer_unsaved(monkeypatch, BUTTON.Cancel)
    type_cell(window, 123.75, commit=False)
    assert window.new_project() is False
    assert window.project.tables[MAP].values[0][0] == 123.75
    assert_clean(window, False)


@pytest.mark.parametrize('value', [123.45678901234567, 0.000000123456789])
def test_reopening_delegate_without_changes_preserves_precision(window, value):
    type_cell(window, value)
    count = window.undo_stack.count()
    window.grid.editItem(window.grid.item(0, 0))
    QApplication.processEvents()
    editor = window.grid.findChild(QLineEdit)
    assert float(editor.text()) == value
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert window.project.tables[MAP].values[0][0] == value
    assert window.undo_stack.count() == count
    window._select_table('Fuel / VE')
    window._select_table(MAP)
    assert float(window.grid.item(0, 0).text()) == value


def test_edit_after_undo_removes_unreachable_saved_checkpoint(window, monkeypatch, tmp_path):
    choose_save(monkeypatch, tmp_path / 'checkpoint.json')
    type_cell(window, 123)
    assert window.save_project()
    window.undo_stack.undo()
    type_cell(window, 125)
    assert window.undo_stack.cleanIndex() == -1
    assert not window.redo_action.isEnabled()
    window.undo_stack.undo()
    assert_clean(window, False)


def test_clean_document_never_prompts_on_new_or_close(window, dialogs):
    assert window.new_project()
    assert window.close()
    assert dialogs == []


def test_open_dialog_cancel_preserves_dirty_document(window, monkeypatch, dialogs):
    choose_open(monkeypatch, '')
    type_cell(window, 123)
    original = window.project
    assert window.open_project() is False
    assert window.project is original
    assert_clean(window, False)
    assert dialogs == []


def test_invalid_description_open_preserves_active_document(window, monkeypatch, tmp_path, dialogs):
    incoming = default_project().to_dict()
    incoming['tables'][MAP]['description'] = 123
    target = tmp_path / 'invalid-description.json'
    target.write_text(json.dumps(incoming), encoding='utf-8')
    choose_open(monkeypatch, target)
    original = window.project
    assert window.open_project() is False
    assert window.project is original
    assert window.path is None
    assert dialogs[-1][:2] == ('critical', 'Cannot load')
