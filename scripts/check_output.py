#!/usr/bin/env python3
"""Stage 5, CHECK. Referential integrity of data/, not of the workbook.

validate.py checks the source. This checks the product: that the identifiers
the build writes actually resolve inside data/. Those are two different
failures. A join can be perfect in the workbook and still be broken here by a
normalisation mistake, which is exactly how `HunterSkill_000 (Attack Boost)`
and `HunterSkill_000` once ended up in two files meant to join.

Exit code 0 when everything resolves, 1 otherwise.

Usage: check_output.py [--data data]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Report, iter_entity_files  # noqa: E402


# file -> field expected to be unique and non-null
PRIMARY_KEYS = {
    "core/items": "data_id",
    "core/skills": "skill_id",
    "core/species": "name",
    "core/locales": "name",
    "core/weapon_types": "name",
    "monsters/monsters": "em_id",
    "armor/series": "series",
    "palico/series": "name",
    "progression/missions": "mission_id",
    "world/gimmicks": "gimmick_id",
}

# (child file, field) -> (parent file, field). Nested fields use "a.b".
FOREIGN_KEYS = {
    ("monsters/drops", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/hitzones", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/parts", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/part_breaks", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/weak_points", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/scar_points", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/multi_parts", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/part_params", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/ailment_resistances", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/crown_chances", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/quest_rewards", "em_id"): ("monsters/monsters", "em_id"),
    ("monsters/turf_wars", "attacker_em_id"): ("monsters/monsters", "em_id"),
    ("monsters/turf_wars", "receiver_em_id"): ("monsters/monsters", "em_id"),
    ("progression/medals", "em_id"): ("monsters/monsters", "em_id"),

    ("monsters/drops", "item_data_id"): ("core/items", "data_id"),
    ("economy/slinger_ammo", "item_data_id"): ("core/items", "data_id"),
    ("economy/ingredients", "item_data_id"): ("core/items", "data_id"),
    ("weapons/recipes", "materials.item_data_id"): ("core/items", "data_id"),
    ("weapons/kinsect_recipes", "materials.item_data_id"): ("core/items", "data_id"),
    ("palico/recipes", "materials.item_data_id"): ("core/items", "data_id"),
    ("charms/talisman_recipes", "materials.item_data_id"): ("core/items", "data_id"),
    ("progression/mission_rewards", "item_data_id"): ("core/items", "data_id"),
    ("economy/npc_trades", "requested.item_data_id"): ("core/items", "data_id"),
    ("economy/npc_trades", "rewards.item_data_id"): ("core/items", "data_id"),

    ("economy/shop", "item_id"): ("core/items", "item_id"),
    ("economy/fixed_items", "item_id"): ("core/items", "item_id"),
    ("economy/exchange", "pay_item_id"): ("core/items", "item_id"),
    ("economy/exchange", "reward_item_id"): ("core/items", "item_id"),
    ("economy/support_ship", "item_id"): ("core/items", "item_id"),
    ("economy/item_recipes", "result_item_id"): ("core/items", "item_id"),
    ("economy/item_recipes", "materials.item_id"): ("core/items", "item_id"),
    ("economy/auto_use_items", "item_id"): ("core/items", "item_id"),
    ("armor/recipes", "materials.item_id"): ("core/items", "item_id"),
    ("armor/upgrade_recipes", "materials.item_id"): ("core/items", "item_id"),

    ("core/skill_levels", "skill_id"): ("core/skills", "skill_id"),
    ("charms/rng_talisman_skills", "skill_id"): ("core/skills", "skill_id"),
    ("artian/skill_groups", "series_skill_id"): ("core/skills", "skill_id"),
    ("artian/skill_groups", "group_skill_id"): ("core/skills", "skill_id"),
    ("charms/talismans", "skills.skill_id"): ("core/skills", "skill_id"),
    ("weapons/weapons", "skills.skill_id"): ("core/skills", "skill_id"),

    ("armor/armor", "series"): ("armor/series", "series"),
    ("armor/recipes", "series"): ("armor/series", "series"),
    ("armor/upgrade_recipes", "series"): ("armor/series", "series"),
    ("armor/layered", "series"): ("armor/series", "series"),
    ("palico/armor", "series"): ("palico/series", "name"),
    ("palico/weapons", "series"): ("palico/series", "name"),
    ("palico/layered_armor", "series"): ("palico/series", "name"),
    ("palico/recipes", "series"): ("palico/series", "name"),

    # the monster part tables chain to each other through engine instance guids
    ("monsters/weak_points", "meat_guid"): ("monsters/hitzones", "instance_guid"),
    ("monsters/scar_points", "meat_guid"): ("monsters/hitzones", "instance_guid"),
    ("monsters/weak_points", "link_parts_guid"): ("monsters/parts", "instance_guid"),
    ("monsters/scar_points", "link_parts_guid"): ("monsters/parts", "instance_guid"),
    ("monsters/multi_parts", "link_parts_guid"): ("monsters/parts", "instance_guid"),

    ("progression/mission_reward_tables", "mission_id"): ("progression/missions",
                                                          "mission_id"),
    ("world/gimmick_texts", "gimmick_id"): ("world/gimmicks", "gimmick_id"),
}

# Fields ending in _guid that identify a row inside the workbook rather than a
# translated string. They are not expected to resolve in i18n/.
STRUCTURAL_GUIDS = {
    "instance_guid", "meat_guid", "meat_guid_normal", "meat_guid_break",
    "link_parts_guid", "target_data_guid", "node_guid",
}

# Composite foreign keys: (child, (fields...)) -> (parent, (fields...)).
# weapons has no single unique column, its key is the pair.
COMPOSITE_KEYS = {
    ("weapons/tree_nodes", ("weapon_type", "weapon_id")):
        ("weapons/weapons", ("weapon_type", "id")),
    ("weapons/tree_nodes", ("weapon_type", "previous_weapon_id")):
        ("weapons/weapons", ("weapon_type", "id")),
}

# Known dangling references in the source, with the reason. Anything not listed
# here that fails is a real regression.
ACCEPTED = {
    ("economy/slinger_ammo", "item_data_id"): (
        1, "the SLEEP entry points at item 185, absent from ItemData"),
    ("armor/armor", "series"): (
        1, "ID_000 is a placeholder series with no definition"),
    ("world/gimmick_texts", "gimmick_id"): (
        None, "the text sheet covers gimmick ids the data sheet does not list"),
    ("monsters/weak_points", "link_parts_guid"): (
        1, "one weak point links to a part row the workbook does not carry"),
    ("monsters/multi_parts", "link_parts_guid"): (
        2, "two multi-part rows link to part rows the workbook does not carry"),
}


class Data:
    """Every entity file, each read once."""

    def __init__(self, root: Path):
        self.root = root
        self._cache = {}

    def get(self, path):
        if path not in self._cache:
            f = self.root / f"{path}.json"
            self._cache[path] = json.loads(f.read_text()) if f.exists() else None
        return self._cache[path]

    def all(self):
        for path, _ in iter_entity_files(self.root):
            rows = self.get(path)
            if isinstance(rows, list):
                yield path, rows


def pluck(rows, field):
    """Collect a field's values, walking one level of nested list or object."""
    head, _, tail = field.partition(".")
    out = []
    for r in rows:
        v = r.get(head)
        if v is None:
            continue
        if not tail:
            out.append(v)
        elif isinstance(v, list):
            out += [x.get(tail) for x in v if isinstance(x, dict)
                    and x.get(tail) is not None]
        elif isinstance(v, dict) and v.get(tail) is not None:
            out.append(v[tail])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    data = Path(args.data)
    if not (data / "manifest.json").exists():
        print("no data/manifest.json, run build.py first", file=sys.stderr)
        return 1

    manifest = json.loads((data / "manifest.json").read_text())
    store = Data(data)
    print(f"data      {data}")
    print(f"source    {manifest['source_file']}")
    print(f"files     {manifest['entity_files']} entities, "
          f"{manifest['view_files']} views, {manifest['reference_files']} reference\n")

    rep = Report()
    ok = 0

    # --- primary keys
    for path, key in PRIMARY_KEYS.items():
        rows = store.get(path)
        if rows is None:
            rep.error(f"missing file: {path}.json")
            continue
        values = [r.get(key) for r in rows]
        if any(v is None for v in values):
            rep.error(f"{path}.{key} has null values")
        seen, dupes = set(), set()
        for v in values:
            (dupes if v in seen else seen).add(v)
        if dupes:
            rep.error(f"{path}.{key} is not unique: {sorted(dupes)[:3]}")
        else:
            ok += 1

    # --- foreign keys
    for (child, field), (parent, pfield) in FOREIGN_KEYS.items():
        crows, prows = store.get(child), store.get(parent)
        if crows is None or prows is None:
            rep.error(f"missing file for {child}.{field} -> {parent}.{pfield}")
            continue
        target = {r.get(pfield) for r in prows}
        values = pluck(crows, field)
        missing = sorted({v for v in values if v not in target}, key=str)
        if not missing:
            ok += 1
            continue
        accepted = ACCEPTED.get((child, field))
        label = f"{child}.{field} -> {parent}.{pfield}: {len(missing)} orphan(s) {missing[:3]}"
        if accepted and (accepted[0] is None or len(missing) <= accepted[0]):
            rep.warn(f"{label}  [known: {accepted[1]}]")
        else:
            rep.error(label)

    # --- composite foreign keys
    for (child, cfields), (parent, pfields) in COMPOSITE_KEYS.items():
        crows, prows = store.get(child), store.get(parent)
        if crows is None or prows is None:
            rep.error(f"missing file for {child}{cfields} -> {parent}{pfields}")
            continue
        target = {tuple(r.get(f) for f in pfields) for r in prows}
        pairs = [tuple(r.get(f) for f in cfields) for r in crows
                 if all(r.get(f) is not None for f in cfields)]
        missing = sorted({p for p in pairs if p not in target}, key=str)
        if missing:
            rep.error(f"{child}{cfields} -> {parent}{pfields}: "
                          f"{len(missing)} orphan(s) {missing[:3]}")
        else:
            ok += 1

    # weapons is keyed by the pair, so check that pair is unique
    wrows = store.get("weapons/weapons")
    if wrows:
        pairs = [(r.get("weapon_type"), r.get("id")) for r in wrows]
        dupes = len(pairs) - len(set(pairs))
        if dupes:
            rep.error(f"weapons/weapons (weapon_type, id) is not unique: "
                          f"{dupes} duplicate pair(s)")
        elif any(p[1] is None for p in pairs):
            rep.error("weapons/weapons.id has null values")
        else:
            ok += 1

    # --- translation guids
    english = set(json.loads((data / "i18n" / "english.json").read_text()))
    index = set(json.loads((data / "i18n" / "_index.json").read_text()))
    total = unknown = untranslated = 0
    for _, rows in store.all():
        for r in rows:
            if not isinstance(r, dict):
                continue
            for k, v in r.items():
                if k.endswith("_guid") and v and k not in STRUCTURAL_GUIDS:
                    total += 1
                    if v not in index:
                        unknown += 1
                    elif v not in english:
                        untranslated += 1
    if unknown:
        rep.error(f"{unknown} GUID reference(s) point outside i18n/_index.json")
    else:
        ok += 1
    if untranslated:
        rep.warn(f"{untranslated}/{total} GUID references have no English "
                        f"string; the entries exist but the workbook leaves them blank")

    return rep.emit(f"{ok} constraint(s) satisfied, "
                    f"{total} GUID references checked")


if __name__ == "__main__":
    sys.exit(main())
