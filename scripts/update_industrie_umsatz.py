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

import requests
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import plotly.graph_objects as go


G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"
D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()

OUT_DIR = "static/umsatz-industrie"
os.makedirs(OUT_DIR, exist_ok=True)

# Offizielle Abgrenzung Abschnitt C (Verarbeitendes Gewerbe) nach WZ 2008: Abteilungen 10 bis 33
WZ_C_DIVISIONS = [f"WZ08-{d:02d}" for d in range(10, 34)]

# SVR / Deutsche Bundesbank Rezessions- und Schwächephasen ab 2019
SVR_PHASES = [
    ("2020-02", "2020-05"),
    ("2022-10", "2023-03"),
    ("2023-10", "2024-12"),
]

# Quartale mit realem BIP < 0 % gg. Vj. (Destatis VGR)
NEG_BIP_QUARTERS = [
    ("2020-01", "2020-12"),
    ("2023-01", "2023-12"),
    ("2024-04", "2024-12"),
]

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "x_m": "Berichtsmonat",
        "y_mrd": "Mrd. Euro",
        "src": "Quelle: Statistisches Bundesamt (GENESIS-Online, Tabelle 42111-0004), eigene Berechnungen | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "tot_lbl": "Umsatz insgesamt",
        "dom_lbl": "Umsatz Inland",
        "for_lbl": "Umsatz Ausland",
        "share_fmt": "Aktuellster Monat ({ym}): Anteil Ausland {for_pct} % | Anteil Inland {dom_pct} %",
        "share_dual_fmt": (
            "Aktuellster Monat ({ym}): {lbl_a}: Ausland {for_a} % / Inland {dom_a} % | "
            "{lbl_b}: Ausland {for_b} % / Inland {dom_b} %"
        ),
        "g1_t": "Verarbeitendes Gewerbe insgesamt (WZ08-C) – Umsatz",
        "g2_t": "Kraftwagen und Kraftwagenteile (WZ08-29) – Umsatz",
        "g3_t": "Metallerzeugung (WZ08-24) vs. inkl. Metallerzeugnisse (WZ08-24+25) – Umsatz",
        "g3_a": "Metallerzeugung (WZ08-24)",
        "g3_b": "inkl. Metallerzeugnisse (WZ08-24+25)",
        "g4_t": "Chemie ohne Pharma (WZ08-20) vs. Chemie inkl. Pharma (WZ08-20+21) – Umsatz",
        "g4_a": "Chemie ohne Pharma (WZ08-20)",
        "g4_b": "Chemie inkl. Pharma (WZ08-20+21)",
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "x_m": "Reporting month",
        "y_mrd": "EUR billion",
        "src": "Source: Federal Statistical Office (GENESIS-Online, Table 42111-0004), own calculations | As of: ",
        "leg_svr": "Recession/weakness (GCEE/Bundesbank)",
        "leg_bip": "Real GDP < 0% YoY",
        "tot_lbl": "Total turnover",
        "dom_lbl": "Domestic turnover",
        "for_lbl": "Foreign turnover",
        "share_fmt": "Latest month ({ym}): Foreign share {for_pct}% | Domestic share {dom_pct}%",
        "share_dual_fmt": (
            "Latest month ({ym}): {lbl_a}: Foreign {for_a}% / Domestic {dom_a}% | "
            "{lbl_b}: Foreign {for_b}% / Domestic {dom_b}%"
        ),
        "g1_t": "Total Manufacturing (WZ08-C) – Turnover",
        "g2_t": "Motor Vehicles, Trailers and Semi-Trailers (WZ08-29) – Turnover",
        "g3_t": "Basic Metals (WZ08-24) vs. incl. Fabricated Metal Products (WZ08-24+25) – Turnover",
        "g3_a": "Basic metals (WZ08-24)",
        "g3_b": "incl. fabricated metal products (WZ08-24+25)",
        "g4_t": "Chemicals excl. Pharma (WZ08-20) vs. Chemicals incl. Pharma (WZ08-20+21) – Turnover",
        "g4_a": "Chemicals excl. pharma (WZ08-20)",
        "g4_b": "Chemicals incl. pharma (WZ08-20+21)",
    },
}


def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def normalize_wz(raw_code):
    s = str(raw_code).strip().upper()
    m = re.search(r"WZ08-([A-Z0-9]+)", s)
    if not m:
        return s
    part = m.group(1)
    if part.isdigit():
        return f"WZ08-{int(part):02d}"
    return f"WZ08-{part}"


