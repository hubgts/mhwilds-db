#!/usr/bin/env bash
#
# Chain the MHW pipeline stages.
#
#   scripts/pipeline.sh              extract -> validate -> build -> check -> schema
#   scripts/pipeline.sh --fetch      fetch the workbook first
#   scripts/pipeline.sh --no-build   stop after validation
#
# Stops at the first failure. A failing validation is the normal outcome when
# the upstream sheet has been reorganised: that is not a bug in the pipeline,
# it is its job. The report says what to look at.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FETCH=0
BUILD=1
for arg in "$@"; do
  case "$arg" in
    --fetch)    FETCH=1 ;;
    --no-build) BUILD=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m-- %s\033[0m\n' "$1"; }

if [[ $FETCH -eq 1 ]]; then
  step "1/6  fetch"
  scripts/fetch-mhw-sheet.sh || {
    echo "Fetch failed, or today's file already exists." >&2
    echo "The pipeline continues on the latest file present in rawdata/." >&2
  }
fi

step "2/6  extract"
python3 scripts/extract.py

step "3/6  validate"
if ! python3 scripts/validate.py; then
  cat >&2 <<'MSG'

Validation failed. Do not edit the contract to make the check pass: first work
out what moved in the source sheet, re-measure the join concerned, and write
down only the measured figure.
MSG
  exit 1
fi

if [[ $BUILD -eq 0 ]]; then
  echo; echo "stopping after validation, as requested."
  exit 0
fi

step "4/6  build"
python3 scripts/build.py

step "5/6  check"
if ! python3 scripts/check_output.py; then
  cat >&2 <<'MSG'

The produced data/ is not internally consistent. This is a build problem, not a
source problem: an identifier written one way in one file and another way in
another. Fix scripts/build.py, do not relax the check.
MSG
  exit 1
fi

step "6/6  schema"
python3 scripts/schema.py

printf '\n\033[32mpipeline complete\033[0m, output in data/, SQL in schema/\n'
