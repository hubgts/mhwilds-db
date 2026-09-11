# The two checks

The pipeline validates twice, at two different moments, against two different
things. Both matter, and neither catches what the other does.

| | Stage | Checks | Declared in |
|---|---|---|---|
| `validate.py` | 3 | the **source**: does the workbook still have the shape we expect | `schema/contract.yaml` |
| `check_output.py` | 5 | the **product**: do the identifiers in `data/` resolve inside `data/` | Python dicts in the script |

Plus a third, lighter guard inside the build itself.

## Why two

A join can be perfect in the workbook and still be broken in the output.

That is not hypothetical: `core/skills.skill_id` once carried
`HunterSkill_000 (Attack Boost)` while the files meant to join to it carried
`HunterSkill_000`. The source join was at 100%. Stage 3 was happy. 112 records
pointed at nothing, and only stage 5 saw it.

The reverse also happens: a column renamed upstream breaks the source join long
before anything reaches `data/`, and stopping at stage 3 saves building a broken
dataset at all.

## Stage 3: the contract

`schema/contract.yaml` is **not generated**. It encodes an analysis: which of
the workbook's many possible joins actually carry the database, and below what
coverage a drop is an incident rather than noise.

It declares four things:

**Load-bearing sheets** — 36 of them, with a minimum row count and the columns
that must exist. A missing sheet or column stops the pipeline.

**Joins** — 32, each with a child column, a parent column, an optional
transform, and a `min_coverage`. Coverage is measured on distinct values.

```yaml
  - id: monster_drops.item
    child:  {sheet: Monster Drops, column: Item ID, transform: int_from_float}
    parent: {sheet: ItemData, column: Column 2, transform: hex_to_dec}
    min_coverage: 0.99
```

**`non_empty`** — columns that must hold values. This is the guard against the
worst case: a column goes empty upstream and an amputated database ships without
any join reporting an error.

**`known_empty`** — columns known to be empty today, because their formulas point
at deleted tabs. If one fills up again the validator says so *without* failing,
because that is good news to fold into the build.

### Inventory drift

`schema/inventory.json` is the contract's opposite: the mechanical list of every
sheet and column, regenerated on each extraction. Its diff is the drift report.

- A sheet or column **added**: reported, absorbed, the pipeline continues.
  `validate.py --accept-inventory` writes the new shape as the baseline, once you
  have read the list.
- A load-bearing column **disappearing**, a coverage **collapsing**, a column
  **going empty**: the pipeline stops.

### The rule that makes it worth anything

**A contract line is only corrected after re-measuring the join on the new
file.** Copy it from whatever the extraction found and the contract becomes a
transcript of the present, which catches nothing.

Concretely: never lower a `min_coverage` to make a check pass. If orphan rows
appeared at the source, exclude them by name with `exclude_rows` and say why in a
dated comment. The threshold has to stay high for a real regression to show.

`/mhw-contract` walks through the procedure; [extending.md](extending.md) has
the measurement snippet.

## Stage 5: the product

`check_output.py` declares what must hold inside `data/`:

- **10 primary keys** — unique and non-null;
- **55 foreign keys** — resolvable, including dotted paths that walk one level
  into a list of objects (`materials.item_data_id`);
- **2 composite keys** — `weapons` is keyed by the pair `(weapon_type, id)`;
- **every text GUID** present in `i18n/_index.json`.

67 declared, 64 of which are expected to hold outright; the other three are the
known dangling references below. `scripts/schema.py` reads the same declarations to emit
the PostgreSQL keys, so declaring a key once gives you the check and the
constraint.

### The six expected warnings

These are dangling references in the source itself, listed in the script's
`ACCEPTED` dict with the reason. Anything not listed is a real regression.

| Warning | Why |
|---|---|
| `slinger_ammo.item_data_id` → 1 orphan (185) | the SLEEP entry points at an item absent from `ItemData` |
| `armor.series` → 1 orphan (`ID_000`) | a placeholder series with no definition |
| `weak_points.link_parts_guid` → 1 orphan | links to a part row the workbook does not carry |
| `multi_parts.link_parts_guid` → 2 orphans | same |
| `gimmick_texts.gimmick_id` → 20 orphans | the text sheet covers ids the data sheet does not list |
| 937 of 15,806 GUIDs have no English string | the entry exists, the workbook leaves it blank |

## Inside the build

Two lighter guards, printed as warnings at the end of stage 4:

**A field mapping that converts nothing.** If a declared field converts fewer
than half of its non-empty source values, the column changed shape upstream.
This caught `Rarity` holding `"RARE0 (1)"` where an integer was expected, across
three files and 878 rows that would have shipped null.

Measured only over the rows the spec keeps, since a sheet whose broken rows are
dropped by `require` would otherwise drag every other column under the
threshold.

**A produced column that is null on every row.** Different failure, same
silence: the mapping works but the source column is empty. This is how the
missing talisman skills and kinsect materials were found.

## The views

The eight PostgreSQL views in `schema/views.sql` are hand-written and therefore
outside everything above: `check_output.py` never sees them, and a join on the
wrong column returns fewer rows rather than an error.

They carry their own guard, a `DO` block at the end of `views.sql` asserting the
row count of each view against an independent expectation. It runs when you load
the file, and `psql` stops on failure. See
[postgresql.md](postgresql.md#the-cardinality-assertions).

## Proving a refactor changed nothing

The strongest check is not in the pipeline at all:

```bash
cp -r data /tmp/before
# ... change whatever you like, rebuild ...
python3 scripts/diff_data.py /tmp/before data
```

`no change between the two builds` is the only acceptable answer when the intent
was to refactor. The SQL files can be compared with plain `diff`.
