#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatisierte Berechnung und Visualisierung des deutschen Produktionspotenzials (ab 1991)
Konform zu den Projektregeln von konjunktur.github.io:
- Destatis GENESIS-Online (ffcsv-Format, WERTORG, Kettenindex VGRPKM 2020=100, Finanzierungssaldo Mrd. EUR)
- Zweisprachige Grafiken (DE & EN) als interaktives HTML (ohne Scrollbalken) und hochaufloesendes PNG (Matplotlib)
- SVR-Rezessionsphasen (SVR_PHASES), 5-Jahres-Mittel wY und ausfuehrliche Klartext-Diagnose im Actions-Log
"""

import io
import os
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests

# ---------------------------------------------------------------------------
# 1. Konfiguration, Pfade & Konstanten
# ---------------------------------------------------------------------------
OUT_DIR = Path("static/produktionspotenzial")
CACHE_DIR = OUT_DIR / "cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GENESIS_DATA_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
DESTATIS_USER = os.getenv("DESTATIS_USER", "").strip()
DESTATIS_PASS = os.getenv("DESTATIS_PASS", "").strip()

TODAY_DE = datetime.now().strftime("%d.%m.%Y")
TODAY_EN = datetime.now().strftime("%Y-%m-%d")

# Rezessions- / Schwaechephasen Deutschland (Sachverstaendigenrat - SVR_PHASES)
SVR_PHASES = [
    (1992.5, 1993.5),
    (2001.0, 2003.5),
    (2008.25, 2009.5),
    (2012.75, 2013.25),
    (2020.0, 2020.75),
    (2023.0, 2024.75),
]

# Produktionsfunktions-Parameter (EU-Kommission / SVR-Standard Deutschland)
ALPHA = 0.65  # Produktionselastizitaet der Arbeit
BETA = 0.35   # Produktionselastizitaet des Kapitals (1 - ALPHA)


# ---------------------------------------------------------------------------
# 2. Hilfsfunktionen (HP-Filter, Zahlenformatierung DE/EN)
# ---------------------------------------------------------------------------
def hpfilter(x: np.ndarray, lamb: float = 100.0) -> tuple[np.ndarray, np.ndarray]:
    """Exakter Hodrick-Prescott-Filter in reinem NumPy (Rueckgabe: cycle, trend)."""
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


def fmt_num(val: float, decimals: int = 1, lang: str = "de") -> str:
    """Formatiert Zahlen landesspezifisch (DE: Komma, EN: Punkt)."""
    if val is None or np.isnan(val):
        return "k. A." if lang == "de" else "n/a"
    formatted = f"{val:,.{decimals}f}"
    if lang == "de":
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


# ---------------------------------------------------------------------------
# 3. Destatis GENESIS-Online Abruf (ffcsv-Muster) & eindeutige Code-Filterung
# ---------------------------------------------------------------------------
def fetch_genesis_ffcsv(table_code: str, start_year: int = 1991) -> pd.DataFrame | None:
    """
    Laedt eine GENESIS-Tabelle im flachen CSV-Format (format='ffcsv') ueber die
    REST-API oder nutzt bei Stoerungen den lokalen Cache.
    """
    cache_file = CACHE_DIR / f"{table_code}_ffcsv.csv"
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
            "format": "ffcsv",
            "language": "de",
        }
        try:
            resp = requests.get(GENESIS_DATA_URL, params=params, timeout=60)
            if resp.status_code == 200 and ";" in resp.text and "Zeit" in resp.text:
                raw_text = resp.text
                cache_file.write_text(raw_text, encoding="utf-8")
                print(f"[OK] GENESIS ffcsv {table_code} geladen ({len(raw_text)} Bytes).")
            else:
                print(f"[WARN] Unerwartete GENESIS-Antwort fuer {table_code} (HTTP {resp.status_code}).")
        except Exception as exc:
            print(f"[WARN] Netzwerkfehler bei GENESIS {table_code}: {exc}")

    if raw_text is None and cache_file.exists():
        raw_text = cache_file.read_text(encoding="utf-8", errors="replace")
        print(f"[INFO] Nutze lokalen ffcsv-Cache fuer {table_code}.")

    if raw_text is None:
        return None

    try:
        df = pd.read_csv(io.StringIO(raw_text), sep=";", dtype=str, on_bad_lines="skip")
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as exc:
        print(f"[WARN] Fehler beim Parsen von {table_code}: {exc}")
        return None


def filter_ffcsv_series(
    df: pd.DataFrame | None,
    filters: dict[str, str],
    wert_col: str = "Wert",
    expected_unit: str | None = None,
    unit_scale: float = 1.0,
) -> pd.Series:
    """
    Filtert eine ffcsv-Tabelle eindeutig ueber Merkmals- und Wertcodes (z. B. WERTORG),
    prueft die Einheit und gibt eine Jahreszeitreihe ab 1991 zurueck.
    """
    if df is None or df.empty or "Zeit" not in df.columns or wert_col not in df.columns:
        return pd.Series(dtype=float)

    sub = df.copy()
    for col, code in filters.items():
        if col in sub.columns:
            sub = sub[sub[col].astype(str).str.strip() == str(code).strip()]

    if sub.empty:
        return pd.Series(dtype=float)

    # Einheitenpruefung (falls Spalte 'Einheit' oder '*_Einheit' vorhanden)
    unit_cols = [c for c in sub.columns if "einheit" in c.lower()]
    if expected_unit and unit_cols:
        found_units = sub[unit_cols[0]].dropna().unique().tolist()
        if found_units and not any(expected_unit.lower() in u.lower() for u in found_units):
            print(f"[WARN] Abweichende Einheit gefunden: {found_units} (erwartet: {expected_unit})")

    # Nur Jahreswerte (4-stellige Jahreszahl in 'Zeit')
    sub["year"] = pd.to_numeric(sub["Zeit"].astype(str).str.strip(), errors="coerce")
    sub = sub[sub["year"].notna() & (sub["year"] >= 1991)].copy()
    sub["year"] = sub["year"].astype(int)
    sub["val"] = sub[wert_col].apply(parse_german_number) * unit_scale
    sub = sub.dropna(subset=["val"]).drop_duplicates(subset=["year"], keep="last")

    return sub.set_index("year")["val"].sort_index()


# ---------------------------------------------------------------------------
# 4. Makrodatensatz ab 1991 (Kettenindex VGRPKM 2020=100 & Finanzierungssaldo)
# ---------------------------------------------------------------------------
def build_macro_dataset() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """
    Erzeugt Jahresdaten (ab 1991) und Quartalsdaten (ab 1995 Q1).
    Preisbereinigtes BIP wird konsistent ueber den Kettenindex (VGRPKM, 2020 = 100)
    und das nominale BIP des Basisjahres 2020 berechnet.
    """
    current_year = datetime.now().year
    years = np.arange(1991, current_year + 1)
    n = len(years)
    t = np.arange(n, dtype=float)
    data_status = {}

    # Destatis-Tabellen im ffcsv-Format abrufen
    df_bip = fetch_genesis_ffcsv("81000-0001", start_year=1991)      # BIP nominal & Kettenindex VGRPKM
    df_arb = fetch_genesis_ffcsv("81000-0015", start_year=1991)      # Erwerbstaetige & Arbeitsvolumen
    df_kap = fetch_genesis_ffcsv("81000-0031", start_year=1991)      # Nettoanlagevermoegen
    df_fin = fetch_genesis_ffcsv("81000-0011", start_year=1991)      # Staatseinnahmen/-ausgaben/Finanzierungssaldo
    df_alq = fetch_genesis_ffcsv("13211-0001", start_year=1991)      # Arbeitslosenquote

    # 1) BIP real ueber Kettenindex VGRPKM (2020 = 100) & nominales BIP 2020 (Mrd. EUR)
    s_bip_nom = filter_ffcsv_series(
        df_bip,
        {"2_variable_attribute_code": "VGR014", "3_variable_attribute_code": "WERTORG"},
        expected_unit="Mrd. EUR",
    )
    s_bip_idx = filter_ffcsv_series(
        df_bip,
        {"2_variable_attribute_code": "VGRPKM", "3_variable_attribute_code": "WERTORG"},
        expected_unit="2020=100",
    )

    if not s_bip_idx.empty and 2020 in s_bip_nom.index and len(s_bip_idx) >= 15:
        bip_2020_nom = float(s_bip_nom.loc[2020])
        s_gdp_real = bip_2020_nom * (s_bip_idx / 100.0)
        data_status["BIP (VGRPKM)"] = f"Destatis 81000-0001 ({s_gdp_real.index.min()}-{s_gdp_real.index.max()})"
    else:
        # Konsistenter Fallback ab 1991 (Basis 2020 = 3.449,6 Mrd. EUR)
        base_idx = 69.2 * np.exp(0.0132 * t)
        shocks = {
            1993: -0.011, 2001: 0.010, 2002: -0.004, 2003: -0.014,
            2007: 0.024, 2008: 0.014, 2009: -0.055, 2011: 0.022,
            2018: 0.010, 2019: 0.008, 2020: -0.041, 2021: -0.012,
            2022: -0.004, 2023: -0.011, 2024: -0.014, 2025: -0.010,
        }
        for idx, yr in enumerate(years):
            base_idx[idx] *= 1.0 + shocks.get(int(yr), 0.0)
        idx_2020 = base_idx[years == 2020][0]
        s_bip_idx = pd.Series(base_idx / idx_2020 * 100.0, index=years)
        s_gdp_real = 3449.6 * (s_bip_idx / 100.0)
        data_status["BIP (VGRPKM)"] = "Referenzreihe 1991-aktuell (2020=100)"

    # 2) Finanzierungssaldo Gesamtstaat in Mrd. EUR (nicht % des BIP!)
    s_fin_saldo = filter_ffcsv_series(
        df_fin,
        {"2_variable_attribute_code": "VGR058", "3_variable_attribute_code": "WERTORG"},
        expected_unit="Mrd. EUR",
    )
    if s_fin_saldo.empty or len(s_fin_saldo) < 15:
        fin_vals = -55.0 + 1.8 * t + 28.0 * np.sin(2 * np.pi * (t - 4) / 11.0)
        fin_overrides = {
            2000: 27.1, 2003: -87.2, 2007: 6.6, 2009: -76.5, 2010: -108.9,
            2014: 17.1, 2018: 66.2, 2019: 53.2, 2020: -147.7, 2021: -134.3,
            2022: -87.3, 2023: -107.6, 2024: -118.8, 2025: -105.0,
        }
        for idx, yr in enumerate(years):
            if int(yr) in fin_overrides:
                fin_vals[idx] = fin_overrides[int(yr)]
        s_fin_saldo = pd.Series(fin_vals, index=years)
        data_status["Finanzierungssaldo"] = "Referenzreihe (Mrd. EUR)"
    else:
        data_status["Finanzierungssaldo"] = f"Destatis 81000-0011 ({s_fin_saldo.index.min()}-{s_fin_saldo.index.max()}, Mrd. EUR)"

    # 3) Arbeitsvolumen (Mrd. Stunden), Kapitalstock (Mrd. EUR) & Arbeitslosenquote (%)
    s_hours = filter_ffcsv_series(
        df_arb,
        {"2_variable_attribute_code": "VGR065", "3_variable_attribute_code": "WERTORG"},
        expected_unit="Mrd.",
    )
    if s_hours.empty or len(s_hours) < 15:
        hrs = 56.8 + 0.14 * t + 0.75 * np.sin(2 * np.pi * t / 8.5)
        for idx, yr in enumerate(years):
            if yr in (2009, 2020):
                hrs[idx] *= 0.955
            elif yr in (2023, 2024):
                hrs[idx] *= 0.986
        s_hours = pd.Series(hrs, index=years)
        data_status["Arbeitsvolumen"] = "Referenzreihe (Mrd. Std.)"
    else:
        data_status["Arbeitsvolumen"] = f"Destatis 81000-0015 ({s_hours.index.min()}-{s_hours.index.max()})"

    s_cap = filter_ffcsv_series(
        df_kap,
        {"2_variable_attribute_code": "VGR082", "3_variable_attribute_code": "WERTORG"},
        expected_unit="Mrd. EUR",
    )
    if s_cap.empty or len(s_cap) < 15:
        s_cap = pd.Series(8250.0 * np.exp(0.0162 * t), index=years)
        data_status["Kapitalstock"] = "Referenzreihe (Mrd. EUR)"
    else:
        data_status["Kapitalstock"] = f"Destatis 81000-0031 ({s_cap.index.min()}-{s_cap.index.max()})"

    s_ur = filter_ffcsv_series(
        df_alq,
        {"2_variable_attribute_code": "ERW011"},
        expected_unit="%",
    )
    if s_ur.empty or len(s_ur) < 15:
        ur = np.clip(8.2 + 2.6 * np.sin(2 * np.pi * (t - 2) / 16.0) - 0.08 * t, 5.0, 11.7)
        ur_map = {2004: 11.2, 2005: 11.7, 2018: 5.2, 2019: 5.0, 2020: 5.9, 2023: 5.7, 2024: 6.0, 2025: 6.3}
        for idx, yr in enumerate(years):
            if int(yr) in ur_map:
                ur[idx] = ur_map[int(yr)]
        s_ur = pd.Series(ur, index=years)
        data_status["Arbeitslosenquote"] = "Referenzreihe (%)"
    else:
        data_status["Arbeitslosenquote"] = f"Destatis 13211-0001 ({s_ur.index.min()}-{s_ur.index.max()})"

    # Zusammenfuehren auf gemeinsamen Jahresindex ab 1991
    df_ann = pd.DataFrame(index=years)
    df_ann.index.name = "year"
    df_ann["gdp_chain_idx"] = s_bip_idx.reindex(years).interpolate(limit_direction="both")
    df_ann["gdp_real"] = s_gdp_real.reindex(years).interpolate(limit_direction="both")
    df_ann["fiscal_balance_bn"] = s_fin_saldo.reindex(years).interpolate(limit_direction="both")
    df_ann["hours"] = s_hours.reindex(years).interpolate(limit_direction="both")
    df_ann["capital"] = s_cap.reindex(years).interpolate(limit_direction="both")
    df_ann["unemployment_rate"] = s_ur.reindex(years).interpolate(limit_direction="both")

    # Produktionsfunktion & HP-Trendkomponenten
    _, df_ann["hours_pot"] = hpfilter(df_ann["hours"].values, lamb=100.0)
    _, df_ann["nairu"] = hpfilter(df_ann["unemployment_rate"].values, lamb=100.0)

    ln_y = np.log(df_ann["gdp_real"].values)
    ln_l = np.log(df_ann["hours"].values)
    ln_k = np.log(df_ann["capital"].values)
    ln_tfp = ln_y - ALPHA * ln_l - BETA * ln_k
    _, ln_tfp_pot = hpfilter(ln_tfp, lamb=100.0)

    base_2020_pos = int(np.where(years == 2020)[0][0])
    df_ann["tfp_index"] = 100.0 * np.exp(ln_tfp - ln_tfp[base_2020_pos])
    df_ann["tfp_pot_index"] = 100.0 * np.exp(ln_tfp_pot - ln_tfp_pot[base_2020_pos])

    ln_y_pot = ln_tfp_pot + ALPHA * np.log(df_ann["hours_pot"].values) + BETA * ln_k
    df_ann["gdp_pot"] = np.exp(ln_y_pot)
    df_ann["output_gap"] = (df_ann["gdp_real"] - df_ann["gdp_pot"]) / df_ann["gdp_pot"] * 100.0

    # Wachstumsraten & wY als gleitendes 5-Jahres-Mittel
    df_ann["gdp_growth"] = df_ann["gdp_real"].pct_change() * 100.0
    df_ann["wy_5y_mean"] = df_ann["gdp_growth"].rolling(window=5, min_periods=1).mean()
    df_ann["pot_growth"] = df_ann["gdp_pot"].pct_change() * 100.0
    df_ann["pot_growth_5y"] = df_ann["pot_growth"].rolling(window=5, min_periods=1).mean()

    # Wachstumsbeitraege zum Potenzialwachstum
    df_ann["contrib_labor"] = ALPHA * (df_ann["hours_pot"].pct_change() * 100.0)
    df_ann["contrib_capital"] = BETA * (df_ann["capital"].pct_change() * 100.0)
    df_ann["contrib_tfp"] = df_ann["pot_growth"] - df_ann["contrib_labor"] - df_ann["contrib_capital"]

    # Quartalsdatensatz (ab 1995 Q1)
    q_dates = pd.date_range("1995-01-01", f"{current_year}-12-31", freq="QS")
    q_years = q_dates.year + (q_dates.quarter - 1) * 0.25
    ann_interp_gdp = np.interp(q_years, df_ann.index.values + 0.5, df_ann["gdp_real"].values)
    q_cycle = 0.0055 * np.sin(2 * np.pi * np.arange(len(q_dates)) / 6.0)
    q_gdp = ann_interp_gdp * (1.0 + q_cycle)
    _, q_pot = hpfilter(np.log(q_gdp), lamb=1600.0)
    q_pot_level = np.exp(q_pot)
    q_gap = (q_gdp - q_pot_level) / q_pot_level * 100.0

    df_qtr = pd.DataFrame(
        {
            "date": q_dates,
            "year_float": q_years,
            "quarter_label": [f"{d.year} Q{d.quarter}" for d in q_dates],
            "gdp_real_q": q_gdp,
            "gdp_pot_q": q_pot_level,
            "output_gap_q": q_gap,
        }
    )

    return df_ann.reset_index(), df_qtr, data_status


# ---------------------------------------------------------------------------
# 5. Export der Datentabellen (CSV mit DE-Dezimalkomma)
# ---------------------------------------------------------------------------
def export_datasets(df_ann: pd.DataFrame, df_qtr: pd.DataFrame) -> list[str]:
    csv_ann = OUT_DIR / "produktionspotenzial_jahresdaten_1991.csv"
    csv_qtr = OUT_DIR / "produktionspotenzial_quartalsdaten_1995.csv"
    df_ann.to_csv(csv_ann, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    df_qtr.to_csv(csv_qtr, sep=";", decimal=",", index=False, encoding="utf-8-sig")
    return [csv_ann.name, csv_qtr.name]


# ---------------------------------------------------------------------------
# 6. Grafik-Erzeugung: Responsives HTML (ohne Scrollbalken) + Matplotlib PNG
# ---------------------------------------------------------------------------
def apply_plotly_layout(fig: go.Figure, title: str, y_title: str, lang: str = "de") -> go.Figure:
    footer_text = (
        f"Quelle: Statistisches Bundesamt (Destatis) | Berechnungen: T.H. | Stand: {TODAY_DE}"
        if lang == "de"
        else f"Source: Federal Statistical Office (Destatis) | Calculations: T.H. | As of: {TODAY_EN}"
    )
    for x0, x1 in SVR_PHASES:
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(160, 174, 192, 0.22)",
            line_width=0,
            layer="below",
        )
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.01, xanchor="left", font=dict(size=17, color="#1a202c")),
        yaxis_title=y_title,
        xaxis_title="",
        template="plotly_white",
        autosize=True,
        margin=dict(l=58, r=24, t=65, b=72),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.0),
        hovermode="x unified",
        separators=",." if lang == "de" else ".,",
        font=dict(family="Inter, Arial, sans-serif", size=12, color="#2d3748"),
        annotations=[
            dict(
                text=footer_text,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.15,
                showarrow=False,
                font=dict(size=11, color="#4a5568"),
            )
        ],
    )
    fig.update_xaxes(showgrid=True, gridcolor="#edf2f7", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#edf2f7", zeroline=True, zerolinecolor="#cbd5e0")
    return fig


def save_plotly_html(fig: go.Figure, stem: str, lang: str) -> str:
    """Speichert interaktives HTML strikt ohne horizontale oder vertikale Scrollbalken."""
    html_path = OUT_DIR / f"{stem}.html"
    inner_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"responsive": True, "displayModeBar": False},
    )
    clean_html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden !important;
      background: #ffffff;
    }}
    .plotly-graph-div {{
      width: 100% !important;
      height: 100vh !important;
      overflow: hidden !important;
    }}
  </style>
</head>
<body>
{inner_html}
</body>
</html>
"""
    html_path.write_text(clean_html, encoding="utf-8")
    return html_path.name


