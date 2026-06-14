import sys
import uuid
import queue
import threading
from datetime import datetime
import requests

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QCheckBox,
    QRadioButton, QSpinBox, QDoubleSpinBox, QAbstractSpinBox, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QDialogButtonBox, QAbstractItemView, QButtonGroup, QFrame,
    QSizePolicy, QScrollArea, QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPalette, QColor

from config import load_app_config, save_app_config
from shock_panel import osc_safe_name
from bpm import bpm_monitor, BLEAK_AVAILABLE

# ── Theme ─────────────────────────────────────────────────────────────────────
BG       = "#1C1B1F"
SURFACE  = "#2B2930"
SURFACE2 = "#37333E"
PRIMARY  = "#D0BCFF"
PRIM_CON = "#4F378B"
ON_SURF  = "#E6E1E5"
ON_VAR   = "#CAC4D0"
OUTLINE  = "#938F99"
OUT_VAR  = "#49454F"
POSITIVE = "#A8D5A2"


def _make_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,         QColor(BG))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(ON_SURF))
    p.setColor(QPalette.ColorRole.Base,            QColor(SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(SURFACE2))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(SURFACE))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(ON_SURF))
    p.setColor(QPalette.ColorRole.Text,            QColor(ON_SURF))
    p.setColor(QPalette.ColorRole.Button,          QColor(SURFACE2))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(ON_SURF))
    p.setColor(QPalette.ColorRole.BrightText,      QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Link,            QColor(PRIMARY))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(PRIM_CON))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(ON_SURF))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(OUT_VAR))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor(OUT_VAR))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(OUT_VAR))
    return p


STYLE = f"""
QWidget#sidebar {{
    background-color: {SURFACE};
    border-right: 1px solid {OUT_VAR};
}}
QGroupBox {{
    font-weight: bold;
    color: {PRIMARY};
    border: 1px solid {OUT_VAR};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    background-color: {BG};
}}
QPushButton {{
    border-radius: 4px;
    padding: 6px 16px;
    min-width: 64px;
}}
QPushButton#nav_btn {{
    background-color: transparent;
    color: {ON_VAR};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    padding: 14px 24px;
    min-width: 0;
    min-height: 44px;
    text-align: left;
}}
QPushButton#nav_btn:hover {{
    background-color: rgba(208, 188, 255, 0.08);
    color: {ON_SURF};
}}
QPushButton#nav_btn:checked {{
    background-color: rgba(79, 55, 139, 0.35);
    color: {PRIMARY};
    border-left: 3px solid {PRIMARY};
    font-weight: bold;
}}
QPushButton#stepper_btn {{
    padding: 2px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14pt;
    font-weight: bold;
    border-radius: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0; height: 0; border: none;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    border: 1px solid {OUTLINE};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}
QTableWidget {{
    border: 1px solid {OUT_VAR};
    gridline-color: {OUT_VAR};
}}
QHeaderView::section {{
    background-color: {SURFACE2};
    color: {PRIMARY};
    border: none;
    border-right: 1px solid {OUT_VAR};
    border-bottom: 1px solid {OUT_VAR};
    padding: 6px 10px;
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {OUT_VAR};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none; height: 0;
}}
QLabel#section_title {{
    color: {PRIMARY};
    font-size: 16pt;
    font-weight: bold;
    background-color: transparent;
}}
QLabel#field_label {{
    color: {ON_VAR};
    background-color: transparent;
}}
QLabel#status_lbl {{
    color: {POSITIVE};
    background-color: transparent;
}}
"""



# ── Helpers ───────────────────────────────────────────────────────────────────

class _Bridge(QObject):
    _call = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self._call.connect(lambda fn: fn(), Qt.ConnectionType.QueuedConnection)
    def run_in_main(self, fn):
        self._call.emit(fn)


def _label(text, obj_name=None):
    lbl = QLabel(text)
    if obj_name:
        lbl.setObjectName(obj_name)
    return lbl


def _hline():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {OUT_VAR}; background-color: {OUT_VAR}; max-height: 1px;")
    return line


class Stepper(QWidget):
    """
    Reliable number input: [−] [spinbox] [+]
    Exposes the same value()/setValue()/valueChanged interface as QSpinBox.
    """
    valueChanged = pyqtSignal(object)

    def __init__(self, min_val, max_val, step=1, value=0, decimals=0,
                 spin_width=90, parent=None):
        super().__init__(parent)
        self._decimals = decimals

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._minus = QPushButton("−")
        self._minus.setObjectName("stepper_btn")
        self._minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        if decimals == 0:
            self._spin = QSpinBox()
            self._spin.setRange(int(min_val), int(max_val))
            self._spin.setSingleStep(int(step))
            self._spin.setValue(int(value))
        else:
            self._spin = QDoubleSpinBox()
            self._spin.setRange(float(min_val), float(max_val))
            self._spin.setSingleStep(float(step))
            self._spin.setDecimals(decimals)
            self._spin.setValue(float(value))

        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setFixedWidth(spin_width)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._plus = QPushButton("+")
        self._plus.setObjectName("stepper_btn")
        self._plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._minus.clicked.connect(self._spin.stepDown)
        self._plus.clicked.connect(self._spin.stepUp)
        self._spin.valueChanged.connect(self.valueChanged.emit)

        row.addWidget(self._minus)
        row.addWidget(self._spin)
        row.addWidget(self._plus)

    def value(self):
        return self._spin.value()

    def setValue(self, v):
        self._spin.setValue(v)

    def setRange(self, mn, mx):
        self._spin.setRange(mn, mx)


# ── Main window ───────────────────────────────────────────────────────────────

