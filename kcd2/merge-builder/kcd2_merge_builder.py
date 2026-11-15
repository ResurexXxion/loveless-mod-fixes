r"""KCD2 merge builder - Loveless Mod Fixes (MIT). https://github.com/ResurexXxion/loveless-mod-fixes

Kingdom Come: Deliverance II loads mods in order, and when two mods ship the same file, the later one replaces it
completely: only one mod's keybinds work, one mod's animations vanish, and so on. This script finds every file that
two or more of YOUR installed mods ship, and merges their changes into one copy, using the game's own original
file as the common base (a three-way merge, the way git merges code). The result is a small mod,
`zzz_loveless_merge`, that loads last.

Everything happens on your PC from files you already have. Nothing is downloaded or uploaded.

  python kcd2_merge_builder.py                 build into .\output (nothing in the game folder changes)
  python kcd2_merge_builder.py --install       also copy the merge into the game's Mods folder and put it last
  python kcd2_merge_builder.py --game "D:\\Games\\KingdomComeDeliverance2"
  python kcd2_merge_builder.py --exclude zzz_merge_patch    leave a mod out (e.g. an older hand-made merge)

Rules:
  * Text files (.xml .adb .lua .txt .cfg .tbl .json and similar) are merged against the game's original.
  * Changes in different places are all kept. Lines that two mods insert at the same spot are both kept.
  * If two mods change the SAME lines differently, the mod that loads later wins that spot, and it's listed in
    MERGE-REPORT.txt so you can check it.
  * Binary files (textures, models, UI .gfx) can't be merged: the later mod wins, as it would without this tool.
  * Every merged XML file is test-parsed; if one doesn't parse, that file falls back to "later mod wins".
Needs Python 3.9+ (python.org). Standard library only.
"""

from __future__ import annotations

import argparse, datetime, difflib, glob, io, os, re, shutil, sys, zipfile
import xml.etree.ElementTree as ET

VERSION = "1.0.0"
OUT_MODID = "zzz_loveless_merge"
TEXT_EXT = {".xml", ".adb", ".lua", ".txt", ".cfg", ".tbl", ".json", ".ini", ".mtl", ".ent", ".lyr", ".xls", ".csv"}
XML_EXT = {".xml", ".adb", ".mtl", ".ent", ".lyr"}
GAME_FOLDER = "KingdomComeDeliverance2"

# ---------------------------------------------------------------- finding the game

def steam_libraries() -> list[str]:
    roots = []
    for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files")):
        roots.append(os.path.join(base, "Steam"))
    try:
        import winreg  # Windows only
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"), (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try: roots.append(winreg.QueryValueEx(k, name)[0])
                        except OSError: pass
            except OSError: pass
    except ImportError:
        pass
    libs = []
    for r in roots:
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            libs.append(r)
            with open(vdf, encoding="utf-8", errors="replace") as fh: vtxt = fh.read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', vtxt):
                libs.append(m.group(1).replace("\\\\", "\\"))
    for drive in "CDEFGH":
        libs.append(f"{drive}:\\Steam"); libs.append(f"{drive}:\\SteamLibrary")
    seen, out = set(), []
    for l in libs:
        n = os.path.normcase(os.path.normpath(l))
        if n not in seen: seen.add(n); out.append(l)
    return out


def find_game(arg: str | None) -> str:
    cands = [arg] if arg else []
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [here, os.path.dirname(here)]
    cands += [os.path.join(l, "steamapps", "common", GAME_FOLDER) for l in steam_libraries()]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "Data")) and os.path.isdir(os.path.join(c, "Bin")):
            return os.path.abspath(c)
    sys.exit("Couldn't find the game. Run again with --game \"<path to KingdomComeDeliverance2>\".")

# ---------------------------------------------------------------- mods and load order

def read_text(path: str, enc: str = "utf-8-sig") -> str:
    with open(path, encoding=enc, errors="replace") as fh:
        return fh.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)


