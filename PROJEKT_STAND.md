# Projektstand: konjunktur.github.io

- **System:** Hugo mit Theme PaperMod, zweisprachig (DE unter `/`, EN unter `/en/`).
- **Konfiguration:** `config.yml` (`defaultContentLanguage: de`, `profileMode: enabled: false`, `MainSections: [""]`).
- **Startseiten:** `content/_index.md` (DE) und `content/_index.en.md` (EN) mit 6 Einzelgrafiken + 6-Panel-Übersicht aus `static/dashboard/`.
- **Daten- & Grafik-Skript:** `scripts/update_charts.py` (zieht Destatis-Tabellen `81000-0011` & `81000-0012` per Secrets `DESTATIS_USER`/`DESTATIS_PASS` dynamisch fortlaufend + Bundesbank SDMX-REST-API; erzeugt 7 DE- und 7 EN-PNGs in `static/dashboard/`).
- **Workflows:** `.github/workflows/update-dashboard.yml` (erzeugt Grafiken) & `.github/workflows/hugo.yml` (baut Webseite).
- **Geplante Erweiterung:** Neue Themen-Rubriken (z. B. Geldpolitik, Arbeitsmarkt, Außenwirtschaft) als eigene Ordner `content/<rubrik>/_index.md` + `_index.en.md` mit Menü-Eintrag in `config.yml`.
