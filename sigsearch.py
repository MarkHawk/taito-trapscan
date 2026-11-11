#!/usr/bin/env python3
"""Search a whole ROM collection for the Taito trap code, whatever game or driver it is in.

  python3 sigsearch.py <rom folder> [-o sigsearch.csv] [--max-zip-mb 4]

Opens every .zip (and loose ROM file) under the folder, merged-set clone folders included, and looks
for the exact byte sequences of the 1979 Taito traps and their arming checks, plus looser variants
(the same logic with different addresses). Byte searching doesn't care about ROM layout or CPU mode,
so it finds the code even in sets the scanner can't lay out or run.

Live: each hit is printed as it's found (HIT lines), except the known combo values below and FREE PLAY
text, which only go to the CSV and summary. --quiet turns the live lines off.

Output: one CSV row per hit (zip, file inside it, offset, signature), and a summary per signature.

Merged sets keep only a clone's changed files, so a clone that inherits the trap from its parent's ROMs
is listed under the parent only. Known COMBO_76_ANY values: D6 72 / FE 34 (Space Invaders "TAITO COP"
egg), D6 52 (Part II "TAITO CORP" egg), FE 54 (Lunar Rescue trap), FE 36 / FE 56 (Part II traps 1 / 2).
Anything else is new and worth reading.

KICK_TEXT: the "kick me for a free game" test - KICK / KICK ME / FREE GAME / FREE CREDIT wording in any
letter encoding (ASCII, A=$00, A=$0A, every-second-code ...), any CPU. FREE PLAY is reported separately as
FREE_PLAY_TEXT because it's ordinary DIP-switch text. Short words like KICK can turn up by chance in big
ROMs, so read the bytes around a hit. Turn it off with --no-text.
"""
import argparse
import csv
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trapscan.kickme import best_text_hits, NORMAL   # noqa: E402
from trapscan import skiplist   # noqa: E402

# (name, regex over bytes, what it is). Exact = byte-for-byte from the ROMs; loose = same instruction
# shape with any addresses/values, to catch relocated or edited copies.
SIGS = [
    ('LR_TRAP_EXACT', rb'\xE6\x76\xFE\x54\xC0\x2E\xED\x26\x20\x7E\xA7\xC8\x2B\x2B\x36\x03',
     'Lunar Rescue trap: combo Start1+Fire+Right -> credits = 3'),
    ('LR_TRAP_DISABLED', rb'\xE6\x76\xFE\x54\xC0\x2E\xED\x26\x20\x7E\xA7\xC9\x2B\x2B\x36\x03',
     'Lunar Rescue trap with RZ patched to RET (disabled, as in Rescate Lunar)'),
    ('LR_TRAP_LOOSE', rb'\xE6\x76\xFE.\xC0\x2E.\x26.\x7E\xA7[\xC8\xC9]\x2B\x2B\x36.',
     'Lunar Rescue-style trap, any combo/addresses'),
    ('LR_COPYRIGHT_CHECK', rb'\x1A\xD6.\xC0\x0A\xD6.\xC0\x7E\xD6.\xC0\xAF\x32',
     'screen-memory check that disarms the Lunar Rescue trap'),
    ('P2_TRAP1_EXACT', rb'\x26\x1F\x2E\xE4\x24\x2D\x7E\xA7\xC8\xCD..\xE6\x76\xFE\x36\xC0\x2E\xEC\x2D\x26\x1F\x24\x36\x02',
     'Space Invaders Part II trap 1: combo Start1+Start2+Fire+Left -> credits = 2'),
    ('P2_TRAP1_LOOSE', rb'\x26.\x2E.[\x24\x25][\x2C\x2D]\x7E\xA7[\xC8\xC9]\xCD..\xE6.\xFE.\xC0\x2E.[\x2C\x2D]\x26.[\x24\x25]\x36.',
     'Part II-style disguised-pointer trap, any combo/addresses'),
    ('P2_BOARD_CHECK', rb'\xDB\x00\xE6\x0A\xFE\x0A\xCA\x00\x00',
     'Part II port-0 board check (resets if both lines high)'),
    ('P2_ROM_CHECK', rb'\x1A\xFE.\xC0\x13\x1A\xBC\xC0\x13\x1A\xBD\xC0\x13\x1A\xB8',
     'Part II ROM-bytes check that arms trap 2'),
    ('P2_TRAP2', rb'\xE6\x76\xFE\x56\xC2..\x2E\xEA\x2C\x36\x02\x2E\xCC\x36\x02',
     'Part II trap 2 (buggy: writes ROM)'),
    ('P2_SHADOW_CHECK', rb'\x21\xEB\x20\x7E\x2E\xCC\xBE\xC2\x03\x00',
     'Part II shadow-credit check (restart on mismatch)'),
    ('COMBO_76_ANY', rb'\xE6\x76[\xFE\xD6][\x1C-\x7E]',
     'any Taito-style control mask $76 compared with a value (combo check; easter eggs match too)'),
]
SIGS = [(n, re.compile(p, re.S), d) for n, p, d in SIGS]


