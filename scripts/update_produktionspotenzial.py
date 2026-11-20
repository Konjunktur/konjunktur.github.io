#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (DE & EN, .png & .html) fuer die Rubrik:
"Produktionspotenzial, Auslastung des Produktionspotenzials, angemessenes/nicht angemessenes Wirtschaftswachstum, notwendiges Wirtschaftswachstum"
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
        "src": "Quelle: Statistisches Bundesamt | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "c1_t": "Produktionspotenzial in Deutschland",
        "c1_s": "Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte, in Mrd. €",
        "c1_l": ["Produktionspotenzial (Mrd. €)"],
        "c2_t": "Auslastung des Produktionspotenzials",
        "c2_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte ab 1991 + aktuelle Quartale)",
        "c2_l": ["Auslastung des Produktionspotenzials (%)", "Mittelwert 1991–2019"],
        "c3_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "c3_s": "Links: Zuwachsrate reales BIP − Potenzial (Ppkt.) | Rechts: Arbeitslose gg. Vj. (%)",
        "c3_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c4_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "c4_s": "Links: Zuwachsrate reales BIP − Potenzial (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "c4_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c5_t": "Auslastung des Produktionspotenzials",
        "c5_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte ab 2019 und aktuelle Quartale)",
        "c5_l": ["Reales BIP in % des Produktionspotenzials"],
        "c6_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "c6_s": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Arbeitslose gg. Vj. (%)",
        "c6_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c7_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "c7_s": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "c7_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c8_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Jahresbasis)",
        "c8_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø) = {wy} %",
        "c9_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Quartal)",
        "c9_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø) = {wy} %",
        "cn_l": ["Arbeitslosenquote (%)", "Notwendiges Wirtschaftswachstum (%)"],
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "src": "Source: Federal Statistical Office | As of: ",
        "leg_svr": "Recession/Weakness (GCEE/BBK)",
        "leg_bip": "Real GDP < 0% YoY",
        "c1_t": "Potential Output in Germany",
        "c1_s": "Annual values from 1991 up to the last completed year, followed by quarterly values, in EUR bn",
        "c1_l": ["Potential output (EUR bn)"],
        "c2_t": "Capacity Utilization of Potential Output",
        "c2_s": "Real GDP as a percentage of potential output (annual values from 1991 + latest quarters)",
        "c2_l": ["Utilization of potential output (%)", "Average 1991–2019"],
        "c3_t": "Suitable/Unsuitable Economic Growth and Unemployment",
        "c3_s": "Left: Real GDP growth − potential growth (pp) | Right: Unemployed persons YoY (%)",
        "c3_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c4_t": "Suitable/Unsuitable Economic Growth and Public Finances",
        "c4_s": "Left: Real GDP growth − potential growth (pp) | Right: Government net lending/borrowing (% of nom. GDP)",
        "c4_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit/surplus (% of nom. GDP, right)"],
        "c5_t": "Utilization of Potential Output",
        "c5_s": "Real GDP as a percentage of potential output (annual values from 2019 and latest quarters)",
        "c5_l": ["Real GDP as a percentage of potential output"],
        "c6_t": "Suitable/Unsuitable GDP Growth and Unemployment",
        "c6_s": "Left: Suitable (+) / not suitable (−) real GDP growth (pp) | Right: Unemployed persons YoY (%)",
        "c6_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c7_t": "Suitable/Unsuitable GDP Growth and Public Finances",
        "c7_s": "Left: Suitable (+) / not suitable (−) real GDP growth (pp) | Right: Government deficit (% of nom. GDP)",
        "c7_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit (% of nom. GDP, right)"],
        "c8_t": "Necessary Economic Growth to Reduce Unemployment (Annual Basis)",
        "c8_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y avg) = {wy}%",
        "c9_t": "Necessary Economic Growth to Reduce Unemployment (Quarterly Update)",
        "c9_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y avg) = {wy}%",
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
            txt = _unpack(requests.post(
                f"{G_BASE}/resultfile",
                headers=headers,
                data={"name": jid, "area": "all", "compress": "false", "language": "de"},
                timeout=90,
            ))
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


