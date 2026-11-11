"""Other boards built on Space Invaders code, for the emulator.

SpaceStrangerBoard: Yachiyo/Hoei "Space Stranger" (MAME sstrangr.cpp). Same 8080, RAM and video layout as
Space Invaders, but no shift-register chip, inputs moved to ports $41 (DIPs, player 2) / $42 (player 1, coin,
starts, cabinet) / $44 (vblank on bit 0), and one interrupt vector (RST 7) twice a frame, the handler telling
mid-screen from vblank by reading port $44.
"""
from .emu8080 import Board


class SpaceStrangerBoard(Board):
    def __init__(s, mem):
        super().__init__(mem)
        s.dsw = 0x19          # MAME defaults: extra play 3000, bonus life 1000, SW5 off (needed to boot)
        s.inputs = 0x10       # bit 4 = upright cabinet; coin b0, start2 b1, start1 b2, fire b5, left b6, right b7
        s.vblank = 0

    def inp(s, p):
        if p == 0x41: return s.dsw
        if p == 0x42: return s.inputs
        if p == 0x44: return 0xFC | s.vblank
        return 0

    def outp(s, p, v):
        pass

    def run_frame(s, hook=None):
        c = s.cpu
        for vb in (0, 1):
            end = c.cyc + 16667
            pending = True                          # MAME holds the IRQ line until the CPU takes it
            while c.cyc < end:
                if pending and c.ie:
                    s.vblank = vb
                    c.interrupt(7); pending = False
                if c.halted:
                    c.cyc = end; break
                if hook: hook(c)
                c.step()
            s.vblank = vb
        s.frame += 1


# button bits on Space Stranger's port $42
SS = {'coin': 0x01, 'start2': 0x02, 'start1': 0x04, 'fire': 0x20, 'left': 0x40, 'right': 0x80}
