# The data model

`data/` is grouped by domain, one folder per area of the game. Start at
`data/README.md`: it is generated from the build specs and lists every file
with a one-line description, so it cannot fall out of step with what is
actually produced.

## Layout

| Folder | Files | What is in it |
|---|---:|---|
| `core/` | 10 | the registries everything else references |
| `monsters/` | 18 | registry plus drops, hitzones, parts, crowns, turf wars |
| `weapons/` | 13 | 1,200 weapons, recipes, upgrade trees, kinsects, bowgun mods |
| `armor/` | 8 | pieces, series, recipes, upgrades, layered armour |
| `charms/` | 6 | decorations, talismans, pendants, RNG talisman tables |
| `artian/` | 4 | Artian parts, bonuses, skill groups |
| `palico/` | 5 | Palico series, armour, weapons, recipes |
| `world/` | 5 | map zones, gimmicks, endemic life, fish |
| `economy/` | 9 | crafting, shop, exchange, support ship, NPC trades |
| `progression/` | 13 | missions, reward tables, medals, guild card, mantles |
| `i18n/` | 15 | one file per language, plus an index |
| `views/` | 17 | consultation grids from the workbook |
| `reference/` | 24 | engine enumerations |

91 entity files, 21,781 records, 1,104 image assets.

## Reading a record

Every record is a flat JSON object. Values are typed: integers are integers,
booleans are booleans, absent is `null`. Arrays hold either scalars or objects.

```json
{
 "data_id": 2,
 "item_id": "ITEM_0000",
 "name": "Potion",
 "description": "Restores a small amount of health.",
 "rarity": 1,
 "sell_price": 8,
 "buy_price": 66,
 "consumable": true,
 "name_guid": "bbf28943-461d-45a7-b621-508eec82cb54",
 "description_guid": "883bcb29-3eaa-4c00-bbd5-2959b453858f",
 "_row": 3
}
```

## Keys

Foreign keys use the game's own identifiers, never row ordinals.

| Key | Points at |
|---|---|
| `em_id` | `monsters/monsters.json`, field `em_id` |
| `item_data_id` | `core/items.json`, field `data_id` |
| `item_id` | `core/items.json`, field `item_id` (the `ITEM_xxxx` form) |
| `skill_id` | `core/skills.json`, field `skill_id` |
| `skill_key` | `core/skills.json`, field `engine_key` |
| `series` | `armor/series.json` or `palico/series.json` |
| `(weapon_type, id)` | `weapons/weapons.json` — a pair, not a single column |
| `mission_id` | `progression/missions.json` |
| `gimmick_id` | `world/gimmicks.json` |

`_row` is the row number in the source spreadsheet. It exists so a surprising
value can be traced back to its cell. **It is not a key** and is not stable
across game updates. In the PostgreSQL schema it is called `source_row`, and the
surrogate primary key there is `row_id`; a field named `id` in the JSON is always
the game's own identifier, never a row number.

Two kinds of field end in `_guid` and they are not interchangeable:

- `name_guid`, `description_guid`, `features_guid` and the other text GUIDs
  resolve in `i18n/`;
- `instance_guid`, `meat_guid`, `link_parts_guid`, `node_guid` identify a row
  inside the workbook's own arrays. They are what joins the monster part
  tables to each other.

`scripts/check_output.py` enforces all of this: 10 primary keys, 55 foreign
keys, 2 composite keys and every text GUID reference.

## Translations

The workbook's localisation tabs are translation tables keyed by GUID, and the
data sheets reference them through GUID columns. So entities carry a GUID
rather than a column per language.

```python
import json
items = json.load(open("data/core/items.json"))
fr    = json.load(open("data/i18n/french.json"))

potion = next(i for i in items if i["item_id"] == "ITEM_0000")
print(fr[potion["name_guid"]])          # Potion
print(fr[potion["description_guid"]])   # Restaure une petite quantité de vie.
```

13 languages: Japanese, English, French, Italian, German, Spanish, Russian,
Polish, Brazilian Portuguese, Korean, Traditional and Simplified Chinese,
Arabic. 16,523 GUIDs, about 15,100 strings per language.

`i18n/_index.json` says which workbook tab each GUID came from.
`i18n/_languages.json` lists the languages and their string counts.

About 6% of GUID references have no English string: the entry exists but the
workbook leaves it blank, mostly unused monster text. Fall back to the inline
English field, which is always present.

## The weapon upgrade tree

Three files describe weapons and they are not interchangeable:

- `weapons/weapons.json` — the weapons themselves, keyed by `(weapon_type, id)`.
- `weapons/tree_nodes.json` — each weapon's position: named `lineage`
  (Ore Tree, Bone Tree), `tier`, and `next_weapon_ids` / `previous_weapon_id`.
  **This is the authoritative upgrade graph**, taken from the workbook's own
  node table. 1,096 nodes, 43 lineages, every link resolves.
- `weapons/recipes.json` — what a weapon costs. Its `weapon_name` and
  `upgrades_from` come from a spreadsheet formula that is misaligned for the
  eight classes without a readable ID column, so do not use it for the graph.

## Images

1,104 PNG icons under `data/assets/`, named after their entity:

```
data/assets/medals/aw000.png
data/assets/monster-icons-large/e0006.png
data/assets/atlas/tex000201-1/r0003c05.png
```

Monsters carry `icon_large`, `icon_small`, `icon_map` and `icon_endemic`, each
either null or a path relative to `data/assets/`. 168 such links resolve.

`data/assets.json` maps every file back to its source sheet and cell.

Equipment and item icons live in the workbook's sprite atlases under
`assets/atlas/`, named by grid position because they carry no identifier at
all. See [source-workbook.md](source-workbook.md#equipment-icons) for why they
are deliberately left unlabelled.

## Views and reference

`views/` holds the workbook's consultation and layout sheets as grids
(`columns` plus `rows`), because the cell position carries the meaning: the
14 weapon tree renderings, two formula-driven lookup screens, and the
spreadsheet's own table of contents. They map to SQL views, not tables.

`reference/` holds the engine enumerations, useful for decoding a `Raw` column
the build does not yet expose.
