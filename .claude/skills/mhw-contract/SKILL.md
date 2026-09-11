---
name: mhw-contract
description: Diagnose a validation failure in the Monster Hunter Wilds pipeline and update schema/contract.yaml after re-measuring. Use when validation fails, when a join loses coverage, when a load-bearing column disappears, when the user mentions "fix the contract", "validation is failing", "the data no longer lines up", or invokes /mhw-contract.
---

# Diagnose a drift in the workbook

The contract (`schema/contract.yaml`) encodes an analysis: which joins carry the
database, and below which threshold a drop is an incident. It exists to catch
one thing, that the source sheet changes under our feet without anyone noticing.

**The rule everything rests on: a contract line is corrected only after
re-measuring the join on the new file.** Copying what the extraction found turns
the contract into a transcript and destroys its function.

## Order of operations

**1. Read the report before touching the file.** `python3 scripts/validate.py`
gives, per join: the coverage obtained, the threshold, and some orphan values.
Those orphans are the entry point for the diagnosis.

**2. Tell the three possible causes apart.**

- *The column was renamed upstream.* The inventory shows it:
  `schema/inventory.json` lists the previous version's columns, and validation
  reports disappearances. Find the new name, confirm it carries the same data,
  update the contract.
- *Orphan rows appeared at the source.* Common: recipes pointing at weapons or
  items not yet in the dump. Do not lower the threshold. Drop those rows with
  `exclude_rows`, naming the column that identifies them. The threshold must
  stay high so a genuine regression remains visible.
- *The key is not what we thought.* The most dangerous case, because it does not
  necessarily show up as a failure. See below.

**3. Measure.** Load the workbook with `scripts/mhwlib.py`, compare value sets,
and note the percentage obtained.

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

**4. Check substance, not just the percentage.** Two dense integer columns join
at 99% almost every time while matching the wrong rows. Take three rows and ask
whether the result makes sense in the game: a Rathian carve must yield Rathian
materials, an early Great Sword must ask for ore. That is how the
`ItemData.Index` mistake was caught; the real key was `ItemData."Column 2"`, in
hexadecimal.

**5. Write the measured figure into the contract**, with a comment line saying
what changed and on what date. The contract is read as much for its history as
for its thresholds.

**6. Re-run** `scripts/pipeline.sh` to confirm, and check that the resulting
`data/` still makes sense.

## Inventory drift is not contract drift

An added sheet or column does not fail validation: it is reported, then absorbed
into `schema/inventory.json` with `validate.py --accept-inventory`. Use that
option once you have read the list of additions and it contains nothing touching
a load-bearing join.

## Never do this

Lower a `min_coverage` to make the check pass. Add a value to `ignore_values`
without looking at what it is. Remove an entry from `non_empty` because it
fails, which is precisely the signal that the database is about to be published
amputated.
