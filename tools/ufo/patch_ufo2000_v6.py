#!/usr/bin/env python3
"""Patch FS25_UFO2000/scripts/UFO2000.lua with the v6 features.

  * harvest mode: the beam cuts the crop and threshes it into a real grain tank
  * infinite tank switch ("grain tank: endless")
  * unloading by hovering above a trailer or a tip station
  * adjustable beam focus in manual pen mode (0.25 m .. 8 m)
  * on board menu shows all of it, keyboard and gamepad

Every replacement is an exact block; running the script twice fails loudly
instead of duplicating code.
"""

import re
import sys

PATH = "FS25_UFO2000/scripts/UFO2000.lua"
src = open(PATH, encoding="utf-8").read()
orig = src


def sub(old, new, count=1):
    global src
    if old not in src:
        sys.exit("pattern not found:\n" + old[:200])
    src = src.replace(old, new, count)


# ---------------------------------------------------------------- constants
sub("""-- manual pen: narrow beam, the player draws by flying
UFO2000.MANUAL_RADIUS = 0.25        -- m, half of the 50 cm pen
UFO2000.MANUAL_STEP = 0.22          -- m of flight per stamped dot
""",
"""-- manual pen: narrow beam, the player draws by flying
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

-- beam focus (radius of the beam on the ground) ----------------------------
UFO2000.PEN_MIN_RADIUS = 0.25       -- 50 cm pen
UFO2000.PEN_MAX_RADIUS = 8.00       -- a really fat beam
UFO2000.PEN_RADIUS_STEP = 0.25

-- unloading: hover above a trailer or a tip station and press the unload key
UFO2000.UNLOAD_RANGE = 15.0         -- m horizontal distance
UFO2000.UNLOAD_MIN_HEIGHT = 1.8     -- m, keep the saucer above the trailer
UFO2000.UNLOAD_SPEED = 3000.0       -- l/s
""")

# ---------------------------------------------------------------- spec init
sub("""    spec.drawTotal = 0
    spec.lastRadius = 0
""",
"""    spec.drawTotal = 0
    spec.lastRadius = 0

    -- v6: harvest / unload / beam focus -----------------------------------
    spec.beamMode = UFO2000.BEAM_MODE_DAMAGE
    spec.penRadius = UFO2000.MANUAL_RADIUS
    spec.infiniteTank = false
    spec.harvestTimer = 0
    spec.harvesting = false
    spec.lastHarvestLiters = 0
    spec.harvestFruitName = ""
    spec.unloadTimer = 0
    spec.unloading = false
    spec.unloadTargetName = ""
    spec.unloadedTotal = 0
""")

# ---------------------------------------------------------------- radius
sub("""    if UFO2000.isManual(spec.patternIndex) then
        -- the pen: the beam stays bundled instead of opening into a cone
        return UFO2000.MANUAL_RADIUS
    end""",
"""    if UFO2000.isManual(spec.patternIndex) then
        -- the pen: the beam stays bundled instead of opening into a cone,
        -- but the pilot can widen or narrow it with the focus keys
        return spec.penRadius or UFO2000.MANUAL_RADIUS
    end""")

