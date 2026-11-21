#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (DE & EN, .png und .html) fuer die Rubrik:
"Produktionspotenzial, Auslastung des Produktionspotenzials,
angemessenes/nicht angemessenes Wirtschaftswachstum, notwendiges Wirtschaftswachstum"
Methode: Claus Koehler / Thorsten Hild
Datenbasis: Statistisches Bundesamt (GENESIS-Online)
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

# SVR / Deutsche Bundesbank Rezessions- und Schwaechephasen ab 1991
SVR_PHASES_Y = [
    (1992, 1993),
    (2001, 2003),
    (2008, 2009),
    (2020, 2020),
    (2022, 2025),
]

SVR_PHASES_M = [
    ("1992-01", "1993-04"),
    ("2001-01", "2003-06"),
    ("2008-01", "2009-04"),
    ("2020-02", "2020-04"),
    ("2022-10", "2025-12"),
]

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "src": "Quelle: Statistisches Bundesamt | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "g1_t": "Produktionspotenzial in Deutschland",
        "g1_sub": "In Mrd. € | Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte (4-Quartals-Summe)",
        "g1_l": ["Produktionspotenzial (Basis)", "Produktionspotenzial (inkl. Kurzarbeit)"],
        "g2_t": "Auslastung des Produktionspotenzials",
        "g2_sub": "Reales BIP in % des Produktionspotenzials | Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte",
        "g2_l": ["Auslastung (Basis)", "Auslastung (inkl. Kurzarbeit)", "Mittelwert 1991–2019"],
        "g3_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "g3_sub": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Zuwachsrate Arbeitslose (%)",
        "g3_l": ["Angemessenes (+)/nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "g4_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "g4_sub": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "g4_l": ["Angemessenes (+)/nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "g5_t": "Auslastung des Produktionspotenzials",
        "g5_sub": "Reales BIP in % des Produktionspotenzials | Jahreswerte ab 2019 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte",
        "g5_l": ["Auslastung des Produktionspotenzials (%)"],
        "g6_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "g6_sub": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Zuwachsrate Arbeitslose (%)",
        "g6_l": ["Angemessenes (+)/nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "g7_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "g7_sub": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "g7_l": ["Angemessenes (+)/nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "g8_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Jahresbasis)",
        "g8_sub": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø {wy_span}) = {wy_star} %",
        "g8_l": ["Arbeitslosenquote (%)", "Notwendiges Wirtschaftswachstum (%)"],
        "g9_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Quartal)",
        "g9_sub": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø {wy_span}) = {wy_star} %",
        "g9_l": ["Arbeitslosenquote (%)", "Notwendiges Wirtschaftswachstum (%)"],
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "src": "Source: Federal Statistical Office | As of: ",
        "leg_svr": "Recession/Weakness (GCEE/BBK)",
        "leg_bip": "Real GDP < 0% YoY",
        "g1_t": "Potential Output in Germany",
        "g1_sub": "In EUR bn | Annual values from 1991 to the last completed year, followed by quarterly values (4-quarter sum)",
        "g1_l": ["Potential output (baseline)", "Potential output (incl. short-time work)"],
        "g2_t": "Capacity Utilization of Potential Output",
        "g2_sub": "Real GDP as a % of potential output | Annual values from 1991 to the last completed year, followed by quarterly values",
        "g2_l": ["Utilization (baseline)", "Utilization (incl. short-time work)", "1991–2019 mean"],
        "g3_t": "Appropriate/Inappropriate Growth and Unemployment",
        "g3_sub": "Left: Appropriate (+) / inappropriate (−) growth (pp) | Right: Unemployment growth rate (%)",
        "g3_l": ["Appropriate (+)/inappropriate (−) growth (pp, left)", "Unemployment growth rate (%, right)"],
        "g4_t": "Appropriate/Inappropriate Growth and Public Budgets",
        "g4_sub": "Left: Appropriate (+) / inappropriate (−) growth (pp) | Right: Government net lending/borrowing (% of nom. GDP)",
        "g4_l": ["Appropriate (+)/inappropriate (−) growth (pp, left)", "Government balance (% of nom. GDP, right)"],
        "g5_t": "Capacity Utilization of Potential Output",
        "g5_sub": "Real GDP as a % of potential output | Annual values from 2019 to the last completed year, followed by quarterly values",
        "g5_l": ["Capacity utilization of potential output (%)"],
        "g6_t": "Appropriate/Inappropriate Growth and Unemployment",
        "g6_sub": "Left: Appropriate (+) / inappropriate (−) growth (pp) | Right: Unemployment growth rate (%)",
        "g6_l": ["Appropriate (+)/inappropriate (−) growth (pp, left)", "Unemployment growth rate (%, right)"],
        "g7_t": "Appropriate/Inappropriate Growth and Public Budgets",
        "g7_sub": "Left: Appropriate (+) / inappropriate (−) growth (pp) | Right: Government net lending/borrowing (% of nom. GDP)",
        "g7_l": ["Appropriate (+)/inappropriate (−) growth (pp, left)", "Government balance (% of nom. GDP, right)"],
        "g8_t": "Necessary Economic Growth to Reduce Unemployment (Annual Basis)",
        "g8_sub": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y-avg {wy_span}) = {wy_star}%",
        "g8_l": ["Unemployment rate (%)", "Necessary economic growth (%)"],
        "g9_t": "Necessary Economic Growth to Reduce Unemployment (Quarterly Update)",
        "g9_sub": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y-avg {wy_span}) = {wy_star}%",
        "g9_l": ["Unemployment rate (%)", "Necessary economic growth (%)"],
    },
}


def fmt_num(val, use_comma=True, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def roman_q(q_str):
    return {"Q1": "I", "Q2": "II", "Q3": "III", "Q4": "IV"}.get(q_str, q_str)


def _destatis_ffcsv(table, startyear="1991", extra_params=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER / DESTATIS_PASS fehlen in den Environment-Variablen.")
    headers = {
        "username": D_USER,
        "password": D_PASS,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "name": table,
        "area": "all",
        "compress": "false",
        "format": "ffcsv",
        "language": "de",
        "startyear": startyear,
    }
    if extra_params:
        data.update(extra_params)

    def _unpack(resp):
        if resp.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
                return zf.read(csv_name).decode("utf-8", errors="replace")
        return resp.text

    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90)
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        status_txt = str(json.loads(rj.text).get("Status", {}).get("Content", ""))
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", status_txt)
        if not m:
            raise RuntimeError(f"Destatis Job-ID nicht gefunden fuer {table}: {status_txt[:200]}")
        job_id = m.group(1)
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            resp_res = requests.post(
                f"{G_BASE}/resultfile",
                headers=headers,
                data={"name": job_id, "area": "all", "compress": "false", "language": "de"},
                timeout=90,
            )
            txt = _unpack(resp_res)
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
        if not raw:
            raise RuntimeError(f"Destatis Job-Timeout fuer {table} ({job_id})")

    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3:
        return pd.DataFrame()
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)

    col_map = {c.lower(): c for c in df.columns}
    t_col = col_map.get("time") or col_map.get("zeit")
    v_col = col_map.get("value") or col_map.get("wert")
    zeit_s = df[t_col].astype(str).str.strip()

    for c in df.columns:
        if c in (t_col, v_col) or "label" in c.lower():
            continue
        s_code = df[c].astype(str).str.strip()
        if s_code.str.match(r"^QUART0?[1-4]$", case=False).any():
            q_ext = s_code.str.extract(r"([1-4])", expand=False)
            zeit_s = pd.Series(np.where(q_ext.notna(), zeit_s + "-Q" + q_ext.fillna(""), zeit_s), index=df.index)
            break
        if s_code.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            m_ext = s_code.str.extract(r"([0-9]+)", expand=False).str.zfill(2)
            zeit_s = pd.Series(np.where(m_ext.notna(), zeit_s + "-" + m_ext.fillna(""), zeit_s), index=df.index)
            break

    df["ZEIT"] = zeit_s
    df["WERT"] = df[v_col]
    return df


