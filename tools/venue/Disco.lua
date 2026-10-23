-- SPDX-License-Identifier: GPL-3.0-or-later
-- FS25_Disco - farm disco placeable.
--
-- Everyone who walks into the hall hears the same track: the music is a
-- synchronised OGG sample that starts at the same network time on every
-- client, and the track is picked by the server (dirty flags + event), so
-- multiplayer stays in step. The mirror ball turns, the neon groups blink
-- to the beat.

Disco = {}
local Disco_mt = Class(Disco, Placeable)
InitStaticObjectClass(Disco, "Disco")

Disco.SOUNDS_FILE = "sounds/discoSounds.xml"
Disco.MAX_TRACKS = 8
Disco.LEAD_TIME_MS = 1500         -- head start so every client can start in sync
Disco.NOTIFY_RADIUS = 16.0        -- where the "next track" key is active
Disco.BLINK_GROUPS = {"lightPink", "lightCyan", "lightYellow"}

function Disco.new(isServer, isClient, customMt)
	local self = Object.new(isServer, isClient, customMt or Disco_mt)
	self.finishedLoading = false
	self.rootNode = nil
	self.loadingState = PlaceableLoadingState.OK
	self.loadingStep = SpecializationLoadStep.CREATED
	self.isDeleting = false
	self.isDeleted = false
	self.isLoadedFromSavegame = false
	self.loadingTasks = {}
	self.readyForFinishLoading = false
	self.propertyState = PlaceablePropertyState.OWNED
	self.age = 0
	self.price = 0

	self.tracks = {}
	self.trackIndex = 1
	self.playing = false
	self.startTime = 0
	self.volume = 0.9
	self.localSample = nil
	self.inputActions = {}
	return self
end

-- The base game collects events and functions from the type class, so our own
-- class has to add its listeners on top of Placeable's list.
function Disco.registerEvents(placeableType)
	Placeable.registerEvents(placeableType)
	SpecializationUtil.registerEventListener(placeableType, "onLoad", Disco)
	SpecializationUtil.registerEventListener(placeableType, "onDelete", Disco)
	SpecializationUtil.registerEventListener(placeableType, "onReadStream", Disco)
	SpecializationUtil.registerEventListener(placeableType, "onWriteStream", Disco)
	SpecializationUtil.registerEventListener(placeableType, "onReadUpdateStream", Disco)
	SpecializationUtil.registerEventListener(placeableType, "onWriteUpdateStream", Disco)
end

function Disco:getL10n(key)
	if key == nil then
		return ""
	end
	local env = self.customEnvironment or "FS25_Disco"
	if g_i18n:hasText(key, env) then
		return g_i18n:getText(key, env)
	end
	if g_i18n:hasText(key) then
		return g_i18n:getText(key)
	end
	return key
end

-- ---------------------------------------------------------------------------
-- loading

function Disco:onLoad(savegame)
	self.stateDirtyFlag = self:getNextDirtyFlag()
	self.musicNode = I3DUtil.indexToObject(self.components, "musicNode", self.i3dMappings)
	self.ballPivot = I3DUtil.indexToObject(self.components, "mirrorBallPivot", self.i3dMappings)
	self.lightGroups = {}
	for i, name in ipairs(Disco.BLINK_GROUPS) do
		self.lightGroups[i] = I3DUtil.indexToObject(self.components, name, self.i3dMappings)
	end

	self:loadTracks()
	self:registerInput()

	if g_currentMission ~= nil then
		g_currentMission:addUpdateable(self)
	end
end

function Disco:loadTracks()
	local path = Utils.getFilename(Disco.SOUNDS_FILE, self.baseDirectory)
	local xmlFile = loadXMLFile("discoSounds", path)
	if xmlFile == nil or xmlFile == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Disco: cannot load %s", path)
		return
	end
	self.volume = Utils.getNoNil(getXMLFloat(xmlFile, "sounds#volume"), self.volume)
	local audioGroup = AudioGroup.MUSIC or AudioGroup.ENVIRONMENT
	for i = 1, Disco.MAX_TRACKS do
		local key = string.format("sounds.music%d", i)
		if not hasXMLProperty(xmlFile, key) then
			break
		end
		local sample = g_soundManager:loadSampleFromXML(xmlFile, "sounds",
			string.format("music%d", i), self.baseDirectory, self.musicNode, 0,
			audioGroup, nil, nil)
		if sample ~= nil then
			sample.volumeScale = sample.volumeScale * self.volume
			table.insert(self.tracks, {
				sample = sample,
				bpm = Utils.getNoNil(getXMLInt(xmlFile, key .. "#bpm"), 120),
				title = getXMLString(xmlFile, key .. "#title"),
			})
		end
	end
	delete(xmlFile)
	if #self.tracks == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Disco: no music tracks defined")
		self.trackIndex = 0
	end
