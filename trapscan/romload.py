"""Load MAME-style ROM sets (zip or folder) for 8080 Space Invaders-family hardware.

Handles three packings:
  * non-merged / split: one set per zip, files at the top level
  * merged: the parent's files at the top level, each clone's differing files in a
    sub-folder named after the clone (e.g. lrescue.zip -> grescue/grescue.4)
  * plain folders of ROM files

Program ROMs live at $0000-$1FFF and optionally $4000-$5FFF. Known parents use an exact layout;
other parents get a heuristic layout (printed, overridable with --map ADDR=FILE). Clone ROMs are
placed by CONTENT: each is matched against the parent's code at every 1KB boundary and dropped
where it fits best. Bootleg and revision ROMs are mostly copies, so this finds their address
without needing MAME's ROM database.
"""
import os
import re
import zipfile

# Exact layouts for parent sets we have verified (addresses in hex).
KNOWN = {
    'invaders': [('0000', 'invaders.h'), ('0800', 'invaders.g'), ('1000', 'invaders.f'), ('1800', 'invaders.e')],
    'invadpt2': [('0000', 'pv01'), ('0800', 'pv02'), ('1000', 'pv03'), ('1800', 'pv04'), ('4000', 'pv05')],
    'lrescue':  [('0000', 'lrescue.1'), ('0800', 'lrescue.2'), ('1000', 'lrescue.3'), ('1800', 'lrescue.4'),
                 ('4000', 'lrescue.5'), ('4800', 'lrescue.6')],
    # sets whose ROMs the matcher/self-locator can't place reliably (layouts from MAME's 8080bw.cpp)
    'cosmicbat': [('0000', '1.5m'), ('0400', '2.5n'), ('0800', '3.5p'), ('0C00', '4.5r'), ('1000', '5.5s'),
                  ('1400', '6.5t'), ('1800', '7.5u'), ('1C00', '8.5v')],
    'mraker':   [('0000', 'mr_1.a4'), ('0400', 'mr_2.c4'), ('0800', 'mr_3.e4'), ('0C00', 'mr_4.f4'),
                 ('1000', 'mr_5.h4'), ('1400', 'mr_6.l4'), ('1800', 'mr_7.a5'), ('1C00', 'mr_8.c5'),
                 ('4000', 'mr_9.e5'), ('4800', 'mr_10.f5'), ('5000', 'mr_11.h5')],
}
MATCH_THRESHOLD = 0.7      # fraction of identical bytes needed to place a clone ROM over the parent
                           # (real bootleg/revision ROMs match at 90-100%; unrelated code ~50%)


def read_files(path):
    """Return {relative/path: bytes} from a zip file or a folder (sub-folders kept)."""
    files = {}
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            for fn in names:
                full = os.path.join(root, fn)
                files[os.path.relpath(full, path).replace(os.sep, '/')] = open(full, 'rb').read()
    else:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    files[info.filename.replace('\\', '/')] = z.read(info)
    return files


def split_sets(files, parent_name):
    """{set name: {basename: bytes}} - top-level files are the parent, sub-folders are clones."""
    sets = {parent_name: {}}
    for rel, d in files.items():
        parts = rel.split('/')
        if len(parts) == 1:
            sets[parent_name][parts[0]] = d
        else:
            sets.setdefault(parts[-2], {})[parts[-1]] = d
    return sets


def looks_like_reset_rom(d):
    """8080 startup code at $0000: NOPs then JMP, a JMP, or stack setup (LXI SP / DI; LXI SP)."""
    if d[0] == 0 and d[1] == 0 and d[2] == 0 and d[3] == 0xC3:
        return True
    if d[0] == 0xC3 and 0x0000 <= (d[1] | d[2] << 8) < 0x6000:
        return True
    if d[0] == 0x31 and 0x20 <= d[2] < 0x44:                  # LXI SP,$2xxx-$43xx
        return True
    if d[0] == 0xF3 and d[1] == 0x31:                         # DI; LXI SP
        return True
    return False


def is_prom(d):
    """Colour/timing PROMs hold a handful of distinct values (or are tiny); program code doesn't."""
    return len(d) < 1024 or max(d) < 0x10 or len(set(d)) <= 16


def program_files(files):
    return {fn: d for fn, d in files.items() if len(d) in (1024, 2048) and not is_prom(d)}


def natural_key(fn):
    """Order by the ROM's position number: lrescue.1 .. grescue.4, pv01 .., invaders.h/.g/.f/.e."""
    base, ext = os.path.splitext(fn.lower())
    m = re.search(r'(\d+)$', ext[1:]) or re.search(r'(\d+)[a-z]?$', base)
    if m:
        return (0, int(m.group(1)), fn.lower())
    if len(ext) == 2 and ext[1].isalpha():
        return (1, ext[1], fn.lower())
    return (2, 0, fn.lower())


