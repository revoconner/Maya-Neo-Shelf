try:
    from PySide6.QtCore import Qt, QSize, QRect, QPoint, QTimer, Signal, QPointF, QMimeData
    from PySide6.QtWidgets import (
        QWidget, QLayout, QToolButton, QVBoxLayout, QHBoxLayout,
        QScrollArea, QMenu, QSizePolicy, QLabel, QApplication
    )
    from PySide6.QtGui import QIcon, QColor, QPainter, QBrush, QPen, QPixmap, QDragEnterEvent, QDropEvent, QDrag
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2.QtCore import Qt, QSize, QRect, QPoint, QTimer, Signal, QPointF, QMimeData
    from PySide2.QtWidgets import (
        QWidget, QLayout, QToolButton, QVBoxLayout, QHBoxLayout,
        QScrollArea, QMenu, QSizePolicy, QLabel, QApplication
    )
    from PySide2.QtGui import QIcon, QColor, QPainter, QBrush, QPen, QPixmap, QDragEnterEvent, QDropEvent, QDrag
    from shiboken2 import wrapInstance

import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from . import core
import re

PANEL_PREFIX = "neoShelf_"
REORDER_MIME_TYPE = "application/x-neo-shelf-index"
_active_panels = {}
_panel_close_jobs = {}


def _on_panel_closed(workspace_name):
    """Called when a panel is closed via closeCommand callback."""
    if workspace_name in _active_panels:
        del _active_panels[workspace_name]
    core.unregister_panel(workspace_name)
    # Notify manager if open
    try:
        from . import manager
        manager.notify_panel_closed(workspace_name)
    except Exception:
        pass


def _register_panel_close_callback(workspace_name):
    """Register closeCommand callback and set flags on workspace control."""
    cmd = "from neo_shelf import widgets; widgets._on_panel_closed('{}')".format(workspace_name)
    try:
        cmds.workspaceControl(workspace_name, edit=True, closeCommand=cmd)
        cmds.workspaceControl(workspace_name, edit=True, actLikeMayaUIElement=True)
    except Exception as e:
        print("[neo_shelf] Failed to configure workspace control: {}".format(e))


def _detect_script_type(code):
    """Detect if code is MEL or Python based on syntax patterns."""
    code = code.strip()
    if not code:
        return "python"

    # Python indicators
    python_patterns = [
        r'^import\s+',
        r'^from\s+\w+\s+import',
        r'^def\s+\w+\s*\(',
        r'^class\s+\w+',
        r'^\s*print\s*\(',
        r'cmds\.',
        r'pymel\.',
        r'maya\.cmds',
        r'__\w+__',
        r'\.format\(',
        r'f".*\{',
        r"f'.*\{",
    ]

    # MEL indicators
    mel_patterns = [
        r'^global\s+proc\s+',
        r'^proc\s+',
        r'^\s*\$\w+\s*=',
        r';\s*$',
        r'`[^`]+`',
        r'-\w+\s+\d',
        r'-\w+\s+"',
        r'-\w+\s+\$',
    ]

    for pattern in python_patterns:
        if re.search(pattern, code, re.MULTILINE):
            return "python"

    for pattern in mel_patterns:
        if re.search(pattern, code, re.MULTILINE):
            return "mel"

    # Default to python if undetermined
    return "python"


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QWidget)


class FlowLayout(QLayout):
    """Responsive layout that wraps items based on available width."""

    def __init__(self, parent=None):
        super(FlowLayout, self).__init__(parent)
        self._items = []
        self._spacing = 2

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def spacing(self):
        return self._spacing

    def setSpacing(self, spacing):
        self._spacing = spacing

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, move=False):
        m = self.contentsMargins()
        effective_rect = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        row_height = 0

        for item in self._items:
            widget = item.widget()
            if widget and hasattr(widget, "_break_line") and widget._break_line:
                if row_height > 0:
                    x = effective_rect.x()
                    y = y + row_height + self._spacing
                    row_height = 0
                if move:
                    item.setGeometry(QRect(QPoint(x, y), QSize(0, 0)))
                continue

            item_size = item.sizeHint()
            next_x = x + item_size.width() + self._spacing

            if next_x - self._spacing > effective_rect.right() and row_height > 0:
                x = effective_rect.x()
                y = y + row_height + self._spacing
                next_x = x + item_size.width() + self._spacing
                row_height = 0

            if move:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            row_height = max(row_height, item_size.height())

        return y + row_height - rect.y() + m.bottom()


