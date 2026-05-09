#!/usr/bin/env python3
"""Test armor stats and passive integration."""

import json
from pathlib import Path

def test_armor_integration():
    """Test armor stats and passive data integration."""
    
    print("=" * 60)
    print("ARMOR STATS & PASSIVE INTEGRATION TEST")
    print("=" * 60)
    
    # Load data files
    armor_stats = json.loads(Path("armor_stats.json").read_text())
    hd_data = json.loads(Path("helldivers_loadout_data.json").read_text())
    
    passives = hd_data.get("armor", {}).get("passive_descriptions", {})
    
    print(f"\n✓ Loaded {len(armor_stats)} armor pieces")
    print(f"✓ Loaded {len(passives)} passive descriptions")
    
    # Test a few armor pieces
    test_armors = [
        "SC-37 Legionnaire",
        "SC-34 Infiltrator", 
        "FS-38 Eradicator",
        "CE-79 Polaris",
        "AP-2 The Quartermaster"
    ]
    
    print("\n" + "-" * 60)
    print("ARMOR STATS & PASSIVE LOOKUP TEST")
    print("-" * 60)
    
    for armor_name in test_armors:
        if armor_name in armor_stats:
            stats = armor_stats[armor_name]
            passive = stats.get("passive", "Unknown")
            armor_val = stats.get("armor", "?")
            speed = stats.get("speed", "?")
            stamina = stats.get("stamina", "?")
            
            description = passives.get(passive, "No description found")
            
            print(f"\n{armor_name}:")
            print(f"  Stats: Armor={armor_val} | Speed={speed} | Stamina={stamina}")
            print(f"  Passive: {passive}")
            print(f"  Effect: {description[:70]}...")
        else:
            print(f"\n✗ {armor_name} not found in armor_stats.json")
    
    print("\n" + "-" * 60)
    print("COVERAGE TEST")
    print("-" * 60)
    
    # Check all passives have descriptions
    armor_passives = set()
    for armor_name, stats in armor_stats.items():
        passive = stats.get("passive")
        if passive:
            armor_passives.add(passive)
    
    print(f"\nUnique passives in armor data: {len(armor_passives)}")
    print(f"Passive descriptions available: {len(passives)}")
    
    # Check coverage
    missing_descriptions = []
    for passive in armor_passives:
        if passive not in passives:
            missing_descriptions.append(passive)
    
    if missing_descriptions:
        print(f"\n⚠ Missing descriptions for: {missing_descriptions}")
    else:
        print("\n✓ All armor passives have descriptions!")
    
    # Verify all have required fields
    print("\n" + "-" * 60)
    print("DATA INTEGRITY CHECK")
    print("-" * 60)
    
    all_valid = True
    for armor_name, stats in armor_stats.items():
        required_fields = ["armor", "speed", "stamina", "passive"]
        for field in required_fields:
            if field not in stats:
                print(f"✗ {armor_name} missing field: {field}")
                all_valid = False
    
    if all_valid:
        print("\n✓ All armor pieces have complete data!")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_armor_integration()