end

function Disco:registerInput()
	local actions = {
		{action = "DISCO_NEXT_TRACK", callback = "onActionNextTrack", text = "l10n_disco_action_next"},
		{action = "DISCO_TOGGLE_MUSIC", callback = "onActionToggleMusic", text = "l10n_disco_action_toggle"},
	}
	for _, entry in ipairs(actions) do
		local ok, eventId = g_inputBinding:registerActionEvent(entry.action, self,
			entry.callback, false, true, false, false)
		if ok then
			g_inputBinding:setActionEventText(eventId, self:getL10n(entry.text))
			g_inputBinding:setActionEventTextVisibility(eventId, true)
			g_inputBinding:setActionEventActive(eventId, false)
			table.insert(self.inputActions, {id = eventId, name = entry.action})
		end
	end
end

function Disco:onDelete()
	if g_currentMission ~= nil then
		g_currentMission:removeUpdateable(self)
	end
	for _, entry in ipairs(self.inputActions) do
		g_inputBinding:removeActionEvent(entry.id)
	end
	self.inputActions = {}
	self:stopLocalPlayback()
	for _, track in ipairs(self.tracks) do
		if track.sample ~= nil then
			g_soundManager:deleteSample(track.sample)
		end
	end
	self.tracks = {}
end

-- ---------------------------------------------------------------------------
-- multiplayer state

