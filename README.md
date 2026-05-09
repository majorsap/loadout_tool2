# Helldivers 2 Loadout Tool

A desktop loadout manager for Helldivers 2 built with Tkinter.

It lets you:
- Pick a full build (primary, secondary, throwable, armor, stratagems, booster).
- View weapon stats from `weapon_stats.json`.
- View armor stats and passive descriptions from `armor_stats.json` + `helldivers_loadout_data.json`.
- Save, load, and delete named loadout presets.
- Update armor and stratagem data from the Helldivers wiki.
- Cache item icons locally.
- Adjust window transparency from the Settings tab.
- Configure hotkeys for visibility and overlay toggles from the Settings tab.

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
6. Open the **Settings** tab to manage app behavior:
   - **Update from Wiki** refreshes armor + stratagem data in `helldivers_loadout_data.json`.
   - It also launches `fetch_weapon_stats_v2.py` in the background to refresh `weapon_stats.json`.
   - **Transparency** slider controls app opacity.
   - **Hotkeys** lets you choose keys for:
     - Toggle visibility
     - Toggle overlay mode
   - Click **Apply Hotkeys** to activate and save them.
7. Presets file path is shown in **Settings**.

## Settings Tab

The **Settings** tab currently includes:

- `Update from Wiki`
- `Transparency` slider
- Hotkey selection + `Apply Hotkeys`
- Presets save file location label

Link buttons and link editing controls are currently hidden from the UI.

## Hotkeys

Global hotkeys are enabled when `pynput` is installed.

- Configurable in Settings for:
   - Toggle tool visibility
   - Toggle overlay/topmost mode

Available key choices:

- Numpad `1`
- Numpad `2`
- `End`
- `Down Arrow`
- `F8`
- `F9`
- `F10`
- `F11`
- `F12`

If `pynput` is not available, the selected key binds are attached to the app window instead of global hooks.

## Data and Saved Files

The app stores user data in:

- `%USERPROFILE%\.loadout_tool\helldivers_saved_loadouts.json`
- `%USERPROFILE%\.loadout_tool\icons\` (icon cache)
- `%USERPROFILE%\.loadout_tool\app_settings.json` (settings, including hotkeys)

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
- If dropdown options seem outdated, run **Update from Wiki** from the Settings tab or run the manual fetch scripts.
- The app expects JSON files in this repository folder; run commands from here.

## Recent UI Changes

- Added a dedicated **Settings** tab.
- Moved **Update from Wiki** to the Settings tab.
- Moved **Transparency** control to the Settings tab.
- Added configurable hotkeys in Settings with persistent save support.
- Moved presets file path label to Settings.
- Hid link buttons and link editing controls from the active UI for now.