def read_manifest_modid(folder: str) -> str:
    p = os.path.join(folder, "mod.manifest")
    try:
        m = re.search(r"<modid>\s*([^<\s]+)\s*</modid>", read_text(p), re.I)
        if m: return m.group(1).strip().lower()
    except OSError:
        pass
    return os.path.basename(folder).lower()


def game_version(game: str) -> str | None:
    """The game's version as kcd.log reports it (e.g. '1.5.6'), if a log exists."""
    try:
        m = re.search(r"game version '([\d.]+)'", read_text(os.path.join(game, "kcd.log"), "utf-8"))
        return m.group(1) if m else None
    except OSError:
        return None


def version_ok(folder: str, ver: str | None) -> bool:
    """False if the mod's manifest limits it to game versions that don't include `ver` (the game disables those)."""
    if not ver: return True
    try: txt = read_text(os.path.join(folder, "mod.manifest"))
    except OSError: return True
    pats = re.findall(r"<kcd_version>\s*([^<\s]+)\s*</kcd_version>", txt, re.I)
    if not pats: return True
    return any(re.fullmatch(re.escape(p).replace(r"\*", ".*"), ver) for p in pats)


def mod_load_order(mods_dir: str, exclude: set[str]) -> list[tuple[str, str]]:
    """[(name, folder)] in load order: mod_order.txt first (matched by modid or folder name), the rest alphabetically."""
    folders = {}
    for e in sorted(os.listdir(mods_dir), key=str.lower):
        f = os.path.join(mods_dir, e)
        if os.path.isdir(f) and os.path.isfile(os.path.join(f, "mod.manifest")):
            folders[e.lower()] = (e, f, read_manifest_modid(f))
    by_id = {mid: key for key, (_, _, mid) in folders.items()}
    order, used = [], set()
    mo = os.path.join(mods_dir, "mod_order.txt")
    if os.path.isfile(mo):
        for line in read_text(mo).splitlines():
            n = line.strip().lower()
            if not n or n.startswith("#"): continue
            key = by_id.get(n) or (n if n in folders else None)
            if key and key not in used: used.add(key); order.append(key)
    order += [k for k in folders if k not in used]
    out = []
    for k in order:
        name, folder, mid = folders[k]
        if mid == OUT_MODID or k == OUT_MODID or mid in exclude or k in exclude: continue
        out.append((name, folder))
    return out


def norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").lower()


def index_mod(folder: str) -> dict[str, tuple[str, str]]:
    """{normalised path: (pak file, entry name)} for the mod's top-level Data/*.pak (later paks in a mod win)."""
    idx = {}
    for pak in sorted(glob.glob(os.path.join(folder, "Data", "*.pak")) + glob.glob(os.path.join(folder, "data", "*.pak"))):
        try:
            with zipfile.ZipFile(pak) as z:
                for i in z.infolist():
                    if not i.is_dir(): idx[norm(i.filename)] = (pak, i.filename)
        except (zipfile.BadZipFile, OSError) as e:
            print(f"  ! can't read {pak}: {e}")
    return idx


def vanilla_index(game: str, wanted: set[str]) -> dict[str, tuple[str, str]]:
    idx = {}
    for pak in sorted(glob.glob(os.path.join(game, "Data", "**", "*.pak"), recursive=True)):
        try:
            with zipfile.ZipFile(pak) as z:
                for i in z.infolist():
                    k = norm(i.filename)
                    if k in wanted and k not in idx: idx[k] = (pak, i.filename)
        except (zipfile.BadZipFile, OSError):
            pass
    return idx


def read_entry(pak: str, name: str) -> bytes:
    with zipfile.ZipFile(pak) as z:
        return z.read(name)

# ---------------------------------------------------------------- three-way merge

def decode(b: bytes) -> tuple[str, bool] | None:
    bom = b.startswith(b"\xef\xbb\xbf")
    try:
        return b[3:].decode("utf-8") if bom else b.decode("utf-8"), bom
    except UnicodeDecodeError:
        try: return b.decode("cp1252"), False
        except UnicodeDecodeError: return None