# ---------------------------------------------------------------- paint / harvest
sub("""    local r = UFO2000.MANUAL_RADIUS
    UFO2000.damageArea(px - r, pz - r, px + r, pz + r)
end""",
"""    local r = vehicle:getUFOCircleRadius()
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
-- unloading by hovering
-- ---------------------------------------------------------------------------
--- Finds a trailer or a tip station below the saucer.
--- Returns the target object, its display name and whether it is a station.
function UFO2000.findUnloadTarget(vehicle, fillTypeIndex)
    local cx, cy, cz = getWorldTranslation(vehicle.components[1].node)
    local farmId = vehicle:getOwnerFarmId()
    local best, bestDist = nil, UFO2000.UNLOAD_RANGE * UFO2000.UNLOAD_RANGE
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
    if g_currentMission ~= nil and g_currentMission.storageSystem ~= nil then
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
                        and other.getFillUnitSupportsFillType(i, fillTypeIndex)
                    local free = 0
                    if supports then
                        free = other:getFillUnitFreeCapacity(i, fillTypeIndex, farmId)
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

--- Moves grain from the saucer's tank into whatever is below it.
function UFO2000.updateUnloading(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    if not spec.unloading then
        return
    end
    local fillUnitIndex = UFO2000.HARVEST_TANK_INDEX
    local fillLevel = vehicle:getFillUnitFillLevel(fillUnitIndex)
    local fillTypeIndex = vehicle:getFillUnitFillType(fillUnitIndex)
    if fillLevel <= 1 or fillTypeIndex == FillType.UNKNOWN then
        spec.unloading = false
        spec.unloadTargetName = ""
        return
    end

    local target, name, isStation = UFO2000.findUnloadTarget(vehicle, fillTypeIndex)
    if target == nil then
        spec.unloading = false
        spec.unloadTargetName = ""
        return
    end
    spec.unloadTargetName = name

    local farmId = vehicle:getOwnerFarmId()
    local amount = math.min(fillLevel, UFO2000.UNLOAD_SPEED * dt)
    local moved = 0
    if isStation then
        moved = target:addFillLevelFromTool(farmId, amount, fillTypeIndex, nil,
            ToolType.UNLOADING)
    else
        -- trailer: pick the first fill unit that takes the fill type
        for i = 1, target:getFillUnitCount() do
            if target:getFillUnitSupportsFillType(i, fillTypeIndex) then
                moved = target:addFillUnitFillLevel(farmId, i, amount, fillTypeIndex,
                    ToolType.UNLOADING, nil)
                if moved > 0 then
                    break
                end
            end
        end
    end
    if moved > 0 then
        vehicle:addFillUnitFillLevel(farmId, fillUnitIndex, -moved, fillTypeIndex,
            ToolType.UNLOADING, nil)
        spec.unloadedTotal = spec.unloadedTotal + moved
        spec.unloadIdle = 0
    else
        -- nothing moved this tick: keep trying for a moment before stopping,
        -- so a single busy tick does not abort the whole transfer
        spec.unloadIdle = (spec.unloadIdle or 0) + dt
        if spec.unloadIdle > 1.0 then
            spec.unloading = false
            spec.unloadIdle = 0
        end
    end
end""")

# ---------------------------------------------------------------- server tick
sub("""            if spec.beamActive then
                UFO2000.updateDrawing(self, dt)
            end""",
"""            if spec.beamActive then
                UFO2000.updateDrawing(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
                    UFO2000.updateHarvest(self, dt)
                end
            end
            if spec.unloading then
                UFO2000.updateUnloading(self, dt)
            end""")

# ---------------------------------------------------------------- state setters
sub("""function UFO2000:setUFOBeamActive(active)""",
"""--- 1 = press the crop down, 2 = harvest it into the tank
function UFO2000:getUFOBeamMode()
    return self.spec_ufo2000.beamMode
end

function UFO2000:setUFOBeamMode(mode)
    local spec = self.spec_ufo2000
    spec.beamMode = mode == UFO2000.BEAM_MODE_HARVEST and UFO2000.BEAM_MODE_HARVEST
        or UFO2000.BEAM_MODE_DAMAGE
    spec.harvestTimer = 0
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
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

function UFO2000:setUFOBeamActive(active)""")

# ---------------------------------------------------------------- sync
sub("""    streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
end""",
"""    streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
    streamWriteUIntN(streamId, spec.beamMode, 2)
    streamWriteUIntN(streamId, math.floor(spec.penRadius / UFO2000.PEN_RADIUS_STEP + 0.5), 6)
    streamWriteBool(streamId, spec.infiniteTank)
end""")

sub("""    spec.drawProgress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
    UFO2000.applyState(self)""",
"""    spec.drawProgress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
    spec.beamMode = streamReadUIntN(streamId, 2)
    spec.penRadius = streamReadUIntN(streamId, 6) * UFO2000.PEN_RADIUS_STEP
    spec.infiniteTank = streamReadBool(streamId)
    UFO2000.applyState(self)""")

sub("""            local progress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
            local changed = hovering ~= spec.isHovering or beam ~= spec.beamActive
            spec.isHovering = hovering
            spec.altitude = altitude
            spec.beamActive = beam
            spec.patternIndex = pattern
            spec.drawProgress = progress""",
"""            local progress = streamReadUIntN(streamId, 8) / UFO2000.PROGRESS_MAX_SEND
            local mode = streamReadUIntN(streamId, 2)
            local penRadius = streamReadUIntN(streamId, 6) * UFO2000.PEN_RADIUS_STEP
            local infinite = streamReadBool(streamId)
            local changed = hovering ~= spec.isHovering or beam ~= spec.beamActive
            spec.isHovering = hovering
            spec.altitude = altitude
            spec.beamActive = beam
            spec.patternIndex = pattern
            spec.drawProgress = progress
            spec.beamMode = mode
            spec.penRadius = penRadius
            spec.infiniteTank = infinite""")

