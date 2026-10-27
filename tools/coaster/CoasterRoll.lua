-- Höhensturm: roll-aware spline orientation for FS25's native train system.
-- PC mod script; all co-op riders still use the game's native passenger seats.

CoasterRoll = {}

CoasterRoll.FRAME_SAMPLES = 3072
CoasterRoll.WORLD_UP = {0, 1, 0}

-- The driver manually dispatches the car. From the first movement command, the
-- native locomotive follows the closed spline back to the station under its
-- own requested-position controller; player brake/reverse input is ignored.
CoasterRoll.START_INPUT_THRESHOLD = 0.01
CoasterRoll.START_SPEED_THRESHOLD = 0.15
CoasterRoll.MIN_TARGET_DISTANCE = 0.10
CoasterRoll.MIN_LAP_PROGRESS = 0.95
CoasterRoll.STATION_TOLERANCE = 0.006

local function vec3(x, y, z)
    return {x, y, z}
end

local function add(a, b)
    return {a[1] + b[1], a[2] + b[2], a[3] + b[3]}
end

local function sub(a, b)
    return {a[1] - b[1], a[2] - b[2], a[3] - b[3]}
end

local function scale(a, s)
    return {a[1] * s, a[2] * s, a[3] * s}
end

local function dot(a, b)
    return a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
end

local function cross(a, b)
    return {a[2] * b[3] - a[3] * b[2],
            a[3] * b[1] - a[1] * b[3],
            a[1] * b[2] - a[2] * b[1]}
end

local function normalize(a, fallback)
    local l = math.sqrt(dot(a, a))
    if l < 0.0000001 then
        return fallback or {0, 1, 0}
    end
    return scale(a, 1 / l)
end

local function rotateAroundAxis(v, axis, angle)
    local c, s = math.cos(angle), math.sin(angle)
    return add(add(scale(v, c), scale(cross(axis, v), s)),
               scale(axis, dot(axis, v) * (1 - c)))
end

local function projectUp(up, tangent)
    return normalize(sub(up, scale(tangent, dot(up, tangent))), {1, 0, 0})
end

local function getSplineWorldPoint(spline, splineTime)
    -- This is the same local-to-world conversion used by SplineVehicle.lua.
    local x, y, z = getSplinePositionWithDistance(spline, splineTime, 0, true, 0.01)
    return localToWorld(getParent(spline), x, y, z)
end

local function getValidTime(t)
    return SplineUtil.getValidSplineTime(t)
end

local function buildFrameCache(spline)
    local count = CoasterRoll.FRAME_SAMPLES
    local points, tangents, ups = {}, {}, {}

    for i = 0, count - 1 do
        points[i + 1] = vec3(getSplineWorldPoint(spline, i / count))
    end

    for i = 1, count do
        local prev = points[((i - 2) % count) + 1]
        local next = points[(i % count) + 1]
        tangents[i] = normalize(sub(next, prev), {0, 0, 1})
    end

    local seed = CoasterRoll.WORLD_UP
    if math.abs(dot(seed, tangents[1])) > 0.94 then
        seed = {1, 0, 0}
    end
    ups[1] = projectUp(seed, tangents[1])

    for i = 2, count do
        local oldTangent, newTangent = tangents[i - 1], tangents[i]
        local axisVector = cross(oldTangent, newTangent)
        local axisLength = math.sqrt(dot(axisVector, axisVector))
        local cosine = math.max(-1, math.min(1, dot(oldTangent, newTangent)))
        local candidate = ups[i - 1]
        if axisLength > 0.0000001 then
            local axis = scale(axisVector, 1 / axisLength)
            candidate = rotateAroundAxis(candidate, axis, math.atan2(axisLength, cosine))
        end
        ups[i] = projectUp(candidate, newTangent)
    end

    -- A closed, non-planar rail can accumulate a small holonomy twist.  Spread
    -- it evenly around the circuit so the up vector is continuous at the seam.
    local seamAxisVector = cross(tangents[count], tangents[1])
    local seamAxisLength = math.sqrt(dot(seamAxisVector, seamAxisVector))
    local seamCosine = math.max(-1, math.min(1, dot(tangents[count], tangents[1])))
    local endUp = ups[count]
    if seamAxisLength > 0.0000001 then
        endUp = rotateAroundAxis(endUp, scale(seamAxisVector, 1 / seamAxisLength),
                                 math.atan2(seamAxisLength, seamCosine))
    end
    endUp = projectUp(endUp, tangents[1])
    local seamAngle = math.atan2(dot(tangents[1], cross(endUp, ups[1])),
                                 math.max(-1, math.min(1, dot(endUp, ups[1]))))

    local frames = {}
    for i = 1, count do
        local fraction = (i - 1) / count
        local tangent = tangents[i]
        local up = projectUp(rotateAroundAxis(ups[i], tangent, seamAngle * fraction), tangent)
        local right = normalize(cross(up, tangent), {1, 0, 0})
        up = normalize(cross(tangent, right), {0, 1, 0})
        frames[i] = {tangent = tangent, up = up, right = right}
    end

    return {count = count, frames = frames, spline = spline}
