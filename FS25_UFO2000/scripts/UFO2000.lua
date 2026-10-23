--[[
UFO2000 - hover flight specialization for the cute little saucer.

The vanilla vehicle stack (Drivable/Motorized/Enterable) keeps handling the
engine, fuel, HUD, cameras, honking and enter/leave.  This specialization adds
what a base-game vehicle cannot do:

  * hover flight:  the craft leaves the ground, floats on a damped magnetic
                   cushion and is steered with the normal drive keys
  * altitude control with two extra keys (up / down)
  * retractable landing legs and a tractor beam that can be switched on
  * a rotating red beacon and a wobbling little pilot (client side only)

Everything that changes the vehicle state is simulated on the server; clients
send their key state and get hover state / altitude / beam state back through
the standard update stream, so it works in multiplayer.

Author: Arena.ai Agent Mode (FS25 mod, generated from tools/ufo)
--]]

UFO2000 = {}
local UFO2000_mt = Class(UFO2000, Specialization)

UFO2000.ALTITUDE_SEND_BITS = 8
UFO2000.ALTITUDE_MAX_SEND = 255

-- flight tuning (all values are for the UFO 2000 and do not need an XML entry)
UFO2000.MAX_ALTITUDE = 120.0        -- metres above ground
UFO2000.MIN_ALTITUDE = 1.10         -- hover height with the legs retracted
UFO2000.CLIMB_SPEED = 6.5           -- m/s while the climb key is held
UFO2000.YAW_SPEED = 55.0            -- deg/s at full steering input
UFO2000.MAX_SPEED = 8.5             -- m/s (~31 km/h) horizontal flight
UFO2000.LEG_RETRACT_TIME = 1.4      -- seconds to fold the legs away

function UFO2000.prerequisitesPresent(specializations)
    return true
end

--- Looks a node up by its i3dMappings id (no extra XML entries needed).
function UFO2000.getNode(vehicle, name)
    if vehicle.i3dMappings == nil then
        return nil
    end
    for _, mapping in ipairs(vehicle.i3dMappings) do
        if mapping.id == name then
            return mapping.node
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
end

function UFO2000.registerOverwrittenFunctions(vehicleType)
    -- while hovering the craft must not be pushed around by wheel/ground physics
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getCanMotorRun", UFO2000.getCanMotorRun)
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
-- load / save
-- ---------------------------------------------------------------------------
function UFO2000:onLoad(savegame)
    local spec = self.spec_ufo2000

    spec.maxAltitude = UFO2000.MAX_ALTITUDE
    spec.minAltitude = UFO2000.MIN_ALTITUDE
    spec.climbSpeed = UFO2000.CLIMB_SPEED
    spec.yawSpeed = UFO2000.YAW_SPEED
    spec.maxSpeed = UFO2000.MAX_SPEED
    spec.legSpeed = 1 / UFO2000.LEG_RETRACT_TIME

    spec.isHovering = false
    spec.appliedHovering = false
    spec.altitude = spec.minAltitude
    spec.altitudeTarget = spec.minAltitude
    spec.yaw = 0
    spec.pitch = 0
    spec.roll = 0
    spec.speed = 0
    spec.inputVertical = 0
    spec.verticalDirty = false
    spec.legsTarget = 0
    spec.legsAlpha = 0
    spec.beamActive = false

    spec.appliedHovering = false
    spec.legNodes = {}
    spec.legRestRotation = {}
    for i = 0, 2 do
        local node = UFO2000.getNode(self, "leg" .. i)
        if node ~= nil then
            table.insert(spec.legNodes, node)
            table.insert(spec.legRestRotation, select(3, getRotation(node)))
        end
    end

    spec.beamNode = UFO2000.getNode(self, "beamNode")
    spec.beamLight = UFO2000.getNode(self, "beamLight")
    spec.beaconLight = UFO2000.getNode(self, "beaconLight")
    spec.alienNode = UFO2000.getNode(self, "alienNode")
    spec.alienBaseY = 1.02
    if spec.alienNode ~= nil then
        _, spec.alienBaseY = getTranslation(spec.alienNode)
    end

    if spec.beamNode ~= nil then
        setVisibility(spec.beamNode, false)
    end
    if spec.beamLight ~= nil then
        setVisibility(spec.beamLight, false)
    end

    spec.dirtyFlag = self:getNextDirtyFlag()
    spec.actionEvents = {}

    -- the craft has no wheels, so the steering times used by Drivable would be
    -- nil/0 and produce NaN inputs; keep sane values around
    if self.minRotTime == nil or self.minRotTime == 0 then
        self.minRotTime = -0.001
    end
    if self.maxRotTime == nil or self.maxRotTime == 0 then
        self.maxRotTime = 0.001
    end
