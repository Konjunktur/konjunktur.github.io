import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("static/spannungszahl", exist_ok=True)

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"

DE_RECESSIONS = [
    ("2008-04", "2009-06"),
    ("2012-10", "2013-03"),
    ("2020-01", "2020-06"),
    ("2022-10", "2025-12"),
]

TEXTS = {
    "de": {
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "sfx": "",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "x_m": "Berichtsmonate",
        "x_mq": "Berichtsmonate / Quartale",
        "src_ba": "Quelle: Statistisches Bundesamt (BA-Daten) | Stand: ",
        "src_ba_kug": "Quelle: Statistisches Bundesamt (BA-Daten) | Stand: ",
        "src_all": "Quelle: Statistisches Bundesamt (BA-Daten, VGR) | Stand: ",
        "rec_svr": "Rezession/Schwäche (SVR/BBK)",
        "rec_bip": "Reales BIP < 0 % gg. Vj.",
        "p1_t": "Einfache Spannungszahl (in Tsd.)",
        "p1_l": "Einfache Spannungszahl (Diff. gg. Vj., in Tsd.)",
        "p2_t": "Einfache Spannungszahl – Aktueller 13-Monats-Verlauf (in Tsd.)",
        "p2_l1": "Einfache Spannungszahl (Diff. gg. Vj., in Tsd.)",
        "p3_t": "Erweiterte Spannungszahl inkl. Kurzarbeit (in Tsd.)",
        "p3_l": "Erweiterte Spannungszahl (Diff. gg. Vj., in Tsd.)",
        "p4_t": "Erweiterte Spannungszahl – Aktueller 13-Monats-Verlauf (in Tsd.)",
        "p5_t": "Spannungszahl und reales BIP",
        "p5_yl": "Reales BIP gg. Vj. (%)",
        "p5_yr": "Spannungszahl (in Tsd.)",
        "p5_l": ("Reales BIP gg. Vj. (%)", "Einfache Spannungszahl (in Tsd.)", "Erweiterte Spannungszahl (in Tsd.)"),
    },
    "en": {
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "sfx": "_en",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "x_m": "Reporting Months",
        "x_mq": "Reporting Months / Quarters",
        "src_ba": "Source: Federal Statistical Office (BA data) | As of: ",
        "src_ba_kug": "Source: Federal Statistical Office (BA data) | As of: ",
        "src_all": "Source: Federal Statistical Office (BA data, National Accounts) | As of: ",
        "rec_svr": "Recession/Slowdown (GCEE/BBK)",
        "rec_bip": "Real GDP < 0% YoY",
        "p1_t": "Simple Economic Tension Number (in thousands)",
        "p1_l": "Simple Economic Tension Number (YoY diff., in thousands)",
        "p2_t": "Simple Economic Tension Number – Current 13-Month View (in thousands)",
        "p2_l1": "Simple Economic Tension Number (YoY diff., in thousands)",
        "p3_t": "Extended Economic Tension Number incl. Short-Time Work (in thousands)",
        "p3_l": "Extended Economic Tension Number (YoY diff., in thousands)",
        "p4_t": "Extended Economic Tension Number – Current 13-Month View (in thousands)",
        "p5_t": "Economic Tension Number and Real GDP",
        "p5_yl": "Real GDP YoY (%)",
        "p5_yr": "Economic Tension Number (in thousands)",
        "p5_l": ("Real GDP YoY (%)", "Simple Economic Tension Number (in thousands)", "Extended Economic Tension Number (in thousands)"),
    }
}

def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s

def _destatis_ffcsv(table, startyear="2005"):
    if not D_USER or not D_PASS:
        return pd.DataFrame()
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    def _unpack(resp):
        if resp.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
        return resp.text
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90)
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            return pd.DataFrame()
        raw = ""
        for _ in range(45):
            time.sleep(2.5)
            txt = _unpack(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=90))
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
    df["ZEIT"], df["WERT"] = zeit_s, df[v_col]
    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    df["_CODES"] = df.loc[:, code_cols].fillna("").astype(str).apply(lambda r: set(x.strip() for x in r if x.strip()), axis=1)
    label_cols = [c for c in df.columns if c.endswith("_label") and c not in {"statistics_label", "time_label"}]
    df["_LABELS"] = df.loc[:, label_cols].fillna("").astype(str).apply(lambda r: " | ".join(x.strip().lower() for x in r if x.strip()), axis=1)
    return df

