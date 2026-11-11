#!/usr/bin/env python3
"""List exactly what every clone and bootleg changed from its parent: changed bytes, and any changed text
decoded in the game's own letter codes.

  python3 clonediff.py <rom folder> [-o clonediff.md] [--max-zip-mb 4] [--context 6]

Merged sets (MAME's default: clone files in a sub-folder of the parent's zip) are compared with the parent
in the same zip. Non-merged/split sets (one zip per clone) are compared with their closest relative: the
other zip sharing the most identical ROM files (found from the zips' CRCs, without unpacking).

Each clone ROM is paired with the parent ROM of the same name, else the same size that matches best. The
report lists, per clone: identical files, files changed in a few places (with every changed run: offset,
old -> new bytes, and old -> new text if it decodes), and files that are new or rewritten.

The Moon Lander pair (mlander vs mlandera) and the protection patches in bootlegs are the kind of thing
this shows up: a handful of changed bytes in an otherwise identical ROM.
"""
import argparse
import collections
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trapscan.textenc import find_encodings, table   # noqa: E402

MAX_FILE = 1024 * 1024


def runs(a, b, join=4):
    """Changed byte runs between equal-length a and b, merging runs closer than `join` bytes."""
    out, i, n = [], 0, len(a)
    while i < n:
        if a[i] != b[i]:
            j = i
            last = i
            while j < n and j - last <= join:
                if a[j] != b[j]:
                    last = j
                j += 1
            out.append((i, last + 1))
            i = last + 1
        else:
            i += 1
    return out


def similarity(a, b):
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x == y for x, y in zip(a, b)) / len(a)


def decode(bs, tab):
    t = bytes(bs).translate(tab)
    s = ''.join(chr(c) if c else '·' for c in t)
    return s if sum(ch.isalpha() for ch in s) >= 3 else None


def textlike(bs, tab):
    t = bytes(bs).translate(tab)
    letters = sum(65 <= c <= 90 for c in t)
    return len(set(c for c in t if 65 <= c <= 90)) >= 2 and letters >= 2 and sum(c != 0 for c in t) >= 0.8 * len(t) and letters >= 0.5 * len(t)


def compare(own, parent, encs, ctx, max_runs=40):
    """Lines describing clone files `own` against `parent` files."""
    lines, counts = [], collections.Counter()
    tabs = [table(*e[:4]) for e in encs[:1]]
    pfiles = dict(parent)
    for fn in sorted(own):
        data = own[fn]
        short = fn.split('/', 1)[-1]
        cand = [p for p in pfiles if p.split('/', 1)[-1] == short and len(pfiles[p]) == len(data)]
        if not cand:
            same = [(similarity(data, pfiles[p]), p) for p in pfiles if len(pfiles[p]) == len(data)]
            same = [x for x in same if x[0] >= 0.5]
            cand = [max(same)[1]] if same else []
        if not cand:
            counts['new'] += 1
            lines.append(f'- `{short}` ({len(data)} bytes): **new or rewritten** (no parent ROM of this size matches 50%+)')
            continue
        p = cand[0]
        pd = pfiles[p]
        if pd == data:
            counts['same'] += 1
            continue
        rs = runs(pd, data)
        nbytes = sum(sum(pd[k] != data[k] for k in range(s, e)) for s, e in rs)
        sim = similarity(pd, data)
        if sim < 0.9:
            counts['rewritten'] += 1
            lines.append(f'- `{short}` vs parent `{p}`: **largely rewritten** ({sim:.0%} identical, {nbytes} bytes differ)')
            continue
        counts['changed'] += 1
        lines.append(f'- `{short}` vs parent `{p}`: {nbytes} byte(s) changed in {len(rs)} place(s)')
        for s, e in rs[:max_runs]:
            old, new = pd[s:e], data[s:e]
            row = f'    - +{s:05X}: `{old.hex(" ").upper()[:3 * 24]}` → `{new.hex(" ").upper()[:3 * 24]}`'
            for tab in tabs:
                # only when the changed bytes themselves read as text (mostly letters/spaces), not code
                if textlike(old, tab) or textlike(new, tab):
                    a0, a1 = max(0, s - ctx), min(len(data), e + ctx)
                    to, tn = decode(pd[a0:a1], tab), decode(data[a0:a1], tab)
                    if to != tn:
                        row += f'  text "{to}" → "{tn}"'
            lines.append(row)
        if len(rs) > max_runs:
            lines.append(f'    - ... {len(rs) - max_runs} more')
    return lines, counts


