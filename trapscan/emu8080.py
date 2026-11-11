"""Minimal Intel 8080 emulator plus a Space Invaders-family board model.

RAM is $2000-$3FFF (video from $2400); writes anywhere else are ignored, as on the real board."""

class CPU:
    def __init__(s, mem):
        s.m = mem; s.a = s.b = s.c = s.d = s.e = s.h = s.l = 0
        s.sp = 0; s.pc = 0; s.fs = s.fz = s.fp = s.fc = s.fac = 0
        s.ie = 0; s.halted = False
        s.inp = lambda p: 0; s.outp = lambda p, v: None
        s.cyc = 0
    # memory
    # A15 isn't decoded on these boards: $8000-$FFFF mirrors $0000-$7FFF
    def rd(s, a): return s.m[a & 0x7fff]
    def wr(s, a, v):
        a &= 0x7fff
        if 0x2000 <= a < 0x4000: s.m[a] = v & 0xff
    def rw(s, a): return s.rd(a) | (s.rd(a + 1) << 8)
    def fetch(s):
        v = s.rd(s.pc); s.pc = (s.pc + 1) & 0xffff; return v
    def fetchw(s):
        v = s.rw(s.pc); s.pc = (s.pc + 2) & 0xffff; return v
    def push(s, v):
        s.sp = (s.sp - 2) & 0xffff; s.wr(s.sp, v & 0xff); s.wr(s.sp + 1, v >> 8)
    def pop(s):
        v = s.rw(s.sp); s.sp = (s.sp + 2) & 0xffff; return v
    # regs
    def gr(s, i):
        return [s.b, s.c, s.d, s.e, s.h, s.l, None, s.a][i] if i != 6 else s.rd(s.hl)
    def sr(s, i, v):
        v &= 0xff
        if i == 0: s.b = v
        elif i == 1: s.c = v
        elif i == 2: s.d = v
        elif i == 3: s.e = v
        elif i == 4: s.h = v
        elif i == 5: s.l = v
        elif i == 6: s.wr(s.hl, v)
        else: s.a = v
    @property
    def hl(s): return (s.h << 8) | s.l
    def grp(s, i):
        return [(s.b << 8) | s.c, (s.d << 8) | s.e, (s.h << 8) | s.l, s.sp][i]
    def srp(s, i, v):
        v &= 0xffff
        if i == 0: s.b, s.c = v >> 8, v & 0xff
        elif i == 1: s.d, s.e = v >> 8, v & 0xff
        elif i == 2: s.h, s.l = v >> 8, v & 0xff
        else: s.sp = v
    def szp(s, v):
        v &= 0xff; s.fz = int(v == 0); s.fs = v >> 7; s.fp = int(bin(v).count('1') % 2 == 0)
    def flags(s):
        return (s.fs << 7) | (s.fz << 6) | (s.fac << 4) | (s.fp << 2) | 2 | s.fc
    def setflags(s, f):
        s.fs = (f >> 7) & 1; s.fz = (f >> 6) & 1; s.fac = (f >> 4) & 1; s.fp = (f >> 2) & 1; s.fc = f & 1
    def cond(s, y):
        return [not s.fz, s.fz, not s.fc, s.fc, not s.fp, s.fp, not s.fs, s.fs][y]
    def alu(s, op, v):
        a = s.a
        if op in (0, 1):
            r = a + v + (s.fc if op == 1 else 0)
            s.fac = int(((a & 0xf) + (v & 0xf) + (s.fc if op == 1 else 0)) > 0xf)
            s.fc = int(r > 0xff); s.a = r & 0xff; s.szp(s.a)
        elif op in (2, 3, 7):
            r = a - v - (s.fc if op == 3 else 0)
            s.fac = int((a & 0xf) - (v & 0xf) - (s.fc if op == 3 else 0) >= 0)
            s.fc = int(r < 0); s.szp(r & 0xff)
            if op != 7: s.a = r & 0xff
        elif op == 4:
            s.fac = int(((a | v) & 8) != 0); s.a = a & v; s.fc = 0; s.szp(s.a)
        elif op == 5:
            s.a = a ^ v; s.fc = 0; s.fac = 0; s.szp(s.a)
        elif op == 6:
            s.a = a | v; s.fc = 0; s.fac = 0; s.szp(s.a)
    def interrupt(s, n):
        if not s.ie: return False
        s.ie = 0; s.halted = False; s.push(s.pc); s.pc = n * 8; s.cyc += 11; return True

    def step(s):
        o = s.fetch(); s.cyc += 7
        hi = o >> 6; y = (o >> 3) & 7; z = o & 7
        if o == 0x76: s.halted = True; return
        if hi == 1: s.sr(y, s.gr(z)); return
        if hi == 2: s.alu(y, s.gr(z)); return
        if hi == 0:
            if z == 0: return  # nop
            if z == 1:
                if y % 2 == 0: s.srp(y >> 1, s.fetchw())
                else:
                    r = s.hl + s.grp(y >> 1); s.fc = int(r > 0xffff); s.srp(2, r)
                return
            if z == 2:
                if y == 0: s.wr(s.grp(0), s.a)
                elif y == 1: s.a = s.rd(s.grp(0))
                elif y == 2: s.wr(s.grp(1), s.a)
                elif y == 3: s.a = s.rd(s.grp(1))
                elif y == 4:
                    a = s.fetchw(); s.wr(a, s.l); s.wr(a + 1, s.h)
                elif y == 5:
                    a = s.fetchw(); s.l = s.rd(a); s.h = s.rd(a + 1)
                elif y == 6: s.wr(s.fetchw(), s.a)
                else: s.a = s.rd(s.fetchw())
                return
            if z == 3:
                s.srp(y >> 1, s.grp(y >> 1) + (1 if y % 2 == 0 else -1)); return
            if z == 4:
                v = (s.gr(y) + 1) & 0xff; s.fac = int((v & 0xf) == 0); s.sr(y, v); s.szp(v); return
            if z == 5:
                v = (s.gr(y) - 1) & 0xff; s.fac = int((v & 0xf) != 0xf); s.sr(y, v); s.szp(v); return
            if z == 6: s.sr(y, s.fetch()); return
            # z == 7
            a = s.a
            if y == 0: s.fc = a >> 7; s.a = ((a << 1) | s.fc) & 0xff
            elif y == 1: s.fc = a & 1; s.a = (a >> 1) | (s.fc << 7)
            elif y == 2: c = s.fc; s.fc = a >> 7; s.a = ((a << 1) | c) & 0xff
            elif y == 3: c = s.fc; s.fc = a & 1; s.a = (a >> 1) | (c << 7)
            elif y == 4:
                cor = 0; c = s.fc
                if (a & 0xf) > 9 or s.fac: cor |= 6
                if (a >> 4) > 9 or c or ((a >> 4) >= 9 and (a & 0xf) > 9): cor |= 0x60; c = 1
                s.fac = int((a & 0xf) + (cor & 0xf) > 0xf)
                s.a = (a + cor) & 0xff; s.fc = c; s.szp(s.a)
            elif y == 5: s.a = (~a) & 0xff
            elif y == 6: s.fc = 1
            else: s.fc ^= 1
            return
        # hi == 3
        if z == 0:
            if s.cond(y): s.pc = s.pop()
            return
        if z == 1:
            if y % 2 == 0:
                v = s.pop()
                if y >> 1 == 3: s.a = v >> 8; s.setflags(v & 0xff)
                else: s.srp(y >> 1, v)
            elif y == 1: s.pc = s.pop()
            elif y == 5: s.pc = s.hl
            elif y == 7: s.sp = s.hl
            return
        if z == 2:
            a = s.fetchw()
            if s.cond(y): s.pc = a
            return
        if z == 3:
            if y == 0: s.pc = s.fetchw()
            elif y == 2: s.outp(s.fetch(), s.a)
            elif y == 3: s.a = s.inp(s.fetch()) & 0xff
            elif y == 4:
                v = s.rw(s.sp); s.wr(s.sp, s.l); s.wr(s.sp + 1, s.h); s.h, s.l = v >> 8, v & 0xff
            elif y == 5:
                s.d, s.h = s.h, s.d; s.e, s.l = s.l, s.e
            elif y == 6: s.ie = 0
            elif y == 7: s.ie = 1
            return
        if z == 4:
            a = s.fetchw()
            if s.cond(y): s.push(s.pc); s.pc = a
            return
        if z == 5:
            if y % 2 == 0:
                if y >> 1 == 3: s.push((s.a << 8) | s.flags())
                else: s.push(s.grp(y >> 1))
            elif y == 1:
                a = s.fetchw(); s.push(s.pc); s.pc = a
            return
        if z == 6: s.alu(y, s.fetch()); return
        s.push(s.pc); s.pc = y * 8


