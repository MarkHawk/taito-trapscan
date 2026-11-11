"""Z80 mode: Taito SJ System (1981-) and Crazy Balloon (1980).

The Z80 runs 8080 code, and the instructions the signatures look for (JP/CALL, LD A,(nn), AND/CP n,
DAA, LD (nn),A, LD (HL),n) have identical encodings, so the 8080 scanner is reused with a Z80 profile:
memory-mapped inputs instead of IN ports, and the board's own RAM/video ranges.

Board facts used (from the code itself and MAME's taitosj driver):
  Taito SJ main CPU: ROM $0000-$5FFF + banked $6000-$7FFF (two banks), RAM $8000-$87FF,
                     68705 protection MCU at $8800-$8801 (some games), inputs $D400-$D40F.
                     A second Z80 runs sound from its own ROMs.
  Crazy Balloon:     ROM $0000-$3FFF, inputs via IN ports.
"""
from .romload import read_files, split_sets, similarity

JUMPS = {0xC3, 0xCD, 0xC2, 0xCA, 0xD2, 0xDA, 0xC4, 0xCC, 0xD4, 0xDC, 0xE2, 0xEA, 0xF2, 0xFA}
SJ_INPUTS = (0xD400, 0xD410)
MCU = (0x8800, 0x8802)


def self_locate(d, lo=0x0000, hi=0x8000):
    t = [d[i + 1] | d[i + 2] << 8 for i in range(len(d) - 2) if d[i] in JUMPS]
    step = len(d)
    return {b: sum(1 for x in t if b <= x < b + step) for b in range(lo, hi, step)}


def refs(d, lo, hi, ops=(0x3A, 0x32, 0x21, 0x2A, 0x22)):
    return sum(1 for i in range(len(d) - 2) if d[i] in ops and lo <= (d[i + 1] | d[i + 2] << 8) < hi)


def classify(files):
    """Split ROM files into main-CPU code (with bank info), sound-CPU code, and data/graphics."""
    info = []
    for fn, d in files.items():
        if len(d) < 2048:
            continue
        sc = sorted(self_locate(d).items(), key=lambda kv: -kv[1])
        best, top = sc[0]
        second = sc[1][1] if len(sc) > 1 else 0
        code = top >= 15 and top >= 1.6 * max(second, 1)
        info.append(dict(fn=fn, d=d, base=best, score=top, code=code,
                         inputs=refs(d, *SJ_INPUTS, ops=(0x3A,)), ram=refs(d, 0x8000, 0x8800),
                         mcu=refs(d, *MCU)))
    sj = sum(i['inputs'] for i in info) >= 3
    import re
    nat = lambda fn: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', fn.split('/')[-1].lower())]
    info.sort(key=lambda i: nat(i['fn']))
    if not sj:                                          # e.g. Crazy Balloon: one continuous ROM block
        progs = [i for i in info if len(i['d']) in (1024, 2048, 4096)]
        addr = 0
        for i in progs:
            i['base'], i['bank'] = addr, 0
            addr += len(i['d'])
        return sj, progs, [], [i for i in info if i not in progs]
    main = [i for i in info if i['ram'] >= 40 or (i['inputs'] >= 1 and i['ram'] >= 15)]
    rest = [i for i in info if i not in main]
    sound = [i for i in rest if i['code']]
    data = [i for i in rest if not i['code']]
    used = set()                                    # (bank, 4KB slot)
    def take(i, base, bank):
        span = [(bank, a) for a in range(base, base + len(i['d']), 0x1000)]
        if base + len(i['d']) > 0x8000 or (bank == 1 and base < 0x6000) or any(x in used for x in span):
            return False
        used.update(span); i['base'], i['bank'] = base, bank
        return True
    anchored = []
    for i in sorted(main, key=lambda i: -i['score']):   # 1) confident self-location wins
        if i['code'] and i['score'] >= 40 and i['base'] < 0x8000:
            if take(i, i['base'], 0) or (i['base'] >= 0x6000 and take(i, i['base'], 1)):
                anchored.append(i)
    for i in main:                                       # 2) the rest fill free slots in name order
        if i in anchored:
            continue
        step = len(i['d'])
        for bank, base in [(0, b) for b in range(0, 0x8000, step)] + [(1, b) for b in range(0x6000, 0x8000, step)]:
            if take(i, base, bank):
                break
    return sj, main, sound, data