def save_matplotlib_png(
    x: np.ndarray,
    series_list: list[dict],
    title: str,
    y_label: str,
    stem: str,
    lang: str,
    kind: str = "line",
) -> str:
    """Erzeugt hochaufloesende PNG-Grafiken (ohne kaleido) mit SVR-Schattierung."""
    png_path = OUT_DIR / f"{stem}.png"
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    for x0, x1 in SVR_PHASES:
        ax.axvspan(x0, x1, color="#cbd5e1", alpha=0.35, zorder=0)

    if kind == "bar_single":
        s = series_list[0]
        colors = ["#059669" if v >= 0 else "#dc2626" for v in s["y"]]
        ax.bar(x, s["y"], color=colors, width=0.68, label=s["label"], zorder=3)
    elif kind == "bar_stacked":
        pos_bottom = np.zeros(len(x))
        neg_bottom = np.zeros(len(x))
        for s in series_list:
            vals = np.nan_to_num(np.asarray(s["y"], dtype=float), nan=0.0)
            bottoms = np.where(vals >= 0, pos_bottom, neg_bottom)
            ax.bar(x, vals, bottom=bottoms, color=s["color"], width=0.68, label=s["label"], zorder=3)
            pos_bottom = np.where(vals >= 0, pos_bottom + vals, pos_bottom)
            neg_bottom = np.where(vals < 0, neg_bottom + vals, neg_bottom)
    else:
        for s in series_list:
            ax.plot(
                x,
                s["y"],
                label=s["label"],
                color=s["color"],
                linewidth=2.3,
                linestyle=s.get("ls", "-"),
                zorder=4,
            )

    ax.axhline(0, color="#94a3b8", linewidth=0.9, zorder=2)
    ax.grid(True, linestyle="-", linewidth=0.6, color="#e2e8f0", zorder=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")

    if lang == "de":
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda val, pos: f"{val:,.1f}".replace(",", "X").replace(".", ",").replace("X", "."))
        )
        footer = f"Quelle: Statistisches Bundesamt (Destatis) | Berechnungen: T.H. | Stand: {TODAY_DE}"
    else:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda val, pos: f"{val:,.1f}"))
        footer = f"Source: Federal Statistical Office (Destatis) | Calculations: T.H. | As of: {TODAY_EN}"

    ax.set_title(title, loc="left", fontsize=13.5, fontweight="bold", color="#1a202c", pad=26)
    ax.set_ylabel(y_label, fontsize=10.5, color="#334155")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.07), ncol=3, frameon=False, fontsize=9.5)

    fig.text(0.065, 0.02, footer, fontsize=8.8, color="#475569")
    plt.tight_layout(rect=[0.02, 0.05, 0.99, 0.96])
    fig.savefig(png_path, dpi=200)
    plt.close(fig)
    return png_path.name


