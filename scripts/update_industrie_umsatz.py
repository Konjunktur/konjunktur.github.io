#!/usr/bin/env python3
"""
Aktualisiert alle Grafiken (DE & EN, .png und .html) fuer die Unterrubrik:
"Umsatz insgesamt, Umsatz Inland, Umsatz Ausland und nach ausgewählten Warengruppen
des Verarbeitenden Gewerbes"
Datenbasis: Statistisches Bundesamt (Destatis GENESIS-Online), Tabelle 42111-0004
Merkmale: UMS002 (Umsatz), UMSN2 (Inlandsumsatz), UMSN3 (Auslandsumsatz)
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


G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"
D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()

OUT_DIR = "static/umsatz-industrie"

# Offizielle WZ-2008-Abteilungen des Abschnitts C (Verarbeitendes Gewerbe: 10 bis 33)
WZ_C_DIVISIONS = [f"WZ08-{i:02d}" for i in range(10, 34)]

# SVR / Deutsche Bundesbank Rezessions- und Schwaechephasen ab 2019
SVR_PHASES = [
    ("2020-02", "2020-04"),
    ("2022-10", "2025-12"),
]

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "x_m": "Monat / Jahr",
        "src": "Quelle: Statistisches Bundesamt (GENESIS-Online, Tabelle 42111-0004) | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "g1_t": "Verarbeitendes Gewerbe insgesamt: Umsatz, Inlandsumsatz und Auslandsumsatz",
        "g1_sub": "Monatswerte (Januar 2019 bis {end_lbl}), in Mrd. € | Aktuell ({end_lbl}): Ausland {f_sh} %, Inland {d_sh} %",
        "g1_l": ["Umsatz insgesamt", "Inlandsumsatz", "Auslandsumsatz"],
        "g2_t": "Kraftwagen und Kraftwagenteile (WZ 29): Umsatz, Inlandsumsatz und Auslandsumsatz",
        "g2_sub": "Monatswerte (Januar 2019 bis {end_lbl}), in Mrd. € | Aktuell ({end_lbl}): Ausland {f_sh} %, Inland {d_sh} %",
        "g2_l": ["Umsatz insgesamt", "Inlandsumsatz", "Auslandsumsatz"],
        "g3_t": "Metallerzeugung/-bearbeitung (WZ 24) vs. inkl. Metallerzeugnisse (WZ 24+25)",
        "g3_sub": "Monatswerte in Mrd. € | Aktuell ({end_lbl}): WZ 24 Ausland {f1_sh} % (Inland {d1_sh} %) | WZ 24+25 Ausland {f2_sh} % (Inland {d2_sh} %)",
        "g3_l": [
            "Umsatz gesamt (WZ 24)",
            "Inlandsumsatz (WZ 24)",
            "Auslandsumsatz (WZ 24)",
            "Umsatz gesamt (WZ 24+25)",
            "Inlandsumsatz (WZ 24+25)",
            "Auslandsumsatz (WZ 24+25)",
        ],
        "g4_t": "Chemische Erzeugnisse (WZ 20) vs. Chemie inkl. Pharmazeutika (WZ 20+21)",
        "g4_sub": "Monatswerte in Mrd. € | Aktuell ({end_lbl}): WZ 20 Ausland {f1_sh} % (Inland {d1_sh} %) | WZ 20+21 Ausland {f2_sh} % (Inland {d2_sh} %)",
        "g4_l": [
            "Umsatz gesamt (WZ 20)",
            "Inlandsumsatz (WZ 20)",
            "Auslandsumsatz (WZ 20)",
            "Umsatz gesamt (WZ 20+21)",
            "Inlandsumsatz (WZ 20+21)",
            "Auslandsumsatz (WZ 20+21)",
        ],
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "x_m": "Month / Year",
        "src": "Source: Federal Statistical Office (GENESIS-Online, Table 42111-0004) | As of: ",
        "leg_svr": "Recession/Weakness (GCEE/BBK)",
        "leg_bip": "Real GDP < 0% YoY",
        "g1_t": "Manufacturing Total: Total, Domestic and Foreign Turnover",
        "g1_sub": "Monthly values (January 2019 to {end_lbl}), in EUR bn | Latest ({end_lbl}): Foreign {f_sh}%, Domestic {d_sh}%",
        "g1_l": ["Total turnover", "Domestic turnover", "Foreign turnover"],
        "g2_t": "Motor Vehicles, Trailers and Semi-Trailers (WZ 29): Total, Domestic and Foreign Turnover",
        "g2_sub": "Monthly values (January 2019 to {end_lbl}), in EUR bn | Latest ({end_lbl}): Foreign {f_sh}%, Domestic {d_sh}%",
        "g2_l": ["Total turnover", "Domestic turnover", "Foreign turnover"],
        "g3_t": "Basic Metals (WZ 24) vs. Basic Metals incl. Fabricated Metal Products (WZ 24+25)",
        "g3_sub": "Monthly values in EUR bn | Latest ({end_lbl}): WZ 24 Foreign {f1_sh}% (Domestic {d1_sh}%) | WZ 24+25 Foreign {f2_sh}% (Domestic {d2_sh}%)",
        "g3_l": [
            "Total turnover (WZ 24)",
            "Domestic turnover (WZ 24)",
            "Foreign turnover (WZ 24)",
            "Total turnover (WZ 24+25)",
            "Domestic turnover (WZ 24+25)",
            "Foreign turnover (WZ 24+25)",
        ],
        "g4_t": "Chemicals and Chemical Products (WZ 20) vs. Chemicals incl. Pharmaceuticals (WZ 20+21)",
        "g4_sub": "Monthly values in EUR bn | Latest ({end_lbl}): WZ 20 Foreign {f1_sh}% (Domestic {d1_sh}%) | WZ 20+21 Foreign {f2_sh}% (Domestic {d2_sh}%)",
        "g4_l": [
            "Total turnover (WZ 20)",
            "Domestic turnover (WZ 20)",
            "Foreign turnover (WZ 20)",
            "Total turnover (WZ 20+21)",
            "Domestic turnover (WZ 20+21)",
            "Foreign turnover (WZ 20+21)",
        ],
    },
}


def fmt_num(val, use_comma=True, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def ym_label(ym, lang="de"):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{TEXTS[lang]['m'][m - 1]} {y}"


def normalize_wz(code_str):
    s = str(code_str).strip().upper()
    m = re.match(r"^WZ08-0*(\d+)$", s)
    if m:
        num = int(m.group(1))
        return f"WZ08-{num:02d}"
    return s


def _destatis_ffcsv(table, startyear="2019", extra_params=None):
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


def load_destatis_turnover():
    # Abruf exakt wie in v6 (ohne einschraenkendes classifyingvariable1, da sonst nur WZ08-X geliefert wird)
    df = _destatis_ffcsv("42111-0004", startyear="2019")
    if df.empty:
        raise RuntimeError("Destatis Tabelle 42111-0004 lieferte keine Daten.")

    wz_col = None
    for c in df.columns:
        if c.endswith("_code") and c not in {"statistics_code", "time_code", "value_variable_code"}:
            vals_sample = df[c].dropna().astype(str).str.strip().head(200)
            if vals_sample.str.startswith("WZ08-").any():
                wz_col = c
                break
    if wz_col is None:
        for c in df.columns:
            vals_sample = df[c].dropna().astype(str).str.strip().head(200)
            if vals_sample.str.startswith("WZ08-").any():
                wz_col = c
                break
    if wz_col is None:
        raise RuntimeError(f"WZ08-Spalte in 42111-0004 nicht gefunden. Spalten: {list(df.columns)}")

    df["WZ"] = df[wz_col].apply(normalize_wz)
    df = df[df["ZEIT"].astype(str).str.match(r"^20\d{2}-\d{2}$")].copy()
    df = df[df["ZEIT"] >= "2019-01"].copy()
    df["NUM"] = pd.to_numeric(df["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["NUM"]).copy()

    v_code_col = "value_variable_code" if "value_variable_code" in df.columns else None
    v_lbl_col = "value_variable_label" if "value_variable_label" in df.columns else None

    if v_code_col and v_lbl_col:
        pairs = sorted({f"{c}={l}" for c, l in zip(df[v_code_col].astype(str), df[v_lbl_col].astype(str))})
        print(f"[DESTATIS 42111-0004] Merkmale: {pairs}")

    avail_wz = sorted(df["WZ"].unique().tolist())
    print(f"[DESTATIS 42111-0004] WZ-Codes ({len(avail_wz)}): {avail_wz[:10]} ... {avail_wz[-5:]}")

    # Offizielle Destatis-Codes in 42111-0004:
    # UMS002 = Umsatz, UMSN2 = Inlandsumsatz, UMSN3 = Auslandsumsatz
    targets = {
        "tot": ("UMS002", "umsatz"),
        "dom": ("UMSN2", "inlandsumsatz"),
        "for": ("UMSN3", "auslandsumsatz"),
    }

    ums_map = {}
    for key, (code_exact, lbl_exact) in targets.items():
        sub = pd.DataFrame()
        if v_code_col:
            sub = df[df[v_code_col].astype(str).str.strip().str.upper() == code_exact].copy()
        if sub.empty and v_lbl_col:
            sub = df[df[v_lbl_col].astype(str).str.strip().str.lower() == lbl_exact].copy()
        if sub.empty:
            raise RuntimeError(f"Merkmal {code_exact} ({lbl_exact}) nicht in 42111-0004 gefunden.")

        # Einheit pruefen (Standard in 42111-0004 ist Tsd. EUR -> Faktor 1e-6 fuer Mrd. EUR)
        unit_scale = 1e-6
        if "value_unit" in sub.columns:
            u_str = " ".join(sub["value_unit"].dropna().astype(str).unique()).lower()
            if "mill" in u_str:
                unit_scale = 1e-3
            elif "mrd" in u_str:
                unit_scale = 1.0

        piv = sub.pivot_table(index="ZEIT", columns="WZ", values="NUM", aggfunc="first").sort_index()
        ums_map[key] = piv * unit_scale

    return ums_map


def get_destatis_bip_q():
    try:
        df = _destatis_ffcsv("81000-0002", startyear="2018")
        if df.empty:
            return pd.Series(dtype=float)
        code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
        df["_CODES"] = df.loc[:, code_cols].fillna("").astype(str).apply(
            lambda r: {x.strip() for x in r if x.strip()}, axis=1
        )
        req = {"WERTORG", "VGR014", "VGRPKM"}
        sub = df[df["_CODES"].apply(lambda s: req.issubset(s))].copy()
        if sub.empty:
            lbl_cols = [c for c in df.columns if "label" in c.lower()]
            lbl_txt = df.loc[:, lbl_cols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
            mask = (
                lbl_txt.str.contains("originalwerte")
                & lbl_txt.str.contains("preisbereinigt")
                & lbl_txt.str.contains("bruttoinlandsprodukt")
            )
            sub = df[mask].copy()
        sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
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
    except Exception as exc:
        print(f"[WARN] BIP-Abruf 81000-0002 fehlgeschlagen: {exc}")
        return pd.Series(dtype=float)


def extract_turnover_series(ums_map, wz_list):
    out = {}
    for key in ("tot", "dom", "for"):
        piv = ums_map[key]
        missing = [w for w in wz_list if w not in piv.columns]
        if missing:
            raise KeyError(f"Fehlende WZ-Codes {missing} in {key}. Verfuegbare: {sorted(piv.columns.tolist())}")
        s = piv[wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
        out[key] = s

    common_idx = out["tot"].index.intersection(out["dom"].index).intersection(out["for"].index).sort_values()
    for key in ("tot", "dom", "for"):
        out[key] = out[key].loc[common_idx]

    last_ym = common_idx[-1]
    t_last = float(out["tot"].loc[last_ym])
    d_last = float(out["dom"].loc[last_ym])
    f_last = float(out["for"].loc[last_ym])
    if t_last > 0:
        out["dom_share"] = round(d_last / t_last * 100.0, 1)
        out["for_share"] = round(f_last / t_last * 100.0, 1)
    else:
        out["dom_share"] = 0.0
        out["for_share"] = 0.0
    out["last_ym"] = last_ym
    return out


def get_bip_neg_intervals(months, bip_q):
    q_months = {"Q1": ("01", "02", "03"), "Q2": ("04", "05", "06"), "Q3": ("07", "08", "09"), "Q4": ("10", "11", "12")}
    neg_set = set()
    for qk, val in bip_q.items():
        if val < 0 and "-Q" in qk:
            yr = qk[:4]
            qp = qk[-2:]
            for mm in q_months.get(qp, ()):
                neg_set.add(f"{yr}-{mm}")

    intervals = []
    start_m = None
    prev_m = None
    for ym in months:
        if ym in neg_set:
            if start_m is None:
                start_m = ym
            prev_m = ym
        else:
            if start_m is not None:
                intervals.append((start_m, prev_m))
                start_m = None
                prev_m = None
    if start_m is not None:
        intervals.append((start_m, prev_m))
    return intervals


def add_recession_shading_mpl(ax, months, bip_intervals, t):
    has_svr = False
    for s_ym, e_ym in SVR_PHASES:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            ax.axvspan(min(idxs) - 0.5, max(idxs) + 0.5, color="#CBD5E1", alpha=0.38, zorder=0)
            has_svr = True

    has_bip = False
    for s_ym, e_ym in bip_intervals:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            ax.axvspan(min(idxs) - 0.5, max(idxs) + 0.5, color="#93C5FD", alpha=0.30, zorder=0)
            has_bip = True

    patches = []
    if has_svr:
        patches.append(mpatches.Patch(color="#CBD5E1", alpha=0.55, label=t["leg_svr"]))
    if has_bip:
        patches.append(mpatches.Patch(color="#93C5FD", alpha=0.45, label=t["leg_bip"]))
    return patches


def add_recession_shading_plotly(fig_p, months, bip_intervals, t):
    shapes = []
    has_svr = False
    for s_ym, e_ym in SVR_PHASES:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=min(idxs) - 0.5,
                    x1=max(idxs) + 0.5,
                    y0=0,
                    y1=1,
                    fillcolor="rgba(203, 213, 225, 0.38)",
                    line=dict(width=0),
                    layer="below",
                )
            )
            has_svr = True

    has_bip = False
    for s_ym, e_ym in bip_intervals:
        idxs = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
        if idxs:
            shapes.append(
                dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=min(idxs) - 0.5,
                    x1=max(idxs) + 0.5,
                    y0=0,
                    y1=1,
                    fillcolor="rgba(147, 197, 253, 0.30)",
                    line=dict(width=0),
                    layer="below",
                )
            )
            has_bip = True

    if shapes:
        fig_p.update_layout(shapes=shapes)
    if has_svr:
        fig_p.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, symbol="square", color="rgba(203, 213, 225, 0.85)"),
                name=t["leg_svr"],
                showlegend=True,
                hoverinfo="skip",
            )
        )
    if has_bip:
        fig_p.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, symbol="square", color="rgba(147, 197, 253, 0.75)"),
                name=t["leg_bip"],
                showlegend=True,
                hoverinfo="skip",
            )
        )


def style_mpl_ax(fig, ax, title, subtitle, ymax, ystep, xlabel_text):
    fig.suptitle(title, x=0.08, y=0.965, ha="left", fontsize=11.5, fontweight="bold", color="#0F172A")
    fig.text(0.08, 0.922, subtitle, ha="left", fontsize=8.4, color="#334155")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(0, ymax)
    ax.set_yticks(np.arange(0, ymax + ystep * 0.5, ystep))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.text(0.5, -0.29, xlabel_text, transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")


def draw_year_groups(ax, months, m_names):
    ticks, labels = [], []
    for i, ym in enumerate(months):
        m = int(ym[5:7])
        if m in (1, 4, 7, 10):
            ticks.append(i)
            labels.append(m_names[m - 1])
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    years = sorted({ym[:4] for ym in months})
    for y in years:
        idxs = [i for i, ym in enumerate(months) if ym.startswith(y)]
        if idxs:
            mid = (min(idxs) + max(idxs)) / 2.0
            ax.text(mid, -0.22, y, transform=ax.get_xaxis_transform(), ha="center", fontsize=8.2, color="#475569")


def save_plotly_chart(fig_p, title_p, sub_p, src_text, now_str, fname_p, sfx, height_p=500, top_m=135):
    fig_p.update_layout(
        title=dict(
            text=f"<b>{title_p}</b><br><span style='font-size:11.5px;color:#334155;font-weight:normal'>{sub_p}</span>",
            x=0.02,
            y=0.97,
            yanchor="top",
            font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=10.0, color="#1E293B"),
        ),
        margin=dict(l=48, r=20, t=top_m, b=88),
        height=height_p,
        annotations=[
            dict(
                text=f"{src_text}{now_str}",
                x=0.0,
                y=-0.27,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.8, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.27,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.2, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    all_x = list(fig_p.data[0].x) if fig_p.data and fig_p.data[0].x is not None else []
    t_vals = [x for i, x in enumerate(all_x) if i % 3 == 0]
    fig_p.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        showgrid=False,
        linecolor="#94A3B8",
        tickmode="array",
        tickvals=t_vals,
        ticktext=t_vals,
        tickfont=dict(size=10.0, color="#475569"),
    )
    fig_p.update_yaxes(
        fixedrange=True,
        rangemode="tozero",
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#64748B",
        zerolinewidth=1.1,
        tickfont=dict(size=10.0, color="#475569"),
    )
    out_path = f"{OUT_DIR}/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_single_sector_chart(lang, fname, title_key, sub_key, labels_key, data_dict, bip_intervals, ymax, ystep):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(data_dict["tot"].index)
    x = np.arange(len(months))
    y_tot = [float(data_dict["tot"].loc[ym]) for ym in months]
    y_dom = [float(data_dict["dom"].loc[ym]) for ym in months]
    y_for = [float(data_dict["for"].loc[ym]) for ym in months]

    end_lbl = ym_label(data_dict["last_ym"], lang)
    f_sh = fmt_num(data_dict["for_share"], use_c, 1)
    d_sh = fmt_num(data_dict["dom_share"], use_c, 1)
    subtitle = t[sub_key].format(end_lbl=end_lbl, f_sh=f_sh, d_sh=d_sh)
    l_tot, l_dom, l_for = t[labels_key]

    fig, ax = plt.subplots(figsize=(8.2, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.08, right=0.96, top=0.77, bottom=0.24)
    style_mpl_ax(fig, ax, t[title_key], subtitle, ymax, ystep, t["x_m"])
    shade_patches = add_recession_shading_mpl(ax, months, bip_intervals, t)

    p1 = ax.plot(x, y_tot, color="#1B3A6B", lw=2.3, label=l_tot, zorder=4)
    p2 = ax.plot(x, y_dom, color="#059669", lw=2.0, label=l_dom, zorder=3)
    p3 = ax.plot(x, y_for, color="#D97706", lw=2.0, label=l_for, zorder=3)

    draw_year_groups(ax, months, t["m"])
    handles = p1 + p2 + p3 + shade_patches
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=3, frameon=False, fontsize=7.4)
    fig.text(0.08, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fmt_arr = lambda seq: [fmt_num(v, use_c, 1) for v in seq]
    fp = go.Figure()
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_tot],
            customdata=fmt_arr(y_tot),
            name=l_tot,
            mode="lines",
            line=dict(color="#1B3A6B", width=2.3),
            hovertemplate=f"{l_tot}: <b>%{{customdata}} Mrd. €</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_dom],
            customdata=fmt_arr(y_dom),
            name=l_dom,
            mode="lines",
            line=dict(color="#059669", width=2.0),
            hovertemplate=f"{l_dom}: <b>%{{customdata}} Mrd. €</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_for],
            customdata=fmt_arr(y_for),
            name=l_for,
            mode="lines",
            line=dict(color="#D97706", width=2.0),
            hovertemplate=f"{l_for}: <b>%{{customdata}} Mrd. €</b><extra></extra>",
        )
    )
    add_recession_shading_plotly(fp, months, bip_intervals, t)
    save_plotly_chart(fp, t[title_key], subtitle, t["src"], now_str, fname, t["sfx"], height_p=490, top_m=130)


def build_dual_sector_chart(lang, fname, title_key, sub_key, labels_key, d_narrow, d_broad, bip_intervals, ymax, ystep):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(d_narrow["tot"].index.intersection(d_broad["tot"].index).sort_values())
    x = np.arange(len(months))

    y1_tot = [float(d_narrow["tot"].loc[ym]) for ym in months]
    y1_dom = [float(d_narrow["dom"].loc[ym]) for ym in months]
    y1_for = [float(d_narrow["for"].loc[ym]) for ym in months]

    y2_tot = [float(d_broad["tot"].loc[ym]) for ym in months]
    y2_dom = [float(d_broad["dom"].loc[ym]) for ym in months]
    y2_for = [float(d_broad["for"].loc[ym]) for ym in months]

    end_lbl = ym_label(months[-1], lang)
    subtitle = t[sub_key].format(
        end_lbl=end_lbl,
        f1_sh=fmt_num(d_narrow["for_share"], use_c, 1),
        d1_sh=fmt_num(d_narrow["dom_share"], use_c, 1),
        f2_sh=fmt_num(d_broad["for_share"], use_c, 1),
        d2_sh=fmt_num(d_broad["dom_share"], use_c, 1),
    )
    l1_tot, l1_dom, l1_for, l2_tot, l2_dom, l2_for = t[labels_key]

    fig, ax = plt.subplots(figsize=(8.2, 5.7), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.08, right=0.96, top=0.73, bottom=0.23)
    style_mpl_ax(fig, ax, t[title_key], subtitle, ymax, ystep, t["x_m"])
    shade_patches = add_recession_shading_mpl(ax, months, bip_intervals, t)

    p1 = ax.plot(x, y1_tot, color="#1B3A6B", lw=2.1, ls="--", label=l1_tot, zorder=4)
    p2 = ax.plot(x, y1_dom, color="#059669", lw=1.8, ls="--", label=l1_dom, zorder=3)
    p3 = ax.plot(x, y1_for, color="#D97706", lw=1.8, ls="--", label=l1_for, zorder=3)

    p4 = ax.plot(x, y2_tot, color="#1B3A6B", lw=2.3, ls="-", label=l2_tot, zorder=5)
    p5 = ax.plot(x, y2_dom, color="#059669", lw=2.0, ls="-", label=l2_dom, zorder=4)
    p6 = ax.plot(x, y2_for, color="#D97706", lw=2.0, ls="-", label=l2_for, zorder=4)

    draw_year_groups(ax, months, t["m"])
    handles = p1 + p2 + p3 + p4 + p5 + p6 + shade_patches
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=3, frameon=False, fontsize=6.9)
    fig.text(0.08, 0.015, f"{t['src']}{now_str}", fontsize=6.9, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=7.8, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fmt_arr = lambda seq: [fmt_num(v, use_c, 1) for v in seq]
    fp = go.Figure()
    traces = [
        (y1_tot, l1_tot, "#1B3A6B", 2.0, "dash"),
        (y1_dom, l1_dom, "#059669", 1.8, "dash"),
        (y1_for, l1_for, "#D97706", 1.8, "dash"),
        (y2_tot, l2_tot, "#1B3A6B", 2.3, "solid"),
        (y2_dom, l2_dom, "#059669", 2.0, "solid"),
        (y2_for, l2_for, "#D97706", 2.0, "solid"),
    ]
    for y_seq, lbl, col, wid, dsh in traces:
        fp.add_trace(
            go.Scatter(
                x=months,
                y=[round(v, 2) for v in y_seq],
                customdata=fmt_arr(y_seq),
                name=lbl,
                mode="lines",
                line=dict(color=col, width=wid, dash=dsh),
                hovertemplate=f"{lbl}: <b>%{{customdata}} Mrd. €</b><extra></extra>",
            )
        )
    add_recession_shading_plotly(fp, months, bip_intervals, t)
    save_plotly_chart(fp, t[title_key], subtitle, t["src"], now_str, fname, t["sfx"], height_p=525, top_m=155)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    ums_map = load_destatis_turnover()

    s_gesamt = extract_turnover_series(ums_map, WZ_C_DIVISIONS)
    s_autos = extract_turnover_series(ums_map, ["WZ08-29"])
    s_stahl_24 = extract_turnover_series(ums_map, ["WZ08-24"])
    s_stahl_2425 = extract_turnover_series(ums_map, ["WZ08-24", "WZ08-25"])
    s_chemie_20 = extract_turnover_series(ums_map, ["WZ08-20"])
    s_chemie_2021 = extract_turnover_series(ums_map, ["WZ08-20", "WZ08-21"])

    print(
        f"[RESULT] Verarbeitendes Gewerbe bis {s_gesamt['last_ym']}: "
        f"Gesamt={s_gesamt['tot'].iloc[-1]:.2f} Mrd. EUR | "
        f"Inland={s_gesamt['dom_share']:.1f} % | Ausland={s_gesamt['for_share']:.1f} %"
    )

    bip_q = get_destatis_bip_q()
    months_ref = list(s_gesamt["tot"].index)
    bip_intervals = get_bip_neg_intervals(months_ref, bip_q)

    ymax_ges = int(np.ceil(max(s_gesamt["tot"].max(), 200.0) / 25.0) * 25)
    ymax_aut = int(np.ceil(max(s_autos["tot"].max(), 50.0) / 10.0) * 10)
    ymax_sta = int(np.ceil(max(s_stahl_2425["tot"].max(), 25.0) / 5.0) * 5)
    ymax_che = int(np.ceil(max(s_chemie_2021["tot"].max(), 25.0) / 5.0) * 5)

    for lang in ("de", "en"):
        build_single_sector_chart(
            lang, "umsatz_gesamt", "g1_t", "g1_sub", "g1_l", s_gesamt, bip_intervals, ymax_ges, 25
        )
        build_single_sector_chart(
            lang, "umsatz_autos", "g2_t", "g2_sub", "g2_l", s_autos, bip_intervals, ymax_aut, 10
        )
        build_dual_sector_chart(
            lang, "umsatz_stahl", "g3_t", "g3_sub", "g3_l", s_stahl_24, s_stahl_2425, bip_intervals, ymax_sta, 5
        )
        build_dual_sector_chart(
            lang, "umsatz_chemie", "g4_t", "g4_sub", "g4_l", s_chemie_20, s_chemie_2021, bip_intervals, ymax_che, 5
        )


if __name__ == "__main__":
    main()

