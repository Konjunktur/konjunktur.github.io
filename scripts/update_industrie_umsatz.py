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
import matplotlib.patches as mpatches
import plotly.graph_objects as go
from plotly.subplots import make_subplots

D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()
G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"

OUT_DIR = "static/umsatz-industrie"
os.makedirs(OUT_DIR, exist_ok=True)

RECESSION_SVR_BBK = [
    ("2019-01", "2020-04"),
    ("2022-10", "2023-03"),
    ("2024-04", "2025-12"),
]

WZ_C_DIVISIONS = [f"WZ08-{d:02d}" for d in range(10, 34)]

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "x_lbl": "Berichtsmonat (Originalwerte)",
        "y_lbl": "Mrd. EUR",
        "src": "Quelle: Statistisches Bundesamt (GENESIS-Online, Tab. 42111-0004), eigene Berechnungen | Stand: ",
        "rec_svr": "Rezession/Schwäche (SVR/BBK)",
        "rec_bip": "Reales BIP < 0 % gg. Vj.",
        "tot_lbl": "Umsatz insgesamt",
        "dom_lbl": "Umsatz Inland",
        "for_lbl": "Umsatz Ausland",
        "tot_a_lbl": "Umsatz insgesamt (engere Abgrenzung)",
        "dom_a_lbl": "Umsatz Inland (engere Abgrenzung)",
        "for_a_lbl": "Umsatz Ausland (engere Abgrenzung)",
        "tot_b_lbl": "Umsatz insgesamt (inkl. Erweiterung)",
        "dom_b_lbl": "Umsatz Inland (inkl. Erweiterung)",
        "for_b_lbl": "Umsatz Ausland (inkl. Erweiterung)",
        "share_prefix": "Aktueller Monat",
        "share_for": "Auslandsanteil",
        "share_dom": "Inlandsanteil",
        "charts": {
            "umsatz_gesamt": {
                "title": "Verarbeitendes Gewerbe insgesamt: Umsatz, Inland und Ausland",
                "sub_wz": "WZ 2008: Abschnitt C (Abteilungen 10–33), Betriebe, in Mrd. Euro",
            },
            "umsatz_autos": {
                "title": "Kraftwagen und Kraftwagenteile: Umsatz, Inland und Ausland",
                "sub_wz": "WZ 2008: Abt. 29 (vgl. WAM2 Kap. 87), Betriebe, in Mrd. Euro",
            },
            "umsatz_stahl": {
                "title": "Metallerzeugung und -bearbeitung (mit/ohne Metallerzeugnisse)",
                "sub_wz": "WZ 2008: Abt. 24 vs. Abt. 24+25 (vgl. WAM2 Kap. 72 / 72+73), in Mrd. Euro",
                "a_name": "Abt. 24 (Metallerzeugung)",
                "b_name": "Abt. 24+25 (inkl. Metallerzeugnisse)",
            },
            "umsatz_chemie": {
                "title": "Chemische Erzeugnisse (ohne/mit pharmazeutischen Erzeugnissen)",
                "sub_wz": "WZ 2008: Abt. 20 vs. Abt. 20+21 (vgl. WAM2 Kap. 28–38 ohne/mit Kap. 30), in Mrd. Euro",
                "a_name": "Abt. 20 (Chemie ohne Pharma)",
                "b_name": "Abt. 20+21 (Chemie inkl. Pharma)",
            },
        },
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "x_lbl": "Reporting month (unadjusted data)",
        "y_lbl": "EUR billion",
        "src": "Source: Federal Statistical Office (GENESIS-Online, Table 42111-0004), own calculations | As of: ",
        "rec_svr": "Recession/weakness (GCEE/BBK)",
        "rec_bip": "Real GDP < 0% YoY",
        "tot_lbl": "Total turnover",
        "dom_lbl": "Domestic turnover",
        "for_lbl": "Foreign turnover",
        "tot_a_lbl": "Total turnover (narrow scope)",
        "dom_a_lbl": "Domestic turnover (narrow scope)",
        "for_a_lbl": "Foreign turnover (narrow scope)",
        "tot_b_lbl": "Total turnover (incl. extended scope)",
        "dom_b_lbl": "Domestic turnover (incl. extended scope)",
        "for_b_lbl": "Foreign turnover (incl. extended scope)",
        "share_prefix": "Latest month",
        "share_for": "Foreign share",
        "share_dom": "Domestic share",
        "charts": {
            "umsatz_gesamt": {
                "title": "Total Manufacturing: Total, Domestic and Foreign Turnover",
                "sub_wz": "WZ 2008: Section C (Divisions 10–33), local units, EUR billion",
            },
            "umsatz_autos": {
                "title": "Motor Vehicles, Trailers and Semi-Trailers: Turnover",
                "sub_wz": "WZ 2008: Div. 29 (cf. WAM2 Ch. 87), local units, EUR billion",
            },
            "umsatz_stahl": {
                "title": "Basic Metals (with/without Fabricated Metal Products)",
                "sub_wz": "WZ 2008: Div. 24 vs. Div. 24+25 (cf. WAM2 Ch. 72 / 72+73), EUR billion",
                "a_name": "Div. 24 (Basic metals)",
                "b_name": "Div. 24+25 (incl. fabricated metals)",
            },
            "umsatz_chemie": {
                "title": "Chemicals and Chemical Products (with/without Pharmaceuticals)",
                "sub_wz": "WZ 2008: Div. 20 vs. Div. 20+21 (cf. WAM2 Ch. 28–38 excl./incl. Ch. 30), EUR billion",
                "a_name": "Div. 20 (Chemicals excl. pharma)",
                "b_name": "Div. 20+21 (Chemicals incl. pharma)",
            },
        },
    },
}


