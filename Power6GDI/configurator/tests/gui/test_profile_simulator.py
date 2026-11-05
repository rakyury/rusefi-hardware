import json
from test_app import window, qapp, dialogs, choose_open, choose_save
from PyQt6.QtWidgets import QAbstractItemView, QInputDialog, QFileDialog

from power8gdi_configurator.app import CANPreviewDialog
from power8gdi_configurator.can_preview import CANPreview, CANSignalPreview
from power8gdi_configurator.project import CalibrationProject


def test_simulation_is_read_only_bounded_and_stops_on_new(window):
    before = window.project.to_dict()
    assert '6 DI / 6 PI' in window.hardware_labels['Injection'].text()
    assert '1 DBW / 1 EWG' in window.hardware_labels['DBW / EWG'].text()
    window.toggle_simulator()
    window.simulation_timer.stop()  # use deterministic event ticks for this test
    for _ in range(150):
        window._simulation_tick()
    assert len(window.simulation_plot.samples) == 120
    assert window.telemetry.item(0, 1).text() != '—'
    assert window.project.to_dict() == before
    assert window.undo_stack.isClean()
    assert 'No physical ECU' in window.hardware_labels['Connection'].text()
    window.new_project()
    assert not window.simulator.connected
    assert not window.simulation_timer.isActive()
    assert not window.simulation_plot.samples
    assert window.telemetry.item(0, 1).text() == '—'


def test_legacy_open_stop_simulator_save_retains_eight_and_maps(window, monkeypatch, tmp_path):
    original = window.project.to_dict()
    original.update(format_version=2, cylinders=8, name='Existing legacy V8')
    original.pop('profile_id')
    original.pop('imported_format_version')
    old = tmp_path / 'old.json'
    old.write_text(json.dumps(original), encoding='utf-8')
    window.toggle_simulator()
    choose_open(monkeypatch, old)
    window.open_project()
    assert not window.simulator.connected
    assert window.project.is_legacy
    assert window.project.cylinders == 8
    assert 'LEGACY' in window.brand.text()
    assert not window.simulation_action.isEnabled()
    assert 'No conversion' in window.profile_notice.text()
    assert 'Unspecified' in window.hardware_labels['Sensors'].text()
    new = tmp_path / 'legacy-v3.json'
    choose_save(monkeypatch, new)
    window.save_as()
    restored = CalibrationProject.load(new)
    assert restored.cylinders == 8
    assert restored.to_dict()['tables'] == original['tables']
    assert json.loads(old.read_text(encoding='utf-8')) == original
    window.new_project()
    assert window.simulation_action.isEnabled()
    assert window.project.cylinders == 6


def test_invalid_open_leaves_simulator_and_project_intact(window, monkeypatch, tmp_path):
    invalid = tmp_path / 'invalid.json'
    invalid.write_text('{}', encoding='utf-8')
    original = window.project
    window.toggle_simulator()
    choose_open(monkeypatch, invalid)
    window.open_project()
    assert window.simulator.connected
    assert window.project is original


def test_can_preview_dialog_is_read_only_and_displays_warnings(window):
    before = window.project.to_dict()
    preview = CANPreview('test.dbc', (CANSignalPreview(
        'RPM', 'Engine', 'CAN2', '0x600 (11 bit)', 'rpm', 'raw × 1/1 + 0', False),),
        ('PREVIEW ONLY', 'Example skipped signal'))
    dialog = CANPreviewDialog(preview, window)
    assert dialog.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert dialog.table.item(0, 2).text() == 'CAN2'
    assert 'Example skipped' in dialog.warnings.toPlainText()
    assert window.project.to_dict() == before
    dialog.close()


def test_can_preview_bus_cancel_does_not_read_or_change_project(window, monkeypatch):
    before = window.project.to_dict()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('missing.dbc', ''))
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *a: ('CAN1', False))
    window.preview_can_definitions()
    assert window.project.to_dict() == before
