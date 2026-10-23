"""Navigation filtering must not change calibration or layer identity."""
from test_app import window, qapp, dialogs, type_cell  # shared real-widget fixtures


def visible_names(window):
    names=[]
    for i in range(window.tree.topLevelItemCount()):
        group=window.tree.topLevelItem(i)
        if not group.isHidden():
            names.extend(group.text(0)+' / '+group.child(j).text(0)
                         for j in range(group.childCount()) if not group.child(j).isHidden())
    return names


def test_search_name_axis_and_unit(window):
    window.map_search.setText('ETHANOL RPM')
    assert visible_names(window)==['Ignition / Ethanol 4D']
    window.map_search.setText('kPa abs')
    assert 'Boost / Target' in visible_names(window)
    window.map_search.clear()
    assert len(visible_names(window))==len(window.project.tables)


def test_search_preserves_edited_layer_and_undo(window):
    window._select_table('Ignition / Ethanol 4D')
    window.layer_selector.setCurrentIndex(2)
    old=window.project.tables[window.active_name].values[2][0][0]
    type_cell(window,old+1)
    snapshot=window.project.to_dict()
    window.map_search.setText('no matching calibration map')
    assert visible_names(window)==[]
    assert window.active_name=='Ignition / Ethanol 4D'
    assert window.layer_selector.currentIndex()==2
    assert window.project.to_dict()==snapshot
    assert not window.undo_stack.isClean()
    window.undo_stack.undo()
    assert window.project.tables[window.active_name].values[2][0][0]==old
    window.map_search.clear()
    assert window.undo_stack.isClean()
