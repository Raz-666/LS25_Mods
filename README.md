# FS25 UFO 2000 – fliegende Untertasse

Ein kleiner, niedlicher Flug-UFO-Mod für **Farming Simulator 25**, optisch an die
Untertasse aus der alten **ALF**-Serie angelehnt: Kuppel mit Alien-Pilot,
grün leuchtender Kranz, drei Landebeine, rotes Drehlicht und ein Traktorstrahl
nach unten.

![UFO 2000](docs/renders/ufo_hero.png)

---

## 1. Installation

1. Datei **`dist/FS25_UFO2000.zip`** herunterladen/herstellen.
2. Die ZIP **unverändert** (nicht entpacken) in den Mods-Ordner legen:
   - Windows: `Dokumente\My Games\FarmingSimulator25\mods\`
   - macOS: `~/Library/Application Support/FarmingSimulator25/mods/`
3. Spiel starten, im Hauptmenü unter **Mods** das Häkchen bei „UFO 2000" setzen
   (bzw. in der Karriere-Konfiguration aktivieren).
4. Im Spiel am Händler unter **Fahrzeuge → Autos** kaufen (Preis 42.000 €),
   oder direkt im Savegame über die Fahrzeugliste.

Der Mod braucht **keine weiteren Mods** und keine zusätzlichen Skripte im
Mods-Ordner – alles (Modell, Texturen, Sounds, Fluglogik) steckt in der ZIP.

## 2. Steuerung

| Taste | Funktion |
| --- | --- |
| `H` | Abheben / Landen |
| `Bild ↑` (`Page Up`) | Steigen (Zielhöhe erhöhen) |
| `Bild ↓` (`Page Down`) | Sinken (Zielhöhe verringern) |
| `B` | Traktorstrahl ein / aus |
| `W` / `S` | Vorwärts / rückwärts fliegen |
| `A` / `D` | Kurve fliegen (Gieren) |
| `HupTaste` (`Horn`) | Alien-Begrüßung |
| `C` | Kamera wechseln (Außen-/Innenansicht) |

Die Belegung lässt sich wie gewohnt unter **Optionen → Steuerung** ändern
(Suche nach „UFO"). Beim Aussteigen sinkt das UFO automatisch ab und landet.

## 3. Flugverhalten

- **Abheben:** `H` – die Landebeine klappen ein, das UFO schwebt auf ca. 3 m
  über dem Boden und bleibt dort stehen.
- **Höhe:** `Bild ↑` / `Bild ↓` verändern die Zielhöhe stufenlos, maximal
  **120 m** über Grund. Das UFO folgt der Zielhöhe weich, mit leichtem
  Schweben/Wiegen.
- **Fliegen:** mit `W`/`S` bis ca. **31 km/h**, `A`/`D` dreht das UFO. Beim
  Fliegen neigt es sich leicht in die Richtung – wie eine echte Untertasse.
- **Landen:** `H` (oder `Bild ↓` bis ganz unten) – das UFO sinkt, die Beine
  fahren aus, das Gerät steht wieder normal am Boden und kann ganz normal
  rangiert werden.
- **Traktorstrahl:** `B` schaltet den kegelförmigen Lichtstrahl unter dem
  Rumpf ein und aus.
- **Sound:** Starten/Stoppen des Antigravitations-Antriebs, drei
  Motordrehzahl-Stufen (Leerlauf / Reise / Last), dazu ein fröhliches
  Alien-Piepen als Hupe. Hörprobe: `docs/sound_demo.ogg`.

Der UFO-Motor (113 PS Diesel, 90 l Tank) muss laufen, sonst hebt das Gerät nicht
ab – tanken also nicht vergessen. Auf der Straße fährt es sich wie ein
schwerfälliger, aber braver Traktor.

## 4. Was drin ist

- `FS25_UFO2000/ufo.i3d` + `.shapes` – Modell (13.284 Dreiecke, 12 Shapes):
  Untertassenrumpf, Kuppel, Alien-Pilot, Cockpit-Konsole, drei Landebeine,
  Leuchtkranz, rotes Drehlicht, Traktorstrahl-Kegel
- 6 Lichter (Abblendlicht links/rechts, Arbeitslicht, Traktorstrahl, Drehlicht,
  Rücklicht) und 2 Kameras (Außen/Innen)
- `scripts/UFO2000.lua` – Flug-Specialization (Server-autoritativ,
  mehrspielerfähig, eigene Netzwerk-Synchronisation und Tasten-Events)
- 7 selbst erzeugte OGG-Sounds, DDS-Texturen, Shop-Icon und Brand-Logo
- Deutsche und englische Texte (`translations/`)

### Feintuning

Flugwerte stehen als Konstanten oben in `FS25_UFO2000/scripts/UFO2000.lua`:

```lua
UFO2000.MAX_ALTITUDE    = 120.0   -- maximale Höhe über Grund
UFO2000.MIN_ALTITUDE    = 1.10    -- Schwebehöhe mit eingeklappten Beinen
UFO2000.CLIMB_SPEED     = 6.5     -- m/s beim Steigen/Sinken
UFO2000.YAW_SPEED       = 55.0    -- Grad/s beim Drehen
UFO2000.MAX_SPEED       = 8.5     -- m/s Horizontalflug (~31 km/h)
UFO2000.LEG_RETRACT_TIME = 1.4    -- Sekunden für das Ein-/Ausfahren der Beine
```

## 5. Selbst bauen (optional)

Alles im Mod wurde per Python-Skript erzeugt, Blender ist nicht nötig:

```bash
python3 -m venv .venv
.venv/bin/pip install numpy pillow soundfile lxml luaparser
.venv/bin/python tools/build_mod.py          # Modell, Media, Prüfung, ZIP
.venv/bin/python tools/ufo/validate.py       # nur prüfen
.venv/bin/python tools/ufo/luatest.py        # Fluglogik ohne Spiel testen
```

Ergebnis: `dist/FS25_UFO2000.zip`. Die Prüfskripte kontrollieren XML gegen die
FS25-Schemas (modDesc, vehicle, i3d 1.6), alle i3dMappings, die l10n-Keys, die
Lua-Syntax und den Inhalt der ZIP.

## 6. Ehrlicher Hinweis

Der Mod wurde **nicht im echten Spiel getestet** – in dieser Umgebung läuft kein
FS25. Modell, XML, Texturen, Sounds und ZIP sind geprüft, die Fluglogik wurde
gegen eine nachgebaute Engine-Schnittstelle simuliert (Abheben, Steigen, Kurven,
Landen, Multiplayer-Sync). Sollte im Spiel etwas klemmen, hilft ein Blick in die
`log.txt`; Fehlermeldungen mit „UFO2000" lassen sich dann gezielt beheben.

Viel Spaß beim Schweben – und grüß Alf. 👽