def _filter_series(df, req_codes, lbl_terms, z_regex, excl_terms=None, pick="max"):
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
        if excl_terms:
            for eterm in excl_terms:
                mask &= ~ltxt.str.contains(eterm.lower(), regex=False)
        sub = df[mask].copy()
    sub = sub[sub["ZEIT"].astype(str).str.match(z_regex)].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    if pick == "max":
        s = sub.groupby("ZEIT")["NUM"].max()
    elif pick == "min":
        s = sub.groupby("ZEIT")["NUM"].min()
    else:
        s = sub.drop_duplicates(subset=["ZEIT"], keep="first").set_index("ZEIT")["NUM"]
    return s.sort_index()


def load_all_macro_data():
    df_bip_y = _destatis_ffcsv("81000-0001", "1991")
    df_bip_q = _destatis_ffcsv("81000-0002", "1991")

    bip_real_y = _filter_series(df_bip_y, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}$", pick="max")
    if bip_real_y.empty:
        bip_real_y = _filter_series(df_bip_y, {"VGR014"}, ["preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}$", pick="max")

    bip_nom_y = _filter_series(df_bip_y, {"WERTORG", "VGR013"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}$", pick="max")
    if bip_nom_y.empty:
        bip_nom_y = _filter_series(df_bip_y, {"VGR013"}, ["jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}$", pick="max")

    bip_real_q = _filter_series(df_bip_q, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$", pick="max")
    if bip_real_q.empty:
        bip_real_q = _filter_series(df_bip_q, {"VGR014"}, ["preisbereinigt", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$", pick="max")

    bip_nom_q = _filter_series(df_bip_q, {"WERTORG", "VGR013"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$", pick="max")
    if bip_nom_q.empty:
        bip_nom_q = _filter_series(df_bip_q, {"VGR013"}, ["jeweiligen preisen", "bruttoinlandsprodukt"], r"^\d{4}-Q[1-4]$", pick="max")

    bip_chain_q = _filter_series(df_bip_q, {"WERTORG", "VGRPKM"}, ["originalwerte", "preisbereinigt", "verkettet"], r"^\d{4}-Q[1-4]$", pick="max")
    bip_chain_yoy = (bip_chain_q / bip_chain_q.shift(4) - 1.0) * 100.0

    df_et_y = _destatis_ffcsv("81000-0011", "1991")
    df_et_q = _destatis_ffcsv("81000-0012", "1991")

    et_y = _filter_series(df_et_y, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige", "inland"], r"^\d{4}$", pick="max")
    if et_y.empty:
        et_y = _filter_series(df_et_y, set(), ["erwerbstätige", "inland"], r"^\d{4}$", pick="max")

    et_q = _filter_series(df_et_q, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige", "inland"], r"^\d{4}-Q[1-4]$", pick="max")
    if et_q.empty:
        et_q = _filter_series(df_et_q, set(), ["erwerbstätige", "inland"], r"^\d{4}-Q[1-4]$", pick="max")

    df_alo = _destatis_ffcsv("13211-0002", "1991")
    alo_m_raw = _filter_series(df_alo, {"ARB001"}, ["arbeitslose"], r"^\d{4}-\d{2}$", excl_terms=["quote"], pick="max")
    if alo_m_raw.empty:
        alo_m_raw = _filter_series(df_alo, set(), ["arbeitslose"], r"^\d{4}-\d{2}$", excl_terms=["quote"], pick="max")
    alo_m = alo_m_raw / 1000.0 if alo_m_raw.median() > 50000 else alo_m_raw

    # Offizielle BA-Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen (immer die niedrigere der beiden Quoten)
    alq_m = _filter_series(df_alo, set(), ["arbeitslosenquote", "alle zivilen"], r"^\d{4}-\d{2}$", pick="min")
    if alq_m.empty:
        alq_m = _filter_series(df_alo, set(), ["arbeitslosenquote"], r"^\d{4}-\d{2}$", excl_terms=["abhängig"], pick="min")
    if alq_m.empty:
        alq_m = _filter_series(df_alo, {"ALQ001"}, ["arbeitslosenquote"], r"^\d{4}-\d{2}$", pick="min")

    alo_q = alo_m.groupby(lambda z: f"{z[:4]}-Q{(int(z[5:7]) - 1)//3 + 1}").mean()
    alo_y = alo_m.groupby(lambda z: z[:4]).mean()

    df_fin = _destatis_ffcsv("81000-0031", "1991")
    fin_y = _filter_series(df_fin, {"WERTORG"}, ["originalwerte", "finanzierungssaldo", "staat"], r"^\d{4}$", pick="first")
    if fin_y.empty:
        fin_y = _filter_series(df_fin, set(), ["finanzierungssaldo", "staat"], r"^\d{4}$", pick="first")

    fin_q = _filter_series(df_fin, {"WERTORG"}, ["originalwerte", "finanzierungssaldo", "staat"], r"^\d{4}-Q[1-4]$", pick="first")
    if fin_q.empty:
        fin_q = _filter_series(df_fin, set(), ["finanzierungssaldo", "staat"], r"^\d{4}-Q[1-4]$", pick="first")

    return {
        "bip_real_y": bip_real_y, "bip_nom_y": bip_nom_y,
        "bip_real_q": bip_real_q, "bip_nom_q": bip_nom_q,
        "bip_chain_yoy": bip_chain_yoy,
        "et_y": et_y, "et_q": et_q,
        "alo_m": alo_m, "alq_m": alq_m, "alo_q": alo_q, "alo_y": alo_y,
        "fin_y": fin_y, "fin_q": fin_q,
    }


def compute_koehler_tables(d):
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

    return df_y[df_y.index >= "1991"].copy(), df_q[df_q.index >= "1991-Q1"].copy()


def build_hybrid_series(df_y, df_q, start_year="1991", add_gap=False):
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

    return labels, keys, is_q, get_col, completed_years


def get_recession_spans(keys, bip_chain_yoy):
    svr_spans = []
    bip_spans = []
    neg_q = {q for q, v in bip_chain_yoy.items() if not np.isnan(v) and v < 0}
    neg_y = {q[:4] for q in neg_q}

    def _in_svr(kind, k):
        if kind == "Q":
            return any(s <= k <= e for s, e in SVR_PHASES)
        if kind == "Y":
            return any(s[:4] <= k <= e[:4] for s, e in SVR_PHASES)
        return False

    def _in_bip(kind, k):
        if kind == "Q":
            return k in neg_q
        if kind == "Y":
            return k in neg_y
        return False

    def _collect(pred):
        spans = []
        st = None
        for i, (kind, k) in enumerate(keys):
            if kind != "GAP" and pred(kind, k):
                if st is None:
                    st = i
                en = i
            else:
                if st is not None:
                    spans.append((st - 0.5, en + 0.5))
                    st = None
        if st is not None:
            spans.append((st - 0.5, len(keys) - 0.5))
        return spans

    return _collect(_in_svr), _collect(_in_bip)


def add_shades_mpl(ax, svr_spans, bip_spans, t):
    patches = []
    for x0, x1 in svr_spans:
        ax.axvspan(x0, x1, color="#CBD5E1", alpha=0.38, zorder=0)
    if svr_spans:
        patches.append(mpatches.Patch(color="#CBD5E1", alpha=0.55, label=t["leg_svr"]))
    for x0, x1 in bip_spans:
        ax.axvspan(x0, x1, color="#93C5FD", alpha=0.28, zorder=0)
    if bip_spans:
        patches.append(mpatches.Patch(color="#93C5FD", alpha=0.45, label=t["leg_bip"]))
    return patches


def add_shades_plotly(fp, svr_spans, bip_spans, t):
    shapes = []
    for x0, x1 in svr_spans:
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1, fillcolor="rgba(203,213,225,0.38)", line=dict(width=0), layer="below"))
    for x0, x1 in bip_spans:
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1, fillcolor="rgba(147,197,253,0.28)", line=dict(width=0), layer="below"))
    if shapes:
        fp.update_layout(shapes=shapes)
    if svr_spans:
        fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, symbol="square", color="rgba(203,213,225,0.85)"), name=t["leg_svr"], hoverinfo="skip"))
    if bip_spans:
        fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, symbol="square", color="rgba(147,197,253,0.75)"), name=t["leg_bip"], hoverinfo="skip"))


