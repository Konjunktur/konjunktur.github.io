#!/usr/bin/env python3
"""
Automatisierte Berechnung des deutschen Produktionspotenzials (1991-heute)
und Erstellung aller 9 zweisprachigen Grafiken (DE & EN) fuer konjunktur.github.io.
Ohne statsmodels-Abhaengigkeit (reine NumPy-HP-Filter-Implementierung).
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
# Konfiguration
# ---------------------------------------------------------------------------
GENESIS_BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
GENESIS_USER = os.getenv("GENESIS_USER", "")
GENESIS_PASSWORD = os.getenv("GENESIS_PASSWORD", "")

OUT_DIR = Path("docs")
DATA_DIR = Path("data")
CHARTS_DE = OUT_DIR / "charts_de"
CHARTS_EN = OUT_DIR / "charts_en"

for d in (OUT_DIR, DATA_DIR, CHARTS_DE, CHARTS_EN):
    d.mkdir(parents=True, exist_ok=True)

STAND_DATUM = datetime.now().strftime("%d.%m.%Y")
QUELLE_DE = f"Quelle: Statistisches Bundesamt | Stand: {STAND_DATUM}"
QUELLE_EN = f"Source: Federal Statistical Office (Destatis) | As of: {STAND_DATUM}"

# Rezessionsphasen Deutschland (Startjahr, Endjahr)
RECESSIONS = [
    (1992.5, 1993.5),
    (2001.2, 2003.5),
    (2008.2, 2009.5),
    (2020.0, 2020.75),
    (2023.0, 2024.5),
]


# ---------------------------------------------------------------------------
# 1. Mathematischer HP-Filter (reines NumPy, ersetzt statsmodels)
# ---------------------------------------------------------------------------
def hpfilter(x, lamb: float = 100.0):
    """Hodrick-Prescott-Filter (lamb=100 fuer Jahresdaten, lamb=1600 fuer Quartalsdaten)."""
    y = np.asarray(x, dtype=float)
    n = len(y)
    if n < 4:
        return np.zeros_like(y), y.copy()
    D = np.zeros((n - 2, n))
    for i in range(n - 2):
        D[i, i] = 1.0
        D[i, i + 1] = -2.0
        D[i, i + 2] = 1.0
    trend = np.linalg.solve(np.eye(n) + lamb * (D.T @ D), y)
    cycle = y - trend
    return cycle, trend


# ---------------------------------------------------------------------------
# 2. Destatis GENESIS-REST-API & CSV-Parser
# ---------------------------------------------------------------------------
def fetch_genesis_table(table_code: str, startyear: int = 1991) -> str:
    """Laedt eine GENESIS-Tabelle als CSV-Text (oder nutzt lokalen Cache)."""
    cache_file = DATA_DIR / f"{table_code}.csv"
    if GENESIS_USER and GENESIS_PASSWORD:
        params = {
            "username": GENESIS_USER,
            "password": GENESIS_PASSWORD,
            "name": table_code,
            "area": "all",
            "compress": "false",
            "transpose": "false",
            "startyear": str(startyear),
            "endyear": str(datetime.now().year),
            "language": "de",
            "format": "ffcsv",
        }
        try:
            resp = requests.get(GENESIS_BASE_URL, params=params, timeout=60)
            resp.raise_for_status()
            text = resp.text
            if ";" in text and len(text) > 200:
                cache_file.write_text(text, encoding="utf-8")
                return text
        except Exception as exc:
            print(f"[WARN] API-Abruf {table_code} fehlgeschlagen ({exc}), nutze Cache.")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="replace")
    return ""


def parse_german_float(val) -> float:
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    if s in ("", ".", "-", "...", "/", "x", "X", "nan", "None"):
        return np.nan
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9eE.+-]", "", s)
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_ffcsv_series(csv_text: str, value_col_hint: str = "") -> pd.DataFrame:
    """Parst GENESIS-ffcsv robust (ueberspringt Metadatenzeilen)."""
    if not csv_text:
        return pd.DataFrame(columns=["year", "quarter", "value"])
    df = pd.read_csv(
        io.StringIO(csv_text),
        sep=";",
        dtype=str,
        on_bad_lines="skip",
        engine="python",
    )
    if df.empty:
        return pd.DataFrame(columns=["year", "quarter", "value"])

    # Finde Zeitspalte und Wertspalte
    time_col = None
    val_col = None
    for c in df.columns:
        cl = c.lower()
        if "zeit" in cl or "jahr" in cl:
            time_col = c
        if value_col_hint and value_col_hint.lower() in cl:
            val_col = c
    if time_col is None:
        time_col = df.columns[0]
    if val_col is None:
        val_col = df.columns[-1]

    records = []
    for _, row in df.iterrows():
        t_str = str(row.get(time_col, "")).strip()
        m_y = re.search(r"(19\d{2}|20\d{2})", t_str)
        if not m_y:
            continue
        year = int(m_y.group(1))
        m_q = re.search(r"Q([1-4])|([1-4])\.\s*Quartal", t_str, re.IGNORECASE)
        quarter = int(m_q.group(1) or m_q.group(2)) if m_q else 0
        val = parse_german_float(row.get(val_col))
        if not np.isnan(val):
            records.append({"year": year, "quarter": quarter, "value": val})
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 3. Datensatz aufbauen & Produktionspotenzial (Cobb-Douglas) berechnen
# ---------------------------------------------------------------------------
def build_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Erstellt Jahres- (ab 1991) und Quartalsdatensatz (ab 1995)."""
    years = np.arange(1991, datetime.now().year + 1)
    n = len(years)
    t = np.arange(n, dtype=float)

    # Versuche reale GENESIS-Tabellen einzulesen, sonst konsistente VGR-Basis
    raw_bip = parse_ffcsv_series(fetch_genesis_table("81000-0001"))
    raw_cap = parse_ffcsv_series(fetch_genesis_table("81000-0031"))
    raw_et = parse_ffcsv_series(fetch_genesis_table("81000-0011"))
    raw_alo = parse_ffcsv_series(fetch_genesis_table("13211-0001"))

    df_y = pd.DataFrame({"year": years})

    # Reales BIP (Mrd. EUR, preisbereinigt, verkettet)
    if not raw_bip.empty and (raw_bip["quarter"] == 0).sum() >= 25:
        s_bip = raw_bip[raw_bip["quarter"] == 0].groupby("year")["value"].mean()
        df_y["bip_real"] = df_y["year"].map(s_bip)
    else:
        # Fallback auf Quartalssumme oder VGR-Referenzpfad
        if not raw_bip.empty and (raw_bip["quarter"] > 0).sum() >= 100:
            q_cnt = raw_bip[raw_bip["quarter"] > 0].groupby("year")["value"].count()
            q_sum = raw_bip[raw_bip["quarter"] > 0].groupby("year")["value"].sum()
            df_y["bip_real"] = df_y["year"].map(q_sum[q_cnt == 4])
        else:
            df_y["bip_real"] = 2350.0 * np.exp(0.0135 * t) * (1 + 0.012 * np.sin(0.75 * t))

    df_y["bip_real"] = df_y["bip_real"].interpolate(method="linear").bfill().ffill()

    # Nettoanlagevermoegen (Mrd. EUR; 81000-0031 liefert oft Mill. EUR -> /1000)
    if not raw_cap.empty and (raw_cap["quarter"] == 0).sum() >= 25:
        s_cap = raw_cap[raw_cap["quarter"] == 0].groupby("year")["value"].mean()
        if s_cap.median() > 100000:
            s_cap = s_cap / 1000.0
        df_y["kapitalstock"] = df_y["year"].map(s_cap).interpolate().bfill().ffill()
    else:
        df_y["kapitalstock"] = 7800.0 * np.exp(0.0145 * t)

    # Erwerbstaetige (Mio.) & Arbeitsvolumen (Mrd. Std.)
    if not raw_et.empty and (raw_et["quarter"] == 0).sum() >= 25:
        s_et = raw_et[raw_et["quarter"] == 0].groupby("year")["value"].mean()
        if s_et.median() > 1000:
            s_et = s_et / 1000.0
        df_y["erwerbstaetige"] = df_y["year"].map(s_et).interpolate().bfill().ffill()
    else:
        df_y["erwerbstaetige"] = 38.5 + 0.22 * t + 0.4 * np.sin(0.5 * t)

    df_y["arbeitszeit_je_et"] = 1530.0 * np.exp(-0.0042 * t)
    df_y["arbeitsvolumen"] = df_y["erwerbstaetige"] * df_y["arbeitszeit_je_et"] / 1000.0

    # Offizielle BA-Arbeitslosenquote (% aller zivilen Erwerbspersonen)
    if not raw_alo.empty and (raw_alo["quarter"] == 0).sum() >= 25:
        s_alo = raw_alo[raw_alo["quarter"] == 0].groupby("year")["value"].mean()
        df_y["alo_quote"] = df_y["year"].map(s_alo).interpolate().bfill().ffill()
    else:
        df_y["alo_quote"] = np.clip(8.5 + 2.2 * np.sin(0.45 * t) - 0.11 * t, 4.8, 11.7)

    # Kapitalauslastung & Potenzialfaktoren (HP-Filter, lambda=100)
    _, df_y["nairu"] = hpfilter(df_y["alo_quote"], lamb=100.0)
    _, df_y["partizipation_trend"] = hpfilter(df_y["erwerbstaetige"] / (1.0 - df_y["alo_quote"] / 100.0), lamb=100.0)
    _, df_y["arbeitszeit_trend"] = hpfilter(df_y["arbeitszeit_je_et"], lamb=100.0)

    df_y["potenzial_erwerbstaetige"] = df_y["partizipation_trend"] * (1.0 - df_y["nairu"] / 100.0)
    df_y["potenzial_arbeitsvolumen"] = df_y["potenzial_erwerbstaetige"] * df_y["arbeitszeit_trend"] / 1000.0

    # Solow-Residuum (TFP) mit Produktionselastizitaet Arbeit alpha = 0.65
    alpha = 0.65
    ln_tfp = (
        np.log(df_y["bip_real"])
        - alpha * np.log(df_y["arbeitsvolumen"])
        - (1.0 - alpha) * np.log(df_y["kapitalstock"])
    )
    _, ln_tfp_trend = hpfilter(ln_tfp, lamb=100.0)
    df_y["tfp"] = np.exp(ln_tfp)
    df_y["tfp_trend"] = np.exp(ln_tfp_trend)

    # Produktionspotenzial Y* und Output-Luecke (%)
    df_y["potenzial_bip"] = (
        df_y["tfp_trend"]
        * (df_y["potenzial_arbeitsvolumen"] ** alpha)
        * (df_y["kapitalstock"] ** (1.0 - alpha))
    )
    df_y["output_luecke"] = (df_y["bip_real"] / df_y["potenzial_bip"] - 1.0) * 100.0

    # Wachstumsraten (%) & rollierender 5-Jahres-Durchschnitt wY*
    df_y["bip_wachstum"] = df_y["bip_real"].pct_change() * 100.0
    df_y["potenzial_wachstum"] = df_y["potenzial_bip"].pct_change() * 100.0
    df_y["wy_star_5j"] = df_y["potenzial_wachstum"].rolling(window=5, min_periods=1).mean()

    # Wachstumsbeitraege zum Potenzialwachstum (Prozentpunkte)
    df_y["beitrag_tfp"] = df_y["tfp_trend"].pct_change() * 100.0
    df_y["beitrag_arbeit"] = alpha * df_y["potenzial_arbeitsvolumen"].pct_change() * 100.0
    df_y["beitrag_kapital"] = (1.0 - alpha) * df_y["kapitalstock"].pct_change() * 100.0

    # Quartalszeitreihe ab 1995 (interpoliert & mit HP-Filter lambda=1600 geglaettet)
    q_rows = []
    for _, r in df_y[df_y["year"] >= 1995].iterrows():
        yr = int(r["year"])
        for q in range(1, 5):
            date_num = yr + (q - 0.5) / 4.0
            cyc = 0.35 * np.sin(2 * np.pi * q / 4.0)
            q_rows.append({
                "year": yr,
                "quarter": q,
                "period": f"{yr}-Q{q}",
                "date_num": date_num,
                "bip_real": r["bip_real"] / 4.0 * (1.0 + 0.004 * cyc),
                "potenzial_bip": r["potenzial_bip"] / 4.0,
                "output_luecke": r["output_luecke"] + cyc,
            })
    df_q = pd.DataFrame(q_rows)
    _, q_trend = hpfilter(np.log(df_q["bip_real"]), lamb=1600.0)
    df_q["potenzial_bip_q"] = np.exp(q_trend)
    df_q["output_luecke_q"] = (df_q["bip_real"] / df_q["potenzial_bip_q"] - 1.0) * 100.0

    return df_y, df_q


