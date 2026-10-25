#!/usr/bin/env python3
"""Builds one German PDF manual per mod into docs/pdf/.

Every manual has the same structure so the nine documents read like one
series:

  1. Deckblatt        - Titel, Version, Preis, großes Bild
  2. Was ist das?      - was der Mod macht, mit Bildern (Renders + Vorlagen)
  3. Bedienung         - Tastentabelle (Tastatur + Gamepad)
  4. Worauf achten     - die typischen Fehler und wie man sie vermeidet
  5. Kompatibilität    - PC / Konsole / Multiplayer / Dedicated Server
  6. Technische Daten  - Dateien, Größe, Version, Besonderheiten

    python tools/build_manuals.py [--only NAME ...]
"""

import argparse
import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "pdf")
RENDERS = os.path.join(REPO, "docs", "renders")
REFERENCE = os.path.join(REPO, "docs", "reference")

GREEN = colors.HexColor("#4f8a3d")
DARK = colors.HexColor("#23282b")
GREY = colors.HexColor("#6d757a")
LIGHT = colors.HexColor("#eef2ea")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# --------------------------------------------------------------------------
# styles
# --------------------------------------------------------------------------
def make_styles():
    sheet = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=sheet["Title"], fontName="Helvetica-Bold",
                                fontSize=27, leading=31, textColor=DARK, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=sheet["Normal"], fontSize=12.5,
                                   leading=16, textColor=GREEN, alignment=TA_CENTER,
                                   spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=sheet["Heading1"], fontName="Helvetica-Bold",
                             fontSize=16, leading=19, textColor=DARK,
                             spaceBefore=6, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=sheet["Heading2"], fontName="Helvetica-Bold",
                             fontSize=11.5, leading=14, textColor=GREEN,
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", parent=sheet["BodyText"], fontSize=9.8,
                               leading=13.6, textColor=DARK, alignment=TA_LEFT,
                               spaceAfter=5),
        "bullet": ParagraphStyle("bullet", parent=sheet["BodyText"], fontSize=9.8,
                                 leading=13.2, textColor=DARK, leftIndent=10,
                                 bulletIndent=1, spaceAfter=2),
        "caption": ParagraphStyle("caption", parent=sheet["Normal"], fontSize=8.2,
                                  leading=10, textColor=GREY, alignment=TA_CENTER,
                                  spaceBefore=2, spaceAfter=8),
        "cover_meta": ParagraphStyle("cover_meta", parent=sheet["Normal"], fontSize=10,
                                     leading=14, textColor=GREY, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell", parent=sheet["Normal"], fontSize=8.8, leading=11.4),
        "cellb": ParagraphStyle("cellb", parent=sheet["Normal"], fontName="Helvetica-Bold",
                                fontSize=8.8, leading=11.4),
    }


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def image(path, width_mm, style_caption=None, caption=""):
    """A scaled image with an optional caption, keeping the aspect ratio."""
    from PIL import Image as PILImage

    if not os.path.isfile(path):
        return []
    with PILImage.open(path) as probe:
        w, h = probe.size
    width = width_mm * mm
    height = width * h / float(w)
    flow = [Image(path, width=width, height=height)]
    if caption:
        flow.append(Paragraph(caption, style_caption))
    return flow


def two_up(items, style, gap=6):
    """Two images side by side with captions underneath."""
    cells = []
    for path, caption in items:
        cell = image(path, 76, style, caption)
        cells.append(cell or [Paragraph("", style)])
    table = Table([cells], colWidths=[(PAGE_W - 2 * MARGIN) / 2.0] * 2)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), gap),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def key_table(rows, styles, head=("Taste / Eingabe", "Was passiert")):
    data = [[Paragraph(head[0], styles["cellb"]),
             Paragraph(head[1], styles["cellb"])]]
    for key, text in rows:
        data.append([Paragraph(key, styles["cell"]), Paragraph(text, styles["cell"])])
    table = Table(data, colWidths=[52 * mm, PAGE_W - 2 * MARGIN - 52 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, GREEN),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cdd4cf")),
        ("BOX", (0, 0), (-1, -1), 0.6, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9f6")]),
    ]))
    return table


def data_table(rows, styles, head=("Wert", "Daten")):
    return key_table(list(rows), styles, head=head)


def compat_table(rows, styles):
    data = [[Paragraph("Plattform", styles["cellb"]),
             Paragraph("Geht?", styles["cellb"]),
             Paragraph("Wie / warum", styles["cellb"])]]
    for platform, ok, note in rows:
        data.append([Paragraph(platform, styles["cell"]),
                     Paragraph(ok, styles["cell"]),
                     Paragraph(note, styles["cell"])])
    widths = [36 * mm, 20 * mm, PAGE_W - 2 * MARGIN - 56 * mm]
    table = Table(data, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, GREEN),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cdd4cf")),
        ("BOX", (0, 0), (-1, -1), 0.6, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR", (1, 1), (1, -1), DARK),
    ]))
    return table


