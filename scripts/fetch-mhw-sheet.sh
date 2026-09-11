#!/usr/bin/env bash
#
# Fetch the "Monster Hunter Wilds" Google Sheet as .xlsx into rawdata/,
# suffixed with today's date: "Monster Hunter Wilds YYYY-MM-DD.xlsx".
#
# Usage:
#   scripts/fetch-mhw-sheet.sh            download (refuses to overwrite)
#   scripts/fetch-mhw-sheet.sh --force    overwrite today's file
#
# Environment:
#   MHW_RAW_DIR     destination directory (default: <root>/rawdata)
#   MHW_SHEET_ID    Google Sheet id (default: this project's)

set -euo pipefail

SHEET_ID="${MHW_SHEET_ID:-178o8U97P2cpb0RZbZBvGIoX4bPhUm_lPczg6elfIj9s}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${MHW_RAW_DIR:-$ROOT/rawdata}"
BASENAME="Monster Hunter Wilds"
MIN_SIZE=$((10 * 1024 * 1024))   # a real export is ~86 MB; below that it is an error page

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

TODAY="$(date +%F)"
DEST="$RAW_DIR/$BASENAME $TODAY.xlsx"
URL="https://docs.google.com/spreadsheets/d/$SHEET_ID/export?format=xlsx"

mkdir -p "$RAW_DIR"

if [[ -e "$DEST" && $FORCE -eq 0 ]]; then
  echo "Today's file already exists: $DEST" >&2
  echo "Re-run with --force to overwrite it." >&2
  exit 1
fi

# Previous version (most recent, excluding today's) for comparison.
PREV=""
while IFS= read -r f; do
  [[ "$f" == "$DEST" ]] && continue
  PREV="$f"
done < <(find "$RAW_DIR" -maxdepth 1 -name "$BASENAME [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].xlsx" | sort)

TMP="$(mktemp "$RAW_DIR/.mhw-download.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

echo "Downloading from Google Sheets..."
HTTP_CODE="$(curl -sL --fail-with-body --max-time 600 -o "$TMP" -w '%{http_code}' "$URL")" || {
  echo "Download failed (HTTP $HTTP_CODE)." >&2
  exit 1
}

SIZE="$(stat -c %s "$TMP")"
if (( SIZE < MIN_SIZE )); then
  echo "Response too small ($SIZE bytes): Google most likely returned an error page." >&2
  echo "Check that the sheet is still shared with link-based read access." >&2
  exit 1
fi

# The archive must be a valid, complete .xlsx.
python3 - "$TMP" <<'PY' || { echo "The downloaded archive is invalid or truncated." >&2; exit 1; }
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
assert z.testzip() is None
z.read("xl/workbook.xml")
PY

chmod 644 "$TMP"
mv "$TMP" "$DEST"
trap - EXIT
ln -sfn "$(basename "$DEST")" "$RAW_DIR/latest.xlsx"

echo
echo "OK: $DEST"
echo "    $(numfmt --to=iec --suffix=B "$SIZE" 2>/dev/null || echo "$SIZE bytes")"
echo "    rawdata/latest.xlsx -> $(basename "$DEST")"

if [[ -n "$PREV" ]]; then
  echo
  echo "Comparison with the previous version:"
  python3 "$ROOT/scripts/mhw_fingerprint.py" "$PREV" "$DEST" || true
fi
