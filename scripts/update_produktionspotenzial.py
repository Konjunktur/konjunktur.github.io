#!/usr/bin/env python3
"""
Update-Skript fuer die Rubrik "Produktionspotenzial nach Claus Koehler"
(Deutsch & Englisch, PNG & interaktives HTML, ohne Scrollbalken).
"""

import io
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

OUT_DIR = Path("static/produktionspotenzial")
GENESIS_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020"
DESTATIS_USER = os.getenv("DESTATIS_USER", "")
DESTATIS_PASS = os.getenv("DESTATIS_PASS", "")

MONATE_DE = {
    1: "Jan", 2: "Feb", 3: "Mrz", 4: "Apr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez",
}
MONATE_EN = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

SVR_PHASES_Y = [
    (1992, 1993), (2001, 2003), (2008, 2009), (2020, 2020), (2022, 2025)
]
SVR_PHASES_Q = [
    ("1992-Q1", "1993-Q2"), ("2001-Q1", "2003-Q2"),
    ("2008-Q2", "2009-Q2"), ("2020-Q1", "2020-Q2"),
    ("2022-Q4", "2025-Q1"),
]


def _parse_num(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    s = str(val).strip()
    if s in {"", "-", ".", "...", "x", "/", "None", "nan", "NaN"}:
        return np.nan
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def fetch_destatis_table(table_name: str, start_year: int = 1991) -> pd.DataFrame:
    url = f"{GENESIS_BASE}/data/tablefile"
    params = {
        "username": DESTATIS_USER,
        "password": DESTATIS_PASS,
        "name": table_name,
        "area": "all",
        "compress": "false",
        "transpose": "false",
        "startyear": str(start_year),
        "endyear": str(datetime.now().year),
        "language": "de",
        "format": "ffcsv",
    }
    resp = requests.get(url, params=params, timeout=90)
    resp.raise_for_status()
    raw_text = resp.text
    if raw_text.lstrip().startswith("{"):
        payload = resp.json()
        raw_text = (
            payload.get("Object", {}).get("Content")
            or payload.get("Content")
            or raw_text
        )
    lines = raw_text.splitlines()
    header_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("statistics_code;") or (
            ";" in line and "value" in line.lower() and line.count(";") >= 4
        ):
            header_idx = i
            break
    cleaned = "\n".join(lines[header_idx:])
    df = pd.read_csv(
        io.StringIO(cleaned),
        sep=";",
        dtype=str,
        on_bad_lines="skip",
    )
    df.columns = [c.strip() for c in df.columns]
    return df


def _filter_total_economy(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    code_cols = [c for c in out.columns if c.endswith("_attribute_code")]
    for cc in code_cols:
        vals = set(out[cc].dropna().astype(str).str.strip().unique())
        if "INSGESAMT" in vals:
            out = out[out[cc].astype(str).str.strip() == "INSGESAMT"]
        elif "WZ08-A-U" in vals:
            out = out[out[cc].astype(str).str.strip() == "WZ08-A-U"]
        elif "WERTORG" in vals:
            out = out[out[cc].astype(str).str.strip() == "WERTORG"]
    return out


def _extract_year_series(
    df: pd.DataFrame,
    include_terms: list,
    exclude_terms: list = None,
    min_val: float = None,
    max_val: float = None,
) -> pd.Series:
    if df.empty or "value" not in df.columns:
        return pd.Series(dtype=float)
    sub = _filter_total_economy(df)
    label_col = "value_variable_label" if "value_variable_label" in sub.columns else None
    code_col = "value_variable_code" if "value_variable_code" in sub.columns else None
    if label_col or code_col:
        txt = (
            sub[label_col].fillna("") if label_col else pd.Series("", index=sub.index)
        ) + " " + (
            sub[code_col].fillna("") if code_col else pd.Series("", index=sub.index)
        )
        txt_low = txt.str.lower()
        mask = pd.Series(True, index=sub.index)
        for term in include_terms:
            mask &= txt_low.str.contains(term.lower(), regex=False)
        if exclude_terms:
            for term in exclude_terms:
                mask &= ~txt_low.str.contains(term.lower(), regex=False)
        sub = sub[mask]

    if "time" not in sub.columns:
        return pd.Series(dtype=float)
    sub = sub[sub["time"].astype(str).str.fullmatch(r"\d{4}")].copy()
    sub["year"] = sub["time"].astype(int)
    sub["num"] = sub["value"].apply(_parse_num)
    sub = sub.dropna(subset=["num"])
    if min_val is not None:
        sub = sub[sub["num"] >= min_val]
    if max_val is not None:
        sub = sub[sub["num"] <= max_val]
    if sub.empty:
        return pd.Series(dtype=float)
    s = sub.groupby("year")["num"].median().sort_index()
    return s


def _extract_quarter_series(
    df: pd.DataFrame,
    include_terms: list,
    exclude_terms: list = None,
    min_val: float = None,
    max_val: float = None,
) -> pd.Series:
    if df.empty or "value" not in df.columns:
        return pd.Series(dtype=float)
    sub = _filter_total_economy(df)
    label_col = "value_variable_label" if "value_variable_label" in sub.columns else None
    code_col = "value_variable_code" if "value_variable_code" in sub.columns else None
    if label_col or code_col:
        txt = (
            sub[label_col].fillna("") if label_col else pd.Series("", index=sub.index)
        ) + " " + (
            sub[code_col].fillna("") if code_col else pd.Series("", index=sub.index)
        )
        txt_low = txt.str.lower()
        mask = pd.Series(True, index=sub.index)
        for term in include_terms:
            mask &= txt_low.str.contains(term.lower(), regex=False)
        if exclude_terms:
            for term in exclude_terms:
                mask &= ~txt_low.str.contains(term.lower(), regex=False)
        sub = sub[mask]

    q_col = None
    for c in sub.columns:
        if c.endswith("_attribute_code") and sub[c].astype(str).str.startswith("QUART").any():
            q_col = c
            break
    if q_col is None or "time" not in sub.columns:
        return pd.Series(dtype=float)

    sub = sub[
        sub["time"].astype(str).str.fullmatch(r"\d{4}")
        & sub[q_col].astype(str).str.fullmatch(r"QUART[1-4]")
    ].copy()
    sub["q_label"] = sub["time"].astype(str) + "-Q" + sub[q_col].astype(str).str[-1]
    sub["num"] = sub["value"].apply(_parse_num)
    sub = sub.dropna(subset=["num"])
    if min_val is not None:
        sub = sub[sub["num"] >= min_val]
    if max_val is not None:
        sub = sub[sub["num"] <= max_val]
    if sub.empty:
        return pd.Series(dtype=float)
    s = sub.groupby("q_label")["num"].median().sort_index()
    return s


def _extract_monthly_ba_alq(df: pd.DataFrame) -> pd.Series:
    if df.empty or "value" not in df.columns:
        return pd.Series(dtype=float)
    sub = df.copy()
    txt = pd.Series("", index=sub.index)
    for col in sub.columns:
        if col.endswith("_label") or col.endswith("_code"):
            txt = txt + " " + sub[col].fillna("").astype(str)
    txt_low = txt.str.lower()
    mask = txt_low.str.contains("arbeitslosenquote", regex=False)
    if (mask & txt_low.str.contains("alle zivilen erwerbspersonen", regex=False)).any():
        mask = mask & txt_low.str.contains("alle zivilen erwerbspersonen", regex=False)
    elif (mask & ~txt_low.str.contains("abhängig", regex=False)).any():
        mask = mask & ~txt_low.str.contains("abhängig", regex=False)
    sub = sub[mask]

    m_col = None
    for c in sub.columns:
        if c.endswith("_attribute_code") and sub[c].astype(str).str.startswith("MONAT").any():
            m_col = c
            break
    if m_col is None or "time" not in sub.columns:
        return pd.Series(dtype=float)

    sub = sub[
        sub["time"].astype(str).str.fullmatch(r"\d{4}")
        & sub[m_col].astype(str).str.fullmatch(r"MONAT\d{2}")
    ].copy()
    sub["ym"] = sub["time"].astype(str) + "-" + sub[m_col].astype(str).str[-2:]
    sub["num"] = sub["value"].apply(_parse_num)
    sub = sub[(sub["num"] >= 1.0) & (sub["num"] <= 25.0)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("ym")["num"].min().sort_index()


def _extract_monthly_ba_alo(df: pd.DataFrame) -> pd.Series:
    if df.empty or "value" not in df.columns:
        return pd.Series(dtype=float)
    sub = _filter_total_economy(df)
    txt = pd.Series("", index=sub.index)
    for col in sub.columns:
        if col.endswith("_label") or col.endswith("_code"):
            txt = txt + " " + sub[col].fillna("").astype(str)
    txt_low = txt.str.lower()
    sub = sub[
        txt_low.str.contains("arbeitslose", regex=False)
        & ~txt_low.str.contains("quote", regex=False)
    ]
    m_col = None
    for c in sub.columns:
        if c.endswith("_attribute_code") and sub[c].astype(str).str.startswith("MONAT").any():
            m_col = c
            break
    if m_col is None or "time" not in sub.columns:
        return pd.Series(dtype=float)
    sub = sub[
        sub["time"].astype(str).str.fullmatch(r"\d{4}")
        & sub[m_col].astype(str).str.fullmatch(r"MONAT\d{2}")
    ].copy()
    sub["ym"] = sub["time"].astype(str) + "-" + sub[m_col].astype(str).str[-2:]
    sub["num"] = sub["value"].apply(_parse_num)
    sub = sub[sub["num"] > 500_000]
    if sub.empty:
        return pd.Series(dtype=float)
    # In Tsd. umrechnen falls in Personen
    s = sub.groupby("ym")["num"].median().sort_index()
    if s.median() > 100_000:
        s = s / 1000.0
    return s


def load_all_macro_data() -> dict:
    t_bip_y = fetch_destatis_table("81000-0001", 1991)
    t_bip_q = fetch_destatis_table("81000-0002", 1991)
    t_et_y = fetch_destatis_table("81000-0011", 1991)
    t_et_q = fetch_destatis_table("81000-0012", 1991)
    t_fin = fetch_destatis_table("81000-0031", 1991)
    t_alo_y = fetch_destatis_table("13211-0001", 1991)
    t_alo_m = fetch_destatis_table("13211-0002", 2005)

    bip_real_q = _extract_quarter_series(
        t_bip_q, ["bruttoinlandsprodukt", "preisbereinigt"], ["je ", "%"], 300.0, 2000.0
    )
    bip_nom_q = _extract_quarter_series(
        t_bip_q, ["bruttoinlandsprodukt", "jeweilige"], ["je ", "%"], 300.0, 2000.0
    )
    bip_real_y = _extract_year_series(
        t_bip_y, ["bruttoinlandsprodukt", "preisbereinigt"], ["je ", "%"], 1500.0, 6000.0
    )
    if bip_real_y.empty and not bip_real_q.empty:
        q_df = bip_real_q.to_frame("v")
        q_df["y"] = q_df.index.str[:4].astype(int)
        cnt = q_df.groupby("y")["v"].count()
        bip_real_y = q_df.groupby("y")["v"].sum()[cnt == 4]

    bip_nom_y = _extract_year_series(
        t_bip_y, ["bruttoinlandsprodukt", "jeweilige"], ["je ", "%"], 1500.0, 6500.0
    )
    if bip_nom_y.empty and not bip_nom_q.empty:
        q_df = bip_nom_q.to_frame("v")
        q_df["y"] = q_df.index.str[:4].astype(int)
        cnt = q_df.groupby("y")["v"].count()
        bip_nom_y = q_df.groupby("y")["v"].sum()[cnt == 4]

    et_q = _extract_quarter_series(
        t_et_q, ["erwerbstätige"], ["%", "stunde"], 30000.0, 55000.0
    )
    et_y = _extract_year_series(
        t_et_y, ["erwerbstätige"], ["%", "stunde"], 30000.0, 55000.0
    )
    if et_y.empty and not et_q.empty:
        q_df = et_q.to_frame("v")
        q_df["y"] = q_df.index.str[:4].astype(int)
        cnt = q_df.groupby("y")["v"].count()
        et_y = q_df.groupby("y")["v"].mean()[cnt == 4]

    alo_y_hist = _extract_year_series(
        t_alo_y, ["arbeitslose"], ["quote", "%"], 1000.0, 7000.0
    )
    alo_m = _extract_monthly_ba_alo(t_alo_m)
    alq_m = _extract_monthly_ba_alq(t_alo_m)

    if not alo_m.empty:
        m_df = alo_m.to_frame("v")
        m_df["y"] = m_df.index.str[:4].astype(int)
        m_df["m"] = m_df.index.str[5:7].astype(int)
        m_df["q"] = (m_df["m"] - 1) // 3 + 1
        m_df["qlab"] = m_df["y"].astype(str) + "-Q" + m_df["q"].astype(str)
        alo_q = m_df.groupby("qlab")["v"].mean()
        y_cnt = m_df.groupby("y")["v"].count()
        alo_y_recent = m_df.groupby("y")["v"].mean()[y_cnt == 12]
        alo_y = alo_y_hist.combine_first(alo_y_recent)
        for y_idx, val in alo_y_recent.items():
            alo_y.loc[y_idx] = val
    else:
        alo_q = pd.Series(dtype=float)
        alo_y = alo_y_hist

    # Finanzierungssaldo des Staates (81000-0031 in Mill. EUR -> Mrd. EUR)
    fin_y = _extract_year_series(t_fin, ["finanzierungssaldo"], ["%"], -400000.0, 200000.0)
    if not fin_y.empty and fin_y.abs().max() > 500.0:
        fin_y = fin_y / 1000.0
    fin_q = _extract_quarter_series(t_fin, ["finanzierungssaldo"], ["%"], -200000.0, 100000.0)
    if not fin_q.empty and fin_q.abs().max() > 250.0:
        fin_q = fin_q / 1000.0

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


def _fmt_q_label(qlab: str) -> str:
    y, q = qlab.split("-Q")
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}[q]
    return f"{y} {roman}"


def build_potential_datasets(macro: dict) -> dict:
    bip_y = macro["bip_real_y"]
    bip_nom_y = macro["bip_nom_y"]
    et_y = macro["et_y"]
    alo_y = macro["alo_y"]
    fin_y = macro["fin_y"]

    bip_q = macro["bip_real_q"]
    bip_nom_q = macro["bip_nom_q"]
    et_q = macro["et_q"]
    alo_q = macro["alo_q"]
    fin_q = macro["fin_q"]
    alq_m = macro["alq_m"]

    idx_y = bip_y.index.intersection(et_y.index).intersection(alo_y.index)
    idx_y = idx_y[idx_y >= 1991].sort_values()

    pot_y = bip_y.loc[idx_y] * (1.0 + alo_y.loc[idx_y] / et_y.loc[idx_y])
    ausl_y = (bip_y.loc[idx_y] / pot_y) * 100.0

    # Quartalswerte (aktuell nach letztem abgeschlossenen Jahr)
    last_y = int(idx_y.max())
    idx_q = bip_q.index.intersection(et_q.index).intersection(alo_q.index).sort_values()
    pot_q = bip_q.loc[idx_q] * (1.0 + alo_q.loc[idx_q] / et_q.loc[idx_q])
    ausl_q = (bip_q.loc[idx_q] / pot_q) * 100.0
    # Gleitende 4-Quartals-Summe fuer Niveauvergleich mit Jahreswerten
    pot_q_ann = pot_q.rolling(4).sum()

    post_q = [q for q in idx_q if int(q[:4]) > last_y]

    # Kombinierte Achse 1991..last_y + post_q
    x_long = [str(y) for y in idx_y] + [_fmt_q_label(q) for q in post_q]
    pot_long = list(pot_y.values) + [float(pot_q_ann.loc[q]) for q in post_q]
    ausl_long = list(ausl_y.values) + [float(ausl_q.loc[q]) for q in post_q]

    mean_91_19 = float(ausl_y.loc[(ausl_y.index >= 1991) & (ausl_y.index <= 2019)].mean())

    # Wachstumsraten (ab 1992)
    wy_y = bip_y.pct_change() * 100.0
    wpot_y = pot_y.pct_change() * 100.0
    diff_y = (wy_y - wpot_y).dropna()
    walo_y = (alo_y.pct_change() * 100.0).dropna()
    fin_pct_y = ((fin_y / bip_nom_y) * 100.0).dropna()

    wy_q = bip_q.pct_change(4) * 100.0
    wpot_q = pot_q.pct_change(4) * 100.0
    diff_q = (wy_q - wpot_q).dropna()
    walo_q = (alo_q.pct_change(4) * 100.0).dropna()
    fin_pct_q = ((fin_q / bip_nom_q) * 100.0).dropna()

    idx_g_y = diff_y.index.intersection(walo_y.index)
    idx_g_y = idx_g_y[idx_g_y >= 1992].sort_values()

    x_g_long = [str(y) for y in idx_g_y] + [_fmt_q_label(q) for q in post_q if q in diff_q.index]
    diff_long = list(diff_y.loc[idx_g_y].values) + [
        float(diff_q.loc[q]) for q in post_q if q in diff_q.index
    ]
    walo_long = list(walo_y.loc[idx_g_y].values) + [
        float(walo_q.loc[q]) if q in walo_q.index else np.nan
        for q in post_q if q in diff_q.index
    ]
    fin_long = [
        float(fin_pct_y.loc[y]) if y in fin_pct_y.index else np.nan for y in idx_g_y
    ] + [
        float(fin_pct_q.loc[q]) if q in fin_pct_q.index else np.nan
        for q in post_q if q in diff_q.index
    ]

    # Rezessions-Flags je Balken (SVR/BBK vs. Reales BIP < 0 % gg. Vj.)
    svr_long = []
    bip_neg_long = []
    for y in idx_y:
        is_svr = any(a <= y <= b for a, b in SVR_PHASES_Y)
        svr_long.append(is_svr)
        bip_neg_long.append(bool(y in wy_y.index and wy_y.loc[y] < 0.0))
    for q in post_q:
        is_svr = any(a <= q <= b for a, b in SVR_PHASES_Q)
        svr_long.append(is_svr)
        bip_neg_long.append(bool(q in wy_q.index and wy_q.loc[q] < 0.0))

    svr_g_long = svr_long[1:]
    bip_neg_g_long = bip_neg_long[1:]

    # Kuerzere Frist ab 2019
    start_19_idx = x_long.index("2019") if "2019" in x_long else 0
    x_short = x_long[start_19_idx:]
    ausl_short = ausl_long[start_19_idx:]
    svr_short = svr_long[start_19_idx:]
    bip_neg_short = bip_neg_long[start_19_idx:]

    start_g19_idx = x_g_long.index("2019") if "2019" in x_g_long else 0
    x_g_short = x_g_long[start_g19_idx:]
    diff_short = diff_long[start_g19_idx:]
    walo_short = walo_long[start_g19_idx:]
    fin_short = fin_long[start_g19_idx:]
    svr_g_short = svr_g_long[start_g19_idx:]
    bip_neg_g_short = bip_neg_g_long[start_g19_idx:]

    # Gleitender 5-Jahres-Mittelwert wY* der letzten 5 abgeschlossenen Jahre
    wpot_valid = wpot_y.dropna()
    wy_star_5y = float(wpot_valid.iloc[-5:].mean()) if len(wpot_valid) >= 5 else 1.1
    wy_star_years = f"{int(wpot_valid.index[-5])}–{int(wpot_valid.index[-1])}" if len(wpot_valid) >= 5 else "2021–2025"

    # BA-ALQ fuer Grafik 8 (Jan des aktuellsten Jahres) & Grafik 9 (letzter Quartalsendmonat)
    latest_ym = str(alq_m.index.max()) if not alq_m.empty else f"{last_y + 1}-01"
    latest_y = int(latest_ym[:4])
    jan_key = f"{latest_y}-01"
    alq_jan = float(alq_m.loc[jan_key]) if jan_key in alq_m.index else float(alq_m.iloc[-1])

    q_end_candidates = [ym for ym in alq_m.index if ym.endswith(("-03", "-06", "-09", "-12"))]
    q_end_ym = q_end_candidates[-1] if q_end_candidates else latest_ym
    alq_qend = float(alq_m.loc[q_end_ym])

    now = datetime.now()
    stand_de = f"{MONATE_DE[now.month]} {now.year}"
    stand_en = f"{MONATE_EN[now.month]} {now.year}"

    return {
        "last_y": last_y,
        "x_long": x_long,
        "pot_long": pot_long,
        "ausl_long": ausl_long,
        "mean_91_19": mean_91_19,
        "svr_long": svr_long,
        "bip_neg_long": bip_neg_long,
        "x_g_long": x_g_long,
        "diff_long": diff_long,
        "walo_long": walo_long,
        "fin_long": fin_long,
        "svr_g_long": svr_g_long,
        "bip_neg_g_long": bip_neg_g_long,
        "x_short": x_short,
        "ausl_short": ausl_short,
        "svr_short": svr_short,
        "bip_neg_short": bip_neg_short,
        "x_g_short": x_g_short,
        "diff_short": diff_short,
        "walo_short": walo_short,
        "fin_short": fin_short,
        "svr_g_short": svr_g_short,
        "bip_neg_g_short": bip_neg_g_short,
        "wy_star_5y": wy_star_5y,
        "wy_star_years": wy_star_years,
        "jan_key": jan_key,
        "alq_jan": alq_jan,
        "q_end_ym": q_end_ym,
        "alq_qend": alq_qend,
        "stand_de": stand_de,
        "stand_en": stand_en,
    }


def _merged_spans(flags: list) -> list:
    spans = []
    start = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(flags) - 1))
    return spans