def _write_clean_html(fp, out_html):
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(s)


def compute_necessary_growth(d, df_y, completed_years, mode="year"):
    alq_s = d["alq_m"]
    if alq_s.empty:
        alq_vals = {}
        for ym in d["alo_m"].index:
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
        q_ends = [ym for ym in alq_s.index if ym[5:7] in ("03", "06", "09", "12")]
        start_ym = q_ends[-1] if q_ends else last_ym

    alq0 = round(float(alq_s.loc[start_ym]), 1)

    # Gleitender 5-Jahres-Mittelwert der Zuwachsraten des Produktionspotenzials der letzten 5 abgeschlossenen Jahre (z.B. 2021-2025)
    last5_y = completed_years[-5:]
    g_pot_5y = df_y.loc[last5_y, "g_pot"].dropna()
    wy_star = round(float(g_pot_5y.mean()), 1) if not g_pot_5y.empty else 1.0

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


def save_dual_chart(lang, fname, title, sub, labels, line_vals, line_name, bar_vals, bar_name, bar_color, is_q, svr_spans, bip_spans, lmax, bmax, is_short=False):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))
    fig, ax1 = plt.subplots(figsize=(8.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.90, top=0.77, bottom=0.20)
    ax2 = ax1.twinx()

    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=10.6, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=7.9, color="#334155")

    ax1.set_facecolor("#F8FAFC")
    sh_patches = add_shades_mpl(ax1, svr_spans, bip_spans, t)
    ax1.axhline(0, color="#64748B", lw=1.0, zorder=2)

    b1 = ax2.bar(x, bar_vals, width=0.48 if is_short else 0.58, color=bar_color, alpha=0.82, label=bar_name, zorder=2)
    line_arr = np.array(line_vals, dtype=float)
    l1 = ax1.plot(x, line_arr, color="#1B3A6B", lw=2.3, marker="o" if is_short else None, markersize=4, label=line_name, zorder=4)

    ax1.set_ylim(-lmax, lmax)
    ax2.set_ylim(-bmax, bmax)
    ax1.set_yticks(np.linspace(-lmax, lmax, 7))
    ax2.set_yticks(np.linspace(-bmax, bmax, 7))

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

    handles = [l1[0], b1] + sh_patches
    ax1.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.3)
    fig.text(0.09, 0.015, f"{t['src']}{now_s}", fontsize=6.8, color="#64748B")
    fig.text(0.90, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

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
    add_shades_plotly(fp, svr_spans, bip_spans, t)
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=13.5, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=9.5)),
        margin=dict(l=48, r=48, t=122, b=76),
        height=470,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickfont=dict(size=9.8))
    fp.update_yaxes(fixedrange=True, range=[-lmax, lmax], tickvals=list(np.linspace(-lmax, lmax, 7)), zeroline=True, zerolinecolor="#64748B", secondary_y=False)
    fp.update_yaxes(fixedrange=True, range=[-bmax, bmax], tickvals=list(np.linspace(-bmax, bmax, 7)), showgrid=False, secondary_y=True)
    _write_clean_html(fp, f"{OUT_DIR}/{fname}{t['sfx']}.html")


