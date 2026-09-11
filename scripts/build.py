#!/usr/bin/env python3
"""Stage 4, BUILD. The opinionated layer: renaming, typing, resolution.

build/<date>/ -> data/
    <domain>/*.json   entities and relations, grouped by domain
    i18n/*.json       one file per language, keyed by GUID
    views/*.json      consultation and layout sheets, kept as grids
    reference/*.json  engine enumerations
    assets/           images named after their entity
    README.md         generated from the specs, one line per file
    manifest.json     provenance and counts

Two phases, as the dependency graph demands:
  A. load the registries and build the indexes
  B. project every entity, resolving against those indexes

At 62,000 rows everything fits in memory, so load order is not a problem to
solve: indexing before projecting is enough.

Usage: build.py [--build build/<date>] [--out data]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (CONV, DIM, OFF, YEL, Source, as_bool, as_code,  # noqa: E402
                  as_code_label, as_csv, as_float, as_int, as_lines, as_str,
                  clean, from_hex, is_rejected, iter_entity_files,
                  latest_build, write_json)
from mhwlib import slug, write_if_changed  # noqa: E402
from i18n import Translations  # noqa: E402
from specs import SPECS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def project(rows, mapping, require=None, guids=None, tr=None):
    """Apply {output field: (source column, converter)} to every row."""
    out = []
    for r in rows:
        rec = {}
        for field, (col, conv) in mapping.items():
            rec[field] = CONV[conv](clean(r.get(col)))
        if require and rec.get(require) is None:
            continue
        for field, col in (guids or {}).items():
            rec[field] = tr.norm(r.get(col)) if tr else None
        rec["_row"] = r["_row"]
        out.append(rec)
    return out


# --------------------------------------------------- custom: core registries

ICON_FAMILIES = {
    # output field -> (EnemyData raw column, IconDef id column, IconDef name
    #                  column, folder under data/assets/)
    "icon_large": ("Boss Icon Type Raw", "ID__7", "Name__7", "monster-icons-large"),
    "icon_small": ("Zako Icon Type Raw", "ID__6", "Name__6", "monster-icons-small"),
    "icon_map": ("Map Icon Type Raw", "ID__9", "Name__9", "map-icons"),
    "icon_endemic": ("Animal Icon Type Raw", "ID__5", "Name__5", "endemic-life-icons"),
}


def icon_lookup(src):
    """IconDef maps a raw icon type to a family name such as E0006 or MAP_0012.

    The workbook's own Icon columns are empty formulas, so this is the only
    route from a monster to its icon file.
    """
    ref = src.rows("IconDef")
    return {field: {r[id_col]: r[name_col] for r in ref
                    if r.get(id_col) and r.get(name_col)}
            for field, (_, id_col, name_col, _folder) in ICON_FAMILIES.items()}


def build_monsters(src, tr):
    """EM IDs is the registry. Monsters and EnemyData add detail for some of them.

    The Name column of Monsters packs up to three variants separated by
    newlines, so we explode it into `variants` and keep EM IDs.Name as the
    canonical name.
    """
    detail = {as_str(r.get("EM ID")): r for r in src.rows("Monsters") if r.get("EM ID")}
    text = {as_str(r.get("EM ID")): r for r in src.rows("EnemyData") if r.get("EM ID")}
    icons = icon_lookup(src)
    guid_cols = {
        "name_guid": "Enemy Name Raw", "description_guid": "Enemy Exp Raw",
        "boss_name_guid": "Enemy Boss Name Raw",
        "frenzy_name_guid": "Enemy Frenzy Name Raw",
        "tempered_name_guid": "Enemy Legendary Name Raw",
        "arch_tempered_name_guid": "Enemy Legendary King Name Raw",
        "features_guid": "Enemy Features Raw", "tips_guid": "Enemy Tips Raw",
        "first_capture_guid": "First Capture Raw", "memo_guid": "Memo Raw",
    }
    out = []
    for r in src.rows("EM IDs"):
        em = as_str(r.get("EM ID"))
        if not em or em == "INVALID":
            continue
        d, t = detail.get(em, {}), text.get(em, {})
        rec = {
            "em_id": em,
            "enum_value": as_int(r.get("Enum Value")),
            "fixed_id": as_str(r.get("Fixed ID")),
            "name": as_str(clean(r.get("Name"))),
            "variants": as_lines(clean(d.get("Name"))),
            "class": as_str(clean(d.get("Class"))),
            "species": as_str(clean(d.get("Species") or t.get("Species"))),
            "locales": as_csv(clean(d.get("Locale"))),
            "base_health": as_int(d.get("Base Health")),
            "base_size": as_float(d.get("Base Size")),
            "crown_small": as_float(d.get("Small Crown Size")),
            "crown_big": as_float(d.get("Big Crown Size")),
            "crown_king": as_float(d.get("King Crown Size")),
            "points": as_int(d.get("Points")),
            "reward": as_int(d.get("Reward")),
            "weakness": as_csv(clean(d.get("Weakness"))),
            "special_attacks": as_csv(clean(d.get("Special Attacks"))),
            "frenzied": as_bool(d.get("Frenzied")),
            "tempered": as_bool(d.get("Tempered")),
            "arch_tempered": as_bool(d.get("Arch Tempered")),
            "detailed": em in detail,
            "_row": r["_row"],
        }
        for field, col in guid_cols.items():
            rec[field] = tr.norm(t.get(col))
        for field, (raw_col, _, _, folder) in ICON_FAMILIES.items():
            name = icons[field].get(as_str(t.get(raw_col)))
            rec[field] = f"{folder}/{slug(name)}.png" if name and name != "INVALID" else None
        out.append(rec)
    return out


def build_monster_drops(src, item_by_id):
    out = []
    for r in src.rows("Monster Drops"):
        em = as_str(r.get("Monster ID"))
        if not em:
            continue
        out.append({
            "em_id": em, "monster": as_str(clean(r.get("Monster"))),
            "reward_type": as_str(clean(r.get("Reward Type"))),
            "reward_type_id": as_str(clean(r.get("Reward Type ID"))),
            "parts_index": as_int(r.get("Parts Index")),
            "rank": as_str(clean(r.get("Rank"))),
            **item_ref(item_by_id, as_int(r.get("Item ID"))),
            "quantity": as_int(r.get("Number")),
            "probability": as_float(r.get("Probability")),
            "_row": r["_row"],
        })
    return out


def build_monster_parts(src, em_by_name):
    out = []
    for r in src.rows("Monster Parts Array"):
        name = as_str(clean(r.get("Monster")))
        out.append({
            "em_id": em_by_name.get(name) or as_str(r.get("Monster ID")),
            "monster": name,
            "instance_guid": as_str(r.get("Instance GUID")),
            "part_type": as_str(clean(r.get("Parts Type"))),
            "vital": as_int(r.get("Vital")),
            "kinsect_extract": as_str(clean(r.get("Kinsect Extract"))),
            "meat_guid_normal": as_str(r.get("Meat GUID Normal")),
            "meat_guid_break": as_str(r.get("Meat GUID Break")),
            "_row": r["_row"],
        })
    return out


def build_monster_ailments(src, em_by_name):
    fields = ["Paralysis", "Poison", "Sleep", "KO", "Ride", "Parry", "Flash", "Sonic",
              "Sand Trap", "Block", "Blast", "Exhaust", "Pitfall Trap", "Shock Trap",
              "Ivy Trap", "Capture", "Lure Pod"]
    out = []
    for r in src.rows("Monster Ailment Resistances"):
        name = as_str(clean(r.get("Monster")))
        if not name:
            continue
        out.append({
            "em_id": em_by_name.get(name), "monster": name,
            "resistances": {slug(f).replace("-", "_"): as_float(r.get(f)) for f in fields},
            "_row": r["_row"],
        })
    return out


def build_monster_crowns(src, em_by_name):
    out = []
    for r in src.rows("Monster Crown Chances"):
        name = as_str(clean(r.get("Monster")))
        if not name:
            continue
        out.append({
            "em_id": em_by_name.get(name), "monster": name,
            "rank": as_str(clean(r.get("Rank"))),
            "mini_size": as_float(r.get("Mini Size (Table 1)")),
            "mini_chance": as_float(r.get("Mini Chance (Table 1)")),
            "large_size": as_float(r.get("Large Size (Table 1)")),
            "large_chance": as_float(r.get("Large Chance (Table 1)")),
            "king_size": as_float(r.get("King Size (Table 1)")),
            "king_chance": as_float(r.get("King Chance (Table 1)")),
            "_row": r["_row"],
        })
    return out


def build_turf_wars(src, em_by_name):
    out = []
    for r in src.rows("Turf War"):
        a, b = as_str(clean(r.get("Attacker"))), as_str(clean(r.get("Receiver")))
        if not a or not b:
            continue
        out.append({
            "attacker": a, "attacker_em_id": em_by_name.get(a),
            "receiver": b, "receiver_em_id": em_by_name.get(b),
            "attacker_damage_pct": as_float(r.get("Attacker Damage Per")),
            "receiver_damage_pct": as_float(r.get("Receiver Damage Per")),
            "type": as_str(clean(r.get("Type"))), "_row": r["_row"],
        })
    return out


def build_monster_quest_rewards(src):
    out = []
    for r in src.rows("EnemyQuestData"):
        em = as_str(clean(r.get("EM ID")))
        if not em or em == "INVALID":
            continue
        out.append({
            "em_id": em, "monster": as_str(clean(r.get("Monster"))),
            "guild_points": [as_int(r.get(c)) for c in
                             ("Guild Points", "Guild Points 2", "Guild Points 3")],
            "hr_points": [as_int(r.get(c)) for c in
                          ("HR Points", "HR Points 2", "HR Points 3")],
            "palico_xp": as_int(r.get("Palico xp")),
            "zenny": [as_int(r.get(c)) for c in ("Reward", "Reward 2", "Reward 3")],
            "_row": r["_row"],
        })
    return out


# --------------------------------------------------------- custom: weapons

SHARPNESS = ("Red", "Orange", "Yellow", "Green", "Blue", "White", "Purple")


# These eight sheets expose no resolved ID column, so their weapon id has to
# come from the raw block. That block carries one id column per weapon class,
# in the same order as the Weapon Recipes header (GS, SNS, DB, LS, Hammer, HH,
# Lance, GL), and each sheet holds its own id in its class's slot. Verified:
# with these columns the tree node tables resolve 100% for all 14 classes.
RAW_ID_COLUMN = {
    "LongSword": "Column 5",    # Great Sword
    "ShortSword": "Column 6",   # Sword & Shield
    "TwinSword": "Column 7",    # Dual Blades
    "Tachi": "Column 8",        # Long Sword
    "Hammer": "Column 9",
    "Whistle": "Column 10",     # Hunting Horn
    "Lance": "Column 11",
    "GunLance": "Column 12",
}


def build_weapons(src, contract, tr, skill_by_key):
    """The 14 sheets merged. The business key is (weapon_type, id)."""
    out = []
    for wtype, sheet in contract["weapon_sheets"].items():
        # the eight sheets without a readable ID also keep their text GUIDs in
        # unnamed columns, and list their skills as a resolved CSV pair
        raw_layout = sheet in RAW_ID_COLUMN
        ng, dg = (("Column 19", "Column 20") if raw_layout
                  else ("Name Raw", "Description Raw"))
        for r in src.rows(sheet):
            name = as_str(clean(r.get("Name")))
            if not name:
                continue
            sharp = {c.lower(): as_int(r.get(f"{c} Sharpness")) for c in SHARPNESS
                     if r.get(f"{c} Sharpness") is not None}
            sharp_h = {c.lower(): as_int(r.get(f"{c} Sharpness +1")) for c in SHARPNESS
                       if r.get(f"{c} Sharpness +1") is not None}
            out.append({
                "weapon_type": wtype, "sheet": sheet,
                "index": as_int(r.get("Index")),
                "id": (from_hex(r.get(RAW_ID_COLUMN[sheet]))
                       if sheet in RAW_ID_COLUMN else as_int(r.get("ID"))),
                "name": name, "description": as_str(clean(r.get("Description"))),
                "rarity": as_int(r.get("Rarity")), "price": as_int(r.get("Price")),
                "attack": as_int(r.get("Attack")), "defense": as_int(r.get("Defense")),
                "affinity": as_int(r.get("Affinity")),
                "element": as_str(clean(r.get("Attribute"))),
                "element_value": as_int(r.get("Attribute Value")),
                "slots": as_str(clean(r.get("Slots"))),
                "sharpness": sharp or None,
                "sharpness_handicraft": sharp_h or None,
                "skills": (
                    [{"skill_id": c["code"], "skill_name": c["label"],
                      "level": as_int(l)}
                     for c, l in ((as_code_label(n), l)
                                  for n, l in zip(as_csv(clean(r.get("Skills"))),
                                                  as_csv(clean(r.get("Skill Levels")))))
                     if c and c["code"] != "NONE"]
                    if raw_layout else
                    _skills_from_hex(r, skill_by_key, (0, 1, 2, 3),
                                     "Skill {n} Raw", "Skill {n} Lv Raw", True)
                ),
                "name_guid": tr.norm(r.get(ng)),
                "description_guid": tr.norm(r.get(dg)),
                "_row": r["_row"],
            })
    return out


def item_ref(item_by_id, idx):
    """The three fields every item reference carries. One place for the miss."""
    item = item_by_id.get(idx)
    return {"item_data_id": idx,
            "item_id": item["item_id"] if item else None,
            "item_name": item["name"] if item else None}


def skill_ref(skill_by_key, key):
    """The skill behind an engine key, or None for an empty or rejected slot."""
    skill = skill_by_key.get(key)
    if not skill or not skill["skill_id"] or skill["skill_id"] == "NONE":
        return None
    return None if is_rejected(skill["name"]) else skill


def _materials_from_hex(r, item_by_id, count=4, item_fmt="Item {n} Raw",
                        qty_fmt="Number {n}", qty_hex=False):
    mats = []
    for n in range(1, count + 1):
        idx = from_hex(r.get(item_fmt.format(n=n)))
        if idx is None:
            continue
        qty_raw = r.get(qty_fmt.format(n=n))
        mats.append(item_ref(item_by_id, idx) |
                    {"quantity": from_hex(qty_raw) if qty_hex else as_int(qty_raw)})
    return mats


def build_weapon_recipes(src, item_by_id):
    """The Item n columns are empty in the workbook, so rebuild them from hex."""
    out = []
    for r in src.rows("Weapon Recipes"):
        name = clean(r.get("Name"))
        mats = _materials_from_hex(r, item_by_id)
        out.append({
            "index": as_int(r.get("Index")),
            "recipe_number": as_int(r.get("Recipe Number")),
            "weapon_type": as_str(clean(r.get("Type"))),
            "weapon_id": as_int(r.get("ID")),
            "weapon_name": as_str(name),
            "upgrades_from": as_str(clean(r.get("Uprades From"))),
            "key_monster": as_str(clean(r.get("Key Monster"))),
            "key_story": as_str(clean(r.get("Key Story"))),
            "materials": mats, "orphan": name is None, "_row": r["_row"],
        })
    return out


def build_kinsect_recipes(src, item_by_id):
    out = []
    for r in src.rows("Kinsect Recipes"):
        kinsect = as_str(clean(r.get("Kinsect")))
        if not kinsect:
            continue
        mats = _materials_from_hex(r, item_by_id, item_fmt="Item {n} Raw",
                                   qty_fmt="Item {n} Quantity")
        out.append({
            "index": as_int(r.get("Index")), "kinsect": kinsect,
            "upgrades_from": as_str(clean(r.get("Previous Kinsect"))),
            "materials": mats, "_row": r["_row"],
        })
    return out


def build_weapon_tree_nodes(src, contract):
    """The weapon tree sheets are not only layout.

    Their left half is ASCII art, but their right half is a proper node table:
    weapon id, tier, row, and the GUIDs of the next and previous nodes. The
    lineage name (Ore Tree, Bone Tree) sits in the second column of the ASCII
    half, on the row the node's own `Row` points at. Neither the lineage nor
    the tier exists anywhere else in the workbook.
    """
    out = []
    for wtype in contract["weapon_sheets"]:
        sheet = f"{wtype} Weapon Tree"
        if not src.has(sheet):
            continue
        rows = src.rows(sheet)
        if not rows:
            continue
        header, body = rows[0], rows[1:]
        # locate the node table by header text, not by column index: the sheets
        # do not all have the same width
        col = {}
        for key, label in header.items():
            if key == "_row" or not label:
                continue
            col.setdefault(label.strip(), key)
        need = ("Weapon ID", "Column", "Row", "GUID", "Previous Data GUID")
        if any(c not in col for c in need):
            continue

        lineage_by_row = {}
        for i, r in enumerate(body):
            name = as_str(clean(r.get("_c1")))
            if name:
                lineage_by_row[i] = name

        by_guid = {}
        for r in body:
            g = as_str(r.get(col["GUID"]))
            if g:
                by_guid[g] = as_int(r.get(col["Weapon ID"]))

        for r in body:
            guid = as_str(r.get(col["GUID"]))
            wid = as_int(r.get(col["Weapon ID"]))
            if not guid or wid is None:
                continue
            row_index = as_int(r.get(col["Row"]))
            nexts = []
            for n in (1, 2, 3, 4):
                key = col.get(f"Next Data GUID {n}")
                target = by_guid.get(as_str(r.get(key))) if key else None
                if target is not None:
                    nexts.append(target)
            out.append({
                "weapon_type": wtype,
                "weapon_id": wid,
                "tier": as_int(r.get(col["Column"])),
                "row": row_index,
                "lineage": lineage_by_row.get(row_index),
                "next_weapon_ids": nexts,
                "previous_weapon_id": by_guid.get(as_str(r.get(col["Previous Data GUID"]))),
                "enabled": as_bool(r.get(col.get("Enable"))),
                "node_guid": guid,
                "_row": r["_row"],
            })
    return out


# ---------------------------------------------------------- custom: armour



def _items_csv(r, items_col, qty_col):
    codes = [as_code_label(c) for c in as_csv(clean(r.get(items_col)))]
    qty = [as_int(q) for q in as_csv(clean(r.get(qty_col)))]
    return [{"item_id": c["code"], "item_name": c["label"],
             "quantity": qty[i] if i < len(qty) else None}
            for i, c in enumerate(codes) if c]


def build_armor_recipes(src):
    out = []
    for r in src.rows("ArmorRecipeData"):
        series = as_str(r.get("Series"))
        if not series:
            continue
        out.append({
            "index": as_int(r.get("Index")), "recipe_id": as_str(r.get("Recipe ID")),
            "series": series, "part": as_str(clean(r.get("Part"))),
            "key_item": as_code(clean(r.get("Key Item"))),
            "key_monster": as_code(clean(r.get("Key Enemy"))),
            "key_story": as_str(clean(r.get("Key Story"))),
            "hunter_rank": as_int(r.get("Flag Hunter Rank")),
            "materials": _items_csv(r, "Items", "Quantities"), "_row": r["_row"],
        })
    return out


def build_armor_upgrade_recipes(src):
    out = []
    for r in src.rows("ArmorUpgradeRecipeData"):
        series = as_str(clean(r.get("Series")))
        if not series:
            continue
        out.append({"index": as_int(r.get("Index")), "series": series,
                    "materials": _items_csv(r, "Items", "Quantities"),
                    "_row": r["_row"]})
    return out


# ---------------------------------------------------------- custom: charms


def _skills_from_hex(r, skill_by_key, slots, key_fmt, lvl_fmt, lvl_hex=False):
    """Skill columns read #REF! across the workbook; rebuild from the hex keys."""
    out = []
    for n in slots:
        skill = skill_ref(skill_by_key, as_str(r.get(key_fmt.format(n=n))))
        if not skill:
            continue
        raw_lvl = r.get(lvl_fmt.format(n=n))
        out.append({"skill_id": skill["skill_id"], "skill_name": skill["name"],
                    "level": from_hex(raw_lvl) if lvl_hex else as_int(raw_lvl)})
    return out


