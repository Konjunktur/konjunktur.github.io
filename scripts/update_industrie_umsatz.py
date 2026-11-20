import os
import io
import re
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
import plotly.graph_objects as go
from plotly.subplots import make_subplots

D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()
G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"

OUT_DIR = "static/umsatz-industrie"
os.makedirs(OUT_DIR, exist_ok=True)

TEXTS = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "x_label": "Monat / Jahr",
        "y_label": "Mrd. Euro",
        "src": "Quelle: Statistisches Bundesamt (Tabelle 42111-0004) | Stand: ",
        "share_fmt": "Aktueller Monat ({ym}): Anteil Ausland {for_pct} % | Anteil Inland {dom_pct} %",
        "share_dual_fmt": (
            "Aktueller Monat ({ym}) – {lbl1}: Ausland {for1} % / Inland {dom1} %  |  "
            "{lbl2}: Ausland {for2} % / Inland {dom2} %"
        ),
        "p1_t": "Umsatz im Verarbeitenden Gewerbe insgesamt",
        "p1_l": ("Umsatz insgesamt", "Umsatz Inland", "Umsatz Ausland"),
        "p2_t": "Umsatz: Kraftwagen und Kraftwagenteile (WZ08-29)",
        "p2_l": ("Umsatz insgesamt", "Umsatz Inland", "Umsatz Ausland"),
        "p3_t": "Umsatz: Metallerzeugung/-bearbeitung (WZ08-24) vs. inkl. Metallerzeugnisse (WZ08-24+25)",
        "p3_l": (
            "Metallerzeugung/-bearbeitung (WZ08-24): Umsatz insgesamt",
            "Metallerzeugung/-bearbeitung (WZ08-24): Umsatz Inland",
            "Metallerzeugung/-bearbeitung (WZ08-24): Umsatz Ausland",
            "inkl. Metallerzeugnisse (WZ08-24+25): Umsatz insgesamt",
            "inkl. Metallerzeugnisse (WZ08-24+25): Umsatz Inland",
            "inkl. Metallerzeugnisse (WZ08-24+25): Umsatz Ausland",
        ),
        "p3_short": ("WZ08-24", "WZ08-24+25"),
        "p4_t": "Umsatz: Chemie ohne Pharma (WZ08-20) vs. Chemie inkl. Pharma (WZ08-20+21)",
        "p4_l": (
            "Chemie ohne Pharma (WZ08-20): Umsatz insgesamt",
            "Chemie ohne Pharma (WZ08-20): Umsatz Inland",
            "Chemie ohne Pharma (WZ08-20): Umsatz Ausland",
            "Chemie inkl. Pharma (WZ08-20+21): Umsatz insgesamt",
            "Chemie inkl. Pharma (WZ08-20+21): Umsatz Inland",
            "Chemie inkl. Pharma (WZ08-20+21): Umsatz Ausland",
        ),
        "p4_short": ("WZ08-20", "WZ08-20+21"),
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "x_label": "Month / Year",
        "y_label": "EUR billion",
        "src": "Source: Federal Statistical Office (Table 42111-0004) | As of: ",
        "share_fmt": "Latest month ({ym}): Foreign share {for_pct}% | Domestic share {dom_pct}%",
        "share_dual_fmt": (
            "Latest month ({ym}) – {lbl1}: Foreign {for1}% / Domestic {dom1}%  |  "
            "{lbl2}: Foreign {for2}% / Domestic {dom2}%"
        ),
        "p1_t": "Turnover in Manufacturing Total",
        "p1_l": ("Total turnover", "Domestic turnover", "Foreign turnover"),
        "p2_t": "Turnover: Motor Vehicles, Trailers and Semi-Trailers (WZ08-29)",
        "p2_l": ("Total turnover", "Domestic turnover", "Foreign turnover"),
        "p3_t": "Turnover: Basic Metals (WZ08-24) vs. incl. Fabricated Metal Products (WZ08-24+25)",
        "p3_l": (
            "Basic metals (WZ08-24): Total turnover",
            "Basic metals (WZ08-24): Domestic turnover",
            "Basic metals (WZ08-24): Foreign turnover",
            "incl. fabricated metal products (WZ08-24+25): Total turnover",
            "incl. fabricated metal products (WZ08-24+25): Domestic turnover",
            "incl. fabricated metal products (WZ08-24+25): Foreign turnover",
        ),
        "p3_short": ("WZ08-24", "WZ08-24+25"),
        "p4_t": "Turnover: Chemicals excl. Pharmaceuticals (WZ08-20) vs. incl. Pharmaceuticals (WZ08-20+21)",
        "p4_l": (
            "Chemicals excl. pharma (WZ08-20): Total turnover",
            "Chemicals excl. pharma (WZ08-20): Domestic turnover",
            "Chemicals excl. pharma (WZ08-20): Foreign turnover",
            "Chemicals incl. pharma (WZ08-20+21): Total turnover",
            "Chemicals incl. pharma (WZ08-20+21): Domestic turnover",
            "Chemicals incl. pharma (WZ08-20+21): Foreign turnover",
        ),
        "p4_short": ("WZ08-20", "WZ08-20+21"),
    },
}


