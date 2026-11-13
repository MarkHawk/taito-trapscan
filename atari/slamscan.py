#!/usr/bin/env python3
"""slamscan.py - look for a "kick me for a free game" trap in Atari 6502 arcade games.

  python3 slamscan.py ROMDIR [-o slamscan.md] [--csv slamscan.csv] [--max-zip-mb 2]

The story (Ned Batchelder, heard at General Computer in 1982): after many plays the game checks screen memory for
its copyright notice and, if it's missing, shows "KICK ME FOR A FREE GAME" and gives a credit each time the cabinet's
slam switch trips.

Atari's 6502 games share one coin routine, and in it the slam switch only blocks coins for a moment:

    LDA slam / AND #mask / BNE +4 / LDA #$F0 / STA timer / LDA timer / BEQ +8 / DEC timer / LDA #0 / STA,X / STA,X

This script finds that routine in every set (so it knows the game uses Atari's coin code), reads off where the slam
switch comes from and which RAM bytes the coin code adds credits to, and then lists:

  - every other place the code reads the slam switch, with the code that follows it, and
  - every instruction that writes a credit byte, with the code before it.

A slam read that leads to a credit write (SLAM->CREDIT) is the trap the story describes. Expected credit writers are
coin, start, free play and a cap. Pure Python 3, no dependencies. Byte-pattern search, so it needs no ROM layout:
addresses in the report are offsets inside each ROM file.
"""
OPS = """
BRK.imp ORA.inx ???.imp ???.imp ???.imp ORA.zpg ASL.zpg ???.imp PHP.imp ORA.imm ASL.acc ???.imp
???.imp ORA.abs ASL.abs ???.imp BPL.rel ORA.iny ???.imp ???.imp ???.imp ORA.zpx ASL.zpx ???.imp
CLC.imp ORA.aby ???.imp ???.imp ???.imp ORA.abx ASL.abx ???.imp JSR.abs AND.inx ???.imp ???.imp
BIT.zpg AND.zpg ROL.zpg ???.imp PLP.imp AND.imm ROL.acc ???.imp BIT.abs AND.abs ROL.abs ???.imp
BMI.rel AND.iny ???.imp ???.imp ???.imp AND.zpx ROL.zpx ???.imp SEC.imp AND.aby ???.imp ???.imp
???.imp AND.abx ROL.abx ???.imp RTI.imp EOR.inx ???.imp ???.imp ???.imp EOR.zpg LSR.zpg ???.imp
PHA.imp EOR.imm LSR.acc ???.imp JMP.abs EOR.abs LSR.abs ???.imp BVC.rel EOR.iny ???.imp ???.imp
???.imp EOR.zpx LSR.zpx ???.imp CLI.imp EOR.aby ???.imp ???.imp ???.imp EOR.abx LSR.abx ???.imp
RTS.imp ADC.inx ???.imp ???.imp ???.imp ADC.zpg ROR.zpg ???.imp PLA.imp ADC.imm ROR.acc ???.imp
JMP.ind ADC.abs ROR.abs ???.imp BVS.rel ADC.iny ???.imp ???.imp ???.imp ADC.zpx ROR.zpx ???.imp
SEI.imp ADC.aby ???.imp ???.imp ???.imp ADC.abx ROR.abx ???.imp ???.imp STA.inx ???.imp ???.imp
STY.zpg STA.zpg STX.zpg ???.imp DEY.imp ???.imp TXA.imp ???.imp STY.abs STA.abs STX.abs ???.imp
BCC.rel STA.iny ???.imp ???.imp STY.zpx STA.zpx STX.zpy ???.imp TYA.imp STA.aby TXS.imp ???.imp
???.imp STA.abx ???.imp ???.imp LDY.imm LDA.inx LDX.imm ???.imp LDY.zpg LDA.zpg LDX.zpg ???.imp
TAY.imp LDA.imm TAX.imp ???.imp LDY.abs LDA.abs LDX.abs ???.imp BCS.rel LDA.iny ???.imp ???.imp
LDY.zpx LDA.zpx LDX.zpy ???.imp CLV.imp LDA.aby TSX.imp ???.imp LDY.abx LDA.abx LDX.aby ???.imp
CPY.imm CMP.inx ???.imp ???.imp CPY.zpg CMP.zpg DEC.zpg ???.imp INY.imp CMP.imm DEX.imp ???.imp
CPY.abs CMP.abs DEC.abs ???.imp BNE.rel CMP.iny ???.imp ???.imp ???.imp CMP.zpx DEC.zpx ???.imp
CLD.imp CMP.aby ???.imp ???.imp ???.imp CMP.abx DEC.abx ???.imp CPX.imm SBC.inx ???.imp ???.imp
CPX.zpg SBC.zpg INC.zpg ???.imp INX.imp SBC.imm NOP.imp ???.imp CPX.abs SBC.abs INC.abs ???.imp
BEQ.rel SBC.iny ???.imp ???.imp ???.imp SBC.zpx INC.zpx ???.imp SED.imp SBC.aby ???.imp ???.imp
???.imp SBC.abx INC.abx ???.imp
""".split()

