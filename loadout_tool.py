"""
Helldivers 2 loadout manager.
Run from this folder: python loadout_tool.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import threading
import ctypes
import time
import webbrowser
from html import unescape
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    from pynput import keyboard as pynput_keyboard
except Exception:
    pynput_keyboard = None

if sys.platform == "win32":
    from ctypes import wintypes

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("USERPROFILE", ".")) / ".loadout_tool"
HELLDIVERS_DATA_PATH = SCRIPT_DIR / "helldivers_loadout_data.json"
WEAPON_STATS_PATH = SCRIPT_DIR / "weapon_stats.json"
ARMOR_STATS_PATH = SCRIPT_DIR / "armor_stats.json"
SAVED_HELLDIVERS_LOADOUTS = DATA_DIR / "helldivers_saved_loadouts.json"
SAVED_WEB_LINKS = DATA_DIR / "web_links.json"
APP_SETTINGS_PATH = DATA_DIR / "app_settings.json"
ICON_DIR = DATA_DIR / "icons"
ICON_SIZE = 40  # pixels for icon thumbnails
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_END = 0x23
VK_DOWN = 0x28
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040

HOTKEY_OPTIONS = [
    {"id": "kp1", "label": "Numpad 1", "vk": 0x61, "tk": "<KP_1>"},
    {"id": "kp2", "label": "Numpad 2", "vk": 0x62, "tk": "<KP_2>"},
    {"id": "end", "label": "End", "vk": 0x23, "tk": "<End>"},
    {"id": "down", "label": "Down Arrow", "vk": 0x28, "tk": "<Down>"},
    {"id": "f8", "label": "F8", "vk": 0x77, "tk": "<F8>"},
    {"id": "f9", "label": "F9", "vk": 0x78, "tk": "<F9>"},
    {"id": "f10", "label": "F10", "vk": 0x79, "tk": "<F10>"},
    {"id": "f11", "label": "F11", "vk": 0x7A, "tk": "<F11>"},
    {"id": "f12", "label": "F12", "vk": 0x7B, "tk": "<F12>"},
]

DEFAULT_HOTKEYS = {
    "toggle_visibility": "kp1",
    "toggle_overlay": "kp2",
}


def _normalize_hotkey_token(value: str) -> str:
    token = str(value or "").strip().lower()
    if token.startswith("<") and token.endswith(">"):
        token = token[1:-1]
    token = token.replace("keypress-", "")
    token = token.replace("key-", "")
    token = re.sub(r"[\s_\-]+", "", token)
    return token


def _make_hotkey_spec(token: str) -> dict[str, object] | None:
    token = _normalize_hotkey_token(token)
    if not token:
        return None

    token_aliases = {
        "leftarrow": "left",
        "rightarrow": "right",
        "uparrow": "up",
        "downarrow": "down",
        "pgup": "pageup",
        "pgdn": "pagedown",
        "return": "enter",
        "esc": "escape",
        "del": "delete",
    }
    token = token_aliases.get(token, token)

    predefined = {str(opt["id"]): opt for opt in HOTKEY_OPTIONS}
    if token in predefined:
        return dict(predefined[token])

    special_keys = {
        "left": {"label": "Left Arrow", "vk": 0x25, "tk": "<Left>"},
        "up": {"label": "Up Arrow", "vk": 0x26, "tk": "<Up>"},
        "right": {"label": "Right Arrow", "vk": 0x27, "tk": "<Right>"},
        "down": {"label": "Down Arrow", "vk": 0x28, "tk": "<Down>"},
        "home": {"label": "Home", "vk": 0x24, "tk": "<Home>"},
        "end": {"label": "End", "vk": 0x23, "tk": "<End>"},
        "insert": {"label": "Insert", "vk": 0x2D, "tk": "<Insert>"},
        "delete": {"label": "Delete", "vk": 0x2E, "tk": "<Delete>"},
        "pageup": {"label": "Page Up", "vk": 0x21, "tk": "<Prior>"},
        "pagedown": {"label": "Page Down", "vk": 0x22, "tk": "<Next>"},
        "space": {"label": "Space", "vk": 0x20, "tk": "<space>"},
        "tab": {"label": "Tab", "vk": 0x09, "tk": "<Tab>"},
        "escape": {"label": "Escape", "vk": 0x1B, "tk": "<Escape>"},
        "enter": {"label": "Enter", "vk": 0x0D, "tk": "<Return>"},
        "backspace": {"label": "Backspace", "vk": 0x08, "tk": "<BackSpace>"},
    }
    if token in special_keys:
        spec = dict(special_keys[token])
        spec["id"] = token
        return spec

    if token.startswith("kp") and token[2:].isdigit():
        num = int(token[2:])
        if 0 <= num <= 9:
            return {
                "id": token,
                "label": f"Numpad {num}",
                "vk": 0x60 + num,
                "tk": f"<KP_{num}>",
            }

    if token.startswith("num") and token[3:].isdigit():
        num = int(token[3:])
        if 0 <= num <= 9:
            return {
                "id": f"kp{num}",
                "label": f"Numpad {num}",
                "vk": 0x60 + num,
                "tk": f"<KP_{num}>",
            }

    if token.startswith("f") and token[1:].isdigit():
        num = int(token[1:])
        if 1 <= num <= 24:
            return {
                "id": token,
                "label": f"F{num}",
                "vk": 0x70 + (num - 1),
                "tk": f"<F{num}>",
            }

    if len(token) == 1 and token.isalpha():
        return {
            "id": token,
            "label": token.upper(),
            "vk": ord(token.upper()),
            "tk": f"<KeyPress-{token}>",
        }

    if len(token) == 1 and token.isdigit():
        return {
            "id": token,
            "label": token,
            "vk": ord(token),
            "tk": f"<KeyPress-{token}>",
        }

    return None


def _resolve_hotkey_choice(value: str) -> dict[str, object] | None:
    text = str(value or "").strip()
    if not text:
        return None

    normalized = _normalize_hotkey_token(text)
    for opt in HOTKEY_OPTIONS:
        if normalized in {
            str(opt["id"]),
            _normalize_hotkey_token(str(opt["label"])),
            _normalize_hotkey_token(str(opt["tk"])),
        }:
            return dict(opt)
    return _make_hotkey_spec(normalized)


def _get_window_process_name(hwnd: int) -> str:
    if sys.platform != "win32" or not hwnd:
        return ""

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not proc:
        return ""

    try:
        size = wintypes.DWORD(260)
        buff = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(proc, 0, buff, ctypes.byref(size))
        if not ok:
            return ""
        return Path(buff.value).name.lower()
    finally:
        kernel32.CloseHandle(proc)

def _find_helldivers_hwnd() -> int | None:
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    matches: list[int] = []
    process_names = {
        "helldivers2.exe",
        "helldivers 2.exe",
    }

    def _enum_cb(hwnd: int, _lparam: int) -> int:
        if not user32.IsWindowVisible(hwnd):
            return 1
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip().lower()
        process_name = _get_window_process_name(int(hwnd))
        if "helldivers" in title or process_name in process_names:
            matches.append(int(hwnd))
            return 0
        return 1

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(_enum_cb)
    user32.EnumWindows(enum_proc, 0)
    return matches[0] if matches else None


def _focus_window(hwnd: int) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)
    return bool(user32.SetForegroundWindow(hwnd))


def _set_window_topmost(hwnd: int, enabled: bool) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    user32 = ctypes.windll.user32
    insert_after = HWND_TOPMOST if enabled else HWND_NOTOPMOST
    flags = SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
    return bool(user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags))


def _set_windows_dpi_aware() -> None:
    """Align coordinate space on scaled displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


NONE_CHOICE = "-- none --"


def _with_none(options: list[str]) -> list[str]:
    return [NONE_CHOICE] + list(options)


