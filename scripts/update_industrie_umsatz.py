#!/usr/bin/env python3
"""
Aktualisiert alle Grafiken (DE & EN, .png und .html) fuer die Unterrubrik:
"Umsatz insgesamt, Umsatz Inland, Umsatz Ausland und nach ausgewählten Warengruppen
des Verarbeitenden Gewerbes"
Datenbasis: Statistisches Bundesamt (Destatis GENESIS-Online), Tabelle 42111-0004
Zeitraum: Januar 2019 bis aktuellster verfuegbarer Berichtsmonat, Werte in Mrd. Euro.
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
from matplotlib.patches import Patch
import plotly.graph_objects as go

G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"
D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()

OUT_DIR = "static/umsatz-industrie"

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "y_lbl": "Mrd. Euro",
        "x_lbl": "Berichtsmonat",
        "src": "Quelle: Statistisches Bundesamt (GENESIS-Online 42111-0004), eigene Berechnungen | Stand: ",
        "leg_tot": "Umsatz insgesamt",
        "leg_dom": "Umsatz Inland",
        "leg_for": "Umsatz Ausland",
        "leg_tot_a": "Umsatz insgesamt (Abgrenzung A)",
        "leg_dom_a": "Umsatz Inland (Abgrenzung A)",
        "leg_for_a": "Umsatz Ausland (Abgrenzung A)",
        "leg_tot_b": "Umsatz insgesamt (Abgrenzung B)",
        "leg_dom_b": "Umsatz Inland (Abgrenzung B)",
        "leg_for_b": "Umsatz Ausland (Abgrenzung B)",
        "leg_rec_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_rec_bip": "Reales BIP < 0 % gg. Vj.",
        "share_fmt": "Aktueller Monat ({ym}): Anteil Ausland {for_pct} % | Anteil Inland {dom_pct} %",
        "share_dual_fmt": "Aktuell ({ym}): {lbl_a} — Ausland {for_a} % / Inland {dom_a} % | {lbl_b} — Ausland {for_b} % / Inland {dom_b} %",
        "p1_t": "Umsatz im Verarbeitenden Gewerbe insgesamt (WZ08-C)",
        "p2_t": "Umsatz: Kraftwagen und Kraftwagenteile (WZ08-29)",
        "p3_t": "Umsatz: Metallerzeugung/-bearbeitung (WZ08-24) vs. inkl. Metallerzeugnisse (WZ08-24 + 25)",
        "p3_a": "WZ08-24",
        "p3_b": "WZ08-24+25",
        "p3_tot_a": "Insgesamt: Metallerzeugung/-bearbeitung (WZ08-24)",
        "p3_dom_a": "Inland: Metallerzeugung/-bearbeitung (WZ08-24)",
        "p3_for_a": "Ausland: Metallerzeugung/-bearbeitung (WZ08-24)",
        "p3_tot_b": "Insgesamt: inkl. Metallerzeugnisse (WZ08-24+25)",
        "p3_dom_b": "Inland: inkl. Metallerzeugnisse (WZ08-24+25)",
        "p3_for_b": "Ausland: inkl. Metallerzeugnisse (WZ08-24+25)",
        "p4_t": "Umsatz: Chemische Erzeugnisse (WZ08-20) vs. inkl. Pharmazeutika (WZ08-20 + 21)",
        "p4_a": "WZ08-20",
        "p4_b": "WZ08-20+21",
        "p4_tot_a": "Insgesamt: Chemische Erzeugnisse (WZ08-20)",
        "p4_dom_a": "Inland: Chemische Erzeugnisse (WZ08-20)",
        "p4_for_a": "Ausland: Chemische Erzeugnisse (WZ08-20)",
        "p4_tot_b": "Insgesamt: inkl. Pharmazeutika (WZ08-20+21)",
        "p4_dom_b": "Inland: inkl. Pharmazeutika (WZ08-20+21)",
        "p4_for_b": "Ausland: inkl. Pharmazeutika (WZ08-20+21)",
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "y_lbl": "EUR billion",
        "x_lbl": "Reporting month",
        "src": "Source: Federal Statistical Office (GENESIS-Online 42111-0004), own calculations | As of: ",
        "leg_tot": "Total turnover",
        "leg_dom": "Domestic turnover",
        "leg_for": "Foreign turnover",
        "leg_rec_svr": "Recession/Slowdown (GCEE/BBK)",
        "leg_rec_bip": "Real GDP < 0% YoY",
        "share_fmt": "Latest month ({ym}): Foreign share {for_pct}% | Domestic share {dom_pct}%",
        "share_dual_fmt": "Latest ({ym}): {lbl_a} — Foreign {for_a}% / Domestic {dom_a}% | {lbl_b} — Foreign {for_b}% / Domestic {dom_b}%",
        "p1_t": "Total Manufacturing Turnover (WZ08-C)",
        "p2_t": "Turnover: Motor Vehicles, Trailers and Semi-Trailers (WZ08-29)",
        "p3_t": "Turnover: Basic Metals (WZ08-24) vs. incl. Fabricated Metal Products (WZ08-24 + 25)",
        "p3_a": "WZ08-24",
        "p3_b": "WZ08-24+25",
        "p3_tot_a": "Total: Basic metals (WZ08-24)",
        "p3_dom_a": "Domestic: Basic metals (WZ08-24)",
        "p3_for_a": "Foreign: Basic metals (WZ08-24)",
        "p3_tot_b": "Total: incl. fabricated metal products (WZ08-24+25)",
        "p3_dom_b": "Domestic: incl. fabricated metal products (WZ08-24+25)",
        "p3_for_b": "Foreign: incl. fabricated metal products (WZ08-24+25)",
        "p4_t": "Turnover: Chemicals and Chemical Products (WZ08-20) vs. incl. Pharmaceuticals (WZ08-20 + 21)",
        "p4_a": "WZ08-20",
        "p4_b": "WZ08-20+21",
        "p4_tot_a": "Total: Chemicals (WZ08-20)",
        "p4_dom_a": "Domestic: Chemicals (WZ08-20)",
        "p4_for_a": "Foreign: Chemicals (WZ08-20)",
        "p4_tot_b": "Total: incl. pharmaceuticals (WZ08-20+21)",
        "p4_dom_b": "Domestic: incl. pharmaceuticals (WZ08-20+21)",
        "p4_for_b": "Foreign: incl. pharmaceuticals (WZ08-20+21)",
    },
}

REC_SVR_PHASES = [
    ("2020-01", "2020-06"),
    ("2022-10", "2023-03"),
    ("2023-10", "2024-12"),
]


def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def normalize_wz(raw_code):
    s = str(raw_code).strip().upper()
    m = re.search(r"WZ08-([A-Z0-9]+)", s)
    if not m:
        return ""
    suffix = m.group(1)
    if suffix.isdigit():
        suffix = str(int(suffix)).zfill(2)
    return f"WZ08-{suffix}"


def _destatis_ffcsv(table, startyear="2019", extra_params=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt in den Umgebungsvariablen.")
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
            return pd.DataFrame()
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            resp_res = requests.post(
                f"{G_BASE}/resultfile",
                headers=headers,
                data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"},
                timeout=90,
            )
            txt = _unpack(resp_res)
            if not txt.lstrip().startswith("{"):
                raw = txt
                break

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
    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    df["_CODES"] = df.loc[:, code_cols].fillna("").astype(str).apply(
        lambda r: set(x.strip() for x in r if x.strip()), axis=1
    )
    return df


def _parse_42111_df(df):
    if df.empty:
        return pd.DataFrame(columns=["ZEIT", "WZ", "UMS_TYPE", "VAL_MRD"])

    wz_col = None
    for c in df.columns:
        if c.endswith("_code") and df[c].astype(str).str.contains("WZ08-", case=False, na=False).any():
            wz_col = c
            break
    if wz_col is None:
        for c in df.columns:
            if df[c].astype(str).str.contains("WZ08-", case=False, na=False).any():
                wz_col = c
                break
    if wz_col is None:
        return pd.DataFrame(columns=["ZEIT", "WZ", "UMS_TYPE", "VAL_MRD"])

    df = df.copy()
    df["WZ"] = df[wz_col].apply(normalize_wz)
    df = df[df["WZ"] != ""].copy()

    def detect_ums(row):
        codes = row["_CODES"]
        for u in ("UMS002", "UMS003", "UMS004"):
            if u in codes:
                return u
        for c in df.columns:
            if "label" in c.lower():
                val = str(row.get(c, "")).lower()
                if "inlandsumsatz" in val:
                    return "UMS003"
                if "auslandsumsatz" in val:
                    return "UMS004"
                if "umsatz" in val and "insgesamt" in val:
                    return "UMS002"
        return ""

    df["UMS_TYPE"] = df.apply(detect_ums, axis=1)
    df = df[df["UMS_TYPE"].isin({"UMS002", "UMS003", "UMS004"})].copy()

    df["V"] = pd.to_numeric(
        df["WERT"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    if df["V"].isna().mean() > 0.5:
        df["V"] = pd.to_numeric(df["WERT"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df = df.dropna(subset=["V"]).copy()

    med = float(df["V"].median()) if not df.empty else 0.0
    if med > 1e6:
        scale = 1e-9
    elif med > 1e3:
        scale = 1e-6
    else:
        scale = 1e-3
    df["VAL_MRD"] = df["V"] * scale
    return df[["ZEIT", "WZ", "UMS_TYPE", "VAL_MRD"]].copy()


def load_destatis_turnover():
    # 1) Gesamtes Verarbeitendes Gewerbe (WZ08-C) ohne classifyingvariable1-Einschraenkung
    df_c_raw = _destatis_ffcsv(
        "42111-0004",
        startyear="2019",
        extra_params={"classifyingkey1": "WZ08-C"},
    )
    df_c = _parse_42111_df(df_c_raw)
    if df_c.empty or "WZ08-C" not in set(df_c["WZ"]):
        df_c_raw2 = _destatis_ffcsv("42111-0004", startyear="2019")
        df_c = _parse_42111_df(df_c_raw2)

    # 2) Ausgewaehlte 2-Steller-Branchen (in GENESIS mit fuehrender Null: WZ08-029 usw.)
    df_b_raw = _destatis_ffcsv(
        "42111-0004",
        startyear="2019",
        extra_params={
            "classifyingvariable1": "WZ08",
            "classifyingkey1": "WZ08-029,WZ08-024,WZ08-025,WZ08-020,WZ08-021",
        },
    )
    df_b = _parse_42111_df(df_b_raw)

    df_all = pd.concat([df_c, df_b], ignore_index=True)
    df_all = df_all[df_all["ZEIT"].str.match(r"^20\d{2}-\d{2}$")].copy()
    df_all = df_all.drop_duplicates(subset=["ZEIT", "WZ", "UMS_TYPE"], keep="first")

    ums_map = {}
    for u_code in ("UMS002", "UMS003", "UMS004"):
        sub = df_all[df_all["UMS_TYPE"] == u_code]
        piv = sub.pivot(index="ZEIT", columns="WZ", values="VAL_MRD").sort_index()
        ums_map[u_code] = piv
    return ums_map


def get_destatis_bip_neg_months():
    try:
        df = _destatis_ffcsv("81000-0002", startyear="2018")
        if df.empty:
            return []
        req = {"WERTORG", "VGR014", "VGRPKM"}
        sub = df[df["_CODES"].apply(lambda s: req.issubset(s))].copy()
        sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
        idx_map = dict(zip(sub["ZEIT"].astype(str).str.strip(), sub["V"]))
        q_months = {
            "Q1": ["01", "02", "03"],
            "Q2": ["04", "05", "06"],
            "Q3": ["07", "08", "09"],
            "Q4": ["10", "11", "12"],
        }
        neg_months = []
        for z, vc in sorted(idx_map.items()):
            if "-Q" not in z or z < "2019-Q1":
                continue
            prev_z = f"{int(z[:4]) - 1}{z[4:]}"
            vp = idx_map.get(prev_z, np.nan)
            if not np.isnan(vp) and vp != 0:
                yoy = (vc / vp - 1.0) * 100.0
                if yoy < 0.0:
                    yr, qp = z.split("-")
                    neg_months.extend([f"{yr}-{mm}" for mm in q_months.get(qp, [])])
        return sorted(list(set(neg_months)))
    except Exception:
        return []


def extract_turnover_series(ums_map, wz_list):
    for u_code in ("UMS002", "UMS003", "UMS004"):
        piv = ums_map.get(u_code, pd.DataFrame())
        missing = [w for w in wz_list if w not in piv.columns]
        if missing:
            raise KeyError(f"Fehlende WZ-Codes {missing} in {u_code}. Verfuegbare: {sorted(piv.columns.tolist())}")
    tot = ums_map["UMS002"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    dom = ums_map["UMS003"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    for_s = ums_map["UMS004"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    common = tot.index.intersection(dom.index).intersection(for_s.index).sort_values()
    return pd.DataFrame({
        "tot": tot.loc[common],
        "dom": dom.loc[common],
        "for": for_s.loc[common],
    })


def shade_recessions_mpl(ax, months, bip_neg_months):
    m_set = set(months)
    for start_ym, end_ym in REC_SVR_PHASES:
        idxs = [i for i, ym in enumerate(months) if start_ym <= ym <= end_ym]
        if idxs:
            ax.axvspan(min(idxs) - 0.5, max(idxs) + 0.5, color="#CBD5E1", alpha=0.45, zorder=0)
    for ym in bip_neg_months:
        if ym in m_set:
            idx = months.index(ym)
            ax.axvspan(idx - 0.5, idx + 0.5, color="#93C5FD", alpha=0.35, zorder=0)


def shade_recessions_plotly(fig, months, bip_neg_months):
    for start_ym, end_ym in REC_SVR_PHASES:
        in_p = [ym for ym in months if start_ym <= ym <= end_ym]
        if in_p:
            fig.add_vrect(x0=in_p[0], x1=in_p[-1], fillcolor="#CBD5E1", opacity=0.40, line_width=0, layer="below")
    m_set = set(months)
    for ym in bip_neg_months:
        if ym in m_set:
            fig.add_vrect(x0=ym, x1=ym, fillcolor="#93C5FD", opacity=0.35, line_width=0, layer="below")


def draw_year_groups(ax, months, m_names):
    ticks, labels = [], []
    for i, ym in enumerate(months):
        m = int(ym[5:7])
        if m in (1, 4, 7, 10):
            ticks.append(i)
            labels.append(m_names[m - 1])
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    for y in sorted({ym[:4] for ym in months}):
        idxs = [i for i, ym in enumerate(months) if ym.startswith(y)]
        if idxs:
            ax.text((min(idxs) + max(idxs)) / 2.0, -0.22, y, transform=ax.get_xaxis_transform(), ha="center", fontsize=8.2, color="#475569")


def build_single_chart(lang, fname, title, df_s, bip_neg_months, now_str):
    t = TEXTS[lang]
    use_c = t["comma"]
    months = list(df_s.index)
    x = np.arange(len(months))
    y_tot = df_s["tot"].values
    y_dom = df_s["dom"].values
    y_for = df_s["for"].values

    last_ym = months[-1]
    last_tot = float(y_tot[-1])
    for_pct = fmt_num((float(y_for[-1]) / last_tot) * 100.0, use_c, 1)
    dom_pct = fmt_num((float(y_dom[-1]) / last_tot) * 100.0, use_c, 1)
    subtitle = t["share_fmt"].format(ym=last_ym, for_pct=for_pct, dom_pct=dom_pct)

    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.76, bottom=0.24)
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=12.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.905, subtitle, ha="left", fontsize=8.8, fontweight="bold", color="#1E3A8A")

    ax.set_facecolor("#F8FAFC")
    ymax = max(10.0, float(np.ceil((np.nanmax(y_tot) * 1.12) / 5.0) * 5.0))
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_lbl"], fontsize=8.5, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    shade_recessions_mpl(ax, months, bip_neg_months)
    l1, = ax.plot(x, y_tot, color="#0F172A", lw=2.3, label=t["leg_tot"], zorder=4)
    l2, = ax.plot(x, y_for, color="#1D4ED8", lw=2.0, label=t["leg_for"], zorder=3)
    l3, = ax.plot(x, y_dom, color="#059669", lw=2.0, label=t["leg_dom"], zorder=3)
    p_svr = Patch(facecolor="#CBD5E1", alpha=0.55, label=t["leg_rec_svr"])
    p_bip = Patch(facecolor="#93C5FD", alpha=0.45, label=t["leg_rec_bip"])

    draw_year_groups(ax, months, t["m"])
    ax.text(0.5, -0.30, t["x_lbl"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(handles=[l1, l2, l3, p_svr, p_bip], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=3, frameon=False, fontsize=7.5)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    shade_recessions_plotly(fp, months, bip_neg_months)
    fmt_a = lambda arr: [fmt_num(v, use_c, 1) for v in arr]
    fp.add_trace(go.Scatter(x=months, y=[round(float(v), 2) for v in y_tot], customdata=fmt_a(y_tot), name=t["leg_tot"], mode="lines", line=dict(color="#0F172A", width=2.4), hovertemplate=f"{t['leg_tot']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(float(v), 2) for v in y_for], customdata=fmt_a(y_for), name=t["leg_for"], mode="lines", line=dict(color="#1D4ED8", width=2.0), hovertemplate=f"{t['leg_for']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(float(v), 2) for v in y_dom], customdata=fmt_a(y_dom), name=t["leg_dom"], mode="lines", line=dict(color="#059669", width=2.0), hovertemplate=f"{t['leg_dom']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#CBD5E1", symbol="square"), name=t["leg_rec_svr"], showlegend=True))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#93C5FD", symbol="square"), name=t["leg_rec_bip"], showlegend=True))

    t_vals = [m for i, m in enumerate(months) if i % 6 == 0]
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:12px;color:#1E3A8A;'>{subtitle}</span>", x=0.02, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", yanchor="bottom", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=115, b=95), height=480,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.28, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.28, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickmode="array", tickvals=t_vals, ticktext=t_vals, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(title_text=t["y_lbl"], range=[0, ymax], fixedrange=True, gridcolor="#E2E8F0", tickfont=dict(size=10.5, color="#475569"))
    out_html = f"{OUT_DIR}/{fname}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_dual_chart(lang, fname, title, df_a, df_b, prefix_key, bip_neg_months, now_str):
    t = TEXTS[lang]
    use_c = t["comma"]
    common = df_a.index.intersection(df_b.index).sort_values()
    df_a = df_a.loc[common]
    df_b = df_b.loc[common]
    months = list(common)
    x = np.arange(len(months))

    last_ym = months[-1]
    fa = fmt_num((float(df_a["for"].iloc[-1]) / float(df_a["tot"].iloc[-1])) * 100.0, use_c, 1)
    da = fmt_num((float(df_a["dom"].iloc[-1]) / float(df_a["tot"].iloc[-1])) * 100.0, use_c, 1)
    fb = fmt_num((float(df_b["for"].iloc[-1]) / float(df_b["tot"].iloc[-1])) * 100.0, use_c, 1)
    db = fmt_num((float(df_b["dom"].iloc[-1]) / float(df_b["tot"].iloc[-1])) * 100.0, use_c, 1)
    subtitle = t["share_dual_fmt"].format(
        ym=last_ym,
        lbl_a=t[f"{prefix_key}_a"], for_a=fa, dom_a=da,
        lbl_b=t[f"{prefix_key}_b"], for_b=fb, dom_b=db,
    )

    fig, ax = plt.subplots(figsize=(8.2, 5.7), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.71, bottom=0.23)
    fig.suptitle(title, x=0.09, y=0.965, ha="left", fontsize=11.3, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, subtitle, ha="left", fontsize=8.0, fontweight="bold", color="#1E3A8A")

    ax.set_facecolor("#F8FAFC")
    ymax = max(5.0, float(np.ceil((np.nanmax(df_b["tot"].values) * 1.12) / 2.0) * 2.0))
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_lbl"], fontsize=8.5, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    shade_recessions_mpl(ax, months, bip_neg_months)
    l_tb, = ax.plot(x, df_b["tot"].values, color="#0F172A", lw=2.2, label=t[f"{prefix_key}_tot_b"], zorder=4)
    l_ta, = ax.plot(x, df_a["tot"].values, color="#475569", lw=1.9, ls="--", label=t[f"{prefix_key}_tot_a"], zorder=4)
    l_fb, = ax.plot(x, df_b["for"].values, color="#1D4ED8", lw=2.0, label=t[f"{prefix_key}_for_b"], zorder=3)
    l_fa, = ax.plot(x, df_a["for"].values, color="#60A5FA", lw=1.7, ls="--", label=t[f"{prefix_key}_for_a"], zorder=3)
    l_db, = ax.plot(x, df_b["dom"].values, color="#059669", lw=2.0, label=t[f"{prefix_key}_dom_b"], zorder=3)
    l_da, = ax.plot(x, df_a["dom"].values, color="#34D399", lw=1.7, ls="--", label=t[f"{prefix_key}_dom_a"], zorder=3)
    p_svr = Patch(facecolor="#CBD5E1", alpha=0.55, label=t["leg_rec_svr"])
    p_bip = Patch(facecolor="#93C5FD", alpha=0.45, label=t["leg_rec_bip"])

    draw_year_groups(ax, months, t["m"])
    ax.text(0.5, -0.30, t["x_lbl"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(handles=[l_tb, l_ta, l_fb, l_fa, l_db, l_da, p_svr, p_bip], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=6.7)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    shade_recessions_plotly(fp, months, bip_neg_months)
    fmt_a = lambda arr: [fmt_num(v, use_c, 1) for v in arr]
    traces = [
        (df_b["tot"].values, t[f"{prefix_key}_tot_b"], "#0F172A", 2.3, "solid"),
        (df_a["tot"].values, t[f"{prefix_key}_tot_a"], "#475569", 1.9, "dash"),
        (df_b["for"].values, t[f"{prefix_key}_for_b"], "#1D4ED8", 2.0, "solid"),
        (df_a["for"].values, t[f"{prefix_key}_for_a"], "#60A5FA", 1.8, "dash"),
        (df_b["dom"].values, t[f"{prefix_key}_dom_b"], "#059669", 2.0, "solid"),
        (df_a["dom"].values, t[f"{prefix_key}_dom_a"], "#34D399", 1.8, "dash"),
    ]
    for vals, name_l, col, wd, dsh in traces:
        fp.add_trace(go.Scatter(x=months, y=[round(float(v), 2) for v in vals], customdata=fmt_a(vals), name=name_l, mode="lines", line=dict(color=col, width=wd, dash=dsh), hovertemplate=f"{name_l}: <b>%{{customdata}} Mrd. €</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#CBD5E1", symbol="square"), name=t["leg_rec_svr"], showlegend=True))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#93C5FD", symbol="square"), name=t["leg_rec_bip"], showlegend=True))

    t_vals = [m for i, m in enumerate(months) if i % 6 == 0]
    fp.update_layout(
        title=dict(text=f"<b>{title}</b><br><span style='font-size:11.5px;color:#1E3A8A;'>{subtitle}</span>", x=0.02, y=0.96, yanchor="top", font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", yanchor="bottom", font=dict(size=9.8, color="#1E293B")),
        margin=dict(l=52, r=24, t=145, b=95), height=520,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.26, xref="paper", yref="paper", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.26, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, tickmode="array", tickvals=t_vals, ticktext=t_vals, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(title_text=t["y_lbl"], range=[0, ymax], fixedrange=True, gridcolor="#E2E8F0", tickfont=dict(size=10.5, color="#475569"))
    out_html = f"{OUT_DIR}/{fname}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    ums_map = load_destatis_turnover()
    bip_neg_months = get_destatis_bip_neg_months()

    s_gesamt = extract_turnover_series(ums_map, ["WZ08-C"])
    s_autos = extract_turnover_series(ums_map, ["WZ08-29"])
    s_stahl_a = extract_turnover_series(ums_map, ["WZ08-24"])
    s_stahl_b = extract_turnover_series(ums_map, ["WZ08-24", "WZ08-25"])
    s_chemie_a = extract_turnover_series(ums_map, ["WZ08-20"])
    s_chemie_b = extract_turnover_series(ums_map, ["WZ08-20", "WZ08-21"])

    print(f"[OK] Destatis 42111-0004 geladen bis {s_gesamt.index[-1]} ({len(s_gesamt)} Monate)")

    for lang in ("de", "en"):
        t = TEXTS[lang]
        now_str = datetime.now().strftime(t["date_fmt"])
        build_single_chart(lang, "umsatz_gesamt", t["p1_t"], s_gesamt, bip_neg_months, now_str)
        build_single_chart(lang, "umsatz_autos", t["p2_t"], s_autos, bip_neg_months, now_str)
        build_dual_chart(lang, "umsatz_stahl", t["p3_t"], s_stahl_a, s_stahl_b, "p3", bip_neg_months, now_str)
        build_dual_chart(lang, "umsatz_chemie", t["p4_t"], s_chemie_a, s_chemie_b, "p4", bip_neg_months, now_str)


if __name__ == "__main__":
    main()