def load_labor_market():
    s_alo = pd.Series(dtype=float)
    s_ste = pd.Series(dtype=float)
    s_kug = pd.Series(dtype=float)
    df_ba = _destatis_ffcsv("13211-0002", "2005")
    if not df_ba.empty and "2_variable_attribute_label" in df_ba.columns:
        df_ba = df_ba[df_ba["2_variable_attribute_label"].astype(str).str.strip() == "Insgesamt"].copy()
    if not df_ba.empty:
        for code_v, target_s in (("ERW007", "ste"), ("ERW006", "alo"), ("ERW064", "kug")):
            sub = df_ba[df_ba["_CODES"].apply(lambda s: code_v in s)].copy()
            sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
            sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
            if not sub.empty:
                vals = sub["V"].values
                scale = 0.001 if np.nanmedian(vals) > 20000 else 1.0
                s_new = pd.Series(vals * scale, index=sub["ZEIT"].astype(str).str.strip().values).sort_index()
                if target_s == "ste":
                    s_ste = s_new
                elif target_s == "alo":
                    s_alo = s_new
                else:
                    s_kug = s_new
    return s_ste, s_alo, s_kug

def get_destatis_bip_q():
    try:
        df = _destatis_ffcsv("81000-0002", "2005")
        if df.empty:
            return pd.Series(dtype=float)
        # 1. Strikter Code-Filter: Originalwerte (WERTORG), preisbereinigt (VGRPKM), Veränderung in % (VGR014)
        sub = df[df["_CODES"].apply(lambda s: {"WERTORG", "VGRPKM", "VGR014"}.issubset(s))].copy()
        # 2. Fallback über Code + Label, falls GENESIS in 81000-0002 leicht abweichende Attribut-Codes liefert
        if sub.empty:
            m_vgr014 = df["_CODES"].apply(lambda s: "VGR014" in s) | df["_LABELS"].str.contains("veränderung in %", na=False)
            m_org = df["_CODES"].apply(lambda s: "WERTORG" in s) | df["_LABELS"].str.contains("originalwerte", na=False)
            m_real = df["_CODES"].apply(lambda s: "VGRPKM" in s) | df["_LABELS"].str.contains("preisbereinigt", na=False)
            m_no_chain = ~df["_LABELS"].str.contains("kettenindex|je einwohner|saison|kalender", na=False)
            sub = df[m_vgr014 & m_org & m_real & m_no_chain].copy()
        if sub.empty:
            return pd.Series(dtype=float)
        sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=["V"])
        sub = sub[sub["ZEIT"].astype(str).str.match(r"^\d{4}-Q[1-4]$")].drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
        return pd.Series(sub["V"].round(1).values, index=sub["ZEIT"].astype(str).str.strip().values).sort_index()
    except Exception:
        return pd.Series(dtype=float)

def bip_q_to_bands(bip_q):
    q_months = {
        "Q1": ("01", "03"),
        "Q2": ("04", "06"),
        "Q3": ("07", "09"),
        "Q4": ("10", "12"),
    }
    neg_intervals = []
    for z, val in bip_q.sort_index().items():
        if pd.notna(val) and float(val) < 0.0 and "-Q" in str(z):
            yr, q_part = str(z).split("-Q")
            m1, m2 = q_months[f"Q{q_part}"]
            neg_intervals.append((f"{yr}-{m1}", f"{yr}-{m2}"))
    if not neg_intervals:
        return []
    merged = [neg_intervals[0]]
    for s_ym, e_ym in neg_intervals[1:]:
        prev_s, prev_e = merged[-1]
        py, pm = int(prev_e[:4]), int(prev_e[5:7])
        nxt_e = f"{py + 1:04d}-01" if pm == 12 else f"{py:04d}-{pm + 1:02d}"
        if s_ym <= nxt_e:
            merged[-1] = (prev_s, max(prev_e, e_ym))
        else:
            merged.append((s_ym, e_ym))
    return merged

def _add_rec_bands_ax(ax, months, gdp_bands):
    m_map = {ym: i for i, ym in enumerate(months)}
    for r_s, r_e in DE_RECESSIONS:
        vis = [i for ym, i in m_map.items() if r_s <= ym <= r_e]
        if vis:
            ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color="#CBD5E1", alpha=0.45, zorder=0)
    for g_s, g_e in gdp_bands:
        vis = [i for ym, i in m_map.items() if g_s <= ym <= g_e]
        if vis:
            ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color="#93C5FD", alpha=0.42, zorder=0.5)

