#!/usr/bin/env python3
"""trapscan - hunt for hidden credit routines in 8080 Space Invaders-family arcade ROMs.

  python3 trapscan.py scan lrescue.zip                 # report + disassembly file
  python3 trapscan.py scan roms/*.zip                  # every set, clones in merged zips too
  python3 trapscan.py run lrescue.zip --set desterth   # a clone inside a merged zip
  python3 trapscan.py run lrescue.zip --frames 1800 \\
          --poke 20ed=1@170 --hold start1+fire+right@1600-1700 --watch 20eb --break 47e9

See README.md for details.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trapscan.romload import load, expand    # noqa: E402
from trapscan.disasm import disassemble      # noqa: E402
from trapscan.scanner import Scanner         # noqa: E402

BUTTONS = {'coin': 0x01, 'start2': 0x02, 'start1': 0x04, 'fire': 0x10, 'left': 0x20, 'right': 0x40}


def regions_from(layout):
    return [(addr, size) for addr, _, size in layout]


def cmd_scan(args):
    paths = [p for pat in args.sets for p in (glob.glob(pat) or [pat])]
    for path in paths:
        from batch import is_z80_set
        if is_z80_set(path):
            from trapscan.z80mode import expand_z80, scanner_profile, disassemble_z80
            for name, images, desc, parent in expand_z80(path, args.set):
                print('=' * 70)
                print(f'{name}  ({path}' + (f', clone of {parent})' if parent else ')') + f"  [Z80 mode: {desc['board']}]")
                if desc['mcu_refs']:
                    print(f"  main code talks to the 68705 protection MCU ({desc['mcu_refs']} refs to $8800-$8801)")
                for bank, mem, lay in images:
                    print(f'  [{bank}] ' + ' '.join(f'${a:04X}:{fn.split("/")[-1]}' for a, fn, _ in lay))
                    sc = Scanner(mem, regions_from(lay), **scanner_profile(desc)); sc.scan()
                    print(sc.report())
                    if not args.no_asm:
                        os.makedirs(args.out, exist_ok=True)
                        out = os.path.join(args.out, f'{name}_{bank.replace(" ", "")}.asm')
                        with open(out, 'w') as f:
                            f.writelines(l + '\n' for l in disassemble_z80(mem, regions_from(lay)))
                        print(f'Disassembly written to {out}')
            continue
        for name, mem, layout, notes, parent in expand(path, args.map, args.set):
            print('=' * 70)
            print(f'{name}  ({path}' + (f', clone of {parent})' if parent else ')'))
            for n in notes: print('  ' + n)
            if mem is None: continue
            for addr, fn, size in layout: print(f'    ${addr:04X}-${addr + size - 1:04X}  {fn}')
            sc = Scanner(mem, regions_from(layout))
            sc.scan()
            print(sc.report())
            if not args.no_asm:
                out = os.path.join(args.out, f'{name}.asm')
                os.makedirs(args.out, exist_ok=True)
                with open(out, 'w') as f:
                    for line in disassemble(mem, regions_from(layout)):
                        f.write(line + '\n')
                print(f'\nDisassembly written to {out}')
    print('=' * 70)


def parse_buttons(spec):
    v = 0
    for b in spec.lower().split('+'):
        if b.startswith('0x'): v |= int(b, 16)
        elif b in BUTTONS: v |= BUTTONS[b]
        else: raise SystemExit(f'unknown button "{b}" (use {", ".join(BUTTONS)} or 0xNN)')
    return v


def cmd_run(args):
    from trapscan.emu8080 import Board
    mem, layout, name, notes = load(args.zip, args.map, args.set)
    for n in notes: print(n)
    for p in args.patch or []:
        a, v = p.split('=')
        mem[int(a, 16)] = int(v, 16)
        print(f'patched ROM ${int(a,16):04X} = ${int(v,16):02X}')
    b = Board(mem)
    b.port0, b.port2 = int(args.port0, 16), int(args.port2, 16)
    idle = int(args.port1_idle, 16)
    holds = []
    for h in args.hold or []:
        spec, rng = h.split('@')
        f0, f1 = (int(x) for x in rng.split('-'))
        holds.append((parse_buttons(spec), f0, f1))
    pokes = []
    for p in args.poke or []:
        av, f = p.split('@')
        a, v = av.split('=')
        pokes.append((int(a, 16), int(v, 16), int(f)))
    watch = [int(w, 16) for w in args.watch or []]
    brk = {int(x, 16): 0 for x in args.brk or []}
    shots = set(int(x) for x in args.shot or [])
    first = {}

    def hook(c):
        if c.pc in brk:
            brk[c.pc] += 1
            first.setdefault(c.pc, b.frame)

    m = b.cpu.m
    last = None
    for f in range(args.frames):
        b.port1 = idle
        for v, f0, f1 in holds:
            if f0 <= f < f1: b.port1 |= v
        for a, v, pf in pokes:
            if pf == f:
                m[a] = v; print(f'frame {f}: poke ${a:04X} = ${v:02X}')
        b.run_frame(hook if brk else None)
        if watch:
            cur = tuple(m[a] for a in watch)
            if cur != last:
                print(f'frame {f}: ' + '  '.join(f'${a:04X}={x:02X}' for a, x in zip(watch, cur)))
                last = cur
        if f in shots:
            fn = os.path.join(args.out, f'{name}_f{f}.png')
            os.makedirs(args.out, exist_ok=True)
            b.screenshot(fn); print(f'frame {f}: screenshot {fn}')
    for a, n in brk.items():
        print(f'break ${a:04X}: ' + (f'hit {n} times, first at frame {first[a]}' if n else 'never reached'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan', help='scan ROM set(s) for signatures and write disassembly')
    s.add_argument('sets', nargs='+', help='MAME zip(s) or folder(s); wildcards allowed')
    s.add_argument('--map', nargs='+', metavar='ADDR=FILE', help='explicit ROM layout, e.g. 0000=pv01 4000=pv05')
    s.add_argument('--set', help='only this set from a merged zip (default: parent and all clones)')
    s.add_argument('--out', default='out', help='folder for .asm files (default: out)')
    s.add_argument('--no-asm', action='store_true', help='do not write disassembly files')
    s.set_defaults(fn=cmd_scan)

    r = sub.add_parser('run', help='run a set in the emulator with held inputs, pokes and watches')
    r.add_argument('zip', help='set zip or folder')
    r.add_argument('--set', help='clone inside a merged zip, e.g. --set desterth')
    r.add_argument('--map', nargs='+', metavar='ADDR=FILE')
    r.add_argument('--frames', type=int, default=1800, help='frames to run (60 per second)')
    r.add_argument('--hold', action='append', metavar='BUTTONS@F0-F1',
                   help='hold buttons for a frame range, e.g. start1+fire+right@1600-1700')
    r.add_argument('--poke', action='append', metavar='ADDR=VAL@FRAME', help='write a RAM byte at a frame')
    r.add_argument('--patch', action='append', metavar='ADDR=VAL', help='patch a ROM byte before running')
    r.add_argument('--watch', action='append', metavar='ADDR', help='print a RAM byte whenever it changes')
    r.add_argument('--break', dest='brk', action='append', metavar='ADDR', help='count executions of an address')
    r.add_argument('--shot', action='append', metavar='FRAME', help='save a screenshot (needs Pillow)')
    r.add_argument('--port0', default='00'); r.add_argument('--port2', default='00')
    r.add_argument('--port1-idle', default='08', help='port 1 value with nothing pressed (default 08)')
    r.add_argument('--out', default='out')
    r.set_defaults(fn=cmd_run)

    args = ap.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
