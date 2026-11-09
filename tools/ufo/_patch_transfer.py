#!/usr/bin/env python3
"""Adds the combination transfer beam, the status ticker and the richer HUD
to tools/ufo/UFO2000.lua (the single Lua source for all three saucers)."""

import io
import sys

LUA = "tools/ufo/UFO2000.lua"

src = io.open(LUA, encoding="utf-8").read()
problems = []


def sub(old, new, count=1, label=""):
    global src
    if old not in src:
        problems.append("anchor missing: " + (label or old[:60]))
        return
    src = src.replace(old, new, count)


# ---------------------------------------------------------------- constants
sub(
    "UFO2000.HARVEST_TRAILER_RADIUS = 0.85  -- m, narrow visible transfer beam",
    """UFO2000.HARVEST_TRAILER_RADIUS = 0.85  -- m, narrow visible transfer beam
UFO2000.TRANSFER_MAX_TARGETS = 4        -- truck + trailers shown in the HUD
UFO2000.TRANSFER_RETRY_TIME = 2.5       -- s before a refusing target is retried
UFO2000.STATUS_TIME = 4.0               -- s the action ticker stays visible""",
    label="constants")

# ------------------------------------------------------- target list search
old_find_start = "function UFO2000.findUnloadTarget(vehicle, fillTypeIndex, centerX, centerZ,"
old_find_end = "--- Moves a limited amount from one UFO fill unit to a vehicle or tip station."
start = src.index(old_find_start)
end = src.index(old_find_end)

