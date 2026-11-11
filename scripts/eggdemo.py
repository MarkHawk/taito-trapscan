#!/usr/bin/env python3
"""Show the Space Invaders "TAITO COP" easter egg, and its "HOEI COP" copy in Space Stranger, in the emulator.

  python3 scripts/eggdemo.py invaders.zip          # -> taito-cop.png
  python3 scripts/eggdemo.py sstrangr.zip          # -> hoei-cop.png

During the attract-mode demo it holds the first button combination until the game accepts it ($201E = 1),
then the second, and saves a screenshot with the message under the scores.

  Space Invaders : P2 Start + Fire + Left + Right, then P1 Start + Fire + Left   (port 1)
  Space Stranger : P2 Start + Fire + Left,         then P1 Start + Fire          (port $42; the egg's mask also
                   needs bit 4, which is the cabinet switch and reads 1 on an upright, so it can't fire on a
                   cocktail table)
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from trapscan.boards import SpaceStrangerBoard, SS   # noqa: E402
from trapscan.emu8080 import Board                   # noqa: E402

INVADERS = [(0x0000, '9316b-0869_m739h.h1'), (0x0800, '9316b-0856_m739g.g1'),
            (0x1000, '9316b-0855_m739f.f1'), (0x1800, '9316b-0854_m739e.e1')]
SSTRANGR = [(0x400 * i, f'hss-0{i + 1}.{58 + i}') for i in range(8)]


def load(zpath, layout):
    z = zipfile.ZipFile(zpath)
    names = {n.rsplit('/', 1)[-1]: n for n in z.namelist()}
    mem = bytearray(0x10000)
    for a, n in layout:
        d = z.read(names[n]); mem[a:a + len(d)] = d
    return mem


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__); return 0 if len(sys.argv) == 2 else 2
    zpath = sys.argv[1]
    names = {n.rsplit('/', 1)[-1] for n in zipfile.ZipFile(zpath).namelist()}
    if 'hss-01.58' in names:
        b = SpaceStrangerBoard(load(zpath, SSTRANGR))
        setp = lambda v: setattr(b, 'inputs', 0x10 | v)
        step1, step2, out = SS['start2'] | SS['fire'] | SS['left'], SS['start1'] | SS['fire'], 'hoei-cop.png'
    else:
        b = Board(load(zpath, INVADERS))
        setp = lambda v: setattr(b, 'port1', 0x08 | v)
        step1, step2, out = 0x02 | 0x10 | 0x20 | 0x40, 0x04 | 0x10 | 0x20, 'taito-cop.png'
    m = b.cpu.m
    for _ in range(600):
        b.run_frame()                       # into the attract demo
    for f in range(3000):
        setp(step2 if m[0x201E] else step1)
        b.run_frame()
        if m[0x201E] and f > 0:
            setp(step2)
            for _ in range(120):               # keep the second combination held while the message is drawn
                b.run_frame()
            break
    else:
        print('first combination never accepted'); return 1
    setp(0)
    b.screenshot(out)
    print(f'egg triggered; screenshot saved to {out}')


if __name__ == '__main__':
    sys.exit(main())