def build_talismans(src, tr, skill_by_key):
    rows = project(src.rows("Talismans"), {
        "index": ("Index", "int"), "data_id": ("Data ID", "str"),
        "level": ("Level", "int"), "type": ("Type", "str"), "name": ("Name", "str"),
        "description": ("Description", "str"), "rarity": ("Rarity", "int"),
        "price": ("Price", "int"), "is_rng": ("Is RNG", "bool"),
    }, "name", {"name_guid": "Name Raw", "description_guid": "Description Raw"}, tr)
    by_row = {r["_row"]: r for r in src.rows("Talismans")}
    for rec in rows:
        rec["skills"] = _skills_from_hex(by_row[rec["_row"]], skill_by_key, (1, 2, 3),
                                         "Skill {n} Raw", "Skill {n} Lv Raw", True)
    return rows


def build_talisman_recipes(src, item_by_id):
    out = []
    for r in src.rows("Talisman Recipes"):
        name = as_str(clean(r.get("Name")))
        if not name:
            continue
        mats = _materials_from_hex(r, item_by_id, item_fmt="ItemId {n} Raw",
                                   qty_fmt="ItemNum {n} Raw", qty_hex=True)
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "type": as_str(clean(r.get("Type"))), "level": as_int(r.get("Level")),
            "name": name,
            "key_item_data_id": from_hex(r.get("KeyItemId Raw")),
            "key_monster": as_code(clean(r.get("Key Monster"))),
            "key_story": as_str(clean(r.get("Key Story"))),
            "materials": mats, "_row": r["_row"],
        })
    return out


