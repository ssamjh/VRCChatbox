import sys
import threading
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
from PyQt6.QtGui import QFont

from config import load_app_config, save_app_config

# ── Palette ───────────────────────────────────────────────────────────────────
# Inline SVG arrow for combobox (border-trick doesn't work in Qt)
_ARROW_SVG = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6'><polygon points='0,0 10,0 5,6' fill='%23CAC4D0'/></svg>"

# Inline SVG radio-button indicators — CSS background-color on ::indicator is unreliable
_RADIO_OFF_SVG     = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'><circle cx='9' cy='9' r='7.5' fill='none' stroke='%23938F99' stroke-width='2'/></svg>"
_RADIO_HOVER_SVG   = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'><circle cx='9' cy='9' r='7.5' fill='none' stroke='%23D0BCFF' stroke-width='2'/></svg>"
_RADIO_ON_SVG      = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'><circle cx='9' cy='9' r='7.5' fill='none' stroke='%23D0BCFF' stroke-width='2'/><circle cx='9' cy='9' r='4.5' fill='%23D0BCFF'/></svg>"

BG       = "#1C1B1F"   # main background
SURFACE  = "#2B2930"   # cards / sidebar
SURFACE2 = "#37333E"   # elevated cards inside cards
PRIMARY  = "#D0BCFF"   # purple accent
PRIM_CON = "#4F378B"   # primary container (selection)
ON_SURF  = "#E6E1E5"   # primary text
ON_VAR   = "#CAC4D0"   # secondary text
OUTLINE  = "#938F99"   # input borders
OUT_VAR  = "#49454F"   # subtle borders
POSITIVE = "#A8D5A2"   # status/success green

