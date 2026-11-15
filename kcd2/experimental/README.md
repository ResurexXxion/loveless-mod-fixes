# Experimental console scripts (untested)

> ⚠️ **Not yet tested in game.** Back up your saves (`Saved Games\kingdomcome2`) first. These **can't be undone**: raised levels and unlocked perks stay.

Plain console scripts for KCD2 1.5.6. Each line is a normal console command, the same mechanism the "addallCombos" mod uses.

| File | Does |
|---|---|
| `level_20.cfg`, `level.cfg` (30), `level_50.cfg` | Raise all stats and skills to 20 / 30 / 50 |
| `level_stats.cfg`, `level_skills.cfg`, `level_combat.cfg` | Only main stats / non-combat skills / combat skills (to 30) |
| `pcr.cfg` | Unlock all perks, combos and recipes |
| `pcr_perks.cfg`, `pcr_combos.cfg`, `pcr_recipes.cfg` | Just one of those groups |

**Use:** put the file in the game folder (next to `Bin`, not in `Mods`), load a save, open the console with `~` and type `exec level_20.cfg` (or the file you want). The console needs the game launched with `-devmode`.

**Notes**
- The level scripts only *raise* a level; anything already higher is left alone. Levels above 20 need a mod that raises the caps (Galahad, or skillcap50 / statcap50).
- `pcr.cfg` was generated for one specific 130-mod setup. Lines for mods you don't have just print an error and the rest still run. Mutually exclusive perks (like the backstory pairs) are at the end, switched off.
- If you test one, please report how it went in the [Discord](https://discord.gg/qcmgVa2Fx6) or an issue, so this folder can lose its warning label.