new_find = '''--- Every destination under the saucer, nearest first.
--- A truck and the trailers behind it are separate vehicles in FS25, so this
--- returns a list: the transfer beam works through the whole combination one
--- after the other, without any extra key press.
function UFO2000.findUnloadTargets(vehicle, fillTypeIndex, centerX, centerZ,
        includeStations, searchRange)
    local cx, cy, cz = getWorldTranslation(vehicle.components[1].node)
    cx = centerX or cx
    cz = centerZ or cz
    local farmId = vehicle:getOwnerFarmId()
    local range = searchRange or UFO2000.UNLOAD_RANGE
    local list, seen = {}, {}

    local function consider(obj, node, name, isStation, free)
        if node == nil or obj == nil or seen[obj] then
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
        if dist > range * range then
            return
        end
        seen[obj] = true
        table.insert(list, {
            target = obj,
            name = name or "",
            isStation = isStation,
            free = free or 0,
            dist = dist,
        })
    end

    -- 1. tip stations: the classic "hover over the yard" case
    if includeStations ~= false
        and g_currentMission ~= nil and g_currentMission.storageSystem ~= nil then
        for _, station in pairs(g_currentMission.storageSystem:getUnloadingStations()) do
            local allowed = station.getIsFillTypeAllowed ~= nil
                and station:getIsFillTypeAllowed(fillTypeIndex)
            local free = 0
            if allowed and station.getFreeCapacity ~= nil then
                free = station:getFreeCapacity(fillTypeIndex, farmId) or 0
            end
            if free > 1 then
                local node = nil
                if station.unloadTriggers ~= nil then
                    for _, trigger in pairs(station.unloadTriggers) do
                        node = trigger.exactFillRootNode or trigger.triggerNode
                        if node ~= nil then
                            consider(station, node, station.stationName or "Tip station",
                                true, free)
                        end
                    end
                end
                if node == nil then
                    consider(station, station.rootNode, station.stationName or "Tip station",
                        true, free)
                end
            end
        end
    end

    -- 2. every vehicle below the saucer: the truck first, then its trailers
    if g_currentMission ~= nil and g_currentMission.vehicleSystem ~= nil then
        for _, other in pairs(g_currentMission.vehicleSystem:getVehicles()) do
            if other ~= vehicle and other.getFillUnitCount ~= nil then
                local free = 0
                for i = 1, other:getFillUnitCount() do
                    local supports = other.getFillUnitSupportsFillType ~= nil
                        and other:getFillUnitSupportsFillType(i, fillTypeIndex)
                    if supports and other.getFillUnitFreeCapacity ~= nil then
                        free = free
                            + (other:getFillUnitFreeCapacity(i, fillTypeIndex, farmId) or 0)
                    end
                end
                if free > 1 and other.components ~= nil then
                    local name = other.getName ~= nil and other:getName() or "Trailer"
                    consider(other, other.components[1].node, name, false, free)
                end
            end
        end
    end

    table.sort(list, function(a, b)
        return a.dist < b.dist
    end)
    return list
end


--- Nearest destination only - used by the loading beam and the old call sites.
function UFO2000.findUnloadTarget(vehicle, fillTypeIndex, centerX, centerZ,
        includeStations, searchRange)
    local list = UFO2000.findUnloadTargets(vehicle, fillTypeIndex, centerX,
        centerZ, includeStations, searchRange)
    local entry = list[1]
    if entry == nil then
        return nil, "", false
    end
    return entry.target, entry.name, entry.isStation
end


--- Next destination that still has room and did not just refuse this fill type
--- (a trailer that only takes a different fruit, for example).
function UFO2000.pickTransferTarget(vehicle, list)
    local spec = vehicle.spec_ufo2000
    local now = g_currentMission ~= nil and g_currentMission.time or 0
    spec.transferSkip = spec.transferSkip or {}
    for i = 1, #list do
        local entry = list[i]
        local skipUntil = spec.transferSkip[tostring(entry.target)]
        if (skipUntil == nil or skipUntil < now) and entry.free > 1 then
            return entry
        end
    end
    return nil
end


--- Remembers that a destination refused, so the beam moves on to the next one
--- instead of hammering the same trailer every frame.
function UFO2000.markTransferRefused(vehicle, entry)
    if entry == nil or entry.target == nil then
        return
    end
    local spec = vehicle.spec_ufo2000
    local now = g_currentMission ~= nil and g_currentMission.time or 0
    spec.transferSkip = spec.transferSkip or {}
    spec.transferSkip[tostring(entry.target)] = now + UFO2000.TRANSFER_RETRY_TIME * 1000
end


--- Short litre format for the HUD: 21.500 l -> "21,5 Tsd".
function UFO2000.formatLiters(liters)
    liters = liters or 0
    if liters >= 1000000 then
        return string.format("%.1f Mio", liters / 1000000)
    elseif liters >= 10000 then
        return string.format("%.0f Tsd", liters / 1000)
    end
    return string.format("%d", math.floor(liters))
end


--- Builds the "who is being filled" list for the HUD. Runs twice a second on
--- the client as well, so multiplayer players see the same queue.
function UFO2000.updateTransferQueue(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    spec.transferQueueTime = (spec.transferQueueTime or 0) + dt
    if spec.transferQueueTime < 0.5 then
        return
    end
    spec.transferQueueTime = 0
    spec.transferQueue = {}
    if not (spec.harvestToTrailer or spec.unloading) or not spec.isHovering then
        return
    end

    local fillUnitIndex, fillTypeIndex
    if spec.unloading then
        fillUnitIndex, fillTypeIndex = UFO2000.getLoadedFillUnitIndex(vehicle)
    else
        fillUnitIndex = UFO2000.HARVEST_TANK_INDEX
        fillTypeIndex = vehicle:getFillUnitFillType(fillUnitIndex)
    end
    if fillUnitIndex == nil or fillTypeIndex == nil
        or fillTypeIndex == FillType.UNKNOWN then
        return
    end

    local centerX, centerZ
    if not spec.unloading then
        centerX, centerZ = UFO2000.getHarvestTransferPosition(vehicle)
    end
    local list = UFO2000.findUnloadTargets(vehicle, fillTypeIndex, centerX, centerZ,
        spec.unloading,
        spec.unloading and UFO2000.UNLOAD_RANGE or UFO2000.HARVEST_TRAILER_RANGE)
    for i = 1, math.min(#list, UFO2000.TRANSFER_MAX_TARGETS) do
        table.insert(spec.transferQueue, {name = list[i].name, free = list[i].free})
    end
end


'''
src = src[:start] + new_find + src[end:]

