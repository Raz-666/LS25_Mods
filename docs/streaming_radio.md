# Internetradio im FS25 – was ein Mod darf und was nicht

## Kurzfassung

* **Lua im Spiel kann keine URLs öffnen.** Es gibt kein HTTP-, Socket- oder
  Download-API für Mods. `createSample`, `loadSample`, `createAudioSource`
  nehmen ausschließlich Dateinamen. Ein Mod kann also **keinen** SoundCloud-Link
  und **keine** frei eingegebene Stream-URL abspielen.
* Das **Spiel selbst** hat einen Radio-Player (`g_soundPlayer`). Er liest die
  Senderliste aus dem Spielprofil und kann Icecast-/Shoutcast-Streams
  (mp3, aac, m3u, pls) abspielen – aber nur auf dem jeweiligen PC und nur, wenn
  der Spieler das zugelassen hat.
* Die Distillery nimmt das Spielradio als **zweite Quelle in die Auswahl am
  DJ-Pult** auf: Taste **`R`** schaltet zwischen *Club-PA* (synchronisierte
  Playlist) und *Club-Radio* (dein Stream) um, `N` wechselt dann die Sender,
  `M` pausiert. Zwei kleine Lampen am Set-List-Board zeigen die aktive Quelle
  (amber = PA, cyan = Radio). Die Club-PA läuft für alle anderen weiter.

## Sender hinzufügen

1. Im Profilordner den Ordner `FS25` öffnen, dort die Datei
   `streamingInternetRadios.xml` suchen (bzw. anlegen):

   * Windows: `Dokumente/My Games/FarmingSimulator2025/`
   * Linux (Proton): `.../steamapps/compatdata/2300320/pfx/drive_c/users/steamuser/Documents/My Games/FarmingSimulator2025/`
   * macOS: `~/Library/Application Support/FarmingSimulator2025/`

2. Einen Eintrag ergänzen:

```xml
<?xml version="1.0" encoding="utf-8" standalone="no"?>
<streamingInternetRadios>
    <streamingInternetRadio href="https://example.org/stream.mp3" />
    <streamingInternetRadio href="https://example.org/chill.pls" />
</streamingInternetRadios>
```

3. Im Spiel einmal das Radio öffnen und den Stream bestätigen
   („Stream erlauben?"). Danach schaltet `R` am DJ-Pult auf die Radio-Quelle,
   und `N` blättert durch deine Sender.

## Warum kein echter „ein Stream für alle"

Ein Stream, den der Server abspielt und an alle Clients verteilt, würde einen
Audio-Mixdown und eine eigene Netzwerk-Übertragung im Mod brauchen – beides
gibt es in FS25 für Mods nicht. Deshalb ist die synchronisierte **Playlist mit
OGG-Dateien im Mod** der einzige Weg, bei dem wirklich alle im Club dasselbe
hören, und zwar ab derselben Sekunde.

## Eigene Titel in die Playlist

1. Datei nach OGG Vorbis wandeln (44,1 kHz, stereo), z. B. mit `ffmpeg`:

```bash
ffmpeg -i lied.mp3 -c:a libvorbis -q:a 5 FS25_Distillery/sounds/lied.ogg
```

2. In `FS25_Distillery/sounds/distillerySounds.xml` eine Zeile ergänzen:

```xml
<music7 file="sounds/lied.ogg" loops="0" bpm="128" title="l10n_distillery_track_lied"
        volumeScale="0.92" innerRadius="9" outerRadius="55" priority="HIGH"
        fadeIn="0.6" fadeOut="1.0" supportsReverb="true"/>
```

3. In `modDesc.xml` den passenden l10n-Text `l10n_distillery_track_lied`
   (deutsch/englisch) eintragen. Der Titel erscheint dann auch in der
   Bildschirmmeldung beim Wechsel. Das Board am DJ-Pult zeigt weiterhin die
   sechs eingebauten Zeilen – für mehr Zeilen die Textur in
   `tools/venue/signs.py` (`playlist_panel`) erweitern und neu bauen.
