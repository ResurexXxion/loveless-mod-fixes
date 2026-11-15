# KCD2 merge builder

**The problem:** when two KCD2 mods ship the same file, the one that loads later replaces it completely. That's why only one mod's hotkeys work, why animations from one mod vanish when another loads, and why some mods "do nothing".

**What this does:** it finds every file that two or more of **your installed mods** ship, and merges their changes into one copy, using the game's own original file as the common base. That's a three-way merge, the same idea git uses for code. The result is a small mod, `zzz_loveless_merge`, that loads last.

Everything happens on your PC, from files you already have. Nothing from anyone's mod is included in this download.

## Use

1. Install **Python 3.9+** from [python.org](https://www.python.org/downloads/) and tick *Add python.exe to PATH*.
2. Download this folder, then double-click **`Build-Merge.bat`**. It finds the game through Steam, reads your mods in load order, and builds into `output\`. It doesn't touch the game folder.
3. Install the result, one of two ways:
   - **Vortex:** drag `output\zzz_loveless_merge.zip` into Vortex, enable it, and make sure it loads **last**. Deploy.
   - **Manual:** run `Build-Merge.bat --install`. That copies the mod into `Mods\` and puts it last in `mod_order.txt`, keeping a backup of the old file in `output\`.
4. Read `output\zzz_loveless_merge\MERGE-REPORT.txt`. It lists every merged file, which mods it came from, and any spot where two mods changed the same lines.

**Rebuild** whenever you add, remove or update a mod.

Options: `--game "D:\Games\KingdomComeDeliverance2"` if it can't find the game; `--exclude modid1,modid2` to leave mods out, such as an older hand-made merge patch; `--out <folder>`.

## How it merges

- **Text files** (`.xml`, `.adb`, `.lua`, `.txt`, `.cfg` and similar) are merged against the game's original. Changes in different places are all kept. Lines that two mods insert at the same spot are both kept.
- **Formatting doesn't count as a change.** Tabs vs spaces, LF vs CRLF, blank lines, XML comments and spacing inside tags are all ignored, because mods often re-save game files with a different editor.
- **Duplicate entries are prevented.** If two mods ship overlapping copies of the same block (common with compatibility patches), XML files are merged entry by entry instead (by tag and `name`), so each action or entry appears once.
- **Same lines, different changes:** the mod that loads later wins that spot, the same as without this tool, and it's listed in the report so you can check it.
- **Binary files** (textures, models, `.gfx` UI) can't be merged. The later mod wins, as usual.
- Mods the game disables for your game version are skipped, as the game would.
- Every merged XML file is test-parsed. If one ever fails, that file is left to the later mod and the report says so.

## Tested

Built against a 159-mod install (game 1.5.6): about 1,640 shared files, of which 24 needed merging. Every mod's additions to the keybind files (Very Important Activities, the Camping mod and its compatibility file, Camping Toggle, Magus QuickSave, Pull Hood, Noclip) came through, with no duplicated actions. The two animation-tag files matched a hand-made merge line for line. A full build takes about a minute, mostly reading large mod archives.

## Limits

- Mod *table patches* (`table__yourmod.xml` files) are merged by the game itself, row by row, so they rarely overlap. When two mods do ship the same one, it's merged like any other file.
- Level paks (`Data\levels\...`) aren't scanned yet; it's rare for two mods to overlap there.
- The merge is careful but can't understand intent. If a mod still misbehaves, check the report for that file, and try `--exclude` to see whether a specific mod is the cause.
- Not affiliated with Warhorse Studios. MIT licensed, part of [Loveless Mod Fixes](https://github.com/ResurexXxion/loveless-mod-fixes).
