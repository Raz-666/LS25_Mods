-- SPDX-License-Identifier: GPL-3.0-or-later
-- FS25_Distillery - the Leipzig techno club as a placeable.
--
-- Everyone in the hall hears the same track at the same second: the server
-- picks the record, stores its index plus a common start time and every PC
-- starts the OGG sample at that time. The set list board next to the mixer is
-- part of the model; the amber marker bar under it is moved to the row of the
-- track that is running, so anybody who walks up to the DJ booth sees what is
-- playing and can skip to the next record with one key.

Distillery = {}
local Distillery_mt = Class(Distillery, Placeable)
InitStaticObjectClass(Distillery, "Distillery")

Distillery.SOUNDS_FILE = "sounds/distillerySounds.xml"
Distillery.MAX_TRACKS = 8
Distillery.LEAD_TIME_MS = 1500      -- head start so every client can start in sync
Distillery.DJ_RADIUS = 4.5          -- "at the mixer" - keys are only offered here
Distillery.CLUB_RADIUS = 34.0       -- inside/around the building
Distillery.BLINK_GROUPS = {"lightPink", "lightCyan", "lightAmber"}

function Distillery.new(isServer, isClient, customMt)
	local self = Object.new(isServer, isClient, customMt or Distillery_mt)
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
	self.volume = 0.95
	self.localSample = nil
	self.radioMode = false
	self.inputActions = {}

	-- board geometry (row height + node), filled in onLoad
	self.rowHeight = 0.234
	self.markerNode = nil
	self.markerBaseY = 0
	self.clubNode = nil
	return self
end

-- The base game collects events and functions from the type class, so our own
-- class has to add its listeners on top of Placeable's list.
function Distillery.registerEvents(placeableType)
	Placeable.registerEvents(placeableType)
	SpecializationUtil.registerEventListener(placeableType, "onLoad", Distillery)
	SpecializationUtil.registerEventListener(placeableType, "onDelete", Distillery)
	SpecializationUtil.registerEventListener(placeableType, "onReadStream", Distillery)
	SpecializationUtil.registerEventListener(placeableType, "onWriteStream", Distillery)
	SpecializationUtil.registerEventListener(placeableType, "onReadUpdateStream", Distillery)
	SpecializationUtil.registerEventListener(placeableType, "onWriteUpdateStream", Distillery)
end

function Distillery:getL10n(key)
	if key == nil then
		return ""
	end
	local env = self.customEnvironment or "FS25_Distillery"
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

function Distillery:onLoad(savegame)
	self.stateDirtyFlag = self:getNextDirtyFlag()
	self.musicNode = I3DUtil.indexToObject(self.components, "musicNode", self.i3dMappings)
	self.ballPivot = I3DUtil.indexToObject(self.components, "mirrorBallPivot", self.i3dMappings)
	self.djNode = I3DUtil.indexToObject(self.components, "djNode", self.i3dMappings)
	self.markerNode = I3DUtil.indexToObject(self.components, "playlistMarker", self.i3dMappings)
	if self.markerNode ~= nil then
		local _, y, _ = getTranslation(self.markerNode)
		self.markerBaseY = y
	end
	self.lightGroups = {}
	for i, name in ipairs(Distillery.BLINK_GROUPS) do
		self.lightGroups[i] = I3DUtil.indexToObject(self.components, name, self.i3dMappings)
	end

	self:loadTracks()
	self:registerInput()

	if g_currentMission ~= nil then
		g_currentMission:addUpdateable(self)
	end
end

function Distillery:loadTracks()
	local path = Utils.getFilename(Distillery.SOUNDS_FILE, self.baseDirectory)
	local xmlFile = loadXMLFile("distillerySounds", path)
	if xmlFile == nil or xmlFile == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Distillery: cannot load %s", path)
		return
	end
	self.volume = Utils.getNoNil(getXMLFloat(xmlFile, "sounds#volume"), self.volume)
	self.rowHeight = Utils.getNoNil(getXMLFloat(xmlFile, "sounds#rowHeight"), self.rowHeight)
	local audioGroup = AudioGroup.MUSIC or AudioGroup.ENVIRONMENT
	for i = 1, Distillery.MAX_TRACKS do
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
				bpm = Utils.getNoNil(getXMLInt(xmlFile, key .. "#bpm"), 128),
				title = getXMLString(xmlFile, key .. "#title"),
			})
		end
	end
	delete(xmlFile)
	if #self.tracks == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Distillery: no music tracks defined")
		self.trackIndex = 0
	end
