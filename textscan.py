#!/usr/bin/env python3
"""Decode all the text hidden in a collection's ROMs, whatever letter codes each game uses, and flag the
interesting bits (strong ones printed live as found): programmer credits, anti-piracy wording, developer messages, years.

  python3 textscan.py <rom folder> [-o textscan] [--max-zip-mb 4] [--all]

For each set it finds the game's own encoding from words every game shows (SCORE, CREDIT, PLAYER, INSERT
COIN...), decodes every ROM, and writes:
  <out>/report.md          flagged strings, grouped by set (credits, anti-piracy, dev, years)
  <out>/text/<set>.txt     all readable text found in the set, with file and offset (to skim by eye)

A string in the ROM isn't necessarily shown on screen. Anything flagged that you don't recognise from
playing the game, or from The Cutting Room Floor (tcrf.net), is worth a closer look.
Merged sets: a clone is decoded with its parent's files too, but only the clone's own files are listed.
"""
import argparse
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trapscan.textenc import find_encodings, strings, flags, strong   # noqa: E402
from trapscan import skiplist   # noqa: E402

MAX_FILE = 1024 * 1024


def sets_in_zip(path):
    """{set name: ({file: bytes} own files, {file: bytes} parent files)} for a merged or standalone zip."""
    name = os.path.splitext(os.path.basename(path))[0]
    files = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.is_dir() and info.file_size <= MAX_FILE:
                files[info.filename] = z.read(info)
    parent = {f: d for f, d in files.items() if '/' not in f}
    out = {name: (parent, {})}
    clones = sorted({f.split('/')[0] for f in files if '/' in f})
    for c in clones:
        own = {f: d for f, d in files.items() if f.startswith(c + '/')}
        out[c] = (own, parent)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('-o', '--out', default='textscan')
    ap.add_argument('--max-zip-mb', type=float, default=4.0)
    skiplist.add_args(ap)
    ap.add_argument('--verbose', action='store_true', help='print every flagged line live, not just the strong ones')
    ap.add_argument('--all', action='store_true', help='list every set in report.md, not only flagged ones')
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, 'text'), exist_ok=True)

    skip = skiplist.parse(args)
    zips = sorted(os.path.join(r, f) for r, _, fs in os.walk(args.folder) for f in fs
                  if f.lower().endswith('.zip') and not (skip and skiplist.skipped(f, skip)))
    report_strong, report_top, report, n_sets, n_enc, n_flag = [], [], [], 0, 0, 0
    for zi, path in enumerate(zips, 1):
        if zi % 500 == 0:
            print(f'  {zi} zips...', file=sys.stderr, flush=True)
        if os.path.getsize(path) > args.max_zip_mb * 1024 * 1024:
            continue
        try:
            sets = sets_in_zip(path)
        except Exception as ex:
            print(f'  skip {path}: {ex}', file=sys.stderr)
            continue
        for set_name, (own, parent) in sets.items():
            if not own:
                continue
            n_sets += 1
            encs = find_encodings(list(own.values()) + list(parent.values()))
            if not encs:
                continue
            n_enc += 1
            lines, flagged = [], []
            for enc in encs:
                base, step, space, digits, anchors = enc
                lines.append(f'# encoding: A=${base:02X} step {step} space={",".join(f"${s:02X}" for s in space) or "?"}'
                             f' digits={"$%02X" % digits if digits is not None else "?"} '
                             f'(found {", ".join(a.replace("?", " ") for a in anchors)})')
                for fn in sorted(own):
                    for off, s in strings(own[fn], enc):
                        lines.append(f'{fn}\t+{off:05X}\t{s}')
                        f = flags(s)
                        if f:
                            flagged.append((fn, off, s, f))
            with open(os.path.join(args.out, 'text', f'{set_name}.txt'), 'w') as fh:
                fh.write('\n'.join(lines) + '\n')
            if flagged or args.all:
                n_flag += bool(flagged)
                interesting = any(c != 'year' for _, _, _, f in flagged for c, _ in f)
                is_strong = any(strong(s) for _, _, s, _ in flagged)
                block = [f'\n## {set_name}  ({os.path.basename(path)})\n']
                seen = set()
                for fn, off, s, f in flagged:
                    if s in seen:
                        continue
                    seen.add(s)
                    cats = ', '.join(sorted({c for c, _ in f}))
                    star = '**★** ' if strong(s) else ''
                    block.append(f'- {star}`{s[:100]}`  — {cats}  ({fn} +{off:05X})')
                    if strong(s) or args.verbose:
                        print(f'  {set_name:12} [{cats}] {s[:90]}', flush=True)
                (report_strong if is_strong else report_top if interesting else report).extend(block)

    with open(os.path.join(args.out, 'report.md'), 'w') as fh:
        fh.write(f'# Hidden text scan of {args.folder}\n\n{n_sets} sets; encoding found in {n_enc}; '
                 f'{n_flag} with flagged text. Full text per set in text/.\n'
                 'Flags: credits (PROGRAM, DESIGN, BY...), anti-piracy (COPY, PIRATE, ILLEGAL...), '
                 'dev (TEST, SECRET, HELLO...), year (19xx). Check finds against tcrf.net before calling them new.\n')
        fh.write('\n# ★ Strong: named credits, anti-piracy, personal or secret messages\n'
                 'Lines marked ★ have a strong word (PIRATE, STOLEN, PROGRAMMED BY, THANKS, HELLO, LOVE, SECRET...).\n'
                 + '\n'.join(report_strong) + '\n')
        fh.write('\n# Other flagged text (test menus, LICENSED TO, BY..., VERSION)\n' + '\n'.join(report_top) + '\n')
        fh.write('\n# Sets with only a copyright year\n' + '\n'.join(report) + '\n')
    print(f'\n{n_sets} sets, encoding found in {n_enc}, {n_flag} with flagged text. '
          f'Report: {args.out}/report.md, full text: {args.out}/text/')


if __name__ == '__main__':
    main()
