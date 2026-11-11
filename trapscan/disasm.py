"""Intel 8080 disassembler (Intel mnemonics)."""
R = ['b', 'c', 'd', 'e', 'h', 'l', 'm', 'a']
RP = ['b', 'd', 'h', 'sp']
RPS = ['b', 'd', 'h', 'psw']
CC = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
ALU = ['add', 'adc', 'sub', 'sbb', 'ana', 'xra', 'ora', 'cmp']
ALUI = ['adi', 'aci', 'sui', 'sbi', 'ani', 'xri', 'ori', 'cpi']


def decode(o):
    """Return (template, operand_bytes). '#' = immediate, '$' = address."""
    if o == 0x76: return 'hlt', 0
    if 0x40 <= o < 0x80: return f'mov {R[(o >> 3) & 7]},{R[o & 7]}', 0
    if 0x80 <= o < 0xC0: return f'{ALU[(o >> 3) & 7]} {R[o & 7]}', 0
    single = {0: 'nop', 0x07: 'rlc', 0x0F: 'rrc', 0x17: 'ral', 0x1F: 'rar', 0x27: 'daa', 0x2F: 'cma',
              0x37: 'stc', 0x3F: 'cmc', 0xC9: 'ret', 0xE3: 'xthl', 0xE9: 'pchl', 0xEB: 'xchg',
              0xF3: 'di', 0xF9: 'sphl', 0xFB: 'ei'}
    if o in single: return single[o], 0
    hi, y, z = o >> 6, (o >> 3) & 7, o & 7
    if hi == 0:
        if z == 1: return (f'lxi {RP[y >> 1]},#', 2) if y % 2 == 0 else (f'dad {RP[y >> 1]}', 0)
        if z == 2: return [('stax b', 0), ('ldax b', 0), ('stax d', 0), ('ldax d', 0),
                           ('shld $', 2), ('lhld $', 2), ('sta $', 2), ('lda $', 2)][y]
        if z == 3: return (f'inx {RP[y >> 1]}' if y % 2 == 0 else f'dcx {RP[y >> 1]}'), 0
        if z == 4: return f'inr {R[y]}', 0
        if z == 5: return f'dcr {R[y]}', 0
        if z == 6: return f'mvi {R[y]},#', 1
        return f'db {o:02x}', 0
    if z == 0: return f'r{CC[y]}', 0
    if z == 1: return (f'pop {RPS[y >> 1]}', 0) if y % 2 == 0 else (f'db {o:02x}', 0)
    if z == 2: return f'j{CC[y]} $', 2
    if z == 3: return {0: ('jmp $', 2), 2: ('out #', 1), 3: ('in #', 1)}.get(y, (f'db {o:02x}', 0))
    if z == 4: return f'c{CC[y]} $', 2
    if z == 5:
        if y % 2 == 0: return f'push {RPS[y >> 1]}', 0
        return ('call $', 2) if y == 1 else (f'db {o:02x}', 0)
    if z == 6: return f'{ALUI[y]} #', 1
    return f'rst {y}', 0


def disassemble(mem, regions):
    """Yield text lines for each (start, length) region. Linear sweep: data shows as code."""
    for start, length in regions:
        pc, end = start, start + length
        while pc < end:
            o = mem[pc]
            t, n = decode(o)
            bs = [mem[(pc + i) & 0xFFFF] for i in range(1 + n)]
            if n == 1:
                t = t.replace('#', f'${bs[1]:02x}')
            elif n == 2:
                v = bs[1] | bs[2] << 8
                t = t.replace('#', f'${v:04x}') if '#' in t else t.replace('$', f'${v:04x}')
            yield f"{pc:04X}  {' '.join(f'{b:02X}' for b in bs):9} {t}"
            pc += 1 + n
