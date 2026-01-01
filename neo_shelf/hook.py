import maya.cmds as cmds
from . import core


def add_menu_item_to_shelf(menu_item_name):
    """
    Called from menuItemToShelf.mel when user Ctrl+Shift+Clicks a menu item.
    Extracts command/icon/label and adds to active neo_shelf.
    """
    active = core.get_active_shelf()
    if not active:
        cmds.warning("[neo_shelf] No active shelf. Click on a shelf panel first.")
        return False

    button_data = extract_menu_item_data(menu_item_name)
    if button_data:
        core.add_button_to_shelf(active, button_data)
        cmds.inViewMessage(
            msg="Added to shelf: {}".format(active),
            pos="topCenter",
            fade=True
        )
        refresh_active_panel()
        return True
    return False


def extract_menu_item_data(menu_item):
    """Extract command, icon, label from a Maya menu item."""
    if not cmds.menuItem(menu_item, exists=True):
        cmds.warning("[neo_shelf] Menu item not found: {}".format(menu_item))
        return None

    label = cmds.menuItem(menu_item, query=True, label=True) or "Unknown"
    annotation = cmds.menuItem(menu_item, query=True, annotation=True) or ""
    command = cmds.menuItem(menu_item, query=True, command=True) or ""
    source_type = cmds.menuItem(menu_item, query=True, sourceType=True) or "mel"
    image = cmds.menuItem(menu_item, query=True, image=True) or ""

    if not image:
        image = "commandButton.png"

    command_type = "mel" if source_type == "mel" else "python"

    return {
        "icon": image,
        "label": label[:12] if len(label) > 12 else label,
        "width": None,
        "bg_color": None,
        "label_bg_color": None,
        "label_text_color": None,
        "command": command,
        "command_type": command_type,
        "shift_command": "",
        "shift_command_type": "python",
        "submenu": [],
        "annotation": annotation or label,
    }


def refresh_active_panel():
    """Trigger refresh of the currently active shelf panel."""
    try:
        from . import widgets
        widgets.refresh_all_panels()
    except Exception:
        pass
