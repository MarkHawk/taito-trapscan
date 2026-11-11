# Results across a full MAME 0.277 collection (149 sets)

Scanned with `batch.py` (merged zips expanded; clone ROMs placed by matching the parent's code).

## Lunar Rescue family (trap at $47D8, armed unless "© TAITO CORPORATION" is intact)

| Set | Maker | Trap status as shipped | Combo in attract (P1 Start + Fire + Right) |
|---|---|---|---|
| `lrescue` | Taito | disarmed at frame 156 (copyright intact) | nothing |
| `grescue` Galaxy Rescue | Taito (licence) | disarmed (copyright intact; only 12 bytes differ: the title and score-header text) | nothing |
| `lrescueabl` | Artic bootleg | disarmed (copyright intact) | nothing |
| `lrescuem`, `lrescuem2` | Model Racing bootlegs | disarmed (copyright intact) | nothing |
| **`desterth`** Destination Earth | bootleg | **armed** | **3 credits** |
| **`escmars`** Escape from Mars | bootleg | **armed** | **3 credits** |
| **`mlandera`** Moon Lander, set 2 | Leisure Time Electronics (UK) bootleg | **armed** (copyright changed) | **3 credits** |
| `mlander` Moon Lander, set 1 | Leisure Time Electronics (UK) bootleg | armed, but **blocked**: controls read as 0 while no game is running ($0A48 → new code at $0D2C), so the combo can't register | nothing |
| `resclunar` Rescate Lunar | Niemer S.A. (Spain) bootleg | **patched out**: `RZ`→`RET` at $47E6; also adds its own ROM checksum at $5040 that crashes the machine if altered | nothing |

The two Moon Lander sets differ by 25 bytes, all of them the idle-controls check that set 1 adds: `MVI A,1 / STA $20EF`
at game start ($0662), `CALL $425B` → `XRA A / STA $20EF` when the game ends ($46B5), and the player-1 input read at
$0A48 redirected to `LDA $20EF / ORA A / RZ / IN 1 / RET` ($0D2C). Set 2 (`mlandera`, ROM 5 labelled "rev d") has
none of it, so its trap pays out. Which set came first, and whether the check was added to stop the trick, is not
known.

## Space Invaders Part II family (trap 1 at $418F, armed by port-0 board check; trap 2 at $0A2D is broken)

All six sets (`invadpt2`, `invadpt2a`, `invadpt2br`, `invaddlx`, `moonbase`, `moonbasea`) carry the shadow
credit copy, the board check, the ROM check and both traps.

- `invaddlx` (Midway licence) changed the checked ROM bytes **and updated the check's constants** to match.
- `moonbase` (Nichibutsu) changed the checked bytes without updating the check, so trap 2 arms and its combo
  is accepted – but trap 2's bug writes the credits into ROM, so nothing pays out.

## Other findings

- **Rolling Crash** (Nichibutsu) is built on Taito's Space Invaders code and keeps the "TAITO COP" easter egg. Clean.
- **Galaxy Wars** (Universal) resets itself at power-up unless input port 0 reads exactly $40 – a board check.
- **Z80 era** (Crazy Balloon, Space Cruiser, Space Seeker, Alpine Ski, Wild Western, Jungle King/Hunt + clones,
  Front Line, Elevator Action): no button-combo credit traps in any of 21 sets.
- **Elevator Action bootleg** (`elevatorb`, runs without the 68705 MCU): 64 bytes patched in 9 places – checks
  NOPped or forced, a check routine made to return 0, a computed value hard-coded ($8648 = $59), two table lookups
  redirected to the bootleg's own ROM bank. These look like the places the game relies on the chip (not confirmed
  by emulation – there's no Z80/68705 emulator here). Protection had moved into hardware.

## Not analysable here

`sflush` (6800 CPU), `shuttlei`, `skylove` (Omori boards), `gunchamps`, `attackfc` (encrypted) / `attackfcu`
(different board), `starw1` (Galaxy Wars bootleg, layout unresolved).

## Credit-writer audit (8080 games)

Credit counter found by inserting coins in the emulator; then every instruction that can write it traced,
including disguised and offset pointers (`trapscan/audit.py`).

| Game | Writers of the credit counter | Verdict |
|---|---|---|
| Lunar Rescue + clones | coin ($0038), coin during music ($4DA9), start ($00B2), **trap $47E9** | trap |
| Space Invaders Part II, Deluxe, Moon Base | coin ($0038), start ($0889), **trap $419D** (trap 2 writes ROM, not credits) | trap |
| Space Invaders (all Taito revisions) | coin, start | clean |
| Space Chaser (all sets) | coin ($13D0, via pointer), start ($1459) | clean |
| Balloon Bomber, Lupin III, Polaris, Indian Battle, Steel Worker | coin, start | clean |
| Galactica (Taito do Brasil) | its own coin routine ($4E48), 1P start ($0869), 2P start ($080A) | clean |
| Cosmic Battle (`cosmicbat`, Recreativos Franco bootleg of Space Invaders) | coin ($0038, via its own coinage code at $0BFE), 50p coin chute ($10AF), start ($07A3) | clean |
| Space Invaders SV rev 3 (`sisv3`) | coin, start (same writers as `invaders`) | clean |
| Moon Raker (`mraker`, Nichibutsu) | coin ($00DD), start 1P/2P ($0C11, $0C2D, $0C49) | clean |
| Ozma Wars (`ozmawars`, `ozmawars3`) | coin ($02E8), 2P start ($03AC), 1P start ($04B3) | clean |

Writers are followed down both sides of every branch and through jumps; the method finds all four Lunar Rescue
writers (including the trap) without being told where they are.

Destination Earth replaces the coin check in the interrupt routine with a call to its own code at $5080: it reads
a coin input on port 1 bit 7 and adds **3 or 6 credits per coin**, chosen by a DIP switch (port 2 bit 7)
($50A7; the same code appears again at $54A7). A pirate coinage change, not a trap. Not covered: Straight Flush (6800 CPU) and the Z80 games (no emulator, so no
coin test – static combo search only).