def _unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _is_valid_stratagem_name(name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False

    lower = name.lower()
    blocked_prefixes = (
        "edit section:",
        "helldivers 1:",
        "helldivers 2",
    )
    blocked_exact = {
        "medal",
        "requisition slips",
        "stratagems/stratagem previews",
        "reinforce",
        "resupply",
        "sos beacon",
        "eagle rearm",
        "call in super destroyer",
        "nux-223 hellbomb",
        "upload data",
        "sssd delivery",
        "super earth flag",
        "seismic probe",
        "prospecting drill",
        "dark fluid vessel",
        "tectonic drill",
        "hive breaker drill",
        "cargo container",
        "reinforcement pods",
        "seaf artillery",
        "orbital illumination flare",
        "a stratagem permit",
        "government of super earth",
        "ship master",
        "template:nav stratagem",
    }
    blocked_contains = (
        "premium warbond",
        "legendary warbond",
    )

    if lower in blocked_exact:
        return False
    if any(lower.startswith(p) for p in blocked_prefixes):
        return False
    if any(token in lower for token in blocked_contains):
        return False

    return True


def _clean_stratagem_list(values: list[str]) -> list[str]:
    return _unique_ordered(
        [
            str(v).strip()
            for v in values
            if isinstance(v, str) and _is_valid_stratagem_name(str(v))
        ]
    )


def _collect_stratagem_options(game_data: dict) -> list[str]:
    opts: list[str] = []

    flat = game_data.get("stratagems_flat")
    if isinstance(flat, list):
        opts.extend(_clean_stratagem_list(flat))

    groups = game_data.get("stratagem_groups")
    if isinstance(groups, dict):
        for group_values in groups.values():
            if isinstance(group_values, list):
                opts.extend(_clean_stratagem_list(group_values))

    return _unique_ordered(opts)


def _collect_armor_options(game_data: dict) -> list[str]:
    opts: list[str] = []

    armor = game_data.get("armor")
    if not isinstance(armor, dict):
        return opts

    by_weight = armor.get("body_by_weight")
    if not isinstance(by_weight, dict):
        return opts

    passive_by_body = armor.get("passive_by_body")
    if not isinstance(passive_by_body, dict):
        passive_by_body = {}

    ordered_groups = (
        ("Light", by_weight.get("light")),
        ("Medium", by_weight.get("medium")),
        ("Heavy", by_weight.get("heavy")),
    )
    seen_names: set[str] = set()

    for group_name, values in ordered_groups:
        if not isinstance(values, list):
            continue
        valid = [str(v) for v in values if isinstance(v, str) and v]
        if not valid:
            continue
        opts.append(f"--- {group_name} ---")
        for name in valid:
            if name in seen_names:
                continue
            seen_names.add(name)
            passive = str(passive_by_body.get(name) or "").strip()
            if passive:
                opts.append(f"{group_name}: {name} ({passive})")
            else:
                opts.append(f"{group_name}: {name}")

    return opts


def _armor_label_to_name(value: str) -> str:
    if not value:
        return ""
    if value.startswith("--- ") and value.endswith(" ---"):
        return ""
    if ": " in value:
        label = value.split(": ", 1)[1].strip()
        # Dropdown label format: "Weight: Armor Name (Passive)"
        if label.endswith(")") and " (" in label:
            label = label.rsplit(" (", 1)[0].rstrip()
        return label
    return value.strip()


def _armor_name_to_label(options: list[str], armor_name: str) -> str:
    armor_name = (armor_name or "").strip()
    if not armor_name:
        return ""

    for opt in options:
        if _armor_label_to_name(str(opt)) == armor_name:
            return str(opt)
    return ""


def _collect_secondary_options(game_data: dict) -> list[str]:
    """Combine pistols and melee into grouped dropdown options."""
    opts: list[str] = []
    sec = game_data.get("secondary") or {}
    
    pistols = sec.get("pistols")
    if isinstance(pistols, list):
        valid = [str(v) for v in pistols if isinstance(v, str) and v]
        if valid:
            opts.append("--- Pistols ---")
            opts.extend(f"Pistol: {name}" for name in valid)
    
    melee = sec.get("melee")
    if isinstance(melee, list):
        valid = [str(v) for v in melee if isinstance(v, str) and v]
        if valid:
            opts.append("--- Melee ---")
            opts.extend(f"Melee: {name}" for name in valid)
    
    return opts


def _secondary_label_to_name(value: str) -> tuple[str, str]:
    """Convert dropdown label to (type, name). Returns (type, name) where type is 'pistol' or 'melee'."""
    if not value or value.startswith("--- "):
        return "", ""
    
    if value.startswith("Pistol: "):
        return "pistol", value[8:].strip()
    elif value.startswith("Melee: "):
        return "melee", value[7:].strip()
    
    return "", ""


def _secondary_name_to_label(options: list[str], sec_type: str, sec_name: str) -> str:
    """Convert (type, name) to dropdown label using reverse lookup."""
    sec_type = (sec_type or "").strip().lower()
    sec_name = (sec_name or "").strip()
    if not sec_type or not sec_name:
        return ""
    
    prefix = "Pistol: " if sec_type == "pistol" else "Melee: " if sec_type == "melee" else ""
    if not prefix:
        return ""
    
    target = f"{prefix}{sec_name}"
    for opt in options:
        if str(opt) == target:
            return str(opt)
    return ""


def _fetch_wiki_parse_html(page_name: str) -> str:
    """Fetch rendered page HTML via MediaWiki API with anti-bot friendly headers."""
    urls = [
        f"https://helldivers.wiki.gg/api.php?action=parse&page={page_name}&prop=text&format=json",
        f"https://helldivers.wiki.gg/api.php?action=parse&page={page_name}&prop=text&format=json&origin=*",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://helldivers.wiki.gg/",
    }

    last_err: Exception | None = None
    for url in urls:
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))

            parse = payload.get("parse")
            if not isinstance(parse, dict):
                raise ValueError("Missing parse payload")

            text = parse.get("text")
            if isinstance(text, dict):
                html = str(text.get("*", ""))
            elif isinstance(text, str):
                html = text
            else:
                html = ""

            if html:
                return html
            raise ValueError("API response did not include rendered HTML")
        except Exception as e:
            last_err = e

    raise URLError(str(last_err) if last_err else f"Unknown error fetching {page_name}")