def _add_recession_shading(fig: go.Figure, svr_flags: list, bip_neg_flags: list, lang: str):
    for a, b in _merged_spans(svr_flags):
        fig.add_vrect(
            x0=a - 0.5,
            x1=b + 0.5,
            fillcolor="rgba(148, 163, 184, 0.30)",
            line_width=0,
            layer="below",
        )
    for a, b in _merged_spans(bip_neg_flags):
        fig.add_vrect(
            x0=a - 0.5,
            x1=b + 0.5,
            fillcolor="rgba(96, 165, 250, 0.36)",
            line_width=0,
            layer="below",
        )
    lbl_svr = "Rezession (SVR / BBK)" if lang == "de" else "Recession (SVR / Bundesbank)"
    lbl_bip = "Reales BIP < 0 % gg. Vj." if lang == "de" else "Real GDP < 0% YoY"
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=11, symbol="square", color="rgba(148, 163, 184, 0.55)"),
            name=lbl_svr, showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=11, symbol="square", color="rgba(96, 165, 250, 0.65)"),
            name=lbl_bip, showlegend=True,
        )
    )


def _apply_common_layout(fig: go.Figure, title: str, subtitle: str, source: str, height: int = 470):
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:12px;color:#475569'>{subtitle}</span>",
            x=0.02,
            y=0.96,
            xanchor="left",
            yanchor="top",
            font=dict(size=15, color="#0F172A", family="Inter, Arial, sans-serif"),
        ),
        legend=dict(
            orientation="h",
            x=0.02,
            y=1.03,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=11, color="#1E293B"),
            bgcolor="rgba(255,255,255,0.0)",
        ),
        margin=dict(l=58, r=58, t=118, b=66),
        height=height,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        font=dict(family="Inter, Arial, sans-serif", size=11, color="#334155"),
    )
    fig.add_annotation(
        text=source,
        xref="paper",
        yref="paper",
        x=0.0,
        y=-0.16,
        xanchor="left",
        yanchor="top",
        showarrow=False,
        font=dict(size=11, color="#64748B"),
    )