# ---------------------------------------------------------- custom: Palico





def build_palico_recipes(src, item_by_id):
    """Item n columns are empty in the workbook; rebuilt from the hex columns."""
    out = []
    for r in src.rows("Palico Equipment Recipes"):
        series = as_str(clean(r.get("Series")))
        if not series:
            continue
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "series": series, "category": as_str(clean(r.get("Category"))),
            "key_monster": as_str(clean(r.get("Key Enemy"))),
            "key_story": as_str(clean(r.get("Key Story"))),
            "materials": _materials_from_hex(r, item_by_id,
                                             qty_fmt="Item {n} Quantity Raw",
                                             qty_hex=True),
            "_row": r["_row"],
        })
    return out


# --------------------------------------------------------- custom: economy

def build_item_recipes(src):
    out = []
    for r in src.rows("ItemRecipe"):
        result = as_code_label(clean(r.get("Result Item")))
        if not result:
            continue
        out.append({
            "index": as_int(r.get("Index")),
            "recipe_id": as_code(clean(r.get("Item Recipe ID"))),
            "result_item_id": result["code"], "result_item_name": result["label"],
            "result_quantity": as_int(r.get("Quantity")),
            "materials": [{"item_id": c["code"], "item_name": c["label"]}
                          for c in (as_code_label(x)
                                    for x in as_csv(clean(r.get("Items")))) if c],
            "auto_craft": as_bool(r.get("Enable Auto")), "_row": r["_row"],
        })
    return out


