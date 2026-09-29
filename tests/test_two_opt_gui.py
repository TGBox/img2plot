import pytest
from PySide6.QtWidgets import QApplication

from img2plot.gui.sidebar import SidebarWidget
from img2plot.core.parameters import PlotParameters


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_two_opt_checkbox_hidden_and_disabled_by_default(app):
    sidebar = SidebarWidget()
    assert sidebar.chk_tsp.isChecked() is False
    assert sidebar.chk_two_opt.isEnabled() is False
    assert sidebar.chk_two_opt.isVisibleTo(sidebar) is False


def test_two_opt_checkbox_enabled_only_when_tsp_active(app):
    sidebar = SidebarWidget()

    sidebar.chk_tsp.setChecked(True)
    assert sidebar.chk_two_opt.isEnabled() is True
    assert sidebar.chk_two_opt.isVisibleTo(sidebar) is True

    sidebar.chk_two_opt.setChecked(True)
    sidebar.chk_tsp.setChecked(False)

    # disabling sort_paths must also force two_opt off again
    assert sidebar.chk_two_opt.isChecked() is False
    assert sidebar.chk_two_opt.isEnabled() is False
    assert sidebar.chk_two_opt.isVisibleTo(sidebar) is False


def test_get_current_parameters_never_sets_two_opt_without_sort_paths(app):
    """Defensive: even if the checkbox state were somehow left stale
    (e.g. programmatic manipulation), get_current_parameters must not
    report two_opt=True while sort_paths=False."""
    sidebar = SidebarWidget()

    sidebar.chk_tsp.setChecked(True)
    sidebar.chk_two_opt.setChecked(True)
    params = sidebar.get_current_parameters()
    assert params.sort_paths is True
    assert params.two_opt is True

    # force an inconsistent widget state directly, bypassing the toggle handler
    sidebar.chk_tsp.blockSignals(True)
    sidebar.chk_tsp.setChecked(False)
    sidebar.chk_tsp.blockSignals(False)

    params = sidebar.get_current_parameters()
    assert params.sort_paths is False
    assert params.two_opt is False


def test_apply_parameters_restores_two_opt_visibility(app):
    sidebar = SidebarWidget()
    p = PlotParameters(sort_paths=True, two_opt=True)

    sidebar.apply_parameters(p)

    assert sidebar.chk_tsp.isChecked() is True
    assert sidebar.chk_two_opt.isChecked() is True
    assert sidebar.chk_two_opt.isEnabled() is True
    assert sidebar.chk_two_opt.isVisibleTo(sidebar) is True

    p_off = PlotParameters(sort_paths=False, two_opt=False)
    sidebar.apply_parameters(p_off)

    assert sidebar.chk_tsp.isChecked() is False
    assert sidebar.chk_two_opt.isChecked() is False
    assert sidebar.chk_two_opt.isEnabled() is False
    assert sidebar.chk_two_opt.isVisibleTo(sidebar) is False