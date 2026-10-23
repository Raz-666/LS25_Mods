-- SPDX-License-Identifier: GPL-3.0-or-later
-- FS25_Autokino - drive-in cinema placeable.
--
-- The screen shows one of three short cartoons. They are not videos but 16
-- frame textures per film that are swapped on the screen material; the frame
-- number is derived from the network time of the film start, so every client
-- in a multiplayer session sees the very same frame and hears the soundtrack
-- from the same moment. The film is chosen by the server.

Autokino = {}
local Autokino_mt = Class(Autokino, Placeable)
InitStaticObjectClass(Autokino, "Autokino")

Autokino.CONFIG_FILE = "sounds/autokinoSounds.xml"
Autokino.MAX_FILMS = 6
Autokino.MAX_FRAMES = 32
Autokino.LEAD_TIME_MS = 1500
Autokino.NOTIFY_RADIUS = 40.0
Autokino.FRAME_FOLDER = "textures/film/"

function Autokino.new(isServer, isClient, customMt)
	local self = Object.new(isServer, isClient, customMt or Autokino_mt)
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

	self.films = {}
	self.filmIndex = 1
	self.playing = true
	self.startTime = 0
	self.volume = 0.85
	self.fps = 6
	self.frameIndex = -1
	self.screenMaterial = 0
	self.localSample = nil
	self.inputActions = {}
	return self
end

function Autokino.registerEvents(placeableType)
	Placeable.registerEvents(placeableType)
	SpecializationUtil.registerEventListener(placeableType, "onLoad", Autokino)
	SpecializationUtil.registerEventListener(placeableType, "onDelete", Autokino)
	SpecializationUtil.registerEventListener(placeableType, "onReadStream", Autokino)
	SpecializationUtil.registerEventListener(placeableType, "onWriteStream", Autokino)
	SpecializationUtil.registerEventListener(placeableType, "onReadUpdateStream", Autokino)
	SpecializationUtil.registerEventListener(placeableType, "onWriteUpdateStream", Autokino)
end

function Autokino:getL10n(key)
	if key == nil then
		return ""
	end
	local env = self.customEnvironment or "FS25_Autokino"
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

function Autokino:onLoad(savegame)
	self.stateDirtyFlag = self:getNextDirtyFlag()
	self.screenNode = I3DUtil.indexToObject(self.components, "screenMesh", self.i3dMappings)
	self.filmSoundNode = I3DUtil.indexToObject(self.components, "filmSoundNode", self.i3dMappings)
	if self.screenNode ~= nil then
		self.screenMaterial = getMaterial(self.screenNode, 0)
	end
	self:loadConfig()
	self:registerInput()
	if g_currentMission ~= nil then
		g_currentMission:addUpdateable(self)
	end
	if #self.films > 0 then
		self:setFrame(self.films[1], 0)
	end
	if self.isServer then
		self.startTime = (g_time + Autokino.LEAD_TIME_MS) / 1000
		self.playing = #self.films > 0
		self:applyPlayback(false)
	end
end

function Autokino:loadConfig()
	local path = Utils.getFilename(Autokino.CONFIG_FILE, self.baseDirectory)
	local xmlFile = loadXMLFile("autokinoSounds", path)
	if xmlFile == nil or xmlFile == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Autokino: cannot load %s", path)
		return
	end
	self.volume = Utils.getNoNil(getXMLFloat(xmlFile, "autokino#volume"), self.volume)
	self.fps = Utils.getNoNil(getXMLInt(xmlFile, "autokino#fps"), self.fps)
	local audioGroup = AudioGroup.MUSIC or AudioGroup.ENVIRONMENT

	for i = 1, Autokino.MAX_FILMS do
		local key = string.format("autokino.films.film(%d)", i - 1)
		if not hasXMLProperty(xmlFile, key) then
			break
		end
		local filmKey = getXMLString(xmlFile, key .. "#key")
		local frames = Utils.getNoNil(getXMLInt(xmlFile, key .. "#frames"), 0)
		local sound = getXMLString(xmlFile, key .. "#sound")
		if filmKey ~= nil and frames > 0 then
			local sample = nil
			if sound ~= nil then
				sample = g_soundManager:loadSampleFromXML(xmlFile, "autokino.sounds",
					sound, self.baseDirectory, self.filmSoundNode, 0, audioGroup, nil, nil)
				if sample ~= nil then
					sample.volumeScale = sample.volumeScale * self.volume
				end
			end
			table.insert(self.films, {
				key = filmKey,
				frames = math.min(frames, Autokino.MAX_FRAMES),
				sample = sample,
				title = getXMLString(xmlFile, key .. "#title"),
			})
		end
	end
	delete(xmlFile)
	if #self.films == 0 then
		Logging.xmlWarning(self.xmlFile, "FS25_Autokino: no films defined")
	end