def _lis(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Longest chain of pairs increasing in both coordinates (pairs are already sorted by the first)."""
    import bisect
    tails, tails_idx, prev = [], [], [-1] * len(pairs)
    for k, (_, j) in enumerate(pairs):
        p = bisect.bisect_left(tails, j)
        if p == len(tails): tails.append(j); tails_idx.append(k)
        else: tails[p] = j; tails_idx[p] = k
        prev[k] = tails_idx[p - 1] if p else -1
    out, k = [], tails_idx[-1] if tails_idx else -1
    while k != -1: out.append(pairs[k]); k = prev[k]
    return out[::-1]


def _patience(a: list[int], b: list[int], alo: int, ahi: int, blo: int, bhi: int, out: list) -> None:
    """Patience diff: anchor on lines unique in both ranges, recurse between anchors. Fast on 100k+ line files."""
    while alo < ahi and blo < bhi and a[alo] == b[blo]:
        out.append((alo, blo, 1)); alo += 1; blo += 1
    tail = []
    while alo < ahi and blo < bhi and a[ahi - 1] == b[bhi - 1]:
        ahi -= 1; bhi -= 1; tail.append((ahi, bhi, 1))
    if alo < ahi and blo < bhi:
        ca, cb = {}, {}
        for i in range(alo, ahi): ca[a[i]] = i if a[i] not in ca else -1
        for j in range(blo, bhi): cb[b[j]] = j if b[j] not in cb else -1
        pairs = sorted((i, cb[x]) for x, i in ca.items() if i >= 0 and cb.get(x, -1) >= 0)
        anchors = _lis(pairs)
        if anchors:
            pa, pb = alo, blo
            for i, j in anchors:
                _patience(a, b, pa, i, pb, j, out)
                out.append((i, j, 1)); pa, pb = i + 1, j + 1
            _patience(a, b, pa, ahi, pb, bhi, out)
        elif (ahi - alo) * (bhi - blo) <= 250_000:  # small gap with no unique lines: exact match is cheap
            sm = difflib.SequenceMatcher(None, a[alo:ahi], b[blo:bhi], autojunk=False)
            out.extend((alo + x, blo + y, s) for x, y, s in sm.get_matching_blocks() if s)
        # else: a large gap with only repeated lines is treated as changed; merge3 still compares the actual text.
    out.extend(reversed(tail))


def _match_pairs(base: list[str], other: list[str]) -> list[tuple[int, int, int]]:
    """Matching blocks (base_start, other_start, length), merged and ending with the (n, m, 0) sentinel."""
    ids: dict[str, int] = {}
    a = [ids.setdefault(l, len(ids)) for l in base]
    b = [ids.setdefault(l, len(ids)) for l in other]
    raw: list[tuple[int, int, int]] = []
    _patience(a, b, 0, len(a), 0, len(b), raw)
    raw.sort()
    blocks: list[tuple[int, int, int]] = []
    for i, j, s in raw:
        if blocks and blocks[-1][0] + blocks[-1][2] == i and blocks[-1][1] + blocks[-1][2] == j:
            blocks[-1] = (blocks[-1][0], blocks[-1][1], blocks[-1][2] + s)
        else:
            blocks.append((i, j, s))
    blocks.append((len(base), len(other), 0))
    return blocks


_WS, _TAGEND, _EQ = re.compile(r"\s+"), re.compile(r"\s*(/?>)"), re.compile(r"\s*=\s*")


def _key(s: str) -> str:
    """Comparison key: ignores indentation, line endings and whitespace inside tags (`" />` vs `"/>`)."""
    return _EQ.sub("=", _TAGEND.sub(r"\1", _WS.sub(" ", s.strip())))


class Line(str):
    """A line that compares equal to another when only formatting differs. Mods often re-save a game file with
    spaces instead of tabs, LF instead of CRLF, or through an XML tool that respaces tags; without this every line
    of such a file would look changed. The original text of the chosen line is what gets written."""
    def __new__(cls, s: str):
        o = str.__new__(cls, s); o.k = _key(s); return o
    def __eq__(self, other): return self.k == (other.k if isinstance(other, Line) else _key(str(other)))
    def __ne__(self, other): return not self.__eq__(other)
    def __hash__(self): return hash(self.k)


_COMMENT = re.compile(r"<!--.*?-->", re.S)


def to_lines(text: str, eol: str, xml: bool) -> list[Line]:
    """Split into Line objects. XML comments and blank lines are dropped (the game ignores both, and mods that
    re-save files often strip or double them). Every line ends with a newline so lines never run together."""
    if xml: text = _COMMENT.sub("", text)
    return [Line(l if l.endswith("\n") else l + eol) for l in text.splitlines(keepends=True) if l.strip()]


def _contains(seq: list[str], sub: list[str]) -> bool:
    """True if `sub` appears in `seq` as one contiguous run."""
    n, m = len(seq), len(sub)
    if m == 0: return True
    first = sub[0]
    for i in range(n - m + 1):
        if seq[i] == first and seq[i:i + m] == sub: return True
    return False


def merge3(base: list[str], ours: list[str], theirs: list[str]) -> tuple[list[str], list[tuple[int, int]]]:
    """Merge `theirs` changes into `ours` (both edits of `base`). Same-spot pure insertions keep both; true conflicts
    take `theirs` (the later mod). Returns (lines, conflicts as (start, end) base line ranges)."""
    if ours == base: return list(theirs), []
    if theirs == base or theirs == ours: return list(ours), []
    mo, mt = _match_pairs(base, ours), _match_pairs(base, theirs)
    # sync regions: base ranges unchanged in both
    syncs, i, j = [], 0, 0
    while i < len(mo) and j < len(mt):
        a0, o0, al = mo[i]; b0, t0, bl = mt[j]
        lo, hi = max(a0, b0), min(a0 + al, b0 + bl)
        if lo < hi:
            syncs.append((lo, o0 + (lo - a0), t0 + (lo - b0), hi - lo))
        if a0 + al < b0 + bl: i += 1
        else: j += 1
    syncs.append((len(base), len(ours), len(theirs), 0))
    out, conflicts = [], []
    pb = po = pt = 0
    for sb, so, st, sl in syncs:
        bseg, oseg, tseg = base[pb:sb], ours[po:so], theirs[pt:st]
        if oseg == bseg: out += tseg
        elif tseg == bseg or tseg == oseg: out += oseg
        elif not bseg:  # both inserted different lines at the same spot: keep both (once, if one contains the other)
            if _contains(tseg, oseg): out += tseg
            elif _contains(oseg, tseg): out += oseg
            else: out += oseg + tseg
        else:
            out += tseg; conflicts.append((pb + 1, sb))
        out += base[sb:sb + sl]
        pb, po, pt = sb + sl, so + sl, st + sl
    return out, conflicts

# ---------------------------------------------------------------- XML element merge (used when the line merge duplicates entries)

def _ekey(e: ET.Element):
    """Identity of an element among its siblings: tag + name/id when it has one, else tag + all attributes."""
    for a in ("name", "id", "atl_name", "Name", "ID"):
        if a in e.attrib: return (e.tag, a, e.attrib[a])
    return (e.tag, "#attrs", tuple(sorted(e.attrib.items())))


def _canon(e: ET.Element) -> str:
    """Formatting-independent form of an element, to tell whether a mod changed it."""
    parts = [e.tag, repr(sorted(e.attrib.items())), (e.text or "").strip()]
    parts += [_canon(c) + "|" + (c.tail or "").strip() for c in e]
    return "<" + "\x1f".join(parts) + ">"


def _keyed(e: ET.Element) -> list:
    """[(key, child)], numbering repeats of the same key so duplicates in the original stay distinct."""
    seen, out = {}, []
    for c in e:
        k = _ekey(c); n = seen.get(k, 0); seen[k] = n + 1
        out.append(((k, n), c))
    return out


def xml_merge3(base: ET.Element, ours: ET.Element, theirs: ET.Element) -> ET.Element:
    """Three-way merge of elements: attributes, text and children (matched by identity). Later mod wins clashes."""
    cb, co, ct = _canon(base), _canon(ours), _canon(theirs)
    if co == cb: return theirs
    if ct == cb or ct == co: return ours
    out = ET.Element(ours.tag)
    for a in set(base.attrib) | set(ours.attrib) | set(theirs.attrib):
        b, o, t = base.attrib.get(a), ours.attrib.get(a), theirs.attrib.get(a)
        v = o if t == b else t
        if v is not None: out.set(a, v)
    tb, to, tt = (base.text or "").strip(), (ours.text or "").strip(), (theirs.text or "").strip()
    out.text = ours.text if tt == tb else theirs.text
    kb, ko, kt = dict(_keyed(base)), _keyed(ours), _keyed(theirs)
    kt_map = dict(kt)
    result = []  # [(key, element)] in ours' order, with theirs' changes applied
    for k, oc in ko:
        if k in kt_map:
            result.append((k, xml_merge3(kb.get(k, oc), oc, kt_map[k])))
        elif k in kb and _canon(kb[k]) == _canon(oc):
            continue  # theirs deleted it and ours didn't change it
        else:
            result.append((k, oc))
    have = {k for k, _ in result}
    for i, (k, tc) in enumerate(kt):  # theirs' new children, placed after their previous sibling
        if k in have or k in kb: continue
        prev = next((kt[j][0] for j in range(i - 1, -1, -1) if kt[j][0] in have), None)
        pos = next((n + 1 for n, (rk, _) in enumerate(result) if rk == prev), 0) if prev else 0
        if prev is None:  # no earlier sibling in common: put it before theirs' next sibling, else at the end
            nxt = next((kt[j][0] for j in range(i + 1, len(kt)) if kt[j][0] in have), None)
            pos = next((n for n, (rk, _) in enumerate(result) if rk == nxt), len(result)) if nxt else len(result)
        result.insert(pos, (k, tc)); have.add(k)
    for _, c in result: out.append(c)
    out.tail = ours.tail
    return out


def _dup_count(root: ET.Element) -> int:
    n = 0
    for parent in root.iter():
        seen = {}
        for c in parent:
            if any(a in c.attrib for a in ("name", "id", "atl_name")):
                k = _ekey(c); seen[k] = seen.get(k, 0) + 1
        n += sum(v - 1 for v in seen.values() if v > 1)
    return n


def _parse(data: str) -> ET.Element:
    return ET.fromstring(_XMLDECL.sub("", data, count=1).encode("utf-8"))


_XMLDECL = re.compile(r"^\s*<\?xml[^>]*\?>")

# ---------------------------------------------------------------- build

def build(args) -> int:
    sys.setrecursionlimit(20000)
    game = find_game(args.game)
    mods_dir = os.path.join(game, "Mods")
    print(f"KCD2 merge builder {VERSION}\nGame: {game}")
    if not os.path.isdir(mods_dir): sys.exit("No Mods folder in the game folder.")
    exclude = {e.strip().lower() for e in (args.exclude or "").split(",") if e.strip()}
    mods = mod_load_order(mods_dir, exclude)
    ver = game_version(game)
    off = [n for n, f in mods if not version_ok(f, ver)]
    mods = [(n, f) for n, f in mods if version_ok(f, ver)]
    print(f"Mods: {len(mods)} in load order" + (f" (excluded: {', '.join(sorted(exclude))})" if exclude else ""))
    if off: print(f"Skipped (the game disables them on version {ver}): {', '.join(off)}")

    owners: dict[str, list[tuple[str, str, str]]] = {}
    for name, folder in mods:
        for k, (pak, entry) in index_mod(folder).items():
            owners.setdefault(k, []).append((name, pak, entry))
    overlaps = {k: v for k, v in owners.items() if len(v) > 1}
    print(f"Files shipped by 2+ mods: {len(overlaps)}")
    van = vanilla_index(game, set(overlaps))

    report = [f"KCD2 merge builder {VERSION} - report, {datetime.datetime.now():%Y-%m-%d %H:%M}",
              f"Game: {game}" + (f" (version {ver})" if ver else ""), f"Mods in load order: {len(mods)}", ""]
    if off: report.insert(3, f"Skipped, disabled by the game on this version: {', '.join(off)}")
    merged: dict[str, bytes] = {}
    counts = {"merged": 0, "identical": 0, "binary": 0, "fallback": 0, "conflict": 0}
    for k in sorted(overlaps):
        vers = [(name, read_entry(pak, entry), entry) for name, pak, entry in overlaps[k]]
        names = ", ".join(n for n, _, _ in vers)
        datas = [d for _, d, _ in vers]
        if all(d == datas[0] for d in datas):
            counts["identical"] += 1; continue
        ext = os.path.splitext(k)[1]
        texts = [decode(d) for d in datas] if ext in TEXT_EXT else [None]
        if ext not in TEXT_EXT or any(t is None for t in texts):
            counts["binary"] += 1
            report.append(f"[later mod wins] {k}\n    binary file in: {names} -> {vers[-1][0]} wins (can't be merged)")
            continue
        base_b = read_entry(*van[k]) if k in van else None
        base_t = decode(base_b) if base_b is not None else None
        base_src = "the game's original" if base_t else f"{vers[0][0]} (no original in the game)"
        base_text = (base_t or texts[0])[0]
        eol = "\r\n" if base_text.count("\r\n") * 2 >= base_text.count("\n") else "\n"
        is_xml = ext in XML_EXT
        base_lines = to_lines(base_text, eol, is_xml)
        result, file_conflicts = list(base_lines), []
        for (name, _, _), (txt, _) in zip(vers, texts):
            result, conf = merge3(base_lines, result, to_lines(txt, eol, is_xml))
            file_conflicts += [(name, a, b) for a, b in conf]
        out_text = "".join(result)
        bom = (base_t or texts[-1])[1]
        method = "line merge"
        if is_xml:
            # The line merge is kept when it parses and adds no duplicate entries the sources didn't already have.
            # Otherwise (e.g. two mods ship overlapping copies of the same block) merge element by element instead.
            try:
                src_roots = [_parse(base_text)] + [_parse(t) for t, _ in texts]
            except ET.ParseError:
                src_roots = None
            ok = False
            try:
                if src_roots is None:
                    _parse(out_text); ok = True
                else:
                    # Repeated names can be legitimate (e.g. one action bound in two maps). Allow the original's
                    # repeats plus whatever each mod adds on its own; more than that means the merge duplicated a block.
                    d0 = _dup_count(src_roots[0])
                    allowed = d0 + sum(max(0, _dup_count(r) - d0) for r in src_roots[1:])
                    ok = _dup_count(_parse(out_text)) <= allowed
            except ET.ParseError:
                ok = False
            if not ok and src_roots:
                r = src_roots[0]
                for v in src_roots[1:]:
                    r = xml_merge3(src_roots[0], r, v)
                ET.indent(r, space="\t")
                decl = _XMLDECL.match(base_text)
                out_text = (decl.group(0).strip() + eol if decl else "") + ET.tostring(r, encoding="unicode").replace("\n", eol) + eol
                file_conflicts, method, ok = [], "element merge (the line merge duplicated entries)", True
            if not ok:
                counts["fallback"] += 1
                report.append(f"[later mod wins] {k}\n    merge of {names} didn't parse as XML; left to {vers[-1][0]}")
                continue
        merged[vers[-1][2]] = (b"\xef\xbb\xbf" if bom else b"") + out_text.encode("utf-8")
        counts["merged"] += 1
        line = f"[merged] {k}\n    from: {names}\n    base: {base_src}\n    how: {method}"
        if file_conflicts:
            counts["conflict"] += 1
            line += "\n    same lines changed by more than one mod (later mod used):" + "".join(
                f"\n      original lines {a}-{b}: {n}" for n, a, b in file_conflicts[:20])
            if len(file_conflicts) > 20: line += f"\n      ... and {len(file_conflicts) - 20} more"
        report.append(line)

    report[3:3] = [f"Merged: {counts['merged']} (with same-line conflicts: {counts['conflict']}), identical copies skipped: "
                   f"{counts['identical']}, binary (later mod wins): {counts['binary']}, XML fallback: {counts['fallback']}", ""]
    out_root = os.path.abspath(args.out)
    mod_dir = os.path.join(out_root, OUT_MODID)
    if os.path.isdir(mod_dir): shutil.rmtree(mod_dir)
    os.makedirs(os.path.join(mod_dir, "Data"))
    with open(os.path.join(mod_dir, "mod.manifest"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<kcd_mod>
  <info>
    <name>Loveless merge (built on this PC)</name>
    <modid>{OUT_MODID}</modid>
    <description>Merges files that several installed mods ship. Built by the KCD2 merge builder from Loveless Mod Fixes. Must load last. Rebuild after adding, removing or updating mods.</description>
    <author>Loveless Mod Fixes merge builder</author>
    <version>{VERSION}</version>
    <created_on>{datetime.date.today():%Y-%m-%d}</created_on>
  </info>
</kcd_mod>
""")
    with zipfile.ZipFile(os.path.join(mod_dir, "Data", f"{OUT_MODID}.pak"), "w", zipfile.ZIP_DEFLATED) as z:
        for entry, data in sorted(merged.items()):
            z.writestr(entry.replace("\\", "/"), data)
    with open(os.path.join(mod_dir, "MERGE-REPORT.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(report) + "\n")
    zpath = os.path.join(out_root, f"{OUT_MODID}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for r, _, files in os.walk(mod_dir):
            for fn in files:
                p = os.path.join(r, fn); z.write(p, os.path.relpath(p, out_root))
    print(report[3])
    print(f"Built: {mod_dir}\nVortex-ready zip: {zpath}\nReport: {os.path.join(mod_dir, 'MERGE-REPORT.txt')}")

    if args.install:
        target = os.path.join(mods_dir, OUT_MODID)
        stamp = f"{datetime.datetime.now():%Y%m%d-%H%M%S}"
        if os.path.isdir(target):
            shutil.move(target, os.path.join(out_root, f"{OUT_MODID}.previous-{stamp}"))
        shutil.copytree(mod_dir, target)
        mo = os.path.join(mods_dir, "mod_order.txt")
        if os.path.isfile(mo):
            shutil.copy2(mo, os.path.join(out_root, f"mod_order.backup-{stamp}.txt"))
            lines = [l for l in read_text(mo).splitlines() if l.strip().lower() != OUT_MODID] + [OUT_MODID]
            write_text(mo, "\n".join(lines) + "\n")
        print(f"Installed into {target} and set to load last."
              "\nIf you use Vortex: it rewrites mod_order.txt when it deploys. Installing the zip through Vortex instead"
              " (drag it into Vortex, then put it last) keeps it managed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge files that several KCD2 mods ship, into one last-loading mod.")
    ap.add_argument("--game", help="game folder (found automatically if omitted)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"), help="where to build (default: .\\output)")
    ap.add_argument("--exclude", help="comma-separated mod ids or folder names to leave out")
    ap.add_argument("--install", action="store_true", help="copy the merge into the game's Mods folder and put it last")
    return build(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
