#!/usr/bin/env python3
"""verify.py - check that the code listings and emulator results in README.md and docs/ match the real ROMs.

  python3 scripts/verify.py ROM_FOLDER        # ROM_FOLDER: your MAME ROM folder (required)

Prints one PASS/FAIL line per check and exits non-zero if any fail. A set that cannot be found counts as a FAIL.
Uses trapscan's loader (romload.expand, so clones inside merged zips work) and emulator (emu8080.Board),
driven the way `trapscan.py run` drives them.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from trapscan.romload import expand          # noqa: E402
from trapscan.emu8080 import Board           # noqa: E402

BTN = {'coin': 0x01, 'start2': 0x02, 'start1': 0x04, 'fire': 0x10, 'left': 0x20, 'right': 0x40}

LR = bytes.fromhex('CD7C03E676FE54C02EED26207EA7C82B2B3603')
LR_ADDR = 0x47D8
IP_A = bytes.fromhex('261F2EE4242D7EA7C8CD491FE676FE36C02EEC2D261F2436022ECC3602C9')
IP_A_ADDR = 0x4186
IP_B = bytes.fromhex('DB00E60AFE0ACA0000A700C0 21E32036 00C9'.replace(' ', ''))
IP_B_ADDR = 0x459C
RESCLUNAR = bytearray(LR); RESCLUNAR[0x47E6 - LR_ADDR] = 0xC9
RESCLUNAR = bytes(RESCLUNAR)

LRESCUE_CLONES = ['desterth', 'escmars', 'mlander', 'mlandera', 'grescue', 'lrescueabl', 'lrescuem', 'lrescuem2', 'resclunar']
INVADPT2_CLONES = ['invadpt2a', 'invadpt2br', 'invaddlx', 'moonbase', 'moonbasea']

fails = 0
cache = {}      # zip path -> {set name: mem or None}
where = {}      # set name -> zip it was found in


def report(ok, text):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + text)
    if not ok:
        fails += 1


def find_zips(folder):
    """Every zip in the folder that could hold the sets we need."""
    # mlandera is a full set in its own zip (made from the .7z); it is placed by self-location, like any unknown parent
    return [os.path.join(folder, z) for z in ('lrescue.zip', 'invadpt2.zip', 'mlandera.zip') if os.path.exists(os.path.join(folder, z))]


def index_sets(folder, wanted):
    """Expand each candidate zip once; every set (parent or clone) found is recorded under its name."""
    for path in find_zips(folder):
        for n, mem, _, notes, _ in expand(path):
            if n in wanted and mem is not None and n not in cache:
                where[n] = path; cache[n] = mem


def get(name):
    return cache.get(name)


def board_for(name, patches=None, port0=0):
    mem = bytearray(get(name))
    for a, v in (patches or {}).items():
        mem[a] = v
    b = Board(mem)
    b.port0 = port0
    return b


def run(b, frames, holds=(), watch=(), brk=(), idle=0x08):
    """Drive a Board like trapscan.py's `run`. Returns (log of (frame, tuple) changes, {pc: first frame}, hit counts)."""
    first, hits = {}, {a: 0 for a in brk}
    changes, last = [], None
    m = b.cpu.m
    hooked = set(brk)

    def hook(c):
        if c.pc in hooked:
            hits[c.pc] += 1
            first.setdefault(c.pc, b.frame)
    for f in range(frames):
        b.port1 = idle
        for spec, f0, f1 in holds:
            if f0 <= f < f1:
                for k in spec.split('+'):
                    b.port1 |= BTN[k]
        b.run_frame(hook if hooked else None)
        cur = tuple(m[a] for a in watch)
        if cur != last:
            changes.append((f, cur)); last = cur
    return changes, first, hits


def need(name, what):
    """True if the set is loaded; otherwise record a FAIL for this check."""
    if get(name) is None:
        report(False, f'{what}: set "{name}" not found under the ROM folder (checked lrescue.zip, invadpt2.zip and mlandera.zip)')
        return False
    return True


