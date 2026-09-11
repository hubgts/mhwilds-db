#!/usr/bin/env python3
"""Low-level reader for a Google Sheets .xlsx export, no external dependencies.

Three services:
  Workbook.table(name)   -> (deduplicated headers, rows)
  Workbook.anchors(name) -> {(row, col): media path inside the archive}
  png_pixel_hash(bytes)  -> digest of the decoded pixels

The last one exists because Google re-encodes every PNG on each export: the
bytes change while the image is identical. Comparing decoded pixels avoids
rewriting 1,104 files on every rebuild.
"""
from __future__ import annotations

import hashlib
import re
import struct
import zlib
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_SD = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_RE_REL = re.compile(r'Id="(rId\d+)"[^>]*Target="([^"]+)"')
_RE_SHEET = re.compile(
    r'<sheet state="(\w+)" name="([^"]+)" sheetId="\d+" r:id="(rId\d+)"/>'
)
_RE_COL = re.compile(r"[A-Z]+")


def col_index(ref: str) -> int:
    """'AH12' -> 33 (zero-based column index)."""
    n = 0
    for ch in _RE_COL.match(ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _unescape(s: str) -> str:
    return (
        s.replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", '"').replace("&apos;", "'")
        .replace("&amp;", "&")
    )


class Workbook:
    def __init__(self, path):
        self.path = str(path)
        self._z = zipfile.ZipFile(self.path)
        self._names = set(self._z.namelist())
        self._strings = [
            "".join(t.text or "" for t in si.iter(NS + "t"))
            for si in ET.fromstring(self._z.read("xl/sharedStrings.xml"))
        ]
        rels = dict(_RE_REL.findall(self._z.read("xl/_rels/workbook.xml.rels").decode()))
        wb = self._z.read("xl/workbook.xml").decode()
        self.sheets = {}   # name -> worksheet path
        self.states = {}   # name -> visible | hidden
        for state, name, rid in _RE_SHEET.findall(wb):
            clean = _unescape(name)
            self.sheets[clean] = "xl/" + rels[rid]
            self.states[clean] = state

    # ------------------------------------------------------------------ cells

    def rows(self, sheet):
        """Yield (row number, positional list of str | None) for each row."""
        tree = ET.fromstring(self._z.read(self.sheets[sheet]))
        for row in tree.iter(NS + "row"):
            out = []
            for c in row.iter(NS + "c"):
                i = col_index(c.get("r"))
                while len(out) < i:
                    out.append(None)
                v = c.find(NS + "v")
                if v is None:
                    out.append(None)
                elif c.get("t") == "s":
                    out.append(self._strings[int(v.text)])
                else:
                    out.append(v.text)
            yield int(row.get("r")), out

    def table(self, sheet):
        """(headers, [(row number, cells)]) with deduplicated headers.

        64 sheets carry duplicate header names; we suffix __2, __3... so JSON
        keys stay unique, and name untitled columns _c<N>.
        """
        it = self.rows(sheet)
        try:
            _, raw = next(it)
        except StopIteration:
            return [], []
        seen, headers = {}, []
        for i, h in enumerate(raw):
            name = (h or "").strip() or f"_c{i}"
            seen[name] = seen.get(name, 0) + 1
            headers.append(name if seen[name] == 1 else f"{name}__{seen[name]}")
        return headers, list(it)

    def records(self, sheet):
        """Yield one dict per row, plus _row (row number within the sheet).

        Empty cells and empty strings both become None: the workbook does not
        distinguish them and carrying both would invent a difference.
        """
        headers, data = self.table(sheet)
        for rownum, cells in data:
            rec = {"_row": rownum}
            for i, h in enumerate(headers):
                val = cells[i] if i < len(cells) else None
                rec[h] = val if val != "" else None
            yield rec

    def row_count(self, sheet):
        return self._z.read(self.sheets[sheet]).count(b"<row ")

    # ----------------------------------------------------------------- images

    def anchors(self, sheet):
        """{(row, col) one-based: media path} for every anchored image.

        This is the only reliable link between an image and an entity: the
        workbook's Icon columns are empty, and xl/media/imageNNN.png names are
        reassigned on every export.
        """
        rels_path = self.sheets[sheet].replace("worksheets/", "worksheets/_rels/") + ".rels"
        if rels_path not in self._names:
            return {}
        m = re.search(r'Target="([^"]*drawing\d+\.xml)"', self._z.read(rels_path).decode())
        if not m:
            return {}
        drawing = m.group(1).replace("../", "xl/")
        drels_path = drawing.replace("xl/drawings/", "xl/drawings/_rels/") + ".rels"
        if drels_path not in self._names:
            return {}
        drels = dict(_RE_REL.findall(self._z.read(drels_path).decode()))
        out = {}
        for anchor in ET.fromstring(self._z.read(drawing)):
            frm = anchor.find(NS_SD + "from")
            if frm is None:
                continue
            blip = next(anchor.iter(NS_A + "blip"), None)
            if blip is None:
                continue
            target = drels.get(blip.get(NS_R + "embed"))
            if not target:
                continue
            row = int(frm.find(NS_SD + "row").text) + 1
            col = int(frm.find(NS_SD + "col").text) + 1
            out[(row, col)] = "xl/" + target.replace("../", "")
        return out

    @property
    def strings(self):
        """The shared string table, in workbook order."""
        return self._strings

    def read(self, member):
        return self._z.read(member)

    @property
    def media(self):
        return sorted(n for n in self._names if n.startswith("xl/media/"))


# ------------------------------------------------------------------------ PNG

_PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def png_pixel_hash(data: bytes) -> str:
    """Digest of the decoded pixels, immune to encoder differences.

    Falls back to a digest of the raw bytes when the image is interlaced or
    cannot be decoded, which degrades to a plain byte comparison.
    """
    i, idat, ihdr = 8, [], None
    while i < len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        kind = data[i + 4 : i + 8]
        if kind == b"IHDR":
            ihdr = data[i + 8 : i + 8 + length]
        elif kind == b"IDAT":
            idat.append(data[i + 8 : i + 8 + length])
        i += 12 + length
    if ihdr is None or not idat or ihdr[12] != 0:
        return "raw:" + hashlib.sha256(data).hexdigest()

    width, height, depth, ctype = struct.unpack(">IIBB", ihdr[:10])
    channels = _PNG_CHANNELS.get(ctype)
    if channels is None:
        return "raw:" + hashlib.sha256(data).hexdigest()
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error:
        return "raw:" + hashlib.sha256(data).hexdigest()

    bpp = max(1, channels * depth // 8)
    stride = (width * channels * depth + 7) // 8
    digest = hashlib.sha256(struct.pack(">IIBB", width, height, depth, ctype))
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        if pos >= len(raw):
            break
        filt = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if filt == 1:
            for k in range(bpp, stride):
                line[k] = (line[k] + line[k - bpp]) & 255
        elif filt == 2:
            for k in range(stride):
                line[k] = (line[k] + prev[k]) & 255
        elif filt == 3:
            for k in range(stride):
                left = line[k - bpp] if k >= bpp else 0
                line[k] = (line[k] + ((left + prev[k]) >> 1)) & 255
        elif filt == 4:
            for k in range(stride):
                a = line[k - bpp] if k >= bpp else 0
                c = prev[k - bpp] if k >= bpp else 0
                b = prev[k]
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[k] = (line[k] + pred) & 255
        digest.update(line)
        prev = line
    return "px:" + digest.hexdigest()


def write_if_changed(target, data: bytes, digest: str = None) -> bool:
    """Write data unless the image already there has the same pixels.

    Identical bytes are checked first, which is the common case on a rebuild
    from the same export and skips the decode entirely. Only when the bytes
    differ, because Google re-encoded the PNG, do we pay for the pixel compare.
    """
    target = Path(target)
    if target.exists():
        existing = target.read_bytes()
        if existing == data:
            return False
        if png_pixel_hash(existing) == (digest or png_pixel_hash(data)):
            return False
    target.write_bytes(data)
    return True


def slug(name: str, sep: str = "-") -> str:
    """Sheet or field name -> safe, stable identifier.

    Used for file names (sep="-") and for SQL columns (sep="_"). Both must
    agree on the character class, since an asset path and the column holding
    it are produced by the same rule.
    """
    s = name.strip().lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", sep, s)
    return re.sub(re.escape(sep) + "+", sep, s).strip(sep) or "sheet"
