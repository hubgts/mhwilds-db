# The source workbook

Everything here comes from one public Google Sheet: 252 tabs, 61,686 rows,
16,523 translated strings, 1,104 embedded PNG icons, about 86 MB per export.

It was written for people to read, not for programs. These are the traps that
cost real debugging time. All of them are handled by the pipeline; this page is
for when you go back to the spreadsheet yourself, or when a validation failure
sends you looking.

## The item key is not `Index`

`ItemData` carries two numeric columns that both look like an identifier.

| Column | What it is |
|---|---|
| `Index` | a row ordinal, 0 to 787 |
| `Column 2` | the engine's item id, in hexadecimal, unique across all 782 items |

Every other sheet references items by the second one. Both are dense integer
ranges, so **joining on `Index` reports 99.5% coverage while matching entirely
wrong rows**. Joined on `Index`, a Rathian carve yields "Dash Extract" and an
early Great Sword asks for an "Arkveld Calloushell".

The lesson generalises: a coverage percentage validates that a key *exists*,
never that it is the *right* one. Resolve three rows and check the result makes
sense in the game.

## The ingredient columns are empty

The workbook's readable columns are formulas. Some of them reference tabs named
`Items!`, `Skills!`, `Lances!`, `Hammers!` and `Gunlances!` that have since been
renamed, and every formula is wrapped in an `iferror`, so the failure is
**silent**: the column returns an empty string rather than an error.

The affected columns are, precisely, every place a recipe states what it needs:

| Sheet | Empty columns |
|---|---|
| `Weapon Recipes` | Key Item, Item 1 to 4 |
| `Palico Equipment Recipes` | Key Item, Item 1 to 4, Number 1 to 4 |
| `Kinsect Recipes` | Item 1 to 4 |
| `Talisman Recipes` | Key Item, Item 1 to 4 |
| `NPC Trades` | Requested Item, Rewarded Item 1 to 3 |
| `Mission Common Reward Data` | Item (reads `#REF!` on all 1,421 rows) |
| `Decorations` | Skill 1, Skill 2 |
| `Talismans` | Skill 1 to 3 |
| `Monster Drops` | Item (the name; the identifier still works) |
| all sheets | every `Icon` column |

The raw data is intact in the `Raw` columns, and the relation is a hexadecimal
conversion. `build.py` rebuilds all of them and resolves 100%.

```python
by_item_id = {int(row["Column 2"], 16): row for row in item_data}

raw = recipe["Item 1 Raw"]            # "00000218"
if raw and int(raw, 16) != 0:         # zero is the engine's null
    item = by_item_id[int(raw, 16)]   # 536 -> "Rathian Webbing"
```

`schema/contract.yaml` lists these as `known_empty`: if one ever fills up again,
the validator says so without failing, because that is good news to fold in.

## Eight weapon sheets hide their id

Only six of the fourteen weapon sheets expose a readable `ID` column. The other
eight carry it in the shared raw block, which holds one id column per weapon
class in the same order as the `Weapon Recipes` header:

| Sheet | Class | Column |
|---|---|---|
| `LongSword` | Great Sword | Column 5 |
| `ShortSword` | Sword & Shield | Column 6 |
| `TwinSword` | Dual Blades | Column 7 |
| `Tachi` | Long Sword | Column 8 |
| `Hammer` | Hammer | Column 9 |
| `Whistle` | Hunting Horn | Column 10 |
| `Lance` | Lance | Column 11 |
| `GunLance` | Gunlance | Column 12 |

Note the sheet names: the workbook uses the Japanese internal names, so
`LongSword` is the Great Sword and `Tachi` is the Long Sword.

With those columns the upgrade tree resolves 100% for all fourteen classes.

## The weapon recipe names are misaligned