def heuristic_layout(files):
    """Guess: program ROMs in name order, reset ROM first, filling $0000-$1FFF then $4000+."""
    progs = sorted(program_files(files), key=natural_key)
    if not progs:
        raise ValueError('no 1KB/2KB program ROMs found; pass an explicit --map')
    first = next((fn for fn in progs if looks_like_reset_rom(files[fn])), progs[0])
    if first == progs[-1] and len(progs) > 1:
        progs.reverse()
    if progs[0] != first:
        progs.remove(first)
        progs.insert(0, first)
    layout, addr = [], 0
    for fn in progs:
        if addr < 0x2000 and addr + len(files[fn]) > 0x2000:
            addr = 0x4000
        if addr == 0x2000:
            addr = 0x4000
        layout.append((addr, fn))
        addr += len(files[fn])
    return layout


JUMP_OPS = {0xC3, 0xCD, 0xC2, 0xCA, 0xD2, 0xDA, 0xC4, 0xCC, 0xD4, 0xDC, 0xE2, 0xEA, 0xF2, 0xFA}
SLOTS = list(range(0x0000, 0x2000, 0x400)) + list(range(0x4000, 0x6000, 0x400))


def self_locate(d):
    """{base: score} - how many jump/call targets inside this ROM point back into it if loaded at base.
    Code jumps around inside itself a lot, so the true load address scores far above the rest."""
    t = [d[i + 1] | d[i + 2] << 8 for i in range(len(d) - 2) if d[i] in JUMP_OPS]
    out = {}
    for base in SLOTS:
        if base % len(d) or (base < 0x2000 < base + len(d)):
            continue
        out[base] = sum(1 for x in t if base <= x < base + len(d))
    return out


def located_layout(files):
    """Place code ROMs where their own jumps say they belong; data ROMs fill the gaps in name order.
    Returns (layout, uncertain_files)."""
    progs = program_files(files)
    if not progs:
        raise ValueError('no 1KB/2KB program ROMs found; pass an explicit --map')
    cands = []
    for fn, d in progs.items():
        sc = self_locate(d)
        ranked = sorted(sc.items(), key=lambda kv: -kv[1])
        top, second = ranked[0][1], (ranked[1][1] if len(ranked) > 1 else 0)
        confident = top >= 12 and top >= 1.6 * max(second, 1)
        cands.append((confident, top, fn, ranked))
    used, layout, later = set(), [], []
    for confident, top, fn, ranked in sorted(cands, key=lambda c: (not c[0], -c[1])):
        size = len(progs[fn])
        if not confident:
            later.append(fn); continue
        for base, _ in ranked:
            span = set(range(base, base + size, 0x400))
            if not span & used:
                used |= span; layout.append((base, fn)); break
        else:
            later.append(fn)
    uncertain = []
    std = lambda fn: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', fn.lower())]
    order = sorted(progs, key=std)          # plain natural order: 1.36, 2.35 ... (leading number first)
    placed_at = {fn: base for base, fn in layout}
    for fn in sorted(later, key=std):                    # data ROMs / weak signal
        size = len(progs[fn])
        prev = order[order.index(fn) - 1] if order.index(fn) > 0 else None
        tries = []
        if prev in placed_at:                            # right after the ROM before it in name order
            nxt = placed_at[prev] + len(progs[prev])
            tries.append(0x4000 if nxt == 0x2000 else nxt)
        tries += [b for b in SLOTS if b % size == 0 and not (b < 0x2000 < b + size)]
        for base in tries:
            span = set(range(base, base + size, 0x400))
            if base % size == 0 and base in SLOTS and not span & used:
                used |= span; layout.append((base, fn)); placed_at[fn] = base; uncertain.append(fn); break
    return sorted(layout), uncertain


def build(name, files, overrides=None):
    """Lay out one stand-alone set. Returns (mem, layout[(addr, fn, size)], notes)."""
    notes = []
    if overrides:
        lay = [(int(a, 16), fn) for a, fn in (o.split('=', 1) for o in overrides)]
        notes.append('layout: from --map')
    elif name in KNOWN and all(fn in files for _, fn in KNOWN[name]):
        lay = [(int(a, 16), fn) for a, fn in KNOWN[name]]
        notes.append(f'layout: known set "{name}"')
    else:
        lay, unsure = located_layout(files)
        notes.append('layout: self-located from each ROM\'s own jump targets'
                     + (f' (no code signal, placed in free slots: {", ".join(unsure)})' if unsure else ''))
    mem = bytearray(0x10000)
    for a, fn in lay:
        if fn not in files:
            raise ValueError(f'ROM file {fn} not found')
        mem[a:a + len(files[fn])] = files[fn]
    return mem, [(a, fn, len(files[fn])) for a, fn in lay], notes


def similarity(a, b):
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def place_onto(base_mem, base_layout, clone_files):
    """Match each clone ROM against a base image. Returns (placed, unplaced, score)."""
    progs = program_files(clone_files)
    placed, unplaced = [], []
    for fn in sorted(progs, key=natural_key):
        d = progs[fn]
        best = (0.0, None)
        for base, _, size in base_layout:
            for off in range(base, base + size - len(d) + 1, 0x400):
                s = similarity(d, base_mem[off:off + len(d)])
                if s > best[0]:
                    best = (s, off)
        if best[1] is not None and best[0] >= MATCH_THRESHOLD:
            placed.append((best[1], fn, len(d), best[0]))
        else:
            unplaced.append((fn, len(d), best[0]))
    score = sum(sz * s for _, _, sz, s in placed)
    return placed, unplaced, score


