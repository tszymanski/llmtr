-- M8-spike: throwaway Hammerspoon module. Installed as ~/.hammerspoon/llmtr_spike.lua and loaded
-- by one require("llmtr_spike") line in init.lua. Removed again in S10.
--
-- Driven from the shell with URL events, e.g.:
--   open -g "hammerspoon://llmtr_spike?cmd=flow&value=s5"
-- cmd=flow   value=log|s5|s6      what the hotkeys run (S4 / S5 / S6)
-- cmd=mode   value=press|release  when the hotkeys fire
-- cmd=delay  value=<seconds>      start delay before Cmd+C (S5 and S6)
-- cmd=env | notify_osa | notify_hs | notify_replace

local M = {}

-- Edit SPIKE to point at spike/macos in your clone. LOG matches common.sh's default.
local HOME = os.getenv("HOME")
local SPIKE = HOME .. "/llmtr/spike/macos"
local LOG = HOME .. "/.local/state/llmtr-spike/spike.log"
hs.fs.mkdir(HOME .. "/.local/state/llmtr-spike")

local state = { flow = "log", mode = "release", delay = 0 }
local hotkeys = {}

local function log(msg)
  local f = io.open(LOG, "a")
  if f then
    f:write(os.date("%H:%M:%S") .. " [lua] " .. msg .. "\n")
    f:close()
  end
end

local function fmt(s) return string.format("%.2f", s) end

local function run(script, args, onExit)
  local t = hs.task.new(SPIKE .. "/" .. script, function(code, out, err)
    if code ~= 0 or (err and #err > 0) then
      log(script .. " exit=" .. code .. " stderr=" .. (err or ""))
    end
    if onExit then onExit(code) end
  end, args)
  t:start()
  return t
end

-- S6: Lua sends the keys; the script only waits for the copy and transforms.
local function flowS6(combo, tKey)
  local old = hs.pasteboard.getContents()
  hs.pasteboard.clearContents()
  local function go()
    local tCopy = hs.timer.secondsSinceEpoch()
    hs.eventtap.keyStroke({ "cmd" }, "c")
    run("s6_transform.sh", {}, function(code)
      local tDone = hs.timer.secondsSinceEpoch()
      if code ~= 0 then
        if old then hs.pasteboard.setContents(old) end
        log("S6 FAIL combo=" .. combo .. " mode=" .. state.mode .. " delay=" .. state.delay
          .. " nothing copied front=" .. tostring(hs.application.frontmostApplication():bundleID()))
        return
      end
      hs.eventtap.keyStroke({ "cmd" }, "v")
      local tPaste = hs.timer.secondsSinceEpoch()
      hs.timer.doAfter(0.3, function()
        if old then hs.pasteboard.setContents(old) else hs.pasteboard.clearContents() end
        local restored = hs.pasteboard.getContents() == old
        log("S6 OK combo=" .. combo .. " mode=" .. state.mode .. " delay=" .. state.delay
          .. " start_to_copykey=" .. fmt(tCopy - tKey) .. "s transform=" .. fmt(tDone - tCopy)
          .. "s hotkey_to_paste=" .. fmt(tPaste - tKey) .. "s restored=" .. tostring(restored)
          .. " front=" .. tostring(hs.application.frontmostApplication():bundleID()))
      end)
    end)
  end
  if state.delay > 0 then hs.timer.doAfter(state.delay, go) else go() end
end

local function fire(combo)
  local tKey = hs.timer.secondsSinceEpoch()
  local args = { combo, string.format("%.6f", tKey), state.mode }
  if state.flow == "log" then
    run("s4_hotkey.sh", args)
  elseif state.flow == "s5" then
    table.insert(args, tostring(state.delay))
    run("s5_flow.sh", args)
  else
    flowS6(combo, tKey)
  end
end

local COMBOS = {
  { { "ctrl", "alt" }, "t", "C-A-T" },
  { { "ctrl", "alt" }, "g", "C-A-G" },
  { { "ctrl", "alt" }, "r", "C-A-R" },
  { { "shift", "ctrl", "alt" }, "r", "S-C-A-R" },
  { { "shift", "ctrl", "alt" }, "t", "S-C-A-T" },
}

local function bindAll()
  for _, hk in ipairs(hotkeys) do hk:delete() end
  hotkeys = {}
  for _, c in ipairs(COMBOS) do
    local fn = function() fire(c[3]) end
    local hk
    if state.mode == "press" then
      hk = hs.hotkey.bind(c[1], c[2], fn)
    else
      hk = hs.hotkey.bind(c[1], c[2], nil, fn)
    end
    table.insert(hotkeys, hk)
  end
  log("bound " .. #hotkeys .. " hotkeys flow=" .. state.flow .. " mode=" .. state.mode
    .. " delay=" .. state.delay)
end

local notes = {}

hs.urlevent.bind("llmtr_spike", function(_, params)
  local cmd, value = params.cmd, params.value
  if cmd == "flow" then
    state.flow = value
    bindAll()
  elseif cmd == "mode" then
    state.mode = value
    bindAll()
  elseif cmd == "delay" then
    state.delay = tonumber(value) or 0
    bindAll()
  elseif cmd == "env" then
    run("env_dump.sh", {})
  elseif cmd == "notify_osa" then
    local t = hs.task.new("/usr/bin/osascript", function(code, _, err)
      log("notify_osa exit=" .. code .. " err=" .. (err or ""))
    end, { "-e", 'display notification "Translating… (S3 from hs.task)" with title "llmtr"' })
    t:start()
  elseif cmd == "notify_hs" then
    local n = hs.notify.new({ title = "llmtr", informativeText = "Translating… (S3 hs.notify)" })
    n:send()
    table.insert(notes, n)
    log("notify_hs sent presented=" .. tostring(n:presented()))
  elseif cmd == "notify_replace" then
    local n = hs.notify.new({ title = "llmtr", informativeText = "Translating… (will be replaced in 4 s)" })
    n:send()
    table.insert(notes, n)
    hs.timer.doAfter(4, function()
      n:withdraw()
      local done = hs.notify.new({ title = "llmtr", informativeText = "Done (replaced the old one)" })
      done:send()
      table.insert(notes, done)
      log("notify_replace: withdrew first, sent second")
    end)
  end
end)

bindAll()
log("llmtr_spike loaded")

return M