import argparse
import collections
import csv
import hashlib
import os
import re
import sys
import zipfile

LEN = {'imp': 1, 'acc': 1, 'imm': 2, 'zpg': 2, 'zpx': 2, 'zpy': 2, 'inx': 2, 'iny': 2, 'rel': 2,
       'abs': 3, 'abx': 3, 'aby': 3, 'ind': 3}
OPC = [tuple(o.split('.')) for o in OPS]
END = {'RTS', 'RTI', 'JMP', 'BRK'}

# Atari's slam check inside the coin routine (see the docstring). Groups: 1 abs source, 2 zp source, 3 abs (LDX),
# 4 zp (LDX), 5 mask, 6 the slam timer.
SIG = re.compile(rb'(?:\xad(..)|\xa5(.)|\xae(..)|\xa6(.))\x29(.)[\xd0\xf0]\x04\xa9\xf0\x85(.)\xa5\6\xf0\x08\xc6\6'
                 rb'\xa9\x00\x95.\x95.', re.S)

# opcodes that read a zero-page / absolute byte (for slam reads)
READ_ZP = {0xA5, 0xA6, 0xA4, 0x24, 0x25, 0x05, 0x45, 0xC5, 0xE4, 0xC4, 0x65, 0xE5}
READ_ABS = {0xAD, 0xAE, 0xAC, 0x2C, 0x2D, 0x0D, 0x4D, 0xCD, 0xEC, 0xCC, 0x6D, 0xED}
# opcodes that write a zero-page byte (for credit writes); indexed forms are flagged
WRITE_ZP = {0x85: '', 0x86: '', 0x84: '', 0xE6: '', 0xC6: '', 0x06: '', 0x26: '', 0x46: '', 0x66: ''}
WRITE_ZPX = {0x95, 0x96, 0x94, 0xF6, 0xD6, 0x16, 0x36, 0x56, 0x76}
WRITE_ABS = {0x8D, 0x8E, 0x8C, 0xEE, 0xCE}


def ins(d, i):
    """(length, text) of the instruction at offset i of d."""
    mn, mode = OPC[d[i]]
    n = LEN[mode]
    if i + n > len(d):
        return 1, '???'
    if mode in ('imp', 'acc'):
        return n, mn + (' A' if mode == 'acc' else '')
    b = d[i + 1]
    if mode == 'imm':
        return n, '%s #$%02X' % (mn, b)
    if mode == 'rel':
        return n, '%s +%04X' % (mn, (i + 2 + (b - 256 if b > 127 else b)) & 0xFFFF)
    if n == 2:
        f = {'zpg': '$%02X', 'zpx': '$%02X,X', 'zpy': '$%02X,Y', 'inx': '($%02X,X)', 'iny': '($%02X),Y'}[mode]
        return n, mn + ' ' + f % b
    w = b | d[i + 2] << 8
    f = {'abs': '$%04X', 'abx': '$%04X,X', 'aby': '$%04X,Y', 'ind': '($%04X)'}[mode]
    return n, mn + ' ' + f % w