def build_item_shop(src):
    out = []
    for r in src.rows("ItemShopData"):
        item = as_code_label(clean(r.get("Item ID")))
        if not item:
            continue
        out.append({"index": as_int(r.get("Index")), "item_id": item["code"],
                    "item_name": item["label"],
                    "story_flag": as_str(clean(r.get("Story Flag"))),
                    "on_sale": as_bool(r.get("Is Sale Target")), "_row": r["_row"]})
    return out


def build_item_exchange(src):
    out = []
    for r in src.rows("ItemExchange"):
        pay, got = (as_code_label(clean(r.get("Pay Item ID"))),
                    as_code_label(clean(r.get("Reward Item ID"))))
        if not pay or not got:
            continue
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "pay_item_id": pay["code"], "pay_item_name": pay["label"],
            "pay_quantity": as_int(r.get("Pay Quantity")),
            "reward_item_id": got["code"], "reward_item_name": got["label"],
            "reward_quantity": as_int(r.get("Reward Quantity")), "_row": r["_row"],
        })
    return out


def build_support_ship(src):
    out = []
    for r in src.rows("SupportShipData"):
        item = as_code_label(clean(r.get("Item ID")))
        if not item or item["code"] == "INVALID":
            continue
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "category": as_str(clean(r.get("Category"))),
            "item_id": item["code"], "item_name": item["label"],
            "weapon_type": as_str(clean(r.get("Weapon Type"))),
            "stock": as_int(r.get("Stock Number")), "points": as_int(r.get("Points")),
            "rate": as_int(r.get("Rate")),
            "story_flag": as_str(clean(r.get("Story Flag"))), "_row": r["_row"],
        })
    return out


def build_fixed_items(src):
    out = []
    for r in src.rows("FixItems"):
        item = as_code_label(clean(r.get("Item ID")))
        if not item or item["code"] == "NONE":
            continue
        out.append({"index": as_int(r.get("Index")), "item_id": item["code"],
                    "item_name": item["label"],
                    "story_flag": as_str(clean(r.get("Story Flag"))), "_row": r["_row"]})
    return out


def build_auto_use_items(src):
    out = []
    for kind, sheet, trigger in (("health", "AutoUseHealthItemData", "Lack Health"),
                                 ("status", "AutoUseStatusItemData", "Condition")):
        for r in src.rows(sheet):
            item = as_code_label(clean(r.get("Item ID")))
            if item:
                out.append({"kind": kind, "trigger": as_str(clean(r.get(trigger))),
                            "item_id": item["code"], "item_name": item["label"],
                            "_row": r["_row"]})
    return out


def build_slinger_ammo(src, item_by_id):
    out = []
    for r in src.rows("Slinger Ammo"):
        enum = as_str(clean(r.get("Enum Name")))
        if not enum or enum == "NONE":
            continue
        out.append({"enum_name": enum, "enum_value": as_int(r.get("Enum Value")),
                    "fixed_id": as_str(clean(r.get("Fixed ID"))),
                    **item_ref(item_by_id, as_int(r.get("Item ID"))),
                    "_row": r["_row"]})
    return out


