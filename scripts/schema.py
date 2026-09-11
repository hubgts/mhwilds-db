#!/usr/bin/env python3
"""Generate a PostgreSQL schema from data/, plus the CSV files that fill it.

The shape is derived from the data itself, so it cannot drift from what the
build produces. Keys come from the declarations in check_output.py, which are
already enforced against the JSON.

Modelling choices, made once here:

  * one Postgres schema per data/ folder, so `core.items` and `monsters.drops`
    read the same way as the file tree;
  * every table gets a surrogate `id`, because several files have no natural
    key (a merged sheet like weapons has no unique column of its own);
  * an array of objects becomes a child table, not JSONB, because those are
    genuine relations: recipe materials point at items and deserve a real
    foreign key;
  * an array of scalars also becomes a child table, so `WHERE locale = ...`
    is an index lookup rather than a containment operator;
  * an object with fixed keys is flattened into columns, because it is a
    record, not a relation: sharpness has seven colours and always will.

Usage:
  schema.py                write schema/postgres.sql and build/<date>/sql/*.csv
  schema.py --sql-only     DDL only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_output import (PRIMARY_KEYS, FOREIGN_KEYS, STRUCTURAL_GUIDS,  # noqa: E402
                          ACCEPTED)
from core import iter_entity_files  # noqa: E402
from mhwlib import slug  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ORDER = ["core", "monsters", "weapons", "armor", "charms", "artian",
                "palico", "world", "economy", "progression", "i18n", "views"]
RESERVED = {"class", "order", "type", "default", "user", "table", "column",
            "index", "group", "values", "level", "references", "primary", "key",
            "position", "condition", "action", "time"}

# The surrogate key. Deliberately not "id": several entities carry a field of
# their own called id (weapons, medals, name plates), and taking that name for
# the row number renamed theirs to id_ and silently invited joins on the wrong
# column.
ROW_ID = "row_id"


def ident(name):
    """Snake-case a JSON field into a safe SQL identifier."""
    n = slug(name, sep="_")
    return f"{n}_" if n in RESERVED else n


def table_name(path):
    schema, _, name = path.partition("/")
    return schema, ident(name)


# ----------------------------------------------------------- type inference

def scalar_type(values):
    seen = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            seen.add("bool")
        elif isinstance(v, int):
            seen.add("int")
        elif isinstance(v, float):
            seen.add("float")
        else:
            seen.add("text")
    if not seen:
        return "text"
    if seen == {"bool"}:
        return "boolean"
    if seen == {"int"}:
        return "bigint"
    if seen <= {"int", "float"}:
        return "double precision"
    return "text"


def describe(rows):
    """Return (columns, scalar_arrays, object_arrays, flattened_objects)."""
    columns, arrays_scalar, arrays_object, objects = {}, {}, {}, {}
    for r in rows:
        for k, v in r.items():
            if k == "_row":
                continue
            if isinstance(v, list):
                if v and isinstance(v[0], dict):
                    arrays_object.setdefault(k, {})
                    for item in v:
                        for ik, iv in item.items():
                            arrays_object[k].setdefault(ik, []).append(iv)
                else:
                    arrays_scalar.setdefault(k, []).extend(v)
            elif isinstance(v, dict):
                for ik, iv in v.items():
                    objects.setdefault(k, {}).setdefault(ik, []).append(iv)
            else:
                columns.setdefault(k, []).append(v)
    # A field can be an empty list on one row and a list of objects on the
    # next; the object shape wins, otherwise the same child table is declared
    # twice.
    for k in list(arrays_scalar):
        if k in arrays_object:
            arrays_scalar.pop(k)
    for k in list(columns):
        if k in arrays_scalar or k in arrays_object or k in objects:
            columns.pop(k)
    return (
        {k: scalar_type(v) for k, v in columns.items()},
        {k: scalar_type(v) for k, v in arrays_scalar.items()},
        {k: {ik: scalar_type(iv) for ik, iv in cols.items()}
         for k, cols in arrays_object.items()},
        {k: {ik: scalar_type(iv) for ik, iv in cols.items()}
         for k, cols in objects.items()},
    )


# ------------------------------------------------------------------- schema

def build_model(data: Path):
    """Inspect every entity file and return the tables to create."""
    tables = []
    for rel, path in iter_entity_files(data):
        rows = json.loads(path.read_text())
        if not isinstance(rows, list) or not rows:
            continue
        cols, arr_scalar, arr_object, objects = describe(rows)
        schema, name = table_name(rel)
        flat = dict(cols)
        for field, subcols in objects.items():
            for sub, t in subcols.items():
                flat[f"{field}_{sub}"] = t
        tables.append({
            "path": rel, "schema": schema, "name": name, "rows": rows,
            "columns": flat, "objects": objects,
            "arrays_scalar": arr_scalar, "arrays_object": arr_object,
            "pk": PRIMARY_KEYS.get(rel),
        })
    return tables


def ddl(tables):
    """Return (tables DDL, constraints DDL). Constraints come after the load."""
    by_path = {t["path"]: t for t in tables}
    out = [
        "-- PostgreSQL schema for the Monster Hunter Wilds dataset.",
        "-- Generated by scripts/schema.py from data/. Do not edit by hand.",
        "--",
        "-- Load order matters: this file creates schemas and tables, then the",
        "-- CSVs in build/<date>/sql/ fill them in dependency order.",
        "",
    ]
    for s in SCHEMA_ORDER:
        out.append(f"CREATE SCHEMA IF NOT EXISTS {s};")
    out.append("")

    # translations first, everything can reference them
    out += [
        "-- Localisation. One row per GUID and language, which is why entities",
        "-- carry a GUID rather than a column per language.",
        "CREATE TABLE i18n.entries (",
        "  guid   text NOT NULL,",
        "  entry  text,",
        "  source text NOT NULL",
        ");",
        "",
        "CREATE TABLE i18n.translations (",
        "  guid text NOT NULL,",
        "  lang text NOT NULL,",
        "  text text NOT NULL",
        ");",
        "",
        "-- Consultation grids from the workbook. Not relations: the cell",
        "-- position carries the meaning, so they stay as documents.",
        "CREATE TABLE views.sheets (",
        "  name    text NOT NULL,",
        "  columns jsonb NOT NULL,",
        "  rows    jsonb NOT NULL",
        ");",
        "",
    ]

    for t in tables:
        out.append(f"-- {t['path']}.json")
        lines = [f"  {ROW_ID} bigint NOT NULL"]
        for col, typ in t["columns"].items():
            lines.append(f"  {ident(col)} {typ}")
        lines.append("  source_row integer")
        out.append(f"CREATE TABLE {t['schema']}.{t['name']} (")
        out.append(",\n".join(lines))
        out.append(");")
        for field, typ in t["arrays_scalar"].items():
            child = f"{t['name']}_{ident(field)}"
            out += [
                f"CREATE TABLE {t['schema']}.{child} (",
                f"  {t['name']}_{ROW_ID} bigint NOT NULL,",
                f"  position integer NOT NULL,",
                f"  value {typ}",
                ");",
            ]
        for field, subcols in t["arrays_object"].items():
            child = f"{t['name']}_{ident(field)}"
            lines = [f"  {t['name']}_{ROW_ID} bigint NOT NULL",
                     "  position integer NOT NULL"]
            lines += [f"  {ident(c)} {typ}" for c, typ in subcols.items()]
            out += [f"CREATE TABLE {t['schema']}.{child} (",
                    ",\n".join(lines), ");"]
        out.append("")

    # A foreign key needs a unique constraint on the column it points at.
    # Which columns those are follows from FOREIGN_KEYS, but uniqueness is a
    # property of the data, so it is measured here rather than assumed.
    targets = {}
    for _, (parent_path, pfield) in FOREIGN_KEYS.items():
        targets.setdefault(parent_path, set()).add(pfield)
    for t in tables:
        if t["pk"]:
            targets.setdefault(t["path"], set()).add(t["pk"])
    unique_ok, not_unique = set(), {}
    for path, fields in targets.items():
        t = by_path.get(path)
        if not t:
            continue
        for f in fields:
            values = [r.get(f) for r in t["rows"] if r.get(f) is not None]
            if len(values) == len(set(values)):
                unique_ok.add((path, f))
            else:
                dupes = len(values) - len(set(values))
                not_unique[(path, f)] = dupes

    tables_sql = "\n".join(out) + "\n"
    out = [
        "-- Keys and indexes for the Monster Hunter Wilds dataset.",
        "-- Generated by scripts/schema.py. Apply AFTER schema/load.sql:",
        "-- creating a foreign key on populated tables is what proves the data.",
        "",
        "ALTER TABLE i18n.entries ADD PRIMARY KEY (guid);",
        "ALTER TABLE i18n.translations ADD PRIMARY KEY (guid, lang);",
        "ALTER TABLE i18n.translations ADD FOREIGN KEY (guid) "
        "REFERENCES i18n.entries(guid);",
        "CREATE INDEX ON i18n.translations (lang);",
        "ALTER TABLE views.sheets ADD PRIMARY KEY (name);",
        "",
    ]
    for t in tables:
        out.append(f"ALTER TABLE {t['schema']}.{t['name']} ADD PRIMARY KEY ({ROW_ID});")
        for field in list(t["arrays_scalar"]) + list(t["arrays_object"]):
            child = f"{t['name']}_{ident(field)}"
            out.append(f"ALTER TABLE {t['schema']}.{child} ADD PRIMARY KEY "
                       f"({t['name']}_{ROW_ID}, position);")
            out.append(f"ALTER TABLE {t['schema']}.{child} ADD FOREIGN KEY "
                       f"({t['name']}_{ROW_ID}) REFERENCES "
                       f"{t['schema']}.{t['name']}({ROW_ID}) ON DELETE CASCADE;")
    out.append("")
    out.append("-- Unique constraints, required by the foreign keys below and")
    out.append("-- measured against the data at generation time.")
    for path, f in sorted(unique_ok):
        t = by_path[path]
        out.append(f"ALTER TABLE {t['schema']}.{t['name']} "
                   f"ADD CONSTRAINT {t['name']}_{ident(f)}_key UNIQUE ({ident(f)});")
    for (path, f), dupes in sorted(not_unique.items()):
        t = by_path[path]
        out.append(f"-- {t['schema']}.{t['name']}.{ident(f)} is not unique "
                   f"({dupes} duplicate value(s)), so it carries an index rather "
                   f"than a key.")
        out.append(f"CREATE INDEX ON {t['schema']}.{t['name']} ({ident(f)});")
    out.append("")

    from check_output import COMPOSITE_KEYS
    pairs = {(parent, pfields) for _, (parent, pfields) in COMPOSITE_KEYS.items()}
    if pairs:
        out.append("-- Composite natural keys.")
        for parent, pfields in sorted(pairs):
            t = by_path.get(parent)
            if not t:
                continue
            cols = ", ".join(ident(f) for f in pfields)
            out.append(f"ALTER TABLE {t['schema']}.{t['name']} ADD CONSTRAINT "
                       f"{t['name']}_key UNIQUE ({cols});")
        out.append("")

    out.append("-- Foreign keys. Created on populated tables, so PostgreSQL")
    out.append("-- checks every row as it goes.")
    seen = set()
    for (child_path, field), (parent_path, pfield) in FOREIGN_KEYS.items():
        if child_path not in by_path or parent_path not in by_path:
            continue
        c, p = by_path[child_path], by_path[parent_path]
        head, _, tail = field.partition(".")
        if tail:
            if head in c["arrays_object"]:
                tbl, col = f"{c['name']}_{ident(head)}", ident(tail)
            elif head in c["objects"]:
                tbl, col = c["name"], f"{ident(head)}_{ident(tail)}"
            else:
                continue
        else:
            tbl, col = c["name"], ident(field)
        if (child_path, field) in ACCEPTED:
            _, reason = ACCEPTED[(child_path, field)]
            out.append(f"-- no key on {c['schema']}.{tbl}.{col}: {reason}.")
            out.append(f"CREATE INDEX ON {c['schema']}.{tbl} ({col});")
            continue
        if (parent_path, pfield) not in unique_ok:
            out.append(f"-- skipped: {c['schema']}.{tbl}.{col} -> "
                       f"{p['schema']}.{p['name']}.{ident(pfield)} "
                       f"(target column is not unique)")
            continue
        name = f"{tbl}_{col}_fk"
        if name in seen:
            continue
        seen.add(name)
        out.append(f"ALTER TABLE {c['schema']}.{tbl} ADD CONSTRAINT {name} "
                   f"FOREIGN KEY ({col}) REFERENCES {p['schema']}.{p['name']}"
                   f"({ident(pfield)});")
    out.append("")
    out.append("-- Text GUIDs resolve through i18n; declared as indexes rather than")
    out.append("-- foreign keys because the workbook leaves some entries blank.")
    for t in tables:
        for col in t["columns"]:
            if col.endswith("_guid") and col not in STRUCTURAL_GUIDS:
                out.append(f"CREATE INDEX ON {t['schema']}.{t['name']} ({ident(col)});")
    return tables_sql, "\n".join(out) + "\n"


# -------------------------------------------------------------------- export

def export_csv(tables, data: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    def dump(name, header, rows):
        path = out_dir / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        written.append((name, len(rows)))

    entries = json.loads((data / "i18n" / "_index.json").read_text())
    dump("i18n.entries", ["guid", "entry", "source"],
         [[g, e["entry"], e["source"]] for g, e in entries.items()])
    trans = []
    for f in sorted((data / "i18n").glob("*.json")):
        if f.stem.startswith("_"):
            continue
        for guid, text in json.loads(f.read_text()).items():
            trans.append([guid, f.stem, text])
    dump("i18n.translations", ["guid", "lang", "text"], trans)

    views = []
    for f in sorted((data / "views").glob("*.json")):
        v = json.loads(f.read_text())
        views.append([v["sheet"], json.dumps(v["columns"], ensure_ascii=False),
                      json.dumps(v["rows"], ensure_ascii=False)])
    dump("views.sheets", ["name", "columns", "rows"], views)

    for t in tables:
        cols = list(t["columns"])
        header = [ROW_ID] + [ident(c) for c in cols] + ["source_row"]
        # columns that came from flattening an object: where to read them back
        flat_src = {f"{field}_{sub}": (field, sub)
                    for field, subcols in t["objects"].items() for sub in subcols}
        main, children = [], {}
        for i, r in enumerate(t["rows"]):
            row = [i]
            for c in cols:
                val = r.get(c)
                if val is None and c in flat_src:
                    field, sub = flat_src[c]
                    val = (r.get(field) or {}).get(sub)
                row.append(val)
            row.append(r.get("_row"))
            main.append(row)
            for field in t["arrays_scalar"]:
                for pos, v in enumerate(r.get(field) or []):
                    children.setdefault(f"{t['name']}_{ident(field)}", []).append(
                        [i, pos, v])
            for field, subcols in t["arrays_object"].items():
                for pos, item in enumerate(r.get(field) or []):
                    children.setdefault(f"{t['name']}_{ident(field)}", []).append(
                        [i, pos] + [item.get(c) for c in subcols])
        dump(f"{t['schema']}.{t['name']}", header, main)
        for field, typ in t["arrays_scalar"].items():
            child = f"{t['name']}_{ident(field)}"
            dump(f"{t['schema']}.{child}",
                 [f"{t['name']}_{ROW_ID}", "position", "value"],
                 children.get(child, []))
        for field, subcols in t["arrays_object"].items():
            child = f"{t['name']}_{ident(field)}"
            dump(f"{t['schema']}.{child}",
                 [f"{t['name']}_{ROW_ID}", "position"] + [ident(c) for c in subcols],
                 children.get(child, []))
    return written


# Curated views. Unlike the tables, these are hand-written: they encode what a
# consuming application actually asks for, which no amount of introspection can
# guess. Everything they join is already enforced by schema/constraints.sql.
VIEWS_SQL = """-- Convenience views over the Monster Hunter Wilds dataset.
-- Generated by scripts/schema.py. Apply after schema/constraints.sql.

