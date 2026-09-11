# Using this with Claude Code

The pipeline works entirely on its own; nothing here is required. What Claude
adds is the judgment half of the job, which is the half that actually costs
time when the spreadsheet changes shape.

## How the work is split

Running the pipeline is mechanical: launch six scripts, read the exit code.
Diagnosing *why* stage 3 failed is not, because it needs the context of the
analysis that produced the contract in the first place.

So the two are separated:

| | Model | What it does |
|---|---|---|
| `mhw-pipeline` agent | Sonnet | runs the scripts, reports faithfully, changes nothing |
| main session | Opus | diagnoses failures, re-measures joins, edits the contract |

The agent is explicitly forbidden from editing `schema/contract.yaml`, editing
the scripts, or re-running with `--force`. If it hits any of those cases it
hands the report back. That boundary is the point: an executor that "fixes" a
failing check by relaxing it destroys the only thing the check was for.

## The two commands

### `/mhw-refresh`

Refreshes the dataset. Spawns the Sonnet agent for the run, then interprets the
report:

- **pipeline completed** — reports the source date, per-entity counts, and how
  many assets were rewritten versus unchanged. A rebuild from an unchanged
  source must show 0 assets rewritten; anything else means the pixel comparison
  broke.
- **validation failed** — hands over to the diagnosis procedure below.
- **a `known_empty` warning** — a column the workbook had stopped resolving is
  filled again. Good news: the corresponding reconstruction in `build.py` can
  become a direct read. It reports it rather than acting unprompted.

### `/mhw-contract`

The diagnosis procedure for a failing validation. In order:

1. Read the report before touching anything. Orphan values are the entry point.
2. Tell the three causes apart: a column renamed upstream, orphan rows appearing
   at the source, or the key not being what we thought.
3. Measure. The skill carries a ready-made snippet using `scripts/mhwlib.py`.
4. **Check substance, not just the percentage.** Two dense integer columns join
   at 99% while matching the wrong rows every time. Resolve three rows and ask
   whether the result makes sense in the game.
5. Write the measured figure into the contract, with a dated comment.
6. Re-run the pipeline.

Step 4 is there because that exact mistake was made: the item join was first
written against `ItemData.Index` and reported 99.5% coverage while pairing
Rathian carves with Dash Extract. The real key was `ItemData."Column 2"`.

## Working without Claude

Everything above is a convenience. The equivalent by hand:

```bash
scripts/pipeline.sh --fetch          # instead of /mhw-refresh
python3 scripts/validate.py          # read the report yourself
$EDITOR schema/contract.yaml         # after measuring, per docs/extending.md
```

The contract, the checks and the generated `data/README.md` are all designed to
be read by a person. No step of the pipeline calls out to a model, and none of
the output depends on one.

## Where the files live

```
.claude/agents/mhw-pipeline.md      the Sonnet executor
.claude/skills/mhw-refresh/          the refresh entry point
.claude/skills/mhw-contract/         the diagnosis procedure
```

They are plain Markdown with YAML frontmatter. Read them; they document the
same reasoning as this page, at the point of use.
