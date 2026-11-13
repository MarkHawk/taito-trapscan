#!/usr/bin/env python3
"""verify_atari.py - check the Atari code listings in README.md and docs/ against the real ROMs.

  python3 atari/verify_atari.py ROM_FOLDER

Needs astdelux.zip and centiped.zip (MAME 0.277 merged sets, clones in sub-folders) in ROM_FOLDER.
Prints one PASS/FAIL line per check and exits non-zero if any fail. Pure Python 3, no dependencies.
"""
import os
import sys
import zipfile

fails = 0


def report(ok, text):
    global fails
    print(('PASS  ' if ok else 'FAIL  ') + text)
    if not ok:
        fails += 1


def rom(z, name):
    try:
        return z.read(name)
    except KeyError:
        return None


def at(z, name, off, hexbytes, what):
    d = rom(z, name)
    want = bytes.fromhex(hexbytes)
    if d is None:
        report(False, '%s: %s not in zip' % (what, name))
        return
    report(d[off:off + len(want)] == want, '%s: %s +%04X = %s' % (what, name, off, hexbytes))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    folder = os.path.expanduser(sys.argv[1])

    # ---------------- Asteroids Deluxe (MAME astdelux, rev 3; astdelux1, rev 1; astdelux2, rev 2) ----------------
    p = os.path.join(folder, 'astdelux.zip')
    if not os.path.exists(p):
        report(False, 'astdelux.zip not found in ' + folder)
    else:
        z = zipfile.ZipFile(p)
        fh1, j1, r2 = 'astdelux1/036432-01.fh1', 'astdelux1/036433-01.j1', 'astdelux1/036800-01.r2'
        # $703B-$7049 (fh1 is $7000-$77FF): the payout
        at(z, fh1, 0x03B, 'A5 91 F0 0B A9 55 CD 0A 2C 90 04 E6 93 E6 93',
           'rev 1 payout at $703B (LDA $91 / BEQ / LDA #$55 / CMP $2C0A / BCC / INC $93 x2)')
        # $7032: only when the player made the high-score table; $704A-$7053: compare only on a new top score
        at(z, fh1, 0x032, 'A6 D5 30 1F', 'rev 1 $7032: LDX $D5 / BMI (skip unless on the high-score table)')
        at(z, fh1, 0x04A, '8A D0 08 38 66 90 20 F5 77', 'rev 1 $704A: TXA / BNE / SEC / ROR $90 / JSR $77F5')
        # $7835 (j1 is $7800-$7FFF): compare one byte, OR any difference into $91
        at(z, j1, 0x035, '51 03 05 91 85 91 C8 60', 'rev 1 $7835: EOR ($03),Y / ORA $91 / STA $91 / INY / RTS')
        # $77F5-$782D: the comparison routine, redrawing from the copy at $7845
        at(z, fh1, 0x7F5, '24 90 10 3B', 'rev 1 $77F5: BIT $90 / BPL (only in compare mode)')
        at(z, j1, 0x023, 'A9 45 85 09 A9 78 85 0A 20 BD 71', 'rev 1 $7823: text pointer = $7845, JSR $71BD')
        # $714E: the on-screen copyright is drawn from $7603
        at(z, fh1, 0x168, 'A9 03 85 09 A9 76 85 0A', 'rev 1 $7168: text pointer = $7603 (the copy drawn on screen)')
        # the two copies of the copyright text
        a, b = rom(z, fh1), rom(z, j1)
        if a and b:
            txt = '1F C4 09 70 2D 9A 0B 64 38 00'
            report(a[0x603:0x60D] == bytes.fromhex(txt), 'rev 1 copyright text at $7603 = %s' % txt)
            report(b[0x045:0x04F] == bytes.fromhex(txt), 'rev 1 second copy at $7845 is identical')
        # the credit count is $93: coins add (rev 1 $7971/$7973), Start takes away ($4CA3/$4CA7, in 036800-01.r2)
        at(z, j1, 0x171, 'E6 93 E6 93', 'rev 1 coin routine $7971: INC $93 / INC $93')
        at(z, r2, 0x47C, 'A4 93 A2 01 AD 03 24', 'rev 1 Start $4C7C: LDY $93 / LDX #1 / LDA $2403 (Start 1)')
        at(z, r2, 0x4A3, 'C6 93 86 22 C6 93', 'rev 1 Start $4CA3: DEC $93 / STX $22 / DEC $93')
        # rev 2 keeps it: same first three program ROMs, and its own last ROM still has the comparison helper
        at(z, 'astdelux2/036433-02.j1', 0x035, '51 03 05 91 85 91 C8 60', 'rev 2 still has $7835')
        # rev 3 has none of it
        prog3 = b''.join(rom(z, n) or b'' for n in ('036430-02.d1', '036431-02.ef1', '036432-02.fh1', '036433-03.j1'))
        report(len(prog3) == 0x2000 and bytes.fromhex('A9 55 CD 0A 2C') not in prog3,
               'rev 3: no "LDA #$55 / CMP $2C0A" anywhere in the program ROMs')
        report(len(prog3) == 0x2000 and bytes.fromhex('51 03 05 91 85 91') not in prog3,
               'rev 3: no comparison helper (EOR ($03),Y / ORA $91 / STA $91)')

    # ---------------- Centipede (MAME centiped, rev 4, and clones) ----------------
    p = os.path.join(folder, 'centiped.zip')
    if not os.path.exists(p):
        report(False, 'centiped.zip not found in ' + folder)
    else:
        z = zipfile.ZipFile(p)
        # 136001-408.e1 is $2800-$2FFF
        at(z, '136001-408.e1', 0x091, 'A9 00 8D 0F 10', 'rev 4 $2891: LDA #0 / STA $100F (POKEY into reset)')
        at(z, '136001-408.e1', 0x0A2, 'AD 0A 10 4D 0A 10 18 65 C8 85 C8 A9 03 8D 0F 10',
           'rev 4 $28A2: LDA $100A / EOR $100A / CLC / ADC $C8 / STA $C8 / LDA #3 / STA $100F')
        for name, off, rev in (('centiped1/136001-108.e1', 0x09F, 'rev 1'), ('centiped2/136001-208.e1', 0x09F, 'rev 2'),
                               ('centipdd/136001-308.e1', 0x09E, 'dedicated-cabinet set')):
            at(z, name, off, 'AD 0A 10 4D 0A 10 18 65 C8 85 C8', '%s has the same check' % rev)
        at(z, 'magworma/h42.1e', 0x09F, 'A5 E2 EA 45 E2 EA 18 65 C8 85 C8',
           'Magic Worm set 2: LDA $E2 / NOP / EOR $E2 / NOP (reads RAM twice: always 0)')
        at(z, 'caterplr/olympia.c29', 0x09F, 'AD 9F 28 4D 9F 28 18 65 C8 85 C8',
           'Caterpillar: LDA $289F / EOR $289F (reads ROM twice: always 0)')
        at(z, 'centipdb/e1', 0x09F, 'AD 0A 10 4D 0A 10 18 65 C8 85 C8', 'centipdb bootleg kept the check')
        at(z, 'millpac/millpac2.1e', 0x09F, 'AD 0A 10 4D 0A 10 18 65 C8 85 C8', 'Millpac bootleg kept the check')

    print('\n%s' % ('all checks passed' if not fails else '%d check(s) failed' % fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