-- Every item in every language, one row per language.
CREATE VIEW core.items_localised AS
SELECT i.data_id, i.item_id, i.name AS name_en, t.lang,
       t.text AS name, d.text AS description
FROM core.items i
JOIN i18n.translations t ON t.guid = i.name_guid
LEFT JOIN i18n.translations d
       ON d.guid = i.description_guid AND d.lang = t.lang;

-- Every monster in every language, with its icon file.
CREATE VIEW monsters.monsters_localised AS
SELECT m.em_id, m.name AS name_en, m.class_, m.species, m.base_health,
       m.icon_large, t.lang, t.text AS name, e.text AS description
FROM monsters.monsters m
JOIN i18n.translations t ON t.guid = m.name_guid
LEFT JOIN i18n.translations e
       ON e.guid = m.description_guid AND e.lang = t.lang;

-- Reward tables with the monster and item spelled out.
CREATE VIEW monsters.drops_detailed AS
SELECT d.em_id, m.name AS monster, d.rank, d.reward_type,
       i.item_id, i.name AS item, d.quantity, d.probability
FROM monsters.drops d
JOIN monsters.monsters m ON m.em_id = d.em_id
LEFT JOIN core.items i ON i.data_id = d.item_data_id;

-- Which monsters drop a given item. The reverse lookup an app needs when a
-- player asks where to farm something.
CREATE VIEW monsters.item_sources AS
SELECT i.item_id, i.name AS item, m.name AS monster, d.rank,
       d.reward_type, d.probability
