try:
    from PySide6.QtCore import Qt, Signal, QEvent
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
        QListWidgetItem, QPushButton, QLabel, QLineEdit, QFormLayout,
        QComboBox, QTextEdit, QWidget, QMenu, QStackedWidget,
        QInputDialog, QMessageBox, QToolButton, QSpinBox, QSlider,
        QTabWidget, QRadioButton, QButtonGroup, QSizePolicy, QFrame,
        QAbstractItemView, QColorDialog, QCheckBox
    )
    from PySide6.QtGui import QIcon, QColor
except ImportError:
    from PySide2.QtCore import Qt, Signal, QEvent
    from PySide2.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
        QListWidgetItem, QPushButton, QLabel, QLineEdit, QFormLayout,
        QComboBox, QTextEdit, QWidget, QMenu, QStackedWidget,
        QInputDialog, QMessageBox, QToolButton, QSpinBox, QSlider,
        QTabWidget, QRadioButton, QButtonGroup, QSizePolicy, QFrame,
        QAbstractItemView, QColorDialog, QCheckBox
    )
    from PySide2.QtGui import QIcon, QColor

import maya.cmds as cmds
from . import core
from . import widgets

_manager_instance = None


class ColorButtonWithSlider(QWidget):
    colorChanged = Signal(list)

    def __init__(self, support_alpha=False, parent=None):
        super(ColorButtonWithSlider, self).__init__(parent)
        self._color = None
        self._support_alpha = support_alpha
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(120, 24)
        self._color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self._color_btn)

        if self._support_alpha:
            self._slider = QSlider(Qt.Horizontal)
            self._slider.setRange(0, 100)
            self._slider.setValue(100)
            self._slider.setMinimumWidth(80)
            self._slider.valueChanged.connect(self._on_slider_changed)
            layout.addWidget(self._slider, 1)

            self._alpha_label = QLabel("100%")
            self._alpha_label.setFixedWidth(40)
            layout.addWidget(self._alpha_label)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setFixedWidth(90)
        self._reset_btn.clicked.connect(self.clear_color)
        layout.addWidget(self._reset_btn)

        layout.addStretch()
        self._update_style()

    def _update_style(self):
        disabled_style = "QPushButton:disabled { background-color: rgb(56, 56, 56); color: rgb(100, 100, 100); }"
        if self._color:
            r, g, b = [int(c * 255) for c in self._color[:3]]
            if self._support_alpha and len(self._color) > 3:
                a = int(self._color[3] * 255)
                self._color_btn.setStyleSheet(
                    "QPushButton {{ background-color: rgba({},{},{},{}); border: 1px solid #555; }} {}".format(r, g, b, a, disabled_style))
            else:
                self._color_btn.setStyleSheet(
                    "QPushButton {{ background-color: rgb({},{},{}); border: 1px solid #555; }} {}".format(r, g, b, disabled_style))
            self._color_btn.setText("")
        else:
            self._color_btn.setStyleSheet("QPushButton {{ border: 1px solid #555; }} {}".format(disabled_style))
            self._color_btn.setText("None")

    def _pick_color(self):
        initial = QColor(127, 127, 127)
        if self._color:
            initial = QColor(int(self._color[0] * 255), int(self._color[1] * 255), int(self._color[2] * 255))

        # Use top-level window as parent so dialog inherits WindowStaysOnTopHint
        parent_window = self.window()
        color = QColorDialog.getColor(initial, parent_window, "Select Color")

        if color.isValid():
            rgb = [color.redF(), color.greenF(), color.blueF()]
            if self._support_alpha:
                alpha = self._slider.value() / 100.0
                self._color = [rgb[0], rgb[1], rgb[2], alpha]
            else:
                self._color = rgb
            self._update_style()
            self.colorChanged.emit(self._color)

    def _on_slider_changed(self, value):
        self._alpha_label.setText("{}%".format(value))
        if self._color and len(self._color) >= 3:
            self._color = [self._color[0], self._color[1], self._color[2], value / 100.0]
            self._update_style()
            self.colorChanged.emit(self._color)

    def color(self):
        return self._color

    def setColor(self, color):
        self._color = color
        if self._support_alpha and color and len(color) > 3:
            self._slider.blockSignals(True)
            self._slider.setValue(int(color[3] * 100))
            self._alpha_label.setText("{}%".format(int(color[3] * 100)))
            self._slider.blockSignals(False)
        self._update_style()

    def clear_color(self):
        self._color = None
        if self._support_alpha:
            self._slider.setValue(100)
        self._update_style()
        self.colorChanged.emit(self._color)


