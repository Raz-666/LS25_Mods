#!/usr/bin/env python3
"""Head-less smoke test for scripts/UFO2000.lua.

The game cannot be started here, so this mocks the handful of GIANTS engine
functions the flight code touches and runs the specialization through a short
flight: take off, climb, fly a circle, descend, land.  It catches typos, nil
indexing, NaN maths and multiplayer-stream mistakes before the mod ever reaches
the game.

      python tools/ufo/luatest.py        (needs the 'lupa' package)
"""

import math
import os
import sys

from lupa import LuaRuntime

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LUA = os.path.join(REPO, "FS25_UFO2000", "scripts", "UFO2000.lua")

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
nodeIds = { leg0 = 11, leg1 = 12, leg2 = 13, beamNode = 20, beamLight = 21,
            beaconLight = 22, groundRing = 23, driverSeatNode = 24 }

function getWorldTranslation(node) return world.x, world.y, world.z end
function getTranslation(node) return 0, 0, 0 end
function getRotation(node) return 0, 0, 16 end
function getWorldRotation(node) return world.pitch, world.yaw, world.roll end
function setRotation(node, a, b, c)
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

-- density map mock: records the mown rectangles
mown = { count = 0, area = 0 }
FSDensityMapUtil = {
    getFruitTypeIndexAtWorldPos = function(x, z) return 2, 4 end,
    updateMowerArea = function(fruitIndex, x1, z1, x2, z1b, x1b, z2, limitToField)
        local w = math.abs(x2 - x1)
        local h = math.abs(z2 - z1)
        mown.count = mown.count + 1
        mown.area = mown.area + w * h
        return 0, 0
    end,
}
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
    UFO2000.registerFunctions(vehicleType)
    -- GIANTS adds the registered functions to the vehicle class; the mock does
    -- the same on the shared metatable
    for name, fn in pairs(_G.functions or {}) do
        vehicle_mt[name] = function(self, ...) return fn(self, ...) end
    end
    UFO2000.registerOverwrittenFunctions(vehicleType)
    UFO2000.registerEventListeners(vehicleType)
    """)

    lua.execute("""
    vehicle = newVehicle()
    vehicle.spec_ufo2000 = {}
    callEvent(vehicle, "onLoad", nil)
    """)

    def check(name, cond, extra=""):
        print(("  ok    " if cond else "  ERROR ") + name + ((" " + extra) if extra else ""))
        return cond

    ok = True
    spec = lua.eval("vehicle.spec_ufo2000")
    ok &= check("legs found", lua.eval("#vehicle.spec_ufo2000.legNodes") == 3)
    ok &= check("beam node found", lua.eval("vehicle.spec_ufo2000.beamNode") == 11 + 9)
    ok &= check("beam hidden at load", lua.eval("world.visibility[20]") is False)
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
    hov = lua.eval("vehicle.spec_ufo2000.isHovering")
    alt = lua.eval("vehicle.spec_ufo2000.altitude")
    y = lua.eval("world.y")
    ok &= check("hovering after key press", hov is True)
    ok &= check("climbed off the ground", y > 2.6, "y=%.2f" % y)
    ok &= check("altitude reached target", abs(alt - lua.eval("vehicle.spec_ufo2000.altitudeTarget")) < 0.5,
                "alt=%.2f" % alt)
    ok &= check("legs folded away", lua.eval("vehicle.spec_ufo2000.legsAlpha") > 0.9,
                "alpha=%.2f" % lua.eval("vehicle.spec_ufo2000.legsAlpha"))

    # ---- climb with the ascend key ----------------------------------------
    lua.execute("""
    vehicle.spec_ufo2000.digitalUp = true
    for i = 1, 300 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    vehicle.spec_ufo2000.digitalUp = false
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
    speed = lua.eval("vehicle.spec_ufo2000.speed")
    yaw = lua.eval("vehicle.spec_ufo2000.yaw")
    x, z = lua.eval("world.x"), lua.eval("world.z")
    ok &= check("accelerated forward", speed > 6.0, "v=%.2f m/s" % speed)
    ok &= check("steering turns the craft", abs(yaw) > 20, "yaw=%.1f" % yaw)
    ok &= check("moved horizontally", math.hypot(x, z) > 5, "dist=%.1f" % math.hypot(x, z))

    # NaN check on every numeric state
    for name in ("altitude", "yaw", "speed", "pitch", "roll"):
        v = lua.eval("vehicle.spec_ufo2000.%s" % name)
        ok &= check("no NaN in %s" % name, v == v and abs(v) < 1e6)

    # ---- beam toggle -------------------------------------------------------
    lua.execute("vehicle:setUFOBeamActive(true)")
    ok &= check("beam visible", lua.eval("world.visibility[20]") is True)
    ok &= check("beam light visible", lua.eval("world.visibility[21]") is True)

    # ---- multiplayer update stream ----------------------------------------
    lua.execute("""
    local s = newStream()
    s.obj = vehicle
    callEvent(vehicle, "onWriteUpdateStream", s, { getIsServer = function() return true end }, vehicle.dirtyFlags)
    callEvent(vehicle, "onReadUpdateStream", s, 0, { getIsServer = function() return true end })
    local s2 = newStream()
    vehicle.spec_ufo2000.axisValue = -1
    vehicle.spec_ufo2000.verticalDirty = true
    callEvent(vehicle, "onWriteUpdateStream", s2, { getIsServer = function() return false end }, 0)
    vehicle.spec_ufo2000.axisValue = 0
    callEvent(vehicle, "onReadUpdateStream", s2, 0, { getIsServer = function() return false end })
    """)
    ok &= check("update stream round trip", abs(lua.eval("vehicle.spec_ufo2000.axisValue") + 1) < 0.01)
    lua.execute("vehicle.spec_ufo2000.axisValue = 0")

    # ---- descend and land -------------------------------------------------
    lua.execute("""
    vehicle.spec_drivable.axisForward = 0
    vehicle.spec_drivable.axisSide = 0
    vehicle.spec_ufo2000.digitalDown = true
    for i = 1, 1500 do
        world.time = world.time + 1/60
        g_currentMission.time = world.time * 1000
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if not vehicle.spec_ufo2000.isHovering then break end
    end
    vehicle.spec_ufo2000.digitalDown = false
    """)
    ok &= check("landed back on the ground", lua.eval("vehicle.spec_ufo2000.isHovering") is False,
                "y=%.2f" % lua.eval("world.y"))
    ok &= check("beam switches off when landing",
                lua.eval("vehicle.spec_ufo2000.beamActive") is False)

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
    alt = lua.eval("vehicle.spec_ufo2000.altitude")
    expected = alt * math.tan(math.radians(34.0))
    ok &= check("beam radius follows the altitude", abs(radius - expected) < 0.01,
                "r=%.2f at %.1f m" % (radius, alt))

    lua.execute("""
    UFO2000.actionEventMenu(vehicle, "ufo_menu", 1, nil)
    """)
    ok &= check("menu opens", lua.eval("vehicle.spec_ufo2000.menuOpen") is True)
    before = lua.eval("vehicle.spec_ufo2000.patternIndex")
    lua.execute("UFO2000.actionEventAltitudeUp(vehicle, 'ufo_altitudeUp', 1, nil)")
    after = lua.eval("vehicle.spec_ufo2000.patternIndex")
    ok &= check("pattern can be picked in the menu", after == (before % 9) + 1,
                "%d -> %d" % (before, after))
    heightBefore = lua.eval("vehicle.spec_ufo2000.altitudeTarget")
    ok &= check("menu keys do not change the altitude",
                abs(lua.eval("vehicle.spec_ufo2000.altitudeTarget") - heightBefore) < 1e-9)

    # selected pattern 1 = full circle: mown area has to be about pi r^2
    lua.execute("vehicle:setUFOCirclePattern(1)")
    lua.execute("""
    mown.count, mown.area = 0, 0
    UFO2000.actionEventBeam(vehicle, "ufo_menu", 1, nil)   -- menu was open: fires
    """)
    ok &= check("beam fires from the menu", lua.eval("vehicle.spec_ufo2000.beamActive") is True)
    ok &= check("menu closes on fire", lua.eval("vehicle.spec_ufo2000.menuOpen") is False)
    spans = lua.eval("#(vehicle.spec_ufo2000.drawQueue or {})")
    ok &= check("pattern broken into slices", spans > 10, "%d slices" % spans)

    lua.execute("""
    for i = 1, 600 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_ufo2000.drawQueue == nil then break end
    end
    """)
    area = lua.eval("mown.area")
    cells = lua.eval("mown.count")
    want = math.pi * radius * radius
    ok &= check("mowing finished", lua.eval("vehicle.spec_ufo2000.drawQueue") is None,
                "%d rectangles" % cells)
    ok &= check("circle area matches pi r^2", abs(area - want) / want < 0.10,
                "%.0f m2 vs %.0f m2" % (area, want))
    ok &= check("progress reported to clients", lua.eval("vehicle.spec_ufo2000.drawProgress") == 1)

    # ring pattern mows less than a filled circle
    lua.execute("""
    vehicle:setUFOCirclePattern(2)
    mown.count, mown.area = 0, 0
    vehicle:setUFOBeamActive(false)
    vehicle:setUFOBeamActive(true)
    for i = 1, 600 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if vehicle.spec_ufo2000.drawQueue == nil then break end
    end
    """)
    ringArea = lua.eval("mown.area")
    ok &= check("ring mows less than the filled circle", area * 0.5 < ringArea < area * 0.95,
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

    # ---- legs: fold in when flying, unfold when landing -------------------
    lua.execute("""
    vehicle.spec_ufo2000.digitalDown = true
    for i = 1, 2000 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
        if not vehicle.spec_ufo2000.isHovering then break end
    end
    vehicle.spec_ufo2000.digitalDown = false
    for i = 1, 400 do
        g_currentMission.time = g_currentMission.time + 16
        callEvent(vehicle, "onUpdateTick", 1/60, true, true, true)
    end
    """)
    ok &= check("landed", lua.eval("vehicle.spec_ufo2000.isHovering") is False,
                "y=%.2f" % lua.eval("world.y"))
    ok &= check("landing legs are deployed again", lua.eval("vehicle.spec_ufo2000.legsAlpha") < 0.02,
                "alpha=%.3f" % lua.eval("vehicle.spec_ufo2000.legsAlpha"))
    ok &= check("beam stopped on landing", lua.eval("world.visibility[20]") is False)

    # ---- overridden getCanMotorRun ---------------------------------------
    can = lua.eval("callOverwritten(vehicle, 'getCanMotorRun')")
    ok &= check("getCanMotorRun overwrite callable", can is True)

    print("\n%s" % ("all Lua smoke tests passed" if ok else "LUA SMOKE TESTS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