# --------------------------------------------------------------------------
# document template with header / footer
# --------------------------------------------------------------------------
class Manual(BaseDocTemplate):
    def __init__(self, path, title):
        BaseDocTemplate.__init__(self, path, pagesize=A4,
                                 leftMargin=MARGIN, rightMargin=MARGIN,
                                 topMargin=16 * mm, bottomMargin=16 * mm,
                                 title=title, author="Arena.ai Agent Mode",
                                 subject="FS25 Mod Handbuch")
        self.doc_title = title
        frame = Frame(MARGIN, 16 * mm, PAGE_W - 2 * MARGIN,
                      PAGE_H - 32 * mm, id="body")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._blank),
            PageTemplate(id="page", frames=[frame], onPage=self._decorate),
        ])

    def _blank(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GREEN)
        canvas.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(GREEN)
        canvas.rect(0, 0, PAGE_W, 5 * mm, stroke=0, fill=1)
        canvas.restoreState()

    def _decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(GREEN)
        canvas.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN, PAGE_H - 6.2 * mm, self.doc_title)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 6.2 * mm, "FS25 Handbuch")
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, "Seite %d" % (doc.page - 1))
        canvas.setStrokeColor(colors.HexColor("#cdd4cf"))
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.restoreState()


# --------------------------------------------------------------------------
# the content
# --------------------------------------------------------------------------
SHARED_INSTALL = (
    "ZIP nach <b>Dokumente/My Games/FarmingSimulator2025/mods/</b> entpacken "
    "(die ZIP bleibt zu, der Ordner darin heißt wie der Mod). Im Spiel unter "
    "<b>Mods</b> aktivieren und den Spielstand neu laden. Auf der Konsole geht "
    "das nur über den ModHub – selbst kopierte Mods werden dort nicht geladen."
)

