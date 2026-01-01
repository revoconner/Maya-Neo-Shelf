import os
import re

try:
    from PySide6.QtWidgets import QFileDialog, QMessageBox
except ImportError:
    from PySide2.QtWidgets import QFileDialog, QMessageBox

import maya.cmds as cmds

from . import core


def get_maya_shelves_dir():
    """Get the Maya user prefs shelves directory."""
    prefs_dir = cmds.internalVar(userPrefDir=True)
    return os.path.join(prefs_dir, "shelves").replace("\\", "/")


def parse_shelf_mel(file_path):
    """Parse a Maya shelf .mel file and return shelf name and button data."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Check for valid shelf file structure
    match = re.match(r'\s*global\s+proc\s+(\w+)\s*\(\s*\)', content)
    if not match:
        raise ValueError("Invalid shelf file: must start with 'global proc name ()'")

    shelf_name = match.group(1)
    # Remove shelf_ prefix if present
    if shelf_name.startswith("shelf_"):
        shelf_name = shelf_name[6:]

    buttons = []

    # Find all shelfButton and separator blocks
    # The ; that ends a block is on its own line (preceded by whitespace only)
    shelf_button_pattern = re.compile(
        r'shelfButton\s+(.*?)\n[ \t]*;',
        re.DOTALL
    )
    separator_pattern = re.compile(
        r'separator\s+(.*?)\n[ \t]*;',
        re.DOTALL
    )

    # Find positions of all shelfButton and separator commands
    items = []
    for m in shelf_button_pattern.finditer(content):
        items.append(("button", m.start(), m.group(1)))
    for m in separator_pattern.finditer(content):
        items.append(("separator", m.start(), m.group(1)))

    # Sort by position in file
    items.sort(key=lambda x: x[1])

    for item_type, _, block in items:
        if item_type == "separator":
            buttons.append(core.make_separator())
        else:
            btn = parse_shelf_button(block)
            if btn:
                buttons.append(btn)

    return shelf_name, buttons


def parse_shelf_button(block):
    """Parse a shelfButton block and return button data dict."""
    btn = core.make_default_button()

    # Extract simple string flags
    def get_string_flag(flag_name):
        # Match -flag "value" or -flag "value with spaces"
        # Handle escaped quotes inside the string
        pattern = r'-{}\s+"((?:[^"\\]|\\.)*)"\s*'.format(flag_name)
        m = re.search(pattern, block)
        if m:
            # Unescape MEL string escape sequences
            s = m.group(1)
            s = s.replace('\\\\', '\x00')  # Temp placeholder for literal backslash
            s = s.replace('\\n', '\n')
            s = s.replace('\\t', '\t')
            s = s.replace('\\r', '\r')
            s = s.replace('\\"', '"')
            s = s.replace('\x00', '\\')  # Restore literal backslashes
            return s
        return None

    # Extract numeric flags (space-separated values)
    def get_numeric_flags(flag_name, count):
        pattern = r'-{}\s+'.format(flag_name)
        m = re.search(pattern, block)
        if not m:
            return None
        start = m.end()
        # Extract numbers after the flag
        remainder = block[start:]
        nums = []
        for part in remainder.split():
            if part.startswith('-') and not part[1:].replace('.', '').replace('-', '').isdigit():
                break
            try:
                nums.append(float(part))
                if len(nums) >= count:
                    break
            except ValueError:
                break
        return nums if len(nums) == count else None

    # Parse main fields
    annotation = get_string_flag("annotation")
    if annotation:
        btn["annotation"] = annotation

    label = get_string_flag("label")
    if label:
        btn["name"] = label

    # Icon overlay label text
    overlay_label = get_string_flag("imageOverlayLabel")
    if overlay_label:
        btn["label"] = overlay_label

    # Icon - prefer image1, fallback to image
    icon = get_string_flag("image1") or get_string_flag("image")
    if icon:
        btn["icon"] = icon.replace("\\", "/")

    # Command
    command = get_string_flag("command")
    if command:
        btn["command"] = command

    # Source type (mel or python)
    source_type = get_string_flag("sourceType")
    if source_type:
        btn["command_type"] = source_type.lower()

    # Double click command (secondary/shift command)
    double_click = get_string_flag("doubleClickCommand")
    if double_click:
        btn["shift_command"] = double_click
        btn["shift_command_type"] = btn["command_type"]

    # Overlay label colors
    label_color = get_numeric_flags("overlayLabelColor", 3)
    if label_color:
        btn["label_text_color"] = label_color

    label_bg = get_numeric_flags("overlayLabelBackColor", 4)
    if label_bg:
        btn["label_bg_color"] = label_bg

    # Parse submenu items: -mi "Label" ( "command" )
    def unescape_mel(s):
        s = s.replace('\\\\', '\x00')
        s = s.replace('\\n', '\n')
        s = s.replace('\\t', '\t')
        s = s.replace('\\r', '\r')
        s = s.replace('\\"', '"')
        s = s.replace('\x00', '\\')
        return s

    submenu = []
    mi_pattern = re.compile(r'-mi\s+"([^"]+)"\s*\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
    for m in mi_pattern.finditer(block):
        label_text = m.group(1)
        cmd = unescape_mel(m.group(2))
        submenu.append({
            "label": label_text,
            "command": cmd,
            "type": btn["command_type"]
        })

    if submenu:
        btn["submenu"] = submenu

    return btn


def import_shelf_files(parent=None):
    """Open file dialog and import selected .mel shelf files."""
    default_dir = get_maya_shelves_dir()
    file_paths, _ = QFileDialog.getOpenFileNames(
        parent,
        "Import Maya Shelf Files",
        default_dir,
        "MEL Files (*.mel);;All Files (*.*)"
    )

    if not file_paths:
        return []

    imported = []
    errors = []

    for path in file_paths:
        try:
            shelf_name, buttons = parse_shelf_mel(path)

            # Check if shelf already exists
            existing = core.get_all_shelf_names()
            original_name = shelf_name
            counter = 1
            while shelf_name in existing:
                shelf_name = "{}_{}".format(original_name, counter)
                counter += 1

            # Create shelf and add buttons
            core.create_shelf(shelf_name)
            for btn in buttons:
                core.add_button_to_shelf(shelf_name, btn)

            imported.append(shelf_name)

        except Exception as e:
            errors.append("{}: {}".format(os.path.basename(path), str(e)))

    # Show result
    if imported:
        msg = "Imported {} shelf(s):\n{}".format(len(imported), "\n".join(imported))
        if errors:
            msg += "\n\nErrors:\n{}".format("\n".join(errors))
        QMessageBox.information(parent, "Import Complete", msg)
    elif errors:
        QMessageBox.warning(parent, "Import Failed", "Errors:\n{}".format("\n".join(errors)))

    return imported


def show(parent=None):
    """Show import dialog - called from manager."""
    return import_shelf_files(parent)
