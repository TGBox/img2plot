"""
Tests for the reorganized Accordion sidebar, progressive disclosure, and pinned sticky footer.
"""

import pytest
from PySide6.QtCore import Qt
from img2plot.gui.sidebar import SidebarWidget
from img2plot.core.parameters import PlotParameters


def test_sidebar_accordion_structure(app):
    sidebar = SidebarWidget()
    assert hasattr(sidebar, "acc_filter")
    assert hasattr(sidebar, "acc_artistic")
    assert hasattr(sidebar, "acc_contours")
    assert hasattr(sidebar, "acc_plotter")

    # Initial expanded states
    assert sidebar.acc_filter.is_expanded() is False
    assert sidebar.acc_artistic.is_expanded() is True
    assert sidebar.acc_contours.is_expanded() is True
    assert sidebar.acc_plotter.is_expanded() is False

    # Check titles
    assert "Filter" in sidebar.acc_filter._title
    assert "Künstlerische Stile" in sidebar.acc_artistic._title
    assert "Konturen" in sidebar.acc_contours._title
    assert "Plotter" in sidebar.acc_plotter._title

    # Toggling single section
    sidebar.acc_filter.toggle()
    assert sidebar.acc_filter.is_expanded() is True
    sidebar.acc_filter.toggle()
    assert sidebar.acc_filter.is_expanded() is False


def test_sections_toolbar_expand_and_collapse_all(app):
    sidebar = SidebarWidget()
    assert hasattr(sidebar, "btn_expand_all")
    assert hasattr(sidebar, "btn_collapse_all")

    # Collapse all
    sidebar.btn_collapse_all.click()
    assert sidebar.acc_filter.is_expanded() is False
    assert sidebar.acc_artistic.is_expanded() is False
    assert sidebar.acc_contours.is_expanded() is False
    assert sidebar.acc_plotter.is_expanded() is False

    # Expand all
    sidebar.btn_expand_all.click()
    assert sidebar.acc_filter.is_expanded() is True
    assert sidebar.acc_artistic.is_expanded() is True
    assert sidebar.acc_contours.is_expanded() is True
    assert sidebar.acc_plotter.is_expanded() is True


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


def test_accordion_dynamic_badges(app):
    sidebar = SidebarWidget()

    # Initial state badges
    assert sidebar.acc_artistic.lbl_badge.text() == "Keiner"
    assert sidebar.acc_filter.lbl_badge.text() == "Standard"

    # Activate artistic mode (Joy division / waveform)
    sidebar.combo_artistic_mode.setCurrentIndex(1)
    assert "Wellenform" in sidebar.acc_artistic.lbl_badge.text()

    # Deactivate artistic mode
    sidebar.combo_artistic_mode.setCurrentIndex(0)
    assert sidebar.acc_artistic.lbl_badge.text() == "Keiner"

    # Activate hatching
    sidebar.chk_hatching.setChecked(True)
    assert "Schraffur" in sidebar.acc_contours.lbl_badge.text()

    sidebar.chk_hatching.setChecked(False)
    assert "Konturen" in sidebar.acc_contours.lbl_badge.text()

    # Activate Kuwahara
    sidebar.chk_kuwahara.setChecked(True)
    assert "Kuwahara" in sidebar.acc_filter.lbl_badge.text()

    sidebar.chk_kuwahara.setChecked(False)
    assert sidebar.acc_filter.lbl_badge.text() == "Standard"

    # Activate TSP sort + 2-opt
    sidebar.chk_tsp.setChecked(True)
    assert "TSP" in sidebar.acc_plotter.lbl_badge.text()

    sidebar.chk_two_opt.setChecked(True)
    assert "2-Opt" in sidebar.acc_plotter.lbl_badge.text()


def test_preset_auto_accordion_focus(app):
    sidebar = SidebarWidget()

    # Collapse all first
    sidebar._collapse_all_sections()

    # Spiral preset expands Artistic section
    sidebar._on_preset_selected("Archimedische Spirale (1-Linie)")
    assert sidebar.acc_artistic.is_expanded() is True

    # Hatching preset expands Contours section
    sidebar._collapse_all_sections()
    sidebar._on_preset_selected("Klassische Gravur (Schraffur)")
    assert sidebar.acc_contours.is_expanded() is True

    # Kuwahara preset expands Filter section
    sidebar._collapse_all_sections()
    sidebar._on_preset_selected("Malerisches Ölgemälde (Kuwahara)")
    assert sidebar.acc_filter.is_expanded() is True


def test_progressive_disclosure(app):
    sidebar = SidebarWidget()

    # 1. Artistic modes
    sidebar.combo_artistic_mode.setCurrentIndex(0)  # None
    assert sidebar.widget_waveform_opts.isHidden() is True
    assert sidebar.widget_spiral_opts.isHidden() is True
    assert sidebar.widget_tsp_opts.isHidden() is True
    assert sidebar.widget_delaunay_opts.isHidden() is True
    assert sidebar.widget_flow_opts.isHidden() is True

    sidebar.combo_artistic_mode.setCurrentIndex(1)  # Waveform
    assert sidebar.widget_waveform_opts.isHidden() is False
    assert sidebar.widget_spiral_opts.isHidden() is True

    sidebar.combo_artistic_mode.setCurrentIndex(2)  # Spiral
    assert sidebar.widget_waveform_opts.isHidden() is True
    assert sidebar.widget_spiral_opts.isHidden() is False

    # 2. Hatching options
    assert sidebar.chk_hatching.isChecked() is False
    assert sidebar.widget_hatching_opts.isHidden() is True
    sidebar.chk_hatching.setChecked(True)
    assert sidebar.widget_hatching_opts.isHidden() is False

    # 3. Shapes options
    assert sidebar.chk_shapes.isChecked() is False
    assert sidebar.widget_shapes_opts.isHidden() is True
    sidebar.chk_shapes.setChecked(True)
    assert sidebar.widget_shapes_opts.isHidden() is False

    # 4. Kuwahara radius slider
    assert sidebar.chk_kuwahara.isChecked() is False
    assert sidebar.slider_kuwahara_r.isHidden() is True
    sidebar.chk_kuwahara.setChecked(True)
    assert sidebar.slider_kuwahara_r.isHidden() is False