For those same eight classes, `Weapon Recipes.Name` and
`Weapon Recipes.Uprades From` (the typo is the source's) are produced by a
`switch(Type, ...)` array formula whose alignment cannot be verified: neither the
name nor the id retrieves the prerequisite the tree reports.

Use `weapons/tree_nodes.json` for the upgrade graph. It comes from the tree
sheets' own node table, not from a formula.

## Monster names pack several variants

`Monsters.Name` holds up to three names in one cell, separated by newlines:

```
"Yian Kut-Ku\nFrenzied Yian Kut-Ku\nTempered Yian Kut-Ku"
```

Four of the five monster child tables join by name, not by id. Until that cell
is exploded, `Turf War` drops to 0% coverage and `Monster Crown Chances` to
6.7%. Split on `\n` and all four return to 98–100%.

Also note that `Monsters` is **not** the monster registry: it holds 57 rows, the
large monsters given an in-game profile. The registry is `EM IDs`, 212 entries.

## Two conventions for the same reference

Some sheets write `Rathalos`, others `EM0002_00_0 (Rathalos)`, others again
`ITEM_0000 (Potion)` or `RARE0 (1)`. Normalise by extracting the code outside
the parentheses at ingestion, or the same join works in one direction and not
the other. That is what the `code` and `paren_int` converters are for.

## Image file names are not stable

Google reassigns `xl/media/imageNNN.png` on every export. Measured: out of the
50 `Medals` icons, **2 keep their name** between two exports, and 139 files
across the workbook have the same name for different dimensions.

The only reliable link between an image and an entity is the **cell anchor** in
the drawing XML. Resolved that way, the same image is pixel-identical across
exports (verified 50/50 and 20/20 on two samples).

The PNGs are also re-encoded each time, so the pipeline compares decoded pixels
rather than bytes: only genuinely changed images are rewritten.

## Equipment icons

657 of the 1,104 images live in sprite atlases (`tex000201_0`, `_1`, `_2`,
`_20`, `tex000225_1`): grids of icons whose tabs contain **no text at all**, not
one identifier.

Their composition can be inferred. The workbook's own contents page describes
them ("Item icons and facility icons", "Map icons, skill icons, monster icons
and equipment icons", "Status icons and endemic life icons", "Additional
icons", "Stage icons"), and the `IconDef` family sizes line up approximately:

| Atlas | Images | Plausible families | Sum |
|---|---:|---|---:|
| `tex000201_0` | 219 | ITEM 102 + FACILITY 123 | 225 |
| `tex000201_1` | 191 | MAP 63 + SKILL 15 + E 37 + S 20 + EQUIP 58 | 193 |
| `tex000201_2` | 191 | STATUS 104 + A 91 | 195 |
| `tex000201_20` | 40 | additional icons 43 | 43 |
| `tex000225_1` | 16 | STAGE 17 | 17 |

But the counts are off by a few every time, and **no atlas image is
pixel-identical to any labelled one**, so there is nothing to anchor the
alignment against. An off-by-one would mislabel all 657 silently.

They are therefore extracted under `assets/atlas/<sheet>/rNNNNcNN.png`, named by
grid position, and left unlabelled on purpose. Finishing this properly needs a
visual comparison against the game, not more inference.

Monster, endemic life, map and status icons **are** identified, through
`EnemyData`'s icon type columns and `IconDef`: 168 links that all point at files
that exist.

## Never open it in Excel

140,216 of the workbook's 399,786 formulas carry the `__xludf.DUMMYFUNCTION`
marker: Google Sheets specific functions such as `JOIN`, `FILTER` and
`CHOOSECOLS` that Excel cannot evaluate. Their cached value survives in the
export, so reading is fine. **Re-saving in Excel would destroy them.**

## A checksum will not tell you if it changed

Google regenerates the archive on every export. Two exports of identical content
differ on 1,381 of 2,086 archive members and even in total file size
(89,852,582 vs 89,824,728 bytes measured). The shared string table is reordered,
the PNGs re-encoded, the drawing ids renumbered.

Use `scripts/mhw_fingerprint.py`, which hashes the sorted strings, the sheet
list and the per-sheet row counts instead.

## What is not usable

Some tabs cannot be projected and are not oversights:

- `Sheet173`, `Sheet195`, `Sheet265`, `Sheet308`, `Sheet309`, `Sheet310` —
  working drafts with no headers;
- `ArmorSeriesData (Benchmark)`, `Palico Equipment Series (Benchmark)`,
  `Locale Zones OBT` — predictions from the demo and the open beta, superseded;
- the meal system — the contents page lists `FoodData`, `MealData`,
  `MealSkillData` and six others, but **those tabs do not exist** in the
  workbook. `Main Ingredients` and `Other Ingredients` are all there is, and
  without the meal tables they have no use on their own.

## One more thing

The workbook's own header says: *"With all of Monster Hunter Wilds' TUs now
released, I will be reorganizing this spreadsheet in preparation for the coming
expansion. STILL WIP"*.

That sentence is why the pipeline is built the way it is: extraction that
interprets nothing, a contract that fails loudly, and two independent checks.
The source is going to move.
