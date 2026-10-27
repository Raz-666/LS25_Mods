--[[
UFO 2000 - hover flight and crop circle specialization.

The vanilla vehicle stack (Drivable / Motorized / Enterable) keeps handling the
engine, fuel, HUD, cameras, honking and enter/leave.  This specialization adds
what a base game vehicle cannot do:

  * hover flight with a damped hover cushion - the craft can stand still in the
    air without any input, so it is easy to fly with keyboard or joystick
  * altitude control with the stock front loader arm axis, the stock "lower
    implement" action and a normal key binding
  * retractable landing legs, a rotating beacon and a beam that reaches exactly
    down to the ground
  * crop circle patterns: the beam sweeps the field below and leaves a mown
    pattern - select the geometry in the on-board menu (key M) and fire the
    beam (stock "implement extra" action, Z)
  * eight working modes, all of them invisible: flatten, harvest, cultivate,
    plow, sow, fertilize, load and unload.  Each mode has its own coloured beam
    cone, its own light colour, its own hum and its own little cockpit lamp
  * a virtual cargo hold: hover over a trailer to suck its load in, hover over
    a trailer or tip station to pour it out again

Everything that changes the world (mowing, hover state) is done on the server.
Clients send their input through events / update streams, so multiplayer works.

The file has no dependency on any other mod. Loaded from modDesc.xml.
This tracked file is the canonical source copied into UFO 2000 and renamed by
build_crop_harvester_mod.py for the independent Crop Harvester release.
--]]

UFO2000 = {}
local UFO2000_mt = Class(UFO2000, Specialization)

UFO2000.ALTITUDE_SEND_BITS = 8
UFO2000.ALTITUDE_MAX_SEND = 255
UFO2000.PROGRESS_MAX_SEND = 255

-- flight tuning -------------------------------------------------------------
UFO2000.MAX_ALTITUDE = 120.0        -- m above ground
UFO2000.MIN_ALTITUDE = 1.10         -- hover height with the legs folded in
UFO2000.CLIMB_SPEED = 6.5           -- m/s with a fully deflected axis
UFO2000.YAW_SPEED = 55.0            -- deg/s at full steering input
UFO2000.MAX_SPEED = 8.5             -- m/s (~31 km/h) horizontal flight
UFO2000.LEG_RETRACT_TIME = 1.4      -- s for the legs to fold in / out
UFO2000.HOVER_ACCEL = 2.6           -- how quickly the height follows the target
UFO2000.SPEED_ACCEL = 2.4

-- crop circle tuning --------------------------------------------------------
UFO2000.BEAM_HALF_ANGLE = 34.0      -- degrees; matches the visible cone
UFO2000.MIN_CIRCLE_RADIUS = 1.8     -- m
UFO2000.MAX_CIRCLE_RADIUS = 70.0    -- m
UFO2000.CIRCLE_CELL = 0.35          -- m, finest raster of the pressed pattern
UFO2000.CIRCLE_DRAW_TIME = 3.2      -- s until the pattern is finished

-- manual pen: narrow beam, the player draws by flying
UFO2000.MANUAL_RADIUS = 0.25        -- m, half of the 50 cm pen
UFO2000.MANUAL_STEP = 0.22          -- m of flight per stamped dot

-- beam modes ---------------------------------------------------------------
UFO2000.BEAM_MODE_DAMAGE = 1        -- press the crop down (crop circles)
UFO2000.BEAM_MODE_HARVEST = 2       -- cut and thresh the crop into the tank
UFO2000.HARVEST_TANK_INDEX = 2      -- fill unit 2 of ufo.xml is the grain tank
UFO2000.HARVEST_MANUAL_STEP = 0.9   -- s between two cuts in pen mode
UFO2000.HARVEST_STEP = 0.5          -- s between two cuts in circle mode
UFO2000.HARVEST_SPEED = 1200.0      -- l/s the beam can thresh at most
UFO2000.MIN_HARVEST_STATE = 1       -- growth state that can be cut

-- v7: the full set of working modes -----------------------------------------
-- 1 flatten (crop circles) 2 harvest 3 cultivate 4 plow 5 sow 6 fertilize
-- 7 load (suction) 8 unload (pour)
UFO2000.BEAM_MODE_CULTIVATE = 3
UFO2000.BEAM_MODE_PLOW = 4
UFO2000.BEAM_MODE_SOW = 5
UFO2000.BEAM_MODE_FERTILIZE = 6
UFO2000.BEAM_MODE_LOAD = 7
UFO2000.BEAM_MODE_UNLOAD = 8
UFO2000.MODE_COUNT = 8

--- one table with everything the rest of the script needs per mode:
--- the i3d node of its beam cone, its label and the colour of its light.
UFO2000.MODES = {
    {id = 1, node = "beamNodeDamage", text = "ufo_mode_damage",
     light = {1.00, 0.22, 0.16}, work = false},
    {id = 2, node = "beamNodeHarvest", text = "ufo_mode_harvest",
     light = {0.35, 1.00, 0.42}, work = false},
    {id = 3, node = "beamNodeCultivate", text = "ufo_mode_cultivate",
     light = {0.98, 0.62, 0.28}, work = true},
    {id = 4, node = "beamNodePlow", text = "ufo_mode_plow",
     light = {1.00, 0.45, 0.10}, work = true},
    {id = 5, node = "beamNodeSow", text = "ufo_mode_sow",
     light = {0.72, 1.00, 0.25}, work = true},
    {id = 6, node = "beamNodeFertilize", text = "ufo_mode_fertilize",
     light = {0.72, 0.45, 1.00}, work = true},
    {id = 7, node = "beamNodeLoad", text = "ufo_mode_load",
     light = {0.30, 0.70, 1.00}, work = false},
    {id = 8, node = "beamNodeUnload", text = "ufo_mode_unload",
     light = {0.35, 1.00, 1.00}, work = false},
}