def read_zip(path):
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir() and i.file_size <= MAX_FILE}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('-o', '--out', default='clonediff.md')
    ap.add_argument('--max-zip-mb', type=float, default=4.0)
    ap.add_argument('--context', type=int, default=6, help='bytes of context when decoding changed text')
    args = ap.parse_args()

    zips = sorted(os.path.join(r, f) for r, _, fs in os.walk(args.folder) for f in fs if f.lower().endswith('.zip')
                  and os.path.getsize(os.path.join(r, f)) <= args.max_zip_mb * 1024 * 1024)

    # CRC index for non-merged sets: (crc, size) -> zips holding that ROM at the top level
    crcs, index = {}, collections.defaultdict(set)
    for path in zips:
        try:
            with zipfile.ZipFile(path) as z:
                top = {(i.CRC, i.file_size) for i in z.infolist() if not i.is_dir() and '/' not in i.filename}
        except Exception as ex:
            print(f'  skip {path}: {ex}', file=sys.stderr)
            continue
        crcs[path] = top
        for k in top:
            index[k].add(path)

    out = [f'# Clone and bootleg differences: {args.folder}\n',
           'Each clone against its parent (merged sets) or closest relative (one zip per set). '
           'Text is decoded with the parent\'s letter codes where they could be found.\n']
    totals, done = collections.Counter(), set()
    for zi, path in enumerate(zips, 1):
        if zi % 500 == 0:
            print(f'  {zi} zips...', file=sys.stderr, flush=True)
        if path not in crcs:
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            files = read_zip(path)
        except Exception:
            continue
        parent = {f: d for f, d in files.items() if '/' not in f}
        pairs = []
        clones = sorted({f.split('/')[0] for f in files if '/' in f})
        for c in clones:
            pairs.append((c, name, {f: d for f, d in files.items() if f.startswith(c + '/')}, parent))
        if not clones and crcs[path]:
            # non-merged: closest relative = other zip sharing the most identical ROMs (and not identical)
            share = collections.Counter(z for k in crcs[path] for z in index[k] if z != path)
            best = [z for z, n in share.most_common(3) if n and crcs[z] != crcs[path]]
            # only treat this zip as the clone if it's not the relative's parent: prefer the one with more files
            if best:
                rel = best[0]
                if frozenset((rel, path)) not in done:          # each pair once
                    done.add(frozenset((rel, path)))
                    try:
                        relfiles = {f: d for f, d in read_zip(rel).items() if '/' not in f}
                    except Exception:
                        relfiles = None
                    if relfiles:
                        own = {f: d for f, d in parent.items()
                               if (zipfile.crc32(d) & 0xFFFFFFFF, len(d)) not in crcs[rel]}
                        if own:
                            pairs.append((name, os.path.splitext(os.path.basename(rel))[0], own, relfiles))
        for clone, pname, own, pfiles in pairs:
            encs = find_encodings(list(pfiles.values()))
            lines, counts = compare(own, pfiles, encs, args.context)
            totals['sets'] += 1
            totals.update(counts)
            if not lines:
                continue
            summ = ', '.join(f'{v} {k}' for k, v in counts.items())
            out.append(f'\n## {clone} (vs {pname})  — {summ}\n')
            out.extend(lines)
            changed_text = [l for l in lines if 'text "' in l]
            print(f'  {clone:14} vs {pname:12} {summ}' + (f'  [{len(changed_text)} text change(s)]' if changed_text else ''),
                  flush=True)

    out.insert(2, f'\n{totals["sets"]} clones compared: {totals["changed"]} files changed in a few places, '
                  f'{totals["rewritten"]} largely rewritten, {totals["new"]} new, {totals["same"]} identical.\n')
    with open(args.out, 'w') as fh:
        fh.write('\n'.join(out) + '\n')
    print(f'\nReport: {args.out}')


if __name__ == '__main__':
    main()