def build_npc_trades(src, item_by_id):
    """Requested / Rewarded Item columns are empty; rebuilt from the hex columns."""
    def resolve(raw):
        idx = from_hex(raw)
        return item_ref(item_by_id, idx) if idx is not None else None

    out = []
    for r in src.rows("NPC Trades"):
        requested = resolve(r.get("Request Raw"))
        if requested is None:
            continue
        rewards = []
        for n in (1, 2, 3):
            got = resolve(r.get(f"Reward {n} Raw"))
            if got is None:
                continue
            got["quantity"] = as_int(r.get(f"Rewarded Number {n}"))
            got["bonus"] = as_int(r.get(f"Bonus Number {n}"))
            rewards.append(got)
        requested["quantity"] = as_int(r.get("Requested Nummber"))
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "npc": as_str(clean(r.get("NPC"))), "locale": as_str(clean(r.get("Locale"))),
            "season": as_str(clean(r.get("Season"))), "requested": requested,
            "rewards": rewards, "max_count": as_int(r.get("Max Count")),
            "special": as_bool(r.get("Is Special")), "_row": r["_row"],
        })
    return out


def build_rng_talisman_skills(src, skill_by_key):
    """The Skill column reads #REF!; rebuilt from Skill Raw."""
    out = []
    for r in src.rows("RNG Talisman Skills"):
        key = as_str(r.get("Skill Raw"))
        skill = skill_ref(skill_by_key, key)
        out.append({
            "index": as_int(r.get("Index")), "skill_lot": as_str(clean(r.get("Skill Lot"))),
            "skill_key": key,
            "skill_id": skill["skill_id"] if skill else None,
            "skill_name": skill["name"] if skill else None,
            "skill_level": as_int(r.get("Skill Level")),
            "group": as_str(clean(r.get("Group"))),
            "talismans_with_group": as_int(r.get("Number of Talismans with Group")),
            "skills_in_group": as_int(r.get("Number of Skills in Group")),
            "chance": as_float(r.get("Chance to get on a Talisman")),
            "_row": r["_row"],
        })
    return out


def build_artian_skill_groups(src, skill_by_key):
    """Series Skill and Group Skill read #REF!; rebuilt from their Raw columns."""
    out = []
    for r in src.rows("Artian Skill Group Data"):
        series = skill_ref(skill_by_key, as_str(r.get("Skill 1 Raw")))
        group = skill_ref(skill_by_key, as_str(r.get("Skill 2 Raw")))
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "series_skill_id": series["skill_id"] if series else None,
            "series_skill_name": series["name"] if series else None,
            "group_skill_id": group["skill_id"] if group else None,
            "group_skill_name": group["name"] if group else None,
            "_row": r["_row"],
        })
    return out


def build_ingredients(src, item_by_id):
    """Item ID and Meal Skill read #REF!; the item is rebuilt from Item ID Raw."""
    out = []
    for r in src.rows("Other Ingredients"):
        out.append({
            "index": as_int(r.get("Index")),
            **item_ref(item_by_id, from_hex(r.get("Item ID Raw"))),
            "duration": as_int(r.get("Time")), "health": as_int(r.get("Health")),
            "stamina": as_int(r.get("Stamina")), "attack": as_int(r.get("Attack")),
            "defense": as_int(r.get("Defense")),
            "attribute_resistance": as_int(r.get("Attribute Resistance")),
            "meal_skill_key": as_str(r.get("Meal Skill Raw")),
            "random_table_1": as_str(clean(r.get("Random Table 1"))),
            "random_table_2": as_str(clean(r.get("Random Table 2"))),
            "is_main": as_bool(r.get("Is Main")), "_row": r["_row"],
        })
    return out


# ------------------------------------------------------ custom: progression

def build_missions(src):
    names = {}
    for r in src.rows("Mission Reward Tables"):
        mid, name = as_str(clean(r.get("Mission ID"))), as_str(clean(r.get("Mission Name")))
        if mid and name:
            names.setdefault(mid, name)
    out = []
    for r in src.rows("Mission IDs"):
        mid = as_str(clean(r.get("Mission ID")))
        if not mid or mid == "INVALID":
            continue
        out.append({"mission_id": mid, "enum_value": as_int(r.get("Enum Value")),
                    "fixed_id": as_int(r.get("Fixed ID")), "name": names.get(mid),
                    "_row": r["_row"]})
    return out



def build_mission_rewards(src, item_by_id):
    """The Item column reads #REF! on every row; rebuilt from Item Raw."""
    out = []
    for r in src.rows("Mission Common Reward Data"):
        idx = from_hex(r.get("Item Raw"))
        if idx is None:
            continue
        out.append({
            "index": as_int(r.get("Index")), "data_id": as_int(r.get("Data ID")),
            "table_id": as_int(r.get("Table ID")),
            "lot_type": as_str(clean(r.get("Common Lot Type"))),
            "additional_lot_type": as_str(clean(r.get("Additional Lot Type"))),
            **item_ref(item_by_id, idx),
            "quantity": as_int(r.get("Quantity")),
            "probability": as_float(r.get("Probability")), "_row": r["_row"],
        })
    return out


def build_medals(src, em_by_name, tr):
    out = []
    for r in src.rows("Medals"):
        name = as_str(clean(r.get("Name")))
        if not name:
            continue
        monster = as_str(clean(r.get("Monster")))
        out.append({
            "index": as_int(r.get("Index")), "id": as_str(clean(r.get("ID"))),
            "name": name, "description": as_str(clean(r.get("Description"))),
            "hidden": as_bool(r.get("Is Hidden")), "monster": monster,
            "em_id": em_by_name.get(monster),
            "name_guid": tr.norm(r.get("Name Raw")),
            "description_guid": tr.norm(r.get("Description Raw")),
            "_row": r["_row"],
        })
    return out




# ------------------------------------------------------------------- views

VIEWS = {
    "Contents": "The workbook's own table of contents, as laid out by its authors.",
    "Monster Hit Zone Viewer": "Formula-driven lookup UI: pick a monster, read its "
                               "hitzones. Kept as a grid; the underlying data is in "
                               "monsters/hitzones.json.",
    "Monster Drop Viewer": "Formula-driven lookup UI for drop tables. The underlying "
                           "data is in monsters/drops.json.",
}
TREE_SHEETS = [
    "Great Sword Weapon Tree", "Sword & Shield Weapon Tree", "Dual Blades Weapon Tree",
    "Long Sword Weapon Tree", "Hammer Weapon Tree", "Hunting Horn Weapon Tree",
    "Lance Weapon Tree", "Gunlance Weapon Tree", "Switch Axe Weapon Tree",
    "Charge Blade Weapon Tree", "Insect Glaive Weapon Tree", "Bow Weapon Tree",
    "Heavy Bowgun Weapon Tree", "Light Bowgun Weapon Tree",
]


