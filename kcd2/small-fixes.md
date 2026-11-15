# KCD2 small fixes

Quick fixes found while running about 130 mods on game 1.5.6. Each is an edit you make to your own copy of a mod or to the game's files; nothing from those mods is included here.

## A mod is silently disabled after a game update

**Symptom:** the mod is enabled in Vortex but does nothing. `kcd.log` (in the game folder) says the mod `will be disabled` because of the game version.

**Fix:** open the mod's `mod.manifest` (in Vortex's staging folder, then Deploy) and widen the version line, for example:

```xml
<kcd_version>1.1.*</kcd_version>   →   <kcd_version>1.*.*</kcd_version>
```

Only do this for mods that are just textures, models or simple tables (such as **Arrows and bolts retexture** by AleTal). Script mods can genuinely break on a new game version.

## "not found" for a mod that's installed

**Symptom:** `kcd.log` says a mod from `mod_order.txt` was "not found", even though its folder exists.

**Cause:** the game matches `mod_order.txt` entries to the manifest's `<modid>`, which must be **lowercase letters and underscores**, not to the folder name. A mixed-case entry like `VerticalLightFix` doesn't match `verticallightfix`.

**Fix:** make the entry lowercase. Vortex rewrites the file on deploy, so if it keeps coming back, the mod's own id is the problem. **Vertical Light Fix** in particular is just one setting, so you can replace the whole mod with this line in `user.cfg`:

```
wh_e_VerticalLightCulling=2
```

## Game crashes at launch with lots of mods

Somewhere around 120 to 130 mod folders the game crashes on startup. Install **Mod Limit Fix** (Nexus 3427, a KCSE plugin). Also fold config-only mods into `user.cfg` (see [`user.cfg`](user.cfg)) to free up folders.

## Every KCSE mod stopped working

Check `Bin\Win64MasterMasterSteamPGO\dinput8.dll`. KCSE's is about **1.4 MB**. If it's about **3.6 MB**, a mod extracted its own ASI loader over it. Reinstall KCSE, and don't let that other mod's `dinput8.dll` overwrite it.

## Galahad perk points (Perk Progression Controller)

With **Galahad** (caps at 50) and **Perk Progression Controller**, this schedule gives 16 points per tree at level 20, 21 at 30 and 28 at 50 (the base game gives 13). Put these rules in the controller's config:

```
5-20=1
22-30/2=1
32-50/3=1
```

That's 1 point per level from 5 to 20, one every 2 levels from 22 to 30, and one every 3 levels from 32 to 50. Rules add up. To give extra points to every tree, add a line like `1=5` (+5 per tree, about +100 in total), then in the console with a save loaded type `perkctrl_reload_config` and check with `perkctrl_auto_status`.

## Harmless log noise

With the **cheat** mod installed, dozens of `Skipping duplicated item id` lines and three `Failed to load data from XML database` errors appear. They come from the cheat mod's own item search index, not from real conflicts. Leave them.