def _save_fig(fig: go.Figure, out_dir: Path, stem: str):
    png_path = out_dir / f"{stem}.png"
    html_path = out_dir / f"{stem}.html"
    try:
        fig.write_image(str(png_path), width=1050, height=int(fig.layout.height or 470), scale=2)
    except Exception as exc:
        print(f"[WARN] PNG export skipped for {stem}: {exc}")
    html_str = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False, "responsive": True},
    )
    html_str = html_str.replace(
        "<body>",
        "<body style='margin:0;padding:0;overflow:hidden;'>",
    )
    html_path.write_text(html_str, encoding="utf-8")


def build_potenzial_chart(series: dict, out_dir: Path):
    for lang in ("de", "en"):
        fig = go.Figure()
        _add_recession_shading(fig, series["svr_long"], series["bip_neg_long"], lang)
        name_pot = "Produktionspotenzial (Mrd. €)" if lang == "de" else "Potential output (EUR bn)"
        fig.add_trace(
            go.Scatter(
                x=series["x_long"],
                y=[round(v, 1) for v in series["pot_long"]],
                mode="lines+markers",
                name=name_pot,
                line=dict(color="#1D4ED8", width=2.8),
                marker=dict(size=5, color="#1D4ED8"),
            )
        )
        title = "Produktionspotenzial in Deutschland" if lang == "de" else "Potential Output in Germany"
        sub = (
            "In Mrd. Euro (preisbereinigt) | Jahreswerte ab 1991, danach gleitende 4-Quartals-Summe"
            if lang == "de"
            else "In EUR billion (price-adjusted) | Annual values from 1991, followed by 4-quarter rolling sum"
        )
        src = (
            f"Quelle: Statistisches Bundesamt | Stand: {series['stand_de']}"
            if lang == "de"
            else f"Source: Federal Statistical Office | As of: {series['stand_en']}"
        )
        _apply_common_layout(fig, title, sub, src, height=465)
        fig.update_yaxes(
            title_text="Mrd. €" if lang == "de" else "EUR bn",
            gridcolor="#E2E8F0",
            zeroline=False,
        )
        fig.update_xaxes(showgrid=False, tickangle=-45)
        stem = "01_potenzial_lang" if lang == "de" else "01_potenzial_lang_en"
        _save_fig(fig, out_dir, stem)


