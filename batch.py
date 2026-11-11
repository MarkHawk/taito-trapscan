#!/usr/bin/env python3
"""Scan every ROM set in a folder and write one Markdown report.

  python3 batch.py ~/roms                      # -> report.md + out/<set>.asm
  python3 batch.py ~/roms -o taito_report.md --out asm/

Each .zip (or folder) is a set; merged zips also yield every clone in their sub-folders.
Sets that fail to load are listed, not fatal.
"""
import argparse
import datetime
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trapscan.romload import expand          # noqa: E402
from trapscan.emu8080 import Board            # noqa: E402
from trapscan.z80mode import expand_z80, scanner_profile, disassemble_z80   # noqa: E402
from trapscan.disasm import disassemble      # noqa: E402
from trapscan.scanner import Scanner         # noqa: E402

RANK = {'SUSPICIOUS': 0, 'CHECK': 1, 'EASTER EGG?': 2, 'CLEAN': 3, 'OTHER HW?': 4, 'ERROR': 5}


def hidden_credit_pointer(hits, credit):
    """True when an H value and an L value built at run time together make the credit address."""
    if credit is None:
        return False
    import re
    hs = [(a, int(re.search(r'= \$([0-9A-F]{2})', t).group(1), 16)) for k, a, t in hits if k == 'POINTER' and t.startswith('H')]
    ls = [(a, int(re.search(r'= \$([0-9A-F]{2})', t).group(1), 16)) for k, a, t in hits if k == 'POINTER' and t.startswith('L')]
    return any(hv == credit >> 8 and lv == credit & 0xFF and abs(ha - la) <= 24 for ha, hv in hs for la, lv in ls)


def classify(hits, sc):
    kinds = {k for k, _, _ in hits}
    combos = [h for h in hits if h[0] == 'COMBO']
    stores = [c for c in combos if 'MVI M' in c[2]]
    credit_ptr = hidden_credit_pointer(hits, sc.credit)
    if stores or credit_ptr:
        return 'SUSPICIOUS'
    if kinds & {'SHADOW', 'VRAMCMP', 'ROMCMP', 'RESET'}:
        return 'CHECK'
    if combos:
        return 'EASTER EGG?'
    return 'CLEAN'


def count(hits, *kinds):
    n = sum(1 for k, _, _ in hits if k in kinds)
    return str(n) if n else '–'


def is_z80_set(path):
    """4KB/8KB program ROMs = Taito SJ-era Z80 board; Crazy Balloon is listed by name."""
    from trapscan.romload import read_files
    import os
    if os.path.splitext(os.path.basename(path))[0] in ('crbaloon',):
        return True
    from trapscan.romload import split_sets
    parent = os.path.splitext(os.path.basename(path.rstrip('/\\')))[0]
    own = split_sets(read_files(path), parent)[parent]        # the parent's own files only, not its clones'
    sizes = [len(d) for d in own.values()]
    return sum(1 for x in sizes if x in (4096, 8192)) >= 4