def build_images(files):
    """Main-CPU memory images: [bank0 image, bank1 image?] plus a description."""
    sj, main, sound, data = classify(files)
    slots, banks = {}, []
    for i in main:
        size = len(i['d'])
        span = range(i['base'], i['base'] + size, 0x1000)
        if i.get('bank', 0) == 1:
            banks.append(i)
        elif not any(s in slots for s in span):
            for s in span: slots[s] = i
        elif i['base'] >= 0x6000:
            banks.append(i)
    mem = bytearray(0x10000)
    layout = []
    for i in {id(v): v for v in slots.values()}.values():
        mem[i['base']:i['base'] + len(i['d'])] = i['d']
        layout.append((i['base'], i['fn'], len(i['d'])))
    images = [('bank 0', mem, sorted(layout))]
    if banks:
        mem1 = bytearray(mem)
        lay1 = [l for l in layout if l[0] < 0x6000]
        for i in banks:
            mem1[i['base']:i['base'] + len(i['d'])] = i['d']
            lay1.append((i['base'], i['fn'], len(i['d'])))
        images.append(('bank 1', mem1, sorted(lay1)))
    desc = dict(board='Taito SJ' if sj else 'Z80 (IN-port inputs)',
                sound=[i['fn'] for i in sound], data=[i['fn'] for i in data],
                mcu_refs=sum(i['mcu'] for i in main))
    return images, desc


def scanner_profile(desc):
    if desc['board'] == 'Taito SJ':
        return dict(input_ports=(), input_mem=SJ_INPUTS, ram=(0x8000, 0x8800), vram=(0x9000, 0xC000))
    return dict(input_ports=tuple(range(8)), input_mem=None, ram=(0x4000, 0x4800), vram=(0x4800, 0x5000))


def expand_z80(path, only=None):
    """Yield (name, images, desc, parent) for each set; clones overlay the parent by content."""
    import os
    parent = os.path.splitext(os.path.basename(path.rstrip('/\\')))[0]
    sets = split_sets(read_files(path), parent)
    pfiles = sets[parent]
    if only in (None, parent):
        images, desc = build_images(pfiles)
        yield parent, images, desc, None
    for clone in sorted(c for c in sets if c != parent):
        if only not in (None, clone):
            continue
        merged = dict(pfiles)
        for fn, d in sets[clone].items():          # replace the parent file this ROM most resembles
            same = [p for p, pd in pfiles.items() if len(pd) == len(d)]
            if same:
                best = max(same, key=lambda p: similarity(d, pfiles[p]))
                if similarity(d, pfiles[best]) >= 0.5:
                    merged.pop(best, None)
            merged[f'{clone}/{fn}'] = d
        images, desc = build_images(merged)
        yield clone, images, desc, parent


def disassemble_z80(mem, regions):
    try:
        from z80dis import z80
    except ImportError:
        yield '(install z80dis for Z80 disassembly: py -m pip install z80dis)'
        return
    for start, length in regions:
        pc = start
        while pc < start + length:
            chunk = bytes(mem[pc:pc + 4])
            try:
                dec = z80.decode(chunk, pc)
                n = max(dec.len, 1)
                text = z80.disasm(dec)
            except Exception:
                n, text = 1, f'db ${mem[pc]:02X}'
            yield f"{pc:04X}  {' '.join(f'{b:02X}' for b in mem[pc:pc + n]):11} {text}"
            pc += n