FROM monsters.drops d
JOIN core.items i ON i.data_id = d.item_data_id
JOIN monsters.monsters m ON m.em_id = d.em_id;

-- Weapons with their position in the upgrade tree.
CREATE VIEW weapons.weapons_in_tree AS
SELECT w.weapon_type, w.id, w.name, w.rarity, w.attack, w.affinity,
       w.element, w.element_value, n.lineage, n.tier, n.previous_weapon_id
FROM weapons.weapons w
LEFT JOIN weapons.tree_nodes n
       ON n.weapon_type = w.weapon_type AND n.weapon_id = w.id;

-- The upgrade graph as edges, ready to walk or render.
CREATE VIEW weapons.upgrade_edges AS
SELECT n.weapon_type, n.lineage,
       n.weapon_id AS from_id, w.name AS from_name, n.tier AS from_tier,
       e.value AS to_id, t.name AS to_name
FROM weapons.tree_nodes n
JOIN weapons.tree_nodes_next_weapon_ids e ON e.tree_nodes_row_id = n.row_id
JOIN weapons.weapons w ON w.weapon_type = n.weapon_type AND w.id = n.weapon_id
LEFT JOIN weapons.weapons t ON t.weapon_type = n.weapon_type AND t.id = e.value;

-- Armour pieces with their series.
CREATE VIEW armor.pieces_with_series AS
SELECT a.series, s.name AS series_name, s.rarity, a.part, a.name,
       a.defense, a.res_fire, a.res_water, a.res_thunder, a.res_ice,
       a.res_dragon, a.slots