class TriggerSettingsDialog(QDialog):
    ACTIONS = [
        ("main_command", "Execute Main Command"),
        ("secondary_command", "Execute Secondary Command"),
        ("open_manager", "Open Manager Panel"),
        ("show_submenu", "Open Popup Menu (Submenu)"),
    ]

    TRIGGERS = [
        ("lmb_click", "LMB Single Click"),
        ("shift_lmb_click", "Shift + LMB Click"),
        ("lmb_hold", "LMB Hold"),
        ("rmb_click", "RMB Single Click"),
        ("lmb_double_click", "LMB Double Click"),
        ("not_set", "Not set"),
    ]

    def __init__(self, parent=None):
        super(TriggerSettingsDialog, self).__init__(parent)
        self.setWindowTitle("Set Trigger Mechanism")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(400)
        self._combos = {}
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Form layout for dropdowns
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight)

        for key, label in self.ACTIONS:
            combo = QComboBox()
            for trig_key, trig_label in self.TRIGGERS:
                combo.addItem(trig_label, trig_key)
            combo.currentIndexChanged.connect(lambda idx, k=key: self._on_combo_changed(k))
            self._combos[key] = combo
            form.addRow(label + ":", combo)

        layout.addLayout(form)

        # Validation message
        self._validation_label = QLabel("All options must be unique and set before saving.")
        self._validation_label.setStyleSheet("color: #888;")
        layout.addWidget(self._validation_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _load_settings(self):
        triggers = core.get_trigger_settings()
        for key, combo in self._combos.items():
            val = triggers.get(key, "not_set")
            idx = combo.findData(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._update_validation()

    def _on_combo_changed(self, changed_key):
        changed_combo = self._combos[changed_key]
        new_val = changed_combo.currentData()

        # If new value is "not_set", no conflict possible
        if new_val == "not_set":
            self._update_validation()
            return

        # Auto-clear any other combo that has the same value
        for key, combo in self._combos.items():
            if key != changed_key and combo.currentData() == new_val:
                not_set_idx = combo.findData("not_set")
                combo.blockSignals(True)
                combo.setCurrentIndex(not_set_idx)
                combo.blockSignals(False)

        self._update_validation()

    def _update_validation(self):
        valid = self._is_valid()
        self._save_btn.setEnabled(valid)
        if valid:
            self._validation_label.setStyleSheet("color: #4a4;")
            self._validation_label.setText("Settings are valid and can be saved.")
        else:
            self._validation_label.setStyleSheet("color: #a44;")
            self._validation_label.setText("All options must be unique and set before saving.")

    def _is_valid(self):
        values = []
        for combo in self._combos.values():
            val = combo.currentData()
            if val == "not_set":
                return False
            if val in values:
                return False
            values.append(val)
        return True

    def _save_and_close(self):
        if not self._is_valid():
            return
        triggers = {}
        for key, combo in self._combos.items():
            triggers[key] = combo.currentData()
        core.set_trigger_settings(triggers)
        self.close()


class ShelfManager(QDialog):

    def __init__(self, parent=None, select_shelf=None, select_button=None):
        super(ShelfManager, self).__init__(parent)
        self._current_shelf = None
        self._current_button_indices = []
        self._select_shelf = select_shelf
        self._select_button = select_button
        self._clipboard = None
        self._submenu_items = []

        self.setWindowTitle("Neo Shelf Manager v1.0")
        self.setMinimumSize(1425, 1225)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._build_ui()
        self._refresh_shelf_list()

        if select_shelf:
            self._select_shelf_by_name(select_shelf)
            if select_button is not None:
                self._button_list.setCurrentRow(select_button)
                self._options_stack.setCurrentIndex(1)
                self._update_column_highlight(1)
            else:
                self._options_stack.setCurrentIndex(0)
                self._update_column_highlight(0)
        else:
            if self._shelf_list.count() > 0:
                self._shelf_list.setCurrentRow(0)
            self._options_stack.setCurrentIndex(0)
            self._update_column_highlight(0)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # Style disabled fields to match background
        self.setStyleSheet("""
            QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled,
            QComboBox:disabled, QSlider:disabled {
                background-color: rgb(56, 56, 56);
                color: rgb(100, 100, 100);
            }
            QPushButton:disabled {
                background-color: rgb(56, 56, 56);
                color: rgb(100, 100, 100);
            }
            QRadioButton:disabled {
                color: rgb(100, 100, 100);
            }
        """)

        # Main vertical splitter (columns on top, options below)
        self._main_splitter = QSplitter(Qt.Vertical)

        # Top area: two columns
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_splitter = QSplitter(Qt.Horizontal)

        # Left column - Shelves
        self._shelf_widget = QWidget()
        shelf_layout = QVBoxLayout(self._shelf_widget)
        shelf_layout.setContentsMargins(4, 4, 4, 4)
        shelf_layout.addWidget(QLabel("Shelves"))
        self._shelf_list = QListWidget()
        self._shelf_list.currentRowChanged.connect(self._on_shelf_selected)
        self._shelf_list.itemClicked.connect(self._on_shelf_clicked)
        self._shelf_list.viewport().installEventFilter(self)
        shelf_layout.addWidget(self._shelf_list)
        top_splitter.addWidget(self._shelf_widget)

        # Right column - Buttons
        self._button_widget = QWidget()
        button_layout = QVBoxLayout(self._button_widget)
        button_layout.setContentsMargins(4, 4, 4, 4)
        button_layout.addWidget(QLabel("Buttons"))
        self._button_list = QListWidget()
        self._button_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._button_list.itemSelectionChanged.connect(self._on_button_selection_changed)
        self._button_list.itemClicked.connect(self._on_button_clicked)
        self._button_list.setDragDropMode(QListWidget.InternalMove)
        self._button_list.model().rowsMoved.connect(self._on_buttons_reordered)
        self._button_list.viewport().installEventFilter(self)
        button_layout.addWidget(self._button_list)
        top_splitter.addWidget(self._button_widget)

        top_splitter.setSizes([250, 350])
        top_layout.addWidget(top_splitter)
        self._main_splitter.addWidget(top_widget)

        # Bottom area: stacked widget for options
        self._options_stack = QStackedWidget()
        self._shelf_options = self._build_shelf_options()
        self._button_options = self._build_button_options()
        self._options_stack.addWidget(self._shelf_options)
        self._options_stack.addWidget(self._button_options)
        self._main_splitter.addWidget(self._options_stack)

        self._main_splitter.setSizes([350, 300])
        main_layout.addWidget(self._main_splitter, 1)

        # Bottom buttons row
        bottom_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh All Panels")
        self._refresh_btn.clicked.connect(self._refresh_panels)
        bottom_row.addWidget(self._refresh_btn)

        self._import_btn = QPushButton("Import Native Shelf")
        self._import_btn.clicked.connect(self._import_native_shelf)
        bottom_row.addWidget(self._import_btn)

        self._trigger_btn = QPushButton("Set Trigger Mechanism")
        self._trigger_btn.clicked.connect(self._open_trigger_settings)
        bottom_row.addWidget(self._trigger_btn)

        self._help_btn = QPushButton("Help")
        self._help_btn.clicked.connect(self._open_help)
        bottom_row.addWidget(self._help_btn)

        bottom_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn)
        main_layout.addLayout(bottom_row)

    def _build_shelf_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Buttons row
        btn_row = QHBoxLayout()

        self._shelf_open_btn = QPushButton("Open")
        self._shelf_open_btn.setStyleSheet("QPushButton { background-color: #337928; }")
        self._shelf_open_btn.clicked.connect(self._open_shelf_panel)
        btn_row.addWidget(self._shelf_open_btn)

        self._shelf_new_btn = QPushButton("New")
        self._shelf_new_btn.clicked.connect(self._create_shelf)
        btn_row.addWidget(self._shelf_new_btn)

        self._shelf_dup_btn = QPushButton("Duplicate")
        self._shelf_dup_btn.clicked.connect(self._duplicate_shelf)
        btn_row.addWidget(self._shelf_dup_btn)

        self._shelf_refresh_btn = QPushButton("Refresh Panel")
        self._shelf_refresh_btn.clicked.connect(self._refresh_current_panel)
        btn_row.addWidget(self._shelf_refresh_btn)

        self._shelf_close_btn = QPushButton("Close Panel")
        self._shelf_close_btn.clicked.connect(self._close_shelf_panel)
        btn_row.addWidget(self._shelf_close_btn)

        self._shelf_delete_btn = QPushButton("Delete")
        self._shelf_delete_btn.setStyleSheet("QPushButton { background-color: #792425; }")
        self._shelf_delete_btn.clicked.connect(self._delete_shelf)
        btn_row.addWidget(self._shelf_delete_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Settings form
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Name
        name_row = QHBoxLayout()
        self._shelf_name_edit = QLineEdit()
        name_row.addWidget(self._shelf_name_edit, 1)
        self._shelf_name_save = QPushButton("Save")
        self._shelf_name_save.setFixedWidth(50)
        self._shelf_name_save.clicked.connect(self._save_shelf_name)
        name_row.addWidget(self._shelf_name_save)
        form.addRow("Name:", name_row)

        # Icon size
        size_row = QHBoxLayout()
        self._shelf_icon_size = QSpinBox()
        self._shelf_icon_size.setRange(35, 150)
        self._shelf_icon_size.setValue(55)
        self._shelf_icon_size.valueChanged.connect(self._on_shelf_setting_changed)
        size_row.addWidget(self._shelf_icon_size)
        size_row.addStretch()
        form.addRow("Icon Size:", size_row)

        # BG Color
        self._shelf_bg_color = ColorButtonWithSlider(support_alpha=True)
        self._shelf_bg_color.colorChanged.connect(self._on_shelf_setting_changed)
        form.addRow("BG Color:", self._shelf_bg_color)

        # Highlight Color
        self._shelf_highlight_color = ColorButtonWithSlider(support_alpha=True)
        self._shelf_highlight_color.colorChanged.connect(self._on_shelf_setting_changed)
        form.addRow("Highlight:", self._shelf_highlight_color)

        # Alignment
        align_row = QHBoxLayout()
        self._shelf_alignment = QComboBox()
        self._shelf_alignment.addItems(["left", "center", "right"])
        self._shelf_alignment.currentTextChanged.connect(self._on_shelf_setting_changed)
        align_row.addWidget(self._shelf_alignment)
        align_row.addStretch()
        form.addRow("Alignment:", align_row)

        # Layout
        layout_row = QHBoxLayout()
        self._shelf_layout = QComboBox()
        self._shelf_layout.addItems(["horizontal", "vertical", "flow"])
        self._shelf_layout.currentTextChanged.connect(self._on_shelf_layout_changed)
        layout_row.addWidget(self._shelf_layout)
        layout_row.addStretch()
        form.addRow("Layout:", layout_row)

        # Hide highlight checkbox
        self._shelf_hide_highlight = QCheckBox(
            "Do not show Highlight color (It may not be possible to see where new shelf items get added, unless being dragged to)"
        )
        self._shelf_hide_highlight.stateChanged.connect(self._on_shelf_setting_changed)
        form.addRow("", self._shelf_hide_highlight)

        layout.addLayout(form)
        return widget

    def _build_button_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Buttons row
        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add")
        self._btn_add.clicked.connect(self._add_button)
        btn_row.addWidget(self._btn_add)

        self._btn_add_sep = QPushButton("Add Sep")
        self._btn_add_sep.clicked.connect(self._add_separator)
        btn_row.addWidget(self._btn_add_sep)

        self._btn_dup = QPushButton("Duplicate")
        self._btn_dup.clicked.connect(self._duplicate_button)
        btn_row.addWidget(self._btn_dup)

        self._btn_del = QPushButton("Delete")
        self._btn_del.setStyleSheet("QPushButton { background-color: #792425; }")
        self._btn_del.clicked.connect(self._delete_button)
        btn_row.addWidget(self._btn_del)

        # Transfer to menu button
        self._btn_transfer = QPushButton("Transfer to")
        self._transfer_menu = QMenu()
        self._btn_transfer.setMenu(self._transfer_menu)
        btn_row.addWidget(self._btn_transfer)

        # Copy to menu button
        self._btn_copy_to = QPushButton("Copy to")
        self._copy_menu = QMenu()
        self._btn_copy_to.setMenu(self._copy_menu)
        btn_row.addWidget(self._btn_copy_to)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Tabs
        self._button_tabs = QTabWidget()
        self._button_tabs.addTab(self._build_main_tab(), "Main")
        self._button_tabs.addTab(self._build_command_tab(), "Command")
        self._button_tabs.addTab(self._build_secondary_tab(), "Secondary Command")
        self._button_tabs.addTab(self._build_submenu_tab(), "Submenus")
        layout.addWidget(self._button_tabs)

        return widget

    def _build_main_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Name
        self._btn_name_edit = QLineEdit()
        self._btn_name_edit.textChanged.connect(self._on_button_prop_changed)
        layout.addRow("Name:", self._btn_name_edit)

        # Icon
        icon_row = QHBoxLayout()
        self._btn_icon_edit = QLineEdit()
        self._btn_icon_edit.textChanged.connect(self._on_button_prop_changed)
        icon_row.addWidget(self._btn_icon_edit, 1)
        self._btn_icon_browse = QPushButton("Browse")
        self._btn_icon_browse.setFixedWidth(90)
        self._btn_icon_browse.clicked.connect(self._browse_icon)
        icon_row.addWidget(self._btn_icon_browse)
        layout.addRow("Icon:", icon_row)

        # Icon Label
        self._btn_label_edit = QLineEdit()
        self._btn_label_edit.textChanged.connect(self._on_button_prop_changed)
        layout.addRow("Icon Label:", self._btn_label_edit)

        # Tooltip
        self._btn_tooltip_edit = QLineEdit()
        self._btn_tooltip_edit.textChanged.connect(self._on_button_prop_changed)
        layout.addRow("Tooltip:", self._btn_tooltip_edit)

        # Icon Background Color
        self._btn_bg_color = ColorButtonWithSlider(support_alpha=True)
        self._btn_bg_color.colorChanged.connect(self._on_button_color_changed)
        layout.addRow("Icon Background Color:", self._btn_bg_color)

        # Icon Tint Color
        self._btn_icon_tint = ColorButtonWithSlider(support_alpha=False)
        self._btn_icon_tint.colorChanged.connect(self._on_button_color_changed)
        layout.addRow("Icon Tint Color:", self._btn_icon_tint)

        # Label Background Color
        self._btn_label_bg_color = ColorButtonWithSlider(support_alpha=True)
        self._btn_label_bg_color.colorChanged.connect(self._on_button_color_changed)
        layout.addRow("Label Background Color:", self._btn_label_bg_color)

        # Label Text Color
        self._btn_label_text_color = ColorButtonWithSlider(support_alpha=False)
        self._btn_label_text_color.colorChanged.connect(self._on_button_color_changed)
        layout.addRow("Label Text Color:", self._btn_label_text_color)

        return widget

    def _build_command_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._cmd_edit = QTextEdit()
        self._cmd_edit.textChanged.connect(self._on_button_prop_changed)
        self._cmd_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._cmd_edit, 1)

        type_row = QHBoxLayout()
        self._cmd_type_group = QButtonGroup(self)
        self._cmd_python = QRadioButton("Python")
        self._cmd_mel = QRadioButton("MEL")
        self._cmd_python.setChecked(True)
        self._cmd_type_group.addButton(self._cmd_python)
        self._cmd_type_group.addButton(self._cmd_mel)
        self._cmd_python.toggled.connect(self._on_button_prop_changed)
        type_row.addWidget(self._cmd_python)
        type_row.addWidget(self._cmd_mel)
        type_row.addStretch()
        layout.addLayout(type_row)

        self._cmd_unavailable = QLabel("Unavailable for separators")
        self._cmd_unavailable.setStyleSheet("color: #888;")
        self._cmd_unavailable.hide()
        layout.addWidget(self._cmd_unavailable)

        return widget

    def _build_secondary_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._shift_cmd_edit = QTextEdit()
        self._shift_cmd_edit.textChanged.connect(self._on_button_prop_changed)
        self._shift_cmd_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._shift_cmd_edit, 1)

        type_row = QHBoxLayout()
        self._shift_type_group = QButtonGroup(self)
        self._shift_python = QRadioButton("Python")
        self._shift_mel = QRadioButton("MEL")
        self._shift_python.setChecked(True)
        self._shift_type_group.addButton(self._shift_python)
        self._shift_type_group.addButton(self._shift_mel)
        self._shift_python.toggled.connect(self._on_button_prop_changed)
        type_row.addWidget(self._shift_python)
        type_row.addWidget(self._shift_mel)
        type_row.addStretch()
        layout.addLayout(type_row)

        self._shift_unavailable = QLabel("Unavailable for separators")
        self._shift_unavailable.setStyleSheet("color: #888;")
        self._shift_unavailable.hide()
        layout.addWidget(self._shift_unavailable)

        return widget

    def _build_submenu_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Buttons row
        btn_row = QHBoxLayout()
        self._sub_add = QPushButton("Add")
        self._sub_add.clicked.connect(self._add_submenu_item)
        btn_row.addWidget(self._sub_add)

        self._sub_remove = QPushButton("Remove")
        self._sub_remove.clicked.connect(self._remove_submenu_item)
        btn_row.addWidget(self._sub_remove)

        self._sub_add_sep = QPushButton("Add Separator")
        self._sub_add_sep.clicked.connect(self._add_submenu_separator)
        btn_row.addWidget(self._sub_add_sep)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Two-column splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: list
        self._submenu_list = QListWidget()
        self._submenu_list.setDragDropMode(QListWidget.InternalMove)
        self._submenu_list.currentRowChanged.connect(self._on_submenu_selected)
        self._submenu_list.model().rowsMoved.connect(self._on_submenu_reordered)
        splitter.addWidget(self._submenu_list)

        # Right: editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        self._sub_cmd_edit = QTextEdit()
        self._sub_cmd_edit.textChanged.connect(self._on_submenu_changed)
        self._sub_cmd_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self._sub_cmd_edit, 1)

        # Label row
        label_row = QHBoxLayout()
        label_row.addWidget(QLabel("Label:"))
        self._sub_label_edit = QLineEdit()
        self._sub_label_edit.textChanged.connect(self._on_submenu_changed)
        label_row.addWidget(self._sub_label_edit, 1)
        right_layout.addLayout(label_row)

        # Type row
        type_row = QHBoxLayout()
        self._sub_type_group = QButtonGroup(self)
        self._sub_python = QRadioButton("Python")
        self._sub_mel = QRadioButton("MEL")
        self._sub_python.setChecked(True)
        self._sub_type_group.addButton(self._sub_python)
        self._sub_type_group.addButton(self._sub_mel)
        self._sub_python.toggled.connect(self._on_submenu_changed)
        type_row.addWidget(self._sub_python)
        type_row.addWidget(self._sub_mel)
        type_row.addStretch()
        right_layout.addLayout(type_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([150, 350])
        layout.addWidget(splitter, 1)

        # Disable editor by default until something is selected
        self._sub_cmd_edit.setEnabled(False)
        self._sub_label_edit.setEnabled(False)
        self._sub_python.setEnabled(False)
        self._sub_mel.setEnabled(False)

        self._submenu_unavailable = QLabel("Unavailable for separators")
        self._submenu_unavailable.setStyleSheet("color: #888;")
        self._submenu_unavailable.hide()
        layout.addWidget(self._submenu_unavailable)

        return widget

    # Shelf list operations
    def _is_panel_open(self, shelf_name):
        panel_name = widgets.PANEL_PREFIX + shelf_name.replace(" ", "_") + "WorkspaceControl"
        config = core.load_config()
        return panel_name in config.get("panels", {})

    def _get_shelf_display_name(self, shelf_name):
        if self._is_panel_open(shelf_name):
            return shelf_name
        return "[CLOSED] " + shelf_name

    def _get_shelf_real_name(self, display_name):
        if display_name.startswith("[CLOSED] "):
            return display_name[9:]
        return display_name

    def _update_panel_buttons(self):
        if not self._current_shelf:
            self._shelf_open_btn.setEnabled(False)
            self._shelf_close_btn.setEnabled(False)
            self._shelf_refresh_btn.setEnabled(False)
            return

        is_open = self._is_panel_open(self._current_shelf)
        self._shelf_open_btn.setEnabled(not is_open)
        self._shelf_close_btn.setEnabled(is_open)
        self._shelf_refresh_btn.setEnabled(is_open)

    def _refresh_shelf_list(self):
        self._shelf_list.clear()
        for name in core.get_all_shelf_names():
            display = self._get_shelf_display_name(name)
            self._shelf_list.addItem(QListWidgetItem(display))

        selected = False
        if self._current_shelf:
            display = self._get_shelf_display_name(self._current_shelf)
            items = self._shelf_list.findItems(display, Qt.MatchExactly)
            if items:
                self._shelf_list.setCurrentItem(items[0])
                selected = True

        # Fallback: select first item if nothing selected
        if not selected and self._shelf_list.count() > 0:
            self._shelf_list.setCurrentRow(0)

    def _select_shelf_by_name(self, name):
        display = self._get_shelf_display_name(name)
        items = self._shelf_list.findItems(display, Qt.MatchExactly)
        if items:
            self._shelf_list.setCurrentItem(items[0])

    def _on_shelf_selected(self, row):
        if row < 0:
            self._current_shelf = None
            self._refresh_button_list()
            self._update_panel_buttons()
            return

        item = self._shelf_list.item(row)
        display_name = item.text()
        self._current_shelf = self._get_shelf_real_name(display_name)
        self._refresh_button_list()
        self._load_shelf_settings()
        self._update_panel_buttons()
        self._options_stack.setCurrentIndex(0)

    def _on_shelf_clicked(self, item):
        self._options_stack.setCurrentIndex(0)
        self._update_column_highlight(0)

    def _load_shelf_settings(self):
        if not self._current_shelf:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        self._shelf_name_edit.blockSignals(True)
        self._shelf_icon_size.blockSignals(True)
        self._shelf_alignment.blockSignals(True)
        self._shelf_layout.blockSignals(True)
        self._shelf_hide_highlight.blockSignals(True)

        self._shelf_name_edit.setText(self._current_shelf)
        self._shelf_icon_size.setValue(shelf_data.get("icon_size", 55))
        self._shelf_bg_color.setColor(shelf_data.get("bg_color"))
        self._shelf_highlight_color.setColor(shelf_data.get("active_highlight_color"))

        alignment = shelf_data.get("alignment", "left")
        idx = self._shelf_alignment.findText(alignment)
        if idx >= 0:
            self._shelf_alignment.setCurrentIndex(idx)

        layout = shelf_data.get("layout", "horizontal")
        idx = self._shelf_layout.findText(layout)
        if idx >= 0:
            self._shelf_layout.setCurrentIndex(idx)

        self._shelf_hide_highlight.setChecked(shelf_data.get("hide_highlight", False))

        self._update_alignment_enabled()

        self._shelf_name_edit.blockSignals(False)
        self._shelf_icon_size.blockSignals(False)
        self._shelf_alignment.blockSignals(False)
        self._shelf_layout.blockSignals(False)
        self._shelf_hide_highlight.blockSignals(False)

    def _update_alignment_enabled(self):
        layout_mode = self._shelf_layout.currentText()
        # Alignment only works in horizontal mode
        self._shelf_alignment.setEnabled(layout_mode == "horizontal")

    def _on_shelf_setting_changed(self):
        if not self._current_shelf:
            return

        core.update_shelf_settings(
            self._current_shelf,
            icon_size=self._shelf_icon_size.value(),
            bg_color=self._shelf_bg_color.color(),
            active_highlight_color=self._shelf_highlight_color.color(),
            alignment=self._shelf_alignment.currentText(),
            hide_highlight=self._shelf_hide_highlight.isChecked()
        )

    def _on_shelf_layout_changed(self, text):
        self._update_alignment_enabled()
        if self._current_shelf:
            core.update_shelf_settings(self._current_shelf, layout=text)

    def _save_shelf_name(self):
        if not self._current_shelf:
            return

        new_name = self._shelf_name_edit.text().strip()
        if not new_name or new_name == self._current_shelf:
            return

        if new_name in core.get_all_shelf_names():
            QMessageBox.warning(self, "Error", "Shelf '{}' already exists.".format(new_name))
            self._shelf_name_edit.setText(self._current_shelf)
            return

        core.rename_shelf(self._current_shelf, new_name)
        self._current_shelf = new_name
        self._refresh_shelf_list()

    def _create_shelf(self):
        name, ok = QInputDialog.getText(self, "New Shelf", "Shelf name:")
        if ok and name:
            name = name.strip()
            if name in core.get_all_shelf_names():
                QMessageBox.warning(self, "Error", "Shelf '{}' already exists.".format(name))
                return
            core.create_shelf(name)
            self._current_shelf = name
            self._refresh_shelf_list()

    def _duplicate_shelf(self):
        if not self._current_shelf:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        name, ok = QInputDialog.getText(self, "Duplicate Shelf", "New shelf name:",
                                        text=self._current_shelf + "_copy")
        if ok and name:
            name = name.strip()
            if name in core.get_all_shelf_names():
                QMessageBox.warning(self, "Error", "Shelf '{}' already exists.".format(name))
                return

            core.create_shelf(name)
            import copy
            new_data = copy.deepcopy(shelf_data)
            new_data["buttons"] = copy.deepcopy(shelf_data.get("buttons", []))
            core.update_shelf_settings(name, **{k: v for k, v in new_data.items() if k != "buttons"})
            for btn in new_data.get("buttons", []):
                core.add_button_to_shelf(name, btn)

            self._current_shelf = name
            self._refresh_shelf_list()

    def _delete_shelf(self):
        if not self._current_shelf:
            return

        reply = QMessageBox.question(self, "Delete Shelf",
                                     "Delete shelf '{}'?".format(self._current_shelf),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            core.delete_shelf(self._current_shelf)
            self._current_shelf = None
            self._refresh_shelf_list()
            self._refresh_button_list()

    def _open_shelf_panel(self):
        if self._current_shelf:
            widgets.create_panel(self._current_shelf)
            self._refresh_shelf_list()
            self._update_panel_buttons()

    def _close_shelf_panel(self):
        if self._current_shelf:
            panel_name = widgets.PANEL_PREFIX + self._current_shelf.replace(" ", "_") + "WorkspaceControl"
            widgets.close_panel(panel_name)
            self._refresh_shelf_list()
            self._update_panel_buttons()

    def _refresh_current_panel(self):
        if self._current_shelf:
            widgets.refresh_all_panels()

    # Button list operations
    def _refresh_button_list(self):
        self._button_list.clear()
        self._current_button_indices = []

        if not self._current_shelf:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])
        for i, btn in enumerate(buttons):
            if btn.get("separator"):
                item = QListWidgetItem("--- Separator ---")
            else:
                display = btn.get("name") or btn.get("label") or btn.get("icon", "Button")
                item = QListWidgetItem(display)
                icon_path = btn.get("icon", "commandButton.png")
                if not ("/" in icon_path or "\\" in icon_path):
                    item.setIcon(QIcon(":{}".format(icon_path)))
                else:
                    item.setIcon(QIcon(icon_path))
            self._button_list.addItem(item)

        self._update_transfer_menus()

    def _update_transfer_menus(self):
        self._transfer_menu.clear()
        self._copy_menu.clear()

        for name in core.get_all_shelf_names():
            if name != self._current_shelf:
                self._transfer_menu.addAction(name, lambda n=name: self._transfer_buttons(n))
                self._copy_menu.addAction(name, lambda n=name: self._copy_buttons_to(n))

    def _on_button_selection_changed(self):
        self._current_button_indices = [idx.row() for idx in self._button_list.selectedIndexes()]
        self._load_button_props()
        self._update_button_controls()

    def _on_button_clicked(self, item):
        self._options_stack.setCurrentIndex(1)
        self._update_column_highlight(1)

    def _update_column_highlight(self, active_col):
        # 0 = shelf column active, 1 = button column active
        # Apply to list widget only (not the header label)
        active_style = "QListWidget { background-color: rgb(19, 22, 23); }"
        if active_col == 0:
            self._shelf_list.setStyleSheet(active_style)
            self._button_list.setStyleSheet("")
        else:
            self._shelf_list.setStyleSheet("")
            self._button_list.setStyleSheet(active_style)

    def _update_button_controls(self):
        count = len(self._current_button_indices)
        multi = count > 1
        has_selection = count > 0

        # Check if any separator is in selection
        has_separator = False
        if self._current_shelf and has_selection:
            shelf_data = core.get_shelf_data(self._current_shelf)
            if shelf_data:
                buttons = shelf_data.get("buttons", [])
                for idx in self._current_button_indices:
                    if idx < len(buttons) and buttons[idx].get("separator"):
                        has_separator = True
                        break

        # Single separator selected
        single_separator = count == 1 and has_separator

        # Buttons row
        self._btn_add.setEnabled(not multi)
        self._btn_add_sep.setEnabled(not multi)
        self._btn_dup.setEnabled(has_selection)
        self._btn_del.setEnabled(has_selection)
        self._btn_transfer.setEnabled(has_selection)
        self._btn_copy_to.setEnabled(has_selection)

        # Tab enabling based on selection
        # Command tab (index 1)
        self._button_tabs.setTabEnabled(1, has_selection and not multi and not single_separator)
        # Secondary Command tab (index 2)
        self._button_tabs.setTabEnabled(2, has_selection and not multi and not single_separator)
        # Submenus tab (index 3)
        self._button_tabs.setTabEnabled(3, has_selection and not multi and not single_separator)

        # Main tab field disabling
        main_tab = self._button_tabs.widget(0)

        # If multi-select or separator, disable text fields
        for child in main_tab.findChildren(QLineEdit):
            child.setEnabled(has_selection and not multi and not single_separator)

        # Browse button
        self._btn_icon_browse.setEnabled(has_selection and not multi and not single_separator)

        # Color controls: enabled unless multi with separator, or single separator
        colors_enabled = has_selection and not (multi and has_separator) and not single_separator
        self._btn_bg_color.setEnabled(colors_enabled)
        self._btn_icon_tint.setEnabled(colors_enabled)
        self._btn_label_bg_color.setEnabled(colors_enabled)
        self._btn_label_text_color.setEnabled(colors_enabled)

    def _load_button_props(self):
        if not self._current_shelf:
            self._clear_button_props()
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            self._clear_button_props()
            return

        buttons = shelf_data.get("buttons", [])
        count = len(self._current_button_indices)

        if count == 0:
            self._clear_button_props()
            return

        # Multi-selection: only load common color values
        if count > 1:
            self._load_multi_button_colors(buttons)
            self._clear_text_props()
            return

        # Single selection
        idx = self._current_button_indices[0]
        if idx >= len(buttons):
            self._clear_button_props()
            return

        btn = buttons[idx]
        is_separator = btn.get("separator", False)

        # Show/hide unavailable labels
        self._cmd_unavailable.setVisible(is_separator)
        self._cmd_edit.setVisible(not is_separator)
        self._cmd_python.setVisible(not is_separator)
        self._cmd_mel.setVisible(not is_separator)

        self._shift_unavailable.setVisible(is_separator)
        self._shift_cmd_edit.setVisible(not is_separator)
        self._shift_python.setVisible(not is_separator)
        self._shift_mel.setVisible(not is_separator)

        self._submenu_unavailable.setVisible(is_separator)
        self._submenu_list.setVisible(not is_separator)
        self._sub_cmd_edit.setVisible(not is_separator)

        if is_separator:
            self._clear_button_props()
            return

        # Block signals on all widgets that trigger _on_button_prop_changed
        widgets_to_block = [
            self._btn_name_edit, self._btn_icon_edit, self._btn_label_edit,
            self._btn_tooltip_edit, self._cmd_edit, self._shift_cmd_edit,
            self._cmd_python, self._cmd_mel, self._shift_python, self._shift_mel
        ]
        for w in widgets_to_block:
            w.blockSignals(True)

        # Load submenu first (before radio buttons that might trigger signals)
        self._submenu_items = list(btn.get("submenu", []))
        self._refresh_submenu_list()

        self._btn_name_edit.setText(btn.get("name", ""))
        self._btn_icon_edit.setText(btn.get("icon", ""))
        self._btn_label_edit.setText(btn.get("label", ""))
        self._btn_tooltip_edit.setText(btn.get("annotation", ""))
        self._btn_bg_color.setColor(btn.get("bg_color"))
        self._btn_icon_tint.setColor(btn.get("icon_tint"))
        self._btn_label_bg_color.setColor(btn.get("label_bg_color"))
        self._btn_label_text_color.setColor(btn.get("label_text_color"))

        self._cmd_edit.setPlainText(btn.get("command", ""))
        if btn.get("command_type", "python") == "mel":
            self._cmd_mel.setChecked(True)
        else:
            self._cmd_python.setChecked(True)

        self._shift_cmd_edit.setPlainText(btn.get("shift_command", ""))
        if btn.get("shift_command_type", "python") == "mel":
            self._shift_mel.setChecked(True)
        else:
            self._shift_python.setChecked(True)

        for w in widgets_to_block:
            w.blockSignals(False)

    def _load_multi_button_colors(self, buttons):
        color_keys = ["bg_color", "icon_tint", "label_bg_color", "label_text_color"]
        color_widgets = [
            self._btn_bg_color, self._btn_icon_tint,
            self._btn_label_bg_color, self._btn_label_text_color
        ]

        # Get non-separator buttons from selection
        selected_btns = []
        for idx in self._current_button_indices:
            if idx < len(buttons) and not buttons[idx].get("separator"):
                selected_btns.append(buttons[idx])

        if not selected_btns:
            for widget in color_widgets:
                widget.setColor(None)
            return

        # For each color property, check if all selected buttons have the same value
        for key, widget in zip(color_keys, color_widgets):
            first_val = selected_btns[0].get(key)
            all_same = all(btn.get(key) == first_val for btn in selected_btns)
            if all_same:
                widget.setColor(first_val)
            else:
                widget.setColor(None)

    def _clear_text_props(self):
        for w in [self._btn_name_edit, self._btn_icon_edit, self._btn_label_edit,
                  self._btn_tooltip_edit, self._cmd_edit, self._shift_cmd_edit]:
            w.blockSignals(True)
        self._btn_name_edit.clear()
        self._btn_icon_edit.clear()
        self._btn_label_edit.clear()
        self._btn_tooltip_edit.clear()
        self._cmd_edit.clear()
        self._shift_cmd_edit.clear()
        self._submenu_items = []
        self._refresh_submenu_list()
        for w in [self._btn_name_edit, self._btn_icon_edit, self._btn_label_edit,
                  self._btn_tooltip_edit, self._cmd_edit, self._shift_cmd_edit]:
            w.blockSignals(False)

    def _clear_button_props(self):
        for w in [self._btn_name_edit, self._btn_icon_edit, self._btn_label_edit,
                  self._btn_tooltip_edit, self._cmd_edit, self._shift_cmd_edit]:
            w.blockSignals(True)
        self._btn_name_edit.clear()
        self._btn_icon_edit.clear()
        self._btn_label_edit.clear()
        self._btn_tooltip_edit.clear()
        self._btn_bg_color.setColor(None)
        self._btn_icon_tint.setColor(None)
        self._btn_label_bg_color.setColor(None)
        self._btn_label_text_color.setColor(None)
        self._cmd_edit.clear()
        self._shift_cmd_edit.clear()
        self._submenu_items = []
        self._refresh_submenu_list()
        for w in [self._btn_name_edit, self._btn_icon_edit, self._btn_label_edit,
                  self._btn_tooltip_edit, self._cmd_edit, self._shift_cmd_edit]:
            w.blockSignals(False)

    def _on_button_prop_changed(self):
        if len(self._current_button_indices) != 1 or not self._current_shelf:
            return

        idx = self._current_button_indices[0]
        shelf_data = core.get_shelf_data(self._current_shelf)
        if shelf_data:
            buttons = shelf_data.get("buttons", [])
            if idx < len(buttons) and buttons[idx].get("separator"):
                return

        import copy
        updates = {
            "name": self._btn_name_edit.text(),
            "icon": self._btn_icon_edit.text() or "commandButton.png",
            "label": self._btn_label_edit.text(),
            "annotation": self._btn_tooltip_edit.text(),
            "command": self._cmd_edit.toPlainText(),
            "command_type": "mel" if self._cmd_mel.isChecked() else "python",
            "shift_command": self._shift_cmd_edit.toPlainText(),
            "shift_command_type": "mel" if self._shift_mel.isChecked() else "python",
            "submenu": copy.deepcopy(self._submenu_items),
        }

        core.update_button(self._current_shelf, idx, updates)

        # Update list item display
        item = self._button_list.item(idx)
        if item:
            display = updates["name"] or updates["label"] or updates["icon"]
            item.setText(display)
            icon_path = updates["icon"]
            if not ("/" in icon_path or "\\" in icon_path):
                item.setIcon(QIcon(":{}".format(icon_path)))
            else:
                item.setIcon(QIcon(icon_path))

    def _on_button_color_changed(self, color_value):
        if not self._current_shelf or not self._current_button_indices:
            return

        sender = self.sender()
        if sender == self._btn_bg_color:
            key = "bg_color"
        elif sender == self._btn_icon_tint:
            key = "icon_tint"
        elif sender == self._btn_label_bg_color:
            key = "label_bg_color"
        elif sender == self._btn_label_text_color:
            key = "label_text_color"
        else:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])

        for idx in self._current_button_indices:
            if idx < len(buttons) and not buttons[idx].get("separator"):
                core.update_button(self._current_shelf, idx, {key: color_value})

    def _browse_icon(self):
        try:
            from . import icon_chooser
            chooser = icon_chooser.IconChooserDialog(callback=self._on_icon_selected, parent=self)
            chooser.exec_()
        except Exception as e:
            cmds.warning("[neo_shelf] Icon chooser error: {}".format(e))

    def _on_icon_selected(self, icon_name):
        self._btn_icon_edit.setText(icon_name)

    def _add_button(self):
        if not self._current_shelf:
            return
        new_btn = core.make_default_button(command="print('new')")
        core.add_button_to_shelf(self._current_shelf, new_btn)
        self._refresh_button_list()
        self._button_list.setCurrentRow(self._button_list.count() - 1)

    def _add_separator(self):
        if not self._current_shelf:
            return
        core.add_button_to_shelf(self._current_shelf, core.make_separator())
        self._refresh_button_list()

    def _duplicate_button(self):
        if not self._current_shelf or not self._current_button_indices:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])
        import copy
        for idx in sorted(self._current_button_indices):
            if idx < len(buttons):
                core.add_button_to_shelf(self._current_shelf, copy.deepcopy(buttons[idx]))

        self._refresh_button_list()

    def _delete_button(self):
        if not self._current_shelf or not self._current_button_indices:
            return

        for idx in sorted(self._current_button_indices, reverse=True):
            core.remove_button(self._current_shelf, idx)

        self._current_button_indices = []
        self._refresh_button_list()

    def _transfer_buttons(self, target_shelf):
        if not self._current_shelf or not self._current_button_indices:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])
        import copy
        for idx in sorted(self._current_button_indices):
            if idx < len(buttons):
                core.add_button_to_shelf(target_shelf, copy.deepcopy(buttons[idx]))

        for idx in sorted(self._current_button_indices, reverse=True):
            core.remove_button(self._current_shelf, idx)

        self._current_button_indices = []
        self._refresh_button_list()

    def _copy_buttons_to(self, target_shelf):
        if not self._current_shelf or not self._current_button_indices:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])
        import copy
        for idx in sorted(self._current_button_indices):
            if idx < len(buttons):
                core.add_button_to_shelf(target_shelf, copy.deepcopy(buttons[idx]))

    def _on_buttons_reordered(self, parent, start, end, dest, row):
        if not self._current_shelf:
            return

        shelf_data = core.get_shelf_data(self._current_shelf)
        if not shelf_data:
            return

        buttons = shelf_data.get("buttons", [])
        if start < len(buttons):
            btn = buttons.pop(start)
            insert_pos = row if row < start else row - 1
            buttons.insert(insert_pos, btn)
            core.update_shelf_buttons(self._current_shelf, buttons)

    # Submenu operations
    def _refresh_submenu_list(self):
        self._submenu_list.clear()
        for item in self._submenu_items:
            if item.get("separator"):
                self._submenu_list.addItem("--- Separator ---")
            else:
                self._submenu_list.addItem(item.get("label", "Item"))

    def _on_submenu_selected(self, row):
        if row < 0 or row >= len(self._submenu_items):
            self._sub_cmd_edit.clear()
            self._sub_label_edit.clear()
            self._sub_cmd_edit.setEnabled(False)
            self._sub_label_edit.setEnabled(False)
            self._sub_python.setEnabled(False)
            self._sub_mel.setEnabled(False)
            return

        item = self._submenu_items[row]
        if item.get("separator"):
            self._sub_cmd_edit.setEnabled(False)
            self._sub_label_edit.setEnabled(False)
            self._sub_python.setEnabled(False)
            self._sub_mel.setEnabled(False)
            return

        self._sub_cmd_edit.setEnabled(True)
        self._sub_label_edit.setEnabled(True)
        self._sub_python.setEnabled(True)
        self._sub_mel.setEnabled(True)

        self._sub_cmd_edit.blockSignals(True)
        self._sub_label_edit.blockSignals(True)

        self._sub_cmd_edit.setPlainText(item.get("command", ""))
        self._sub_label_edit.setText(item.get("label", ""))
        if item.get("type", "python") == "mel":
            self._sub_mel.setChecked(True)
        else:
            self._sub_python.setChecked(True)

        self._sub_cmd_edit.blockSignals(False)
        self._sub_label_edit.blockSignals(False)

    def _on_submenu_changed(self):
        row = self._submenu_list.currentRow()
        if row < 0 or row >= len(self._submenu_items):
            return

        item = self._submenu_items[row]
        if item.get("separator"):
            return

        item["command"] = self._sub_cmd_edit.toPlainText()
        item["label"] = self._sub_label_edit.text()
        item["type"] = "mel" if self._sub_mel.isChecked() else "python"

        self._submenu_list.item(row).setText(item["label"] or "Item")
        self._on_button_prop_changed()

    def _add_submenu_item(self):
        self._submenu_items.append({"label": "New Item", "command": "", "type": "python"})
        self._refresh_submenu_list()
        self._submenu_list.setCurrentRow(len(self._submenu_items) - 1)
        self._on_button_prop_changed()

    def _remove_submenu_item(self):
        row = self._submenu_list.currentRow()
        if row >= 0 and row < len(self._submenu_items):
            self._submenu_items.pop(row)
            self._refresh_submenu_list()
            self._on_button_prop_changed()

    def _add_submenu_separator(self):
        self._submenu_items.append({"separator": True})
        self._refresh_submenu_list()
        self._on_button_prop_changed()

    def _on_submenu_reordered(self, parent, start, end, dest, row):
        if start < len(self._submenu_items):
            item = self._submenu_items.pop(start)
            insert_pos = row if row < start else row - 1
            self._submenu_items.insert(insert_pos, item)
            self._on_button_prop_changed()

    def _refresh_panels(self):
        widgets.refresh_all_panels()

    def _import_native_shelf(self):
        from . import importer
        imported = importer.import_shelf_files(self)
        if imported:
            self._refresh_shelf_list()

    def _open_trigger_settings(self):
        dialog = TriggerSettingsDialog(self)
        dialog.exec_()

    def _open_help(self):
        import webbrowser
        webbrowser.open("https://github.com/revoconner/Maya-Neo-Shelf/wiki/User-Guide")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if obj == self._shelf_list.viewport():
                item = self._shelf_list.itemAt(event.pos())
                if item is None:
                    self._options_stack.setCurrentIndex(0)
                    self._update_column_highlight(0)
            elif obj == self._button_list.viewport():
                item = self._button_list.itemAt(event.pos())
                if item is None:
                    self._button_list.clearSelection()
                    self._current_button_indices = []
                    self._clear_button_props()
                    self._update_button_controls()
                    self._options_stack.setCurrentIndex(1)
                    self._update_column_highlight(1)
        return super(ShelfManager, self).eventFilter(obj, event)


def show(select_shelf=None):
    global _manager_instance
    if _manager_instance:
        _manager_instance.close()
    _manager_instance = ShelfManager(select_shelf=select_shelf)
    _manager_instance.show()


def show_with_button(shelf_name, button_index):
    global _manager_instance
    if _manager_instance:
        _manager_instance.close()
    _manager_instance = ShelfManager(select_shelf=shelf_name, select_button=button_index)
    _manager_instance.show()


def notify_panel_closed(workspace_name):
    """Called by widgets.py when a panel is closed externally."""
    global _manager_instance
    if _manager_instance and _manager_instance.isVisible():
        _manager_instance._refresh_shelf_list()
        _manager_instance._update_panel_buttons()
