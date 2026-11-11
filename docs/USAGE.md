# trapscan

Tools for finding hidden credit routines ("free-play backdoors") in 8080 Space Invaders-family
arcade ROMs: Taito, Midway and their bootlegs, 1978–81.

They came out of reverse-engineering two 1979 Taito games, where both turned out to contain
anti-bootleg traps that hand out credits on a secret button combination: see the main README.

Pure Python 3 (3.8+). No dependencies, except Pillow if you want screenshots (`pip install pillow`).

## Quick start

```bash
# Scan one set, or a whole folder of MAME zips
python3 trapscan.py scan lrescue.zip
python3 trapscan.py scan ~/roms/*.zip

# Run a set in the emulator, hold buttons, poke RAM, watch bytes, count executions
python3 trapscan.py run lrescue.zip --frames 1720 \
    --poke 20ed=1@600 --hold start1+fire+right@1600-1700 \
    --watch 20eb --break 47e9 --shot 150
```

`scan` prints a report and writes a full disassembly to `out/<set>.asm`.

## Batch: a whole folder into one report

```bash
python3 batch.py ~/roms                    # writes report.md and out/<set>.asm
python3 batch.py ~/roms -o taito.md --no-asm
```

Every `.zip` (or folder) is a set; merged zips also yield each clone inside them. Sets are ranked SUSPICIOUS → CHECK →
EASTER EGG? → CLEAN → OTHER HW? → ERROR. A set that fails to load is reported and skipped.
Which sets to collect: [ROMLIST.md](ROMLIST.md).

## Search a whole MAME collection for the trap code

```bash
python3 sigsearch.py /path/to/mame/roms -o sigsearch.csv
```

Byte-searches every zip (clone folders included) for the exact trap routines, their arming checks, a
relocated/edited version of each, and any `ANI $76` combo check. It doesn't need to lay out or run anything,
so it covers games on any board. Zips over 4 MB are skipped (`--max-zip-mb` to change).

### Big collections: skip what's out of scope

A full modern MAME set is mostly hardware this search isn't aimed at. `sigsearch.py` takes:

- `--max-zip-mb 1`: 1978–84 sets are small, so this skips most later games without reading them (default 4);
- `--skip-nonarcade`: skip fruit machines (Barcrest MPU, JPM, Maygay, BFM Scorpion, Astra), video poker,
  PlayChoice-10, Mega-Tech and Game & Watch sets, by name prefix;
- `--skip a,b,c`: your own extra prefixes.

On a 13,000-zip MAME 0.277 set, `--max-zip-mb 1 --skip-nonarcade` cuts a run to a fraction of the time. Big merged golden-age sets (Galaxian, Pac-Man with all their clones) can be over 1 MB; run those on
their own if so.

## Merged ROM sets and clones

Merged MAME sets keep each clone's differing ROMs in a sub-folder of the parent zip (e.g. `lrescue.zip` →
`desterth/…`). trapscan expands every clone automatically and places each clone ROM by **matching its content**
against the parent (or a sibling set, when the clone shares files with it). Bootleg ROMs typically match at 90–100%;
ROMs with no counterpart (extra code) go in the next free slot. Pick one clone with `--set`:

```bash
python3 trapscan.py scan lrescue.zip --set desterth
python3 trapscan.py run lrescue.zip --set desterth --hold start1+fire+right@1000-2500 --watch 20eb
```

Unknown parents are laid out by **self-location**: each ROM's own jump/call targets show where it loads.

## Z80 mode (Taito SJ System, Crazy Balloon)

Sets with 4 KB/8 KB ROMs are detected automatically. Main-CPU ROMs are separated from sound and graphics ROMs,
banked ROMs at $6000–$7FFF are scanned as bank 0 and bank 1, and inputs are read from $D400–$D40F. Disassembly
needs `py -m pip install z80dis`. There's no Z80 emulator, so `run` is 8080-only.

## Boot check

`batch.py` runs each 8080 set for 4 seconds and reports **Boots**. Some boards check input port 0 at power-up, so it
tries several values and notes the one that worked (Galaxy Wars needs `$40`, Lupin III `$03`, the TV-version Space
Invaders `$01`). Pass the same with `run --port0`.

## What `scan` looks for

