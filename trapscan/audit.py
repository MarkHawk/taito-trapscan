"""Credit audit: find the credit counter by inserting coins in the emulator, then list every
instruction in the ROMs that can write it.

Normal games have two writers: the coin routine and the start button (plus, sometimes, a second
coin chute or a 2-player start). Anything else is worth reading by hand.
"""
from .emu8080 import Board

COMMON = [(1, 0, False), (1, 0, True), (1, 1, False), (1, 2, False), (1, 7, False), (1, 7, True)]


def coin_probe(mem, port0=0, port2=0):
    """Return (counter addresses, (port, bit, active_low)) or ([], None)."""
    tries = COMMON + [(p, b, low) for p in (0, 1, 2) for b in range(8) for low in (False, True)
                      if (p, b, low) not in COMMON]
    for port, bit, low in tries:
        b = Board(mem); b.port0, b.port2 = port0, port2
        m = b.cpu.m
        idle = {0: port0, 1: 0x08, 2: port2}[port]
        base = (idle | (1 << bit)) if low else (idle & ~(1 << bit))

        def setp(v):
            if port == 0: b.port0 = v
            elif port == 1: b.port1 = v
            else: b.port2 = v
        setp(base)
        for _ in range(240): b.run_frame()
        s0 = bytes(m[0x2000:0x2400]); res = []
        for _ in range(2):
            setp(base ^ (1 << bit))
            for _ in range(8): b.run_frame()
            setp(base)
            for _ in range(40): b.run_frame()
            res.append(bytes(m[0x2000:0x2400]))
        c = [0x2000 + i for i in range(0x400)       # 0 -> n -> 2n credits (n = 1-3: some bootlegs pay 2 a coin)
             if s0[i] == 0 and 1 <= res[0][i] <= 3 and res[1][i] == 2 * res[0][i]]
        if c:
            return c, (port, bit, low)
    return [], None


def writers(mem, regions, x, reach=4):
    """Every place that can write byte x: direct stores, 16-bit stores over it, and pointers aimed at or
    near it (a pointer a few bytes off, then INX/DCX, is how the Lunar Rescue trap hides its write)."""
    rd = lambda a: mem[a & 0xFFFF]
    rw = lambda a: rd(a) | rd(a + 1) << 8
    out = []
    addrs = [a for s, n in regions for a in range(s, s + n)]
    for a in addrs:
        o = rd(a)
        if o == 0x32 and rw(a + 1) == x:
            out.append((a, f'STA ${x:04X}'))
        elif o == 0x22 and rw(a + 1) in (x, x - 1):
            out.append((a, f'SHLD ${rw(a + 1):04X} (16-bit store covers ${x:04X})'))
        elif o in (0x21, 0x11, 0x01) and abs(rw(a + 1) - x) <= reach:
            reg = {0x21: 'H', 0x11: 'D', 0x01: 'B'}[o]
            off = rw(a + 1) - x
            out.append((a, f'LXI {reg},${rw(a + 1):04X}' + (f' (pointer {off:+d} from credits)' if off else ' (pointer to credits)')))
        elif o == 0x26 and rd(a + 1) in ((x >> 8) - 1, x >> 8, (x >> 8) + 1):     # MVI H,hi  (near MVI L,lo)
            for k in range(-8, 10):
                if rd(a + k) == 0x2E and abs(((rd(a + 1) << 8) | rd(a + k + 1)) - x) <= reach + 256 \
                        and abs(rd(a + k + 1) - (x & 0xFF)) <= reach:
                    out.append((min(a, a + k), f'MVI H,${rd(a+1):02X} / MVI L,${rd(a+k+1):02X} '
                                               f'(pointer built near credits)'))
                    break
    return sorted(set(out))