end

function UFO2000:onDelete()
end

-- ---------------------------------------------------------------------------
-- network
-- ---------------------------------------------------------------------------
function UFO2000:onReadStream(streamId, connection)
    local spec = self.spec_ufo2000
    spec.isHovering = streamReadBool(streamId)
    spec.altitude = streamReadUIntN(streamId, UFO2000.ALTITUDE_SEND_BITS) / UFO2000.ALTITUDE_MAX_SEND * spec.maxAltitude
    spec.beamActive = streamReadBool(streamId)
    UFO2000.applyState(self)
end

function UFO2000:onWriteStream(streamId, connection)
    local spec = self.spec_ufo2000
    streamWriteBool(streamId, spec.isHovering)
    local alt = math.floor(math.clamp(spec.altitude / spec.maxAltitude, 0, 1) * UFO2000.ALTITUDE_MAX_SEND + 0.5)
    streamWriteUIntN(streamId, alt, UFO2000.ALTITUDE_SEND_BITS)
    streamWriteBool(streamId, spec.beamActive)
end

function UFO2000:onReadUpdateStream(streamId, timestamp, connection)
    local spec = self.spec_ufo2000
    if connection:getIsServer() then
        if streamReadBool(streamId) then
            local hovering = streamReadBool(streamId)
            local altitude = streamReadUIntN(streamId, UFO2000.ALTITUDE_SEND_BITS) / UFO2000.ALTITUDE_MAX_SEND * spec.maxAltitude
            local beam = streamReadBool(streamId)
            local changed = hovering ~= spec.isHovering or beam ~= spec.beamActive
            spec.isHovering = hovering
            spec.altitude = altitude
            spec.beamActive = beam
            if changed then
                UFO2000.applyState(self)
            end
        end
    else
        if streamReadBool(streamId) then
            spec.inputVertical = streamReadIntN(streamId, 2)
        end
    end
end

function UFO2000:onWriteUpdateStream(streamId, connection, dirtyMask)
    local spec = self.spec_ufo2000
    if connection:getIsServer() then
        if streamWriteBool(streamId, bit32.band(dirtyMask, spec.dirtyFlag) ~= 0) then
            streamWriteBool(streamId, spec.isHovering)
            local alt = math.floor(math.clamp(spec.altitude / spec.maxAltitude, 0, 1) * UFO2000.ALTITUDE_MAX_SEND + 0.5)
            streamWriteUIntN(streamId, alt, UFO2000.ALTITUDE_SEND_BITS)
            streamWriteBool(streamId, spec.beamActive)
        end
    else
        if streamWriteBool(streamId, spec.verticalDirty) then
            streamWriteIntN(streamId, spec.inputVertical, 2)
            spec.verticalDirty = false
        end
    end
end

-- ---------------------------------------------------------------------------
-- state changes (server authoritative)
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

function UFO2000:setUFOAltitude(altitude)
    local spec = self.spec_ufo2000
    altitude = math.clamp(altitude, spec.minAltitude, spec.maxAltitude)
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
    if not self.isServer then
        return
    end

    if hovering then
        if not self:getIsMotorStarted() and self.getIsMotorStarted ~= nil then
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
    else
        spec.isHovering = false
        spec.altitude = spec.minAltitude
        spec.altitudeTarget = spec.minAltitude
        spec.hoverY = nil
    end
    self:raiseDirtyFlags(spec.dirtyFlag)
    UFO2000.applyState(self)
end

function UFO2000:setUFOBeamActive(active)
    local spec = self.spec_ufo2000
    if spec.beamActive == active then
        return
    end
    spec.beamActive = active
    if self.isServer then
        self:raiseDirtyFlags(spec.dirtyFlag)
    end
    UFO2000.applyState(self)
end