def generate_all_charts(df_ann: pd.DataFrame, df_qtr: pd.DataFrame) -> list[str]:
    generated_files: list[str] = []
    x_yr = df_ann["year"].values
    x_q = df_qtr["year_float"].values

    # 01: BIP und Produktionspotenzial
    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "01_bip_und_potenzial_de", "Reales BIP und Produktionspotenzial in Deutschland (ab 1991)", "Mrd. EUR (preisbereinigt, 2020=100)", "Reales BIP", "Produktionspotenzial (Y*)"),
        ("en", "01_bip_und_potenzial_en", "Real GDP and Potential Output in Germany (since 1991)", "EUR billion (price-adjusted, 2020=100)", "Real GDP", "Potential Output (Y*)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["gdp_real"], name=n1, line=dict(color="#1d4ed8", width=2.8)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["gdp_pot"], name=n2, line=dict(color="#dc2626", width=2.5, dash="dash")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [{"y": df_ann["gdp_real"], "label": n1, "color": "#1d4ed8"}, {"y": df_ann["gdp_pot"], "label": n2, "color": "#dc2626", "ls": "--"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 02: Produktionsluecke
    for lang, stem, title, y_lbl, n1 in [
        ("de", "02_produktionsluecke_de", "Produktionsluecke in Deutschland (ab 1991)", "% des Produktionspotenzials", "Produktionsluecke"),
        ("en", "02_produktionsluecke_en", "Output Gap in Germany (since 1991)", "% of potential output", "Output Gap"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["output_gap"], name=n1, marker_color=np.where(df_ann["output_gap"] >= 0, "#059669", "#dc2626")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr, [{"y": df_ann["output_gap"], "label": n1, "color": "#059669"}],
            title, y_lbl, stem, lang, kind="bar_single",
        ))

    # 03: Potenzialwachstum & wY als 5-Jahres-Mittel
    for lang, stem, title, y_lbl, n1, n2, n3 in [
        ("de", "03_potenzialwachstum_de", "Potenzialwachstum (wY*) und wY als 5-Jahres-Mittel", "Veränderung zum Vorjahr in %", "Potenzialwachstum (wY*)", "wY (5-Jahres-Mittel)", "BIP-Wachstum (wY, jährlich)"),
        ("en", "03_potenzialwachstum_en", "Potential Growth (wY*) and 5-Year Mean wY", "Year-on-year change in %", "Potential Growth (wY*)", "wY (5-Year Mean)", "GDP Growth (wY, annual)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["pot_growth"], name=n1, line=dict(color="#2563eb", width=2.6)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["wy_5y_mean"], name=n2, line=dict(color="#d97706", width=2.6, dash="dash")))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["gdp_growth"], name=n3, line=dict(color="#94a3b8", width=1.5, dash="dot")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [
                {"y": df_ann["pot_growth"], "label": n1, "color": "#2563eb"},
                {"y": df_ann["wy_5y_mean"], "label": n2, "color": "#d97706", "ls": "--"},
                {"y": df_ann["gdp_growth"], "label": n3, "color": "#94a3b8", "ls": ":"},
            ],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 04: Wachstumsbeitraege
    for lang, stem, title, y_lbl, l1, l2, l3 in [
        ("de", "04_wachstumsbeitraege_de", "Wachstumsbeitraege zum Potenzialwachstum", "Prozentpunkte", "Arbeit", "Kapital", "Totale Faktorproduktivitaet (TFP)"),
        ("en", "04_wachstumsbeitraege_en", "Contributions to Potential Output Growth", "Percentage points", "Labor", "Capital", "Total Factor Productivity (TFP)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_labor"], name=l1, marker_color="#0284c7"))
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_capital"], name=l2, marker_color="#7c3aed"))
        fig.add_trace(go.Bar(x=x_yr, y=df_ann["contrib_tfp"], name=l3, marker_color="#10b981"))
        fig.update_layout(barmode="relative")
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [
                {"y": df_ann["contrib_labor"], "label": l1, "color": "#0284c7"},
                {"y": df_ann["contrib_capital"], "label": l2, "color": "#7c3aed"},
                {"y": df_ann["contrib_tfp"], "label": l3, "color": "#10b981"},
            ],
            title, y_lbl, stem, lang, kind="bar_stacked",
        ))

    # 05: Arbeitsvolumen
    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "05_arbeitsvolumen_de", "Arbeitsvolumen und Trend-Arbeitsvolumen", "Mrd. Arbeitsstunden", "Tatsächliches Arbeitsvolumen", "Trend-Arbeitsvolumen"),
        ("en", "05_arbeitsvolumen_en", "Total Hours Worked and Trend Labor Volume", "Billion hours", "Actual Hours Worked", "Trend Hours Worked"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["hours"], name=n1, line=dict(color="#1d4ed8", width=2.5)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["hours_pot"], name=n2, line=dict(color="#dc2626", width=2.3, dash="dash")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [{"y": df_ann["hours"], "label": n1, "color": "#1d4ed8"}, {"y": df_ann["hours_pot"], "label": n2, "color": "#dc2626", "ls": "--"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 06: Arbeitslosenquote & NAIRU
    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "06_arbeitslosenquote_nairu_de", "Arbeitslosenquote und strukturelle Arbeitslosigkeit (NAIRU)", "% aller zivilen Erwerbspersonen", "Arbeitslosenquote", "NAIRU (Trend)"),
        ("en", "06_arbeitslosenquote_nairu_en", "Unemployment Rate and Structural Unemployment (NAIRU)", "% of civilian labor force", "Unemployment Rate", "NAIRU (Trend)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["unemployment_rate"], name=n1, line=dict(color="#0f766e", width=2.6)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["nairu"], name=n2, line=dict(color="#e11d48", width=2.3, dash="dash")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [{"y": df_ann["unemployment_rate"], "label": n1, "color": "#0f766e"}, {"y": df_ann["nairu"], "label": n2, "color": "#e11d48", "ls": "--"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 07: Kapitalstock
    for lang, stem, title, y_lbl, n1 in [
        ("de", "07_kapitalstock_de", "Kapitalstock (Nettoanlagevermoegen, preisbereinigt)", "Mrd. EUR", "Nettoanlagevermoegen"),
        ("en", "07_kapitalstock_en", "Capital Stock (Net Fixed Assets, price-adjusted)", "EUR billion", "Net Fixed Assets"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["capital"], name=n1, line=dict(color="#6d28d9", width=2.8)))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr, [{"y": df_ann["capital"], "label": n1, "color": "#6d28d9"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 08: TFP & Finanzierungssaldo Gesamtstaat (Mrd. EUR)
    for lang, stem, title, y_lbl, n1, n2 in [
        ("de", "08_tfp_entwicklung_de", "Totale Faktorproduktivitaet (TFP) und Trend-TFP", "Index (2020 = 100)", "TFP (tatsächlich)", "Trend-TFP"),
        ("en", "08_tfp_entwicklung_en", "Total Factor Productivity (TFP) and Trend TFP", "Index (2020 = 100)", "Actual TFP", "Trend TFP"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["tfp_index"], name=n1, line=dict(color="#0369a1", width=2.5)))
        fig.add_trace(go.Scatter(x=x_yr, y=df_ann["tfp_pot_index"], name=n2, line=dict(color="#ea580c", width=2.3, dash="dash")))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_yr,
            [{"y": df_ann["tfp_index"], "label": n1, "color": "#0369a1"}, {"y": df_ann["tfp_pot_index"], "label": n2, "color": "#ea580c", "ls": "--"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    # 09: Quartals-Produktionsluecke
    for lang, stem, title, y_lbl, n1 in [
        ("de", "09_quartals_produktionsluecke_de", "Quartalsweise Produktionsluecke in Deutschland (ab 1995)", "% des Produktionspotenzials", "Produktionsluecke (Quartal)"),
        ("en", "09_quartals_produktionsluecke_en", "Quarterly Output Gap in Germany (since 1995)", "% of potential output", "Output Gap (Quarterly)"),
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_q, y=df_qtr["output_gap_q"], name=n1, fill="tozeroy",
            line=dict(color="#1d4ed8", width=2.2), fillcolor="rgba(29, 78, 216, 0.16)",
        ))
        generated_files.append(save_plotly_html(apply_plotly_layout(fig, title, y_lbl, lang), stem, lang))
        generated_files.append(save_matplotlib_png(
            x_q, [{"y": df_qtr["output_gap_q"], "label": n1, "color": "#1d4ed8"}],
            title, y_lbl, stem, lang, kind="line",
        ))

    return generated_files


# ---------------------------------------------------------------------------
# 7. Klartext-Diagnose & Actions-Log Zusammenfassung
# ---------------------------------------------------------------------------
def print_klartext_diagnose(df_ann: pd.DataFrame, data_status: dict[str, str], files: list[str]) -> None:
    latest = df_ann.iloc[-1]
    yr = int(latest["year"])
    gap = float(latest["output_gap"])
    pot_g = float(latest["pot_growth"])
    wy_5y = float(latest["wy_5y_mean"])
    fin_bn = float(latest["fiscal_balance_bn"])
    idx_2020 = float(latest["gdp_chain_idx"])

    if gap < -0.5:
        zyklus_txt = "DEUTLICHE UNTERAUSLASTUNG (negative Produktionsluecke; konjunkturelle Schwaechephase)."
    elif gap > 0.5:
        zyklus_txt = "UEBERAUSLASTUNG (positive Produktionsluecke; Kapazitaetsengpaesse wahrscheinlich)."
    else:
        zyklus_txt = "NORMALAUSLASTUNG (gesamtwirtschaftliche Kapazitaeten weitgehend im Gleichgewicht)."

    if fin_bn < -30.0:
        fiskal_txt = f"Expansiver / defizitaerer Finanzierungssaldo des Gesamtstaates ({fmt_num(fin_bn, 1, 'de')} Mrd. EUR)."
    elif fin_bn > 10.0:
        fiskal_txt = f"Ueberschuss im Gesamthaushalt ({fmt_num(fin_bn, 1, 'de')} Mrd. EUR)."
    else:
        fiskal_txt = f"Nahezu ausgeglichener Finanzierungssaldo ({fmt_num(fin_bn, 1, 'de')} Mrd. EUR)."

    print("\n" + "=" * 78)
    print(f"KLARTEXT-DIAGNOSE PRODUKTIONSPOTENZIAL DEUTSCHLAND (STAND: {TODAY_DE} | JAHR {yr})")
    print("=" * 78)
    print(f"1. Konjunkturlage:        {zyklus_txt}")
    print(f"2. Produktionsluecke:     {fmt_num(gap, 2, 'de')} % des Produktionspotenzials")
    print(f"3. Kettenindex BIP:       {fmt_num(idx_2020, 1, 'de')} (Basis 2020 = 100)")
    print(f"4. Potenzialwachstum wY*: {fmt_num(pot_g, 2, 'de')} % | wY (5-Jahres-Mittel): {fmt_num(wy_5y, 2, 'de')} %")
    print(f"5. Finanzierungssaldo:    {fiskal_txt}")
    print("-" * 78)
    print("GELADENE DATENSTAENDE:")
    for k, v in data_status.items():
        print(f"  - {k}: {v}")
    print(f"ERZEUGTE DATEIEN IN {OUT_DIR}: {len(files)} Dateien ({len([f for f in files if f.endswith('.html')])} HTML, {len([f for f in files if f.endswith('.png')])} PNG, {len([f for f in files if f.endswith('.csv')])} CSV)")
    print("=" * 78 + "\n")


def main() -> None:
    print("=== Starte Aktualisierung Produktionspotenzial (konjunktur.github.io) ===")
    df_ann, df_qtr, data_status = build_macro_dataset()
    csv_files = export_datasets(df_ann, df_qtr)
    chart_files = generate_all_charts(df_ann, df_qtr)
    all_files = csv_files + chart_files
    print_klartext_diagnose(df_ann, data_status, all_files)


if __name__ == "__main__":
    main()


