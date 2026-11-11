# ROM sets in scope

Every set on MAME's **`midw8080/8080bw.cpp`** driver (the Taito/clone side of the 8080 Space Invaders
board family; 135 sets as of MAME 0.289), plus the Midway Invaders sets on `mw8080bw.cpp`, plus the
first Taito games after the hardware changed. Set names are MAME short names; keep clone zips next to
their parent zip.

Generate/verify against your own MAME:

```bash
mame -listsource | awk '$2 ~ /8080bw\.cpp/ {print $1}' > sets.txt
mame -listfull $(cat sets.txt) > titles.txt
```

Legend: ★ = top priority.

---

## 1. Taito genuine (and Taito-licensed), 8080 board

### Space Invaders (1978–79), the baseline

| Set | Title | Notes |
|---|---|---|
| `sisv`, `sisv1`, `sisv2`, `sisv3` | Space Invaders (SV Version rev 4, 1, 2, 3) | Taito |
| `sitv`, `sitv1` | Space Invaders (TV Version rev 2, 1) | Taito; has service mode |
| `sicv`, `sicv1` | Space Invaders (CV Version, larger/smaller ROMs) | Taito, 1979 colour |
| `invaders` | Space Invaders (Midway) | **mw8080bw.cpp**; already scanned: easter egg only |
| `invaderl` | Space Invaders (Logitec) | Taito / Logitec |
| `invadrmr` | Space Invaders (Model Racing) | Taito / Model Racing |
| `spceking` | Space King | Taito / Leijac |
| `spcewars` | Space War (Sanritsu) | Taito / Sanritsu |
| `sinvzen` | Super Invaders (Zenitone-Microsec) | Taito / Zenitone |
| `ultrainv` | Ultra Invaders (1980) | Taito / Konami |
| `jspecter`, `jspecter2` | Jatre Specter (sets 1, 2) | Taito / Jatre, 1979 |

### Space Invaders Part II (1979) ★

| Set | Title | Notes |
|---|---|---|
| `invadpt2` | Part II (Taito, bigger ROMs) | already scanned: **2-credit trap** |
| `invadpt2a` ★ | Part II (Taito, smaller ROMs) | other ROM layout: same trap? |
| `invadpt2br` ★ | Part II (Brazil) | Taito do Brasil |
| `invaddlx` ★ | Space Invaders Deluxe (1980) | Midway licence: does Midway's wiring arm it? |
| `invad2ct` ★ | Space Invaders II (Midway cocktail) | **mw8080bw.cpp** |
| `moonbase`, `moonbasea` ★ | Moon Base Zeta (sets 1, 2) | Taito / Nichibutsu, 1979 |

### Lunar Rescue (1979) ★

| Set | Title | Notes |
|---|---|---|
| `lrescue` | Lunar Rescue | already scanned: **3-credit trap** |
| `grescue` ★ | Galaxy Rescue | "Taito (Universal licence?)": tested – Taito copyright intact, trap switched off |

### Other Taito 8080 games, 1979–80 ★

| Set | Title | Year |
|---|---|---|
| `schaser`, `schasera`, `schaserb`, `schaserc` | Space Chaser (sets 1–4) | 1979 |
| `schasercv` | Space Chaser (CV version) | 1979 |
| `sflush` | Straight Flush | 1979 |
| `ballbomb` | Balloon Bomber | 1980 |
| `steelwkr` | Steel Worker | 1980 |
| `lupin3`, `lupin3a` | Lupin III (sets 1, 2) | 1980 |
| `polaris`, `polariso`, `polarisa`, `polarisb` | Polaris (latest, original, 2nd rev, 1st rev) | 1980 |
| `polarisbr` | Polaris (Brazil) | 1981, Taito do Brasil |
| `indianbt` | Indian Battle | 1980 |
| `indianbtbr` | Indian Battle (Brazil) | 1983, Taito do Brasil |
| `galactic` | Galactica – Batalha Espacial | 1980?, Taito do Brasil |
| `galxwarst`, `galxwarst2` | Galaxy Wars (Taito versions) | 1979, Universal/Taito |
| `spclaser` | Space Laser | 1980, Konami (Taito licence) |

Revisions matter: if a trap appears or disappears between `polariso` → `polarisb` → `polarisa` →
`polaris`, that dates the practice.

---

## 2. Bootlegs, 8080 board

These are what the traps were aimed at. If a bootleg altered the checked text or hardware, the trap
may simply **work** in MAME with no poking.

### Of Lunar Rescue ★ (all eight)

| Set | Title |
|---|---|
| `desterth` | Destination Earth |
| `escmars` | Escape from Mars (1980) |
| `lrescueabl` | Lunar Rescue (Artic bootleg) |
| `lrescuem`, `lrescuem2` | Lunar Rescue (Model Racing bootleg, sets 1, 2) |
| `mlander`, `mlandera` | Moon Lander (Leisure Time Electronics, sets 1, 2) |
| `resclunar` | Rescate Lunar (Niemer S.A., Spain) |

### Of Space Invaders