def save_single_series_chart(lang, fname, title, sub, labels, series_list, is_q, unit_str, svr_spans, bip_spans, mean_val=None, mean_lbl=None, as_bar=False, is_short=False):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.2, 5.1), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.77, bottom=0.20)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=10.8, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=7.9, color="#334155")
    ax.set_facecolor("#F8FAFC")
    sh_patches = add_shades_mpl(ax, svr_spans, bip_spans, t)

    all_vals = []
    line_handles = []
    for vals, lbl, col in series_list:
        all_vals.extend([v for v in vals if not np.isnan(v)])
        if as_bar:
            b = ax.bar(x, vals, width=0.50, color=col, alpha=0.85, label=lbl, zorder=3)
            line_handles.append(b)
            for xi, v in zip(x, vals):
                if not np.isnan(v):
                    ax.text(xi, v + 0.12, fmt_v(v, use_c, 1), ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#0F172A")
        else:
            p = ax.plot(x, vals, color=col, lw=2.3, marker="o" if is_short else None, markersize=4, label=lbl, zorder=3)
            line_handles.extend(p)

    if mean_val is not None and not np.isnan(mean_val):
        m_str = fmt_v(mean_val, use_c, 1)
        m_full = f"{mean_lbl} ({m_str} %)"
        pm = ax.axhline(mean_val, color="#D97706", lw=1.7, ls="--", label=m_full, zorder=4)
        line_handles.append(pm)
        ax.text(len(labels) - 0.6, mean_val + 0.15, m_str, ha="right", va="bottom", fontsize=8.0, fontweight="bold", color="#D97706",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))

    vmin, vmax = min(all_vals), max(all_vals)
    if as_bar:
        ax.set_ylim(max(0, np.floor(vmin - 1.0)), np.ceil(vmax + 0.8))
    else:
        pad = (vmax - vmin) * 0.14 if vmax > vmin else 1.0
        ax.set_ylim(max(0, vmin - pad), vmax + pad)

    ax.set_xticks(x)
    step_lbl = 1 if is_short else 2
    ax.set_xticklabels([lbl if (i % step_lbl == 0 or is_q[i]) else "" for i, lbl in enumerate(labels)], rotation=90, fontsize=7.8, color="#475569")
    ax.tick_params(axis="y", labelsize=8.4, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(handles=line_handles + sh_patches, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.4)
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
    if mean_val is not None and not np.isnan(mean_val):
        m_str = fmt_v(mean_val, use_c, 1)
        m_full = f"{mean_lbl} ({m_str} %)"
        fp.add_trace(go.Scatter(x=labels, y=[round(mean_val, 2)] * len(labels), customdata=[m_str] * len(labels), name=m_full, mode="lines", line=dict(color="#D97706", width=1.8, dash="dash"), hovertemplate=f"{mean_lbl}: <b>%{{customdata}} %</b><extra></extra>"))
    add_shades_plotly(fp, svr_spans, bip_spans, t)
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=13.5, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=9.5)),
        margin=dict(l=48, r=24, t=122, b=76),
        height=470,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickfont=dict(size=9.8))
    if as_bar:
        fp.update_yaxes(fixedrange=True, range=[max(0, np.floor(vmin - 1.0)), np.ceil(vmax + 0.8)])
    else:
        fp.update_yaxes(fixedrange=True)
    _write_clean_html(fp, f"{OUT_DIR}/{fname}{t['sfx']}.html")


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

    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.77, bottom=0.17)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=10.6, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub, ha="left", fontsize=7.9, color="#334155")
    ax.set_facecolor("#F8FAFC")

    bars = ax.bar(x, alq_vals, width=0.45, color="#CBD5E1", edgecolor="#1B3A6B", lw=1.2, label=l_alq, zorder=2)
    for xi, v in zip(x, alq_vals):
        ax.text(xi, v + 0.18, fmt_v(v, use_c, 1), ha="center", va="bottom", fontsize=8.4, fontweight="bold", color="#1B3A6B")

    line = ax.plot(x[1:], nec_vals[1:], color="#D97706", lw=2.5, marker="o", markersize=5, label=l_nec, zorder=4)
    # Kollisionsfreie Beschriftung: immer sauber unterhalb der Linie (bzw. oberhalb, falls nahe an Balkenoberkante)
    text_positions = []
    for xi, v_nec, v_bar in zip(x[1:], nec_vals[1:], alq_vals[1:]):
        if abs((v_nec - 0.50) - v_bar) < 0.45:
            y_pos = v_nec + 0.35
            va_pos = "bottom"
            text_positions.append("top center")
        else:
            y_pos = v_nec - 0.42
            va_pos = "top"
            text_positions.append("bottom center")
        ax.text(
            xi, y_pos, fmt_v(v_nec, use_c, 1),
            ha="center", va=va_pos, fontsize=8.4, fontweight="bold", color="#D97706",
            bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none", alpha=0.88),
            zorder=5,
        )

    ax.set_ylim(0, max(8.0, np.ceil(alq0 + 1.5)))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.0, color="#334155")
    ax.tick_params(axis="y", labelsize=8.5, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(handles=[bars, line[0]], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.8)
    fig.text(0.09, 0.015, f"{t['src']}{now_s}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Bar(x=labels, y=alq_vals, customdata=[fmt_v(v, use_c, 1) for v in alq_vals], name=l_alq, marker_color="#CBD5E1", marker_line_color="#1B3A6B", marker_line_width=1.2, text=[fmt_v(v, use_c, 1) for v in alq_vals], textposition="outside", hovertemplate=f"{l_alq}: <b>%{{customdata}} %</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=labels[1:], y=nec_vals[1:], customdata=[fmt_v(v, use_c, 1) for v in nec_vals[1:]], name=l_nec, mode="lines+markers+text", line=dict(color="#D97706", width=2.6), text=[fmt_v(v, use_c, 1) for v in nec_vals[1:]], textposition=text_positions, textfont=dict(color="#D97706", size=11), hovertemplate=f"{l_nec}: <b>%{{customdata}} %</b><extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11px;color:#334155;font-weight:normal'>{sub}</span>", x=0.02, y=0.96, font=dict(size=13.5, color="#0F172A")),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, yanchor="bottom", font=dict(size=9.5)),
        margin=dict(l=48, r=24, t=122, b=72),
        height=460,
        annotations=[
            dict(text=f"{t['src']}{now_s}", x=0.0, y=-0.21, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.21, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True)
    fp.update_yaxes(fixedrange=True, range=[0, max(8.0, np.ceil(alq0 + 1.5))])
    _write_clean_html(fp, f"{OUT_DIR}/{fname}{t['sfx']}.html")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    d = load_all_macro_data()
    df_y, df_q = compute_koehler_tables(d)

    lbl_long, keys_long, isq_long, get_long, completed_years = build_hybrid_series(df_y, df_q, start_year="1991", add_gap=False)
    lbl_short, keys_short, isq_short, get_short, _ = build_hybrid_series(df_y, df_q, start_year="2019", add_gap=True)

    svr_long, bip_long = get_recession_spans(keys_long, d["bip_chain_yoy"])
    svr_short, bip_short = get_recession_spans(keys_short, d["bip_chain_yoy"])

    # Mittelwert der Auslastung 1991-2019
    ausl_91_19 = df_y.loc[(df_y.index >= "1991") & (df_y.index <= "2019"), "ausl"].dropna()
    mean_ausl_91_19 = float(ausl_91_19.mean()) if not ausl_91_19.empty else np.nan

    start_y, alq0_y, wy_y, rows_y = compute_necessary_growth(d, df_y, completed_years, mode="year")
    start_q, alq0_q, wy_q, rows_q = compute_necessary_growth(d, df_y, completed_years, mode="quarter")

    for lang in ("de", "en"):
        t = TXT[lang]
        # 1-4: Lange Frist (ab 1991)
        save_single_series_chart(lang, "01_potenzial_lang", t["c1_t"], t["c1_s"], lbl_long, [(get_long("pot"), t["c1_l"][0], "#1B3A6B")], isq_long, "Mrd. €", svr_long, bip_long)
        save_single_series_chart(lang, "02_auslastung_lang", t["c2_t"], t["c2_s"], lbl_long, [(get_long("ausl"), t["c2_l"][0], "#1B3A6B")], isq_long, "%", svr_long, bip_long, mean_val=mean_ausl_91_19, mean_lbl=t["c2_l"][1])
        save_dual_chart(lang, "03_angemessen_alo_lang", t["c3_t"], t["c3_s"], lbl_long, get_long("diff"), t["c3_l"][0], get_long("g_alo"), t["c3_l"][1], "#D97706", isq_long, svr_long, bip_long, lmax=3.0, bmax=30.0, is_short=False)
        save_dual_chart(lang, "04_angemessen_staat_lang", t["c4_t"], t["c4_s"], lbl_long, get_long("diff"), t["c4_l"][0], get_long("fin_pct"), t["c4_l"][1], "#059669", isq_long, svr_long, bip_long, lmax=3.0, bmax=12.0, is_short=False)

        # 5-7: Kuerzere Frist (ab 2019)
        save_single_series_chart(lang, "05_auslastung_kurz", t["c5_t"], t["c5_s"], lbl_short, [(get_short("ausl"), t["c5_l"][0], "#D97706")], isq_short, "%", svr_short, bip_short, as_bar=True, is_short=True)
        save_dual_chart(lang, "06_angemessen_alo_kurz", t["c6_t"], t["c6_s"], lbl_short, get_short("diff"), t["c6_l"][0], get_short("g_alo"), t["c6_l"][1], "#D97706", isq_short, svr_short, bip_short, lmax=3.0, bmax=30.0, is_short=True)
        save_dual_chart(lang, "07_angemessen_staat_kurz", t["c7_t"], t["c7_s"], lbl_short, get_short("diff"), t["c7_l"][0], get_short("fin_pct"), t["c7_l"][1], "#059669", isq_short, svr_short, bip_short, lmax=3.0, bmax=12.0, is_short=True)

        # 8-9: Notwendiges Wirtschaftswachstum
        save_necessary_chart(lang, "08_notwendig_jahr", "c8_t", "c8_s", start_y, alq0_y, wy_y, rows_y)
        save_necessary_chart(lang, "09_notwendig_quartal", "c9_t", "c9_s", start_q, alq0_q, wy_q, rows_q)

    print("[OK] Alle 36 Dateien (9 Grafiken x DE/EN x PNG/HTML) unter static/produktionspotenzial/ erzeugt.")


if __name__ == "__main__":
    main()