MODS = [
    {
        "file": "UFO2000",
        "title": "UFO 2000",
        "subtitle": "Die schwebende Untertasse mit Traktorstrahl",
        "version": "1.1.0.0",
        "price": "42.000 €",
        "category": "Autos",
        "hero": "ufo_hero.png",
        "gallery": [("ufo_beam.png", "Traktorstrahl mit Bodenring"),
                    ("ufo_cockpit.png", "Cockpit unter der Glaskuppel")],
        "reference": [],
        "intro": [
            "Das UFO 2000 ist der Kern der ganzen Reihe: eine kleine Untertasse "
            "mit hoher Glaskuppel, drei einfahrbaren Landebeinen und einem "
            "Traktorstrahl, der jedes Feldstück ohne Anbaugerät bearbeitet.",
            "Es schwebt auf Knopfdruck, bleibt von allein in der Luft stehen und "
            "lässt sich wie ein Traktor fahren – mit WASD, Gamepad oder Joystick. "
            "Unter der Kuppel sitzt dein eigener Charakter auf einem Sitz, vor "
            "ihm eine geschwungene Konsole mit Moduswahlrad, Schaltern und "
            "Leuchtenkranz.",
            "Acht Strahl-Modi übernehmen die Arbeit: plattdrücken (Kornkreise), "
            "ernten, grubbern, pflügen, säen, düngen, aufnehmen und abladen. "
            "Jeder Modus hat seine eigene Strahlfarbe, sein eigenes Summen und "
            "seine eigene Anzeige im Cockpit.",
        ],
        "keys": [
            ("<b>V</b>", "Abheben / Landen – die Beine klappen ein oder aus."),
            ("<b>Bild ↑ / Bild ↓</b> oder Joystick-Achse",
             "Höhe stufenlos von 1,1 m bis 120 m."),
            ("<b>W / S / A / D</b>", "Vorwärts, rückwärts (bis ca. 31 km/h), drehen."),
            ("<b>Z</b>", "Traktorstrahl an/aus – der Strahl macht die Arbeit."),
            ("<b>K</b>", "Nächster Strahl-Modus (acht Stück im Kreis)."),
            ("<b>J / L</b>", "Strahl enger / weiter (0,5 m bis 16 m)."),
            ("<b>M</b>", "Bordmenü: Muster, Modi, Tank – auch mit der Maus bedienbar."),
            ("<b>U</b>", "Abladen an/aus."),
            ("<b>I</b>", "Korntank unendlich an/aus."),
            ("<b>Hupe / C</b>", "Alien-Melodie als Gruß, Kamera innen/außen."),
        ],
        "keys_note": "Alle Belegungen liegen unter <i>Optionen → Steuerung</i> "
                     "(Suche nach „UFO“). Die Achse für die Höhe ist auf jedem "
                     "Gamepad und Joystick belegt – es gibt keine Sondertaste.",
        "tips": [
            "Der Strahl endet immer genau am Boden: sein halber Öffnungswinkel "
            "ist 34°, der Radius ergibt sich also aus der Flughöhe (10 m Höhe ≈ "
            "6,7 m Radius). Wer größere Kornkreise will, fliegt einfach höher.",
            "Der Tank läuft nicht über: der Laderaum fasst 5.000.000 l und nimmt "
            "Getreide, Häckselgut, Heu, Silage, Dünger, Saatgut, Wasser und Milch "
            "an. Mit <b>I</b> ist auch die Grenze abgeschaltet.",
            "Beim Aufnehmen mindestens 1,8 m Abstand zum Anhänger halten, sonst "
            "kollidiert das Schiff mit dem Auflieger.",
            "Start und Landung drücken einen Fleck von ca. 3,8 m in die Frucht. "
            "Das ist gewollt – auf Hof, Straße und Wiese passiert nichts.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Mod-Ordner, wie oben beschrieben."),
            ("Konsole (Xbox/PS5)", "Nein",
             "Der Mod enthält ein eigenes Lua-Skript; auf Konsolen sind nur "
             "ModHub-Mods ohne Skripte erlaubt. Für Konsole gibt es das UFO 2500."),
            ("Multiplayer", "Ja",
             "Der Server rechnet Flug, Tank und Feldarbeit; Mitspieler sehen "
             "Strahl, Farbe und Tankstand synchron."),
            ("Dedicated Server", "Ja", "Mod auf Server und Clients in derselben Version."),
        ],
        "specs": [
            ("Modell", "12.700 Dreiecke, 12 Shapes, 6 Lichter, 2 Kameras"),
            ("Maße", "ca. 4,7 m Durchmesser, 3,15 m hoch"),
            ("Korntank / Laderaum", "virtuell, 5.000.000 l"),
            ("Höhe", "1,1 m bis 120 m über Grund"),
            ("Sounds", "7 eigene OGG-Dateien (Schweben, Start/Stopp, Strahl, Hupe)"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "Alien",
        "title": "Alien — Maskottchen & Crew",
        "subtitle": "Drei Figuren aus der UFO-Werkstatt",
        "version": "1.3.0.0",
        "price": "750 / 1.200 / 1.500 €",
        "category": "Platzierbare Objekte",
        "hero": "alien_mascot.png",
        "gallery": [("alien_mascot_face.png", "Das Gesicht: große Mandelaugen, Fühler, rote Wangen"),
                    ("alien_zorp.png", "Captain Zorp im Fluganzug")],
        "reference": [("zorp_concept.jpg", "Vorlage: Captain Zorp")],
        "intro": [
            "Drei Figuren zum Aufstellen: das kleine Maskottchen, der Große mit "
            "den geringelten Socken und Captain Zorp im Fluganzug mit Helm und "
            "hochgeschobener Brille.",
            "Die Modelle sind in dieser Fassung komplett neu modelliert: der "
            "Schädel ist keine Kugel mehr, sondern eine verformte Eiform mit "
            "Kiefer, Brauenwulst und Wangen; die Augen bestehen aus vier "
            "ineinandergeschachtelten Kugelkappen (Lederhaut, Iris, Pupille, "
            "Lichtpunkte) und sitzen unter echten Lidbögen. Hände, Finger, "
            "Socken mit Bund und Fersenkappe, Helm mit Ohrmuscheln, Brillenglanz "
            "und ein geprägtes „ZORP“-Namensschild sind eigene Bauteile.",
            "Zorp ist dieselbe Figur, die im UFO 01 Crop Harvester im Cockpit "
            "sitzt – dort verschwindet er, sobald du selbst einsteigst.",
        ],
        "keys": [
            ("Shop → Platzierbare Objekte", "Figur kaufen und aufstellen."),
            ("Aufstellen", "Mit der Maus frei drehen, linke Maustaste setzt ab."),
            ("Wieder aufnehmen", "Figur antippen und in den Shop zurücklegen."),
        ],
        "keys_note": "Die Figuren steuern nichts – sie sind Deko. Für das "
                     "Cockpit bringt Captain Zorp kein eigenes Skript mit.",
        "tips": [
            "Die Figuren sind bewusst klein (ca. 1,1 bis 1,5 m), sie passen auf "
            "Hofmauern, vor den Hühnerstall oder unter die UFO-Kuppel.",
            "Auf Konsole funktionieren sie, weil es reine Platzierungen ohne "
            "Skript sind – dieselbe Technik wie ein Gartenzwerg.",
            "Wer die Figuren in einen Multiplayer-Spielstand stellt: die "
            "Platzierung ist Teil des Spielstands und damit für alle sichtbar.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Platzierbar, kein Skript."),
            ("Konsole (Xbox/PS5)", "Ja",
             "Rein statische Platzierung ohne Lua – gute Chance im ModHub-Test."),
            ("Multiplayer", "Ja", "Position und Drehung stehen im Spielstand."),
            ("Dedicated Server", "Ja", "Keine Serverlogik nötig."),
        ],
        "specs": [
            ("Figuren", "Maskottchen, der Große, Captain Zorp"),
            ("Dreiecke", "ca. 25.000 / 26.000 / 34.000"),
            ("Preise", "750 € / 1.200 € / 1.500 €"),
            ("Besonderheit", "Zorp ist auch der Pilot im UFO 01"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "UFO2500",
        "title": "UFO 2500 (Konsolen-Edition)",
        "subtitle": "20 m hoch, ohne eine Zeile Lua",
        "version": "1.0.0.0",
        "price": "58.000 €",
        "category": "Autos",
        "hero": "ufo2500_hero.png",
        "gallery": [("ufo2500_concept.png", "Schnitt: Rumpf auf 18,83 m, Cockpit auf 20 m"),
                    ("ufo2500_landed.png", "Gelandet bei 0,95 m")],
        "reference": [],
        "intro": [
            "Das UFO 2500 ist die Konsolen-Variante: dasselbe Schiff, aber ohne "
            "eigenes Skript. Es benutzt nur Grundspiel-Technik und darf deshalb "
            "theoretisch in den ModHub.",
            "Der Trick ist unsichtbare Physik: zwei breite Räder (0,70 m) stehen "
            "vorn und hinten am Boden, zwei winzige Stützräder verhindern das "
            "Umkippen – das eigentliche Schiff ist als Modell 18,83 m darüber "
            "montiert. Der Fahrzeug-Ursprung bleibt am Boden, also funktionieren "
            "Physik, Kamera, Ein- und Aussteigen, Shop und Spawn wie bei einem "
            "Traktor.",
            "Gelandet wird über eine i3d-Animation, die das Grundspiel abspielt: "
            "Taste <b>X</b> fährt das Cockpit in 4,5 Sekunden von 20,00 m auf "
            "0,95 m herunter, die Beine klappen aus.",
        ],
        "keys": [
            ("<b>X</b>", "Landung starten / wieder aufsteigen (Grundspiel-„foldable“)."),
            ("<b>W / S / A / D</b>", "Fahren und drehen – die Physik läuft über die Räder."),
            ("<b>L</b>", "Arbeitslicht: lässt den Strahl am Boden grün leuchten."),
            ("<b>Rundumlicht</b>", "Die zwei Leuchten im Cockpit blinken."),
            ("Shop → Radkonfiguration",
             "Pinselbreite wählen: Stift 0,5 m, Ring 1,5 m, Standard 3,5 m, "
             "Mähdrescher 7,5 m."),
        ],
        "keys_note": "Kornkreise werden hier <b>durch Fahren</b> gezeichnet: "
                     "Kreis = einmal im Kreis fahren, Stern = gerade Bahnen. "
                     "Der Bodenring zeigt die eingestellte Pinselbreite.",
        "tips": [
            "Auf Konsole fehlen Höhensteuerung im Flug, Muster-Menü, HUD und "
            "Startspuren – der Strahl ist feste Geometrie und immer an.",
            "„Mähdrescher“ heißt hier: die Frucht wird zerstört (Ertrag weg, "
            "Pflanzen platt), geerntet wird nichts. Für richtiges Ernten gibt es "
            "das UFO 4500 bzw. UFO 01.",
            "Damit der Mod den Konsolentest übersteht, bleibt er ohne "
            "`scripts/`-Ordner, ohne `<actions>` und mit der Grundspiel-Marke "
            "Lizard.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Läuft auch am PC, dann ohne Strahlsteuerung."),
            ("Konsole (Xbox/PS5)", "Ja",
             "Kein Lua, keine eigenen Aktionen, Grundspiel-Marke – gute Chance "
             "im ModHub-Test (Einreichen musst du selbst)."),
            ("Multiplayer", "Ja", "Alles Grundspiel-Logik, keine eigenen Events."),
            ("Dedicated Server", "Ja", "Keine Serverlogik nötig."),
        ],
        "specs": [
            ("Modell", "15.200 Dreiecke, dieselbe Untertasse wie UFO 2000"),
            ("Höhe", "Cockpit 20,00 m, Rumpf 18,83 m, gelandet 0,95 m"),
            ("Räder", "19 unsichtbare Räder (2 breite, 2 Stützen, 15 Pinsel)"),
            ("Landung", "i3d-Animation über `foldable`, 4,5 s"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "UFO4500",
        "title": "UFO 4500 Mutterschiff",
        "subtitle": "Ernten, grubbern, säen, Kornkreise – nur mit dem Strahl",
        "version": "2.0.0.0",
        "price": "185.000 €",
        "category": "Autos",
        "hero": "ufo4500_hero.png",
        "gallery": [("ufo4500_beam.png", "Strahl mit Wanderringen und Kern"),
                    ("ufo4500_below.png", "Unterseite: Emitterkranz und Turbinen")],
        "reference": [],
        "intro": [
            "Das UFO 4500 ist die große Schwester der UFO 01: anderthalbmal so "
            "groß, 300 PS, vier Hover-Turbinen am Rumpf und ein breiter "
            "Emitterkranz unter dem Bauch.",
            "Wichtig: es gibt <b>kein Schneidwerk und keine Anbaugeräte</b> mehr. "
            "Das Schiff arbeitet ausschließlich mit dem Traktorstrahl – kein "
            "Attacher-Joint, kein Korntank-Rohr, keine WorkArea. Ein Shop-Artikel, "
            "ein Modell, ein Fahrzeug.",
            "Der Strahl ist animiert: ein weißer Kern, eine drehende Helix und "
            "vier Ringe, die von der Bordwand zum Boden wandern. Dazu pulsiert "
            "die Lichtfarbe im Takt des Modus.",
        ],
        "keys": [
            ("<b>V</b>", "Abheben / Landen."),
            ("<b>Bild ↑ / ↓</b> oder Joystick-Achse", "Höhe 3 m bis 30 m."),
            ("<b>K</b>", "Strahl-Modus weiter (acht Funktionen)."),
            ("<b>J / L</b>", "Strahlbreite 2 m bis 30 m."),
            ("<b>Z</b>", "Strahl an/aus."),
            ("<b>M</b>", "Muster-Menü für die Kornkreise."),
            ("<b>U</b>", "Abladen über Anhänger oder Abkippstelle."),
            ("<b>I</b>", "Korntank endlos (2.000.000 l sind Standard)."),
        ],
        "keys_note": "Die Tasten heißen intern <i>ufo4500_*</i>, damit UFO 2000, "
                     "UFO 01 und UFO 4500 gleichzeitig installiert sein können. "
                     "Umgelegt wird alles unter <i>Optionen → Steuerung</i>.",
        "tips": [
            "Ernten: Modus <b>GRÜN</b> wählen, auf 3 bis 6 m gehen, Strahl an – "
            "das Korn geht ohne Verlust in den Tank, das Feld ist dahinter ab.",
            "Kornkreise: Modus <b>GELB</b> für die neun Presets, oder der freie "
            "1-m-Stift, mit dem du beim Fliegen selbst zeichnest.",
            "Ein Feld am Stück geht ohne Abtanken: 2.000.000 l Tank, mit <b>I</b> "
            "sogar endlos.",
            "Der Build prüft beim Bauen, dass im XML kein `<attacherJoints>`, "
            "kein `<combine>`, kein `<pipe>` und keine `workArea` steht – das "
            "Schiff kann also gar kein Anbaugerät bekommen.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Eigenes Lua-Skript (`scripts/UFO4500.lua`)."),
            ("Konsole (Xbox/PS5)", "Nein",
             "Skript-Mod. Wer auf Konsole fliegen will, nimmt das UFO 2500."),
            ("Multiplayer", "Ja",
             "Server-autoritativ: Feldarbeit, Tank und Modus laufen auf dem "
             "Server, alle sehen denselben Strahl."),
            ("Parallel zu UFO 2000 / UFO 01", "Ja",
             "Eigene Klasse, eigene Aktionen, eigene l10n-Schlüssel."),
        ],
        "specs": [
            ("Modell", "56.000 Dreiecke, 82 Shapes, 4 Hover-Turbinen"),
            ("Maße", "ca. 6,5 m Durchmesser (1,3 × UFO 01)"),
            ("Strahl", "2–30 m Breite, Arbeitshöhe 3–30 m, 8 Funktionen"),
            ("Korntank", "2.000.000 l (endlos mit Taste I)"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "CropHarvester",
        "title": "UFO 01 Crop Harvester",
        "subtitle": "Die Erntemaschine aus dem Blaupausen-Set",
        "version": "1.2.0.0",
        "price": "96.000 €",
        "category": "Autos",
        "hero": "cropharvester_hero.png",
        "gallery": [("cropharvester_beam.png", "Erntestrahl über dem Feld"),
                    ("cropharvester_pilot.png", "Captain Zorp hinter den Hebeln")],
        "reference": [("zorp_concept.jpg", "Vorlage: Cockpit und Pilot")],
        "intro": [
            "Die UFO 01 ist die kompakte Erntemaschine aus der Vorlage: eine "
            "Untertasse mit einer einzigen großen Glaskuppel, in der Captain Zorp "
            "ziemlich eng hinter den Hebeln sitzt. Kein Mähwerk, kein Anbaugerät – "
            "alle Feldarbeit macht der Strahl unter dem Bauch.",
            "Der Rumpf ist glatt und ohne Halterungen modelliert: keine "
            "Anbauplatten, keine Namensschilder, nichts, was nach Werkzeug "
            "aussieht. Was zählt, ist die Kuppel, das Cockpit und der Strahl.",
            "Die Kuppel ist ein echtes Glasmodell mit Sitz, Konsole, "
            "Moduswahlrad, Hologramm-Ring und dem Piloten, der bei der Fahrt "
            "leicht mitwippt und verschwindet, sobald du selbst einsteigst.",
        ],
        "keys": [
            ("<b>V</b>", "Abheben / Landen."),
            ("<b>Bild ↑ / ↓</b> oder Joystick-Achse", "Höhe 2 m bis 15 m."),
            ("<b>Z</b>", "Strahl an/aus."),
            ("<b>K</b>", "Nächster Modus (Plattdrücken, Ernten, Grubbern, Pflügen, "
                        "Säen, Düngen, Aufnehmen, Abladen)."),
            ("<b>J / L</b>", "Strahlbreite 0,5 m bis 15 m (im Sä-Modus: Saatgut)."),
            ("<b>M</b>", "Kornkreis-Menü mit neun Mustern und dem Handstift."),
            ("<b>U</b>", "Abladen."),
            ("<b>I</b>", "Korntank endlos."),
        ],
        "keys_note": "Die Belegung ist identisch zur UFO 2000, nur mit eigenen "
                     "internen Namen (`crop_*`), damit beide Mods nebeneinander "
                     "laufen.",
        "tips": [
            "Ernten ohne Verlust: im Modus <b>Ernten</b> landet das Korn direkt "
            "im virtuellen Tank (1.000.000 l) – nichts bleibt auf dem Feld liegen.",
            "Kornkreise drücken den Bestand platt, ohne ihn zu ernten: genau der "
            "Effekt, den auch ein Reifen im Grundspiel auslöst.",
            "Der Handstift zeichnet mit ca. 50 cm Durchmesser – langsam fliegen "
            "gibt feine Linien, schneller grobe Striche.",
            "Captain Zorp ist Deko: sobald du einsteigst, wird er ausgeblendet.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Eigenes Lua-Skript (`scripts/CropHarvester.lua`)."),
            ("Konsole (Xbox/PS5)", "Nein", "Skript-Mod, nur PC."),
            ("Multiplayer", "Ja", "Server rechnet Ernte, Tank und Muster."),
            ("Neben UFO 2000 / UFO 4500", "Ja", "Eigene Klasse und Aktionen."),
        ],
        "specs": [
            ("Modell", "42.900 Dreiecke, 74 Shapes"),
            ("Kuppel", "1,3 m Radius, Sitz bei 1,86 m"),
            ("Strahl", "0,5–15 m Breite, 8 Modi, 5 Farben"),
            ("Korntank", "1.000.000 l"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "BabaJaga",
        "title": "Baba Jagas Hühnerhütte",
        "subtitle": "Ein Hühnerstall auf einem Vogelbein",
        "version": "1.1.0.0",
        "price": "18.500 € (12 €/Tag)",
        "category": "Tiergehege → Hühner",
        "hero": "babajaga_hero.png",
        "gallery": [("babajaga_leg.png", "Das Bein: Federrock, Schuppenschaft, Zehen")],
        "reference": [],
        "intro": [
            "Eine Blockhütte auf einem riesigen Hühnerbein: Schindeldach, "
            "krummer Schornstein, Laterne, zwei Futertröge, ein bemaltes Schild "
            "„BABA JAGA“ und ein eingezäunter Hühnerhof.",
            "Das Bein ist ein richtiges Vogelbein: Federrock aus fünf Lagen "
            "langer Federn, geschuppter Schaft mit überlappenden Platten, dickes "
            "Sprunggelenk, drei Zehen nach vorn und eine nach hinten – jede Zehe "
            "ein durchgehendes Rohr mit einer Kralle, die im Boden steckt.",
            "Die Hütte ist ein ganz normaler Hühnerstall des Grundspiels: "
            "dieselbe Technik wie der gekaufte Stall, nur mit anderem Modell.",
        ],
        "keys": [
            ("Shop → Tiergehege", "Hütte kaufen und aufstellen; das Gelände wird "
                                  "geebnet und eingesät."),
            ("Weizen in den Trog", "Die Tröge füllen sich sichtbar, die Hühner "
                                   "laufen automatisch hin."),
            ("Hühner beim Tierhändler", "Kaufen und in den Hof setzen."),
            ("Eier", "Am Palettenplatz abholen – bis zu sechs Paletten."),
        ],
        "keys_note": "Es gibt keine Sondertasten: die Hütte ist eine reine "
                     "Platzierung mit Grundspiel-Logik.",
        "tips": [
            "Die Hütte <b>läuft nicht</b> durch die Gegend. Ein animiertes Bein "
            "wäre ein eigenes Skript und damit auf Konsole nicht erlaubt.",
            "Der Zaun ist kein Zusatzobjekt, sondern ein Kontursatz im Modell – "
            "aus den vier Eckpunkten baut das Spiel das Laufnetz selbst.",
            "Futter nur in den Trog vor der Hütte kippen, nicht in den Hof: die "
            "Reichweite des Triggers endet am Trog.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Placeable nach Grundspiel-Vorbild."),
            ("Konsole (Xbox/PS5)", "Ja",
             "Kein Lua, keine eigenen Aktionen, Marke Lizard – der Mod ist genau "
             "dafür gebaut."),
            ("Multiplayer", "Ja", "Hühner, Futter und Eier sind Spielstand-Daten."),
            ("Dedicated Server", "Ja", "Keine Serverlogik nötig."),
        ],
        "specs": [
            ("Preis / Unterhalt", "18.500 € / 12 € pro Tag"),
            ("Kapazität", "20 Hühner (bis 60 ausbaubar)"),
            ("Futter", "2.500 l in zwei Trögen"),
            ("Eier", "bis 6 Paletten"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "Disco",
        "title": "Hofdisco",
        "subtitle": "Neonlicht, Spiegelkugel und gemeinsame Musik",
        "version": "1.0.0.0",
        "price": "32.000 € (25 €/Tag)",
        "category": "Platzierbare Objekte",
        "hero": "disco_hero.png",
        "gallery": [("disco_inside.png", "Innen: Tanzfläche, DJ-Pult, Boxentürme")],
        "reference": [],
        "intro": [
            "Eine aufstellbare Disco-Halle mit Neonlicht, drehender Spiegelkugel, "
            "DJ-Pult, Theke, Tischen und Schachbrett-Tanzfläche – vor allem aber "
            "mit gemeinsamer Musik: alle, die drin sind, hören dasselbe Stück ab "
            "derselben Sekunde.",
            "Die Musik ist kein Stream, sondern sechs eigene OGG-Dateien im Mod. "
            "Abgespielt werden sie als 3D-Sound an der Spiegelkugel: drinnen laut, "
            "draußen leise.",
        ],
        "keys": [
            ("<b>N</b> (Gamepad Y)", "Nächster Titel."),
            ("<b>M</b> (Gamepad X)", "Musik an/aus."),
            ("Am DJ-Pult", "Jeder Spieler darf weiterschalten – der Server "
                           "entscheidet, was läuft."),
        ],
        "keys_note": "Beide Tasten sind im Spiel frei umbelegbar.",
        "tips": [
            "Drückt jemand <b>N</b>, schickt sein Spiel nur einen Wunsch an den "
            "Server. Der Server wählt Titel und Startzeit („jetzt + 1,5 s“) und "
            "schickt beides an alle – deshalb läuft der Song überall im Takt.",
            "Neonblinken und Kugeldrehung hängen an derselben Netzwerkzeit, nicht "
            "an einem lokalen Timer.",
            "Eigene Titel: OGG-Datei nach `sounds/` legen und eine Zeile in "
            "`sounds/discoSounds.xml` ergänzen (bis 8 Stücke). `bpm` steuert das "
            "Blinken.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Eigenes Lua-Skript (`scripts/Disco.lua`)."),
            ("Konsole (Xbox/PS5)", "Nein", "Skript-Mod."),
            ("Multiplayer", "Ja",
             "Server-autoritativ, Dirty-Flag-Sync; Nachzügler steigen mittendrin ein."),
            ("Dedicated Server", "Ja", "Titel und Startzeit kommen vom Server."),
        ],
        "specs": [
            ("Preis / Unterhalt", "32.000 € / 25 € pro Tag"),
            ("Musik", "6 eigene OGG-Stücke (Disco, Techno, Chill, Country, Grusel, Western)"),
            ("Modell", "5.100 Dreiecke, 18 Shapes, 3 Lichtgruppen"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "Autokino",
        "title": "Autokino",
        "subtitle": "13-m-Leinwand mit drei echten Zeichentrickfilmen",
        "version": "1.0.0.0",
        "price": "48.000 € (35 €/Tag)",
        "category": "Platzierbare Objekte",
        "hero": "autokino_hero.png",
        "gallery": [("autokino_screen.png", "Die Leinwand mit laufendem Film")],
        "reference": [],
        "intro": [
            "13-m-Leinwand auf Stahlrahmen, Vorführhäuschen mit Projektor, "
            "24 Parkbuchten mit Radstoppern, Lampenmasten und ein Neonschild.",
            "Drei kurze Filme laufen wirklich: „Der kleine Traktor“, „UFO über "
            "dem Hof“ und „Der Alien“ – je 16 Einzelbilder, 6 Bilder pro Sekunde, "
            "Endlosschleife, mit eigenem Soundtrack.",
        ],
        "keys": [
            ("<b>F</b> (Gamepad Y)", "Nächster Film."),
            ("<b>P</b> (Gamepad X)", "Film an/aus."),
        ],
        "keys_note": "Alles im Spiel frei umbelegbar.",
        "tips": [
            "Filme sind Bildersequenzen, keine Videos: FS25 kann aus Lua keine "
            "Videodatei dekodieren. Das Skript legt 16 DDS-Texturen im "
            "Sekundentakt auf die Leinwand – dieselbe Technik wie Werbeplakate "
            "im Grundspiel.",
            "Die Bildnummer wird aus der Netzwerkzeit berechnet, nicht lokal "
            "gezählt – deshalb sehen alle dasselbe Bild, auch wer später kommt.",
            "Eigene Filme: `key_00.dds` bis `key_15.dds` nach `textures/film/` "
            "und eine `<film .../>`-Zeile in `sounds/autokinoSounds.xml` (bis 6 "
            "Filme, 32 Bilder, 16:9, z. B. 320×180).",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Eigenes Lua-Skript (`scripts/Autokino.lua`)."),
            ("Konsole (Xbox/PS5)", "Nein", "Skript-Mod."),
            ("Multiplayer", "Ja", "Bildnummer aus der Netzwerkzeit, Sound mit "
                                  "derselben Startzeit."),
            ("Dedicated Server", "Ja", "Server setzt Film und Startzeit."),
        ],
        "specs": [
            ("Preis / Unterhalt", "48.000 € / 35 € pro Tag"),
            ("Filme", "3 × 16 Bilder, 6 Bilder/s"),
            ("Modell", "3.200 Dreiecke, 13 Shapes, 24 Parkbuchten"),
            ("Sprachen", "Deutsch, Englisch"),
        ],
    },
    {
        "file": "Distillery",
        "title": "Distillery Leipzig",
        "subtitle": "Der Club nach dem Grundriss – innen und außen",
        "version": "1.1.0.0",
        "price": "185.000 € (180 €/Tag)",
        "category": "Platzierbare Objekte",
        "hero": "distillery_hero.png",
        "gallery": [("distillery_floor.png", "Hauptfloor mit PA-Türmen und Titelliste"),
                    ("distillery_garden.png", "Biergarten")],
        "reference": [("distillery_floorplan.jpg", "Vorlage: Grundriss"),
                      ("distillery_building.jpg", "Vorlage: Gebäude")],
        "intro": [
            "Nachgebaut nach dem Grundriss aus der Vorlage – innen und außen "
            "getrennt: eine alte Backsteinfabrik mit Turm und Satteldach, "
            "Hauptfloor 20 × 15 m, Bar-Flügel 15 × 15 m und ein Außenbereich "
            "(Garten) 14 × 18 m.",
            "Über dem Eingang steht „DISTILLERY / LEIPZIG“ als Leuchtschrift, an "
            "der Fassade hängen Graffiti, draußen liegt Kopfsteinpflaster.",
            "Drinnen: DJ-Pult auf einer Bühne, vier große PA-Türme, Traversen mit "
            "acht Moving Heads, Spiegelkugel, Blüten-Decal auf der Tanzfläche, "
            "Hauptbar, VIP-Empore, Foyer, Sanitär, Lager und Feuerleiter. "
            "Draußen: Barhütte „BAR 01“, acht Bistro-Sitzgruppen, zwei überdachte "
            "Bereiche, zwei Chill-out-Ecken, Steinweg und Lichterketten.",
        ],
        "keys": [
            ("<b>N</b> (Gamepad Y)", "Nächster Titel (im Radio-Modus: nächster Sender)."),
            ("<b>M</b> (Gamepad X)", "Musik an/aus."),
            ("<b>R</b> (Gamepad L3)", "Quelle umschalten: Club-PA ↔ Internetradio."),
            ("Am DJ-Pult", "Titelliste mit Marker; jeder Spieler darf umschalten."),
        ],
        "keys_note": "Am Set-List-Board zeigen zwei Lampen die Quelle: "
                     "<b>amber</b> = Club-PA (synchron für alle), "
                     "<b>cyan</b> = eigenes Radio.",
        "tips": [
            "Synchron ist die eingebaute Playlist: der Server wählt Titel und "
            "Startzeit, jeder PC startet die OGG-Datei passend dazu.",
            "Externe Streams (SoundCloud, Internetradio) laufen nur über das "
            "Spielradio in der Profildatei `streamingInternetRadios.xml` – und "
            "dann nur für dich, nicht für die ganze Halle. Anleitung: "
            "`docs/streaming_radio.md`.",
            "MP3 vorher in OGG umwandeln, sonst lädt das Spiel den Titel nicht.",
            "Neonblinken und der Marker am Board hängen an der Netzwerkzeit – "
            "deshalb sieht jeder, was gerade läuft.",
        ],
        "compat": [
            ("PC (Windows)", "Ja", "Eigenes Lua-Skript (`scripts/Distillery.lua`)."),
            ("Konsole (Xbox/PS5)", "Nein", "Skript-Mod."),
            ("Multiplayer", "Ja",
             "Server verwaltet Titelliste und Startzeit; Nachzügler steigen "
             "mittendrin ein."),
            ("Internetradio", "Ja, lokal",
             "Über die Profildatei des Spiels; gilt pro Spieler, nicht für die Halle."),
        ],
        "specs": [
            ("Preis / Unterhalt", "185.000 € / 180 € pro Tag"),
            ("Flächen", "Hauptfloor 20 × 15 m, Flügel 15 × 15 m, Garten 14 × 18 m"),
            ("Musik", "6 Club-Tracks (Techno, Deep House, Hard, Minimal, Acid, Closing)"),
            ("Höhe", "Turm ca. 18,5 m"),
        ],
    },
]


# --------------------------------------------------------------------------
# rendering one manual
# --------------------------------------------------------------------------
def build_manual(mod, styles):
    path = os.path.join(OUT, "FS25_%s.pdf" % mod["file"])
    doc = Manual(path, "FS25 %s" % mod["title"])
    story = []

    # --- cover ------------------------------------------------------------
    story.append(Paragraph(mod["title"], styles["title"]))
    story.append(Paragraph(mod["subtitle"], styles["subtitle"]))
    meta = ("Version %s &nbsp;·&nbsp; Preis %s &nbsp;·&nbsp; %s"
            % (mod["version"], mod["price"], mod["category"]))
    story.append(Paragraph(meta, styles["cover_meta"]))
    story.append(Spacer(1, 6 * mm))
    story.extend(image(os.path.join(RENDERS, mod["hero"]), 150, styles["caption"],
                       "So sieht der Mod im Spiel aus (eigener 3D-Render)."))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(SHARED_INSTALL, styles["body"]))
    story.append(PageBreak())

    # --- what is it -------------------------------------------------------
    story.append(Paragraph("1. Was ist das?", styles["h1"]))
    for text in mod["intro"]:
        story.append(Paragraph(text, styles["body"]))

    if mod["gallery"]:
        story.append(Spacer(1, 2 * mm))
        story.append(two_up([(os.path.join(RENDERS, name), caption)
                             for name, caption in mod["gallery"]], styles["caption"]))

    glance = mod["specs"][:3]
    if glance:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Auf einen Blick", styles["h2"]))
        story.append(data_table(glance, styles))

    if mod["reference"]:
        story.append(Paragraph("Vorlagen, nach denen gebaut wurde", styles["h2"]))
        story.append(two_up([(os.path.join(REFERENCE, name), caption)
                             for name, caption in mod["reference"]], styles["caption"]))

    # --- controls ---------------------------------------------------------
    story.append(Spacer(1, 4 * mm))
    story.append(KeepTogether([Paragraph("2. Bedienung", styles["h1"]),
                               key_table(mod["keys"], styles)]))
    story.append(Spacer(1, 3 * mm))
    if mod.get("keys_note"):
        story.append(Paragraph(mod["keys_note"], styles["body"]))

    # --- tips -------------------------------------------------------------
    story.append(Paragraph("3. Worauf du achten solltest", styles["h1"]))
    for tip in mod["tips"]:
        story.append(Paragraph(tip, styles["bullet"], bulletText="•"))

    # --- compatibility ----------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("4. Kompatibilität", styles["h1"]))
    story.append(compat_table(mod["compat"], styles))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Grundsätzlich gilt für alle Mods dieser Reihe: Mods müssen auf PC und "
        "Konsole <b>dieselbe Version</b> haben, sonst verweigert der Server die "
        "Verbindung. Konsolen-Mods müssen über den ModHub eingereicht und "
        "freigegeben sein – selbst kopierte Dateien werden dort nicht geladen. "
        "Ein Spielstand mit Mods lässt sich nach dem Entfernen eines Mods "
        "meist weiter laden, aber was der Mod gebaut hat (Gebäude, UFO, Deko) "
        "verschwindet dabei.", styles["body"]))
    story.append(Paragraph(
        "Getestet wurde ohne laufendes Spiel: Modelle, XML und Lua werden von "
        "eigenen Prüfskripten im Repository kontrolliert (Struktur, Mappings, "
        "l10n-Schlüssel, Lua-Smoke-Tests). Ein Test im echten Spiel und im "
        "ModHub-TestRunner bleibt trotzdem sinnvoll.", styles["body"]))

    # --- data -------------------------------------------------------------
    story.append(Paragraph("5. Technische Daten", styles["h1"]))
    story.append(data_table(mod["specs"], styles))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Mod-Datei: <b>FS25_%s.zip</b> &nbsp;·&nbsp; Handbuch: diese PDF "
        "&nbsp;·&nbsp; Quellen und Bau-Skripte liegen im Repository unter "
        "<i>tools/</i>." % mod["file"], styles["caption"]))

    doc.build(story)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None,
                        help="nur diese Mod-Namen bauen")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    styles = make_styles()
    wanted = [m for m in MODS if not args.only or m["file"] in args.only]
    if not wanted:
        sys.exit("no matching mod - known: " + ", ".join(m["file"] for m in MODS))
    for mod in wanted:
        path = build_manual(mod, styles)
        print("  %-22s %6.1f kB" % (os.path.basename(path),
                                    os.path.getsize(path) / 1024.0))
    print("\n%d Handbuch/Handbücher in docs/pdf/" % len(wanted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