def dump_view(src, sheet):
    """Views keep their grid shape: position carries the meaning, not a schema."""
    rows = src.rows(sheet)
    cols = src.inventory["sheets"][sheet]["columns"]
    grid = []
    for r in rows:
        grid.append([r.get(c) for c in cols])
    return {"sheet": sheet, "columns": cols, "rows": grid}


# --------------------------------------------------------------- reference

REFERENCE = {
    "AppDef": "Application-level enums.",
    "ArmorDef": "Engine enums for armour parts and slots.",
    "EnemyDef": "Engine enums for monsters.",
    "EquipDef": "Engine enums shared by all equipment.",
    "HunterDef": "Engine enums for the hunter.",
    "IconDef": "Icon families: ITEM_, EQUIP_, SKILL_, MAP_ and so on.",
    "ItemDef": "Engine enums for items: type, group, rarity.",
    "ItemRecipeDef": "Engine enums for item crafting.",
    "SupportShipDef": "Engine enums for the support ship.",
    "WeaponDef": "Engine enums shared by all weapons.",
    "Wp05Def": "Hunting horn specific enums.",
    "Wp07Def": "Gunlance specific enums.",
    "Wp07ShellLevel": "Gunlance shelling levels.",
    "ColorPreset": "Colour preset enum referenced by icons.",
    "QuestTimeRank": "Quest completion time ranks.",
    "StoryPackageFlag": "Story progression flags.",
    "MissionIDList": "Raw mission id list.",
    "Mission Manage IDs": "Mission management enum.",
    "Gimmick IDs": "Gimmick enum: id, value and fixed id.",
    "Area ID Enum": "Map area enum.",
    "Weapon Series Enum": "Weapon series enum.",
    "Decoration Enum": "Decoration enum.",
    "Talisman Type Enum": "Talisman type enum.",
    "EM IDs": "Monster id registry in its raw form; monsters/monsters.json is "
              "the usable version.",
}


def dump_reference(src, sheet):
    cols = [c for c in src.inventory["sheets"][sheet]["columns"]
            if not c.startswith("_c")]
    out = []
    for r in src.rows(sheet):
        rec = {c: clean(r.get(c)) for c in cols}
        if any(v is not None for k, v in rec.items() if k != "_row"):
            rec["_row"] = r["_row"]
            out.append(rec)
    return out


# ------------------------------------------------------------------- assets

ASSET_MAP = {
    "Medals": ("medals", "ID"),
    "Large Monster Icons": ("monster-icons-large", "ID"),
    "Small Monster Icons": ("monster-icons-small", "ID"),
    "Skill Icons": ("skill-icons", "ID"),
    "Status Icons": ("status-icons", "ID"),
    "Map Icons": ("map-icons", "ID"),
    "Endemic Life Icons": ("endemic-life-icons", "ID"),
    "Name Plates": ("name-plates", "Name"),
    "Hunter Profile Backgrounds": ("profile-backgrounds", "Name"),
}


def copy_assets(src: Source, out_dir: Path):
    """Name every image after its entity, never after its source file.

    xl/media/imageNNN.png names are reassigned on every export: out of 50
    Medals icons, 2 keep their name between two exports. The cell anchor, on
    the other hand, is stable.
    """
    dest_root = out_dir / "assets"
    written = kept = 0
    manifest = {}
    keyed = {}
    for sheet, (folder, keycol) in ASSET_MAP.items():
        rows = {r["_row"]: r for r in src.rows(sheet)}
        keyed[slug(sheet)] = (folder, keycol, rows)

    for rel, meta in src.assets.items():
        sheet_slug = rel.split("/", 1)[0]
        source_file = src.dir / "assets" / rel
        if not source_file.exists():
            continue
        if sheet_slug in keyed:
            folder, keycol, rows = keyed[sheet_slug]
            row = rows.get(meta["row"])
            raw_key = as_str(clean((row or {}).get(keycol)))
            key = slug(raw_key) if raw_key else "row%04d" % meta["row"]
            name = f"{key}.png"
        else:
            # sprite atlas: the grid position IS the information
            folder = "atlas/" + sheet_slug
            name = Path(rel).name

        target_dir = dest_root / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        if write_if_changed(target_dir / name, source_file.read_bytes(),
                            meta["pixel_hash"]):
            written += 1
        else:
            kept += 1
        manifest[f"{folder}/{name}"] = {"sheet": meta["sheet"], "row": meta["row"]}
    return manifest, written, kept


# --------------------------------------------------------------- the README