def synced(d, off):
    """A start offset from which linear decoding lands exactly on off, or None if most decodings from further back
    step over it (then off is inside another instruction, e.g. the address of a JSR, or data)."""
    starts = range(max(0, off - 48), max(0, off - 48) + 8) if off >= 48 else [0]
    land = 0
    for st in starts:
        i = st
        while i < off:
            i += ins(d, i)[0]
        land += i == off
    if land * 2 <= len(starts):
        return None
    for st in range(max(0, off - 30), off):     # a short clean run-in for the listing
        i, ok = st, True
        while i < off:
            n, t = ins(d, i)
            if t.startswith('???'):
                ok = False
                break
            i += n
        if ok and i == off:
            return st
    return off


def listing(d, start, count, stop_at_end=True):
    out, i = [], start
    for _ in range(count):
        if i >= len(d):
            break
        n, t = ins(d, i)
        out.append((i, n, t))
        i += n
        if stop_at_end and t.split()[0] in END:
            break
    return out


def fmt(d, rows, mark=None):
    return '\n'.join('%s%04X  %-9s %s' % ('>' if o == mark else ' ', o, ' '.join('%02X' % x for x in d[o:o + n]), t)
                     for o, n, t in rows)


def tests_mask(rows, mask):
    """Does the code right after a read (rows[0] is the read) test the slam bit?"""
    first = rows[0][2].split()[0]
    shifts = 0
    for o, n, t in rows[1:5]:
        mn = t.split()[0]
        if mn == 'AND' and t.startswith('AND #$'):
            return bool(int(t[6:8], 16) & mask)    # tests some other bit if the mask misses the slam bit
        if mn == 'LSR' and t == 'LSR A':
            shifts += 1
            continue
        if mn == 'ASL' and t == 'ASL A':
            shifts -= 1
            continue
        if mn in ('BCS', 'BCC') and shifts:
            bit = shifts - 1 if shifts > 0 else 8 + shifts
            return bool(mask & (1 << bit))
        if mn in ('BVS', 'BVC') and first == 'BIT':
            return bool(mask & 0x40)
        if mn in ('BMI', 'BPL') and (first == 'BIT' or first in ('LDA', 'LDX', 'LDY')):
            return bool(mask & 0x80)
        if mn in ('STA', 'STX', 'STY', 'TAX', 'TAY', 'PHA'):
            return None                     # copied somewhere: can't tell from here, keep it
        if mn in ('JSR', 'JMP', 'RTS', 'RTI'):
            return False
    return False


def is_cap(rows, off, byte):
    """A credit write that only limits the count (LDA #max / CMP credits / BCS / STA credits) - never adds."""
    idx = [k for k, r in enumerate(rows) if r[0] == off]
    if not idx:
        return False
    prev = [t for _, _, t in rows[max(0, idx[0] - 3):idx[0]]]
    return any(t == 'CMP $%02X' % byte for t in prev) and any(t.startswith('LDA #') for t in prev)


def writes_credit(d, o, n, t, credits):
    op = d[o]
    if n == 2 and op in WRITE_ZP and d[o + 1] in credits:
        return d[o + 1], ''
    if n == 2 and op in WRITE_ZPX and any(0 <= c - d[o + 1] <= 2 for c in credits):
        return d[o + 1], ' (indexed)'
    if n == 3 and op in WRITE_ABS and d[o + 2] == 0 and d[o + 1] in credits:
        return d[o + 1], ''
    return None


def sets_in_zip(z):
    """{set name: [member names]} - the root files are the parent; each folder is a clone (plus the parent's files)."""
    root, clones = [], collections.defaultdict(list)
    for n in z.namelist():
        if n.endswith('/'):
            continue
        if '/' in n:
            clones[n.split('/')[0]].append(n)
        else:
            root.append(n)
    out = {}
    if root:
        out[None] = root
    for c, files in clones.items():
        out[c] = files + root
    return out