# ------------------------------------------------------------- notify/status
sub('''local function notify(vehicle, textKey, ...)
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
end''',
'''local function notify(vehicle, textKey, ...)
    local text = g_i18n ~= nil and g_i18n:getText(textKey) or textKey
    local args = {...}
    if #args > 0 then
        local unpackArgs = table.unpack or unpack
        text = string.format(text, unpackArgs(args))
    end
    -- the same text also runs through the HUD ticker, so the player can see
    -- what the last key press changed even when notifications are switched off
    local spec = vehicle.spec_ufo2000
    if spec ~= nil then
        spec.statusText = text
        spec.statusTime = UFO2000.STATUS_TIME
    end
    if g_currentMission == nil or g_currentMission.addIngameNotification == nil
        or vehicle.getIsEntered == nil or not vehicle:getIsEntered() then
        return
    end
    g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO, text)
end''',
    label="notify")

# --------------------------------------------------------------- unloading
start = src.index("function UFO2000.updateUnloading(vehicle, dt)")
end = src.index("--- World position of the narrow, offset second tractor beam used for filling")
new_unload = '''function UFO2000.updateUnloading(vehicle, dt)
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

    local list = UFO2000.findUnloadTargets(vehicle, fillTypeIndex)
    local entry = UFO2000.pickTransferTarget(vehicle, list)
    if entry == nil then
        UFO2000.setUnloadingState(vehicle, false)
        return
    end
    UFO2000.setUnloadTargetName(vehicle, entry.name)

    local amount = math.min(fillLevel, UFO2000.UNLOAD_SPEED * dt)
    if amount <= 0 then
        UFO2000.setUnloadingState(vehicle, false)
        return
    end

    -- The helper restores any amount the destination did not accept.
    local moved = UFO2000.transferFillToTarget(vehicle, fillUnitIndex,
        fillTypeIndex, entry.target, entry.isStation, amount)
    if moved <= 0 then
        -- try the next vehicle of the combination instead of stalling
        UFO2000.markTransferRefused(vehicle, entry)
        spec.unloadIdle = (spec.unloadIdle or 0) + dt
        if spec.unloadIdle > 2.5 then
            UFO2000.setUnloadingState(vehicle, false)
            spec.unloadIdle = 0
        end
        return
    end
    spec.unloadedTotal = spec.unloadedTotal + moved
    spec.unloadIdle = 0
end


'''
src = src[:start] + new_unload + src[end:]

# ------------------------------------------------------- harvest -> trailer
start = src.index("function UFO2000.updateHarvestToTrailer(vehicle, dt)")
end = src.index("--- presses the next slice of the pattern into the field (server side)")
new_transfer = '''function UFO2000.updateHarvestToTrailer(vehicle, dt)
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
    local list = UFO2000.findUnloadTargets(vehicle, fillTypeIndex, beamX, beamZ,
        false, UFO2000.HARVEST_TRAILER_RANGE)
    local entry = UFO2000.pickTransferTarget(vehicle, list)
    if entry == nil then
        UFO2000.setDirectTargetName(vehicle, "")
        return
    end
    UFO2000.setDirectTargetName(vehicle, entry.name)
    local moved = UFO2000.transferFillToTarget(vehicle, fillUnitIndex,
        fillTypeIndex, entry.target, entry.isStation,
        UFO2000.HARVEST_TRAILER_SPEED * dt)
    if moved <= 0 then
        UFO2000.markTransferRefused(vehicle, entry)
        return
    end
    spec.unloadedTotal = (spec.unloadedTotal or 0) + moved
end


'''
src = src[:start] + new_transfer + src[end:]

# ---------------------------------------------------------------- tick glue
sub('''function UFO2000:onUpdateTick(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)''',
    '''function UFO2000:onUpdateTick(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)''',
    label="tick header")

sub('''    spec.legsAlpha = UFO2000.clamp(
        spec.legsAlpha + (spec.legsTarget - spec.legsAlpha) * math.min(dt * spec.legSpeed, 1), 0, 1)''',
    '''    spec.legsAlpha = UFO2000.clamp(
        spec.legsAlpha + (spec.legsTarget - spec.legsAlpha) * math.min(dt * spec.legSpeed, 1), 0, 1)
    spec.statusTime = math.max((spec.statusTime or 0) - dt, 0)
    UFO2000.updateTransferQueue(self, dt)''',
    label="tick glue")

io.open(LUA, "w", encoding="utf-8", newline="\n").write(src)

if problems:
    print("PROBLEMS:")
    for p in problems:
        print("  " + p)
    sys.exit(1)
print("patched", LUA)
