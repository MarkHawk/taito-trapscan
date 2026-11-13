-- astdelux_trap.lua: show Asteroids Deluxe rev 1's hidden anti-bootleg credit trap in MAME.
--
--   mame astdelux1 -autoboot_script atari/astdelux_trap.lua                  bootleg simulation
--   TAMPER=none mame astdelux1 -autoboot_script atari/astdelux_trap.lua      genuine board, for comparison
--
-- On Windows PowerShell set the variable first: $env:TAMPER="none". Add -nothrottle to run faster than real time.
-- Add -debug -debugger none to also log when the copyright comparison and the payout code run.
--
-- What the script does, all in memory (your ROM zip is not changed):
--   1. Bootleg simulation: changes the copyright line the game draws on screen from "1980 ATARI INC" to
--      "1980 ACME  INC" (ROM $7606-$7608, in 036432-01.fh1), then resets so the game redraws it, as a bootlegger who
--      put their own name in the copyright would have done.
--   2. Inserts a coin and presses Start every 2 minutes, then leaves the ship alone until the game ends.
--   3. Empties the high-score table at the start of each game, so every game ends with a new top score.
--
-- The trap (rev 1 and rev 2; removed in rev 3): when a game ends with a new top score, the game redraws its
-- copyright from a second copy of the text ($7845) and compares it with what is in vector RAM. Any difference sets a
-- flag at $91, which stays set. From then on, each game that ends on the high-score table has a 1 in 3 chance
-- (POKEY random number <= $55) of adding 2 credits ($7046). Watch CREDITS on the attract screen: it climbs by 2 at
-- some game overs. On a genuine board it never does.

local mode = os.getenv("TAMPER") or "rom"
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local in1 = manager.machine.ioport.ports[":IN1"]
local function field(name)
  for n, f in pairs(in1.fields) do if n == name then return f end end
end
local coin, start = field("Coin 1"), field("1 Player Start")
local frame, last93, last91, last22 = 0, -1, -1, -1

if mode == "rom" then
  local rom = manager.machine.memory.regions[":maincpu"]
  -- "1980 ATARI INC" is packed three characters to two bytes: 1F C4 09 70 2D 9A 0B 64 38 00
  local patch = { [0x7606] = 0x4e, [0x7607] = 0x8a, [0x7608] = 0x42 }    -- -> 1F C4 09 4E 8A 42 0B 64 38 00
  local changed = false
  for a, v in pairs(patch) do
    if rom:read_u8(a) ~= v then rom:write_u8(a, v); changed = true end
  end
  if changed then
    print("Bootleg simulation: on-screen copyright changed to \"1980 ACME INC\"; resetting so the game redraws it")
    manager.machine:soft_reset()
  end
else
  print("Genuine board: nothing changed")
end

local function press(f, on) if f then f:set_value(on and 1 or 0) end end

notifier = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local g = mem:read_u8(0x22)
  if g == 1 and last22 ~= 1 then
    for i = 0x23, 0x40 do mem:write_u8(i, 0) end      -- empty the high-score table
  end
  local t = frame % 7200
  press(coin, t >= 300 and t < 306)
  press(start, t >= 400 and t < 406)
  local c, f91 = mem:read_u8(0x93), mem:read_u8(0x91)
  if frame > 3 and (c ~= last93 or f91 ~= last91 or (g == 0 and last22 == 1)) then
    local what = ''
    if g == 0 and last22 == 1 then what = '  <- game over' end
    if last93 >= 0 and c == last93 + 2 then what = what .. '  <- +2 FREE CREDITS' end
    if f91 ~= 0 and last91 == 0 then what = what .. '  <- copyright check failed: trap armed' end
    print(string.format("%5d s  credits %d  tampered flag $91=%02X%s", frame // 60, c, f91, what))
  end
  last93, last91, last22 = c, f91, g
end)

if manager.machine.debugger then
  local d = manager.machine.debugger
  d:command('bpset 77ff,1,{printf "copyright comparison runs (new top score)"; g}')
  d:command('bpset 7046,1,{printf "$7046 reached: +2 credits"; g}')
  d:command('go')
  stopper = emu.add_machine_stop_notifier(function()
    for _, l in ipairs(d.consolelog) do
      if l:match("copyright") or l:match("credits") then print("DBG " .. l) end
    end
  end)
end