def build_clone(parent_mem, parent_layout, clone_files, bases=None, base_name=None):
    """Overlay clone ROMs onto a copy of the best-matching base (parent or sibling)."""
    progs = program_files(clone_files)
    candidates = bases or [(base_name or 'parent', parent_mem, parent_layout)]
    results = [(bname, bmem, blay) + place_onto(bmem, blay, clone_files) for bname, bmem, blay in candidates]
    # Stay on the parent (listed first) unless a sibling places more ROMs or scores clearly better (3%+).
    pick = results[0]
    for r in results[1:]:
        more = len(r[3]) > len(pick[3])
        if more or (len(r[3]) == len(pick[3]) and r[5] > pick[5] * 1.03):
            pick = r
    bname, bmem, blay, placed, unplaced, score = pick
    best = (score, bname, bmem, blay, placed, unplaced)
    _, bname, parent_mem, parent_layout, placed, unplaced = best
    mem = bytearray(parent_mem)
    notes = []
    placed_bytes = sum(p[2] for p in placed)
    total = placed_bytes + sum(u[1] for u in unplaced)
    if total and placed_bytes / total < 0.5:
        # Mostly new code: lay the clone out on its own instead.
        mem, layout, n2 = build('', clone_files)
        return mem, layout, ['clone: little in common with parent, laid out on its own'] + n2[1:]
    for off, fn, size, s in placed:
        mem[off:off + size] = progs[fn]
    # ROMs with no counterpart in the parent (bootleggers' extra code) go in the next free slot
    top = max([a + s for a, _, s in parent_layout] + [o + s for o, _, s, _ in placed])
    extra = []
    for fn, size, s in unplaced:
        slot = 0x4000 if 0x2000 <= top < 0x4000 else top    # $2000-$3FFF is RAM, never ROM
        mem[slot:slot + size] = progs[fn]
        extra.append((slot, fn, size))
        notes.append(f'NOTE: {fn} matches nothing in the parent (best {s:.0%}) - extra code, '
                     f'placed at ${slot:04X} (next free slot; verify)')
        top = slot + size
    # layout = parent files not completely overwritten + clone files
    covered = set()
    for off, _, size, _ in placed:
        covered.update(range(off, off + size))
    layout = [(a, fn if fn.startswith('(') else f'({bname}) {fn}', s) for a, fn, s in parent_layout
              if not all(x in covered for x in range(a, a + s))]
    layout += [(off, fn, size) for off, fn, size, _ in placed] + extra
    layout.sort()
    notes.append(f'layout: clone ROMs placed by matching against {bname} (' +
                 ', '.join(f'{fn}@${off:04X} {s:.0%}' for off, fn, _, s in placed) + ')')
    return mem, layout, notes


def expand(path, overrides=None, only=None):
    """Yield (name, mem, layout, notes, parent_name) for every set in a zip/folder."""
    files = read_files(path)
    parent = os.path.splitext(os.path.basename(path.rstrip('/\\')))[0]
    sets = split_sets(files, parent)
    pmem, playout, pnotes = build(parent, sets[parent], overrides)
    if not looks_like_reset_rom(pmem[0:16]):
        pnotes.append('WARNING: $0000 does not look like an Invaders-family reset ROM')
    if only in (None, parent):
        yield parent, pmem, playout, pnotes, None
    clones = sorted(c for c in sets if c != parent)
    first = {}
    for clone in clones:                                  # pass 1: on the parent only
        try:
            first[clone] = build_clone(pmem, playout, sets[clone], base_name=parent)
        except ValueError:
            pass
    bases = [(parent, pmem, playout)] + [
        (c, first[c][0], first[c][1]) for c in clones
        if c in first and len(program_files(sets[c])) >= 3]   # siblings that carry most of their own ROMs
    for clone in clones:
        if only not in (None, clone):
            continue
        if clone in KNOWN and all(fn in sets[clone] for _, fn in KNOWN[clone]):
            mem, layout, notes = build(clone, sets[clone])
            yield clone, mem, layout, notes, parent
            continue
        try:
            mem, layout, notes = build_clone(pmem, playout, sets[clone],
                                             bases=[b for b in bases if b[0] != clone])
        except ValueError as ex:
            yield clone, None, [], [f'ERROR: {ex}'], parent
            continue
        if not looks_like_reset_rom(mem[0:16]):
            notes.append('WARNING: $0000 does not look like an Invaders-family reset ROM')
        yield clone, mem, layout, notes, parent


def load(path, overrides=None, only=None):
    """Return (mem, layout, name, notes) for one set (the parent unless `only` names a clone)."""
    for name, mem, layout, notes, _ in expand(path, overrides, only):
        if mem is None:
            raise ValueError(notes[0])
        return mem, layout, name, notes
    raise ValueError(f'set "{only}" not found in {path}')