def _filter_total_series(df, req_codes, label_keywords, time_regex, min_plausible=None, max_plausible=None):
    if df.empty:
        return pd.Series(dtype=float)
    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    lbl_cols = [c for c in df.columns if "label" in c.lower()]

    df = df[df["ZEIT"].astype(str).str.match(time_regex)].copy()
    if df.empty:
        return pd.Series(dtype=float)

    df["_CODES"] = df.loc[:, code_cols].fillna("").astype(str).apply(
        lambda r: {x.strip().upper() for x in r if x.strip()}, axis=1
    )
    sub = df[df["_CODES"].apply(lambda s: req_codes.issubset(s))].copy()
    if sub.empty and label_keywords:
        lbl_txt = df.loc[:, lbl_cols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
        mask = pd.Series(True, index=df.index)
        for kw in label_keywords:
            mask &= lbl_txt.str.contains(kw, regex=False)
        sub = df[mask].copy()

    # Ausschluss von Teilaggregaten (z. B. Saisonbereinigt BV4.1/X13, Teilsektoren)
    if not sub.empty and lbl_cols:
        lbl_sub = sub.loc[:, lbl_cols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
        sub = sub[~lbl_sub.str.contains("saisonbereinigt|x13|bv4|verarbeitendes|landwirtschaft|dienstleist")].copy()

    sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=["V"]).copy()
    if min_plausible is not None:
        sub = sub[sub["V"] >= min_plausible].copy()
    if max_plausible is not None:
        sub = sub[sub["V"] <= max_plausible].copy()

    # Bei verbleibenden Mehrfachzeilen je Zeitpunkt den Gesamtwert (Maximum des Betrags) waehlen
    sub["ABS_V"] = sub["V"].abs()
    sub = sub.sort_values(["ZEIT", "ABS_V"], ascending=[True, False]).drop_duplicates(subset=["ZEIT"], keep="first")
    return pd.Series(sub["V"].values, index=sub["ZEIT"].astype(str).str.strip()).sort_index()


def load_all_macro_data():
    # 1. Reales & nominales BIP (Jahre: 81000-0001, Quartale: 81000-0002)
    df_bip_y = _destatis_ffcsv("81000-0001", startyear="1991")
    bip_real_y = _filter_total_series(
        df_bip_y, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^199\d$|^20\d{2}$", min_plausible=1500.0
    )
    bip_nom_y = _filter_total_series(
        df_bip_y, {"WERTORG", "VGR012"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
        r"^199\d$|^20\d{2}$", min_plausible=1400.0
    )

    df_bip_q = _destatis_ffcsv("81000-0002", startyear="1991")
    bip_real_q = _filter_total_series(
        df_bip_q, {"WERTORG", "VGR014"}, ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^(199\d|20\d{2})-Q[1-4]$", min_plausible=350.0
    )
    bip_nom_q = _filter_total_series(
        df_bip_q, {"WERTORG", "VGR012"}, ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
        r"^(199\d|20\d{2})-Q[1-4]$", min_plausible=300.0
    )

    # 2. Erwerbstaetige Inland in Tsd. (Jahre: 81000-0011, Quartale: 81000-0012)
    df_et_y = _destatis_ffcsv("81000-0011", startyear="1991")
    et_y = _filter_total_series(
        df_et_y, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige"],
        r"^199\d$|^20\d{2}$", min_plausible=30000.0, max_plausible=55000.0
    )

    df_et_q = _destatis_ffcsv("81000-0012", startyear="1991")
    et_q = _filter_total_series(
        df_et_q, {"WERTORG", "ERW060"}, ["originalwerte", "erwerbstätige"],
        r"^(199\d|20\d{2})-Q[1-4]$", min_plausible=30000.0, max_plausible=55000.0
    )

    # 3. Arbeitslose BA in Tsd. & BA-Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen (%)
    # Lange Jahresreihe ab 1991 aus 13211-0001 + Monatsreihe ab 2005 aus 13211-0002
    df_alo_y = _destatis_ffcsv("13211-0001", startyear="1991")
    alo_y_hist = _filter_total_series(
        df_alo_y, {"ERW011"}, ["arbeitslose"], r"^199\d$|^20\d{2}$", min_plausible=1500.0, max_plausible=6000.0
    )

    df_alo_m = _destatis_ffcsv("13211-0002", startyear="2005")
    alo_m = _filter_total_series(
        df_alo_m, {"ERW011"}, ["arbeitslose"], r"^20\d{2}-\d{2}$", min_plausible=1500.0, max_plausible=6000.0
    )
    # Offizielle BA-Arbeitslosenquote bezogen auf alle zivilen Erwerbspersonen (nicht abhaengige!)
    lbl_cols_m = [c for c in df_alo_m.columns if "label" in c.lower()]
    lbl_m_txt = df_alo_m.loc[:, lbl_cols_m].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
    df_alq_all = df_alo_m[
        lbl_m_txt.str.contains("arbeitslosenquote")
        & lbl_m_txt.str.contains("alle zivilen erwerbspersonen")
    ].copy()
    if df_alq_all.empty:
        df_alq_all = df_alo_m[lbl_m_txt.str.contains("arbeitslosenquote") & ~lbl_m_txt.str.contains("abhängige")].copy()
    df_alq_all = df_alq_all[df_alq_all["ZEIT"].astype(str).str.match(r"^20\d{2}-\d{2}$")].copy()
    df_alq_all["V"] = pd.to_numeric(df_alq_all["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    df_alq_all = df_alq_all.dropna(subset=["V"]).sort_values(["ZEIT", "V"]).drop_duplicates(subset=["ZEIT"], keep="first")
    alq_m = pd.Series(df_alq_all["V"].values, index=df_alq_all["ZEIT"].astype(str).str.strip()).sort_index()

    # Jahreswerte Arbeitslose aus Monatswerten ab 2005 mit historischer Jahresreihe 1991-2004 verknuepfen
    alo_m_df = alo_m.to_frame("V")
    alo_m_df["Y"] = alo_m_df.index.str[:4]
    alo_y_from_m = alo_m_df.groupby("Y").filter(lambda g: len(g) == 12).groupby("Y")["V"].mean()
    alo_y = alo_y_hist.combine_first(alo_y_from_m).sort_index()
    for y_k, v_k in alo_y_from_m.items():
        alo_y.loc[y_k] = v_k

    # Quartalswerte Arbeitslose ab 2005 (nur vollstaendige 3-Monats-Quartale)
    q_map = {"01": "Q1", "02": "Q1", "03": "Q1", "04": "Q2", "05": "Q2", "06": "Q2",
             "07": "Q3", "08": "Q3", "09": "Q3", "10": "Q4", "11": "Q4", "12": "Q4"}
    alo_m_df["YQ"] = alo_m_df.index.str[:4] + "-" + alo_m_df.index.str[5:7].map(q_map)
    alo_q = alo_m_df.groupby("YQ").filter(lambda g: len(g) == 3).groupby("YQ")["V"].mean().sort_index()

    # 4. Konjunkturelle Kurzarbeiter in Tsd. (Destatis 13211 / BA, ab 2009 verfuegbar, davor 0)
    kug_y = pd.Series(0.0, index=bip_real_y.index)
    kug_q = pd.Series(0.0, index=bip_real_q.index)
    try:
        df_kug = _destatis_ffcsv("13211-0005", startyear="2009")
        if not df_kug.empty:
            kug_m = _filter_total_series(
                df_kug, set(), ["kurzarbeiter"], r"^20\d{2}-\d{2}$", min_plausible=0.0, max_plausible=8000.0
            )
            if not kug_m.empty:
                kdf = kug_m.to_frame("V")
                kdf["Y"] = kdf.index.str[:4]
                kdf["YQ"] = kdf.index.str[:4] + "-" + kdf.index.str[5:7].map(q_map)
                for yk, vk in kdf.groupby("Y").filter(lambda g: len(g) == 12).groupby("Y")["V"].mean().items():
                    if yk in kug_y.index:
                        kug_y.loc[yk] = vk
                for qk, vk in kdf.groupby("YQ").filter(lambda g: len(g) == 3).groupby("YQ")["V"].mean().items():
                    if qk in kug_q.index:
                        kug_q.loc[qk] = vk
    except Exception as exc:
        print(f"[INFO] Kurzarbeiter-Abruf optional uebersprungen: {exc}")

    # 5. Finanzierungssaldo des Staates (81000-0031: Destatis liefert Mill. EUR -> Umrechnung in Mrd. EUR!)
    df_fin = _destatis_ffcsv("81000-0031", startyear="1991")
    fin_y_raw = _filter_total_series(
        df_fin, {"WERTORG"}, ["finanzierungssaldo", "staat"], r"^199\d$|^20\d{2}$"
    )
    fin_q_raw = _filter_total_series(
        df_fin, {"WERTORG"}, ["finanzierungssaldo", "staat"], r"^(199\d|20\d{2})-Q[1-4]$"
    )
    # Einheitenpruefung: Betraege > 1000 bedeuten Mill. EUR -> Division durch 1000 fuer Mrd. EUR
    scale_y = 1e-3 if (not fin_y_raw.empty and fin_y_raw.abs().median() > 1000.0) else 1.0
    scale_q = 1e-3 if (not fin_q_raw.empty and fin_q_raw.abs().median() > 1000.0) else 1.0
    fin_y = fin_y_raw * scale_y
    fin_q = fin_q_raw * scale_q

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
        "kug_y": kug_y,
        "kug_q": kug_q,
        "fin_y": fin_y,
        "fin_q": fin_q,
    }


def compute_koehler_indicators(md):
    # Jahreswerte ab 1991
    idx_y = md["bip_real_y"].index.intersection(md["et_y"].index).intersection(md["alo_y"].index).sort_values()
    idx_y = idx_y[idx_y >= "1991"]

    bip_y = md["bip_real_y"].loc[idx_y]
    et_y = md["et_y"].loc[idx_y]
    alo_y = md["alo_y"].loc[idx_y]
    kug_y = md["kug_y"].reindex(idx_y).fillna(0.0)

    prod_y = bip_y / et_y
    pot_base_y = (et_y + alo_y) * prod_y
    pot_ext_y = (et_y + alo_y + kug_y) * prod_y
    util_base_y = (bip_y / pot_base_y) * 100.0
    util_ext_y = (bip_y / pot_ext_y) * 100.0

    g_bip_y = bip_y.pct_change() * 100.0
    g_pot_y = pot_base_y.pct_change() * 100.0
    diff_y = g_bip_y - g_pot_y
    g_alo_y = alo_y.pct_change() * 100.0

    fin_pct_y = pd.Series(np.nan, index=idx_y)
    common_fy = idx_y.intersection(md["fin_y"].index).intersection(md["bip_nom_y"].index)
    fin_pct_y.loc[common_fy] = (md["fin_y"].loc[common_fy] / md["bip_nom_y"].loc[common_fy]) * 100.0

    # Quartalswerte (YoY gg. Vorjahresquartal & gleitende 4-Quartals-Summe fuer Niveauvergleich mit Jahreswerten)
    idx_q = md["bip_real_q"].index.intersection(md["et_q"].index).intersection(md["alo_q"].index).sort_values()
    bip_q = md["bip_real_q"].loc[idx_q]
    et_q = md["et_q"].loc[idx_q]
    alo_q = md["alo_q"].loc[idx_q]
    kug_q = md["kug_q"].reindex(idx_q).fillna(0.0)

    prod_q = bip_q / et_q
    pot_base_q = (et_q + alo_q) * prod_q
    pot_ext_q = (et_q + alo_q + kug_q) * prod_q

    # Gleitende 4-Quartals-Summe (Jahresrate) fuer Grafik 1 & 2/5
    bip_q_4sum = bip_q.rolling(4).sum()
    pot_base_q_4sum = pot_base_q.rolling(4).sum()
    pot_ext_q_4sum = pot_ext_q.rolling(4).sum()
    util_base_q = (bip_q_4sum / pot_base_q_4sum) * 100.0
    util_ext_q = (bip_q_4sum / pot_ext_q_4sum) * 100.0

    # Vorjahresquartals-Wachstumsraten (4 Quartale Differenz)
    g_bip_q = bip_q.pct_change(4) * 100.0
    g_pot_q = pot_base_q.pct_change(4) * 100.0
    diff_q = g_bip_q - g_pot_q
    g_alo_q = alo_q.pct_change(4) * 100.0

    fin_pct_q = pd.Series(np.nan, index=idx_q)
    common_fq = idx_q.intersection(md["fin_q"].index).intersection(md["bip_nom_q"].index)
    fin_pct_q.loc[common_fq] = (md["fin_q"].loc[common_fq] / md["bip_nom_q"].loc[common_fq]) * 100.0

    last_completed_year = idx_y[-1]
    curr_quarters = [q for q in idx_q if q[:4] > last_completed_year]

    # Gleitender 5-Jahres-Mittelwert von wY* (die letzten 5 abgeschlossenen Jahre, aktuell 2021-2025)
    valid_g_pot = g_pot_y.dropna()
    last5_wy = valid_g_pot.iloc[-5:]
    wy_star = float(last5_wy.mean())
    wy_span = f"{last5_wy.index[0]}–{last5_wy.index[-1]}"

    # Mittelwert Auslastung 1991-2019
    util_mean_91_19 = float(util_base_y.loc[(util_base_y.index >= "1991") & (util_base_y.index <= "2019")].mean())

    return {
        "idx_y": idx_y,
        "curr_quarters": curr_quarters,
        "pot_base_y": pot_base_y,
        "pot_ext_y": pot_ext_y,
        "pot_base_q_4sum": pot_base_q_4sum,
        "pot_ext_q_4sum": pot_ext_q_4sum,
        "util_base_y": util_base_y,
        "util_ext_y": util_ext_y,
        "util_base_q": util_base_q,
        "util_ext_q": util_ext_q,
        "util_mean_91_19": util_mean_91_19,
        "g_bip_y": g_bip_y,
        "diff_y": diff_y,
        "g_alo_y": g_alo_y,
        "fin_pct_y": fin_pct_y,
        "g_bip_q": g_bip_q,
        "diff_q": diff_q,
        "g_alo_q": g_alo_q,
        "fin_pct_q": fin_pct_q,
        "alq_m": md["alq_m"],
        "wy_star": wy_star,
        "wy_span": wy_span,
    }


def compute_necessary_growth_path(start_ym, alq0, wy_star):
    start_year = int(start_ym[:4])
    labels = [start_ym]
    alq_vals = [round(float(alq0), 1)]
    nec_vals = [None]

    curr_alq = float(alq0)
    step = 0
    while curr_alq > 3.0 and step < 12:
        next_alq = max(round(curr_alq - 1.0, 1), 0.0)
        w_one_plus_alq = ((1.0 + next_alq / 100.0) / (1.0 + curr_alq / 100.0) - 1.0) * 100.0
        nec_g = wy_star - w_one_plus_alq
        labels.append(str(start_year + step))
        alq_vals.append(next_alq)
        nec_vals.append(round(nec_g, 1))
        curr_alq = next_alq
        step += 1

    return labels, alq_vals, nec_vals

def _merge_intervals(flags, n):
    out, st = [], None
    for i in range(n):
        if flags[i] and st is None:
            st = i
        elif not flags[i] and st is not None:
            out.append((st, i - 1))
            st = None
    if st is not None:
        out.append((st, n - 1))
    return out


def add_shading_mpl(ax, cats, bip_neg_set, t):
    svr_flags = [
        any(s <= ym <= e for s, e in SVR_PHASES)
        for ym in [c_to_ym(c) for c in cats]
    ]
    bip_flags = [c in bip_neg_set for c in cats]
    svr_iv = _merge_intervals(svr_flags, len(cats))
    bip_iv = _merge_intervals(bip_flags, len(cats))
    for i0, i1 in svr_iv:
        ax.axvspan(i0 - 0.5, i1 + 0.5, color="#CBD5E1", alpha=0.45, lw=0, zorder=0)
    for i0, i1 in bip_iv:
        ax.axvspan(i0 - 0.5, i1 + 0.5, color="#60A5FA", alpha=0.35, lw=0, zorder=1)
    patches = []
    if svr_iv:
        patches.append(mpatches.Patch(color="#CBD5E1", alpha=0.65, label=t["leg_svr"]))
    if bip_iv:
        patches.append(mpatches.Patch(color="#60A5FA", alpha=0.50, label=t["leg_bip"]))
    return patches


def add_shading_plotly(fp, cats, bip_neg_set, t):
    svr_flags = [
        any(s <= ym <= e for s, e in SVR_PHASES)
        for ym in [c_to_ym(c) for c in cats]
    ]
    bip_flags = [c in bip_neg_set for c in cats]
    svr_iv = _merge_intervals(svr_flags, len(cats))
    bip_iv = _merge_intervals(bip_flags, len(cats))
    shapes = []
    for i0, i1 in svr_iv:
        shapes.append(dict(
            type="rect", xref="x", yref="paper",
            x0=i0 - 0.5, x1=i1 + 0.5, y0=0, y1=1,
            fillcolor="rgba(203, 213, 225, 0.45)", line=dict(width=0), layer="below"
        ))
    for i0, i1 in bip_iv:
        shapes.append(dict(
            type="rect", xref="x", yref="paper",
            x0=i0 - 0.5, x1=i1 + 0.5, y0=0, y1=1,
            fillcolor="rgba(96, 165, 250, 0.35)", line=dict(width=0), layer="below"
        ))
    if shapes:
        fp.update_layout(shapes=shapes)
    if svr_iv:
        fp.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, symbol="square", color="rgba(203, 213, 225, 0.9)"),
            name=t["leg_svr"], showlegend=True, hoverinfo="skip"
        ))
    if bip_iv:
        fp.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, symbol="square", color="rgba(96, 165, 250, 0.8)"),
            name=t["leg_bip"], showlegend=True, hoverinfo="skip"
        ))