end

function Distillery:registerInput()
	local actions = {
		{action = "DISTILLERY_NEXT_TRACK", callback = "onActionNextTrack", text = "l10n_distillery_action_next"},
		{action = "DISTILLERY_TOGGLE_MUSIC", callback = "onActionToggleMusic", text = "l10n_distillery_action_toggle"},
		{action = "DISTILLERY_RADIO", callback = "onActionRadio", text = "l10n_distillery_action_radio"},
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

function Distillery:onDelete()
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

function Distillery:onWriteStream(streamId, connection)
	streamWriteUIntN(streamId, self.trackIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function Distillery:onReadStream(streamId, connection)
	self.trackIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:applyPlayback(true)
end

function Distillery:onWriteUpdateStream(streamId, connection, dirtyMask)
	if not connection:getIsServer() then
		if streamWriteBool(streamId, bit32.band(dirtyMask, self.stateDirtyFlag) ~= 0) then
			streamWriteUIntN(streamId, self.trackIndex, 4)
			streamWriteBool(streamId, self.playing)
			streamWriteFloat32(streamId, self.startTime)
		end
	end
end

function Distillery:onReadUpdateStream(streamId, timestamp, connection)
	if connection:getIsServer() then
		if streamReadBool(streamId) then
			self.trackIndex = streamReadUIntN(streamId, 4)
			self.playing = streamReadBool(streamId)
			self.startTime = streamReadFloat32(streamId)
			self:applyPlayback(false)
		end
	end
end

function Distillery:getStartTimeFor(playing)
	if playing then
		return (g_time + Distillery.LEAD_TIME_MS) / 1000
	end
	return 0
end

-- Called by a player: ask the server, it decides track and start time.
function Distillery:requestState(trackIndex, playing)
	if self.tracks == nil or #self.tracks == 0 then
		return
	end
	trackIndex = math.max(1, math.min(#self.tracks, trackIndex or 1))
	playing = playing == true
	if g_currentMission:getIsServer() then
		local startTime = self:getStartTimeFor(playing)
		self:applyState(trackIndex, playing, startTime)
		if g_server ~= nil then
			g_server:broadcastEvent(DistilleryStateEvent.new(self, trackIndex, playing, startTime), false, nil, nil)
		end
	else
		g_client:getServerConnection():sendEvent(DistilleryStateEvent.new(self, trackIndex, playing, 0))
	end
end

-- The one place that writes the state (server) or receives it (client).
function Distillery:applyState(trackIndex, playing, startTime, announce)
	self.trackIndex = math.max(1, math.min(math.max(#self.tracks, 1), trackIndex or 1))
	self.playing = playing == true
	self.startTime = startTime or 0
	if self.isServer then
		self:raiseDirtyFlags(self.stateDirtyFlag)
	end
	self:applyPlayback(announce)
end

function Distillery:applyPlayback(announce)
	if self.radioMode then
		-- the local player listens to the game radio instead of the club PA
		return
	end
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

function Distillery:startLocalPlayback(delay)
	local track = self.tracks[self.trackIndex]
	self:stopLocalPlayback()
	if track == nil or track.sample == nil then
		return
	end
	self.localSample = track.sample
	g_soundManager:playSample(track.sample, delay or 0)
end

function Distillery:stopLocalPlayback()
	if self.localSample ~= nil then
		g_soundManager:stopSample(self.localSample, 0, 0.6)
		self.localSample = nil
	end
end

-- ---------------------------------------------------------------------------
-- input

-- Distance to the DJ booth node (where the mixer is), nil-safe.
function Distillery:getDistanceTo(node)
	if node == nil or g_localPlayer == nil or g_localPlayer.rootNode == nil then
		return math.huge
	end
	local x, _, z = getWorldTranslation(node)
	local px, _, pz = getWorldTranslation(g_localPlayer.rootNode)
	local dx, dz = px - x, pz - z
	return math.sqrt(dx * dx + dz * dz)
end

function Distillery:getIsAtMixer()
	return self:getDistanceTo(self.djNode) < Distillery.DJ_RADIUS
end

function Distillery:getIsNearClub()
	if self.rootNode == nil or g_localPlayer == nil then
		return false
	end
	local x, _, z = getWorldTranslation(self.rootNode)
	local px, _, pz = getWorldTranslation(g_localPlayer.rootNode)
	local dx, dz = px - x, pz - z
	return dx * dx + dz * dz < Distillery.CLUB_RADIUS * Distillery.CLUB_RADIUS
end

function Distillery:onActionNextTrack()
	if not self:getIsAtMixer() then
		return
	end
	local nextIndex = self.trackIndex + 1
	if self.tracks ~= nil and nextIndex > #self.tracks then
		nextIndex = 1
	end
	self.radioMode = false
	self:requestState(nextIndex, true)
end

function Distillery:onActionToggleMusic()
	if not self:getIsAtMixer() then
		return
	end
	self.radioMode = false
	self:requestState(self.trackIndex, not self.playing)
end

-- "Radio": hand the local player over to the game's own radio. This is a
-- per-player switch - the club PA (and everybody else) keeps running.
function Distillery:onActionRadio()
	if not self:getIsAtMixer() then
		return
	end
	if g_soundPlayer == nil then
		g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
			self:getL10n("l10n_distillery_radio_unavailable"))
		return
	end
	self.radioMode = not self.radioMode
	if self.radioMode then
		self:stopLocalPlayback()
		pcall(function()
			if not g_soundPlayer:getIsPlaying() then
				g_soundPlayer:play()
			end
		end)
		g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
			self:getL10n("l10n_distillery_radio_on"))
	else
		pcall(function()
			if g_soundPlayer:getIsPlaying() then
				g_soundPlayer:pause()
			end
		end)
		self:applyPlayback(false)
		g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
			self:getL10n("l10n_distillery_radio_off"))
	end
end

-- ---------------------------------------------------------------------------
-- per frame: mirror ball, neon, marker bar, key visibility

function Distillery:update(dt)
	if self.rootNode ~= nil then
		self:tick(dt)
	end
	Placeable.update(self, dt)
end

function Distillery:tick(dt)
	if self.rootNode == nil then
		return
	end
	local atMixer = self:getIsAtMixer()
	for _, entry in ipairs(self.inputActions) do
		g_inputBinding:setActionEventActive(entry.id, atMixer)
	end

	local beat = 0
	if self.playing and not self.radioMode then
		local track = self.tracks[self.trackIndex]
		local bpm = track ~= nil and track.bpm or 128
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
	-- the marker bar: one row down per track
	if self.markerNode ~= nil then
		local row = math.max(0, math.min(Distillery.MAX_TRACKS - 1, (self.trackIndex or 1) - 1))
		local x, _, z = getTranslation(self.markerNode)
		setTranslation(self.markerNode, x, self.markerBaseY - row * self.rowHeight, z)
		setVisibility(self.markerNode, self.playing)
	end
end

-- ---------------------------------------------------------------------------
-- the "change the record" event

DistilleryStateEvent = {}
local DistilleryStateEvent_mt = Class(DistilleryStateEvent, Event)
InitStaticEventClass(DistilleryStateEvent, "DistilleryStateEvent")

function DistilleryStateEvent.emptyNew()
	return Event.new(DistilleryStateEvent_mt)
end

function DistilleryStateEvent.new(placeable, trackIndex, playing, startTime)
	local self = DistilleryStateEvent.emptyNew()
	self.placeable = placeable
	self.trackIndex = trackIndex
	self.playing = playing
	self.startTime = startTime
	return self
end

function DistilleryStateEvent:readStream(streamId, connection)
	self.placeable = NetworkUtil.readNodeObject(streamId)
	self.trackIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:run(connection)
end

function DistilleryStateEvent:writeStream(streamId, connection)
	NetworkUtil.writeNodeObject(streamId, self.placeable)
	streamWriteUIntN(streamId, self.trackIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function DistilleryStateEvent:run(connection)
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
