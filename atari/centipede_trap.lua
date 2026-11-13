-- centipede_trap.lua: Centipede's "add credits if it's not a POKEY" check, in MAME.
--
--   mame centiped -autoboot_script atari/centipede_trap.lua                  board without a genuine POKEY
--   NOPOKEY=0 mame centiped -autoboot_script atari/centipede_trap.lua        genuine board, for comparison
--
-- At power-up and at the start of every game, Centipede switches its POKEY sound chip into reset (which freezes the
-- chip's random-number register), reads the random number twice, and adds the difference (EOR) to the credit
-- count ($28A2 in rev 4). On a genuine POKEY the two reads are equal and nothing is added. This script makes those
-- two reads differ by XORVAL (default 3), as on a board whose random register kept changing, so each game start adds
-- 3 credits. Only those two reads are changed: Centipede checks for a genuine POKEY elsewhere too, and faking the
-- chip everywhere makes the game reset. The credit count is $C8 (BCD), shown as CREDITS on the attract screen.
-- Inserts one coin and presses Start every 2 minutes (COINS=n to stop after n).

local mem = manager.machine.devices[":maincpu"].spaces["program"]
local cpu = manager.machine.devices[":maincpu"]
local function field(name)
  for _, p in pairs(manager.machine.ioport.ports) do
    for n, f in pairs(p.fields) do if n == name then return f end end
  end
end
local coin, start = field("Coin 1"), field("1 Player Start")
local ncoins = tonumber(os.getenv("COINS") or "999")
local frame, last = 0, -1

if os.getenv("NOPOKEY") ~= "0" then
  local xv = tonumber(os.getenv("XORVAL") or "3")
  tap = mem:install_read_tap(0x100a, 0x100a, "nopokey", function(offset, data, mask)
    local pc = cpu.state["PC"].value
    if pc >= 0x28a0 and pc <= 0x28a4 then return 0x5a end          -- LDA $100A at $28A2
    if pc >= 0x28a5 and pc <= 0x28ab then return 0x5a ~ xv end     -- EOR $100A at $28A5
    return data
  end)
  print(string.format("No-POKEY simulation: the two reads at $28A2/$28A5 now differ by %d", xv))
else
  print("Genuine board: nothing changed")
end

local function press(f, on) if f then f:set_value(on and 1 or 0) end end
notifier = emu.add_machine_frame_notifier(function()
  frame = frame + 1
  local t = frame % 7200
  if frame // 7200 >= ncoins then t = 0 end
  press(coin, t >= 300 and t < 306)
  press(start, t >= 400 and t < 406)
  local c = mem:read_u8(0xc8)
  if frame > 3 and c ~= last then print(string.format("%5d s  credits %X", frame // 60, c)) end
  last = c
end)