def _destatis_ffcsv(table, startyear="2019", extra_params=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt in den GitHub Secrets.")
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
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            return pd.DataFrame()
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            txt = _unpack(
                requests.post(
                    f"{G_BASE}/resultfile",
                    headers=headers,
                    data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"},
                    timeout=90,
                )
            )
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


def load_destatis_turnover():
    df = _destatis_ffcsv("42111-0004", startyear="2019")
    if df.empty:
        raise RuntimeError("Destatis Tabelle 42111-0004 lieferte keine Daten.")

    wz_col = None
    for c in df.columns:
        if c.endswith("_code") and c not in {"statistics_code", "time_code"}:
            if df[c].astype(str).str.startswith("WZ08-").any():
                wz_col = c
                break
    if not wz_col:
        raise RuntimeError(f"Keine WZ08-Spalte in 42111-0004 gefunden. Spalten: {list(df.columns)}")

    df["WZ"] = df[wz_col].apply(normalize_wz)
    df["V"] = pd.to_numeric(df["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["V"])
    df = df[df["ZEIT"].str.match(r"^20\d{2}-\d{2}$")].copy()

    # Pruefen, ob Werte in Tsd. EUR vorliegen -> Umrechnung in Mrd. EUR (/ 1_000_000)
    unit_scale = 1e-6
    for u_col in [c for c in df.columns if "unit" in c.lower() or "einheit" in c.lower()]:
        u_txt = " ".join(df[u_col].dropna().astype(str).unique()).lower()
        if "mio" in u_txt:
            unit_scale = 1e-3
            break
        if "mrd" in u_txt:
            unit_scale = 1.0
            break

    ums_map = {}
    for u_code in ("UMS002", "UMS003", "UMS004"):
        sub = df[df["_CODES"].apply(lambda s: u_code in s)].copy()
        if sub.empty:
            raise RuntimeError(f"Merkmal {u_code} nicht in 42111-0004 gefunden.")
        sub = sub.drop_duplicates(subset=["ZEIT", "WZ"], keep="first")
        piv = sub.pivot(index="ZEIT", columns="WZ", values="V").sort_index() * unit_scale

        # Offizielles Gesamtaggregat Verarbeitendes Gewerbe (WZ08-C = Summe Abteilungen 10..33)
        avail_c = [c for c in WZ_C_DIVISIONS if c in piv.columns]
        if len(avail_c) < 20:
            raise RuntimeError(f"Zu wenige WZ08-C Abteilungen fuer {u_code}: {avail_c}")
        piv["WZ08-C"] = piv[avail_c].sum(axis=1, min_count=len(avail_c))
        ums_map[u_code] = piv

    return ums_map


def extract_turnover_series(ums_map, wz_list):
    for u_code in ("UMS002", "UMS003", "UMS004"):
        piv = ums_map[u_code]
        missing = [w for w in wz_list if w not in piv.columns]
        if missing:
            raise KeyError(f"Fehlende WZ-Codes {missing} in {u_code}. Verfuegbare: {sorted(piv.columns.tolist())}")

    tot = ums_map["UMS002"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    dom = ums_map["UMS003"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    for_ = ums_map["UMS004"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()

    common = tot.index.intersection(dom.index).intersection(for_.index).sort_values()
    common = [ym for ym in common if ym >= "2019-01"]
    return pd.DataFrame({
        "tot": tot.loc[common],
        "dom": dom.loc[common],
        "for": for_.loc[common],
    }, index=common)


def add_recession_shading_mpl(ax, months):
    if not months:
        return
    m_min, m_max = months[0], months[-1]

    def _span(intervals, color, alpha):
        for s_ym, e_ym in intervals:
            if e_ym < m_min or s_ym > m_max:
                continue
            vis = [i for i, ym in enumerate(months) if s_ym <= ym <= e_ym]
            if vis:
                ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color=color, alpha=alpha, lw=0, zorder=0)

    _span(SVR_PHASES, "#CBD5E1", 0.45)
    _span(NEG_BIP_QUARTERS, "#93C5FD", 0.35)


def add_recession_shading_plotly(fig, months):
    if not months:
        return
    m_min, m_max = months[0], months[-1]

    def _shapes(intervals, fillcolor):
        for s_ym, e_ym in intervals:
            if e_ym < m_min or s_ym > m_max:
                continue
            vis = [ym for ym in months if s_ym <= ym <= e_ym]
            if vis:
                fig.add_vrect(
                    x0=vis[0],
                    x1=vis[-1],
                    fillcolor=fillcolor,
                    line_width=0,
                    layer="below",
                )

    _shapes(SVR_PHASES, "rgba(203, 213, 225, 0.45)")
    _shapes(NEG_BIP_QUARTERS, "rgba(147, 197, 253, 0.35)")


def draw_year_groups(ax, months, m_names, step=3, year_y=-0.22):
    ticks, labels = [], []
    for i, ym in enumerate(months):
        m = int(ym[5:7])
        if step == 1 or m in (1, 4, 7, 10):
            ticks.append(i)
            labels.append(m_names[m - 1])
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    years = sorted(list({ym[:4] for ym in months}))
    for y in years:
        idxs = [i for i, ym in enumerate(months) if ym.startswith(y)]
        if idxs:
            mid = (min(idxs) + max(idxs)) / 2.0
            ax.text(mid, year_y, y, transform=ax.get_xaxis_transform(), ha="center", fontsize=8.3, color="#475569")


def save_plotly_chart(fig_p, title_p, sub_p, src_text, now_str, fname_p, sfx, height_p=490, top_m=125):
    fig_p.update_layout(
        title=dict(
            text=f"<b>{title_p}</b><br><span style='font-size:11.5px;color:#475569;font-weight:normal'>{sub_p}</span>",
            x=0.02,
            y=0.97,
            yanchor="top",
            font=dict(size=15.5, color="#0F172A", family="DejaVu Sans, sans-serif"),
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
            font=dict(size=10.2, color="#1E293B"),
        ),
        margin=dict(l=54, r=24, t=top_m, b=95),
        height=height_p,
        annotations=[
            dict(
                text=f"{src_text}{now_str}",
                x=0.0,
                y=-0.28,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.8, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.28,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.5, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    all_x = list(fig_p.data[0].x) if fig_p.data and fig_p.data[0].x is not None else []
    t_vals = [x for i, x in enumerate(all_x) if i % 6 == 0]
    fig_p.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        showgrid=False,
        linecolor="#94A3B8",
        tickmode="array",
        tickvals=t_vals,
        ticktext=t_vals,
        tickfont=dict(size=10.2, color="#475569"),
    )
    fig_p.update_yaxes(
        fixedrange=True,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#64748B",
        zerolinewidth=1.1,
        tickfont=dict(size=10.5, color="#475569"),
    )
    out_path = f"{OUT_DIR}/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_single_chart(lang, fname, title_txt, df_s, now_str):
    t = TEXTS[lang]
    use_c = t["comma"]
    months = list(df_s.index)
    x = np.arange(len(months))

    y_tot = df_s["tot"].values.astype(float)
    y_dom = df_s["dom"].values.astype(float)
    y_for = df_s["for"].values.astype(float)

    last_ym = months[-1]
    last_tot = y_tot[-1]
    for_pct = fmt_num((y_for[-1] / last_tot) * 100.0 if last_tot else 0.0, use_c, 1)
    dom_pct = fmt_num((y_dom[-1] / last_tot) * 100.0 if last_tot else 0.0, use_c, 1)
    sub_txt = t["share_fmt"].format(ym=last_ym, for_pct=for_pct, dom_pct=dom_pct)

    # Matplotlib PNG (300 dpi)
    fig, ax = plt.subplots(figsize=(8.2, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.75, bottom=0.24)
    fig.suptitle(title_txt, x=0.09, y=0.96, ha="left", fontsize=12.2, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.905, sub_txt, ha="left", fontsize=8.6, color="#334155")

    ax.set_facecolor("#F8FAFC")
    ymax = max(10.0, float(np.ceil((np.nanmax(y_tot) * 1.12) / 10.0) * 10.0))
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_mrd"], fontsize=8.4, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.6, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.9, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    add_recession_shading_mpl(ax, months)
    l1, = ax.plot(x, y_tot, color="#0F172A", lw=2.3, label=t["tot_lbl"], zorder=4)
    l2, = ax.plot(x, y_for, color="#1D4ED8", lw=2.0, label=t["for_lbl"], zorder=3)
    l3, = ax.plot(x, y_dom, color="#059669", lw=2.0, label=t["dom_lbl"], zorder=3)

    draw_year_groups(ax, months, t["m"], step=3, year_y=-0.22)
    ax.text(0.5, -0.30, t["x_m"], transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")

    p_svr = Patch(facecolor="#CBD5E1", alpha=0.55, label=t["leg_svr"])
    p_bip = Patch(facecolor="#93C5FD", alpha=0.45, label=t["leg_bip"])
    ax.legend(
        handles=[l1, l2, l3, p_svr, p_bip],
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=3,
        frameon=False,
        fontsize=7.4,
    )

    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    # Plotly HTML
    fmt_arr = lambda seq: [fmt_num(v, use_c, 2) for v in seq]
    fp = go.Figure()
    add_recession_shading_plotly(fp, months)
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), 2) for v in y_tot],
            customdata=fmt_arr(y_tot),
            name=t["tot_lbl"],
            mode="lines",
            line=dict(color="#0F172A", width=2.4),
            hovertemplate=f"{t['tot_lbl']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"
            if lang == "de"
            else f"{t['tot_lbl']}: <b>EUR %{{customdata}} bn</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), 2) for v in y_for],
            customdata=fmt_arr(y_for),
            name=t["for_lbl"],
            mode="lines",
            line=dict(color="#1D4ED8", width=2.0),
            hovertemplate=f"{t['for_lbl']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"
            if lang == "de"
            else f"{t['for_lbl']}: <b>EUR %{{customdata}} bn</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), 2) for v in y_dom],
            customdata=fmt_arr(y_dom),
            name=t["dom_lbl"],
            mode="lines",
            line=dict(color="#059669", width=2.0),
            hovertemplate=f"{t['dom_lbl']}: <b>%{{customdata}} Mrd. €</b><extra></extra>"
            if lang == "de"
            else f"{t['dom_lbl']}: <b>EUR %{{customdata}} bn</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="rgba(203, 213, 225, 0.7)", symbol="square"),
            name=t["leg_svr"],
            showlegend=True,
        )
    )
    fp.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="rgba(147, 197, 253, 0.6)", symbol="square"),
            name=t["leg_bip"],
            showlegend=True,
        )
    )
    save_plotly_chart(fp, title_txt, sub_txt, t["src"], now_str, fname, t["sfx"], height_p=490, top_m=125)


def build_dual_chart(lang, fname, title_txt, lbl_a, df_a, lbl_b, df_b, now_str):
    t = TEXTS[lang]
    use_c = t["comma"]
    months = list(df_a.index.intersection(df_b.index).sort_values())
    x = np.arange(len(months))

    ya_tot = df_a.loc[months, "tot"].values.astype(float)
    ya_for = df_a.loc[months, "for"].values.astype(float)
    ya_dom = df_a.loc[months, "dom"].values.astype(float)

    yb_tot = df_b.loc[months, "tot"].values.astype(float)
    yb_for = df_b.loc[months, "for"].values.astype(float)
    yb_dom = df_b.loc[months, "dom"].values.astype(float)

    last_ym = months[-1]
    for_a = fmt_num((ya_for[-1] / ya_tot[-1]) * 100.0 if ya_tot[-1] else 0.0, use_c, 1)
    dom_a = fmt_num((ya_dom[-1] / ya_tot[-1]) * 100.0 if ya_tot[-1] else 0.0, use_c, 1)
    for_b = fmt_num((yb_for[-1] / yb_tot[-1]) * 100.0 if yb_tot[-1] else 0.0, use_c, 1)
    dom_b = fmt_num((yb_dom[-1] / yb_tot[-1]) * 100.0 if yb_tot[-1] else 0.0, use_c, 1)
    sub_txt = t["share_dual_fmt"].format(
        ym=last_ym,
        lbl_a=lbl_a,
        for_a=for_a,
        dom_a=dom_a,
        lbl_b=lbl_b,
        for_b=for_b,
        dom_b=dom_b,
    )

    # Matplotlib PNG (300 dpi)
    fig, ax = plt.subplots(figsize=(8.4, 5.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.96, top=0.71, bottom=0.23)
    fig.suptitle(title_txt, x=0.09, y=0.96, ha="left", fontsize=11.6, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.905, sub_txt, ha="left", fontsize=7.8, color="#334155")

    ax.set_facecolor("#F8FAFC")
    ymax = max(5.0, float(np.ceil((np.nanmax(yb_tot) * 1.12) / 5.0) * 5.0))
    ax.set_ylim(0, ymax)
    ax.set_ylabel(t["y_mrd"], fontsize=8.4, color="#475569")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.6, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.9, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    add_recession_shading_mpl(ax, months)
    la1, = ax.plot(x, ya_tot, color="#0F172A", lw=2.1, label=f"{lbl_a}: {t['tot_lbl']}", zorder=4)
    la2, = ax.plot(x, ya_for, color="#1D4ED8", lw=1.8, label=f"{lbl_a}: {t['for_lbl']}", zorder=3)
    la3, = ax.plot(x, ya_dom, color="#059669", lw=1.8, label=f"{lbl_a}: {t['dom_lbl']}", zorder=3)

    lb1, = ax.plot(x, yb_tot, color="#0F172A", lw=2.0, ls="--", label=f"{lbl_b}: {t['tot_lbl']}", zorder=4)
    lb2, = ax.plot(x, yb_for, color="#1D4ED8", lw=1.7, ls="--", label=f"{lbl_b}: {t['for_lbl']}", zorder=3)
    lb3, = ax.plot(x, yb_dom, color="#059669", lw=1.7, ls="--", label=f"{lbl_b}: {t['dom_lbl']}", zorder=3)

    draw_year_groups(ax, months, t["m"], step=3, year_y=-0.22)
    ax.text(0.5, -0.30, t["x_m"], transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")

    p_svr = Patch(facecolor="#CBD5E1", alpha=0.55, label=t["leg_svr"])
    p_bip = Patch(facecolor="#93C5FD", alpha=0.45, label=t["leg_bip"])
    ax.legend(
        handles=[la1, la2, la3, lb1, lb2, lb3, p_svr, p_bip],
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=2,
        frameon=False,
        fontsize=6.9,
    )

    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=6.8, color="#64748B")
    fig.text(0.96, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    # Plotly HTML
    fmt_arr = lambda seq: [fmt_num(v, use_c, 2) for v in seq]
    unit_suffix = "Mrd. €" if lang == "de" else "EUR bn"
    fp = go.Figure()
    add_recession_shading_plotly(fp, months)

    series_specs = [
        (ya_tot, f"{lbl_a}: {t['tot_lbl']}", "#0F172A", "solid", 2.2),
        (ya_for, f"{lbl_a}: {t['for_lbl']}", "#1D4ED8", "solid", 1.9),
        (ya_dom, f"{lbl_a}: {t['dom_lbl']}", "#059669", "solid", 1.9),
        (yb_tot, f"{lbl_b}: {t['tot_lbl']}", "#0F172A", "dash", 2.1),
        (yb_for, f"{lbl_b}: {t['for_lbl']}", "#1D4ED8", "dash", 1.8),
        (yb_dom, f"{lbl_b}: {t['dom_lbl']}", "#059669", "dash", 1.8),
    ]
    for arr, name_s, col_s, dash_s, w_s in series_specs:
        fp.add_trace(
            go.Scatter(
                x=months,
                y=[round(float(v), 2) for v in arr],
                customdata=fmt_arr(arr),
                name=name_s,
                mode="lines",
                line=dict(color=col_s, width=w_s, dash=dash_s),
                hovertemplate=f"{name_s}: <b>%{{customdata}} {unit_suffix}</b><extra></extra>",
            )
        )

    fp.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="rgba(203, 213, 225, 0.7)", symbol="square"),
            name=t["leg_svr"],
            showlegend=True,
        )
    )
    fp.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="rgba(147, 197, 253, 0.6)", symbol="square"),
            name=t["leg_bip"],
            showlegend=True,
        )
    )
    save_plotly_chart(fp, title_txt, sub_txt, t["src"], now_str, fname, t["sfx"], height_p=525, top_m=155)