end

local function getFrameAtTime(cache, splineTime)
    local t = getValidTime(splineTime) or 0
    t = t % 1
    local position = t * cache.count
    local firstIndex = math.floor(position) + 1
    local alpha = position - math.floor(position)
    local secondIndex = (firstIndex % cache.count) + 1
    local a, b = cache.frames[firstIndex], cache.frames[secondIndex]
    local tangent = normalize({
        a.tangent[1] + (b.tangent[1] - a.tangent[1]) * alpha,
        a.tangent[2] + (b.tangent[2] - a.tangent[2]) * alpha,
        a.tangent[3] + (b.tangent[3] - a.tangent[3]) * alpha
    }, a.tangent)
    local up = projectUp({
        a.up[1] + (b.up[1] - a.up[1]) * alpha,
        a.up[2] + (b.up[2] - a.up[2]) * alpha,
        a.up[3] + (b.up[3] - a.up[3]) * alpha
    }, tangent)
    return tangent, up
end

function CoasterRoll.prerequisitesPresent(specializations)
    return SpecializationUtil.hasSpecialization(SplineVehicle, specializations)
end

function CoasterRoll.registerEventListeners(vehicleType)
    SpecializationUtil.registerEventListener(vehicleType, "onLoad", CoasterRoll)
    SpecializationUtil.registerEventListener(vehicleType, "onDelete", CoasterRoll)
    SpecializationUtil.registerEventListener(vehicleType, "onUpdate", CoasterRoll)
    SpecializationUtil.registerEventListener(vehicleType, "onEnterVehicle", CoasterRoll)
    SpecializationUtil.registerEventListener(vehicleType, "onLeaveVehicle", CoasterRoll)
end

function CoasterRoll.registerOverwrittenFunctions(vehicleType)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "setTrainSystem", CoasterRoll.setTrainSystem)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "alignToSplineTime", CoasterRoll.alignToSplineTime)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "updateVehiclePhysics", CoasterRoll.updateVehiclePhysics)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getCanLeave", CoasterRoll.getCanLeave)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getCanLeaveVehicle", CoasterRoll.getCanLeaveVehicle)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getCanLeaveRideable", CoasterRoll.getCanLeaveRideable)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getIsLeavingAllowed", CoasterRoll.getIsLeavingAllowed)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "getIsEnterable", CoasterRoll.getIsEnterable)
    SpecializationUtil.registerOverwrittenFunction(vehicleType, "leaveLocalPassengerSeat", CoasterRoll.leaveLocalPassengerSeat)
end

function CoasterRoll:onLoad(savegame)
    local spec = self.spec_coasterRoll
    spec.frameCache = nil
    spec.frameCacheSpline = nil
    spec.rideInProgress = false
    spec.rideTargetPosition = nil
    spec.rideLastPosition = nil
    spec.rideProgress = 0
    spec.previousIsLeavingAllowed = nil
    spec.awaitingThrottleRelease = false
end

function CoasterRoll:onDelete()
    local spec = self.spec_coasterRoll
    spec.frameCache = nil
    spec.frameCacheSpline = nil
end

