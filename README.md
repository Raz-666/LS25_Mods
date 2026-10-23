# FS25 UFO 2000 – fliegende Untertasse mit Kornkreis-Generator

Zwei kleine Mods für **Farming Simulator 25**:

| Mod | Was es ist |
| --- | --- |
| **`dist/FS25_UFO2000.zip`** | Die fliegende Untertasse – großes Glaskuppel-Cockpit (Simpsons-Stil), grüner Leuchtenkranz, drei Landebeine, rotes Drehlicht, Traktorstrahl, **Kornkreis-Menü mit manuellem 50-cm-Stift** |
| **`dist/FS25_Alien.zip`** | Das Alien-Maskottchen als eigene, aufstellbare Deko – getrennt vom UFO, weil unter der Kuppel jetzt **dein eigener Charakter** sitzt |
| **`dist/FS25_UFO2500.zip`** | **Konsolen-Edition ohne eine Zeile Lua** – dasselbe UFO, 10 m über dem Feld, rollt auf unsichtbaren Rädern und drückt mit einem 0,5 – 7,5 m breiten Pinsel Kornkreise ins Getreide |

![UFO 2000](docs/renders/ufo_hero.png)

| Mod | PC / Mac | Xbox / PlayStation |
| --- | --- | --- |
| UFO 2000 | ✅ fliegen, Höhe, Strahl, 10 Muster | ❌ eigener Lua-Code |
| Alien-Maskottchen | ✅ | ⚠️ möglich (nur noch über ModHub einreichen) |
| UFO 2500 | ✅ | ✅ **kein Lua, nur Grundspiel-Technik** |

---

## 1. Installation

