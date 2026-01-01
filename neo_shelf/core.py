import json
import os
import maya.cmds as cmds

CONFIG_FILENAME = "neo_shelf_config.json"

DEFAULT_SETTINGS = {
    "icon_size": 55,
    "show_labels": True,
    "default_layout": "flow",
    "triggers": {
        "main_command": "lmb_click",
        "secondary_command": "shift_lmb_click",
        "open_manager": "rmb_click",
        "show_submenu": "lmb_hold",
    },
}

DEFAULT_SHELF = {
    "layout": "horizontal",
    "alignment": "left",
    "icon_size": 55,
    "bg_color": [0.22, 0.22, 0.22],
    "active_highlight_color": [0.3, 0.5, 0.7],
    "hide_highlight": False,
    "buttons": [],
}

_config_cache = None
_active_shelf = None


def get_config_path():
    scripts_dir = cmds.internalVar(userScriptDir=True)
    return os.path.join(scripts_dir, CONFIG_FILENAME)


def load_config():
    global _config_cache
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
                for key, val in DEFAULT_SETTINGS.items():
                    _config_cache.setdefault("settings", {}).setdefault(key, val)
                return _config_cache
        except Exception as e:
            cmds.warning("Failed to load neo_shelf config: {}".format(e))

    _config_cache = {
        "settings": dict(DEFAULT_SETTINGS),
        "active_shelf": "",
        "shelves": {},
        "panels": {},
    }
    return _config_cache


def save_config(config=None):
    global _config_cache
    if config is not None:
        _config_cache = config
    if _config_cache is None:
        return

    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_config_cache, f, indent=2)
    except Exception as e:
        cmds.warning("Failed to save neo_shelf config: {}".format(e))


def get_active_shelf():
    global _active_shelf
    if _active_shelf:
        return _active_shelf
    config = load_config()
    return config.get("active_shelf", "")


def set_active_shelf(name):
    global _active_shelf
    _active_shelf = name
    config = load_config()
    config["active_shelf"] = name
    save_config()


def create_shelf(name):
    config = load_config()
    if name not in config["shelves"]:
        config["shelves"][name] = dict(DEFAULT_SHELF)
        config["shelves"][name]["buttons"] = []
        save_config()
        return True
    return False


def delete_shelf(name):
    config = load_config()
    if name in config["shelves"]:
        del config["shelves"][name]
        panels_to_remove = [p for p, s in config.get("panels", {}).items() if s == name]
        for p in panels_to_remove:
            del config["panels"][p]
        if config.get("active_shelf") == name:
            config["active_shelf"] = ""
        save_config()
        return True
    return False


def rename_shelf(old_name, new_name):
    config = load_config()
    if old_name in config["shelves"] and new_name not in config["shelves"]:
        config["shelves"][new_name] = config["shelves"].pop(old_name)
        for p, s in list(config.get("panels", {}).items()):
            if s == old_name:
                config["panels"][p] = new_name
        if config.get("active_shelf") == old_name:
            config["active_shelf"] = new_name
        save_config()
        return True
    return False


def get_shelf_data(name):
    config = load_config()
    return config.get("shelves", {}).get(name)


def update_shelf_settings(name, **kwargs):
    config = load_config()
    if name in config["shelves"]:
        for key, val in kwargs.items():
            if val is not None:
                config["shelves"][name][key] = val
        save_config()
        return True
    return False


def add_button_to_shelf(shelf_name, button_data, index=None):
    config = load_config()
    if shelf_name not in config["shelves"]:
        create_shelf(shelf_name)
        config = load_config()

    buttons = config["shelves"][shelf_name].setdefault("buttons", [])
    if index is None:
        buttons.append(button_data)
    else:
        buttons.insert(index, button_data)
    save_config()
    return True


def update_button(shelf_name, button_index, updates):
    config = load_config()
    shelf = config.get("shelves", {}).get(shelf_name)
    if not shelf:
        return False

    buttons = shelf.get("buttons", [])
    if button_index < 0 or button_index >= len(buttons):
        return False

    buttons[button_index].update(updates)
    save_config()
    return True


def remove_button(shelf_name, button_index):
    config = load_config()
    shelf = config.get("shelves", {}).get(shelf_name)
    if not shelf:
        return False

    buttons = shelf.get("buttons", [])
    if button_index < 0 or button_index >= len(buttons):
        return False

    buttons.pop(button_index)
    save_config()
    return True


def move_button(shelf_name, from_index, to_index):
    config = load_config()
    shelf = config.get("shelves", {}).get(shelf_name)
    if not shelf:
        return False

    buttons = shelf.get("buttons", [])
    if from_index < 0 or from_index >= len(buttons):
        return False
    if to_index < 0 or to_index > len(buttons):
        return False

    btn = buttons.pop(from_index)
    if to_index > from_index:
        to_index -= 1
    buttons.insert(to_index, btn)
    save_config()
    return True


def update_shelf_buttons(shelf_name, buttons):
    config = load_config()
    shelf = config.get("shelves", {}).get(shelf_name)
    if not shelf:
        return False
    shelf["buttons"] = buttons
    save_config()
    return True


def get_all_shelf_names():
    config = load_config()
    return list(config.get("shelves", {}).keys())


def register_panel(workspace_name, shelf_name):
    config = load_config()
    config.setdefault("panels", {})[workspace_name] = shelf_name
    save_config()


def unregister_panel(workspace_name):
    config = load_config()
    if workspace_name in config.get("panels", {}):
        del config["panels"][workspace_name]
        save_config()


def make_default_button(name="", label="", command="", command_type="python", icon="commandButton.png"):
    return {
        "name": name,
        "icon": icon,
        "label": label,
        "bg_color": None,
        "icon_tint": None,
        "label_bg_color": None,
        "label_text_color": None,
        "command": command,
        "command_type": command_type,
        "shift_command": "",
        "shift_command_type": "python",
        "submenu": [],
        "annotation": "",
    }


def make_separator():
    return {"separator": True}


def get_trigger_settings():
    config = load_config()
    return config.get("settings", {}).get("triggers", DEFAULT_SETTINGS["triggers"])


def set_trigger_settings(triggers):
    config = load_config()
    config.setdefault("settings", {})["triggers"] = triggers
    save_config()
