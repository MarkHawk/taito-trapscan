"""'Kick me' test: look for the anti-piracy trick described by Ned Batchelder from his time at General
Computer (https://nedbatchelder.com/blog/200404/arcade_copy_protection): after some plays the game checks
video memory for its copyright notice and, if it's missing, shows "KICK ME FOR A FREE GAME" and gives a
credit each time the cabinet's kick (slam/tilt) switch trips.

Two tests, both independent of what the game is:

1. text_hits(): searches ROM bytes for the words of such a message (KICK, KICK ME, FREE GAME ...) in any
   character encoding where the letters A-Z are consecutive codes (ASCII, A=$00, A=$0A, ...) or every
   second code (as in some vector games; phrases of 7+ characters only, to avoid chance matches). Works on any CPU, so it can be run over a whole collection.

2. pulse_test(): (8080 Invaders-family boards) boots the game, then pulses every input bit in turn,
   coin excepted - including tilt/slam - and reports any bit that makes the credit counter go up. Pass
   patches (e.g. one letter of the copyright text) to simulate a bootleg.

Limit: a trap that only arms after a number of paid plays (as in the story) won't fire in the pulse test,
which runs in attract mode on a fresh boot. The credit-writer audit (trapscan.audit.writers) still lists
its credit write, so read every writer that isn't coin or start.
"""
import copy

from .emu8080 import Board

# '?' = any one byte (the space, whose code varies)
# (bare 'KICK' was dropped: four letters turn up by chance in big ROMs; the message was 'KICK ME FOR A FREE GAME')
PHRASES = ['KICK?ME', 'FREE?GAME', 'FREE?CREDIT', 'FREE?PLAY']
# FREE PLAY is ordinary DIP-switch/attract text in many games; listed so it's recognised, not alarming
NORMAL = {'FREE?PLAY'}


import operator
import re


import functools


@functools.lru_cache(maxsize=None)
def _pattern(ph, step):
    """Regex over the byte-difference string: letter-to-letter steps fixed, steps next to a gap free."""
    out = b''
    for a, b in zip(ph, ph[1:]):
        if a == '?' or b == '?':
            out += b'.'
        else:
            out += re.escape(bytes([(step * (ord(b) - ord(a))) & 0xFF]))
    return re.compile(b'(?=' + out + b')', re.S)


_PATTERNS = {}


def _check(data, i, ph, step):
    """Full check at offset i: letters consecutive from one base code, gaps not letters. Returns base or None."""
    letters = [(k, ord(c) - 65) for k, c in enumerate(ph) if c != '?']
    k0, l0 = letters[0]
    base = data[i + k0] - step * l0
    if base < 0 or base + step * 25 > 255:
        return None
    if not all(data[i + k] == base + step * l for k, l in letters):
        return None
    gaps = [data[i + k] for k, c in enumerate(ph) if c == '?']
    if any(base <= g <= base + step * 25 and (g - base) % step == 0 for g in gaps):
        return None              # a space must not itself be a letter (else e.g. 'KICKXME' would match)
    return base


def text_hits(data, phrases=PHRASES):
    """Yield (offset, phrase, base code of 'A', step) for each phrase found in any letter encoding.

    Works on the differences between neighbouring bytes, which are the same whatever code 'A' has, so one
    regex per phrase finds every encoding at C speed; each candidate is then checked in full."""
    data = bytes(data)
    if len(data) < 2:
        return
    diff = bytes(map((256).__rmod__, map(operator.sub, data[1:], data)))
    for ph in phrases:
        # every-second-code encodings only for longer phrases: a 4-letter word in steps of 2 matches
        # ordinary program bytes by chance (seen in Astro Fighter, Gun Champ and Invaders Part II bootlegs)
        for step in ((1, 2) if len(ph) >= 7 else (1,)):
            rx = _PATTERNS.get((ph, step)) or _PATTERNS.setdefault((ph, step), _pattern(ph, step))
            for m in rx.finditer(diff):
                i = m.start()
                if i + len(ph) > len(data):
                    continue
                base = _check(data, i, ph, step)
                if base is not None:
                    yield i, ph.replace('?', ' '), base, step


