# Space Invaders Part II (Taito, 1979, MAME `invadpt2`) – hidden routines

ROMs: pv01–pv04 at $0000–$1FFF, pv05 at $4000–$47FF. Same 8080 hardware family as Lunar Rescue.
Controls are read through $1F49, which jumps via `PCHL` to $15E8 (port 1 for P1, port 2 for P2).
Bits used below (port 1): b1 Start2, b2 Start1, b4 Fire, b5 Left, b6 Right.

## Credits are guarded
- Credits: $20EB (BCD). Shadow copy: **$20CC**.
- The interrupt handler at $0094 compares the two copies and jumps to $0003 (restart) if they differ,
  so simply poking $20EB resets the game. Both hidden routines write both copies.
- Neither hidden routine has "$20EB" in its code: it's built at run time (`MVI L,$EA / INR L`,
  `MVI H,$1F / INR H / MVI L,$EC / DCR L`).

## Trap 1 – works: Start1 + Start2 + Fire + Left, attract mode ($418F)
```
4186  mvi  h,$1F
4188  mvi  l,$E4
418A  inr  h
418B  dcr  l           ; HL = $20E3 (arming flag)
418C  mov  a,m
418D  ana  a
418E  rz
418F  call $1F49       ; read player 1 controls
4192  ani  $76
4194  cpi  $36         ; Start1+Start2+Fire+Left, Right released
4196  rnz
4197  mvi  l,$EC
4199  dcr  l
419A  mvi  h,$1F
419C  inr  h           ; HL = $20EB
419D  mvi  m,$02       ; credits = 2
419F  mvi  l,$CC
41A1  mvi  m,$02       ; shadow = 2
```
**Arming flag $20E3:** set to 1 at power-up. At $459C (called from $1F53 in attract):
```
459C  in   0
459E  ani  $0A
45A0  cpi  $0A
45A2  jz   $0000       ; port 0 bits 1 AND 3 high -> reset the machine
45A5  ana  a
45A6  nop
45A7  rnz              ; exactly one high -> stay armed
45A8  lxi  h,$20E3
45AB  mvi  m,$00       ; both low -> clear $20E3: disarm
45AD  ret
```
MAME's driver notes (from Taito's schematic) say port 0 bits 1 and 3 are **tied low** on Taito's board, while
bits 2, 4, 5 and 7 are pulled high through 1k resistors. MAME reads them as 0, so the trap disarms at frame 18
(and the check keeps running through attract mode, clearing it again).
On a board where one of them reads high (one ground link missing or wired differently), it stays live; with
both high (both links missing: unconnected TTL inputs usually read high), the game resets. Whether Taito's ground
links were hidden or ordinary tracks is unknown – a question for owners of real boards.

**Taito's schematic (PV070010 I/O board, "P.T-GAME P.C. BOARD", PVN00004; from
[robotron-2084.co.uk](https://www.robotron-2084.co.uk/hardware/boardset/taito-space-invaders-part-ii-3-layer-board-stack)):** the CPU reads ports 0–2 through
four 74LS153s (positions 4, 5, 9, 10; selected by A8/A9). Port 0 is input C0 of each. Every unused C0 input has a
1k pull-up to +5V; pin 10 (2C0) of **chip 4** and **chip 9** also has a ground symbol on the same node, so those two
read low. That's port 0 bits 1 and 3 – the pair the trap checks. Chip 9's ground link also takes in pin 11 (2C1),
port 1 bit 3, which MAME likewise notes as tied low. The schematic draws them as plain ground connections; whether
the copper link is visible on the board (or under the chip) needs a look at the solder side around chips 4 and 9.

Prior knowledge: the reset was identified in 2022 on the Arcade Museum forum (thread "Taito 3 board space invaders
part 2 bad shifter causes resets?"), described as a guard against swapping Part II ROMs into a Space Invaders board,
with the fix "NOP out the jp nz,$0000" (it's `JZ $0000` at $45A2 here). The lines are input 0 (pin 10) of the
74LS153s at 6A/6B on the sound board; one owner's Moon Base Zeta board has them wired straight to pin 8 (GND).
The thread doesn't mention the one-line-high case that arms the credit trap.

**Emulator result:** with port 0 = $02 and the combo held during attract → credits 2, game starts.
Genuine port values → nothing.

## Trap 2 – dead: Start1 + Start2 + Fire + Right ($0A2D)
- Arming flag $20E2, cleared at $454F if five ROM bytes at $174C–$1750 are intact
  (D6 DB D0 C8 DB). Patch them and the flag stays set.
- Combo check: `call $1F49 / ani $76 / cpi $56`.
- **Bug:** $1F49 returns with H = $15, and this routine never reloads H, so its "credit" stores hit
  $15EB/$15CC – ROM – and do nothing. Confirmed in the emulator: the store executes, credits stay 0.

## Also in the extra ROM (not credit-related)
- **"TAITO CORP" easter egg ($4519):** hold Start2 + Fire + Right, then Start1 + Fire + Left → prints
  an encoded "TAITO CORP" string (stored at $0D6F, each byte +$3F).
- **PRESET MODE ($45B9):** opened at game start when DIP IN2 bit 3 is on (MAME: "Preset Mode: Name Entry").
  Fire or Start1 leaves it, Start2 steps a counter, Left/Right toggle a setting at $20E4.

## Try it in MAME
1. `bpset 419d` – never hit on a normal run.
2. The board check ($459C) clears $20E3 again and again in attract mode, so a one-off `b@20e3=1` doesn't stick.
   Set it at the moment the trap reads it instead: `bpset 418c,1,{b@20e3=1;g}`.
3. Reset and hold P1 Start + P2 Start + Fire + Left from power-on. The trap runs once per attract cycle, about
   4 seconds in (frame 233): credits go to 2 (both $20EB and $20CC), and the held Start begins a game.