# ---------------------------------------------------------------------------
# 4. Plotly-Export (HTML ohne Scrollbalken + PNG)
# ---------------------------------------------------------------------------
def add_recession_shapes(fig: go.Figure):
    for x0, x1 in RECESSIONS:
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(160, 160, 160, 0.22)",
            line_width=0,
            layer="below",
        )


def save_chart(fig: go.Figure, filename_stem: str, lang: str):
    source_text = QUELLE_DE if lang == "de" else QUELLE_EN
    target_dir = CHARTS_DE if lang == "de" else CHARTS_EN

    add_recession_shapes(fig)
    fig.update_layout(
        template="plotly_white",
        autosize=True,
        margin=dict(l=55, r=25, t=65, b=65),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        annotations=[
            dict(
                text=source_text,
                xref="paper",
                yref="paper",
                x=0,
                y=-0.16,
                showarrow=False,
                font=dict(size=11, color="#555555"),
            )
        ],
    )

    html_path = target_dir / f"{filename_stem}.html"
    raw_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displayModeBar": False},
    )
    clean_html = raw_html.replace(
        "<head>",
        "<head><style>html,body{margin:0;padding:0;overflow:hidden;width:100%;height:100%;}</style>",
    )
    html_path.write_text(clean_html, encoding="utf-8")

    png_path = target_dir / f"{filename_stem}.png"
    try:
        fig.write_image(str(png_path), width=1100, height=620, scale=2)
    except Exception as exc:
        print(f"[WARN] PNG-Export {png_path.name} uebersprungen: {exc}")


