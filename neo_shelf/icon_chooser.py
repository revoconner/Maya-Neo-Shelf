# icon_chooser.py
import maya.cmds as cmds
import os
import platform
import re

__version__ = "1.4.0"

class IconChooser:
    WINDOW_NAME = "iconChooserWindow"
    
    def __init__(self):
        self.all_internal_icons = []
        self.cur_all_icons = []
        self.icon_path_map = {}
        self.cur_icon_path = ""
        self.icon_buttons = []
        
        delimiter = ';' if platform.system() == 'Windows' else ':'
        icon_paths = os.environ.get('XBMLANGPATH', '').split(delimiter)
        
        if platform.system() == 'Linux':
            icon_paths = [os.path.dirname(p) for p in icon_paths if p.endswith('%B')]
        
        self.path_with_icons = []
        for p in icon_paths:
            if os.path.isdir(p):
                files = os.listdir(p)
                if files:
                    self.path_with_icons.append(p)
        
        self.all_internal_icons = cmds.resourceManager(nameFilter="*.png") or []
        self.path_with_icons.insert(0, 'Internal Icons')
        self.path_with_icons.insert(0, 'All Paths')
        
        self._build_all_icons_map()
        self._build_ui()
    
    def _build_all_icons_map(self):
        self.icon_path_map = {}
        for icon_name in self.all_internal_icons:
            if icon_name not in self.icon_path_map:
                self.icon_path_map[icon_name] = 'Internal Icons'
        
        for path in self.path_with_icons[2:]:
            try:
                files = os.listdir(path)
                files = self._exclude_icons(files)
                for icon_name in files:
                    if icon_name not in self.icon_path_map:
                        self.icon_path_map[icon_name] = path
            except OSError:
                pass
    
    def _build_ui(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)
        
        self.window = cmds.window(
            self.WINDOW_NAME,
            title=f"Icon Chooser {__version__}",
            widthHeight=(600, 500),
            sizeable=True
        )
        
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(80, 200))
        cmds.text(label="Icon Path:")
        self.path_menu = cmds.optionMenu(changeCommand=self._on_path_changed)
        for p in self.path_with_icons:
            cmds.menuItem(label=p)
        cmds.setParent('..')
        
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(80, 200, 60))
        cmds.text(label="Filter:")
        self.filter_field = cmds.textField(placeholderText="Search icons...")
        cmds.button(label="Search", command=self._on_filter_changed)
        cmds.setParent('..')
        
        cmds.separator(height=5, style='in')
        
        self.count_label = cmds.text(label="Icons: 0", align='left')
        
        self.scroll_layout = cmds.scrollLayout(
            horizontalScrollBarThickness=0,
            verticalScrollBarThickness=16,
            childResizable=True,
            height=350
        )
        self.icon_grid = cmds.gridLayout(
            numberOfColumns=12,
            cellWidthHeight=(46, 46),
            allowEmptyCells=True
        )
        cmds.setParent('..')
        cmds.setParent('..')
        
        cmds.separator(height=5, style='in')
        
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(80, 200))
        cmds.text(label="Selected:")
        self.selected_field = cmds.textField(editable=True)
        cmds.setParent('..')
        
        self._update_icon_list()
        cmds.showWindow(self.window)
    
    def _exclude_icons(self, icons):
        exclude_ext = ('tdi', 'iff')
        result = []
        for i in icons:
            if '.' not in i:
                continue
            ext = i.rsplit('.', 1)[-1].lower()
            if ext not in exclude_ext:
                result.append(i)
        return result
    
    def _get_icon_path(self, icon_name):
        if self.cur_icon_path == 'All Paths':
            source_path = self.icon_path_map.get(icon_name, 'Internal Icons')
            if source_path == 'Internal Icons':
                return f":/{icon_name}"
            return os.path.join(source_path, icon_name)
        
        if self.cur_icon_path == 'Internal Icons':
            return f":/{icon_name}"
        return os.path.join(self.cur_icon_path, icon_name)
    
    def _on_icon_clicked(self, icon_name):
        if self.cur_icon_path == 'All Paths':
            source_path = self.icon_path_map.get(icon_name, 'Internal Icons')
            if source_path == 'Internal Icons':
                display = icon_name
            else:
                full_path = os.path.join(source_path, icon_name).replace('\\', '/')
                display = f"{icon_name} | {full_path}"
        elif self.cur_icon_path == 'Internal Icons':
            display = icon_name
        else:
            full_path = os.path.join(self.cur_icon_path, icon_name).replace('\\', '/')
            display = f"{icon_name} | {full_path}"
        cmds.textField(self.selected_field, edit=True, text=display)
    
    def _clear_grid(self):
        if cmds.gridLayout(self.icon_grid, exists=True):
            children = cmds.gridLayout(self.icon_grid, query=True, childArray=True) or []
            for child in children:
                cmds.deleteUI(child)
        self.icon_buttons = []
    
    def _populate_icons(self, filter_text=""):
        self._clear_grid()
        
        pattern = None
        if filter_text:
            try:
                pattern = re.compile(filter_text, re.IGNORECASE)
            except re.error:
                pattern = re.compile(re.escape(filter_text), re.IGNORECASE)
        
        count = 0
        for icon_name in self.cur_all_icons:
            if pattern and not pattern.search(icon_name):
                continue
            
            icon_path = self._get_icon_path(icon_name)
            
            btn = cmds.iconTextButton(
                parent=self.icon_grid,
                style='iconOnly',
                image=icon_path,
                width=44,
                height=44,
                annotation=icon_name,
                command=lambda n=icon_name: self._on_icon_clicked(n)
            )
            self.icon_buttons.append(btn)
            count += 1
        
        cmds.text(self.count_label, edit=True, label=f"Icons: {count}")
    
    def _update_icon_list(self):
        selected_idx = cmds.optionMenu(self.path_menu, query=True, select=True) - 1
        self.cur_icon_path = self.path_with_icons[selected_idx]
        
        if selected_idx == 0:
            self.cur_all_icons = sorted(self.icon_path_map.keys())
        elif selected_idx == 1:
            self.cur_all_icons = self.all_internal_icons[:]
        else:
            try:
                self.cur_all_icons = os.listdir(self.cur_icon_path)
            except OSError:
                self.cur_all_icons = []
            self.cur_all_icons = self._exclude_icons(self.cur_all_icons)
    
    def _on_path_changed(self, *args):
        self._update_icon_list()
        self._clear_grid()
        cmds.text(self.count_label, edit=True, label="Icons: 0")
    
    def _on_filter_changed(self, *args):
        filter_text = cmds.textField(self.filter_field, query=True, text=True)
        self._populate_icons(filter_text)