def analyse(files):
    """files: {name: bytes}. Returns a result dict, or None if Atari's coin routine isn't there."""
    hit = None
    for name, d in files.items():
        m = SIG.search(d)
        if m:
            hit = (name, m)
            break
    if not hit:
        return None
    name, m = hit
    d = files[name]
    timer, mask = m.group(6)[0], m.group(5)[0]
    src_abs = m.group(1) or m.group(3)
    src_zp = m.group(2) or m.group(4)
    if src_abs is not None:
        a = src_abs[0] | src_abs[1] << 8
        src = ('zp', a) if a < 0x100 else ('abs', a)
    else:
        src = ('zp', src_zp[0])
    # credit bytes: what the coin routine INCs in the 260 bytes after the slam check
    incs = collections.Counter(d[i + 1] for i in range(m.end(), min(len(d) - 1, m.end() + 260)) if d[i] == 0xE6)
    incs.pop(timer, None)
    for i in range(max(0, m.start() - 40), m.start() - 1):
        if d[i] in (0xA5, 0xA6, 0xA4, 0x25, 0x45, 0xC5):
            incs.pop(d[i + 1], None)
    credits = set(incs)
    # if the slam byte is a RAM copy, find the port that fills it (LDA/LDX/LDY port ; STA/STX/STY copy)
    ports = set()
    if src[0] == 'abs':
        ports.add(src[1])
    else:
        for f, fd in files.items():
            for mm in re.finditer(rb'[\xad\xae\xac](..)[\x85\x86\x84]' + re.escape(bytes([src[1]])), fd, re.S):
                ports.add(mm.group(1)[0] | mm.group(1)[1] << 8)
    res = {'file': name, 'off': m.start(), 'mask': mask, 'timer': timer, 'src': src, 'ports': sorted(ports),
           'credits': sorted(credits), 'coin': fmt(d, listing(d, m.start(), 14, False)), 'reads': [], 'writers': []}
    seen = set()
    for f, fd in files.items():
        h = hashlib.sha1(fd).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        # slam reads
        pats = []
        if src[0] == 'zp':
            z = src[1]
            pats += [(bytes([op, z]), 2) for op in READ_ZP] + [(bytes([op, z, 0]), 3) for op in READ_ABS]
        for p in ports:
            pats += [(bytes([op, p & 255, p >> 8]), 3) for op in READ_ABS]
        offs = sorted({mm.start() for pat, _ in pats for mm in re.finditer(re.escape(pat), fd)})
        for o in offs:
            if any(mm.start() <= o < mm.end() for mm in SIG.finditer(fd[max(0, o - 4):o + 40])) or \
                    SIG.match(fd, o):
                continue                       # Atari's coin routine itself
            st = synced(fd, o)
            if st is None:
                continue
            after = listing(fd, o, 40)
            if tests_mask(after, mask) is False:
                continue                       # reads the same port for another bit (vblank, test, buttons)
            cw = [(oo, writes_credit(fd, oo, n, t, credits)) for oo, n, t in after]
            cw = [(oo, w) for oo, w in cw if w and not is_cap(after, oo, w[0])]
            res['reads'].append({'file': f, 'off': o, 'sha': h, 'credit_after': cw,
                                 'code': fmt(fd, [r for r in listing(fd, st, 40, False) if r[0] < o][-4:] + after[:16], o)})
        # credit writers
        for o in range(len(fd) - 1):
            n = LEN[OPC[fd[o]][1]]
            if o + n > len(fd):
                continue
            w = writes_credit(fd, o, n, OPC[fd[o]][0], credits)
            if not w:
                continue
            st = synced(fd, o)
            if st is None:
                continue
            before = [r for r in listing(fd, st, 40, False) if r[0] < o][-8:]
            if any(t.startswith('???') for _, _, t in before):
                continue
            res['writers'].append({'file': f, 'off': o, 'sha': h, 'byte': w[0], 'note': w[1],
                                   'in_coin': f == name and m.start() <= o < m.start() + 330,
                                   'code': fmt(fd, before + listing(fd, o, 3, False), o)})
    return res


