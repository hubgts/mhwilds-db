#!/usr/bin/env python3
"""Stable fingerprint of a Google Sheets .xlsx export.

Google regenerates the archive on every export: PNGs are re-encoded, drawing
ids are renumbered and the shared string table is reordered. An md5 of the file
therefore always reports "different" even when nothing changed.

This fingerprint ignores those variations: it hashes the sorted shared strings,
the sheet list and the per-sheet row counts.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mhwlib import Workbook  # noqa: E402


def fingerprint(path):
    wb = Workbook(path)
    strings_md5 = hashlib.md5("\n".join(sorted(wb.strings)).encode()).hexdigest()
    rows = [(name, wb.states[name], wb.row_count(name)) for name in wb.sheets]
    sheets_md5 = hashlib.md5(
        "\n".join(f"{n}\t{s}\t{r}" for n, s, r in rows).encode()
    ).hexdigest()
    return {
        "strings_count": len(wb.strings),
        "strings_md5": strings_md5,
        "sheets_count": len(rows),
        "sheets_md5": sheets_md5,
        "total_rows": sum(r for _, _, r in rows),
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: mhw_fingerprint.py <file.xlsx> [other.xlsx]")

    prints = [(p, fingerprint(p)) for p in sys.argv[1:]]
    for path, fp in prints:
        print(f"{path}")
        print(f"  sheets      : {fp['sheets_count']}")
        print(f"  rows        : {fp['total_rows']}")
        print(f"  strings     : {fp['strings_count']}")
        print(f"  fingerprint : {fp['strings_md5'][:12]} / {fp['sheets_md5'][:12]}")

    if len(prints) == 2:
        a, b = prints[0][1], prints[1][1]
        same = a["strings_md5"] == b["strings_md5"] and a["sheets_md5"] == b["sheets_md5"]
        print()
        if same:
            print("=> content IDENTICAL (no data change)")
        else:
            print("=> content DIFFERENT")
            if a["strings_md5"] != b["strings_md5"]:
                print(f"   strings: {a['strings_count']} -> {b['strings_count']}")
            if a["sheets_md5"] != b["sheets_md5"]:
                print(f"   sheets: {a['sheets_count']} -> {b['sheets_count']}, "
                      f"rows: {a['total_rows']} -> {b['total_rows']}")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
