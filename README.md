# FS25 UFO 2000 – fliegende Untertasse mit Kornkreis-Generator

Zwei kleine Mods für **Farming Simulator 25**:

| Mod | Was es ist |
| --- | --- |
| **`dist/FS25_UFO2000.zip`** | Die fliegende Untertasse – großes Glaskuppel-Cockpit (Simpsons-Stil), grüner Leuchtenkranz, drei Landebeine, rotes Drehlicht, Traktorstrahl und ein **Kornkreis-Menü** |
| **`dist/FS25_Alien.zip`** | Das Alien-Maskottchen als eigene, aufstellbare Deko – getrennt vom UFO, weil unter der Kuppel jetzt **dein eigener Charakter** sitzt |

![UFO 2000](docs/renders/ufo_hero.png)

---

## 1. Installation

1. Beide ZIPs (oder nur die, die du willst) **unverändert** in den Mods-Ordner legen:
   - Windows: `Dokumente\My Games\FarmingSimulator25\mods\`
   - macOS: `~/Library/Application Support/FarmingSimulator25/mods/`
2. Spiel starten, im Hauptmenü unter **Mods** die Häkchen setzen.
3. UFO: am Händler unter **Fahrzeuge → Autos** für 42.000 € kaufen.
   Alien: unter **Platzierbare Objekte → Deko** für 750 € aufstellen.

Keine weiteren Mods nötig, die beiden sind unabhängig voneinander.

## 2. Steuerung – alles über die normalen Spiel-Optionen

Es gibt **keine Sondertasten** außer dem Menü. Alles läuft über Aktionen, die
das Spiel schon kennt, damit Tastatur, Gamepad und Joystick einfach mitgehen:

| Was | Taste (Standard) | Kommentar |
| --- | --- | --- |
| Abheben / Landen | `V` („Gerät absenken") | ist auch auf jedem Gamepad/Joystick belegt |
| Steigen / Sinken | Frontladerarm-Achse (`Joystick`) oder `Bild ↑` / `Bild ↓` | analog, also stufenlos |
| Traktorstrahl an/aus | `Z` („Gerät extra") | löst den Kornkreis aus |
| Kornkreis-Menü | `M` | eigenes Menü, frei belegbar |
| Vorwärts / Rückwärts | `W` / `S` (Gas/Bremse) | wie beim Traktor |
| Lenken | `A` / `D` | dreht das UFO um die Hochachse |
| Hupe | Hupe | das UFO grüßt |
| Kamera | `C` | außen / innen |

Alles davon lässt sich unter **Optionen → Steuerung** umbelegen (Suche nach
„UFO"). Tastenbelegungen mit `Bild ↑/↓` sind nur die bequeme Tastatur-Variante
der Achse.

## 3. Fliegen

- **Abheben:** `V` – die Beine klappen ein, das UFO schwebt auf etwa 3 m und
  **bleibt von allein in der Luft stehen**, ohne dass du etwas halten musst.
- **Höhe:** Joystick-Achse oder `Bild ↑/↓` – stufenlos bis **120 m** über Grund.
  Das UFO folgt weich und wiegt leicht.
- **Fliegen:** `W`/`S` bis ca. **31 km/h**, `A`/`D` dreht. Beim Fliegen neigt
  sich die Untertasse leicht in die Richtung.
- **Landen:** `V` oder ganz nach unten steuern – das UFO sinkt, die Beine
  fahren aus, es steht wieder normal am Boden. Der Strahl geht dabei aus.
- **Sound:** weicher Schwebe-Sound mit kleinen „Blubber"-Tönen, drei
  Drehzahl-Ebenen, Start/Stopp-Sweep und eine fröhliche Alien-Melodie als Hupe
  (Hörprobe: `docs/sound_demo.ogg`).

![Landebeine ein- und ausgefahren](docs/renders/ufo_legs.png)

## 4. Kornkreise ins Feld mähen

1. Über das Feld fliegen und mit `V` abheben.
2. `M` öffnet das **Bordmenü** – dort stehen neun Geometrien zur Auswahl.
3. Mit `Bild ↑ / ↓` (bzw. der Achse) das Muster wählen, mit `Z` anwenden.
4. Der Traktorstrahl fährt auf, ein Ring am Boden wächst auf die Zielgröße, und
   die Pflanzen darunter werden **von oben nach unten gemäht** – genau in der
   gewählten Form, ohne dass ein Mähdrescher drüberfahren muss.

Der **Radius ergibt sich aus der Flughöhe**: der Strahl endet immer genau am
Boden, sein halber Öffnungswinkel beträgt 34°. Bei 10 m Höhe sind das ca. 6,7 m
Radius, bei 40 m ca. 27 m (gedeckelt bei 70 m). Die Formskala ist der Strahl,
die Größe stellst du also einfach mit der Höhe ein. Das HUD zeigt während des
Fluges Höhe, gewähltes Muster und aktuellen Radius.

![Die neun Grundkreis-Geometrien](docs/renders/circles.png)

Muster: Kreis · Ring · Drei Ringe · Spirale · Blüte · Stern · Alien-Gesicht ·
Blume des Lebens · Sonne

Das Mähen passiert serverseitig in Streifen (kein Lag), funktioniert also auch
im Multiplayer. Es wird nur **Frucht auf Feldern** gemäht, Zäune und Gebäude
bleiben unangetastet.

![Strahl und Markierungsring](docs/renders/ufo_beam.png)

## 5. Was drin ist

**UFO 2000**
- Modell: 12.700 Dreiecke, 12 Shapes – Rumpf, große Glaskuppel mit Sitz für
  deinen Charakter, Konsole, drei einfahrbare Beine, Leuchtenkranz, Drehlicht,
  Strahlkegel, Bodenring
- 6 Lichter (Abblendlicht links/rechts, Arbeitslicht, Strahl, Drehlicht,
  Rücklicht), 2 Kameras
- `scripts/UFO2000.lua`: Flug-Specialization mit Server-Autorität,
  Multiplayer-Sync, Achsen-/Tasten-Eingabe, Kornkreis-Raster und HUD-Menü
- 7 selbst erzeugte OGG-Sounds, DDS-Texturen, Shop-Icon, Brand-Logo
- Deutsch + Englisch

**Alien-Maskottchen**
- 4.400 Dreiecke, 2 Shapes (Mesh + unsichtbare Kollision), 7 Texturen
- Platzierbar, frei drehbar, wieder aufnehmbar, Preis 750 €

### Feintuning

Flugwerte stehen oben in `FS25_UFO2000/scripts/UFO2000.lua`:

```lua
UFO2000.MAX_ALTITUDE   = 120.0   -- maximale Höhe über Grund
UFO2000.MIN_ALTITUDE   = 1.10    -- Schwebehöhe mit eingeklappten Beinen
UFO2000.CLIMB_SPEED    = 6.5     -- m/s auf der Höhenachse
UFO2000.YAW_SPEED      = 55.0    -- Grad/s beim Drehen
UFO2000.MAX_SPEED      = 8.5     -- m/s Horizontalflug (~31 km/h)
UFO2000.BEAM_HALF_ANGLE = 34.0   -- Öffnungswinkel des Strahls (= Radius/Höhe)
UFO2000.CIRCLE_CELL    = 0.35    -- Rasterfeinheit der gemähten Form
```

## 6. Selbst bauen (optional)

Alles ist per Python erzeugt, Blender ist nicht nötig:

```bash
python3 -m venv .venv
.venv/bin/pip install numpy pillow soundfile lxml luaparser lupa
.venv/bin/python tools/build_mod.py            # UFO: Modell, Media, Prüfung, ZIP
.venv/bin/python tools/alien/build.py          # Alien: Modell, Icon, Prüfung, ZIP
.venv/bin/python tools/ufo/validate.py         # nur prüfen
.venv/bin/python tools/alien/validate.py
.venv/bin/python tools/ufo/luatest.py          # Fluglogik ohne Spiel testen
.venv/bin/python tools/ufo/circle_preview.py   # Muster-Vorschau erzeugen
```

Die Prüfskripte kontrollieren beide XMLs gegen die echten FS25-Schemas
(modDesc, vehicle, placeable, i3d 1.6), alle i3dMappings, die l10n-Keys, die
Lua-Syntax und den ZIP-Inhalt. `luatest.py` simuliert die Engine-Schnittstelle
und fliegt einmal komplett durch: abheben, steigen, kurven, Kornkreis mähen,
landen, Beine ein-/ausfahren, Multiplayer-Sync.

## 7. Ehrlicher Hinweis

Getestet ist alles, was ohne Spiel geht – **im echten FS25 lief es noch nicht**
(hier ist keins installiert). Wenn etwas klemmt, hilft die `log.txt`; Zeilen mit
„UFO2000" oder „Alien" zeigen die Stelle, dann bessere ich gezielt nach.

Viel Spaß beim Schweben – und grüß Alf. 👽