--- applies server state to the local scene (called on clients, too)
function UFO2000.applyState(vehicle)
    local spec = vehicle.spec_ufo2000
    if spec == nil then
        return
    end
    spec.appliedHovering = spec.isHovering
    spec.legsTarget = spec.isHovering and 1 or 0
    if spec.beamNode ~= nil then
        setVisibility(spec.beamNode, spec.beamActive)
    end
    if spec.beamLight ~= nil then
        setVisibility(spec.beamLight, spec.beamActive)
    end
end

-- ---------------------------------------------------------------------------
-- input
-- ---------------------------------------------------------------------------
function UFO2000:onRegisterActionEvents(isActiveForInput, isActiveForInputIgnoreSelection)
    if self.isClient then
        local spec = self.spec_ufo2000
        self:clearActionEventsTable(spec.actionEvents)
        if isActiveForInputIgnoreSelection then
            local _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_toggleHover", self,
                UFO2000.actionEventToggleHover, true, false, false, true)
            g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_HIGH)
            g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_toggleHover"))

            _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_ascend", self,
                UFO2000.actionEventAscend, false, false, true, true)
            g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_NORMAL)
            g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_ascend"))

            _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_descend", self,
                UFO2000.actionEventDescend, false, false, true, true)
            g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_NORMAL)
            g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_descend"))

            _, actionEventId = self:addActionEvent(spec.actionEvents, "ufo_toggleBeam", self,
                UFO2000.actionEventToggleBeam, true, false, false, true)
            g_inputBinding:setActionEventTextPriority(actionEventId, GS_PRIO_NORMAL)
            g_inputBinding:setActionEventText(actionEventId, g_i18n:getText("ufo_action_toggleBeam"))
        end
    end
end

function UFO2000:actionEventToggleHover(actionName, inputValue, callbackState)
    local spec = self.spec_ufo2000
    if self.isServer then
        self:setUFOIsHovering(not spec.isHovering)
    else
        g_client:getServerConnection():sendEvent(UFO2000ToggleHoverEvent.new(self))
    end
end

function UFO2000:actionEventToggleBeam(actionName, inputValue, callbackState)
    local spec = self.spec_ufo2000
    if self.isServer then
        self:setUFOBeamActive(not spec.beamActive)
    else
        g_client:getServerConnection():sendEvent(UFO2000ToggleBeamEvent.new(self))
    end
end

function UFO2000:actionEventAscend(actionName, inputValue, callbackState)
    local spec = self.spec_ufo2000
    local pressed = inputValue ~= 0
    local newInput = pressed and 1 or 0
    if spec.inputVertical ~= newInput then
        spec.inputVertical = newInput
        spec.verticalDirty = true
    end
end

function UFO2000:actionEventDescend(actionName, inputValue, callbackState)
    local spec = self.spec_ufo2000
    local pressed = inputValue ~= 0
    local newInput = pressed and -1 or 0
    if spec.inputVertical ~= newInput then
        spec.inputVertical = newInput
        spec.verticalDirty = true
    end
end

function UFO2000:onLeaveVehicle(wasEntered)
    local spec = self.spec_ufo2000
    spec.inputVertical = 0
    spec.verticalDirty = true
end

-- ---------------------------------------------------------------------------
-- simulation
-- ---------------------------------------------------------------------------
function UFO2000:getCanMotorRun(superFunc)
    local spec = self.spec_ufo2000
    if spec ~= nil and spec.isHovering then
        -- a hovering craft always has "ground contact" through its cushion
        local baseOk = superFunc(self)
        if not baseOk then
            return false
        end
        return true
    end
    return superFunc(self)
end

function UFO2000:onUpdateTick(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)
    local spec = self.spec_ufo2000
    if self.isServer then
        if spec.isHovering then
            UFO2000.updateFlight(self, dt)
        else
            spec.altitudeTarget = spec.minAltitude
        end
        spec.legsAlpha = math.clamp(spec.legsAlpha + (spec.legsTarget - spec.legsAlpha) * math.min(dt * spec.legSpeed, 1), 0, 1)
        self:raiseDirtyFlags(spec.dirtyFlag)
    else
        spec.legsAlpha = math.clamp(spec.legsAlpha + (spec.legsTarget - spec.legsAlpha) * math.min(dt * spec.legSpeed, 1), 0, 1)
        spec.legsTarget = spec.isHovering and 1 or 0
    end
    UFO2000.updateLegs(self, dt)
end