class SubmenuIndicator(QWidget):
    """Small triangle indicator for buttons with submenus."""

    def __init__(self, parent=None):
        super(SubmenuIndicator, self).__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(8, 8)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(255, 255, 255, 191)  # 75% opacity
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        # Triangle pointing to bottom-right corner
        points = [
            QPoint(self.width(), 0),
            QPoint(self.width(), self.height()),
            QPoint(0, self.height())
        ]
        painter.drawPolygon(points)


class ShelfButton(QToolButton):
    """Button widget with configurable trigger support."""

    HOLD_THRESHOLD = 300
    DOUBLE_CLICK_DELAY = 200

    def __init__(self, button_data, index, icon_size=55, shelf_name="", parent=None):
        super(ShelfButton, self).__init__(parent)
        self._data = button_data
        self._index = index
        self._icon_size = icon_size
        self._shelf_name = shelf_name

        # Hold timer for detecting held clicks
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_timeout)
        self._was_held = False

        # Single-click delay timer (for double-click detection)
        self._single_click_timer = QTimer(self)
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.timeout.connect(self._on_single_click_timeout)
        self._pending_action = None
        self._was_double_click = False
        self._shift_held = False

        self._label_widget = None
        self._submenu_indicator = None
        self._drag_start_pos = None

        self.setAutoRaise(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)  # Handle RMB ourselves

        self._update_appearance()

    def _update_appearance(self):
        icon_size = max(self._icon_size, 35)
        label = self._data.get("label", "")

        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        btn_width = icon_size + 4
        btn_height = icon_size + 4

        self.setFixedSize(QSize(btn_width, btn_height))
        self.setIconSize(QSize(icon_size, icon_size))

        icon_path = self._data.get("icon", "commandButton.png")
        if icon_path.startswith(":/") or icon_path.startswith(":"):
            full_path = icon_path
        elif "/" in icon_path or "\\" in icon_path:
            full_path = icon_path
        else:
            full_path = ":{}".format(icon_path)

        icon_tint = self._data.get("icon_tint")

        # SVG files need QIcon directly, raster images use QPixmap for scaling
        if icon_path.lower().endswith(".svg"):
            icon = QIcon(full_path)
            if icon_tint:
                # Render SVG to pixmap first, then apply tint
                pixmap = icon.pixmap(icon_size, icon_size)
                if not pixmap.isNull():
                    pixmap = self._apply_tint(pixmap, icon_tint)
                    self.setIcon(QIcon(pixmap))
                else:
                    self.setIcon(icon)
            else:
                self.setIcon(icon)
        else:
            pixmap = QPixmap(full_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if icon_tint:
                    scaled = self._apply_tint(scaled, icon_tint)
                self.setIcon(QIcon(scaled))
            else:
                self.setIcon(QIcon(full_path))

        tooltip = self._data.get("annotation", "") or self._data.get("label", "")
        self.setToolTip(tooltip)

        style_parts = ["border: none;", "border-radius: 5px;"]
        bg = self._data.get("bg_color")
        if bg:
            r, g, b = [int(c * 255) for c in bg[:3]]
            style_parts.append("background-color: rgb({},{},{});".format(r, g, b))

        label_text = self._data.get("label_text_color")
        if label_text:
            r, g, b = [int(c * 255) for c in label_text[:3]]
            style_parts.append("color: rgb({},{},{});".format(r, g, b))

        self.setStyleSheet(
            "QToolButton {{ {} }} QToolTip {{ background-color: #383838; color: white; border: 1px solid #555; }}".format(
                " ".join(style_parts)))

        if label:
            if not self._label_widget:
                self._label_widget = QLabel(self)
                self._label_widget.setAlignment(Qt.AlignCenter)
                self._label_widget.setAttribute(Qt.WA_TransparentForMouseEvents)

            self._label_widget.setText(label)

            label_bg = self._data.get("label_bg_color")
            if label_bg:
                r, g, b = [int(c * 255) for c in label_bg[:3]]
                a = int(label_bg[3] * 255) if len(label_bg) > 3 else 128
            else:
                r, g, b, a = 0, 0, 0, 128

            text_color = self._data.get("label_text_color")
            if text_color:
                tr, tg, tb = [int(c * 255) for c in text_color[:3]]
            else:
                tr, tg, tb = 255, 255, 255

            self._label_widget.setStyleSheet(
                "background-color: rgba({},{},{},{}); color: rgb({},{},{}); font-weight: bold; padding: 3px 0px;".format(r, g, b, a, tr, tg, tb)
            )

            label_height = 25
            self._label_widget.setGeometry(0, btn_height - label_height, btn_width, label_height)
            self._label_widget.show()
        else:
            if self._label_widget:
                self._label_widget.hide()

        # Submenu indicator
        submenu = self._data.get("submenu", [])
        if submenu:
            if not self._submenu_indicator:
                self._submenu_indicator = SubmenuIndicator(self)
            self._submenu_indicator.move(btn_width - 10, btn_height - 10)
            self._submenu_indicator.show()
            self._submenu_indicator.raise_()
        else:
            if self._submenu_indicator:
                self._submenu_indicator.hide()

    def _get_triggers(self):
        return core.get_trigger_settings()

    def _uses_double_click(self):
        triggers = self._get_triggers()
        return "lmb_double_click" in triggers.values()

    def _trigger_action(self, action_name):
        if action_name == "main_command":
            self._execute_main_command()
        elif action_name == "secondary_command":
            self._execute_shift_command()
        elif action_name == "open_manager":
            self._open_manager()
        elif action_name == "show_submenu":
            self._show_submenu()

    def _get_action_for_trigger(self, trigger_type):
        triggers = self._get_triggers()
        for action, trigger in triggers.items():
            if trigger == trigger_type:
                return action
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._was_held = False
            self._was_double_click = False
            self._shift_held = bool(event.modifiers() & Qt.ShiftModifier)

            # Start hold timer for lmb_hold trigger
            action = self._get_action_for_trigger("lmb_hold")
            if action:
                self._hold_timer.start(self.HOLD_THRESHOLD)

        elif event.button() == Qt.MiddleButton:
            self._drag_start_pos = event.pos()

        elif event.button() == Qt.RightButton:
            action = self._get_action_for_trigger("rmb_click")
            if action:
                self._trigger_action(action)

        super(ShelfButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MiddleButton and self._drag_start_pos:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                self._start_drag()
        super(ShelfButton, self).mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(REORDER_MIME_TYPE, str(self._index).encode())
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(QPoint(self.width() // 2, self.height() // 2))
        drag.exec_(Qt.MoveAction)
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        self._hold_timer.stop()

        if event.button() == Qt.LeftButton and not self._was_held and not self._was_double_click:
            # Determine which trigger type this is
            if self._shift_held:
                trigger_type = "shift_lmb_click"
            else:
                trigger_type = "lmb_click"

            action = self._get_action_for_trigger(trigger_type)
            if action:
                # If double-click is configured, delay single-click action
                if self._uses_double_click():
                    self._pending_action = action
                    self._single_click_timer.start(self.DOUBLE_CLICK_DELAY)
                else:
                    self._trigger_action(action)

        super(ShelfButton, self).mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._was_double_click = True
            self._single_click_timer.stop()
            self._pending_action = None

            action = self._get_action_for_trigger("lmb_double_click")
            if action:
                self._trigger_action(action)

        super(ShelfButton, self).mouseDoubleClickEvent(event)

    def _on_single_click_timeout(self):
        if self._pending_action:
            self._trigger_action(self._pending_action)
            self._pending_action = None

    def _on_hold_timeout(self):
        self._was_held = True
        action = self._get_action_for_trigger("lmb_hold")
        if action:
            self._trigger_action(action)

    def _execute_main_command(self):
        cmd = self._data.get("command", "")
        cmd_type = self._data.get("command_type", "mel")
        if cmd:
            self._execute(cmd, cmd_type)

    def _execute_shift_command(self):
        cmd = self._data.get("shift_command", "")
        cmd_type = self._data.get("shift_command_type", "python")
        if cmd:
            self._execute(cmd, cmd_type)
        else:
            self._execute_main_command()

    def _execute(self, cmd, cmd_type):
        try:
            if cmd_type == "mel":
                mel.eval(cmd)
            else:
                exec(cmd, globals())
        except Exception as e:
            cmds.warning("[neo_shelf] Command error: {}".format(e))

    def _show_submenu(self):
        submenu = self._data.get("submenu", [])
        if not submenu:
            return

        menu = QMenu(self)
        for item in submenu:
            if item.get("separator"):
                menu.addSeparator()
            else:
                label = item.get("label", "Item")
                action = menu.addAction(label)
                cmd = item.get("command", "")
                cmd_type = item.get("type", "python")
                action.triggered.connect(lambda *args, c=cmd, t=cmd_type: self._execute(c, t))

        menu.exec_(self.mapToGlobal(QPoint(0, self.height())))

    def _open_manager(self):
        try:
            from . import manager
            manager.show_with_button(self._shelf_name, self._index)
        except Exception as e:
            cmds.warning("[neo_shelf] Manager error: {}".format(e))

    def _apply_tint(self, pixmap, tint_color):
        """Apply a color tint to a pixmap using the original as a mask."""
        if not tint_color or len(tint_color) < 3:
            return pixmap

        r, g, b = [int(c * 255) for c in tint_color[:3]]
        tint = QColor(r, g, b)

        # Create a copy to paint on
        result = QPixmap(pixmap.size())
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Draw original pixmap
        painter.drawPixmap(0, 0, pixmap)

        # Apply tint using SourceIn composition (uses original alpha as mask)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(result.rect(), tint)

        painter.end()
        return result

    def update_data(self, data, index, shelf_name=""):
        self._data = data
        self._index = index
        if shelf_name:
            self._shelf_name = shelf_name
        self._update_appearance()


class ShelfSeparator(QWidget):
    """Separator widget for shelf layouts."""

    def __init__(self, index, orientation="vertical", shelf_name="", parent=None):
        super(ShelfSeparator, self).__init__(parent)
        self._index = index
        self._orientation = orientation
        self._shelf_name = shelf_name
        self._drag_start_pos = None

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        if orientation == "vertical":
            self.setFixedWidth(12)
            self.setMinimumHeight(20)
        elif orientation == "horizontal":
            self.setFixedHeight(12)
            self.setMinimumWidth(20)
        else:
            self.setFixedSize(0, 0)

    def paintEvent(self, event):
        if self._orientation == "invisible":
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor(80, 80, 80))
        pen.setWidth(2)
        painter.setPen(pen)

        if self._orientation == "vertical":
            x = self.width() // 2
            painter.drawLine(x, 4, x, self.height() - 4)
        elif self._orientation == "horizontal":
            y = self.height() // 2
            painter.drawLine(4, y, self.width() - 4, y)

    def _show_context_menu(self, pos):
        try:
            from . import manager
            manager.show_with_button(self._shelf_name, self._index)
        except Exception as e:
            cmds.warning("[neo_shelf] Manager error: {}".format(e))

    def update_index(self, index, shelf_name=""):
        self._index = index
        if shelf_name:
            self._shelf_name = shelf_name

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._drag_start_pos = event.pos()
        super(ShelfSeparator, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MiddleButton and self._drag_start_pos:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                self._start_drag()
        super(ShelfSeparator, self).mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(REORDER_MIME_TYPE, str(self._index).encode())
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(QPoint(self.width() // 2, self.height() // 2))
        drag.exec_(Qt.MoveAction)
        self._drag_start_pos = None


class FlowBreakWidget(QWidget):
    """Invisible widget that forces a line break in FlowLayout."""

    def __init__(self, index, shelf_name="", parent=None):
        super(FlowBreakWidget, self).__init__(parent)
        self._index = index
        self._shelf_name = shelf_name
        self._break_line = True
        self._drag_start_pos = None
        self.setFixedSize(0, 0)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        try:
            from . import manager
            manager.show_with_button(self._shelf_name, self._index)
        except Exception as e:
            cmds.warning("[neo_shelf] Manager error: {}".format(e))

    def update_index(self, index, shelf_name=""):
        self._index = index
        if shelf_name:
            self._shelf_name = shelf_name

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._drag_start_pos = event.pos()
        super(FlowBreakWidget, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MiddleButton and self._drag_start_pos:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                self._start_drag()
        super(FlowBreakWidget, self).mouseMoveEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(REORDER_MIME_TYPE, str(self._index).encode())
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)
        self._drag_start_pos = None


class ShelfPanel(MayaQWidgetDockableMixin, QWidget):
    """Dockable shelf panel widget."""

    def __init__(self, shelf_name, parent=None):
        super(ShelfPanel, self).__init__(parent=parent)
        self._shelf_name = shelf_name
        self._buttons = []
        base_name = PANEL_PREFIX + shelf_name.replace(" ", "_")
        self._workspace_name = base_name + "WorkspaceControl"

        self.setObjectName(base_name)
        self.setWindowTitle("Shelf: {}".format(shelf_name))
        self.setMinimumHeight(30)
        self.setMinimumWidth(30)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_shelf_menu)

        self._build_ui()
        self.refresh()

        core.register_panel(self._workspace_name, shelf_name)
        _active_panels[self._workspace_name] = self

    def _build_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        self._content = QWidget()
        self._content.setContextMenuPolicy(Qt.CustomContextMenu)
        self._content.customContextMenuRequested.connect(self._show_shelf_menu)
        self._scroll.setWidget(self._content)

        self.setAcceptDrops(True)

        self._button_layout = None
        self._main_layout.addWidget(self._scroll)

    def _setup_layout(self, layout_mode, alignment="left"):
        if self._button_layout:
            while self._button_layout.count():
                item = self._button_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

        old_layout = self._content.layout()
        if old_layout:
            QWidget().setLayout(old_layout)

        # Map alignment string to Qt alignment
        h_align_map = {
            "left": Qt.AlignLeft,
            "center": Qt.AlignHCenter,
            "right": Qt.AlignRight
        }
        h_align = h_align_map.get(alignment, Qt.AlignLeft)

        if layout_mode == "horizontal":
            self._button_layout = QHBoxLayout(self._content)
            self._button_layout.setAlignment(h_align | Qt.AlignVCenter)
        elif layout_mode == "vertical":
            self._button_layout = QVBoxLayout(self._content)
            self._button_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        else:
            self._button_layout = FlowLayout(self._content)
            # FlowLayout respects alignment via content margins and alignment
            if hasattr(self._button_layout, 'setAlignment'):
                self._button_layout.setAlignment(h_align | Qt.AlignTop)

        self._button_layout.setContentsMargins(2, 2, 2, 2)
        self._button_layout.setSpacing(10)

    def refresh(self):
        self._buttons.clear()

        shelf_data = core.get_shelf_data(self._shelf_name)
        if not shelf_data:
            self._setup_layout("flow")
            return

        layout_mode = shelf_data.get("layout", "flow")
        alignment = shelf_data.get("alignment", "left")
        self._setup_layout(layout_mode, alignment)

        icon_size = shelf_data.get("icon_size", 55)

        bg = shelf_data.get("bg_color")
        if bg:
            r, g, b = [int(c * 255) for c in bg[:3]]
            self._content.setStyleSheet("background-color: rgb({},{},{});".format(r, g, b))
        else:
            self._content.setStyleSheet("")

        buttons = shelf_data.get("buttons", [])
        for i, btn_data in enumerate(buttons):
            if btn_data.get("separator"):
                if layout_mode == "horizontal":
                    sep = ShelfSeparator(i, "vertical", self._shelf_name, self._content)
                elif layout_mode == "vertical":
                    sep = ShelfSeparator(i, "horizontal", self._shelf_name, self._content)
                else:
                    sep = FlowBreakWidget(i, self._shelf_name, self._content)
                self._button_layout.addWidget(sep)
                self._buttons.append(sep)
            else:
                btn = ShelfButton(btn_data, i, icon_size, self._shelf_name, self._content)
                self._button_layout.addWidget(btn)
                self._buttons.append(btn)

        self._content.updateGeometry()
        self._apply_highlight(self._shelf_name == core.get_active_shelf())

        # Force repaint for docked panels (Maya workspaceControl bug workaround)
        self._content.update()
        self._scroll.update()
        self.update()
        self.repaint()

    def _on_edit_button(self, index):
        try:
            from . import manager
            manager.show_with_button(self._shelf_name, index)
        except Exception as e:
            cmds.warning("[neo_shelf] Manager error: {}".format(e))

    def _on_delete_button(self, index):
        result = cmds.confirmDialog(
            title="Delete Item",
            message="Delete this item?",
            button=["Yes", "No"],
            defaultButton="No",
            cancelButton="No",
            dismissString="No"
        )
        if result == "Yes":
            core.remove_button(self._shelf_name, index)
            self.refresh()

    def _on_move_button(self, from_idx, to_idx):
        core.move_button(self._shelf_name, from_idx, to_idx)
        self.refresh()

    def _show_shelf_menu(self, pos):
        menu = QMenu(self)

        add_btn = menu.addAction("Add New Button")
        add_btn.triggered.connect(self._add_new_button)

        add_sep = menu.addAction("Add Separator")
        add_sep.triggered.connect(self._add_separator)

        menu.addSeparator()

        settings_action = menu.addAction("Shelf Settings...")
        settings_action.triggered.connect(self._open_shelf_settings)

        menu.addSeparator()

        manager_action = menu.addAction("Open Manager")
        manager_action.triggered.connect(self._open_manager)

        sender = self.sender()
        if sender:
            menu.exec_(sender.mapToGlobal(pos))
        else:
            menu.exec_(self.mapToGlobal(pos))

    def _add_new_button(self):
        new_btn = core.make_default_button(command="print('new button')")
        core.add_button_to_shelf(self._shelf_name, new_btn)
        self.refresh()

    def _add_separator(self):
        sep = core.make_separator()
        core.add_button_to_shelf(self._shelf_name, sep)
        self.refresh()

    def _open_shelf_settings(self):
        try:
            from . import manager
            manager.show(select_shelf=self._shelf_name)
        except Exception as e:
            cmds.warning("[neo_shelf] Manager error: {}".format(e))

    def _open_manager(self):
        try:
            from . import manager
            manager.show()
        except ImportError:
            cmds.warning("[neo_shelf] Manager not yet implemented")

    def mousePressEvent(self, event):
        core.set_active_shelf(self._shelf_name)
        self._update_active_highlight()
        super(ShelfPanel, self).mousePressEvent(event)

    def _update_active_highlight(self):
        for ws, panel in _active_panels.items():
            panel._apply_highlight(panel._shelf_name == core.get_active_shelf())

    def _apply_highlight(self, is_active):
        shelf_data = core.get_shelf_data(self._shelf_name) or {}
        bg = shelf_data.get("bg_color", [0.22, 0.22, 0.22])
        bg_r, bg_g, bg_b = [int(c * 255) for c in bg[:3]]
        hide_highlight = shelf_data.get("hide_highlight", False)

        if is_active and not hide_highlight:
            highlight = shelf_data.get("active_highlight_color", [0.3, 0.5, 0.7])
            h_r, h_g, h_b = [int(c * 255) for c in highlight[:3]]
            self._scroll.setStyleSheet(
                "QScrollArea {{ border: 3px solid rgb({},{},{}); background-color: rgb({},{},{}); }}".format(
                    h_r, h_g, h_b, bg_r, bg_g, bg_b))
        else:
            self._scroll.setStyleSheet(
                "QScrollArea {{ border: 1px solid #444; background-color: rgb({},{},{}); }}".format(
                    bg_r, bg_g, bg_b))

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(REORDER_MIME_TYPE) or mime.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(REORDER_MIME_TYPE) or mime.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(REORDER_MIME_TYPE):
            source_idx = int(mime.data(REORDER_MIME_TYPE).data().decode())
            target_idx = self._get_drop_index(event.pos())
            if target_idx != source_idx and target_idx != source_idx + 1:
                if target_idx > source_idx:
                    target_idx -= 1
                core.move_button(self._shelf_name, source_idx, target_idx)
                self.refresh()
            event.acceptProposedAction()
        elif mime.hasText():
            code = mime.text().strip()
            if code:
                self._add_button_from_drop(code)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def _get_drop_index(self, pos):
        content_pos = self._content.mapFrom(self, pos)
        for i, btn in enumerate(self._buttons):
            btn_rect = btn.geometry()
            if content_pos.x() < btn_rect.center().x():
                return i
        return len(self._buttons)

    def _add_button_from_drop(self, code):
        script_type = _detect_script_type(code)
        new_btn = core.make_default_button(command=code, command_type=script_type)
        core.add_button_to_shelf(self._shelf_name, new_btn)
        self.refresh()
        cmds.inViewMessage(
            amg="Button added to shelf <hl>{}</hl>".format(self._shelf_name),
            pos="botCenter", fade=True, fadeStayTime=1000
        )


def restore_panel(shelf_name):
    """Restore a panel from workspace layout (called by uiScript on Maya restart)."""
    if shelf_name not in core.get_all_shelf_names():
        return None

    base_name = PANEL_PREFIX + shelf_name.replace(" ", "_")
    workspace_name = base_name + "WorkspaceControl"

    if workspace_name in _active_panels:
        return workspace_name

    # When called from uiScript, the workspaceControl already exists
    # Parent widget directly to existing container instead of creating new one
    ptr = omui.MQtUtil.findControl(workspace_name)
    if ptr:
        parent_widget = wrapInstance(int(ptr), QWidget)
        panel = ShelfPanel(shelf_name, parent=parent_widget)
        panel.setObjectName(base_name + "_content")
        if parent_widget.layout():
            parent_widget.layout().addWidget(panel)
    else:
        # Fallback: workspaceControl doesn't exist, create via show()
        ui_script = "from neo_shelf import widgets; widgets.restore_panel('{}')".format(shelf_name)
        panel = ShelfPanel(shelf_name)
        panel.show(
            dockable=True,
            retain=False,
            widthProperty='free',
            heightProperty='free',
            minimumWidth=30,
            minimumHeight=30,
            uiScript=ui_script,
            actLikeMayaUIElement=True
        )

    _register_panel_close_callback(workspace_name)

    return workspace_name


def create_panel(shelf_name):
    """Create a new dockable shelf panel."""
    if shelf_name not in core.get_all_shelf_names():
        core.create_shelf(shelf_name)

    base_name = PANEL_PREFIX + shelf_name.replace(" ", "_")
    workspace_name = base_name + "WorkspaceControl"
    ui_script = "from neo_shelf import widgets; widgets.restore_panel('{}')".format(shelf_name)

    # Check if workspaceControl exists
    if cmds.workspaceControl(workspace_name, exists=True):
        # Panel already tracked and valid - just restore visibility
        if workspace_name in _active_panels:
            try:
                cmds.workspaceControl(workspace_name, edit=True, restore=True)
                cmds.workspaceControl(workspace_name, edit=True, visible=True)
                return workspace_name
            except RuntimeError:
                pass

        # WorkspaceControl exists but no panel (stale from previous session)
        # Delete it so we can create fresh with proper uiScript
        cmds.deleteUI(workspace_name)

    if cmds.workspaceControlState(workspace_name, exists=True):
        cmds.workspaceControlState(workspace_name, remove=True)

    panel = ShelfPanel(shelf_name)
    panel.show(
        dockable=True,
        floating=False,
        retain=False,
        widthProperty='free',
        heightProperty='free',
        minimumWidth=30,
        minimumHeight=30,
        uiScript=ui_script,
        actLikeMayaUIElement=True
    )

    _register_panel_close_callback(workspace_name)
    core.set_active_shelf(shelf_name)

    return workspace_name


def close_panel(workspace_name):
    """Close a shelf panel."""
    if cmds.workspaceControl(workspace_name, exists=True):
        cmds.deleteUI(workspace_name)
    if cmds.workspaceControlState(workspace_name, exists=True):
        cmds.workspaceControlState(workspace_name, remove=True)

    core.unregister_panel(workspace_name)

    if workspace_name in _active_panels:
        del _active_panels[workspace_name]


def refresh_all_panels():
    """Refresh all open shelf panels."""
    # First, recover any panels that exist in config but not in _active_panels
    config = core.load_config()
    orphans = []
    for workspace_name, shelf_name in config.get("panels", {}).items():
        if workspace_name not in _active_panels:
            # Try to find existing widget and register it
            ptr = omui.MQtUtil.findControl(workspace_name)
            if ptr:
                parent_widget = wrapInstance(int(ptr), QWidget)
                # Look for ShelfPanel child widget
                found = False
                for child in parent_widget.findChildren(QWidget):
                    if isinstance(child, ShelfPanel):
                        _active_panels[workspace_name] = child
                        found = True
                        break
                if not found:
                    # No ShelfPanel found - mark as orphan to clean up
                    orphans.append(workspace_name)
            else:
                # WorkspaceControl doesn't exist - mark for cleanup
                orphans.append(workspace_name)

    # Clean up orphaned panel entries from config and delete stale workspaceControls
    for ws in orphans:
        if cmds.workspaceControl(ws, exists=True):
            try:
                cmds.deleteUI(ws)
            except Exception:
                pass
        core.unregister_panel(ws)

    # Now refresh all tracked panels
    for ws, panel in list(_active_panels.items()):
        try:
            panel.refresh()
        except Exception:
            pass
    # Force Qt to process events (fixes docked panel refresh bug)
    QApplication.processEvents()


def show(shelf_name=None):
    """Show a shelf panel. If no name given, show manager."""
    if shelf_name:
        create_panel(shelf_name)
    else:
        try:
            from . import manager
            manager.show()
        except ImportError:
            cmds.warning("[neo_shelf] Manager not yet implemented")