def update_helldivers_wiki_data() -> tuple[bool, str]:
    """Fetch latest armor and stratagem data from wiki and update JSON."""
    try:
        current_data = load_helldivers_game_data() or {}
        
        # Fetch wiki pages from API with browser-like headers to avoid 403 blocks.
        try:
            armor_html = _fetch_wiki_parse_html("Armor")
        except URLError as e:
            return False, f"Failed to fetch Armor wiki API page: {e}"
        
        try:
            strat_html = _fetch_wiki_parse_html("Stratagems")
        except URLError as e:
            return False, f"Failed to fetch Stratagems wiki API page: {e}"
        
        # Extract armor names and passives from rendered API HTML.
        armors_light: list[str] = []
        armors_medium: list[str] = []
        armors_heavy: list[str] = []
        passive_by_body: dict[str, str] = {}

        light_marker = 'id="Light-0"'
        medium_marker = 'id="Medium-0"'
        heavy_marker = 'id="Heavy-0"'
        helmet_marker = 'id="Helmet-0"'

        light_idx = armor_html.find(light_marker)
        medium_idx = armor_html.find(medium_marker)
        heavy_idx = armor_html.find(heavy_marker)
        helmet_idx = armor_html.find(helmet_marker)

        if light_idx != -1 and medium_idx != -1 and heavy_idx != -1 and helmet_idx != -1:
            sections = [
                ("light", armor_html[light_idx:medium_idx]),
                ("medium", armor_html[medium_idx:heavy_idx]),
                ("heavy", armor_html[heavy_idx:helmet_idx]),
            ]

            row_re = re.compile(r"<tr>.*?</tr>", re.DOTALL | re.IGNORECASE)
            title_re = re.compile(r'title="([^"]+)"', re.IGNORECASE)

            for weight, section in sections:
                for row in row_re.findall(section):
                    titles = [
                        unescape(t).strip()
                        for t in title_re.findall(row)
                        if t and not t.lower().startswith("file:")
                    ]
                    # Typical title order: [Armor Name, Passive, ...]
                    if len(titles) < 2:
                        continue
                    armor_name = titles[0]
                    passive_name = titles[1]
                    if not armor_name or not passive_name:
                        continue

                    if weight == "light" and armor_name not in armors_light:
                        armors_light.append(armor_name)
                    elif weight == "medium" and armor_name not in armors_medium:
                        armors_medium.append(armor_name)
                    elif weight == "heavy" and armor_name not in armors_heavy:
                        armors_heavy.append(armor_name)

                    passive_by_body[armor_name] = passive_name
        
        # Update armor data if found
        if armors_light or armors_medium or armors_heavy:
            if "armor" not in current_data:
                current_data["armor"] = {"weight_class_counts": {}, "body_by_weight": {}, "passives": []}
            armor_dict = current_data["armor"]
            if "body_by_weight" not in armor_dict:
                armor_dict["body_by_weight"] = {}
            if "weight_class_counts" not in armor_dict:
                armor_dict["weight_class_counts"] = {}
            
            if armors_light:
                armor_dict["body_by_weight"]["light"] = armors_light
                armor_dict["weight_class_counts"]["light"] = len(armors_light)
            if armors_medium:
                armor_dict["body_by_weight"]["medium"] = armors_medium
                armor_dict["weight_class_counts"]["medium"] = len(armors_medium)
            if armors_heavy:
                armor_dict["body_by_weight"]["heavy"] = armors_heavy
                armor_dict["weight_class_counts"]["heavy"] = len(armors_heavy)

            if passive_by_body:
                armor_dict["passive_by_body"] = passive_by_body
                armor_dict["passives"] = sorted({p for p in passive_by_body.values() if p})
        
        # Extract stratagem names from HTML
        strats_flat = []
        lines = strat_html.split("\n")
        for line in lines:
            if "<a href" in line.lower() and "title=" in line.lower():
                if "/wiki/" in line:
                    if 'title="' in line:
                        parts = line.split('title="')
                        if len(parts) > 1:
                            name = parts[1].split('"')[0]
                            if name and not name.startswith("file:") and not name.startswith("Category:"):
                                name = name.strip()
                                if _is_valid_stratagem_name(name) and name not in strats_flat and len(strats_flat) < 200:
                                    strats_flat.append(name)
        
        # Update stratagem data if found
        if strats_flat:
            current_data["stratagems_flat"] = _clean_stratagem_list(strats_flat)

        # Sanity cleanup for legacy files that contain headings/source entries.
        existing_flat = current_data.get("stratagems_flat")
        if isinstance(existing_flat, list):
            current_data["stratagems_flat"] = _clean_stratagem_list(existing_flat)
        
        # Save updated data
        with open(HELLDIVERS_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
        
        # Launch weapon stats scraper in background (non-blocking subprocess)
        weapon_script = SCRIPT_DIR / "fetch_weapon_stats_v2.py"
        if weapon_script.is_file():
            try:
                # Log file for weapon scraper output (silent in background)
                log_file = DATA_DIR / "weapon_scraper.log"
                with open(log_file, "w", encoding="utf-8") as log:
                    subprocess.Popen(
                        [sys.executable, str(weapon_script)],
                        cwd=str(SCRIPT_DIR),
                        stdout=log,
                        stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
            except Exception:
                pass  # Silently fail if subprocess cannot start
        
        armor_count = len(armors_light) + len(armors_medium) + len(armors_heavy)
        return True, f"Updated wiki data:\n{len(strats_flat)} stratagems\n{armor_count} armor pieces\n(weapon stats updating in background…)"
    
    except Exception as e:
        return False, f"Error updating wiki data: {e}"


def load_helldivers_game_data() -> dict | None:
    if not HELLDIVERS_DATA_PATH.is_file():
        return None
    try:
        return json.loads(HELLDIVERS_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_saved_helldivers_loadouts() -> dict[str, dict]:
    if not SAVED_HELLDIVERS_LOADOUTS.is_file():
        return {}
    try:
        data = json.loads(SAVED_HELLDIVERS_LOADOUTS.read_text(encoding="utf-8"))
        raw = data.get("loadouts")
        if isinstance(raw, dict):
            return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_saved_helldivers_loadouts(loadouts: dict[str, dict]) -> None:
    ensure_data_dir()
    payload = {"version": 1, "loadouts": loadouts}
    with open(SAVED_HELLDIVERS_LOADOUTS, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_web_links() -> list[dict[str, str]]:
    defaults = [
        {"name": "Link 1", "url": ""},
        {"name": "Link 2", "url": ""},
        {"name": "Link 3", "url": ""},
    ]
    if not SAVED_WEB_LINKS.is_file():
        return defaults

    try:
        data = json.loads(SAVED_WEB_LINKS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults

    raw_links = data.get("links") if isinstance(data, dict) else None
    if not isinstance(raw_links, list):
        return defaults

    out: list[dict[str, str]] = []
    for i in range(3):
        item = raw_links[i] if i < len(raw_links) else None
        if isinstance(item, dict):
            name = str(item.get("name") or f"Link {i + 1}").strip() or f"Link {i + 1}"
            url = str(item.get("url") or "").strip()
            out.append({"name": name, "url": url})
        else:
            out.append({"name": f"Link {i + 1}", "url": ""})
    return out


def save_web_links(links: list[dict[str, str]]) -> None:
    ensure_data_dir()
    payload = {"version": 1, "links": links[:3]}
    with open(SAVED_WEB_LINKS, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_app_settings() -> dict:
    if not APP_SETTINGS_PATH.is_file():
        return {}
    try:
        data = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_app_settings(settings: dict) -> None:
    ensure_data_dir()
    with open(APP_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


class IconCache:
    """Downloads item icons from the wiki and caches them to disk.

    Uses the MediaWiki API (2 calls per new item) to discover the correct image
    file (PNG render or SVG stratagem icon -> rasterised PNG thumb) then downloads
    and caches it locally.
    """

    _WIKI_API = "https://helldivers.wiki.gg/api.php"
    _PNG_MAGIC = b"\x89PNG"
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://helldivers.wiki.gg/",
    }
    _PREFER_SUFFIXES = (
        "_primary_render.png",
        "_support_render.png",
        "_armor_render.png",
        "_render.png",
    )

    def __init__(self) -> None:
        self._mem: dict[str, tk.PhotoImage | None] = {}
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def _disk_path(self, name: str) -> Path:
        safe = re.sub(r"[^\w\-. ]", "_", name).strip().replace(" ", "_")
        return ICON_DIR / f"{safe}.png"

    def _api_get(self, params: dict) -> dict:
        qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
        req = Request(f"{self._WIKI_API}?{qs}", headers=self._HEADERS)
        with urlopen(req, timeout=12) as resp:
            return json.loads(resp.read())

    def _find_thumb_url(self, page_name: str) -> str | None:
        """Return a PNG thumbnail URL for the best image on the wiki page, or None."""
        # Step 1 — list images used on the page (may be many for nav templates)
        try:
            data = self._api_get({
                "action": "query",
                "titles": page_name,
                "prop": "images",
                "imlimit": "max",
                "format": "json",
            })
        except Exception:
            return None

        images: list[str] = []
        for page in data.get("query", {}).get("pages", {}).values():
            images = [img["title"].replace("File:", "") for img in page.get("images", [])]

        if not images:
            return None

        # Normalize page name words for matching (lowercase, split on spaces/hyphens/digits)
        name_words = set(re.split(r"[\s\-/]+", page_name.lower()))
        name_words = {w for w in name_words if len(w) > 2}

        def _score(fname: str) -> tuple[int, int, int]:
            """Return (suffix_priority, name_word_overlap, -file_word_count) — higher is better."""
            norm = fname.lower().replace(" ", "_")
            suffix_rank = 0
            for rank, suffix in enumerate(self._PREFER_SUFFIXES, start=1):
                if norm.endswith(suffix):
                    suffix_rank = len(self._PREFER_SUFFIXES) - rank + 1
                    break
            file_words = set(re.split(r"[\s\-_/.()+]+", fname.lower()))
            overlap = len(name_words & file_words)
            return (suffix_rank, overlap, -len(file_words))

        # Filter to PNG files with a preferred suffix (SVGs can't be displayed by tk.PhotoImage)
        candidates = [f for f in images if f.lower().endswith(".png") and _score(f)[0] > 0]
        if not candidates:
            return None

        best = max(candidates, key=_score)

        # Step 2 — get a thumbnail URL via imageinfo (handles SVG rasterisation too)
        try:
            data2 = self._api_get({
                "action": "query",
                "titles": f"File:{best}",
                "prop": "imageinfo",
                "iiprop": "url|thumburl",
                "iiurlwidth": str(ICON_SIZE),
                "format": "json",
            })
        except Exception:
            return None

        for page in data2.get("query", {}).get("pages", {}).values():
            for info in page.get("imageinfo", []):
                url = info.get("thumburl") or info.get("url")
                if url:
                    return url
        return None

    def get_async(self, item_name: str, callback, root: tk.Misc) -> None:
        """Fetch icon in a background thread; invoke callback(PhotoImage|None) on the main thread."""
        with self._lock:
            if item_name in self._mem:
                img = self._mem[item_name]
                root.after(0, lambda: callback(img))
                return
            if item_name in self._pending:
                return
            self._pending.add(item_name)

        def _worker() -> None:
            path = self._disk_path(item_name)
            ok = path.is_file() and path.stat().st_size > 4 and path.read_bytes()[:4] == self._PNG_MAGIC
            if not ok:
                try:
                    thumb_url = self._find_thumb_url(item_name)
                    if thumb_url:
                        req = Request(thumb_url, headers=self._HEADERS)
                        with urlopen(req, timeout=10) as resp:
                            data = resp.read()
                        if data[:4] == self._PNG_MAGIC:
                            ICON_DIR.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(data)
                            ok = True
                except Exception:
                    pass

            def _on_main() -> None:
                img: tk.PhotoImage | None = None
                if ok:
                    try:
                        img = tk.PhotoImage(file=str(path))
                    except Exception:
                        img = None
                with self._lock:
                    self._mem[item_name] = img
                    self._pending.discard(item_name)
                callback(img)

            root.after(0, _on_main)

        threading.Thread(target=_worker, daemon=True).start()


_icon_cache = IconCache()


class HelldiversPanel(ttk.Frame):
    """Dropdowns from helldivers_loadout_data.json; save named presets to ~/.loadout_tool/."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=10)
        self._game = load_helldivers_game_data()
        self._weapon_stats = self._load_weapon_stats()
        self._armor_stats = self._load_armor_stats()
        self._passive_descriptions = self._game.get("armor", {}).get("passive_descriptions", {}) if self._game else {}
        self._web_links = load_web_links()
        self._link_buttons: list[ttk.Button] = []
        self._fields: dict[str, ttk.Combobox] = {}
        self._icon_labels: dict[str, tk.Label] = {}
        self._stats_labels: dict[str, tk.Label] = {}  # Store stats display labels
        self._armor_passive_label: tk.Label | None = None
        self._name_entry: ttk.Entry | None = None
        self._saved_cb: ttk.Combobox | None = None
        self._base_strats: list[str] = []  # Store full stratagem list for filtering
        self._placeholder = tk.PhotoImage(width=ICON_SIZE, height=ICON_SIZE)

        if not self._game:
            ttk.Label(
                self,
                text=f"Missing or invalid game data file:\n{HELLDIVERS_DATA_PATH}",
                foreground="#a00",
                justify=tk.CENTER,
            ).pack(expand=True)
            return

        form = ttk.LabelFrame(self, text="Build loadout", padding=8)
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, minsize=ICON_SIZE + 8)

        primaries = _with_none(self._game.get("primary") or [])
        throwables = _with_none(self._game.get("throwable") or [])
        secondary_opts = _with_none(_collect_secondary_options(self._game))
        strats = _with_none(_collect_stratagem_options(self._game))
        self._base_strats = [s for s in strats if s != NONE_CHOICE]  # Store base list without "-- none --"
        armors = _with_none(_collect_armor_options(self._game))
        boosters = _with_none(self._game.get("boosters") or [])

        row = 0
        for label, key, opts in (
            ("Primary", "primary", primaries),
            ("Secondary Weapon", "secondary", secondary_opts),
            ("Throwable", "throwable", throwables),
            ("Armor", "armor", armors),
        ):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
            cb = ttk.Combobox(form, values=opts, width=48, state="readonly")
            cb.set(NONE_CHOICE)
            cb.grid(row=row, column=1, sticky="ew", pady=3)
            # For primary and secondary, also update stats display
            if key in ("primary", "secondary"):
                cb.bind("<<ComboboxSelected>>", lambda e, k=key: [self._update_icon(k), self._update_weapon_stats()])
            elif key == "armor":
                cb.bind("<<ComboboxSelected>>", lambda e, k=key: [self._update_icon(k), self._update_armor_passive()])
            else:
                cb.bind("<<ComboboxSelected>>", lambda e, k=key: self._update_icon(k))
            self._fields[key] = cb
            icon_lbl = tk.Label(form, image=self._placeholder)
            icon_lbl.grid(row=row, column=2, padx=(4, 0), pady=3)
            self._icon_labels[key] = icon_lbl
            row += 1

        for i in range(1, 5):
            key = f"stratagem_{i}"
            ttk.Label(form, text=f"Stratagem {i}").grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
            cb = ttk.Combobox(form, values=strats, width=48, state="readonly")
            cb.set(NONE_CHOICE)
            cb.grid(row=row, column=1, sticky="ew", pady=3)
            cb.bind("<<ComboboxSelected>>", lambda e, k=key: [self._on_stratagem_changed(), self._update_icon(k)])
            self._fields[key] = cb
            icon_lbl = tk.Label(form, image=self._placeholder)
            icon_lbl.grid(row=row, column=2, padx=(4, 0), pady=3)
            self._icon_labels[key] = icon_lbl
            row += 1

        key = "booster_1"
        ttk.Label(form, text="Booster").grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
        cb = ttk.Combobox(form, values=boosters, width=48, state="readonly")
        cb.set(NONE_CHOICE)
        cb.grid(row=row, column=1, sticky="ew", pady=3)
        cb.bind("<<ComboboxSelected>>", lambda e, k=key: self._update_icon(k))
        self._fields[key] = cb
        icon_lbl = tk.Label(form, image=self._placeholder)
        icon_lbl.grid(row=row, column=2, padx=(4, 0), pady=3)
        self._icon_labels[key] = icon_lbl
        row += 1

        # Armor passive display
        ttk.Label(form, text="Armor Passive").grid(row=row, column=0, sticky="nw", pady=3, padx=(0, 8))
        armor_passive_lbl = tk.Label(
            form,
            text="",
            font=("Segoe UI", 9),
            foreground="#666",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=400,
            height=2,
        )
        armor_passive_lbl.grid(row=row, column=1, sticky="w", pady=3)
        self._armor_passive_label = armor_passive_lbl
        row += 1

        # Weapon stats display frame
        stats_fr = ttk.LabelFrame(self, text="Weapon stats", padding=8)
        stats_fr.pack(fill=tk.X, pady=(12, 0))
        stats_fr.columnconfigure(0, weight=1)
        stats_fr.columnconfigure(1, weight=1)
        
        # Primary stats (left)
        primary_text = tk.Label(
            stats_fr,
            text="Select primary weapon",
            font=("Segoe UI", 9),
            foreground="#666",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=300,
            height=7,
        )
        primary_text.grid(row=0, column=0, sticky="nw", padx=(0, 8))
        self._stats_labels["primary"] = primary_text
        
        # Secondary stats (right)
        secondary_text = tk.Label(
            stats_fr,
            text="Select secondary weapon",
            font=("Segoe UI", 9),
            foreground="#666",
            justify=tk.LEFT,
            anchor="nw",
            wraplength=300,
            height=7,
        )
        secondary_text.grid(row=0, column=1, sticky="nw")
        self._stats_labels["secondary"] = secondary_text

        save_fr = ttk.LabelFrame(self, text="Save / load named presets", padding=8)
        save_fr.pack(fill=tk.X, pady=(12, 0))

        line1 = ttk.Frame(save_fr)
        line1.pack(fill=tk.X)
        ttk.Label(line1, text="Name").pack(side=tk.LEFT)
        self._name_entry = ttk.Entry(line1, width=28)
        self._name_entry.pack(side=tk.LEFT, padx=8)
        ttk.Button(line1, text="Save loadout", command=self._on_save).pack(side=tk.LEFT)

        line2 = ttk.Frame(save_fr)
        line2.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(line2, text="Saved").pack(side=tk.LEFT)
        self._saved_cb = ttk.Combobox(line2, width=34, state="readonly")
        self._saved_cb.pack(side=tk.LEFT, padx=8)
        ttk.Button(line2, text="Load", command=self._on_load_selected).pack(side=tk.LEFT)
        ttk.Button(line2, text="Delete", command=self._on_delete_selected).pack(side=tk.LEFT, padx=(8, 0))

        self._refresh_saved_names()

    def _get_val(self, key: str) -> str:
        cb = self._fields[key]
        v = cb.get()
        if v == NONE_CHOICE:
            return ""
        if key == "armor":
            return _armor_label_to_name(v)
        return v

    def _get_secondary_vals(self) -> tuple[str, str]:
        """Get secondary weapon as (type, name)."""
        v = self._fields.get("secondary")
        if not v:
            return "", ""
        return _secondary_label_to_name(v.get())

    def _set_val(self, key: str, value: str) -> None:
        cb = self._fields[key]
        opts = list(cb["values"])
        if not value or value == NONE_CHOICE:
            cb.set(NONE_CHOICE)
            return
        if key == "armor":
            label = _armor_name_to_label([str(v) for v in opts], str(value))
            if label:
                cb.set(label)
                return
        if value not in opts:
            cb.set(NONE_CHOICE)
            return
        cb.set(value)

    def _set_secondary_vals(self, sec_type: str, sec_name: str) -> None:
        """Set secondary weapon from (type, name)."""
        if "secondary" not in self._fields:
            return
        cb = self._fields["secondary"]
        opts = [str(v) for v in cb["values"]]
        label = _secondary_name_to_label(opts, sec_type, sec_name)
        if label:
            cb.set(label)
        else:
            cb.set(NONE_CHOICE)

    def _collect_payload(self) -> dict:
        sec_type, sec_name = self._get_secondary_vals()
        return {
            "schema": 1,
            "primary": self._get_val("primary"),
            "pistol": sec_name if sec_type == "pistol" else "",
            "melee": sec_name if sec_type == "melee" else "",
            "throwable": self._get_val("throwable"),
            "armor": self._get_val("armor"),
            "stratagems": [self._get_val(f"stratagem_{i}") for i in range(1, 5)],
            "boosters": [self._get_val("booster_1")],
        }

    def get_current_build_payload(self) -> dict:
        """Public wrapper used by recorder tab to snapshot selected loadout fields."""
        return self._collect_payload()

    def _apply_payload(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self._set_val("primary", str(data.get("primary") or ""))
        
        # Handle secondary weapon (check pistol or melee)
        pistol = str(data.get("pistol") or "")
        melee = str(data.get("melee") or "")
        if pistol:
            self._set_secondary_vals("pistol", pistol)
        elif melee:
            self._set_secondary_vals("melee", melee)
        else:
            self._set_secondary_vals("", "")
        
        self._set_val("throwable", str(data.get("throwable") or ""))
        self._set_val("armor", str(data.get("armor") or ""))
        st = data.get("stratagems")
        if isinstance(st, list):
            for i in range(4):
                key = f"stratagem_{i + 1}"
                v = str(st[i]) if i < len(st) and st[i] else ""
                self._set_val(key, v)
        bo = data.get("boosters")
        if isinstance(bo, list):
            v = str(bo[0]) if bo and bo[0] else ""
            self._set_val("booster_1", v)
        elif isinstance(bo, str):
            self._set_val("booster_1", bo)
        for key in list(self._icon_labels):
            self._update_icon(key)
        self._update_weapon_stats()
        self._update_armor_passive()

    def _refresh_saved_names(self) -> None:
        if not self._saved_cb:
            return
        names = sorted(load_saved_helldivers_loadouts().keys())
        self._saved_cb["values"] = names
        if names:
            self._saved_cb.set(names[0])
        else:
            self._saved_cb.set("")

    def _key_to_icon_name(self, key: str, raw: str) -> str:
        """Return the wiki image name for a given dropdown key + raw value."""
        if not raw or raw == NONE_CHOICE or raw.startswith("--- "):
            return ""
        if key == "secondary":
            _, name = _secondary_label_to_name(raw)
            return name
        if key == "armor":
            return _armor_label_to_name(raw)
        return raw

    def _update_icon(self, key: str) -> None:
        lbl = self._icon_labels.get(key)
        cb = self._fields.get(key)
        if not lbl or not cb:
            return
        item_name = self._key_to_icon_name(key, cb.get())
        if not item_name:
            lbl.config(image=self._placeholder)
            return

        def _set(img: tk.PhotoImage | None) -> None:
            lbl.config(image=img if img else self._placeholder)
            if img:
                lbl._photo = img  # type: ignore[attr-defined]

        _icon_cache.get_async(item_name, _set, self.winfo_toplevel())

    def _on_stratagem_changed(self) -> None:
        """Update stratagem dropdown options to exclude already-selected items."""
        # Collect currently selected strategems (their names without labels)
        selected: set[str] = set()
        for i in range(1, 5):
            key = f"stratagem_{i}"
            value = self._fields[key].get()
            if value and value != NONE_CHOICE:
                selected.add(value)
        
        # For each stratagem slot, update options to exclude selections in other slots
        for i in range(1, 5):
            key = f"stratagem_{i}"
            current_val = self._fields[key].get()
            
            # Build filtered list: include NONE_CHOICE + base stratagems except those selected in other slots
            filtered = [NONE_CHOICE]
            for strat in self._base_strats:
                if strat not in selected or strat == current_val:
                    filtered.append(strat)
            
            # Update dropdown values
            self._fields[key]["values"] = filtered
            
            # Restore current selection if it's still valid
            if current_val in filtered:
                self._fields[key].set(current_val)
            elif current_val and current_val != NONE_CHOICE:
                # If current value is no longer valid, clear it
                self._fields[key].set(NONE_CHOICE)

    def _load_weapon_stats(self) -> dict:
        """Load weapon stats from weapon_stats.json."""
        try:
            if WEAPON_STATS_PATH.is_file():
                return json.loads(WEAPON_STATS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _load_armor_stats(self) -> dict:
        """Load armor stats from armor_stats.json."""
        try:
            if ARMOR_STATS_PATH.is_file():
                return json.loads(ARMOR_STATS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    @staticmethod
    def _clip_lines(lines: list[str], max_lines: int) -> str:
        """Limit display text to a fixed number of lines to keep layout stable."""
        if len(lines) <= max_lines:
            return "\n".join(lines)
        clipped = lines[: max_lines - 1]
        clipped.append("...")
        return "\n".join(clipped)

    @staticmethod
    def _clip_chars(text: str, max_chars: int) -> str:
        """Limit a single-line label to avoid layout growth from long content."""
        text = str(text or "").strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    def _load_armor_stats(self) -> dict:
        """Load armor stats from armor_stats.json."""
        try:
            if ARMOR_STATS_PATH.is_file():
                return json.loads(ARMOR_STATS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _update_weapon_stats(self) -> None:
        """Update weapon stats display based on selected primary and secondary."""
        if not self._weapon_stats:
            self._stats_labels["primary"].config(text="Weapon stats not available")
            self._stats_labels["secondary"].config(text="")
            return

        primary = self._get_val("primary")
        secondary_type, secondary = self._get_secondary_vals()

        # Primary stats
        if primary and primary in self._weapon_stats.get("primary", {}):
            stats = self._weapon_stats["primary"][primary]
            lines = [f"Primary: {primary}"]
            for key, val in stats.items():
                lines.append(f"{key.replace('_', ' ').title()}: {val}")
            self._stats_labels["primary"].config(text=self._clip_lines(lines, max_lines=7))
        else:
            self._stats_labels["primary"].config(text="Select primary weapon")

        # Secondary stats
        if secondary and secondary in self._weapon_stats.get("secondary", {}):
            stats = self._weapon_stats["secondary"][secondary]
            lines = [f"Secondary: {secondary}"]
            for key, val in stats.items():
                lines.append(f"{key.replace('_', ' ').title()}: {val}")
            self._stats_labels["secondary"].config(text=self._clip_lines(lines, max_lines=7))
        else:
            self._stats_labels["secondary"].config(text="Select secondary weapon")

    def _update_armor_passive(self) -> None:
        """Update armor passive and stats display based on selected armor."""
        armor_label = self._fields.get("armor")
        if not armor_label:
            self._armor_passive_label.config(text="")
            return
        
        selected = armor_label.get().strip()
        if not selected or selected == NONE_CHOICE:
            self._armor_passive_label.config(text="")
            return
        
        # Extract armor name from label format: "Weight: Armor Name (Passive)"
        # Parse: everything between first colon and opening paren
        armor_name = ""
        if ":" in selected and "(" in selected:
            armor_name = selected[selected.find(":")+1:selected.rfind("(")].strip()
        
        # Extract passive from label format
        passive_name = ""
        if "(" in selected and ")" in selected:
            passive_name = selected[selected.rfind("(") + 1 : selected.rfind(")")]
        
        # Build display with stats + passive
        display_parts: list[str] = []
        
        # Add armor stats if available
        if armor_name and self._armor_stats and armor_name in self._armor_stats:
            stats = self._armor_stats[armor_name]
            display_parts.append(
                f"Armor: {stats.get('armor', 'N/A')} | Speed: {stats.get('speed', 'N/A')} | Stamina: {stats.get('stamina', 'N/A')}"
            )
        
        # Add passive with description
        if passive_name:
            description = self._passive_descriptions.get(passive_name, "")
            if description:
                display_parts.append(f"{passive_name}: {description}")
            else:
                display_parts.append(passive_name)
        
        if display_parts:
            # Keep the row compact so lower controls remain visible.
            self._armor_passive_label.config(text=self._clip_lines(display_parts, max_lines=2))
        else:
            self._armor_passive_label.config(text="")

    def _on_save(self) -> None:
        if not self._name_entry:
            return
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showwarning("Name required", "Enter a name for this loadout.")
            return
        loadouts = load_saved_helldivers_loadouts()
        if name in loadouts:
            if not messagebox.askyesno("Overwrite?", f'Loadout "{name}" already exists. Replace it?'):
                return
        loadouts[name] = self._collect_payload()
        try:
            save_saved_helldivers_loadouts(loadouts)
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self._refresh_saved_names()
        self._saved_cb.set(name)
        self._name_entry.delete(0, tk.END)
        messagebox.showinfo("Saved", f'Saved "{name}" to\n{SAVED_HELLDIVERS_LOADOUTS}')

    def _on_load_selected(self) -> None:
        if not self._saved_cb:
            return
        name = self._saved_cb.get().strip()
        if not name:
            messagebox.showinfo("Nothing to load", "No saved loadouts yet.")
            return
        loadouts = load_saved_helldivers_loadouts()
        data = loadouts.get(name)
        if not data:
            self._refresh_saved_names()
            messagebox.showwarning("Missing", f'Could not find "{name}".')
            return
        self._apply_payload(data)

    def _on_delete_selected(self) -> None:
        if not self._saved_cb:
            return
        name = self._saved_cb.get().strip()
        if not name:
            return
        if not messagebox.askyesno("Delete?", f'Delete saved loadout "{name}"?'):
            return
        loadouts = load_saved_helldivers_loadouts()
        loadouts.pop(name, None)
        try:
            save_saved_helldivers_loadouts(loadouts)
        except OSError as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._refresh_saved_names()

    def _on_update_wiki(self) -> None:
        """Fetch and update data from Helldivers wiki."""
        success, message = update_helldivers_wiki_data()
        if success:
            messagebox.showinfo("Wiki Update", message)
            self._game = load_helldivers_game_data()
            # Refresh dropdown options with new data
            if self._game:
                strats = _with_none(_collect_stratagem_options(self._game))
                armors = _with_none(_collect_armor_options(self._game))
                if "stratagem_1" in self._fields:
                    self._fields["stratagem_1"]["values"] = strats
                if "armor" in self._fields:
                    self._fields["armor"]["values"] = armors
        else:
            messagebox.showerror("Wiki Update Failed", message)

    def _normalize_link_url(self, url: str) -> str:
        url = (url or "").strip()
        if not url:
            return ""
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = f"https://{url}"
        return url

    def _refresh_link_buttons(self) -> None:
        for i, btn in enumerate(self._link_buttons):
            if i < len(self._web_links):
                btn.configure(text=self._web_links[i].get("name") or f"Link {i + 1}")

    def _save_links(self) -> None:
        try:
            save_web_links(self._web_links)
        except OSError as e:
            messagebox.showerror("Save failed", f"Could not save web links:\n{e}")

    def _on_open_link(self, index: int) -> None:
        if index < 0 or index >= len(self._web_links):
            return
        item = self._web_links[index]
        url = self._normalize_link_url(item.get("url") or "")
        if not url:
            self._on_edit_single_link(index)
            return
        if not webbrowser.open_new_tab(url):
            messagebox.showerror("Open link failed", f"Could not open:\n{url}")

    def _on_edit_single_link(self, index: int) -> str:
        if index < 0 or index >= len(self._web_links):
            return "break"
        current = self._web_links[index]
        name = simpledialog.askstring(
            "Edit Link",
            f"Link name for Link {index + 1}:",
            initialvalue=current.get("name") or f"Link {index + 1}",
            parent=self,
        )
        if name is None:
            return "break"
        url = simpledialog.askstring(
            "Edit Link",
            f"Web URL for {name.strip() or f'Link {index + 1}'}:\n(Leave blank to clear)",
            initialvalue=current.get("url") or "",
            parent=self,
        )
        if url is None:
            return "break"
        self._web_links[index] = {
            "name": name.strip() or f"Link {index + 1}",
            "url": self._normalize_link_url(url),
        }
        self._refresh_link_buttons()
        self._save_links()
        return "break"

    def _on_edit_links(self) -> None:
        main = self.winfo_toplevel()
        editor = tk.Toplevel(main)
        editor.withdraw()
        editor.title("Edit Web Links")
        editor.transient(main)
        editor.resizable(False, False)
        # Keep this dialog above the app window (including overlay/topmost mode).
        desired_topmost = bool(main.attributes("-topmost"))
        editor.attributes("-topmost", desired_topmost)
        editor.grab_set()

        frame = ttk.Frame(editor, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        entries: list[tuple[tk.StringVar, tk.StringVar]] = []
        for i in range(3):
            item = self._web_links[i] if i < len(self._web_links) else {"name": f"Link {i + 1}", "url": ""}
            name_var = tk.StringVar(value=item.get("name") or f"Link {i + 1}")
            url_var = tk.StringVar(value=item.get("url") or "")
            entries.append((name_var, url_var))

            row = i * 2
            ttk.Label(frame, text=f"Link {i + 1} Name").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=(0, 2))
            ttk.Entry(frame, width=28, textvariable=name_var).grid(row=row, column=1, sticky="ew", pady=(0, 2))
            ttk.Label(frame, text=f"Link {i + 1} URL").grid(row=row + 1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
            ttk.Entry(frame, width=28, textvariable=url_var).grid(row=row + 1, column=1, sticky="ew", pady=(0, 8))

        frame.columnconfigure(1, weight=1)

        button_row = ttk.Frame(frame)
        button_row.grid(row=6, column=0, columnspan=2, sticky="e", pady=(2, 0))

        def _save_and_close() -> None:
            updated: list[dict[str, str]] = []
            for i, (name_var, url_var) in enumerate(entries):
                updated.append(
                    {
                        "name": name_var.get().strip() or f"Link {i + 1}",
                        "url": self._normalize_link_url(url_var.get()),
                    }
                )
            self._web_links = updated
            self._refresh_link_buttons()
            self._save_links()
            editor.destroy()

        ttk.Button(button_row, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_row, text="Save", command=_save_and_close).pack(side=tk.RIGHT, padx=(0, 8))
        editor.protocol("WM_DELETE_WINDOW", editor.destroy)
        main.update_idletasks()
        editor.update_idletasks()

        def _place_editor() -> None:
            w = max(editor.winfo_reqwidth(), editor.winfo_width())
            h = max(editor.winfo_reqheight(), editor.winfo_height())
            x = main.winfo_rootx() + max(0, (main.winfo_width() - w) // 2)
            y = main.winfo_rooty() + max(0, (main.winfo_height() - h) // 2)
            editor.geometry(f"{w}x{h}+{x}+{y}")

        _place_editor()
        editor.deiconify()
        editor.lift(main)
        # Re-apply placement after map to override Windows initial-placement behavior.
        editor.after(1, _place_editor)
        # Brief topmost pulse ensures the dialog is raised in front of the app.
        editor.attributes("-topmost", True)
        editor.after(1, lambda: editor.attributes("-topmost", desired_topmost))
        editor.focus_force()
        editor.wait_window(editor)

    def open_links_editor(self) -> None:
        """Public entry point for opening the web link editor from other tabs."""
        self._on_edit_links()

    def update_wiki_data(self) -> None:
        """Public entry point for wiki refresh from other tabs."""
        self._on_update_wiki()


class LoadoutApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Loadout tool")
        self.root.minsize(560, 620)
        self.root.geometry("680x860")
        self._center_main_window()
        self.root.attributes("-alpha", 1.0)
        self._is_visible = True
        self._overlay_enabled = False
        self._hotkey_listener = None
        self._hotkey_settings = dict(DEFAULT_HOTKEYS)
        self._hotkey_visibility_var = tk.StringVar()
        self._hotkey_overlay_var = tk.StringVar()
        self._hotkey_note_lbl: ttk.Label | None = None
        self._last_hotkey_times: dict[str, float] = {"num1": 0.0, "num2": 0.0}
        self._alpha_var = tk.DoubleVar(value=100.0)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._load_hotkey_settings()

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True)

        helldivers_tab = HelldiversPanel(nb)
        self._helldivers_panel = helldivers_tab
        nb.add(helldivers_tab, text="Helldivers loadout")

        settings_tab = ttk.Frame(nb, padding=10)
        nb.add(settings_tab, text="Settings")

        settings_fr = ttk.LabelFrame(settings_tab, text="General", padding=10)
        settings_fr.pack(fill=tk.X)

        wiki_row = ttk.Frame(settings_fr)
        wiki_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(wiki_row, text="Game data").pack(side=tk.LEFT)
        ttk.Button(wiki_row, text="Update from Wiki", command=self._helldivers_panel.update_wiki_data).pack(side=tk.LEFT, padx=(10, 0))

        presets_path_lbl = ttk.Label(
            settings_fr,
            text=f"Presets file: {SAVED_HELLDIVERS_LOADOUTS}",
            font=("Segoe UI", 8),
            foreground="#666",
        )
        presets_path_lbl.pack(anchor="w", pady=(0, 10))

        trans_row = ttk.Frame(settings_fr)
        trans_row.pack(fill=tk.X)
        ttk.Label(trans_row, text="Transparency").pack(side=tk.LEFT)
        alpha_slider = ttk.Scale(
            trans_row,
            from_=35,
            to=100,
            variable=self._alpha_var,
            command=self._on_alpha_changed,
        )
        alpha_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 10))
        self._alpha_value_lbl = ttk.Label(trans_row, text="100%")
        self._alpha_value_lbl.pack(side=tk.RIGHT)

        hotkey_fr = ttk.LabelFrame(settings_tab, text="Hotkeys", padding=10)
        hotkey_fr.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(hotkey_fr, text="Toggle visibility").grid(row=0, column=0, sticky="w")
        vis_entry = ttk.Entry(
            hotkey_fr,
            width=20,
            textvariable=self._hotkey_visibility_var,
            state="readonly",
        )
        vis_entry.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        ttk.Button(hotkey_fr, text="Bind", command=lambda: self._capture_hotkey_input(self._hotkey_visibility_var, "Toggle visibility")).grid(row=0, column=2, padx=(10, 0), pady=(0, 6), sticky="w")

        ttk.Label(hotkey_fr, text="Toggle overlay").grid(row=1, column=0, sticky="w")
        over_entry = ttk.Entry(
            hotkey_fr,
            width=20,
            textvariable=self._hotkey_overlay_var,
            state="readonly",
        )
        over_entry.grid(row=1, column=1, sticky="w", padx=(10, 0))
        ttk.Button(hotkey_fr, text="Bind", command=lambda: self._capture_hotkey_input(self._hotkey_overlay_var, "Toggle overlay")).grid(row=1, column=2, padx=(10, 0), sticky="w")

        ttk.Button(hotkey_fr, text="Apply Hotkeys", command=self._on_apply_hotkeys).grid(row=0, column=3, rowspan=2, padx=(12, 0))
        ttk.Button(hotkey_fr, text="Reset to Default", command=self._reset_hotkeys_to_default).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self._hotkey_note_lbl = ttk.Label(
            settings_tab,
            text="",
            font=("Segoe UI", 9),
            foreground="#666",
        )
        self._hotkey_note_lbl.pack(anchor="w", pady=(10, 0))

        self._sync_hotkey_dropdowns()
        self._refresh_hotkey_note()

        self._setup_hotkeys()

    def _load_hotkey_settings(self) -> None:
        settings = load_app_settings()
        raw = settings.get("hotkeys") if isinstance(settings, dict) else None
        if isinstance(raw, dict):
            for key in ("toggle_visibility", "toggle_overlay"):
                value = str(raw.get(key) or "")
                if _resolve_hotkey_choice(value) is not None:
                    self._hotkey_settings[key] = value

    def _save_hotkey_settings(self) -> None:
        settings = load_app_settings()
        if not isinstance(settings, dict):
            settings = {}
        settings["hotkeys"] = dict(self._hotkey_settings)
        save_app_settings(settings)

    def _sync_hotkey_dropdowns(self) -> None:
        vis_id = self._hotkey_settings.get("toggle_visibility", DEFAULT_HOTKEYS["toggle_visibility"])
        over_id = self._hotkey_settings.get("toggle_overlay", DEFAULT_HOTKEYS["toggle_overlay"])
        vis_spec = _resolve_hotkey_choice(vis_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_visibility"])
        over_spec = _resolve_hotkey_choice(over_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_overlay"])
        self._hotkey_visibility_var.set(str(vis_spec["label"]) if vis_spec else vis_id)
        self._hotkey_overlay_var.set(str(over_spec["label"]) if over_spec else over_id)

    def _refresh_hotkey_note(self) -> None:
        if not self._hotkey_note_lbl:
            return
        vis_id = self._hotkey_settings.get("toggle_visibility", DEFAULT_HOTKEYS["toggle_visibility"])
        over_id = self._hotkey_settings.get("toggle_overlay", DEFAULT_HOTKEYS["toggle_overlay"])
        vis_spec = _resolve_hotkey_choice(vis_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_visibility"])
        over_spec = _resolve_hotkey_choice(over_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_overlay"])
        vis_lbl = str(vis_spec["label"] if vis_spec else vis_id)
        over_lbl = str(over_spec["label"] if over_spec else over_id)
        self._hotkey_note_lbl.configure(text=f"Hotkeys: {vis_lbl} toggles visibility, {over_lbl} toggles overlay mode.")

    def _hotkey_spec_from_event(self, event) -> dict[str, object] | None:
        keysym = getattr(event, "keysym", "") or getattr(event, "char", "") or ""
        return _make_hotkey_spec(str(keysym))

    def _capture_hotkey_input(self, target_var: tk.StringVar, title: str) -> None:
        main = self.root
        dialog = tk.Toplevel(main)
        dialog.title(title)
        dialog.transient(main)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Press a key now.").pack(anchor="w")
        ttk.Label(frame, text="Esc cancels.", foreground="#666").pack(anchor="w", pady=(4, 0))

        status_lbl = ttk.Label(frame, text="Waiting for key press...", foreground="#666")
        status_lbl.pack(anchor="w", pady=(10, 0))

        def _close() -> None:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()

        def _on_key_press(event) -> str | None:
            if getattr(event, "keysym", "") == "Escape":
                _close()
                return "break"

            spec = self._hotkey_spec_from_event(event)
            if not spec:
                status_lbl.configure(text="That key is not supported. Try another one.", foreground="#a33")
                return "break"

            target_var.set(str(spec["label"]))
            _close()
            return "break"

        dialog.bind("<KeyPress>", _on_key_press)
        dialog.bind("<Escape>", lambda _event: (_close(), "break")[1])
        dialog.protocol("WM_DELETE_WINDOW", _close)
        dialog.update_idletasks()
        dialog.geometry(f"{dialog.winfo_reqwidth()}x{dialog.winfo_reqheight()}+{main.winfo_rootx() + 60}+{main.winfo_rooty() + 60}")
        dialog.focus_force()
        dialog.wait_window(dialog)

    def _on_apply_hotkeys(self) -> None:
        vis_spec = _resolve_hotkey_choice(self._hotkey_visibility_var.get())
        over_spec = _resolve_hotkey_choice(self._hotkey_overlay_var.get())
        if not vis_spec or not over_spec:
            messagebox.showwarning(
                "Invalid hotkeys",
                "Enter a supported key name like A, F1, Numpad 1, Left Arrow, Space, or End.",
            )
            self._sync_hotkey_dropdowns()
            return
        if str(vis_spec["id"]) == str(over_spec["id"]):
            messagebox.showwarning("Duplicate hotkeys", "Choose different keys for visibility and overlay.")
            return

        self._hotkey_settings["toggle_visibility"] = str(vis_spec["id"])
        self._hotkey_settings["toggle_overlay"] = str(over_spec["id"])
        self._save_hotkey_settings()
        self._refresh_hotkey_note()
        self._setup_hotkeys()
        messagebox.showinfo("Hotkeys updated", "New hotkeys are now active.")

    def _reset_hotkeys_to_default(self) -> None:
        self._hotkey_settings = dict(DEFAULT_HOTKEYS)
        self._sync_hotkey_dropdowns()
        self._save_hotkey_settings()
        self._refresh_hotkey_note()
        self._setup_hotkeys()
        messagebox.showinfo("Hotkeys reset", "Hotkeys restored to the default Numpad 1 and Numpad 2 settings.")

    def _center_main_window(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _setup_hotkeys(self) -> None:
        self._clear_tk_hotkey_bindings()
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

        if pynput_keyboard is not None:
            self._hotkey_listener = pynput_keyboard.Listener(on_press=self._on_global_key_press)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
            return

        vis_id = self._hotkey_settings.get("toggle_visibility", DEFAULT_HOTKEYS["toggle_visibility"])
        over_id = self._hotkey_settings.get("toggle_overlay", DEFAULT_HOTKEYS["toggle_overlay"])
        vis_spec = _resolve_hotkey_choice(vis_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_visibility"])
        over_spec = _resolve_hotkey_choice(over_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_overlay"])
        if not vis_spec or not over_spec:
            return
        vis_tk = str(vis_spec["tk"])
        over_tk = str(over_spec["tk"])
        self.root.bind_all(vis_tk, self._on_toggle_visibility)
        self.root.bind_all(over_tk, self._on_toggle_overlay)

    def _clear_tk_hotkey_bindings(self) -> None:
        for opt in HOTKEY_OPTIONS:
            self.root.unbind_all(str(opt["tk"]))

    def _on_global_key_press(self, key) -> None:
        if pynput_keyboard is None:
            return
        now = time.monotonic()

        vis_id = self._hotkey_settings.get("toggle_visibility", DEFAULT_HOTKEYS["toggle_visibility"])
        over_id = self._hotkey_settings.get("toggle_overlay", DEFAULT_HOTKEYS["toggle_overlay"])
        vis_spec = _resolve_hotkey_choice(vis_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_visibility"])
        over_spec = _resolve_hotkey_choice(over_id) or _make_hotkey_spec(DEFAULT_HOTKEYS["toggle_overlay"])
        if not vis_spec or not over_spec:
            return
        vis_vk = int(vis_spec["vk"])
        over_vk = int(over_spec["vk"])

        vk = getattr(key, "vk", None)
        num1_match = vk == vis_vk
        num2_match = vk == over_vk

        if num1_match:
            if now - self._last_hotkey_times["num1"] < 0.2:
                return
            self._last_hotkey_times["num1"] = now
            self.root.after(0, self._on_toggle_visibility)
        elif num2_match:
            if now - self._last_hotkey_times["num2"] < 0.2:
                return
            self._last_hotkey_times["num2"] = now
            self.root.after(0, self._on_toggle_overlay)

    def _on_alpha_changed(self, _value: str | None = None) -> None:
        pct = max(35.0, min(100.0, float(self._alpha_var.get())))
        self.root.attributes("-alpha", pct / 100.0)
        if hasattr(self, "_alpha_value_lbl"):
            self._alpha_value_lbl.configure(text=f"{int(round(pct))}%")

    def _on_toggle_visibility(self, _event: tk.Event | None = None) -> str:
        if self._is_visible:
            self.root.withdraw()
            self._is_visible = False
            return "break"

        self.root.deiconify()
        self._is_visible = True
        self.root.lift()
        self.root.attributes("-topmost", self._overlay_enabled)

        if sys.platform == "win32":
            _set_window_topmost(int(self.root.winfo_id()), self._overlay_enabled)
        return "break"

    def _on_toggle_overlay(self, _event: tk.Event | None = None) -> str:
        if not self._is_visible:
            self.root.deiconify()
            self._is_visible = True

        self._overlay_enabled = not self._overlay_enabled
        self.root.attributes("-topmost", self._overlay_enabled)
        self.root.lift()

        if sys.platform == "win32":
            _set_window_topmost(int(self.root.winfo_id()), self._overlay_enabled)
        return "break"

    def _on_switch_focus(self, _event: tk.Event | None = None) -> str:
        if sys.platform != "win32":
            return "break"

        user32 = ctypes.windll.user32
        active_hwnd = int(user32.GetForegroundWindow())
        tool_hwnd = int(self.root.winfo_id())

        if active_hwnd == tool_hwnd:
            hd_hwnd = _find_helldivers_hwnd()
            if hd_hwnd:
                _focus_window(hd_hwnd)
        else:
            if not self._is_visible:
                self.root.deiconify()
                self._is_visible = True
            self.root.lift()
            _focus_window(tool_hwnd)
        return "break"

    def _on_close(self) -> None:
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

def main() -> None:
    _set_windows_dpi_aware()
    ensure_data_dir()
    LoadoutApp().run()


if __name__ == "__main__":
    main()