def write_readme(out: Path, entries, i18n_counts, view_names, ref_names, manifest):
    """data/README.md is generated from the specs so it can never go stale."""
    by_domain = {}
    for path, doc, count in entries:
        by_domain.setdefault(path.split("/")[0], []).append((path, doc, count))

    titles = {
        "core": "core, the registries everything else references",
        "monsters": "monsters",
        "weapons": "weapons",
        "armor": "armour",
        "charms": "decorations, talismans, pendants",
        "artian": "Artian weapons",
        "palico": "Palico gear",
        "world": "maps, gathering, wildlife",
        "economy": "shops, crafting, trades",
        "progression": "quests, rewards, guild card",
    }
    lines = [
        "# data",
        "",
        f"Generated from `{manifest['source_file']}` on {manifest['generated_at'][:10]}.",
        "Do not edit by hand: `scripts/build.py` overwrites this directory.",
        "",
        "## How to read a file",
        "",
        "Every record is a flat JSON object. Foreign keys use the game's own",
        "identifiers, never row ordinals:",
        "",
        "| Key | Points at |",
        "|---|---|",
        "| `em_id` | `monsters/monsters.json` |",
        "| `item_data_id` | `core/items.json` (field `data_id`) |",
        "| `item_id` | `core/items.json` (field `item_id`, the `ITEM_xxxx` form) |",
        "| `skill_id` | `core/skills.json` |",
        "| `series` | `armor/series.json` or `weapons/series.json` |",
        "| `mission_id` | `progression/missions.json` |",
        "| `name_guid`, `description_guid`, and the other text GUIDs "
        "| `i18n/<language>.json` |",
        "",
        "`instance_guid`, `meat_guid` and `link_parts_guid` are different: they",
        "identify a row inside the workbook's own arrays, not a translated string.",
        "They join the monster part tables to each other.",
        "",
        "`_row` is the row number in the source sheet, kept for tracing a value",
        "back to the workbook. It is not a key.",
        "",
        "## Translations",
        "",
        "Text fields carry the English string inline for convenience, plus a",
        "`*_guid` that resolves in every language. `i18n/<language>.json` maps",
        "GUID to text; `i18n/_index.json` says which sheet each GUID came from.",
        "",
        "| Language | Strings |",
        "|---|---:|",
    ]
    for code, n in i18n_counts.items():
        lines.append(f"| `{code}` | {n:,} |")
    lines += ["", "## Files", ""]

    for domain in titles:
        if domain not in by_domain:
            continue
        lines += [f"### {domain}/", "", f"_{titles[domain]}_", "",
                  "| File | Rows | Contents |", "|---|---:|---|"]
        for path, doc, count in sorted(by_domain[domain]):
            lines.append(f"| `{path}.json` | {count:,} | {doc} |")
        lines.append("")

    lines += [
        "### views/", "",
        "_Consultation and layout sheets. These are grids, not entities: the cell",
        "position carries the meaning. They map to SQL views, not tables._", "",
        "| File | Contents |", "|---|---|",
    ]
    for name, doc in sorted(view_names.items()):
        lines.append(f"| `views/{slug(name)}.json` | {doc} |")
    lines += ["", "### reference/", "",
              "_Engine enumerations. Useful for decoding a `Raw` column the build",
              "does not yet expose._", "", "| File | Contents |", "|---|---|"]
    for name, doc in sorted(ref_names.items()):
        lines.append(f"| `reference/{slug(name)}.json` | {doc} |")
    lines += [
        "", "### assets/", "",
        f"{manifest['asset_count']:,} PNG icons named after their entity, for example",
        "`assets/medals/aw000.png`. Icons that live in the workbook's sprite atlases",
        "have no identifier at all, so they keep their grid position under",
        "`assets/atlas/`. `assets.json` maps every file back to its source sheet",
        "and cell.", "",
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")


def audit_fields(src):
    """Every declared field must convert at least half its non-empty values.

    A column renamed or reshaped upstream otherwise turns into a column of
    nulls without anything failing, which is the same silent-loss failure mode
    the contract guards against on the join side.
    """
    dead = []
    for spec in SPECS:
        if not src.has(spec.sheet):
            continue
        rows = src.rows(spec.sheet)
        # Measure only the rows the spec keeps. A sheet whose broken rows are
        # dropped by `require` would otherwise drag every other column under
        # the threshold.
        if spec.require:
            col, conv = spec.fields[spec.require]
            rows = [r for r in rows if CONV[conv](clean(r.get(col))) is not None]
        for field, (col, conv) in spec.fields.items():
            values = [r.get(col) for r in rows]
            filled = [v for v in values if v not in (None, "")]
            if not filled:
                continue
            got = sum(1 for v in filled if CONV[conv](clean(v)) is not None)
            if got / len(filled) < 0.5:
                dead.append(f"{spec.out}.{field} <- {spec.sheet}.{col} "
                            f"({got}/{len(filled)}, e.g. {filled[0]!r})")
    return dead


def audit_output(entries, out):
    """A field that is null on every row of a produced file is a dead column."""
    dead = []
    for path, _, count in entries:
        if not count:
            continue
        rows = json.loads((out / f"{path}.json").read_text())
        for key in rows[0]:
            if key == "_row":
                continue
            if all(r.get(key) in (None, [], {}) for r in rows):
                dead.append(f"{path}.{key} is null on all {count} rows")
    return dead


# ---------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=None)
    ap.add_argument("--out", default="data")
    ap.add_argument("--skip-assets", action="store_true")
    args = ap.parse_args()

    build_dir = Path(args.build) if args.build else latest_build()
    if build_dir is None:
        print("no extract in build/", file=sys.stderr)
        return 1

    contract = yaml.safe_load((ROOT / "schema" / "contract.yaml").read_text())
    src = Source(build_dir)
    src.assets = json.loads((build_dir / "assets.json").read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Keep the previous build so scripts/diff_data.py has something to compare
    # against even before data/ is under version control.
    previous = out / "manifest.json"
    if previous.exists():
        old = json.loads(previous.read_text())
        if old.get("source_date") != src.inventory["source_date"]:
            snap = Path("build") / old["source_date"] / "data-snapshot"
            if snap.exists():
                shutil.rmtree(snap)
            for f in list(out.glob("*/*.json")) + [previous]:
                if f.parent.name == "assets":
                    continue
                target = snap / f.relative_to(out)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, target)
            print(f"snapshot  previous build kept in {snap}")

    print(f"extract   {build_dir}")
    print(f"output    {out}\n")

    # ---- phase A: the indexes
    tr = Translations(src)
    item_spec = next(s for s in SPECS if s.out == "core/items")
    items = project(src.rows(item_spec.sheet), item_spec.fields,
                    item_spec.require, item_spec.guids, tr)
    item_by_id = {i["data_id"]: i for i in items if i["data_id"] is not None}
    monsters = build_monsters(src, tr)
    em_by_name = {}
    for m in monsters:
        if m["name"]:
            em_by_name[m["name"]] = m["em_id"]
        for v in m["variants"]:
            em_by_name.setdefault(v, m["em_id"])
    skill_by_key = {}
    for r in src.rows("SkillCommonData"):
        key = as_str(r.get("Column 2"))
        if key:
            skill_by_key[key] = {"skill_id": as_code(clean(r.get("Skill ID"))),
                                 "name": as_str(clean(r.get("Name")))}
    print(f"index     {len(item_by_id)} items, {len(em_by_name)} monster names, "
          f"{len(monsters)} monsters, {len(skill_by_key)} skills, "
          f"{len(tr.entries)} translated strings")

    # ---- phase B: the projections
    weapon_recipes = build_weapon_recipes(src, item_by_id)
    materials = [m for r in weapon_recipes for m in r["materials"]]
    resolved = sum(1 for m in materials if m["item_id"])
    unresolved = len(materials) - resolved
    custom = {
        "monsters/monsters": ("The monster registry, with the detail sheets folded in. "
                              "`variants` holds the frenzied and tempered names.",
                              monsters),
        "monsters/drops": ("Every reward table: carves, target rewards, broken parts, "
                           "wounds, with quantity and probability.",
                           build_monster_drops(src, item_by_id)),
        "monsters/parts": ("Body parts per monster, with health and kinsect extract.",
                           build_monster_parts(src, em_by_name)),
        "monsters/ailment_resistances": ("Resistance value per monster and per status, "
                                         "trap or flash.",
                                         build_monster_ailments(src, em_by_name)),
        "monsters/crown_chances": ("Size thresholds and odds for mini, gold and king "
                                   "crowns.", build_monster_crowns(src, em_by_name)),
        "monsters/turf_wars": ("Turf war pairings and the damage each side takes.",
                               build_turf_wars(src, em_by_name)),
        "monsters/quest_rewards": ("Guild points, HR points, Palico xp and zenny per "
                                   "monster and quest tier.",
                                   build_monster_quest_rewards(src)),
        "weapons/weapons": ("All 1,200 weapons across the 14 classes, with sharpness "
                            "and skills. Key is (weapon_type, id). Eight of the "
                            "sheets hide that id in a raw hex column; it is "
                            "recovered here.",
                            build_weapons(src, contract, tr, skill_by_key)),
        "weapons/recipes": ("Weapon crafting and upgrade recipes. Note: `weapon_name` "
                            "and `upgrades_from` come from a workbook formula that is "
                            "misaligned for the eight classes without an ID column, so "
                            "use weapons/tree_nodes.json for the upgrade graph.",
                            weapon_recipes),
        "weapons/kinsect_recipes": ("Kinsect crafting and upgrade recipes.",
                                    build_kinsect_recipes(src, item_by_id)),
        "weapons/tree_nodes": ("Position of every weapon in its upgrade tree: "
                               "named lineage, tier, and the links to the next "
                               "and previous weapons.",
                               build_weapon_tree_nodes(src, contract)),
        "armor/recipes": ("Armour crafting recipes, keyed by (series, part).",
                          build_armor_recipes(src)),
        "armor/upgrade_recipes": ("Materials needed to upgrade an armour series.",
                                  build_armor_upgrade_recipes(src)),
        "charms/talismans": ("Fixed talismans and the skills they grant.",
                             build_talismans(src, tr, skill_by_key)),
        "charms/talisman_recipes": ("Talisman crafting recipes.",
                                    build_talisman_recipes(src, item_by_id)),
        "palico/recipes": ("Palico gear recipes, rebuilt from the hex columns.",
                           build_palico_recipes(src, item_by_id)),
        "economy/item_recipes": ("Item combining recipes.", build_item_recipes(src)),
        "economy/shop": ("What the provisions stockpile sells.", build_item_shop(src)),
        "economy/exchange": ("Ticket exchanges: pay one item, receive another.",
                             build_item_exchange(src)),
        "economy/support_ship": ("Support ship stock, points cost and restock rate.",
                                 build_support_ship(src)),
        "economy/fixed_items": ("Items granted permanently by story progress.",
                                build_fixed_items(src)),
        "economy/auto_use_items": ("Which item the quick-heal and quick-cure "
                                   "shortcuts pick.", build_auto_use_items(src)),
        "economy/slinger_ammo": ("Slinger ammo types mapped to their item.",
                                 build_slinger_ammo(src, item_by_id)),
        "economy/npc_trades": ("Field NPC trades: item requested against rewards, "
                               "rebuilt from the hex columns.",
                               build_npc_trades(src, item_by_id)),
        "progression/missions": ("Mission registry with names where the workbook "
                                 "supplies them.", build_missions(src)),
        "progression/mission_rewards": ("Contents of every quest reward table, with "
                                        "odds. Rebuilt from Item Raw.",
                                        build_mission_rewards(src, item_by_id)),
        "progression/medals": ("Medals and their unlock condition.",
                               build_medals(src, em_by_name, tr)),
        "charms/rng_talisman_skills": ("Per-skill odds of appearing on a randomly "
                                       "generated talisman. Skill rebuilt from hex.",
                                       build_rng_talisman_skills(src, skill_by_key)),
        "artian/skill_groups": ("Series and group skills an Artian weapon can roll. "
                                "Both rebuilt from hex.",
                                build_artian_skill_groups(src, skill_by_key)),
        "economy/ingredients": ("Meal ingredients and the buffs they contribute. Item "
                                "rebuilt from hex.", build_ingredients(src, item_by_id)),
    }

    entries = []

    def emit(path, doc, rows):
        write_json(out / f"{path}.json", rows)
        entries.append((path, doc, len(rows)))

    prebuilt = {"core/items": items}
    for spec in SPECS:
        if not src.has(spec.sheet):
            print(f"  ! sheet missing, skipped: {spec.sheet}")
            continue
        emit(spec.out, spec.doc, prebuilt.get(spec.out) or
             project(src.rows(spec.sheet), spec.fields, spec.require, spec.guids, tr))
    for path, (doc, rows) in custom.items():
        emit(path, doc, rows)

    # views and reference
    views_dir = out / "views"
    views_dir.mkdir(parents=True, exist_ok=True)
    view_docs = dict(VIEWS)
    for sheet in TREE_SHEETS:
        view_docs[sheet] = ("Layout grid of the in-game weapon tree. The usable "
                            "relation is `upgrades_from` in weapons/recipes.json.")
    view_count = 0
    for sheet in view_docs:
        if not src.has(sheet):
            continue
        write_json(views_dir / f"{slug(sheet)}.json", dump_view(src, sheet))
        view_count += 1

    ref_dir = out / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_count = 0
    for sheet in REFERENCE:
        if not src.has(sheet):
            continue
        write_json(ref_dir / f"{slug(sheet)}.json", dump_reference(src, sheet))
        ref_count += 1

    i18n_counts = tr.write(out / "i18n")

    assets_manifest, written, kept = ({}, 0, 0)
    if not args.skip_assets:
        assets_manifest, written, kept = copy_assets(src, out)
        write_json(out / "assets.json", assets_manifest)

    manifest = {
        "source_file": src.inventory["source_file"],
        "source_date": src.inventory["source_date"],
        "schema_version": contract["schema_version"],
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sheet_count": src.inventory["sheet_count"],
        "row_total": src.inventory["row_total"],
        "entity_files": len(entries),
        "view_files": view_count,
        "reference_files": ref_count,
        "languages": i18n_counts,
        "translated_guids": len(tr.entries),
        "counts": {path: n for path, _, n in entries},
        "asset_count": len(assets_manifest),
        "weapon_recipe_materials": {"resolved": resolved, "unresolved": unresolved},
    }
    write_json(out / "manifest.json", manifest)
    write_readme(out, entries, i18n_counts, view_docs, REFERENCE, manifest)

    by_domain = {}
    for path, _, n in entries:
        d = path.split("/")[0]
        by_domain[d] = by_domain.get(d, 0) + n
    for d, n in sorted(by_domain.items()):
        files = sum(1 for p, _, _ in entries if p.startswith(d + "/"))
        print(f"  {d:14s} {files:3d} files {n:7d} rows")
    print(f"  {'views':14s} {view_count:3d} files")
    print(f"  {'reference':14s} {ref_count:3d} files")
    print(f"  {'i18n':14s} {len(i18n_counts):3d} languages {len(tr.entries):7d} guids")
    if not args.skip_assets:
        print(f"  {'assets':14s} {len(assets_manifest):3d} files "
              f"({written} written, {kept} unchanged)")
    print(f"\nweapon recipe materials rebuilt from hex: "
          f"{resolved} resolved, {unresolved} unresolved")

    dead = audit_fields(src) + audit_output(entries, out)
    if dead:
        print(f"\n\033[33m{len(dead)} field mapping(s) convert nothing:\033[0m")
        for line in dead:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
