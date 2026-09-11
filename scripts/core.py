#!/usr/bin/env python3
"""Shared vocabulary for the pipeline stages.

Value converters, the JSONL reader over build/<date>/, the data/ tree walker,
and the report format the stages print. These live here because more than one
stage needs them and, more importantly, because two stages measuring the same
join must measure it the same way: validate.py checks that a join will work,
build.py performs it. When those two used separate copies of "strip the
parentheses off a code", a change to one silently made the other lie.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

GREEN, RED, YEL, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

PAREN = re.compile(r"^(.*?)\s*\((.*)\)\s*$")
BROKEN = "#REF!", "#N/A", "#VALUE!", "#NAME?"

# Directories under data/ that hold something other than entity records.
NON_ENTITY_DIRS = {"i18n", "views", "reference", "assets"}


# -------------------------------------------------------------- converters

def as_int(v):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def as_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def as_bool(v):
    if v in (None, ""):
        return None
    if v in ("0", "1"):
        return v == "1"
    if str(v).lower() in ("true", "false"):
        return str(v).lower() == "true"
    return None


def as_str(v):
    if v in (None, ""):
        return None
    v = str(v).strip()
    return v or None


def as_str_dash(v):
    """Like as_str, but the workbook's "-" placeholder also means absent."""
    v = as_str(v)
    return None if v == "-" else v


def as_lines(v):
    return [p.strip() for p in v.split("\n") if p.strip()] if v else []


def as_csv(v):
    return [p.strip() for p in v.split(",") if p.strip()] if v else []


def as_code(v):
    """'ITEM_0000 (Potion)' -> 'ITEM_0000'. 'Potion' -> 'Potion'."""
    if not v:
        return None
    m = PAREN.match(v)
    return (m.group(1) if m else v).strip() or None


def as_code_label(v):
    """'ITEM_0000 (Potion)' -> {'code': 'ITEM_0000', 'label': 'Potion'}."""
    if not v:
        return None
    m = PAREN.match(v)
    if m:
        return {"code": m.group(1).strip(), "label": m.group(2).strip()}
    return {"code": v.strip(), "label": None}


def paren_int(v):
    """'RARE0 (1)' -> 1. The workbook renders enums as code plus display value."""
    if not v:
        return None
    m = PAREN.match(v)
    return as_int(m.group(2)) if m else as_int(v)


def from_hex(v):
    """'00000218' -> 536. Zero and empty become None (0 is the engine's null)."""
    if not v:
        return None
    try:
        n = int(v, 16)
    except (TypeError, ValueError):
        return None
    return n or None


CONV = {
    "int": as_int, "float": as_float, "bool": as_bool, "str": as_str,
    "str_dash": as_str_dash, "lines": as_lines, "csv": as_csv, "code": as_code,
    "code_label": as_code_label, "hex": from_hex, "paren_int": paren_int,
    "rejected": lambda v: is_rejected(v),
}


def clean(v):  # noqa: E302
    """Drop the workbook's own formula errors; they are not values."""
    return None if v in BROKEN else v


def is_rejected(v):
    """The workbook marks unused entries with a #Rejected# tag inside the name."""
    return bool(v) and "#Rejected#" in v


# ------------------------------------------------------------------ sources

class Source:
    """Reader over one build/<date>/ extraction, caching each sheet once."""

    def __init__(self, build_dir: Path):
        self.dir = Path(build_dir)
        self.inventory = json.loads((self.dir / "inventory.json").read_text())
        self._cache = {}

    def rows(self, sheet):
        if sheet not in self._cache:
            from mhwlib import slug
            path = self.dir / "sheets" / f"{slug(sheet)}.jsonl"
            if path.exists():
                with path.open(encoding="utf-8") as fh:
                    self._cache[sheet] = [json.loads(l) for l in fh]
            else:
                self._cache[sheet] = []
        return self._cache[sheet]

    def has(self, sheet):
        return sheet in self.inventory["sheets"]


def latest_build(base="build"):
    """The most recent extraction. A build directory is one with an inventory."""
    dirs = sorted(p for p in Path(base).glob("*") if (p / "inventory.json").exists())
    return dirs[-1] if dirs else None


def iter_entity_files(data: Path):
    """Every entity file under data/, as (relative path without .json, Path)."""
    for p in sorted(Path(data).glob("*/*.json")):
        if p.parent.name in NON_ENTITY_DIRS:
            continue
        yield f"{p.parent.name}/{p.stem}", p


def write_json(path: Path, obj, indent=1):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent),
                    encoding="utf-8")


# ------------------------------------------------------------------- report

class Report:
    """Errors fail the stage, warnings do not, infos are context."""

    def __init__(self):
        self.errors, self.warnings, self.infos = [], [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)

    def emit(self, extra=""):
        for m in self.infos:
            print(f"  {DIM}·{OFF} {m}")
        for m in self.warnings:
            print(f"  {YEL}!{OFF} {m}")
        for m in self.errors:
            print(f"  {RED}x{OFF} {m}")
        if extra:
            print(f"\n  {DIM}{extra}{OFF}")
        print()
        if self.errors:
            print(f"{RED}FAILED{OFF}  {len(self.errors)} error(s), "
                  f"{len(self.warnings)} warning(s)")
            return 1
        print(f"{GREEN}OK{OFF}  {len(self.warnings)} warning(s), no error")
        return 0
