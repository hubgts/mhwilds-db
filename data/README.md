# data

Generated from `Monster Hunter Wilds 2026-09-10.xlsx` on 2026-09-11.
Do not edit by hand: `scripts/build.py` overwrites this directory.

## How to read a file

Every record is a flat JSON object. Foreign keys use the game's own
identifiers, never row ordinals:

| Key | Points at |
|---|---|
| `em_id` | `monsters/monsters.json` |
| `item_data_id` | `core/items.json` (field `data_id`) |
| `item_id` | `core/items.json` (field `item_id`, the `ITEM_xxxx` form) |
| `skill_id` | `core/skills.json` |
| `series` | `armor/series.json` or `weapons/series.json` |
| `mission_id` | `progression/missions.json` |
| `name_guid`, `description_guid`, and the other text GUIDs | `i18n/<language>.json` |

`instance_guid`, `meat_guid` and `link_parts_guid` are different: they
identify a row inside the workbook's own arrays, not a translated string.
They join the monster part tables to each other.

`_row` is the row number in the source sheet, kept for tracing a value
back to the workbook. It is not a key.

## Translations

Text fields carry the English string inline for convenience, plus a
`*_guid` that resolves in every language. `i18n/<language>.json` maps
GUID to text; `i18n/_index.json` says which sheet each GUID came from.

| Language | Strings |
|---|---:|
| `japanese` | 15,167 |
| `english` | 15,135 |
| `french` | 15,133 |
| `italian` | 15,133 |
| `german` | 15,133 |
| `spanish` | 15,135 |
| `russian` | 15,133 |
| `polish` | 15,129 |
| `portuguese_br` | 15,133 |
| `korean` | 15,167 |
| `chinese_traditional` | 15,133 |
| `chinese_simplified` | 15,133 |
| `arabic` | 15,133 |

## Files

### core/

_core, the registries everything else references_

| File | Rows | Contents |
|---|---:|---|
| `core/colours.json` | 116 | Named colour presets referenced by icon and equipment tables. |
| `core/hunter_ranks.json` | 999 | Point threshold for each Hunter Rank. |
| `core/items.json` | 782 | Every item in the game. `data_id` is the engine key that all other tables reference; `index` is only a row ordinal. |
| `core/locales.json` | 16 | The game's maps and hubs. |
| `core/sharpness.json` | 7 | Raw and elemental multipliers for each sharpness colour. |
| `core/skill_levels.json` | 443 | One row per skill level, carrying the effect values for that level. |
| `core/skills.json` | 218 | Skill definitions: one row per skill, independent of its level. `engine_key` is what `skill_key` fields elsewhere point at. |
| `core/species.json` | 22 | Monster species (Flying Wyvern, Brute Wyvern, and so on). |
| `core/weapon_attributes.json` | 10 | Elemental and status attribute enum used by weapons. |
| `core/weapon_types.json` | 14 | The 14 weapon classes and their raw-damage multiplier. |

### monsters/

_monsters_

| File | Rows | Contents |
|---|---:|---|
| `monsters/aggro.json` | 140 | Which monsters pick fights with which, and how the clash resolves. |
| `monsters/ailment_resistances.json` | 51 | Resistance value per monster and per status, trap or flash. |
| `monsters/appearances.json` | 19 | Which monsters can appear on each map, and how many at once. |
| `monsters/crown_chances.json` | 90 | Size thresholds and odds for mini, gold and king crowns. |
| `monsters/drops.json` | 1,988 | Every reward table: carves, target rewards, broken parts, wounds, with quantity and probability. |
| `monsters/hitzones.json` | 433 | Damage multipliers per hitzone: cut, blunt, shot and the five elements. |
| `monsters/monsters.json` | 211 | The monster registry, with the detail sheets folded in. `variants` holds the frenzied and tempered names. |
| `monsters/multi_parts.json` | 542 | Parts that exist in several instances (each wing, each leg) and their links. |
| `monsters/part_breaks.json` | 148 | Break and sever conditions per monster part. |
| `monsters/part_params.json` | 51 | Per-monster scar thresholds and base part health. |
| `monsters/part_types.json` | 108 | Catalogue of body-part types (head, wing, tail) shared by all monsters. |
| `monsters/parts.json` | 385 | Body parts per monster, with health and kinsect extract. |
| `monsters/quest_rewards.json` | 148 | Guild points, HR points, Palico xp and zenny per monster and quest tier. |
| `monsters/scar_points.json` | 280 | Scar (wound) points, their health pools and sizes. |
| `monsters/special_attack_types.json` | 29 | Enum of special-attack categories used by the field guide. |
| `monsters/special_attacks.json` | 26 | Named special attacks referenced by the monster field guide. |
| `monsters/turf_wars.json` | 46 | Turf war pairings and the damage each side takes. |
| `monsters/weak_points.json` | 81 | Wound-able weak points and the hitzone each one links to. |

### weapons/

_weapons_

