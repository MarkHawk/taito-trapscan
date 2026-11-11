# Lunar Lander (Atari, 1979) – fuel/credit path notes

Program ROM image: 0x6000–0x7FFF (f1, de1, c1, b1). RESET/IRQ $7B84, NMI $7AA8 (rev 2).

## Inputs actually read by game code
| Address | Meaning (from code use) | Where read |
|---|---|---|
| $2000 b0 | Vector generator halt | $6531 |
| $2000 b1 | Self-test switch (main loop stalls, watchdog resets into test) | $60D7, $7B93 |
| $2000 b2 | Slam switch (blanks coins for 240 frames) | $60FB, $78F3 |
| $2000 b6 | 3 kHz clock | self-test delays |
| $2000 b7 | Diagnostic step | $7E95 |
| $2400 | Start | $6166 (attract only) |
| $2401 / $2403 | Left / right coin mech | $78D5 (NMI) |
| $2402 | **never read by game code** (self-test only) | $7D70 |
| $2404 | Select Game (cycles difficulty $23) | $62AB |
| $2405 | Abort | $61C3 (only while playing with fuel) |
| $2406 / $2407 | Rotate right / left | $6404 (only when $97 bit 7 = fuel present) |
| $2C00 | Thrust lever (analogue) | NMI $7AAE |
| $2800–$2803 | DIP switches, 2 bits each | $796B |

## Fuel = credits
- Fuel is BCD at $AE:$AD:$AC. $97 bit 7 = "has fuel"; set only at $6313.
- Writers of $AD/$AE: $6313 (add) and $6461 (subtract). Nothing else.
- Callers of the add routine:
  - $62EF – **free-play DIP**: if $98 == 0, adds 900 units once per game cycle.
  - $62F8 – left coin (count $B6).
  - $6301 – right coin (count $B8), repeated $99 times (x1/x4/x5/x6 DIP).
  - $61E6 – adds 50 units inside the in-play state ($22 bit 6). Not reachable from attract and not tied to any input.
- Fuel-per-coin table $632A (index $98): 900 (free play), 450, 600, 750, 900, 1100, 1300, 1550, 1800.

## DIP decode ($796B, rev 2)
- $2803 → right coin multiplier table $799B: 1,4,5,6.
- $2802 → language; forced to English if byte at $5800 (language vector ROM) is $FF.
- $2801:$2800 → 4-bit value v; $98 = v+1, or 0 (free play) if v ≥ 8 (i.e. DIP bit 0x20).

## Rev 1 vs rev 2
- Rev 1 (llander1) has only 4 fuel settings and free play on a separate bit. Same fuel-writer structure, no extra path.
- Rev 1 Select Game routine ($62B0) does `ROL $2406` where rev 2 does `ASL $24`, so in rev 1 Select
  only registers while **rotate right is held**. It's a coding slip (absolute address instead of zero page), not a fuel path.

## Anti-tamper
- NMI at $7AE1: ($00 XOR $C1 XOR $C2) must equal $85, otherwise it spins until the watchdog resets.
