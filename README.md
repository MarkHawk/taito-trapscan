# Taito's hidden free credits: anti-bootleg traps in 1979 arcade code

*For Phil.*

In the 1980s, Bexley Squash Club had a bootleg arcade machine, and I remember someone there who could
get free games out of it with a button trick. I'd always half-assumed that was playground legend.
Forty-odd years later I went looking for it in the code.

It's real. Two Taito games from 1979, **Lunar Rescue** and **Space Invaders Part II**, contain hidden
routines that hand out free credits when you hold a secret button combination in attract mode, and
**they're designed to work only on copied boards**. On a genuine Taito machine the trap switches
itself off a few seconds after power-up. On a bootleg, it stays live.

As far as I can find, none of this has been documented before.

---

## The short version

| Game | Secret combo (attract mode) | Gives | Armed when… |
|---|---|---|---|
| **Lunar Rescue** (1979) | P1 Start + Fire + Right | 3 credits | the "© TAITO CORPORATION" text on the title screen has been altered |
| **Space Invaders Part II** (1979) | P1 Start + P2 Start + Fire + Left | 2 credits | one of two unused input lines on the board reads high (i.e. it isn't running on the expected hardware) |
| Space Invaders Part II, second trap | P1 Start + P2 Start + Fire + Right | nothing (bug) | the game's own ROM has been patched |
| Space Invaders (1978, Midway set) | none | – | no trap, just the known "TAITO COP" easter egg |
| Atari Lunar Lander (1979) | none | – | clean; checked as a control |

Combos must be exact: the other buttons have to be released, or nothing happens.

## Lunar Rescue

The game keeps its credit count in RAM at `$20EB`. Besides the normal coin and start-button code,
there's one more place that writes it, tucked into the extra ROM at `$4000`:

```
47D8  call $037C       ; read player 1 controls
47DB  ani  $76         ; keep Start1, Start2, Fire, Left, Right
47DD  cpi  $54         ; = Start1 + Fire + Right, nothing else
47DF  rnz
47E0  lxi  h,$20ED     ; the "armed" flag
47E4  mov  a,m
47E5  ana  a
47E6  rz               ; not armed -> do nothing
47E7  dcx  h
47E8  dcx  h           ; -> $20EB, the credit counter
47E9  mvi  m,$03       ; credits = 3
```

This runs on every pass of the attract-mode demo.

**What arms it:** the flag at `$20ED` is set to 1 at power-up. Each time the title screen draws
"© TAITO CORPORATION", a routine reads three bytes of screen memory *inside the letters of "TAITO"*
and compares them with what they should be. If they match, the flag is cleared and the trap is dead.

So on a genuine board, the trap disarms itself 2.6 seconds after switch-on. But if a bootlegger
changed the copyright line, which they routinely did to sell copies under another name, the check
fails, the flag stays set, and anyone who knows the combo gets free games on the bootlegger's
machine.

## Space Invaders Part II

Part II hides the same idea more carefully:

- **The credit address never appears in the code.** It's built at run time from neighbouring values
  (`MVI H,$1F / INR H` and `MVI L,$EC / DCR L` gives `$20EB`), so searching the ROM for `$20EB`
  won't find it.
- **Credits have a shadow copy** at `$20CC`. The interrupt handler compares the two every frame and
  restarts the game if they differ, so poking the credit counter in a debugger just resets the
  machine. The hidden routine writes both copies.
- **The trigger is the hardware, not the text.** At power-up the game reads two input lines that
  aren't connected to anything on the genuine board. Both low: trap disarmed. One high: trap stays
  armed. Both high: the game resets itself.
- **There's a second trap that doesn't work.** It's armed if five bytes of the program ROM have been
  changed, but it reads the controls through a helper that leaves a register pointing at ROM. Its
  "2 credits" are written into read-only memory and vanish. Whether that's a bug or a decoy, it never
  pays out.

The add-on ROM also contains a cleaned-up version of the known Space Invaders "TAITO COP" easter
egg: it now spells "TAITO CORP", and its first step no longer needs Left and Right held at once.

## It worked on real bootlegs

Scanning a full MAME 0.277 collection (144 sets) and running each Lunar Rescue copy in the emulator:

| Set | Made by | Trap as shipped |
|---|---|---|
| **Destination Earth** (`desterth`) | bootleg | **live: the combo gives 3 credits** |
| **Escape from Mars** (`escmars`) | bootleg | **live: the combo gives 3 credits** |
| Moon Lander (`mlander`) | Leisure Time Electronics (UK) | armed but blocked: patched so the controls read nothing while idle |
| Rescate Lunar (`resclunar`) | Niemer S.A. (Spain) | disabled: `RZ`→`RET` at `$47E6`, plus its own ROM checksum |
| Lunar Rescue Model Racing / Artic copies, Galaxy Rescue | various | switched off: Taito copyright left intact |

Two pirate copies paid out free games, and two other pirates found the trap and removed it.
All six Space Invaders Part II sets carry their trap too; Midway's *Space Invaders Deluxe* even updated one check to
match its own changes. Full details: [docs/bootleg-results.md](docs/bootleg-results.md).

## So what was going on at the squash club?

If the machine was a Lunar Rescue copy with the Taito name changed — *Destination Earth* or *Escape from
Mars*, say — holding the combo during the attract demo gave free credits, exactly as described above. I can't
know which board it was, but the memory fits the code, and those copies were real.

## Was this Taito policy?

On the evidence so far, it was a 1979–80 tactic:

- The original 1978 **Space Invaders** has no trap, only an easter egg.
- Both 1979 games put the trap in the **add-on ROM at `$4000`**, and tie it to an anti-copy check.
  That was the moment bootleg Invaders hardware was everywhere.
- Through the 1980s Taito moved to **hardware protection**: custom microcontrollers the game can't run
  without. Hiding traps in the code mattered less once copiers had to beat a chip.

Since checked: Balloon Bomber, Lupin III, Polaris, Space Chaser, Indian Battle and Steel Worker (no trap), and
the Z80 games that followed — Crazy Balloon, Space Cruiser, Space Seeker, Alpine Ski, Wild Western, Jungle King,
Front Line, Elevator Action (no trap). The Elevator Action bootleg had to patch nine places to run without
Taito's 68705 protection chip: by 1983 the protection lived in hardware.

## How it was found

1. Disassembled the program ROMs: 6502 for Lunar Lander, Intel 8080 for the Taito games.
2. Found the credit counter from the coin routine, then traced **every** instruction that writes it.
   Anything other than "coin in" and "start pressed" is suspicious.
3. Ran the ROMs in a purpose-built 8080 emulator of the Space Invaders board, held the combos, and
   simulated a bootleg by altering one letter of "TAITO". The credits appeared; on the unmodified ROM
   they don't.
4. Turned the patterns into a scanner, which finds every hidden routine above and, on the original
   Space Invaders, only the known easter egg.

## Try it yourself

This repo contains the tools: a disassembler, a signature scanner and an emulator, pure Python 3.
ROMs are not included; use your own MAME sets.

```bash
python3 trapscan.py scan lrescue.zip invadpt2.zip     # report + disassembly
python3 trapscan.py run lrescue.zip --frames 1720 --patch 4676=13 \
    --hold start1+fire+right@1600-1700 --watch 20eb     # bootleg simulation -> credits 03
```

In MAME's debugger:

- **Lunar Rescue:** after **both** title screens (~10 s from power-on), enter `b@20ed=1`, then hold
  P1 Start + Fire + Right once the demo starts.
- **Space Invaders Part II:** in attract mode, enter `b@20e3=1` and hold P1 Start + P2 Start + Fire + Left.

Scan a whole folder of sets into one report (suspicious sets listed first):

```bash
python3 batch.py ~/roms -o report.md
```

Full instructions: [docs/USAGE.md](docs/USAGE.md). Sets worth collecting: [docs/ROMLIST.md](docs/ROMLIST.md). Detailed notes with addresses:

- [docs/lunar-rescue.md](docs/lunar-rescue.md)
- [docs/space-invaders-part-ii.md](docs/space-invaders-part-ii.md)
- [docs/lunar-lander-clean.md](docs/lunar-lander-clean.md)

## Caveats

- Confirmed by disassembly and emulation, **not yet on real hardware**.
- Z80 games are scanned statically (no Z80 emulator yet).
- Which real boards had the Part II input lines high is unknown. MAME leaves them low, so the trap is
  off there unless you poke the flag.
- "Right" means bit 6 of input port 1, the standard Space Invaders wiring.
- "Not documented before" means I couldn't find it online, in TCRF, Computer Archeology or the arcade
  history databases. If you know otherwise, open an issue; I'd love to hear it.

## References

- [The Cutting Room Floor: Space Invaders (Arcade)](https://new.tcrf.net/Space_Invaders_(Arcade)), the "TAITO COP" easter egg
- [Computer Archeology: Space Invaders](https://www.computerarcheology.com/Arcade/SpaceInvaders/), hardware and original code
- [arcade-history.com: Lunar Rescue](https://www.arcade-history.com/game/1418/)
- [MAME machine data: Space Invaders Part II](https://data.spludlow.co.uk/mame/machine/invadpt2)
- [List of Taito games (Wikipedia)](https://en.wikipedia.org/wiki/List_of_Taito_games)

*Mark Hawkings, Bexley, 2026.*
