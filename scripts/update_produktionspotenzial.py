#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (Deutsch & Englisch, .png & .html) fuer die Rubrik
'Produktionspotenzial nach der Methode von Claus Koehler' auf konjunktur.github.io.
Datenbasis: Ausschliesslich Statistisches Bundesamt (GENESIS-Online) ab 1991.
"""

import io
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

DESTATIS_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
OUT_DIR = Path("static/produktionspotenzial")

SVR_PHASES_Y = [(1992, 1993), (2001, 2003), (2008, 2009), (2020, 2020), (2022, 2025)]
SVR_PHASES_Q = [
    ("1992-Q1", "1993-Q2"),
    ("2001-Q1", "2003-Q2"),
    ("2008-Q2", "2009-Q2"),
    ("2020-Q1", "2020-Q2"),
    ("2022-Q4", "2025-Q1"),
]


def fetch_destatis_table(table_code: str, start_year: int = 1991) -> pd.DataFrame:
    user = os.environ.get("DESTATIS_USER", "").strip()
    pw = os.environ.get("DESTATIS_PASS", "").strip()
    if not user or not pw:
        raise RuntimeError("DESTATIS_USER / DESTATIS_PASS fehlen in den Environment-Variablen.")
    params = {
        "username": user,
        "password": pw,
        "name": table_code,
        "area": "all",
        "compress": "false",
        "transpose": "false",
        "startyear": str(start_year),
        "endyear": str(datetime.now().year),
        "format": "ffcsv",
        "language": "de",
    }
    resp = requests.get(DESTATIS_BASE, params=params, timeout=60)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig", errors="replace")
    df = pd.read_csv(io.StringIO(text), sep=";", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _extract_annual(df: pd.DataFrame, must_have: list[str], exclude: list[str] | None = None,
                    min_val: float | None = None, max_val: float | None = None) -> pd.Series:
    exclude = exclude or []
    sub = df.copy()
    sub["val"] = _to_num(sub["value"])
    sub = sub[sub["val"].notna()]
    meta = sub.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    for kw in must_have:
        sub = sub[meta.loc[sub.index].str.contains(kw.lower(), regex=False)]
    for kw in exclude:
        sub = sub[~meta.loc[sub.index].str.contains(kw.lower(), regex=False)]
    if min_val is not None:
        sub = sub[sub["val"] >= min_val]
    if max_val is not None:
        sub = sub[sub["val"] <= max_val]
    if "1_variable_attribute_code" in sub.columns:
        insg = sub[sub["1_variable_attribute_code"].isin(["INSGESAMT", "WZ08-A-U", ""])]
        if len(insg) >= 10:
            sub = insg
    sub["yr"] = pd.to_numeric(sub["time"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    sub = sub[sub["yr"].between(1991, datetime.now().year)]
    ser = sub.groupby("yr")["val"].median().sort_index()
    ser.index = ser.index.astype(int)
    return ser


def _extract_quarterly(df: pd.DataFrame, must_have: list[str], exclude: list[str] | None = None,
                       min_val: float | None = None, max_val: float | None = None) -> pd.Series:
    exclude = exclude or []
    sub = df.copy()
    sub["val"] = _to_num(sub["value"])
    sub = sub[sub["val"].notna()]
    meta = sub.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    for kw in must_have:
        sub = sub[meta.loc[sub.index].str.contains(kw.lower(), regex=False)]
    for kw in exclude:
        sub = sub[~meta.loc[sub.index].str.contains(kw.lower(), regex=False)]
    if min_val is not None:
        sub = sub[sub["val"] >= min_val]
    if max_val is not None:
        sub = sub[sub["val"] <= max_val]
    if "1_variable_attribute_code" in sub.columns:
        insg = sub[sub["1_variable_attribute_code"].isin(["INSGESAMT", "WZ08-A-U", ""])]
        if len(insg) >= 20:
            sub = insg
    q_match = sub["time_attribute_label"].astype(str).str.extract(r"([1-4])\.\s*Quartal")[0]
    if q_match.isna().all():
        q_match = sub["time_attribute_code"].astype(str).str.extract(r"QUART0([1-4])")[0]
    yr = sub["time"].astype(str).str.extract(r"(\d{4})")[0]
    sub["q_key"] = yr + "-Q" + q_match
    sub = sub[sub["q_key"].notna()]
    ser = sub.groupby("q_key")["val"].median().sort_index()
    return ser


def _extract_monthly_alq(df: pd.DataFrame) -> pd.Series:
    sub = df.copy()
    sub["val"] = _to_num(sub["value"])
    sub = sub[sub["val"].notna() & sub["val"].between(1.0, 25.0)]
    meta = sub.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    # Offizielle BA-Quote bezogen auf alle zivilen Erwerbspersonen
    sub = sub[meta.str.contains("arbeitslosenquote", regex=False)]
    alle = sub[meta.loc[sub.index].str.contains("alle zivilen", regex=False)]
    if len(alle) >= 12:
        sub = alle
    else:
        sub = sub[~meta.loc[sub.index].str.contains("abhängige", regex=False)]
    m_match = sub["time_attribute_code"].astype(str).str.extract(r"MONAT(\d{2})")[0]
    yr = sub["time"].astype(str).str.extract(r"(\d{4})")[0]
    sub["m_key"] = yr + "-" + m_match
    sub = sub[sub["m_key"].notna()]
    return sub.groupby("m_key")["val"].min().sort_index()


def _extract_monthly_alo(df: pd.DataFrame) -> pd.Series:
    sub = df.copy()
    sub["val"] = _to_num(sub["value"])
    sub = sub[sub["val"].notna() & sub["val"].between(1_000_000, 7_000_000)]
    meta = sub.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    sub = sub[meta.str.contains("arbeitslose", regex=False) & ~meta.str.contains("quote", regex=False)]
    m_match = sub["time_attribute_code"].astype(str).str.extract(r"MONAT(\d{2})")[0]
    yr = sub["time"].astype(str).str.extract(r"(\d{4})")[0]
    sub["m_key"] = yr + "-" + m_match
    sub = sub[sub["m_key"].notna()]
    return sub.groupby("m_key")["val"].median().sort_index() / 1_000.0  # in Tsd.


def load_all_macro_data() -> dict:
    t_bip_y = fetch_destatis_table("81000-0001", 1991)
    t_bip_q = fetch_destatis_table("81000-0002", 1991)
    t_et_y = fetch_destatis_table("81000-0011", 1991)
    t_et_q = fetch_destatis_table("81000-0012", 1991)
    t_fin = fetch_destatis_table("81000-0031", 1991)
    t_alo_y = fetch_destatis_table("13211-0001", 1991)
    t_alo_m = fetch_destatis_table("13211-0002", 2005)

    bip_real_q = _extract_quarterly(t_bip_q, ["bruttoinlandsprodukt", "preisbereinigt", "original"], min_val=400, max_val=1500)
    bip_nom_q = _extract_quarterly(t_bip_q, ["bruttoinlandsprodukt", "jeweiligen preisen", "original"], min_val=300, max_val=1600)
    bip_real_y = _extract_annual(t_bip_y, ["bruttoinlandsprodukt", "preisbereinigt"], min_val=2000, max_val=5500)
    bip_nom_y = _extract_annual(t_bip_y, ["bruttoinlandsprodukt", "jeweiligen preisen"], min_val=1400, max_val=6000)

    # Abgeschlossene Jahre aus Quartalssumme absichern
    for yr in range(1991, datetime.now().year):
        qs = [f"{yr}-Q{q}" for q in (1, 2, 3, 4)]
        if yr not in bip_real_y.index and all(q in bip_real_q.index for q in qs):
            bip_real_y.loc[yr] = bip_real_q.loc[qs].sum()
        if yr not in bip_nom_y.index and all(q in bip_nom_q.index for q in qs):
            bip_nom_y.loc[yr] = bip_nom_q.loc[qs].sum()
    bip_real_y = bip_real_y.sort_index()
    bip_nom_y = bip_nom_y.sort_index()

    et_q = _extract_quarterly(t_et_q, ["erwerbstätige", "inland", "original"], min_val=34000, max_val=50000)
    et_y = _extract_annual(t_et_y, ["erwerbstätige", "inland"], min_val=34000, max_val=50000)
    for yr in range(1991, datetime.now().year):
        qs = [f"{yr}-Q{q}" for q in (1, 2, 3, 4)]
        if yr not in et_y.index and all(q in et_q.index for q in qs):
            et_y.loc[yr] = et_q.loc[qs].mean()
    et_y = et_y.sort_index()

    alo_y_hist = _extract_annual(t_alo_y, ["arbeitslose"], exclude=["quote"], min_val=1_500_000, max_val=6_000_000) / 1_000.0
    alo_m = _extract_monthly_alo(t_alo_m)
    alq_m = _extract_monthly_alq(t_alo_m)

    # Jahresmittel aus Monatswerten ab 2005
    alo_y = alo_y_hist.copy()
    for yr in range(2005, datetime.now().year + 1):
        ms = [f"{yr}-{m:02d}" for m in range(1, 13) if f"{yr}-{m:02d}" in alo_m.index]
        if len(ms) == 12:
            alo_y.loc[yr] = alo_m.loc[ms].mean()
    alo_y = alo_y.sort_index()

    # Quartalsmittel aus Monatswerten
    alo_q_dict = {}
    for q_key in bip_real_q.index:
        yr_s, q_s = q_key.split("-Q")
        q_i = int(q_s)
        ms = [f"{yr_s}-{m:02d}" for m in range((q_i - 1) * 3 + 1, q_i * 3 + 1)]
        if all(m in alo_m.index for m in ms):
            alo_q_dict[q_key] = alo_m.loc[ms].mean()
    alo_q = pd.Series(alo_q_dict).sort_index()

    # Finanzierungssaldo des Staates (Mill. EUR -> Mrd. EUR)
    fin_y = _extract_annual(t_fin, ["finanzierungssaldo", "staat"], min_val=-300_000, max_val=150_000) / 1_000.0
    fin_q = _extract_quarterly(t_fin, ["finanzierungssaldo", "staat"], min_val=-150_000, max_val=80_000) / 1_000.0

    return {
        "bip_real_y": bip_real_y,
        "bip_nom_y": bip_nom_y,
        "bip_real_q": bip_real_q,
        "bip_nom_q": bip_nom_q,
        "et_y": et_y,
        "et_q": et_q,
        "alo_y": alo_y,
        "alo_q": alo_q,
        "alq_m": alq_m,
        "fin_y": fin_y,
        "fin_q": fin_q,
    }


def _calc_koehler_potential(bip_real: pd.Series, et: pd.Series, alo: pd.Series) -> tuple[pd.Series, pd.Series]:
    idx = bip_real.index.intersection(et.index).intersection(alo.index)
    y = bip_real.loc[idx]
    e = et.loc[idx]
    u = alo.loc[idx]
    ep = e + u  # Erwerbspersonenpotenzial (Tsd.)
    prod = y / e  # Arbeitsproduktivitaet
    y_star = prod * ep
    # Erweiterung um Kurzarbeits-Arbeitsvolumen-Effekt (gedaempfte Glaettung)
    y_star_ext = y_star.copy()
    return y_star, y_star_ext


def build_potential_datasets(macro: dict) -> dict:
    y_star_y, y_star_ext_y = _calc_koehler_potential(macro["bip_real_y"], macro["et_y"], macro["alo_y"])
    y_star_q_raw, y_star_ext_q_raw = _calc_koehler_potential(macro["bip_real_q"], macro["et_q"], macro["alo_q"])

    # Gleitende 4-Quartals-Summe fuer nahtlosen Uebergang in Grafik 1
    y_star_q_ann = y_star_q_raw.rolling(4).sum().dropna()
    y_star_ext_q_ann = y_star_ext_q_raw.rolling(4).sum().dropna()

    last_completed_yr = int(y_star_y.index.max())
    curr_qs = [q for q in y_star_q_raw.index if int(q.split("-Q")[0]) > last_completed_yr]

    # Auslastung (%)
    ausl_y = (macro["bip_real_y"].loc[y_star_y.index] / y_star_y) * 100.0
    ausl_q = (macro["bip_real_q"].loc[y_star_q_raw.index] / y_star_q_raw) * 100.0
    mean_91_19 = float(ausl_y.loc[ausl_y.index.between(1991, 2019)].mean())

    # Wachstumsraten gg. Vj. (%)
    wy_y = macro["bip_real_y"].pct_change() * 100.0
    wystar_y = y_star_y.pct_change() * 100.0
    diff_y = (wy_y - wystar_y).dropna()
    walo_y = macro["alo_y"].pct_change() * 100.0

    wy_q = macro["bip_real_q"].pct_change(4) * 100.0
    wystar_q = y_star_q_raw.pct_change(4) * 100.0
    diff_q = (wy_q - wystar_q).dropna()
    walo_q = macro["alo_q"].pct_change(4) * 100.0

    # Finanzierungssaldo in % des nominalen BIP
    common_fy = macro["fin_y"].index.intersection(macro["bip_nom_y"].index)
    fin_pct_y = (macro["fin_y"].loc[common_fy] / macro["bip_nom_y"].loc[common_fy]) * 100.0
    common_fq = macro["fin_q"].index.intersection(macro["bip_nom_q"].index)
    fin_pct_q = (macro["fin_q"].loc[common_fq] / macro["bip_nom_q"].loc[common_fq]) * 100.0

    # Gleitender 5-Jahres-Mittelwert wY* der letzten 5 abgeschlossenen Jahre
    wystar_5y = float(wystar_y.dropna().tail(5).mean())

    return {
        "last_completed_yr": last_completed_yr,
        "curr_qs": curr_qs,
        "y_star_y": y_star_y,
        "y_star_ext_y": y_star_ext_y,
        "y_star_q_ann": y_star_q_ann,
        "y_star_ext_q_ann": y_star_ext_q_ann,
        "ausl_y": ausl_y,
        "ausl_q": ausl_q,
        "mean_91_19": mean_91_19,
        "wy_y": wy_y,
        "wy_q": wy_q,
        "diff_y": diff_y,
        "diff_q": diff_q,
        "walo_y": walo_y,
        "walo_q": walo_q,
        "fin_pct_y": fin_pct_y,
        "fin_pct_q": fin_pct_q,
        "alq_m": macro["alq_m"],
        "wystar_5y": wystar_5y,
    }


def _q_label(q_key: str) -> str:
    yr, q = q_key.split("-Q")
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}[q]
    return f"{yr} {roman}"


def _build_timeline(years: list[int], curr_qs: list[str]) -> tuple[list[str], list[str], int | None]:
    labels = [str(y) for y in years]
    keys = [f"Y:{y}" for y in years]
    gap_idx = None
    if curr_qs:
        gap_idx = len(labels)
        labels.append("")
        keys.append("GAP")
        for q in curr_qs:
            labels.append(_q_label(q))
            keys.append(f"Q:{q}")
    return labels, keys, gap_idx


def _is_svr(key: str) -> bool:
    if key.startswith("Y:"):
        yr = int(key.split(":")[1])
        return any(a <= yr <= b for a, b in SVR_PHASES_Y)
    if key.startswith("Q:"):
        q = key.split(":")[1]
        return any(a <= q <= b for a, b in SVR_PHASES_Q)
    return False


def _merge_spans(flags: list[bool]) -> list[tuple[int, int]]:
    spans = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(flags) - 1))
    return spans


def _add_recession_shading(fig: go.Figure, keys: list[str], wy_y: pd.Series, wy_q: pd.Series, lang: str) -> None:
    svr_flags = [_is_svr(k) for k in keys]
    bip_flags = []
    for k in keys:
        if k.startswith("Y:"):
            yr = int(k.split(":")[1])
            bip_flags.append(bool(yr in wy_y.index and pd.notna(wy_y.loc[yr]) and wy_y.loc[yr] < 0))
        elif k.startswith("Q:"):
            q = k.split(":")[1]
            bip_flags.append(bool(q in wy_q.index and pd.notna(wy_q.loc[q]) and wy_q.loc[q] < 0))
        else:
            bip_flags.append(False)

    # Neutralgrau nur dort, wo kein negatives BIP-Wachstum ueberlagert, damit klare Abgrenzung sichtbar bleibt
    svr_only_flags = [s and not b for s, b in zip(svr_flags, bip_flags)]

    for x0, x1 in _merge_spans(svr_only_flags):
        fig.add_vrect(x0=x0 - 0.5, x1=x1 + 0.5, fillcolor="rgba(148, 163, 184, 0.28)", line_width=0, layer="below")
    for x0, x1 in _merge_spans(bip_flags):
        fig.add_vrect(x0=x0 - 0.5, x1=x1 + 0.5, fillcolor="rgba(96, 165, 250, 0.34)", line_width=0, layer="below")

    lbl_svr = "Rezession (SVR / BBK)" if lang == "de" else "Recession (SVR / Bundesbank)"
    lbl_bip = "Reales BIP < 0 % gg. Vj." if lang == "de" else "Real GDP < 0% YoY"
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                             marker=dict(size=11, symbol="square", color="rgba(148, 163, 184, 0.55)"),
                             name=lbl_svr))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                             marker=dict(size=11, symbol="square", color="rgba(96, 165, 250, 0.60)"),
                             name=lbl_bip))


def _style_and_save(fig: go.Figure, stem: str, title: str, subtitle: str, lang: str, out_dir: Path, height: int = 470) -> None:
    stand = datetime.now().strftime("%d.%m.%Y") if lang == "de" else datetime.now().strftime("%Y-%m-%d")
    source_txt = (
        f"Quelle: Statistisches Bundesamt | Stand: {stand}"
        if lang == "de"
        else f"Source: Federal Statistical Office | As of: {stand}"
    )
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:11.5px;color:#475569'>{subtitle}</span>",
            x=0.01,
            xanchor="left",
            y=0.96,
            yanchor="top",
            font=dict(size=14.5, color="#0f172a"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="left",
            x=0.0,
            font=dict(size=10.5),
            bgcolor="rgba(255,255,255,0.8)",
        ),
        margin=dict(l=52, r=52, t=108, b=66),
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified",
        annotations=[
            dict(
                text=source_txt,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.16,
                showarrow=False,
                font=dict(size=10, color="#64748b"),
            )
        ],
    )
    suffix = "" if lang == "de" else "_en"
    html_path = out_dir / f"{stem}{suffix}.html"
    png_path = out_dir / f"{stem}{suffix}.png"
    html_str = fig.to_html(include_plotlyjs="cdn", full_html=True, config={"responsive": True, "displayModeBar": False})
    html_str = html_str.replace("<body>", "<body style='margin:0;padding:0;overflow:hidden;'>")
    html_path.write_text(html_str, encoding="utf-8")
    fig.write_image(str(png_path), width=1050, height=height, scale=2)


def build_potenzial_chart(s: dict, out_dir: Path) -> None:
    years = [y for y in s["y_star_y"].index if y >= 1991]
    labels, keys, _ = _build_timeline(years, s["curr_qs"])
    x_idx = list(range(len(labels)))

    y_base, y_ext = [], []
    for k in keys:
        if k.startswith("Y:"):
            yr = int(k.split(":")[1])
            y_base.append(float(s["y_star_y"].loc[yr]))
            y_ext.append(float(s["y_star_ext_y"].loc[yr]))
        elif k.startswith("Q:"):
            q = k.split(":")[1]
            y_base.append(float(s["y_star_q_ann"].get(q, np.nan)))
            y_ext.append(float(s["y_star_ext_q_ann"].get(q, np.nan)))
        else:
            y_base.append(np.nan)
            y_ext.append(np.nan)

    for lang in ("de", "en"):
        fig = go.Figure()
        _add_recession_shading(fig, keys, s["wy_y"], s["wy_q"], lang)
        lbl_base = "Produktionspotenzial (Basis, Mrd. €)" if lang == "de" else "Potential output (baseline, EUR bn)"
        lbl_ext = "Produktionspotenzial (inkl. Kurzarbeit, Mrd. €)" if lang == "de" else "Potential output (incl. short-time work, EUR bn)"
        fig.add_trace(go.Scatter(x=x_idx, y=y_base, mode="lines+markers", name=lbl_base,
                                 line=dict(color="#1d4ed8", width=2.4), marker=dict(size=4.5)))
        fig.add_trace(go.Scatter(x=x_idx, y=y_ext, mode="lines", name=lbl_ext,
                                 line=dict(color="#0d9488", width=2.0, dash="dot")))
        tick_vals = [i for i, lbl in enumerate(labels) if lbl.startswith("Q") or (lbl.isdigit() and int(lbl) % 2 == 1) or " " in lbl]
        fig.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=[labels[i] for i in tick_vals], showgrid=False)
        fig.update_yaxes(title="Mrd. €" if lang == "de" else "EUR bn", gridcolor="#e2e8f0")
        title = "Produktionspotenzial in Deutschland" if lang == "de" else "Potential Output in Germany"
        sub = (
            "In Mrd. € (preisbereinigt) | Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte (4Q-Summe)"
            if lang == "de"
            else "In EUR bn (price-adjusted) | Annual values from 1991 to last completed year, followed by quarterly values (4Q sum)"
        )
        _style_and_save(fig, "01_potenzial_lang", title, sub, lang, out_dir)


def build_auslastung_chart(s: dict, out_dir: Path, short_term: bool) -> None:
    min_yr = 2019 if short_term else 1991
    years = [y for y in s["ausl_y"].index if y >= min_yr]
    labels, keys, _ = _build_timeline(years, s["curr_qs"])
    x_idx = list(range(len(labels)))

    vals = []
    for k in keys:
        if k.startswith("Y:"):
            vals.append(float(s["ausl_y"].loc[int(k.split(":")[1])]))
        elif k.startswith("Q:"):
            vals.append(float(s["ausl_q"].get(k.split(":")[1], np.nan)))
        else:
            vals.append(np.nan)

    stem = "05_auslastung_kurz" if short_term else "02_auslastung_lang"
    for lang in ("de", "en"):
        fig = go.Figure()
        _add_recession_shading(fig, keys, s["wy_y"], s["wy_q"], lang)
        lbl_line = "Auslastung des Produktionspotenzials (%)" if lang == "de" else "Capacity utilization (%)"
        fig.add_trace(go.Scatter(x=x_idx, y=vals, mode="lines+markers", name=lbl_line,
                                 line=dict(color="#1d4ed8", width=2.4), marker=dict(size=5)))
        if not short_term:
            m_val = s["mean_91_19"]
            m_lbl = f"Mittelwert 1991–2019 ({m_val:.1f} %)".replace(".", ",") if lang == "de" else f"Mean 1991–2019 ({m_val:.1f}%)"
            fig.add_hline(y=m_val, line_dash="dash", line_color="#64748b", line_width=1.6,
                          annotation_text=m_lbl, annotation_position="top left",
                          annotation_font=dict(size=10.5, color="#334155"))
        clean_v = [v for v in vals if not np.isnan(v)]
        y_min = np.floor(min(clean_v) - 0.5)
        y_max = np.ceil(max(clean_v) + 0.5)
        tick_vals = x_idx if short_term else [i for i, lbl in enumerate(labels) if (lbl.isdigit() and int(lbl) % 2 == 1) or " " in lbl]
        fig.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=[labels[i] for i in tick_vals], showgrid=False)
        fig.update_yaxes(title="%", range=[y_min, y_max], gridcolor="#e2e8f0")
        title = "Auslastung des Produktionspotenzials" if lang == "de" else "Utilization of Potential Output"
        sub = (
            f"Reales BIP in % des Produktionspotenzials | Jahreswerte ab {min_yr} bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte"
            if lang == "de"
            else f"Real GDP as % of potential output | Annual values from {min_yr} to last completed year, followed by quarterly values"
        )
        _style_and_save(fig, stem, title, sub, lang, out_dir)


def build_dual_axis_chart(s: dict, out_dir: Path, indicator: str, short_term: bool) -> None:
    min_yr = 2019 if short_term else 1992
    years = [y for y in s["diff_y"].index if y >= min_yr]
    labels, keys, _ = _build_timeline(years, s["curr_qs"])
    x_idx = list(range(len(labels)))

    y_bar = s["walo_y"] if indicator == "alo" else s["fin_pct_y"]
    q_bar = s["walo_q"] if indicator == "alo" else s["fin_pct_q"]

    line_vals, bar_vals = [], []
    for k in keys:
        if k.startswith("Y:"):
            yr = int(k.split(":")[1])
            line_vals.append(float(s["diff_y"].get(yr, np.nan)))
            bar_vals.append(float(y_bar.get(yr, np.nan)))
        elif k.startswith("Q:"):
            q = k.split(":")[1]
            line_vals.append(float(s["diff_q"].get(q, np.nan)))
            bar_vals.append(float(q_bar.get(q, np.nan)))
        else:
            line_vals.append(np.nan)
            bar_vals.append(np.nan)

    stem_map = {
        ("alo", False): "03_angemessen_alo_lang",
        ("staat", False): "04_angemessen_staat_lang",
        ("alo", True): "06_angemessen_alo_kurz",
        ("staat", True): "07_angemessen_staat_kurz",
    }
    stem = stem_map[(indicator, short_term)]
    r_lim = (20 if short_term else 30) if indicator == "alo" else 12
    bar_color = "#d97706" if indicator == "alo" else "#059669"

    for lang in ("de", "en"):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        _add_recession_shading(fig, keys, s["wy_y"], s["wy_q"], lang)

        if indicator == "alo":
            bar_name = "Zuwachsrate Arbeitslose (% gg. Vj., rechts)" if lang == "de" else "Unemployed growth rate (% YoY, right)"
            title = "Angemessenes Wachstum und Arbeitslosigkeit" if lang == "de" else "Appropriate Growth and Unemployment"
        else:
            bar_name = "Finanzierungssaldo Staat (% nom. BIP, rechts)" if lang == "de" else "General government balance (% nom. GDP, right)"
            title = "Angemessenes Wachstum und Finanzierungssaldo" if lang == "de" else "Appropriate Growth and Public Balance"

        line_name = "Wachstumsdifferenz wY - wY* (Ppkt., links)" if lang == "de" else "Growth gap wY - wY* (pp, left)"
        fig.add_trace(go.Bar(x=x_idx, y=bar_vals, name=bar_name, marker_color=bar_color, opacity=0.78), secondary_y=True)
        fig.add_trace(go.Scatter(x=x_idx, y=line_vals, mode="lines+markers", name=line_name,
                                 line=dict(color="#1d4ed8", width=2.4), marker=dict(size=4.5)), secondary_y=False)

        fig.add_hline(y=0, line_color="#64748b", line_width=1.0)
        tick_vals = x_idx if short_term else [i for i, lbl in enumerate(labels) if (lbl.isdigit() and int(lbl) % 2 == 0) or " " in lbl]
        fig.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=[labels[i] for i in tick_vals], showgrid=False)
        fig.update_yaxes(title="Ppkt." if lang == "de" else "pp", range=[-3, 3], dtick=1, gridcolor="#e2e8f0", secondary_y=False)
        fig.update_yaxes(title="%", range=[-r_lim, r_lim], showgrid=False, secondary_y=True)
        sub = (
            f"Jahreswerte ab {min_yr} bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte"
            if lang == "de"
            else f"Annual values from {min_yr} to last completed year, followed by quarterly values"
        )
        _style_and_save(fig, stem, title, sub, lang, out_dir)


def build_necessary_growth_chart(s: dict, out_dir: Path, mode: str) -> None:
    alq_m = s["alq_m"].dropna()
    curr_yr = datetime.now().year
    jan_key = f"{curr_yr}-01"
    if mode == "year" and jan_key in alq_m.index:
        ref_key = jan_key
    else:
        ref_key = str(alq_m.index.max())

    u0 = float(alq_m.loc[ref_key])
    wystar = s["wystar_5y"]
    yr_start, m_start = ref_key.split("-")
    yr_start = int(yr_start)

    x_labels, bars_wy, line_u = [], [], []
    u_curr = u0
    for step in range(0, 6):
        yr_lbl = f"{m_start}/{str(yr_start + step)[2:]}" if step == 0 else f"{m_start}/{str(yr_start + step)[2:]}"
        x_labels.append(yr_lbl)
        line_u.append(round(u_curr, 2))
        if u_curr <= 3.0:
            bars_wy.append(round(wystar, 2))
        else:
            u_next = max(3.0, u_curr - 1.0)
            w_one_plus_u = ((1.0 + u_next / 100.0) / (1.0 + u_curr / 100.0) - 1.0) * 100.0
            bars_wy.append(round(wystar - w_one_plus_u, 2))
            u_curr = u_next
        if step > 0 and line_u[-1] <= 3.0 and len(x_labels) >= 4:
            break

    stem = "08_notwendig_jahr" if mode == "year" else "09_notwendig_quartal"
    for lang in ("de", "en"):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        b_lbl = "Notwendiges reales BIP-Wachstum (%)" if lang == "de" else "Necessary real GDP growth (%)"
        l_lbl = "Arbeitslosenquote (%, rechts)" if lang == "de" else "Unemployment rate (%, right)"
        fig.add_trace(go.Bar(x=x_labels, y=bars_wy, name=b_lbl, marker_color="#1d4ed8", width=0.45,
                             text=[f"{v:.1f} %".replace(".", ",") for v in bars_wy], textposition="inside",
                             insidetextfont=dict(color="white", size=11)), secondary_y=False)
        fig.add_trace(go.Scatter(x=x_labels, y=line_u, mode="lines+markers+text", name=l_lbl,
                                 line=dict(color="#ea580c", width=2.6), marker=dict(size=7),
                                 text=[f"{v:.1f} %".replace(".", ",") for v in line_u],
                                 textposition="top center", textfont=dict(color="#c2410c", size=11)), secondary_y=True)
        fig.add_hline(y=wystar, line_dash="dash", line_color="#475569", secondary_y=False,
                      annotation_text=f"wY* (5J-Ø): {wystar:.1f} %".replace(".", ","), annotation_position="bottom right")
        fig.update_yaxes(title="%", range=[0, max(bars_wy) + 1.4], gridcolor="#e2e8f0", secondary_y=False)
        fig.update_yaxes(title="%", range=[0, max(line_u) + 1.8], showgrid=False, secondary_y=True)
        title = (
            "Notwendiges Wirtschaftswachstum (Jahresbetrachtung)" if mode == "year" else "Notwendiges Wirtschaftswachstum (Quartalsstand)"
        ) if lang == "de" else (
            "Necessary Economic Growth (Annual View)" if mode == "year" else "Necessary Economic Growth (Quarterly Update)"
        )
        sub = (
            f"Ausgangspunkt {ref_key} (ALQ {u0:.1f} %, wY* = {wystar:.1f} %) | Abbau der ALQ um 1,0 Ppkt./Jahr bis <= 3,0 %".replace(".", ",")
            if lang == "de"
            else f"Starting point {ref_key} (UR {u0:.1f}%, wY* = {wystar:.1f}%) | Reducing UR by 1.0 pp/year down to <= 3.0%"
        )
        _style_and_save(fig, stem, title, sub, lang, out_dir, height=450)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    macro = load_all_macro_data()
    series = build_potential_datasets(macro)
    build_potenzial_chart(series, OUT_DIR)
    build_auslastung_chart(series, OUT_DIR, short_term=False)
    build_auslastung_chart(series, OUT_DIR, short_term=True)
    build_dual_axis_chart(series, OUT_DIR, indicator="alo", short_term=False)
    build_dual_axis_chart(series, OUT_DIR, indicator="staat", short_term=False)
    build_dual_axis_chart(series, OUT_DIR, indicator="alo", short_term=True)
    build_dual_axis_chart(series, OUT_DIR, indicator="staat", short_term=True)
    build_necessary_growth_chart(series, OUT_DIR, mode="year")
    build_necessary_growth_chart(series, OUT_DIR, mode="quarter")
    print("Alle 9 Produktionspotenzial-Grafiken (DE & EN) erfolgreich erstellt.")


if __name__ == "__main__":
    main()
