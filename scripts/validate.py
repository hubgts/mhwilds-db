#!/usr/bin/env python3
"""Stage 3, VALIDATE. Compares the extract against the contract and the baseline.

Two kinds of check, deliberately kept apart:

  The INVENTORY (schema/inventory.json) is mechanical and regenerates itself.
  A sheet added, a column added: absorbed, reported, the run continues.

  The CONTRACT (schema/contract.yaml) encodes an analysis. A load-bearing
  column that disappears, a join whose coverage collapses, a column that goes
  empty: the pipeline stops.

Exit code 0 when everything passes, 1 otherwise. The report lists every gap.

Usage: validate.py [--build build/<date>] [--accept-inventory]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (DIM, GREEN, OFF, RED, YEL, Report, Source,  # noqa: E402
                  as_code, as_csv, as_int, as_lines, from_hex, latest_build,
                  write_json)

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YEL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


# ---------------------------------------------------------------- transforms
# A join is declared in the contract, measured here, and performed in build.py.
# All three must agree on what "the same value" means, so these adapt the shared
# converters rather than re-implementing them: each returns a list, because one
# cell can hold several values.

TRANSFORMS = {
    "identity": lambda v: [v],
    "int_from_float": lambda v: [str(as_int(v))] if as_int(v) is not None else [v],
    "hex_to_dec": lambda v: [str(n)] if (n := from_hex(v)) else [],
    "split_newlines": as_lines,
    "split_commas": as_csv,
    "strip_paren": lambda v: [as_code(v)] if as_code(v) else [],
}


# ------------------------------------------------------------------- loading

class Build(Source):
    """A Source that also answers "what values does this column hold"."""

    def values(self, sheet, column, transform="identity", exclude=None):
        """exclude = {"column": ..., "values": [...]} drops whole rows."""
        rows = self.rows(sheet)
        if not rows and not self.has(sheet):
            return None
        fn = TRANSFORMS[transform]
        ex_col = (exclude or {}).get("column")
        ex_vals = set((exclude or {}).get("values", []))
        out = set()
        for r in rows:
            if ex_col and r.get(ex_col) in ex_vals:
                continue
            v = r.get(column)
            if v in (None, ""):
                continue
            out.update(fn(v))
        return out


# -------------------------------------------------------------------- checks

def check_inventory_drift(build: Build, rep: Report, accept: bool):
    """Additive drift is absorbed. A disappearance is an error."""
    ref_path = ROOT / "schema" / "inventory.json"
    current = {
        name: sorted(meta["columns"]) for name, meta in build.inventory["sheets"].items()
    }
    if not ref_path.exists():
        write_json(ref_path, current)
        rep.info(f"baseline inventory created ({len(current)} sheets)")
        return

    ref = json.loads(ref_path.read_text())
    added = sorted(set(current) - set(ref))
    removed = sorted(set(ref) - set(current))
    changed = []
    for name in sorted(set(current) & set(ref)):
        gone = set(ref[name]) - set(current[name])
        new = set(current[name]) - set(ref[name])
        if gone or new:
            changed.append((name, sorted(gone), sorted(new)))

    for name in added:
        rep.info(f"new sheet: {name}")
    for name in removed:
        rep.warn(f"sheet gone: {name}")
    for name, gone, new in changed:
        if gone:
            rep.warn(f"{name}: columns gone {gone[:4]}")
        if new:
            rep.info(f"{name}: columns added {new[:4]}")

    if accept and (added or removed or changed):
        write_json(ref_path, current)
        rep.info("baseline inventory updated (--accept-inventory)")


def check_sheets(contract, build: Build, rep: Report):
    src = contract["source"]
    inv = build.inventory
    if inv["sheet_count"] < src["min_sheets"]:
        rep.error(f"{inv['sheet_count']} sheets, minimum expected {src['min_sheets']}")
    if inv["row_total"] < src["min_rows"]:
        rep.error(f"{inv['row_total']} rows in total, minimum expected {src['min_rows']}")

    for name, spec in contract["sheets"].items():
        meta = inv["sheets"].get(name)
        if meta is None:
            rep.error(f"load-bearing sheet missing: {name}")
            continue
        if meta["rows"] < spec["min_rows"]:
            rep.error(f"{name}: {meta['rows']} rows, minimum {spec['min_rows']}")
        missing = [c for c in spec["columns"] if c not in meta["columns"]]
        if missing:
            rep.error(f"{name}: contract columns missing {missing}")


def check_joins(contract, build: Build, rep: Report):
    weapon_sheets = list(contract["weapon_sheets"].values())
    for j in contract["joins"]:
        child, parent = j["child"], j["parent"]
        cvals = build.values(
            child["sheet"], child["column"],
            child.get("transform", "identity"), child.get("exclude_rows"),
        )
        if cvals is None:
            rep.error(f"{j['id']}: child sheet missing ({child['sheet']})")
            continue

        if parent.get("sheets") == "weapon_sheets":
            pvals = set()
            for s in weapon_sheets:
                v = build.values(s, parent["column"], parent.get("transform", "identity"))
                if v:
                    pvals |= v
        else:
            pvals = build.values(parent["sheet"], parent["column"], parent.get("transform", "identity"))
        if pvals is None:
            rep.error(f"{j['id']}: parent sheet missing ({parent.get('sheet')})")
            continue

        cvals -= set(j.get("ignore_values", []))
        if not cvals:
            rep.error(f"{j['id']}: no value to join on the child side")
            continue

        orphans = sorted(cvals - pvals)
        coverage = (len(cvals) - len(orphans)) / len(cvals)
        line = f"{j['id']:38s} {coverage*100:5.1f}%  ({len(cvals)} values)"
        if coverage < j["min_coverage"]:
            rep.error(f"{line}  below threshold {j['min_coverage']*100:.0f}%, orphans: {orphans[:4]}")
        else:
            rep.info(line)


def check_emptiness(contract, build: Build, rep: Report):
    for sheet, column in contract["non_empty"]:
        vals = build.values(sheet, column)
        if vals is None:
            rep.error(f"non_empty: sheet missing ({sheet})")
        elif not vals:
            rep.error(f"non_empty: {sheet}.{column} is empty, a join was silently lost")

    for sheet, column in contract["known_empty"]:
        vals = build.values(sheet, column)
        if vals:
            rep.warn(
                f"known_empty: {sheet}.{column} now holds {len(vals)} values, "
                f"the workbook repaired this formula, fold it into the build"
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=None)
    ap.add_argument("--accept-inventory", action="store_true",
                    help="accept inventory drift as the new baseline")
    args = ap.parse_args()

    build_dir = Path(args.build) if args.build else latest_build()
    if build_dir is None:
        print("no extract found in build/, run extract.py first", file=sys.stderr)
        return 1

    contract = yaml.safe_load((ROOT / "schema" / "contract.yaml").read_text())
    build = Build(build_dir)
    rep = Report()

    print(f"extract   {build_dir}")
    print(f"source    {build.inventory['source_file']}")
    print(f"contract  schema/contract.yaml (v{contract['schema_version']})\n")

    check_inventory_drift(build, rep, args.accept_inventory)
    check_sheets(contract, build, rep)
    check_joins(contract, build, rep)
    check_emptiness(contract, build, rep)
    return rep.emit()


if __name__ == "__main__":
    sys.exit(main())