def main():
    ap = argparse.ArgumentParser(description='Look for a slam-switch credit trap in Atari 6502 games.')
    ap.add_argument('romdir')
    ap.add_argument('-o', '--out', default='slamscan.md')
    ap.add_argument('--csv', default='slamscan.csv')
    ap.add_argument('--max-zip-mb', type=float, default=2)
    a = ap.parse_args()
    zips = sorted(f for f in os.listdir(a.romdir) if f.lower().endswith('.zip'))
    rows, details, found = [], [], 0
    for k, zf in enumerate(zips):
        p = os.path.join(a.romdir, zf)
        if os.path.getsize(p) > a.max_zip_mb * 1e6:
            continue
        try:
            z = zipfile.ZipFile(p)
            sets = sets_in_zip(z)
            data = {n: z.read(n) for n in {x for v in sets.values() for x in v} if z.getinfo(n).file_size <= 0x10000}
        except Exception as e:
            print('skip %s: %s' % (zf, e), file=sys.stderr)
            continue
        if (k + 1) % 200 == 0:
            print('%d/%d zips, %d Atari-coin sets so far' % (k + 1, len(zips), found), file=sys.stderr)
        done = {}
        for sname, members in sets.items():
            files = {n: data[n] for n in members if n in data}
            key = hashlib.sha1(b''.join(hashlib.sha1(files[n]).digest() for n in sorted(files))).hexdigest()
            label = zf[:-4] + ('' if sname is None else ' / ' + sname)
            if key in done:
                continue
            r = analyse(files)
            done[key] = r
            if not r:
                continue
            found += 1
            flag = 'SLAM->CREDIT' if any(rd['credit_after'] for rd in r['reads']) else ''
            other_w = [w for w in r['writers'] if not w['in_coin']]
            rows.append([label, r['file'], '%s $%X' % r['src'], '$%02X' % r['mask'],
                         ' '.join('$%02X' % c for c in r['credits']), ' '.join('$%04X' % p for p in r['ports']),
                         len(r['reads']), len(other_w), flag])
            details.append((label, r, flag))
            print('%-34s credits %-12s slam reads %2d  other credit writers %2d  %s'
                  % (label, rows[-1][4], len(r['reads']), len(other_w), flag), flush=True)
    with open(a.csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['set', 'coin_file', 'slam_source', 'mask', 'credit_bytes', 'slam_ports', 'slam_reads',
                    'credit_writers_outside_coin', 'flag'])
        w.writerows(rows)
    with open(a.out, 'w') as fh:
        fh.write('# slamscan report\n\n%d sets use Atari\'s coin routine. Offsets are inside each ROM file.\n\n' % found)
        fh.write('| set | slam source | credits | slam reads | other credit writers | flag |\n|---|---|---|---|---|---|\n')
        for r in rows:
            fh.write('| %s | %s & $%s | %s | %d | %d | %s |\n' % (r[0], r[2], r[3][1:], r[4], r[6], r[7], r[8]))
        shown = {}
        for label, r, flag in sorted(details, key=lambda x: (not x[2], x[0])):
            fh.write('\n## %s %s\n\nCoin routine in `%s` +%04X; slam = %s $%X & $%02X; ports %s; credit bytes %s\n\n'
                     % (label, flag, r['file'], r['off'], r['src'][0], r['src'][1], r['mask'],
                        ' '.join('$%04X' % p for p in r['ports']) or '-',
                        ' '.join('$%02X' % c for c in r['credits']) or '(none found)'))
            fh.write('```\n%s\n```\n' % r['coin'])
            same = collections.Counter()
            for rd in r['reads']:
                if (rd['sha'], rd['off']) in shown:
                    same[shown[rd['sha'], rd['off']]] += 1
                    continue
                shown[rd['sha'], rd['off']] = label
                fh.write('\n**Slam read** `%s` +%04X%s\n```\n%s\n```\n' % (
                    rd['file'], rd['off'], '  **writes credits after it**' if rd['credit_after'] else '', rd['code']))
            for wr in r['writers']:
                if wr['in_coin']:
                    continue
                if (wr['sha'], wr['off']) in shown:
                    same[shown[wr['sha'], wr['off']]] += 1
                    continue
                shown[wr['sha'], wr['off']] = label
                fh.write('\n**Credit write** `%s` +%04X ($%02X%s)\n```\n%s\n```\n' % (
                    wr['file'], wr['off'], wr['byte'], wr['note'], wr['code']))
            for other, n in same.items():
                fh.write('\n%d more listed under %s (same ROM file).\n' % (n, other))
    print("\n%d zips scanned, %d sets use Atari's coin routine. Report: %s  Table: %s" % (len(zips), found, a.out, a.csv))


if __name__ == '__main__':
    main()