function CoasterRoll:setTrainSystem(superFunc, trainSystem)
    superFunc(self, trainSystem)

    local spec = self.spec_coasterRoll
    spec.frameCache = nil
    spec.frameCacheSpline = nil
    if trainSystem ~= nil and trainSystem.getSpline ~= nil then
        local spline = trainSystem:getSpline()
        if spline ~= nil then
            spec.frameCache = buildFrameCache(spline)
            spec.frameCacheSpline = spline
        end
    end
end

function CoasterRoll:alignToSplineTime(superFunc, spline, yOffset, tFront)
    local backSplineTime = superFunc(self, spline, yOffset, tFront)
    if backSplineTime == nil then
        return nil
    end

    local spec = self.spec_coasterRoll
    local trainSpec = self.spec_splineVehicle
    local cache = spec.frameCache
    if cache == nil or cache.spline ~= spline then
        cache = buildFrameCache(spline)
        spec.frameCache = cache
        spec.frameCacheSpline = spline
    end

    -- Align the car's local up axis to the rotation-minimising frame at its
    -- heartline position; doing this after the native alignment preserves all
    -- native translation, speed, multiplayer and save-game behaviour.
    local _, _, _, heartlineTime = self:getSplinePositionAndTimeFromDistance(
        tFront, trainSpec.rootNodeToFrontDistance,
        -1.2 * trainSpec.rootNodeToFrontSplineTime)
    local tangent, up = getFrameAtTime(cache, heartlineTime)
    setDirection(self.rootNode, tangent[1], tangent[2], tangent[3], up[1], up[2], up[3])

    -- The base SplineVehicle has already queued its position.  Replace only
    -- the replicated quaternion so remote riders see the same inverted frame.
    local qx, qy, qz, qw = getWorldQuaternion(self.rootNode)
    local component = self.components ~= nil and self.components[1] or nil
    local interpolators = component ~= nil and component.networkInterpolators or nil
    if interpolators ~= nil and interpolators.quaternion ~= nil then
        interpolators.quaternion:setQuaternion(qx, qy, qz, qw)
    end

    return backSplineTime
end

local function isLocomotiveState(self, stateName)
    if Locomotive == nil or self.spec_locomotive == nil then
        return false
    end

    local state = Locomotive[stateName]
    return state ~= nil and self.spec_locomotive.state == state
end

local function sign(value)
    if value > 0 then
        return 1
    elseif value < 0 then
        return -1
    end
    return 0
end

local function getNextStationTarget(currentPosition)
    -- The spline starts at the station. Keep the native request target at the
    -- next integer spline time so the locomotive's own wrap/brake logic applies.
    local target = math.floor(currentPosition + 0.0000001) + 1
    if target - currentPosition < CoasterRoll.MIN_TARGET_DISTANCE then
        target = target + 1
    end
    return target
end

local function setLeavingAllowed(self, isAllowed)
    if self.setIsLeavingAllowed ~= nil then
        self:setIsLeavingAllowed(isAllowed)
    elseif self.spec_enterable ~= nil then
        self.spec_enterable.isLeavingAllowed = isAllowed
    end
end

function CoasterRoll.isRideLocked(self)
    local spec = self.spec_coasterRoll
    if spec ~= nil and spec.rideInProgress then
        return true
    end

    return isLocomotiveState(self, "STATE_REQUESTED_POSITION")
        or isLocomotiveState(self, "STATE_REQUESTED_POSITION_BRAKING")
end

local function setRideTarget(self, target)
    local spec = self.spec_coasterRoll
    spec.rideTargetPosition = target
    self:setRequestedSplinePosition(target)

    -- setRequestedSplinePosition intentionally suppresses the native state
    -- event. Re-broadcast the state so remote passenger clients lock exits too.
    if self.setLocomotiveState ~= nil and Locomotive ~= nil
        and Locomotive.STATE_REQUESTED_POSITION ~= nil then
        self:setLocomotiveState(Locomotive.STATE_REQUESTED_POSITION)
    end

    -- Locomotive may move a wrapped target forward by one spline turn.
    local locomotiveSpec = self.spec_locomotive
    if locomotiveSpec.requestedSplinePosition ~= nil then
        spec.rideTargetPosition = locomotiveSpec.requestedSplinePosition
    end
end

