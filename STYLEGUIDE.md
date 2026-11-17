# Projekt-Styleguide & Bauplan (konjunktur.github.io)

Dieser Leitfaden definiert den einheitlichen Standard für alle Skripte, Grafiken, Texte und Workflows auf `konjunktur.github.io`.

## 1. Verzeichnisstruktur pro Rubrik
- **Python-Skript:** `scripts/update_<rubrik>.py`
- **Grafiken (PNG & HTML):** `static/<rubrik>/<name>.png` und `<name>.html` (Englisch: `<name>_en.png` / `<name>_en.html`)
- **Inhaltsseiten:** `content/<rubrik>/_index.md` (DE) und `content/<rubrik>/_index.en.md` (EN)
- **GitHub Action:** `.github/workflows/update-<rubrik>.yml`

## 2. Visueller Standard (PNG & Plotly HTML)
- **Schriftart:** `DejaVu Sans`
- **Farben:**
  - Hauptreihe (Dunkelblau): `#1B3A6B`
  - Vergleichsreihe / Referenz (Bernstein): `#D97706`
  - Dritte Reihe / Positiv (Smaragdgrün): `#059669` (Balken: `#16A34A`)
  - Negativ / Warnung (Rot): `#DC2626`
  - Rezessionsbänder / Hintergrund: `#CBD5E1` (Alpha `0.35–0.45`), Plot-Fläche `#F8FAFC`, Gitterlinien `#E2E8F0`
- **Signatur & Quelle:**
  - Unten links: `Quelle: <Institution> | Stand: TT.MM.JJJJ` (EN: `Source: <Institution> | As of: YYYY-MM-DD`)
  - Unten rechts: `T.H.` (`#94A3B8`)
- **Sprachtrennung:**
  - Deutsch: Dezimalkomma (`separators=",."` in Plotly, Komma-Formatter in Matplotlib)
  - Englisch: Dezimalpunkt

## 3. Achsen- & Zahlenformatierung
- **Achsen & Referenz-Legenden (`fmt_clean`):** Glatte Zahlen ohne überflüssige Endnullen (`5` statt `5,00`, `1,5` statt `1,50`).
- **Endpunkt-Labels & Hover-Tooltips (`fmt_num`):** Einheitliche Nachkommastellen (1 oder 2 Stellen).
- **Y-Achsen-Puffer:** Mindestens **10–12 % der Spannweite** (`ymax - ymin`) nach oben und unten, damit keine Kurve den Rahmen berührt.
- **Endpunkt-Labels (`mark_ends`):** Mindestabstand `4,2 %` der Achsenspannweite mit symmetrischer Verschiebung nach oben und unten, damit Zahlen exakt auf Punkthöhe stehen und sich nie überlappen.


## 4. Hugo-Seiten & Markdown-Regeln
- **Keine `$`-Zeichen für Formeln:** Hugo rendert ohne LaTeX-Plugin `$`-Zeichen wörtlich. Stattdessen HTML nutzen (`<i>u</i>`, `<i>v</i>`, `<i>u</i>*`, `<i>R</i>²`).
- **Leerzeile nach `<iframe>`:** Nach jedem `</iframe>`-Tag zwingend eine Leerzeile lassen, damit Aufzählungspunkte (`- ...`) darunter korrekt als Liste gerendert werden.
- **Standard-Einbettung:**

    <iframe src="/<rubrik>/<name>.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

    - [In Vollbild anzeigen](/<rubrik>/<name>.png)

## 5. Datenquellen-Bausteine
- **Destatis GENESIS (`ffcsv`):** `https://destatis.de` (inkl. Job-Polling bei großen Tabellen, Secrets `DESTATIS_USER` / `DESTATIS_PASS`).
- **Deutsche Bundesbank (`csv` / `sdmx_csv`):** `https://bundesbank.de`

## 6. Reihenfolge beim Aktualisieren
1. Gewünschte Update-Workflows unter **Actions** -> **Run workflow** ausführen (erzeugt neue `.png`- und `.html`-Dateien).
2. Danach einmalig **Deploy Hugo site to Pages** -> **Run workflow** starten.
