#!/usr/bin/env python3
"""Headless smoke test for roll orientation and the locked ride lifecycle.

Needs ``lupa``. The test uses a synthetic engine spline made from the same
uniform route points as the build, then checks both inverted frames, seam
continuity, multiplayer quaternion updates, and the full-lap exit/brake lock.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
COASTER = Path(__file__).resolve().parent
sys.path.insert(0, str(COASTER))
from path import build_route, nearest_index  # noqa: E402


def main() -> None:
    points, _labels, route_length, landmarks = build_route()
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().testPoints = lua.table_from([lua.table_from(p) for p in points])
    lua.globals().routeLength = route_length
    lua.execute(r"""
        math.atan2 = math.atan2 or function(y, x) return math.atan(y, x) end
        SplineVehicle = {}
        registeredOverwrites = {}
        SpecializationUtil = {
            hasSpecialization = function() return true end,
            registerEventListener = function() end,
            registerOverwrittenFunction = function(vehicleType, name, func)
                registeredOverwrites[name] = func
            end
        }
        SplineUtil = {
            getValidSplineTime = function(t)
                local r = t % 1
                if r < 0 then r = r + 1 end
                return r
            end
        }
        function getParent(node) return node.parent end
        function localToWorld(parent, x, y, z) return x, y, z end
        function getSplinePositionWithDistance(spline, t, distance, positive, timeStep)
            local count = #spline.points
            local position = (t % 1) * count
            local index = math.floor(position) + 1
            local alpha = position - math.floor(position)
            local nextIndex = index % count + 1
            local a, b = spline.points[index], spline.points[nextIndex]
            return a[1] + (b[1] - a[1]) * alpha,
                   a[2] + (b[2] - a[2]) * alpha,
                   a[3] + (b[3] - a[3]) * alpha,
                   t
        end
        orientation = nil
        function setDirection(node, fx, fy, fz, ux, uy, uz)
            orientation = {fx, fy, fz, ux, uy, uz}
        end
        function getWorldQuaternion(node) return 0, 0, 0, 1 end
        quaternionWrites = 0
        quaternionInterpolator = {
            setQuaternion = function(self, x, y, z, w)
                quaternionWrites = quaternionWrites + 1
                lastQuaternion = {x, y, z, w}
            end
        }
        spline = {points = {}}
        for i, p in ipairs(testPoints) do spline.points[i] = p end
        trainSystem = {
            getSpline = function(self) return spline end,
            getSplineLength = function(self) return routeLength end
        }
        vehicle = {
            rootNode = 1,
            trainSystem = trainSystem,
            spec_coasterRoll = {},
            spec_splineVehicle = {
                rootNodeToFrontDistance = 2.1,
                rootNodeToFrontSplineTime = 2.1 / routeLength
            },
            components = {{networkInterpolators = {quaternion = quaternionInterpolator}}}
        }
        function vehicle:getSplinePositionAndTimeFromDistance(t, distance, step)
            return 0, 0, 0, (t - distance / routeLength) % 1
        end
    """)
    lua.execute((COASTER / "CoasterRoll.lua").read_text(encoding="utf-8"))
    lua.execute("CoasterRoll.registerOverwrittenFunctions({})")
    lua.execute(r"""
        CoasterRoll.setTrainSystem(vehicle, function(self, ts)
            self.trainSystem = ts
        end, trainSystem)

        function orientAtTime(targetTime)
            local frontTime = (targetTime + vehicle.spec_splineVehicle.rootNodeToFrontDistance / routeLength) % 1
            return CoasterRoll.alignToSplineTime(vehicle, function(self, spline, yOffset, tFront)
                return (tFront - 0.01) % 1
            end, spline, 0, frontTime)
        end
    """)

    def orient_at(index: int):
        t = index / len(points)
        lua.globals().targetTime = t
        lua.execute("orientAtTime(targetTime)")
        return tuple(float(lua.eval("orientation[%d]" % i)) for i in range(1, 7))

    checks = []
    for name in ("loop1Top", "loop2Top"):
        index = nearest_index(points, landmarks[name])
        orientation = orient_at(index)
        up = orientation[3:6]
        checks.append((name + " inverts", up[1] < -0.35, up))

    # The station seam is intentionally smooth after the holonomy correction.
    start = orient_at(1)
    end = orient_at(len(points) - 1)
    up_dot = sum(start[3 + i] * end[3 + i] for i in range(3))
    checks.append(("station seam up-vector continuity", up_dot > 0.90, up_dot))
    checks.append(("network quaternion updated", int(lua.eval("quaternionWrites")) >= 4,
                   int(lua.eval("quaternionWrites"))))

    # Exercise the ride-to-station lifecycle with mocked FS25 locomotive and
    # passenger methods: dispatch lock, ignored brake input, exit guards, and
    # unlock only after a complete lap at the station.
    lua.execute(r"""
        Locomotive = {
            STATE_MANUAL_TRAVEL_ACTIVE = 1,
            STATE_MANUAL_TRAVEL_INACTIVE = 2,
            STATE_REQUESTED_POSITION = 3,
            STATE_REQUESTED_POSITION_BRAKING = 4
        }
        rideVehicle = {
            isServer = true,
            trainSystem = {},
            currentPosition = 0,
            movingDirection = 1,
            spec_coasterRoll = {
                rideInProgress = false,
                rideProgress = 0,
                awaitingThrottleRelease = false
            },
            spec_locomotive = {
                state = Locomotive.STATE_MANUAL_TRAVEL_ACTIVE,
                speed = 0,
                sellingDirection = 1
            },
            spec_enterable = {isLeavingAllowed = true}
        }
        function rideVehicle:getCurrentSplinePosition()
            return self.currentPosition
        end
        function rideVehicle:setIsLeavingAllowed(value)
            self.spec_enterable.isLeavingAllowed = value
        end
        function rideVehicle:setRequestedSplinePosition(target)
            self.spec_locomotive.requestedSplinePosition = target
            self.spec_locomotive.state = Locomotive.STATE_REQUESTED_POSITION
        end
        stateBroadcastCount = 0
        function rideVehicle:setLocomotiveState(state)
            stateBroadcastCount = stateBroadcastCount + 1
            self.spec_locomotive.state = state
        end
        remotePassengerVehicle = {
            spec_coasterRoll = {rideInProgress = false},
            spec_locomotive = {state = Locomotive.STATE_REQUESTED_POSITION}
        }
        remoteCanLeave = CoasterRoll.getIsLeavingAllowed(
            remotePassengerVehicle, function() return true end)
        physicsSuperCalls = 0
        capturedPhysics = nil
        function capturePhysics(self, axisForward, axisSide, doHandbrake, dt)
            physicsSuperCalls = physicsSuperCalls + 1
            capturedPhysics = {axisForward, axisSide, doHandbrake, dt}
            return 42
        end
        startResult = CoasterRoll.updateVehiclePhysics(
            rideVehicle, capturePhysics, 1, 0, 0, 16)
        startSuperCalls = physicsSuperCalls
        rideInProgressAtStart = rideVehicle.spec_coasterRoll.rideInProgress
        targetAtStart = rideVehicle.spec_locomotive.requestedSplinePosition
        canLeaveDuringRide = CoasterRoll.getCanLeave(rideVehicle, function() return true end)
        canLeaveVehicleDuringRide = CoasterRoll.getCanLeaveVehicle(rideVehicle, function() return true end)
        canLeaveRideableDuringRide = CoasterRoll.getCanLeaveRideable(rideVehicle, function() return true end)
        leavingAllowedDuringRide = CoasterRoll.getIsLeavingAllowed(rideVehicle, function() return true end)
        canBoardDuringRide = CoasterRoll.getIsEnterable(rideVehicle, function() return true end)
        passengerLeaveCalls = 0
        CoasterRoll.leaveLocalPassengerSeat(rideVehicle, function()
            passengerLeaveCalls = passengerLeaveCalls + 1
        end, false)
        disconnectCleanupIsNative = registeredOverwrites["onPlayerLeaveVehicle"] == nil
            and registeredOverwrites["leavePassengerSeat"] == nil
        passengerActionStillGuarded = registeredOverwrites["leaveLocalPassengerSeat"] ~= nil

        -- A brake/reverse command during the autonomous part must become a
        -- forward route update; the real braking phase is only near the station.
        rideVehicle.currentPosition = 0.25
        physicsResult = CoasterRoll.updateVehiclePhysics(
            rideVehicle, capturePhysics, -1, 0.8, 1, 16)
        forcedForward = capturedPhysics[1]
        forcedSide = capturedPhysics[2]
        forcedHandbrake = capturedPhysics[3]
        rideVehicle.spec_locomotive.state = Locomotive.STATE_REQUESTED_POSITION_BRAKING
        CoasterRoll.updateVehiclePhysics(rideVehicle, capturePhysics, 1, 0.5, 1, 16)
        stationBrakeForward = capturedPhysics[1]
        stationBrakeSide = capturedPhysics[2]
        stationBrakeHandbrake = capturedPhysics[3]
        rideVehicle.spec_locomotive.state = Locomotive.STATE_REQUESTED_POSITION

        CoasterRoll.onUpdate(rideVehicle, 16)
        rideVehicle.currentPosition = 0.50
        CoasterRoll.onUpdate(rideVehicle, 16)
        rideVehicle.currentPosition = 0.75
        CoasterRoll.onUpdate(rideVehicle, 16)
        rideVehicle.currentPosition = 1.00
        CoasterRoll.onUpdate(rideVehicle, 16)
        rideProgressBeforeFinish = rideVehicle.spec_coasterRoll.rideProgress
        rideVehicle.spec_locomotive.state = Locomotive.STATE_MANUAL_TRAVEL_ACTIVE
        rideVehicle.spec_locomotive.speed = 0
        CoasterRoll.onUpdate(rideVehicle, 16)

        completedCanLeave = CoasterRoll.getCanLeave(rideVehicle, function() return true end)
        completedLeavingAllowed = CoasterRoll.getIsLeavingAllowed(rideVehicle, function() return true end)
        heldThrottleResult = CoasterRoll.updateVehiclePhysics(
            rideVehicle, capturePhysics, 1, 0, 0, 16)
        heldThrottleForward = capturedPhysics[1]
        heldThrottleStillLocked = rideVehicle.spec_coasterRoll.rideInProgress

        recoveryVehicle = {
            isServer = true,
            trainSystem = {},
            currentPosition = 0.40,
            spec_coasterRoll = {
                rideInProgress = true,
                rideTargetPosition = 1.0,
                rideLastPosition = 0.40,
                rideProgress = 0.40
            },
            spec_locomotive = {
                state = Locomotive.STATE_MANUAL_TRAVEL_INACTIVE,
                speed = 0,
                sellingDirection = 1
            }
        }
        function recoveryVehicle:getCurrentSplinePosition()
            return self.currentPosition
        end
        function recoveryVehicle:setRequestedSplinePosition(target)
            self.spec_locomotive.requestedSplinePosition = target
            self.spec_locomotive.state = Locomotive.STATE_REQUESTED_POSITION
        end
        function recoveryVehicle:setLocomotiveState(state)
            self.spec_locomotive.state = state
        end
        CoasterRoll.onLeaveVehicle(recoveryVehicle)
        recoveredAfterLeave = recoveryVehicle.spec_locomotive.state
            == Locomotive.STATE_REQUESTED_POSITION
        recoveryVehicle.spec_locomotive.state = Locomotive.STATE_MANUAL_TRAVEL_ACTIVE
        recoveryVehicle.spec_locomotive.requestedSplinePosition = nil
        CoasterRoll.onEnterVehicle(recoveryVehicle, true)
        recoveredAfterEnter = recoveryVehicle.spec_locomotive.state
            == Locomotive.STATE_REQUESTED_POSITION
    """)
    ride_progress = float(lua.eval("rideProgressBeforeFinish"))
    station_target = float(lua.eval("targetAtStart"))
    ride_checks = [
        ("dispatch locks a full station lap", bool(lua.eval("rideInProgressAtStart"))
         and abs(station_target - 1.0) < 1e-6, station_target),
        ("ride lock state rebroadcast for clients", int(lua.eval("stateBroadcastCount")) >= 1,
         int(lua.eval("stateBroadcastCount"))),
        ("remote client blocks exits from synced state", not bool(lua.eval("remoteCanLeave")), None),
        ("driver exit locked mid-ride", not bool(lua.eval("canLeaveDuringRide")), None),
        ("vehicle exit capability locked", not bool(lua.eval("canLeaveVehicleDuringRide")), None),
        ("rideable exit capability locked", not bool(lua.eval("canLeaveRideableDuringRide")), None),
        ("leaving flag locked mid-ride", not bool(lua.eval("leavingAllowedDuringRide")), None),
        ("new riders cannot board en route", not bool(lua.eval("canBoardDuringRide")), None),
        ("disconnect cleanup uses native leave paths", bool(lua.eval("disconnectCleanupIsNative")), None),
        ("normal passenger exit remains guarded", bool(lua.eval("passengerActionStillGuarded"))
         and int(lua.eval("passengerLeaveCalls")) == 0, int(lua.eval("passengerLeaveCalls"))),
        ("start frame skips manual physics", int(lua.eval("startSuperCalls")) == 0,
         int(lua.eval("startSuperCalls"))),
        ("mid-ride input forced forward", float(lua.eval("forcedForward")) == 1.0
         and float(lua.eval("forcedSide")) == 0.0 and float(lua.eval("forcedHandbrake")) == 0.0,
         (float(lua.eval("forcedSide")), float(lua.eval("forcedHandbrake")))),
        ("station braking is script-controlled", float(lua.eval("stationBrakeForward")) == -1.0
         and float(lua.eval("stationBrakeSide")) == 0.0
         and float(lua.eval("stationBrakeHandbrake")) == 0.0,
         (float(lua.eval("stationBrakeForward")), float(lua.eval("stationBrakeHandbrake")))),
        ("run unlocks at station after lap", not bool(lua.eval("rideVehicle.spec_coasterRoll.rideInProgress"))
         and ride_progress >= 0.95, ride_progress),
        ("station restores exits", bool(lua.eval("completedCanLeave"))
         and bool(lua.eval("completedLeavingAllowed")), None),
        ("held dispatch throttle cannot restart", bool(lua.eval("heldThrottleStillLocked")) is False
         and float(lua.eval("heldThrottleForward")) == 0.0, float(lua.eval("heldThrottleForward"))),
        ("disconnect keeps the lap running", bool(lua.eval("recoveredAfterLeave")), None),
        ("re-entering preserves the lap lock", bool(lua.eval("recoveredAfterEnter")), None),
    ]
    checks.extend(ride_checks)

    ok = True
    for name, passed, detail in checks:
        print("  %-38s %s %r" % (name, "ok" if passed else "FAIL", detail))
        ok = ok and passed
    if not ok:
        raise SystemExit(1)
    print("Lua roll/full-lap lock smoke test passed (%.1f m route, %d frames)." %
          (route_length, int(lua.eval("vehicle.spec_coasterRoll.frameCache.count"))))


if __name__ == "__main__":
    main()