class Board:
    """Space Invaders-family board: 8080 + shift register on ports 2/4 (write) and 3 (read).

    port0/port1/port2 are the raw input bytes the game reads. Interrupts: RST 1 mid-frame,
    RST 2 at vblank, 60 frames/s at roughly 2 MHz.
    """
    def __init__(s, mem):
        s.cpu = CPU(bytearray(mem))
        s.shift = 0; s.shamt = 0
        s.port0 = 0x00; s.port1 = 0x08; s.port2 = 0x00
        s.cpu.inp = s.inp; s.cpu.outp = s.outp
        s.frame = 0
    def inp(s, p):
        if p == 0: return s.port0
        if p == 1: return s.port1
        if p == 2: return s.port2
        if p == 3: return (s.shift >> (8 - s.shamt)) & 0xff
        return 0
    def outp(s, p, v):
        if p == 2: s.shamt = v & 7
        elif p == 4: s.shift = (s.shift >> 8) | (v << 8)
    def run_frame(s, hook=None):
        c = s.cpu
        for half in (1, 2):
            end = c.cyc + 16667
            while c.cyc < end:
                if c.halted: c.cyc = end; break
                if hook: hook(c)
                c.step()
            c.interrupt(half)
        s.frame += 1
    def screenshot(s, path, marks=()):
        """Save the screen upright (needs Pillow). marks: video RAM addresses to box in red."""
        from PIL import Image, ImageDraw
        m = s.cpu.m
        img = Image.new('RGB', (224, 256)); px = img.load()
        for i in range(0x1c00):
            x = i // 32; yb = i % 32; v = m[0x2400 + i]
            for bit in range(8):
                if v >> bit & 1: px[x, 255 - (yb * 8 + bit)] = (255, 255, 255)
        d = ImageDraw.Draw(img)
        for a in marks:
            i = a - 0x2400; x = i // 32; yb = i % 32
            d.rectangle([x - 1, 255 - (yb * 8 + 7) - 1, x + 1, 255 - yb * 8 + 1], outline=(255, 0, 0))
        img.resize((448, 512), Image.NEAREST).save(path)