def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def normalize_wz(code_str):
    s = str(code_str).strip().upper()
    m = re.search(r"WZ08-([A-Z0-9]+)", s)
    if not m:
        return ""
    part = m.group(1)
    if part.isdigit() and len(part) == 3 and part.startswith("0"):
        part = part[1:]
    return f"WZ08-{part}"


def _destatis_ffcsv(table, startyear="2019", extra_params=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlen in den Environment-Variablen.")
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

    wz_series = pd.Series("", index=df.index)
    for c in df.columns:
        if c in (t_col, v_col, "ZEIT", "WERT", "_CODES"):
            continue
        normed = df[c].fillna("").astype(str).map(normalize_wz)
        if normed.ne("").any():
            wz_series = wz_series.where(wz_series.ne(""), normed)
    df["WZ"] = wz_series
    return df


def load_destatis_turnover():
    # Tabelle 42111-0004 enthält sowohl WZ08-C als auch die 2-Steller (im GENESIS-Format mit führender Null: WZ08-029 usw.)
    keys_padded = "WZ08-C,WZ08-029,WZ08-024,WZ08-025,WZ08-020,WZ08-021"
    df = _destatis_ffcsv(
        "42111-0004",
        startyear="2019",
        extra_params={"classifyingvariable1": "WZ08", "classifyingkey1": keys_padded},
    )
    if df.empty:
        raise RuntimeError("Destatis Tabelle 42111-0004 lieferte keine Daten.")

    # Falls ein Teil der 2-Steller ohne führende Null geliefert wird, gezielt ergänzen
    needed = {"WZ08-C", "WZ08-29", "WZ08-24", "WZ08-25", "WZ08-20", "WZ08-21"}
    found = set(df["WZ"].unique()) - {""}
    if not needed.issubset(found):
        df_alt = _destatis_ffcsv(
            "42111-0004",
            startyear="2019",
            extra_params={"classifyingvariable1": "WZ08", "classifyingkey1": "WZ08-C,WZ08-29,WZ08-24,WZ08-25,WZ08-20,WZ08-21"},
        )
        if not df_alt.empty:
            df = pd.concat([df, df_alt], ignore_index=True)

    df = df[df["WZ"].isin(needed)].copy()
    df["V"] = pd.to_numeric(df["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["V"]).copy()
    df = df[df["ZEIT"].str.match(r"^20\d{2}-\d{2}$")].copy()

    # Nur Originalwerte (falls Saison-/Kalenderbereinigung mitgeliefert wird)
    has_wertorg = df["_CODES"].apply(lambda s: "WERTORG" in s)
    if has_wertorg.any():
        df = df[has_wertorg].copy()

    # Einheit prüfen (Tsd. EUR -> Mrd. EUR)
    unit_scale = 1e-6
    unit_cols = [c for c in df.columns if "unit" in c.lower() or "einheit" in c.lower()]
    if unit_cols:
        u_txt = " ".join(df[unit_cols[0]].dropna().astype(str).unique()).lower()
        if "mill" in u_txt or "mio" in u_txt:
            unit_scale = 1e-3
        elif "mrd" in u_txt or "milliarde" in u_txt:
            unit_scale = 1.0

    df["V_MRD"] = df["V"] * unit_scale

    # Umsatzmerkmale zuordnen (UMS002=Gesamt, UMS003=Inland, UMS004=Ausland)
    ums_map = {}
    for code_u in ("UMS002", "UMS003", "UMS004"):
        sub = df[df["_CODES"].apply(lambda s: code_u in s)].copy()
        sub = sub.drop_duplicates(subset=["ZEIT", "WZ"], keep="first")
        if not sub.empty:
            ums_map[code_u] = sub.pivot(index="ZEIT", columns="WZ", values="V_MRD").sort_index()

    return ums_map


def extract_turnover_series(ums_map, wz_list):
    for code_u in ("UMS002", "UMS003", "UMS004"):
        if code_u not in ums_map:
            raise KeyError(f"Umsatzmerkmal {code_u} fehlt in Destatis 42111-0004.")
        piv = ums_map[code_u]
        missing = [w for w in wz_list if w not in piv.columns]
        if missing:
            raise KeyError(f"Fehlende WZ-Codes {missing}. Verfügbare WZ-Codes: {sorted(piv.columns.tolist())}")

    tot = ums_map["UMS002"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    dom = ums_map["UMS003"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    for_s = ums_map["UMS004"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()

    common = tot.index.intersection(dom.index).intersection(for_s.index).sort_values()
    if common.empty:
        raise KeyError(f"Keine gemeinsamen Monate für {wz_list}.")
    tot = tot.loc[common]
    dom = dom.loc[common]
    for_s = for_s.loc[common]

    # Prozentuale Anteile am Gesamtumsatz
    tot_safe = tot.replace(0, np.nan)
    for_share = (for_s / tot_safe) * 100.0
    dom_share = (dom / tot_safe) * 100.0

    return {
        "months": list(common),
        "tot": tot,
        "dom": dom,
        "for": for_s,
        "for_share": for_share,
        "dom_share": dom_share,
    }


def draw_year_groups(ax, months, m_names, step=3, year_y=-0.24):
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


def style_ax(fig, ax, title, subtitle, ymin, ymax, yticks, xlabel_text, ylabel_text):
    fig.suptitle(title, x=0.09, y=0.965, ha="left", fontsize=11.8, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, subtitle, ha="left", fontsize=8.4, color="#1E40AF", fontweight="bold")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
    ax.tick_params(axis="y", colors="#475569", labelsize=8.6, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.set_ylabel(ylabel_text, fontsize=8.2, color="#475569")
    ax.text(0.5, -0.31, xlabel_text, transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")


def save_plotly(fig_p, title_p, subtitle_p, y_title, src_text, now_str, fname_p, sfx, height_p=480, top_m=125):
    full_title = (
        f"<b>{title_p}</b><br>"
        f"<span style='font-size:12px;color:#1E40AF;font-weight:600;'>{subtitle_p}</span>"
    )
    fig_p.update_layout(
        title=dict(
            text=full_title,
            x=0.03,
            y=0.965,
            yanchor="top",
            font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(
            orientation="v",
            x=0.0,
            y=1.01,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=10.3, color="#1E293B"),
        ),
        margin=dict(l=58, r=24, t=top_m, b=95),
        height=height_p,
        annotations=[
            dict(
                text=f"{src_text}{now_str}",
                x=0.0,
                y=-0.30,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.30,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10.5, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fig_p.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=10.3, color="#475569"),
        nticks=18,
    )
    fig_p.update_yaxes(
        title_text=y_title,
        title_font=dict(size=10.5, color="#475569"),
        fixedrange=True,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#94A3B8",
        zerolinewidth=1.0,
        tickfont=dict(size=10.3, color="#475569"),
    )
    out_path = f"{OUT_DIR}/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def build_single_chart(lang, data_d, title_key, lbl_key, fname):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    fmt_arr = lambda seq: [fmt_num(v, use_c, dec=1) for v in seq]

    months = data_d["months"]
    x = np.arange(len(months))
    y_tot = [float(data_d["tot"].loc[ym]) for ym in months]
    y_dom = [float(data_d["dom"].loc[ym]) for ym in months]
    y_for = [float(data_d["for"].loc[ym]) for ym in months]
    sh_for = [float(data_d["for_share"].loc[ym]) for ym in months]
    sh_dom = [float(data_d["dom_share"].loc[ym]) for ym in months]

    last_ym = months[-1]
    sub_txt = t["share_fmt"].format(
        ym=last_ym,
        for_pct=fmt_num(sh_for[-1], use_c, dec=1),
        dom_pct=fmt_num(sh_dom[-1], use_c, dec=1),
    )

    ymax_raw = max(y_tot) * 1.12
    step_y = 50 if ymax_raw > 140 else (10 if ymax_raw > 30 else 5)
    ymax = int(np.ceil(ymax_raw / step_y) * step_y)
    yticks = range(0, ymax + step_y, step_y)

    fig, ax = plt.subplots(figsize=(8.0, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.75, bottom=0.25)
    style_ax(fig, ax, t[title_key], sub_txt, 0, ymax, yticks, t["x_label"], t["y_label"])

    l_tot, l_dom, l_for = t[lbl_key]
    ax.plot(x, y_tot, color="#0F172A", lw=2.3, label=l_tot, zorder=4)
    ax.plot(x, y_dom, color="#1D4ED8", lw=2.0, label=l_dom, zorder=3)
    ax.plot(x, y_for, color="#D97706", lw=2.0, label=l_for, zorder=3)

    draw_year_groups(ax, months, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=1, frameon=False, fontsize=7.6)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.0, color="#64748B")
    fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_tot],
            customdata=fmt_arr(y_tot),
            name=l_tot,
            mode="lines",
            line=dict(color="#0F172A", width=2.4),
            hovertemplate=f"{l_tot}: <b>%{{customdata}} {t['y_label']}</b><extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_dom],
            customdata=list(zip(fmt_arr(y_dom), fmt_arr(sh_dom))),
            name=l_dom,
            mode="lines",
            line=dict(color="#1D4ED8", width=2.1),
            hovertemplate=f"{l_dom}: <b>%{{customdata[0]}} {t['y_label']}</b> (%{{customdata[1]}} %)<extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(v, 2) for v in y_for],
            customdata=list(zip(fmt_arr(y_for), fmt_arr(sh_for))),
            name=l_for,
            mode="lines",
            line=dict(color="#D97706", width=2.1),
            hovertemplate=f"{l_for}: <b>%{{customdata[0]}} {t['y_label']}</b> (%{{customdata[1]}} %)<extra></extra>",
        )
    )
    save_plotly(fp, t[title_key], sub_txt, t["y_label"], t["src"], now_str, fname, t["sfx"], height_p=485, top_m=135)


def build_dual_chart(lang, data_1, data_2, title_key, lbl_key, short_key, fname):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    fmt_arr = lambda seq: [fmt_num(v, use_c, dec=1) for v in seq]

    months = sorted(list(set(data_1["months"]).intersection(set(data_2["months"]))))
    x = np.arange(len(months))

    y1_tot = [float(data_1["tot"].loc[ym]) for ym in months]
    y1_dom = [float(data_1["dom"].loc[ym]) for ym in months]
    y1_for = [float(data_1["for"].loc[ym]) for ym in months]
    s1_for = [float(data_1["for_share"].loc[ym]) for ym in months]
    s1_dom = [float(data_1["dom_share"].loc[ym]) for ym in months]

    y2_tot = [float(data_2["tot"].loc[ym]) for ym in months]
    y2_dom = [float(data_2["dom"].loc[ym]) for ym in months]
    y2_for = [float(data_2["for"].loc[ym]) for ym in months]
    s2_for = [float(data_2["for_share"].loc[ym]) for ym in months]
    s2_dom = [float(data_2["dom_share"].loc[ym]) for ym in months]

    lbl1, lbl2 = t[short_key]
    sub_txt = t["share_dual_fmt"].format(
        ym=months[-1],
        lbl1=lbl1,
        for1=fmt_num(s1_for[-1], use_c, dec=1),
        dom1=fmt_num(s1_dom[-1], use_c, dec=1),
        lbl2=lbl2,
        for2=fmt_num(s2_for[-1], use_c, dec=1),
        dom2=fmt_num(s2_dom[-1], use_c, dec=1),
    )

    ymax_raw = max(max(y1_tot), max(y2_tot)) * 1.12
    step_y = 5 if ymax_raw > 18 else 2
    ymax = int(np.ceil(ymax_raw / step_y) * step_y)
    yticks = range(0, ymax + step_y, step_y)

    fig, ax = plt.subplots(figsize=(8.0, 5.9), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.69, bottom=0.24)
    style_ax(fig, ax, t[title_key], sub_txt, 0, ymax, yticks, t["x_label"], t["y_label"])

    l1_tot, l1_dom, l1_for, l2_tot, l2_dom, l2_for = t[lbl_key]
    ax.plot(x, y1_tot, color="#0F172A", lw=2.1, ls="--", label=l1_tot, zorder=3)
    ax.plot(x, y1_dom, color="#1D4ED8", lw=1.8, ls="--", label=l1_dom, zorder=3)
    ax.plot(x, y1_for, color="#D97706", lw=1.8, ls="--", label=l1_for, zorder=3)

    ax.plot(x, y2_tot, color="#0F172A", lw=2.3, ls="-", label=l2_tot, zorder=4)
    ax.plot(x, y2_dom, color="#1D4ED8", lw=2.0, ls="-", label=l2_dom, zorder=4)
    ax.plot(x, y2_for, color="#D97706", lw=2.0, ls="-", label=l2_for, zorder=4)

    draw_year_groups(ax, months, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=1, frameon=False, fontsize=6.7)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.0, color="#64748B")
    fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    traces = [
        (y1_tot, None, l1_tot, "#0F172A", 2.0, "dash"),
        (y1_dom, s1_dom, l1_dom, "#1D4ED8", 1.8, "dash"),
        (y1_for, s1_for, l1_for, "#D97706", 1.8, "dash"),
        (y2_tot, None, l2_tot, "#0F172A", 2.3, "solid"),
        (y2_dom, s2_dom, l2_dom, "#1D4ED8", 2.0, "solid"),
        (y2_for, s2_for, l2_for, "#D97706", 2.0, "solid"),
    ]
    for vals, sh_arr, nm, col, wd, dsh in traces:
        if sh_arr is None:
            fp.add_trace(
                go.Scatter(
                    x=months,
                    y=[round(v, 2) for v in vals],
                    customdata=fmt_arr(vals),
                    name=nm,
                    mode="lines",
                    line=dict(color=col, width=wd, dash=dsh),
                    hovertemplate=f"{nm}: <b>%{{customdata}} {t['y_label']}</b><extra></extra>",
                )
            )
        else:
            fp.add_trace(
                go.Scatter(
                    x=months,
                    y=[round(v, 2) for v in vals],
                    customdata=list(zip(fmt_arr(vals), fmt_arr(sh_arr))),
                    name=nm,
                    mode="lines",
                    line=dict(color=col, width=wd, dash=dsh),
                    hovertemplate=f"{nm}: <b>%{{customdata[0]}} {t['y_label']}</b> (%{{customdata[1]}} %)<extra></extra>",
                )
            )
    save_plotly(fp, t[title_key], sub_txt, t["y_label"], t["src"], now_str, fname, t["sfx"], height_p=560, top_m=195)


def main():
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    ums_map = load_destatis_turnover()

    series_dict = {
        "umsatz_gesamt": extract_turnover_series(ums_map, ["WZ08-C"]),
        "umsatz_autos": extract_turnover_series(ums_map, ["WZ08-29"]),
        "umsatz_stahl_24": extract_turnover_series(ums_map, ["WZ08-24"]),
        "umsatz_stahl_24_25": extract_turnover_series(ums_map, ["WZ08-24", "WZ08-25"]),
        "umsatz_chemie_20": extract_turnover_series(ums_map, ["WZ08-20"]),
        "umsatz_chemie_20_21": extract_turnover_series(ums_map, ["WZ08-20", "WZ08-21"]),
    }

    for k, d in series_dict.items():
        print(
            f"[OK] {k}: {d['months'][0]} bis {d['months'][-1]} | "
            f"Gesamt={d['tot'].iloc[-1]:.2f} Mrd. EUR | "
            f"Ausland={d['for_share'].iloc[-1]:.1f} % | Inland={d['dom_share'].iloc[-1]:.1f} %"
        )

    for lang in ("de", "en"):
        build_single_chart(lang, series_dict["umsatz_gesamt"], "p1_t", "p1_l", "umsatz_gesamt")
        build_single_chart(lang, series_dict["umsatz_autos"], "p2_t", "p2_l", "umsatz_autos")
        build_dual_chart(
            lang,
            series_dict["umsatz_stahl_24"],
            series_dict["umsatz_stahl_24_25"],
            "p3_t",
            "p3_l",
            "p3_short",
            "umsatz_stahl",
        )
        build_dual_chart(
            lang,
            series_dict["umsatz_chemie_20"],
            series_dict["umsatz_chemie_20_21"],
            "p4_t",
            "p4_l",
            "p4_short",
            "umsatz_chemie",
        )


if __name__ == "__main__":
    main()

