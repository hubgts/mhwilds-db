# Credit, and what this project is

## Credit where it is due

None of this data was produced here. It was extracted from the game files and
assembled, tab by tab, by the **Monster Hunter Wilds datamining community**, who
publish and maintain it as a public spreadsheet:

<https://docs.google.com/spreadsheets/d/178o8U97P2cpb0RZbZBvGIoX4bPhUm_lPczg6elfIj9s>

252 tabs. 61,686 rows. 16,523 translated strings across 13 languages. 1,104
icons. Kept current through every title update, and reorganised by hand for each
expansion.

That is an enormous amount of patient, unpaid work, and this repository is
nothing without it. Everything here is a format conversion sitting on top of
their effort: the analysis, the extraction from the game, the cross-referencing,
the translation tables, all of that was already done.

**If you use this dataset, credit the spreadsheet and its maintainers, not this
repository.**

## Nature of this project

This is a **recreational, non-commercial project**. It exists because turning a
spreadsheet into a queryable database is a pleasant problem, and because fan
tools are more fun to build on clean data.

Nothing here is sold, monetised, advertised, or offered as a service, and there
is no intention to do so.

## Rights

The underlying data belongs to **Capcom**. Monster Hunter Wilds, its text, its
names and its icons are their intellectual property. This repository is not
affiliated with, endorsed by, sponsored by or connected to Capcom in any way,
and nothing here is official. Values may differ from the shipped game.

Neither the data nor the icons are ours to license, so **no licence is offered
over them**. If you build something public on top of this dataset, credit the
spreadsheet's authors, and work out for yourself where you stand on
redistributing game assets.

The scripts in this repository are a different matter. They are ordinary code
and you may do as you like with them.

## Traceability

`data/manifest.json` records exactly which export each build came from:

```json
{
 "source_file": "Monster Hunter Wilds 2026-09-10.xlsx",
 "source_date": "2026-09-10",
 "generated_at": "2026-09-10T18:23:54+02:00",
 "sheet_count": 252,
 "row_total": 61686
}
```

Every record also keeps `_row`, the row number in the source sheet. So any value
in `data/` can be traced back to a dated export and a specific spreadsheet cell,
which matters both for debugging and for being able to point at where something
came from.
