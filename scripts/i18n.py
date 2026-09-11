#!/usr/bin/env python3
"""Localisation layer.

Every .msg.23 sheet is a translation table with the same shape: a GUID, an
entry name, then one column per language. Data sheets reference those entries
through GUID columns (ItemData."Column 3" is the item's name, "Column 4" its
description), which is why entities here carry `name_guid` and
`description_guid` rather than an inlined English string.

Emitted as one file per language, `{guid: text}`, so a consumer loads only the
languages it needs and a Postgres import maps to translations(guid, lang, text).
"""
from __future__ import annotations

LANGUAGES = [
    "Japanese", "English", "French", "Italian", "German", "Spanish",
    "Russian", "Polish", "PortugueseBr", "Korean",
    "TraditionalChinese", "SimplifiedChinese", "Arabic",
]

# File name used for each language column.
FILENAME = {
    "Japanese": "japanese", "English": "english", "French": "french",
    "Italian": "italian", "German": "german", "Spanish": "spanish",
    "Russian": "russian", "Polish": "polish", "PortugueseBr": "portuguese_br",
    "Korean": "korean", "TraditionalChinese": "chinese_traditional",
    "SimplifiedChinese": "chinese_simplified", "Arabic": "arabic",
}


class Translations:
    """Index of every translated string in the workbook, keyed by GUID."""

    def __init__(self, src):
        self.by_lang = {lang: {} for lang in LANGUAGES}
        self.entries = {}
        self.sources = []
        for sheet in src.inventory["sheets"]:
            if not sheet.endswith(".msg.23"):
                continue
            count = 0
            for r in src.rows(sheet):
                guid = (r.get("guid") or "").lower()
                if not guid:
                    continue
                self.entries[guid] = {
                    "entry": r.get("entry name"),
                    "source": sheet,
                }
                for lang in LANGUAGES:
                    text = r.get(lang)
                    if text:
                        self.by_lang[lang][guid] = text
                count += 1
            if count:
                self.sources.append({"sheet": sheet, "entries": count})

    def norm(self, guid):
        """Normalise a GUID cell into the key used by the index."""
        if not guid:
            return None
        g = str(guid).strip().lower()
        return g if g in self.entries else None

    def text(self, guid, lang="English"):
        g = self.norm(guid)
        return self.by_lang[lang].get(g) if g else None

    @property
    def available(self):
        """Languages that actually carry text, in workbook order."""
        return [l for l in LANGUAGES if self.by_lang[l]]

    def write(self, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        import json
        written = {}
        for lang in self.available:
            path = out_dir / f"{FILENAME[lang]}.json"
            path.write_text(
                json.dumps(self.by_lang[lang], ensure_ascii=False, indent=0),
                encoding="utf-8",
            )
            written[FILENAME[lang]] = len(self.by_lang[lang])
        (out_dir / "_index.json").write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=0), encoding="utf-8"
        )
        (out_dir / "_languages.json").write_text(
            json.dumps(
                {
                    "languages": [
                        {"code": FILENAME[l], "column": l, "strings": len(self.by_lang[l])}
                        for l in self.available
                    ],
                    "sources": self.sources,
                    "total_guids": len(self.entries),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        return written
