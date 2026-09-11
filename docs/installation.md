# Installation

## Requirements

| What | Why | Needed for |
|---|---|---|
| Python 3.11+ | the pipeline | everything |
| PyYAML | reads `schema/contract.yaml` | everything |
| `curl` | downloads the spreadsheet | stage 1 only |
| PostgreSQL client and server | loading the generated schema | optional |

Nothing else. No numpy, no pandas, no Pillow, no openpyxl: the `.xlsx` reader,
the PNG pixel hasher and the JSON writers are all standard library. That is
deliberate, so the pipeline keeps working years from now without a dependency
archaeology session.

```bash
python3 --version          # 3.11 or later
python3 -c "import yaml"   # must not raise
```

If PyYAML is missing:

```bash
pip install --user PyYAML
```

## First run

```bash
git clone <this repository>
cd mhwdb
scripts/pipeline.sh --fetch
```

About a minute, most of it the 86 MB download. When it finishes you have
`data/` and `schema/`.

Expect roughly:

```
252 sheets, 61,686 rows extracted
32 joins validated
91 entity files, 17 views, 24 reference files
13 languages, 16,523 translated strings
1,104 image assets
116 SQL tables
```

## Disk space

| Path | Size | Keep it? |
|---|---|---|
| `rawdata/` | 86 MB per export | yes, it is the archive |
| `build/` | 140 MB | no, fully derived |
| `data/` | 104 MB, of which 75 MB images and 20 MB translations | yes |
| `data/**/*.json` alone | 30 MB | yes, this is the part worth versioning |

`.gitignore` already excludes `rawdata/*.xlsx`, `build/` and `data/assets/`.
The entity JSON is small enough to version and diffs well; the images are not,
so use Git LFS or an attached release for those.

## Working without network access

Stage 1 is the only stage that touches the network. If you already have a
workbook in `rawdata/`, run the other five:

```bash
scripts/pipeline.sh
```

`rawdata/latest.xlsx` is a symlink to the most recent export; every script
defaults to it.

## Optional: PostgreSQL

Only needed if you want the relational version. See
[postgresql.md](postgresql.md). Producing `data/` does not require a database
at all.