STYLE = f"""
QMainWindow, QDialog {{
    background-color: {BG};
}}
QWidget {{
    background-color: {BG};
    color: {ON_SURF};
    font-family: 'Segoe UI', 'Roboto', Arial, sans-serif;
    font-size: 10pt;
}}

/* ── Sidebar ── */
QWidget#sidebar {{
    background-color: {SURFACE};
    border-right: 1px solid {OUT_VAR};
}}

/* ── Content pages ── */
QStackedWidget, QStackedWidget > QWidget {{
    background-color: {BG};
}}

/* ── Group/card boxes ── */
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {OUT_VAR};
    border-radius: 12px;
    margin-top: 16px;
    padding: 14px 16px 14px 16px;
    font-weight: bold;
    font-size: 10pt;
    color: {PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: {SURFACE};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {SURFACE2};
    color: {ON_SURF};
    border: none;
    border-radius: 20px;
    padding: 8px 20px;
    min-width: 72px;
    font-weight: 500;
    font-size: 10pt;
}}
QPushButton:hover {{
    background-color: #4A4458;
}}
QPushButton:pressed {{
    background-color: {PRIMARY};
    color: {BG};
}}
QPushButton:disabled {{
    background-color: {SURFACE};
    color: {OUT_VAR};
}}

/* Stepper ± buttons — square, no pill radius */
QPushButton#stepper_btn {{
    background-color: {SURFACE2};
    color: {PRIMARY};
    border: 1px solid {OUT_VAR};
    border-radius: 6px;
    padding: 0;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 16pt;
    font-weight: bold;
}}
QPushButton#stepper_btn:hover {{
    background-color: #4A4458;
    border-color: {PRIMARY};
}}
QPushButton#stepper_btn:pressed {{
    background-color: {PRIMARY};
    color: {BG};
}}

/* Nav rail buttons — use :checked so no setStyleSheet() in click handlers */
QPushButton#nav_btn {{
    background-color: transparent;
    color: {ON_VAR};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    padding: 16px 28px;
    min-width: 0;
    min-height: 48px;
    text-align: left;
    font-size: 10pt;
}}
QPushButton#nav_btn:hover {{
    background-color: rgba(208, 188, 255, 0.08);
    color: {ON_SURF};
    border-left: 3px solid transparent;
}}
QPushButton#nav_btn:checked {{
    background-color: rgba(79, 55, 139, 0.35);
    color: {PRIMARY};
    border-left: 3px solid {PRIMARY};
    font-weight: bold;
}}

/* ── Inputs ── */
QLineEdit, QComboBox {{
    background-color: {SURFACE};
    color: {ON_SURF};
    border: 1px solid {OUTLINE};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 10pt;
    selection-background-color: {PRIM_CON};
    selection-color: {ON_SURF};
    min-height: 20px;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {PRIMARY};
    padding: 7px 11px;
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: {ON_VAR};
}}

/* Stepper's internal QSpinBox — borderless, transparent */
QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE};
    color: {ON_SURF};
    border: 1px solid {OUTLINE};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 10pt;
    min-height: 20px;
    selection-background-color: {PRIM_CON};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {PRIMARY};
}}
/* Hide native buttons — we use our own */
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0; height: 0; border: none;
}}

/* ── Combo ── */
QComboBox::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 28px;
    background-color: {SURFACE2};
    border-left: 1px solid {OUT_VAR};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QComboBox::down-arrow {{
    image: url({_ARROW_SVG});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {ON_SURF};
    border: 1px solid {OUT_VAR};
    border-radius: 8px;
    selection-background-color: {SURFACE2};
    outline: none;
    padding: 4px;
}}

/* ── Checkboxes & radios ── */
QCheckBox, QRadioButton {{
    color: {ON_SURF};
    spacing: 10px;
    font-size: 10pt;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 2px solid {OUTLINE};
    border-radius: 4px;
    background-color: transparent;
}}
QCheckBox::indicator:hover {{ border-color: {PRIMARY}; }}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}
QRadioButton::indicator {{
    width: 18px; height: 18px;
    image: url({_RADIO_OFF_SVG});
}}
QRadioButton::indicator:hover {{
    image: url({_RADIO_HOVER_SVG});
}}
QRadioButton::indicator:checked {{
    image: url({_RADIO_ON_SVG});
}}

/* ── Table ── */
QTableWidget {{
    background-color: {SURFACE};
    color: {ON_SURF};
    border: 1px solid {OUT_VAR};
    border-radius: 10px;
    gridline-color: {OUT_VAR};
    alternate-background-color: {SURFACE2};
    font-size: 10pt;
}}
QTableWidget::item {{
    padding: 8px 18px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {PRIM_CON};
    color: {ON_SURF};
}}
QHeaderView::section {{
    background-color: {SURFACE2};
    color: {PRIMARY};
    border: none;
    border-right: 1px solid {OUT_VAR};
    border-bottom: 1px solid {OUT_VAR};
    padding: 8px 12px;
    font-weight: bold;
    font-size: 10pt;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {OUT_VAR};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {OUTLINE};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none; height: 0;
}}

/* ── Labels ── */
QLabel {{
    background-color: transparent;
    color: {ON_SURF};
}}
QLabel#section_title {{
    color: {PRIMARY};
    font-size: 18pt;
    font-weight: bold;
}}
QLabel#field_label {{
    color: {ON_VAR};
    font-size: 9pt;
}}
QLabel#status_lbl {{
    color: {POSITIVE};
    font-size: 9pt;
}}

/* ── Message boxes ── */
QMessageBox {{
    background-color: {SURFACE};
}}
QMessageBox QLabel {{
    color: {ON_SURF};
}}

/* ── Dialogs ── */
QDialog {{
    background-color: {SURFACE};
}}
QDialog QWidget {{
    background-color: {SURFACE};
}}
QDialog QGroupBox {{
    background-color: {SURFACE2};
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

        self.app.setStyle("Fusion")   # Fusion respects stylesheets; native Windows style ignores ::indicator etc.
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
            ("  General",  self._build_general_page()),
            ("  ShockOSC", self._build_shockosc_page()),
            ("  Slide",    self._build_slide_page()),
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
        self._stack.setCurrentIndex(index)
        self._nav_btns[index].setChecked(True)

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
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(_label("Slide", "section_title"))
        layout.addWidget(_hline())

        # Two-column header
        header_row = QHBoxLayout()
        header_row.setSpacing(24)
        layout.addLayout(header_row)

        # Left: enable + poll + intensity
        left = QVBoxLayout()
        left.setSpacing(20)
        header_row.addLayout(left, stretch=1)

        ctrl_card = QGroupBox("Controls")
        cc = QGridLayout(ctrl_card)
        cc.setSpacing(16)
        cc.setContentsMargins(20, 24, 20, 20)

        self.slide_enabled_cb = QCheckBox("Enable Slide Feature")
        self.slide_enabled_cb.setChecked(sl.get("enabled", False))
        self.slide_enabled_cb.toggled.connect(self.on_slide_settings_change)
        cc.addWidget(self.slide_enabled_cb, 0, 0, 1, 2)

        cc.addWidget(_label("Poll Interval (s)", "field_label"), 1, 0)
        self.slide_poll_spinbox = Stepper(0.1, 10.0, 0.1, sl.get("poll_interval", 1.0), decimals=1, spin_width=90)
        self.slide_poll_spinbox.valueChanged.connect(self.on_slide_settings_change)
        cc.addWidget(self.slide_poll_spinbox, 1, 1)

        left.addWidget(ctrl_card)

        # Right: intensity range
        right = QVBoxLayout()
        right.setSpacing(20)
        header_row.addLayout(right, stretch=1)

        int_card = QGroupBox("Value-Based Intensity Range")
        ic = QGridLayout(int_card)
        ic.setSpacing(16)
        ic.setContentsMargins(20, 24, 20, 20)

        ic.addWidget(_label("Min Intensity %", "field_label"), 0, 0)
        self.slide_min_spinbox = Stepper(0, 100, 5, sl.get("intensity_min", 30), spin_width=90)
        self.slide_min_spinbox.valueChanged.connect(self.on_slide_settings_change)
        ic.addWidget(self.slide_min_spinbox, 0, 1)

        ic.addWidget(_label("Max Intensity %", "field_label"), 1, 0)
        self.slide_max_spinbox = Stepper(0, 100, 5, sl.get("intensity_max", 70), spin_width=90)
        self.slide_max_spinbox.valueChanged.connect(self.on_slide_settings_change)
        ic.addWidget(self.slide_max_spinbox, 1, 1)

        ic.addWidget(_label("Prob. Cooldown (s)", "field_label"), 2, 0)
        self.slide_prob_cooldown_spinbox = Stepper(0.0, 60.0, 1.0, sl.get("probability_cooldown", 10.0), decimals=1, spin_width=90)
        self.slide_prob_cooldown_spinbox.valueChanged.connect(self.on_slide_settings_change)
        ic.addWidget(self.slide_prob_cooldown_spinbox, 2, 1)

        right.addWidget(int_card)

        # Variables section
        vars_card = QGroupBox("OSC Variables")
        vc = QVBoxLayout(vars_card)
        vc.setSpacing(14)
        vc.setContentsMargins(20, 24, 20, 20)

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
        self.slide_vars_table.setMinimumHeight(200)
        vc.addWidget(self.slide_vars_table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        add_btn = QPushButton("Add Variable")
        add_btn.clicked.connect(self.add_slide_variable)
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self.edit_slide_variable)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_slide_variable)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        vc.addLayout(btn_row)

        layout.addWidget(vars_card)
        layout.addStretch()

        self.refresh_slide_variables_display()
        return page

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
        variables = self.config.get("slide", {}).get("variables", [])
        if row >= len(variables): return
        dlg = SlideVariableDialog(self, variables[row], self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            variables[row] = dlg.get_data()
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
        variables = self.config.get("slide", {}).get("variables", [])
        if row < len(variables):
            del variables[row]
            save_app_config(self.config)
            self.refresh_slide_variables_display()
            self.update_slide_controller()

    def refresh_slide_variables_display(self):
        self.slide_vars_table.setRowCount(0)
        for v in self.config.get("slide", {}).get("variables", []):
            r = self.slide_vars_table.rowCount()
            self.slide_vars_table.insertRow(r)
            shockers = v.get("shockers", [])
            hold = f"{v.get('hold_time', 3.0)}s" if v.get("hold_mode") else "—"
            self.slide_vars_table.setItem(r, 0, QTableWidgetItem(v.get("name", "")))
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
            "probability_cooldown": round(self.slide_prob_cooldown_spinbox.value(), 1),
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


# ── Entry point ───────────────────────────────────────────────────────────────

def show_settings_gui(messenger=None):
    gui = VRCChatboxGUI(messenger)
    gui.run()


if __name__ == "__main__":
    show_settings_gui()