class VRCChatboxGUI(QMainWindow):
    def __init__(self, messenger=None):
        self.app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()
        self.messenger = messenger
        self.config = load_app_config()
        self._bridge = _Bridge()

        self.app.setStyle("Fusion")
        self.app.setPalette(_make_palette())
        self.setWindowTitle("VRC Chatbox Settings")
        self.setFixedSize(1600, 900)
        self.app.setStyleSheet(STYLE)
        self._center_window()
        self._setup_ui()

    def _center_window(self):
        screen = self.app.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    # ── Shell ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Main row: sidebar + content
        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)
        outer.addLayout(main_row, stretch=1)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        app_title = QLabel("VRC Chatbox")
        app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_title.setStyleSheet(
            f"color:{PRIMARY};font-size:13pt;font-weight:bold;"
            f"padding:24px 16px 20px 16px;background:{SURFACE};"
        )
        sb_layout.addWidget(app_title)
        sb_layout.addWidget(_hline())

        self._nav_btns = []
        self._stack = QStackedWidget()
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        pages = [
            ("  General",      self._build_general_page()),
            ("  ShockOSC",     self._build_shockosc_page()),
            ("  Slide",        self._build_slide_page()),
            ("  Shock Panel",  self._build_shock_panel_page()),
            ("  BPM",          self._build_bpm_page()),
            ("  OSC Monitor",  self._build_osc_monitor_page()),
        ]
        for i, (label, page) in enumerate(pages):
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.clicked.connect(lambda _, idx=i: self._nav_to(idx))
            self._nav_group.addButton(btn)
            sb_layout.addWidget(btn)
            self._nav_btns.append(btn)
            self._stack.addWidget(page)

        sb_layout.addStretch()
        main_row.addWidget(sidebar)
        main_row.addWidget(self._stack, stretch=1)

        # Bottom bar
        bottom = QWidget()
        bottom.setStyleSheet(f"background-color:{SURFACE};border-top:1px solid {OUT_VAR};")
        bottom.setFixedHeight(52)
        bot_row = QHBoxLayout(bottom)
        bot_row.setContentsMargins(24, 0, 24, 0)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status_lbl")
        bot_row.addWidget(self.status_label)
        bot_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        bot_row.addWidget(close_btn)

        outer.addWidget(bottom)

    def _nav_to(self, index):
        prev = self._stack.currentIndex()
        osc_idx = len(self._nav_btns) - 1
        if prev == osc_idx and index != osc_idx:
            self._osc_timer.stop()
            if self.messenger:
                self.messenger.set_monitor_callback(None)
        self._stack.setCurrentIndex(index)
        self._nav_btns[index].setChecked(True)
        if index == osc_idx and prev != osc_idx:
            if self.messenger:
                self.messenger.set_monitor_callback(self._on_osc_message)
            self._osc_timer.start()

    def _set_status(self, text, ms=2500):
        self.status_label.setText(text)
        QTimer.singleShot(ms, lambda: self.status_label.setText(""))

    # ── General page ───────────────────────────────────────────────────────

    def _build_general_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(_label("General", "section_title"))
        layout.addWidget(_hline())

        card = QGroupBox("Display")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        self.show_music_cb = QCheckBox("Show Music Info in chatbox")
        self.show_music_cb.setChecked(self.config.get("show_music", True))
        self.show_music_cb.toggled.connect(self.on_music_toggle)
        card_layout.addWidget(self.show_music_cb)

        layout.addWidget(card)
        layout.addStretch()
        return page

    # ── ShockOSC page ──────────────────────────────────────────────────────

    def _build_shockosc_page(self):
        sc = self.config.get("shockosc", {})
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(_label("ShockOSC", "section_title"))
        layout.addWidget(_hline())

        # ── Two-column body ──────────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(24)
        layout.addLayout(body)

        # ── Left column ──────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(20)
        body.addLayout(left, stretch=1)

        # Options card
        opts_card = QGroupBox("Options")
        opts_grid = QGridLayout(opts_card)
        opts_grid.setSpacing(16)
        opts_grid.setContentsMargins(20, 24, 20, 20)

        self.shock_enabled_cb = QCheckBox("Enable ShockOSC")
        self.shock_enabled_cb.setChecked(sc.get("enabled", False))
        self.shock_show_info_cb = QCheckBox("Show shock info in chatbox")
        self.shock_show_info_cb.setChecked(sc.get("show_shock_info", True))
        self.shock_show_internet_cb = QCheckBox("Show internet shocks in chatbox")
        self.shock_show_internet_cb.setChecked(sc.get("show_internet_shocks", True))

        opts_grid.addWidget(self.shock_enabled_cb, 0, 0)
        opts_grid.addWidget(self.shock_show_info_cb, 1, 0)
        opts_grid.addWidget(self.shock_show_internet_cb, 2, 0)

        # Mode
        mode_row = QHBoxLayout()
        mode_row.setSpacing(24)
        mode_row.addWidget(_label("Mode:", "field_label"))
        self._mode_group = QButtonGroup(self)
        self.static_radio = QRadioButton("Static")
        self.random_radio = QRadioButton("Random")
        self._mode_group.addButton(self.static_radio)
        self._mode_group.addButton(self.random_radio)
        mode = sc.get("mode", "static")
        self.static_radio.setChecked(mode == "static")
        self.random_radio.setChecked(mode == "random")
        mode_row.addWidget(self.static_radio)
        mode_row.addWidget(self.random_radio)
        mode_row.addStretch()
        opts_grid.addLayout(mode_row, 3, 0)
        left.addWidget(opts_card)

        # Shock settings card
        shock_card = QGroupBox("Shock Settings")
        sg = QGridLayout(shock_card)
        sg.setSpacing(16)
        sg.setContentsMargins(20, 24, 20, 20)
        sg.setColumnMinimumWidth(0, 130)
        sg.setColumnStretch(1, 1)

        # Rows 0-2: intensity controls — each in its own row so columns align with
        # Duration/Cooldown/Hold below. Hidden rows collapse to 0px in QGridLayout.
        self._static_label = _label("Intensity %", "field_label")
        self.static_spinbox = Stepper(0, 100, 1, sc.get("static_intensity", 50), spin_width=90)
        sg.addWidget(self._static_label, 0, 0)
        sg.addWidget(self.static_spinbox, 0, 1)

        self._rand_min_label = _label("Min %", "field_label")
        self.random_min_spinbox = Stepper(0, 100, 1, sc.get("random_min", 20), spin_width=90)
        sg.addWidget(self._rand_min_label, 1, 0)
        sg.addWidget(self.random_min_spinbox, 1, 1)

        self._rand_max_label = _label("Max %", "field_label")
        self.random_max_spinbox = Stepper(0, 100, 1, sc.get("random_max", 80), spin_width=90)
        sg.addWidget(self._rand_max_label, 2, 0)
        sg.addWidget(self.random_max_spinbox, 2, 1)

        # Duration / Cooldown / Hold
        sg.addWidget(_label("Duration (s)", "field_label"), 3, 0)
        self.duration_spinbox = Stepper(0.3, 30.0, 0.1, sc.get("duration", 1.0), decimals=1, spin_width=90)
        sg.addWidget(self.duration_spinbox, 3, 1)

        sg.addWidget(_label("Cooldown (s)", "field_label"), 4, 0)
        self.cooldown_spinbox = Stepper(0.0, 60.0, 0.1, sc.get("cooldown_delay", 5.0), decimals=1, spin_width=90)
        sg.addWidget(self.cooldown_spinbox, 4, 1)

        sg.addWidget(_label("Hold Time (s)", "field_label"), 5, 0)
        self.hold_time_spinbox = Stepper(0.0, 5.0, 0.1, sc.get("hold_time", 0.5), decimals=2, spin_width=90)
        sg.addWidget(self.hold_time_spinbox, 5, 1)

        left.addWidget(shock_card)
        left.addStretch()


        # ── Right column ─────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(20)
        body.addLayout(right, stretch=1)

        openshock_card = QGroupBox("OpenShock Integration")
        og = QVBoxLayout(openshock_card)
        og.setSpacing(16)
        og.setContentsMargins(20, 24, 20, 20)

        # API token row
        token_row = QHBoxLayout()
        token_row.setSpacing(12)
        token_row.addWidget(_label("API Token", "field_label"))
        self.token_entry = QLineEdit()
        self.token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_entry.setText(sc.get("openshock_token", ""))
        self.token_entry.textChanged.connect(self.on_token_change)
        token_row.addWidget(self.token_entry, stretch=1)
        og.addLayout(token_row)

        self.discover_button = QPushButton("Discover Shockers")
        self.discover_button.setFixedWidth(200)
        self.discover_button.clicked.connect(self.discover_shockers)
        og.addWidget(self.discover_button)

        og.addWidget(_label("Shocker Assignments", "field_label"))

        self.shockers_table = QTableWidget(0, 2)
        self.shockers_table.setHorizontalHeaderLabels(["Name", "Group"])
        hh = self.shockers_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.shockers_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.shockers_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.shockers_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.shockers_table.setAlternatingRowColors(True)
        self.shockers_table.setMinimumHeight(220)
        self.shockers_table.verticalHeader().setVisible(False)
        og.addWidget(self.shockers_table)

        shocker_btns_row = QHBoxLayout()
        shocker_btns_row.setSpacing(12)
        self.add_shocker_btn = QPushButton("Add Shocker")
        self.add_shocker_btn.clicked.connect(self.add_shocker)
        self.edit_shocker_btn = QPushButton("Edit Selected")
        self.edit_shocker_btn.clicked.connect(self.edit_shocker)
        self.remove_shocker_btn = QPushButton("Remove Selected")
        self.remove_shocker_btn.clicked.connect(self.remove_shocker)
        shocker_btns_row.addWidget(self.add_shocker_btn)
        shocker_btns_row.addWidget(self.edit_shocker_btn)
        shocker_btns_row.addWidget(self.remove_shocker_btn)
        shocker_btns_row.addStretch()
        og.addLayout(shocker_btns_row)

        og.addWidget(_hline())

        og.addWidget(_label("Groups", "field_label"))

        self.groups_table = QTableWidget(0, 2)
        self.groups_table.setHorizontalHeaderLabels(["Group Name", "Shockers"])
        gh = self.groups_table.horizontalHeader()
        gh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        gh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.groups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.groups_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.groups_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.groups_table.setAlternatingRowColors(True)
        self.groups_table.setMinimumHeight(110)
        self.groups_table.verticalHeader().setVisible(False)
        og.addWidget(self.groups_table)

        group_btns_row = QHBoxLayout()
        group_btns_row.setSpacing(12)
        self.add_group_btn = QPushButton("Add Group")
        self.add_group_btn.clicked.connect(self.add_group)
        self.edit_group_btn = QPushButton("Edit Selected")
        self.edit_group_btn.clicked.connect(self.edit_group)
        self.remove_group_btn = QPushButton("Remove Selected")
        self.remove_group_btn.clicked.connect(self.remove_group)
        group_btns_row.addWidget(self.add_group_btn)
        group_btns_row.addWidget(self.edit_group_btn)
        group_btns_row.addWidget(self.remove_group_btn)
        group_btns_row.addStretch()
        og.addLayout(group_btns_row)

        og.addWidget(_hline())

        test_row = QHBoxLayout()
        test_row.setSpacing(12)
        self.test_leftleg_button = QPushButton("Test Left")
        self.test_leftleg_button.clicked.connect(self.test_leftleg)
        self.test_rightleg_button = QPushButton("Test Right")
        self.test_rightleg_button.clicked.connect(self.test_rightleg)
        test_row.addWidget(self.test_leftleg_button)
        test_row.addWidget(self.test_rightleg_button)
        test_row.addStretch()
        og.addLayout(test_row)

        right.addWidget(openshock_card)
        right.addStretch()

        # Wire signals and init state
        self.shock_enabled_cb.toggled.connect(self.on_shock_settings_change)
        self.shock_show_info_cb.toggled.connect(self.on_shock_settings_change)
        self.shock_show_internet_cb.toggled.connect(self.on_shock_settings_change)
        self.static_radio.toggled.connect(self.on_mode_change)
        self.static_spinbox.valueChanged.connect(self.on_shock_settings_change)
        self.random_min_spinbox.valueChanged.connect(self.on_shock_settings_change)
        self.random_max_spinbox.valueChanged.connect(self.on_shock_settings_change)
        self.duration_spinbox.valueChanged.connect(self.on_shock_settings_change)
        self.cooldown_spinbox.valueChanged.connect(self.on_shock_settings_change)
        self.hold_time_spinbox.valueChanged.connect(self.on_shock_settings_change)

        self._convert_legacy_shocker_config()
        self._init_default_groups()
        self.refresh_groups_display()
        self.refresh_shockers_display()
        self.on_mode_change()

        return page

    # ── Slide page ─────────────────────────────────────────────────────────

    def _build_slide_page(self):
        sl = self.config.get("slide", {})
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(_label("Slide", "section_title"))
        layout.addWidget(_hline())

        # Compact settings card — all controls in one tight grid
        settings_card = QGroupBox("Settings")
        sg = QGridLayout(settings_card)
        sg.setSpacing(8)
        sg.setContentsMargins(12, 16, 12, 12)
        sg.setColumnMinimumWidth(0, 110)
        sg.setColumnMinimumWidth(2, 110)
        sg.setColumnStretch(1, 1)
        sg.setColumnStretch(3, 1)

        self.slide_enabled_cb = QCheckBox("Enable Slide")
        self.slide_enabled_cb.setChecked(sl.get("enabled", False))
        self.slide_enabled_cb.toggled.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_enabled_cb, 0, 0, 1, 4)

        sg.addWidget(_label("Poll interval (s)", "field_label"), 1, 0)
        self.slide_poll_spinbox = Stepper(0.1, 10.0, 0.1, sl.get("poll_interval", 1.0), decimals=1, spin_width=75)
        self.slide_poll_spinbox.valueChanged.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_poll_spinbox, 1, 1)

        sg.addWidget(_label("Intensity min %", "field_label"), 1, 2)
        self.slide_min_spinbox = Stepper(0, 100, 5, sl.get("intensity_min", 30), spin_width=75)
        self.slide_min_spinbox.valueChanged.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_min_spinbox, 1, 3)

        sg.addWidget(_label("Cooldown min (s)", "field_label"), 2, 0)
        self.slide_cooldown_min_spinbox = Stepper(0.0, 300.0, 1.0, sl.get("cooldown_min", 5.0), decimals=1, spin_width=75)
        self.slide_cooldown_min_spinbox.valueChanged.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_cooldown_min_spinbox, 2, 1)

        sg.addWidget(_label("Intensity max %", "field_label"), 2, 2)
        self.slide_max_spinbox = Stepper(0, 100, 5, sl.get("intensity_max", 70), spin_width=75)
        self.slide_max_spinbox.valueChanged.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_max_spinbox, 2, 3)

        sg.addWidget(_label("Cooldown max (s)", "field_label"), 3, 0)
        self.slide_cooldown_max_spinbox = Stepper(0.0, 300.0, 1.0, sl.get("cooldown_max", 20.0), decimals=1, spin_width=75)
        self.slide_cooldown_max_spinbox.valueChanged.connect(self.on_slide_settings_change)
        sg.addWidget(self.slide_cooldown_max_spinbox, 3, 1)

        layout.addWidget(settings_card)

        # Variables table — stretch=1 fills remaining space; table scrolls internally
        vars_card = QGroupBox("OSC Variables")
        vc = QVBoxLayout(vars_card)
        vc.setSpacing(8)
        vc.setContentsMargins(12, 16, 12, 12)

        self.slide_vars_table = QTableWidget(0, 6)
        self.slide_vars_table.setHorizontalHeaderLabels(
            ["Name", "OSC Path", "Threshold", "Shockers", "Hold", "Enabled"])
        vh = self.slide_vars_table.horizontalHeader()
        vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        vh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.slide_vars_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.slide_vars_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.slide_vars_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.slide_vars_table.setAlternatingRowColors(True)
        vc.addWidget(self.slide_vars_table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_slide_variable)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_slide_variable)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_slide_variable)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        vc.addLayout(btn_row)

        layout.addWidget(vars_card, stretch=1)

        self.refresh_slide_variables_display()
        return page

    # ── Shock Panel page ───────────────────────────────────────────────────

    def _build_shock_panel_page(self):
        sp = self.config.get("shock_panel", {})
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(_label("Shock Panel", "section_title"))
        layout.addWidget(_hline())

        # Enable toggle
        self.panel_enabled_cb = QCheckBox("Enable Shock Panel")
        self.panel_enabled_cb.setChecked(sp.get("enabled", False))
        self.panel_enabled_cb.toggled.connect(self.on_shock_panel_settings_change)
        layout.addWidget(self.panel_enabled_cb)

        # Entries table
        entries_card = QGroupBox("Entries")
        ec = QVBoxLayout(entries_card)
        ec.setSpacing(8)
        ec.setContentsMargins(12, 16, 12, 12)

        self.panel_table = QTableWidget(0, 5)
        self.panel_table.setHorizontalHeaderLabels(
            ["Name", "Mode", "OSC Name", "Shockers", "Enabled"])
        ph = self.panel_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        ph.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.panel_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.panel_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.panel_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.panel_table.setAlternatingRowColors(True)
        ec.addWidget(self.panel_table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_panel_entry)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_panel_entry)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_panel_entry)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        ec.addLayout(btn_row)

        layout.addWidget(entries_card, stretch=1)

        # OSC path reference card
        info_card = QGroupBox("OSC Path Reference")
        ic = QVBoxLayout(info_card)
        ic.setContentsMargins(12, 12, 12, 12)
        ic.setSpacing(4)
        ref_text = (
            "Per-entry paths  (replace {OscName} with the entry's OSC Name):\n"
            "  …/Trigger       bool   — One-shot: rising edge fires; Hold: true=on, false=off\n"
            "  …/IntensityMin  float 0–1  — get/set minimum intensity (0=0%, 1=100%)\n"
            "  …/IntensityMax  float 0–1  — get/set maximum intensity (0=0%, 1=100%)\n"
            "  …/Duration      float 0–1  — get/set duration (0=0.5s, 1=10s)\n"
            "Intensity/Duration are bidirectional — the app echoes values back so your avatar params stay in sync."
        )
        ref_lbl = QLabel(ref_text)
        ref_lbl.setObjectName("field_label")
        ref_lbl.setWordWrap(True)
        ic.addWidget(ref_lbl)
        layout.addWidget(info_card)

        self.refresh_panel_display()
        return page

    def on_shock_panel_settings_change(self, *_):
        self.config.setdefault("shock_panel", {})["enabled"] = self.panel_enabled_cb.isChecked()
        save_app_config(self.config)
        self._update_shock_panel_controller()
        s = "enabled" if self.config["shock_panel"]["enabled"] else "disabled"
        self._set_status(f"Shock Panel {s}")

    def add_panel_entry(self):
        dlg = ShockPanelEntryDialog(self, None, self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["id"] = str(uuid.uuid4())
            self.config.setdefault("shock_panel", {}).setdefault("entries", []).append(data)
            save_app_config(self.config)
            self.refresh_panel_display()
            self._update_shock_panel_controller()
            self._set_status("Entry added")

    def edit_panel_entry(self):
        row = self.panel_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an entry to edit."); return
        idx = self.panel_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        entries = self.config.get("shock_panel", {}).get("entries", [])
        if idx >= len(entries): return
        dlg = ShockPanelEntryDialog(self, entries[idx], self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["id"] = entries[idx]["id"]
            entries[idx] = data
            save_app_config(self.config)
            self.refresh_panel_display()
            self._update_shock_panel_controller()
            self._set_status("Entry updated")

    def remove_panel_entry(self):
        row = self.panel_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select an entry to remove."); return
        if QMessageBox.question(self, "Confirm", "Remove this entry?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes: return
        idx = self.panel_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        entries = self.config.get("shock_panel", {}).get("entries", [])
        if idx < len(entries):
            del entries[idx]
            save_app_config(self.config)
            self.refresh_panel_display()
            self._update_shock_panel_controller()
            self._set_status("Entry removed")

    def refresh_panel_display(self):
        self.panel_table.setRowCount(0)
        entries = self.config.get("shock_panel", {}).get("entries", [])
        shockers_cfg = self.config.get("shockosc", {}).get("shockers", {})
        mode_labels = {"trigger": "One-shot", "hold": "Hold"}
        for i, entry in enumerate(entries):
            r = self.panel_table.rowCount()
            self.panel_table.insertRow(r)
            name_item = QTableWidgetItem(entry.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, i)
            self.panel_table.setItem(r, 0, name_item)
            self.panel_table.setItem(r, 1, QTableWidgetItem(
                mode_labels.get(entry.get("mode", "trigger"), "One-shot")))
            self.panel_table.setItem(r, 2, QTableWidgetItem(
                osc_safe_name(entry.get("osc_name") or entry.get("name", ""))))
            ids = entry.get("shocker_ids", [])
            names = [
                shockers_cfg[sid].get("name", sid[:8]) if isinstance(shockers_cfg.get(sid), dict)
                else sid[:8]
                for sid in ids if sid in shockers_cfg
            ]
            self.panel_table.setItem(r, 3, QTableWidgetItem(
                ", ".join(names) if names else ("None" if not ids else f"{len(ids)} shockers")))
            self.panel_table.setItem(r, 4, QTableWidgetItem(
                "Yes" if entry.get("enabled", True) else "No"))

    def _update_shock_panel_controller(self):
        if self.messenger and hasattr(self.messenger, 'update_shock_panel_config'):
            self.messenger.update_shock_panel_config(self.config.get("shock_panel", {}))

    # ── BPM page ───────────────────────────────────────────────────────────

    def _build_bpm_page(self):
        bm = self.config.get("bpm", {})
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(_label("BPM Monitor", "section_title"))
        layout.addWidget(_hline())

        self.bpm_enabled_cb = QCheckBox("Enable BPM Monitor")
        self.bpm_enabled_cb.setChecked(bm.get("enabled", False))
        self.bpm_enabled_cb.toggled.connect(self._on_bpm_enabled_change)
        layout.addWidget(self.bpm_enabled_cb)

        body = QHBoxLayout()
        body.setSpacing(24)
        layout.addLayout(body)

        # ── Left: live display ─────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(16)
        body.addLayout(left, stretch=1)

        display_card = QGroupBox("Live BPM")
        dc = QVBoxLayout(display_card)
        dc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dc.setContentsMargins(20, 24, 20, 20)
        dc.setSpacing(4)

        self._bpm_display = QLabel("--")
        self._bpm_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bpm_display.setStyleSheet(
            f"color: {PRIMARY}; font-size: 72pt; font-weight: bold; background: transparent;")
        dc.addWidget(self._bpm_display)

        unit_lbl = QLabel("BPM")
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit_lbl.setObjectName("field_label")
        unit_lbl.setStyleSheet("font-size: 14pt; background: transparent;")
        dc.addWidget(unit_lbl)

        self._bpm_status_lbl = QLabel(bpm_monitor.get_status())
        self._bpm_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bpm_status_lbl.setObjectName("field_label")
        dc.addWidget(self._bpm_status_lbl)

        left.addWidget(display_card)

        info_card = QGroupBox("Placeholder")
        ic = QVBoxLayout(info_card)
        ic.setContentsMargins(16, 16, 16, 16)
        ic.addWidget(_label(
            "Use {bpm} in message templates to display your current heart rate.",
            "field_label"))
        left.addWidget(info_card)
        left.addStretch()

        # ── Right: device management ───────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(16)
        body.addLayout(right, stretch=1)

        device_card = QGroupBox("Device")
        dvc = QVBoxLayout(device_card)
        dvc.setSpacing(12)
        dvc.setContentsMargins(20, 24, 20, 20)

        if not BLEAK_AVAILABLE:
            dvc.addWidget(_label(
                "bleak library not installed.\nRun:  pip install bleak",
                "field_label"))
        else:
            scan_row = QHBoxLayout()
            self._bpm_scan_btn = QPushButton("Scan for Devices")
            self._bpm_scan_btn.setFixedWidth(180)
            self._bpm_scan_btn.clicked.connect(self._bpm_scan)
            scan_row.addWidget(self._bpm_scan_btn)
            scan_row.addStretch()
            dvc.addLayout(scan_row)

            dvc.addWidget(_label("Discovered devices:", "field_label"))
            self._bpm_device_combo = QComboBox()
            saved_addr = bm.get("device_address", "")
            saved_name = bm.get("device_name", "")
            if saved_addr:
                display = f"{saved_name} ({saved_addr})" if saved_name else saved_addr
                self._bpm_device_combo.addItem(display, userData=(saved_name, saved_addr))
            dvc.addWidget(self._bpm_device_combo)

            conn_row = QHBoxLayout()
            self._bpm_connect_btn = QPushButton("Connect")
            self._bpm_connect_btn.setFixedWidth(120)
            self._bpm_connect_btn.clicked.connect(self._bpm_connect)
            self._bpm_disconnect_btn = QPushButton("Disconnect")
            self._bpm_disconnect_btn.setFixedWidth(120)
            self._bpm_disconnect_btn.clicked.connect(self._bpm_disconnect)
            self._bpm_disconnect_btn.setEnabled(False)
            conn_row.addWidget(self._bpm_connect_btn)
            conn_row.addWidget(self._bpm_disconnect_btn)
            conn_row.addStretch()
            dvc.addLayout(conn_row)

        right.addWidget(device_card)
        right.addStretch()

        # Live update timer (always runs)
        self._bpm_ui_timer = QTimer()
        self._bpm_ui_timer.setInterval(1000)
        self._bpm_ui_timer.timeout.connect(self._bpm_ui_tick)
        self._bpm_ui_timer.start()

        # Auto-connect if enabled and device address saved
        if bm.get("enabled", False) and bm.get("device_address"):
            bpm_monitor.connect(bm["device_address"])

        return page

    def _bpm_ui_tick(self):
        if not hasattr(self, '_bpm_display'):
            return
        bpm = bpm_monitor.get_bpm()
        self._bpm_display.setText(str(bpm) if bpm else "--")
        self._bpm_status_lbl.setText(bpm_monitor.get_status())
        if BLEAK_AVAILABLE and hasattr(self, '_bpm_connect_btn'):
            connected = bpm_monitor.is_connected()
            self._bpm_connect_btn.setEnabled(not connected)
            self._bpm_disconnect_btn.setEnabled(connected)

    def _bpm_scan(self):
        self._bpm_scan_btn.setEnabled(False)
        self._bpm_scan_btn.setText("Scanning…")
        self._bpm_device_combo.clear()

        def on_done(devices):
            self._bridge.run_in_main(lambda d=devices: self._bpm_scan_done(d))

        bpm_monitor.scan(on_done)

    def _bpm_scan_done(self, devices):
        self._bpm_scan_btn.setEnabled(True)
        self._bpm_scan_btn.setText("Scan for Devices")
        self._bpm_device_combo.clear()
        for name, addr in devices:
            self._bpm_device_combo.addItem(f"{name} ({addr})", userData=(name, addr))
        if not devices:
            self._set_status("No HR devices found nearby")

    def _bpm_connect(self):
        if not hasattr(self, '_bpm_device_combo'):
            return
        data = self._bpm_device_combo.currentData()
        if not data:
            return
        name, addr = data
        self.config.setdefault("bpm", {}).update({
            "device_address": addr,
            "device_name": name,
        })
        save_app_config(self.config)
        bpm_monitor.connect(addr)

    def _bpm_disconnect(self):
        bpm_monitor.disconnect()

    def _on_bpm_enabled_change(self, checked):
        self.config.setdefault("bpm", {})["enabled"] = checked
        save_app_config(self.config)
        if checked:
            addr = self.config.get("bpm", {}).get("device_address", "")
            if addr:
                bpm_monitor.connect(addr)
        else:
            bpm_monitor.disconnect()
        self._set_status(f"BPM Monitor {'enabled' if checked else 'disabled'}")

    # ── OSC Monitor page ───────────────────────────────────────────────────

    def _build_osc_monitor_page(self):
        self._osc_queue = queue.Queue()
        self._osc_params = {}  # {address: (display_value, type_str, datetime)}

        self._osc_timer = QTimer()
        self._osc_timer.setInterval(100)
        self._osc_timer.timeout.connect(self._osc_monitor_tick)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(_label("OSC Monitor", "section_title"))
        layout.addWidget(_hline())

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._osc_filter = QLineEdit()
        self._osc_filter.setPlaceholderText("Filter by path…")
        self._osc_filter.textChanged.connect(self._refresh_osc_table)
        toolbar.addWidget(self._osc_filter, stretch=1)

        self._osc_count_lbl = QLabel("0 parameters")
        self._osc_count_lbl.setObjectName("field_label")
        toolbar.addWidget(self._osc_count_lbl)

        copy_btn = QPushButton("Copy Path")
        copy_btn.setToolTip("Copy selected row's OSC path to clipboard (or double-click a row)")
        copy_btn.clicked.connect(self._copy_osc_path)
        toolbar.addWidget(copy_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_osc_monitor)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        self._osc_table = QTableWidget(0, 4)
        self._osc_table.setHorizontalHeaderLabels(["OSC Path", "Value", "Type", "Updated"])
        oh = self._osc_table.horizontalHeader()
        oh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        oh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        oh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        oh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._osc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._osc_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._osc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._osc_table.setAlternatingRowColors(True)
        self._osc_table.doubleClicked.connect(self._copy_osc_path)
        layout.addWidget(self._osc_table, stretch=1)

        layout.addWidget(_label("Double-click or select a row and press Copy Path to copy the OSC path.", "field_label"))

        return page

    def _on_osc_message(self, address, args):
        value = args[0] if len(args) == 1 else list(args)
        self._osc_queue.put((address, value, datetime.now()))

    def _osc_monitor_tick(self):
        updated = False
        while True:
            try:
                address, value, ts = self._osc_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(value, bool):
                type_str, display = "bool", "True" if value else "False"
            elif isinstance(value, float):
                type_str, display = "float", f"{value:.4f}"
            elif isinstance(value, int):
                type_str, display = "int", str(value)
            else:
                type_str, display = type(value).__name__, str(value)
            self._osc_params[address] = (display, type_str, ts)
            updated = True
        if updated:
            self._osc_count_lbl.setText(f"{len(self._osc_params)} parameters")
            self._refresh_osc_table()

    def _refresh_osc_table(self):
        filt = self._osc_filter.text().lower()
        # Remember selected path so we can re-select after rebuild
        sel_row = self._osc_table.currentRow()
        sel_path = (self._osc_table.item(sel_row, 0).text()
                    if sel_row >= 0 and self._osc_table.item(sel_row, 0) else None)

        self._osc_table.setRowCount(0)
        for address, (display, type_str, ts) in sorted(self._osc_params.items()):
            if filt and filt not in address.lower():
                continue
            r = self._osc_table.rowCount()
            self._osc_table.insertRow(r)
            self._osc_table.setItem(r, 0, QTableWidgetItem(address))
            self._osc_table.setItem(r, 1, QTableWidgetItem(display))
            self._osc_table.setItem(r, 2, QTableWidgetItem(type_str))
            self._osc_table.setItem(r, 3, QTableWidgetItem(ts.strftime("%H:%M:%S.%f")[:-3]))
            if address == sel_path:
                self._osc_table.selectRow(r)

    def _copy_osc_path(self):
        row = self._osc_table.currentRow()
        if row < 0:
            return
        path = self._osc_table.item(row, 0).text()
        QApplication.clipboard().setText(path)
        self._set_status(f"Copied: {path}")

    def _clear_osc_monitor(self):
        self._osc_params.clear()
        self._osc_table.setRowCount(0)
        self._osc_count_lbl.setText("0 parameters")

    # ── ShockOSC logic ─────────────────────────────────────────────────────

    def on_mode_change(self, *_):
        is_static = self.static_radio.isChecked()
        self._static_label.setVisible(is_static)
        self.static_spinbox.setVisible(is_static)
        self._rand_min_label.setVisible(not is_static)
        self.random_min_spinbox.setVisible(not is_static)
        self._rand_max_label.setVisible(not is_static)
        self.random_max_spinbox.setVisible(not is_static)
        self.on_shock_settings_change()

    def on_shock_settings_change(self, *_):
        if self.random_min_spinbox.value() > self.random_max_spinbox.value():
            self.random_max_spinbox.setValue(self.random_min_spinbox.value())
        if "shockosc" not in self.config:
            self.config["shockosc"] = {}
        token = self.token_entry.text() if hasattr(self, 'token_entry') else \
            self.config["shockosc"].get("openshock_token", "")
        self.config["shockosc"].update({
            "enabled":           self.shock_enabled_cb.isChecked(),
            "mode":              "static" if self.static_radio.isChecked() else "random",
            "static_intensity":  self.static_spinbox.value(),
            "random_min":        self.random_min_spinbox.value(),
            "random_max":        self.random_max_spinbox.value(),
            "duration":          round(self.duration_spinbox.value(), 1),
            "show_shock_info":   self.shock_show_info_cb.isChecked(),
            "show_internet_shocks": self.shock_show_internet_cb.isChecked(),
            "cooldown_delay":    round(self.cooldown_spinbox.value(), 1),
            "hold_time":         round(self.hold_time_spinbox.value(), 2),
            "openshock_token":   token,
            "shockers":          self.config["shockosc"].get("shockers", {}),
            "openshock_url":     self.config["shockosc"].get("openshock_url", "https://api.openshock.app"),
        })
        save_app_config(self.config)
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
        if hasattr(self, 'status_label'):
            s = "enabled" if self.config["shockosc"]["enabled"] else "disabled"
            self._set_status(f"ShockOSC {s}")

    def on_music_toggle(self, checked):
        self.config["show_music"] = checked
        save_app_config(self.config)
        if self.messenger:
            self.messenger.show_music = checked
            self.messenger.request_display_update()
        self._set_status(f"Music display {'enabled' if checked else 'disabled'}")

    def on_token_change(self, text):
        if "shockosc" not in self.config:
            self.config["shockosc"] = {}
        self.config["shockosc"]["openshock_token"] = text
        save_app_config(self.config)
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])

    def discover_shockers(self):
        token = self.token_entry.text().strip()
        if not token:
            QMessageBox.critical(self, "Error", "Please enter your OpenShock API token first.")
            return
        self.discover_button.setEnabled(False)
        self.discover_button.setText("Discovering…")

        def _thread():
            try:
                if len(token) < 10:
                    self._bridge.run_in_main(lambda: QMessageBox.critical(
                        self, "Invalid Token", "API token appears too short."))
                    return
                base = self.config['shockosc'].get('openshock_url', 'https://api.openshock.app')
                endpoints = ["/1/shockers/own", "/1/shockers/shared", "/1/devices/own"]
                headers = {'Open-Shock-Token': token,
                           'User-Agent': 'VRCChatbox-ShockOSC/1.0',
                           'Accept': 'application/json'}
                response, url = None, None
                for ep in endpoints:
                    url = f"{base}{ep}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            break
                        if response.status_code == 401:
                            break
                    except requests.RequestException:
                        continue

                if not response or response.status_code != 200:
                    code = response.status_code if response else 0
                    msgs = {
                        0:   ("Connection Error", "Could not reach any OpenShock endpoint."),
                        400: ("API Error", f"Bad request (400).\n{response.text[:300]}"),
                        401: ("Auth Error", "Invalid API token."),
                        403: ("Permission Error", "Token lacks permission to access devices."),
                    }
                    title, msg = msgs.get(code, ("API Error", f"HTTP {code}\n{response.text[:300]}"))
                    self._bridge.run_in_main(lambda t=title, m=msg: QMessageBox.critical(self, t, m))
                    return

                try:
                    api = response.json()
                except ValueError as e:
                    self._bridge.run_in_main(lambda: QMessageBox.critical(
                        self, "Parse Error", f"Invalid JSON: {e}"))
                    return

                shockers, devices = [], None
                if isinstance(api, dict) and 'data' in api:
                    data = api['data']
                    if isinstance(data, list):
                        if data and 'shockers' in data[0]:
                            devices = data
                        elif data and ('id' in data[0] or 'name' in data[0]):
                            for s in data:
                                shockers.append({'id': s.get('id'),
                                    'name': s.get('name', f"Shocker {s.get('id')}"),
                                    'device_name': (s.get('device', {}).get('name', 'Unknown')
                                                    if isinstance(s.get('device'), dict) else 'Unknown')})
                elif isinstance(api, list):
                    devices = api
                elif isinstance(api, dict):
                    if 'devices' in api:
                        devices = api['devices']
                    elif 'shockers' in api:
                        for s in api['shockers']:
                            shockers.append({'id': s.get('id'),
                                'name': s.get('name', f"Shocker {s.get('id')}"),
                                'device_name': 'Unknown'})
                    else:
                        devices = [api]

                if devices:
                    for dev in devices:
                        ds = dev.get('shockers', [dev]) if isinstance(dev, dict) else []
                        for s in ds:
                            if isinstance(s, dict) and 'id' in s:
                                shockers.append({'id': s['id'],
                                    'name': s.get('name', f"Shocker {s['id']}"),
                                    'device_name': dev.get('name', 'Unknown') if isinstance(dev, dict) else 'Unknown'})

                captured = shockers
                self._bridge.run_in_main(lambda: self._update_discovered_shockers(captured))
            except Exception as e:
                import traceback
                msg = f"{e}\n\n{traceback.format_exc()}"
                self._bridge.run_in_main(lambda m=msg: QMessageBox.critical(self, "Error", m))
            finally:
                self._bridge.run_in_main(lambda: (
                    self.discover_button.setEnabled(True),
                    self.discover_button.setText("Discover Shockers"),
                ))

        threading.Thread(target=_thread, daemon=True).start()

    def _update_discovered_shockers(self, shockers):
        self.discovered_shockers = {str(s['id']): s for s in shockers}
        if not shockers:
            QMessageBox.information(self, "No Shockers",
                "No shockers found. Check your OpenShock account.")
            return
        existing = self.config["shockosc"].setdefault("shockers", {})
        added = 0
        for sid, s in self.discovered_shockers.items():
            if sid not in existing:
                existing[sid] = {
                    "name": s["name"],
                    "group": "",
                    "device_name": s.get("device_name", "Unknown"),
                }
                added += 1
        if added:
            save_app_config(self.config)
            if self.messenger and hasattr(self.messenger, 'update_shock_config'):
                self.messenger.update_shock_config(self.config["shockosc"])
        self.refresh_shockers_display()
        QMessageBox.information(self, "Success",
            f"Discovered {len(shockers)} shocker(s). {added} new shocker(s) added.")

    def refresh_shockers_display(self):
        self.shockers_table.setRowCount(0)
        for sid, info in self.config.get("shockosc", {}).get("shockers", {}).items():
            if isinstance(info, dict):
                name = info.get('name', f"Shocker {sid[:8]}…")
                group = info.get("group", "")
            else:
                name = f"Shocker {sid[:8]}…"
                group = info or ""
            self._add_shocker_row(name, sid, group)

    def _add_shocker_row(self, name, sid, group):
        r = self.shockers_table.rowCount()
        self.shockers_table.insertRow(r)
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, sid)
        self.shockers_table.setItem(r, 0, name_item)
        self.shockers_table.setItem(r, 1, QTableWidgetItem(group))

    def add_shocker(self):
        dlg = ShockerEditDialog(self, mode="add",
                                discovered=getattr(self, 'discovered_shockers', {}),
                                groups=self.config.get("shockosc", {}).get("groups", []))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            sid = data["id"]
            if not sid:
                return
            self.config["shockosc"].setdefault("shockers", {})[sid] = {
                "name": data["name"],
                "group": data["group"],
                "device_name": "Manual",
            }
            save_app_config(self.config)
            if self.messenger and hasattr(self.messenger, 'update_shock_config'):
                self.messenger.update_shock_config(self.config["shockosc"])
            self.refresh_shockers_display()
            self._set_status("Shocker added")

    def edit_shocker(self):
        row = self.shockers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a shocker first."); return
        sid = self.shockers_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        info = self.config.get("shockosc", {}).get("shockers", {}).get(sid, {})
        if isinstance(info, str):
            info = {"name": f"Shocker {sid[:8]}…", "group": info}
        dlg = ShockerEditDialog(self, mode="edit", current={
            "name": info.get("name", f"Shocker {sid[:8]}…"),
            "group": info.get("group", ""),
        }, groups=self.config.get("shockosc", {}).get("groups", []))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.config["shockosc"].setdefault("shockers", {})[sid] = {
                **info,
                "name": data["name"],
                "group": data["group"],
            }
            save_app_config(self.config)
            if self.messenger and hasattr(self.messenger, 'update_shock_config'):
                self.messenger.update_shock_config(self.config["shockosc"])
            self.refresh_shockers_display()
            self._set_status("Shocker updated")

    def remove_shocker(self):
        row = self.shockers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a shocker first."); return
        sid = self.shockers_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Confirm", "Remove this shocker?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes: return
        shockers = self.config.get("shockosc", {}).get("shockers", {})
        if sid in shockers:
            del shockers[sid]
            save_app_config(self.config)
            if self.messenger and hasattr(self.messenger, 'update_shock_config'):
                self.messenger.update_shock_config(self.config["shockosc"])
            self.refresh_shockers_display()
            self._set_status("Shocker removed")

    # ── Group management ───────────────────────────────────────────────────

    def _init_default_groups(self):
        sc = self.config.setdefault("shockosc", {})
        if "groups" not in sc:
            sc["groups"] = ["leftleg", "rightleg"]
            save_app_config(self.config)

    def refresh_groups_display(self):
        self.groups_table.setRowCount(0)
        shockers = self.config.get("shockosc", {}).get("shockers", {})
        for group_name in self.config.get("shockosc", {}).get("groups", []):
            count = sum(
                1 for info in shockers.values()
                if (isinstance(info, dict) and info.get("group") == group_name)
                or (isinstance(info, str) and info == group_name)
            )
            r = self.groups_table.rowCount()
            self.groups_table.insertRow(r)
            self.groups_table.setItem(r, 0, QTableWidgetItem(group_name))
            self.groups_table.setItem(r, 1, QTableWidgetItem(str(count)))

    def add_group(self):
        name, ok = QInputDialog.getText(self, "Add Group", "Group name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        groups = self.config.setdefault("shockosc", {}).setdefault("groups", [])
        if name in groups:
            QMessageBox.warning(self, "Duplicate", f'Group "{name}" already exists.')
            return
        groups.append(name)
        save_app_config(self.config)
        self.refresh_groups_display()
        self._set_status(f'Group "{name}" added')

    def edit_group(self):
        row = self.groups_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a group first."); return
        old_name = self.groups_table.item(row, 0).text()
        name, ok = QInputDialog.getText(self, "Edit Group", "Group name:", text=old_name)
        if not ok or not name.strip() or name.strip() == old_name:
            return
        name = name.strip()
        groups = self.config.get("shockosc", {}).get("groups", [])
        if name in groups:
            QMessageBox.warning(self, "Duplicate", f'Group "{name}" already exists.')
            return
        groups[groups.index(old_name)] = name
        for info in self.config.get("shockosc", {}).get("shockers", {}).values():
            if isinstance(info, dict) and info.get("group") == old_name:
                info["group"] = name
        save_app_config(self.config)
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
        self.refresh_groups_display()
        self.refresh_shockers_display()
        self._set_status(f'Group renamed to "{name}"')

    def remove_group(self):
        row = self.groups_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a group first."); return
        name = self.groups_table.item(row, 0).text()
        count = sum(
            1 for info in self.config.get("shockosc", {}).get("shockers", {}).values()
            if (isinstance(info, dict) and info.get("group") == name)
            or (isinstance(info, str) and info == name)
        )
        msg = f'Remove group "{name}"?'
        if count > 0:
            msg += f"\n\n{count} shocker(s) in this group will have their group cleared."
        if QMessageBox.question(self, "Confirm", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes: return
        groups = self.config.get("shockosc", {}).get("groups", [])
        groups.remove(name)
        for info in self.config.get("shockosc", {}).get("shockers", {}).values():
            if isinstance(info, dict) and info.get("group") == name:
                info["group"] = ""
        save_app_config(self.config)
        if self.messenger and hasattr(self.messenger, 'update_shock_config'):
            self.messenger.update_shock_config(self.config["shockosc"])
        self.refresh_groups_display()
        self.refresh_shockers_display()
        self._set_status(f'Group "{name}" removed')

    def test_leftleg(self):
        if not self.messenger or not hasattr(self.messenger, 'shock_controller'): return
        self.test_leftleg_button.setEnabled(False)
        self.test_leftleg_button.setText("Testing…")
        def _run():
            try: self.messenger.shock_controller.test_leftleg_shock()
            except Exception as e: print(f"Left test failed: {e}")
            finally: self._bridge.run_in_main(lambda: (
                self.test_leftleg_button.setEnabled(True),
                self.test_leftleg_button.setText("Test Left"),
            ))
        threading.Thread(target=_run, daemon=True).start()

    def test_rightleg(self):
        if not self.messenger or not hasattr(self.messenger, 'shock_controller'): return
        self.test_rightleg_button.setEnabled(False)
        self.test_rightleg_button.setText("Testing…")
        def _run():
            try: self.messenger.shock_controller.test_rightleg_shock()
            except Exception as e: print(f"Right test failed: {e}")
            finally: self._bridge.run_in_main(lambda: (
                self.test_rightleg_button.setEnabled(True),
                self.test_rightleg_button.setText("Test Right"),
            ))
        threading.Thread(target=_run, daemon=True).start()

    def _convert_legacy_shocker_config(self):
        shockers = self.config.get("shockosc", {}).get("shockers", {})
        changed = False
        for sid, info in shockers.items():
            if isinstance(info, str):
                shockers[sid] = {"group": info, "name": f"Shocker {sid[:8]}…", "device_name": "Unknown"}
                changed = True
        if changed:
            save_app_config(self.config)

    # ── Slide logic ────────────────────────────────────────────────────────

    def add_slide_variable(self):
        dlg = SlideVariableDialog(self, None, self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.config.setdefault("slide", {}).setdefault("variables", []).append(dlg.get_data())
            save_app_config(self.config)
            self.refresh_slide_variables_display()
            self.update_slide_controller()

    def edit_slide_variable(self):
        row = self.slide_vars_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a variable to edit."); return
        config_idx = self.slide_vars_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        variables = self.config.get("slide", {}).get("variables", [])
        if config_idx >= len(variables): return
        dlg = SlideVariableDialog(self, variables[config_idx], self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            variables[config_idx] = dlg.get_data()
            save_app_config(self.config)
            self.refresh_slide_variables_display()
            self.update_slide_controller()

    def remove_slide_variable(self):
        row = self.slide_vars_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Select a variable to remove."); return
        if QMessageBox.question(self, "Confirm", "Delete this variable?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes: return
        config_idx = self.slide_vars_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        variables = self.config.get("slide", {}).get("variables", [])
        if config_idx < len(variables):
            del variables[config_idx]
            save_app_config(self.config)
            self.refresh_slide_variables_display()
            self.update_slide_controller()

    def refresh_slide_variables_display(self):
        self.slide_vars_table.setRowCount(0)
        variables = self.config.get("slide", {}).get("variables", [])
        sorted_vars = sorted(enumerate(variables), key=lambda x: x[1].get("name", "").lower())
        for r, (config_idx, v) in enumerate(sorted_vars):
            self.slide_vars_table.insertRow(r)
            shockers = v.get("shockers", [])
            hold = f"{v.get('hold_time', 3.0)}s" if v.get("hold_mode") else "—"
            name_item = QTableWidgetItem(v.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, config_idx)
            self.slide_vars_table.setItem(r, 0, name_item)
            self.slide_vars_table.setItem(r, 1, QTableWidgetItem(v.get("osc_path", "")))
            self.slide_vars_table.setItem(r, 2, QTableWidgetItem(f"{v.get('threshold', 0.0):.2f}"))
            self.slide_vars_table.setItem(r, 3, QTableWidgetItem(str(len(shockers)) if shockers else "All"))
            self.slide_vars_table.setItem(r, 4, QTableWidgetItem(hold))
            self.slide_vars_table.setItem(r, 5, QTableWidgetItem("Yes" if v.get("enabled", True) else "No"))

    def on_slide_settings_change(self, *_):
        self.config.setdefault("slide", {}).update({
            "enabled":              self.slide_enabled_cb.isChecked(),
            "poll_interval":        round(self.slide_poll_spinbox.value(), 1),
            "intensity_min":        self.slide_min_spinbox.value(),
            "intensity_max":        self.slide_max_spinbox.value(),
            "cooldown_min": round(self.slide_cooldown_min_spinbox.value(), 1),
            "cooldown_max": round(self.slide_cooldown_max_spinbox.value(), 1),
        })
        save_app_config(self.config)
        self.update_slide_controller()
        if hasattr(self, 'status_label'):
            s = "enabled" if self.config["slide"]["enabled"] else "disabled"
            self._set_status(f"Slide {s}")

    def update_slide_controller(self):
        if self.messenger and hasattr(self.messenger, 'slide_controller'):
            self.messenger.update_slide_config(self.config.get("slide", {}))

    def run(self):
        self.show()
        self.app.exec()


# ── Dialogs ───────────────────────────────────────────────────────────────────

class ShockerEditDialog(QDialog):
    def __init__(self, parent, mode="add", current=None, discovered=None, groups=None):
        """
        mode="add"  — fields: Shocker (dropdown or manual ID), Name, Group
        mode="edit" — fields: Name, Group
        discovered  — dict {id: {name, device_name, ...}} from Discover Shockers
        groups      — list of group name strings from config
        """
        super().__init__(parent)
        self.mode = mode
        self._discovered = discovered or {}
        self._groups = groups or []
        self.setWindowTitle("Add Shocker" if mode == "add" else "Edit Shocker")
        self.setFixedSize(420, 280 if mode == "add" else 220)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(18)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnMinimumWidth(0, 120)
        next_row = 0

        if mode == "add":
            grid.addWidget(_label("Shocker", "field_label"), next_row, 0)
            if self._discovered:
                # Dropdown of discovered shockers
                self._shocker_combo = QComboBox()
                for sid, s in self._discovered.items():
                    label = f"{s['name']}  ({s.get('device_name', '')})"
                    self._shocker_combo.addItem(label, userData=sid)
                self._shocker_combo.currentIndexChanged.connect(self._on_shocker_selected)
                grid.addWidget(self._shocker_combo, next_row, 1)
                self._id_edit = None
            else:
                # Fallback: manual UUID entry
                self._id_edit = QLineEdit()
                self._id_edit.setPlaceholderText("UUID from OpenShock")
                grid.addWidget(self._id_edit, next_row, 1)
                self._shocker_combo = None
            next_row += 1

        grid.addWidget(_label("Name", "field_label"), next_row, 0)
        self.name_edit = QLineEdit()
        if current:
            self.name_edit.setText(current.get("name", ""))
        grid.addWidget(self.name_edit, next_row, 1)
        next_row += 1

        grid.addWidget(_label("Group", "field_label"), next_row, 0)
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.group_combo.setPlaceholderText("Select or type a group…")
        for g in self._groups:
            self.group_combo.addItem(g)
        if current:
            g = current.get("group", "")
            idx = self.group_combo.findText(g)
            if idx >= 0:
                self.group_combo.setCurrentIndex(idx)
            else:
                self.group_combo.setCurrentText(g)
        grid.addWidget(self.group_combo, next_row, 1)

        layout.addLayout(grid)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Pre-fill name from first discovered shocker
        if mode == "add" and self._discovered:
            self._on_shocker_selected(0)

    def _on_shocker_selected(self, index):
        sid = self._shocker_combo.itemData(index)
        if sid and sid in self._discovered:
            self.name_edit.setText(self._discovered[sid]["name"])

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.critical(self, "Error", "Name cannot be empty."); return
        if self.mode == "add" and self._id_edit is not None and not self._id_edit.text().strip():
            QMessageBox.critical(self, "Error", "Shocker ID cannot be empty."); return
        self.accept()

    def get_data(self):
        selected_id = None
        if self.mode == "add":
            if self._shocker_combo is not None:
                selected_id = self._shocker_combo.currentData()
            elif self._id_edit is not None:
                selected_id = self._id_edit.text().strip()
        return {
            "name": self.name_edit.text().strip(),
            "id": selected_id,
            "group": self.group_combo.currentText().strip(),
        }


class SlideVariableDialog(QDialog):
    def __init__(self, parent, current, config):
        super().__init__(parent)
        self.config = config
        self.selected_shockers = list(current.get("shockers", [])) if current else []
        self.setWindowTitle("Edit Variable" if current else "Add Variable")
        self.setFixedSize(700, 540)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(20)

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnMinimumWidth(0, 160)
        grid.setColumnStretch(1, 1)

        grid.addWidget(_label("Name", "field_label"), 0, 0)
        self.name_edit = QLineEdit()
        if current: self.name_edit.setText(current.get("name", ""))
        grid.addWidget(self.name_edit, 0, 1)

        grid.addWidget(_label("OSC Path", "field_label"), 1, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setText(current.get("osc_path", "/avatar/parameters/") if current else "/avatar/parameters/")
        grid.addWidget(self.path_edit, 1, 1)

        grid.addWidget(_label("Threshold (0–1)", "field_label"), 2, 0)
        self.threshold_s = Stepper(0.0, 1.0, 0.05, current.get("threshold", 0.0) if current else 0.0,
                                   decimals=2, spin_width=110)
        grid.addWidget(self.threshold_s, 2, 1)

        grid.addWidget(_label("Shockers", "field_label"), 3, 0)
        self.shocker_btn = QPushButton("Select Shockers (All)")
        self.shocker_btn.clicked.connect(self._pick_shockers)
        grid.addWidget(self.shocker_btn, 3, 1)
        self._update_shocker_btn()

        grid.addWidget(_label("Hold Mode", "field_label"), 4, 0)
        self.hold_mode_cb = QCheckBox("Enable Hold Mode")
        self.hold_mode_cb.setChecked(current.get("hold_mode", False) if current else False)
        grid.addWidget(self.hold_mode_cb, 4, 1)

        grid.addWidget(_label("Hold Time (s)", "field_label"), 5, 0)
        self.hold_time_s = Stepper(1.0, 10.0, 0.5, current.get("hold_time", 3.0) if current else 3.0,
                                   decimals=1, spin_width=110)
        grid.addWidget(self.hold_time_s, 5, 1)

        grid.addWidget(_label("Hold Threshold", "field_label"), 6, 0)
        self.hold_thresh_s = Stepper(0.0, 1.0, 0.05, current.get("hold_threshold", 0.9) if current else 0.9,
                                     decimals=2, spin_width=110)
        grid.addWidget(self.hold_thresh_s, 6, 1)

        grid.addWidget(_label("Status", "field_label"), 7, 0)
        self.enabled_cb = QCheckBox("Enabled")
        self.enabled_cb.setChecked(current.get("enabled", True) if current else True)
        grid.addWidget(self.enabled_cb, 7, 1)

        layout.addLayout(grid)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_shocker_btn(self):
        n = len(self.selected_shockers)
        self.shocker_btn.setText(f"Select Shockers ({n} selected)" if n else "Select Shockers (All)")

    def _pick_shockers(self):
        dlg = ShockerSelectionDialog(self, self.config, self.selected_shockers)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.selected_shockers = dlg.get_selected()
            self._update_shocker_btn()

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.critical(self, "Error", "Name cannot be empty."); return
        if not self.path_edit.text().strip():
            QMessageBox.critical(self, "Error", "OSC Path cannot be empty."); return
        self.accept()

    def get_data(self):
        return {
            "name":            self.name_edit.text().strip(),
            "osc_path":        self.path_edit.text().strip(),
            "threshold":       round(self.threshold_s.value(), 2),
            "enabled":         self.enabled_cb.isChecked(),
            "shockers":        self.selected_shockers,
            "hold_mode":       self.hold_mode_cb.isChecked(),
            "hold_time":       round(self.hold_time_s.value(), 1),
            "hold_threshold":  round(self.hold_thresh_s.value(), 2),
        }


class ShockerSelectionDialog(QDialog):
    def __init__(self, parent, config, current_selected):
        super().__init__(parent)
        self.setWindowTitle("Select Shockers")
        self.setFixedSize(440, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(QLabel("Select shockers for this variable:"))

        self._cbs = {}
        for sid, info in config.get("shockosc", {}).get("shockers", {}).items():
            if isinstance(info, dict):
                label = f"{info.get('name', sid[:8])} ({info.get('device_name', '')})"
            else:
                label = sid[:8]
            cb = QCheckBox(label)
            cb.setChecked(sid in current_selected)
            self._cbs[sid] = cb
            layout.addWidget(cb)

        if not self._cbs:
            layout.addWidget(_label("No shockers configured in ShockOSC tab.", "field_label"))

        layout.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_selected(self):
        return [sid for sid, cb in self._cbs.items() if cb.isChecked()]


class ShockPanelEntryDialog(QDialog):
    def __init__(self, parent, current, config):
        super().__init__(parent)
        self.config = config
        self.selected_shocker_ids = list(current.get("shocker_ids", [])) if current else []
        self._osc_name_auto = True
        self.setWindowTitle("Edit Entry" if current else "Add Entry")
        self.setFixedSize(560, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(16)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnMinimumWidth(0, 140)
        grid.setColumnStretch(1, 1)

        grid.addWidget(_label("Name", "field_label"), 0, 0)
        self.name_edit = QLineEdit()
        if current:
            self.name_edit.setText(current.get("name", ""))
        self.name_edit.textChanged.connect(self._on_name_changed)
        grid.addWidget(self.name_edit, 0, 1)

        grid.addWidget(_label("OSC Name", "field_label"), 1, 0)
        self.osc_name_edit = QLineEdit()
        self.osc_name_edit.setPlaceholderText("auto-derived from Name")
        if current:
            stored = current.get("osc_name", "")
            auto = osc_safe_name(current.get("name", ""))
            if stored and stored != auto:
                self._osc_name_auto = False
                self.osc_name_edit.setText(stored)
            else:
                self.osc_name_edit.setText(auto)
        self.osc_name_edit.textChanged.connect(self._on_osc_name_changed)
        grid.addWidget(self.osc_name_edit, 1, 1)

        grid.addWidget(_label("Mode", "field_label"), 2, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("One-shot (trigger)", userData="trigger")
        self.mode_combo.addItem("Hold (continuous)", userData="hold")
        current_mode = current.get("mode", "trigger") if current else "trigger"
        self.mode_combo.setCurrentIndex(
            next((i for i in range(self.mode_combo.count())
                  if self.mode_combo.itemData(i) == current_mode), 0))
        self.mode_combo.currentIndexChanged.connect(self._refresh_paths_preview)
        grid.addWidget(self.mode_combo, 2, 1)

        grid.addWidget(_label("Shockers", "field_label"), 3, 0)
        self.shocker_btn = QPushButton("Select Shockers (All)")
        self.shocker_btn.clicked.connect(self._pick_shockers)
        grid.addWidget(self.shocker_btn, 3, 1)
        self._update_shocker_btn()

        grid.addWidget(_label("Status", "field_label"), 4, 0)
        self.enabled_cb = QCheckBox("Enabled")
        self.enabled_cb.setChecked(current.get("enabled", True) if current else True)
        grid.addWidget(self.enabled_cb, 4, 1)

        layout.addLayout(grid)
        layout.addWidget(_hline())

        paths_card = QGroupBox("OSC Paths for this entry")
        pc = QVBoxLayout(paths_card)
        pc.setContentsMargins(12, 10, 12, 10)
        self.paths_lbl = QLabel()
        self.paths_lbl.setObjectName("field_label")
        self.paths_lbl.setWordWrap(True)
        pc.addWidget(self.paths_lbl)
        layout.addWidget(paths_card)
        self._refresh_paths_preview()

        layout.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_name_changed(self, text):
        if self._osc_name_auto:
            self.osc_name_edit.blockSignals(True)
            self.osc_name_edit.setText(osc_safe_name(text))
            self.osc_name_edit.blockSignals(False)
        self._refresh_paths_preview()

    def _on_osc_name_changed(self, text):
        auto = osc_safe_name(self.name_edit.text())
        self._osc_name_auto = (text == auto or text == "")
        self._refresh_paths_preview()

    def _refresh_paths_preview(self, *_):
        raw = self.osc_name_edit.text().strip() or osc_safe_name(self.name_edit.text())
        name = osc_safe_name(raw) or "Entry"
        base = f"/avatar/parameters/ShockPanel/{name}"
        mode_hint = {
            "trigger": "rising edge → one-shot shock",
            "hold":    "true = shock continuously, false = stop",
        }.get(self.mode_combo.currentData(), "")
        self.paths_lbl.setText(
            f"{base}/Trigger       (bool — {mode_hint})\n"
            f"{base}/IntensityMin  (float 0–1 — get/set min intensity)\n"
            f"{base}/IntensityMax  (float 0–1 — get/set max intensity)\n"
            f"{base}/Duration      (float 0–1 — get/set duration, 0=0.5s, 1=10s)"
        )

    def _update_shocker_btn(self):
        n = len(self.selected_shocker_ids)
        self.shocker_btn.setText(
            f"Select Shockers ({n} selected)" if n else "Select Shockers (All)")

    def _pick_shockers(self):
        dlg = ShockerSelectionDialog(self, self.config, self.selected_shocker_ids)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.selected_shocker_ids = dlg.get_selected()
            self._update_shocker_btn()

    def _validate(self):
        if not self.name_edit.text().strip():
            QMessageBox.critical(self, "Error", "Name cannot be empty."); return
        self.accept()

    def get_data(self):
        raw_osc = self.osc_name_edit.text().strip() or osc_safe_name(self.name_edit.text())
        return {
            "name":        self.name_edit.text().strip(),
            "osc_name":    osc_safe_name(raw_osc),
            "mode":        self.mode_combo.currentData(),
            "shocker_ids": self.selected_shocker_ids,
            "enabled":     self.enabled_cb.isChecked(),
        }


# ── Entry point ───────────────────────────────────────────────────────────────

def show_settings_gui(messenger=None):
    gui = VRCChatboxGUI(messenger)
    gui.run()


if __name__ == "__main__":
    show_settings_gui()
