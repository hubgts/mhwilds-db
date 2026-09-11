# Usage

## The whole thing

```bash
scripts/pipeline.sh --fetch     # with a fresh download
scripts/pipeline.sh             # from the workbook already in rawdata/
scripts/pipeline.sh --no-build  # stop after validation, to inspect drift
```

Six stages, stopping at the first failure. Each is a standalone script, so you
can run them one at a time while debugging.

| Stage | Script | Input | Output | Time |
|---|---|---|---|---|
| 1. Fetch | `fetch-mhw-sheet.sh` | Google Sheets | `rawdata/<date>.xlsx` | ~45 s |
| 2. Extract | `extract.py` | `rawdata/` | `build/<date>/` | ~14 s |
| 3. Validate | `validate.py` | `build/<date>/` | report, exit code | ~3 s |
| 4. Build | `build.py` | `build/<date>/` | `data/` | ~2 s |
| 5. Check | `check_output.py` | `data/` | report, exit code | ~2 s |
| 6. Schema | `schema.py` | `data/` | `schema/*.sql`, CSVs | ~4 s |

## Stage 1, fetch

```bash
scripts/fetch-mhw-sheet.sh            # refuses to overwrite today's file
scripts/fetch-mhw-sheet.sh --force    # overwrite it
```

Writes `rawdata/Monster Hunter Wilds <YYYY-MM-DD>.xlsx` and repoints
`rawdata/latest.xlsx`. Validates that the download is a complete `.xlsx` before
keeping it, so a Google error page never lands in the archive. If a previous
export exists it prints a content comparison.

Environment: `MHW_RAW_DIR` changes the destination, `MHW_SHEET_ID` the source
spreadsheet.

## Stage 2, extract

```bash
python3 scripts/extract.py [--source rawdata/latest.xlsx] [--out build] [--skip-assets]
```

One JSONL file per sheet under `build/<date>/sheets/`, every column kept
including the raw hexadecimal ones, every value a string or null. Images are
resolved through their cell anchor and written to `build/<date>/assets/`.

This stage interprets nothing. That is what lets it keep passing when the
spreadsheet is reorganised upstream.

## Stage 3, validate

```bash
python3 scripts/validate.py [--build build/<date>] [--accept-inventory]
```

Checks the **source** against `schema/contract.yaml`: are the load-bearing
sheets and columns still there, do the 32 declared joins still resolve above
their thresholds, are the columns that must hold values still holding them.

Exit code 1 on any of those. A sheet or column merely *added* is reported and
absorbed; `--accept-inventory` writes the new shape into
`schema/inventory.json` once you have read the list of additions.

When it fails, read [../docs/source-workbook.md](source-workbook.md) and the
procedure in `/mhw-contract`. Do not edit the contract to make the check pass.

## Stage 4, build

```bash
python3 scripts/build.py [--build build/<date>] [--out data] [--skip-assets]
```

The opinionated stage: renames columns, converts types, resolves joins,
rebuilds the references the workbook lost, writes `data/` and generates
`data/README.md`.

It also prints a warning when a field mapping converts nothing or a produced
column is null on every row. Both mean a column changed shape upstream and are
worth the same attention as a validation failure, even though the build still
completes.

When the source date changes it first copies the previous `data/` to
`build/<old date>/data-snapshot/`, so the diff tool has something to compare
against.

## Stage 5, check

```bash
python3 scripts/check_output.py [--data data]
```

Checks the **product**: 10 primary keys unique and non-null, 55 foreign keys
resolvable, 2 composite keys, and every translation GUID present in `i18n/`.

Six warnings are expected and documented in the script: five dangling
references that exist in the source itself, and the GUIDs the workbook leaves
untranslated.

## Stage 6, schema

```bash
python3 scripts/schema.py [--data data] [--sql-only]
```

Generates `schema/postgres.sql`, `schema/constraints.sql`, `schema/views.sql`,
`schema/load.sql` and the CSV exports under `build/<date>/sql/`. See
[postgresql.md](postgresql.md).

## Comparing two versions

```bash
python3 scripts/diff_data.py build/2026-08-01/data-snapshot data
python3 scripts/diff_data.py OLD NEW --details
python3 scripts/diff_data.py OLD NEW --file monsters/monsters
```

Says what a game update actually changed, record by record:

```
core/items          +1     + Rathian Ruby
monsters/monsters   ~1     ~ Rathian: base_health 6900 -> 4500
i18n/french         ~1
```

## Comparing two workbook exports

```bash
python3 scripts/mhw_fingerprint.py rawdata/*.xlsx
```

Answers whether two exports carry the same content. Necessary because Google
regenerates the archive every time: two identical exports differ on most of
their bytes and even in file size, so a checksum is useless here.