def _add_rec_shapes_plotly(months, gdp_bands):
    m_set = set(months)
    shapes = []
    for r_s, r_e in DE_RECESSIONS:
        vis = sorted([ym for ym in m_set if r_s <= ym <= r_e])
        if vis:
            shapes.append(dict(type="rect", xref="x", yref="paper", x0=vis[0], x1=vis[-1], y0=0, y1=1, fillcolor="#CBD5E1", opacity=0.35, line_width=0, layer="below"))
    for g_s, g_e in gdp_bands:
        vis = sorted([ym for ym in m_set if g_s <= ym <= g_e])
        if vis:
            shapes.append(dict(type="rect", xref="x", yref="paper", x0=vis[0], x1=vis[-1], y0=0, y1=1, fillcolor="#93C5FD", opacity=0.32, line_width=0, layer="below"))
    return shapes

def style_sz_ax(fig, ax, title, ymin, ymax, yticks, xlabel_text, xlabel_y=-0.27):
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=12.0, fontweight="bold", color="#0F172A")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.6, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#64748B", linewidth=1.0, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.text(0.5, xlabel_y, xlabel_text, transform=ax.transAxes, ha="center", va="top", fontsize=8.1, color="#475569")

def draw_year_groups(ax, months, m_names, step=6, year_y=-0.20, show_months=True):
    ticks, labels = [], []
    if show_months:
        for i, ym in enumerate(months):
            m = int(ym[5:7])
            if step == 1 or m in (1, 7):
                ticks.append(i)
                labels.append(m_names[m - 1])
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)
    else:
        for i, ym in enumerate(months):
            if ym.endswith("-01"):
                ticks.append(i)
                labels.append(ym[:4])
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        return
    years = sorted(list({ym[:4] for ym in months}))
    for idx_y, y in enumerate(years):
        if len(years) > 12 and idx_y % 2 == 1:
            continue
        idxs = [i for i, ym in enumerate(months) if ym.startswith(y)]
        if idxs:
            mid = (min(idxs) + max(idxs)) / 2.0
            ax.text(mid, year_y, y, transform=ax.get_xaxis_transform(), ha="center", fontsize=7.8, color="#475569")

def save_sz_plotly(fig_p, title_p, src_text, now_str, fname_p, sfx, height_p=460, top_m=95, tick_step=12, shapes=None):
    fig_p.update_layout(
        title=dict(text=f"<b>{title_p}</b>", x=0.03, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.0, color="#1E293B")),
        margin=dict(l=52, r=24, t=top_m, b=95), height=height_p,
        shapes=shapes or [],
        annotations=[
            dict(text=f"{src_text}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    xaxis_kw = dict(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.0, color="#475569"))
    if tick_step > 1 and fig_p.data and fig_p.data[0].x is not None:
        all_x = list(fig_p.data[0].x)
        t_vals = [x for i, x in enumerate(all_x) if i % tick_step == 0]
        xaxis_kw.update(tickmode="array", tickvals=t_vals, ticktext=t_vals)
    fig_p.update_xaxes(**xaxis_kw)
    fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.0, color="#475569"))
    out_path = f"static/spannungszahl/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def add_legend_dummies_plotly(fig_p, t, secondary_y=False):
    kw = {"secondary_y": secondary_y} if secondary_y else {}
    fig_p.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(symbol="square", size=11, color="rgba(203,213,225,0.65)"), name=t["rec_svr"], hoverinfo="skip"), **kw)
    fig_p.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(symbol="square", size=11, color="rgba(147,197,253,0.65)"), name=t["rec_bip"], hoverinfo="skip"), **kw)

