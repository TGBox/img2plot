"""
Tests for the reorganized tabbed sidebar and pinned sticky footer progress bar.
"""

import pytest
from PySide6.QtCore import Qt
from img2plot.gui.sidebar import SidebarWidget
from img2plot.core.parameters import PlotParameters


def test_sidebar_tab_structure(app):
    sidebar = SidebarWidget()
    assert hasattr(sidebar, "tab_widget")
    assert sidebar.tab_widget.count() == 4

    # Check tab titles
    tab_titles = [sidebar.tab_widget.tabText(i) for i in range(4)]
    assert "🎨 Stile" in tab_titles[0]
    assert "✏️ Schraffur" in tab_titles[1]
    assert "🧪 Filter" in tab_titles[2]
    assert "📐 Plotter" in tab_titles[3]


def test_sticky_footer_elements(app):
    sidebar = SidebarWidget()

    # Sticky footer components must exist on sidebar
    assert hasattr(sidebar, "lbl_status")
    assert hasattr(sidebar, "lbl_percent")
    assert hasattr(sidebar, "progress_bar")
    assert hasattr(sidebar, "btn_calc")
    assert hasattr(sidebar, "btn_cancel")
    assert hasattr(sidebar, "btn_randomize_top")

    # Initial state
    assert sidebar.lbl_status.text() == "Bereit"
    assert sidebar.lbl_percent.text() == "0%"
    assert sidebar.progress_bar.value() == 0
    assert sidebar.btn_calc.isEnabled() is True
    assert sidebar.btn_cancel.isEnabled() is False

    # Progress update
    sidebar.set_progress(0.45, "Berechne Schraffur...")
    assert sidebar.progress_bar.value() == 45
    assert sidebar.lbl_percent.text() == "45%"
    assert sidebar.lbl_status.text() == "Berechne Schraffur..."

    # Computing state
    sidebar.set_computing_state(True)
    assert sidebar.btn_calc.isEnabled() is False
    assert sidebar.btn_cancel.isEnabled() is True

    sidebar.set_computing_state(False)
    assert sidebar.btn_calc.isEnabled() is True
    assert sidebar.btn_cancel.isEnabled() is False
    assert sidebar.progress_bar.value() == 100
    assert sidebar.lbl_percent.text() == "100%"


def test_tab_active_badges(app):
    sidebar = SidebarWidget()

    # Initially no dot badges
    assert "•" not in sidebar.tab_widget.tabText(0)
    assert "•" not in sidebar.tab_widget.tabText(1)
    assert "•" not in sidebar.tab_widget.tabText(2)
    assert "•" not in sidebar.tab_widget.tabText(3)

    # Activate artistic mode (Joy division / waveform)
    sidebar.combo_artistic_mode.setCurrentIndex(1)
    assert "•" in sidebar.tab_widget.tabText(0)

    # Deactivate artistic mode
    sidebar.combo_artistic_mode.setCurrentIndex(0)
    assert "•" not in sidebar.tab_widget.tabText(0)

    # Activate hatching
    sidebar.chk_hatching.setChecked(True)
    assert "•" in sidebar.tab_widget.tabText(1)

    sidebar.chk_hatching.setChecked(False)
    assert "•" not in sidebar.tab_widget.tabText(1)

    # Activate Kuwahara
    sidebar.chk_kuwahara.setChecked(True)
    assert "•" in sidebar.tab_widget.tabText(2)

    sidebar.chk_kuwahara.setChecked(False)
    assert "•" not in sidebar.tab_widget.tabText(2)

    # Activate TSP sort
    sidebar.chk_tsp.setChecked(True)
    assert "•" in sidebar.tab_widget.tabText(3)


def test_preset_auto_tab_focus(app):
    sidebar = SidebarWidget()

    # Spiral preset switches to Tab 0 (Stile)
    sidebar._on_preset_selected("Archimedische Spirale (1-Linie)")
    assert sidebar.tab_widget.currentIndex() == 0

    # Hatching preset switches to Tab 1 (Schraffur)
    sidebar._on_preset_selected("Klassische Gravur (Schraffur)")
    assert sidebar.tab_widget.currentIndex() == 1

    # Kuwahara preset switches to Tab 2 (Filter)
    sidebar._on_preset_selected("Malerisches Ölgemälde (Kuwahara)")
    assert sidebar.tab_widget.currentIndex() == 2

