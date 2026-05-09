#!/usr/bin/env python3
"""
Fetch armor stats from Helldivers 2 wiki and save to armor_stats.json.
Extracts armor value, speed, and stamina for all armor pieces.
"""

import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError
from html.parser import HTMLParser


def _fetch_armor_stats_from_wiki() -> dict:
    """
    Fetch armor stats from wiki. Returns dict:
    {
      "armor_name": {
        "armor": 50,
        "speed": 550,
        "stamina": 125,
        "passive": "Scout"
      },
      ...
    }
    """
    url = "https://helldivers.wiki.gg/api.php?action=parse&page=Armor&format=json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            html_content = data.get("parse", {}).get("text", {}).get("*", "")
    except (URLError, json.JSONDecodeError, KeyError) as e:
        print(f"Error fetching wiki: {e}")
        return {}

    if not html_content:
        print("No HTML content retrieved")
        return {}

    armor_stats = {}
    
    # Parse tables for Light, Medium, Heavy armor
    # Extract rows from <tr> tags containing armor data
    # Format: <td>icon</td><td>Name</td><td>Armor#</td><td>Speed#</td><td>Stamina#</td><td>Passive</td>
    
    # Find all table rows
    rows = re.findall(r'<tr>(.*?)</tr>', html_content, re.DOTALL)
    
    for row in rows:
        # Extract cell values
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 6:
            continue
        
        # cells[0] = icon, cells[1] = armor name link, cells[2] = armor value, 
        # cells[3] = speed, cells[4] = stamina, cells[5] = passive link
        
        # Extract armor name from link
        name_match = re.search(r'title="([^"]+)"', cells[1])
        if not name_match:
            continue
        armor_name = name_match.group(1)
        
        # Extract armor value (may have gray 0 prefix)
        armor_str = cells[2].replace('<span style="color:gray">0</span>', '0').strip()
        armor_val = re.search(r'\d+', armor_str)
        if not armor_val:
            continue
        
        # Extract speed
        speed_str = cells[3].replace('<span style="color:gray">0</span>', '0').strip()
        speed_val = re.search(r'\d+', speed_str)
        if not speed_val:
            continue
        
        # Extract stamina
        stamina_str = cells[4].replace('<span style="color:gray">0</span>', '0').strip()
        stamina_val = re.search(r'\d+', stamina_str)
        if not stamina_val:
            continue
        
        # Extract passive name from link
        passive_match = re.search(r'title="([^"]+)"', cells[5])
        passive = passive_match.group(1) if passive_match else ""
        
        armor_stats[armor_name] = {
            "armor": int(armor_val.group()),
            "speed": int(speed_val.group()),
            "stamina": int(stamina_val.group()),
            "passive": passive
        }
    
    return armor_stats


def save_armor_stats(output_path: str = "armor_stats.json") -> None:
    """Fetch armor stats and save to JSON file."""
    print(f"Fetching armor stats from wiki...")
    stats = _fetch_armor_stats_from_wiki()
    
    if not stats:
        print("Failed to fetch armor stats")
        return
    
    print(f"Found {len(stats)} armor pieces")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_path}")
    
    # Print summary
    for name, data in list(stats.items())[:5]:
        print(f"  {name}: armor={data['armor']}, speed={data['speed']}, stamina={data['stamina']}, passive={data['passive']}")


if __name__ == "__main__":
    save_armor_stats()