def build_auslastung_chart(series: dict, out_dir: Path, short_term: bool):
    for lang in ("de", "en"):
        x = series["x_short"] if short_term else series["x_long"]
        y = series["ausl_short"] if short_term else series["ausl_long"]
        svr = series["svr_short"] if short_term else series["svr_long"]
        bneg = series["bip_neg_short"] if short_term else series["bip_neg_long"]

        fig = go.Figure()
        _add_recession_shading(fig, svr, bneg, lang)
        name_u = "Auslastung des Produktionspotenzials (%)" if lang == "de" else "Capacity utilization (%)"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[round(v, 2) for v in y],
                mode="lines+markers",
                name=name_u,
                line=dict(color="#1D4ED8", width=2.8),
                marker=dict(size=5.5, color="#1D4ED8"),
            )
        )
        if not short_term:
            m_val = series["mean_91_19"]
            m_lbl = (
                f"Mittelwert 1991–2019: {m_val:.1f} %".replace(".", ",")
                if lang == "de"
                else f"Mean 1991–2019: {m_val:.1f}%"
            )
            fig.add_hline(
                y=m_val,
                line_dash="dash",
                line_color="#64748B",
                line_width=1.8,
                annotation_text=m_lbl,
                annotation_position="bottom right",
                annotation_font=dict(size=11, color="#475569"),
            )

        title = (
            "Auslastung des Produktionspotenzials"
            if lang == "de"
            else "Capacity Utilization of Potential Output"
        )
        start_yr = "2019" if short_term else "1991"
        sub = (
            f"Reales BIP in % des Produktionspotenzials | Jahreswerte ab {start_yr} bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte"
            if lang == "de"
            else f"Real GDP as % of potential output | Annual values from {start_yr} to last completed year, followed by quarterly values"
        )
        src = (
            f"Quelle: Statistisches Bundesamt | Stand: {series['stand_de']}"
            if lang == "de"
            else f"Source: Federal Statistical Office | As of: {series['stand_en']}"
        )
        _apply_common_layout(fig, title, sub, src, height=465)
        y_min = np.floor(min(y) - 0.5)
        y_max = np.ceil(max(y) + 0.5)
        fig.update_yaxes(
            title_text="%" ,
            range=[y_min, y_max],
            gridcolor="#E2E8F0",
            zeroline=False,
        )
        fig.update_xaxes(showgrid=False, tickangle=-45 if not short_term else 0)
        base = "05_auslastung_kurz" if short_term else "02_auslastung_lang"
        stem = base if lang == "de" else f"{base}_en"
        _save_fig(fig, out_dir, stem)