def build_charts_for_lang(lang, sz_einf, sz_erw, bip_q):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    fmt_arr = lambda seq: [fmt_num(v, use_c) for v in seq]

    months_all = [ym for ym in sz_einf.index if ym >= "2005-01"]
    if len(months_all) < 2:
        months_all = list(sz_einf.index)
    x_all = np.arange(len(months_all))
    y_einf = [float(sz_einf.loc[ym]) for ym in months_all]
    y_erw = [float(sz_erw.loc[ym]) if ym in sz_erw.index else np.nan for ym in months_all]
    gdp_bands = bip_q_to_bands(bip_q)
    shapes_all = _add_rec_shapes_plotly(months_all, gdp_bands)

    p_svr = Patch(facecolor="#CBD5E1", alpha=0.55, label=t["rec_svr"])
    p_bip_patch = Patch(facecolor="#93C5FD", alpha=0.55, label=t["rec_bip"])

    def save_fig(fig, src_text, fname):
        fig.text(0.09, 0.015, f"{src_text}{now_str}", fontsize=7.0, color="#64748B")
        fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
        plt.savefig(f"static/spannungszahl/{fname}{t['sfx']}.png", dpi=300)
        plt.close()

    # 1. Einfache Spannungszahl (Gesamtzeitraum ab 2005/2006)
    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.78, bottom=0.22)
    ymin_1 = min(-1200, int(np.floor((min(y_einf) - 300) / 300.0) * 300))
    ymax_1 = max(1200, int(np.ceil((max(y_einf) + 300) / 300.0) * 300))
    style_sz_ax(fig, ax, t["p1_t"], ymin_1, ymax_1, range(ymin_1, ymax_1 + 300, 300), t["x_m"], xlabel_y=-0.22)
    _add_rec_bands_ax(ax, months_all, gdp_bands)
    l1 = ax.plot(x_all, y_einf, color="#1B3A6B", lw=2.1, label=t["p1_l"], zorder=4)[0]
    draw_year_groups(ax, months_all, t["m"], show_months=False)
    ax.legend(handles=[l1, p_svr, p_bip_patch], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.5)
    save_fig(fig, t["src_ba"], "01_einfache_spannungszahl")

    fp1 = go.Figure()
    fp1.add_trace(go.Scatter(x=months_all, y=[round(v, 1) for v in y_einf], customdata=fmt_arr(y_einf), name=t["p1_l"], mode="lines", line=dict(color="#1B3A6B", width=2.2), hovertemplate=f"{t['p1_l']}: <b>%{{customdata}}</b><extra></extra>"))
    add_legend_dummies_plotly(fp1, t)
    save_sz_plotly(fp1, t["p1_t"], t["src_ba"], now_str, "01_einfache_spannungszahl", t["sfx"], height_p=460, top_m=105, tick_step=12, shapes=shapes_all)

    # 2. Einfache Spannungszahl (Aktueller 13-Monats-Verlauf)
    months_z = months_all[-13:]
    xz = np.arange(len(months_z))
    yz = [float(sz_einf.loc[ym]) for ym in months_z]
    shapes_z = _add_rec_shapes_plotly(months_z, gdp_bands)
    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.78, bottom=0.25)
    ymin_z = int(np.floor((min(yz) - 100) / 100.0) * 100)
    ymax_z = int(np.ceil((max(yz) + 100) / 100.0) * 100)
    style_sz_ax(fig, ax, t["p2_t"], ymin_z, ymax_z, range(ymin_z, ymax_z + 100, 100), t["x_m"], xlabel_y=-0.33)
    _add_rec_bands_ax(ax, months_z, gdp_bands)
    l2 = ax.plot(xz, yz, color="#1B3A6B", lw=2.3, marker="o", ms=3.5, label=t["p2_l1"], zorder=4)[0]
    draw_year_groups(ax, months_z, t["m"], step=1, year_y=-0.26, show_months=True)
    ax.legend(handles=[l2, p_svr, p_bip_patch], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.5)
    save_fig(fig, t["src_ba"], "02_einfache_spannungszahl_zoom")

    fp2 = go.Figure()
    fp2.add_trace(go.Scatter(x=months_z, y=[round(v, 1) for v in yz], customdata=fmt_arr(yz), name=t["p2_l1"], mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{t['p2_l1']}: <b>%{{customdata}}</b><extra></extra>"))
    add_legend_dummies_plotly(fp2, t)
    save_sz_plotly(fp2, t["p2_t"], t["src_ba"], now_str, "02_einfache_spannungszahl_zoom", t["sfx"], height_p=470, top_m=110, tick_step=1, shapes=shapes_z)

    # 3. Erweiterte Spannungszahl (Gesamtzeitraum ab 2005/2006)
    months_erw = [ym for ym in sz_erw.index if ym >= "2005-01"]
    if len(months_erw) < 2:
        months_erw = list(sz_erw.index)
    x_erw = np.arange(len(months_erw))
    y_erw_v = [float(sz_erw.loc[ym]) for ym in months_erw]
    shapes_erw = _add_rec_shapes_plotly(months_erw, gdp_bands)
    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.78, bottom=0.22)
    ymin_3 = min(-8000, int(np.floor((min(y_erw_v) - 500) / 1000.0) * 1000))
    ymax_3 = max(4000, int(np.ceil((max(y_erw_v) + 500) / 1000.0) * 1000))
    style_sz_ax(fig, ax, t["p3_t"], ymin_3, ymax_3, range(ymin_3, ymax_3 + 1000, 1000), t["x_m"], xlabel_y=-0.22)
    _add_rec_bands_ax(ax, months_erw, gdp_bands)
    l3 = ax.plot(x_erw, y_erw_v, color="#D97706", lw=2.1, label=t["p3_l"], zorder=4)[0]
    draw_year_groups(ax, months_erw, t["m"], show_months=False)
    ax.legend(handles=[l3, p_svr, p_bip_patch], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.5)
    save_fig(fig, t["src_ba_kug"], "03_erweiterte_spannungszahl")

    fp3 = go.Figure()
    fp3.add_trace(go.Scatter(x=months_erw, y=[round(v, 1) for v in y_erw_v], customdata=fmt_arr(y_erw_v), name=t["p3_l"], mode="lines", line=dict(color="#D97706", width=2.2), hovertemplate=f"{t['p3_l']}: <b>%{{customdata}}</b><extra></extra>"))
    add_legend_dummies_plotly(fp3, t)
    save_sz_plotly(fp3, t["p3_t"], t["src_ba_kug"], now_str, "03_erweiterte_spannungszahl", t["sfx"], height_p=460, top_m=105, tick_step=12, shapes=shapes_erw)

    # 4. Erweiterte Spannungszahl (Aktueller 13-Monats-Verlauf)
    months_ez = months_erw[-13:]
    xez = np.arange(len(months_ez))
    yez = [float(sz_erw.loc[ym]) for ym in months_ez]
    shapes_ez = _add_rec_shapes_plotly(months_ez, gdp_bands)
    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.78, bottom=0.25)
    ymin_4 = int(np.floor((min(yez) - 100) / 100.0) * 100)
    ymax_4 = int(np.ceil((max(yez) + 100) / 100.0) * 100)
    style_sz_ax(fig, ax, t["p4_t"], ymin_4, ymax_4, range(ymin_4, ymax_4 + 100, 100), t["x_m"], xlabel_y=-0.33)
    _add_rec_bands_ax(ax, months_ez, gdp_bands)
    l4 = ax.plot(xez, yez, color="#D97706", lw=2.3, marker="o", ms=3.5, label=t["p3_l"], zorder=4)[0]
    draw_year_groups(ax, months_ez, t["m"], step=1, year_y=-0.26, show_months=True)
    ax.legend(handles=[l4, p_svr, p_bip_patch], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.5)
    save_fig(fig, t["src_ba_kug"], "04_erweiterte_spannungszahl_zoom")

    fp4 = go.Figure()
    fp4.add_trace(go.Scatter(x=months_ez, y=[round(v, 1) for v in yez], customdata=fmt_arr(yez), name=t["p3_l"], mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.3), hovertemplate=f"{t['p3_l']}: <b>%{{customdata}}</b><extra></extra>"))
    add_legend_dummies_plotly(fp4, t)
    save_sz_plotly(fp4, t["p4_t"], t["src_ba_kug"], now_str, "04_erweiterte_spannungszahl_zoom", t["sfx"], height_p=470, top_m=110, tick_step=1, shapes=shapes_ez)

    # 5. Spannungszahl und reales BIP (Dual-Achse)
    fig, ax1 = plt.subplots(figsize=(8.6, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.88, top=0.75, bottom=0.22)
    style_sz_ax(fig, ax1, t["p5_t"], -12, 12, range(-12, 16, 4), t["x_mq"], xlabel_y=-0.22)
    _add_rec_bands_ax(ax1, months_all, gdp_bands)
    ax1.set_ylabel(t["p5_yl"], fontsize=8.0, color="#475569")
    ax2 = ax1.twinx()
    ax2.set_ylim(-8000, 8000)
    ax2.set_yticks(range(-8000, 10000, 2000))
    ax2.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax2.set_ylabel(t["p5_yr"], fontsize=8.0, color="#475569", labelpad=8)
    for s in ("top", "right", "left", "bottom"):
        ax2.spines[s].set_visible(False)

    l5_bip, l5_einf, l5_erw = t["p5_l"]
    q_to_m = {"Q1": "02", "Q2": "05", "Q3": "08", "Q4": "11"}
    bx, by, bip_map = [], [], {}
    for k, v in bip_q.items():
        m_part = q_to_m.get(k[-2:], "")
        ym_key = f"{k[:4]}-{m_part}"
        if ym_key in months_all:
            bx.append(months_all.index(ym_key))
            by.append(float(v))
            bip_map[ym_key] = round(float(v), 1)
    p_bip = ax1.plot(bx, by, color="#059669", lw=2.1, marker="o", ms=3.0, label=l5_bip, zorder=5)[0]
    p_einf = ax2.plot(x_all, y_einf, color="#1B3A6B", lw=2.0, label=l5_einf, zorder=3)[0]
    p_erw = ax2.plot(x_all, y_erw, color="#D97706", lw=2.0, label=l5_erw, zorder=4)[0]
    draw_year_groups(ax1, months_all, t["m"], show_months=False)
    ax1.legend(handles=[p_bip, p_einf, p_erw, p_svr, p_bip_patch], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.3)
    save_fig(fig, t["src_all"], "05_spannungszahl_bip")

    y_bip_full = [bip_map.get(ym, None) for ym in months_all]
    fp5 = make_subplots(specs=[[{"secondary_y": True}]])
    fp5.add_trace(go.Scatter(x=months_all, y=y_bip_full, customdata=fmt_arr(y_bip_full), name=l5_bip, mode="lines+markers", marker=dict(size=5), line=dict(color="#059669", width=2.2), connectgaps=True, hovertemplate=f"{l5_bip}: <b>%{{customdata}} %</b><extra></extra>"), secondary_y=False)
    fp5.add_trace(go.Scatter(x=months_all, y=[round(v, 1) for v in y_einf], customdata=fmt_arr(y_einf), name=l5_einf, mode="lines", line=dict(color="#1B3A6B", width=2.0), hovertemplate=f"{l5_einf}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    y_erw_clean = [None if np.isnan(v) else round(float(v), 1) for v in y_erw]
    fp5.add_trace(go.Scatter(x=months_all, y=y_erw_clean, customdata=fmt_arr(y_erw_clean), name=l5_erw, mode="lines", line=dict(color="#D97706", width=2.0), hovertemplate=f"{l5_erw}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    add_legend_dummies_plotly(fp5, t, secondary_y=False)
    fp5.update_yaxes(title_text=t["p5_yl"].replace("\n", " "), range=[-12, 12], dtick=4, fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, secondary_y=False)
    fp5.update_yaxes(title_text=t["p5_yr"].replace("\n", " "), range=[-8000, 8000], dtick=2000, fixedrange=True, showgrid=False, secondary_y=True)
    save_sz_plotly(fp5, t["p5_t"], t["src_all"], now_str, "05_spannungszahl_bip", t["sfx"], height_p=490, top_m=125, tick_step=12, shapes=shapes_all)

def main():
    s_stellen, s_alo, s_kug = load_labor_market()
    common = s_stellen.index.intersection(s_alo.index)
    print(f"[DESTATIS/BA MERGE] Gemeinsame Monate: {len(common)}")

    d_einf = s_stellen.loc[common] - s_alo.loc[common]
    sz_einf = (d_einf - d_einf.shift(12)).dropna()

    common_erw = common.intersection(s_kug.index)
    d_erw = s_stellen.loc[common_erw] - (s_alo.loc[common_erw] + s_kug.loc[common_erw])
    sz_erw = (d_erw - d_erw.shift(12)).dropna()
    print(f"[RESULT] Einfache SZ bis {sz_einf.index[-1]} ({sz_einf.values[-1]:.1f}) | Erweiterte SZ bis {sz_erw.index[-1]} ({sz_erw.values[-1]:.1f})")

    bip_q = get_destatis_bip_q()
    print(f"[DESTATIS BIP] Quartale geladen: {len(bip_q)}")
    build_charts_for_lang("de", sz_einf, sz_erw, bip_q)
    build_charts_for_lang("en", sz_einf, sz_erw, bip_q)

if __name__ == "__main__":
    main()