function UFO2000.getModeInfo(id)
    return UFO2000.MODES[UFO2000.clamp(id or 1, 1, #UFO2000.MODES)]
end

-- field work pacing ----------------------------------------------------------
UFO2000.FIELD_STEP = 0.4            -- s between two passes over the field
UFO2000.SOW_FRUITS = { "WHEAT", "BARLEY", "OAT", "CANOLA", "MAIZE", "SUNFLOWER",
    "SOYBEAN", "RYE", "TRITICALE", "SPELT", "POTATO", "SUGARBEET", "SORGHUM",
    "COTTON", "GRASS" }

-- virtual cargo hold: fill unit 3 of ufo.xml, large enough for a whole field
UFO2000.CARGO_TANK_INDEX = 3
UFO2000.LOAD_RANGE = 16.0           -- m horizontal distance to the source
UFO2000.LOAD_MIN_HEIGHT = 1.8       -- m, keep the saucer above the trailer
UFO2000.LOAD_SPEED = 6000.0         -- l/s the beam can suck up


-- beam focus (radius of the beam on the ground) ----------------------------
UFO2000.PEN_MIN_RADIUS = 0.25       -- 50 cm pen
UFO2000.PEN_MAX_RADIUS = 8.00       -- a really fat beam
UFO2000.PEN_RADIUS_STEP = 0.25

-- unloading: hover above a trailer or a tip station and press the unload key
UFO2000.UNLOAD_RANGE = 15.0         -- m horizontal distance
UFO2000.UNLOAD_MIN_HEIGHT = 1.8     -- m, keep the saucer above the trailer
UFO2000.UNLOAD_SPEED = 3000.0       -- l/s

-- optional second beam: while the green harvest beam is working, the narrow
-- offset beam feeds the grain tank into a truck, trailer or other fill unit.
UFO2000.HARVEST_TRAILER_SPEED = 4500.0 -- l/s delivered to a nearby vehicle
UFO2000.HARVEST_TRAILER_OFFSET = 3.0   -- m to the right of the main beam
UFO2000.HARVEST_TRAILER_RANGE = 6.0    -- m from the beam axis to a trailer root
UFO2000.HARVEST_TRAILER_RADIUS = 0.85  -- m, narrow visible transfer beam

-- physical-object transport -------------------------------------------------
-- One dynamic object at a time. The beam accepts only cargo whose collision
-- bounds and mass can be measured, then enforces these hard limits.
UFO2000.PHYSICAL_CARGO_ENABLED = true
UFO2000.PHYSICAL_CARGO_MAX_MASS = 12000.0 -- kg
UFO2000.PHYSICAL_CARGO_MAX_WIDTH = 4.5    -- m, local X
UFO2000.PHYSICAL_CARGO_MAX_HEIGHT = 4.0   -- m, local Y
UFO2000.PHYSICAL_CARGO_MAX_LENGTH = 8.0   -- m, local Z
UFO2000.PHYSICAL_CARGO_MAX_PICKUP_ALTITUDE = 18.0 -- m above local terrain
UFO2000.PHYSICAL_CARGO_SCAN_WIDTH = 5.0  -- m
UFO2000.PHYSICAL_CARGO_SCAN_HEIGHT = 4.5 -- m
UFO2000.PHYSICAL_CARGO_HOLD_CLEARANCE = 1.0 -- m below the saucer
UFO2000.PHYSICAL_CARGO_GROUND_CLEARANCE = 0.75 -- m

UFO2000.PHYSICAL_CARGO_STATUS = {
    IDLE = 0, HELD = 1, RELEASED = 2, NEED_HOVER = 3, BEAM_OFF = 4,
    NO_TARGET = 5, TOO_HEAVY = 6, TOO_LARGE = 7, LOWER_TO_RELEASE = 8,
    DETACH_FIRST = 9, SAFE_DROP = 10, TOO_HIGH = 11,
}

UFO2000.PHYSICAL_CARGO_STATUS_TEXT = {
    [UFO2000.PHYSICAL_CARGO_STATUS.HELD] = "ufo_notify_cargoHeld",
    [UFO2000.PHYSICAL_CARGO_STATUS.RELEASED] = "ufo_notify_cargoReleased",
    [UFO2000.PHYSICAL_CARGO_STATUS.NEED_HOVER] = "ufo_notify_cargoNeedHover",
    [UFO2000.PHYSICAL_CARGO_STATUS.BEAM_OFF] = "ufo_notify_cargoBeamOff",
    [UFO2000.PHYSICAL_CARGO_STATUS.NO_TARGET] = "ufo_notify_cargoNoTarget",
    [UFO2000.PHYSICAL_CARGO_STATUS.TOO_HEAVY] = "ufo_notify_cargoTooHeavy",
    [UFO2000.PHYSICAL_CARGO_STATUS.TOO_LARGE] = "ufo_notify_cargoTooLarge",
    [UFO2000.PHYSICAL_CARGO_STATUS.LOWER_TO_RELEASE] = "ufo_notify_cargoLowerToRelease",
    [UFO2000.PHYSICAL_CARGO_STATUS.DETACH_FIRST] = "ufo_notify_cargoDetachFirst",
    [UFO2000.PHYSICAL_CARGO_STATUS.SAFE_DROP] = "ufo_notify_cargoSafeDrop",
    [UFO2000.PHYSICAL_CARGO_STATUS.TOO_HIGH] = "ufo_notify_cargoTooHigh",
}

-- marks the craft leaves on the ground when it takes off / lands
UFO2000.LANDING_MARK_RADIUS = 1.9   -- m, the flattened pad under the hull
UFO2000.LEG_MARK_RADIUS = 0.30      -- m, one footprint per leg

UFO2000.clamp = function(value, minValue, maxValue)
    if value < minValue then
        return minValue
    elseif maxValue < value then
        return maxValue
    end
    return value
end

-- ---------------------------------------------------------------------------
-- crop circle patterns
-- every test() gets normalised coordinates in [-1, 1] and returns true if the
-- crop at that spot is mown
-- ---------------------------------------------------------------------------
local function radiusOf(u, v)
    return math.sqrt(u * u + v * v)
end

local function pointSegmentDistance(px, pz, ax, az, bx, bz)
    local dx, dz = bx - ax, bz - az
    local lengthSq = dx * dx + dz * dz
    local t = 0
    if lengthSq > 0 then
        t = UFO2000.clamp(((px - ax) * dx + (pz - az) * dz) / lengthSq, 0, 1)
    end
    local cx, cz = ax + dx * t, az + dz * t
    return math.sqrt((px - cx) * (px - cx) + (pz - cz) * (pz - cz))
end

local function patternCircle(u, v)
    return radiusOf(u, v) <= 1.0
end

local function patternRing(u, v)
    local r = radiusOf(u, v)
    return 0.44 <= r and r <= 1.0
end

local function patternTripleRing(u, v)
    local r = radiusOf(u, v)
    return (0.14 <= r and r <= 0.27) or (0.44 <= r and r <= 0.57) or (0.74 <= r and r <= 0.87)
end

local function patternSpiral(u, v)
    local r = radiusOf(u, v)
    if 1.0 < r then
        return false
    end
    local angle = math.atan2(u, v) -- -pi .. pi
    angle = angle / (2 * math.pi) + 0.5 -- 0 .. 1
    local arm = (angle * 3 + r * 1.35) % 1.0
    return arm <= 0.42
end

local function patternFlower(u, v)
    local r = radiusOf(u, v)
    if 1.0 < r then
        return false
    end
    local angle = math.atan2(u, v)
    local petal = 0.28 + 0.68 * math.abs(math.cos(3 * angle))
    return r <= petal
end

local function patternStar(u, v)
    if 1.02 < radiusOf(u, v) then
        return false
    end
    -- pentagram: five lines from point i to point i + 2
    for i = 0, 4 do
        local a1 = math.pi / 2 + i * 2 * math.pi / 5
        local a2 = math.pi / 2 + ((i + 2) % 5) * 2 * math.pi / 5
        local ax, az = math.cos(a1), math.sin(a1)
        local bx, bz = math.cos(a2), math.sin(a2)
        if pointSegmentDistance(u, v, ax, az, bx, bz) < 0.075 then
            return true
        end
    end
    return false
end

local function patternAlien(u, v)
    -- outer ring
    local r = radiusOf(u, v)
    if 0.94 <= r and r <= 1.0 then
        return true
    end
    -- two big eyes
    for _, sx in ipairs({-1, 1}) do
        local eu, ev = (u - 0.36 * sx) / 0.24, (v - 0.18) / 0.15
        if eu * eu + ev * ev <= 1.0 then
            return true
        end
    end
    -- smile (arc below the eyes)
    local mu, mv = u, v - 0.05
    local mr = math.sqrt(mu * mu + mv * mv)
    return 0.42 <= mr and mr <= 0.48 and 0.33 < v
end

local function patternFlowerOfLife(u, v)
    if 1.02 < radiusOf(u, v) then
        return false
    end
    -- seven circles: one in the middle, six around it
    if math.abs(radiusOf(u, v) - 0.52) < 0.045 then
        return true
    end
    for i = 0, 5 do
        local a = i * math.pi / 3
        local cx, cz = 0.52 * math.cos(a), 0.52 * math.sin(a)
        local du, dv = u - cx, v - cz
        if math.abs(math.sqrt(du * du + dv * dv) - 0.52) < 0.045 then
            return true
        end
    end
    return false
end

local function patternSun(u, v)
    local r = radiusOf(u, v)
    if 1.0 < r then
        return false
    end
    if 0.62 <= r and r <= 0.80 then
        return true
    end
    if r <= 0.24 then
        return true
    end
    -- twelve tapered rays from the ring to the outer edge
    if 0.80 < r then
        local angle = math.atan2(u, v)
        local ray = (angle + math.pi) * 12 / (2 * math.pi)
        local delta = math.abs(ray - math.floor(ray + 0.5)) * 2 * math.pi / 12
        local width = 0.075 - 0.045 * (r - 0.80) / 0.20
        if delta < width then
            return true
        end
    end
    return false
end

--- The last entry is the manual pen: no fixed shape, the beam is bundled into a
--- thin column and the player paints by flying.
local MANUAL_PATTERN = {name = "ufo_circle_manual", manual = true}

UFO2000.PATTERNS = {
    {name = "ufo_circle_circle", test = patternCircle},
    {name = "ufo_circle_ring", test = patternRing},
    {name = "ufo_circle_tripleRing", test = patternTripleRing},
    {name = "ufo_circle_spiral", test = patternSpiral},
    {name = "ufo_circle_flower", test = patternFlower},
    {name = "ufo_circle_star", test = patternStar},
    {name = "ufo_circle_alien", test = patternAlien},
    {name = "ufo_circle_flowerOfLife", test = patternFlowerOfLife},
    {name = "ufo_circle_sun", test = patternSun},
    MANUAL_PATTERN,
}

function UFO2000.getPatternCount()
    return #UFO2000.PATTERNS
end

--- true if the given pattern index is the manual pen
function UFO2000.isManual(patternIndex)
    local pattern = UFO2000.PATTERNS[patternIndex]
    return pattern ~= nil and pattern.manual == true
end

--- true if the crop at the normalised position belongs to the pattern
function UFO2000.isPointInPattern(patternIndex, u, v)
    local pattern = UFO2000.PATTERNS[patternIndex]
    if pattern == nil or pattern.test == nil then
        return false
    end
    return pattern.test(u, v)
end

-- ---------------------------------------------------------------------------
-- registration
-- ---------------------------------------------------------------------------
function UFO2000.prerequisitesPresent(specializations)
    return true
end

--- Looks a node up by its i3dMappings id.
function UFO2000.getNode(vehicle, name)
    local mappings = vehicle.i3dMappings
    if mappings == nil then
        return nil
    end
    for i = 1, #mappings do
        if mappings[i].id == name then
            return mappings[i].node
        end
    end
    return nil
end

function UFO2000.registerFunctions(vehicleType)
    SpecializationUtil.registerFunction(vehicleType, "getUFOIsHovering", UFO2000.getUFOIsHovering)
    SpecializationUtil.registerFunction(vehicleType, "setUFOIsHovering", UFO2000.setUFOIsHovering)
    SpecializationUtil.registerFunction(vehicleType, "getUFOAltitude", UFO2000.getUFOAltitude)
    SpecializationUtil.registerFunction(vehicleType, "setUFOAltitude", UFO2000.setUFOAltitude)
    SpecializationUtil.registerFunction(vehicleType, "getUFOHasBeamActive", UFO2000.getUFOHasBeamActive)
    SpecializationUtil.registerFunction(vehicleType, "setUFOBeamActive", UFO2000.setUFOBeamActive)
    SpecializationUtil.registerFunction(vehicleType, "getUFOCirclePattern", UFO2000.getUFOCirclePattern)
    SpecializationUtil.registerFunction(vehicleType, "setUFOCirclePattern", UFO2000.setUFOCirclePattern)
    SpecializationUtil.registerFunction(vehicleType, "getUFOCircleRadius", UFO2000.getUFOCircleRadius)
    SpecializationUtil.registerFunction(vehicleType, "showUFOStartHint", UFO2000.showUFOStartHint)
    SpecializationUtil.registerFunction(vehicleType, "getUFOBeamMode", UFO2000.getUFOBeamMode)
    SpecializationUtil.registerFunction(vehicleType, "setUFOBeamMode", UFO2000.setUFOBeamMode)
    SpecializationUtil.registerFunction(vehicleType, "getUFOPenRadius", UFO2000.getUFOPenRadius)
    SpecializationUtil.registerFunction(vehicleType, "setUFOPenRadius", UFO2000.setUFOPenRadius)
    SpecializationUtil.registerFunction(vehicleType, "getUFOInfiniteTank", UFO2000.getUFOInfiniteTank)
    SpecializationUtil.registerFunction(vehicleType, "setUFOInfiniteTank", UFO2000.setUFOInfiniteTank)
end

function UFO2000.registerOverwrittenFunctions(vehicleType)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getCanMotorRun", UFO2000.getCanMotorRun)
    -- The virtual cargo hold is intentionally universal: let it accept every
    -- fill type registered by the current game / installed mods. Other fill
    -- units keep their normal restrictions.
    SpecializationUtil.registerOverwrittenFunction(vehicleType,
        "getFillUnitSupportsFillType", UFO2000.getFillUnitSupportsFillType)
end

function UFO2000.registerEventListeners(vehicleType)
    SpecializationUtil.registerEventListener(vehicleType, "onLoad", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onDelete", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onReadStream", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onWriteStream", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onReadUpdateStream", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onWriteUpdateStream", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onUpdate", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onUpdateTick", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onRegisterActionEvents", UFO2000)
    SpecializationUtil.registerEventListener(vehicleType, "onLeaveVehicle", UFO2000)
end

-- ---------------------------------------------------------------------------
-- load / delete
-- ---------------------------------------------------------------------------
function UFO2000:onLoad(savegame)
    local spec = self.spec_ufo2000

    spec.maxAltitude = UFO2000.MAX_ALTITUDE
    spec.minAltitude = UFO2000.MIN_ALTITUDE
    spec.climbSpeed = UFO2000.CLIMB_SPEED
    spec.yawSpeed = UFO2000.YAW_SPEED
    spec.maxSpeed = UFO2000.MAX_SPEED
    spec.legSpeed = 1 / UFO2000.LEG_RETRACT_TIME
    spec.beamTan = math.tan(math.rad(UFO2000.BEAM_HALF_ANGLE))

    spec.isHovering = false
    spec.altitude = spec.minAltitude
    spec.altitudeTarget = spec.minAltitude
    spec.hoverY = nil
    spec.yaw = 0
    spec.pitch = 0
    spec.roll = 0
    spec.speed = 0
    spec.axisValue = 0
    spec.digitalUp = false
    spec.digitalDown = false
    spec.legsTarget = 0
    spec.legsAlpha = 0

    spec.inputVertical = 0
    spec.verticalDirty = false
    spec.beamActive = false
    spec.patternIndex = 1
    spec.menuOpen = false
    spec.drawProgress = 0
    spec.drawQueue = nil
    spec.drawIndex = 0
    spec.drawTotal = 0
    spec.lastRadius = 0

    -- v6: harvest / unload / beam focus -----------------------------------
    spec.beamMode = UFO2000.BEAM_MODE_DAMAGE
    spec.penRadius = UFO2000.MANUAL_RADIUS
    spec.infiniteTank = false
    spec.harvestTimer = 0
    spec.harvesting = false
    spec.lastHarvestLiters = 0
    spec.harvestFruitName = ""
    spec.harvestToTrailer = false
    spec.directTargetName = ""
    spec.unloadTimer = 0
    spec.unloading = false
    spec.unloadTargetName = ""
    spec.unloadedTotal = 0

    -- v7: field work, cargo hold and mode sounds ---------------------------
    spec.workTimer = 0
    spec.working = false
    spec.lastWorkArea = 0
    spec.sowFruitIndex = 1
    spec.loading = false
    spec.loadTargetName = ""
    spec.loadedTotal = 0

    -- Runtime-only physical object cargo; it is restored to physics on release.
    spec.physicalCargo = nil
    spec.physicalCargoName = ""
    spec.physicalCargoMass = 0
    spec.physicalCargoStatus = UFO2000.PHYSICAL_CARGO_STATUS.IDLE
    spec.physicalCargoStatusSequence = 0

    spec.legNodes = {}
    spec.legRestRotation = {}
    for i = 0, 2 do
        local node = UFO2000.getNode(self, "leg" .. i)
        if node ~= nil then
            table.insert(spec.legNodes, node)
            table.insert(spec.legRestRotation, select(3, getRotation(node)))
        end
    end

    spec.patternPointer = UFO2000.getNode(self, "patternPointer")
    spec.modeLever = UFO2000.getNode(self, "modeLever")
    spec.modeNeedle = UFO2000.getNode(self, "modeNeedle")
    spec.focusSlider = UFO2000.getNode(self, "focusSlider")

    -- one cone per mode: only the one of the selected mode is ever visible
    spec.beamNodes = {}
    for i = 1, #UFO2000.MODES do
        local node = UFO2000.getNode(self, UFO2000.MODES[i].node)
        spec.beamNodes[i] = node
        if node ~= nil then
            setVisibility(node, false)
            setScale(node, 1, 1, 1)
        end
    end
    spec.transferBeamNode = UFO2000.getNode(self, "transferBeamNode")
    if spec.transferBeamNode ~= nil then
        setVisibility(spec.transferBeamNode, false)
    end
    spec.beamLight = UFO2000.getNode(self, "beamLight")
    spec.beaconLight = UFO2000.getNode(self, "beaconLight")
    spec.ringNode = UFO2000.getNode(self, "groundRing")

    if spec.beamLight ~= nil then
        setVisibility(spec.beamLight, false)
    end
    if spec.ringNode ~= nil then
        setVisibility(spec.ringNode, false)
    end

    UFO2000.loadModeSounds(self)

    spec.dirtyFlag = self:getNextDirtyFlag()
    spec.actionEvents = {}

    -- on board menu needs a draw callback once per frame
    UFO2000.addToDrawables(self)

    -- the craft has no wheels, so Drivable would divide by zero steering times
    if self.minRotTime == nil or self.minRotTime == 0 then
        self.minRotTime = -0.001
    end
    if self.maxRotTime == nil or self.maxRotTime == 0 then
        self.maxRotTime = 0.001
    end

    spec.hintShown = false
end

function UFO2000:onDelete()
    if self.isServer then
        UFO2000.releasePhysicalCargo(self, true)
    end
    UFO2000.removeFromDrawables(self)
end

function UFO2000.addToDrawables(vehicle)
    local spec = vehicle.spec_ufo2000
    if g_currentMission ~= nil and spec.drawable == nil then
        spec.drawable = {draw = function() UFO2000.drawHud(vehicle) end}
        g_currentMission:addDrawable(spec.drawable)
    end
end

function UFO2000.removeFromDrawables(vehicle)
    local spec = vehicle.spec_ufo2000
    if g_currentMission ~= nil and spec ~= nil and spec.drawable ~= nil then
        g_currentMission:removeDrawable(spec.drawable)
        spec.drawable = nil
    end
end

-- ---------------------------------------------------------------------------
-- network
-- ---------------------------------------------------------------------------
function UFO2000:onReadStream(streamId, connection)
    local spec = self.spec_ufo2000
    spec.isHovering = streamReadBool(streamId)
    spec.altitude = streamReadUIntN(streamId, UFO2000.ALTITUDE_SEND_BITS) / UFO2000.ALTITUDE_MAX_SEND * spec.maxAltitude
    spec.beamActive = streamReadBool(streamId)
    spec.patternIndex = streamReadUIntN(streamId, 4)
    spec.drawProgress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
    spec.beamMode = streamReadUIntN(streamId, 3)
    spec.penRadius = streamReadUIntN(streamId, 6) * UFO2000.PEN_RADIUS_STEP
    spec.infiniteTank = streamReadBool(streamId)
    spec.sowFruitIndex = streamReadUIntN(streamId, 4)
    spec.harvestToTrailer = streamReadBool(streamId)
    spec.unloading = streamReadBool(streamId)
    spec.loading = streamReadBool(streamId)
    spec.loadTargetName = streamReadString(streamId)
    spec.unloadTargetName = streamReadString(streamId)
    spec.directTargetName = streamReadString(streamId)
    spec.physicalCargoName = streamReadString(streamId)
    spec.physicalCargoMass = streamReadFloat32(streamId)
    spec.physicalCargoStatus = streamReadUIntN(streamId, 4)
    spec.physicalCargoStatusSequence = streamReadUIntN(streamId, 8)
    UFO2000.applyState(self)
end

function UFO2000:onWriteStream(streamId, connection)
    local spec = self.spec_ufo2000
    streamWriteBool(streamId, spec.isHovering)
    local altitude = math.floor(UFO2000.clamp(spec.altitude / spec.maxAltitude, 0, 1) * UFO2000.ALTITUDE_MAX_SEND + 0.5)
    streamWriteUIntN(streamId, altitude, UFO2000.ALTITUDE_SEND_BITS)
    streamWriteBool(streamId, spec.beamActive)
    streamWriteUIntN(streamId, spec.patternIndex, 4)
    streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
    streamWriteUIntN(streamId, spec.beamMode, 3)
    streamWriteUIntN(streamId, math.floor(spec.penRadius / UFO2000.PEN_RADIUS_STEP + 0.5), 6)
    streamWriteBool(streamId, spec.infiniteTank)
    streamWriteUIntN(streamId, spec.sowFruitIndex or 1, 4)
    streamWriteBool(streamId, spec.harvestToTrailer == true)
    streamWriteBool(streamId, spec.unloading == true)
    streamWriteBool(streamId, spec.loading == true)
    streamWriteString(streamId, spec.loadTargetName or "")
    streamWriteString(streamId, spec.unloadTargetName or "")
    streamWriteString(streamId, spec.directTargetName or "")
    streamWriteString(streamId, spec.physicalCargoName or "")
    streamWriteFloat32(streamId, spec.physicalCargoMass or 0)
    streamWriteUIntN(streamId, spec.physicalCargoStatus or 0, 4)
    streamWriteUIntN(streamId, spec.physicalCargoStatusSequence or 0, 8)
end

function UFO2000:onReadUpdateStream(streamId, timestamp, connection)
    local spec = self.spec_ufo2000
    if connection:getIsServer() then
        if streamReadBool(streamId) then
            local hovering = streamReadBool(streamId)
            local altitude = streamReadUIntN(streamId, UFO2000.ALTITUDE_SEND_BITS) / UFO2000.ALTITUDE_MAX_SEND * spec.maxAltitude
            local beam = streamReadBool(streamId)
            local pattern = streamReadUIntN(streamId, 4)
            local progress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
            local mode = streamReadUIntN(streamId, 3)
            local penRadius = streamReadUIntN(streamId, 6) * UFO2000.PEN_RADIUS_STEP
            local infinite = streamReadBool(streamId)
            local sowFruitIndex = streamReadUIntN(streamId, 4)
            local harvestToTrailer = streamReadBool(streamId)
            local unloading = streamReadBool(streamId)
            local loading = streamReadBool(streamId)
            local loadTargetName = streamReadString(streamId)
            local unloadTargetName = streamReadString(streamId)
            local directTargetName = streamReadString(streamId)
            local physicalCargoName = streamReadString(streamId)
            local physicalCargoMass = streamReadFloat32(streamId)
            local physicalCargoStatus = streamReadUIntN(streamId, 4)
            local physicalCargoStatusSequence = streamReadUIntN(streamId, 8)
            local physicalCargoStatusChanged = physicalCargoStatusSequence
                ~= spec.physicalCargoStatusSequence
            local changed = hovering ~= spec.isHovering or beam ~= spec.beamActive
                or mode ~= spec.beamMode or harvestToTrailer ~= spec.harvestToTrailer
                or physicalCargoName ~= spec.physicalCargoName
            spec.isHovering = hovering
            spec.altitude = altitude
            spec.beamActive = beam
            spec.patternIndex = pattern
            spec.drawProgress = progress
            spec.beamMode = mode
            spec.penRadius = penRadius
            spec.infiniteTank = infinite
            spec.sowFruitIndex = sowFruitIndex
            spec.harvestToTrailer = harvestToTrailer
            spec.unloading = unloading
            spec.loading = loading
            spec.loadTargetName = loadTargetName
            spec.unloadTargetName = unloadTargetName
            spec.directTargetName = directTargetName
            spec.physicalCargoName = physicalCargoName
            spec.physicalCargoMass = physicalCargoMass
            spec.physicalCargoStatus = physicalCargoStatus
            spec.physicalCargoStatusSequence = physicalCargoStatusSequence
            if changed then
                UFO2000.applyState(self)
            end
            if physicalCargoStatusChanged then
                UFO2000.notifyPhysicalCargoStatus(self, physicalCargoStatus)
            end
        end
    else
        if streamReadBool(streamId) then
            spec.axisValue = streamReadIntN(streamId, 4) / 7
        end
    end
end

function UFO2000:onWriteUpdateStream(streamId, connection, dirtyMask)
    local spec = self.spec_ufo2000
    if connection:getIsServer() then
        if streamWriteBool(streamId, bit32.band(dirtyMask, spec.dirtyFlag) ~= 0) then
            streamWriteBool(streamId, spec.isHovering)
            local altitude = math.floor(UFO2000.clamp(spec.altitude / spec.maxAltitude, 0, 1) * UFO2000.ALTITUDE_MAX_SEND + 0.5)
            streamWriteUIntN(streamId, altitude, UFO2000.ALTITUDE_SEND_BITS)
            streamWriteBool(streamId, spec.beamActive)
            streamWriteUIntN(streamId, spec.patternIndex, 4)
            streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
            streamWriteUIntN(streamId, spec.beamMode, 3)
            streamWriteUIntN(streamId, math.floor(spec.penRadius / UFO2000.PEN_RADIUS_STEP + 0.5), 6)
            streamWriteBool(streamId, spec.infiniteTank)
            streamWriteUIntN(streamId, spec.sowFruitIndex or 1, 4)
            streamWriteBool(streamId, spec.harvestToTrailer == true)
            streamWriteBool(streamId, spec.unloading == true)
            streamWriteBool(streamId, spec.loading == true)
            streamWriteString(streamId, spec.loadTargetName or "")
            streamWriteString(streamId, spec.unloadTargetName or "")
            streamWriteString(streamId, spec.directTargetName or "")
            streamWriteString(streamId, spec.physicalCargoName or "")
            streamWriteFloat32(streamId, spec.physicalCargoMass or 0)
            streamWriteUIntN(streamId, spec.physicalCargoStatus or 0, 4)
            streamWriteUIntN(streamId, spec.physicalCargoStatusSequence or 0, 8)
        end
    else
        if streamWriteBool(streamId, spec.verticalDirty) then
            streamWriteIntN(streamId, math.floor(UFO2000.clamp(spec.axisValue, -1, 1) * 7 + 0.5), 4)
            spec.verticalDirty = false
        end
    end
end

-- ---------------------------------------------------------------------------
-- state (server authoritative)
-- ---------------------------------------------------------------------------
function UFO2000:getUFOIsHovering()
    return self.spec_ufo2000.isHovering
end

function UFO2000:getUFOAltitude()
    return self.spec_ufo2000.altitude
end

function UFO2000:getUFOHasBeamActive()
    return self.spec_ufo2000.beamActive
end

function UFO2000:getUFOCirclePattern()
    return self.spec_ufo2000.patternIndex
end

function UFO2000:setUFOCirclePattern(index)
    local spec = self.spec_ufo2000
    spec.patternIndex = ((index - 1) % UFO2000.getPatternCount()) + 1
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
end

--- radius of the circle that the beam covers right now
function UFO2000:getUFOCircleRadius()
    local spec = self.spec_ufo2000
    if UFO2000.isManual(spec.patternIndex) then
        -- the pen: the beam stays bundled instead of opening into a cone,
        -- but the pilot can widen or narrow it with the focus keys
        return spec.penRadius or UFO2000.MANUAL_RADIUS
    end
    local radius = spec.altitude * spec.beamTan
    return UFO2000.clamp(radius, UFO2000.MIN_CIRCLE_RADIUS, UFO2000.MAX_CIRCLE_RADIUS)
end

function UFO2000:setUFOAltitude(altitude)
    local spec = self.spec_ufo2000
    altitude = UFO2000.clamp(altitude, spec.minAltitude, spec.maxAltitude)
    if math.abs(altitude - spec.altitudeTarget) > 0.01 then
        spec.altitudeTarget = altitude
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
end

function UFO2000:setUFOIsHovering(hovering)
    local spec = self.spec_ufo2000
    if hovering == spec.isHovering then
        return
    end
    if not hovering and spec.physicalCargo ~= nil then
        UFO2000.setPhysicalCargoStatus(self, UFO2000.PHYSICAL_CARGO_STATUS.LOWER_TO_RELEASE)
        return
    end
    if not self.isServer then
        return
    end

    if hovering then
        if self.getIsMotorStarted ~= nil and not self:getIsMotorStarted() then
            return
        end
        local cx, cy, cz = getWorldTranslation(self.components[1].node)
        spec.yaw = select(2, getWorldRotation(self.components[1].node))
        local groundY = getTerrainHeightAtWorldPos(g_terrainNode, cx, 0, cz)
        spec.altitude = math.max(spec.minAltitude, cy - groundY)
        spec.altitudeTarget = math.max(spec.altitude, 3.0)
        spec.hoverY = cy
        spec.speed = 0
        spec.isHovering = true
        -- the cushion and the legs leave their trace in the field
        UFO2000.stampLandingMarks(self)
    else
        spec.isHovering = false
        spec.altitude = spec.minAltitude
        spec.altitudeTarget = spec.minAltitude
        spec.hoverY = nil
        spec.speed = 0
        -- landed: the beam switches itself off and the craft leaves its mark
        spec.beamActive = false
        UFO2000.setLoadingState(self, false, "")
        UFO2000.stopDrawing(self)
        UFO2000.setDirectTargetName(self, "")
        UFO2000.stampLandingMarks(self)
    end
    self:raiseDirtyFlags(spec.dirtyFlag)
    UFO2000.applyState(self)
end

--- 1 = flatten, 2 = harvest, 3 = cultivate, 4 = plow, 5 = sow,
--- 6 = fertilize, 7 = load, 8 = unload
function UFO2000:getUFOBeamMode()
    return self.spec_ufo2000.beamMode
end

--- the l10n key of the current mode (for the HUD)
function UFO2000:getUFOBeamModeText()
    return UFO2000.getModeInfo(self.spec_ufo2000.beamMode).text
end

function UFO2000:setUFOBeamMode(mode)
    local spec = self.spec_ufo2000
    mode = UFO2000.clamp(math.floor((mode or 1) + 0.5), 1, UFO2000.MODE_COUNT)
    local changed = mode ~= spec.beamMode
    spec.beamMode = mode
    spec.harvestTimer = 0
    spec.workTimer = 0
    spec.loadTimer = 0
    -- only the unload mode unloads by itself
    if changed and mode ~= UFO2000.BEAM_MODE_UNLOAD then
        UFO2000.setUnloadingState(self, false)
    end
    if changed and mode ~= UFO2000.BEAM_MODE_LOAD then
        UFO2000.setLoadingState(self, false, "")
    end
    if mode ~= UFO2000.BEAM_MODE_HARVEST then
        UFO2000.setDirectTargetName(self, "")
    end
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
    if changed then
        UFO2000.playModeSound(self)
        UFO2000.applyState(self)
    end
end


function UFO2000:getUFOPenRadius()
    return self.spec_ufo2000.penRadius
end

--- beam focus: 0.25 m (a 50 cm pen) up to a 16 m wide beam
function UFO2000:setUFOPenRadius(radius)
    local spec = self.spec_ufo2000
    radius = UFO2000.clamp(radius, UFO2000.PEN_MIN_RADIUS, UFO2000.PEN_MAX_RADIUS)
    radius = math.floor(radius / UFO2000.PEN_RADIUS_STEP + 0.5) * UFO2000.PEN_RADIUS_STEP
    spec.penRadius = radius
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
end

function UFO2000:getUFOInfiniteTank()
    return self.spec_ufo2000.infiniteTank
end

function UFO2000:setUFOInfiniteTank(infinite)
    local spec = self.spec_ufo2000
    spec.infiniteTank = infinite == true
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
end

function UFO2000:setUFOBeamActive(active)
    local spec = self.spec_ufo2000
    if not active then
        UFO2000.stopDrawing(self)
        UFO2000.setDirectTargetName(self, "")
        UFO2000.setLoadingState(self, false, "")
    end
    if spec.beamActive == active then
        return
    end
    spec.beamActive = active
    if active and self.isServer and spec.isHovering then
        UFO2000.startDrawing(self)
    end
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
    UFO2000.applyState(self)
end

--- applies synced state to the local scene (clients, too)
function UFO2000.applyState(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec == nil then
        return
    end
    spec.legsTarget = spec.isHovering and 1 or 0
    if spec.beamNodes ~= nil then
        for i = 1, #spec.beamNodes do
            local node = spec.beamNodes[i]
            if node ~= nil then
                setVisibility(node, spec.beamActive and i == spec.beamMode)
            end
        end
    end
    if spec.beamLight ~= nil then
        setVisibility(spec.beamLight, spec.beamActive)
        local info = UFO2000.getModeInfo(spec.beamMode)
        setLightColor(spec.beamLight, info.light[1], info.light[2], info.light[3])
    end
    if spec.ringNode ~= nil then
        setVisibility(spec.ringNode, spec.beamActive)
    end
    if not spec.beamActive then
        UFO2000.stopDrawing(vehicle)
    end
end

-- ---------------------------------------------------------------------------
-- crop circles
-- ---------------------------------------------------------------------------
--- presses the crop inside one rectangle down (server side).
--- updateWheelDestructionArea is the vanilla "a wheel rolled over the field"
--- effect: the plants are flattened and lose their yield, the field itself and
--- its fruit stay intact - exactly the trace a landing saucer would leave.
function UFO2000.damageArea(x1, z1, x2, z2)
    if FSDensityMapUtil == nil or FSDensityMapUtil.updateWheelDestructionArea == nil then
        return false
    end
    FSDensityMapUtil.updateWheelDestructionArea(x1, z1, x2, z1, x1, z2)
    return true
end

--- builds the list of rectangles for a pattern around a world position
function UFO2000.buildSpans(cx, cz, radius, patternIndex)
    local cell = math.max(UFO2000.CIRCLE_CELL, radius / 80)
    local spans = {}

    local v = -radius
    while v <= radius do
        local u = -radius
        local spanStart = nil
        local lastU = nil
        while u <= radius + 0.0001 do
            local inside = UFO2000.isPointInPattern(patternIndex, u / radius, v / radius)
            if inside and spanStart == nil then
                spanStart = u
            elseif not inside and spanStart ~= nil then
                local x2 = lastU + cell
                table.insert(spans, {
                    x1 = cx + spanStart, z1 = cz + v,
                    x2 = cx + x2, z2 = cz + v + cell,
                    distSq = (spanStart + x2) * (spanStart + x2) / 4 + v * v,
                })
                spanStart = nil
            end
            lastU = u
            u = u + cell
        end
        if spanStart ~= nil then
            table.insert(spans, {
                x1 = cx + spanStart, z1 = cz + v,
                x2 = cx + radius, z2 = cz + v + cell,
                distSq = v * v,
            })
        end
        v = v + cell
    end

    -- from the centre outwards, so the pattern appears to grow
    table.sort(spans, function(a, b) return a.distSq < b.distSq end)
    return spans
end

function UFO2000.startDrawing(vehicle)
    local spec = vehicle.spec_ufo2000
    spec.drawIndex = 0
    spec.drawProgress = 0
    spec.lastPaint = nil
    if UFO2000.isManual(spec.patternIndex) then
        -- nothing precomputed: the pen paints while the craft moves
        spec.drawQueue = nil
        spec.drawTotal = 0
        return
    end
    local radius = vehicle:getUFOCircleRadius()
    local cx, _, cz = getWorldTranslation(vehicle.components[1].node)
    spec.drawQueue = UFO2000.buildSpans(cx, cz, radius, spec.patternIndex)
    spec.drawTotal = #spec.drawQueue
    spec.lastRadius = radius
    if spec.drawTotal == 0 then
        spec.drawQueue = nil
    end
end

function UFO2000.stopDrawing(vehicle)
    local spec = vehicle.spec_ufo2000
    spec.drawQueue = nil
    spec.drawIndex = 0
    spec.drawTotal = 0
    spec.drawProgress = 0
    spec.lastPaint = nil
end

--- the manual pen: presses a 50 cm dot onto the field below the craft
function UFO2000.paintManual(vehicle)
    local spec = vehicle.spec_ufo2000
    local node = vehicle.components[1].node
    local px, _, pz = getWorldTranslation(node)

    if spec.lastPaint ~= nil then
        local dx, dz = px - spec.lastPaint[1], pz - spec.lastPaint[2]
        if dx * dx + dz * dz < UFO2000.MANUAL_STEP * UFO2000.MANUAL_STEP then
            return
        end
    end
    spec.lastPaint = {px, pz}

    local r = vehicle:getUFOCircleRadius()
    if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
        UFO2000.harvestArea(vehicle, px - r, pz - r, px + r, pz + r)
    else
        UFO2000.damageArea(px - r, pz - r, px + r, pz + r)
    end
end

-- ---------------------------------------------------------------------------
-- harvest mode
-- ---------------------------------------------------------------------------
--- Is the grain tank too full to take more crop?
function UFO2000.getTankIsFull(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec.infiniteTank then
        return false
    end
    local fillUnitIndex = UFO2000.HARVEST_TANK_INDEX
    if vehicle.getFillUnitFreeCapacity == nil then
        return false
    end
    local fruitType, _ = FSDensityMapUtil.getFruitTypeIndexAtWorldPos(
        select(1, getWorldTranslation(vehicle.components[1].node)),
        select(3, getWorldTranslation(vehicle.components[1].node)))
    if fruitType == nil then
        return false
    end
    local desc = g_fruitTypeManager:getFruitTypeByIndex(fruitType)
    local fillTypeIndex = desc ~= nil and desc.fillType or nil
    if fillTypeIndex == nil then
        return false
    end
    return vehicle:getFillUnitFreeCapacity(fillUnitIndex, fillTypeIndex,
        vehicle:getOwnerFarmId()) <= 1
end

--- Cuts the crop inside one rectangle and puts the grain into the tank.
--- cutFruitArea is the very function the vanilla cutter uses, so field state,
--- spray level, weeds and growth stages all behave exactly like a header.
function UFO2000.harvestArea(vehicle, x1, z1, x2, z2)
    local spec = vehicle.spec_ufo2000
    if FSDensityMapUtil == nil or FSDensityMapUtil.cutFruitArea == nil then
        return 0
    end
    local cx, cz = (x1 + x2) * 0.5, (z1 + z2) * 0.5
    local fruitIndex = FSDensityMapUtil.getFruitTypeIndexAtWorldPos(cx, cz)
    if fruitIndex == nil then
        spec.harvestFruitName = ""
        return 0
    end

    local desc = g_fruitTypeManager:getFruitTypeByIndex(fruitIndex)
    if desc == nil then
        return 0
    end
    spec.harvestFruitName = desc.name or ""

    local fillTypeIndex = desc.fillType
    if fillTypeIndex == nil or not g_fillTypeManager:getFillTypeByIndex(fillTypeIndex) then
        return 0
    end

    if UFO2000.getTankIsFull(vehicle) then
        return 0
    end

    local area = FSDensityMapUtil.cutFruitArea(fruitIndex, x1, z1,
        x2 - x1, 0, 0, z2 - z1, true, false, nil, false)
    if area == nil or area <= 0 then
        return 0
    end

    local liters = desc:getAreaLiters(area)
    if spec.infiniteTank then
        -- endless tank: the grain vanishes into the saucer's own little
        -- wormhole, but the field is harvested for real
        spec.lastHarvestLiters = liters
        return liters
    end

    local added = vehicle:addFillUnitFillLevel(vehicle:getOwnerFarmId(),
        UFO2000.HARVEST_TANK_INDEX, liters, fillTypeIndex, ToolType.UNDEFINED, nil)
    spec.lastHarvestLiters = added
    return added
end

--- Runs a few cutting passes along the beam rectangle while the beam is on.
function UFO2000.updateHarvest(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    if spec.beamMode ~= UFO2000.BEAM_MODE_HARVEST or spec.unloading then
        -- nothing is harvested while the tank is being emptied
        spec.harvesting = false
        return
    end
    spec.harvestTimer = spec.harvestTimer - dt
    if spec.harvestTimer > 0 then
        return
    end
    local manual = UFO2000.isManual(spec.patternIndex)
    spec.harvestTimer = manual and UFO2000.HARVEST_MANUAL_STEP or UFO2000.HARVEST_STEP

    local cx, _, cz = getWorldTranslation(vehicle.components[1].node)
    local radius = vehicle:getUFOCircleRadius()
    -- split the circle into a few strips so the edge is not jagged
    local strips = math.max(1, math.min(4, math.ceil(radius / 2.0)))
    local total = 0
    local h = 2 * radius / strips
    for i = 0, strips - 1 do
        local z1 = cz - radius + i * h
        -- half width of the circle at this z offset, so the beam stays round
        local dz = z1 + h * 0.5 - cz
        local halfWidth = math.sqrt(math.max(0, radius * radius - dz * dz))
        if halfWidth > 0.05 then
            total = total + UFO2000.harvestArea(vehicle,
                cx - halfWidth, z1, cx + halfWidth, z1 + h)
        end
    end
    spec.harvesting = total > 0
end

-- ---------------------------------------------------------------------------
-- field work modes: cultivate, plow, sow, fertilize
-- ---------------------------------------------------------------------------
function UFO2000.getFruitIndexByName(name)
    if g_fruitTypeManager == nil then
        return nil
    end
    if g_fruitTypeManager.getFruitTypeIndexByName ~= nil then
        return g_fruitTypeManager:getFruitTypeIndexByName(name)
    end
    local desc = g_fruitTypeManager:getFruitTypeByName(name)
    return desc ~= nil and desc.index or nil
end

function UFO2000.getSprayTypeIndex(name)
    if g_sprayTypeManager == nil then
        return nil
    end
    local sprayType = g_sprayTypeManager:getSprayTypeByName(name)
    return sprayType ~= nil and sprayType.index or nil
end

--- One rectangle of field work. Every call here is the vanilla function the
--- matching machine uses, so the field looks exactly like real work.
function UFO2000.workArea(vehicle, mode, x1, z1, x2, z2)
    if FSDensityMapUtil == nil then
        return 0
    end
    local w, h = x2 - x1, z2 - z1
    if w <= 0.01 or h <= 0.01 then
        return 0
    end
    local area = 0
    if mode == UFO2000.BEAM_MODE_CULTIVATE then
        if FSDensityMapUtil.updateCultivatorArea ~= nil then
            area = FSDensityMapUtil.updateCultivatorArea(x1, z1, w, 0, 0, h,
                false, true, 0, nil, false, true) or 0
        end
    elseif mode == UFO2000.BEAM_MODE_PLOW then
        if FSDensityMapUtil.updatePlowArea ~= nil then
            area = FSDensityMapUtil.updatePlowArea(x1, z1, w, 0, 0, h,
                false, true, 0, true, true) or 0
        end
    elseif mode == UFO2000.BEAM_MODE_SOW then
        if FSDensityMapUtil.updateSowingArea ~= nil then
            local spec = vehicle.spec_ufo2000
            local name = UFO2000.SOW_FRUITS[spec.sowFruitIndex] or "WHEAT"
            local fruitIndex = UFO2000.getFruitIndexByName(name)
            if fruitIndex ~= nil then
                area = FSDensityMapUtil.updateSowingArea(fruitIndex, x1, z1, w, 0, 0, h,
                    nil, false, 0, nil, nil) or 0
            end
        end
    elseif mode == UFO2000.BEAM_MODE_FERTILIZE then
        if FSDensityMapUtil.updateSprayArea ~= nil then
            local sprayTypeIndex = UFO2000.getSprayTypeIndex("fertilizer")
            if sprayTypeIndex ~= nil then
                area = FSDensityMapUtil.updateSprayArea(x1, z1, w, 0, 0, h,
                    sprayTypeIndex, 1.0) or 0
            end
        end
    end
    return area
end

--- cuts the beam circle into strips and works the ground below the saucer
function UFO2000.updateFieldWork(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    local info = UFO2000.getModeInfo(spec.beamMode)
    if not info.work or spec.unloading then
        spec.working = false
        return
    end
    spec.workTimer = (spec.workTimer or 0) - dt
    if spec.workTimer > 0 then
        return
    end
    spec.workTimer = UFO2000.FIELD_STEP

    local cx, _, cz = getWorldTranslation(vehicle.components[1].node)
    local radius = vehicle:getUFOCircleRadius()
    local strips = math.max(1, math.min(5, math.ceil(radius / 2.0)))
    local h = 2 * radius / strips
    local total = 0
    for i = 0, strips - 1 do
        local z1 = cz - radius + i * h
        local dz = z1 + h * 0.5 - cz
        local halfWidth = math.sqrt(math.max(0, radius * radius - dz * dz))
        if halfWidth > 0.05 then
            total = total + UFO2000.workArea(vehicle, spec.beamMode,
                cx - halfWidth, z1, cx + halfWidth, z1 + h)
        end
    end
    spec.working = total > 0
    spec.lastWorkArea = total
end

-- ---------------------------------------------------------------------------
-- virtual cargo hold: load by hovering over a trailer, unload by hovering
-- ---------------------------------------------------------------------------
function UFO2000.getCargoFillUnitIndex(vehicle)
    if vehicle.getFillUnitCount == nil then
        return nil
    end
    if vehicle:getFillUnitCount() >= UFO2000.CARGO_TANK_INDEX then
        return UFO2000.CARGO_TANK_INDEX
    end
    return nil
end

--- the fill unit that currently holds something and should be emptied
function UFO2000.getLoadedFillUnitIndex(vehicle)
    local indices = { UFO2000.HARVEST_TANK_INDEX, UFO2000.CARGO_TANK_INDEX }
    for i = 1, #indices do
        local index = indices[i]
        if vehicle:getFillUnitCount() >= index
            and vehicle:getFillUnitFillLevel(index) > 1 then
            local fillType = vehicle:getFillUnitFillType(index)
            if fillType ~= nil and fillType ~= FillType.UNKNOWN then
                return index, fillType
            end
        end
    end
    return nil, nil
end

--- Finds a trailer below the saucer that has something the hold can take.
--- Returns the vehicle, its name, the fill unit index and the fill type.
function UFO2000.findLoadSource(vehicle)
    local cargoIndex = UFO2000.getCargoFillUnitIndex(vehicle)
    if cargoIndex == nil or g_currentMission == nil
        or g_currentMission.vehicleSystem == nil then
        return nil
    end
    local cx, cy, cz = getWorldTranslation(vehicle.components[1].node)
    local best, bestDist = nil, UFO2000.LOAD_RANGE * UFO2000.LOAD_RANGE
    local bestUnit, bestFillType, bestName = nil, nil, ""

    for _, other in pairs(g_currentMission.vehicleSystem:getVehicles()) do
        if other ~= vehicle and other.getFillUnitCount ~= nil
            and other.components ~= nil then
            local tx, ty, tz = getWorldTranslation(other.components[1].node)
            if ty <= cy - UFO2000.LOAD_MIN_HEIGHT then
                local dx, dz = tx - cx, tz - cz
                local dist = dx * dx + dz * dz
                if dist < bestDist then
                    for i = 1, other:getFillUnitCount() do
                        local fillLevel = other:getFillUnitFillLevel(i)
                        local fillType = other:getFillUnitFillType(i)
                        if fillLevel > 1 and fillType ~= nil
                            and fillType ~= FillType.UNKNOWN
                            and vehicle:getFillUnitSupportsFillType(cargoIndex, fillType) then
                            best, bestDist = other, dist
                            bestUnit, bestFillType = i, fillType
                            bestName = other.getName ~= nil and other:getName() or "Trailer"
                        end
                    end
                end
            end
        end
    end
    return best, bestName, bestUnit, bestFillType
end

--- sucks whatever is below the saucer into the cargo hold
function UFO2000.updateLoading(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    local cargoIndex = UFO2000.getCargoFillUnitIndex(vehicle)
    if cargoIndex == nil then
        return
    end
    local source, name, unit, fillType = UFO2000.findLoadSource(vehicle)
    if source == nil then
        UFO2000.setLoadingState(vehicle, false, "")
        return
    end
    local farmId = vehicle:getOwnerFarmId()
    local free = vehicle:getFillUnitFreeCapacity(cargoIndex, fillType, farmId)
    local available = source:getFillUnitFillLevel(unit)
    local amount = math.min(free, math.min(available, UFO2000.LOAD_SPEED * dt))
    if amount <= 1 then
        UFO2000.setLoadingState(vehicle, false, name)
        return
    end

    local taken = -source:addFillUnitFillLevel(farmId, unit, -amount,
        fillType, ToolType.LOADING, nil)
    if taken <= 0 then
        UFO2000.setLoadingState(vehicle, false, name)
        return
    end
    local added = vehicle:addFillUnitFillLevel(farmId, cargoIndex, taken,
        fillType, ToolType.LOADING, nil)
    if added < taken then
        -- the hold filled up in between: give the rest back
        source:addFillUnitFillLevel(farmId, unit, taken - added,
            fillType, ToolType.LOADING, nil)
    end
    UFO2000.setLoadingState(vehicle, added > 0, name)
    spec.loadedTotal = (spec.loadedTotal or 0) + added
end

-- ---------------------------------------------------------------------------
-- unloading by hovering
-- ---------------------------------------------------------------------------
--- Finds a trailer or a tip station below the saucer.
--- Returns the target object, its display name and whether it is a station.
function UFO2000.findUnloadTarget(vehicle, fillTypeIndex, centerX, centerZ,
        includeStations, searchRange)
    local cx, cy, cz = getWorldTranslation(vehicle.components[1].node)
    -- The secondary harvest beam is a little to one side of the main emitter.
    cx = centerX or cx
    cz = centerZ or cz
    local farmId = vehicle:getOwnerFarmId()
    local range = searchRange or UFO2000.UNLOAD_RANGE
    local best, bestDist = nil, range * range
    local bestName, bestIsStation = "", false

    local function consider(obj, node, name, isStation)
        if node == nil then
            return
        end
        local tx, ty, tz = getWorldTranslation(node)
        -- the saucer has to hover above the target, not next to it at the
        -- same height, otherwise it would collide with the trailer
        if ty > cy - UFO2000.UNLOAD_MIN_HEIGHT then
            return
        end
        local dx, dz = tx - cx, tz - cz
        local dist = dx * dx + dz * dz
        if dist < bestDist then
            best, bestDist = obj, dist
            bestName, bestIsStation = name or "", isStation
        end
    end

    -- 1. tip stations: the classic "hover over the yard" case
    if includeStations ~= false
        and g_currentMission ~= nil and g_currentMission.storageSystem ~= nil then
        for _, station in pairs(g_currentMission.storageSystem:getUnloadingStations()) do
            local allowed = station.getIsFillTypeAllowed ~= nil
                and station:getIsFillTypeAllowed(fillTypeIndex)
            local free = 0
            if allowed and station.getFreeCapacity ~= nil then
                free = station:getFreeCapacity(fillTypeIndex, farmId)
            end
            if free > 1 then
                local node = nil
                if station.unloadTriggers ~= nil then
                    for _, trigger in pairs(station.unloadTriggers) do
                        node = trigger.exactFillRootNode or trigger.triggerNode
                        if node ~= nil then
                            consider(station, node, station.stationName or "Tip station", true)
                        end
                    end
                end
                if node == nil then
                    consider(station, station.rootNode, station.stationName or "Tip station", true)
                end
            end
        end
    end

    -- 2. trailers standing below the saucer
    if g_currentMission ~= nil and g_currentMission.vehicleSystem ~= nil then
        for _, other in pairs(g_currentMission.vehicleSystem:getVehicles()) do
            if other ~= vehicle and other.getFillUnitCount ~= nil then
                for i = 1, other:getFillUnitCount() do
                    local supports = other.getFillUnitSupportsFillType ~= nil
                        and other:getFillUnitSupportsFillType(i, fillTypeIndex)
                    local free = 0
                    if supports and other.getFillUnitFreeCapacity ~= nil then
                        free = other:getFillUnitFreeCapacity(i, fillTypeIndex, farmId) or 0
                    end
                    if free > 1 and other.components ~= nil then
                        local name = other.getName ~= nil and other:getName() or "Trailer"
                        consider(other, other.components[1].node, name, false)
                    end
                    if best == other then
                        break
                    end
                end
            end
        end
    end
    return best, bestName, bestIsStation
end

--- Moves a limited amount from one UFO fill unit to a vehicle or tip station.
--- Any amount the destination refuses is put back into the source unit.
function UFO2000.transferFillToTarget(vehicle, fillUnitIndex, fillTypeIndex,
        target, isStation, requestedAmount)
    if target == nil or requestedAmount <= 0 then
        return 0
    end
    local farmId = vehicle:getOwnerFarmId()
    local amount = math.min(vehicle:getFillUnitFillLevel(fillUnitIndex), requestedAmount)
    if amount <= 0 then
        return 0
    end
    local taken = -vehicle:addFillUnitFillLevel(farmId, fillUnitIndex, -amount,
        fillTypeIndex, ToolType.UNLOADING, nil)
    if taken <= 0 then
        return 0
    end

    local moved = 0
    if isStation then
        if target.addFillLevelFromTool ~= nil then
            moved = target:addFillLevelFromTool(farmId, taken, fillTypeIndex, nil,
                ToolType.UNLOADING) or 0
        end
    elseif target.getFillUnitCount ~= nil then
        for i = 1, target:getFillUnitCount() do
            local supports = target.getFillUnitSupportsFillType ~= nil
                and target:getFillUnitSupportsFillType(i, fillTypeIndex)
            local free = supports and target.getFillUnitFreeCapacity ~= nil
                and target:getFillUnitFreeCapacity(i, fillTypeIndex, farmId) or 0
            if free > 1 then
                moved = target:addFillUnitFillLevel(farmId, i, taken, fillTypeIndex,
                    ToolType.UNLOADING, nil) or 0
                if moved > 0 then
                    break
                end
            end
        end
    end

    if moved < taken then
        vehicle:addFillUnitFillLevel(farmId, fillUnitIndex, taken - moved,
            fillTypeIndex, ToolType.UNLOADING, nil)
    end
    return moved
end

--- Moves grain from the saucer's tank into whatever is below it.
function UFO2000.updateUnloading(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    if not spec.unloading then
        return
    end
    -- first the grain tank, then the big cargo hold
    local fillUnitIndex, fillTypeIndex = UFO2000.getLoadedFillUnitIndex(vehicle)
    if fillUnitIndex == nil then
        UFO2000.setUnloadingState(vehicle, false)
        return
    end
    local fillLevel = vehicle:getFillUnitFillLevel(fillUnitIndex)

    local target, name, isStation = UFO2000.findUnloadTarget(vehicle, fillTypeIndex)
    if target == nil then
        UFO2000.setUnloadingState(vehicle, false)
        return
    end
    UFO2000.setUnloadTargetName(vehicle, name)

    local amount = math.min(fillLevel, UFO2000.UNLOAD_SPEED * dt)
    if amount <= 0 then
        UFO2000.setUnloadingState(vehicle, false)
        return
    end

    -- The helper restores any amount the destination did not accept.
    local moved = UFO2000.transferFillToTarget(vehicle, fillUnitIndex,
        fillTypeIndex, target, isStation, amount)
    if moved <= 0 then
        spec.unloadIdle = (spec.unloadIdle or 0) + dt
        if spec.unloadIdle > 1.0 then
            UFO2000.setUnloadingState(vehicle, false)
            spec.unloadIdle = 0
        end
        return
    end
    spec.unloadedTotal = spec.unloadedTotal + moved
    if moved > 0 then
        spec.unloadIdle = 0
    else
        spec.unloadIdle = (spec.unloadIdle or 0) + dt
        if spec.unloadIdle > 1.0 then
            UFO2000.setUnloadingState(vehicle, false)
            spec.unloadIdle = 0
        end
    end
end

--- World position of the narrow, offset second tractor beam used for filling
--- a truck or trailer while the primary beam stays in harvest mode.
function UFO2000.getHarvestTransferPosition(vehicle)
    local cx, _, cz = getWorldTranslation(vehicle.components[1].node)
    local yaw = math.rad(vehicle.spec_ufo2000.yaw or 0)
    return cx + math.cos(yaw) * UFO2000.HARVEST_TRAILER_OFFSET,
        cz - math.sin(yaw) * UFO2000.HARVEST_TRAILER_OFFSET
end

function UFO2000.setDirectTargetName(vehicle, name)
    local spec = vehicle.spec_ufo2000
    name = name or ""
    if spec.directTargetName ~= name then
        spec.directTargetName = name
        if vehicle.isServer then
            vehicle:raiseDirtyFlags(spec.dirtyFlag)
        end
    end
end

function UFO2000.setUnloadTargetName(vehicle, name)
    local spec = vehicle.spec_ufo2000
    name = name or ""
    if spec.unloadTargetName ~= name then
        spec.unloadTargetName = name
        if vehicle.isServer then
            vehicle:raiseDirtyFlags(spec.dirtyFlag)
        end
    end
end

function UFO2000.setUnloadingState(vehicle, active)
    local spec = vehicle.spec_ufo2000
    active = active == true
    if spec.unloading ~= active then
        spec.unloading = active
        if not active then
            UFO2000.setUnloadTargetName(vehicle, "")
        end
        if vehicle.isServer then
            vehicle:raiseDirtyFlags(spec.dirtyFlag)
        end
    end
end

function UFO2000.setLoadingState(vehicle, active, targetName)
    local spec = vehicle.spec_ufo2000
    active = active == true
    targetName = active and (targetName or "") or ""
    if spec.loading ~= active or spec.loadTargetName ~= targetName then
        spec.loading = active
        spec.loadTargetName = targetName
        if vehicle.isServer then
            vehicle:raiseDirtyFlags(spec.dirtyFlag)
        end
    end
end

function UFO2000.setHarvestToTrailer(vehicle, active)
    local spec = vehicle.spec_ufo2000
    active = active == true
    if spec.harvestToTrailer ~= active then
        spec.harvestToTrailer = active
        UFO2000.setDirectTargetName(vehicle, "")
        if vehicle.isServer then
            vehicle:raiseDirtyFlags(spec.dirtyFlag)
        end
    end
end

--- Feeds harvested grain from the UFO tank into the nearest fill unit under
--- the second beam. The main green beam keeps harvesting at the same time.
function UFO2000.updateHarvestToTrailer(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    if not spec.harvestToTrailer or spec.infiniteTank or spec.unloading
        or not spec.isHovering or not spec.beamActive
        or spec.beamMode ~= UFO2000.BEAM_MODE_HARVEST then
        UFO2000.setDirectTargetName(vehicle, "")
        return
    end

    local fillUnitIndex = UFO2000.HARVEST_TANK_INDEX
    local fillLevel = vehicle:getFillUnitFillLevel(fillUnitIndex)
    local fillTypeIndex = vehicle:getFillUnitFillType(fillUnitIndex)
    if fillLevel <= 1 or fillTypeIndex == nil or fillTypeIndex == FillType.UNKNOWN then
        UFO2000.setDirectTargetName(vehicle, "")
        return
    end

    local beamX, beamZ = UFO2000.getHarvestTransferPosition(vehicle)
    local target, name = UFO2000.findUnloadTarget(vehicle, fillTypeIndex,
        beamX, beamZ, false, UFO2000.HARVEST_TRAILER_RANGE)
    if target == nil then
        UFO2000.setDirectTargetName(vehicle, "")
        return
    end
    UFO2000.setDirectTargetName(vehicle, name)
    local moved = UFO2000.transferFillToTarget(vehicle, fillUnitIndex,
        fillTypeIndex, target, false, UFO2000.HARVEST_TRAILER_SPEED * dt)
    spec.unloadedTotal = (spec.unloadedTotal or 0) + moved
end

--- presses the next slice of the pattern into the field (server side)
function UFO2000.updateDrawing(vehicle, dt)
    local spec = vehicle.spec_ufo2000

    if spec.beamMode ~= UFO2000.BEAM_MODE_DAMAGE then
        -- only the flatten mode presses crop circles; harvest, the field work
        -- modes, loading and unloading never touch the plants that way
        spec.drawProgress = 1
        return
    end

    if UFO2000.isManual(spec.patternIndex) then
        UFO2000.paintManual(vehicle)
        spec.drawProgress = 1
        return
    end

    local queue = spec.drawQueue
    if queue == nil or spec.drawTotal == 0 then
        return
    end

    local perFrame = math.max(1, math.ceil(spec.drawTotal * dt / UFO2000.CIRCLE_DRAW_TIME))
    for i = 1, perFrame do
        spec.drawIndex = spec.drawIndex + 1
        local span = queue[spec.drawIndex]
        if span == nil then
            break
        end
        UFO2000.damageArea(span.x1, span.z1, span.x2, span.z2)
    end

    spec.drawProgress = UFO2000.clamp(spec.drawIndex / spec.drawTotal, 0, 1)
    vehicle:raiseDirtyFlags(spec.dirtyFlag)

    if spec.drawTotal <= spec.drawIndex then
        spec.drawQueue = nil
        spec.drawTotal = 0
        spec.drawProgress = 1
        vehicle:raiseDirtyFlags(spec.dirtyFlag)
    end
end

--- the cushion and the legs flatten a small pad into the field on every
--- take off and landing - the classic saucer trace
function UFO2000.stampLandingMarks(vehicle)
    local spec = vehicle.spec_ufo2000
    if FSDensityMapUtil == nil or FSDensityMapUtil.updateWheelDestructionArea == nil then
        return
    end

    local cx, _, cz = getWorldTranslation(vehicle.components[1].node)
    local spans = UFO2000.buildSpans(cx, cz, UFO2000.LANDING_MARK_RADIUS, 1)
    for i = 1, #spans do
        local span = spans[i]
        UFO2000.damageArea(span.x1, span.z1, span.x2, span.z2)
    end

    -- the feet dig in a little deeper around the hull
    local r = UFO2000.LEG_MARK_RADIUS
    for i = 1, #spec.legNodes do
        local lx, _, lz = getWorldTranslation(spec.legNodes[i])
        UFO2000.damageArea(lx - r, lz - r, lx + r, lz + r)
    end
end

--- little chat message so players find the controls
function UFO2000.showUFOStartHint(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec.hintShown then
        return
    end
    spec.hintShown = true
    if g_currentMission ~= nil and g_currentMission.hud ~= nil
        and vehicle.getIsEntered ~= nil and vehicle:getIsEntered() then
        g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
            g_i18n:getText("ufo_hint_controls"))
    end
end

--- Common, localized feedback for a user-initiated setting change.
local function notify(vehicle, textKey, ...)
    if g_currentMission == nil or g_currentMission.addIngameNotification == nil
        or vehicle.getIsEntered == nil or not vehicle:getIsEntered() then
        return
    end
    local text = g_i18n ~= nil and g_i18n:getText(textKey) or textKey
    local args = {...}
    if #args > 0 then
        local unpackArgs = table.unpack or unpack
        text = string.format(text, unpackArgs(args))
    end
    g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO, text)
end

--- Fill / fruit labels are localized when the game exposes a title, with the
--- registered internal name as a safe fallback for modded fill types.
function UFO2000.getFillTypeLabel(fillTypeIndex)
    if fillTypeIndex == nil or fillTypeIndex == FillType.UNKNOWN then
        return g_i18n ~= nil and g_i18n:getText("ufo_hud_empty") or "Empty"
    end
    local desc = g_fillTypeManager ~= nil
        and g_fillTypeManager.getFillTypeByIndex ~= nil
        and g_fillTypeManager:getFillTypeByIndex(fillTypeIndex) or nil
    local label = desc ~= nil and (desc.title or desc.name) or tostring(fillTypeIndex)
    if g_i18n ~= nil and label ~= nil then
        local translated = g_i18n:getText(label)
        if translated ~= nil and translated ~= "" then
            return translated
        end
    end
    return tostring(label or fillTypeIndex)
end

function UFO2000.getSowFruitLabel(index)
    local name = UFO2000.SOW_FRUITS[index or 1] or UFO2000.SOW_FRUITS[1]
    local fruitIndex = UFO2000.getFruitIndexByName(name)
    local desc = fruitIndex ~= nil and g_fruitTypeManager:getFruitTypeByIndex(fruitIndex) or nil
    local label = desc ~= nil and (desc.title or desc.name) or name
    if g_i18n ~= nil and label ~= nil then
        local translated = g_i18n:getText(label)
        if translated ~= nil and translated ~= "" then
            return translated
        end
    end
    return tostring(label or name)
end

-- ---------------------------------------------------------------------------
-- input
-- ---------------------------------------------------------------------------
function UFO2000:onRegisterActionEvents(isActiveForInput, isActiveForInputIgnoreSelection)
    if not self.isClient then
        return
    end
    local spec = self.spec_ufo2000
    self:clearActionEventsTable(spec.actionEvents)
    if not isActiveForInputIgnoreSelection then
        return
    end

    local _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_menu", self,
        UFO2000.actionEventMenu, true, false, false, true)
    g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_HIGH)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_menu"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_altitudeUp", self,
        UFO2000.actionEventAltitudeUp, false, false, true, true)
    g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_NORMAL)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_ascend"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_altitudeDown", self,
        UFO2000.actionEventAltitudeDown, false, false, true, true)
    g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_NORMAL)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_descend"))

    -- stock actions: no extra bindings needed, joystick friendly
    _, actionEventId = self:addActionEvent(spec.actionEvents, "LOWER_IMPLEMENT", self,
        UFO2000.actionEventToggleHover, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_toggleHover"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "IMPLEMENT_EXTRA", self,
        UFO2000.actionEventBeam, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_beam"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_beamMode", self,
        UFO2000.actionEventBeamMode, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_mode"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_penUp", self,
        UFO2000.actionEventPenUp, false, false, true, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_penWide"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_penDown", self,
        UFO2000.actionEventPenDown, false, false, true, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_penNarrow"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_unload", self,
        UFO2000.actionEventUnload, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_unload"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_harvestToTrailer", self,
        UFO2000.actionEventHarvestToTrailer, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_harvestToTrailer"))

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_infinite", self,
        UFO2000.actionEventInfinite, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_infinite"))

    if UFO2000.PHYSICAL_CARGO_ENABLED then
        _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_physicalCargo", self,
            UFO2000.actionEventPhysicalCargo, true, false, false, true)
        g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_physicalCargo"))
    end

    -- analog: the same axis a front loader uses, so a joystick works right away
    self:addActionEvent(spec.actionEvents, "AXIS_FRONTLOADER_ARM", self,
        UFO2000.actionEventAxis, false, false, true, true)

    if not spec.hintShown then
        UFO2000.showUFOStartHint(self)
    end
end

function UFO2000.actionEventMenu(vehicle, actionName, inputValue, callbackState)
    local spec = vehicle.spec_ufo2000
    if inputValue == 0 then
        return
    end
    spec.menuOpen = not spec.menuOpen
    if spec.menuOpen and vehicle.getIsEntered ~= nil and not vehicle:getIsEntered() then
        spec.menuOpen = false
    end
    spec.mouseWasDown = false
    UFO2000.setMenuCursor(spec.menuOpen)
end

function UFO2000.actionEventAltitudeUp(vehicle, actionName, inputValue, callbackState)
    local spec = vehicle.spec_ufo2000
    local pressed = inputValue ~= 0
    if pressed and spec.menuOpen then
        local count = UFO2000.getPatternCount()
        local index = spec.patternIndex % count + 1
        UFO2000.sendCommand(vehicle, "pattern", index)
        notify(vehicle, "ufo_notify_pattern", g_i18n:getText(UFO2000.PATTERNS[index].name))
        return
    end
    spec.digitalUp = pressed
    UFO2000.updateAxis(vehicle)
end

function UFO2000.actionEventAltitudeDown(vehicle, actionName, inputValue, callbackState)
    local spec = vehicle.spec_ufo2000
    local pressed = inputValue ~= 0
    if pressed and spec.menuOpen then
        local count = UFO2000.getPatternCount()
        local index = (spec.patternIndex - 2) % count + 1
        UFO2000.sendCommand(vehicle, "pattern", index)
        notify(vehicle, "ufo_notify_pattern", g_i18n:getText(UFO2000.PATTERNS[index].name))
        return
    end
    spec.digitalDown = pressed
    UFO2000.updateAxis(vehicle)
end

function UFO2000.actionEventAxis(vehicle, actionName, inputValue, callbackState, isAnalog)
    local spec = vehicle.spec_ufo2000
    spec.axisValue = UFO2000.clamp(inputValue or 0, -1, 1)
    spec.verticalDirty = true
end

--- merges the analog stick and the keyboard keys into one vertical input
function UFO2000.updateAxis(vehicle)
    local spec = vehicle.spec_ufo2000
    local value = spec.axisValue or 0
    if spec.digitalUp then
        value = 1
    elseif spec.digitalDown then
        value = -1
    end
    if value ~= spec.inputVertical then
        spec.inputVertical = value
        spec.verticalDirty = true
    end
end

function UFO2000.actionEventToggleHover(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local willHover = not vehicle:getUFOIsHovering()
    if not willHover and vehicle.spec_ufo2000.physicalCargo ~= nil then
        notify(vehicle, "ufo_notify_cargoLowerToRelease")
        return
    end
    if willHover and vehicle.getIsMotorStarted ~= nil and not vehicle:getIsMotorStarted() then
        notify(vehicle, "ufo_notify_engineRequired")
        return
    end
    if vehicle.isServer then
        vehicle:setUFOIsHovering(willHover)
    else
        g_client:getServerConnection():sendEvent(UFO2000ToggleHoverEvent.new(vehicle))
    end
    notify(vehicle, willHover and "ufo_notify_hoverOn" or "ufo_notify_hoverOff")
end

function UFO2000.actionEventBeam(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local spec = vehicle.spec_ufo2000
    if spec.menuOpen then
        -- closing the menu with the beam key also fires the selected setting
        spec.menuOpen = false
        spec.mouseWasDown = false
        UFO2000.setMenuCursor(false)
    end
    local willBeActive = not spec.beamActive
    if vehicle.isServer then
        vehicle:setUFOBeamActive(willBeActive)
    else
        g_client:getServerConnection():sendEvent(UFO2000ToggleBeamEvent.new(vehicle))
    end
    local modeName = g_i18n:getText(UFO2000.getModeInfo(spec.beamMode).text)
    notify(vehicle, willBeActive and "ufo_notify_beamOn" or "ufo_notify_beamOff", modeName)
end

--- sends a small command to the server (mode, focus, unload, endless tank)
function UFO2000.sendCommand(vehicle, command, value)
    if vehicle.isServer then
        UFO2000.runCommand(vehicle, command, value)
    elseif g_client ~= nil and g_client.getServerConnection ~= nil then
        g_client:getServerConnection():sendEvent(UFO2000CommandEvent.new(vehicle, command, value))
    end
end

function UFO2000.runCommand(vehicle, command, value)
    if command == "mode" then
        vehicle:setUFOBeamMode(vehicle:getUFOBeamMode() % UFO2000.MODE_COUNT + 1)
    elseif command == "modeSet" then
        vehicle:setUFOBeamMode(value)
    elseif command == "pattern" then
        vehicle:setUFOCirclePattern(value)
    elseif command == "penUp" then
        if vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_SOW then
            UFO2000.cycleSowFruit(vehicle, 1)
        else
            vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() + UFO2000.PEN_RADIUS_STEP)
        end
    elseif command == "penDown" then
        if vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_SOW then
            UFO2000.cycleSowFruit(vehicle, -1)
        else
            vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() - UFO2000.PEN_RADIUS_STEP)
        end
    elseif command == "unload" then
        local spec = vehicle.spec_ufo2000
        if spec.physicalCargo ~= nil then
            UFO2000.releasePhysicalCargo(vehicle, false)
        else
            UFO2000.setUnloadingState(vehicle, not spec.unloading)
            spec.unloadTimer = 0
        end
    elseif command == "physicalCargo" and UFO2000.PHYSICAL_CARGO_ENABLED then
        UFO2000.acquirePhysicalCargo(vehicle)
    elseif command == "harvestToTrailer" then
        local spec = vehicle.spec_ufo2000
        UFO2000.setHarvestToTrailer(vehicle, not spec.harvestToTrailer)
    elseif command == "infinite" then
        vehicle:setUFOInfiniteTank(not vehicle:getUFOInfiniteTank())
    end
end

--- next / previous seed in sowing mode
function UFO2000.cycleSowFruit(vehicle, step)
    local spec = vehicle.spec_ufo2000
    local count = #UFO2000.SOW_FRUITS
    spec.sowFruitIndex = ((spec.sowFruitIndex - 1 + step) % count) + 1
    if vehicle.isServer then
        vehicle:raiseDirtyFlags(spec.dirtyFlag)
    end
end

function UFO2000.actionEventBeamMode(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local nextMode = vehicle:getUFOBeamMode() % UFO2000.MODE_COUNT + 1
    UFO2000.sendCommand(vehicle, "mode")
    notify(vehicle, "ufo_notify_mode",
        g_i18n:getText(UFO2000.getModeInfo(nextMode).text))
end

local function showPenOrSeedFeedback(vehicle, direction)
    local spec = vehicle.spec_ufo2000
    if vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_SOW then
        local count = #UFO2000.SOW_FRUITS
        local index = ((spec.sowFruitIndex - 1 + direction) % count) + 1
        notify(vehicle, "ufo_notify_seed", UFO2000.getSowFruitLabel(index))
    else
        local radius = UFO2000.clamp(vehicle:getUFOPenRadius()
            + direction * UFO2000.PEN_RADIUS_STEP,
            UFO2000.PEN_MIN_RADIUS, UFO2000.PEN_MAX_RADIUS)
        radius = math.floor(radius / UFO2000.PEN_RADIUS_STEP + 0.5)
            * UFO2000.PEN_RADIUS_STEP
        notify(vehicle, "ufo_notify_focus", string.format("%.2f", radius * 2))
    end
end

function UFO2000.actionEventPenUp(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "penUp")
    showPenOrSeedFeedback(vehicle, 1)
end

function UFO2000.actionEventPenDown(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "penDown")
    showPenOrSeedFeedback(vehicle, -1)
end

function UFO2000.actionEventUnload(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local spec = vehicle.spec_ufo2000
    if spec.physicalCargoName ~= "" then
        UFO2000.sendCommand(vehicle, "unload")
        return
    end
    local willUnload = not spec.unloading
    UFO2000.sendCommand(vehicle, "unload")
    notify(vehicle, willUnload and "ufo_notify_unloadOn" or "ufo_notify_unloadOff")
end

function UFO2000.actionEventPhysicalCargo(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local spec = vehicle.spec_ufo2000
    if spec.physicalCargoName ~= "" then
        notify(vehicle, "ufo_notify_cargoAlreadyHeld", spec.physicalCargoName)
        return
    end
    UFO2000.sendCommand(vehicle, "physicalCargo")
end

function UFO2000.actionEventHarvestToTrailer(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local willEnable = not vehicle.spec_ufo2000.harvestToTrailer
    UFO2000.sendCommand(vehicle, "harvestToTrailer")
    notify(vehicle, willEnable and "ufo_notify_trailerBeamOn" or "ufo_notify_trailerBeamOff")
end

function UFO2000.actionEventInfinite(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    local willBeInfinite = not vehicle:getUFOInfiniteTank()
    UFO2000.sendCommand(vehicle, "infinite")
    notify(vehicle, willBeInfinite and "ufo_notify_tankEndless" or "ufo_notify_tankNormal")
end

function UFO2000:onLeaveVehicle(wasEntered)
    local spec = self.spec_ufo2000
    spec.menuOpen = false
    spec.mouseWasDown = false
    UFO2000.setMenuCursor(false)
    spec.unloading = false
    spec.digitalUp = false
    spec.digitalDown = false
    spec.axisValue = 0
    spec.inputVertical = 0
    spec.verticalDirty = true
end

-- ---------------------------------------------------------------------------
-- simulation
-- ---------------------------------------------------------------------------
function UFO2000:getCanMotorRun(superFunc)
    local spec = self.spec_ufo2000
    if spec ~= nil and spec.isHovering then
        if not superFunc(self) then
            return false
        end
        return true
    end
    return superFunc(self)
end

--- Makes fill unit 3 a genuinely universal, virtual transport hold. The game
--- still validates the fill type globally; this only removes the static list
--- limitation from the UFO's cargo unit.
function UFO2000.getFillUnitSupportsFillType(self, superFunc, fillUnitIndex, fillTypeIndex)
    if self.spec_ufo2000 ~= nil
        and fillUnitIndex == UFO2000.CARGO_TANK_INDEX
        and fillTypeIndex ~= nil and fillTypeIndex ~= FillType.UNKNOWN
        and g_fillTypeManager ~= nil
        and g_fillTypeManager.getFillTypeByIndex ~= nil
        and g_fillTypeManager:getFillTypeByIndex(fillTypeIndex) ~= nil then
        return true
    end
    return superFunc(self, fillUnitIndex, fillTypeIndex)
end

-- ---------------------------------------------------------------------------
-- physical cargo: dynamic vehicles, implements, pallets, bales, and split-shape
-- logs are detected in a small ground volume below the beam. Only one object
-- is carried at a time; its original physics is restored when U releases it.
-- ---------------------------------------------------------------------------
function UFO2000.setPhysicalCargoStatus(vehicle, status)
    local spec = vehicle.spec_ufo2000
    if spec == nil then
        return
    end
    spec.physicalCargoStatus = status or UFO2000.PHYSICAL_CARGO_STATUS.IDLE
    spec.physicalCargoStatusSequence = ((spec.physicalCargoStatusSequence or 0) + 1) % 256
    if vehicle.isServer and spec.dirtyFlag ~= nil then
        vehicle:raiseDirtyFlags(spec.dirtyFlag)
        UFO2000.notifyPhysicalCargoStatus(vehicle, spec.physicalCargoStatus)
    end
end

function UFO2000.notifyPhysicalCargoStatus(vehicle, status)
    local key = UFO2000.PHYSICAL_CARGO_STATUS_TEXT[status]
    if key ~= nil then
        if status == UFO2000.PHYSICAL_CARGO_STATUS.HELD then
            notify(vehicle, key, vehicle.spec_ufo2000.physicalCargoName or "cargo")
        else
            notify(vehicle, key)
        end
    end
end

local function physicalCargoNodeExists(node)
    return node ~= nil and node ~= 0
        and (entityExists == nil or entityExists(node))
end

local function physicalCargoRootNodes(object)
    local nodes, seen = {}, {}
    local function add(node)
        if physicalCargoNodeExists(node) and not seen[node] then
            seen[node] = true
            nodes[#nodes + 1] = node
        end
    end
    if object ~= nil and object.components ~= nil then
        for _, component in ipairs(object.components) do
            add(component.node)
        end
    end
    if #nodes == 0 and object ~= nil then
        add(object.rootNode or object.nodeId)
    end
    return nodes
end

local function physicalCargoMass(object, rootNode)
    local ok, mass
    if object ~= nil and object.isSplitShape and getMass ~= nil then
        ok, mass = pcall(getMass, rootNode)
    elseif object ~= nil and object.getTotalMass ~= nil then
        ok, mass = pcall(object.getTotalMass, object)
    elseif object ~= nil and object.getMass ~= nil then
        ok, mass = pcall(object.getMass, object)
    elseif getMass ~= nil then
        ok, mass = pcall(getMass, rootNode)
    end
    if not ok or type(mass) ~= "number" or mass ~= mass
        or mass <= 0 or mass == math.huge then
        return nil
    end
    return mass
end

local function physicalCargoBounds(object, rootNode)
    local bounds = {minX = math.huge, minY = math.huge, minZ = math.huge,
        maxX = -math.huge, maxY = -math.huge, maxZ = -math.huge, shapes = 0}
    local seen = {}
    local function addSphere(node)
        if getShapeBoundingSphere == nil or localToLocal == nil then
            return
        end
        local ok, x, y, z, radius = pcall(getShapeBoundingSphere, node)
        if not ok or type(radius) ~= "number" or radius <= 0 or radius == math.huge then
            return
        end
        local lx, ly, lz = localToLocal(node, rootNode, x or 0, y or 0, z or 0)
        local r = radius * 1.1
        bounds.minX = math.min(bounds.minX, lx - r)
        bounds.maxX = math.max(bounds.maxX, lx + r)
        bounds.minY = math.min(bounds.minY, ly - r)
        bounds.maxY = math.max(bounds.maxY, ly + r)
        bounds.minZ = math.min(bounds.minZ, lz - r)
        bounds.maxZ = math.max(bounds.maxZ, lz + r)
        bounds.shapes = bounds.shapes + 1
    end
    local function visit(node)
        if not physicalCargoNodeExists(node) or seen[node] then
            return
        end
        seen[node] = true
        local isShape = getHasClassId == nil or ClassIds == nil
            or ClassIds.SHAPE == nil or getHasClassId(node, ClassIds.SHAPE)
        if isShape then
            local group = getCollisionFilterGroup ~= nil and getCollisionFilterGroup(node) or nil
            local isTrigger = group ~= nil and CollisionFlag ~= nil
                and CollisionFlag.TRIGGER ~= nil and bitAND ~= nil
                and bitAND(group, CollisionFlag.TRIGGER) ~= 0
            if not isTrigger then
                addSphere(node)
            end
        end
        if getNumOfChildren ~= nil and getChildAt ~= nil then
            local count = getNumOfChildren(node) or 0
            for i = 0, count - 1 do
                visit(getChildAt(node, i))
            end
        end
    end
    if object ~= nil and object.components ~= nil then
        for _, component in ipairs(object.components) do
            visit(component.node)
        end
    else
        visit(rootNode)
    end
    if bounds.shapes == 0 and object ~= nil then
        local w, h, l = object.sizeX, object.sizeY, object.sizeZ
        if type(w) == "number" and type(h) == "number" and type(l) == "number"
            and w > 0 and h > 0 and l > 0 then
            bounds.minX, bounds.maxX = -w * 0.5, w * 0.5
            bounds.minY, bounds.maxY = -h * 0.5, h * 0.5
            bounds.minZ, bounds.maxZ = -l * 0.5, l * 0.5
            bounds.shapes = 1
        end
    end
    if bounds.shapes == 0 then
        return nil
    end
    bounds.width = bounds.maxX - bounds.minX
    bounds.height = bounds.maxY - bounds.minY
    bounds.length = bounds.maxZ - bounds.minZ
    bounds.centerX = (bounds.minX + bounds.maxX) * 0.5
    bounds.centerY = (bounds.minY + bounds.maxY) * 0.5
    bounds.centerZ = (bounds.minZ + bounds.maxZ) * 0.5
    return bounds
end

local function physicalCargoSplitShape(node)
    if getSplitType == nil or getSplitShapeStats == nil or g_splitShapeManager == nil
        or g_splitShapeManager.getSplitTypeByIndex == nil then
        return nil
    end
    local ok, splitIndex = pcall(getSplitType, node)
    if not ok or splitIndex == nil then
        return nil
    end
    local valid, splitType = pcall(g_splitShapeManager.getSplitTypeByIndex,
        g_splitShapeManager, splitIndex)
    if not valid or splitType == nil then
        return nil
    end
    local statsOk, sx, sy, sz = pcall(getSplitShapeStats, node)
    if not statsOk or type(sx) ~= "number" or type(sy) ~= "number"
        or type(sz) ~= "number" then
        return nil
    end
    return {nodeId = node, isSplitShape = true,
        sizeX = math.abs(sx), sizeY = math.abs(sy), sizeZ = math.abs(sz),
        i3dFilename = "Log"}
end

local function physicalCargoName(object)
    if object ~= nil and object.getName ~= nil then
        local ok, name = pcall(object.getName, object)
        if ok and type(name) == "string" and name ~= "" then
            return name
        end
    end
    if object ~= nil then
        local name = object.name or object.typeDesc or object.i3dFilename
        if type(name) == "string" and name ~= "" then
            return string.match(name, "([^/\\]+)$") or name
        end
    end
    return "Cargo"
end

local function physicalCargoIsAttached(object)
    if object == nil then
        return false
    end
    local attachable = object.spec_attachable
    if attachable ~= nil and attachable.attacherVehicle ~= nil then
        return true
    end
    local joints = object.spec_attacherJoints
    if joints ~= nil and joints.attachedImplements ~= nil
        and next(joints.attachedImplements) ~= nil then
        return true
    end
    return false
end

local function describePhysicalCargo(object, hitNode)
    if object == nil or object.spec_placeable ~= nil or object.isPlaceable == true
        or object.isPlayer == true or object.isAnimal == true or object.spec_human ~= nil
        or object.spec_horse ~= nil or object.spec_animal ~= nil then
        return nil, "noTarget"
    end
    if physicalCargoIsAttached(object) then
        return nil, "attached"
    end
    if object.getIsEntered ~= nil then
        local ok, entered = pcall(object.getIsEntered, object)
        if ok and entered then
            return nil, "noTarget"
        end
    end
    local nodes = physicalCargoRootNodes(object)
    local rootNode = nodes[1]
    if rootNode == nil then
        return nil, "noTarget"
    end
    if getRigidBodyType ~= nil and RigidBodyType ~= nil
        and getRigidBodyType(hitNode or rootNode) ~= RigidBodyType.DYNAMIC then
        return nil, "noTarget"
    end
    local mass = physicalCargoMass(object, rootNode)
    if mass == nil then
        return nil, "unknownMass"
    end
    if mass > UFO2000.PHYSICAL_CARGO_MAX_MASS then
        return nil, "heavy"
    end
    local bounds = physicalCargoBounds(object, rootNode)
    if bounds == nil or bounds.width <= 0 or bounds.height <= 0 or bounds.length <= 0
        or bounds.width > UFO2000.PHYSICAL_CARGO_MAX_WIDTH
        or bounds.height > UFO2000.PHYSICAL_CARGO_MAX_HEIGHT
        or bounds.length > UFO2000.PHYSICAL_CARGO_MAX_LENGTH then
        return nil, "large"
    end
    return {object = object, nodes = nodes, rootNode = rootNode,
        mass = mass, bounds = bounds, name = physicalCargoName(object)}
end

function UFO2000.findPhysicalCargoTarget(vehicle)
    local spec = vehicle.spec_ufo2000
    if g_currentMission == nil or overlapBox == nil or vehicle.components == nil
        or vehicle.components[1] == nil then
        return nil, "noTarget"
    end
    local ufoNode = vehicle.components[1].node
    local cx, cy, cz = getWorldTranslation(ufoNode)
    local terrainY = getTerrainHeightAtWorldPos(g_terrainNode, cx, 0, cz)
    local px, py, pz = cx, terrainY + 1.5, cz
    local rx, ry, rz = getWorldRotation(ufoNode)
    local mask = 0
    if CollisionFlag ~= nil then
        mask = (CollisionFlag.VEHICLE or 0) + (CollisionFlag.DYNAMIC_OBJECT or 0)
            + (CollisionFlag.TREE or 0)
    end
    if mask == 0 then
        return nil, "noTarget"
    end
    local search = {vehicle = vehicle, best = nil, bestDistance = math.huge,
        rejected = nil, seen = {}}
    search.ufo2000PhysicalCargoOverlapCallback = function(target, hitNode)
        if not physicalCargoNodeExists(hitNode) then
            return
        end
        if getHasClassId ~= nil and ClassIds ~= nil and ClassIds.SHAPE ~= nil
            and not getHasClassId(hitNode, ClassIds.SHAPE) then
            return
        end
        if getRigidBodyType ~= nil and RigidBodyType ~= nil
            and getRigidBodyType(hitNode) ~= RigidBodyType.DYNAMIC then
            return
        end
        local object = g_currentMission.getNodeObject ~= nil
            and g_currentMission:getNodeObject(hitNode) or nil
        if object == nil then
            object = physicalCargoSplitShape(hitNode)
        end
        if object == nil or object == target.vehicle then
            return
        end
        local nodes = physicalCargoRootNodes(object)
        local rootNode = nodes[1]
        if rootNode == nil or target.seen[rootNode] then
            return
        end
        target.seen[rootNode] = true
        local cx0, cy0, cz0 = getWorldTranslation(rootNode)
        local dx, dz = cx0 - cx, cz0 - cz
        if cy0 > terrainY + 5.0 or cy0 > cy + 0.1
            or dx * dx + dz * dz > 2.5 * 2.5 then
            return
        end
        local data, reason = describePhysicalCargo(object, hitNode)
        if data == nil then
            target.rejected = target.rejected or reason
            return
        end
        local distance = dx * dx + dz * dz + (cy0 - py) * (cy0 - py) * 0.15
        if distance < target.bestDistance then
            data.centerWorldX, data.centerWorldY, data.centerWorldZ =
                localToWorld(rootNode, data.bounds.centerX,
                    data.bounds.centerY, data.bounds.centerZ)
            target.best, target.bestDistance = data, distance
        end
    end
    overlapBox(px, py, pz, rx, ry, rz,
        UFO2000.PHYSICAL_CARGO_SCAN_WIDTH * 0.5,
        UFO2000.PHYSICAL_CARGO_SCAN_HEIGHT * 0.5,
        UFO2000.PHYSICAL_CARGO_SCAN_WIDTH * 0.5,
        "ufo2000PhysicalCargoOverlapCallback", search, mask, true, true, true, true)
    return search.best, search.rejected or "noTarget"
end

local function setPhysicalCargoPhysics(cargo, enabled)
    local object = cargo.object
    local physicsFunction = enabled and addToPhysics or removeFromPhysics
    if cargo.physicsMode == "object" and object ~= nil then
        local method = enabled and object.addToPhysics or object.removeFromPhysics
        if method ~= nil then
            local ok = pcall(method, object)
            if ok then
                if enabled and object.raiseActive ~= nil then
                    pcall(object.raiseActive, object)
                end
                return true
            end
        end
    end
    if physicsFunction == nil then
        return false
    end
    local changedNodes = {}
    for _, node in ipairs(cargo.nodes or {}) do
        if physicalCargoNodeExists(node) then
            local ok = pcall(physicsFunction, node)
            if not ok then
                local rollback = enabled and removeFromPhysics or addToPhysics
                if rollback ~= nil then
                    for i = #changedNodes, 1, -1 do
                        pcall(rollback, changedNodes[i])
                    end
                end
                return false
            end
            changedNodes[#changedNodes + 1] = node
        end
    end
    return true
end

function UFO2000.updatePhysicalCargo(vehicle)
    local spec = vehicle.spec_ufo2000
    local cargo = spec ~= nil and spec.physicalCargo or nil
    if cargo == nil then
        return
    end
    if not physicalCargoNodeExists(cargo.rootNode) or vehicle.components == nil
        or vehicle.components[1] == nil then
        spec.physicalCargo = nil
        spec.physicalCargoName = ""
        spec.physicalCargoMass = 0
        spec.minAltitude = UFO2000.MIN_ALTITUDE
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.RELEASED)
        return
    end
    local ufoNode = vehicle.components[1].node
    local bounds = cargo.bounds
    local anchorY = math.max(-(bounds.height * 0.5 + UFO2000.PHYSICAL_CARGO_HOLD_CLEARANCE),
        UFO2000.PHYSICAL_CARGO_GROUND_CLEARANCE + bounds.height * 0.5 - spec.altitude)
    local centerX, centerY, centerZ = 0, anchorY, 0
    local rootX = centerX - cargo.centerOffset[1]
    local rootY = centerY - cargo.centerOffset[2]
    local rootZ = centerZ - cargo.centerOffset[3]
    local x, y, z = localToWorld(ufoNode, rootX, rootY, rootZ)
    local rx, ry, rz = localRotationToWorld(ufoNode,
        cargo.relativeRotation[1], cargo.relativeRotation[2], cargo.relativeRotation[3])
    setWorldTranslation(cargo.rootNode, x, y, z)
    setWorldRotation(cargo.rootNode, rx, ry, rz)
    for i = 2, #cargo.nodes do
        local node = cargo.nodes[i]
        local rel = cargo.componentTransforms[i]
        if physicalCargoNodeExists(node) and rel ~= nil then
            local px, py, pz = localToWorld(cargo.rootNode, rel[1], rel[2], rel[3])
            local prx, pry, prz = localRotationToWorld(cargo.rootNode, rel[4], rel[5], rel[6])
            setWorldTranslation(node, px, py, pz)
            setWorldRotation(node, prx, pry, prz)
        end
    end
    cargo.networkTimer = (cargo.networkTimer or 0) + 16
    if cargo.networkTimer >= 200 then
        cargo.networkTimer = 0
        if cargo.object ~= nil and cargo.object.raiseActive ~= nil then
            pcall(cargo.object.raiseActive, cargo.object)
        end
        if cargo.object ~= nil and cargo.object.networkTimeInterpolator ~= nil
            and cargo.object.networkTimeInterpolator.reset ~= nil then
            pcall(cargo.object.networkTimeInterpolator.reset,
                cargo.object.networkTimeInterpolator)
        end
    end
end

function UFO2000.acquirePhysicalCargo(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec == nil or not UFO2000.PHYSICAL_CARGO_ENABLED then
        return false
    end
    if spec.physicalCargo ~= nil then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.HELD)
        return false
    end
    if not spec.isHovering then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.NEED_HOVER)
        return false
    end
    if not spec.beamActive then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.BEAM_OFF)
        return false
    end
    if spec.altitude > UFO2000.PHYSICAL_CARGO_MAX_PICKUP_ALTITUDE then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.TOO_HIGH)
        return false
    end
    local data, reason = UFO2000.findPhysicalCargoTarget(vehicle)
    if data == nil then
        local status = UFO2000.PHYSICAL_CARGO_STATUS.NO_TARGET
        if reason == "heavy" then
            status = UFO2000.PHYSICAL_CARGO_STATUS.TOO_HEAVY
        elseif reason == "large" then
            status = UFO2000.PHYSICAL_CARGO_STATUS.TOO_LARGE
        elseif reason == "attached" then
            status = UFO2000.PHYSICAL_CARGO_STATUS.DETACH_FIRST
        end
        UFO2000.setPhysicalCargoStatus(vehicle, status)
        return false
    end
    local ufoNode = vehicle.components[1].node
    local rootNode = data.rootNode
    local centerX, centerY, centerZ = localToLocal(rootNode, ufoNode,
        data.bounds.centerX, data.bounds.centerY, data.bounds.centerZ)
    local originX, originY, originZ = localToLocal(rootNode, ufoNode, 0, 0, 0)
    local relRotX, relRotY, relRotZ = localRotationToLocal(rootNode, ufoNode, 0, 0, 0)
    local componentTransforms = {}
    for i = 1, #data.nodes do
        local node = data.nodes[i]
        local x, y, z = localToLocal(node, rootNode, 0, 0, 0)
        local rx, ry, rz = localRotationToLocal(node, rootNode, 0, 0, 0)
        componentTransforms[i] = {x, y, z, rx, ry, rz}
    end
    local cargo = {
        object = data.object, nodes = data.nodes, rootNode = rootNode,
        bounds = data.bounds, mass = data.mass, name = data.name,
        centerOffset = {centerX - originX, centerY - originY, centerZ - originZ},
        relativeRotation = {relRotX, relRotY, relRotZ},
        componentTransforms = componentTransforms,
        physicsMode = data.object.removeFromPhysics ~= nil and "object" or "nodes",
    }
    if not setPhysicalCargoPhysics(cargo, false) then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.NO_TARGET)
        return false
    end
    UFO2000.setUnloadingState(vehicle, false)
    spec.physicalCargo = cargo
    spec.physicalCargoName = data.name
    spec.physicalCargoMass = data.mass
    spec.minAltitude = math.max(UFO2000.MIN_ALTITUDE,
        data.bounds.height + UFO2000.PHYSICAL_CARGO_GROUND_CLEARANCE + 0.85)
    spec.altitudeTarget = math.max(spec.altitudeTarget or spec.minAltitude, spec.minAltitude)
    if spec.dirtyFlag ~= nil then
        vehicle:raiseDirtyFlags(spec.dirtyFlag)
    end
    UFO2000.updatePhysicalCargo(vehicle)
    UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.HELD)
    return true
end

function UFO2000.releasePhysicalCargo(vehicle, force)
    local spec = vehicle.spec_ufo2000
    local cargo = spec ~= nil and spec.physicalCargo or nil
    if cargo == nil then
        return false
    end
    if not force and spec.altitude > spec.minAltitude + 0.75 then
        UFO2000.setPhysicalCargoStatus(vehicle, UFO2000.PHYSICAL_CARGO_STATUS.LOWER_TO_RELEASE)
        return false
    end
    if physicalCargoNodeExists(cargo.rootNode) then
        UFO2000.updatePhysicalCargo(vehicle)
        if force and vehicle.components ~= nil and vehicle.components[1] ~= nil then
            -- If the UFO is removed mid-flight, place cargo on the terrain before
            -- restoring gravity; normal U releases remain a short, controlled drop.
            local ufoNode = vehicle.components[1].node
            local ux, _, uz = getWorldTranslation(ufoNode)
            local groundY = getTerrainHeightAtWorldPos(g_terrainNode, ux, 0, uz)
            local root = cargo.rootNode
            local cx, cy, cz = localToWorld(ufoNode,
                cargo.centerOffset[1], cargo.centerOffset[2], cargo.centerOffset[3])
            local ox, oy, oz = localToWorld(ufoNode, 0, 0, 0)
            local vx, vy, vz = cx - ox, cy - oy, cz - oz
            local targetCenterY = groundY + cargo.bounds.height * 0.5
                + UFO2000.PHYSICAL_CARGO_GROUND_CLEARANCE
            setWorldTranslation(root, ux - vx, targetCenterY - vy, uz - vz)
            local rx, ry, rz = localRotationToWorld(ufoNode,
                cargo.relativeRotation[1], cargo.relativeRotation[2], cargo.relativeRotation[3])
            setWorldRotation(root, rx, ry, rz)
            for i = 2, #cargo.nodes do
                local node = cargo.nodes[i]
                local rel = cargo.componentTransforms[i]
                if physicalCargoNodeExists(node) and rel ~= nil then
                    local px, py, pz = localToWorld(root, rel[1], rel[2], rel[3])
                    local prx, pry, prz = localRotationToWorld(root, rel[4], rel[5], rel[6])
                    setWorldTranslation(node, px, py, pz)
                    setWorldRotation(node, prx, pry, prz)
                end
            end
        end
        if not setPhysicalCargoPhysics(cargo, true) then
            return false
        end
        if setLinearVelocity ~= nil and vehicle.components ~= nil
            and vehicle.components[1] ~= nil then
            local heading = math.rad(spec.yaw or 0)
            local speed = spec.speed or 0
            for _, node in ipairs(cargo.nodes) do
                if physicalCargoNodeExists(node) then
                    setLinearVelocity(node, math.sin(heading) * speed, 0,
                        math.cos(heading) * speed)
                end
            end
        end
    end
    spec.physicalCargo = nil
    spec.physicalCargoName = ""
    spec.physicalCargoMass = 0
    spec.minAltitude = UFO2000.MIN_ALTITUDE
    spec.altitudeTarget = math.max(spec.minAltitude,
        math.min(spec.altitudeTarget or spec.altitude, spec.altitude or spec.minAltitude))
    if spec.dirtyFlag ~= nil then
        vehicle:raiseDirtyFlags(spec.dirtyFlag)
    end
    UFO2000.setPhysicalCargoStatus(vehicle,
        force and UFO2000.PHYSICAL_CARGO_STATUS.SAFE_DROP
            or UFO2000.PHYSICAL_CARGO_STATUS.RELEASED)
    return true
end

function UFO2000:onUpdateTick(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)
    local spec = self.spec_ufo2000
    spec.legsAlpha = UFO2000.clamp(
        spec.legsAlpha + (spec.legsTarget - spec.legsAlpha) * math.min(dt * spec.legSpeed, 1), 0, 1)

    if self.isServer then
        UFO2000.updateAxis(self)
        if spec.isHovering then
            UFO2000.updateFlight(self, dt)
            if spec.beamMode == UFO2000.BEAM_MODE_UNLOAD and spec.beamActive
                and spec.physicalCargo == nil then
                UFO2000.setUnloadingState(self, true)
            end
            if spec.beamActive then
                UFO2000.updateDrawing(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
                    UFO2000.updateHarvest(self, dt)
                    UFO2000.updateHarvestToTrailer(self, dt)
                end
                UFO2000.updateFieldWork(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_LOAD then
                    UFO2000.updateLoading(self, dt)
                end
            end
            if spec.unloading and spec.physicalCargo == nil then
                UFO2000.updateUnloading(self, dt)
            end
        else
            spec.altitudeTarget = spec.minAltitude
        end
        if spec.physicalCargo ~= nil then
            UFO2000.updatePhysicalCargo(self)
        end
        self:raiseDirtyFlags(spec.dirtyFlag)
    end

    UFO2000.updateLegs(self, dt)
end

function UFO2000.updateFlight(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    local node = vehicle.components[1].node
    local px, py, pz = getWorldTranslation(node)

    -- vertical: the target height can be raised / lowered with the axis
    if spec.inputVertical ~= 0 then
        spec.altitudeTarget = UFO2000.clamp(
            spec.altitudeTarget + spec.inputVertical * spec.climbSpeed * dt,
            spec.minAltitude, spec.maxAltitude)
    end

    local groundY = getTerrainHeightAtWorldPos(g_terrainNode, px, 0, pz)
    local targetY = groundY + spec.altitudeTarget
    spec.altitude = spec.altitude + (spec.altitudeTarget - spec.altitude) * math.min(dt * 3.0, 1)

    -- horizontal: the normal drive keys (keyboard or joystick)
    local drivable = vehicle.spec_drivable
    local inputForward = 0
    local inputSide = 0
    if drivable ~= nil then
        inputForward = drivable.axisForward or 0
        inputSide = drivable.axisSide or 0
    end
    if inputForward ~= inputForward then
        inputForward = 0
    end
    if inputSide ~= inputSide then
        inputSide = 0
    end
    inputForward = UFO2000.clamp(inputForward, -1, 1)
    inputSide = UFO2000.clamp(inputSide, -1, 1)

    local wantedSpeed = inputForward * spec.maxSpeed
    spec.speed = spec.speed + (wantedSpeed - spec.speed) * math.min(dt * UFO2000.SPEED_ACCEL, 1)
    spec.yaw = spec.yaw + inputSide * spec.yawSpeed * dt

    -- cosmetic tilt into the flight direction
    spec.pitch = spec.pitch + (-4.5 * inputForward - spec.pitch) * math.min(dt * 2.0, 1)
    spec.roll = spec.roll + (-5.5 * inputSide - spec.roll) * math.min(dt * 2.0, 1)

    local heading = math.rad(spec.yaw)
    local fx, fz = math.sin(heading), math.cos(heading)

    -- hover height without the cosmetic bobbing, so the bobbing is not
    -- amplified by the smoothing factor
    if spec.hoverY == nil then
        spec.hoverY = py
    end
    spec.hoverY = spec.hoverY + (targetY - spec.hoverY) * math.min(dt * UFO2000.HOVER_ACCEL, 1)
    if math.abs(py - spec.hoverY) > 2.0 then
        spec.hoverY = py
    end
    local bob = math.sin(g_currentMission.time / 900) * 0.035
    local newY = math.max(spec.hoverY, groundY + 0.6) + bob

    local nx = px + fx * spec.speed * dt
    local nz = pz + fz * spec.speed * dt

    setWorldTranslation(node, nx, newY, nz)
    setRotation(node, spec.pitch, spec.yaw, spec.roll)
    setLinearVelocity(node, fx * spec.speed, (targetY - py) * 0.6, fz * spec.speed)
    setAngularVelocity(node, 0, 0, 0)

    -- automatic landing when the pilot asks for the lowest altitude
    if spec.inputVertical < 0 and spec.physicalCargo == nil
        and spec.altitudeTarget <= spec.minAltitude + 0.01
        and py - groundY < spec.minAltitude + 0.25 then
        spec.altitude = spec.minAltitude
        vehicle:setUFOIsHovering(false)
    end
end

function UFO2000.updateLegs(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    for i = 1, #spec.legNodes do
        local node = spec.legNodes[i]
        local rest = spec.legRestRotation[i]
        local retracted = rest + 74
        setRotation(node, 0, select(2, getRotation(node)), rest + (retracted - rest) * spec.legsAlpha)
    end
end

-- ---------------------------------------------------------------------------
-- client side visuals (beam, ring, beacon, hud)
-- ---------------------------------------------------------------------------
function UFO2000:onUpdate(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)
    local spec = self.spec_ufo2000
    if not self.isClient then
        return
    end

    local node = self.components[1].node
    local px, py, pz = getWorldTranslation(node)
    local groundY = getTerrainHeightAtWorldPos(g_terrainNode, px, 0, pz)
    local height = py - groundY
    local time = g_currentMission.time / 1000

    UFO2000.updateCockpit(self)
    UFO2000.updateMenuMouse(self)

    -- beacon keeps turning
    if spec.beaconLight ~= nil then
        setRotation(spec.beaconLight, 0, time * 220 % 360, 0)
    end

    local manual = UFO2000.isManual(spec.patternIndex)
    if spec.beamActive and spec.isHovering then
        local radius = self:getUFOCircleRadius()
        local drawing = spec.drawTotal ~= nil and 0 < spec.drawTotal
        local pulse = 0.03 * math.sin(time * 9)

        if spec.beamNodes ~= nil then
            local coneHeight = math.max(height - 0.25, 0.5)
            for i = 1, #spec.beamNodes do
                local node = spec.beamNodes[i]
                if node ~= nil then
                    setVisibility(node, i == spec.beamMode)
                end
            end
            local node = spec.beamNodes[spec.beamMode]
            if node ~= nil then
                setScale(node, radius * (1 + pulse), coneHeight, radius * (1 + pulse))
                setRotation(node, 0, time * 70 % 360, 0)
            end
        end

        local transferVisible = spec.harvestToTrailer
            and spec.beamMode == UFO2000.BEAM_MODE_HARVEST
        if spec.transferBeamNode ~= nil then
            setVisibility(spec.transferBeamNode, transferVisible)
            if transferVisible then
                setScale(spec.transferBeamNode, UFO2000.HARVEST_TRAILER_RADIUS,
                    math.max(height - 0.25, 0.5), UFO2000.HARVEST_TRAILER_RADIUS)
                setRotation(spec.transferBeamNode, 0, time * 82 % 360, 0)
            end
        end

        if spec.ringNode ~= nil then
            -- in pen mode the ring would only be a dot: hide it and let the
            -- thin beam mark the spot
            setVisibility(spec.ringNode, not manual)
            if not manual then
                setTranslation(spec.ringNode, 0, -(height) + 0.08, 0)
                local ringScale = radius * (drawing and (0.35 + 0.65 * spec.drawProgress) or 1.0)
                local ringPulse = 1 + 0.012 * math.sin(time * (drawing and 14 or 3))
                setScale(spec.ringNode, ringScale * ringPulse, 1, ringScale * ringPulse)
                setRotation(spec.ringNode, 0, time * 55 % 360, 0)
            end
        end
    else
        if spec.beamNodes ~= nil then
            for i = 1, #spec.beamNodes do
                if spec.beamNodes[i] ~= nil then
                    setVisibility(spec.beamNodes[i], false)
                end
            end
        end
        if spec.ringNode ~= nil then
            setVisibility(spec.ringNode, false)
        end
        if spec.transferBeamNode ~= nil then
            setVisibility(spec.transferBeamNode, false)
        end
    end

    -- the loops follow the mode: work hum, suction, pouring
    UFO2000.updateModeSounds(self)
end

-- ---------------------------------------------------------------------------
-- v7 mode sounds: a little beep per mode change plus a loop per working beam
-- ---------------------------------------------------------------------------
function UFO2000.loadModeSounds(vehicle)
    local spec = vehicle.spec_ufo2000
    spec.sounds = {}
    if g_soundManager == nil or vehicle.externalSoundsFile == nil
        or vehicle.xmlFile == nil then
        return
    end
    local function load(name)
        return g_soundManager:loadSampleFromXML(vehicle.xmlFile, "vehicle.ufo2000",
            name, vehicle.baseDirectory, vehicle.components, 0,
            AudioGroup.VEHICLE, vehicle.i3dMappings, vehicle)
    end
    spec.sounds.modeSwitch = load("modeSwitch")
    spec.sounds.beamLoop = load("beamLoop")
    spec.sounds.loadLoop = load("loadLoop")
    spec.sounds.unloadLoop = load("unloadLoop")
    spec.soundState = {beam = false, load = false, unload = false}
end

function UFO2000.playModeSound(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec.sounds ~= nil and spec.sounds.modeSwitch ~= nil and g_soundManager ~= nil then
        g_soundManager:playSample(spec.sounds.modeSwitch)
    end
end

local function setLoopSound(sample, state, key, want)
    if sample == nil or g_soundManager == nil then
        return
    end
    if want and not state[key] then
        g_soundManager:playSample(sample)
        state[key] = true
    elseif not want and state[key] then
        g_soundManager:stopSample(sample)
        state[key] = false
    end
end

--- Mouse support for the on board menu: returns the cursor position (screen
--- space, 0..1 from the bottom left) and whether the left button is held.
function UFO2000.getMenuMouse()
    if g_inputBinding == nil or g_inputBinding.getMousePosition == nil then
        return nil, nil, false
    end
    local x, y = g_inputBinding:getMousePosition()
    local down = false
    if Input ~= nil and Input.isMouseButtonPressed ~= nil
        and Input.MOUSE_BUTTON_LEFT ~= nil then
        down = Input.isMouseButtonPressed(Input.MOUSE_BUTTON_LEFT) == true
    end
    return x, y, down
end

--- shows / hides the mouse cursor so the menu can be clicked
function UFO2000.setMenuCursor(visible)
    if g_inputBinding ~= nil and g_inputBinding.setShowMouseCursor ~= nil then
        g_inputBinding:setShowMouseCursor(visible == true)
    end
end

local MENU_PANEL = {x = 0.22, y = 0.25, width = 0.56, height = 0.50}

--- Clickable rows make the on-board menu usable without memorising a key map.
function UFO2000.updateMenuMouse(vehicle)
    local spec = vehicle.spec_ufo2000
    if not spec.menuOpen then
        spec.mouseWasDown = false
        return
    end
    local mouseX, mouseY, down = UFO2000.getMenuMouse()
    local clicked = down and not spec.mouseWasDown
    spec.mouseWasDown = down
    if not clicked or mouseX == nil or mouseY == nil then
        return
    end
    local panel = MENU_PANEL
    if mouseX < panel.x or mouseX > panel.x + panel.width
        or mouseY < panel.y or mouseY > panel.y + panel.height then
        return
    end

    local listTop = panel.y + panel.height - 0.11
    if mouseX < 0.50 then
        for i = 1, UFO2000.getPatternCount() do
            local rowY = listTop - (i - 1) * 0.024
            if math.abs(mouseY - rowY) < 0.012 then
                UFO2000.sendCommand(vehicle, "pattern", i)
                notify(vehicle, "ufo_notify_pattern", g_i18n:getText(UFO2000.PATTERNS[i].name))
                return
            end
        end
    else
        for i = 1, UFO2000.MODE_COUNT do
            local rowY = listTop - (i - 1) * 0.028
            if math.abs(mouseY - rowY) < 0.014 then
                UFO2000.sendCommand(vehicle, "modeSet", i)
                notify(vehicle, "ufo_notify_mode", g_i18n:getText(UFO2000.MODES[i].text))
                return
            end
        end
    end

    -- Two bottom buttons mirror the quick keys, and their labels show the
    -- current state so a click never leaves the pilot guessing.
    if mouseY >= panel.y + 0.070 and mouseY <= panel.y + 0.115 then
        if mouseX < 0.50 then
            UFO2000.actionEventInfinite(vehicle, "ufo_infinite", 1, nil)
        else
            UFO2000.actionEventHarvestToTrailer(vehicle, "ufo_harvestToTrailer", 1, nil)
        end
    elseif mouseY >= panel.y + 0.035 and mouseY < panel.y + 0.065 then
        UFO2000.actionEventUnload(vehicle, "ufo_unload", 1, nil)
    end
end

--- starts / stops the humming loops that belong to the current beam
function UFO2000.updateModeSounds(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec.sounds == nil or spec.soundState == nil then
        return
    end
    local info = UFO2000.getModeInfo(spec.beamMode)
    local working = spec.beamActive and spec.isHovering
    setLoopSound(spec.sounds.beamLoop, spec.soundState, "beam", working and info.work)
    setLoopSound(spec.sounds.loadLoop, spec.soundState, "load",
        working and spec.beamMode == UFO2000.BEAM_MODE_LOAD)
    setLoopSound(spec.sounds.unloadLoop, spec.soundState, "unload",
        working and (spec.beamMode == UFO2000.BEAM_MODE_UNLOAD or spec.unloading))
end

-- ---------------------------------------------------------------------------
-- cockpit instruments
-- ---------------------------------------------------------------------------
--- Moves the pattern selector, the mode lever and the focus knob inside the
--- cockpit so the pilot sees the state at a glance (no extra HUD needed).
function UFO2000.updateCockpit(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec.patternPointer == nil then
        return
    end
    -- 2 rows x 5 tiles on the little board next to the left hand
    local index = spec.patternIndex - 1
    local col = index % 5
    local row = math.floor(index / 5)
    setTranslation(spec.patternPointer, -0.15 + col * 0.075,
        0.045 - row * 0.075, 0.030)
    setVisibility(spec.patternPointer, true)
    if spec.modeLever ~= nil then
        -- the lever travels through all eight modes
        local t = (spec.beamMode - 1) / (UFO2000.MODE_COUNT - 1)
        local _, ry, rz = getRotation(spec.modeLever)
        setRotation(spec.modeLever, 32 - 64 * t, ry, rz)
    end
    if spec.modeNeedle ~= nil then
        -- the needle on the dial points at the selected segment
        setRotation(spec.modeNeedle, 0, -(spec.beamMode - 1) * 45, 0)
    end
    if spec.focusSlider ~= nil then
        local t = (spec.penRadius - UFO2000.PEN_MIN_RADIUS)
            / (UFO2000.PEN_MAX_RADIUS - UFO2000.PEN_MIN_RADIUS)
        local x, y, z = getTranslation(spec.focusSlider)
        setTranslation(spec.focusSlider, 0.30 - 0.09 + 0.18 * t, 1.24, 0.52)
    end
end

-- ---------------------------------------------------------------------------
-- on board menu
-- ---------------------------------------------------------------------------
local function drawText(x, y, size, text, alignment, color)
    setTextColor(color[1], color[2], color[3], color[4] or 1)
    setTextAlignment(alignment or RenderText.ALIGN_LEFT)
    renderText(x, y, size, text)
    setTextAlignment(RenderText.ALIGN_LEFT)
    setTextColor(1, 1, 1, 1)
end

function UFO2000.drawHud(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec == nil or g_currentMission == nil then
        return
    end
    if vehicle.getIsEntered == nil or not vehicle:getIsEntered() then
        return
    end
    -- never draw over an open game menu
    if g_gui ~= nil and g_gui.getIsGuiVisible ~= nil and g_gui:getIsGuiVisible() then
        return
    end

    local white = {1, 1, 1, 1}
    local green = {0.45, 1.0, 0.62, 1}
    local dim = {0.8, 0.9, 1.0, 0.85}
    local warning = {1.0, 0.56, 0.26, 1}
    local modeInfo = UFO2000.getModeInfo(spec.beamMode)
    local modeName = g_i18n:getText(modeInfo.text)
    local pattern = UFO2000.PATTERNS[spec.patternIndex] or UFO2000.PATTERNS[1]
    local patternName = g_i18n:getText(pattern.name)
    local altitudeText = spec.isHovering
        and string.format("%s · %s %.1f m", g_i18n:getText("ufo_hud_hovering"),
            g_i18n:getText("ufo_hud_height"), spec.altitude)
        or g_i18n:getText("ufo_hud_landed")
    local beamState = spec.beamActive and g_i18n:getText("ufo_hud_on")
        or g_i18n:getText("ufo_hud_off")
    local modeLine = string.format("%s: %s · %s", g_i18n:getText("ufo_hud_mode"),
        modeName, beamState)
    local beamColor = spec.beamActive and green or dim

    local grainLevel = vehicle:getFillUnitFillLevel(UFO2000.HARVEST_TANK_INDEX) or 0
    local grainCapacity = vehicle:getFillUnitCapacity(UFO2000.HARVEST_TANK_INDEX) or 0
    local grainType = vehicle:getFillUnitFillType(UFO2000.HARVEST_TANK_INDEX)
    local tankText
    if spec.infiniteTank then
        tankText = string.format("%s: %s", g_i18n:getText("ufo_hud_tank"),
            g_i18n:getText("ufo_hud_tankEndless"))
    else
        tankText = string.format("%s: %d / %d l · %s", g_i18n:getText("ufo_hud_tank"),
            math.floor(grainLevel), math.floor(grainCapacity),
            UFO2000.getFillTypeLabel(grainType))
    end

    local cargoLevel = vehicle:getFillUnitFillLevel(UFO2000.CARGO_TANK_INDEX) or 0
    local cargoCapacity = vehicle:getFillUnitCapacity(UFO2000.CARGO_TANK_INDEX) or 0
    local cargoType = vehicle:getFillUnitFillType(UFO2000.CARGO_TANK_INDEX)
    local cargoText = string.format("%s: %d / %d l · %s",
        g_i18n:getText("ufo_hud_cargo"), math.floor(cargoLevel),
        math.floor(cargoCapacity), UFO2000.getFillTypeLabel(cargoType))
    local physicalCargoText
    if spec.physicalCargoName ~= "" then
        physicalCargoText = string.format("%s: %s · %d kg",
            g_i18n:getText("ufo_hud_physicalCargo"), spec.physicalCargoName,
            math.floor(spec.physicalCargoMass or 0))
    else
        physicalCargoText = string.format("%s: %s",
            g_i18n:getText("ufo_hud_physicalCargo"),
            g_i18n:getText("ufo_hud_empty"))
    end

    local radius = vehicle:getUFOCircleRadius()
    local focusText = UFO2000.isManual(spec.patternIndex)
        and string.format("%s: %s · %.2f m", g_i18n:getText("ufo_hud_pattern"),
            patternName, radius * 2)
        or string.format("%s: %s · %s %.1f m · %s %.1f m",
            g_i18n:getText("ufo_hud_pattern"), patternName,
            g_i18n:getText("ufo_hud_radius"), radius,
            g_i18n:getText("ufo_hud_width"), radius * 2)

    local directLine
    if spec.harvestToTrailer then
        if spec.infiniteTank then
            directLine = string.format("%s: %s · %s", g_i18n:getText("ufo_hud_trailerBeam"),
                g_i18n:getText("ufo_hud_on"), g_i18n:getText("ufo_hud_infiniteNoOutput"))
        elseif not spec.isHovering or not spec.beamActive
            or spec.beamMode ~= UFO2000.BEAM_MODE_HARVEST then
            directLine = string.format("%s: %s · %s", g_i18n:getText("ufo_hud_trailerBeam"),
                g_i18n:getText("ufo_hud_on"), g_i18n:getText("ufo_hud_transferPaused"))
        elseif spec.directTargetName ~= "" then
            directLine = string.format("%s: %s → %s", g_i18n:getText("ufo_hud_trailerBeam"),
                g_i18n:getText("ufo_hud_on"), spec.directTargetName)
        else
            directLine = string.format("%s: %s · %s", g_i18n:getText("ufo_hud_trailerBeam"),
                g_i18n:getText("ufo_hud_on"), g_i18n:getText("ufo_hud_waiting"))
        end
    else
        directLine = string.format("%s: %s", g_i18n:getText("ufo_hud_trailerBeam"),
            g_i18n:getText("ufo_hud_off"))
    end

    -- The live status is always visible while seated, whether flying or landed.
    drawText(0.5, 0.218, 0.013, altitudeText, RenderText.ALIGN_CENTER, white)
    drawText(0.5, 0.198, 0.013, modeLine, RenderText.ALIGN_CENTER, beamColor)
    drawText(0.5, 0.178, 0.012, tankText, RenderText.ALIGN_CENTER, white)
    drawText(0.5, 0.158, 0.012, cargoText, RenderText.ALIGN_CENTER, dim)
    drawText(0.5, 0.138, 0.012, physicalCargoText, RenderText.ALIGN_CENTER,
        spec.physicalCargoName ~= "" and warning or dim)
    drawText(0.5, 0.118, 0.012, focusText, RenderText.ALIGN_CENTER, green)
    drawText(0.5, 0.098, 0.012, directLine, RenderText.ALIGN_CENTER,
        spec.harvestToTrailer and green or dim)

    if spec.beamMode == UFO2000.BEAM_MODE_SOW then
        local seedLine = string.format("%s: %s", g_i18n:getText("ufo_hud_sow"),
            UFO2000.getSowFruitLabel(spec.sowFruitIndex))
        drawText(0.5, 0.078, 0.012, seedLine, RenderText.ALIGN_CENTER, white)
    end
    local activityLine
    local activityColor = dim
    if spec.unloading or spec.unloadTargetName ~= "" then
        local targetName = spec.unloadTargetName ~= "" and spec.unloadTargetName
            or g_i18n:getText("ufo_hud_searching")
        activityLine = string.format("%s %s", g_i18n:getText("ufo_hud_unloading"),
            targetName)
        activityColor = warning
    elseif spec.loading then
        local loadName = spec.loadTargetName ~= "" and spec.loadTargetName
            or g_i18n:getText("ufo_hud_searching")
        activityLine = string.format("%s %s", g_i18n:getText("ufo_hud_loading"), loadName)
        activityColor = green
    else
        activityLine = string.format("%s: %s", g_i18n:getText("ufo_hud_unloadState"),
            g_i18n:getText("ufo_hud_off"))
    end
    drawText(0.5, 0.058, 0.012, activityLine, RenderText.ALIGN_CENTER, activityColor)

    if not spec.menuOpen then
        return
    end

    -- One compact two-column panel: patterns on the left, all eight working
    -- modes on the right, with the quick settings as visibly-stateful buttons.
    local panel = MENU_PANEL
    local x, y, width, height = panel.x, panel.y, panel.width, panel.height
    drawFilledRect(x, y, width, height, 0.02, 0.07, 0.06, 0.88)
    drawOutlineRect(x, y, width, height, 0.002, 0.002, 0.35, 1.0, 0.6, 0.95)
    drawText(0.5, y + height - 0.035, 0.018,
        g_i18n:getText("ufo_menu_title"), RenderText.ALIGN_CENTER, green)
    drawText(0.25, y + height - 0.075, 0.012,
        g_i18n:getText("ufo_menu_patterns"), RenderText.ALIGN_LEFT, dim)
    drawText(0.52, y + height - 0.075, 0.012,
        g_i18n:getText("ufo_menu_modes"), RenderText.ALIGN_LEFT, dim)

    local listTop = y + height - 0.11
    for i = 1, UFO2000.getPatternCount() do
        local selected = i == spec.patternIndex
        local label = string.format("%d. %s", i,
            g_i18n:getText(UFO2000.PATTERNS[i].name))
        drawText(0.25, listTop - (i - 1) * 0.024, selected and 0.013 or 0.011,
            (selected and "> " or "  ") .. label,
            RenderText.ALIGN_LEFT, selected and green or dim)
    end
    for i = 1, UFO2000.MODE_COUNT do
        local selected = i == spec.beamMode
        local label = string.format("%d. %s", i,
            g_i18n:getText(UFO2000.MODES[i].text))
        drawText(0.52, listTop - (i - 1) * 0.028, selected and 0.013 or 0.011,
            (selected and "> " or "  ") .. label,
            RenderText.ALIGN_LEFT, selected and green or dim)
    end

    local buttonY = y + 0.078
    local buttonHeight = 0.034
    local tankButton = spec.infiniteTank and "ufo_menu_tankInfinite"
        or "ufo_menu_tankNormal"
    local transferButton = spec.harvestToTrailer and "ufo_menu_trailerOn"
        or "ufo_menu_trailerOff"
    drawFilledRect(x + 0.014, buttonY, 0.255, buttonHeight,
        0.04, 0.12, 0.10, 0.95)
    drawFilledRect(x + 0.285, buttonY, 0.261, buttonHeight,
        spec.harvestToTrailer and 0.08 or 0.04,
        spec.harvestToTrailer and 0.22 or 0.12,
        spec.harvestToTrailer and 0.15 or 0.10, 0.95)
    drawText(x + 0.141, buttonY + 0.011, 0.011,
        g_i18n:getText(tankButton), RenderText.ALIGN_CENTER, white)
    drawText(x + 0.415, buttonY + 0.011, 0.011,
        g_i18n:getText(transferButton), RenderText.ALIGN_CENTER, white)
    drawText(0.5, y + 0.046, 0.011,
        string.format("%s · %s", g_i18n:getText("ufo_menu_unloadState"),
            spec.unloading and g_i18n:getText("ufo_hud_on") or g_i18n:getText("ufo_hud_off")),
        RenderText.ALIGN_CENTER, spec.unloading and warning or dim)
    drawText(0.5, y + 0.025, 0.0105,
        g_i18n:getText("ufo_menu_hint"), RenderText.ALIGN_CENTER, dim)
end

-- ---------------------------------------------------------------------------
-- events
-- ---------------------------------------------------------------------------
UFO2000ToggleHoverEvent = {}
local UFO2000ToggleHoverEvent_mt = Class(UFO2000ToggleHoverEvent, Event)
InitStaticEventClass(UFO2000ToggleHoverEvent, "UFO2000ToggleHoverEvent")

function UFO2000ToggleHoverEvent.emptyNew()
    return Event.new(UFO2000ToggleHoverEvent_mt)
end

function UFO2000ToggleHoverEvent.new(vehicle)
    local self = UFO2000ToggleHoverEvent.emptyNew()
    self.vehicle = vehicle
    return self
end

function UFO2000ToggleHoverEvent:readStream(streamId, connection)
    self.vehicle = NetworkUtil.readNodeObject(streamId)
    self:run(connection)
end

function UFO2000ToggleHoverEvent:writeStream(streamId, connection)
    NetworkUtil.writeNodeObject(streamId, self.vehicle)
end

function UFO2000ToggleHoverEvent:run(connection)
    if self.vehicle ~= nil and self.vehicle.getUFOIsHovering ~= nil then
        self.vehicle:setUFOIsHovering(not self.vehicle:getUFOIsHovering())
    end
end

UFO2000CommandEvent = {}
local UFO2000CommandEvent_mt = Class(UFO2000CommandEvent, Event)
InitStaticEventClass(UFO2000CommandEvent, "UFO2000CommandEvent")

function UFO2000CommandEvent.emptyNew()
    return Event.new(UFO2000CommandEvent_mt)
end

function UFO2000CommandEvent.new(vehicle, command, value)
    local self = UFO2000CommandEvent.emptyNew()
    self.vehicle = vehicle
    self.command = command
    self.value = value
    return self
end

function UFO2000CommandEvent:readStream(streamId, connection)
    self.vehicle = NetworkUtil.readNodeObject(streamId)
    self.command = streamReadString(streamId)
    self.value = streamReadFloat32(streamId)
    self:run(connection)
end

function UFO2000CommandEvent:writeStream(streamId, connection)
    NetworkUtil.writeNodeObject(streamId, self.vehicle)
    streamWriteString(streamId, self.command or "")
    streamWriteFloat32(streamId, self.value or 0)
end

function UFO2000CommandEvent:run(connection)
    if self.vehicle ~= nil and self.vehicle.spec_ufo2000 ~= nil then
        UFO2000.runCommand(self.vehicle, self.command, self.value)
    end
end

UFO2000ToggleBeamEvent = {}
local UFO2000ToggleBeamEvent_mt = Class(UFO2000ToggleBeamEvent, Event)
InitStaticEventClass(UFO2000ToggleBeamEvent, "UFO2000ToggleBeamEvent")

function UFO2000ToggleBeamEvent.emptyNew()
    return Event.new(UFO2000ToggleBeamEvent_mt)
end

function UFO2000ToggleBeamEvent.new(vehicle)
    local self = UFO2000ToggleBeamEvent.emptyNew()
    self.vehicle = vehicle
    return self
end

function UFO2000ToggleBeamEvent:readStream(streamId, connection)
    self.vehicle = NetworkUtil.readNodeObject(streamId)
    self:run(connection)
end

function UFO2000ToggleBeamEvent:writeStream(streamId, connection)
    NetworkUtil.writeNodeObject(streamId, self.vehicle)
end

function UFO2000ToggleBeamEvent:run(connection)
    if self.vehicle ~= nil and self.vehicle.getUFOHasBeamActive ~= nil then
        self.vehicle:setUFOBeamActive(not self.vehicle:getUFOHasBeamActive())
    end
end