def c_to_ym(cat):
    s = str(cat).strip()
    if len(s) == 4 and s.isdigit():
        return f"{s}-07"
    qmap = {"I": "02", "II": "05", "III": "08", "IV": "11"}
    parts = s.split()
    if len(parts) == 2 and parts[1] in qmap:
        return f"{parts[0]}-{qmap[parts[1]]}"
    return "2020-01"


def save_plotly_clean(fp, title, sub, src, now_str, fname, sfx, height_p=470, top_m=132, y_range=None, dtick=None):
    fp.update_layout(
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:11px;color:#334155;font-weight:normal'>{sub}</span>",
            x=0.02, y=0.97, yanchor="top",
            font=dict(size=13.5, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white",
        hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(
            orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom",
            bgcolor="rgba(255,255,255,0)", font=dict(size=9.8, color="#1E293B")
        ),
        margin=dict(l=48, r=24, t=top_m, b=78),
        height=height_p,
        annotations=[
            dict(text=f"{src}{now_str}", x=0.0, y=-0.24, xref="paper", yref="paper",
                 showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.24, xref="paper", yref="paper",
                 showarrow=False, font=dict(size=10.0, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False,
                    linecolor="#94A3B8", tickfont=dict(size=9.8, color="#475569"))
    y_kw = dict(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B",
                zerolinewidth=1.0, tickfont=dict(size=9.8, color="#475569"))
    if y_range is not None:
        y_kw["range"] = y_range
    if dtick is not None:
        y_kw["dtick"] = dtick
    fp.update_yaxes(**y_kw)
    out_p = f"{OUT_DIR}/{fname}{sfx}.html"
    fp.write_html(out_p, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_p, "r", encoding="utf-8") as fh:
        hs = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_p, "w", encoding="utf-8") as fh:
        fh.write(hs)

# ==============================================================================
# TEIL 2B: Zeichenfunktionen fuer Grafiken 1, 2, 5, 8 und 9 (DE & EN)
# ==============================================================================

def _finalize_plotly_layout(fig, title_txt, sub_txt, src_txt, now_str, fname, sfx, y_range=None, y_dtick=None, height_p=470, top_m=132):
    fig.update_layout(
        title=dict(
            text=f"<b>{title_txt}</b><br><span style='font-size:11.5px;color:#334155;font-weight:normal'>{sub_txt}</span>",
            x=0.02,
            y=0.97,
            yanchor="top",
            font=dict(size=14.0, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.03,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=10.0, color="#1E293B"),
        ),
        margin=dict(l=52, r=24, t=top_m, b=82),
        height=height_p,
        annotations=[
            dict(text=f"{src_txt}{now_str}", x=0.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=9.8, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.25, xref="paper", yref="paper", showarrow=False, font=dict(size=10.2, color="#94A3B8"), xanchor="right"),
        ],
    )
    fig.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.0, color="#475569"))
    yaxis_cfg = dict(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.0, tickfont=dict(size=10.0, color="#475569"))
    if y_range is not None:
        yaxis_cfg["range"] = y_range
    if y_dtick is not None:
        yaxis_cfg["dtick"] = y_dtick
    fig.update_yaxes(**yaxis_cfg)

    out_path = f"{OUT_DIR}/{fname}{sfx}.html"
    fig.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_chart_01_potenzial(lang, df_long, bip_intervals):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    labels = df_long["label"].tolist()
    y_pot = df_long["pot_basis"].tolist()
    y_pot_ext = df_long["pot_ext"].tolist()
    x_idx = np.arange(len(labels))

    ymax = int(np.ceil(max(max(y_pot), max(y_pot_ext)) / 500.0) * 500)
    ymin = int(np.floor(min(min(y_pot), min(y_pot_ext)) / 500.0) * 500)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.76, bottom=0.22)
    fig.suptitle(t["g1_t"], x=0.09, y=0.96, ha="left", fontsize=11.2, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, t["g1_sub"], ha="left", fontsize=8.3, color="#334155")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    shade_patches = add_recession_shading_mpl(ax, df_long["period"].tolist(), bip_intervals, t)
    p1 = ax.plot(x_idx, y_pot, color="#1B3A6B", lw=2.3, marker="o", markersize=3.5, label=t["g1_l"][0], zorder=4)
    p2 = ax.plot(x_idx, y_pot_ext, color="#059669", lw=1.9, ls="--", label=t["g1_l"][1], zorder=3)
    step = max(1, len(labels) // 16)
    ax.set_xticks(x_idx[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=8.0, color="#475569")
    ax.legend(handles=p1 + p2 + shade_patches, loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, frameon=False, fontsize=7.5)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/01_potenzial_lang{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Scatter(x=labels, y=[round(v, 1) for v in y_pot], customdata=[fmt_num(v, use_c, 1) for v in y_pot],
                            name=t["g1_l"][0], mode="lines+markers", line=dict(color="#1B3A6B", width=2.4), marker=dict(size=5),
                            hovertemplate=f"{t['g1_l'][0]}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=labels, y=[round(v, 1) for v in y_pot_ext], customdata=[fmt_num(v, use_c, 1) for v in y_pot_ext],
                            name=t["g1_l"][1], mode="lines", line=dict(color="#059669", width=2.0, dash="dash"),
                            hovertemplate=f"{t['g1_l'][1]}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    add_recession_shading_plotly(fp, df_long["period"].tolist(), bip_intervals, t)
    _finalize_plotly_layout(fp, t["g1_t"], t["g1_sub"], t["src"], now_str, "01_potenzial_lang", t["sfx"], y_range=[ymin, ymax])


def build_chart_02_05_auslastung(lang, df_sub, bip_intervals, fname, title_key, sub_key, show_mean_1991_2019=False):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    labels = df_sub["label"].tolist()
    y_util = df_sub["auslastung"].tolist()
    x_idx = np.arange(len(labels))

    ymin = int(np.floor(min(y_util) - 1.5))
    ymax = int(np.ceil(max(y_util) + 1.0))

    mean_val = None
    if show_mean_1991_2019:
        m_mask = df_sub["period"].astype(str).apply(lambda p: p[:4].isdigit() and 1991 <= int(p[:4]) <= 2019)
        if m_mask.any():
            mean_val = round(float(df_sub.loc[m_mask, "auslastung"].mean()), 1)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.22)
    fig.suptitle(t[title_key], x=0.08, y=0.96, ha="left", fontsize=11.2, fontweight="bold", color="#0F172A")
    fig.text(0.08, 0.915, t[sub_key], ha="left", fontsize=8.3, color="#334155")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    shade_patches = add_recession_shading_mpl(ax, df_sub["period"].tolist(), bip_intervals, t)
    p1 = ax.plot(x_idx, y_util, color="#1B3A6B", lw=2.3, marker="o", markersize=4.0, label=t["g2_l"], zorder=4)
    handles = p1 + shade_patches
    if mean_val is not None:
        m_lbl = f"{t['mean_lbl']}: {fmt_num(mean_val, use_c, 1)} %"
        pm = ax.axhline(mean_val, color="#D97706", lw=1.7, ls="--", label=m_lbl, zorder=3)
        ax.text(len(labels) - 0.5, mean_val + 0.18, fmt_num(mean_val, use_c, 1), color="#B45309", fontsize=8.0, fontweight="bold", ha="right")
        handles = p1 + [pm] + shade_patches
    step = max(1, len(labels) // 16)
    ax.set_xticks(x_idx[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=8.0, color="#475569")
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, frameon=False, fontsize=7.5)
    fig.text(0.08, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Scatter(x=labels, y=[round(v, 1) for v in y_util], customdata=[fmt_num(v, use_c, 1) for v in y_util],
                            name=t["g2_l"], mode="lines+markers", line=dict(color="#1B3A6B", width=2.4), marker=dict(size=5.5),
                            hovertemplate=f"{t['g2_l']}: <b>%{{customdata}} %</b><extra></extra>"))
    if mean_val is not None:
        m_lbl = f"{t['mean_lbl']} ({fmt_num(mean_val, use_c, 1)} %)"
        fp.add_trace(go.Scatter(x=labels, y=[mean_val] * len(labels), name=m_lbl, mode="lines",
                                line=dict(color="#D97706", width=1.8, dash="dash"),
                                hovertemplate=f"{t['mean_lbl']}: <b>{fmt_num(mean_val, use_c, 1)} %</b><extra></extra>"))
    add_recession_shading_plotly(fp, df_sub["period"].tolist(), bip_intervals, t)
    _finalize_plotly_layout(fp, t[title_key], t[sub_key], t["src"], now_str, fname, t["sfx"], y_range=[ymin, ymax])


def build_chart_08_09_notwendig(lang, df_nec, fname, title_key, sub_tpl):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    x_lbls = df_nec["step_label"].tolist()
    y_alq = df_nec["alq"].tolist()
    y_nec = df_nec["nec_growth"].tolist()
    wy_star = float(df_nec["wy_star"].iloc[0])
    start_lbl = str(df_nec["start_label"].iloc[0])
    alq_0 = float(df_nec["alq"].iloc[0])

    subtitle = t[sub_tpl].format(start_lbl=start_lbl, alq0=fmt_num(alq_0, use_c, 1), wystar=fmt_num(wy_star, use_c, 1))
    ymax = max(8.0, int(np.ceil(max(max(y_alq), max(y_nec)) + 1.2)))
    x_idx = np.arange(len(x_lbls))

    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.08, right=0.96, top=0.75, bottom=0.20)
    fig.suptitle(t[title_key], x=0.08, y=0.96, ha="left", fontsize=11.2, fontweight="bold", color="#0F172A")
    fig.text(0.08, 0.912, subtitle, ha="left", fontsize=8.2, color="#334155")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(0, ymax)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)

    bars = ax.bar(x_idx, y_alq, width=0.46, color="#1B3A6B", alpha=0.88, label=t["g8_l"][0], zorder=2)
    for rect, val in zip(bars, y_alq):
        ax.text(rect.get_x() + rect.get_width() / 2.0, val + 0.14, fmt_num(val, use_c, 1), ha="center", va="bottom", fontsize=7.8, color="#1E293B")

    valid_x = [i for i, v in enumerate(y_nec) if not pd.isna(v)]
    valid_y = [float(y_nec[i]) for i in valid_x]
    line = ax.plot(valid_x, valid_y, color="#D97706", lw=2.4, marker="o", markersize=5.5, label=t["g8_l"][1], zorder=5)
    for xi, yi in zip(valid_x, valid_y):
        bar_h = float(y_alq[xi])
        offset = -0.55 if abs(yi - bar_h) < 0.75 else 0.25
        ax.text(xi, yi + offset, fmt_num(yi, use_c, 1), ha="center", va="bottom" if offset > 0 else "top",
                fontsize=8.0, fontweight="bold", color="#B45309",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.88), zorder=6)

    ax.set_xticks(x_idx)
    ax.set_xticklabels(x_lbls, fontsize=8.4, color="#334155")
    ax.legend(handles=[bars, line[0]], loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, frameon=False, fontsize=7.8)
    fig.text(0.08, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Bar(
        x=x_lbls, y=[round(v, 1) for v in y_alq],
        text=[fmt_num(v, use_c, 1) for v in y_alq], textposition="outside",
        name=t["g8_l"][0], marker_color="#1B3A6B", opacity=0.88,
        hovertemplate=f"{t['g8_l'][0]}: <b>%{{text}} %</b><extra></extra>",
    ))
    text_pos = ["bottom center" if (not pd.isna(yn) and abs(yn - ya) < 0.75) else "top center" for ya, yn in zip(y_alq, y_nec)]
    fp.add_trace(go.Scatter(
        x=x_lbls, y=[None if pd.isna(v) else round(float(v), 1) for v in y_nec],
        text=["" if pd.isna(v) else fmt_num(v, use_c, 1) for v in y_nec],
        textposition=text_pos, textfont=dict(color="#B45309", size=11),
        name=t["g8_l"][1], mode="lines+markers+text",
        line=dict(color="#D97706", width=2.5), marker=dict(size=7, color="#D97706"),
        hovertemplate=f"{t['g8_l'][1]}: <b>%{{text}} %</b><extra></extra>",
    ))
    _finalize_plotly_layout(fp, t[title_key], subtitle, t["src"], now_str, fname, t["sfx"], y_range=[0, ymax], y_dtick=1, height_p=470, top_m=136)

def build_dual_axis_chart(
    lang,
    fname,
    title_key,
    sub_key,
    line_lbl_key,
    bar_lbl_key,
    labels,
    line_vals,
    bar_vals,
    bip_neg_flags,
    y1_lim,
    y1_step,
    y2_lim,
    y2_step,
    bar_color,
    y1_unit="Ppkt.",
    y2_unit="%",
):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))

    y1_arr = [np.nan if (v is None or pd.isna(v)) else float(v) for v in line_vals]
    y2_arr = [np.nan if (v is None or pd.isna(v)) else float(v) for v in bar_vals]

    fig, ax1 = plt.subplots(figsize=(8.4, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.08, right=0.91, top=0.75, bottom=0.22)

    fig.suptitle(t[title_key], x=0.08, y=0.965, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.08, 0.918, t[sub_key], ha="left", fontsize=8.2, color="#334155")

    ax1.set_facecolor("#F8FAFC")
    ax1.set_ylim(-y1_lim, y1_lim)
    ax1.set_yticks(np.arange(-y1_lim, y1_lim + y1_step * 0.5, y1_step))
    ax1.axhline(0, color="#64748B", linewidth=1.0, zorder=2)
    ax1.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax1.set_axisbelow(True)
    ax1.tick_params(axis="y", colors="#1B3A6B", labelsize=8.3, length=0)
    ax1.tick_params(axis="x", colors="#475569", labelsize=7.6, rotation=90, length=3, color="#CBD5E1")

    ax2 = ax1.twinx()
    ax2.set_ylim(-y2_lim, y2_lim)
    ax2.set_yticks(np.arange(-y2_lim, y2_lim + y2_step * 0.5, y2_step))
    ax2.tick_params(axis="y", colors=bar_color, labelsize=8.3, length=0)

    for s in ("top", "right", "left"):
        ax1.spines[s].set_visible(False)
        ax2.spines[s].set_visible(False)
    ax1.spines["bottom"].set_color("#94A3B8")
    ax2.spines["bottom"].set_visible(False)

    shade_patches = add_recession_shading_mpl(ax1, labels, bip_neg_flags, t)

    bar_clean = [0.0 if np.isnan(v) else v for v in y2_arr]
    b1 = ax2.bar(x, bar_clean, width=0.58, color=bar_color, alpha=0.82, label=t[bar_lbl_key], zorder=2)
    l1 = ax1.plot(x, y1_arr, color="#1B3A6B", lw=2.3, marker="o", markersize=3.2, label=t[line_lbl_key], zorder=5)

    step_x = 2 if len(labels) > 22 else 1
    tick_idx = [i for i in range(len(labels)) if i % step_x == 0]
    ax1.set_xticks(tick_idx)
    ax1.set_xticklabels([labels[i] for i in tick_idx])

    handles = [l1[0], mpatches.Patch(color=bar_color, alpha=0.82, label=t[bar_lbl_key])] + shade_patches
    ax1.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, frameon=False, fontsize=7.3)

    fig.text(0.08, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.91, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    bar_text = [fmt_num(v, use_c, 1) if not np.isnan(v) else "" for v in y2_arr]
    line_text = [fmt_num(v, use_c, 1) if not np.isnan(v) else "" for v in y1_arr]

    fp.add_trace(
        go.Bar(
            x=labels,
            y=[None if np.isnan(v) else round(v, 2) for v in y2_arr],
            customdata=bar_text,
            name=t[bar_lbl_key],
            yaxis="y2",
            marker=dict(color=bar_color, opacity=0.82),
            hovertemplate=f"{t[bar_lbl_key]}: <b>%{{customdata}} {y2_unit}</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=labels,
            y=[None if np.isnan(v) else round(v, 2) for v in y1_arr],
            customdata=line_text,
            name=t[line_lbl_key],
            yaxis="y",
            mode="lines+markers",
            line=dict(color="#1B3A6B", width=2.4),
            marker=dict(size=4.5, color="#1B3A6B"),
            hovertemplate=f"{t[line_lbl_key]}: <b>%{{customdata}} {y1_unit}</b><extra></extra>",
        )
    )

    add_recession_shading_plotly(fp, labels, bip_neg_flags, t)

    t_vals = [labels[i] for i in range(len(labels)) if i % step_x == 0]
    fp.update_layout(
        title=dict(
            text=f"<b>{t[title_key]}</b><br><span style='font-size:11.2px;color:#334155;font-weight:normal'>{t[sub_key]}</span>",
            x=0.02,
            y=0.97,
            yanchor="top",
            font=dict(size=14.0, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.02,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=9.8, color="#1E293B"),
        ),
        margin=dict(l=48, r=48, t=155, b=78),
        height=495,
        xaxis=dict(
            type="category",
            fixedrange=True,
            tickangle=-45,
            showgrid=False,
            linecolor="#94A3B8",
            tickmode="array",
            tickvals=t_vals,
            ticktext=t_vals,
            tickfont=dict(size=9.8, color="#475569"),
        ),
        yaxis=dict(
            fixedrange=True,
            range=[-y1_lim, y1_lim],
            dtick=y1_step,
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#64748B",
            zerolinewidth=1.1,
            tickfont=dict(size=9.8, color="#1B3A6B"),
        ),
        yaxis2=dict(
            fixedrange=True,
            overlaying="y",
            side="right",
            range=[-y2_lim, y2_lim],
            dtick=y2_step,
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=9.8, color=bar_color),
        ),
        annotations=[
            dict(
                text=f"{t['src']}{now_str}",
                x=0.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.6, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.0, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )

    out_path = f"{OUT_DIR}/{fname}{t['sfx']}.html"
    fp.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def _pick_series(macro, candidates):
    for k in candidates:
        s = macro.get(k)
        if s is not None and len(s) > 0:
            return s.sort_index()
    raise KeyError(f"Keine passende Datenreihe in macro gefunden. Verfuegbare Keys: {list(macro.keys())}")


def _to_quarter_label(q_key):
    s = str(q_key).strip()
    if "-Q" in s:
        yr, qp = s.split("-Q")
        roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}.get(qp, qp)
        return f"{yr} {roman}"
    return s


def build_potential_datasets(macro):
    bip_real_y = _pick_series(macro, ["bip_real_y", "gdp_real_y", "real_gdp_y"])
    bip_real_q = _pick_series(macro, ["bip_real_q", "gdp_real_q", "real_gdp_q"])
    bip_nom_y = _pick_series(macro, ["bip_nom_y", "gdp_nom_y", "nom_gdp_y"])
    bip_nom_q = _pick_series(macro, ["bip_nom_q", "gdp_nom_q", "nom_gdp_q"])
    et_y = _pick_series(macro, ["et_y", "emp_y"])
    et_q = _pick_series(macro, ["et_q", "emp_q"])
    alo_y = _pick_series(macro, ["alo_y", "unemp_y"])
    alo_q = _pick_series(macro, ["alo_q", "unemp_q"])
    kug_y = macro.get("kug_y")
    kug_q = macro.get("kug_q")
    fin_y = _pick_series(macro, ["fin_y", "gov_bal_y", "staat_y"])
    fin_q = _pick_series(macro, ["fin_q", "gov_bal_q", "staat_q"])
    alq_m = _pick_series(macro, ["alq_m", "unemp_rate_m"])

    # Einheiten-Normalisierung (Finanzierungssaldo 81000-0031 liegt in Mill. EUR -> Mrd. EUR)
    if fin_y.abs().median() > 500:
        fin_y = fin_y / 1000.0
    if len(fin_q) > 0 and fin_q.abs().median() > 500:
        fin_q = fin_q / 1000.0

    # Produktivitaet & Produktionspotenzial (Jahre ab 1991)
    idx_y = bip_real_y.index.intersection(et_y.index).intersection(alo_y.index).sort_values()
    idx_y = idx_y[idx_y >= "1991"]

    prod_y = (bip_real_y.loc[idx_y] / et_y.loc[idx_y]) * 1e6
    pot_base_y = ((et_y.loc[idx_y] + alo_y.loc[idx_y]) * prod_y) / 1e6

    if kug_y is not None and len(kug_y) > 0:
        kug_y_aligned = kug_y.reindex(idx_y).fillna(0.0)
    else:
        kug_y_aligned = pd.Series(0.0, index=idx_y)
    pot_ext_y = ((et_y.loc[idx_y] + alo_y.loc[idx_y] + kug_y_aligned) * prod_y) / 1e6
    util_y = (bip_real_y.loc[idx_y] / pot_base_y) * 100.0

    # Quartalswerte (inkl. Vorjahresbasis fuer Wachstumsraten & 4-Quartals-Summe)
    idx_q = bip_real_q.index.intersection(et_q.index).intersection(alo_q.index).sort_values()
    prod_q = (bip_real_q.loc[idx_q] / et_q.loc[idx_q]) * 1e6
    pot_base_q = ((et_q.loc[idx_q] + alo_q.loc[idx_q]) * prod_q) / 1e6

    if kug_q is not None and len(kug_q) > 0:
        kug_q_aligned = kug_q.reindex(idx_q).fillna(0.0)
    else:
        kug_q_aligned = pd.Series(0.0, index=idx_q)
    pot_ext_q = ((et_q.loc[idx_q] + alo_q.loc[idx_q] + kug_q_aligned) * prod_q) / 1e6
    util_q = (bip_real_q.loc[idx_q] / pot_base_q) * 100.0

    # Gleitende 4-Quartals-Summe auf Jahresniveau fuer Grafik 1
    pot_base_q4 = pot_base_q.rolling(4).sum().dropna()
    pot_ext_q4 = pot_ext_q.rolling(4).sum().dropna()

    last_full_year = str(idx_y[-1])
    curr_quarters = [q for q in idx_q if str(q)[:4] > last_full_year]

    # Zuwachsraten gg. Vj. (%)
    g_bip_y = bip_real_y.loc[idx_y].pct_change() * 100.0
    g_pot_y = pot_base_y.pct_change() * 100.0
    diff_y = (g_bip_y - g_pot_y).dropna()
    g_alo_y = (alo_y.loc[idx_y].pct_change() * 100.0).reindex(diff_y.index)
    fin_pct_y = ((fin_y / bip_nom_y) * 100.0).reindex(diff_y.index)

    g_bip_q = bip_real_q.loc[idx_q].pct_change(4) * 100.0
    g_pot_q = pot_base_q.pct_change(4) * 100.0
    diff_q = (g_bip_q - g_pot_q).dropna()
    g_alo_q = (alo_q.loc[idx_q].pct_change(4) * 100.0).reindex(diff_q.index)
    fin_pct_q = ((fin_q / bip_nom_q) * 100.0).reindex(diff_q.index)

    # Lange Reihe (Jahre ab 1991 + aktuelle Quartale)
    long_labels = list(idx_y) + [_to_quarter_label(q) for q in curr_quarters]
    long_pot_base = [float(pot_base_y.loc[y]) for y in idx_y] + [float(pot_base_q4.get(q, pot_base_q.loc[q] * 4.0)) for q in curr_quarters]
    long_pot_ext = [float(pot_ext_y.loc[y]) for y in idx_y] + [float(pot_ext_q4.get(q, pot_ext_q.loc[q] * 4.0)) for q in curr_quarters]
    long_util = [float(util_y.loc[y]) for y in idx_y] + [float(util_q.loc[q]) for q in curr_quarters]

    util_1991_2019 = util_y.loc[(util_y.index >= "1991") & (util_y.index <= "2019")]
    mean_util_91_19 = float(util_1991_2019.mean()) if len(util_1991_2019) > 0 else float(util_y.mean())

    # Lange Wachstumsreihen (ab 1992 + aktuelle Quartale)
    idx_y_g = [y for y in diff_y.index if str(y) >= "1992"]
    curr_q_g = [q for q in curr_quarters if q in diff_q.index]
    long_g_labels = list(idx_y_g) + [_to_quarter_label(q) for q in curr_q_g]
    long_diff = [float(diff_y.loc[y]) for y in idx_y_g] + [float(diff_q.loc[q]) for q in curr_q_g]
    long_g_alo = [float(g_alo_y.loc[y]) for y in idx_y_g] + [float(g_alo_q.loc[q]) for q in curr_q_g]
    long_fin_pct = [float(fin_pct_y.loc[y]) if pd.notna(fin_pct_y.loc[y]) else None for y in idx_y_g] + [
        float(fin_pct_q.loc[q]) if pd.notna(fin_pct_q.loc[q]) else None for q in curr_q_g
    ]

    # Kuerzere Reihe (ab 2019 + Trennluecke + aktuelle Quartale)
    short_years = [y for y in idx_y if str(y) >= "2019"]
    short_labels = list(short_years) + ([""] if curr_quarters else []) + [_to_quarter_label(q) for q in curr_quarters]
    short_util = [float(util_y.loc[y]) for y in short_years] + ([None] if curr_quarters else []) + [float(util_q.loc[q]) for q in curr_quarters]
    short_diff = [float(diff_y.loc[y]) for y in short_years] + ([None] if curr_quarters else []) + [float(diff_q.loc[q]) for q in curr_quarters]
    short_g_alo = [float(g_alo_y.loc[y]) for y in short_years] + ([None] if curr_quarters else []) + [float(g_alo_q.loc[q]) for q in curr_quarters]
    short_fin_pct = (
        [float(fin_pct_y.loc[y]) if pd.notna(fin_pct_y.loc[y]) else None for y in short_years]
        + ([None] if curr_quarters else [])
        + [float(fin_pct_q.loc[q]) if pd.notna(fin_pct_q.loc[q]) else None for q in curr_quarters]
    )

    # Notwendiges Wirtschaftswachstum: gleitender 5-Jahres-Mittelwert wY*
    last_5_years = sorted(g_pot_y.dropna().index)[-5:]
    wy_star = float(g_pot_y.loc[last_5_years].mean()) if len(last_5_years) > 0 else 1.1
    wy_window = f"{last_5_years[0]}-{last_5_years[-1]}" if len(last_5_years) >= 2 else "2021-2025"

    def _calc_necessary_path(start_ym, start_alq):
        yr0 = int(str(start_ym)[:4])
        labels = [start_ym]
        alq_vals = [round(float(start_alq), 1)]
        nec_vals = [None]
        cur_alq = float(start_alq)
        step = 0
        while cur_alq > 3.0 and step < 10:
            prev_alq = cur_alq
            cur_alq = max(round(prev_alq - 1.0, 1), 0.0)
            w_1_alq = ((1.0 + cur_alq / 100.0) / (1.0 + prev_alq / 100.0) - 1.0) * 100.0
            nec_wy = wy_star - w_1_alq
            labels.append(str(yr0 + step))
            alq_vals.append(cur_alq)
            nec_vals.append(round(nec_wy, 1))
            step += 1
        return {"labels": labels, "alq": alq_vals, "nec": nec_vals, "wy_star": round(wy_star, 1), "window": wy_window, "start_ym": start_ym, "start_alq": round(float(start_alq), 1)}

    alq_m_sorted = alq_m.dropna().sort_index()
    latest_m = str(alq_m_sorted.index[-1])
    curr_yr = latest_m[:4]
    jan_key = f"{curr_yr}-01" if f"{curr_yr}-01" in alq_m_sorted.index else latest_m
    nec_year = _calc_necessary_path(jan_key, alq_m_sorted.loc[jan_key])
    nec_quarter = _calc_necessary_path(latest_m, alq_m_sorted.loc[latest_m])

    # Rezessionsintervalle (nur tatsaechliche negative BIP-Wachstumsraten)
    neg_bip_years = {str(y) for y, v in g_bip_y.dropna().items() if v < 0}
    neg_bip_quarters = {_to_quarter_label(q) for q, v in g_bip_q.dropna().items() if v < 0}
    neg_set = neg_bip_years | neg_bip_quarters

    return {
        "long_labels": long_labels,
        "long_pot_base": long_pot_base,
        "long_pot_ext": long_pot_ext,
        "long_util": long_util,
        "mean_util_91_19": mean_util_91_19,
        "long_g_labels": long_g_labels,
        "long_diff": long_diff,
        "long_g_alo": long_g_alo,
        "long_fin_pct": long_fin_pct,
        "short_labels": short_labels,
        "short_util": short_util,
        "short_diff": short_diff,
        "short_g_alo": short_g_alo,
        "short_fin_pct": short_fin_pct,
        "nec_year": nec_year,
        "nec_quarter": nec_quarter,
        "neg_bip_set": neg_set,
    }
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    macro = load_all_macro_data()
    series = build_potential_datasets(macro)

    long_df = series["long"]
    short_df = series["short"]
    nec_year = series["nec_year"]
    nec_quart = series["nec_quart"]

    print(
        f"[OK] Lange Reihe: {long_df['label'].iloc[0]} bis {long_df['label'].iloc[-1]} ({len(long_df)} Punkte) | "
        f"Kurze Reihe: {short_df['label'].iloc[0]} bis {short_df['label'].iloc[-1]} | "
        f"wY* (5J-Ø): {nec_year['wy_star']:.2f} %"
    )

    for lang in ("de", "en"):
        build_potential_level_chart(lang, long_df)
        build_utilization_chart(lang, "02_auslastung_lang", "g2_t", "g2_sub", long_df, show_mean_1991_2019=True)
        build_dual_axis_chart(
            lang,
            "03_angemessen_alo_lang",
            "g3_t",
            "g3_sub",
            "g3_l1",
            "g3_l2",
            list(long_df["label"]),
            list(long_df["diff_growth"]),
            list(long_df["alo_yoy"]),
            list(long_df["bip_neg"]),
            y1_lim=3.0,
            y1_step=1.0,
            y2_lim=30.0,
            y2_step=10.0,
            bar_color="#D97706",
            y1_unit="Ppkt." if lang == "de" else "pp",
            y2_unit="%",
        )
        build_dual_axis_chart(
            lang,
            "04_angemessen_staat_lang",
            "g4_t",
            "g4_sub",
            "g4_l1",
            "g4_l2",
            list(long_df["label"]),
            list(long_df["diff_growth"]),
            list(long_df["fin_gdp"]),
            list(long_df["bip_neg"]),
            y1_lim=3.0,
            y1_step=1.0,
            y2_lim=12.0,
            y2_step=4.0,
            bar_color="#059669",
            y1_unit="Ppkt." if lang == "de" else "pp",
            y2_unit="%",
        )
        build_utilization_chart(lang, "05_auslastung_kurz", "g5_t", "g5_sub", short_df, show_mean_1991_2019=False)
        build_dual_axis_chart(
            lang,
            "06_angemessen_alo_kurz",
            "g6_t",
            "g6_sub",
            "g6_l1",
            "g6_l2",
            list(short_df["label"]),
            list(short_df["diff_growth"]),
            list(short_df["alo_yoy"]),
            list(short_df["bip_neg"]),
            y1_lim=3.0,
            y1_step=1.0,
            y2_lim=20.0,
            y2_step=5.0,
            bar_color="#D97706",
            y1_unit="Ppkt." if lang == "de" else "pp",
            y2_unit="%",
        )
        build_dual_axis_chart(
            lang,
            "07_angemessen_staat_kurz",
            "g7_t",
            "g7_sub",
            "g7_l1",
            "g7_l2",
            list(short_df["label"]),
            list(short_df["diff_growth"]),
            list(short_df["fin_gdp"]),
            list(short_df["bip_neg"]),
            y1_lim=3.0,
            y1_step=1.0,
            y2_lim=12.0,
            y2_step=4.0,
            bar_color="#059669",
            y1_unit="Ppkt." if lang == "de" else "pp",
            y2_unit="%",
        )
        build_necessary_growth_chart(lang, "08_notwendig_jahr", "g8_t", "g8_sub", nec_year)
        build_necessary_growth_chart(lang, "09_notwendig_quartal", "g9_t", "g9_sub", nec_quart)


if __name__ == "__main__":
    main()

