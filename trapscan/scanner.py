"""Signature scanner for hidden credit routines in 8080 Invaders-family code.

Signatures (all found in real 1979 Taito code):
  COMBO    control read, then ANI mask / CPI or SUI value with 3+ bits: one exact button combination.
  POINTER  an address built at run time (MVI L,x then INR/DCR L; MVI H,x then INR/DCR H), a way
           to hide which RAM byte is written.
  CREDIT   any direct write to the credit counter, with the counter found from the coin routine.
  VRAMCMP  bytes of screen memory compared with constants (checking the copyright text is intact).
  ROMCMP   bytes of the ROM itself compared with constants (patch detection).
  RESET    jump or call to $0000/$0003 straight after an input check (hardware/board checks).
  SHADOW   the interrupt routine comparing two RAM bytes and restarting on mismatch.
Hits are leads, not proof: confirm in the disassembly and the emulator.
"""


def popcount(v):
    return bin(v).count('1')


class Scanner:
    def __init__(self, mem, regions, input_ports=(0, 1, 2), input_mem=None,
                 ram=(0x2000, 0x2400), vram=(0x2400, 0x4000)):
        """Defaults are the 8080 Invaders board. For Z80 Taito SJ: input_ports=(), input_mem=(0xD400, 0xD410),
        ram=(0x8000, 0x8800), vram=(0x9000, 0xC000)."""
        self.input_ports, self.input_mem, self.ram, self.vram = set(input_ports), input_mem, ram, vram
        self.m = mem
        self.addrs = [a for s, n in regions for a in range(s, s + n)]
        self.in_rom = set(self.addrs)
        self.hits = []

    def rd(self, a): return self.m[a & 0xFFFF]
    def rw(self, a): return self.rd(a) | self.rd(a + 1) << 8

    def add(self, kind, addr, text):
        self.hits.append((kind, addr, text))

    # -- helpers ---------------------------------------------------------------
    def is_input_read(self, a):
        """IN port (8080/Z80) or LD A,(nn) from memory-mapped inputs (Z80 boards). Returns length or 0."""
        o = self.rd(a)
        if o == 0xDB and self.rd(a + 1) in self.input_ports:
            return 2
        if o == 0x3A and self.input_mem and self.input_mem[0] <= self.rw(a + 1) < self.input_mem[1]:
            return 3
        return 0

    def reads_input(self, a, depth=0):
        for k in range(14):
            o = self.rd(a + k)
            if self.is_input_read(a + k): return True
            if o == 0xC3: return depth < 3 and self.reads_input(self.rw(a + k + 1), depth + 1)
            if o == 0xC9: return False
        return False

    def find_credit_counter(self):
        """Coin routine pattern: LDA cr / CPI 9 or 99 / ... ADI 1 / DAA / STA cr."""
        found = {}
        for a in self.addrs:
            if self.rd(a) == 0x3A:
                cr = self.rw(a + 1)
                if not (self.ram[0] <= cr < self.ram[1]): continue
                win = [self.rd(a + 3 + i) for i in range(16)]
                for i in range(len(win) - 5):
                    if win[i] == 0xC6 and win[i + 1] == 0x01 and win[i + 2] == 0x27 and win[i + 3] == 0x32 \
                            and (win[i + 4] | win[i + 5] << 8) == cr:
                        found[cr] = found.get(cr, 0) + 1
        # Start-button deduction: ADI $99/$98 (= -1/-2 in BCD) ; DAA ; STA cr   (any board)
        for a in self.addrs:
            if self.rd(a) == 0xC6 and self.rd(a + 1) in (0x99, 0x98) and self.rd(a + 2) == 0x27 \
                    and self.rd(a + 3) == 0x32:
                cr = self.rw(a + 4)
                if self.ram[0] <= cr < self.ram[1]:
                    found[cr] = found.get(cr, 0) + 2
        return max(found, key=found.get) if found else None

    # -- signatures ------------------------------------------------------------
    def scan(self):
        rd, rw = self.rd, self.rw
        inputs = {a for a in self.addrs if self.reads_input(a)}
        self.credit = self.find_credit_counter()
        for a in self.addrs:
            o = rd(a)
            # COMBO
            src = None
            n_in = self.is_input_read(a)
            if n_in == 2: src, n = f'IN {rd(a + 1)}', 2
            elif n_in == 3: src, n = f'LD A,(${rw(a + 1):04X})', 3
            elif o == 0xCD and (rw(a + 1) in inputs or
                                (rd(a + 3) == 0xE6 and rd(a + 5) in (0xFE, 0xD6))):
                src, n = f'CALL ${rw(a + 1):04X}', 3
            if src and self.input_mem:
                # Z80 boards: also catch "LD A,(input) ... CP/SUB/XOR v" within a few bytes (CPL, BIT, etc. between)
                for k in range(a + n, a + n + 8):
                    if rd(k) in (0xFE, 0xD6, 0xEE) and popcount(rd(k + 1)) >= 3 and rd(k + 1) not in (0x00, 0xFF):
                        if not (rd(k - 2) == 0xE6 and k - 2 == a + n):      # plain ANI/CPI handled below
                            self.add('COMBO', a, f'{src}; ... {"CP" if rd(k)==0xFE else "SUB" if rd(k)==0xD6 else "XOR"} '
                                                 f'${rd(k+1):02X} at ${k:04X} (loose match - check by hand)')
                        break
                    if rd(k) in (0xC9, 0xC3, 0x18, 0xCD):
                        break
            if src:
                p = a + n
                if rd(p) == 0xE6 and rd(p + 2) in (0xFE, 0xD6):
                    mask, val = rd(p + 1), rd(p + 3)
                    if popcount(val) >= 3 and popcount(mask) >= 3:
                        tail = [rd(p + 4 + i) for i in range(28)]
                        stores = [f'MVI M,${tail[i + 1]:02X}' for i in range(len(tail) - 1) if tail[i] == 0x36]
                        self.add('COMBO', a, f'{src}; ANI ${mask:02X}; {"CPI" if rd(p+2)==0xFE else "SUI"} ${val:02X}'
                                 f'  (port bits {val:08b} of {mask:08b})' + (f'  then {", ".join(stores)}' if stores else ''))
            # POINTER (obfuscated HL)
            if o == 0x2E and rd(a + 2) in (0x2C, 0x2D):
                l = (rd(a + 1) + (1 if rd(a + 2) == 0x2C else -1)) & 0xFF
                self.add('POINTER', a, f'L built as ${rd(a+1):02X}{"+1" if rd(a+2)==0x2C else "-1"} = ${l:02X}')
            if o == 0x26 and rd(a + 2) in (0x24, 0x25) or (o == 0x26 and rd(a + 4) in (0x24, 0x25) and rd(a + 2) == 0x2E):
                k = 2 if rd(a + 2) in (0x24, 0x25) else 4
                h = (rd(a + 1) + (1 if rd(a + k) == 0x24 else -1)) & 0xFF
                self.add('POINTER', a, f'H built as ${rd(a+1):02X}{"+1" if rd(a+k)==0x24 else "-1"} = ${h:02X}')
            # CREDIT direct writes
            if self.credit is not None and o == 0x32 and rw(a + 1) == self.credit:
                self.add('CREDIT', a, f'STA ${self.credit:04X}')
            if self.credit is not None and o == 0x34 and rd(a - 3) == 0x21 and rw(a - 2) == self.credit:
                self.add('CREDIT', a - 3, f'LXI H,${self.credit:04X}; INR M (credits + 1)')
            if self.credit is not None and o == 0x21 and rw(a + 1) == self.credit:
                self.add('CREDIT', a, f'LXI H,${self.credit:04X} (pointer to credits)')
            # VRAMCMP / ROMCMP: a pointer, then 2+ "load, compare with a constant, bail out if different"
            # steps close together (a single compare is usually just a table end-marker test)
            if o in (0x21, 0x11, 0x01):
                ptr = rw(a + 1)
                win = [rd(a + 3 + i) for i in range(32)]
                for j, b in enumerate(win):          # don't run past the end of this routine
                    if b in (0xC9, 0xC3, 0xE9):
                        win = win[:j]; break
                steps, first = 0, None
                for i in range(len(win) - 3):
                    if win[i] in (0x1A, 0x0A, 0x7E) and win[i + 1] in (0xD6, 0xFE) and win[i + 3] in (0xC0, 0xC2) \
                            and win[i + 2] not in (0x00, 0xFF):          # $00/$FF compares are end markers
                        steps += 1; first = first if first is not None else i
                    elif win[i] in (0x1A, 0x0A, 0x7E) and win[i + 1] in (0xBC, 0xBD, 0xB8, 0xB9) and win[i + 2] in (0xC0, 0xC2):
                        steps += 1; first = first if first is not None else i
                if steps >= 2 or (steps == 1 and o != 0x21 and any(rd(a - k) in (0x01, 0x11, 0x21) and
                                                                   rd(a - k + 2) == rd(a + 2) for k in (3,))):
                    if self.vram[0] <= ptr < self.vram[1]:
                        self.add('VRAMCMP', a, f'screen near ${ptr:04X} checked against constants ({steps} compares)')
                    elif ptr in self.in_rom:
                        self.add('ROMCMP', a, f'ROM at ${ptr:04X} checked against constants ({steps} compares)')
            # RESET after input
            if self.is_input_read(a):
                k0 = self.is_input_read(a)
                win = [rd(a + k0 + i) for i in range(10)]
                for i in range(len(win) - 2):
                    if win[i] in (0xCA, 0xC2, 0xC3, 0xCC, 0xC4, 0xDA, 0xD2) and (win[i + 1] | win[i + 2] << 8) in (0, 3):
                        self.add('RESET', a, ('IN ' + str(rd(a+1)) if k0 == 2 else f'LD A,(${rw(a+1):04X})') + f' then jump/call to ${win[i+1] | win[i+2] << 8:04X}')
                        break
            # SHADOW: LXI H,x / MOV A,M / MVI L,y / CMP M / JNZ 0 or 3
            if o == 0x21 and rd(a + 3) == 0x7E and rd(a + 4) == 0x2E and rd(a + 6) == 0xBE and rd(a + 7) == 0xC2 \
                    and rw(a + 8) in (0, 3):
                self.add('SHADOW', a, f'${rw(a+1):04X} must equal ${(rw(a+1) & 0xFF00) | rd(a+5):04X} or restart')
        # de-duplicate VRAM/ROM hits that share one compare
        seen, out = set(), []
        for h in self.hits:
            key = (h[0], h[2].split('(at')[-1]) if h[0] in ('VRAMCMP', 'ROMCMP') else h
            if h[0] in ('VRAMCMP', 'ROMCMP') and key in seen:
                continue
            seen.add(key)
            out.append(h)
        self.hits = out
        return self.hits

    def report(self):
        lines = [f'Credit counter: ${self.credit:04X}' if self.credit is not None else
                 'Credit counter: not identified (no standard coin routine found)']
        order = ['COMBO', 'CREDIT', 'POINTER', 'SHADOW', 'VRAMCMP', 'ROMCMP', 'RESET']
        for kind in order:
            hs = [h for h in self.hits if h[0] == kind]
            if not hs: continue
            lines.append(f'\n[{kind}]')
            lines += [f'  ${a:04X}: {t}' for _, a, t in hs]
        # verdict
        combos = [h for h in self.hits if h[0] == 'COMBO']
        pointers = [h for h in self.hits if h[0] == 'POINTER']
        suspicious = [c for c in combos if 'MVI M' in c[2]]
        lines.append('\nVerdict: ' + (
            'SUSPICIOUS - combo check followed by immediate RAM stores; inspect these first.' if suspicious else
            'Combo checks present but no immediate stores after them (easter egg / menu?).' if combos else
            'No combo checks found.'))
        if pointers and self.credit is not None:
            import re
            hs = [(a, int(re.search(r'= \$([0-9A-F]{2})', t).group(1), 16)) for _, a, t in pointers if t.startswith('H')]
            ls = [(a, int(re.search(r'= \$([0-9A-F]{2})', t).group(1), 16)) for _, a, t in pointers if t.startswith('L')]
            if any(hv == self.credit >> 8 and lv == self.credit & 0xFF and abs(ha - la) <= 24
                   for ha, hv in hs for la, lv in ls):
                lines.append('         Run-time-built H and L together make the credit address - likely hidden credit write.')
        return '\n'.join(lines)