function CoasterRoll.beginRide(self)
    local spec = self.spec_coasterRoll
    if not self.isServer or spec.rideInProgress or self.trainSystem == nil
        or self.setRequestedSplinePosition == nil then
        return false
    end

    local currentPosition = self:getCurrentSplinePosition()
    if currentPosition == nil then
        return false
    end

    local enterableSpec = self.spec_enterable
    spec.previousIsLeavingAllowed = enterableSpec == nil or enterableSpec.isLeavingAllowed ~= false
    spec.rideInProgress = true
    spec.rideLastPosition = currentPosition
    spec.rideProgress = 0

    setLeavingAllowed(self, false)
    setRideTarget(self, getNextStationTarget(currentPosition))
    return true
end

local function requestRideToStation(self)
    local spec = self.spec_coasterRoll
    if not spec.rideInProgress or self.setRequestedSplinePosition == nil then
        return false
    end

    local currentPosition = self:getCurrentSplinePosition()
    if currentPosition == nil then
        return false
    end

    local target = spec.rideTargetPosition
    if target == nil or target - currentPosition < CoasterRoll.MIN_TARGET_DISTANCE then
        target = getNextStationTarget(currentPosition)
    end

    setRideTarget(self, target)
    return true
end

local function getStationDistance(currentPosition, targetPosition)
    local currentFraction = currentPosition % 1
    local targetFraction = targetPosition % 1
    local difference = math.abs(currentFraction - targetFraction)
    return math.min(difference, 1 - difference)
end

local function finishRide(self)
    local spec = self.spec_coasterRoll
    local wasLeavingAllowed = spec.previousIsLeavingAllowed

    spec.rideInProgress = false
    spec.rideTargetPosition = nil
    spec.rideLastPosition = nil
    spec.rideProgress = 0
    spec.previousIsLeavingAllowed = nil
    spec.awaitingThrottleRelease = true

    setLeavingAllowed(self, wasLeavingAllowed ~= false)
end

function CoasterRoll:updateVehiclePhysics(superFunc, axisForward, axisSide, doHandbrake, dt)
    local spec = self.spec_coasterRoll
    local locomotiveSpec = self.spec_locomotive
    axisForward = axisForward or 0

    if self.isServer and spec ~= nil and locomotiveSpec ~= nil
        and not spec.rideInProgress and not spec.awaitingThrottleRelease
        and isLocomotiveState(self, "STATE_MANUAL_TRAVEL_ACTIVE") then
        local throttlePressed = axisForward * (locomotiveSpec.sellingDirection or 1)
            > CoasterRoll.START_INPUT_THRESHOLD
        local alreadyMoving = math.abs(locomotiveSpec.speed or 0) >= CoasterRoll.START_SPEED_THRESHOLD
        if throttlePressed or alreadyMoving then
            CoasterRoll.beginRide(self)
            -- Do not apply the last manual input frame: requested-position travel
            -- takes over before the train can be braked or reversed.
            return 0
        end
    end

    local isRequestedPosition = isLocomotiveState(self, "STATE_REQUESTED_POSITION")
    local isBrakingToPosition = isLocomotiveState(self, "STATE_REQUESTED_POSITION_BRAKING")
    if isRequestedPosition then
        local target = locomotiveSpec.requestedSplinePosition
        local current = self:getCurrentSplinePosition()
        local direction = target ~= nil and current ~= nil and sign(target - current) or 1
        if direction == 0 then
            direction = sign(self.movingDirection or 0)
            if direction == 0 then
                direction = 1
            end
        end
        axisForward, axisSide, doHandbrake = direction, 0, 0
    elseif isBrakingToPosition then
        local movingDirection = self.movingDirection or 0
        if movingDirection == 0 then
            movingDirection = sign(locomotiveSpec.speed or 0)
        end
        if movingDirection == 0 then
            movingDirection = 1
        end
        axisForward = movingDirection > 0 and -1 or 1
        axisSide, doHandbrake = 0, 0
    elseif spec ~= nil and spec.rideInProgress then
        if self.isServer then
            requestRideToStation(self)
            return 0
        end
    elseif self.isServer and spec ~= nil and spec.awaitingThrottleRelease
        and (isLocomotiveState(self, "STATE_MANUAL_TRAVEL_ACTIVE")
            or isLocomotiveState(self, "STATE_MANUAL_TRAVEL_INACTIVE")) then
        if math.abs(axisForward) <= CoasterRoll.START_INPUT_THRESHOLD then
            spec.awaitingThrottleRelease = false
        else
            axisForward, axisSide, doHandbrake = 0, 0, 0
        end
    end

    return superFunc(self, axisForward, axisSide, doHandbrake, dt)
