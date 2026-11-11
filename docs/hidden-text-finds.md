# Hidden text finds (`textscan.py` over 1975–85 MAME sets)

`textscan.py` decoded the text in 3,052 sets (MAME 0.277, every 1975–85 arcade set in the collection) and
flagged anything with anti-piracy wording, named credits, or personal or rude words. Each find below was
checked against [The Cutting Room Floor](https://tcrf.net) (TCRF), arcade-history.com and MAME's source
before being called new. "Not found" means not found in those sources, not proof that nobody has seen it.

## ★★★ Anti-piracy messages not found documented

| Set | Game | Text | Where |
|---|---|---|---|
| `tp84`, `tp84b` | Time Pilot '84 (Konami, 1984) | **"THIS IS AN ILLEGAL DUPLICATE OF KONAMI'S ORIGINAL PCBOARD"** | `388_f06.9j` +021F |
| `levers` | Levers (Rock-Ola, 1983) | **"THIS IS AN ILLEGAL COPY OF COPYRIGHTED SOFTWARE"** | `g96061.e8` +0722 |
| `warofbug` (and clones) | War of the Bugs (Armenia, 1981) | "...TOTALLY ORIGINAL ... UNAUTHORISED DUPLICATION" | `warofbug.z` +001C |

Whether these are ever shown, and what triggers them (a copy check, as in Lunar Rescue, or nothing at all, as
in Akka Arrh), is still to be traced in the code.

## ★★ Copyright and legal notices kept in ROM

| Set | Game | Text |
|---|---|---|
| `cclimber`, `ccboot` | Crazy Climber (Nichibutsu, 1980) | "NO PART OF THIS SOFTWARE MAY BE COPIED OR USED WITHOUT THE EXPRESS WRITTEN CONSENT OF NIHON BUSSAN CO LTD" |
| `msisaac` | Metal Soldier Isaac II (Taito, 1985) | program/design copyright notice with "UNAUTHORIZED" |
| `goldnpke` | Golden Poker | "THIS PROGRAM COPYRIGHT ... UNAUTHORISED ..." |

## ★★ Programmer credits and personal messages (not yet checked in full)

| Set | Text |
|---|---|
| `cmissnx` (Mission-X, Data East cassette, 1982) | "BONBER GAME PRG. MADE BY KIZAKI&MURAMOTO 1982/2/2" |
| `mrflea` (Mr. F. Lea, 1982) | "GRAPHICS BY: DAN POSNICK, CRAIG EDWARDS ... DEDICATED TO DORIS AND ..." |
| `scion` (Seibu Denshi, 1984) | "FROM UTSUNOMIYA WITH OUR LOVE" |
| `spectar`, `targc` (Exidy) | "PROGRAMMED BY MANUEL J. CAMPOS" with a home address in San Jose |
| `thief`, `natodef` (Pacific Novelty) | "PROGRAM DEVELOPED BY PHILIP LIEBERMAN" |
| `hardhat` (Exidy, 1982) | "WRITTEN BY: LARRY W. HUTCHERSON SR." |
| `junglek` and clones | "B I LOVE YOU" |
| `lupin3a` | "DARLING I LOVE YOU" |

## Already documented (the scanner found them again)

| Set | Text | Documented at |
|---|---|---|
| `akkaarrh` | "JOHN SALWITZ, DEC 9,1982, FOR ATARI, A WARNER COMPANY / GOOD LUCK, YOU PIRATES" (unused) | [TCRF: Akka Arrh](https://new.tcrf.net/Akka_Arrh) |
| `digger` | "WRITTEN BY DAVID L. EVANS, 4535 TAFT AVENUE, LA MESA, CALIF. ... JUNE 25, 1980 GREMLIN/SEGA INC." | [TCRF: Digger](https://tcrf.net/Digger_(Arcade)) |
| `sdungeon` | "STOLEN FROM THE GOOD BUDDY'S AT TAITO BY AN UNAUTHORIZED DO BADDER" | [TCRF: Space Dungeon](https://new.tcrf.net/Space_Dungeon) |
| `combat`, `cracksht`, `cheyenne` | Exidy's hidden lines after the hardware-error screen ("HELLO, BENNY!", "GREETINGS!... PROFESSOR FALKEN") | TCRF's [Combat](https://tcrf.net/Combat_(Arcade)), [Crackshot](https://tcrf.net/Crackshot) and [Cheyenne](https://new.tcrf.net/Cheyenne) pages cover these hidden messages |
| `gng`, `sectionz` | "THIS PROGRAME IS PROGRAMED BY TOSHIO ARIMA, IF YOU NEED SAME INFORMETION THEN FONE ..." | widely known (Capcom) |

## False reads

- `mmonkey` "FART DESIGNERS": the line is "ART DESIGNERS". Its credits store a one-byte screen position before
  each line, and that byte happens to decode as a letter (the line before reads "FSOUND DIRECTOR").
- Most other hits are ordinary game text: "THIEF" in thief-themed games, "SORRY NO BONUS", "CRAP OUT" in dice
  games, trivia questions, and a Norwegian quiz where *fart* means speed.
