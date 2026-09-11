# Extending the pipeline

## Adding a table

Most output files are declared, not coded. Add a `Spec` to `scripts/specs.py`:

```python
Spec("world/campsites", "CampsiteData",
     "Camps per map and how each is unlocked.",
     {"index": ("Index", "int"),
      "locale": ("Locale", "str"),
      "name": ("Name", "str"),
      "unlocked_by": ("Story Flag", "str")},
     {"name_guid": "Name Raw"},
     "name"),
```

| Field | Meaning |
|---|---|
| 1st | output path under `data/`, without `.json` |
| 2nd | source sheet name, exactly as the workbook spells it |
| 3rd | one sentence; this becomes the line in `data/README.md` |
| 4th | `{output field: (source column, converter)}` |
| 5th | `{output field: GUID column}` for translated text |
| 6th | drop rows where this output field is null |

Then `python3 scripts/build.py`. The doc string lands in `data/README.md`
automatically, so a file cannot be added without being documented.

## Converters

| Name | Does |
|---|---|
| `str` | strip, empty becomes null |
| `str_dash` | same, and the workbook's `-` placeholder also becomes null |
| `int`, `float`, `bool` | typed, `"0"`/`"1"` for booleans |
| `hex` | `"00000218"` → `536`; zero becomes null, it is the engine's null |
| `paren_int` | `"RARE0 (1)"` → `1` |
| `code` | `"ITEM_0000 (Potion)"` → `"ITEM_0000"` |
| `code_label` | same, as `{"code": ..., "label": ...}` |
| `csv`, `lines` | split on commas or newlines into a list |
| `rejected` | true when the value carries the workbook's `#Rejected#` tag |

They live in `scripts/core.py` and are shared with `validate.py`, so a join is
measured the same way it is performed. Adding one there makes it available to
both.

## When a Spec is not enough

Anything needing real logic goes in `build.py` next to the other custom
builders, and gets registered in the `custom` dict in `main()` with its own doc
string. The cases that justify it:

- **merging sheets**, like `weapons/weapons` folding 14 sheets into one file;
- **resolving a reference the workbook lost**, using `item_ref()` or
  `skill_ref()` and the hex columns;
- **exploding a cell**, like `Monsters.Name` which packs up to three variants
  separated by newlines;
- **joining two sheets**, like `monsters/monsters` folding `Monsters` and
  `EnemyData` onto the `EM IDs` registry.

If your builder body is just `return project(rows, {...}, require, guids, tr)`,
it belongs in `specs.py` instead.

## Updating the contract

`schema/contract.yaml` is not generated. It encodes an analysis: which joins
carry the database, and below what coverage a drop is an incident.

**The rule: a contract line is only corrected after re-measuring the join on the
new file.** Copying it from whatever the extraction found turns it into a
transcript and destroys its purpose.

To measure:

```python
import sys; sys.path.insert(0, "scripts")
from mhwlib import Workbook
wb = Workbook("rawdata/latest.xlsx")

def vals(sheet, col):
    h, d = wb.table(sheet)
    i = h.index(col)
    return {c[i] for _, c in d if i < len(c) and c[i]}

child, parent = vals("Monster Drops", "Monster ID"), vals("EM IDs", "EM ID")
print(len(child - parent), "orphans out of", len(child))
```

Then **check the substance, not the percentage.** Two dense integer columns join
at 99% while matching entirely wrong rows. Resolve three values and ask whether
the result makes sense in the game: a Rathian carve must yield Rathian
materials, an early Great Sword must ask for ore.

### Adding a join

```yaml
  - id: campsites.locale
    child:  {sheet: CampsiteData, column: Locale}
    parent: {sheet: Locales, column: Name}
    min_coverage: 0.99
```

Available transforms: `identity`, `int_from_float`, `hex_to_dec`,
`split_newlines`, `split_commas`, `strip_paren`. Add `ignore_values` for
sentinel values the source uses, or `exclude_rows` to drop whole rows
identified by another column.

**Never lower a `min_coverage` to make a check pass.** If orphan rows appeared
at the source, exclude them by name with `exclude_rows` and say why in a
comment. The threshold has to stay high for a real regression to be visible.

## Adding an output-side key

`scripts/check_output.py` declares what must hold inside `data/`:

```python
PRIMARY_KEYS  = {"world/campsites": "name"}
FOREIGN_KEYS  = {("world/campsites", "locale"): ("core/locales", "name")}
```

Nested fields use dotted paths: `("weapons/recipes", "materials.item_data_id")`
walks one level into a list of objects. `COMPOSITE_KEYS` handles pairs.

`scripts/schema.py` reads the same declarations to emit the PostgreSQL keys, so
declaring a key once gives you both the check and the constraint.

## Adding a view or a reference table

In `build.py`:

- `VIEWS` maps a sheet name to its description, for consultation grids where
  the cell position carries the meaning;
- `REFERENCE` does the same for engine enumerations.

Both are dumped mechanically, no mapping needed.

## Adding a language

Nothing to do. `scripts/i18n.py` lists the language columns the workbook uses
and writes one file per language that carries text. A new column appears as a
new file.

## After any change

```bash
scripts/pipeline.sh
```

Stage 5 will tell you if a key you declared does not hold, and the build will
warn if a field mapping converts nothing. Before and after a refactor, prove
you changed nothing you did not mean to:

```bash
cp -r data /tmp/before
# ... make your change, rebuild ...
python3 scripts/diff_data.py /tmp/before data
```