def scan_z80(path, e, results):
    for name, images, desc, parent in expand_z80(path):
        print(f'    {name:14} ', end='', flush=True)
        hits_all, reports, layouts, credit = [], [], [], None
        for bank, mem, lay in images:
            sc = Scanner(mem, [(a, s) for a, _, s in lay], **scanner_profile(desc))
            hits = sc.scan()
            hits_all += [h for h in hits if h not in hits_all]
            credit = credit or sc.credit
            reports.append(f'[{bank}]\n' + sc.report())
            layouts += [(a, f'[{bank}] {fn.split("/")[-1]}', s) for a, fn, s in lay]
        verdict = classify(hits_all, type('S', (), {'credit': credit})())
        notes = [f"layout: Z80 mode, {desc['board']} board (main-CPU ROMs located by code; sound: "
                 f"{', '.join(x.split('/')[-1] for x in desc['sound']) or 'none'})"]
        if desc['mcu_refs']:
            notes.append(f"main code talks to the 68705 protection MCU ({desc['mcu_refs']} references to $8800-$8801)")
        results.append(dict(name=name, file=e, parent=parent, verdict=verdict, layout=layouts, notes=notes,
                            hits=hits_all, report='\n\n'.join(reports), credit=credit, boot='n/a (Z80)'))
        print(verdict)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('romdir')
    ap.add_argument('-o', '--report', default='report.md')
    ap.add_argument('--out', default='out', help='folder for disassemblies (default: out)')
    ap.add_argument('--no-asm', action='store_true')
    ap.add_argument('--no-boot', action='store_true', help='skip the 4-second emulator boot check')
    args = ap.parse_args()

    entries = sorted(e for e in os.listdir(args.romdir)
                     if e.lower().endswith('.zip') or os.path.isdir(os.path.join(args.romdir, e)))
    if not entries:
        sys.exit(f'No .zip files or set folders in {args.romdir}')
    if not args.no_asm:
        os.makedirs(args.out, exist_ok=True)

    results = []

    def boots(mem):
        """Run 4 s of emulation; a correctly laid-out game has drawn something by then.
        Some boards check input port 0 at power-up (e.g. Galaxy Wars wants $40), so try a few values."""
        for p0 in (0x00, 0x01, 0x03, 0x40, 0x41, 0x0E, 0x0F, 0xFF):
            try:
                b = Board(mem); b.port0 = p0
                for _ in range(240):
                    b.run_frame()
                if sum(1 for x in b.cpu.m[0x2400:0x4000] if x) > 40:
                    return 'yes' if p0 == 0 else f'yes (IN0=${p0:02X})'
            except Exception:
                pass
        return 'NO'

    for i, e in enumerate(entries, 1):
        path = os.path.join(args.romdir, e)
        print(f'[{i}/{len(entries)}] {e}')
        try:
            if is_z80_set(path):
                scan_z80(path, e, results)
                continue
            for name, mem, layout, notes, parent in expand(path):
                print(f'    {name:14} ', end='', flush=True)
                if mem is None:
                    results.append(dict(name=name, file=e, parent=parent, verdict='ERROR', error=notes[0]))
                    print('ERROR'); continue
                regions = [(a, n) for a, _, n in layout]
                sc = Scanner(mem, regions)
                hits = sc.scan()
                verdict = classify(hits, sc)
                odd_start = any(n.startswith('WARNING: $0000') for n in notes)
                boot = '–' if args.no_boot else boots(mem)
                other = odd_start and not boot.startswith('yes')
                if other:
                    verdict = 'OTHER HW?'   # not 8080 Invaders-family code: results meaningless
                if not args.no_asm:
                    with open(os.path.join(args.out, f'{name}.asm'), 'w') as f:
                        f.writelines(l + '\n' for l in disassemble(mem, regions))
                results.append(dict(name=name, file=e, parent=parent, verdict=verdict, layout=layout,
                                    notes=notes, hits=hits, report=sc.report(), credit=sc.credit, boot=boot))
                print(f'{verdict}' + ('' if boot.startswith('yes') or boot == '–' else '   (did not boot - layout?)') + (f'   boots with {boot[5:-1]}' if boot.startswith('yes (') else ''))
        except Exception as ex:  # keep going on bad zips
            results.append(dict(name=os.path.splitext(e)[0], file=e, parent=None, verdict='ERROR', error=str(ex),
                                trace=traceback.format_exc(limit=2)))
            print(f'    ERROR: {ex}')

    results.sort(key=lambda r: (RANK[r['verdict']], r['name']))
    L = [f'# trapscan batch report', '',
         f'{datetime.datetime.now():%Y-%m-%d %H:%M} · folder `{args.romdir}` · {len(results)} sets', '',
         '| Verdict | Count |', '|---|---|']
    for v in RANK:
        n = sum(1 for r in results if r['verdict'] == v)
        if n: L.append(f'| {v} | {n} |')
    L += ['', '**SUSPICIOUS** = a button-combo check followed by RAM writes, or a hidden pointer to the credit counter. '
          '**CHECK** = integrity/board checks with no combo write (look for indirect paths). '
          '**EASTER EGG?** = combo checks that don\'t write RAM. **OTHER HW?** = $0000 doesn\'t look like Invaders-family 8080 code (different CPU/hardware, or wrong layout - try `trapscan.py scan --map`), so ignore its results. **Boots** = the set drew a screen within 4 s in the emulator; NO usually means a wrong ROM layout. Layout *matched* = clone ROMs placed by matching the parent\'s code; *guess* = verify.', '',
          '## Summary', '',
          '| Set | Clone of | Verdict | Boots | Layout | Credits at | Combos | Hidden ptrs | Shadow | Screen chk | ROM chk | Board chk |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in results:
        if r['verdict'] == 'ERROR':
            L.append(f"| {r['name']} | {r.get('parent') or ''} | ERROR | – | – | – | – | – | – | – | – | – |")
            continue
        h = r['hits']
        lay = ('known' if any('known' in n for n in r['notes']) else
               'matched' if any('matching against parent' in n for n in r['notes']) else '*guess*')
        cr = f"${r['credit']:04X}" if r['credit'] is not None else '?'
        L.append(f"| [{r['name']}](#{r['name'].lower()}) | {r.get('parent') or ''} | {r['verdict']} | {r['boot']} | {lay} | {cr} | {count(h,'COMBO')} | "
                 f"{count(h,'POINTER')} | {count(h,'SHADOW')} | {count(h,'VRAMCMP')} | {count(h,'ROMCMP')} | {count(h,'RESET')} |")
    L += ['', '## Details', '']
    for r in results:
        L += [f"### {r['name']}", '', f"`{r['file']}`" + (f" (clone of {r['parent']})" if r.get('parent') else '') + f" · **{r['verdict']}**", '']
        if r['verdict'] == 'ERROR':
            L += ['```', r['error'], '```', '']
            continue
        L += [f'- {n}' for n in r['notes']]
        L += [f'- `${a:04X}-${a + s - 1:04X}` {fn}' for a, fn, s in r['layout']]
        L += ['', '```', r['report'], '```', '']
        if not args.no_asm:
            L += [f"Disassembly: `{os.path.join(args.out, r['name'] + '.asm')}`", '']
    with open(args.report, 'w') as f:
        f.write('\n'.join(L) + '\n')
    print(f'\nReport written to {args.report}')


if __name__ == '__main__':
    main()
