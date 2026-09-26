"""
Theme and stylesheet definitions for img2plot GUI.
Provides a modern, high-contrast dark theme with accessible typography.
"""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #121214;
    color: #e4e4e7;
}

QWidget {
    background-color: #121214;
    color: #e4e4e7;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 12px;
}

QMenuBar {
    background-color: #18181b;
    color: #e4e4e7;
    border-bottom: 1px solid #27272a;
    padding: 2px 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #27272a;
}

QMenu {
    background-color: #18181b;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QToolBar {
    background-color: #18181b;
    border-bottom: 1px solid #27272a;
    spacing: 6px;
    padding: 4px 8px;
}

QStatusBar {
    background-color: #18181b;
    color: #a1a1aa;
    border-top: 1px solid #27272a;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #18181b;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #3f3f46;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #18181b;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #3f3f46;
    min-width: 20px;
    border-radius: 5px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 14px;
    padding-bottom: 8px;
    padding-left: 8px;
    padding-right: 8px;
    background-color: #18181b;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #38bdf8;
}

QPushButton {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton:disabled {
    background-color: #1f1f23;
    color: #71717a;
    border-color: #27272a;
}

QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #3b82f6;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton#dangerButton {
    background-color: #991b1b;
    color: #ffffff;
    border: 1px solid #b91c1c;
}

QPushButton#dangerButton:hover {
    background-color: #b91c1c;
}

QLineEdit {
    background-color: #09090b;
    color: #f4f4f5;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 5px 8px;
}

QLineEdit:focus {
    border-color: #38bdf8;
}

QComboBox {
    background-color: #09090b;
    color: #f4f4f5;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 5px 8px;
}

QComboBox:hover {
    border-color: #3f3f46;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #18181b;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    selection-background-color: #3b82f6;
    border-radius: 4px;
    padding: 4px;
}

QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #27272a;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #38bdf8;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #f4f4f5;
    border: 1px solid #38bdf8;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
    border-color: #60a5fa;
    transform: scale(1.1);
}

QCheckBox {
    spacing: 8px;
    color: #e4e4e7;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    background-color: #09090b;
}

QCheckBox::indicator:hover {
    border-color: #38bdf8;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
}

QRadioButton {
    spacing: 8px;
    color: #e4e4e7;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    background-color: #09090b;
}

QRadioButton::indicator:checked {
    background-color: #2563eb;
    border: 4px solid #09090b;
}

QTabWidget::pane {
    border: 1px solid #27272a;
    background-color: #09090b;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #18181b;
    color: #a1a1aa;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #09090b;
    color: #38bdf8;
    font-weight: bold;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #27272a;
    color: #f4f4f5;
}

QProgressBar {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    height: 14px;
    text-align: center;
    font-size: 10px;
    color: #f4f4f5;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 5px;
}

QToolTip {
    background-color: #18181b;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px 8px;
}
"""