sub("""            streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
        end
    else""",
"""            streamWriteUIntN(streamId, math.floor(spec.drawProgress * UFO2000.PROGRESS_MAX_SEND + 0.5), 8)
            streamWriteUIntN(streamId, spec.beamMode, 2)
            streamWriteUIntN(streamId, math.floor(spec.penRadius / UFO2000.PEN_RADIUS_STEP + 0.5), 6)
            streamWriteBool(streamId, spec.infiniteTank)
        end
    else""")

# ---------------------------------------------------------------- input
sub("""    -- analog: the same axis a front loader uses, so a joystick works right away""",
"""    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_beamMode", self,
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

    _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_infinite", self,
        UFO2000.actionEventInfinite, true, false, false, true)
    g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_infinite"))

    -- analog: the same axis a front loader uses, so a joystick works right away""")

sub("""function UFO2000:onLeaveVehicle(wasEntered)""",
"""--- sends a small command to the server (mode, focus, unload, endless tank)
function UFO2000.sendCommand(vehicle, command, value)
    if vehicle.isServer then
        UFO2000.runCommand(vehicle, command, value)
    elseif g_client ~= nil and g_client.getServerConnection ~= nil then
        g_client:getServerConnection():sendEvent(UFO2000CommandEvent.new(vehicle, command, value))
    end
end

function UFO2000.runCommand(vehicle, command, value)
    if command == "mode" then
        local mode = vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_HARVEST
            and UFO2000.BEAM_MODE_DAMAGE or UFO2000.BEAM_MODE_HARVEST
        vehicle:setUFOBeamMode(mode)
    elseif command == "penUp" then
        vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() + UFO2000.PEN_RADIUS_STEP)
    elseif command == "penDown" then
        vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() - UFO2000.PEN_RADIUS_STEP)
    elseif command == "unload" then
        local spec = vehicle.spec_ufo2000
        spec.unloading = not spec.unloading
        spec.unloadTimer = 0
    elseif command == "infinite" then
        vehicle:setUFOInfiniteTank(not vehicle:getUFOInfiniteTank())
    end
end

function UFO2000.actionEventBeamMode(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "mode")
    local spec = vehicle.spec_ufo2000
    if g_currentMission ~= nil and vehicle.getIsEntered ~= nil and vehicle:getIsEntered() then
        local text = vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_HARVEST
            and "ufo_notify_modeHarvest" or "ufo_notify_modeDamage"
        g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
            g_i18n:getText(text))
    end
end

function UFO2000.actionEventPenUp(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "penUp")
end

function UFO2000.actionEventPenDown(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "penDown")
end

function UFO2000.actionEventUnload(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "unload")
end

function UFO2000.actionEventInfinite(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, "infinite")
    if g_currentMission ~= nil and vehicle.getIsEntered ~= nil and vehicle:getIsEntered() then
        local text = vehicle:getUFOInfiniteTank() and "ufo_notify_tankEndless" or "ufo_notify_tankNormal"
        g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
            g_i18n:getText(text))
    end
end

function UFO2000:onLeaveVehicle(wasEntered)""")

# ---------------------------------------------------------------- menu / hud
sub("""        local patternName = g_i18n:getText(UFO2000.PATTERNS[spec.patternIndex].name)
        local line""",
"""        local patternName = g_i18n:getText(UFO2000.PATTERNS[spec.patternIndex].name)
        local modeName = spec.beamMode == UFO2000.BEAM_MODE_HARVEST
            and g_i18n:getText("ufo_hud_modeHarvest") or g_i18n:getText("ufo_hud_modeDamage")
        local tank = 0
        local capacity = 0
        if vehicle.getFillUnitFillLevel ~= nil then
            tank = vehicle:getFillUnitFillLevel(UFO2000.HARVEST_TANK_INDEX)
            capacity = vehicle:getFillUnitCapacity(UFO2000.HARVEST_TANK_INDEX)
        end
        local tankLine
        if spec.infiniteTank then
            tankLine = string.format("%s: %s  (%s)", g_i18n:getText("ufo_hud_tank"),
                g_i18n:getText("ufo_hud_tankEndless"), modeName)
        else
            tankLine = string.format("%s: %d / %d l   (%s)", g_i18n:getText("ufo_hud_tank"),
                math.floor(tank), math.floor(capacity), modeName)
        end
        drawText(0.5, 0.092, 0.014, tankLine, RenderText.ALIGN_CENTER, white)
        if spec.unloading or spec.unloadTargetName ~= "" then
            local unloadLine = string.format("%s %s", g_i18n:getText("ufo_hud_unloading"),
                spec.unloadTargetName)
            drawText(0.5, 0.114, 0.014, unloadLine, RenderText.ALIGN_CENTER, green)
        end
        local line""")