function UFO2000.updateFlight(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    local node = vehicle.components[1].node
    local px, py, pz = getWorldTranslation(node)

    -- vertical: keys move the target altitude, the craft follows it smoothly
    if spec.inputVertical > 0 then
        spec.altitudeTarget = math.min(spec.altitudeTarget + spec.climbSpeed * dt, spec.maxAltitude)
    elseif spec.inputVertical < 0 then
        spec.altitudeTarget = math.max(spec.altitudeTarget - spec.climbSpeed * dt, spec.minAltitude)
    end

    local groundY = getTerrainHeightAtWorldPos(g_terrainNode, px, 0, pz)
    local targetY = groundY + spec.altitudeTarget
    local targetAlt = spec.altitudeTarget
    spec.altitude = spec.altitude + (targetAlt - spec.altitude) * math.min(dt * 3.0, 1)

    -- horizontal: same keys as a tractor
    local drivable = vehicle.spec_drivable
    local inputForward = 0
    local inputSide = 0
    if drivable ~= nil then
        inputForward = drivable.axisForward or 0
        inputSide = drivable.axisSide or 0
    end
    -- never trust the physics inputs blindly (division by the zero wheel
    -- steering times can produce NaN on a wheel-less vehicle)
    if inputForward ~= inputForward then inputForward = 0 end
    if inputSide ~= inputSide then inputSide = 0 end
    inputForward = math.clamp(inputForward, -1, 1)
    inputSide = math.clamp(inputSide, -1, 1)

    local wantedSpeed = inputForward * spec.maxSpeed
    spec.speed = spec.speed + (wantedSpeed - spec.speed) * math.min(dt * 2.4, 1)
    spec.yaw = spec.yaw + inputSide * spec.yawSpeed * dt

    -- tilt into the flight direction (cosmetic, the collision is a disc)
    spec.pitch = spec.pitch + (-4.5 * inputForward - spec.pitch) * math.min(dt * 2.0, 1)
    spec.roll = spec.roll + (-5.5 * inputSide - spec.roll) * math.min(dt * 2.0, 1)

    local heading = math.rad(spec.yaw)
    local fx, fz = math.sin(heading), math.cos(heading)

    -- the hover height is smoothed separately from the cosmetic bobbing,
    -- otherwise the bobbing would be amplified by the smoothing factor and
    -- the craft would float a metre too high
    if spec.hoverY == nil then
        spec.hoverY = py
    end
    spec.hoverY = spec.hoverY + (targetY - spec.hoverY) * math.min(dt * 2.6, 1)
    if math.abs(py - spec.hoverY) > 2.0 then
        -- somebody else moved us (teleport, reset, savegame load)
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

    -- land automatically when the pilot asks for the lowest altitude and the
    -- craft is resting on its cushion
    if spec.inputVertical < 0 and spec.altitudeTarget <= spec.minAltitude + 0.01 and py - groundY < spec.minAltitude + 0.25 then
        spec.altitude = spec.minAltitude
        vehicle:setUFOIsHovering(false)
    end
end

function UFO2000.updateLegs(vehicle, dt)
    local spec = vehicle.spec_ufo2000
    for i, node in ipairs(spec.legNodes) do
        local rest = spec.legRestRotation[i]
        local retracted = rest + 74
        setRotation(node, 0, select(2, getRotation(node)), rest + (retracted - rest) * spec.legsAlpha)
    end
end

-- ---------------------------------------------------------------------------
-- client side eye candy
-- ---------------------------------------------------------------------------
function UFO2000:onUpdate(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)
    local spec = self.spec_ufo2000
    if not self.isClient then
        return
    end

    -- wobbling little pilot, always happy
    if spec.alienNode ~= nil then
        local t = g_currentMission.time / 1000
        local bob = math.sin(t * 2.1) * 0.035
        local tilt = math.sin(t * 1.3) * 4
        setTranslation(spec.alienNode, 0, spec.alienBaseY + bob, 0)
        setRotation(spec.alienNode, 0, tilt, 0)
    end

    -- the beacon light turns like the one on a tow truck
    if spec.beaconLight ~= nil then
        local t = g_currentMission.time / 1000
        setRotation(spec.beaconLight, 0, t * 220 % 360, 0)
    end
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
    if self.vehicle ~= nil and self.vehicle.getIsUFOIsHovering ~= nil then
        self.vehicle:setUFOIsHovering(not self.vehicle:getUFOIsHovering())
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
