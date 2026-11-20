#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (DE & EN, .png & .html) fuer die Rubrik:
"Produktionspotenzial, Auslastung des Produktionspotenzials,
 angemessenes/nicht angemessenes Wirtschaftswachstum, notwendiges Wirtschaftswachstum"
Methode: Claus Koehler / Thorsten Hild
Datenbasis: Statistisches Bundesamt (Destatis GENESIS-Online: 81000-0001, 81000-0002,
            81000-0011, 81000-0012, 81000-0031, 13211-0002)
"""

import os
import re
import io
import csv
import json
import time
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
from plotly.subplots import make_subplots


G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"
D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()
OUT_DIR = "static/produktionspotenzial"

SVR_PHASES = [
    ("1992-Q1", "1993-Q2"),
    ("2001-Q1", "2003-Q2"),
    ("2008-Q2", "2009-Q2"),
    ("2020-Q1", "2020-Q2"),
    ("2022-Q4", "2025-Q4"),
]

ROMAN_Q = {"Q1": "I", "Q2": "II", "Q3": "III", "Q4": "IV"}

TXT = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "src": "Quelle: Statistisches Bundesamt (Destatis, incl. BA-Daten) | Berechnungen: T.H. | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "c1_t": "Produktionspotenzial und reales Bruttoinlandsprodukt (lange Frist)",
        "c1_s": "Jahreswerte bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte, in Mrd. €",
        "c1_l": ["Produktionspotenzial (Mrd. €)", "Reales BIP (Mrd. €)"],
        "c2_t": "Auslastung des Produktionspotenzials (lange Frist)",
        "c2_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte + aktuelle Quartale)",
        "c2_l": ["Auslastung des Produktionspotenzials (%)"],
        "c3_t": "Angemessenes / nicht angemessenes Wirtschaftswachstum und Arbeitslosigkeit (lange Frist)",
        "c3_s": "Linke Skala: Zuwachsrate reales BIP − Zuwachsrate Potenzial (Ppkt.) | Rechte Skala: Arbeitslose gg. Vj. (%)",
        "c3_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c4_t": "Angemessenes / nicht angemessenes Wirtschaftswachstum und Öffentliche Haushalte (lange Frist)",
        "c4_s": "Linke Skala: Zuwachsrate reales BIP − Zuwachsrate Potenzial (Ppkt.) | Rechte Skala: Finanzierungssaldo (% nom. BIP)",
        "c4_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c5_t": "Auslastung des Produktionspotenzials (kürzere Frist)",
        "c5_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte ab 2019 und aktuelle Quartale)",
        "c5_l": ["Reales BIP in % des Produktionspotenzials"],
        "c6_t": "Angemessenes / nicht angemessenes Wirtschaftswachstum und Arbeitslosigkeit (kürzere Frist)",
        "c6_s": "Linke Skala: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechte Skala: Arbeitslose gg. Vj. (%)",
        "c6_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c7_t": "Angemessenes / nicht angemessenes Wirtschaftswachstum und Öffentliche Haushalte (kürzere Frist)",
        "c7_s": "Linke Skala: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechte Skala: Finanzierungssaldo (% nom. BIP)",
        "c7_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c8_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Jahresbasis)",
        "c8_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis Vollbeschäftigung (≤ 3,0 %) | wY* = {wy} %",
        "c9_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Quartalsaktualisierung)",
        "c9_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis Vollbeschäftigung (≤ 3,0 %) | wY* = {wy} %",
        "cn_l": ["Arbeitslosenquote (%)", "Notwendiges Wirtschaftswachstum (%)"],
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "src": "Source: Federal Statistical Office (Destatis, incl. BA data) | Calculations: T.H. | As of: ",
        "leg_svr": "Recession/Weakness (GCEE/BBK)",
        "leg_bip": "Real GDP < 0% YoY",
        "c1_t": "Potential Output and Real Gross Domestic Product (Long Run)",
        "c1_s": "Annual values up to the last completed year, followed by quarterly values, in EUR bn",
        "c1_l": ["Potential output (EUR bn)", "Real GDP (EUR bn)"],
        "c2_t": "Capacity Utilization of Potential Output (Long Run)",
        "c2_s": "Real GDP as a percentage of potential output (annual values + latest quarters)",
        "c2_l": ["Utilization of potential output (%)"],
        "c3_t": "Suitable / Unsuitable Economic Growth and Unemployment (Long Run)",
        "c3_s": "Left axis: Real GDP growth − potential growth (pp) | Right axis: Unemployed persons YoY (%)",
        "c3_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c4_t": "Suitable / Unsuitable Economic Growth and Public Finances (Long Run)",
        "c4_s": "Left axis: Real GDP growth − potential growth (pp) | Right axis: Government net lending/borrowing (% of nom. GDP)",
        "c4_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit/surplus (% of nom. GDP, right)"],
        "c5_t": "Utilization of Potential Output (Short Run)",
        "c5_s": "Real GDP as a percentage of potential output (annual values from 2019 and latest quarters)",
        "c5_l": ["Real GDP as a percentage of potential output"],
        "c6_t": "Suitable / Unsuitable GDP Growth and Unemployment (Short Run)",
        "c6_s": "Left axis: Suitable (+) / not suitable (−) real GDP growth (pp) | Right axis: Unemployed persons YoY (%)",
        "c6_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c7_t": "Suitable / Unsuitable GDP Growth and Public Finances (Short Run)",
        "c7_s": "Left axis: Suitable (+) / not suitable (−) real GDP growth (pp) | Right axis: Government deficit (% of nom. GDP)",
        "c7_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit (% of nom. GDP, right)"],
        "c8_t": "Necessary Economic Growth to Reduce Unemployment (Annual Basis)",
        "c8_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to full employment (≤ 3.0%) | wY* = {wy}%",
        "c9_t": "Necessary Economic Growth to Reduce Unemployment (Quarterly Update)",
        "c9_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to full employment (≤ 3.0%) | wY* = {wy}%",
        "cn_l": ["Unemployment rate (%)", "Necessary economic growth (%)"],
    },
}


def fmt_v(val, comma=True, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if comma else s


def _destatis_ffcsv(table, startyear="1991", extra=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER / DESTATIS_PASS fehlen in den Environment-Variablen.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    if extra:
        data.update(extra)

    def _unpack(resp):
        if resp.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                cname = next(n for n in zf.namelist() if n.endswith(".csv"))
                return zf.read(cname).decode("utf-8", errors="replace")
        return resp.text

    raw = _unpack(requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90))
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        st = str(json.loads(rj.text).get("Status", {}).get("Content", ""))
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", st)
        if not m:
            raise RuntimeError(f"Destatis Job-ID nicht gefunden ({table}): {st[:180]}")
        jid = m.group(1)
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            txt = _unpack(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": jid, "area": "all", "compress": "false", "language": "de"}, timeout=90))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
        if not raw:
            raise RuntimeError(f"Destatis Job-Timeout ({table} / {jid})")

    rows = [r for r in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(r) >= 5]
    if len(rows) < 3:
        return pd.DataFrame()
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([r[:len(hdr)] for r in rows if len(r) >= len(hdr)], columns=hdr)
    cmap = {c.lower(): c for c in df.columns}
    t_col = cmap.get("time") or cmap.get("zeit")
    v_col = cmap.get("value") or cmap.get("wert")
    zeit_s = df[t_col].astype(str).str.strip()
    for c in df.columns:
        if c in (t_col, v_col) or "label" in c.lower():
            continue
        sc = df[c].astype(str).str.strip()
        if sc.str.match(r"^QUART0?[1-4]$", case=False).any():
            qe = sc.str.extract(r"([1-4])", expand=False)
            zeit_s = pd.Series(np.where(qe.notna(), zeit_s + "-Q" + qe.fillna(""), zeit_s), index=df.index)
            break
        if sc.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            me = sc.str.extract(r"([0-9]+)", expand=False).str.zfill(2)
            zeit_s = pd.Series(np.where(me.notna(), zeit_s + "-" + me.fillna(""), zeit_s), index=df.index)
            break
    df["ZEIT"] = zeit_s
    df["NUM"] = pd.to_numeric(df[v_col].astype(str).str.replace(",", "."), errors="coerce")
    return df.dropna(subset=["NUM"]).copy()


def _filter_series(df, req_codes, lbl_terms, z_regex):
    ccols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    sub = pd.DataFrame()
    if req_codes and ccols:
        csets = df[ccols].fillna("").astype(str).apply(lambda r: {x.strip().upper() for x in r if x.strip()}, axis=1)
        sub = df[csets.apply(lambda s: req_codes.issubset(s))].copy()
    if sub.empty and lbl_terms:
        lcols = [c for c in df.columns if "label" in c.lower()]
        ltxt = df[lcols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
        mask = pd.Series(True, index=df.index)
        for term in lbl_terms:
            mask &= ltxt.str.contains(term.lower(), regex=False)
        sub = df[mask].copy()
    sub = sub[sub["ZEIT"].astype(str).str.match(z_regex)].drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
    return pd.Series(sub["NUM"].values, index=sub["ZEIT"].astype(str).values).sort_index()


def load_all_macro_data():
    # 1. BIP real (unverkettet, Mrd. EUR) & nominal (Mrd. EUR) - Jahre (81000-0001) & Quartale (81000-0002)
    df_bip_y = _destatis_ffcsv("81000-0001", "1991")
    df_bip_q = _destatis_ffcsv("81000-0002", "1991")

    bip_real_y = _filter_series(df_bip_y, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}$")
    if bip_real_y.empty:
        bip_real_y = _filter_series(df_bip_y, {"VGR014"}, ["preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}$")
    bip_nom_y = _filter_series(df_bip_y, {"WERTORG", "VGR013"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}$")
    if bip_nom_y.empty:
        bip_nom_y = _filter_series(df_bip_y, {"VGR013"}, ["jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}$")

    bip_real_q = _filter_series(df_bip_q, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$")
    if bip_real_q.empty:
        bip_real_q = _filter_series(df_bip_q, {"VGR014"}, ["preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$")
    bip_nom_q = _filter_series(df_bip_q, {"WERTORG", "VGR013"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$")
    if bip_nom_q.empty:
        bip_nom_q = _filter_series(df_bip_q, {"VGR013"}, ["jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$")

    bip_chain_q = _filter_series(df_bip_q, {"WERTORG", "VGRPKM"}, ["originalwerte", "preisbereinigt", "verkettet"], r"^\d{4}-Q[1-4]$")
    bip_chain_yoy = (bip_chain_q / bip_chain_q.shift(4) - 1.0) * 100.0

    # 2. Erwerbstaetige Inland (Tsd.) - Jahre (81000-0011) & Quartale (81000-0012)
    df_et_y = _destatis_ffcsv("81000-0011", "1991")
    df_et_q = _destatis_ffcsv("81000-0012", "1991")
    et_y = _filter_series(df_et_y, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige", "inland"], r"^\d{4}$")
    if et_y.empty:
        et_y = _filter_series(df_et_y, set(), ["erwerbstätige", "inland"], r"^\d{4}$")
    et_q = _filter_series(df_et_q, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige", "inland"], r"^\d{4}-Q[1-4]$")
    if et_q.empty:
        et_q = _filter_series(df_et_q, set(), ["erwerbstätige", "inland"], r"^\d{4}-Q[1-4]$")

    # 3. Arbeitslose BA & Arbeitslosenquote (13211-0002 monatlich -> Quartals- & Jahresmittel)
    df_alo = _destatis_ffcsv("13211-0002", "1991")
    alo_m_raw = _filter_series(df_alo, {"ARB001"}, ["arbeitslose"], r"^\d{4}-\d{2}$")
    if alo_m_raw.empty:
        alo_m_raw = _filter_series(df_alo, set(), ["arbeitslose"], r"^\d{4}-\d{2}$")
    # In Tsd. normieren (falls 13211-0002 in Personen liefert)
    alo_m = alo_m_raw / 1000.0 if alo_m_raw.median() > 50000 else alo_m_raw

    alq_m = _filter_series(df_alo, {"ALQ001"}, ["arbeitslosenquote"], r"^\d{4}-\d{2}$")
    if alq_m.empty:
        alq_m = _filter_series(df_alo, set(), ["arbeitslosenquote"], r"^\d{4}-\d{2}$")

    alo_q = alo_m.groupby(lambda z: f"{z[:4]}-Q{(int(z[5:7]) - 1)//3 + 1}").mean()
    alo_y = alo_m.groupby(lambda z: z[:4]).mean()

    # 4. Finanzierungssaldo des Staates (Mrd. EUR) - Jahre & Quartale (81000-0031)
    df_fin = _destatis_ffcsv("81000-0031", "1991")
    fin_y = _filter_series(df_fin, set(), ["finanzierungssaldo", "staat"], r"^\d{4}$")
    fin_q = _filter_series(df_fin, set(), ["finanzierungssaldo", "staat"], r"^\d{4}-Q[1-4]$")

    return {
        "bip_real_y": bip_real_y, "bip_nom_y": bip_nom_y,
        "bip_real_q": bip_real_q, "bip_nom_q": bip_nom_q,
        "bip_chain_yoy": bip_chain_yoy,
        "et_y": et_y, "et_q": et_q,
        "alo_m": alo_m, "alq_m": alq_m, "alo_q": alo_q, "alo_y": alo_y,
        "fin_y": fin_y, "fin_q": fin_q,
    }


def compute_koehler_tables(d):
    # Jahresreihe (ab 1992 fuer YoY-Wachstum ab 1993)
    idx_y = d["bip_real_y"].index.intersection(d["et_y"].index).intersection(d["alo_y"].index).sort_values()
    df_y = pd.DataFrame(index=idx_y)
    df_y["bip_real"] = d["bip_real_y"].loc[idx_y]
    df_y["et"] = d["et_y"].loc[idx_y]
    df_y["alo"] = d["alo_y"].loc[idx_y]
    df_y["prod"] = (df_y["bip_real"] * 1e6) / df_y["et"]
    df_y["pot"] = ((df_y["et"] + df_y["alo"]) * df_y["prod"]) / 1e6
    df_y["ausl"] = (df_y["bip_real"] / df_y["pot"]) * 100.0
    df_y["g_bip"] = (df_y["bip_real"] / df_y["bip_real"].shift(1) - 1.0) * 100.0
    df_y["g_pot"] = (df_y["pot"] / df_y["pot"].shift(1) - 1.0) * 100.0
    df_y["diff"] = df_y["g_bip"] - df_y["g_pot"]
    df_y["g_alo"] = (df_y["alo"] / df_y["alo"].shift(1) - 1.0) * 100.0
    common_fin_y = idx_y.intersection(d["fin_y"].index).intersection(d["bip_nom_y"].index)
    df_y["fin_pct"] = np.nan
    df_y.loc[common_fin_y, "fin_pct"] = (d["fin_y"].loc[common_fin_y] / d["bip_nom_y"].loc[common_fin_y]) * 100.0

    # Quartalsreihe (ab 1992-Q1 fuer YoY-Wachstum ab 1993-Q1)
    idx_q = d["bip_real_q"].index.intersection(d["et_q"].index).intersection(d["alo_q"].index).sort_values()
    df_q = pd.DataFrame(index=idx_q)
    df_q["bip_real"] = d["bip_real_q"].loc[idx_q]
    df_q["et"] = d["et_q"].loc[idx_q]
    df_q["alo"] = d["alo_q"].loc[idx_q]
    df_q["prod"] = (df_q["bip_real"] * 1e6) / df_q["et"]
    df_q["pot"] = ((df_q["et"] + df_q["alo"]) * df_q["prod"]) / 1e6
    df_q["ausl"] = (df_q["bip_real"] / df_q["pot"]) * 100.0
    df_q["g_bip"] = (df_q["bip_real"] / df_q["bip_real"].shift(4) - 1.0) * 100.0
    df_q["g_pot"] = (df_q["pot"] / df_q["pot"].shift(4) - 1.0) * 100.0
    df_q["diff"] = df_q["g_bip"] - df_q["g_pot"]
    df_q["g_alo"] = (df_q["alo"] / df_q["alo"].shift(4) - 1.0) * 100.0
    common_fin_q = idx_q.intersection(d["fin_q"].index).intersection(d["bip_nom_q"].index)
    df_q["fin_pct"] = np.nan
    df_q.loc[common_fin_q, "fin_pct"] = (d["fin_q"].loc[common_fin_q] / d["bip_nom_q"].loc[common_fin_q]) * 100.0

    return df_y[df_y.index >= "1993"].copy(), df_q[df_q.index >= "1993-Q1"].copy()


def build_hybrid_series(df_y, df_q, start_year="1993", add_gap=False):
    # Abgeschlossene Jahre = alle Jahre, fuer die 4 Quartale vorliegen
    q_counts = df_q.index.str[:4].value_counts()
    completed_years = sorted([y for y, cnt in q_counts.items() if cnt == 4 and y in df_y.index and y >= start_year])
    last_comp_y = completed_years[-1]
    rem_q = sorted([q for q in df_q.index if q[:4] > last_comp_y])

    labels, keys, is_q = [], [], []
    for y in completed_years:
        labels.append(y)
        keys.append(("Y", y))
        is_q.append(False)
    if add_gap and rem_q:
        labels.append("")
        keys.append(("GAP", ""))
        is_q.append(False)
    for q in rem_q:
        labels.append(f"{q[:4]} {ROMAN_Q[q[-2:]]}")
        keys.append(("Q", q))
        is_q.append(True)

    def get_col(col):
        vals = []
        for kind, k in keys:
            if kind == "Y":
                vals.append(float(df_y.loc[k, col]))
            elif kind == "Q":
                vals.append(float(df_q.loc[k, col]))
            else:
                vals.append(np.nan)
        return vals

    return labels, keys, is_q, get_col


def compute_necessary_growth(d, df_y, df_q, mode="year"):
    alq_s = d["alq_m"]
    if alq_s.empty:
        # Fallback aus ALO / (ET + ALO)
        m_idx = d["alo_m"].index
        alq_vals = {}
        for ym in m_idx:
            qk = f"{ym[:4]}-Q{(int(ym[5:7]) - 1)//3 + 1}"
            if qk in d["et_q"].index:
                a = float(d["alo_m"].loc[ym])
                e = float(d["et_q"].loc[qk])
                alq_vals[ym] = round(a / (e + a) * 100.0, 1)
        alq_s = pd.Series(alq_vals).sort_index()

    last_ym = alq_s.index[-1]
    cur_yr = int(last_ym[:4])
    if mode == "year":
        jan_ym = f"{cur_yr}-01"
        start_ym = jan_ym if jan_ym in alq_s.index else last_ym
    else:
        # Letzter verfuegbarer Quartalsendmonat (03, 06, 09, 12), sonst aktueller Monat
        q_ends = [ym for ym in alq_s.index if ym[5:7] in ("03", "06", "09", "12")]
        start_ym = q_ends[-1] if q_ends else last_ym

    alq0 = round(float(alq_s.loc[start_ym]), 1)
    # Potenzialwachstum wY* aus aktuellem Wert (begrenzt auf realistischen Bereich)
    wy_raw = float(df_q["g_pot"].dropna().iloc[-1]) if not df_q["g_pot"].dropna().empty else 1.0
    wy_star = round(float(np.clip(wy_raw, 0.5, 2.5)), 1)

    rows = [{"ym": start_ym, "yr": int(start_ym[:4]), "alq": alq0, "w_growth": np.nan}]
    prev_alq = alq0
    step_yr = int(start_ym[:4])
    while prev_alq > 3.0 and len(rows) <= 8:
        next_alq = round(max(prev_alq - 1.0, 0.0), 1)
        w_1_alq = ((1.0 + next_alq / 100.0) / (1.0 + prev_alq / 100.0) - 1.0) * 100.0
        w_nec = round(wy_star - w_1_alq, 1)
        rows.append({"ym": None, "yr": step_yr, "alq": next_alq, "w_growth": w_nec})
        prev_alq = next_alq
        step_yr += 1
    return start_ym, alq0, wy_star, rows


def save_dual_chart(lang, fname, title, sub, labels, line_vals, line_name, bar_vals, bar_name, bar_color, is_q, is_short=False):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))

    fig, ax1 = plt.subplots(figsize=(8.2, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.90, top=0.78, bottom=0.22)
    ax2 = ax1.twinx()

    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=8.1, color="#334155")

    ax1.set_facecolor("#F8FAFC")
    ax1.axhline(0, color="#64748B", lw=1.0, zorder=2)
    b1 = ax2.bar(x, bar_vals, width=0.48 if is_short else 0.58, color=bar_color, alpha=0.82, label=bar_name, zorder=2)
    # Linie: Jahres- und Quartalsabschnitt getrennt zeichnen, falls Luecke vorhanden
    line_arr = np.array(line_vals, dtype=float)
    l1 = ax1.plot(x, line_arr, color="#1B3A6B", lw=2.3, marker="o" if is_short else None, markersize=4, label=line_name, zorder=4)

    lmax = max(1.0, float(np.nanmax(np.abs(line_arr))) * 1.25)
    lmax = np.ceil(lmax * 2) / 2.0
    ax1.set_ylim(-lmax, lmax)
    bmax = max(5.0, float(np.nanmax(np.abs(np.array(bar_vals, dtype=float)))) * 1.2)
    bmax = np.ceil(bmax / 5.0) * 5.0
    ax2.set_ylim(-bmax, bmax)

    ax1.set_xticks(x)
    step_lbl = 1 if is_short else 2
    ax1.set_xticklabels([lbl if (i % step_lbl == 0 or is_q[i]) else "" for i, lbl in enumerate(labels)], rotation=90, fontsize=7.8, color="#475569")
    ax1.tick_params(axis="y", labelsize=8.3, colors="#1B3A6B", length=0)
    ax2.tick_params(axis="y", labelsize=8.3, colors=bar_color, length=0)
    ax1.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)
    for ax in (ax1, ax2):
        for s in ("top", "left", "right"):
            ax.spines[s].set_visible(False)
    ax1.spines["bottom"].set_color("#94A3B8")

    handles = [l1[0], b1]
    ax1.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.6)
    fig.text(0.09, 0.015, f"{t['src']}{now_s}", fontsize=6.8, color="#64748B")
    fig.text(0.90, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    # Plotly HTML
    fp = make_subplots(specs=[[{"secondary_y": True}]])
    fp.add_trace(
        go.Bar(
            x=labels,
            y=[None if np.isnan(v) else round(v, 2) for v in bar_vals],
            customdata=[fmt_v(v, use_c, 1) for v in bar_vals],
            name=bar_name,
            marker_color=bar_color,
            opacity=0.82,
            hovertemplate=f"{bar_name}: <b>%{{customdata}} %</b><extra></extra>",
        ),
        secondary_y=True,
    )
    fp.add_trace(
        go.Scatter(
            x=labels,
            y=[None if np.isnan(v) else round(v, 2) for v in line_vals],
            customdata=[fmt_v(v, use_c, 2) for v in line_vals],
            name=line_name,
            mode="lines+markers" if is_short else "lines",
            line=dict(color="#1B3A6B", width=2.4),
            connectgaps=False,
            hovertemplate=f"{line_name}: <b>%{{customdata}} Ppkt.</b><extra></extra>",
        ),
        secondary_y=False,
    )
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11.5px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=14, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=10)),
        margin=dict(l=48, r=48, t=125, b=82),
        height=490,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickfont=dict(size=10))
    fp.update_yaxes(fixedrange=True, range=[-lmax, lmax], zeroline=True, zerolinecolor="#64748B", secondary_y=False)
    fp.update_yaxes(fixedrange=True, range=[-bmax, bmax], showgrid=False, secondary_y=True)
    out_html = f"{OUT_DIR}/{fname}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})


def save_single_series_chart(lang, fname, title, sub, labels, series_list, is_q, unit_str, as_bar=False, is_short=False):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(8.2, 5.3), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.78, bottom=0.22)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=8.1, color="#334155")
    ax.set_facecolor("#F8FAFC")

    all_vals = []
    for vals, lbl, col in series_list:
        all_vals.extend([v for v in vals if not np.isnan(v)])
        if as_bar:
            bars = ax.bar(x, vals, width=0.50, color=col, alpha=0.85, label=lbl, zorder=3)
            for xi, v in zip(x, vals):
                if not np.isnan(v):
                    ax.text(xi, v + 0.12, fmt_v(v, use_c, 1), ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#0F172A")
        else:
            ax.plot(x, vals, color=col, lw=2.2, marker="o" if is_short else None, markersize=4, label=lbl, zorder=3)

    vmin, vmax = min(all_vals), max(all_vals)
    if as_bar:
        ax.set_ylim(max(0, np.floor(vmin - 1.0)), np.ceil(vmax + 0.8))
    else:
        pad = (vmax - vmin) * 0.12 if vmax > vmin else 1.0
        ax.set_ylim(max(0, vmin - pad), vmax + pad)

    ax.set_xticks(x)
    step_lbl = 1 if is_short else 2
    ax.set_xticklabels([lbl if (i % step_lbl == 0 or is_q[i]) else "" for i, lbl in enumerate(labels)], rotation=90, fontsize=7.8, color="#475569")
    ax.tick_params(axis="y", labelsize=8.4, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.8)
    fig.text(0.09, 0.015, f"{t['src']}{now_s}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    for vals, lbl, col in series_list:
        if as_bar:
            fp.add_trace(go.Bar(x=labels, y=[None if np.isnan(v) else round(v, 2) for v in vals], customdata=[fmt_v(v, use_c, 1) for v in vals], name=lbl, marker_color=col, text=[fmt_v(v, use_c, 1) for v in vals], textposition="outside", hovertemplate=f"{lbl}: <b>%{{customdata}} {unit_str}</b><extra></extra>"))
        else:
            fp.add_trace(go.Scatter(x=labels, y=[None if np.isnan(v) else round(v, 2) for v in vals], customdata=[fmt_v(v, use_c, 1) for v in vals], name=lbl, mode="lines+markers" if is_short else "lines", line=dict(color=col, width=2.3), connectgaps=False, hovertemplate=f"{lbl}: <b>%{{customdata}} {unit_str}</b><extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11.5px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=14, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=10)),
        margin=dict(l=48, r=24, t=125, b=82),
        height=490,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickfont=dict(size=10))
    if as_bar:
        fp.update_yaxes(fixedrange=True, range=[max(0, np.floor(vmin - 1.0)), np.ceil(vmax + 0.8)])
    else:
        fp.update_yaxes(fixedrange=True)
    fp.write_html(f"{OUT_DIR}/{fname}{t['sfx']}.html", include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})


def save_necessary_chart(lang, fname, title_key, sub_key, start_ym, alq0, wy_star, rows):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    m_idx = int(start_ym[5:7]) - 1
    start_lbl = f"{t['m'][m_idx]} {start_ym[2:4]}"
    labels = [start_lbl] + [str(r["yr"]) for r in rows[1:]]
    alq_vals = [r["alq"] for r in rows]
    nec_vals = [r["w_growth"] for r in rows]

    title = t[title_key]
    sub = t[sub_key].format(start_lbl=start_lbl, alq0=fmt_v(alq0, use_c, 1), wy=fmt_v(wy_star, use_c, 1))
    l_alq, l_nec = t["cn_l"]

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.78, bottom=0.18)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=8.1, color="#334155")
    ax.set_facecolor("#F8FAFC")

    bars = ax.bar(x, alq_vals, width=0.45, color="#CBD5E1", edgecolor="#1B3A6B", lw=1.2, label=l_alq, zorder=2)
    for xi, v in zip(x, alq_vals):
        ax.text(xi, v + 0.18, fmt_v(v, use_c, 1), ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1B3A6B")

    line = ax.plot(x[1:], nec_vals[1:], color="#D97706", lw=2.5, marker="o", markersize=5, label=l_nec, zorder=4)
    for xi, v in zip(x[1:], nec_vals[1:]):
        ax.text(xi, v - 0.55, fmt_v(v, use_c, 1), ha="center", va="top", fontsize=8.5, fontweight="bold", color="#D97706")

    ax.set_ylim(0, max(8.0, np.ceil(alq0 + 1.5)))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.0, color="#334155")
    ax.tick_params(axis="y", labelsize=8.5, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(handles=[bars, line[0]], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=8.0)
    fig.text(0.09, 0.015, f"{t['src']}{now_s}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Bar(x=labels, y=alq_vals, customdata=[fmt_v(v, use_c, 1) for v in alq_vals], name=l_alq, marker_color="#CBD5E1", marker_line_color="#1B3A6B", marker_line_width=1.2, text=[fmt_v(v, use_c, 1) for v in alq_vals], textposition="outside", hovertemplate=f"{l_alq}: <b>%{{customdata}} %</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=labels[1:], y=nec_vals[1:], customdata=[fmt_v(v, use_c, 1) for v in nec_vals[1:]], name=l_nec, mode="lines+markers+text", line=dict(color="#D97706", width=2.6), text=[fmt_v(v, use_c, 1) for v in nec_vals[1:]], textposition="bottom center", hovertemplate=f"{l_nec}: <b>%{{customdata}} %</b><extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11.5px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=14, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=10)),
        margin=dict(l=48, r=24, t=125, b=78),
        height=475,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True)
    fp.update_yaxes(fixedrange=True, range=[0, max(8.0, np.ceil(alq0 + 1.5))])
    fp.write_html(f"{OUT_DIR}/{fname}{t['sfx']}.html", include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    d = load_all_macro_data()
    df_y, df_q = compute_koehler_tables(d)

    lbl_long, _, isq_long, get_long = build_hybrid_series(df_y, df_q, start_year="1993", add_gap=False)
    lbl_short, _, isq_short, get_short = build_hybrid_series(df_y, df_q, start_year="2019", add_gap=True)

    start_y, alq0_y, wy_y, rows_y = compute_necessary_growth(d, df_y, df_q, mode="year")
    start_q, alq0_q, wy_q, rows_q = compute_necessary_growth(d, df_y, df_q, mode="quarter")

    for lang in ("de", "en"):
        t = TXT[lang]
        # 1-4: Lange Frist (ab 1993)
        save_single_series_chart(lang, "01_potenzial_lang", t["c1_t"], t["c1_s"], lbl_long, [(get_long("pot"), t["c1_l"][0], "#1B3A6B"), (get_long("bip_real"), t["c1_l"][1], "#D97706")], isq_long, "Mrd. €")
        save_single_series_chart(lang, "02_auslastung_lang", t["c2_t"], t["c2_s"], lbl_long, [(get_long("ausl"), t["c2_l"][0], "#1B3A6B")], isq_long, "%")
        save_dual_chart(lang, "03_angemessen_alo_lang", t["c3_t"], t["c3_s"], lbl_long, get_long("diff"), t["c3_l"][0], get_long("g_alo"), t["c3_l"][1], "#D97706", isq_long, is_short=False)
        save_dual_chart(lang, "04_angemessen_staat_lang", t["c4_t"], t["c4_s"], lbl_long, get_long("diff"), t["c4_l"][0], get_long("fin_pct"), t["c4_l"][1], "#059669", isq_long, is_short=False)

        # 5-7: Kuerzere Frist (ab 2019)
        save_single_series_chart(lang, "05_auslastung_kurz", t["c5_t"], t["c5_s"], lbl_short, [(get_short("ausl"), t["c5_l"][0], "#D97706")], isq_short, "%", as_bar=True, is_short=True)
        save_dual_chart(lang, "06_angemessen_alo_kurz", t["c6_t"], t["c6_s"], lbl_short, get_short("diff"), t["c6_l"][0], get_short("g_alo"), t["c6_l"][1], "#2563EB", isq_short, is_short=True)
        save_dual_chart(lang, "07_angemessen_staat_kurz", t["c7_t"], t["c7_s"], lbl_short, get_short("diff"), t["c7_l"][0], get_short("fin_pct"), t["c7_l"][1], "#059669", isq_short, is_short=True)

        # 8-9: Notwendiges Wirtschaftswachstum
        save_necessary_chart(lang, "08_notwendig_jahr", "c8_t", "c8_s", start_y, alq0_y, wy_y, rows_y)
        save_necessary_chart(lang, "09_notwendig_quartal", "c9_t", "c9_s", start_q, alq0_q, wy_q, rows_q)

    print("[OK] Alle 36 Dateien (9 Grafiken x DE/EN x PNG/HTML) unter static/produktionspotenzial/ erzeugt.")


if __name__ == "__main__":
    main()

