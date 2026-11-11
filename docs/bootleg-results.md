# Results across a full MAME 0.277 collection (144 sets)

Scanned with `batch.py` (merged zips expanded; clone ROMs placed by matching the parent's code).

## Lunar Rescue family (trap at $47D8, armed unless "© TAITO CORPORATION" is intact)

| Set | Maker | Trap status as shipped | Combo in attract (P1 Start + Fire + Right) |
|---|---|---|---|
| `lrescue` | Taito | disarmed at frame 156 (copyright intact) | nothing |
| `grescue` Galaxy Rescue | Taito (licence) | disarmed (copyright intact; only 12 bytes differ: title text) | nothing |
| `lrescueabl` | Artic bootleg | disarmed (copyright intact) | nothing |
| `lrescuem`, `lrescuem2` | Model Racing bootlegs | disarmed (copyright intact) | nothing |
| **`desterth`** Destination Earth | bootleg | **armed** | **3 credits** |
| **`escmars`** Escape from Mars | bootleg | **armed** | **3 credits** |
| `mlander` Moon Lander | Leisure Time Electronics (UK) bootleg | armed, but **patched out**: controls read as 0 outside a game ($0A48 → new code at $0D2C) | nothing |
| `resclunar` Rescate Lunar | Niemer S.A. (Spain) bootleg | **patched out**: `RZ`→`RET` at $47E6; also adds its own ROM checksum at $5040 that crashes the machine if altered | nothing |

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
- **Elevator Action bootleg** (`elevatorb`, runs without the 68705 MCU): 64 bytes patched in 9 places – checks on
  MCU-supplied values NOPped or forced, a check routine made to return 0, an MCU-computed value hard-coded
  ($8648 = $59), two table lookups redirected to the bootleg's own ROM bank. Protection had moved into hardware.

## Not analysable here

`sflush` (6800 CPU), `shuttlei`, `skylove` (Omori boards), `gunchamps`, `attackfc` (encrypted) / `attackfcu`
(different board), `starw1` (Galaxy Wars bootleg, layout unresolved).