def build_dual_axis_chart(series: dict, out_dir: Path, indicator: str, short_term: bool):
    for lang in ("de", "en"):
        x = series["x_g_short"] if short_term else series["x_g_long"]
        diff = series["diff_short"] if short_term else series["diff_long"]
        svr = series["svr_g_short"] if short_term else series["svr_g_long"]
        bneg = series["bip_neg_g_short"] if short_term else series["bip_neg_g_long"]

        if indicator == "alo":
            bar_vals = series["walo_short"] if short_term else series["walo_long"]
            bar_color = "#D97706"
            r_lim = 20.0 if short_term else 30.0
            valid_b = [abs(v) for v in bar_vals if not np.isnan(v)]
            if valid_b and max(valid_b) > r_lim:
                r_lim = float(np.ceil(max(valid_b) / 5.0) * 5.0)
            r_dtick = 10.0
            bar_name = (
                "Zuwachsrate Arbeitslose (% gg. Vj., rechts)"
                if lang == "de"
                else "Unemployment growth (% YoY, right)"
            )
            r_title = "Arbeitslose (% gg. Vj.)" if lang == "de" else "Unemployment (% YoY)"
            title = (
                "Angemessenes Wirtschaftswachstum und Arbeitslosigkeit"
                if lang == "de"
                else "Appropriate Economic Growth and Unemployment"
            )
            base = "06_angemessen_alo_kurz" if short_term else "03_angemessen_alo_lang"
        else:
            bar_vals = series["fin_short"] if short_term else series["fin_long"]
            bar_color = "#059669"
            r_lim = 12.0
            valid_b = [abs(v) for v in bar_vals if not np.isnan(v)]
            if valid_b and max(valid_b) > r_lim:
                r_lim = float(np.ceil(max(valid_b) / 4.0) * 4.0)
            r_dtick = 4.0
            bar_name = (
                "Finanzierungssaldo des Staates (% des nom. BIP, rechts)"
                if lang == "de"
                else "General government balance (% of nom. GDP, right)"
            )
            r_title = "Finanzierungssaldo (% BIP)" if lang == "de" else "Public balance (% GDP)"
            title = (
                "Angemessenes Wirtschaftswachstum und Finanzierungssaldo des Staates"
                if lang == "de"
                else "Appropriate Economic Growth and Public Sector Balance"
            )
            base = "07_angemessen_staat_kurz" if short_term else "04_angemessen_staat_lang"

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        _add_recession_shading(fig, svr, bneg, lang)

        fig.add_trace(
            go.Bar(
                x=x,
                y=[None if np.isnan(v) else round(v, 2) for v in bar_vals],
                name=bar_name,
                marker_color=bar_color,
                opacity=0.78,
            ),
            secondary_y=True,
        )
        line_name = (
            "Wachstumsdifferenz wY − wY* (Ppkt., links)"
            if lang == "de"
            else "Growth gap wY − wY* (pp, left)"
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[round(v, 2) for v in diff],
                mode="lines+markers",
                name=line_name,
                line=dict(color="#1D4ED8", width=2.8),
                marker=dict(size=5.5, color="#1D4ED8"),
            ),
            secondary_y=False,
        )

        start_yr = "2019" if short_term else "1992"
        sub = (
            f"Wachstumsdifferenz (Ppkt.) & Indikator (%) | Jahreswerte ab {start_yr} bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte"
            if lang == "de"
            else f"Growth differential (pp) & indicator (%) | Annual values from {start_yr} to last completed year, followed by quarterly values"
        )
        src = (
            f"Quelle: Statistisches Bundesamt | Stand: {series['stand_de']}"
            if lang == "de"
            else f"Source: Federal Statistical Office | As of: {series['stand_en']}"
        )
        _apply_common_layout(fig, title, sub, src, height=480)
        fig.update_yaxes(
            title_text="Ppkt." if lang == "de" else "pp",
            range=[-3.0, 3.0],
            dtick=1.0,
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#94A3B8",
            secondary_y=False,
        )
        fig.update_yaxes(
            title_text=r_title,
            range=[-r_lim, r_lim],
            dtick=r_dtick,
            showgrid=False,
            zeroline=True,
            zerolinecolor="#94A3B8",
            secondary_y=True,
        )
        fig.update_xaxes(showgrid=False, tickangle=-45 if not short_term else 0)
        stem = base if lang == "de" else f"{base}_en"
        _save_fig(fig, out_dir, stem)


