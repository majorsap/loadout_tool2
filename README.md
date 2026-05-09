# Helldivers 2 Loadout Tool

A desktop loadout manager for Helldivers 2 built with Tkinter.

It lets you:
- Pick a full build (primary, secondary, throwable, armor, stratagems, booster).
- View weapon stats from `weapon_stats.json`.
- View armor stats and passive descriptions from `armor_stats.json` + `helldivers_loadout_data.json`.
- Save, load, and delete named loadout presets.
- Update armor and stratagem data from the Helldivers wiki.
- Cache item icons locally.
- Toggle overlay/topmost mode and window visibility with hotkeys.

## Project Files

- `loadout_tool.py`: Main GUI application.
- `helldivers_loadout_data.json`: Core item lists and armor passive descriptions.
- `weapon_stats.json`: Weapon stat data used by the UI.
- `armor_stats.json`: Armor stat data used by the UI.
- `fetch_weapon_stats_v2.py`: Scrapes weapon pages and rewrites `weapon_stats.json`.
- `fetch_armor_stats.py`: Scrapes armor table data and rewrites `armor_stats.json`.
- `test_armor_integration.py`: Simple integration/data check script.

## Requirements

- Python 3.10+ (3.11 recommended).
- Windows is recommended for the full hotkey/window behavior.

Python packages:
- From `requirements.txt`:
  - `pynput>=1.7.6`
  - `pyautogui>=0.9.54`
  - `pydirectinput>=1.0.4`
- Also needed for the wiki weapon scraper:
  - `requests`

## Setup

From the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install requests
```

If your PowerShell execution policy blocks activation, run this in the current shell first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## Run the App

```powershell
python loadout_tool.py
```

## How To Use

1. Open the **Helldivers loadout** tab.
2. Choose items from dropdowns:
   - Primary
   - Secondary Weapon
   - Throwable
   - Armor
   - Stratagem 1-4
   - Booster
3. Review live stats panels:
   - **Weapon stats** updates when primary/secondary changes.
   - **Armor Passive** area shows armor/speed/stamina plus passive effect text.
4. Save presets:
   - Enter a name.
   - Click **Save loadout**.
5. Load/Delete presets:
   - Pick a saved name from **Saved**.
   - Click **Load** or **Delete**.
6. Update data from wiki:
   - Click **Update from Wiki**.
   - This updates armor + stratagem data in `helldivers_loadout_data.json`.
   - It also launches `fetch_weapon_stats_v2.py` in the background to refresh `weapon_stats.json`.
7. Optional link buttons:
   - Three link buttons can open your favorite web pages.
   - Click **Edit Links** to configure.
   - Right-click a link button for quick single-link edit.

## Hotkeys

Global hotkeys are enabled when `pynput` is installed:
- Numpad `1` or `End`: Toggle tool visibility.
- Numpad `2` or `Down Arrow`: Toggle overlay/topmost mode.

If `pynput` is not available, key binds are attached to the app window instead of global hooks.

## Data and Saved Files

The app stores user data in:

- `%USERPROFILE%\.loadout_tool\helldivers_saved_loadouts.json`
- `%USERPROFILE%\.loadout_tool\web_links.json`
- `%USERPROFILE%\.loadout_tool\icons\` (icon cache)

## Refresh Data Manually

You can refresh data files directly with:

```powershell
python fetch_armor_stats.py
python fetch_weapon_stats_v2.py
```

## Run the Integration Check

```powershell
python test_armor_integration.py
```

## Notes

- Wiki data can drift as pages change over time.
- If dropdown options seem outdated, run **Update from Wiki** or the manual fetch scripts.
- The app expects JSON files in this repository folder; run commands from here.