def main():
    return IconChooser()


# PySide dialog version for integration with button_editor
from functools import partial

try:
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
        QComboBox, QLabel, QScrollArea, QWidget, QGridLayout,
        QToolButton, QDialogButtonBox, QFileDialog
    )
    from PySide6.QtGui import QIcon
except ImportError:
    from PySide2.QtCore import Qt, QSize
    from PySide2.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
        QComboBox, QLabel, QScrollArea, QWidget, QGridLayout,
        QToolButton, QDialogButtonBox, QFileDialog
    )
    from PySide2.QtGui import QIcon

from . import core

ADD_FOLDER_ITEM = "Add Icon Folder..."


class IconChooserDialog(QDialog):
    """PySide dialog for icon selection with callback."""

    def __init__(self, callback=None, parent=None):
        super(IconChooserDialog, self).__init__(parent)
        self._callback = callback
        self._selected_icon = ""
        self._icon_buttons = []

        self._setup_icon_data()
        self._build_ui()

    def _setup_icon_data(self):
        self.all_internal_icons = cmds.resourceManager(nameFilter="*.png") or []
        self.icon_path_map = {}

        for icon_name in self.all_internal_icons:
            self.icon_path_map[icon_name] = "Internal Icons"

        delimiter = ";" if platform.system() == "Windows" else ":"
        icon_paths = os.environ.get("XBMLANGPATH", "").split(delimiter)

        if platform.system() == "Linux":
            icon_paths = [os.path.dirname(p) for p in icon_paths if p.endswith("%B")]

        self.path_with_icons = ["Internal Icons", "All Paths"]
        for p in icon_paths:
            if os.path.isdir(p):
                try:
                    files = os.listdir(p)
                    if files:
                        self.path_with_icons.append(p)
                        for f in files:
                            if "." in f and f.rsplit(".", 1)[-1].lower() not in ("tdi", "iff"):
                                if f not in self.icon_path_map:
                                    self.icon_path_map[f] = p
                except OSError:
                    pass

        # Load custom icon folders from config
        self.custom_folders = self._load_custom_folders()
        for folder in self.custom_folders:
            if os.path.isdir(folder) and folder not in self.path_with_icons:
                self.path_with_icons.append(folder)
                self._add_folder_to_map(folder)

    def _load_custom_folders(self):
        config = core.load_config()
        return config.get("settings", {}).get("icon_folders", [])

    def _save_custom_folder(self, folder):
        config = core.load_config()
        if "settings" not in config:
            config["settings"] = {}
        if "icon_folders" not in config["settings"]:
            config["settings"]["icon_folders"] = []
        if folder not in config["settings"]["icon_folders"]:
            config["settings"]["icon_folders"].append(folder)
            core.save_config()

    def _add_folder_to_map(self, folder):
        try:
            files = os.listdir(folder)
            for f in files:
                if "." in f and f.rsplit(".", 1)[-1].lower() not in ("tdi", "iff"):
                    if f not in self.icon_path_map:
                        self.icon_path_map[f] = folder
        except OSError:
            pass

    def _build_ui(self):
        self.setWindowTitle("Icon Chooser")
        self.setMinimumSize(650, 500)

        layout = QVBoxLayout(self)

        # Path selector
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Icon Path:"))
        self._path_combo = QComboBox()
        self._path_combo.addItems(self.path_with_icons)
        self._path_combo.addItem(ADD_FOLDER_ITEM)
        self._path_combo.setCurrentIndex(0)  # Internal Icons is default
        self._path_combo.currentIndexChanged.connect(self._on_path_changed)
        path_row.addWidget(self._path_combo, 1)
        layout.addLayout(path_row)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search icons...")
        self._filter_edit.returnPressed.connect(self._populate_icons)
        filter_row.addWidget(self._filter_edit, 1)
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._populate_icons)
        filter_row.addWidget(self._search_btn)
        layout.addLayout(filter_row)

        # Count label
        self._count_label = QLabel("Icons: 0")
        layout.addWidget(self._count_label)

        # Scroll area with grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(2)
        self._scroll.setWidget(self._grid_widget)

        layout.addWidget(self._scroll, 1)

        # Selected display
        selected_row = QHBoxLayout()
        selected_row.addWidget(QLabel("Selected:"))
        self._selected_edit = QLineEdit()
        self._selected_edit.setReadOnly(True)
        selected_row.addWidget(self._selected_edit, 1)
        layout.addLayout(selected_row)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._accept_selection)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_path_changed(self, index):
        current_text = self._path_combo.currentText()
        if current_text == ADD_FOLDER_ITEM:
            folder = QFileDialog.getExistingDirectory(self, "Select Icon Folder")
            if folder and os.path.isdir(folder):
                folder = folder.replace("\\", "/")
                if folder not in self.path_with_icons:
                    # Insert before the "Add Icon Folder..." item
                    insert_idx = self._path_combo.count() - 1
                    self._path_combo.insertItem(insert_idx, folder)
                    self.path_with_icons.append(folder)
                    self._add_folder_to_map(folder)
                    self._save_custom_folder(folder)
                    self._path_combo.setCurrentIndex(insert_idx)
                else:
                    # Already exists, select it
                    existing_idx = self.path_with_icons.index(folder)
                    self._path_combo.setCurrentIndex(existing_idx)
                return
            else:
                # Cancelled, revert to first item
                self._path_combo.setCurrentIndex(0)
                return

        self._clear_grid()
        self._count_label.setText("Icons: 0")

    def _clear_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._icon_buttons.clear()

    def _get_icons_for_path(self, path_name):
        if path_name == "All Paths":
            return sorted(self.icon_path_map.keys())
        elif path_name == "Internal Icons":
            return self.all_internal_icons[:]
        else:
            try:
                files = os.listdir(path_name)
                return [f for f in files if "." in f and f.rsplit(".", 1)[-1].lower() not in ("tdi", "iff")]
            except OSError:
                return []

    def _get_icon_display_path(self, icon_name, source_path):
        if source_path == "Internal Icons":
            return ":{}".format(icon_name)
        return os.path.join(source_path, icon_name).replace("\\", "/")

    def _populate_icons(self):
        self._clear_grid()

        path_name = self._path_combo.currentText()
        if path_name == ADD_FOLDER_ITEM:
            return

        icons = self._get_icons_for_path(path_name)

        filter_text = self._filter_edit.text().strip().lower()
        if filter_text:
            icons = [i for i in icons if filter_text in i.lower()]

        cols = 12
        count = 0

        for i, icon_name in enumerate(icons):
            if path_name == "All Paths":
                source = self.icon_path_map.get(icon_name, "Internal Icons")
            elif path_name == "Internal Icons":
                source = "Internal Icons"
            else:
                source = path_name

            icon_path = self._get_icon_display_path(icon_name, source)

            btn = QToolButton()
            btn.setAutoRaise(True)
            btn.setToolTip(icon_name)
            btn.setFixedSize(QSize(44, 44))
            btn.setIconSize(QSize(40, 40))

            if source == "Internal Icons":
                btn.setIcon(QIcon(":{}".format(icon_name)))
            else:
                btn.setIcon(QIcon(icon_path))

            btn.clicked.connect(partial(self._on_icon_clicked, icon_name, icon_path, source))

            row = i // cols
            col = i % cols
            self._grid_layout.addWidget(btn, row, col)
            self._icon_buttons.append(btn)
            count += 1

        self._count_label.setText("Icons: {}".format(count))

    def _on_icon_clicked(self, icon_name, icon_path, source):
        # For internal icons, store just the name. For external, store full path.
        if source == "Internal Icons":
            self._selected_icon = icon_name
            self._selected_edit.setText(icon_name)
        else:
            self._selected_icon = icon_path
            self._selected_edit.setText(icon_path)

    def _accept_selection(self):
        if self._callback and self._selected_icon:
            self._callback(self._selected_icon)
        self.accept()