| File | Rows | Contents |
|---|---:|---|
| `weapons/bow_coatings.json` | 8 | Bow coating enum. |
| `weapons/bowgun_ammo_types.json` | 20 | Ammo type enum for both bowguns. |
| `weapons/bowgun_mod_patterns.json` | 166 | Which mods each bowgun mod slot pattern allows. |
| `weapons/bowgun_mods.json` | 15 | Bowgun customisation parts and their effect values. |
| `weapons/hunting_horn_melodies.json` | 114 | Note sequence that triggers each hunting horn melody. |
| `weapons/hunting_horn_notes.json` | 24 | Which notes each hunting horn type carries. |
| `weapons/kinsect_recipes.json` | 21 | Kinsect crafting and upgrade recipes. |
| `weapons/kinsects.json` | 21 | Insect Glaive kinsects and their stats. |
| `weapons/recipes.json` | 1,098 | Weapon crafting and upgrade recipes. Note: `weapon_name` and `upgrades_from` come from a workbook formula that is misaligned for the eight classes without an ID column, so use weapons/tree_nodes.json for the upgrade graph. |
| `weapons/recommendations.json` | 42 | Weapons the game suggests at each point of the story. |
| `weapons/series.json` | 45 | Weapon series (the tree a weapon belongs to). |
| `weapons/tree_nodes.json` | 1,096 | Position of every weapon in its upgrade tree: named lineage, tier, and the links to the next and previous weapons. |
| `weapons/weapons.json` | 1,200 | All 1,200 weapons across the 14 classes, with sharpness and skills. Key is (weapon_type, id). Eight of the sheets hide that id in a raw hex column; it is recovered here. |

### armor/

_armour_

| File | Rows | Contents |
|---|---:|---|
| `armor/armor.json` | 719 | Every armour piece with its defences, slots and skills. |
| `armor/layered.json` | 612 | Layered (cosmetic) armour pieces, with separate male and female names. |
| `armor/recipes.json` | 714 | Armour crafting recipes, keyed by (series, part). |
| `armor/recommendations.json` | 61 | Armour the game suggests at each point of the story. |
| `armor/series.json` | 195 | Armour series, the pivot that pieces and recipes hang off. |
| `armor/sp_upgrade_costs.json` | 4 | Cost of a special upgrade, by rarity. |
| `armor/upgrade_recipes.json` | 151 | Materials needed to upgrade an armour series. |
| `armor/upgrades.json` | 92 | Defence gained and cost per upgrade level, by rarity. |

### charms/

_decorations, talismans, pendants_

| File | Rows | Contents |
|---|---:|---|
| `charms/decorations.json` | 361 | Decorations, their level, slot size and skills. |
| `charms/pendants.json` | 115 | Weapon pendants (cosmetic charms hung on the weapon). |
| `charms/rng_talisman_skills.json` | 288 | Per-skill odds of appearing on a randomly generated talisman. Skill rebuilt from hex. |
| `charms/rng_talismans.json` | 124 | Randomly generated talismans: rarity, skill groups and slot presets. |
| `charms/talisman_recipes.json` | 179 | Talisman crafting recipes. |
| `charms/talismans.json` | 185 | Fixed talismans and the skills they grant. |

### artian/

_Artian weapons_

| File | Rows | Contents |
|---|---:|---|
| `artian/bonus_categories.json` | 4 | Probability and cap for each Artian reinforcement bonus category. |
| `artian/focus_types.json` | 3 | Gogmazios focus types and the weapon classes each one applies to. |
| `artian/parts.json` | 8 | Artian weapon components and which weapon classes accept them. |
| `artian/skill_groups.json` | 294 | Series and group skills an Artian weapon can roll. Both rebuilt from hex. |

### palico/

_Palico gear_

| File | Rows | Contents |
|---|---:|---|
| `palico/armor.json` | 169 | Palico armour pieces. |
| `palico/layered_armor.json` | 184 | Palico layered (cosmetic) armour. |
| `palico/recipes.json` | 236 | Palico gear recipes, rebuilt from the hex columns. |
| `palico/series.json` | 89 | Palico equipment series. `rejected` marks the workbook's unused rows. |
| `palico/weapons.json` | 73 | Palico weapons, melee and ranged. |

### world/

_maps, gathering, wildlife_

| File | Rows | Contents |
|---|---:|---|
| `world/endemic_life.json` | 71 | Endemic creatures, where they live and what they are worth. |
| `world/fish.json` | 20 | Fishable species, their sizes and the lure that works best. |
| `world/gimmick_texts.json` | 529 | Display name and description for each gimmick. |
| `world/gimmicks.json` | 573 | Interactive map objects: gathering points, traps, environmental features. |
| `world/zones.json` | 176 | Area subdivisions of each map, with temperature and environment type. |

### economy/

_shops, crafting, trades_

