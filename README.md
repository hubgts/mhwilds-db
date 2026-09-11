# mhwilds-db

Turn the community datamining spreadsheet for **Monster Hunter Wilds** into a
clean, versioned, multilingual dataset: JSON files plus image assets, ready to
build application databases on.

The source is an 86 MB Google Sheet with 252 tabs, written for people to read.
This repository turns it into something programs can read, and keeps it honest
as the sheet changes with each game update.

A recreational, non-commercial project, built on top of
[someone else's very substantial work](docs/credits.md).

---

## Quick start

```bash
scripts/pipeline.sh --fetch
```

That is the whole thing: it downloads the current spreadsheet, produces `data/`,
and regenerates the SQL schema. About a minute, most of it the download.

Requirements: Python 3.11+ and PyYAML. Nothing else, and no database needed to
produce `data/`. See [docs/installation.md](docs/installation.md).

## What you get

```
data/
  README.md        generated: one line describing every file
  manifest.json    provenance: source file, date, row counts
  core/            items, skills, species, locales, sharpness, weapon types
  monsters/        registry, drops, hitzones, parts, crowns, turf wars
  weapons/         1,200 weapons, recipes, upgrade trees, kinsects, bowgun mods
  armor/           pieces, series, recipes, upgrades, layered armour
  charms/          decorations, talismans, pendants, RNG talisman tables
  artian/          Artian parts, bonuses, skill groups
  palico/          Palico series, armour, weapons, recipes
  world/           map zones, gimmicks, endemic life, fish
  economy/         crafting, shop, exchange, support ship, NPC trades
  progression/     missions, reward tables, medals, guild card, mantles
  i18n/            one file per language, keyed by GUID
  views/           the workbook's consultation grids, kept as grids
  reference/       engine enumerations
  assets/          1,104 PNG icons named after their entity
```

**91 entity files, 21,781 records, 13 languages, 16,523 translated strings,
1,104 images.** The JSON alone is 30 MB and diffs well; the images are 75 MB.

Start at `data/README.md`. It is generated from the build specs, so it lists
every file with a description and cannot fall out of step with reality.

```python
import json
items = json.load(open("data/core/items.json"))
fr    = json.load(open("data/i18n/french.json"))

potion = next(i for i in items if i["item_id"] == "ITEM_0000")
print(fr[potion["name_guid"]])          # Potion
print(fr[potion["description_guid"]])   # Restaure une petite quantité de vie.
```

## Documentation

| Page | Read it when |
|---|---|
| [installation.md](docs/installation.md) | setting up, checking requirements, disk space |
| [usage.md](docs/usage.md) | running the pipeline, each stage on its own, the tools |
| [usage-with-claude.md](docs/usage-with-claude.md) | using `/mhw-refresh` and `/mhw-contract`, and why the work is split |
| [data-model.md](docs/data-model.md) | reading a record, the keys, the translations, the images |
| [postgresql.md](docs/postgresql.md) | loading the relational version, the modelling choices, example queries |
| [validation.md](docs/validation.md) | what the two checks catch, and the contract |
| [extending.md](docs/extending.md) | adding a table, a join, a converter, a language |
| [source-workbook.md](docs/source-workbook.md) | the traps in the spreadsheet, and what is not usable |
| [credits.md](docs/credits.md) | who made the data, and what this project is |

## The pipeline

| Stage | Script | Input | Output |
|---|---|---|---|
| 1. Fetch | `fetch-mhw-sheet.sh` | Google Sheets | `rawdata/<date>.xlsx` |
| 2. Extract | `extract.py` | `rawdata/` | `build/<date>/` |
| 3. Validate | `validate.py` | `build/<date>/` | report, exit code |
| 4. Build | `build.py` | `build/<date>/` | `data/` |
| 5. Check | `check_output.py` | `data/` | report, exit code |
| 6. Schema | `schema.py` | `data/` | `schema/*.sql`, CSVs |

Each stage runs standalone; `scripts/pipeline.sh` chains them and stops at the
first failure.

Extraction is deliberately dumb: it renames nothing, converts nothing, resolves
no join, and keeps every column including the raw hexadecimal ones. That is what
lets it keep passing when the spreadsheet is reorganised upstream, which its
author has announced doing for the next expansion. All interpretation is
concentrated in `build.py`, which then fails at a named place.

Two independent checks guard the result: stage 3 validates the **source** against
a hand-written contract, stage 5 validates the **product** by resolving every key
inside `data/`. They catch different failures. See
[docs/validation.md](docs/validation.md).

## Loading into PostgreSQL

```bash
createdb mhw
psql -d mhw -f schema/postgres.sql      # 116 tables
psql -d mhw -f schema/load.sql          # 250,000 rows
psql -d mhw -f schema/constraints.sql   # keys and indexes
psql -d mhw -f schema/views.sql         # 8 convenience views
```

Generated from `data/` itself, so the schema cannot drift from the JSON.
Verified end to end on PostgreSQL 14; the load takes about a second and a half.
Details and example queries in [docs/postgresql.md](docs/postgresql.md).

## Credit

The data was extracted from the game and assembled, tab by tab, by the
**Monster Hunter Wilds datamining community**, who publish and maintain it as a
[public spreadsheet](https://docs.google.com/spreadsheets/d/178o8U97P2cpb0RZbZBvGIoX4bPhUm_lPczg6elfIj9s).
This repository is a format conversion on top of their work and is nothing
without it. **If you use this dataset, credit the spreadsheet and its
maintainers, not this repository.**

The underlying data belongs to Capcom; this project is unofficial, unaffiliated
and non-commercial. Full statement in [docs/credits.md](docs/credits.md).