def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def _destatis_ffcsv(table, startyear="2019", extra_params=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS nicht gesetzt.")
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
        rj = requests.post(
            f"{G_BASE}/tablefile",
            headers=headers,
            data={**data, "job": "true"},
            timeout=90,
        )
        m = re.search(
            r"([0-9A-Z\-]+_[0-9]+)",
            str(json.loads(rj.text).get("Status", {}).get("Content", "")),
        )
        if not m:
            return pd.DataFrame()
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            txt = _unpack(
                requests.post(
                    f"{G_BASE}/resultfile",
                    headers=headers,
                    data={
                        "name": m.group(1),
                        "area": "all",
                        "compress": "false",
                        "language": "de",
                    },
                    timeout=90,
                )
            )
            if not txt.lstrip().startswith("{"):
                raw = txt
                break

    rows = [
        row
        for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"')
        if len(row) >= 5
    ]
    if len(rows) < 3:
        return pd.DataFrame()
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame(
        [row[: len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr
    )
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
            zeit_s = pd.Series(
                np.where(q_ext.notna(), zeit_s + "-Q" + q_ext.fillna(""), zeit_s),
                index=df.index,
            )
            break
        if s_code.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            m_ext = s_code.str.extract(r"([0-9]+)", expand=False).str.zfill(2)
            zeit_s = pd.Series(
                np.where(m_ext.notna(), zeit_s + "-" + m_ext.fillna(""), zeit_s),
                index=df.index,
            )
            break
    df["ZEIT"] = zeit_s
    df["WERT"] = df[v_col]
    return df


def normalize_wz(raw_str):
    s = str(raw_str).strip().upper()
    m = re.search(r"WZ08[-_\s]*([A-Z]|0?\d{2})", s)
    if not m:
        return ""
    part = m.group(1)
    if part.isdigit():
        return f"WZ08-{int(part):02d}"
    return f"WZ08-{part}"


def load_destatis_turnover():
    df = _destatis_ffcsv("42111-0004", "2019")
    if df.empty:
        raise RuntimeError("Destatis Tabelle 42111-0004 lieferte keine Daten.")

    wz_col = None
    for c in df.columns:
        if c.endswith("_code") and c not in {"statistics_code", "time_code", "value_variable_code"}:
            if df[c].astype(str).str.contains(r"WZ08", case=False, na=False).any():
                wz_col = c
                break
    if wz_col is None:
        for c in df.columns:
            if df[c].astype(str).str.contains(r"WZ08", case=False, na=False).any():
                wz_col = c
                break
    if wz_col is None:
        raise RuntimeError("Keine WZ08-Spalte in 42111-0004 gefunden.")

    df["WZ"] = df[wz_col].apply(normalize_wz)
    df = df[df["WZ"] != ""].copy()

    lbl_col = "value_variable_label" if "value_variable_label" in df.columns else None
    code_col = "value_variable_code" if "value_variable_code" in df.columns else None

    if lbl_col and code_col:
        pairs = (
            df[[code_col, lbl_col]]
            .drop_duplicates()
            .apply(lambda r: f"{r[code_col]}={r[lbl_col]}", axis=1)
            .tolist()
        )
        print(f"[DESTATIS 42111-0004] Merkmale: {pairs}")

    df["V"] = pd.to_numeric(
        df["WERT"].astype(str).str.replace(",", "."), errors="coerce"
    )
    df = df[df["ZEIT"].astype(str).str.match(r"^20\d{2}-\d{2}$")].copy()
    df = df[df["ZEIT"] >= "2019-01"].copy()

    targets = {
        "tot": ("umsatz", {"UMS002"}),
        "dom": ("inlandsumsatz", {"UMS003", "UMS005", "UMS011"}),
        "for": ("auslandsumsatz", {"UMS004", "UMS006", "UMS012"}),
    }

    ums_map = {}
    for key, (lbl_exact, fallback_codes) in targets.items():
        sub = pd.DataFrame()
        if lbl_col:
            s_lbl = df[lbl_col].astype(str).str.strip().str.lower()
            sub = df[s_lbl == lbl_exact].copy()
        if sub.empty and code_col:
            s_cd = df[code_col].astype(str).str.strip().str.upper()
            sub = df[s_cd.isin(fallback_codes)].copy()
        if sub.empty:
            avail_lbls = sorted(df[lbl_col].dropna().unique().tolist()) if lbl_col else []
            raise RuntimeError(
                f"Merkmal '{lbl_exact}' nicht in 42111-0004 gefunden. Verfuegbare Labels: {avail_lbls}"
            )
        sub = sub.dropna(subset=["V"])
        piv = sub.pivot_table(
            index="ZEIT", columns="WZ", values="V", aggfunc="first"
        ).sort_index()
        # Umrechnung Tsd. EUR -> Mrd. EUR (1 Mrd. = 1.000.000 Tsd.)
        if piv.median().median() > 10000:
            piv = piv / 1_000_000.0
        ums_map[key] = piv

    return ums_map


def get_destatis_bip_q():
    try:
        df = _destatis_ffcsv("81000-0002", "2018")
        if df.empty:
            return pd.Series(dtype=float)
        code_cols = [
            c
            for c in df.columns
            if c.endswith("_code") and c not in {"statistics_code", "time_code"}
        ]
        codes_s = (
            df.loc[:, code_cols]
            .fillna("")
            .astype(str)
            .apply(lambda r: set(x.strip() for x in r if x.strip()), axis=1)
        )
        req = {"WERTORG", "VGR014", "VGRPKM"}
        sub = df[codes_s.apply(lambda s: req.issubset(s))].copy()
        sub["V"] = pd.to_numeric(
            sub["WERT"].astype(str).str.replace(",", "."), errors="coerce"
        )
        sub = (
            sub.dropna(subset=["V"])
            .drop_duplicates(subset=["ZEIT"], keep="first")
            .sort_values("ZEIT")
        )
        idx_map = dict(zip(sub["ZEIT"].astype(str).str.strip(), sub["V"]))
        out = {}
        for z, vc in idx_map.items():
            if "-Q" not in z:
                continue
            prev_z = f"{int(z[:4]) - 1}{z[4:]}"
            vp = idx_map.get(prev_z, np.nan)
            if not np.isnan(vp) and vp != 0:
                out[z] = round((vc / vp - 1.0) * 100.0, 1)
        return pd.Series(out).sort_index()
    except Exception:
        return pd.Series(dtype=float)


def get_bip_neg_spans(months, bip_q):
    if bip_q.empty or not months:
        return []
    neg_months = set()
    q_months = {
        "Q1": ("01", "02", "03"),
        "Q2": ("04", "05", "06"),
        "Q3": ("07", "08", "09"),
        "Q4": ("10", "11", "12"),
    }
    for k, v in bip_q.items():
        if float(v) < 0.0 and "-Q" in k:
            yr, q = k.split("-")
            for mm in q_months.get(q, ()):
                neg_months.add(f"{yr}-{mm}")
    spans = []
    in_span = False
    start_i = 0
    for i, ym in enumerate(months):
        if ym in neg_months and not in_span:
            in_span = True
            start_i = i
        elif ym not in neg_months and in_span:
            in_span = False
            spans.append((start_i, i - 1))
    if in_span:
        spans.append((start_i, len(months) - 1))
    return spans


def add_recession_shading_mpl(ax, months, bip_q):
    for s_ym, e_ym in RECESSION_SVR_BBK:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            ax.axvspan(
                min(idxs) - 0.5,
                max(idxs) + 0.5,
                color="#E2E8F0",
                alpha=0.65,
                zorder=0,
            )
    for s_i, e_i in get_bip_neg_spans(months, bip_q):
        ax.axvspan(
            s_i - 0.5,
            e_i + 0.5,
            color="#93C5FD",
            alpha=0.35,
            zorder=0.5,
        )


def add_recession_shading_plotly(fig_p, months, bip_q):
    for s_ym, e_ym in RECESSION_SVR_BBK:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            fig_p.add_vrect(
                x0=months[min(idxs)],
                x1=months[max(idxs)],
                fillcolor="#CBD5E1",
                opacity=0.35,
                layer="below",
                line_width=0,
            )
    for s_i, e_i in get_bip_neg_spans(months, bip_q):
        fig_p.add_vrect(
            x0=months[s_i],
            x1=months[e_i],
            fillcolor="#93C5FD",
            opacity=0.30,
            layer="below",
            line_width=0,
        )


def draw_year_groups(ax, months, m_names):
    ticks, labels = [], []
    for i, ym in enumerate(months):
        m = int(ym[5:7])
        if m in (1, 4, 7, 10):
            ticks.append(i)
            labels.append(m_names[m - 1])
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    years = sorted(list({ym[:4] for ym in months}))
    for y in years:
        idxs = [i for i, ym in enumerate(months) if ym.startswith(y)]
        if idxs:
            mid = (min(idxs) + max(idxs)) / 2.0
            ax.text(
                mid,
                -0.21,
                y,
                transform=ax.get_xaxis_transform(),
                ha="center",
                fontsize=8.2,
                color="#475569",
            )


def extract_turnover_series(ums_map, wz_list):
    out = {}
    for key in ("tot", "dom", "for"):
        piv = ums_map[key]
        missing = [w for w in wz_list if w not in piv.columns]
        if missing:
            raise KeyError(
                f"Fehlende WZ-Codes {missing} in {key}. Verfuegbare: {sorted(piv.columns.tolist())}"
            )
        s = piv[wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
        out[key] = s
    common = out["tot"].index.intersection(out["dom"].index).intersection(out["for"].index)
    return {k: out[k].loc[common] for k in ("tot", "dom", "for")}


def build_single_chart(lang, chart_key, data_dict, bip_q, now_str):
    t = TEXTS[lang]
    c_cfg = t["charts"][chart_key]
    use_c = t["comma"]
    fmt_arr = lambda seq: [fmt_num(v, use_c, 1) for v in seq]

    months = list(data_dict["tot"].index)
    x = np.arange(len(months))
    y_tot = [float(data_dict["tot"].loc[ym]) for ym in months]
    y_dom = [float(data_dict["dom"].loc[ym]) for ym in months]
    y_for = [float(data_dict["for"].loc[ym]) for ym in months]

    last_ym = months[-1]
    last_m_lbl = f"{t['m'][int(last_ym[5:7]) - 1]} {last_ym[:4]}"
    tot_last = y_tot[-1]
    for_share = (y_for[-1] / tot_last * 100.0) if tot_last > 0 else 0.0
    dom_share = (y_dom[-1] / tot_last * 100.0) if tot_last > 0 else 0.0
    share_line = (
        f"{c_cfg['sub_wz']}  |  {t['share_prefix']} ({last_m_lbl}): "
        f"{t['share_for']} {fmt_num(for_share, use_c, 1)} %, "
        f"{t['share_dom']} {fmt_num(dom_share, use_c, 1)} %"
    )

    # PNG
    fig, ax = plt.subplots(figsize=(8.4, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.73, bottom=0.22)
    fig.suptitle(
        c_cfg["title"],
        x=0.09,
        y=0.96,
        ha="left",
        fontsize=12.0,
        fontweight="bold",
        color="#0F172A",
    )
    fig.text(0.09, 0.905, share_line, ha="left", fontsize=8.1, color="#334155")

    ymax = max(y_tot) * 1.12
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_lbl"], fontsize=8.3, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    add_recession_shading_mpl(ax, months, bip_q)
    p1 = ax.plot(x, y_tot, color="#0F172A", lw=2.3, label=t["tot_lbl"], zorder=4)[0]
    p2 = ax.plot(x, y_for, color="#1D4ED8", lw=2.0, label=t["for_lbl"], zorder=3)[0]
    p3 = ax.plot(x, y_dom, color="#D97706", lw=2.0, label=t["dom_lbl"], zorder=3)[0]

    draw_year_groups(ax, months, t["m"])
    ax.text(0.5, -0.28, t["x_lbl"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")

    h_svr = mpatches.Patch(color="#E2E8F0", label=t["rec_svr"])
    h_bip = mpatches.Patch(color="#93C5FD", alpha=0.55, label=t["rec_bip"])
    ax.legend(
        handles=[p1, p2, p3, h_svr, h_bip],
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=3,
        frameon=False,
        fontsize=7.3,
    )

    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{chart_key}{t['sfx']}.png", dpi=300)
    plt.close()

    # HTML
    fp = go.Figure()
    add_recession_shading_plotly(fp, months, bip_q)
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_tot],
            customdata=fmt_arr(y_tot),
            name=t["tot_lbl"],
            mode="lines",
            line=dict(color="#0F172A", width=2.4),
            hovertemplate=f"{t['tot_lbl']}: <b>%{{customdata}} {t['y_lbl']}</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_for],
            customdata=fmt_arr(y_for),
            name=t["for_lbl"],
            mode="lines",
            line=dict(color="#1D4ED8", width=2.1),
            hovertemplate=f"{t['for_lbl']}: <b>%{{customdata}} {t['y_lbl']}</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_dom],
            customdata=fmt_arr(y_dom),
            name=t["dom_lbl"],
            mode="lines",
            line=dict(color="#D97706", width=2.1),
            hovertemplate=f"{t['dom_lbl']}: <b>%{{customdata}} {t['y_lbl']}</b><extra></extra>",
        )
    )
    t_vals = [m for i, m in enumerate(months) if i % 6 == 0]
    fp.update_layout(
        title=dict(
            text=f"<b>{c_cfg['title']}</b><br><span style='font-size:11.5px;color:#475569'>{share_line}</span>",
            x=0.02,
            y=0.96,
            yanchor="top",
            font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=10.5, color="#1E293B"),
        ),
        margin=dict(l=55, r=24, t=115, b=90),
        height=480,
        annotations=[
            dict(
                text=f"{t['src']}{now_str}",
                x=0.0,
                y=-0.27,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.5, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.27,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.5, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fp.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        tickmode="array",
        tickvals=t_vals,
        ticktext=t_vals,
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=10.0, color="#475569"),
    )
    fp.update_yaxes(
        title_text=t["y_lbl"],
        range=[0, ymax],
        fixedrange=True,
        gridcolor="#E2E8F0",
        tickfont=dict(size=10.0, color="#475569"),
    )
    out_html = f"{OUT_DIR}/{chart_key}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_dual_chart(lang, chart_key, data_a, data_b, bip_q, now_str):
    t = TEXTS[lang]
    c_cfg = t["charts"][chart_key]
    use_c = t["comma"]
    fmt_arr = lambda seq: [fmt_num(v, use_c, 1) for v in seq]

    months = list(data_a["tot"].index.intersection(data_b["tot"].index))
    x = np.arange(len(months))

    ya_tot = [float(data_a["tot"].loc[ym]) for ym in months]
    ya_for = [float(data_a["for"].loc[ym]) for ym in months]
    ya_dom = [float(data_a["dom"].loc[ym]) for ym in months]

    yb_tot = [float(data_b["tot"].loc[ym]) for ym in months]
    yb_for = [float(data_b["for"].loc[ym]) for ym in months]
    yb_dom = [float(data_b["dom"].loc[ym]) for ym in months]

    last_ym = months[-1]
    last_m_lbl = f"{t['m'][int(last_ym[5:7]) - 1]} {last_ym[:4]}"
    fa_sh = (ya_for[-1] / ya_tot[-1] * 100.0) if ya_tot[-1] > 0 else 0.0
    da_sh = (ya_dom[-1] / ya_tot[-1] * 100.0) if ya_tot[-1] > 0 else 0.0
    fb_sh = (yb_for[-1] / yb_tot[-1] * 100.0) if yb_tot[-1] > 0 else 0.0
    db_sh = (yb_dom[-1] / yb_tot[-1] * 100.0) if yb_tot[-1] > 0 else 0.0

    share_line = (
        f"{t['share_prefix']} ({last_m_lbl}) – {c_cfg['a_name']}: "
        f"{t['share_for']} {fmt_num(fa_sh, use_c, 1)} % / {t['share_dom']} {fmt_num(da_sh, use_c, 1)} %  |  "
        f"{c_cfg['b_name']}: {t['share_for']} {fmt_num(fb_sh, use_c, 1)} % / {t['share_dom']} {fmt_num(db_sh, use_c, 1)} %"
    )

    # PNG
    fig, ax = plt.subplots(figsize=(8.4, 5.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.69, bottom=0.22)
    fig.suptitle(
        c_cfg["title"],
        x=0.09,
        y=0.96,
        ha="left",
        fontsize=11.8,
        fontweight="bold",
        color="#0F172A",
    )
    fig.text(0.09, 0.912, c_cfg["sub_wz"], ha="left", fontsize=7.9, color="#475569")
    fig.text(0.09, 0.878, share_line, ha="left", fontsize=7.5, color="#1E293B")

    ymax = max(yb_tot) * 1.12
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_lbl"], fontsize=8.3, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    add_recession_shading_mpl(ax, months, bip_q)
    pb1 = ax.plot(x, yb_tot, color="#0F172A", lw=2.2, label=t["tot_b_lbl"], zorder=4)[0]
    pb2 = ax.plot(x, yb_for, color="#1D4ED8", lw=1.9, label=t["for_b_lbl"], zorder=3)[0]
    pb3 = ax.plot(x, yb_dom, color="#D97706", lw=1.9, label=t["dom_b_lbl"], zorder=3)[0]

    pa1 = ax.plot(x, ya_tot, color="#0F172A", lw=1.6, ls="--", label=t["tot_a_lbl"], zorder=4)[0]
    pa2 = ax.plot(x, ya_for, color="#1D4ED8", lw=1.5, ls="--", label=t["for_a_lbl"], zorder=3)[0]
    pa3 = ax.plot(x, ya_dom, color="#D97706", lw=1.5, ls="--", label=t["dom_a_lbl"], zorder=3)[0]

    draw_year_groups(ax, months, t["m"])
    ax.text(0.5, -0.28, t["x_lbl"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")

    h_svr = mpatches.Patch(color="#E2E8F0", label=t["rec_svr"])
    h_bip = mpatches.Patch(color="#93C5FD", alpha=0.55, label=t["rec_bip"])
    ax.legend(
        handles=[pb1, pb2, pb3, pa1, pa2, pa3, h_svr, h_bip],
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=2,
        frameon=False,
        fontsize=6.8,
    )

    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{chart_key}{t['sfx']}.png", dpi=300)
    plt.close()

    # HTML
    fp = go.Figure()
    add_recession_shading_plotly(fp, months, bip_q)
    traces = [
        (yb_tot, t["tot_b_lbl"], "#0F172A", 2.3, "solid"),
        (yb_for, t["for_b_lbl"], "#1D4ED8", 2.0, "solid"),
        (yb_dom, t["dom_b_lbl"], "#D97706", 2.0, "solid"),
        (ya_tot, t["tot_a_lbl"], "#0F172A", 1.7, "dash"),
        (ya_for, t["for_a_lbl"], "#1D4ED8", 1.6, "dash"),
        (ya_dom, t["dom_a_lbl"], "#D97706", 1.6, "dash"),
    ]
    for y_seq, name_s, col_s, w_s, dash_s in traces:
        fp.add_trace(
            go.Scatter(
                x=months,
                y=[round(v, 2) for v in y_seq],
                customdata=fmt_arr(y_seq),
                name=name_s,
                mode="lines",
                line=dict(color=col_s, width=w_s, dash=dash_s),
                hovertemplate=f"{name_s}: <b>%{{customdata}} {t['y_lbl']}</b><extra></extra>",
            )
        )

    t_vals = [m for i, m in enumerate(months) if i % 6 == 0]
    fp.update_layout(
        title=dict(
            text=f"<b>{c_cfg['title']}</b><br><span style='font-size:10.5px;color:#475569'>{share_line}</span>",
            x=0.02,
            y=0.96,
            yanchor="top",
            font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=9.8, color="#1E293B"),
        ),
        margin=dict(l=55, r=24, t=140, b=90),
        height=510,
        annotations=[
            dict(
                text=f"{t['src']}{now_str}",
                x=0.0,
                y=-0.25,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.5, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.25,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.5, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fp.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        tickmode="array",
        tickvals=t_vals,
        ticktext=t_vals,
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=10.0, color="#475569"),
    )
    fp.update_yaxes(
        title_text=t["y_lbl"],
        range=[0, ymax],
        fixedrange=True,
        gridcolor="#E2E8F0",
        tickfont=dict(size=10.0, color="#475569"),
    )
    out_html = f"{OUT_DIR}/{chart_key}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def main():
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    ums_map = load_destatis_turnover()
    bip_q = get_destatis_bip_q()

    s_gesamt = extract_turnover_series(ums_map, WZ_C_DIVISIONS)
    s_autos = extract_turnover_series(ums_map, ["WZ08-29"])
    s_stahl_a = extract_turnover_series(ums_map, ["WZ08-24"])
    s_stahl_b = extract_turnover_series(ums_map, ["WZ08-24", "WZ08-25"])
    s_chemie_a = extract_turnover_series(ums_map, ["WZ08-20"])
    s_chemie_b = extract_turnover_series(ums_map, ["WZ08-20", "WZ08-21"])

    print(
        f"[OK] Daten geladen: {s_gesamt['tot'].index[0]} bis {s_gesamt['tot'].index[-1]} "
        f"({len(s_gesamt['tot'])} Monate)"
    )

    for lang in ("de", "en"):
        now_str = datetime.now().strftime(TEXTS[lang]["date_fmt"])
        build_single_chart(lang, "umsatz_gesamt", s_gesamt, bip_q, now_str)
        build_single_chart(lang, "umsatz_autos", s_autos, bip_q, now_str)
        build_dual_chart(lang, "umsatz_stahl", s_stahl_a, s_stahl_b, bip_q, now_str)
        build_dual_chart(lang, "umsatz_chemie", s_chemie_a, s_chemie_b, bip_q, now_str)

    print("[SUCCESS] Alle 16 Grafik-Dateien unter static/umsatz-industrie/ erzeugt.")


if __name__ == "__main__":
    main()