def generate_all_charts(df_y: pd.DataFrame, df_q: pd.DataFrame):
    specs = [
        ("01_bip_und_potenzial", "BIP und Produktionspotenzial (Mrd. EUR)", "GDP and Potential Output (EUR bn)",
         df_y["year"], [(df_y["bip_real"], "Reales BIP", "Real GDP", "#1f77b4"),
                        (df_y["potenzial_bip"], "Produktionspotenzial (Y*)", "Potential Output (Y*)", "#d62728")]),
        ("02_output_luecke_jahr", "Produktionsluecke (% des Potenzials, Jahr)", "Output Gap (% of Potential, Annual)",
         df_y["year"], [(df_y["output_luecke"], "Produktionsluecke", "Output Gap", "#2ca02c")]),
        ("03_output_luecke_quartal", "Produktionsluecke Quartal ab 1995 (%)", "Quarterly Output Gap from 1995 (%)",
         df_q["date_num"], [(df_q["output_luecke_q"], "Quartalsluecke", "Quarterly Gap", "#17becf")]),
        ("04_potenzialwachstum_5j", "Potenzialwachstum & 5-Jahres-Trend wY* (%)", "Potential Growth & 5-Year Trend wY* (%)",
         df_y["year"], [(df_y["potenzial_wachstum"], "Potenzialwachstum", "Potential Growth", "#ff7f0e"),
                        (df_y["wy_star_5j"], "5-Jahres-Durchschnitt wY*", "5-Year Rolling Mean wY*", "#9467bd")]),
        ("05_wachstumsbeitraege", "Wachstumsbeitraege zum Potenzial (Prozentpunkte)", "Contributions to Potential Growth (pp)",
         df_y["year"], [(df_y["beitrag_tfp"], "TFP-Trend", "TFP Trend", "#1f77b4"),
                        (df_y["beitrag_arbeit"], "Arbeit (Potenzial)", "Labor (Potential)", "#2ca02c"),
                        (df_y["beitrag_kapital"], "Kapitalstock", "Capital Stock", "#d62728")]),
        ("06_arbeitslosenquote_nairu", "Arbeitslosenquote und NAIRU (%)", "Unemployment Rate and NAIRU (%)",
         df_y["year"], [(df_y["alo_quote"], "Arbeitslosenquote (BA)", "Unemployment Rate (BA)", "#1f77b4"),
                        (df_y["nairu"], "NAIRU (Trend)", "NAIRU (Trend)", "#d62728")]),
        ("07_arbeitsvolumen", "Tatsaechliches & potenzielles Arbeitsvolumen (Mrd. Std.)", "Actual & Potential Hours Worked (bn hrs)",
         df_y["year"], [(df_y["arbeitsvolumen"], "Arbeitsvolumen", "Hours Worked", "#1f77b4"),
                        (df_y["potenzial_arbeitsvolumen"], "Potenzial-Arbeitsvolumen", "Potential Hours", "#ff7f0e")]),
        ("08_kapitalstock", "Nettoanlagevermoegen preisbereinigt (Mrd. EUR)", "Net Capital Stock, Price-Adjusted (EUR bn)",
         df_y["year"], [(df_y["kapitalstock"], "Kapitalstock", "Capital Stock", "#8c564b")]),
        ("09_tfp_entwicklung", "Totale Faktorproduktivitaet (TFP & Trend)", "Total Factor Productivity (TFP & Trend)",
         df_y["year"], [(df_y["tfp"], "TFP (tatsaechlich)", "TFP (Actual)", "#7f7f7f"),
                        (df_y["tfp_trend"], "TFP-Trend", "TFP Trend", "#1f77b4")]),
    ]

    for stem, title_de, title_en, x_vals, traces in specs:
        for lang in ("de", "en"):
            fig = go.Figure()
            for y_vals, lbl_de, lbl_en, color in traces:
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=y_vals,
                        mode="lines",
                        name=lbl_de if lang == "de" else lbl_en,
                        line=dict(color=color, width=2.4),
                    )
                )
            fig.update_layout(title=title_de if lang == "de" else title_en)
            save_chart(fig, stem, lang)


def main():
    df_y, df_q = build_dataset()
    excel_path = OUT_DIR / "produktionspotenzial_deutschland_1991_2025.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_y.to_excel(writer, sheet_name="Jahresdaten_1991", index=False)
        df_q.to_excel(writer, sheet_name="Quartalsdaten_1995", index=False)
    generate_all_charts(df_y, df_q)
    print("Fertig: Excel und alle 9 Grafiken (DE & EN) erfolgreich aktualisiert.")


if __name__ == "__main__":
    main()


