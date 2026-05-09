"""
Standalone script: scrape weapon stats from helldivers.wiki.gg and write
weapon_stats.json next to this file.

Run:  python fetch_weapon_stats_v2.py

Output weapon_stats.json structure:
{
  "primary":   { "<name>": { "armor_penetration": "Light", "damage": "90 Ballistic", ... } },
  "secondary": { "<name>": { ... } },
  "throwable": { "<name>": { ... } }
}

Individual weapon pages use druid-infobox divs with class druid-data-<field>.
Categorisation is driven by helldivers_loadout_data.json.
"""

from __future__ import annotations

import json
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_PATH   = SCRIPT_DIR / "weapon_stats.json"
WIKI_API   = "https://helldivers.wiki.gg/api.php"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json,text/html,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://helldivers.wiki.gg/",
})

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _fetch_page_html(page: str) -> str:
    """Return rendered HTML for a MediaWiki page title."""
    resp = SESSION.get(
        WIKI_API,
        params={"action": "parse", "page": page, "prop": "text", "format": "json"},
        timeout=25,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["parse"]["text"]
    return text["*"] if isinstance(text, dict) else str(text)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _strip_html(fragment: str) -> str:
    """Remove all tags and decode HTML entities, collapsing whitespace."""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


# ---------------------------------------------------------------------------
# Individual weapon page parsing
# ---------------------------------------------------------------------------
# Pages use a druid-infobox with divs like:
#   <div class="druid-data druid-data-penetration druid-data-nonempty">Light</div>
# We extract every druid-data-<field> div that is non-empty.

_DRUID_RE = re.compile(
    r'class="druid-data\s+druid-data-([a-z_0-9]+)\s+druid-data-nonempty[^"]*"[^>]*>'
    r'\s*(.*?)\s*</div>',
    re.DOTALL | re.IGNORECASE,
)

# Map druid field names → output key names
_FIELD_MAP: dict[str, str] = {
    "damage":      "damage",
    "penetration": "armor_penetration",
    "fire_rate":   "fire_rate",
    "dps":         "dps",
    "capacity":    "capacity",
    "spare_mags":  "spare_mags",
    "ergonomics":  "ergonomics",
    "recoil":      "recoil",
    "stagger":     "stagger",
    "firing_modes":"firing_modes",
    "weapon_traits":"traits",
    "radius":      "radius",
    "inner_radius":"inner_radius",
    "outer_radius":"outer_radius",
    "fuse_time":   "fuse_time",
    "arc_duration":"arc_duration",
    "speed":       "speed",
}


def _parse_weapon_page(html: str) -> dict[str, object]:
    """Extract stats from a weapon's druid-infobox divs."""
    stats: dict[str, object] = {}
    for field, content_html in _DRUID_RE.findall(html):
        key = _FIELD_MAP.get(field)
        if key is None:
            continue
        value = _strip_html(content_html)
        if not value:
            continue
        # Try to coerce numeric-only values (e.g. DPS, capacity, ergonomics)
        # Keep unit-bearing strings as strings ("640 rpm", "90 Ballistic")
        pure_num = re.fullmatch(r"-?\d+(\.\d+)?", value)
        if pure_num:
            stats[key] = float(value) if "." in value else int(value)
        else:
            stats[key] = value
    return stats


# ---------------------------------------------------------------------------
# Categorisation from existing JSON
# ---------------------------------------------------------------------------

def _load_existing_data() -> dict:
    path = SCRIPT_DIR / "helldivers_loadout_data.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _build_category_map(existing: dict) -> dict[str, str]:
    """Return {weapon_name: category} from helldivers_loadout_data.json."""
    cat_map: dict[str, str] = {}
    sec = existing.get("secondary") or {}
    for n in existing.get("primary") or []:
        cat_map[n] = "primary"
    for n in (sec.get("pistols") or []) + (sec.get("melee") or []):
        cat_map[n] = "secondary"
    for n in existing.get("throwable") or []:
        cat_map[n] = "throwable"
    return cat_map


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    existing = _load_existing_data()
    if not existing:
        sys.exit("Could not load helldivers_loadout_data.json — run from the project folder.")

    cat_map = _build_category_map(existing)
    all_names = list(cat_map.keys())
    total = len(all_names)
    print(f"Weapons to fetch: {total}")

    result: dict[str, dict[str, dict[str, object]]] = {
        "primary": {},
        "secondary": {},
        "throwable": {},
    }

    for i, name in enumerate(all_names, 1):
        cat = cat_map[name]
        wiki_page = name.replace(" ", "_")
        print(f"  [{i}/{total}] {name}", end="", flush=True)
        try:
            html = _fetch_page_html(wiki_page)
            stats = _parse_weapon_page(html)
        except Exception as exc:
            print(f"  => ERROR: {exc}")
            stats = {}

        if stats:
            print(f"  => {list(stats.keys())}")
        else:
            print("  => (no stats found)")
        result[cat][name] = stats
        time.sleep(0.4)

    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {k: len(v) for k, v in result.items()}
    print(f"\nDone. Written to {OUT_PATH}")
    print(f"  primary: {counts['primary']}, secondary: {counts['secondary']}, throwable: {counts['throwable']}")


if __name__ == "__main__":
    main()
