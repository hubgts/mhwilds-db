#!/usr/bin/env python3
"""Declarative description of every file produced in data/.

One Spec per output file. The `doc` field is what ends up in data/README.md,
so it is generated from here and can never go stale.

Field mapping is {output field: (source column, converter)}. Converters live in
build.py. `guids` maps an output field to the column holding a localisation
GUID; those resolve through data/i18n/ rather than being inlined.
"""
from dataclasses import dataclass, field


@dataclass
class Spec:
    out: str                    # path under data/, without .json
    sheet: str                  # source sheet name
    doc: str                    # one sentence, goes into data/README.md
    fields: dict                # output field -> (column, converter)
    guids: dict = field(default_factory=dict)   # output field -> GUID column
    require: str = None         # drop rows where this output field is null


# Shorthands for the two GUID layouts the workbook uses.
NAME_DESC = {"name_guid": "Name Raw", "description_guid": "Description Raw"}
NAME_ONLY = {"name_guid": "Name Raw"}

SPECS = [
    # ---------------------------------------------------------------- core
    Spec("core/items", "ItemData",
         "Every item in the game. `data_id` is the engine key that all other "
         "tables reference; `index` is only a row ordinal.",
         {"data_id": ("Column 2", "hex"), "index": ("Index", "int"),
          "item_id": ("Item ID", "code"), "name": ("Name", "str"),
          "description": ("Description", "str"), "type": ("Type", "str"),
          "rarity": ("Rarity", "paren_int"), "max_count": ("Max Count", "int"),
          "palico_max_count": ("Palico Max Count", "int"),
          "sell_price": ("Sell Price", "int"), "buy_price": ("Buy Price", "int"),
          "sort_id": ("Sort ID", "int"), "consumable": ("Consumable", "bool"),
          "healing": ("Healing Item", "bool"), "battle": ("Battle Item", "bool"),
          "infinite": ("Infinite", "bool"), "for_money": ("For Money", "bool")},
         {"name_guid": "Column 3", "description_guid": "Column 4"}, "data_id"),

    Spec("core/skills", "SkillCommonData",
         "Skill definitions: one row per skill, independent of its level. "
         "`engine_key` is what `skill_key` fields elsewhere point at.",
         {"index": ("Index", "int"), "engine_key": ("Column 2", "str"),
          "skill_id": ("Skill ID", "code"),
          "type": ("Skill Type", "str"), "category": ("Skill Category", "str"),
          "name": ("Name", "str"), "description": ("Description", "str"),
          "sort_id": ("Sort ID", "int")},
         {"name_guid": "Column 6", "description_guid": "Column 7"}, "skill_id"),

    Spec("core/skill_levels", "SkillData",
         "One row per skill level, carrying the effect values for that level.",
         {"index": ("Index", "int"), "data_id": ("Data ID", "str"),
          "skill_id": ("Skill ID", "code"), "level": ("Level", "int"),
          "name": ("Name", "str"), "description": ("Description", "str"),
          "values": ("Values", "str"), "unlocks": ("Open Skills", "str")},
         {"name_guid": "Column 5", "description_guid": "Column 6"}, "skill_id"),

    Spec("core/species", "Species",
         "Monster species (Flying Wyvern, Brute Wyvern, and so on).",
         {"index": ("Index", "int"), "code": ("Species", "str"),
          "name": ("Name", "str")}, NAME_ONLY, "name"),

    Spec("core/locales", "Locales",
         "The game's maps and hubs.",
         {"fixed_id": ("Fixed ID", "str"), "st_id": ("ST ID", "str"),
          "name": ("Name", "str")}, {}, "name"),

    Spec("core/colours", "Colours",
         "Named colour presets referenced by icon and equipment tables.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "colour_1": ("Colour 1", "str"), "colour_2": ("Colour 2", "str"),
          "colour_3": ("Colour 3", "str"), "colour_4": ("Colour 4", "str"),
          "alpha": ("Alpha", "str")}, {}, "id"),

    Spec("core/hunter_ranks", "Hunter Ranks",
         "Point threshold for each Hunter Rank.",
         {"index": ("Index", "int"), "rank": ("Rank", "int"),
          "points": ("Points", "int"), "cap": ("Cap Flag", "str")}, {}, "rank"),

    Spec("core/weapon_types", "Weapon Types",
         "The 14 weapon classes and their raw-damage multiplier.",
         {"index": ("Index", "int"), "sort_id": ("Sort ID", "int"),
          "internal_name": ("Internal Name", "str"), "name": ("Name", "str"),
          "multiplier": ("Multiplier", "float")}, {}, "name"),

    Spec("core/weapon_attributes", "Weapon Attributes",
         "Elemental and status attribute enum used by weapons.",
         {"index": ("Index", "int"), "id": ("ID", "str")}, {}, "id"),

    Spec("core/sharpness", "Sharpness",
         "Raw and elemental multipliers for each sharpness colour.",
         {"colour": ("Colour", "str"), "raw_multiplier": ("Raw Multiplier", "float"),
          "element_multiplier": ("Element Multiplier", "float")}, {}, "colour"),

    # ------------------------------------------------------------ monsters
    Spec("monsters/part_types", "Monster Parts",
         "Catalogue of body-part types (head, wing, tail) shared by all monsters.",
         {"index": ("Index", "int"), "fixed_id": ("Fixed ID", "str"),
          "name": ("Name", "str"), "rotten_name": ("Rotten Name", "str"),
          "description": ("Description", "str"), "icon_type": ("Icon Type", "str")},
         {"name_guid": "Name Raw", "rotten_name_guid": "Rotten Parts Name Raw",
          "description_guid": "Parts Description Raw"}, "index"),

    Spec("monsters/part_breaks", "Monster Parts Break Array",
         "Break and sever conditions per monster part.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "instance_guid": ("Instance GUID", "str"),
          "target_category": ("Target Category", "str"),
          "execute_count": ("Execute Count", "int"), "max_count": ("Max Count", "int"),
          "condition": ("Condition", "str"), "condition_count": ("Condition Count", "int"),
          "part_type": ("Parts Type", "str")}, {}, "em_id"),

    Spec("monsters/hitzones", "Monster Meat Array",
         "Damage multipliers per hitzone: cut, blunt, shot and the five elements.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "instance_guid": ("Instance GUID", "str"),
          "slash": ("Slash", "int"), "blow": ("Blow", "int"), "shot": ("Shot", "int"),
          "fire": ("Fire", "int"), "water": ("Water", "int"),
          "thunder": ("Thunder", "int"), "ice": ("Ice", "int"),
          "dragon": ("Dragon", "int"), "stun": ("Stun", "int"),
          "flash": ("Flash", "int")}, {}, "em_id"),

    Spec("monsters/weak_points", "Monster Weak Point Array",
         "Wound-able weak points and the hitzone each one links to.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "instance_guid": ("Instance GUID", "str"), "vital": ("Vital", "int"),
          "meat_guid": ("Meat GUID", "str"), "link_parts_guid": ("Link Parts GUID", "str"),
          "highlight_type": ("Highlight Effect Type", "str")}, {}, "em_id"),

    Spec("monsters/scar_points", "Monster Scar Point Array",
         "Scar (wound) points, their health pools and sizes.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "instance_guid": ("Instance GUID", "str"),
          "normal_vital": ("Normal Vital", "int"), "tear_vital": ("Tear Vital", "int"),
          "raw_scar_vital": ("Raw Scar Vital", "int"), "meat_guid": ("Meat GUID", "str"),
          "link_parts_guid": ("Link Parts GUID", "str"),
          "size_rate": ("Size Rate", "float"), "count": ("Num", "int")}, {}, "em_id"),

    Spec("monsters/multi_parts", "Monster Multi Parts Array",
         "Parts that exist in several instances (each wing, each leg) and their links.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "instance_guid": ("Instance GUID", "str"), "vital": ("Vital", "int"),
          "default_enable": ("Default Enable", "str"),
          "max_count": ("Max Count", "int"), "action": ("Action", "str"),
          "attribute": ("Attribute", "str"),
          "link_parts_guid": ("Link Parts GUID", "str")}, {}, "em_id"),

    Spec("monsters/part_params", "Monster Parts Param",
         "Per-monster scar thresholds and base part health.",
         {"em_id": ("Monster ID", "str"), "monster": ("Monster", "str"),
          "scar_standard_size": ("Scar Standard Size", "float"),
          "reaction_per": ("Reaction Per", "float"),
          "base_health": ("Base Health", "int"),
          "scar_pitfall_threshold": ("Scar Field Pitfall Threshold", "float"),
          "legendary_scar_pitfall_threshold":
              ("Legendary Scar Field Pitfall Threshold", "float")}, {}, "em_id"),

    Spec("monsters/special_attacks", "Monster Special Attacks",
         "Named special attacks referenced by the monster field guide.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "description": ("Description", "str")}, {}, "id"),

    Spec("monsters/special_attack_types", "EnemySpecialAttackTypes",
         "Enum of special-attack categories used by the field guide.",
         {"index": ("Index", "int"), "type": ("Special Attack Type", "str"),
          "name": ("Name", "str"), "description": ("Description", "str")}, {}, "type"),

    Spec("monsters/aggro", "Monster VS Monster Aggro",
         "Which monsters pick fights with which, and how the clash resolves.",
         {"instance_guid": ("Instance Guid", "str"),
          "first_monster": ("First Monster", "str"),
          "second_monster": ("Second Name", "str"),
          "combat_disabled": ("Is Disable Combat Em", "bool"),
          "attack_hit_type": ("Attack Hit Type", "str"),
          "interpretation": ("Interpretation", "str")}, {}, "first_monster"),

    Spec("monsters/appearances", "EnemyAppearanceStageData",
         "Which monsters can appear on each map, and how many at once.",
         {"locale": ("Locale", "str"), "monster_count": ("Number of Monsters", "int"),
          "monsters": ("Monsters", "str")}, {}, "locale"),

    # ------------------------------------------------------------- weapons
    Spec("weapons/series", "Weapon Series",
         "Weapon series (the tree a weapon belongs to).",
         {"fixed_id": ("Fixed ID", "str"), "index": ("Index", "int"),
          "enum": ("Enum", "str"), "name": ("Name", "str")}, NAME_ONLY, "index"),

    Spec("weapons/kinsects", "Kinsects",
         "Insect Glaive kinsects and their stats.",
         {"fixed_id": ("Fixed ID", "str"), "index": ("Index", "int"),
          "id": ("ID", "str"), "name": ("Name", "str"), "rarity": ("Rarity", "int"),
          "price": ("Price", "int"), "attack_type": ("Attack Type", "str"),
          "powder": ("Powder", "str"), "skill_type": ("Insect Skill Type", "str"),
          "attack": ("Attack", "str"), "move_speed": ("Move Speed", "str"),
          "recovery": ("Recovery Value", "str"),
          "powder_level": ("Powder Level", "str")}, NAME_ONLY, "name"),

    Spec("weapons/bowgun_ammo_types", "Bowgun Ammo Types",
         "Ammo type enum for both bowguns.",
         {"index": ("Index", "int"), "name": ("Name", "str")}, {}, "name"),

    Spec("weapons/bow_coatings", "Bow Coatings",
         "Bow coating enum.",
         {"index": ("Index", "int"), "name": ("Name", "str")}, {}, "name"),

    Spec("weapons/bowgun_mods", "Bowgun Mods",
         "Bowgun customisation parts and their effect values.",
         {"fixed_id": ("Fixed ID", "str"), "index": ("Index", "int"),
          "name": ("Name", "str"), "description": ("Description", "str"),
          "value_1": ("Value 1", "int"), "value_2": ("Value 2", "int")},
         NAME_DESC, "index"),

    Spec("weapons/bowgun_mod_patterns", "Bowgun Mod Patterns",
         "Which mods each bowgun mod slot pattern allows.",
         {"index": ("Index", "int"), "data_id": ("Data ID", "int"),
          "pattern_id": ("Mod Pattern ID", "str"),
          "mod_id": ("Bowgun Mod ID", "str"), "mod": ("Bowgun Mod", "str"),
          "is_default": ("Is First Setting", "bool")}, {}, "pattern_id"),

    Spec("weapons/hunting_horn_notes", "Wp05MusicSkillToneTable",
         "Which notes each hunting horn type carries.",
         {"horn_type": ("Hunting Horn Type", "str"), "notes": ("Notes", "str")},
         {}, "horn_type"),

    Spec("weapons/hunting_horn_melodies", "Wp05MusicSkillToneColorTable",
         "Note sequence that triggers each hunting horn melody.",
         {"melody": ("Melody", "str"), "notes": ("Notes", "str")}, {}, "melody"),

    Spec("weapons/recommendations", "WeaponRecommend",
         "Weapons the game suggests at each point of the story.",
         {"index": ("Index", "int"), "data_id": ("Data ID", "int"),
          "sort_id": ("Sort ID", "int"), "story_flag": ("Story Flag", "str"),
          "weapon_type": ("Weapon Type", "str"), "param_id": ("Param ID", "int")},
         {}, "index"),

    # -------------------------------------------------------------- armour
    Spec("armor/upgrades", "ArmorUpgradeData",
         "Defence gained and cost per upgrade level, by rarity.",
         {"index": ("Index", "int"), "rarity": ("Rarity", "paren_int"),
          "mission_id": ("Mission ID", "str"), "max_level": ("Max Level", "int"),
          "defense_increase": ("Defense Increase", "str"),
          "points": ("Points", "str"), "price": ("Price", "str"),
          "can_sp_upgrade": ("Can SP Upgrade", "bool")}, {}, "index"),

    Spec("armor/sp_upgrade_costs", "ArmorSpUpgradeCostData",
         "Cost of a special upgrade, by rarity.",
         {"index": ("Index", "int"), "rarity": ("Rarity", "paren_int"),
          "cost": ("Cost", "str")}, {}, "index"),

    Spec("armor/recommendations", "ArmorRecommend",
         "Armour the game suggests at each point of the story.",
         {"index": ("Index", "int"), "data_id": ("Data ID", "int"),
          "sort_id": ("Sort ID", "int"), "story_flag": ("Story Flag", "str"),
          "series": ("Series", "str"), "part": ("Part", "str")}, {}, "index"),

    Spec("armor/layered", "OuterArmorData",
         "Layered (cosmetic) armour pieces, with separate male and female names.",
         {"index": ("Index", "int"), "data_value": ("Data Value", "int"),
          "series": ("Series", "str"), "part": ("Part", "str"),
          "name_male": ("Name Male", "str"), "name_female": ("Name Female", "str")},
         {"name_male_guid": "Name Male Raw", "name_female_guid": "Name Female Raw"},
         "index"),

    # -------------------------------------------------------------- charms
    Spec("charms/pendants", "Pendants",
         "Weapon pendants (cosmetic charms hung on the weapon).",
         {"index": ("Index", "int"), "name": ("Name", "str"),
          "sort_id": ("Sort ID", "int"), "model_id": ("Model ID", "str"),
          "story_flag": ("Story Flag", "str")}, NAME_ONLY, "index"),

    Spec("charms/rng_talismans", "RNG Talismans",
         "Randomly generated talismans: rarity, skill groups and slot presets.",
         {"index": ("Index", "int"), "amulet": ("Amulet", "str"),
          "rarity": ("Rarity", "int"),
          "configurations": ("Number of Configurations", "int"),
          "skill_1_group": ("Skill 1 Group", "str"),
          "skill_2_group": ("Skill 2 Group", "str"),
          "skill_3_group": ("Skill 3 Group", "str"),
          "slots_preset": ("Slots Preset", "str")}, {}, "index"),

    # -------------------------------------------------------------- artian
    Spec("artian/parts", "Artian Parts",
         "Artian weapon components and which weapon classes accept them.",
         {"index": ("Index", "int"), "fixed_id": ("Fixed ID", "str"),
          "part_type": ("Parts Type", "str"), "name": ("Name", "str"),
          "sort_id": ("Sort ID", "int"), "sell_price": ("Sell Price", "int"),
          "used_for": ("Used For", "str")}, NAME_ONLY, "index"),

    Spec("artian/bonus_categories", "Artian Reinforcement Bonus Cate",
         "Probability and cap for each Artian reinforcement bonus category.",
         {"index": ("Index", "int"), "category_id": ("Bonus Category ID", "str"),
          "probability": ("Probability", "float"),
          "grinding_max": ("Grinding Max Number", "int")}, {}, "index"),

    Spec("artian/focus_types", "Gogma Artian Focus Types",
         "Gogmazios focus types and the weapon classes each one applies to.",
         {"index": ("Index", "int"), "focus_type_id": ("Focus Type ID", "str"),
          "focus_type": ("Focus Type", "str"), "icon_color": ("Icon Color", "str")},
         {}, "index"),

    # --------------------------------------------------------------- world
    Spec("world/zones", "Locale Zones",
         "Area subdivisions of each map, with temperature and environment type.",
         {"area_id": ("Area ID", "str"), "area_number": ("Area Number", "int"),
          "floor": ("Floor Number", "int"), "subfloor": ("Subfloor Number", "int"),
          "pop_shade": ("Pop Shade", "str"),
          "temperature": ("Temperature Type", "str"),
          "environment": ("Environment Type", "str")}, {}, "area_id"),

    Spec("world/gimmicks", "Gimmicks",
         "Interactive map objects: gathering points, traps, environmental features.",
         {"index": ("Index", "int"), "gimmick_id": ("Gimmick ID", "str"),
          "name": ("Name", "str"), "points": ("Points", "int"),
          "map_display_type": ("Map Display Type", "str"),
          "icon_colour": ("Icon Colour", "str"),
          "palico_pick": ("Otomo Pick", "bool"),
          "advisor_pick": ("Advisor Pick", "bool")}, {}, "gimmick_id"),

    Spec("world/gimmick_texts", "Gimmick Text",
         "Display name and description for each gimmick.",
         {"index": ("Index", "int"), "gimmick_id": ("Gimmick ID", "str"),
          "name": ("Name", "str"), "description": ("Description", "str")},
         NAME_DESC, "gimmick_id"),

    Spec("world/endemic_life", "Endemic Life",
         "Endemic creatures, where they live and what they are worth.",
         {"em_id": ("EM ID", "str"), "fixed_id": ("Fixed ID", "str"),
          "name": ("Name", "str"), "points": ("Points", "int"),
          "locales": ("Locale", "csv")}, {}, "em_id"),

    Spec("world/fish", "Fish",
         "Fishable species, their sizes and the lure that works best.",
         {"em_id": ("EM ID", "str"), "fixed_id": ("Fixed ID", "str"),
          "name": ("Name", "str"), "is_whopper": ("Is Whopper?", "bool"),
          "best_lure": ("Best Lure", "str"),
          "best_lure_action": ("Best Lure Action", "str"),
          "points": ("Points", "int"), "locales": ("Locale", "csv"),
          "base_size": ("Base SIze", "float"),
          "min_size": ("Minimum Size", "float"),
          "max_size": ("Maximum Size", "float")}, {}, "em_id"),

    # ------------------------------------------------------------ progression
    Spec("progression/mantles", "HunterActiveSkillData",
         "Hunter mantles (specialised tools).",
         {"index": ("Index", "int"), "skill_id": ("Active Skill ID", "str"),
          "description": ("Description", "str"), "story_flag": ("Story Flag", "str"),
          "sort_id": ("Sort ID", "int"), "item_id": ("Item ID", "str")},
         {"description_guid": "Column 3"}, "skill_id"),

    Spec("progression/profile_backgrounds", "Hunter Profile Backgrounds",
         "Guild-card backgrounds and how each is unlocked.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "description": ("Description", "str"), "open_type": ("Open Type", "str"),
          "mission_id": ("Mission ID", "str")},
         NAME_DESC, "id"),

    Spec("progression/name_plates", "Name Plates",
         "Guild-card name plates and their unlock condition.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "description": ("Description", "str"), "medal_id": ("Medal ID", "str"),
          "mission_id": ("Mission ID", "str")}, NAME_DESC, "id"),

    Spec("progression/title_words", "Hunter Profile Title Words",
         "Nouns available for the hunter's title, with unlock conditions.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "open_type": ("Open Type", "str"), "mission_id": ("Mission ID", "str"),
          "monster": ("Monster", "str"), "locale": ("Locale", "str")},
         NAME_DESC, "id"),

    Spec("progression/title_conjunctions", "Hunter Profile Title Conjunctio",
         "Adjectives available for the hunter's title.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "open_type": ("Open Type", "str"),
          "mission_id": ("Mission ID", "str")}, NAME_DESC, "id"),

    Spec("progression/npcs", "NPC Names",
         "Named non-player characters.",
         {"fixed_id": ("Fixed ID", "str"), "index": ("Index", "int"),
          "npc_id": ("NPC ID", "str"), "name": ("Name", "str")}, NAME_ONLY, "npc_id"),

    Spec("progression/dlc", "DLC",
         "Downloadable content entries and their store codes.",
         {"index": ("Index", "int"), "fixed_id": ("Fixed ID", "str"),
          "name": ("Name", "str"), "store_category": ("Store Category", "str"),
          "label": ("Label", "str"), "sort_id": ("Sort ID", "int"),
          "product_pack": ("Product Pack", "str")}, NAME_ONLY, "index"),

    # ------------------------------------------------------------- economy

    # ---- migrated from build.py: these need no logic beyond a field mapping
    Spec("armor/series", "ArmourSeriesData",
         "Armour series, the pivot that pieces and recipes hang off.",
         {"index": ("Index", "int"), "series": ("Series", "str"),
          "name": ("Name", "str"), "rarity": ("Rarity", "paren_int"),
          "price": ("Price", "int"), "type": ("Type", "str"),
          "sort_id": ("Sort ID", "int"), "full_set": ("Is Full Set", "bool")},
         NAME_ONLY, "series"),

    Spec("armor/armor", "ArmorData",
         "Every armour piece with its defences, slots and skills.",
         {"index": ("Index", "int"), "series": ("Series", "str"),
          "part": ("Part", "str"), "name": ("Name", "str"),
          "description": ("Description", "str"), "defense": ("Defense", "int"),
          "res_fire": ("Fire Res", "int"), "res_water": ("Water Res", "int"),
          "res_thunder": ("Thunder Res", "int"), "res_ice": ("Ice Res", "int"),
          "res_dragon": ("Dragon Res", "int"), "slots": ("Slots", "str"),
          "skills": ("Skills", "csv"), "skill_levels": ("Skill Levels", "csv")},
         NAME_DESC, "series"),

    Spec("charms/decorations", "Decorations",
         "Decorations, their level, slot size and skills.",
         {"index": ("Index", "int"), "fixed_id": ("Fixed ID", "str"),
          "enum": ("Enum", "str"), "name": ("Name", "str"),
          "description": ("Description", "str"), "type": ("Type", "str"),
          "rarity": ("Rarity", "int"), "price": ("Price", "int"),
          "level": ("Level", "int"), "colour": ("Colour", "str"),
          "skill_1_level": ("Skill 1 Lv", "int"),
          "skill_2_level": ("Skill 2 Lv", "int")},
         NAME_DESC, "name"),

    Spec("palico/series", "Palico Equipment Series",
         "Palico equipment series. `rejected` marks the workbook's unused rows.",
         {"index": ("Index", "int"), "fixed_id": ("Fixed ID", "str"),
          "name": ("Name", "str"), "rarity": ("Rarity", "int"),
          "price": ("Price", "int"), "sort_id": ("Sort ID", "int"),
          "full_set": ("Is Full Set", "bool"), "rejected": ("Name", "rejected")},
         NAME_ONLY, "name"),

    Spec("palico/armor", "Palico Armour",
         "Palico armour pieces.",
         {"index": ("Index", "int"), "data_id": ("Data ID", "int"),
          "series": ("Series", "str"), "part": ("Type", "str"),
          "name": ("Name", "str"), "description": ("Explain", "str"),
          "defense": ("Defense", "int"), "res_fire": ("Fire Res", "int"),
          "res_water": ("Water Res", "int"), "res_thunder": ("Thunder Res", "int"),
          "res_ice": ("Ice Res", "int"), "res_dragon": ("Dragon Res", "int")},
         {"name_guid": "Name Raw", "description_guid": "Explain Raw"}, "name"),

    Spec("palico/weapons", "Palico Weapons",
         "Palico weapons, melee and ranged.",
         {"index": ("Index", "int"), "series": ("Series", "str"),
          "name": ("Name", "str"), "description": ("Explain", "str"),
          "type": ("Type", "str"), "element": ("Attribute", "str_dash"),
          "element_value": ("Attribute Value", "int"),
          "melee_attack": ("Melee Attack", "int"),
          "ranged_attack": ("Ranged Attack", "int"),
          "defense_bonus": ("Defense Bonus", "int"),
          "affinity": ("Affinity", "int")},
         {"name_guid": "Name Raw", "description_guid": "Explain Raw"}, "name"),

    Spec("palico/layered_armor", "Palico Layered Armour",
         "Palico layered (cosmetic) armour.",
         {"index": ("Index", "int"), "data_value": ("Data Value", "int"),
          "series": ("Series", "str"), "part": ("Type", "str"),
          "name": ("Name", "str")}, NAME_ONLY, "name"),

    Spec("progression/mission_reward_tables", "Mission Reward Tables",
         "Which reward tables each mission draws from.",
         {"index": ("Index", "int"), "mission_id": ("Mission ID", "str"),
          "mission_name": ("Mission Name", "str"),
          "common_table_id": ("Common Reward Table ID", "int"),
          "target_table_id": ("Target Additional Reward Table ID", "int"),
          "quest_table_id": ("Quest Additional Reward Table ID", "int")},
         {}, "mission_id"),

    Spec("progression/hunt_order", "Hunt Order (OBT1)",
         "Story order in which monsters are introduced.",
         {"order": ("ID", "int"), "monster": ("Monster", "str"),
          "role": ("Role", "str"), "min_hr": ("Min HR", "int")}, {}, "monster"),

    Spec("progression/highlights", "Hunter Highlights",
         "End-of-quest hunter highlight awards.",
         {"index": ("Index", "int"), "id": ("ID", "str"), "name": ("Name", "str"),
          "description": ("Description", "str"), "unit": ("Unit", "str"),
          "weight": ("Weight", "int"), "threshold": ("Threshold", "int")},
         NAME_DESC, "id"),
]