sub("""    drawText(0.5, y + 0.045, 0.014, radiusLine, RenderText.ALIGN_CENTER, white)
    drawText(0.5, y + 0.022, 0.012, g_i18n:getText("ufo_menu_hint"), RenderText.ALIGN_CENTER, dim)""",
"""    drawText(0.5, y + 0.062, 0.014, radiusLine, RenderText.ALIGN_CENTER, white)
    local modeLine = spec.beamMode == UFO2000.BEAM_MODE_HARVEST
        and g_i18n:getText("ufo_hud_modeHarvest") or g_i18n:getText("ufo_hud_modeDamage")
    local focusText = string.format("%s %s: %.2f m   %s", g_i18n:getText("ufo_hud_mode"),
        modeLine, vehicle:getUFOCircleRadius(), g_i18n:getText("ufo_menu_keysMode"))
    drawText(0.5, y + 0.042, 0.013, focusText, RenderText.ALIGN_CENTER, green)
    local tankLine = spec.infiniteTank and g_i18n:getText("ufo_hud_tankEndless")
        or string.format("%d l", math.floor(vehicle:getFillUnitFillLevel(UFO2000.HARVEST_TANK_INDEX)))
    drawText(0.5, y + 0.024, 0.012, string.format("%s %s   %s", g_i18n:getText("ufo_hud_tank"),
        tankLine, g_i18n:getText("ufo_menu_keysTank")), RenderText.ALIGN_CENTER, dim)
    drawText(0.5, y + 0.006, 0.011, g_i18n:getText("ufo_menu_hint"), RenderText.ALIGN_CENTER, dim)""")

# panel a little taller to fit the extra rows
sub("""    local width, height = 0.32, 0.34
    local x, y = 0.5 - width / 2, 0.42""",
"""    local width, height = 0.34, 0.40
    local x, y = 0.5 - width / 2, 0.39""")

# ---------------------------------------------------------------- instruments
sub("""-- ---------------------------------------------------------------------------
-- on board menu
-- ---------------------------------------------------------------------------""",
"""-- ---------------------------------------------------------------------------
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
        local want = spec.beamMode == UFO2000.BEAM_MODE_HARVEST and -32 or 32
        local _, ry, rz = getRotation(spec.modeLever)
        setRotation(spec.modeLever, want, ry, rz)
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
-- ---------------------------------------------------------------------------""")

sub("""    spec.beamNode = UFO2000.getNode(self, "beamNode")""",
"""    spec.patternPointer = UFO2000.getNode(self, "patternPointer")
    spec.modeLever = UFO2000.getNode(self, "modeLever")
    spec.focusSlider = UFO2000.getNode(self, "focusSlider")

    spec.beamNode = UFO2000.getNode(self, "beamNode")""")

sub("""    -- beacon keeps turning
    if spec.beaconLight ~= nil then""",
"""    UFO2000.updateCockpit(self)

    -- beacon keeps turning
    if spec.beaconLight ~= nil then""")

# ---------------------------------------------------------------- event
sub("""UFO2000ToggleBeamEvent = {}""",
"""UFO2000CommandEvent = {}
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

UFO2000ToggleBeamEvent = {}""")

# ---------------------------------------------------------------- registration
sub("""    SpecializationUtil.registerFunction(vehicleType, "showUFOStartHint", UFO2000.showUFOStartHint)""",
"""    SpecializationUtil.registerFunction(vehicleType, "showUFOStartHint", UFO2000.showUFOStartHint)
    SpecializationUtil.registerFunction(vehicleType, "getUFOBeamMode", UFO2000.getUFOBeamMode)
    SpecializationUtil.registerFunction(vehicleType, "setUFOBeamMode", UFO2000.setUFOBeamMode)
    SpecializationUtil.registerFunction(vehicleType, "getUFOPenRadius", UFO2000.getUFOPenRadius)
    SpecializationUtil.registerFunction(vehicleType, "setUFOPenRadius", UFO2000.setUFOPenRadius)
    SpecializationUtil.registerFunction(vehicleType, "getUFOInfiniteTank", UFO2000.getUFOInfiniteTank)
    SpecializationUtil.registerFunction(vehicleType, "setUFOInfiniteTank", UFO2000.setUFOInfiniteTank)""")

if src == orig:
    sys.exit("nothing changed")

open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("patched", PATH, "+%d lines" % (src.count("\n") - orig.count("\n")))