1. Die ZIPs (oder nur die, die du willst) **unverändert** in den Mods-Ordner legen:
   - Windows: `Dokumente\My Games\FarmingSimulator25\mods\`
   - macOS: `~/Library/Application Support/FarmingSimulator25/mods/`
2. Spiel starten, im Hauptmenü unter **Mods** die Häkchen setzen.
3. UFO 2000: am Händler unter **Fahrzeuge → Autos** für 42.000 € kaufen.
   UFO 2500: ebd. unter der Marke **Lizard** für 38.000 €.
   Alien: unter **Platzierbare Objekte → Deko** für 750 € aufstellen.
   (UFO 2000 und UFO 2500 sind zwei eigenständige Mods – nimm das, was dir
   gefällt, oder beide.)

Keine weiteren Mods nötig, alle drei sind unabhängig voneinander.

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

## 4. Kornkreise ins Feld drücken

1. Über das Feld fliegen und mit `V` abheben.
2. `M` öffnet das **Bordmenü** – dort stehen neun Geometrien plus der **manuelle
   Modus** zur Auswahl.
3. Mit `Bild ↑ / ↓` (bzw. der Achse) das Muster wählen, mit `Z` anwenden.
4. Der Traktorstrahl fährt auf, ein Ring am Boden wächst auf die Zielgröße, und
   die Pflanzen darunter werden **von der Mitte nach außen plattgedrückt** –
   genau in der gewählten Form, ohne dass ein Mähdrescher drüberfahren muss.

Es wird **nichts gemäht**: die Ernte bleibt stehen, wird aber zerdrückt. Genau
das macht das Spiel auch, wenn ein Fahrzeugreifen über ein Feld rollt – die
Pflanzen sind platt, der Ertrag an der Stelle ist weg, das Feld selbst bleibt
unverändert. Das ist der Effekt `updateWheelDestructionArea` aus dem Basisspiel
und funktioniert damit auch bei allen Fruchtarten.

Der **Radius ergibt sich aus der Flughöhe**: der Strahl endet immer genau am
Boden, sein halber Öffnungswinkel beträgt 34°. Bei 10 m Höhe sind das ca. 6,7 m
Radius, bei 40 m ca. 27 m (gedeckelt bei 70 m). Die Formskala ist der Strahl,
die Größe stellst du also einfach mit der Höhe ein. Das HUD zeigt während des
Fluges Höhe, gewähltes Muster und aktuellen Radius.

![Die neun Grundkreis-Geometrien](docs/renders/circles.png)

Muster: Kreis · Ring · Drei Ringe · Spirale · Blüte · Stern · Alien-Gesicht ·
Blume des Lebens · Sonne · **Manuell**

### Manueller Modus (50-cm-Stift)

Im manuellen Modus öffnet sich der Strahl nicht zum Kegel, sondern bleibt zu
einem **dünnen Strich von ca. 50 cm Durchmesser** gebündelt, der senkrecht auf
den Boden zeigt. Du fliegst einfach los und „malst" dabei: alle ~22 cm setzt das
UFO einen 50-cm-Stempel in die Ernte, dazwischen interpoliert das Spiel. So
kannst du eigene Formen, Buchstaben, Pfeile oder Spiralen in ein Feld ziehen –
langsam fliegen = feine Linie, schneller = grober Strich. Stehen bleiben setzt
keine weiteren Stempel, du kannst also in Ruhe neu ansetzen.

### Spuren beim Start und bei der Landung

Jedes Abheben und Aufsetzen drückt einen **kreisrunden Fleck von ca. 3,8 m
Durchmesser** in die Ernte darunter, dazu je Landebein einen kleinen Abdruck.
Das passiert nur, wenn tatsächlich Frucht unter dem UFO steht – auf Wiese,
Straße oder Hof passiert nichts. Wer auf seinem Feld landet, sieht danach
also die Untertasse stehen, wo sie stand. 🙂

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

**UFO 2500 (Konsole)**
- dasselbe Modell (12.800 Dreiecke), aber **kein Lua, kein `scripts/`-Ordner**
- 19 unsichtbare Räder: 4 Pflege-Räder (tragen) + 15 Pinsel-Räder (drücken)
- 4 Radkonfigurationen als Pinselbreite (0,5 / 1,5 / 3,5 / 7,5 m)
- Strahl und Bodenring als feste Geometrie, Bodenlicht, Kameras, Sounds
- Marke `Lizard`, Deutsch + Englisch

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
UFO2000.CIRCLE_CELL    = 0.35    -- Rasterfeinheit der gedrückten Form
UFO2000.MANUAL_RADIUS  = 0.25    -- Stift-Radius (50 cm Durchmesser)
UFO2000.LANDING_MARK_RADIUS = 1.9 -- Spurenfleck beim Start / bei der Landung
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
.venv/bin/python tools/build_console_mod.py    # UFO 2500 (Konsole): Modell, Media, ZIP
.venv/bin/python tools/ufo/validate2500.py     # Konsolen-Regeln prüfen
.venv/bin/python tools/ufo/brush_test.py       # Pinselbreiten nachrechnen
.venv/bin/python tools/ufo/brush_patterns.py   # Beispiel-Kornkreise rendern
.venv/bin/python tools/ufo/brush_preview.py    # Pinselbreiten-Diagramm
.venv/bin/python tools/ufo/console_preview.py  # Schnittzeichnung
```

Die Prüfskripte kontrollieren beide XMLs gegen die echten FS25-Schemas
(modDesc, vehicle, placeable, i3d 1.6), alle i3dMappings, die l10n-Keys, die
Lua-Syntax und den ZIP-Inhalt. `luatest.py` simuliert die Engine-Schnittstelle
und fliegt einmal komplett durch: abheben, steigen, kurven, Muster drücken,
mit dem Stift malen, landen, Beine ein-/ausfahren, Spuren, Multiplayer-Sync.

## 7. Konsole (Xbox / PlayStation) – so geht es doch: das UFO 2500

