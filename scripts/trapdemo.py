#!/usr/bin/env python3
"""Screenshots of the credit traps firing (or not) in attract mode, from trapscan's own emulator.

  python3 scripts/trapdemo.py [ROM_FOLDER] [--out DIR] [--only NAME]     # folder default ~/roms/scope277, DIR default docs/img

For each case it runs the set, holds the combination in the attract demo, watches the credit counter ($20EB) and
lets go as soon as it first changes (a held Start 1 would begin a game and spend a credit), then saves a screenshot
(Pillow needed) on the first frame where the CREDIT line shows the new value. A "nothing happens" case is saved at
the same frame as the case it is compared with. Images are 448x512: the 224x256 screen upright, doubled, nearest-neighbour.

  lrescue-genuine.png        lrescue as shipped, Start 1 + Fire + Right held: nothing, CREDIT 00
  lrescue-desterth.png       desterth as shipped, same buttons: CREDIT 03
  lrescue-mlandera.png       mlandera as shipped, same buttons: CREDIT 03
  invadpt2-genuine.png       invadpt2 with port 0 = $00, Start 1 + Start 2 + Fire + Left: nothing, CREDIT 00
  invadpt2-one-line-high.png invadpt2 with port 0 = $02 (the board reads one line high): CREDIT 02
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from trapscan.romload import load            # noqa: E402
from trapscan.emu8080 import Board           # noqa: E402

BTN = {'coin': 0x01, 'start2': 0x02, 'start1': 0x04, 'fire': 0x10, 'left': 0x20, 'right': 0x40}
LR_COMBO = ('start1+fire+right', 1000, 2500)
IP_COMBO = ('start1+start2+fire+left', 200, 260)

# name, zip, clone inside it, port 0, combo (buttons, from frame, to frame), expected credits, frame source, frames to run
CASES = [
    ('lrescue-desterth', 'lrescue.zip', 'desterth', 0x00, LR_COMBO, 3, None, 2500),
    ('lrescue-mlandera', 'mlandera.zip', None, 0x00, LR_COMBO, 3, None, 2500),
    ('lrescue-genuine', 'lrescue.zip', None, 0x00, LR_COMBO, 0, 'lrescue-desterth', 2500),
    ('invadpt2-one-line-high', 'invadpt2.zip', None, 0x02, IP_COMBO, 2, None, 400),
    ('invadpt2-genuine', 'invadpt2.zip', None, 0x00, IP_COMBO, 0, 'invadpt2-one-line-high', 1500),
]

# "Nothing happens" cases whose shot must be later than the armed case's, so the attract screen has finished drawing
# (invadpt2 is still printing its copyright line, "*TAITO COR", at the armed case's frame)
LATE_SHOT = {'invadpt2-genuine': 600}


def hold_mask(spec):
    v = 0
    for k in spec.split('+'):
        v |= BTN[k]
    return v


def strip(m):
    """The CREDIT line's video RAM: the bottom 16 pixel rows (screen y 240-255) of the right-hand 96 columns."""
    return bytes(m[0x2400 + x * 32 + yb] for x in range(128, 224) for yb in (0, 1))


def play(folder, zipname, clone, port0, combo, upto, release_at=None):
    """Yield (frame, board) after each frame. The combo is held from its start frame until `release_at` (or its end)."""
    mem, _, _, _ = load(os.path.join(folder, zipname), None, clone)
    b = Board(mem)
    b.port0 = port0
    spec, f0, f1 = combo
    mask = hold_mask(spec)
    for f in range(upto):
        held = f0 <= f < f1 and (release_at is None or f <= release_at)
        b.port1 = 0x08 | (mask if held else 0)
        b.run_frame()
        yield f, b


def find_shot(name, folder, zipname, clone, port0, combo, upto, like=None):
    """Return (change frame, shot frame, release frame) for a case.

    Armed case: hold the combo until the credit counter ($20EB) first changes, then let go (a held Start 1 would
    begin a game and spend a credit). The shot is the first frame after that where the CREDIT line has settled to
    its final value and the screen has stopped changing, ie the game has redrawn it.
    "Nothing happens" case (`like` = the armed case's (change, shot, release)): the same frame of the demo (or the
    frame in LATE_SHOT if later), or the first frame after it that shows a CREDIT line at all."""
    if like is not None:
        change, shot, release = like
        shot = max(shot, LATE_SHOT.get(name, 0))
        for f, b in play(folder, zipname, clone, port0, combo, upto, release):
            if f >= shot and any(strip(b.cpu.m)):
                return None, f, release
        return None, None, release
    change = None
    for f, b in play(folder, zipname, clone, port0, combo, upto):
        if b.cpu.m[0x20EB] != 0:
            change = f; break
    if change is None:
        return None, None, None
    rows, prev = [], None
    for f, b in play(folder, zipname, clone, port0, combo, change + 200, change):
        if f >= change:
            vram = bytes(b.cpu.m[0x2400:0x4000])
            rows.append((f, strip(b.cpu.m), vram == prev)); prev = vram
    final = rows[-1][1]
    for f, st, still in rows:
        if st == final and still:
            return change, f, change
    return change, None, change


def shoot(folder, zipname, clone, port0, combo, upto, release, shot, path):
    for f, b in play(folder, zipname, clone, port0, combo, upto, release):
        if f == shot:
            b.screenshot(path)
            return b.cpu.m[0x20EB]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder', nargs='?', default='~/roms/scope277', help='MAME ROM folder (default ~/roms/scope277)')
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'docs', 'img'), help='output folder (default docs/img)')
    ap.add_argument('--only', help='one case name, e.g. lrescue-mlandera')
    args = ap.parse_args()
    folder = os.path.expanduser(args.folder)
    os.makedirs(args.out, exist_ok=True)
    found, bad = {}, 0
    for name, zipname, clone, port0, combo, want, like, upto in CASES:
        try:
            change, shot, release = find_shot(name, folder, zipname, clone, port0, combo, upto, found.get(like))
            if shot is None:
                print(f'BAD {name}: no suitable frame found'); bad += 1; continue
            found[name] = (change, shot, release)
            if args.only not in (None, name):
                continue                      # only needed to give a later case its frame
            path = os.path.join(args.out, name + '.png')
            cr = shoot(folder, zipname, clone, port0, combo, upto, release, shot, path)
            bad += cr != want
            when = f'counter changed at frame {change}, ' if change is not None else ''
            print(f'{"ok  " if cr == want else "BAD "}{name}: {when}saved frame {shot}, $20EB = {cr:02X} (expected {want:02X}) -> {os.path.normpath(path)}')
        except (OSError, ValueError, KeyError) as ex:
            print(f'{name}: {ex}'); bad += 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
