"""Find and decode the text in arcade ROMs, whatever letter codes the game uses.

Old games rarely store text as ASCII: Space Invaders has A=$00, many Taito/Nichibutsu games A=$0A (digits
first), some vector games use every second code. Every game shows a few certain words (SCORE, CREDIT,
PLAYER, INSERT COIN...), so finding those tells us the encoding: the code for 'A', the step between
letters, the space character and where the digits are. Then all the text in the ROMs can be decoded.
"""
import collections
import re

from .kickme import _check, _pattern

# words nearly every game of the era displays. '?' = any one byte (usually the space)
ANCHORS = ['SCORE', 'CREDIT', 'PLAYER', 'INSERT', 'GAME?OVER', 'HIGH?SCORE', 'HI?SCORE', 'PUSH',
           'START', 'BONUS', 'COIN', 'PLAY', 'READY', 'BUTTON', 'ONLY', 'TAITO', 'NAMCO', 'SEGA',
           'KONAMI', 'NINTENDO', 'ATARI', 'WILLIAMS', 'MIDWAY', 'COPYRIGHT', 'CORPORATION']
SPACED = [a for a in ANCHORS if '?' in a]

# words worth flagging when they turn up in decoded text (whole words; a trailing .* allows endings)
FLAGS = {
    'anti-piracy': r'COPY|COPIED|COPIES|PIRATE[SD]?|PIRACY|ILLEGAL\w*|STOLEN|STEAL\w*|THIEF|THIEVES|BOOTLEG\w*|'
                   r'UNAUTHORI\w*|GENUINE|COUNTERFEIT|LICEN[CS]E[SD]?|ORIGINAL',
    'credits': r'PROGRAM\w*|DESIGN\w*|CREATED|WRITTEN|CODED|AUTHOR\w*|STAFF|THANKS?|GREETINGS?|DEDICATED|BY',
    'dev': r'TEST\w*|DEBUG\w*|SECRET\w*|HIDDEN|HELLO|BUGS?|LOVE|DARLING|MOM|MUM|WIFE|KICK|FREE GAME|'
           r'VERSION|VER|REV|SORRY|STUPID|IDIOT|DUMMY|JOKE',
}
# short words must stand alone (not next to letters or digits): 'BY3W' is code bytes, 'BY JOEL' is credits
SHORT = {'BY', 'BUGS?', 'VER', 'REV', 'MOM', 'MUM'}
FLAG_RX = {k: re.compile(r'(?<![A-Z])(' + '|'.join(w for w in v.split('|') if w not in SHORT) + r')(?![A-Z])'
                         + ('|(?<![A-Z0-9])(' + '|'.join(w for w in v.split('|') if w in SHORT) + r')(?![A-Z0-9])'
                            if any(w in SHORT for w in v.split('|')) else ''))
           for k, v in FLAGS.items()}
YEAR = re.compile(r'(?<!\d)19[6-9]\d(?!\d)')

# common words, to tell real text from code bytes that happen to decode as letters
VOCAB = set('''A AN AND ARE AS AT BE BEST BONUS BY CALL COIN COINS CONGRATULATIONS COPYRIGHT CORP CORPORATION
CREDIT CREDITS DO END ENTER EXTRA FOR FREE FROM GAME GAMES GET GO GOOD HAVE HE HELLO HERE HI HIGH HIS HIT IN
INC INITIALS INSERT IS IT LEVEL LIFE LIVES LTD MADE ME MORE MY NAME NEW NO NOT NOW OF OK ON ONE ONLY OR OUT
OVER PLAY PLAYER PLAYERS PLEASE POINT POINTS PRESS PUSH READY ROUND SCORE SHIP SHIPS STAGE START THE THIS
TO TODAY TRY TWO UP WAVE WE WELCOME WILL WITH YOU YOUR'''.split())


