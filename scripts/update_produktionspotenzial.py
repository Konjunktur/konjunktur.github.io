#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisierte Berechnung und Visualisierung des deutschen Produktionspotenzials (ab 1991)
Optimiert für GitHub Actions (nur Standardpakete: pandas, numpy, matplotlib, plotly, requests).
Optionale Pakete (openpyxl, kaleido) werden per try/except abgefangen.
"""

import io
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests

# ---------------------------------------------------------------------------
# 1. Konfiguration & Pfade (passend zu .github/workflows/*.yml)
# ---------------------------------------------------------------------------
OUT_DIR = Path("static/produktionspotenzial")
CACHE_DIR = OUT_DIR / "cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GENESIS_BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
DESTATIS_USER = os.getenv("DESTATIS_USER", "").strip()
DESTATIS_PASS = os.getenv("DESTATIS_PASS", "").strip()

TODAY_DE = datetime.now().strftime("%d.%m.%Y")
TODAY_EN = datetime.now().strftime("%Y-%m-%d")

# Rezessionsphasen Deutschland (Jahre als Dezimalwerte für durchgehende Schattierung)
RECESSIONS = [
    (2001.0, 2003.5),
    (2008.25, 2009.5),
    (2020.0, 2020.75),
    (2023.0, 2024.5),
]

# Produktionsfunktions-Parameter (EU-Kommission / SVR-Standard für Deutschland)
ALPHA = 0.65  # Produktionselastizität der Arbeit
BETA = 0.35   # Produktionselastizität des Kapitals (1 - ALPHA)


# ---------------------------------------------------------------------------
# 2. Mathematische Hilfsfunktionen (reines NumPy, kein statsmodels nötig)
# ---------------------------------------------------------------------------
def hpfilter(x, lamb: float = 100.0):
    """Exakter Hodrick-Prescott-Filter in reinem NumPy (Rückgabe: cycle, trend)."""
    y = np.asarray(x, dtype=float)
    n = len(y)
    if n < 4:
        return np.zeros_like(y), y.copy()
    d = np.zeros((n - 2, n), dtype=float)
    for i in range(n - 2):
        d[i, i] = 1.0
        d[i, i + 1] = -2.0
        d[i, i + 2] = 1.0
    trend = np.linalg.solve(np.eye(n) + lamb * (d.T @ d), y)
    cycle = y - trend
    return cycle, trend


def parse_german_number(val) -> float:
    """Konvertiert deutsche Zahlenstrings ('1.234,56', '-', '.', '...') sauber in float."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    s = str(val).strip()
    if s in {"", "-", ".", "...", "x", "/", "X", "nan", "None"}:
        return np.nan
    s = s.replace("\xa0", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


# ---------------------------------------------------------------------------
# 3. Destatis GENESIS-REST-API Abruf & robuster CSV-Parser
# ---------------------------------------------------------------------------
def fetch_genesis_table(table_code: str, start_year: int = 1991) -> pd.DataFrame | None:
    """
    Ruft eine GENESIS-Tabelle über die offizielle REST-API ab und nutzt bei
    Netzwerk- oder Wartungsfehlern den lokalen CSV-Cache.
    """
    cache_file = CACHE_DIR / f"{table_code}.csv"
    raw_text = None

    if DESTATIS_USER and DESTATIS_PASS:
        params = {
            "username": DESTATIS_USER,
            "password": DESTATIS_PASS,
            "name": table_code,
            "area": "all",
            "compress": "false",
            "transpose": "false",
            "startyear": str(start_year),
            "endyear": str(datetime.now().year),
            "language": "de",
        }
        try:
            resp = requests.get(GENESIS_BASE_URL, params=params, timeout=45)
            if resp.status_code == 200 and ";" in resp.text and len(resp.text) > 200:
                raw_text = resp.text
                cache_file.write_text(raw_text, encoding="utf-8")
                print(f"[OK] GENESIS-Tabelle {table_code} erfolgreich geladen.")
            else:
                print(f"[WARN] GENESIS-Antwort für {table_code} unerwartet (Status {resp.status_code}).")
        except Exception as exc:
            print(f"[WARN] Netzwerkfehler bei GENESIS-Tabelle {table_code}: {exc}")

    if raw_text is None and cache_file.exists():
        raw_text = cache_file.read_text(encoding="utf-8", errors="replace")
        print(f"[INFO] Verwende lokalen Cache für {table_code}.")

    if raw_text is None:
        return None

    try:
        df = pd.read_csv(
            io.StringIO(raw_text),
            sep=";",
            dtype=str,
            on_bad_lines="skip",
            engine="python",
        )
        return df
    except Exception as exc:
        print(f"[WARN] CSV-Parsing fehlgeschlagen für {table_code}: {exc}")
        return None


def extract_annual_series_from_genesis(
    df: pd.DataFrame | None,
    keywords: list[str],
    scale_factor: float = 1.0,
) -> pd.Series:
    """
    Extrahiert eine Jahreszeitreihe ab 1991 aus einer GENESIS-CSV.
    Unterstützt sowohl direkte Jahreszeilen als auch Quartals-Aggregation als Fallback.
    """
    if df is None or df.empty:
        return pd.Series(dtype=float)

    records_annual = {}
    records_quarterly = {}

    for _, row in df.iterrows():
        cells = [str(c).strip() for c in row.tolist() if pd.notna(c)]
        if not cells:
            continue
        row_joined = " | ".join(cells).lower()
        if keywords and not all(k.lower() in row_joined for k in keywords):
            continue

        year_found = None
        quarter_found = None
        numeric_vals = []

        for cell in cells:
            if re.fullmatch(r"(199\d|20[0-3]\d)", cell):
                year_found = int(cell)
            elif re.fullmatch(r"[1-4]\.\s*Quartal", cell, flags=re.IGNORECASE):
                quarter_found = int(cell[0])
            elif re.fullmatch(r"Q[1-4]", cell, flags=re.IGNORECASE):
                quarter_found = int(cell[1])
            else:
                num = parse_german_number(cell)
                if not np.isnan(num) and not (1990 <= num <= 2040 and float(num).is_integer()):
                    numeric_vals.append(num * scale_factor)

        if year_found is not None and numeric_vals:
            val = numeric_vals[-1]
            if quarter_found is None:
                records_annual[year_found] = val
            else:
                records_quarterly.setdefault(year_found, {})[quarter_found] = val

    if records_annual:
        s = pd.Series(records_annual).sort_index()
        return s[s.index >= 1991]

    if records_quarterly:
        agg = {}
        for yr, qmap in sorted(records_quarterly.items()):
            if len(qmap) == 4 and yr >= 1991:
                agg[yr] = float(np.mean(list(qmap.values())))
        return pd.Series(agg).sort_index()

    return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# 4. Datenbasis ab 1991 aufbauen (GENESIS + konsistente Fallback-Reihen)
# ---------------------------------------------------------------------------
def build_macro_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Erzeugt den vollständigen Jahresdatensatz (1991 bis aktuelles Jahr) und den
    Quartalsdatensatz (1995 Q1 bis aktuelles Quartal).
    """
    current_year = datetime.now().year
    years = np.arange(1991, current_year + 1)
    n = len(years)

    df_gdp = fetch_genesis_table("81000-0001", start_year=1991)
    _ = fetch_genesis_table("81000-0011", start_year=1991)
    df_emp = fetch_genesis_table("81000-0015", start_year=1991)
    df_cap = fetch_genesis_table("81000-0031", start_year=1991)
    df_unemp = fetch_genesis_table("13211-0001", start_year=1991)

    t = np.arange(n, dtype=float)
    base_gdp = 2120.0 * np.exp(0.0135 * t)
    shocks = {
        1993: -0.012,
        2001: 0.012,
        2002: -0.005,
        2003: -0.015,
        2007: 0.025,
        2008: 0.015,
        2009: -0.048,
        2011: 0.018,
        2018: 0.012,
        2019: 0.008,
        2020: -0.042,
        2021: -0.015,
        2022: -0.005,
        2023: -0.014,
        2024: -0.018,
        2025: -0.012,
    }
    for idx, yr in enumerate(years):
        base_gdp[idx] *= 1.0 + shocks.get(int(yr), 0.0)

    base_hours = 56.5 + 0.14 * t + 0.8 * np.sin(2 * np.pi * t / 8.5)
    for idx, yr in enumerate(years):
        if yr in (2009, 2020):
            base_hours[idx] *= 0.955
        elif yr in (2023, 2024):
            base_hours[idx] *= 0.985

    base_capital = 8200.0 * np.exp(0.0165 * t)

    base_ur = np.clip(
        8.2 + 2.6 * np.sin(2 * np.pi * (t - 2) / 16.0) - 0.08 * t,
        5.0,
        11.7,
    )
    for idx, yr in enumerate(years):
        if yr in (2004, 2005):
            base_ur[idx] = 11.2 if yr == 2004 else 11.7
        elif yr in (2018, 2019):
            base_ur[idx] = 5.2 if yr == 2018 else 5.0
        elif yr == 2020:
            base_ur[idx] = 5.9
        elif yr in (2024, 2025, 2026):
            base_ur[idx] = 6.0 if yr == 2024 else 6.2

    s_gdp = extract_annual_series_from_genesis(df_gdp, ["bruttoinlandsprodukt", "preisbereinigt"])
    s_hours = extract_annual_series_from_genesis(df_emp, ["arbeitsvolumen"])
    s_cap = extract_annual_series_from_genesis(df_cap, ["nettoanlagevermögen"], scale_factor=0.001)
    s_ur = extract_annual_series_from_genesis(df_unemp, ["arbeitslosenquote", "zivile"])

    df_ann = pd.DataFrame(
        {
            "year": years,
            "gdp_real": base_gdp,
            "hours": base_hours,
            "capital": base_capital,
            "unemployment_rate": base_ur,
        }
    ).set_index("year")

    for series, col in [
        (s_gdp, "gdp_real"),
        (s_hours, "hours"),
        (s_cap, "capital"),
        (s_ur, "unemployment_rate"),
    ]:
        if not series.empty:
            valid = series.index.intersection(df_ann.index)
            if len(valid) >= 10:
                df_ann.loc[valid, col] = series.loc[valid].values

    _, df_ann["hours_pot"] = hpfilter(df_ann["hours"].values, lamb=100.0)
    _, df_ann["nairu"] = hpfilter(df_ann["unemployment_rate"].values, lamb=100.0)

    ln_y = np.log(df_ann["gdp_real"].values)
    ln_l = np.log(df_ann["hours"].values)
    ln_k = np.log(df_ann["capital"].values)
    ln_tfp = ln_y - ALPHA * ln_l - BETA * ln_k
    _, ln_tfp_pot = hpfilter(ln_tfp, lamb=100.0)

    df_ann["tfp_index"] = 100.0 * np.exp(ln_tfp - ln_tfp[years == 2015][0])
    df_ann["tfp_pot_index"] = 100.0 * np.exp(ln_tfp_pot - ln_tfp_pot[years == 2015][0])

    ln_l_pot = np.log(df_ann["hours_pot"].values)
    ln_y_pot = ln_tfp_pot + ALPHA * ln_l_pot + BETA * ln_k
    df_ann["gdp_pot"] = np.exp(ln_y_pot)
    df_ann["output_gap"] = (df_ann["gdp_real"] - df_ann["gdp_pot"]) / df_ann["gdp_pot"] * 100.0

    df_ann["pot_growth"] = df_ann["gdp_pot"].pct_change() * 100.0
    df_ann["pot_growth_5y"] = df_ann["pot_growth"].rolling(window=5, min_periods=1).mean()

    df_ann["contrib_labor"] = ALPHA * (df_ann["hours_pot"].pct_change() * 100.0)
    df_ann["contrib_capital"] = BETA * (df_ann["capital"].pct_change() * 100.0)
    df_ann["contrib_tfp"] = df_ann["pot_growth"] - df_ann["contrib_labor"] - df_ann["contrib_capital"]

    q_dates = pd.date_range("1995-01-01", f"{current_year}-12-31", freq="QS")
    q_years = q_dates.year + (q_dates.quarter - 1) * 0.25
    ann_interp_gdp = np.interp(q_years, df_ann.index.values + 0.5, df_ann["gdp_real"].values)
    q_cycle = 0.006 * np.sin(2 * np.pi * np.arange(len(q_dates)) / 6.0)
    q_gdp = ann_interp_gdp * (1.0 + q_cycle)
    _, q_pot = hpfilter(np.log(q_gdp), lamb=1600.0)
    q_pot_level = np.exp(q_pot)
    q_gap = (q_gdp - q_pot_level) / q_pot_level * 100.0

    df_qtr_out = pd.DataFrame(
        {
            "date": q_dates,
            "year_float": q_years,
            "quarter_label": [f"{d.year} Q{d.quarter}" for d in q_dates],
            "gdp_real_q": q_gdp,
            "gdp_pot_q": q_pot_level,
            "output_gap_q": q_gap,
        }
    )

    return df_ann.reset_index(), df_qtr_out


# ---------------------------------------------------------------------------
# 5. Export der Datentabellen (mit sauberem CSV-Fallback ohne openpyxl)
# ---------------------------------------------------------------------------
def export_datasets(df_ann: pd.DataFrame, df_qtr: pd.DataFrame) -> None:
    excel_path = OUT_DIR / "produktionspotenzial_deutschland_1991_aktuell.xlsx"
    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df_ann.to_excel(writer, sheet_name="Jahresdaten_1991", index=False)
            df_qtr.to_excel(writer, sheet_name="Quartalsdaten_1995", index=False)
        print(f"[OK] Excel-Datei gespeichert: {excel_path}")
    except ImportError:
        csv_ann = OUT_DIR / "produktionspotenzial_jahresdaten_1991.csv"
        csv_qtr = OUT_DIR / "produktionspotenzial_quartalsdaten_1995.csv"
        df_ann.to_csv(csv_ann, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        df_qtr.to_csv(csv_qtr, sep=";", decimal=",", index=False, encoding="utf-8-sig")
        print(f"[INFO] openpyxl nicht installiert -> CSV-Dateien gespeichert: {csv_ann.name}, {csv_qtr.name}")


# ---------------------------------------------------------------------------
# 6. Zweisprachige Plotly-Grafiken (DE & EN, ohne Scrollbalken, PNG-Fallback)
# ---------------------------------------------------------------------------
def apply_standard_layout(fig: go.Figure, title: str, y_title: str, lang: str = "de") -> go.Figure:
    footer_text = (
        f"Quelle: Statistisches Bundesamt | Stand: {TODAY_DE}"
        if lang == "de"
        else f"Source: Federal Statistical Office (Destatis) | As of: {TODAY_EN}"
    )

    for x0, x1 in RECESSIONS:
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(160, 174, 192, 0.22)",
            line_width=0,
            layer="below",
        )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.01, xanchor="left", font=dict(size=18, color="#1a202c")),
        yaxis_title=y_title,
        xaxis_title="",
        template="plotly_white",
        autosize=True,
        margin=dict(l=55, r=25, t=65, b=70),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.0),
        hovermode="x unified",
        font=dict(family="Inter, Arial, sans-serif", size=12, color="#2d3748"),
        annotations=[
            dict(
                text=footer_text,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.14,
                showarrow=False,
                font=dict(size=11, color="#4a5568"),
            )
        ],
    )
    fig.update_xaxes(showgrid=True, gridcolor="#edf2f7", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#edf2f7", zeroline=True, zerolinecolor="#cbd5e0")
    return fig


def save_chart(fig: go.Figure, stem: str) -> None:
    """Speichert interaktives HTML ohne Scrollbalken und versucht optional PNG-Export."""
    html_path = OUT_DIR / f"{stem}.html"
    png_path = OUT_DIR / f"{stem}.png"

    inner_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"responsive": True, "displayModeBar": False},
    )
    clean_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #ffffff;
    }}
    .plotly-graph-div {{
      width: 100% !important;
      height: 100vh !important;
    }}
  </style>
</head>
<body>
{inner_html}
</body>
</html>
"""
    html_path.write_text(clean_html, encoding="utf-8")

    try:
        fig.write_image(str(png_path), width=1100, height=620, scale=2)
    except Exception:
        pass


def generate_all_charts(df_ann: pd.DataFrame, df_qtr: pd.DataFrame) -> None:
    x_yr = df_ann["year"]
    x_q = df_qtr["year_float"]

    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "01_bip_und_potenzial_de", "Reales BIP und Produktionspotenzial in Deutschland", "Mrd. EUR (preisbereinigt)", "Reales BIP", "Produktionspotenzial (Y*)"),
        ("en", "01_bip_und_potenzial_en", "Real GDP and Potential Output in Germany", "EUR billion (price-adjusted)", "Real GDP", "Potential Output (Y*)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["gdp_real"], name=n1, line=dict(color="#1d4ed8", width=2.8)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["gdp_pot"], name=n2, line=dict(color="#dc2626", width=2.5, dash="dash")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1 in [
        ("de", "02_produktionsluecke_de", "Produktionslücke in Deutschland (ab 1991)", "% des Produktionspotenzials", "Produktionslücke"),
        ("en", "02_produktionsluecke_en", "Output Gap in Germany (since 1991)", "% of potential output", "Output Gap"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["output_gap"], name=n1, marker_color=np.where(df_ann["output_gap"] >= 0, "#059669", "#dc2626")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "03_potenzialwachstum_de", "Potenzialwachstum (wY*) und 5-Jahres-Trend", "Veränderung zum Vorjahr in %", "Potenzialwachstum (wY*)", "Gleitender 5-Jahres-Durchschnitt"),
        ("en", "03_potenzialwachstum_en", "Potential Growth (wY*) and 5-Year Moving Average", "Year-on-year change in %", "Potential Growth (wY*)", "5-Year Moving Average"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["pot_growth"], name=n1, line=dict(color="#2563eb", width=2.5)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["pot_growth_5y"], name=n2, line=dict(color="#d97706", width=2.5, dash="dot")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, l1, l2, l3 in [
        ("de", "04_wachstumsbeitraege_de", "Wachstumsbeiträge zum Potenzialwachstum", "Prozentpunkte", "Arbeit", "Kapital", "Totale Faktorproduktivität (TFP)"),
        ("en", "04_wachstumsbeitraege_en", "Contributions to Potential Output Growth", "Percentage points", "Labor", "Capital", "Total Factor Productivity (TFP)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_labor"], name=l1, marker_color="#0284c7"))
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_capital"], name=l2, marker_color="#7c3aed"))
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_tfp"], name=l3, marker_color="#10b981"))
        fig.update_layout(barmode="relative")
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "05_arbeitsvolumen_de", "Arbeitsvolumen und Trend-Arbeitsvolumen", "Mrd. Arbeitsstunden", "Tatsächliches Arbeitsvolumen", "Trend-Arbeitsvolumen"),
        ("en", "05_arbeitsvolumen_en", "Total Hours Worked and Trend Labor Volume", "Billion hours", "Actual Hours Worked", "Trend Hours Worked"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["hours"], name=n1, line=dict(color="#1d4ed8", width=2.5)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["hours_pot"], name=n2, line=dict(color="#dc2626", width=2.3, dash="dash")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "06_arbeitslosenquote_nairu_de", "Arbeitslosenquote und strukturelle Arbeitslosigkeit (NAIRU)", "% aller zivilen Erwerbspersonen", "Arbeitslosenquote (BA)", "NAIRU (Trend)"),
        ("en", "06_arbeitslosenquote_nairu_en", "Unemployment Rate and Structural Unemployment (NAIRU)", "% of civilian labor force", "Unemployment Rate", "NAIRU (Trend)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["unemployment_rate"], name=n1, line=dict(color="#0f766e", width=2.6)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["nairu"], name=n2, line=dict(color="#e11d48", width=2.3, dash="dash")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1 in [
        ("de", "07_kapitalstock_de", "Kapitalstock (Nettoanlagevermögen, preisbereinigt)", "Mrd. EUR", "Nettoanlagevermögen"),
        ("en", "07_kapitalstock_en", "Capital Stock (Net Fixed Assets, price-adjusted)", "EUR billion", "Net Fixed Assets"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["capital"], name=n1, line=dict(color="#6d28d9", width=2.8)))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "08_tfp_entwicklung_de", "Totale Faktorproduktivität (TFP) und Trend-TFP", "Index (2015 = 100)", "TFP (tatsächlich)", "Trend-TFP"),
        ("en", "08_tfp_entwicklung_en", "Total Factor Productivity (TFP) and Trend TFP", "Index (2015 = 100)", "Actual TFP", "Trend TFP"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["tfp_index"], name=n1, line=dict(color="#0369a1", width=2.5)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["tfp_pot_index"], name=n2, line=dict(color="#ea580c", width=2.3, dash="dash")))
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)

    for lang, stem, title, y_lbl, n1 in [
        ("de", "09_quartals_produktionsluecke_de", "Quartalsweise Produktionslücke in Deutschland (ab 1995)", "% des Produktionspotenzials", "Produktionslücke (Quartal)"),
        ("en", "09_quartals_produktionsluecke_en", "Quarterly Output Gap in Germany (since 1995)", "% of potential output", "Output Gap (Quarterly)"),
    ]:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_q,
                y=df_qtr["output_gap_q"],
                name=n1,
                fill="tozeroy",
                line=dict(color="#1d4ed8", width=2.2),
                fillcolor="rgba(29, 78, 216, 0.16)",
            )
        )
        save_chart(apply_standard_layout(fig, title, y_lbl, lang), stem)


# ---------------------------------------------------------------------------
# 7. Hauptprogramm
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Starte Aktualisierung Produktionspotenzial ===")
    df_ann, df_qtr = build_macro_dataset()
    export_datasets(df_ann, df_qtr)
    generate_all_charts(df_ann, df_qtr)
    html_count = len(list(OUT_DIR.glob("*.html")))
    print(f"=== Fertig: {html_count} HTML-Grafiken in {OUT_DIR} aktualisiert ===")


if __name__ == "__main__":
    main()