| Tag | Meaning | Why it matters |
|---|---|---|
| `COMBO` | Controls read, then `ANI mask / CPI value` with 3+ buttons | One exact button combination. "then MVI M,.." means it writes RAM straight after – **look here first** |
| `CREDIT` | Direct writes to the credit counter (found automatically from the coin routine) | Normal: coin + start. Anything else is interesting |
| `POINTER` | An address built at run time (`MVI L,$EA / INR L` = $EB) | Used to hide credit writes from anyone searching for `$20EB` |
| `SHADOW` | Interrupt code comparing credits with a second copy, restarting on mismatch | Stops simple RAM pokes |
| `VRAMCMP` | Screen memory compared with constants | Copyright-text check (Lunar Rescue arms its trap this way) |
| `ROMCMP` | ROM bytes compared with constants | Patch detection |
| `RESET` | Input read, then jump to $0000/$0003 | Board/hardware checks |

Hits are leads, not proof. Confirm in the `.asm`, then in the emulator.

## ROM layouts

Known sets (`invaders`, `invadpt2`, `lrescue`) load with exact MAME layouts. Anything else gets a
**heuristic** layout: 2 KB files are program ROMs, the one that looks like a reset ROM goes to $0000,
four fill $0000–$1FFF, and the rest go to $4000+. The layout is always printed. If it's wrong, override it:

```bash
python3 trapscan.py scan ballbomb.zip --map 0000=tn01 0800=tn02 1000=tn03 1800=tn04 4000=tn05-1
```

(MAME's `-listroms <set>` or the driver source gives the real addresses.)

## The `run` command

| Option | Example | |
|---|---|---|
| `--frames` | `1800` | 60 frames = 1 second |
| `--hold` | `start1+fire+right@1600-1700` | Buttons: coin, start1, start2, fire, left, right, or `0xNN` |
| `--poke` | `20ed=1@600` | Write RAM at a frame |
| `--patch` | `4676=13` | Change a ROM byte before starting (simulate a bootleg) |
| `--watch` | `20eb` | Print whenever the byte changes |
| `--break` | `47e9` | Count executions of an address |
| `--shot` | `150` | Screenshot at a frame (Pillow) |
| `--port0/--port2` | `02` | Raw input values (DIPs, odd wiring) |

Hardware model: 8080 at ~2 MHz, RST 1 mid-frame and RST 2 at vblank, shift register on
ports 2/4 → 3, RAM $2000–$3FFF. Games that use different I/O will scan fine but may not run correctly.

## Reproducing the findings

```bash
# Lunar Rescue: arm the trap (normally cleared by the copyright check), hold the combo in the demo
python3 trapscan.py run lrescue.zip --frames 1720 --poke 20ed=1@600 \
    --hold start1+fire+right@1600-1700 --watch 20eb --break 47e9
#   -> credits 03 at frame 1600 (then 02 as the held Start begins a game)

# Same, as a bootleg would: alter one letter of "TAITO" so the check never disarms it
python3 trapscan.py run lrescue.zip --frames 1720 --patch 4676=13 \
    --hold start1+fire+right@1600-1700 --watch 20eb

# Space Invaders Part II: one port-0 line high arms the trap
python3 trapscan.py run invadpt2.zip --frames 400 --port0 02 \
    --hold start1+start2+fire+left@200-260 --watch 20eb --watch 20cc --break 419d
#   -> credits 02 at frame 233 (the held 2P Start may then spend them)
```

In MAME instead: open the debugger. For Lunar Rescue, after **both** title screens (~10 s from
power-on) do `b@20ed=1`, then hold P1 Start + Fire + Right once the demo is running. For Part II,
the board check clears the flag again and again in attract mode, so set it as the trap reads it:
`bpset 418c,1,{b@20e3=1;g}`, reset, and hold P1 Start + P2 Start + Fire + Left from power-on.

## Files

```
trapscan.py            command line
trapscan/disasm.py     8080 disassembler
trapscan/scanner.py    signature scanner
trapscan/emu8080.py    8080 CPU + Invaders-family board model
trapscan/romload.py    zip/folder loading, known layouts, heuristic layout
trapscan/audit.py      credit counter from a coin test; every instruction that can write it
trapscan/boards.py     other board models (Space Stranger)
trapscan/z80mode.py    Z80 detection, layout and static scan (Taito SJ, Crazy Balloon)
trapscan/skiplist.py   name prefixes for --skip-nonarcade
batch.py               folder -> one Markdown report
sigsearch.py           byte-search a whole collection for the trap code
scripts/eggdemo.py     trigger TAITO COP / HOEI COP and save a screenshot
docs/                  write-ups and this guide
```

ROMs are not included. Use your own dumps.