| Set | Title |
|---|---|
| `cosmicbat` | Cosmic Battle (Recreativos Franco) |
| `cosmicin` | Cosmic Invaders |
| `cosmicmo`, `cosmicm2` | Cosmic Monsters, Cosmic Monsters 2 (Universal) |
| `darthvdr` | Darth Vader |
| `galmonst` | Galaxy Monsters (Laguna S.A.) |
| `invadersem` | Space Invaders (Electromar) |
| `invadernc` | Space Invaders (Nas Corp) |
| `spaceatt`, `spaceatt2k`, `spaceattbp` | Space Attack (three sets) |
| `spaceat2` | Space Attack II (of Super Invaders) |
| `invader4` | Space Invaders Part Four (of Space Attack II) |
| `spcebttl` | Space Battle |
| `spacecom` | Space Combat |
| `spacerng` | Space Ranger (Leisure Time Electronics) |
| `swipeout` | Space Wipeout (Beyer and Brown) |
| `spacewr3` | Space War Part 3 |
| `spcewarl`, `spcewarla` | Space War (Leijac licence; Leisure and Allied bootleg) |
| `spacmiss` | Space Missile |
| `superinv` | Super Invaders (bootleg set 1) |
| `sinvemag`, `sinvemag2` | Super Invaders (Emag sets 1, 2) |
| `supinvsion` | Super Invasion (Electromar/Irecsa) |
| `searthin`, `searthina`, `searthie`, `searthinc` | Super Earth Invasion (sets 1–3, Centromatic) |
| `alieninv`, `alieninvp2` | Alien Invasion, Alien Invasion Part II |
| `invasion` | Invasion (Sidam) |
| `invasionb` | Invasion (Italian bootleg) |
| `invasionrz`, `invasionrza` | Invasion (R Z SRL Bologna, sets 1, 2) |
| `invasiona`, `invasiona2` | UFO Robot Attack (newer, older) |

### Of Space Chaser

| Set | Title |
|---|---|
| `crashrd` | Crash Road (Centromatic) |
| `schaserm` | Space Chaser (Model Racing bootleg) |

### Of other games

| Set | Title |
|---|---|
| `starw`, `starw1` | Star Wars (bootlegs of Galaxy Wars) |
| `solfight` | Solar Fight (of Ozma Wars) |
| `spaceph` | Space Phantoms (of Ozma Wars, Zilec) |
| `ozmawarsmr` | Ozma Wars (Model Racing bootleg) |
| `laser` | Astro Laser (of Space Laser) |

---

## 3. Other manufacturers on the same board

Not Taito code; a hit here would mean the idea spread.

| Set | Title | Maker |
|---|---|---|
| `galxwars`, `galxwars2` | Galaxy Wars | Universal |
| `ozmawars`, `ozmawars2`, `ozmawars3` | Ozma Wars | SNK |
| `rollingc` | Rolling Crash / Moon Base | Nichibutsu |
| `mraker` | Moon Raker | Nichibutsu |
| `shuttlei`, `skylove` | Shuttle Invader, Sky Love | Omori |
| `yosakdon`, `yosakdona` | Yosaku to Donbei | Wing |
| `invrvnge`, `invrvngea`, `invrvngeb`, `invrvngedu`, `invrvngegw` | Invader's Revenge | Zenitone-Microsec |
| `intruder` | Intruder | Konami / Game Plan |
| `vortex` | Vortex | Zilec |
| `astropal` | Astropal | Sidam? |
| `cosmo` | Cosmo | TDS & MINTS |
| `attackfc`, `attackfcu` | Attack Force (encrypted / unencrypted) | Electronic Games Systems |
| `claybust`, `gunchamp`, `cane`, `orbite` | Claybuster, Gun Champ, Cane, Orbite | Model Racing |

**Out of scope:** `invmulti` and its 10 variants (2002 multigame hacks), `tst_invd` (test ROM).

---

## 4. After the architecture changed: "did they add extra insurance?"

Taito's last 8080-board games were Polaris (July 1980) and Indian Battle (Oct 1980). Crazy Balloon
(March 1980) was already on its own Z80 board, and from 1981 Taito moved to the Z80-based
**Taito SJ System**, which later added a **68705 microcontroller "used for protection"**.

The first five on the new hardware, plus the first with the protection chip:

| # | Set(s) | Title | Date | Hardware | Why look |
|---|---|---|---|---|---|
| 1 | `crbaloon`, `crbaloon2` | Crazy Balloon | Mar 1980 | Z80, own board | First Taito game off the Invaders board |
| 2 | `spacecr` | Space Cruiser | Sep 1981 | Taito SJ | First SJ games: did the software traps move across? |
| 3 | `spaceskr` | Space Seeker | Sep 1981 | Taito SJ | |
| 4 | `alpine`, `alpinea` | Alpine Ski | Jan 1982 | Taito SJ | |
| 5 | `wwestern`, `wwestern1` | Wild Western | Apr 1982 | Taito SJ | |
| + | `frontlin` | Front Line | Nov 1982 | Taito SJ **+ 68705 MCU** | The "extra insurance": protection moved into a chip |

Also worth having for comparison: `junglek` / `jungleh` (Jungle King/Hunt, Jun 1982, SJ, no MCU) and
`elevator` + `elevatorb` (Elevator Action, 1983, MCU; the bootleg removes the MCU, so diffing the two
shows exactly what the chip was protecting).

**Note:** these are Z80 games. The current tools are 8080-only (the Z80 runs 8080 code but adds
prefixed instructions the scanner would misread), so they need a Z80 mode. The MCU's own ROM is a
separate 68705 dump in the MAME set.

---

## Lead worth following: MAME bug #09074

MAME Testers bug 9074 (found in 0.273, verified, unfixed): on `lrescue`, `desterth`, `escmars`,
`grescue`, `mlander`, `lrescueabl`, `lrescuem` and `lrescuem2`, **rescuing the first person in stage 1
gives you a credit**, on all clones except `resclunar`.
Unexplained so far. One candidate: the game's music player has its own coin check (`$4D69`), separate
from the interrupt one, so the rescue jingle may be where the extra credit comes from. Worth tracing.
