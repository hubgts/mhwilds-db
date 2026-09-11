#!/usr/bin/env python3
"""Stage 2, EXTRACT. Dumb, lossless, no interpretation.

xlsx -> build/<date>/
          sheets/<slug>.jsonl     one line per record, every column kept
          assets/<slug>/rNNNNcNN.png   images resolved through cell anchors
          assets.json             image -> (sheet, row, col) index
          inventory.json          sheets, columns, volumes

This stage decides nothing: it renames nothing, converts nothing, resolves no
join. That is what lets it keep passing when the upstream sheet is reorganised.

Usage: extract.py [--source rawdata/latest.xlsx] [--out build]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import write_json  # noqa: E402
from mhwlib import Workbook, png_pixel_hash, slug, write_if_changed  # noqa: E402

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def source_date(path: Path, mtime: float) -> str:
    m = DATE_RE.search(path.resolve().name)
    if m:
        return m.group(1)
    import datetime
    return datetime.date.fromtimestamp(mtime).isoformat()


def write_assets(wb: Workbook, out_dir: Path) -> dict:
    """Write one image per anchored cell. Skips the write when pixels match.

    Hashing 1,104 PNGs costs about nine seconds, and a rebuild from the same
    export needs none of it: when the bytes on disk are identical to the source
    the digest recorded last time still describes them, so it is reused.
    """
    previous_path = out_dir / "assets.json"
    previous = (json.loads(previous_path.read_text())
                if previous_path.exists() else {})
    index, written, kept = {}, 0, 0
    for sheet in wb.sheets:
        anchors = wb.anchors(sheet)
        if not anchors:
            continue
        sheet_dir = out_dir / "assets" / slug(sheet)
        sheet_dir.mkdir(parents=True, exist_ok=True)
        for (row, col), member in sorted(anchors.items()):
            data = wb.read(member)
            key = f"{slug(sheet)}/r{row:04d}c{col:02d}.png"
            dest = sheet_dir / f"r{row:04d}c{col:02d}.png"
            known = previous.get(key, {}).get("pixel_hash")
            if known and dest.exists() and dest.read_bytes() == data:
                digest = known
                kept += 1
            else:
                digest = png_pixel_hash(data)
                if write_if_changed(dest, data, digest):
                    written += 1
                else:
                    kept += 1
            index[key] = {"sheet": sheet, "row": row, "col": col,
                          "pixel_hash": digest}
    return {"index": index, "written": written, "unchanged": kept}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="rawdata/latest.xlsx")
    ap.add_argument("--out", default="build")
    ap.add_argument("--skip-assets", action="store_true")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 1

    wb = Workbook(src)
    date = source_date(src, src.stat().st_mtime)
    out_dir = Path(args.out) / date
    (out_dir / "sheets").mkdir(parents=True, exist_ok=True)

    print(f"source   {src}")
    print(f"output   {out_dir}")
    print(f"sheets   {len(wb.sheets)}")

    inventory, total_rows = {}, 0
    for sheet in wb.sheets:
        headers, _ = wb.table(sheet)
        path = out_dir / "sheets" / f"{slug(sheet)}.jsonl"
        count = 0
        with path.open("w", encoding="utf-8") as fh:
            for rec in wb.records(sheet):
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
        inventory[sheet] = {
            "file": f"sheets/{slug(sheet)}.jsonl",
            "state": wb.states[sheet],
            "rows": count,
            "columns": headers,
        }
        total_rows += count

    assets = {"index": {}, "written": 0, "unchanged": 0}
    if not args.skip_assets:
        assets = write_assets(wb, out_dir)
        write_json(out_dir / "assets.json", assets["index"])

    write_json(out_dir / "inventory.json", {
        "source_file": src.resolve().name,
        "source_date": date,
        "sheet_count": len(inventory),
        "row_total": total_rows,
        "asset_count": len(assets["index"]),
        "sheets": inventory,
    })

    print(f"rows     {total_rows}")
    print(f"images   {len(assets['index'])} anchored "
          f"({assets['written']} written, {assets['unchanged']} unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