def best_text_hits(data):
    """Like text_hits, but drop a 'KICK' hit that is part of a longer 'KICK ME' hit."""
    hits = list(text_hits(data))
    long_at = {(o, b, s) for o, p, b, s in hits if p == 'KICK ME'}
    return [h for h in hits if not (h[1] == 'KICK' and (h[0], h[2], h[3]) in long_at)]


def pulse_test(mem, counter, coin=None, port0=0, port2=0, boot_frames=600, patches=()):
    """Pulse each input bit (port 0-2, bits 0-7) three times from a booted attract-mode board.
    Returns [(port, bit, credits_before, credits_after)] for bits that raised the credit counter."""
    m = bytearray(mem)
    for a, v in patches:
        m[a] = v
    b = Board(m); b.port0, b.port2 = port0, port2
    for _ in range(boot_frames):
        b.run_frame()
    hits = []
    for port in (0, 1, 2):
        for bit in range(8):
            if coin and (port, bit) == coin[:2]:
                continue
            t = copy.deepcopy(b)
            idle = {0: t.port0, 1: t.port1, 2: t.port2}[port]

            def setp(v):
                if port == 0: t.port0 = v
                elif port == 1: t.port1 = v
                else: t.port2 = v
            before = t.cpu.m[counter]
            for _ in range(3):
                setp(idle ^ (1 << bit))
                for _ in range(8): t.run_frame()
                setp(idle)
                for _ in range(40): t.run_frame()
            after = t.cpu.m[counter]
            if after > before:
                hits.append((port, bit, before, after))
    return hits


def kick_check(mem, layout, pulse=True, port0=0, port2=0, patches=()):
    """Everything the scan/batch reports need for one 8080 set.
    Returns dict(text=[(addr, phrase, base, step)], counter, coin, pulse=[...] or None, summary=str)."""
    from .audit import coin_probe
    text = []
    for a, _, size in layout:
        text += [(a + off, ph, base, step) for off, ph, base, step in best_text_hits(bytes(mem[a:a + size]))]
    res = dict(text=text, counter=None, coin=None, pulse=None)
    if pulse:
        counter, coin = coin_probe(mem, port0, port2)
        if counter:
            res.update(counter=counter[0], coin=coin,
                       pulse=pulse_test(mem, counter[0], coin, port0, port2, patches=patches))
    res['summary'] = summarise(res)
    return res


def summarise(res):
    odd = [t for t in res['text'] if t[1].replace(' ', '?') not in NORMAL]
    parts = [f'text "{t[1]}" at ${t[0]:04X}' for t in odd]
    if res['pulse']:
        parts += [f'port {p} bit {b} gives credits' for p, b, _, _ in res['pulse']]
    if parts:
        return '; '.join(parts)
    if res['pulse'] is None:
        return 'text clean' + ('' if res['counter'] else ', pulse test not run')
    return 'clean'


def report_lines(res):
    """Readable lines for the per-set report."""
    L = ['[KICK] "kick me for a free game" test']
    for a, ph, base, step in res['text']:
        why = 'ordinary attract/DIP text' if ph.replace(' ', '?') in NORMAL else 'read this'
        L.append(f'  text "{ph}" at ${a:04X} (letters from ${base:02X}, step {step}) - {why}')
    if not res['text']:
        L.append('  no KICK / FREE GAME / FREE CREDIT wording in any letter encoding')
    if res['pulse'] is None:
        L.append('  input pulse test: not run' + ('' if res['counter'] else ' (credit counter not found by coin test)'))
    elif res['pulse']:
        for p, b, c0, c1 in res['pulse']:
            L.append(f'  input port {p} bit {b} raised credits {c0:02X} -> {c1:02X} in attract mode '
                     '(a second coin chute, or a kick/tilt trap: read the code)')
    else:
        c = res['coin']
        L.append(f'  every input pulsed (coin = port {c[0]} bit {c[1]} excepted): none raises credits')
    return L