def main():
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    ums_map = load_destatis_turnover()

    s_gesamt = extract_turnover_series(ums_map, ["WZ08-C"])
    s_autos = extract_turnover_series(ums_map, ["WZ08-29"])
    s_stahl_24 = extract_turnover_series(ums_map, ["WZ08-24"])
    s_stahl_24_25 = extract_turnover_series(ums_map, ["WZ08-24", "WZ08-25"])
    s_chemie_20 = extract_turnover_series(ums_map, ["WZ08-20"])
    s_chemie_20_21 = extract_turnover_series(ums_map, ["WZ08-20", "WZ08-21"])

    print(
        f"[DESTATIS 42111-0004] Zeitraum {s_gesamt.index[0]} bis {s_gesamt.index[-1]} "
        f"({len(s_gesamt)} Monate) erfolgreich geladen."
    )

    for lang in ("de", "en"):
        t = TEXTS[lang]
        now_str = datetime.now().strftime(t["date_fmt"])
        build_single_chart(lang, "umsatz_gesamt", t["g1_t"], s_gesamt, now_str)
        build_single_chart(lang, "umsatz_autos", t["g2_t"], s_autos, now_str)
        build_dual_chart(lang, "umsatz_stahl", t["g3_t"], t["g3_a"], s_stahl_24, t["g3_b"], s_stahl_24_25, now_str)
        build_dual_chart(lang, "umsatz_chemie", t["g4_t"], t["g4_a"], s_chemie_20, t["g4_b"], s_chemie_20_21, now_str)

    print("[DONE] Alle 16 Grafik-Dateien (DE & EN, .png & .html) unter static/umsatz-industrie/ erzeugt.")


if __name__ == "__main__":
    main()
