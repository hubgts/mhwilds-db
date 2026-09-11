---
name: mhw-refresh
description: Update the Monster Hunter Wilds database from the Google Sheet by fetching the workbook, extracting, validating and rebuilding data/. Use when the user asks to "fetch / refresh / update the file", "get the new version of the xlsx", "rebuild the database", "regenerate the JSON", "check whether the sheet changed", or invokes /mhw-refresh.
---

# Refresh the Monster Hunter Wilds database

## How the work is split

Execution is mechanical, so it goes to the `mhw-pipeline` subagent, which runs
on Sonnet. Diagnosis stays here: it needs the context of the analysis that
produced the contract.

Launch the agent rather than the scripts:

```
Agent(subagent_type="mhw-pipeline",
      prompt="Run scripts/pipeline.sh --fetch and report the outcome.")
```

Drop `--fetch` to rebuild from the workbook already present. Wait for the
report; what follows depends on it.

## What to do with the report

**The pipeline completed.** Tell the user the source file date, the per-entity
counts, how many assets were rewritten versus unchanged, and whether the content
changed since the previous version. A rebuild with an unchanged source must show
0 assets rewritten. If it does not, the pixel comparison is broken and you must
say so.

**Validation failed.** This is the interesting case and it is yours to handle.
See [[mhw-contract]] for the diagnosis procedure. Do not re-run the agent, do not
work around it, and do not edit the contract without measuring first.

**A `known_empty` warning.** A column the workbook no longer resolved is filled
again. Good news: the matching reconstruction in `scripts/build.py` can be
replaced by a direct read. Report it, do not act on it unprompted.

## The file that must not be lost

`rawdata/Monster Hunter Wilds 2026-09-10.xlsx` was downloaded by hand from a
Google account holding comment rights: it carries 13 comment sets, discussion
threads and assigned tasks. The anonymous export used by the script does not
contain them and never will. Never delete that copy on the grounds that a newer
version exists.

## Two traps already hit

The workbook must **never** pass through Excel: 140,216 of its formulas use
Google Sheets specific functions, and only their cached value survives in the
export. Re-saving in Excel would destroy them.

High join coverage does not prove the key is right. The item join was first
written against `ItemData.Index`: 99.5% coverage and entirely wrong matches,
because both columns are dense integers. The real key is
`ItemData."Column 2"`. Faced with a new join, always check a few values on
substance, not just the percentage.