| File | Rows | Contents |
|---|---:|---|
| `economy/auto_use_items.json` | 32 | Which item the quick-heal and quick-cure shortcuts pick. |
| `economy/exchange.json` | 7 | Ticket exchanges: pay one item, receive another. |
| `economy/fixed_items.json` | 15 | Items granted permanently by story progress. |
| `economy/ingredients.json` | 16 | Meal ingredients and the buffs they contribute. Item rebuilt from hex. |
| `economy/item_recipes.json` | 66 | Item combining recipes. |
| `economy/npc_trades.json` | 80 | Field NPC trades: item requested against rewards, rebuilt from the hex columns. |
| `economy/shop.json` | 26 | What the provisions stockpile sells. |
| `economy/slinger_ammo.json` | 42 | Slinger ammo types mapped to their item. |
| `economy/support_ship.json` | 66 | Support ship stock, points cost and restock rate. |

### progression/

_quests, rewards, guild card_

| File | Rows | Contents |
|---|---:|---|
| `progression/dlc.json` | 271 | Downloadable content entries and their store codes. |
| `progression/highlights.json` | 30 | End-of-quest hunter highlight awards. |
| `progression/hunt_order.json` | 61 | Story order in which monsters are introduced. |
| `progression/mantles.json` | 4 | Hunter mantles (specialised tools). |
| `progression/medals.json` | 50 | Medals and their unlock condition. |
| `progression/mission_reward_tables.json` | 148 | Which reward tables each mission draws from. |
| `progression/mission_rewards.json` | 1,421 | Contents of every quest reward table, with odds. Rebuilt from Item Raw. |
| `progression/missions.json` | 534 | Mission registry with names where the workbook supplies them. |
| `progression/name_plates.json` | 69 | Guild-card name plates and their unlock condition. |
| `progression/npcs.json` | 337 | Named non-player characters. |
| `progression/profile_backgrounds.json` | 22 | Guild-card backgrounds and how each is unlocked. |
| `progression/title_conjunctions.json` | 123 | Adjectives available for the hunter's title. |
| `progression/title_words.json` | 859 | Nouns available for the hunter's title, with unlock conditions. |

### views/

_Consultation and layout sheets. These are grids, not entities: the cell
position carries the meaning. They map to SQL views, not tables._

| File | Contents |
|---|---|
| `views/bow-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/charge-blade-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/contents.json` | The workbook's own table of contents, as laid out by its authors. |
| `views/dual-blades-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/great-sword-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/gunlance-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/hammer-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/heavy-bowgun-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/hunting-horn-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/insect-glaive-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/lance-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/light-bowgun-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/long-sword-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/monster-drop-viewer.json` | Formula-driven lookup UI for drop tables. The underlying data is in monsters/drops.json. |
| `views/monster-hit-zone-viewer.json` | Formula-driven lookup UI: pick a monster, read its hitzones. Kept as a grid; the underlying data is in monsters/hitzones.json. |
| `views/switch-axe-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |
| `views/sword-and-shield-weapon-tree.json` | Layout grid of the in-game weapon tree. The usable relation is `upgrades_from` in weapons/recipes.json. |

### reference/

_Engine enumerations. Useful for decoding a `Raw` column the build
does not yet expose._

| File | Contents |
|---|---|
| `reference/appdef.json` | Application-level enums. |
| `reference/area-id-enum.json` | Map area enum. |
| `reference/armordef.json` | Engine enums for armour parts and slots. |
| `reference/colorpreset.json` | Colour preset enum referenced by icons. |
| `reference/decoration-enum.json` | Decoration enum. |
| `reference/em-ids.json` | Monster id registry in its raw form; monsters/monsters.json is the usable version. |
| `reference/enemydef.json` | Engine enums for monsters. |
| `reference/equipdef.json` | Engine enums shared by all equipment. |
| `reference/gimmick-ids.json` | Gimmick enum: id, value and fixed id. |
| `reference/hunterdef.json` | Engine enums for the hunter. |
| `reference/icondef.json` | Icon families: ITEM_, EQUIP_, SKILL_, MAP_ and so on. |
| `reference/itemdef.json` | Engine enums for items: type, group, rarity. |
| `reference/itemrecipedef.json` | Engine enums for item crafting. |
| `reference/mission-manage-ids.json` | Mission management enum. |
| `reference/missionidlist.json` | Raw mission id list. |
| `reference/questtimerank.json` | Quest completion time ranks. |
| `reference/storypackageflag.json` | Story progression flags. |
| `reference/supportshipdef.json` | Engine enums for the support ship. |
| `reference/talisman-type-enum.json` | Talisman type enum. |
| `reference/weapon-series-enum.json` | Weapon series enum. |
| `reference/weapondef.json` | Engine enums shared by all weapons. |
| `reference/wp05def.json` | Hunting horn specific enums. |
| `reference/wp07def.json` | Gunlance specific enums. |
| `reference/wp07shelllevel.json` | Gunlance shelling levels. |

### assets/

1,104 PNG icons named after their entity, for example
`assets/medals/aw000.png`. Icons that live in the workbook's sprite atlases
have no identifier at all, so they keep their grid position under
`assets/atlas/`. `assets.json` maps every file back to its source sheet
and cell.
