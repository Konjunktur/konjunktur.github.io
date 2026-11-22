#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vollständiges Update-Skript: Produktionspotenzial & Produktionslücke Deutschland (ab 1991)
- Datenabruf über die Destatis GENESIS-REST-API (www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile)
- Robuster CSV-Parser (on_bad_lines="skip", Semikolon-Trennung, Komma-Dezimalzahlen)
- Vollständige Zeitreihen ab 1991 mit Quartals-Aggregations-Fallbacks (4-Quartals-Summe / -Mittelwert)
- Einheiten-Bereinigung (Mill. EUR -> Mrd. EUR für Tabelle 81000-0031)
- Offizielle BA-Arbeitslosenquote (bezogen auf alle zivilen Erwerbspersonen)
- Trend- und Potenzialschätzung (HP-Filter, rollierender 5-Jahres-Durchschnitt wY*, Produktionsfunktion)
- Erzeugung aller 9 zweisprachigen Grafiken (DE & EN) als interaktives HTML (ohne Scrollbalken) & hochauflösendes PNG
- Durchgehende Rezessionsschattierung und einheitliche Fußzeile: Quelle: Statistisches Bundesamt | Stand: <Datum>
"""

import os
import io
import json
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from statsmodels.tsa.filters.hp_filter import hpfilter
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ==============================================================================
# 1. KONFIGURATION & KONSTANTEN
# ==============================================================================

DESTATIS_BASE_URL = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
START_YEAR = 1991
TODAY_STR = datetime.now().strftime("%d.%m.%Y")
SOURCE_FOOTER = f"Quelle: Statistisches Bundesamt | Stand: {TODAY_STR}"
SOURCE_FOOTER_EN = f"Source: Federal Statistical Office (Destatis) | As of: {TODAY_STR}"

OUTPUT_DIR = Path("output_produktionspotenzial")
HTML_DIR = OUTPUT_DIR / "html"
PNG_DIR = OUTPUT_DIR / "png"
DATA_DIR = OUTPUT_DIR / "data"

# Offizielle Rezessionsphasen Deutschland (Sachverständigenrat / Bundesbank-Datierung)
RECESSIONS = [
    (1992.75, 1993.50, "Rezession 1992/93", "Recession 1992/93"),
    (2001.25, 2003.50, "Stagnation 2001–03", "Stagnation 2001–03"),
    (2008.25, 2009.50, "Finanzkrise 2008/09", "Financial Crisis 2008/09"),
    (2020.00, 2020.50, "COVID-19 2020", "COVID-19 2020"),
    (2022.75, 2024.25, "Energie-/Industriekrise 2022–24", "Energy/Industry Crisis 2022–24"),
]

# Farbpalette (konsistent für alle 9 Grafiken)
COLORS = {
    "primary": "#1B365D",      # Dunkelblau (Ist-Werte)
    "potential": "#C0392B",    # Karmesinrot (Potenzial / Trend)
    "gap_pos": "#2E7D32",      # Grün (Überauslastung)
    "gap_neg": "#D32F2F",      # Rot (Unterauslastung)
    "accent": "#E67E22",       # Orange (Kapital / TFP)
    "teal": "#00838F",         # Petrol (Arbeit / Stunden)
    "gray": "#546E7A",         # Schiefergrau (Referenzlinien)
    "recession": "rgba(180, 190, 200, 0.28)",
}


# ==============================================================================
# 2. DESTATIS GENESIS-API CLIENT & ROBUSTER CSV-PARSER
# ==============================================================================

def get_destatis_credentials() -> Tuple[str, str]:
    """Liest Destatis-Zugangsdaten aus Umgebungsvariablen oder fragt sie interaktiv ab."""
    user = os.environ.get("DESTATIS_USER", "").strip()
    password = os.environ.get("DESTATIS_PASS", "").strip()
    if not user:
        user = input("Destatis GENESIS Benutzername (oder Token): ").strip()
    if not password and not user.startswith("token:"):
        password = getpass.getpass("Destatis GENESIS Passwort (leer lassen bei API-Token): ").strip()
    return user, password


def fetch_destatis_table(
    table_code: str,
    username: str,
    password: str,
    start_year: int = START_YEAR,
    end_year: Optional[int] = None,
    regional_key: str = "",
) -> pd.DataFrame:
    """
    Ruft eine Tabelle über den offiziellen Endpunkt
    https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile
    im CSV-Format ab und überspringt fehlerhafte Metadaten-Kopfzeilen sicher.
    """
    if end_year is None:
        end_year = datetime.now().year

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "username": username,
        "password": password,
    }
    payload = {
        "name": table_code,
        "area": "all",
        "compress": "false",
        "transpose": "false",
        "startyear": str(start_year),
        "endyear": str(end_year),
        "timeslices": "",
        "regionalvariable": "",
        "regionalkey": regional_key,
        "classifyingvariable1": "",
        "classifyingkey1": "",
        "classifyingvariable2": "",
        "classifyingkey2": "",
        "classifyingvariable3": "",
        "classifyingkey3": "",
        "job": "false",
        "stand": "01.01.1970",
        "language": "de",
        "format": "ffcsv",
    }

    response = requests.post(DESTATIS_BASE_URL, headers=headers, data=payload, timeout=60)
    response.raise_for_status()

    raw_text = response.content.decode("utf-8-sig", errors="replace")
    if "Fehler" in raw_text[:300] and ";" not in raw_text[:300]:
        raise RuntimeError(f"Destatis-API meldet Fehler für Tabelle {table_code}: {raw_text[:250]}")

    df = pd.read_csv(
        io.StringIO(raw_text),
        sep=";",
        decimal=",",
        thousands=".",
        on_bad_lines="skip",
        engine="python",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_german_number(series: pd.Series) -> pd.Series:
    """Konvertiert deutsche Zahlenstrings (inkl. '-', '.', 'x', '/') sauber in float."""
    cleaned = (
        series.astype(str)
        .str.strip()
        .replace({"-": np.nan, ".": np.nan, "...": np.nan, "x": np.nan, "/": np.nan, "nan": np.nan, "": np.nan})
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


# ==============================================================================
# 3. AGGREGATIONS-FALLBACKS & DATENAUFBEREITUNG AB 1991
# ==============================================================================

def annualize_from_quarters(
    df_q: pd.DataFrame,
    year_col: str,
    quarter_col: str,
    value_col: str,
    method: str = "sum",
) -> pd.Series:
    """
    Aggregiert Quartalsdaten auf Jahreswerte, sobald alle 4 Quartale vorliegen
    (4-Quartals-Summe für Stromgrößen wie BIP/Arbeitsvolumen; 4-Quartals-Mittelwert für Bestandsgrößen).
    """
    sub = df_q[[year_col, quarter_col, value_col]].dropna().copy()
    sub[year_col] = pd.to_numeric(sub[year_col], errors="coerce").astype("Int64")
    counts = sub.groupby(year_col)[value_col].count()
    complete_years = counts[counts == 4].index

    sub_complete = sub[sub[year_col].isin(complete_years)]
    if method == "sum":
        return sub_complete.groupby(year_col)[value_col].sum()
    return sub_complete.groupby(year_col)[value_col].mean()


def merge_annual_with_quarterly_fallback(
    annual_series: pd.Series,
    quarterly_fallback: pd.Series,
    years: pd.Index,
) -> pd.Series:
    """Ergänzt fehlende Jahreswerte (z. B. aktuelles Jahr) über vollständige 4-Quartals-Aggregate."""
    out = annual_series.reindex(years).copy()
    missing = out.isna()
    out.loc[missing] = quarterly_fallback.reindex(years).loc[missing]
    return out


def rolling_5y_potential_growth(series: pd.Series) -> pd.Series:
    """Berechnet das rollierende 5-Jahres-Mittel der Potenzialwachstumsrate (wY*)."""
    growth = series.pct_change() * 100.0
    return growth.rolling(window=5, min_periods=3).mean()


def build_data(use_api: bool = True) -> dict:
    """
    Erzeugt den vollständigen, geprüften Datensatz für alle 9 Grafiken ab 1991.
    Führt Einheiten-Umrechnungen (81000-0031: Mill. EUR -> Mrd. EUR),
    Quartals-Fallbacks, HP-Filter-Zerlegung und Produktionsfunktions-Beiträge zusammen.
    """
    years = pd.Index(range(START_YEAR, datetime.now().year + 1), name="Jahr")
    df = pd.DataFrame(index=years)

    if use_api:
        user, pwd = get_destatis_credentials()
        # 81000-0001: Bruttoinlandsprodukt (preisbereinigt, Kettenindex & Mrd. EUR)
        raw_bip = fetch_destatis_table("81000-0001", user, pwd, start_year=START_YEAR)
        # 81000-0015: BIP & Erwerbstätige / Arbeitsvolumen (Quartale & Jahre)
        raw_et = fetch_destatis_table("81000-0015", user, pwd, start_year=START_YEAR)
        # 81000-0031: Anlagevermögen / Kapitalstock (in Mill. EUR -> Umrechnung in Mrd. EUR)
        raw_cap = fetch_destatis_table("81000-0031", user, pwd, start_year=START_YEAR)
        # 13211-0001: Offizielle Arbeitslosenquote (BA, bez. auf alle zivilen Erwerbspersonen)
        raw_alq = fetch_destatis_table("13211-0001", user, pwd, start_year=START_YEAR)

        df = _extract_destatis_series(df, raw_bip, raw_et, raw_cap, raw_alq)
    else:
        raise ValueError("use_api=False ist nur für interne Tests zulässig.")

    # Einheiten-Check: Tabelle 81000-0031 liefert Mill. EUR -> konsequent in Mrd. EUR umrechnen
    if df["kapitalstock_mrd"].median() > 50_000:
        df["kapitalstock_mrd"] = df["kapitalstock_mrd"] / 1000.0

    # Produktionsfunktion (Cobb-Douglas mit Lohnquote alpha = 0.65, Kapitalelastizität 1 - alpha = 0.35)
    alpha = 0.65
    df["arbeitsvolumen_mrd_std"] = (df["erwerbstaetige_tsd"] * df["arbeitszeit_std"]) / 1_000_000.0
    df["stundenproduktivitaet"] = (df["bip_real_mrd"] * 1000.0) / df["arbeitsvolumen_mrd_std"]

    # Trend-Komponenten via Hodrick-Prescott-Filter (lambda = 100 für Jahresdaten)
    for col, trend_col in [
        ("bip_real_mrd", "bip_potenzial_mrd"),
        ("erwerbspersonen_tsd", "erwerbspersonen_pot_tsd"),
        ("arbeitszeit_std", "arbeitszeit_pot_std"),
        ("alq_ba_pct", "nairu_pct"),
        ("kapitalstock_mrd", "kapitalstock_pot_mrd"),
    ]:
        valid = df[col].dropna()
        _, trend = hpfilter(np.log(valid), lamb=100) if col != "alq_ba_pct" else hpfilter(valid, lamb=100)
        df[trend_col] = np.exp(trend) if col != "alq_ba_pct" else trend

    # Solow-Residuum (Totale Faktorproduktivität, TFP) & TFP-Trend
    ln_tfp = (
        np.log(df["bip_real_mrd"])
        - alpha * np.log(df["arbeitsvolumen_mrd_std"])
        - (1.0 - alpha) * np.log(df["kapitalstock_mrd"])
    )
    valid_tfp = ln_tfp.dropna()
    _, ln_tfp_trend = hpfilter(valid_tfp, lamb=100)
    df["tfp_index"] = np.exp(valid_tfp - valid_tfp.iloc[0]) * 100.0
    df["tfp_pot_index"] = np.exp(ln_tfp_trend - valid_tfp.iloc[0]) * 100.0

    # Produktionspotenzial auf Basis der Produktionsfunktion (Y*)
    pot_erwerbstaetige = df["erwerbspersonen_pot_tsd"] * (1.0 - df["nairu_pct"] / 100.0)
    pot_arbeitsvolumen = (pot_erwerbstaetige * df["arbeitszeit_pot_std"]) / 1_000_000.0
    df["potenzial_pf_mrd"] = (
        np.exp(ln_tfp_trend)
        * (pot_arbeitsvolumen ** alpha)
        * (df["kapitalstock_pot_mrd"] ** (1.0 - alpha))
    )

    # Produktionslücke in % des Produktionspotenzials
    df["produktionsluecke_pct"] = (
        (df["bip_real_mrd"] - df["potenzial_pf_mrd"]) / df["potenzial_pf_mrd"]
    ) * 100.0

    # Potenzialwachstum (wY*) und rollierender 5-Jahres-Durchschnitt
    df["potenzialwachstum_pct"] = df["potenzial_pf_mrd"].pct_change() * 100.0
    df["potenzialwachstum_5j_pct"] = rolling_5y_potential_growth(df["potenzial_pf_mrd"])

    # Wachstumsbeiträge zum Potenzialwachstum (in Prozentpunkten)
    df["beitrag_tfp_pp"] = ln_tfp_trend.diff() * 100.0
    df["beitrag_arbeit_pp"] = alpha * np.log(pot_arbeitsvolumen).diff() * 100.0
    df["beitrag_kapital_pp"] = (1.0 - alpha) * np.log(df["kapitalstock_pot_mrd"]).diff() * 100.0

    # Arbeitsmarkt-Komponenten (Erwerbspersonenpotenzial-Beiträge)
    df["erwerbsquote_pct"] = (df["erwerbspersonen_tsd"] / df["bevoelkerung_15_64_tsd"]) * 100.0
    _, eq_trend = hpfilter(df["erwerbsquote_pct"].dropna(), lamb=100)
    df["erwerbsquote_pot_pct"] = eq_trend

    df = df.dropna(subset=["bip_real_mrd"]).copy()

    return {
        "df": df,
        "meta": {
            "start_year": int(df.index.min()),
            "end_year": int(df.index.max()),
            "stand": TODAY_STR,
            "source_de": SOURCE_FOOTER,
            "source_en": SOURCE_FOOTER_EN,
        },
    }


def _extract_destatis_series(
    df: pd.DataFrame,
    raw_bip: pd.DataFrame,
    raw_et: pd.DataFrame,
    raw_cap: pd.DataFrame,
    raw_alq: pd.DataFrame,
) -> pd.DataFrame:
    """Mappt die bereinigten Destatis-GENESIS-Tabellen auf das einheitliche Jahres-DataFrame ab 1991."""
    def _extract_col(raw: pd.DataFrame, code_filter: str, value_col: str = "value") -> pd.Series:
        sub = raw.copy()
        if "value_variable_code" in sub.columns and code_filter:
            sub = sub[sub["value_variable_code"].astype(str).str.contains(code_filter, na=False)]
        time_col = "time" if "time" in sub.columns else sub.columns[0]
        val_col = value_col if value_col in sub.columns else sub.columns[-1]
        sub["Jahr"] = pd.to_numeric(sub[time_col].astype(str).str.slice(0, 4), errors="coerce")
        sub["val"] = parse_german_number(sub[val_col])
        annual = sub[sub[time_col].astype(str).str.len() == 4].groupby("Jahr")["val"].first()
        quarterly = sub[sub[time_col].astype(str).str.contains("Q", na=False)].copy()
        if not quarterly.empty:
            quarterly["Q"] = quarterly[time_col].astype(str).str.extract(r"(Q[1-4])")[0]
            q_agg = annualize_from_quarters(quarterly, "Jahr", "Q", "val", method="sum")
            return merge_annual_with_quarterly_fallback(annual, q_agg, df.index)
        return annual.reindex(df.index)

    df["bip_real_mrd"] = _extract_col(raw_bip, "BIP")
    df["erwerbstaetige_tsd"] = _extract_col(raw_et, "ERW")
    df["arbeitszeit_std"] = _extract_col(raw_et, "ARBZ")
    df["kapitalstock_mrd"] = _extract_col(raw_cap, "ANLV")
    df["alq_ba_pct"] = _extract_col(raw_alq, "ALQ")
    df["erwerbspersonen_tsd"] = df["erwerbstaetige_tsd"] / (1.0 - df["alq_ba_pct"] / 100.0)
    df["bevoelkerung_15_64_tsd"] = _extract_col(raw_et, "BEV")
    return df


# ==============================================================================
# 4. LAYOUT-HELFER & EXPORT OHNE SCROLLBALKEN (HTML + PNG)
# ==============================================================================

def apply_standard_layout(
    fig: go.Figure,
    title: str,
    subtitle: str,
    yaxis_title: str,
    lang: str = "de",
    height: int = 560,
) -> go.Figure:
    """Wendet einheitliches Design, durchgehende Rezessionsschattierung und Quellen-Fußzeile an."""
    footer_text = SOURCE_FOOTER if lang == "de" else SOURCE_FOOTER_EN

    for x0, x1, label_de, label_en in RECESSIONS:
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=COLORS["recession"],
            opacity=1.0,
            layer="below",
            line_width=0,
        )

    fig.update_layout(
        template="plotly_white",
        autosize=True,
        height=height,
        margin=dict(l=65, r=35, t=95, b=85),
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:13px;color:#546E7A;'>{subtitle}</span>",
            x=0.01,
            xanchor="left",
            font=dict(size=18, color="#1B365D"),
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(size=13, color="#263238")),
            gridcolor="#ECEFF1",
            zerolinecolor="#B0BEC5",
        ),
        xaxis=dict(
            gridcolor="#F5F7F8",
            dtick=2,
            tickangle=0,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(255,255,255,0.85)",
        ),
        annotations=[
            dict(
                text=footer_text,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.16,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font=dict(size=11, color="#546E7A"),
            )
        ],
    )
    return fig


def save_chart_both_languages(
    fig_de: go.Figure,
    fig_en: go.Figure,
    slug: str,
) -> None:
    """
    Speichert jede Grafik als responsives HTML (ohne Scrollbalken dank overflow:hidden & responsive=True)
    sowie als hochauflösendes PNG (1280x680, scale=2).
    """
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)

    no_scroll_css = (
        "<style>"
        "html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }"
        ".plotly-graph-div { width: 100% !important; height: 100vh !important; }"
        "</style>"
    )

    for suffix, fig in [("de", fig_de), ("en", fig_en)]:
        html_path = HTML_DIR / f"{slug}_{suffix}.html"
        png_path = PNG_DIR / f"{slug}_{suffix}.png"

        raw_html = fig.to_html(
            include_plotlyjs="cdn",
            full_html=True,
            config={"responsive": True, "displaylogo": False},
        )
        clean_html = raw_html.replace("</head>", f"{no_scroll_css}</head>")
        html_path.write_text(clean_html, encoding="utf-8")

        fig.write_image(str(png_path), width=1280, height=680, scale=2)


# ==============================================================================
# 5. ALLE 9 GRAFIKEN (DEUTSCH & ENGLISCH)
# ==============================================================================

def generate_all_9_charts(data: dict) -> List[str]:
    """Erzeugt alle 9 zweisprachigen Grafiken und gibt die Liste der erzeugten Dateien zurück."""
    df: pd.DataFrame = data["df"]
    x = df.index.tolist()
    created: List[str] = []

    # --- Grafik 1: Reales BIP vs. Produktionspotenzial (Mrd. EUR) ---
    for lang, slug in [("de", "01_bip_vs_potenzial"), ("en", "01_bip_vs_potenzial")]:
        pass
    fig1_de = go.Figure()
    fig1_de.add_trace(go.Scatter(x=x, y=df["bip_real_mrd"], name="Reales BIP (Ist)", line=dict(color=COLORS["primary"], width=3)))
    fig1_de.add_trace(go.Scatter(x=x, y=df["potenzial_pf_mrd"], name="Produktionspotenzial (Y*)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig1_de, "1. Reales Bruttoinlandsprodukt und Produktionspotenzial", "Deutschland, preisbereinigt in Mrd. EUR, ab 1991", "Mrd. EUR", "de")

    fig1_en = go.Figure()
    fig1_en.add_trace(go.Scatter(x=x, y=df["bip_real_mrd"], name="Real GDP (Actual)", line=dict(color=COLORS["primary"], width=3)))
    fig1_en.add_trace(go.Scatter(x=x, y=df["potenzial_pf_mrd"], name="Potential Output (Y*)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig1_en, "1. Real Gross Domestic Product and Potential Output", "Germany, price-adjusted in EUR billion, since 1991", "EUR billion", "en")
    save_chart_both_languages(fig1_de, fig1_en, "01_bip_vs_potenzial")
    created.append("01_bip_vs_potenzial")

    # --- Grafik 2: Produktionslücke in % des Produktionspotenzials ---
    bar_colors = [COLORS["gap_pos"] if v >= 0 else COLORS["gap_neg"] for v in df["produktionsluecke_pct"]]
    fig2_de = go.Figure(go.Bar(x=x, y=df["produktionsluecke_pct"], marker_color=bar_colors, name="Produktionslücke"))
    fig2_de.add_hline(y=0, line_color=COLORS["gray"], line_width=1.5)
    apply_standard_layout(fig2_de, "2. Gesamtwirtschaftliche Produktionslücke", "Abweichung des realen BIP vom Produktionspotenzial in %", "Prozent (%)", "de")

    fig2_en = go.Figure(go.Bar(x=x, y=df["produktionsluecke_pct"], marker_color=bar_colors, name="Output Gap"))
    fig2_en.add_hline(y=0, line_color=COLORS["gray"], line_width=1.5)
    apply_standard_layout(fig2_en, "2. Macroeconomic Output Gap", "Deviation of real GDP from potential output in %", "Percent (%)", "en")
    save_chart_both_languages(fig2_de, fig2_en, "02_produktionsluecke")
    created.append("02_produktionsluecke")

    # --- Grafik 3: Potenzialwachstum (wY*) & rollierender 5-Jahres-Durchschnitt ---
    fig3_de = go.Figure()
    fig3_de.add_trace(go.Bar(x=x, y=df["potenzialwachstum_pct"], name="Potenzialwachstum (jährlich)", marker_color="rgba(27,54,93,0.35)"))
    fig3_de.add_trace(go.Scatter(x=x, y=df["potenzialwachstum_5j_pct"], name="5-Jahres-Durchschnitt (rollierend)", line=dict(color=COLORS["potential"], width=3)))
    apply_standard_layout(fig3_de, "3. Wachstumsrate des Produktionspotenzials (wY*)", "Jährliche Veränderungsrate und rollierendes 5-Jahres-Mittel in %", "Prozent (%)", "de")

    fig3_en = go.Figure()
    fig3_en.add_trace(go.Bar(x=x, y=df["potenzialwachstum_pct"], name="Potential Growth (annual)", marker_color="rgba(27,54,93,0.35)"))
    fig3_en.add_trace(go.Scatter(x=x, y=df["potenzialwachstum_5j_pct"], name="5-Year Rolling Average", line=dict(color=COLORS["potential"], width=3)))
    apply_standard_layout(fig3_en, "3. Potential Output Growth Rate (wY*)", "Annual rate of change and rolling 5-year average in %", "Percent (%)", "en")
    save_chart_both_languages(fig3_de, fig3_en, "03_potenzialwachstum")
    created.append("03_potenzialwachstum")

    # --- Grafik 4: Wachstumsbeiträge zum Potenzialwachstum (Arbeit, Kapital, TFP) ---
    fig4_de = go.Figure()
    fig4_de.add_trace(go.Bar(x=x, y=df["beitrag_arbeit_pp"], name="Arbeit (Prozentpunkte)", marker_color=COLORS["teal"]))
    fig4_de.add_trace(go.Bar(x=x, y=df["beitrag_kapital_pp"], name="Kapitalstock (Prozentpunkte)", marker_color=COLORS["accent"]))
    fig4_de.add_trace(go.Bar(x=x, y=df["beitrag_tfp_pp"], name="TFP (Prozentpunkte)", marker_color=COLORS["primary"]))
    fig4_de.add_trace(go.Scatter(x=x, y=df["potenzialwachstum_pct"], name="Potenzialwachstum gesamt (%)", line=dict(color=COLORS["potential"], width=2.5)))
    fig4_de.update_layout(barmode="relative")
    apply_standard_layout(fig4_de, "4. Wachstumsbeiträge zum Produktionspotenzial", "Zerlegung nach Arbeit, Kapital und Totaler Faktorproduktivität (TFP)", "Prozentpunkte / %", "de")

    fig4_en = go.Figure()
    fig4_en.add_trace(go.Bar(x=x, y=df["beitrag_arbeit_pp"], name="Labor (pp)", marker_color=COLORS["teal"]))
    fig4_en.add_trace(go.Bar(x=x, y=df["beitrag_kapital_pp"], name="Capital Stock (pp)", marker_color=COLORS["accent"]))
    fig4_en.add_trace(go.Bar(x=x, y=df["beitrag_tfp_pp"], name="TFP (pp)", marker_color=COLORS["primary"]))
    fig4_en.add_trace(go.Scatter(x=x, y=df["potenzialwachstum_pct"], name="Total Potential Growth (%)", line=dict(color=COLORS["potential"], width=2.5)))
    fig4_en.update_layout(barmode="relative")
    apply_standard_layout(fig4_en, "4. Growth Contributions to Potential Output", "Decomposition into labor, capital, and total factor productivity (TFP)", "Percentage points / %", "en")
    save_chart_both_languages(fig4_de, fig4_en, "04_wachstumsbeitraege")
    created.append("04_wachstumsbeitraege")

    # --- Grafik 5: Arbeitsvolumen (Ist vs. Potenzial in Mrd. Stunden) ---
    pot_av = (df["erwerbspersonen_pot_tsd"] * (1.0 - df["nairu_pct"] / 100.0) * df["arbeitszeit_pot_std"]) / 1_000_000.0
    fig5_de = go.Figure()
    fig5_de.add_trace(go.Scatter(x=x, y=df["arbeitsvolumen_mrd_std"], name="Arbeitsvolumen (Ist)", line=dict(color=COLORS["teal"], width=3)))
    fig5_de.add_trace(go.Scatter(x=x, y=pot_av, name="Potenzial-Arbeitsvolumen", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig5_de, "5. Gesamtwirtschaftliches Arbeitsvolumen", "Geleistete Arbeitsstunden und Potenzialpfad in Mrd. Stunden", "Mrd. Stunden", "de")

    fig5_en = go.Figure()
    fig5_en.add_trace(go.Scatter(x=x, y=df["arbeitsvolumen_mrd_std"], name="Total Hours Worked (Actual)", line=dict(color=COLORS["teal"], width=3)))
    fig5_en.add_trace(go.Scatter(x=x, y=pot_av, name="Potential Hours Worked", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig5_en, "5. Aggregate Hours Worked", "Actual hours worked and potential path in billion hours", "Billion hours", "en")
    save_chart_both_languages(fig5_de, fig5_en, "05_arbeitsvolumen")
    created.append("05_arbeitsvolumen")

    # --- Grafik 6: Offizielle BA-Arbeitslosenquote vs. NAIRU ---
    fig6_de = go.Figure()
    fig6_de.add_trace(go.Scatter(x=x, y=df["alq_ba_pct"], name="Arbeitslosenquote (BA, alle ziv. EP)", line=dict(color=COLORS["primary"], width=3)))
    fig6_de.add_trace(go.Scatter(x=x, y=df["nairu_pct"], name="Strukturelle Arbeitslosenquote (NAIRU)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig6_de, "6. Arbeitslosenquote und strukturelle Arbeitslosigkeit (NAIRU)", "Offizielle BA-Quote (bezogen auf alle zivilen Erwerbspersonen) in %", "Prozent (%)", "de")

    fig6_en = go.Figure()
    fig6_en.add_trace(go.Scatter(x=x, y=df["alq_ba_pct"], name="Unemployment Rate (BA, all civilian LF)", line=dict(color=COLORS["primary"], width=3)))
    fig6_en.add_trace(go.Scatter(x=x, y=df["nairu_pct"], name="Structural Unemployment Rate (NAIRU)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    apply_standard_layout(fig6_en, "6. Unemployment Rate and Structural Unemployment (NAIRU)", "Official BA rate (all civilian labor force) in %", "Percent (%)", "en")
    save_chart_both_languages(fig6_de, fig6_en, "06_arbeitslosigkeit_nairu")
    created.append("06_arbeitslosigkeit_nairu")

    # --- Grafik 7: Erwerbsquote und Arbeitszeit je Erwerbstätigen ---
    fig7_de = make_subplots(specs=[[{"secondary_y": True}]])
    fig7_de.add_trace(go.Scatter(x=x, y=df["erwerbsquote_pct"], name="Erwerbsquote (%)", line=dict(color=COLORS["primary"], width=3)), secondary_y=False)
    fig7_de.add_trace(go.Scatter(x=x, y=df["arbeitszeit_std"], name="Arbeitszeit je ET (Std.)", line=dict(color=COLORS["accent"], width=3)), secondary_y=True)
    apply_standard_layout(fig7_de, "7. Erwerbsbeteiligung und durchschnittliche Arbeitszeit", "Erwerbsquote (15–64 Jahre, %) und Jahresarbeitszeit je Erwerbstätigen (Std.)", "Erwerbsquote (%)", "de")
    fig7_de.update_yaxes(title_text="Stunden je Erwerbstätigen", secondary_y=True)

    fig7_en = make_subplots(specs=[[{"secondary_y": True}]])
    fig7_en.add_trace(go.Scatter(x=x, y=df["erwerbsquote_pct"], name="Participation Rate (%)", line=dict(color=COLORS["primary"], width=3)), secondary_y=False)
    fig7_en.add_trace(go.Scatter(x=x, y=df["arbeitszeit_std"], name="Hours per Worker", line=dict(color=COLORS["accent"], width=3)), secondary_y=True)
    apply_standard_layout(fig7_en, "7. Labor Force Participation and Average Hours Worked", "Participation rate (aged 15–64, %) and annual hours per worker", "Participation rate (%)", "en")
    fig7_en.update_yaxes(title_text="Hours per worker", secondary_y=True)
    save_chart_both_languages(fig7_de, fig7_en, "07_erwerbsquote_arbeitszeit")
    created.append("07_erwerbsquote_arbeitszeit")

    # --- Grafik 8: Kapitalstock (Bruttoanlagevermögen in Mrd. EUR) ---
    fig8_de = go.Figure()
    fig8_de.add_trace(go.Scatter(x=x, y=df["kapitalstock_mrd"], name="Kapitalstock (Ist, Mrd. EUR)", line=dict(color=COLORS["accent"], width=3)))
    fig8_de.add_trace(go.Scatter(x=x, y=df["kapitalstock_pot_mrd"], name="Kapitalstock-Trend", line=dict(color=COLORS["potential"], width=2.5, dash="dash")))
    apply_standard_layout(fig8_de, "8. Gesamtwirtschaftlicher Kapitalstock", "Preisbereinigtes Anlagevermögen in Mrd. EUR (Destatis 81000-0031)", "Mrd. EUR", "de")

    fig8_en = go.Figure()
    fig8_en.add_trace(go.Scatter(x=x, y=df["kapitalstock_mrd"], name="Capital Stock (Actual, EUR bn)", line=dict(color=COLORS["accent"], width=3)))
    fig8_en.add_trace(go.Scatter(x=x, y=df["kapitalstock_pot_mrd"], name="Capital Stock Trend", line=dict(color=COLORS["potential"], width=2.5, dash="dash")))
    apply_standard_layout(fig8_en, "8. Aggregate Capital Stock", "Price-adjusted fixed assets in EUR billion (Destatis 81000-0031)", "EUR billion", "en")
    save_chart_both_languages(fig8_de, fig8_en, "08_kapitalstock")
    created.append("08_kapitalstock")

    # --- Grafik 9: Totale Faktorproduktivität (TFP) & Stundenproduktivität ---
    prod_idx = (df["stundenproduktivitaet"] / df["stundenproduktivitaet"].iloc[0]) * 100.0
    fig9_de = go.Figure()
    fig9_de.add_trace(go.Scatter(x=x, y=df["tfp_index"], name="TFP (Ist, 1991=100)", line=dict(color=COLORS["primary"], width=3)))
    fig9_de.add_trace(go.Scatter(x=x, y=df["tfp_pot_index"], name="TFP-Trend (1991=100)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    fig9_de.add_trace(go.Scatter(x=x, y=prod_idx, name="Stundenproduktivität (1991=100)", line=dict(color=COLORS["teal"], width=2.5)))
    apply_standard_layout(fig9_de, "9. Totale Faktorproduktivität (TFP) und Stundenproduktivität", "Index 1991 = 100, Deutschland", "Index (1991 = 100)", "de")

    fig9_en = go.Figure()
    fig9_en.add_trace(go.Scatter(x=x, y=df["tfp_index"], name="TFP (Actual, 1991=100)", line=dict(color=COLORS["primary"], width=3)))
    fig9_en.add_trace(go.Scatter(x=x, y=df["tfp_pot_index"], name="TFP Trend (1991=100)", line=dict(color=COLORS["potential"], width=3, dash="dash")))
    fig9_en.add_trace(go.Scatter(x=x, y=prod_idx, name="Hourly Labor Productivity (1991=100)", line=dict(color=COLORS["teal"], width=2.5)))
    apply_standard_layout(fig9_en, "9. Total Factor Productivity (TFP) and Hourly Productivity", "Index 1991 = 100, Germany", "Index (1991 = 100)", "en")
    save_chart_both_languages(fig9_de, fig9_en, "09_tfp_produktivitaet")
    created.append("09_tfp_produktivitaet")

    return created


# ==============================================================================
# 6. HAUPTPROGRAMM
# ==============================================================================

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("Starte Aktualisierung der Daten über Destatis GENESIS-API ...")
    data = build_data(use_api=True)

    df: pd.DataFrame = data["df"]
    csv_out = DATA_DIR / "produktionspotenzial_zeitreihen_ab_1991.csv"
    df.to_csv(csv_out, sep=";", decimal=",", encoding="utf-8-sig")

    charts = generate_all_9_charts(data)
    print(f"Erfolgreich abgeschlossen. {len(charts)} zweisprachige Grafiken (HTML + PNG) erstellt in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

