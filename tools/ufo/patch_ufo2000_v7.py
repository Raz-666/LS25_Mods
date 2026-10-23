#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn UFO2000.lua v6 into v7 (all field work modes, cargo hold, mode sounds).

Run from the repository root:

    .venv/bin/python tools/ufo/patch_ufo2000_v7.py

The script is idempotent: if the file already contains
``UFO2000.BEAM_MODE_CULTIVATE`` it does nothing.
"""

import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LUA = os.path.join(REPO, "FS25_UFO2000", "scripts", "UFO2000.lua")


def sub(src, old, new, count=1):
    n = src.count(old)
    if n != count:
        raise SystemExit("expected %d occurrence(s) of:\n%s\n...found %d"
                         % (count, old[:400], n))
    return src.replace(old, new)


CONSTANTS = '''UFO2000.MIN_HARVEST_STATE = 1       -- growth state that can be cut

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
'''

SET_MODE = '''--- 1 = flatten, 2 = harvest, 3 = cultivate, 4 = plow, 5 = sow,
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
        spec.unloading = false
        spec.unloadTargetName = ""
    end
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
    if changed then
        UFO2000.playModeSound(self)
        UFO2000.applyState(self)
    end
end
'''

FIELDWORK = '''-- ---------------------------------------------------------------------------
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
        spec.loading = false
        spec.loadTargetName = ""
        return
    end
    local farmId = vehicle:getOwnerFarmId()
    local free = vehicle:getFillUnitFreeCapacity(cargoIndex, fillType, farmId)
    local available = source:getFillUnitFillLevel(unit)
    local amount = math.min(free, math.min(available, UFO2000.LOAD_SPEED * dt))
    if amount <= 1 then
        spec.loading = false
        return
    end

    local taken = -source:addFillUnitFillLevel(farmId, unit, -amount,
        fillType, ToolType.LOADING, nil)
    if taken <= 0 then
        spec.loading = false
        return
    end
    local added = vehicle:addFillUnitFillLevel(farmId, cargoIndex, taken,
        fillType, ToolType.LOADING, nil)
    if added < taken then
        -- the hold filled up in between: give the rest back
        source:addFillUnitFillLevel(farmId, unit, taken - added,
            fillType, ToolType.LOADING, nil)
    end
    spec.loading = added > 0
    spec.loadTargetName = name
    spec.loadedTotal = (spec.loadedTotal or 0) + added
end

'''

SOUNDS = '''-- ---------------------------------------------------------------------------
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

'''


def main():
    with io.open(LUA, encoding="utf-8") as fh:
        src = fh.read()

    if "UFO2000.BEAM_MODE_CULTIVATE" in src:
        print("already patched, nothing to do")
        return

    # ---- 1. header + constants -------------------------------------------
    src = sub(src, """  * crop circle patterns: the beam sweeps the field below and leaves a mown
    pattern - select the geometry in the on-board menu (key M) and fire the
    beam (stock \"implement extra\" action, Z)""",
              """  * crop circle patterns: the beam sweeps the field below and leaves a mown
    pattern - select the geometry in the on-board menu (key M) and fire the
    beam (stock \"implement extra\" action, Z)
  * eight working modes, all of them invisible: flatten, harvest, cultivate,
    plow, sow, fertilize, load and unload.  Each mode has its own coloured beam
    cone, its own light colour, its own hum and its own little cockpit lamp
  * a virtual cargo hold: hover over a trailer to suck its load in, hover over
    a trailer or tip station to pour it out again""")

    src = sub(src, "UFO2000.MIN_HARVEST_STATE = 1       # growth state that can be cut"
              .replace("#", "--"), CONSTANTS)

    # ---- 2. network: 8 modes need 4 bits ---------------------------------
    src = sub(src, "spec.beamMode = streamReadUIntN(streamId, 2)",
              "spec.beamMode = streamReadUIntN(streamId, 3)")
    src = sub(src, "local mode = streamReadUIntN(streamId, 2)",
              "local mode = streamReadUIntN(streamId, 3)")
    src = sub(src, "streamWriteUIntN(streamId, spec.beamMode, 2)",
              "streamWriteUIntN(streamId, spec.beamMode, 3)", count=2)

    # ---- 3. onLoad state --------------------------------------------------
    src = sub(src, """    spec.unloadTargetName = ""
    spec.unloadedTotal = 0
""",
              """    spec.unloadTargetName = ""
    spec.unloadedTotal = 0

    -- v7: field work, cargo hold and mode sounds ---------------------------
    spec.workTimer = 0
    spec.working = false
    spec.lastWorkArea = 0
    spec.sowFruitIndex = 1
    spec.loading = false
    spec.loadTargetName = ""
    spec.loadedTotal = 0
""")

    src = sub(src, """    spec.beamNode = UFO2000.getNode(self, "beamNode")
    spec.beamLight = UFO2000.getNode(self, "beamLight")""",
              """    -- one cone per mode: only the one of the selected mode is ever visible
    spec.beamNodes = {}
    for i = 1, #UFO2000.MODES do
        local node = UFO2000.getNode(self, UFO2000.MODES[i].node)
        spec.beamNodes[i] = node
        if node ~= nil then
            setVisibility(node, false)
            setScale(node, 1, 1, 1)
        end
    end
    spec.beamLight = UFO2000.getNode(self, "beamLight")""")

    src = sub(src, """    if spec.beamNode ~= nil then
        setVisibility(spec.beamNode, false)
        setScale(spec.beamNode, 1, 1, 1)
    end
    if spec.beamLight ~= nil then""",
              """    if spec.beamLight ~= nil then""")

    src = sub(src, """    spec.modeLever = UFO2000.getNode(self, "modeLever")
    spec.focusSlider = UFO2000.getNode(self, "focusSlider")""",
              """    spec.modeLever = UFO2000.getNode(self, "modeLever")
    spec.modeNeedle = UFO2000.getNode(self, "modeNeedle")
    spec.focusSlider = UFO2000.getNode(self, "focusSlider")""")

    src = sub(src, """    spec.dirtyFlag = self:getNextDirtyFlag()""",
              """    UFO2000.loadModeSounds(self)

    spec.dirtyFlag = self:getNextDirtyFlag()""")

    # ---- 4. mode setter ---------------------------------------------------
    src = sub(src, """--- 1 = press the crop down, 2 = harvest it into the tank
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
end""", SET_MODE)

    # ---- 5. applyState: show exactly one cone -----------------------------
    src = sub(src, """    if spec.beamNode ~= nil then
        setVisibility(spec.beamNode, spec.beamActive)
    end
    if spec.beamLight ~= nil then
        setVisibility(spec.beamLight, spec.beamActive)
    end""",
              """    if spec.beamNodes ~= nil then
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
    end""")

    # ---- 6. field work + cargo, inserted before the unloading section -----
    src = sub(src, """-- ---------------------------------------------------------------------------
-- unloading by hovering
-- ---------------------------------------------------------------------------""",
              FIELDWORK + """-- ---------------------------------------------------------------------------
-- unloading by hovering
-- ---------------------------------------------------------------------------""")

    # ---- 7. updateUnloading works on whichever unit has something in it ---
    src = sub(src, """    local fillUnitIndex = UFO2000.HARVEST_TANK_INDEX
    local fillLevel = vehicle:getFillUnitFillLevel(fillUnitIndex)
    local fillTypeIndex = vehicle:getFillUnitFillType(fillUnitIndex)
    if fillLevel <= 1 or fillTypeIndex == FillType.UNKNOWN then
        spec.unloading = false
        spec.unloadTargetName = ""
        return
    end""",
              """    -- first the grain tank, then the big cargo hold
    local fillUnitIndex, fillTypeIndex = UFO2000.getLoadedFillUnitIndex(vehicle)
    if fillUnitIndex == nil then
        spec.unloading = false
        spec.unloadTargetName = ""
        return
    end
    local fillLevel = vehicle:getFillUnitFillLevel(fillUnitIndex)""")

    # ---- 8. drawing only in flatten mode ---------------------------------
    src = sub(src, """    if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
        -- in harvest mode updateHarvest does the work: nothing is pressed down,
        -- neither in pen mode nor with a ground pattern
        spec.drawProgress = 1
        return
    end""",
              """    if spec.beamMode ~= UFO2000.BEAM_MODE_DAMAGE then
        -- only the flatten mode presses crop circles; harvest, the field work
        -- modes, loading and unloading never touch the plants that way
        spec.drawProgress = 1
        return
    end""")

    # ---- 9. simulation wiring --------------------------------------------
    src = sub(src, """            if spec.beamActive then
                UFO2000.updateDrawing(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
                    UFO2000.updateHarvest(self, dt)
                end
            end""",
              """            if spec.beamMode == UFO2000.BEAM_MODE_UNLOAD and spec.beamActive then
                spec.unloading = true
            end
            if spec.beamActive then
                UFO2000.updateDrawing(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_HARVEST then
                    UFO2000.updateHarvest(self, dt)
                end
                UFO2000.updateFieldWork(self, dt)
                if spec.beamMode == UFO2000.BEAM_MODE_LOAD then
                    UFO2000.updateLoading(self, dt)
                end
            end""")

    # ---- 10. client visuals: one cone, blinking, coloured light ----------
    src = sub(src, """        if spec.beamNode ~= nil then
            local coneHeight = math.max(height - 0.25, 0.5)
            setScale(spec.beamNode, radius * (1 + pulse), coneHeight, radius * (1 + pulse))
            setRotation(spec.beamNode, 0, time * 70 % 360, 0)
            setVisibility(spec.beamNode, true)
        end""",
              """        if spec.beamNodes ~= nil then
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
        end""")

    src = sub(src, """    else
        if spec.beamNode ~= nil then
            setVisibility(spec.beamNode, false)
        end
        if spec.ringNode ~= nil then
            setVisibility(spec.ringNode, false)
        end
    end
end""",
              """    else
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
    end

    -- the loops follow the mode: work hum, suction, pouring
    UFO2000.updateModeSounds(self)
end""")

    # ---- 11. command handling -------------------------------------------
    src = sub(src, """    if command == "mode" then
        local mode = vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_HARVEST
            and UFO2000.BEAM_MODE_DAMAGE or UFO2000.BEAM_MODE_HARVEST
        vehicle:setUFOBeamMode(mode)
    elseif command == "penUp" then
        vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() + UFO2000.PEN_RADIUS_STEP)
    elseif command == "penDown" then
        vehicle:setUFOPenRadius(vehicle:getUFOPenRadius() - UFO2000.PEN_RADIUS_STEP)""",
              """    if command == "mode" then
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
        end""")

    src = sub(src, """function UFO2000.actionEventBeamMode(vehicle, actionName, inputValue, callbackState)
    if inputValue == 0 then
        return
    end
    UFO2000.sendCommand(vehicle, \"mode\")
    local spec = vehicle.spec_ufo2000
    if g_currentMission ~= nil and vehicle.getIsEntered ~= nil and vehicle:getIsEntered() then
        local text = vehicle:getUFOBeamMode() == UFO2000.BEAM_MODE_HARVEST
            and \"ufo_notify_modeHarvest\" or \"ufo_notify_modeDamage\"
        g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
            g_i18n:getText(text))
    end
end""",
              """--- next / previous seed in sowing mode
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
    UFO2000.sendCommand(vehicle, \"mode\")
    if g_currentMission ~= nil and vehicle.getIsEntered ~= nil and vehicle:getIsEntered() then
        local info = UFO2000.getModeInfo(vehicle:getUFOBeamMode() % UFO2000.MODE_COUNT + 1)
        g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
            string.format(g_i18n:getText(\"ufo_notify_mode\"), g_i18n:getText(info.text)))
    end
end""")

    # ---- 11b. mode sounds ------------------------------------------------
    src = sub(src, """-- ---------------------------------------------------------------------------
-- cockpit instruments
-- ---------------------------------------------------------------------------""",
              SOUNDS + """-- ---------------------------------------------------------------------------
-- cockpit instruments
-- ---------------------------------------------------------------------------""")

    # ---- 12. cockpit instruments ----------------------------------------
    src = sub(src, """    if spec.modeLever ~= nil then
        local want = spec.beamMode == UFO2000.BEAM_MODE_HARVEST and -32 or 32
        local _, ry, rz = getRotation(spec.modeLever)
        setRotation(spec.modeLever, want, ry, rz)
    end""",
              """    if spec.modeLever ~= nil then
        -- the lever travels through all eight modes
        local t = (spec.beamMode - 1) / (UFO2000.MODE_COUNT - 1)
        local _, ry, rz = getRotation(spec.modeLever)
        setRotation(spec.modeLever, 32 - 64 * t, ry, rz)
    end
    if spec.modeNeedle ~= nil then
        -- the needle on the dial points at the selected segment
        setRotation(spec.modeNeedle, 0, -(spec.beamMode - 1) * 45, 0)
    end""")

    # ---- 13. HUD ---------------------------------------------------------
    src = sub(src, """        local modeName = spec.beamMode == UFO2000.BEAM_MODE_HARVEST
            and g_i18n:getText(\"ufo_hud_modeHarvest\") or g_i18n:getText(\"ufo_hud_modeDamage\")""",
              """        local modeName = g_i18n:getText(UFO2000.getModeInfo(spec.beamMode).text)""")

    src = sub(src, """    local modeLine = spec.beamMode == UFO2000.BEAM_MODE_HARVEST
        and g_i18n:getText(\"ufo_hud_modeHarvest\") or g_i18n:getText(\"ufo_hud_modeDamage\")""",
              """    local modeLine = g_i18n:getText(UFO2000.getModeInfo(spec.beamMode).text)""")

    # menu: show the whole mode list, the selected one highlighted
    src = sub(src, """    local tankLine = spec.infiniteTank and g_i18n:getText(\"ufo_hud_tankEndless\")
        or string.format(\"%d l\", math.floor(vehicle:getFillUnitFillLevel(UFO2000.HARVEST_TANK_INDEX)))
    drawText(0.5, y + 0.024, 0.012, string.format(\"%s %s   %s\", g_i18n:getText(\"ufo_hud_tank\"),
        tankLine, g_i18n:getText(\"ufo_menu_keysTank\")), RenderText.ALIGN_CENTER, dim)""",
              """    local tankLine = spec.infiniteTank and g_i18n:getText(\"ufo_hud_tankEndless\")
        or string.format(\"%d l\", math.floor(vehicle:getFillUnitFillLevel(UFO2000.HARVEST_TANK_INDEX)))
    drawText(0.5, y + 0.024, 0.012, string.format(\"%s %s   %s\", g_i18n:getText(\"ufo_hud_tank\"),
        tankLine, g_i18n:getText(\"ufo_menu_keysTank\")), RenderText.ALIGN_CENTER, dim)

    -- the eight working modes, the active one lit up
    local modeY = y - 0.030
    for i = 1, UFO2000.MODE_COUNT do
        local info = UFO2000.MODES[i]
        local selected = i == spec.beamMode
        local label = string.format(\"%d %s\", i, g_i18n:getText(info.text))
        drawText(0.5, modeY - (i - 1) * 0.016, selected and 0.013 or 0.011,
            (selected and \"> \" or \"  \") .. label .. (selected and \" <\" or \"  \"),
            RenderText.ALIGN_CENTER, selected and green or dim)
    end
    drawText(0.5, modeY - UFO2000.MODE_COUNT * 0.016 - 0.008, 0.011,
        g_i18n:getText(\"ufo_menu_modeHint\"), RenderText.ALIGN_CENTER, dim)""")

    # ---- 14. onLeaveVehicle stops the loops ------------------------------
    src = sub(src, """function UFO2000:onLeaveVehicle(wasEntered)
    local spec = self.spec_ufo2000
    spec.menuOpen = false""",
              """function UFO2000:onLeaveVehicle(wasEntered)
    local spec = self.spec_ufo2000
    spec.menuOpen = false
    spec.mouseWasDown = false
    UFO2000.setMenuCursor(false)
    spec.unloading = false""")

    with io.open(LUA, "w", encoding="utf-8") as fh:
        fh.write(src)
    print("patched", LUA)


if __name__ == "__main__":
    main()
