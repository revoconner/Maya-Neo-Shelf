from . import core
from . import hook
from . import widgets

__version__ = "0.1.0"


def show(shelf_name=None):
    """
    Show a shelf panel.
    If shelf_name is provided, opens that shelf.
    If not, opens the manager.
    """
    widgets.show(shelf_name)


def create_shelf(name):
    """Create a new shelf."""
    return core.create_shelf(name)


def create_panel(shelf_name):
    """Create a dockable panel for a shelf."""
    return widgets.create_panel(shelf_name)


def close_panel(workspace_name):
    """Close a shelf panel."""
    return widgets.close_panel(workspace_name)


def add_menu_item_to_active_shelf(menu_item):
    """Add a menu item to the active shelf (called from MEL hook)."""
    return hook.add_menu_item_to_shelf(menu_item)


def get_active_shelf():
    """Get the name of the currently active shelf."""
    return core.get_active_shelf()


def set_active_shelf(name):
    """Set the active shelf by name."""
    return core.set_active_shelf(name)


def refresh():
    """Refresh all open shelf panels."""
    widgets.refresh_all_panels()