FROM armor.armor a
JOIN armor.series s ON s.series = a.series;

-- Every craftable thing that needs a given item, across weapons, armour,
-- talismans and Palico gear. The other reverse lookup an app needs.
CREATE VIEW economy.item_demand AS
SELECT 'weapon' AS kind, r.weapon_name AS product, m.item_id, m.item_name,
       m.quantity
FROM weapons.recipes r JOIN weapons.recipes_materials m ON m.recipes_row_id = r.row_id
UNION ALL
SELECT 'armor', a.series || ' ' || a.part, m.item_id, m.item_name, m.quantity
FROM armor.recipes a JOIN armor.recipes_materials m ON m.recipes_row_id = a.row_id
UNION ALL
SELECT 'talisman', t.name, m.item_id, m.item_name, m.quantity
FROM charms.talisman_recipes t
JOIN charms.talisman_recipes_materials m ON m.talisman_recipes_row_id = t.row_id
UNION ALL
SELECT 'palico', p.series || ' ' || p.category, m.item_id, m.item_name, m.quantity
FROM palico.recipes p JOIN palico.recipes_materials m ON m.recipes_row_id = p.row_id;

-- Cardinality assertions.
--
-- Nothing else checks these views: check_output.py validates data/, and the
-- foreign keys validate the tables, but a view is hand-written SQL and a join
-- on the wrong column silently returns fewer rows instead of failing. That is
-- not hypothetical: upgrade_edges once returned 71 rows instead of 957 because
-- it joined a surrogate key against a game id.
--
-- Each expectation below is expressed from a different angle than the view it
-- guards, so a typo in the view cannot satisfy both.

