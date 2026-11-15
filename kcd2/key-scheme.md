# KCD2 key scheme: ending the F-key pile-up

With a lot of mods, half of them want F6, F7 or F8. Here's a layout where nothing clashes, tested on game 1.5.6 with about 130 mods. Use the parts that match the mods you have.

## The layout

| Key | Does | Mod | How it gets there |
|---|---|---|---|
| F1 | Photo mode (in game) / web menu (in menus) | game | unchanged |
| F2 | Camping Mod Menu | Camping Mod Menu | edit, see below (default F1) |
| F3 / F4 | Third-person camera: toggle / orbit | KCD2 TPV Camera | unchanged |
| F6 | Trainer window | KCD2 Companion | fixed by the mod |
| F7 | Minimap settings panel | KCD2 Minimap | edit, see below (default F6) |
| F8 | Go to quest objective | KCD2 Companion | fixed by the mod |
| F9 / F10 | Enhanced GI on/off / cycle profile | Enhanced GI | edit, see below (default F6 / F7) |
| F11 | Lock weather | Dynamic Fog Weather Module | edit, see below (default F8) |
| F5, F12 | free (F12 is Steam's screenshot key) | | |
| Numpad 7 / 8 / 9 | Place campfire / chair / bed | The KCD2 Camping Mod + Toggle | needs a keybind merge (below) |
| Numpad 4 / 5 / 6 | Pack up campfire / chair / bed | same | same |
| Numpad 1 / 2 / 3 | Toggle campfire / chair / bed | same | same |
| Numpad 0 | Pack up the whole camp | same | same |
| Numpad Enter | Fill water | same | same |
| Numpad . | Quick save | ZMagusQuickSave | its default |
| U | Pull hood up/down | Pull Hood Up / Down 2.0.2 | its default |
| Y | Free-combat target toggle | EnhancedEasyFreeCombatTarget | unchanged |
| End | Noclip (fly) | Noclip aka Fly Nocollision | its default, rebindable in Settings |

Using the numpad for camping keeps the number row free for quick slots and dialogue choices.

## The config edits (2 minutes)

These are small edits to each mod's own config file. In Vortex, edit the file in the **staging folder** (Vortex: the mod ▸ Open in File Manager), then **Deploy**; editing the copy inside the game folder gets overwritten on the next deploy.

- **Enhanced GI**, `EGI.cfg`: `Bind f6 GI_Toggle` → `Bind f9 GI_Toggle`, and `Bind f7 GI_CycleProfiles` → `Bind f10 GI_CycleProfiles`
- **Dynamic Fog Weather Module**, `weathermodule.cfg`: `bind f8 df_wm_LockWeather` → `bind f11 df_wm_LockWeather`
- **Camping Mod Menu**, `campingmodmenu.cfg`: on the `Bind f1 "kcdmenus_open 'Camping Mod Menu' ...` line change `f1` to `f2` (leave the `;Bind f1` comment line alone)
- **KCD2 Minimap**, `kcd2minimap.cfg` (next to the game's exe in `Bin\Win64MasterMasterSteamPGO`): set `uiKey` to `F7`

If you've ever rebound a key in the game's own Controls menu, that's saved in your Saved Games `attributes.xml` and can override a mod's default. Reset that binding in the menu if a key doesn't take.

## The camping and other keybind changes

The numpad camping keys, Pull Hood, Noclip and quick save all ship their own copies of the game's keybind files (`defaultProfile.xml`, `keybindSuperactions.xml`). Only the last one loaded wins, so normally only one mod's keys work. The fix is to merge them into one file that loads last.

Those files belong to their mod authors, so this repo doesn't ship a pre-built merge. Instead, run the **[merge builder](merge-builder/)**: it merges the keybind files (and any other shared files) from *your* installed mods into one last-loading mod, on your PC. Then set the numpad keys in the game's Controls menu, or edit the camping mod's entries before building.

## Check in game

- F6 opens the Companion trainer, F7 the Minimap panel, F9 toggles Enhanced GI, F2 opens the Camping Mod Menu.
- Number-row keys still pick quick slots and dialogue options.
- Numpad keys work with NumLock on or off (they're read as scancodes).