def find_encodings(datas, min_anchors=2, min_len=0):
    """datas: iterable of bytes (a set's ROM files). min_len: only use anchor words at least this long
    (short ones like PLAY or COIN can match by chance in big ROMs). Returns [(base, step, space_codes, digit_base,
    anchors_seen)] for each encoding whose letters spell at least min_anchors different anchor words."""
    seen = collections.defaultdict(set)          # (base, step) -> anchor words found
    gaps = collections.defaultdict(collections.Counter)
    datas = [bytes(d) for d in datas]
    for d in datas:
        if len(d) < 8:
            continue
        diff = bytes(map((256).__rmod__, map(__import__('operator').sub, d[1:], d)))
        for ph in ANCHORS:
            if len(ph) < min_len:
                continue
            for step in (1, 2):
                for m in _pattern(ph, step).finditer(diff):
                    i = m.start()
                    if i + len(ph) > len(d):
                        continue
                    base = _check(d, i, ph, step)
                    if base is None:
                        continue
                    seen[(base, step)].add(ph)
                    for k, c in enumerate(ph):
                        if c == '?':
                            gaps[(base, step)][d[i + k]] += 1
    out = []
    for (base, step), words in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        if len(words) < min_anchors:
            continue
        space = [g for g, _ in gaps[(base, step)].most_common(2)]
        out.append((base, step, space, guess_digits(datas, base, step), sorted(words)))
    return out


def guess_digits(datas, base, step):
    """Where 0-9 are: after Z, before A, or ASCII. Pick the one that makes the most 19xx years / '1 PLAYER'."""
    cands = []
    if step == 1:
        cands = [base - 10, base + 26, 0x30, 0x00]
    else:
        cands = [base - 20, base + 52, 0x30, 0x00]
    best, best_score = None, -1
    for db in cands:
        if db < 0 or db + step * 9 > 255:
            continue
        tab = table(base, step, [], db)
        score = sum(len(re.findall(rb'19[6-9]\d|[12] ?PLAYER|[0-9]UP', d.translate(tab))) for d in datas)
        if score > best_score:
            best, best_score = db, score
    return best


def table(base, step, space, digit_base):
    """bytes.translate table: game codes -> ASCII; anything else -> NUL (a separator)."""
    t = bytearray(256)
    for k in range(26):
        t[base + step * k] = 65 + k
    for s in space:              # the gap seen inside GAME OVER etc. wins over a digit guess
        if t[s] == 0:
            t[s] = 32
    if digit_base is not None:
        for k in range(10):
            c = digit_base + step * k
            if 0 <= c < 256 and t[c] == 0:
                t[c] = 48 + k
    return bytes(t)


def strings(data, enc, min_len=4):
    """Decoded text runs [(offset, text)] that look like real words."""
    base, step, space, digits = enc[:4]
    dec = bytes(data).translate(table(base, step, space, digits))
    out = []
    for m in re.finditer(rb'[^\x00]{%d,}' % min_len, dec):
        s = m.group().decode().strip()
        words = re.findall(r'[A-Z]+', s)
        if not words or sum(len(w) for w in words) < 3:
            continue
        # keep it if it has a common word, a flagged word, a year, or several words of 3+ letters
        if any(w in VOCAB for w in words if len(w) >= 2) or flags(s) or YEAR.search(s) or \
                (len([w for w in words if len(w) >= 3]) >= 2 and ' ' in s and plausible(words)):
            out.append((m.start() + (len(m.group()) - len(m.group().lstrip())), s))
    return out


def plausible(words):
    """Rough English-likeness: vowels present, no long consonant runs."""
    for w in words:
        if len(w) >= 3 and (not re.search('[AEIOUY]', w) or re.search('[^AEIOUY]{5}', w)):
            return False
    return True


def flags(s):
    hit = []
    for cat, rx in FLAG_RX.items():
        hit += [(cat, m.group(1) or m.group(2)) for m in rx.finditer(s)]
    m = YEAR.search(s)
    if m:
        hit.append(('year', m.group()))
    return hit