DO $$
DECLARE
  got bigint;
  want bigint;
  problems text := '';
  PROCEDURE_NAME text;
BEGIN
  -- one row per item and language that has a translated name
  SELECT count(*) INTO got FROM core.items_localised;
  SELECT count(*) INTO want FROM core.items i
    JOIN i18n.translations t ON t.guid = i.name_guid;
  IF got <> want THEN
    problems := problems || format('core.items_localised: %s rows, expected %s; ',
                                   got, want);
  END IF;

  SELECT count(*) INTO got FROM monsters.monsters_localised;
  SELECT count(*) INTO want FROM monsters.monsters m
    JOIN i18n.translations t ON t.guid = m.name_guid;
  IF got <> want THEN
    problems := problems || format('monsters.monsters_localised: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- every drop row survives: the monster key is a enforced foreign key and the
  -- item join is a LEFT JOIN
  SELECT count(*) INTO got FROM monsters.drops_detailed;
  SELECT count(*) INTO want FROM monsters.drops;
  IF got <> want THEN
    problems := problems || format('monsters.drops_detailed: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- only the drops that name an item
  SELECT count(*) INTO got FROM monsters.item_sources;
  SELECT count(*) INTO want FROM monsters.drops WHERE item_data_id IS NOT NULL;
  IF got <> want THEN
    problems := problems || format('monsters.item_sources: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- one row per weapon, tree membership is optional
  SELECT count(*) INTO got FROM weapons.weapons_in_tree;
  SELECT count(*) INTO want FROM weapons.weapons;
  IF got <> want THEN
    problems := problems || format('weapons.weapons_in_tree: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- one edge per declared link
  SELECT count(*) INTO got FROM weapons.upgrade_edges;
  SELECT count(*) INTO want FROM weapons.tree_nodes_next_weapon_ids;
  IF got <> want THEN
    problems := problems || format('weapons.upgrade_edges: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- every armour piece whose series exists
  SELECT count(*) INTO got FROM armor.pieces_with_series;
  SELECT count(*) INTO want FROM armor.armor a
    WHERE EXISTS (SELECT 1 FROM armor.series s WHERE s.series = a.series);
  IF got <> want THEN
    problems := problems || format('armor.pieces_with_series: %s rows, expected %s; ',
                                   got, want);
  END IF;

  -- the four crafting systems concatenated
  SELECT count(*) INTO got FROM economy.item_demand;
  SELECT (SELECT count(*) FROM weapons.recipes_materials)
       + (SELECT count(*) FROM armor.recipes_materials)
       + (SELECT count(*) FROM charms.talisman_recipes_materials)
       + (SELECT count(*) FROM palico.recipes_materials) INTO want;
  IF got <> want THEN
    problems := problems || format('economy.item_demand: %s rows, expected %s; ',
                                   got, want);
  END IF;

  IF problems <> '' THEN
    RAISE EXCEPTION 'view cardinality check failed: %', problems;
  END IF;
  RAISE NOTICE 'all 8 views return the expected number of rows';
END
$$;
"""


def load_script(written, out_dir: Path):
    """psql script filling the schema, parents before children."""
    lines = [
        "-- Fill the schema created by schema/postgres.sql.",
        "-- Paths are relative to the project root, so run psql from there.",
        "-- Generated by scripts/schema.py. Run with:",
        "--   psql -v ON_ERROR_STOP=1 -d <db> -f schema/postgres.sql",
        "--   psql -v ON_ERROR_STOP=1 -d <db> -f schema/load.sql",
        "--   psql -v ON_ERROR_STOP=1 -d <db> -f schema/constraints.sql",
        "-- Load order is free: the keys are created afterwards.",
        "",
    ]
    for name, _ in written:
        schema, _, table = name.partition(".")
        lines.append(f"\\copy {schema}.{table} FROM '{out_dir}/{name}.csv' "
                     f"WITH (FORMAT csv, HEADER true, NULL '')")
    lines += ["", "-- Then apply schema/constraints.sql, which creates the keys",
              "-- on populated tables and therefore checks every row."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--sql-only", action="store_true")
    args = ap.parse_args()
    data = Path(args.data)
    manifest = json.loads((data / "manifest.json").read_text())

    tables = build_model(data)
    tables_sql, constraints_sql = ddl(tables)
    (ROOT / "schema").mkdir(exist_ok=True)
    (ROOT / "schema" / "postgres.sql").write_text(tables_sql, encoding="utf-8")
    (ROOT / "schema" / "constraints.sql").write_text(constraints_sql, encoding="utf-8")
    (ROOT / "schema" / "views.sql").write_text(VIEWS_SQL, encoding="utf-8")

    child_count = sum(len(t["arrays_scalar"]) + len(t["arrays_object"]) for t in tables)
    print(f"schema/postgres.sql     {len(tables)} entity tables, {child_count} child "
          f"tables, plus i18n and views")
    print(f"schema/constraints.sql  keys and indexes, applied after the load")
    print(f"schema/views.sql        {VIEWS_SQL.count('CREATE VIEW')} convenience views")

    if args.sql_only:
        return 0
    out_dir = Path("build") / manifest["source_date"] / "sql"
    written = export_csv(tables, data, out_dir)
    total = sum(n for _, n in written)
    (ROOT / "schema" / "load.sql").write_text(load_script(written, out_dir),
                                              encoding="utf-8")
    print(f"{out_dir}  {len(written)} CSV files, {total:,} rows")
    print("schema/load.sql         psql \\copy script")
    return 0


if __name__ == "__main__":
    sys.exit(main())
