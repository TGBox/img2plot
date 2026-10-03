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
    border-left: 1px solid #27272a;
    background: #141416;
    width: 14px;
    margin: 14px 0 14px 0;
}

QScrollBar::handle:vertical {
    background: #52525b;
    border: 1px solid #71717a;
    min-height: 36px;
    border-radius: 4px;
    margin: 1px 2px 1px 2px;
}

QScrollBar::handle:vertical:hover {
    background: #38bdf8;
    border: 1px solid #0284c7;
}

QScrollBar::handle:vertical:pressed {
    background: #0ea5e9;
    border: 1px solid #0369a1;
}

QScrollBar::sub-line:vertical {
    border-left: 1px solid #27272a;
    border-bottom: 1px solid #27272a;
    background: #27272a;
    height: 14px;
    subcontrol-position: top;
    subcontrol-origin: margin;
}

QScrollBar::sub-line:vertical:hover {
    background: #3f3f46;
}

QScrollBar::add-line:vertical {
    border-left: 1px solid #27272a;
    border-top: 1px solid #27272a;
    background: #27272a;
    height: 14px;
    subcontrol-position: bottom;
    subcontrol-origin: margin;
}

QScrollBar::add-line:vertical:hover {
    background: #3f3f46;
}

QScrollBar::up-arrow:vertical {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a1a1aa;
}

QScrollBar::down-arrow:vertical {
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a1a1aa;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: #141416;
}

QScrollBar:horizontal {
    border-top: 1px solid #27272a;
    background: #141416;
    height: 14px;
    margin: 0 14px 0 14px;
}

QScrollBar::handle:horizontal {
    background: #52525b;
    border: 1px solid #71717a;
    min-width: 36px;
    border-radius: 4px;
    margin: 2px 1px 2px 1px;
}

QScrollBar::handle:horizontal:hover {
    background: #38bdf8;
    border: 1px solid #0284c7;
}

QScrollBar::handle:horizontal:pressed {
    background: #0ea5e9;
    border: 1px solid #0369a1;
}

QScrollBar::sub-line:horizontal {
    border-top: 1px solid #27272a;
    border-right: 1px solid #27272a;
    background: #27272a;
    width: 14px;
    subcontrol-position: left;
    subcontrol-origin: margin;
}

QScrollBar::add-line:horizontal {
    border-top: 1px solid #27272a;
    border-left: 1px solid #27272a;
    background: #27272a;
    width: 14px;
    subcontrol-position: right;
    subcontrol-origin: margin;
}

QScrollBar::left-arrow:horizontal {
    width: 0px;
    height: 0px;
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    border-right: 5px solid #a1a1aa;
}

QScrollBar::right-arrow:horizontal {
    width: 0px;
    height: 0px;
    border-top: 4px solid transparent;
    border-bottom: 4px solid transparent;
    border-left: 5px solid #a1a1aa;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: #141416;
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

QPushButton#randomizeButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c3aed, stop:1 #db2777);
    color: #ffffff;
    border: 1px solid #a855f7;
    border-radius: 6px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 12px;
}

QPushButton#randomizeButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6d28d9, stop:1 #be185d);
    border-color: #c084fc;
}

QPushButton#randomizeButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5b21b6, stop:1 #9d174d);
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

QSlider:horizontal {
    min-height: 34px;
    max-height: 38px;
}

QSlider::groove:horizontal {
    border: 1px solid #3f3f46;
    height: 8px;
    background: #18181b;
    border-radius: 4px;
}

QSlider::sub-page:horizontal {
    background: #38bdf8;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 3px solid #0284c7;
    width: 24px;
    height: 24px;
    margin-top: -8px;
    margin-bottom: -8px;
    border-radius: 12px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
    border: 3px solid #38bdf8;
}

QSlider::handle:horizontal:pressed {
    background: #e0f2fe;
    border: 3px solid #0369a1;
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
    background-color: #121214;
    border-radius: 6px;
}

QTabWidget#sidebarTabs::pane {
    border: none;
    border-top: 1px solid #27272a;
    background-color: #121214;
}

QTabBar::tab {
    background-color: #18181b;
    color: #a1a1aa;
    padding: 7px 11px;
    font-size: 11px;
    font-weight: 600;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #27272a;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #121214;
    color: #38bdf8;
    font-weight: bold;
    border: 1px solid #38bdf8;
    border-bottom: 2px solid #121214;
}

QTabBar::tab:hover:!selected {
    background-color: #27272a;
    color: #f4f4f5;
    border-color: #3f3f46;
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

/* Sticky Footer at bottom of sidebar */
QWidget#stickyFooter {
    background-color: #161619;
    border-top: 1px solid #27272a;
}

QProgressBar#stickyProgressBar {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar#stickyProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2563eb, stop:1 #38bdf8);
    border-radius: 3px;
}

QWidget#sidebarHeader {
    background-color: #121214;
}

/* Accordion Section Styles */
QPushButton#accordionHeader {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 8px;
    text-align: left;
}

QPushButton#accordionHeader:hover {
    background-color: #222226;
    border-color: #3f3f46;
}

QPushButton#accordionHeader[expanded="true"] {
    background-color: #1a1b22;
    border-color: #38bdf8;
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}

QWidget#accordionContent {
    background-color: #121214;
    border: 1px solid #27272a;
    border-top: none;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
}

/* Small toolbar buttons */
QPushButton#toolbarSmallBtn {
    background-color: #18181b;
    color: #a1a1aa;
    border: 1px solid #27272a;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#toolbarSmallBtn:hover {
    background-color: #27272a;
    color: #f4f4f5;
    border-color: #3f3f46;
}

QPushButton#toolbarSmallBtn:pressed {
    background-color: #09090b;
    color: #38bdf8;
}

QToolTip {
    background-color: #18181b;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px 8px;
}
"""
