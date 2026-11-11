# Lunar Rescue (Taito, 1979) – hidden credit routine

ROM map: lrescue.1–.4 at $0000–$1FFF, lrescue.5–.6 at $4000–$4FFF. 8080 CPU, Space Invaders-style I/O.
Work RAM $2000–$23FF, video RAM $2400–$3FFF.

## Credits
- Credit count: **$20EB** (BCD, capped at 9).
- Normal writers: coin in the interrupt routine ($0038), coin while music plays ($4DA9),
  start deducts 1 or 2 ($00B2), RAM init at reset (from ROM table $1AA3).
- **Hidden writer: $47E9**, which sets credits to **3**.

## The routine ($47D8)
```
47D8  call $037C        ; read player-1 controls (port 1)
47DB  ani  $76          ; keep bits 1,2,4,5,6
47DE  cpi  $54          ; need: Start1(b2) + Fire(b4) + Right(b6), with Left(b5) and Start2(b1) released
47DF  rnz
47E0  lxi  h,$20ED      ; "armed" flag
47E4  mov  a,m / ana a
47E6  rz                ; not armed -> do nothing
47E7  dcx h / dcx h     ; -> $20EB credits
47E9  mvi  m,$03        ; credits = 3
```
Called once per loop from the attract-mode demo loop ($474E–$478F, call at $4760).

## The arming condition ($4686)
- $20ED is set to 1 at power-up (RAM init table).
- Each time a title screen draws "© TAITO CORPORATION", $4686 checks three bytes of
  screen memory inside the word "TAITO" ($2B47=$7F, $2C47=$44, $2E27=$40).
  If they match, $20ED is cleared and the routine is dead.
- So the combo only works if the copyright line has been **changed** (e.g. a bootleg relabelled
  with another company's name). On a genuine board it never fires.
- A second check at $46A0 (called from $43D0 during play) sums another column of that text
  and diverts to $0362 if it's wrong. This looks like more anti-bootleg logic.

## Emulator results (custom 8080 emulator, inputs held for ~100 frames during the attract demo)
| ROM | Inputs held | Result |
|---|---|---|
| Genuine | Start1 + Fire + Right | nothing; flag cleared at frame 156 |
| One "TAITO" letter altered | Start1 + Fire + Right | credits set to 3, the held Start then starts a game → 2 left |
| Altered | Start1+Right, Fire+Right, Start1+Fire | nothing |
| Altered | combo + Left, or combo + Start2 | nothing (they must be released) |

## Try it in MAME
1. Debugger: `bpset 47e9` – genuine set never hits it.
2. Simulate the bootleg: the copyright check runs on **both** title screens (frames ~156 and ~496),
   so set `b@20ed=1` after the second one (~10 s from power-on). When the attract demo starts
   (~27 s), hold P1 Start + Fire + Right. Credits jump to 3.
3. Or with trapscan: `python3 trapscan.py run lrescue.zip --poke 20ed=1@600 --hold start1+fire+right@1600-1700 --watch 20eb`