end

function Autokino:registerInput()
	local actions = {
		{action = "AUTOKINO_NEXT_FILM", callback = "onActionNextFilm", text = "l10n_autokino_action_next"},
		{action = "AUTOKINO_TOGGLE_FILM", callback = "onActionToggleFilm", text = "l10n_autokino_action_toggle"},
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

function Autokino:onDelete()
	if g_currentMission ~= nil then
		g_currentMission:removeUpdateable(self)
	end
	for _, entry in ipairs(self.inputActions) do
		g_inputBinding:removeActionEvent(entry.id)
	end
	self.inputActions = {}
	self:stopLocalPlayback()
	for _, film in ipairs(self.films) do
		if film.sample ~= nil then
			g_soundManager:deleteSample(film.sample)
		end
	end
	self.films = {}
end

-- ---------------------------------------------------------------------------
-- network state (same scheme as FS25_Disco: the server decides)

function Autokino:onWriteStream(streamId, connection)
	streamWriteUIntN(streamId, self.filmIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function Autokino:onReadStream(streamId, connection)
	self.filmIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:applyPlayback(true)
end

function Autokino:onWriteUpdateStream(streamId, connection, dirtyMask)
	if not connection:getIsServer() then
		if streamWriteBool(streamId, bit32.band(dirtyMask, self.stateDirtyFlag) ~= 0) then
			streamWriteUIntN(streamId, self.filmIndex, 4)
			streamWriteBool(streamId, self.playing)
			streamWriteFloat32(streamId, self.startTime)
		end
	end
end

function Autokino:onReadUpdateStream(streamId, timestamp, connection)
	if connection:getIsServer() then
		if streamReadBool(streamId) then
			self.filmIndex = streamReadUIntN(streamId, 4)
			self.playing = streamReadBool(streamId)
			self.startTime = streamReadFloat32(streamId)
			self:applyPlayback(false)
		end
	end
end

function Autokino:getStartTimeFor(playing)
	if playing then
		return (g_time + Autokino.LEAD_TIME_MS) / 1000
	end
	return 0
end

function Autokino:requestState(filmIndex, playing)
	if #self.films == 0 then
		return
	end
	filmIndex = math.max(1, math.min(#self.films, filmIndex or 1))
	playing = playing == true
	if g_currentMission:getIsServer() then
		local startTime = self:getStartTimeFor(playing)
		self:applyState(filmIndex, playing, startTime)
		if g_server ~= nil then
			g_server:broadcastEvent(AutokinoStateEvent.new(self, filmIndex, playing, startTime),
				false, nil, nil)
		end
	else
		g_client:getServerConnection():sendEvent(
			AutokinoStateEvent.new(self, filmIndex, playing, 0))
	end
end

function Autokino:applyState(filmIndex, playing, startTime, announce)
	self.filmIndex = math.max(1, math.min(math.max(#self.films, 1), filmIndex or 1))
	self.playing = playing == true
	self.startTime = startTime or 0
	if self.isServer then
		self:raiseDirtyFlags(self.stateDirtyFlag)
	end
	self:applyPlayback(announce ~= false)
end

function Autokino:applyPlayback(announce)
	if #self.films == 0 then
		return
	end
	if self.playing then
		local delay = math.max(0, self.startTime - g_time / 1000)
		self:startLocalPlayback(delay)
	else
		self:stopLocalPlayback()
	end
	if announce and self.playing and self.isClient then
		local film = self.films[self.filmIndex]
		if film ~= nil then
			g_currentMission:addIngameNotification(FSBaseMission.INGAME_NOTIFICATION_INFO,
				string.format("%s: %s", self:getName(), self:getL10n(film.title)))
		end
	end
end

function Autokino:startLocalPlayback(delay)
	local film = self.films[self.filmIndex]
	self:stopLocalPlayback()
	if film == nil or film.sample == nil then
		return
	end
	self.localSample = film.sample
	g_soundManager:playSample(film.sample, delay or 0)
end

function Autokino:stopLocalPlayback()
	if self.localSample ~= nil then
		g_soundManager:stopSample(self.localSample, 0, 0.6)
		self.localSample = nil
	end
end

-- ---------------------------------------------------------------------------
-- input

function Autokino:getIsPlayerClose()
	if g_localPlayer == nil or self.rootNode == nil then
		return false
	end
	local x, _, z = getWorldTranslation(self.rootNode)
	local px, _, pz = getWorldTranslation(g_localPlayer.rootNode)
	local dx, dz = px - x, pz - z
	return dx * dx + dz * dz < Autokino.NOTIFY_RADIUS * Autokino.NOTIFY_RADIUS
end

function Autokino:onActionNextFilm()
	if not self:getIsPlayerClose() then
		return
	end
	local nextIndex = self.filmIndex + 1
	if nextIndex > #self.films then
		nextIndex = 1
	end
	self:requestState(nextIndex, true)
end

function Autokino:onActionToggleFilm()
	if not self:getIsPlayerClose() then
		return
	end
	self:requestState(self.filmIndex, not self.playing)
end

-- ---------------------------------------------------------------------------
-- the picture

function Autokino:getFramePath(film, index)
	return string.format("%s%s_%02d.dds", Autokino.FRAME_FOLDER, film.key, index)
end

function Autokino:setFrame(film, index)
	if self.screenMaterial == nil or self.screenMaterial == 0 then
		return
	end
	index = index % film.frames
	if index == self.frameIndex and self.frameFilm == film.key then
		return
	end
	local path = Utils.getFilename(self:getFramePath(film, index), self.baseDirectory)
	self.screenMaterial = setMaterialDiffuseMapFromFile(self.screenMaterial, path,
		false, true, false)
	self.frameIndex = index
	self.frameFilm = film.key
end

function Autokino:update(dt)
	if self.rootNode ~= nil then
		self:tick(dt)
	end
	Placeable.update(self, dt)
end

function Autokino:tick(dt)
	if self.rootNode == nil then
		return
	end
	local close = self:getIsPlayerClose()
	for _, entry in ipairs(self.inputActions) do
		g_inputBinding:setActionEventActive(entry.id, close)
	end

	local film = self.films[self.filmIndex]
	if film == nil then
		return
	end
	local elapsed = self.playing and (g_time / 1000 - self.startTime) or 0
	if elapsed < 0 then
		elapsed = 0
	end
	self:setFrame(film, math.floor(elapsed * self.fps))
end

-- ---------------------------------------------------------------------------
AutokinoStateEvent = {}
local AutokinoStateEvent_mt = Class(AutokinoStateEvent, Event)
InitStaticEventClass(AutokinoStateEvent, "AutokinoStateEvent")

function AutokinoStateEvent.emptyNew()
	return Event.new(AutokinoStateEvent_mt)
end

function AutokinoStateEvent.new(placeable, filmIndex, playing, startTime)
	local self = AutokinoStateEvent.emptyNew()
	self.placeable = placeable
	self.filmIndex = filmIndex
	self.playing = playing
	self.startTime = startTime
	return self
end

function AutokinoStateEvent:readStream(streamId, connection)
	self.placeable = NetworkUtil.readNodeObject(streamId)
	self.filmIndex = streamReadUIntN(streamId, 4)
	self.playing = streamReadBool(streamId)
	self.startTime = streamReadFloat32(streamId)
	self:run(connection)
end

function AutokinoStateEvent:writeStream(streamId, connection)
	NetworkUtil.writeNodeObject(streamId, self.placeable)
	streamWriteUIntN(streamId, self.filmIndex, 4)
	streamWriteBool(streamId, self.playing)
	streamWriteFloat32(streamId, self.startTime)
end

function AutokinoStateEvent:run(connection)
	if self.placeable == nil or self.placeable.isDeleted then
		return
	end
	if not connection:getIsServer() then
		local startTime = self.placeable:getStartTimeFor(self.playing)
		self.startTime = startTime
		self.placeable:applyState(self.filmIndex, self.playing, startTime)
		if g_server ~= nil then
			g_server:broadcastEvent(self, false, connection, nil)
		end
	else
		self.placeable:applyState(self.filmIndex, self.playing, self.startTime)
	end
end
