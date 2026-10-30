# Offline-3D-Prüfung für Mod-ZIPs

Mit diesem kleinen Prüfprogramm lässt sich die 3D-Geometrie direkt aus einer Mod-ZIP ansehen — **ohne FS25 und ohne GIANTS Editor**. Die Vorschau basiert auf den tatsächlich gepackten I3D-Daten und ist kein KI-Bild.

## So benutzt man es unter Windows

1. Python 3.8 oder neuer muss installiert sein. Das Programm verwendet nur die Python-Standardbibliothek; zusätzliche Pakete oder eine Internetverbindung sind nicht nötig.
2. Die Dateien `Pruefe_3D-Mod.bat` und `inspect_mod_3d.py` sowie der Ordner `i3d` müssen zusammenbleiben.
3. Ziehe die gewünschte Mod-`.zip` mit der Maus auf `Pruefe_3D-Mod.bat`.
4. Ein HTML-Prüfbericht wird neben der Mod-ZIP erstellt und im Browser geöffnet. Er enthält die Softwarevorschau, erkannte Geometrie, Shape-IDs, Material-/Texturverweise, Transformwerte, Bounds und fehlende Dateien.

Die ZIP wird nur gelesen und **nicht entpackt**. Inhalte der Mod (insbesondere Lua-Dateien) werden nicht ausgeführt. Alle Prüfungen laufen lokal.

## Was der Bericht aussagt

- Er decodiert die I3D-Szene sowie die gepaarte GIANTS-Formatversion-10-`.i3d.shapes`-Datei und zeichnet deren gespeicherte Dreiecke mit den Szenen-Transforms.
- Damit lässt sich prüfen, ob das tatsächliche Mesh im ZIP vorhanden, lesbar und mit den Shape-Knoten der I3D verbunden ist.
- Die Vorschau ist ein einfacher Software-Renderer. DDS-Texturen, GIANTS-Shader, FS25-Beleuchtung, Animationen, Fahrzeug-/Placeable-Logik und das Laden im Spiel werden nicht nachgebildet. Texturmaterialien bekommen nur eine unterscheidbare Ersatzfarbe.
- Verdeckte und als `nonRenderable` markierte Geometrie (z. B. Kollisionskörper) wird aus der normalen Bildvorschau ausgelassen, aber in den Listen bzw. Shape-Zahlen berücksichtigt.
- Ein fehlerfreier Bericht ist **kein** Beweis für ein korrekt ladendes oder funktionierendes Mod im Spiel. Dafür wäre FS25 bzw. bei Bedarf GIANTS Editor nötig.

## Fehler und Grenzen

Fehlende `.i3d.shapes`-Dateien, kaputte Referenzen, unlesbare XML-Dateien, unbekannte Shape-IDs oder ein nicht unterstütztes Shapes-Format werden im Bericht angezeigt. Der Decoder unterstützt derzeit Shapes-Dateien der Version 10 (FS25 / GIANTS Editor 10). Andere Versionen können nicht verlässlich dargestellt werden.

## Dateien und Lizenz

Das Prüfprogramm ist `tools/inspect_mod_3d.py`; der Doppelklick-/Drag-and-drop-Starter ist `tools/Pruefe_3D-Mod.bat`. Der Decoder und die dazugehörigen Formatdateien liegen unter `tools/i3d/`. Siehe dort `LICENSE-NOTICE.md`.
