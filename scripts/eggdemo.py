#!/usr/bin/env python3
"""Show the Space Invaders "TAITO COP" easter egg, and its "HOEI COP" copy in Space Stranger, in the emulator.

  python3 scripts/eggdemo.py invaders.zip [--gif]   # -> taito-cop.png (and taito-cop.gif)
  python3 scripts/eggdemo.py sstrangr.zip [--gif]   # -> hoei-cop.png (and hoei-cop.gif)

During the attract-mode demo it holds the first button combination until the game accepts it ($201E = 1),
then the second, and saves a screenshot with the message under the scores. --gif also writes a captioned GIF of
the run (2x, 15 emulator frames in 4, from the last half second of the plain demo to 2 s after the screenshot, the
last frame held for 2 s); the caption names the buttons held at each point.

  Space Invaders : P2 Start + Fire + Left + Right, then P1 Start + Fire + Left   (port 1)
  Space Stranger : P2 Start + Fire + Left,         then P1 Start + Fire          (port $42; the egg's mask also
                   needs bit 4, which is the cabinet switch and reads 1 on an upright, so it can't fire on a
                   cocktail table)
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
from trapscan.boards import SpaceStrangerBoard, SS   # noqa: E402
from trapscan.emu8080 import Board                   # noqa: E402
import gifutil                                       # noqa: E402

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
    args = sys.argv[1:]
    gif = '--gif' in args
    args = [a for a in args if a != '--gif']
    if len(args) != 1 or args[0] in ('-h', '--help'):
        print(__doc__); return 0 if len(args) == 1 else 2
    zpath = args[0]
    names = {n.rsplit('/', 1)[-1] for n in zipfile.ZipFile(zpath).namelist()}
    if 'hss-01.58' in names:
        b = SpaceStrangerBoard(load(zpath, SSTRANGR))
        setp = lambda v: setattr(b, 'inputs', 0x10 | v)
        step1, step2, out = SS['start2'] | SS['fire'] | SS['left'], SS['start1'] | SS['fire'], 'hoei-cop.png'
        t1, t2 = 'Holding P2 Start + Fire + Left', 'Then P1 Start + Fire'
    else:
        b = Board(load(zpath, INVADERS))
        setp = lambda v: setattr(b, 'port1', 0x08 | v)
        step1, step2, out = 0x02 | 0x10 | 0x20 | 0x40, 0x04 | 0x10 | 0x20, 'taito-cop.png'
        t1, t2 = 'Holding P2 Start + Fire + Left + Right', 'Then P1 Start + Fire + Left'
    m = b.cpu.m
    frames, n = [], [0]

    def tick(caption):
        """Run one emulator frame, keeping every STEP-th one for the GIF once the plain demo is nearly over."""
        b.run_frame()
        n[0] += 1
        if gif and n[0] > 600 - 30 and n[0] % gifutil.STEP == 0:
            frames.append(gifutil.frame(b, caption))

    for _ in range(600):
        tick('No buttons held')             # into the attract demo
    for f in range(3000):
        second = bool(m[0x201E])
        setp(step2 if second else step1)
        tick(t2 if second else t1)
        if m[0x201E] and f > 0:
            setp(step2)
            for _ in range(120):               # keep the second combination held while the message is drawn
                tick(t2)
            break
    else:
        print('first combination never accepted'); return 1
    setp(0)
    b.screenshot(out)
    print(f'egg triggered; screenshot saved to {out}')
    if gif:
        for _ in range(120):
            tick('Released')
        path = os.path.splitext(out)[0] + '.gif'
        gifutil.save(frames, path)
        print(f'GIF saved to {path} ({os.path.getsize(path) // 1024} KB)')


if __name__ == '__main__':
    sys.exit(main())