Auf Konsolen sind eigene Lua-Skripte verboten („Mods must not contain any extra
lua scripts"), deshalb ist das fliegende **UFO 2000** PC-only. Für das **UFO
2500** ist die Fliegerei aber gar nicht nötig – es benutzt nur, was das
Grundspiel ohnehin mitbringt:

```
        .-'-.
      .'  Cockpit  '.        <- dein Charakter sitzt 10,00 m über dem Boden
     /   (Glaskuppel) \      <- Rumpf schwebt 8,83 m über dem Ursprung
    |=================|
     \__  Strahl  __/        <- feste Geometrie, endet immer am Boden
        |  |  |  |             <- 15 unsichtbare Pinsel-Räder à 0,5 m
  ______|__|__|__|______       <- 4 unsichtbare Pflege-Räder tragen das Fahrzeug
  Aufstandspunkte am Boden  =  das Spiel sieht ein ganz normales Auto
```

**Der Trick:** Das Fahrzeug ist ein stinknormales `baseDrivable`-Fahrzeug – nur
mit **unsichtbaren Rädern**. Die vier Pflegereifen stehen am Boden (Radradius
0,55 m), das eigentliche UFO ist als Modell 8,83 m darüber montiert. Der
Fahrzeug-Ursprung bleibt am Boden, also funktionieren Physik, Kamera,
Ein-/Aussteigen, Shop und Spawn genau wie bei einem Traktor – nur dass oben
eine Untertasse hängt und darunter „Luft statt Räder" ist. Genau das, was du
beschrieben hast: ein 10 m hoher Mähdrescher ohne Aufbau unter dem Cockpit.

**Kornkreise ohne Skript:** Die Rad-Beschädigung des Grundspiels
(`WheelDestruction`) drückt pro Rad und Frame ein Rechteck von
`Breite × 0,5 m` in die Frucht. Das UFO 2500 hat deshalb unter der Mitte eine
**Reihe aus bis zu 15 unsichtbaren Rädern** („Pinsel"). Wie breit der Pinsel
ist, wählst du im Shop:

| Radkonfiguration | Pinsel | Fläche pro 100 m Fahrt | Wofür |
| --- | --- | --- | --- |
| **Stift** | 1 × 0,5 m | 50 m² | frei malen wie mit dem 50-cm-Stift im PC-Mod |
| **Ring** | 3 × 0,5 m = 1,5 m | 150 m² | kleine Kreise, Buchstaben |
| **Standard** | 7 × 0,5 m = 3,5 m | 350 m² | so groß ist der Bodenring unter dem UFO |
| **Mähdrescher** | 15 × 0,5 m = 7,5 m | 750 m² | eine Bahn und das Feld ist platt |

Weil die Stempel lückenlos aneinanderliegen, ist der Streifen exakt so breit wie
eingestellt (nachgerechnet in `tools/ufo/brush_test.py`: Kreis r = 15 m mit dem
Standard-Pinsel = 330 m² gedrückte Fläche, theoretisch 2π·r·b = 330 m²).

![Pinselbreiten](docs/renders/brushes.png)

**Formen zeichnet man durch Fahren:** Kreis = einmal im Kreis fahren (der
Bodenring zeigt die Pinselbreite), Doppelring = außen rum, quer rein, innen rum,
Stern = gerade Bahnen. Kein Menü, keine Sondertaste, alles Gamepad-tauglich.

![So sehen gefahrene Kornkreise aus](docs/renders/ufo2500_patterns.png)

![Schnitt durch das Fahrzeug](docs/renders/ufo2500_concept.png)

**Was auf Konsole fehlt** (ehrlich): kein Abheben, keine Höhensteuerung, kein
Muster-Menü, kein HUD, keine Start-/Landespuren – das braucht alles Lua. Der
Strahl ist feste Geometrie und immer an, das Arbeitslicht (`L`) macht das grüne
Leuchten am Boden. „Mähdrescher" heißt: die Ernte wird zerstört (Ertrag weg,
Pflanzen platt), geerntet wird nichts.

**ModHub:** Das UFO 2500 ist genau dafür gebaut – kein `scripts/`-Ordner, keine
`<specializations>`, keine `<actions>`, Marke `LIZARD` (Basisspiel). Damit sollte
es den Konsolentest überstehen; einreichen musst du es selbst (Konto auf
farming-simulator.com, TestRunner drüberlaufen lassen, ZIP hochladen).

## 8. Ehrlicher Hinweis

Getestet ist alles, was ohne Spiel geht – **im echten FS25 lief es noch nicht**
(hier ist keins installiert). Wenn etwas klemmt, hilft die `log.txt`; Zeilen mit
„UFO2000", „UFO2500" oder „Alien" zeigen die Stelle, dann bessere ich gezielt nach.

Beim UFO 2500 sind zwei Dinge die ersten Kandidaten für Feinschliff, falls es im
Spiel komisch aussieht: die Fahrhöhe (Federn/Dämpfer der unsichtbaren Räder,
`spring`/`damper` in `ufo2500.xml`) und die Anzahl der Pinsel-Räder pro
Konfiguration. Beides lässt sich in `tools/build_console_mod.py` in einer Zeile
ändern und neu bauen.

Viel Spaß beim Schweben – und grüß Alf. 👽
