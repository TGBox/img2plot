# img2plot 🖋️

## **Künstlerischer Vektor-Zeichenvorlagen Generator für Stiftplotter und Lasercutter**

`img2plot` verwandelt Fotos und Rastergrafiken in organische Strichzeichnungen im Stil menschlicher Skizzenbücher. Im Gegensatz zu herkömmlichen Plotterprogrammen, die Flächen mit einfachen Rastern, Punkten oder Wellen füllen, folgt `img2plot` natürlichen Bildgradienten und Kanten, unterstützt flüssige **Bézier-Kurven** und bietet einen integrierten **Schraffur-Modus (Hatching)** für dunkle Schattenbereiche.

---

## ✨ Neue Funktionen & Benutzeroberfläche (GUI)

- **🎨 Moderne Desktop-Benutzeroberfläche (PySide6 / Qt6)** mit Dark-Theme und Drag & Drop für Bilder.
- **👁️ Interaktive Live-Vorschau** mit flüssigem Zoomen (Mausrad) und Verschieben (Pan).
- **🔀 4 Ansichts-Modi**:
  1. *Plot-Ergebnis*: Reine Vektorzeichnung auf weißem, pergamentfarbenem oder dunklem Papier.
  2. *Original / Vorverarbeitung*: Graustufenbild mit CLAHE-Kontrastausgleich und Gauß-Filter.
  3. *Kanten / Sobel-Karte*: Kanten- und Gradientenwahrscheinlichkeitskarte.
  4. *Überlagerung (Overlay)*: Vektorkonturen direkt über dem Quellbild mit einstellbarer Deckkraft.
- **〰️ Organische Bézier-Kurven**: Statt starrer gerader Sehnen können Kantenverläufe als glatte kubische Bézier-Kurven gezeichnet werden, was einen lebendigen Handzeichnungs-Charakter erzeugt.
- **📐 Formfolgende Bézier-Schraffur (Hatching)**: Schattiert dunkle Bildbereiche nicht nur mit geraden Linien, sondern passt die Schraffuren über ein Vektorfeld den organischen Konturen und Kurven der Bildoberfläche an (mit einstellbarer Krümmungsstärke und subtilem Handzeichnungs-Wobble).
- **⚡ Plotter-Wegoptimierung (Nearest Neighbor TSP)**: Beschleunigte räumliche Sortierung (Spatial Bucket Grid) reduziert Leerfahrten (*Pen-Up*) drastisch und verkürzt Plotzeiten um bis zu 70 %.
- **⛶ Vollbild- & Fenstermodus**: Schnelles Umschalten zwischen Vollbild und Fenster per `F11` oder Menüleiste/Toolbar.
- **🎛️ Voreinstellungen (Presets)**: Integrierte Profile (*Standard*, *Feine Details*, *Künstlerische Skizze*, *Starke Konturen*, *Klassische Gravur*, *Schnell-Entwurf*) plus Speichern und Laden von JSON-Dateien.
- **💾 Export**: Saubere SVG-Dateien mit mm-Bemaßung, Stiftbreiten und Ebenen (*Contours* & *Hatching*) für Plotter (Silhouette Cameo, AxiDraw, Cricut etc.) sowie hochauflösender PNG-Export.

---

## 🚀 Installation & Start

Das Projekt nutzt modernstes Python Dependency Management via [`uv`](https://github.com/astral-sh/uv).

### 1. Repository klonen oder öffnen

```bash
cd img2plot
```

### 2. GUI starten

```bash
uv run img2plot
```

*oder direkt mit einem Bild:*

```bash
uv run img2plot readme-imgs/betta.jpg
```

---

## 💻 Headless / CLI-Modus

`img2plot` kann auch vollständig ohne grafische Oberfläche in Batch-Skripten oder Pipelines betrieben werden:

```bash
# Automatische Vektorisierung eines Bildes mit Preset
uv run img2plot eingabe.jpg -o ausgabe.svg --cli --preset "Künstlerische Skizze"

# Hilfe und alle Optionen anzeigen
uv run img2plot --help
```

---

## ⌨️ Tastaturkürzel in der GUI

| Shortcut | Aktion |
| :--- | :--- |
| **F11** / **Esc** | Vollbildmodus aktivieren / beenden |
| **Strg + O** | Bilddatei öffnen |
| **Strg + S** | Vektorgrafik als SVG exportieren |
| **Strg + Shift + S** | Zeichnung als PNG exportieren |
| **Strg + 0** | Vorschau an Fenstergröße anpassen |
| **Strg + 1** | Vorschau auf 100 % (Originalgröße) zoomen |
| **Mausrad** | Dynamischer Zoom am Mauszeiger |
| **Linke / Mittlere Maustaste gedrückt halten** | Bildausschnitt verschieben (Pan) |

---

## 🧪 Tests ausführen

```bash
uv run pytest -v
```

---

## 📄 Lizenz

MIT License - Siehe [LICENSE](LICENSE) für Details.
