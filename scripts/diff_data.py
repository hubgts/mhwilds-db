#!/usr/bin/env python3
"""Compare two builds of data/ and say what the game update actually changed.

The fingerprint in mhw_fingerprint.py compares two .xlsx files and answers
"identical or different". This answers the useful question instead: which
monsters were added, which recipes changed, which prices moved.

Records are matched on their natural key where one is declared in
check_output.py, and on a stable subset of fields otherwise. Nested lists are
compared as a whole, so a changed recipe shows up as one modified record.

Usage:
  diff_data.py OLD NEW            summary per file
  diff_data.py OLD NEW --details  every added, removed and modified record
  diff_data.py OLD NEW --file monsters/monsters
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_output import PRIMARY_KEYS  # noqa: E402
from core import GREEN, OFF, RED, YEL, iter_entity_files  # noqa: E402

# Files with no declared primary key: what identifies a row instead.
FALLBACK_KEYS = {
    "weapons/weapons": ("weapon_type", "id"),
    "weapons/tree_nodes": ("weapon_type", "weapon_id"),
    "weapons/recipes": ("weapon_type", "index"),
    "monsters/drops": ("em_id", "reward_type_id", "item_data_id", "probability"),
    "monsters/hitzones": ("em_id", "instance_guid"),
    "monsters/parts": ("em_id", "instance_guid"),
    "armor/armor": ("series", "part"),
    "armor/recipes": ("series", "part"),
    "charms/decorations": ("enum",),
    "progression/mission_rewards": ("table_id", "data_id"),
}
IGNORED_FIELDS = {"_row", "id", "index"}


def key_of(path, record, fields):
    return tuple(json.dumps(record.get(f), sort_keys=True) for f in fields)


def key_fields(path, rows):
    if path in PRIMARY_KEYS:
        return (PRIMARY_KEYS[path],)
    if path in FALLBACK_KEYS:
        return FALLBACK_KEYS[path]
    # last resort: the whole record minus volatile fields
    return tuple(k for k in rows[0] if k not in IGNORED_FIELDS)


def body(record):
    return {k: v for k, v in record.items() if k not in IGNORED_FIELDS}


def load_dir(root: Path):
    out = {}
    for path, p in iter_entity_files(root):
        rows = json.loads(p.read_text())
        if isinstance(rows, list):
            out[path] = rows
    return out


def compare_file(path, old_rows, new_rows):
    fields = key_fields(path, new_rows or old_rows)
    old = {key_of(path, r, fields): r for r in old_rows}
    new = {key_of(path, r, fields): r for r in new_rows}
    added = [new[k] for k in new.keys() - old.keys()]
    removed = [old[k] for k in old.keys() - new.keys()]
    modified = []
    for k in old.keys() & new.keys():
        a, b = body(old[k]), body(new[k])
        if a != b:
            changed = {f: (a.get(f), b.get(f)) for f in set(a) | set(b)
                       if a.get(f) != b.get(f)}
            modified.append((new[k], changed))
    return added, removed, modified, fields


def label(record, fields):
    for f in ("name", "item_id", "em_id", "mission_id", "series", "weapon_name",
              "monster", "skill_id"):
        if record.get(f):
            return str(record[f])
    return ", ".join(str(record.get(f)) for f in fields)


def diff_i18n(old_root: Path, new_root: Path):
    out = []
    for f in sorted((new_root / "i18n").glob("*.json")):
        if f.stem.startswith("_"):
            continue
        old_f = old_root / "i18n" / f.name
        old = json.loads(old_f.read_text()) if old_f.exists() else {}
        new = json.loads(f.read_text())
        added = len(new.keys() - old.keys())
        removed = len(old.keys() - new.keys())
        changed = sum(1 for k in old.keys() & new.keys() if old[k] != new[k])
        if added or removed or changed:
            out.append((f.stem, added, removed, changed))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--details", action="store_true")
    ap.add_argument("--file")
    args = ap.parse_args()

    old_root, new_root = Path(args.old), Path(args.new)
    for d in (old_root, new_root):
        if not (d / "manifest.json").exists():
            print(f"{d} is not a data directory", file=sys.stderr)
            return 1
    om = json.loads((old_root / "manifest.json").read_text())
    nm = json.loads((new_root / "manifest.json").read_text())
    print(f"old  {om['source_file']}  ({om['source_date']})")
    print(f"new  {nm['source_file']}  ({nm['source_date']})\n")

    old, new = load_dir(old_root), load_dir(new_root)
    paths = sorted(set(old) | set(new))
    if args.file:
        paths = [p for p in paths if p == args.file]
        if not paths:
            print(f"unknown file: {args.file}", file=sys.stderr)
            return 1

    total = [0, 0, 0]
    for path in paths:
        if path not in old:
            print(f"  {GREEN}+{OFF} new file {path} ({len(new[path])} rows)")
            total[0] += len(new[path])
            continue
        if path not in new:
            print(f"  {RED}-{OFF} file gone {path} ({len(old[path])} rows)")
            total[1] += len(old[path])
            continue
        added, removed, modified, fields = compare_file(path, old[path], new[path])
        if not (added or removed or modified):
            continue
        total[0] += len(added)
        total[1] += len(removed)
        total[2] += len(modified)
        bits = []
        if added:
            bits.append(f"{GREEN}+{len(added)}{OFF}")
        if removed:
            bits.append(f"{RED}-{len(removed)}{OFF}")
        if modified:
            bits.append(f"{YEL}~{len(modified)}{OFF}")
        print(f"  {path:42s} {' '.join(bits)}")
        if args.details or args.file:
            for r in added[:40]:
                print(f"      {GREEN}+{OFF} {label(r, fields)}")
            for r in removed[:40]:
                print(f"      {RED}-{OFF} {label(r, fields)}")
            for r, changed in modified[:40]:
                for f, (a, b) in sorted(changed.items()):
                    print(f"      {YEL}~{OFF} {label(r, fields)}: {f} "
                          f"{a!r} -> {b!r}")

    langs = diff_i18n(old_root, new_root)
    if langs:
        print()
        for stem, a, r, c in langs:
            print(f"  i18n/{stem:22s} {GREEN}+{a}{OFF} {RED}-{r}{OFF} {YEL}~{c}{OFF}")

    print()
    if not any(total) and not langs:
        print(f"{GREEN}no change{OFF} between the two builds")
    else:
        print(f"{total[0]} added, {total[1]} removed, {total[2]} modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