def build_necessary_growth_chart(series: dict, out_dir: Path, mode: str):
    is_year = mode == "year"
    start_ym = series["jan_key"] if is_year else series["q_end_ym"]
    start_alq = series["alq_jan"] if is_year else series["alq_qend"]
    wy_star = series["wy_star_5y"]

    base_year = int(start_ym[:4])
    years = [str(base_year + k) for k in range(5)]

    # Abbau bis Vollbeschäftigungsgrenze 3,0 % in max. 0,9 Ppkt./Jahr (gemäß Köhler-Modell)
    alq_path = []
    cur = start_alq
    for _ in range(5):
        alq_path.append(round(cur, 2))
        cur = max(3.0, cur - 0.9)

    al_abbau = []
    for i in range(5):
        if i == 0:
            step = max(0.0, round(alq_path[0] - max(3.0, alq_path[0] - 0.9), 2))
        else:
            step = max(0.0, round(alq_path[i - 1] - alq_path[i], 2))
        al_abbau.append(step)

    wy_pot_bar = [round(wy_star, 2)] * 5
    nec_growth = [round(wy_star + d, 2) for d in al_abbau]

    for lang in ("de", "en"):
        fig = go.Figure()
        lbl_pot = (
            f"Wachstum Produktionspotenzial wY* (Ø {series['wy_star_years']})"
            if lang == "de"
            else f"Potential output growth wY* (avg {series['wy_star_years']})"
        )
        lbl_abbau = (
            "Zusatzwachstum zum Abbau der Arbeitslosigkeit (bis 3,0 %)"
            if lang == "de"
            else "Extra growth to reduce unemployment (to 3.0%)"
        )
        lbl_nec = (
            "Notwendiges reales Wirtschaftswachstum (%)"
            if lang == "de"
            else "Necessary real economic growth (%)"
        )

        fig.add_trace(
            go.Bar(
                x=years,
                y=wy_pot_bar,
                name=lbl_pot,
                marker_color="#1D4ED8",
            )
        )
        fig.add_trace(
            go.Bar(
                x=years,
                y=al_abbau,
                name=lbl_abbau,
                marker_color="#93C5FD",
            )
        )

        # Kollisionsfreie Linienbeschriftung oberhalb der Linie
        txt_vals = [
            (f"{v:.1f} %".replace(".", ",") if lang == "de" else f"{v:.1f}%")
            for v in nec_growth
        ]
        fig.add_trace(
            go.Scatter(
                x=years,
                y=nec_growth,
                mode="lines+markers+text",
                name=lbl_nec,
                line=dict(color="#D97706", width=3.0),
                marker=dict(size=8, color="#D97706"),
                text=txt_vals,
                textposition="top center",
                textfont=dict(size=12, color="#B45309"),
            )
        )

        alq_str = f"{start_alq:.1f} %".replace(".", ",") if lang == "de" else f"{start_alq:.1f}%"
        if is_year:
            title = (
                "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit"
                if lang == "de"
                else "Necessary Economic Growth to Reduce Unemployment"
            )
            sub = (
                f"Jahresbetrachtung ab {start_ym} (BA-Arbeitslosenquote: {alq_str}; Zielwert Vollbeschäftigung: 3,0 %)"
                if lang == "de"
                else f"Annual path from {start_ym} (BA unemployment rate: {alq_str}; full-employment target: 3.0%)"
            )
            base = "08_notwendig_jahr"
        else:
            title = (
                "Notwendiges Wirtschaftswachstum (Quartalsstand)"
                if lang == "de"
                else "Necessary Economic Growth (Quarterly Update)"
            )
            sub = (
                f"Aktualisierter Ausgangspunkt {start_ym} (BA-Arbeitslosenquote: {alq_str}; Zielwert Vollbeschäftigung: 3,0 %)"
                if lang == "de"
                else f"Updated starting point {start_ym} (BA unemployment rate: {alq_str}; full-employment target: 3.0%)"
            )
            base = "09_notwendig_quartal"

        src = (
            f"Quelle: Statistisches Bundesamt | Stand: {series['stand_de']}"
            if lang == "de"
            else f"Source: Federal Statistical Office | As of: {series['stand_en']}"
        )
        _apply_common_layout(fig, title, sub, src, height=465)
        fig.update_layout(barmode="stack")
        y_top = max(nec_growth) + 0.6
        fig.update_yaxes(
            title_text="%",
            range=[0, y_top],
            gridcolor="#E2E8F0",
            zeroline=True,
        )
        fig.update_xaxes(showgrid=False)
        stem = base if lang == "de" else f"{base}_en"
        _save_fig(fig, out_dir, stem)


def main():
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