TEXT_SIGS = [('KICK_TEXT', 'kick-me / free-game wording in any letter encoding (the "kick me for a free game" test)'),
             ('FREE_PLAY_TEXT', 'FREE PLAY wording (usually ordinary DIP-switch text)')]
TEXT = [True]


def scan_bytes(data):
    if TEXT[0]:
        for off, ph, base, step in best_text_hits(data):
            name = 'FREE_PLAY_TEXT' if ph.replace(' ', '?') in NORMAL else 'KICK_TEXT'
            yield name, off, f'"{ph}" (A=${base:02X}, step {step}) ' + data[off:off + len(ph)].hex(' ').upper()
    for name, rx, _ in SIGS:
        for m in rx.finditer(data):
            if name == 'COMBO_76_ANY' and bin(m.group(0)[-1]).count('1') < 2:
                continue                      # one button (e.g. CPI $40 = Right while playing), not a combo
            yield name, m.start(), m.group(0).hex(' ').upper()


KNOWN_COMBOS = {'E6 76 D6 72', 'E6 76 FE 34', 'E6 76 D6 52', 'E6 76 FE 54', 'E6 76 FE 36', 'E6 76 FE 56'}


def live(row):
    """Print a hit as soon as it's found (stdout, flushed). Known easter-egg/trap combo values are left
    to the CSV and summary so they don't drown the new ones."""
    zipname, fn, off, name, hexs = row
    if name == 'COMBO_76_ANY' and hexs in KNOWN_COMBOS:
        return
    if name == 'FREE_PLAY_TEXT':
        return
    print(f'  HIT {name:16} {zipname} {fn} {off}  {hexs}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('-o', '--out', default='sigsearch.csv')
    ap.add_argument('--max-zip-mb', type=float, default=4.0,
                    help='skip zips larger than this (8-bit-era sets are tiny; default 4 MB)')
    skiplist.add_args(ap)
    ap.add_argument('--quiet', action='store_true', help='no live HIT lines, just progress and the summary')
    ap.add_argument('--no-text', action='store_true', help='skip the kick-me / free-game text search')
    args = ap.parse_args()
    TEXT[0] = not args.no_text
    skip = skiplist.parse(args)
    n_skip = 0

    rows, zips, skipped, errors = [], 0, 0, 0
    for root, _, names in os.walk(args.folder):
        for fn in sorted(names):
            path = os.path.join(root, fn)
            if skip and skiplist.skipped(fn, skip):
                n_skip += 1
                continue
            try:
                if fn.lower().endswith('.zip'):
                    if os.path.getsize(path) > args.max_zip_mb * 1024 * 1024:
                        skipped += 1; continue
                    zips += 1
                    if zips % 500 == 0:
                        print(f'  {zips} zips...', file=sys.stderr, flush=True)
                    with zipfile.ZipFile(path) as z:
                        for info in z.infolist():
                            if info.is_dir() or info.file_size > 1024 * 1024:
                                continue
                            data = z.read(info)
                            for name, off, hexs in scan_bytes(data):
                                rows.append((os.path.relpath(path, args.folder), info.filename, f'0x{off:04X}', name, hexs))
                                if not args.quiet: live(rows[-1])
                elif os.path.getsize(path) <= 64 * 1024 and not fn.lower().endswith(('.chd', '.7z', '.txt', '.md')):
                    data = open(path, 'rb').read()
                    for name, off, hexs in scan_bytes(data):
                        rows.append((os.path.relpath(path, args.folder), '', f'0x{off:04X}', name, hexs))
                        if not args.quiet: live(rows[-1])
            except Exception as ex:  # unreadable or odd archive: note and carry on
                errors += 1
                print(f'  skip {path}: {ex}', file=sys.stderr)

    with open(args.out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['zip', 'file', 'offset', 'signature', 'bytes'])
        w.writerows(rows)

    print(f'\nScanned {zips} zips ({skipped} larger than {args.max_zip_mb} MB skipped, {n_skip} skipped by name, '
          f'{errors} unreadable).')
    for name, _, desc in SIGS + [(n, None, d) for n, d in TEXT_SIGS]:
        sets = sorted({(r[0] + ('/' + r[1].split('/')[0] if '/' in r[1] else '')) for r in rows if r[3] == name})
        print(f'\n{name} - {desc}\n  {len(sets)} set(s): ' + (', '.join(s.replace(".zip", "") for s in sets) if sets else 'none'))
    print(f'\nAll hits written to {args.out}')


if __name__ == '__main__':
    main()