# ---------------------------------------------------------------- byte checks
def bytes_check(name, addr, expect, label):
    if not need(name, f'{name} {label} bytes at ${addr:04X}'):
        return
    mem = get(name)
    if bytes(mem[addr:addr + len(expect)]) == expect:
        report(True, f'{name}: {label} bytes at ${addr:04X}')
        return
    i = bytes(mem).find(expect)
    if i >= 0:
        report(False, f'{name}: {label} bytes RELOCATED, found at ${i:04X} not ${addr:04X}')
    else:
        report(False, f'{name}: {label} bytes not at ${addr:04X} and not found anywhere (ROM shows '
                      f'{bytes(mem[addr:addr + len(expect)]).hex(" ").upper()})')


def byte_checks():
    bytes_check('lrescue', LR_ADDR, LR, 'trap')
    for n in LRESCUE_CLONES:
        if n == 'resclunar':
            bytes_check(n, LR_ADDR, RESCLUNAR, 'trap (RZ at $47E6 patched to RET)')
        else:
            bytes_check(n, LR_ADDR, LR, 'trap')
    bytes_check('invadpt2', IP_A_ADDR, IP_A, 'trap 1')
    bytes_check('invadpt2', IP_B_ADDR, IP_B, 'board check')
    for n in INVADPT2_CLONES:
        bytes_check(n, IP_A_ADDR, IP_A, 'trap 1')
        bytes_check(n, IP_B_ADDR, IP_B, 'board check')


# ---------------------------------------------------------------- emulator checks
# README: the Moon Lander sets differ by 25 bytes, all in set 1's idle-controls check
IDLE_REGIONS = [(0x0662, 0x0666), (0x0A48, 0x0A4A), (0x0D2C, 0x0D33), (0x425B, 0x425F), (0x46B5, 0x46BA)]


def moonlander_diff_check():
    if not (need('mlander', 'mlander/mlandera diff') and need('mlandera', 'mlander/mlandera diff')):
        return
    a, b = get('mlander'), get('mlandera')
    d = [i for i in range(len(a)) if a[i] != b[i]]
    outside = [i for i in d if not any(lo <= i <= hi for lo, hi in IDLE_REGIONS)]
    spans = []
    for i in d:
        if spans and i == spans[-1][1] + 1: spans[-1][1] = i
        else: spans.append([i, i])
    report(len(d) == 25 and not outside,
           f'mlander vs mlandera differ by {len(d)} bytes (README: 25), {len(outside)} outside the idle-controls check; at '
           + ', '.join(f'${x:04X}' if x == y else f'${x:04X}-${y:04X}' for x, y in spans))


def lrescue_checks():
    if need('lrescue', 'lrescue emulator checks'):
        # flag $20ED (the copyright check result): nonzero at boot, cleared by about frame 156
        ch, _, _ = run(board_for('lrescue'), 200, watch=(0x20ED,))
        cleared = [f for f, (v,) in ch if v == 0 and f > 0 and any(p[1][0] != 0 for p in ch if p[0] < f)]
        report(bool(cleared) and 150 <= cleared[0] <= 160,
               f'lrescue as shipped: $20ED cleared at frame {cleared[0] if cleared else "never"} (expect about 156)')
        ch, first, hits = run(board_for('lrescue'), 1720, [('start1+fire+right', 1600, 1700)], (0x20EB,), (0x47E9,))
        report(hits[0x47E9] == 0 and all(c[0] == 0 for _, c in ch),
               f'lrescue as shipped: combo @1600-1700 reaches $47E9 {hits[0x47E9]} times, credits {[c[0] for _, c in ch]} (expect never, 0)')
        ch, first, hits = run(board_for('lrescue', {0x4676: 0x13}), 1720, [('start1+fire+right', 1600, 1700)], (0x20EB,), (0x47E9,))
        mx = max(c[0] for _, c in ch)
        report(hits[0x47E9] > 0 and 3 in [c[0] for _, c in ch],
               f'lrescue --patch 4676=13: $47E9 hit {hits[0x47E9]} times (first frame {first.get(0x47E9)}), credits seen {[f"{c[0]:02X}" for _, c in ch]}')
    for n in ('desterth', 'escmars', 'mlandera'):
        if need(n, f'{n} combo'):
            ch, first, hits = run(board_for(n), 2500, [('start1+fire+right', 1000, 2500)], (0x20EB,), (0x47E9,))
            report(hits[0x47E9] > 0 and 3 in [c[0] for _, c in ch],
                   f'{n} as shipped: combo @1000-2500 hits $47E9 {hits[0x47E9]} times (first frame {first.get(0x47E9)}), credits seen {[f"{c[0]:02X}" for _, c in ch]} (expect 03)')
    for n in ('mlander', 'resclunar', 'grescue', 'lrescueabl', 'lrescuem', 'lrescuem2'):
        if need(n, f'{n} combo'):
            ch, first, hits = run(board_for(n), 2500, [('start1+fire+right', 1000, 2500)], (0x20EB,), (0x47E9,))
            report(hits[0x47E9] == 0, f'{n}: combo @1000-2500 reaches $47E9 {hits[0x47E9]} times (expect never); credits seen {[f"{c[0]:02X}" for _, c in ch]}')