function Disco:onWriteStream(streamId, connection)
	streamWriteUIntN(streamId, self.trackIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function Disco:onReadStream(streamId, connection)
	self.trackIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:applyPlayback(true)
end

function Disco:onWriteUpdateStream(streamId, connection, dirtyMask)
	if not connection:getIsServer() then
		if streamWriteBool(streamId, bit32.band(dirtyMask, self.stateDirtyFlag) ~= 0) then
			streamWriteUIntN(streamId, self.trackIndex, 4)
			streamWriteBool(streamId, self.playing)
			streamWriteFloat32(streamId, self.startTime)
		end
	end
end

function Disco:onReadUpdateStream(streamId, timestamp, connection)
	if connection:getIsServer() then
		if streamReadBool(streamId) then
			self.trackIndex = streamReadUIntN(streamId, 4)
			self.playing = streamReadBool(streamId)
			self.startTime = streamReadFloat32(streamId)
			self:applyPlayback(false)
		end
	end
end

function Disco:getStartTimeFor(playing)
	if playing then
		return (g_time + Disco.LEAD_TIME_MS) / 1000
	end
	return 0
end

-- Called by the player: ask the server, it decides track and start time.
function Disco:requestState(trackIndex, playing)
	if self.tracks == nil or #self.tracks == 0 then
		return
	end
	trackIndex = math.max(1, math.min(#self.tracks, trackIndex or 1))
	playing = playing == true
	if g_currentMission:getIsServer() then
		local startTime = self:getStartTimeFor(playing)
		self:applyState(trackIndex, playing, startTime)
		if g_server ~= nil then
			g_server:broadcastEvent(DiscoStateEvent.new(self, trackIndex, playing, startTime), false, nil, nil)
		end
	else
		g_client:getServerConnection():sendEvent(DiscoStateEvent.new(self, trackIndex, playing, 0))
	end
end

-- The one place that writes the state (server) or receives it (client).
function Disco:applyState(trackIndex, playing, startTime, announce)
	self.trackIndex = math.max(1, math.min(math.max(#self.tracks, 1), trackIndex or 1))
	self.playing = playing == true
	self.startTime = startTime or 0
	if self.isServer then
		self:raiseDirtyFlags(self.stateDirtyFlag)
	end
	self:applyPlayback(announce ~= false)
end

function Disco:applyPlayback(announce)
	if self.playing then
		local delay = math.max(0, self.startTime - g_time / 1000)
		self:startLocalPlayback(delay)
	else
		self:stopLocalPlayback()
	end
	if announce and self.playing and self.isClient then
		local track = self.tracks[self.trackIndex]
		if track ~= nil then
			g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
				string.format("%s: %s", self:getName(), self:getL10n(track.title)))
		end
	end
end

function Disco:startLocalPlayback(delay)
	local track = self.tracks[self.trackIndex]
	self:stopLocalPlayback()
	if track == nil or track.sample == nil then
		return
	end
	self.localSample = track.sample
	g_soundManager:playSample(track.sample, delay or 0)
end

function Disco:stopLocalPlayback()
	if self.localSample ~= nil then
		g_soundManager:stopSample(self.localSample, 0, 0.6)
		self.localSample = nil
	end
end

-- ---------------------------------------------------------------------------
-- input

function Disco:getIsPlayerClose()
	if g_localPlayer == nil or self.rootNode == nil then
		return false
	end
	local x, _, z = getWorldTranslation(self.rootNode)
	local px, _, pz = getWorldTranslation(g_localPlayer.rootNode)
	local dx, dz = px - x, pz - z
	return dx * dx + dz * dz < Disco.NOTIFY_RADIUS * Disco.NOTIFY_RADIUS
end

function Disco:onActionNextTrack()
	if not self:getIsPlayerClose() then
		return
	end
	local nextIndex = self.trackIndex + 1
	if self.tracks ~= nil and nextIndex > #self.tracks then
		nextIndex = 1
	end
	self:requestState(nextIndex, true)
end

function Disco:onActionToggleMusic()
	if not self:getIsPlayerClose() then
		return
	end
	self:requestState(self.trackIndex, not self.playing)
end

-- ---------------------------------------------------------------------------
-- per frame: mirror ball, neon, key visibility

function Disco:update(dt)
	if self.rootNode ~= nil then
		self:tick(dt)
	end
	Placeable.update(self, dt)
end

function Disco:tick(dt)
	if self.rootNode == nil then
		return
	end
	local close = self:getIsPlayerClose()
	for _, entry in ipairs(self.inputActions) do
		g_inputBinding:setActionEventActive(entry.id, close)
	end

	local beat = 0
	if self.playing then
		local track = self.tracks[self.trackIndex]
		local bpm = track ~= nil and track.bpm or 120
		beat = math.floor((g_time - self.startTime * 1000) * bpm / 60000)
		if beat < 0 then
			beat = 0
		end
	end

	for i, node in ipairs(self.lightGroups) do
		if node ~= nil then
			setVisibility(node, not self.playing or (beat % #self.lightGroups) == (i - 1))
		end
	end
	if self.ballPivot ~= nil then
		local angle = self.playing and (g_time * 0.0009 % (2 * math.pi)) or 0
		setRotation(self.ballPivot, 0, angle, 0)
	end
end

-- ---------------------------------------------------------------------------
-- the "change the record" event

DiscoStateEvent = {}
local DiscoStateEvent_mt = Class(DiscoStateEvent, Event)
InitStaticEventClass(DiscoStateEvent, "DiscoStateEvent")

function DiscoStateEvent.emptyNew()
	return Event.new(DiscoStateEvent_mt)
end

function DiscoStateEvent.new(placeable, trackIndex, playing, startTime)
	local self = DiscoStateEvent.emptyNew()
	self.placeable = placeable
	self.trackIndex = trackIndex
	self.playing = playing
	self.startTime = startTime
	return self
end

function DiscoStateEvent:readStream(streamId, connection)
	self.placeable = NetworkUtil.readNodeObject(streamId)
	self.trackIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:run(connection)
end

function DiscoStateEvent:writeStream(streamId, connection)
	NetworkUtil.writeNodeObject(streamId, self.placeable)
	streamWriteUIntN(streamId, self.trackIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function DiscoStateEvent:run(connection)
	if self.placeable == nil or self.placeable.isDeleted then
		return
	end
	if not connection:getIsServer() then
		-- a client asked for a change: the server decides the start time and
		-- tells everyone else
		local startTime = self.placeable:getStartTimeFor(self.playing)
		self.startTime = startTime
		self.placeable:applyState(self.trackIndex, self.playing, startTime)
		if g_server ~= nil then
			g_server:broadcastEvent(self, false, connection, nil)
		end
	else
		-- the server told us what is playing
		self.placeable:applyState(self.trackIndex, self.playing, self.startTime)
	end
end
