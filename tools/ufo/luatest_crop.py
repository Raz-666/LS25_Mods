#!/usr/bin/env python3
"""Head-less smoke test for scripts/CropHarvester.lua.

The game cannot be started here, so this mocks the handful of GIANTS engine
functions the flight code touches and runs the specialization through a short
flight: take off, climb, fly a circle, descend, land.  It catches typos, nil
indexing, NaN maths and multiplayer-stream mistakes before the mod ever reaches
the game.

      python tools/ufo/luatest_crop.py        (needs the 'lupa' package)
"""

import math
import os
import sys

from lupa import LuaRuntime

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LUA = os.path.join(REPO, "FS25_CropHarvester", "scripts", "CropHarvester.lua")

MOCK = r"""
-- ---------------------------------------------------------------- engine mock
Class = function(sub, base) 
    local c = {} 
    c.__index = c 
    if base then setmetatable(c, {__index = base}) end
    return c
end

local function deepcopy(t)
    local r = {}
    for k, v in pairs(t) do r[k] = v end
    return r
end

Event = { new = function(mt) return setmetatable({}, mt or {}) end }
InitStaticEventClass = function(cls, name) cls.name = name end
NetworkUtil = {
    readNodeObject = function(streamId) return streamId.obj end,
    writeNodeObject = function(streamId, obj) streamId.obj = obj end,
}

Specialization = {}
SpecializationUtil = {
    registerFunction = function(t, name, fn) _G.functions = _G.functions or {}; _G.functions[name] = fn end,
    registerOverwrittenFunction = function(t, name, fn) _G.overwritten = _G.overwritten or {}; _G.overwritten[name] = fn end,
    registerEventListener = function(t, event, spec)
        _G.listeners = _G.listeners or {}
        _G.listeners[event] = _G.listeners[event] or {}
        table.insert(_G.listeners[event], spec)
    end,
    raiseEvent = function() end,
}

-- scene state of the single test vehicle
world = { x = 0, y = 0.0, z = 0, pitch = 0, yaw = 0, roll = 0,
          vx = 0, vy = 0, vz = 0, terrainY = 0.0, visibility = {}, time = 0 }
nodeIds = { leg0 = 11, leg1 = 12, leg2 = 13, beamLight = 21,
            beaconLight = 22, groundRing = 23, driverSeatNode = 24,
            patternPointer = 30, modeLever = 31, focusSlider = 32, modeNeedle = 33,
            beamNodeDamage = 50, beamNodeHarvest = 51, beamNodeCultivate = 52,
            beamNodePlow = 53, beamNodeSow = 54, beamNodeFertilize = 55,
            beamNodeLoad = 56, beamNodeUnload = 57 }

function getWorldTranslation(node)
    local t = world.nodes and world.nodes[node]
    if t ~= nil then return t[1], t[2], t[3] end
    return world.x, world.y, world.z
end
function getTranslation(node) return 0, 0, 0 end
function getRotation(node) return 0, 0, 16 end
function getWorldRotation(node) return world.pitch, world.yaw, world.roll end
function setRotation(node, a, b, c)
    world.rotation = world.rotation or {}
    world.rotation[node] = { a, b, c }
    if node == world.node then world.pitch, world.yaw, world.roll = a, b, c end
end
function setWorldTranslation(node, x, y, z) world.x, world.y, world.z = x, y, z end
function setTranslation(node, x, y, z)
    world.translation = world.translation or {}
    world.translation[node] = { x, y, z }
end
function setScale(node, x, y, z)
    world.scale = world.scale or {}
    world.scale[node] = { x, y, z }
end
function setLinearVelocity(node, x, y, z) world.vx, world.vy, world.vz = x, y, z end
function setAngularVelocity(node, x, y, z) end
function setVisibility(node, v) world.visibility[node] = v end
function setLightColor(node, r, g, b)
    world.lightColor = world.lightColor or {}
    world.lightColor[node] = { r, g, b }
end
function getTerrainHeightAtWorldPos(terrain, x, y, z) return world.terrainY end

math.clamp = function(v, a, b) return math.max(a, math.min(b, v)) end
if math.atan2 == nil then math.atan2 = function(y, x) return math.atan(y, x) end end
bit32 = { band = function(a, b)
    local r, bit = 0, 1
    while a > 0 and b > 0 do
        local aa, bb = a % 2, b % 2
        if aa == 1 and bb == 1 then r = r + bit end
        a, b, bit = math.floor(a / 2), math.floor(b / 2), bit * 2
    end
    return r
end }
g_terrainNode = 1
g_currentMission = { time = 0, drawables = {},
    hud = { addHelpExtension = function() end },
    addDrawable = function(self, d) self.drawables[#self.drawables + 1] = d end,
    removeDrawable = function(self, d)
        for i = #self.drawables, 1, -1 do
            if self.drawables[i] == d then table.remove(self.drawables, i) end
        end
    end,
    addIngameNotification = function() end }
FSBaseMission = { INGAME_NOTIFICATION_INFO = 1 }
g_gui = { getIsGuiVisible = function() return false end }
RenderText = { ALIGN_LEFT = 1, ALIGN_CENTER = 2 }
setTextColor = function() end
setTextAlignment = function() end
renderText = function() end
drawFilledRect = function() end
drawOutlineRect = function() end

-- density map mock: records the damaged (flattened) rectangles
mown = { count = 0, area = 0, rects = {} }
FSDensityMapUtil = {
    updateWheelDestructionArea = function(x1, z1, x2, z2, x3, z3)
        local w = math.sqrt((x2 - x1) ^ 2 + (z2 - z1) ^ 2)
        local h = math.sqrt((x3 - x1) ^ 2 + (z3 - z1) ^ 2)
        mown.count = mown.count + 1
        mown.area = mown.area + w * h
        table.insert(mown.rects, { x1, z1, x2, z2, x3, z3 })
    end,
}
FillType = { UNKNOWN = 0, WHEAT = 1, FERTILIZER = 2 }
ToolType = { UNDEFINED = 1, UNLOADING = 2, LOADING = 3 }
g_fillTypeManager = {
    getFillTypeByIndex = function(i) return { index = i, name = "wheat" } end,
}
g_fruitTypeManager = {
    getFruitTypeByIndex = function(i)
        return { index = i, name = "WHEAT", fillType = 1, literPerSqm = 0.35,
                 getAreaLiters = function(self, area) return area * self.literPerSqm end }
    end,
    getFruitTypeIndexByName = function(name) return name == "WHEAT" and 1 or 2 end,
}
g_sprayTypeManager = {
    getSprayTypeByName = function(name) return { index = 1, name = name } end,
}

-- sound mock: remembers what was played / stopped
sounds = { played = {}, stopped = {}, playing = {} }
g_soundManager = {
    playSample = function(self, sample) sounds.played[#sounds.played + 1] = sample end,
    stopSample = function(self, sample) sounds.stopped[#sounds.stopped + 1] = sample end,
    getIsSamplePlaying = function(self, sample) return false end,
    loadSampleFromXML = function() return nil end,
}

-- field work mock: counts the worked area per tool
worked = { cultivate = 0, plow = 0, sow = 0, spray = 0, calls = 0 }
local function recordRect(kind, x1, z1, wx, wz, hx, hz)
    local area = math.abs(wx * hz) + math.abs(hx * wz)
    worked[kind] = worked[kind] + area
    worked.calls = worked.calls + 1
    return area, area
end
FSDensityMapUtil.updateCultivatorArea = function(x1, z1, wx, wz, hx, hz)
    return recordRect("cultivate", x1, z1, wx, wz, hx, hz)
end
FSDensityMapUtil.updatePlowArea = function(x1, z1, wx, wz, hx, hz)
    return recordRect("plow", x1, z1, wx, wz, hx, hz)
end
FSDensityMapUtil.updateSowingArea = function(fruit, x1, z1, wx, wz, hx, hz)
    worked.lastFruit = fruit
    return recordRect("sow", x1, z1, wx, wz, hx, hz)
end
FSDensityMapUtil.updateSprayArea = function(x1, z1, wx, wz, hx, hz, sprayType, amount)
    worked.lastSpray = sprayType
    return recordRect("spray", x1, z1, wx, wz, hx, hz)
end
-- harvest mock: counts the cut area and the liters the field gives
cut = { count = 0, area = 0 }
FSDensityMapUtil.getFruitTypeIndexAtWorldPos = function(x, z)
    if world.field then return 1, 4 end
    return nil
end
FSDensityMapUtil.cutFruitArea = function(fruitIndex, x1, z1, wx, wz, hx, hz)
    if not world.field then return 0 end
    local area = math.abs(wx * hz)
    cut.count = cut.count + 1
    cut.area = cut.area + area
    return area
end

-- a tip station standing at the origin, and a trailer next to it
stationNode, trailerNode = 40, 41
g_currentMission.storageSystem = {
    getUnloadingStations = function()
        return { { stationName = "Silo", unloadTriggers = { { triggerNode = stationNode } },
                   getIsFillTypeAllowed = function(self, fillType) return true end,
                   getFreeCapacity = function(self, fillType, farmId) return 999999 end,
                   addFillLevelFromTool = function(self, farmId, amount, fillType, info, toolType)
                       stationFill = (stationFill or 0) + amount
                       return amount
                   end } }
    end,
}
stationFill = 0

g_i18n = { getText = function(k) return k end }
g_inputBinding = { setActionEventTextPriority = function() end, setActionEventText = function() end }
GS_PRIO_HIGH, GS_PRIO_NORMAL = 3, 2
g_client = { getServerConnection = function() return { sendEvent = function(_, e) e:run() end } end }

-- minimal stream implementation for the update stream
stream = {}
stream.__index = stream
function newStream() return setmetatable({ data = {}, pos = 0, obj = nil }, stream) end
function stream:writeBool(v) local b = v and 1 or 0; table.insert(self.data, b); return b end
function stream:writeUIntN(v, n) table.insert(self.data, v); return v end
function stream:writeIntN(v, n) table.insert(self.data, v); return v end
function stream:readBool() self.pos = self.pos + 1; return self.data[self.pos] == 1 end
function stream:readUIntN(n) self.pos = self.pos + 1; return self.data[self.pos] end
function stream:readIntN(n) self.pos = self.pos + 1; return self.data[self.pos] end
streamWriteBool = function(s, v) return s:writeBool(v) end
streamWriteUIntN = function(s, v, n) return s:writeUIntN(v, n) end
streamWriteIntN = function(s, v, n) return s:writeIntN(v, n) end
streamReadBool = function(s) return s:readBool() end
streamReadUIntN = function(s, n) return s:readUIntN(n) end
streamReadIntN = function(s, n) return s:readIntN(n) end

-- vehicle factory ---------------------------------------------------------
vehicle_mt = {}
vehicle_mt.__index = vehicle_mt
function newVehicle()
    local v = setmetatable({}, vehicle_mt)
    v.isServer = true
    v.isClient = true
    v.xmlFile = { getValue = function() return nil end, hasProperty = function() return false end }
    v.i3dMappings = {}
    for name, id in pairs(nodeIds) do
        table.insert(v.i3dMappings, { id = name, node = id })
    end
    v.components = { { node = 1 } }
    v.rootNode = 1
    world.node = 1
    v.spec = {}
    v.dirtyFlags = 0
    v.actionEvents = {}
    v.getNextDirtyFlag = function(self) return 16 end
    v.getOwnerFarmId = function(self) return 1 end
    -- fill units: 1 = diesel, 2 = the grain tank, 3 = the virtual cargo hold
    v.fillUnits = { { fillType = 0, fillLevel = 90, capacity = 90 },
                    { fillType = 1, fillLevel = 0, capacity = 25000 },
                    { fillType = 0, fillLevel = 0, capacity = 5000000 } }
    v.tankAccept = true
    v.getFillUnitCount = function(self) return #self.fillUnits end
    v.getFillUnitFillLevel = function(self, i) return self.fillUnits[i].fillLevel end
    v.getFillUnitFillType = function(self, i) return self.fillUnits[i].fillType end
    v.getFillUnitCapacity = function(self, i) return self.fillUnits[i].capacity end
    v.getFillUnitFreeCapacity = function(self, i, fillType, farmId)
        return self.fillUnits[i].capacity - self.fillUnits[i].fillLevel
    end
    v.getFillUnitSupportsFillType = function(self, i, fillType) return i >= 2 end
    v.addFillUnitFillLevel = function(self, farmId, i, delta, fillType, toolType, pos)
        local fu = self.fillUnits[i]
        local before = fu.fillLevel
        fu.fillType = fillType
        fu.fillLevel = math.max(0, math.min(fu.capacity, fu.fillLevel + delta))
        return fu.fillLevel - before
    end
    v.raiseDirtyFlags = function(self, f) self.dirtyFlags = f end
    v.getIsMotorStarted = function(self) return true end
    v.getIsEntered = function(self) return true end
    v.isControlled = true
    v.getIsControlled = function(self) return true end
    v.clearActionEventsTable = function(self, t)
        if t ~= nil then for k in pairs(t) do t[k] = nil end end
    end
    v.addActionEvent = function(self, table_, name, target, callback, ...)
        return true, 100
    end
    return v
end

function callEvent(vehicle, name, ...)
    _G.listeners = _G.listeners or {}
    for _, spec in ipairs(_G.listeners[name] or {}) do
        local fn = spec[name]
        if fn ~= nil then fn(vehicle, ...) end
    end
end

function runScript(path, vehicle)

end

-- overwritten-function wrapper (GIANTS passes superFunc as 2nd arg)
function callOverwritten(vehicle, name, ...)
    local fn = _G.overwritten[name]
    if fn == nil then return nil end
    return fn(vehicle, function() return true end, ...)
end
"""


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK)
    lua.execute(open(LUA, encoding="utf-8").read())
    # the engine calls these when the vehicle type is registered
    lua.execute("""
    local vehicleType = {}
    CropHarvester.registerFunctions(vehicleType)
    -- GIANTS adds the registered functions to the vehicle class; the mock does
    -- the same on the shared metatable
    for name, fn in pairs(_G.functions or {}) do
        vehicle_mt[name] = function(self, ...) return fn(self, ...) end
    end
    CropHarvester.registerOverwrittenFunctions(vehicleType)
    CropHarvester.registerEventListeners(vehicleType)
    """)

    lua.execute("""
    vehicle = newVehicle()
    vehicle.spec_cropHarvester = {}
    callEvent(vehicle, "onLoad", nil)
    """)

    def check(name, cond, extra=""):
        print(("  ok    " if cond else "  ERROR ") + name + ((" " + extra) if extra else ""))
        return cond

    ok = True
    spec = lua.eval("vehicle.spec_cropHarvester")
    ok &= check("legs found", lua.eval("#vehicle.spec_cropHarvester.legNodes") == 3)
    ok &= check("eight beam nodes found (one per mode)",
                lua.eval("#vehicle.spec_cropHarvester.beamNodes") == 8)
    ok &= check("beam cones hidden at load",
                all(lua.eval("world.visibility[%d]" % n) is False for n in range(50, 58)))
    ok &= check("minRotTime patched", lua.eval("vehicle.minRotTime") != 0)

    # ---- take off ----------------------------------------------------------
    lua.execute("""
    vehicle.spec_drivable = { axisForward = 0, axisSide = 0 }
    callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    vehicle:setUFOIsHovering(true)
    for i = 1, 300 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    end
    """)
    hov = lua.eval("vehicle.spec_cropHarvester.isHovering")
    alt = lua.eval("vehicle.spec_cropHarvester.altitude")
    y = lua.eval("world.y")
    ok &= check("hovering after key press", hov is True)
    ok &= check("climbed off the ground", y > 2.6, "y=%.2f" % y)
    ok &= check("altitude reached target", abs(alt - lua.eval("vehicle.spec_cropHarvester.altitudeTarget")) < 0.5,
                "alt=%.2f" % alt)
    ok &= check("legs folded away", lua.eval("vehicle.spec_cropHarvester.legsAlpha") > 0.9,
                "alpha=%.2f" % lua.eval("vehicle.spec_cropHarvester.legsAlpha"))

    # ---- climb with the ascend key ----------------------------------------
    lua.execute("""
    vehicle.spec_cropHarvester.digitalUp = true
    for i = 1, 300 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    vehicle.spec_cropHarvester.digitalUp = false
    """)
    y2 = lua.eval("world.y")
    ok &= check("climb key raises the craft", y2 > y + 10, "y=%.2f -> %.2f" % (y, y2))

    # ---- fly forward and steer --------------------------------------------
    lua.execute("""
    vehicle.spec_drivable.axisForward = 1
    vehicle.spec_drivable.axisSide = 0.6
    for i = 1, 180 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    speed = lua.eval("vehicle.spec_cropHarvester.speed")
    yaw = lua.eval("vehicle.spec_cropHarvester.yaw")
    x, z = lua.eval("world.x"), lua.eval("world.z")
    ok &= check("accelerated forward", speed > 6.0, "v=%.2f m/s" % speed)
    ok &= check("steering turns the craft", abs(yaw) > 20, "yaw=%.1f" % yaw)
    ok &= check("moved horizontally", math.hypot(x, z) > 5, "dist=%.1f" % math.hypot(x, z))

    # NaN check on every numeric state
    for name in ("altitude", "yaw", "speed", "pitch", "roll"):
        v = lua.eval("vehicle.spec_cropHarvester.%s" % name)
        ok &= check("no NaN in %s" % name, v == v and abs(v) < 1e6)

    # ---- beam toggle -------------------------------------------------------
    lua.execute("vehicle:setUFOBeamActive(true)")
    ok &= check("beam visible", lua.eval("world.visibility[50]") is True)
    ok &= check("only one beam cone visible",
                sum(1 for n in range(50, 58) if lua.eval("world.visibility[%d]" % n)) == 1)
    ok &= check("beam light visible", lua.eval("world.visibility[21]") is True)

    # ---- multiplayer update stream ----------------------------------------
    lua.execute("""
    local s = newStream()
    s.obj = vehicle
    callEvent(vehicle, "onWriteUpdateStream", s, { getIsServer = function() return true end }, vehicle.dirtyFlags)
    callEvent(vehicle, "onReadUpdateStream", s, 0, { getIsServer = function() return true end })
    local s2 = newStream()
    vehicle.spec_cropHarvester.axisValue = -1
    vehicle.spec_cropHarvester.verticalDirty = true
    callEvent(vehicle, "onWriteUpdateStream", s2, { getIsServer = function() return false end }, 0)
    vehicle.spec_cropHarvester.axisValue = 0
    callEvent(vehicle, "onReadUpdateStream", s2, 0, { getIsServer = function() return false end })
    """)
    ok &= check("update stream round trip", abs(lua.eval("vehicle.spec_cropHarvester.axisValue") + 1) < 0.01)
    lua.execute("vehicle.spec_cropHarvester.axisValue = 0")

    # ---- descend and land -------------------------------------------------
    lua.execute("""
    vehicle.spec_drivable.axisForward = 0
    vehicle.spec_drivable.axisSide = 0
    vehicle.spec_cropHarvester.digitalDown = true
    for i = 1, 1500 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if not vehicle.spec_cropHarvester.isHovering then break end
    end
    vehicle.spec_cropHarvester.digitalDown = false
    """)
    ok &= check("landed back on the ground", lua.eval("vehicle.spec_cropHarvester.isHovering") is False,
                "y=%.2f" % lua.eval("world.y"))
    ok &= check("beam switches off when landing",
                lua.eval("vehicle.spec_cropHarvester.beamActive") is False)

    # ---- crop circle menu -------------------------------------------------
    lua.execute("""
    vehicle:setUFOBeamActive(false)
    vehicle:setUFOIsHovering(true)
    vehicle:setUFOAltitude(20)
    for i = 1, 480 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    radius = lua.eval("vehicle:getUFOCircleRadius()")
    alt = lua.eval("vehicle.spec_cropHarvester.altitude")
    expected = alt * math.tan(math.radians(34.0))
    ok &= check("beam radius follows the altitude", abs(radius - expected) < 0.01,
                "r=%.2f at %.1f m" % (radius, alt))

    lua.execute("""
    CropHarvester.actionEventMenu(vehicle, "crop_menu", 1, nil)
    """)
    ok &= check("menu opens", lua.eval("vehicle.spec_cropHarvester.menuOpen") is True)
    before = lua.eval("vehicle.spec_cropHarvester.patternIndex")
    lua.execute("CropHarvester.actionEventAltitudeUp(vehicle, 'crop_altitudeUp', 1, nil)")
    after = lua.eval("vehicle.spec_cropHarvester.patternIndex")
    ok &= check("pattern can be picked in the menu", after == (before % 9) + 1,
                "%d -> %d" % (before, after))
    heightBefore = lua.eval("vehicle.spec_cropHarvester.altitudeTarget")
    ok &= check("menu keys do not change the altitude",
                abs(lua.eval("vehicle.spec_cropHarvester.altitudeTarget") - heightBefore) < 1e-9)

    # selected pattern 1 = full circle: mown area has to be about pi r^2
    lua.execute("vehicle:setUFOCirclePattern(1)")
    lua.execute("""
    mown.count, mown.area = 0, 0
    CropHarvester.actionEventBeam(vehicle, "crop_menu", 1, nil)   -- menu was open: fires
    """)
    ok &= check("beam fires from the menu", lua.eval("vehicle.spec_cropHarvester.beamActive") is True)
    ok &= check("menu closes on fire", lua.eval("vehicle.spec_cropHarvester.menuOpen") is False)
    spans = lua.eval("#(vehicle.spec_cropHarvester.drawQueue or {})")
    ok &= check("pattern broken into slices", spans > 10, "%d slices" % spans)

    lua.execute("""
    for i = 1, 600 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_cropHarvester.drawQueue == nil then break end
    end
    """)
    area = lua.eval("mown.area")
    cells = lua.eval("mown.count")
    want = math.pi * radius * radius
    ok &= check("pattern stamped", lua.eval("vehicle.spec_cropHarvester.drawQueue") is None,
                "%d rectangles" % cells)
    ok &= check("circle area matches pi r^2", abs(area - want) / want < 0.10,
                "%.0f m2 vs %.0f m2" % (area, want))
    ok &= check("progress reported to clients", lua.eval("vehicle.spec_cropHarvester.drawProgress") == 1)

    # ring pattern mows less than a filled circle
    lua.execute("""
    vehicle:setUFOCirclePattern(2)
    mown.count, mown.area = 0, 0
    vehicle:setUFOBeamActive(false)
    vehicle:setUFOBeamActive(true)
    for i = 1, 600 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_cropHarvester.drawQueue == nil then break end
    end
    """)
    ringArea = lua.eval("mown.area")
    ok &= check("ring damages less than the filled circle", area * 0.5 < ringArea < area * 0.95,
                "%.0f m2 vs %.0f m2" % (ringArea, area))

    # the marker ring on the ground grows to the beam radius
    lua.execute("""
    g_currentMission.time = g_currentMission.time + 16
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ringScale = lua.eval("world.scale[%d]" % (23,))
    ok &= check("ground ring scaled to the beam", ringScale is not None and
                abs(ringScale[1] - radius) / radius < 0.05,
                "scale=%.2f" % (ringScale[1] if ringScale else -1))

    # ---- manual pen -------------------------------------------------------
    lua.execute("""
    vehicle:setUFOCirclePattern(CropHarvester.getPatternCount())
    """)
    ok &= check("manual pattern is the last menu entry",
                lua.eval("CropHarvester.isManual(vehicle.spec_cropHarvester.patternIndex)") is True)
    ok &= check("pen radius is 50 cm (1 m pen)", abs(lua.eval("vehicle:getUFOCircleRadius()") - 0.50) < 1e-6)

    lua.execute("""
    vehicle:setUFOAltitude(6)
    for i = 1, 240 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    vehicle:setUFOBeamActive(false)
    mown.count, mown.area, mown.rects = 0, 0, {}
    vehicle:setUFOBeamActive(true)
    vehicle.spec_drivable.axisForward = 1
    for i = 1, 180 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    vehicle.spec_drivable.axisForward = 0
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    penDots = lua.eval("mown.count")
    penArea = lua.eval("mown.area")
    ok &= check("pen paints dots along the flight path", penDots > 20, "%d dots" % penDots)
    # every stamp must be one beam footprint (2 x radius), not a smear
    avg = penArea / max(1.0, penDots)
    ok &= check("pen dots are single 1 m stamps", 0.5 < avg < 1.8,
                "%d dots, %.1f m2, %.2f m2/dot" % (penDots, penArea, avg))
    ok &= check("pen line follows the craft", lua.eval(
        "(function() local minx, maxx = 1e9, -1e9; for _, r in ipairs(mown.rects) do minx = math.min(minx, r[1]); maxx = math.max(maxx, r[1]) end; return maxx - minx end)()") > 8)
    ok &= check("marker ring hidden in pen mode", lua.eval("world.visibility[23]") is False)

    # stationary craft must not keep stamping the same spot
    lua.execute("""
    for i = 1, 400 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_cropHarvester.speed < 0.01 then break end
    end
    mown.count, mown.area = 0, 0
    for i = 1, 120 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("no damage while standing still", lua.eval("mown.count") == 0,
                "%d stamps" % lua.eval("mown.count"))

    # ---- legs: fold in when flying, unfold when landing -------------------
    lua.execute("""
    vehicle:setUFOBeamActive(false)
    vehicle.spec_cropHarvester.digitalDown = true
    for i = 1, 2000 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if not vehicle.spec_cropHarvester.isHovering then break end
    end
    vehicle.spec_cropHarvester.digitalDown = false
    for i = 1, 400 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("landed", lua.eval("vehicle.spec_cropHarvester.isHovering") is False,
                "y=%.2f" % lua.eval("world.y"))
    ok &= check("landing legs are deployed again", lua.eval("vehicle.spec_cropHarvester.legsAlpha") < 0.02,
                "alpha=%.3f" % lua.eval("vehicle.spec_cropHarvester.legsAlpha"))
    ok &= check("beam stopped on landing", lua.eval("world.visibility[50]") is False)
    padArea = lua.eval("mown.area")
    padStamps = lua.eval("mown.count")
    wantPad = math.pi * 1.9 * 1.9
    ok &= check("landing left a flattened pad in the field",
                0.6 * wantPad < padArea < 1.6 * wantPad,
                "%.1f m2 in %d stamps (pad ~ %.1f m2)" % (padArea, padStamps, wantPad))

    # take off again: the cushion stamps the pad a second time
    lua.execute("""
    mown.count, mown.area = 0, 0
    vehicle:setUFOIsHovering(true)
    """)
    ok &= check("take off leaves marks, too", lua.eval("mown.area") > 0.6 * wantPad,
                "%.1f m2" % lua.eval("mown.area"))

    # ---- harvest mode -----------------------------------------------------
    lua.execute("""
    vehicle:setUFOIsHovering(true)
    vehicle:setUFOAltitude(30)
    vehicle:setUFOCirclePattern(1)
    vehicle:setUFOBeamMode(CropHarvester.BEAM_MODE_HARVEST)
    world.field = true
    cut.count, cut.area = 0, 0
    vehicle.fillUnits[2].fillLevel = 0
    mown.count, mown.area = 0, 0
    vehicle:setUFOBeamActive(false)
    vehicle:setUFOBeamActive(true)
    for i = 1, 240 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("harvest mode is selectable",
                lua.eval("vehicle:getUFOBeamMode()") == 2)
    cutArea = lua.eval("cut.area")
    tank = lua.eval("vehicle.fillUnits[2].fillLevel")
    ok &= check("beam cuts the field in harvest mode", cutArea > 100,
                "%.0f m2 cut" % cutArea)
    ok &= check("cut crop lands in the grain tank", tank > 30,
                "%.0f l in the tank" % tank)
    ok &= check("harvest mode does not flatten the crop",
                lua.eval("mown.count") == 0, "%d stamps" % lua.eval("mown.count"))
    ok &= check("tank litres match the cut area",
                abs(tank - cutArea * 0.35) < 1.0,
                "%.0f l vs %.0f l" % (tank, cutArea * 0.35))

    # endless tank: the field is still harvested, the tank stays empty
    lua.execute("""
    vehicle:setUFOInfiniteTank(true)
    cut.count, cut.area = 0, 0
    vehicle.fillUnits[2].fillLevel = 0
    for i = 1, 120 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("endless tank still harvests", lua.eval("cut.area") > 50,
                "%.0f m2" % lua.eval("cut.area"))
    ok &= check("endless tank stays empty", lua.eval("vehicle.fillUnits[2].fillLevel") == 0)
    lua.execute("vehicle:setUFOInfiniteTank(false)")

    # full tank: no more cutting until it is emptied
    lua.execute("""
    vehicle.fillUnits[2].fillLevel = 25000
    cut.count, cut.area = 0, 0
    for i = 1, 60 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("full tank stops the harvest", lua.eval("cut.area") == 0)

    # ---- unload by hovering ----------------------------------------------
    lua.execute("""
    vehicle:setUFOBeamActive(false)     -- the beam is off while unloading
    vehicle:setUFOAltitude(12)
    for i = 1, 300 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    world.x, world.z = 0, 0
    world.nodes = { [stationNode] = { 0, 0, 0 } }
    stationFill = 0
    local before = vehicle.fillUnits[2].fillLevel
    CropHarvester.runCommand(vehicle, "unload")
    callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    targetWhileUnloading = vehicle.spec_cropHarvester.unloadTargetName
    for i = 1, 800 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("unloading empties the tank", lua.eval("vehicle.fillUnits[2].fillLevel") < 1,
                "%.0f l left, unloading=%s" % (lua.eval("vehicle.fillUnits[2].fillLevel"),
                                               lua.eval("tostring(vehicle.spec_cropHarvester.unloading)")))
    ok &= check("grain arrived in the tip station", lua.eval("stationFill") > 1000,
                "%.0f l" % lua.eval("stationFill"))
    ok &= check("unload target name is reported",
                lua.eval("targetWhileUnloading") == "Silo",
                lua.eval("tostring(targetWhileUnloading)"))

    # ---- beam focus -------------------------------------------------------
    lua.execute("""
    vehicle:setUFOCirclePattern(CropHarvester.getPatternCount())
    vehicle:setUFOPenRadius(3.0)
    """)
    ok &= check("pen focus can be widened to 3 m",
                abs(lua.eval("vehicle:getUFOCircleRadius()") - 3.0) < 1e-6)
    lua.execute("vehicle:setUFOPenRadius(99)")
    ok &= check("pen focus is clamped to 15 m",
                abs(lua.eval("vehicle:getUFOCircleRadius()") - 15.0) < 1e-6)
    lua.execute("vehicle:setUFOPenRadius(0.25)")

    # ---- cockpit instruments follow the state ----------------------------
    lua.execute("""
    vehicle:setUFOCirclePattern(1)
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ptr = lua.eval("world.translation[30]")
    ok &= check("pattern pointer sits on the first tile",
                ptr is not None and abs(ptr[1] + 0.15) < 1e-6 and abs(ptr[2] - 0.045) < 1e-6,
                "translation=%s" % (ptr,))
    lua.execute("""
    vehicle:setUFOCirclePattern(7)
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ptr = lua.eval("world.translation[30]")
    ok &= check("pattern pointer moves to the second row",
                ptr is not None and abs(ptr[1] - 0.0) < 0.08 and abs(ptr[2] + 0.03) < 1e-6,
                "translation=%s" % (ptr,))

    # ---- v7: mode dial, field work, cargo hold --------------------------
    lua.execute("""
    vehicle:setUFOAltitude(30)
    for i = 1, 200 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    vehicle:setUFOCirclePattern(1)
    vehicle.fillUnits[2].fillLevel = 0
    """)
    ok &= check("eight modes are defined", lua.eval("#CropHarvester.MODES") == 8)

    # the mode key cycles through all eight and wraps around
    lua.execute("""
    vehicle:setUFOBeamMode(1)
    seen = {}
    for i = 1, 8 do
        seen[i] = vehicle:getUFOBeamMode()
        CropHarvester.runCommand(vehicle, "mode")
    end
    """)
    ok &= check("mode key cycles through all eight modes",
                [lua.eval("seen[%d]" % i) for i in range(1, 9)] == list(range(1, 9)))
    ok &= check("mode wraps around to flatten", lua.eval("vehicle:getUFOBeamMode()") == 1)

    # cultivate / plow / sow / fertilize all work the ground
    for mode, key, label in ((3, "cultivate", "cultivate"),
                             (4, "plow", "plow"),
                             (5, "sow", "sow"),
                             (6, "spray", "fertilize")):
        lua.execute("""
        vehicle:setUFOBeamMode(%d)
        worked.cultivate, worked.plow, worked.sow, worked.spray, worked.calls = 0, 0, 0, 0, 0
        vehicle:setUFOBeamActive(true)
        for i = 1, 120 do
            g_currentMission.time = g_currentMission.time + 16
            callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        end
        """ % mode)
        area = lua.eval("worked.%s" % key)
        ok &= check("%s mode works the field" % label, area > 100,
                    "%.0f m2" % area)
        ok &= check("%s mode does not press crop circles" % label,
                    lua.eval("mown.count") == 0)

    # the right beam cone is the visible one
    lua.execute("""
    vehicle:setUFOBeamMode(4)
    vehicle:setUFOBeamActive(true)
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ok &= check("plow mode shows the orange cone only",
                lua.eval("world.visibility[53]") is True and
                lua.eval("world.visibility[50]") is False)
    ok &= check("beam light takes the mode colour", lua.eval(
        "world.lightColor ~= nil and math.abs(world.lightColor[21][3] - 1.0) < 0.01"
        " and math.abs(world.lightColor[21][1] - 0.62) < 0.01"))
    needle = lua.eval("world.rotation[33]")
    ok &= check("mode needle points at the selected segment",
                needle is not None and abs(needle[2] + 135) < 1e-6,
                "rotation=%s" % (needle,))

    # sowing uses the selected seed and the keys can change it
    lua.execute("""
    vehicle:setUFOBeamMode(5)
    CropHarvester.runCommand(vehicle, "penDown")
    """)
    ok &= check("sowing mode: keys pick the next seed",
                lua.eval("vehicle.spec_cropHarvester.sowFruitIndex") == 15,
                "index %s" % lua.eval("vehicle.spec_cropHarvester.sowFruitIndex"))
    ok &= check("sowing mode does not change the pen radius",
                abs(lua.eval("vehicle:getUFOPenRadius()") - 0.5) < 1e-6)

    # ---- cargo hold: load from a trailer by hovering ---------------------
    lua.execute("""
    trailer = newVehicle()
    trailer.isServer = true
    trailer.components = { { node = 2 } }
    trailer.fillUnits = { { fillType = 1, fillLevel = 12000, capacity = 20000 } }
    trailer.getFillUnitSupportsFillType = function(self, i, fillType) return true end
    trailer.getName = function() return "Kipper" end
    g_currentMission.vehicleSystem = {
        getVehicles = function() return { vehicle, trailer } end,
    }
    world.nodes = { [1] = { 0, 20, 0 }, [2] = { 0, 0, 0 } }
    vehicle.fillUnits[3].fillLevel = 0
    vehicle:setUFOBeamMode(7)
    vehicle:setUFOBeamActive(true)
    for i = 1, 600 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_cropHarvester.loadTargetName ~= "" then
            loadName = vehicle.spec_cropHarvester.loadTargetName
        end
    end
    """)
    ok &= check("load mode sucks the trailer empty",
                lua.eval("trailer.fillUnits[1].fillLevel") < 100,
                "%.0f l left in the trailer" % lua.eval("trailer.fillUnits[1].fillLevel"))
    ok &= check("the cargo hold took the load",
                lua.eval("vehicle.fillUnits[3].fillLevel") > 5000,
                "%.0f l in the hold" % lua.eval("vehicle.fillUnits[3].fillLevel"))
    ok &= check("load target name is reported",
                lua.eval("loadName") == "Kipper", lua.eval("tostring(loadName)"))

    # ---- unload mode pours the cargo hold back out -----------------------
    lua.execute("""
    stationFill = 0
    trailer.fillUnits[1].fillLevel = 20000          -- full: the silo has to take it
    world.nodes[stationNode] = { 0, 0, 0 }
    vehicle:setUFOBeamMode(8)
    vehicle:setUFOBeamActive(true)
    for i = 1, 800 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("unload mode empties the cargo hold",
                lua.eval("vehicle.fillUnits[3].fillLevel") < 100,
                "%.0f l left" % lua.eval("vehicle.fillUnits[3].fillLevel"))
    ok &= check("the unloaded goods arrived",
                lua.eval("stationFill") > 5000, "%.0f l" % lua.eval("stationFill"))
    ok &= check("leaving unload mode stops unloading",
                lua.eval("vehicle.spec_cropHarvester.unloading") is False)

    # ---- mode sounds -----------------------------------------------------
    lua.execute("""
    vehicle.spec_cropHarvester.sounds = { modeSwitch = "beep", beamLoop = "hum",
                                   loadLoop = "load", unloadLoop = "pour" }
    vehicle.spec_cropHarvester.soundState = { beam = false, load = false, unload = false }
    vehicle:setUFOBeamMode(3)
    vehicle:setUFOBeamActive(true)
    sounds.played = {}
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ok &= check("working beam starts its hum loop", lua.eval("#sounds.played") >= 1,
                "%d sample(s)" % lua.eval("#sounds.played"))
    lua.execute("""
    vehicle:setUFOBeamActive(false)
    callEvent(vehicle, "onUpdate", 1/60, true, true, true)
    """)
    ok &= check("beam off stops the hum loop", lua.eval("#sounds.stopped") >= 1)

    # ---- overridden getCanMotorRun ---------------------------------------
    can = lua.eval("callOverwritten(vehicle, 'getCanMotorRun')")
    ok &= check("getCanMotorRun overwrite callable", can is True)

    print("\n%s" % ("all Lua smoke tests passed" if ok else "LUA SMOKE TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