def invadpt2_checks():
    combo = [('start1+start2+fire+left', 200, 260)]
    if need('invadpt2', 'invadpt2 emulator checks'):
        ch, first, hits = run(board_for('invadpt2', port0=0x00), 400, combo, (0x20EB, 0x20CC), (0x419D,))
        report(hits[0x419D] == 0, f'invadpt2 port0=00: combo @200-260 reaches $419D {hits[0x419D]} times (expect never)')
        ch, first, hits = run(board_for('invadpt2', port0=0x02), 400, combo, (0x20EB, 0x20CC), (0x419D,))
        f2 = [f for f, c in ch if c == (2, 2)]
        report(hits[0x419D] > 0 and bool(f2) and 225 <= f2[0] <= 240,
               f'invadpt2 port0=02: $419D hit {hits[0x419D]} times; $20EB=$20CC=02 first at frame {f2[0] if f2 else "never"} (expect about 233)')
        # detect a jump to $0000 after boot: count executions of $0000 beyond the initial one
        b = board_for('invadpt2', port0=0x0A)
        _, first, hits = run(b, 400, brk=(0x0000,))
        report(hits[0x0000] > 1, f'invadpt2 port0=0A: $0000 executed {hits[0x0000]} times (expect more than 1, ie a reset after boot; first frame {first.get(0x0000)})')
    if need('moonbase', 'moonbase trap 2'):
        # Trap 2 ($0A2D) is in-game code, run only in frames ~403-510 of a new game (coin @100, Start 1 @200), so hold the combo then.
        # Its store is `MVI M,$02` at $0A44; H is wrongly $15, so it hits ROM and credits stay 0.
        sched = [('coin', 100, 110), ('start1', 200, 210), ('start1+start2+fire+right', 420, 500)]
        ch, first, hits = run(board_for('moonbase', port0=0x00), 600, sched, (0x20EB,), (0x0A2D, 0x0A44))
        report(hits[0x0A2D] > 0 and hits[0x0A44] > 0 and ch[-1][1][0] == 0,
               f'moonbase trap 2: in-game combo accepted (check $0A2D hit {hits[0x0A2D]}, store $0A44 hit {hits[0x0A44]} times, '
               f'first frame {first.get(0x0A44)}); credits seen {[f"{c[0]:02X}" for _, c in ch]}, final {ch[-1][1][0]:02X} (expect store runs, credits stay 0)')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 scripts/verify.py ROM_FOLDER')
    folder = os.path.expanduser(sys.argv[1])
    if not os.path.isdir(folder):
        raise SystemExit(f'ROM folder not found: {folder}')
    index_sets(folder, ['lrescue', 'invadpt2'] + LRESCUE_CLONES + INVADPT2_CLONES)
    for n, z in sorted(where.items()):
        print(f'      {n}: {os.path.basename(z)}')
    byte_checks()
    moonlander_diff_check()
    lrescue_checks()
    invadpt2_checks()
    print(f'\n{fails} check(s) failed' if fails else '\nall checks passed')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