end

function CoasterRoll:onUpdate(dt, isActiveForInput, isActiveForInputIgnoreSelection, isSelected)
    if not self.isServer then
        return
    end

    local spec = self.spec_coasterRoll
    local locomotiveSpec = self.spec_locomotive
    if spec == nil or locomotiveSpec == nil or self.trainSystem == nil then
        return
    end

    local currentPosition = self:getCurrentSplinePosition()
    if currentPosition == nil then
        return
    end

    if not spec.rideInProgress then
        if not spec.awaitingThrottleRelease
            and isLocomotiveState(self, "STATE_MANUAL_TRAVEL_ACTIVE")
            and math.abs(locomotiveSpec.speed or 0) >= CoasterRoll.START_SPEED_THRESHOLD then
            CoasterRoll.beginRide(self)
        end
        return
    end

    if spec.rideLastPosition ~= nil then
        local delta = currentPosition - spec.rideLastPosition
        if delta < -0.5 then
            delta = delta + 1
        elseif delta > 0.5 then
            delta = delta - 1
        end
        if delta > 0 then
            spec.rideProgress = spec.rideProgress + delta
        end
    end
    spec.rideLastPosition = currentPosition

    local isManualActive = isLocomotiveState(self, "STATE_MANUAL_TRAVEL_ACTIVE")
    local isRequestedPosition = isLocomotiveState(self, "STATE_REQUESTED_POSITION")
    local isBrakingToPosition = isLocomotiveState(self, "STATE_REQUESTED_POSITION_BRAKING")
    local isStopped = math.abs(locomotiveSpec.speed or 0) < CoasterRoll.START_SPEED_THRESHOLD
    if isManualActive and isStopped then
        local target = spec.rideTargetPosition
        local atStation = target ~= nil
            and getStationDistance(currentPosition, target) <= CoasterRoll.STATION_TOLERANCE
        if spec.rideProgress >= CoasterRoll.MIN_LAP_PROGRESS and atStation then
            finishRide(self)
        else
            -- If the native controller was interrupted (for example by a
            -- disconnect), immediately send it back to the next station.
            requestRideToStation(self)
        end
    elseif not isRequestedPosition and not isBrakingToPosition then
        requestRideToStation(self)
    elseif isRequestedPosition and locomotiveSpec.requestedSplinePosition == nil then
        requestRideToStation(self)
    end
end

function CoasterRoll:onEnterVehicle(isControlling)
    local spec = self.spec_coasterRoll
    if spec == nil then
        return
    end

    if isControlling and not spec.rideInProgress then
        spec.awaitingThrottleRelease = false
    elseif self.isServer and spec.rideInProgress then
        -- Locomotive:onEnterVehicle normally returns to manual control. Keep an
        -- in-progress lap locked even if a driver reconnects or re-enters.
        requestRideToStation(self)
    end
end

function CoasterRoll:onLeaveVehicle()
    local spec = self.spec_coasterRoll
    if self.isServer and spec ~= nil and spec.rideInProgress then
        -- The normal locomotive leave handler clears its requested position;
        -- restore it so a disconnect cannot strand the train mid-lap.
        requestRideToStation(self)
    end
end

function CoasterRoll:getCanLeave(superFunc)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self)
end

function CoasterRoll:getCanLeaveVehicle(superFunc)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self)
end

function CoasterRoll:getCanLeaveRideable(superFunc)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self)
end

function CoasterRoll:getIsLeavingAllowed(superFunc)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self)
end

function CoasterRoll:getIsEnterable(superFunc)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self)
end

function CoasterRoll:leaveLocalPassengerSeat(superFunc, noEventSend)
    if CoasterRoll.isRideLocked(self) then
        return false
    end
    return superFunc(self, noEventSend)
end
