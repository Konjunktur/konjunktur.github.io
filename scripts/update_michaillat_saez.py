import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/konjunktur-arbeitsmarkt", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"

# Graue Phasen: Rezessions- und Schwächephasen (Sachverständigenrat / Bundesbank)
DE_RECESSIONS = [
    ("2008-04", "2009-06"),
    ("2012-10", "2013-03"),
    ("2020-01", "2020-06"),
    ("2022-10", "2025-12"),
]

# Fallback falls Destatis 81000-0002 vorübergehend nicht erreichbar ist
# Ausschließlich Vorjahresvergleich (WERTORG + VGRPKM + VGR014 < 0 %)
FALLBACK_GDP_YOY_NEG = [
    ("2008-10", "2009-12"),  # 2008-Q4 bis 2009-Q4
    ("2012-10", "2013-03"),  # 2012-Q4 bis 2013-Q1
    ("2020-01", "2021-03"),  # 2020-Q1 bis 2021-Q1
    ("2023-04", "2025-06"),  # 2023-Q2 bis 2025-Q2
]

TEXTS = {
    "de": {
        "src": "Quelle: Statistisches Bundesamt (Daten der BA) | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": "",
        "rec_grey_lbl": "Rezession/Schwäche (SVR/BBk)",
        "rec_blue_lbl": "Reales BIP < 0 % gg. Vj.",
        "u_title": "Arbeitslosenquote (u)",
        "u_sub": "Registrierte Arbeitslose in % aller zivilen Erwerbspersonen",
        "u_lbl": "Arbeitslosenquote (u)",
        "v_title": "Vakanzrate (v)",
        "v_sub": "Gemeldete Arbeitsstellen in % aller zivilen Erwerbspersonen",
        "v_lbl": "Vakanzrate (v)",
        "theta_title": "Arbeitsmarktanspannung (v / u)",
        "theta_sub": "Verhältnis von Vakanzrate zu Arbeitslosenquote (Effizienz-Referenz = 1)",
        "theta_lbl": "Anspannung (v / u)",
        "bev_title": "Beveridge-Kurve (Deutschland)",
        "bev_sub": "Vakanzrate (v) gegen Arbeitslosenquote (u) mit 45°-Linie (v = u)",
        "bev_hist": "Ab Jan. 2005",
        "bev_rec": "Ab Jan. 2022",
        "bev_45": "45°-Linie (v = u)",
        "feru_title": "Arbeitslosenquote und Vollbeschäftigungsquote (FERU u*)",
        "feru_sub": "Geometrisches Mittel u* = √(u × v) im Vergleich zur Arbeitslosenquote (u)",
        "feru_u": "Arbeitslosenquote (u)",
        "feru_star": "Vollbeschäftigungsquote (FERU u*)",
        "gap_title": "Arbeitslosigkeitslücke (u − u*)",
        "gap_sub": "Abstand zwischen Arbeitslosenquote und FERU in Prozentpunkten (+ Unterauslastung / − Überhitzung)",
        "gap_lbl": "Arbeitslosigkeitslücke (u − u*)",
        "rec_ind_title": "Rezessionsindikator (Michaillat-Regel für Deutschland)",
        "rec_ind_sub": "Minimum aus 3M-Anstieg der Arbeitslosenquote und 3M-Rückgang der Vakanzrate (in %-Punkten)",
        "rec_ind_lbl": "Rezessionsindikator",
        "rec_t1": "Untere Schwelle (möglich)",
        "rec_t2": "Obere Schwelle (sicher)",
        "rec_prob_title": "Rezessionswahrscheinlichkeit (duale Michaillat-Regel)",
        "rec_prob_sub": "Anteil der überschrittenen Rezessionsschwellen zwischen unterer und oberer Schwelle (in %)",
        "rec_prob_lbl": "Rezessionswahrscheinlichkeit",
    },
    "en": {
        "src": "Source: Federal Statistical Office (BA data) | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en",
        "rec_grey_lbl": "Recession/slowdown (GCEE/BBk)",
        "rec_blue_lbl": "Real GDP < 0% YoY",
        "u_title": "Unemployment Rate (u)",
        "u_sub": "Number of registered unemployed divided by civilian labor force (in %)",
        "u_lbl": "Unemployment rate (u)",
        "v_title": "Vacancy Rate (v)",
        "v_sub": "Number of registered job openings divided by civilian labor force (in %)",
        "v_lbl": "Vacancy rate (v)",
        "theta_title": "Labor Market Tightness (v / u)",
        "theta_sub": "Ratio of vacancy rate to unemployment rate (efficiency benchmark = 1)",
        "theta_lbl": "Tightness (v / u)",
        "bev_title": "Beveridge Curve (Germany)",
        "bev_sub": "Vacancy rate (v) against unemployment rate (u) with 45° ray (v = u)",
        "bev_hist": "From Jan 2005",
        "bev_rec": "From Jan 2022",
        "bev_45": "45° ray (v = u)",
        "feru_title": "Unemployment Rate and Full-Employment Rate (FERU u*)",
        "feru_sub": "Geometric average u* = √(u × v) compared to the unemployment rate (u)",
        "feru_u": "Unemployment rate (u)",
        "feru_star": "Full-employment rate (FERU u*)",
        "gap_title": "Unemployment Gap (u − u*)",
        "gap_sub": "Distance between the unemployment rate and FERU in percentage points (+ slack / − tight)",
        "gap_lbl": "Unemployment gap (u − u*)",
        "rec_ind_title": "Recession Indicator (Michaillat Rule for Germany)",
        "rec_ind_sub": "Minimum of 3M unemployment rate rise and 3M vacancy rate drop (in percentage points)",
        "rec_ind_lbl": "Recession indicator",
        "rec_t1": "Lower threshold (possible)",
        "rec_t2": "Upper threshold (certain)",
        "rec_prob_title": "Recession Probability (Dual Michaillat Rule)",
        "rec_prob_sub": "Share of thresholds crossed between lower and upper recession bounds (in %)",
        "rec_prob_lbl": "Recession probability",
    }
}

def fmt_num(val, use_comma, dec=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s

def fmt_clean(val, use_comma, dec=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    v = round(float(val), dec)
    if v == 0:
        v = 0.0
    s = f"{v:.{dec}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if use_comma else s

def _unpack(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def _destatis_ffcsv(table, startyear="2005"):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90)
    r.raise_for_status()
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        rj.raise_for_status()
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
    hdr = [h.strip() for h in rows.pop(0)]
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
    code_cols = [c for c in df.columns if c.endswith("_code")]
    df["_CODES"] = [set(str(r[c]).strip() for c in code_cols) for _, r in df.iterrows()]
    return df

def load_gdp_recession_bands():
    """
    Lädt aus Destatis 81000-0002 strikt die preisbereinigten Originalwerte
    (WERTORG + VGRPKM + VGR014 = Veränderung gegenüber dem Vorjahresquartal in %)
    und gibt zusammenhängende Monatsintervalle zurück, in denen reales BIP < 0 % gg. Vj. liegt.
    """
    try:
        df_gdp = _destatis_ffcsv("81000-0002", "2005")
        if not df_gdp.empty:
            # Strikter Filter auf Vorjahresvergleich (WERTORG), preisbereinigt (VGRPKM), Veränderungsrate (VGR014)
            sub = df_gdp[df_gdp["_CODES"].apply(lambda s: {"WERTORG", "VGRPKM", "VGR014"}.issubset(s))].copy()
            q_col = None
            for c in df_gdp.columns:
                if c.endswith("_code") and df_gdp[c].astype(str).str.match(r"^QUART[1-4]$", case=False).any():
                    q_col = c
                    break
            if not sub.empty and q_col:
                sub["Q_NUM"] = pd.to_numeric(sub[q_col].astype(str).str.extract(r"([1-4])", expand=False), errors="coerce")
                sub["YR"] = pd.to_numeric(sub["ZEIT"].astype(str).str.slice(0, 4), errors="coerce")
                sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
                sub = sub.dropna(subset=["Q_NUM", "YR", "V"]).sort_values(["YR", "Q_NUM"])
                sub = sub.drop_duplicates(subset=["YR", "Q_NUM"], keep="first")

                q_months = {
                    1: ("01", "03"),
                    2: ("04", "06"),
                    3: ("07", "09"),
                    4: ("10", "12"),
                }
                neg_intervals = []
                for _, row in sub[sub["V"] < 0.0].iterrows():
                    yr = int(row["YR"])
                    qn = int(row["Q_NUM"])
                    m_start, m_end = q_months[qn]
                    neg_intervals.append((f"{yr:04d}-{m_start}", f"{yr:04d}-{m_end}"))

                # Angrenzende Quartale zu durchgehenden Bändern zusammenfassen
                merged = []
                for s_ym, e_ym in sorted(neg_intervals):
                    if not merged:
                        merged.append([s_ym, e_ym])
                        continue
                    prev_y, prev_m = int(merged[-1][1][:4]), int(merged[-1][1][5:7])
                    cur_y, cur_m = int(s_ym[:4]), int(s_ym[5:7])
                    if (cur_y * 12 + cur_m) == (prev_y * 12 + prev_m + 1):
                        merged[-1][1] = e_ym
                    else:
                        merged.append([s_ym, e_ym])
                if merged:
                    return [(a, b) for a, b in merged]
    except Exception:
        pass
    return FALLBACK_GDP_YOY_NEG

def load_all_labor_data():
    df_ba = _destatis_ffcsv("13211-0002", "2005")
    if df_ba.empty:
        raise RuntimeError("Destatis Tabelle 13211-0002 lieferte keine Daten.")
    if "2_variable_attribute_label" in df_ba.columns:
        df_ba = df_ba[df_ba["2_variable_attribute_label"].astype(str).str.strip() == "Insgesamt"].copy()

    series_map = {}
    for code_v, target_s in (("ERW007", "ste"), ("ERW006", "alo"), ("ERW112", "alq")):
        sub = df_ba[df_ba["_CODES"].apply(lambda s: code_v in s)].copy()
        sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
        vals = sub["V"].values
        if target_s == "alq":
            series_map[target_s] = pd.Series(vals, index=sub["ZEIT"].astype(str).str.strip().values)
        else:
            scale = 0.001 if np.nanmedian(vals) > 20000 else 1.0
            series_map[target_s] = pd.Series(vals * scale, index=sub["ZEIT"].astype(str).str.strip().values)

    comb = pd.DataFrame(series_map).dropna()
    comb = comb[(comb["alo"] > 0) & (comb["ste"] > 0) & (comb["alq"] > 0)]
    comb = comb[comb.index >= "2005-01"].copy()
    comb["ep"] = comb["alo"] / (comb["alq"] / 100.0)
    comb["u"] = comb["alo"] / comb["ep"] * 100.0
    comb["v"] = comb["ste"] / comb["ep"] * 100.0
    comb["theta"] = comb["v"] / comb["u"]
    comb["feru"] = np.sqrt(comb["u"] * comb["v"])
    comb["gap"] = comb["u"] - comb["feru"]

    u3 = comb["u"].rolling(3).mean()
    v3 = comb["v"].rolling(3).mean()
    du = u3 - u3.shift(1).rolling(12).min()
    dv = v3.shift(1).rolling(12).max() - v3
    comb["michaillat"] = np.minimum(du, dv).clip(lower=0.0)

    rec_peaks = []
    for r_s, r_e in DE_RECESSIONS:
        sub_r = comb.loc[r_s:r_e, "michaillat"].dropna()
        if not sub_r.empty and float(sub_r.max()) > 0:
            rec_peaks.append(float(sub_r.max()))
    if len(rec_peaks) >= 2:
        thr_low = round(min(rec_peaks) * 0.75, 2)
        thr_high = round(float(np.percentile(rec_peaks, 75)), 2)
    else:
        thr_low, thr_high = 0.08, 0.25
    if thr_high <= thr_low:
        thr_high = round(thr_low + 0.10, 2)
    comb["prob"] = ((comb["michaillat"] - thr_low) / (thr_high - thr_low) * 100.0).clip(0.0, 100.0)
    return comb, thr_low, thr_high

def _add_rec_bands_ax(ax, months, gdp_bands):
    m_map = {ym: i for i, ym in enumerate(months)}
    for r_s, r_e in DE_RECESSIONS:
        vis = [i for ym, i in m_map.items() if r_s <= ym <= r_e]
        if vis:
            ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color="#CBD5E1", alpha=0.45, zorder=0)
    for b_s, b_e in gdp_bands:
        vis = [i for ym, i in m_map.items() if b_s <= ym <= b_e]
        if vis:
            ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color="#93C5FD", alpha=0.35, zorder=0.5)

def _add_rec_shapes_plotly(months, gdp_bands):
    m_set = set(months)
    shapes = []
    for r_s, r_e in DE_RECESSIONS:
        vis = sorted([ym for ym in m_set if r_s <= ym <= r_e])
        if vis:
            shapes.append(dict(type="rect", xref="x", yref="paper", x0=vis[0], x1=vis[-1], y0=0, y1=1, fillcolor="#CBD5E1", opacity=0.35, line_width=0, layer="below"))
    for b_s, b_e in gdp_bands:
        vis = sorted([ym for ym in m_set if b_s <= ym <= b_e])
        if vis:
            shapes.append(dict(type="rect", xref="x", yref="paper", x0=vis[0], x1=vis[-1], y0=0, y1=1, fillcolor="#93C5FD", opacity=0.30, line_width=0, layer="below"))
    return shapes

def _save_plotly(fig_p, months, title_p, sub_p, src_text, now_str, out_path, tick_step=24, shapes=None, zero_line=False, y_range=None):
    fig_p.update_layout(
        title=dict(text=f"<b>{title_p}</b><br><span style='font-size:11px;color:#475569;'>{sub_p}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=9.8, color="#1E293B")),
        margin=dict(l=50, r=24, t=108, b=95), height=455,
        shapes=shapes or [],
        annotations=[
            dict(text=f"{src_text}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    xaxis_kw = dict(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10, color="#475569"))
    if tick_step > 1 and months:
        t_vals = [x for i, x in enumerate(months) if i % tick_step == 0]
        xaxis_kw.update(tickmode="array", tickvals=t_vals, ticktext=t_vals)
    fig_p.update_xaxes(**xaxis_kw)
    yaxis_kw = dict(fixedrange=True, gridcolor="#E2E8F0", zeroline=zero_line, zerolinecolor="#64748B", tickfont=dict(size=10, color="#475569"))
    if y_range is not None:
        yaxis_kw["range"] = y_range
    fig_p.update_yaxes(**yaxis_kw)
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def render_ts_chart(key, lang, months, gdp_bands, series_list, ref_lines=None, dec=2, zero_line=False, y_range=None):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    title_t = t[f"{key}_title"]
    sub_t = t[f"{key}_sub"]
    x = np.arange(len(months))
    step = 24 if len(months) > 120 else 12
    tick_pos = [i for i in range(0, len(months), step)]

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.78, bottom=0.21)
    fig.suptitle(title_t, x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub_t, ha="left", fontsize=7.8, color="#64748B")
    ax.set_facecolor("#F8FAFC")
    _add_rec_bands_ax(ax, months, gdp_bands)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    if zero_line:
        ax.axhline(0, color="#64748B", lw=1.0, zorder=1)
    if y_range is not None:
        ax.set_ylim(y_range[0], y_range[1])
    else:
        all_y = [float(v) for vals, _, _, _ in series_list for v in vals if not np.isnan(v)] + [float(r[0]) for r in (ref_lines or [])]
        if all_y:
            ymin_a, ymax_a = min(all_y), max(all_y)
            pad = max((ymax_a - ymin_a) * 0.10, 0.05)
            ax.set_ylim(ymin_a - pad, ymax_a + pad)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_clean(v, use_c, dec)))

    handles = []
    for vals, lbl, col, ls in series_list:
        line_h, = ax.plot(x, vals, color=col, lw=1.9, linestyle=ls, label=str(lbl), zorder=4)
        handles.append(line_h)
        ax.scatter([x[-1]], [vals[-1]], color=col, s=16, zorder=5)
        ax.text(x[-1] + 2.0, vals[-1], fmt_num(vals[-1], use_c, dec), fontsize=7.3, fontweight="bold", color=col, va="center", ha="left")
    for r_val, r_lbl, r_col in (ref_lines or []):
        ref_h = ax.axhline(r_val, color=r_col, lw=1.4, linestyle="--", label=f"{r_lbl} ({fmt_clean(r_val, use_c, dec)})", zorder=3)
        handles.append(ref_h)

    handles.append(Patch(facecolor="#CBD5E1", alpha=0.55, label=t["rec_grey_lbl"]))
    handles.append(Patch(facecolor="#93C5FD", alpha=0.45, label=t["rec_blue_lbl"]))

    ax.set_xlim(-2, len(months) + 18)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i][:7] for i in tick_pos], ha="right")
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.3)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/konjunktur-arbeitsmarkt/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    for vals, lbl, col, ls in series_list:
        dash = "dash" if ls == "--" else "solid"
        fp.add_trace(go.Scatter(x=months, y=[round(float(v), dec) for v in vals], customdata=[fmt_num(v, use_c, dec) for v in vals], name=str(lbl), mode="lines", line=dict(color=col, width=2.1, dash=dash), hovertemplate=f"{lbl}: <b>%{{customdata}}</b><extra></extra>"))
    for r_val, r_lbl, r_col in (ref_lines or []):
        fp.add_trace(go.Scatter(x=months, y=[round(float(r_val), dec)] * len(months), customdata=[fmt_num(r_val, use_c, dec)] * len(months), name=f"{r_lbl} ({fmt_clean(r_val, use_c, dec)})", mode="lines", line=dict(color=r_col, width=1.6, dash="dash"), hovertemplate=f"{r_lbl}: <b>%{{customdata}}</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#CBD5E1", symbol="square"), name=t["rec_grey_lbl"], hoverinfo="skip"))
    fp.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=10, color="#93C5FD", symbol="square"), name=t["rec_blue_lbl"], hoverinfo="skip"))
    if use_c:
        fp.update_layout(separators=",.")
    _save_plotly(fp, months, title_t, sub_t, t["src"], now_str, f"static/konjunktur-arbeitsmarkt/{key}{t['sfx']}.html", tick_step=step, shapes=_add_rec_shapes_plotly(months, gdp_bands), zero_line=zero_line, y_range=y_range)

def _fit_hyperbola_r2(u_vals, v_vals):
    inv_u = 1.0 / np.asarray(u_vals, dtype=float)
    y = np.asarray(v_vals, dtype=float)
    if len(y) < 3 or np.allclose(inv_u, inv_u.mean()):
        return 0.0, np.array([]), np.array([])
    b, a = np.polyfit(inv_u, y, 1)
    y_hat = a + b * inv_u
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    u_grid = np.linspace(float(u_vals.min()), float(u_vals.max()), 60)
    v_grid = a + b / u_grid
    return r2, u_grid, v_grid

def render_beveridge(lang, df):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    title_t = t["bev_title"]
    sub_t = t["bev_sub"]
    lbl_h = t["bev_hist"]
    lbl_r = t["bev_rec"]
    lbl_45 = t["bev_45"]
    hist = df[df.index < "2022-01"]
    rec = df[df.index >= "2022-01"]
    u_max = min(13.5, float(df["u"].max()) * 1.06)
    v_max = min(4.5, max(float(df["v"].max()) * 1.25, 3.5))
    lim = max(u_max, v_max)

    r2_all, ug_all, vg_all = _fit_hyperbola_r2(df["u"].values, df["v"].values)
    r2_rec, ug_rec, vg_rec = _fit_hyperbola_r2(rec["u"].values, rec["v"].values)
    r2_txt_all = f"R² ({min(df.index)[:4]}–{max(df.index)[:4]}) = {fmt_num(r2_all, use_c, 3)}"
    r2_txt_rec = f"R² (ab 2022) = {fmt_num(r2_rec, use_c, 3)}" if lang == "de" else f"R² (from 2022) = {fmt_num(r2_rec, use_c, 3)}"

    last_ym = df.index[-1]
    prev_ym = f"{int(last_ym[:4]) - 1:04d}-{last_ym[5:7]}"
    has_prev = prev_ym in df.index
    u_last, v_last = float(df["u"].iloc[-1]), float(df["v"].iloc[-1])
    u_prev, v_prev = (float(df.loc[prev_ym, "u"]), float(df.loc[prev_ym, "v"])) if has_prev else (u_last, v_last)

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.93, top=0.80, bottom=0.19)
    fig.suptitle(title_t, x=0.10, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.10, 0.915, sub_t, ha="left", fontsize=7.8, color="#64748B")
    ax.set_facecolor("#F8FAFC")
    ax.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#94A3B8")
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot([0, lim], [0, lim], color="#D97706", lw=1.4, linestyle="--", label=lbl_45, zorder=2)
    if len(ug_all) > 0:
        ax.plot(ug_all, vg_all, color="#64748B", lw=1.2, linestyle=":", zorder=2)
    if len(ug_rec) > 0:
        ax.plot(ug_rec, vg_rec, color="#1B3A6B", lw=1.2, linestyle=":", zorder=2)
    ax.scatter(hist["u"], hist["v"], color="#94A3B8", s=16, alpha=0.55, label=lbl_h, zorder=3)
    ax.plot(rec["u"], rec["v"], color="#1B3A6B", lw=1.3, alpha=0.75, zorder=4)
    ax.scatter(rec["u"], rec["v"], color="#1B3A6B", s=22, label=lbl_r, zorder=5)

    if has_prev:
        ax.scatter([u_prev], [v_prev], color="#DC2626", s=45, zorder=6)
        ax.annotate(prev_ym, xy=(u_prev, v_prev), xytext=(10, 8), textcoords="offset points", fontsize=7.4, fontweight="bold", color="#DC2626", ha="left")
    ax.scatter([u_last], [v_last], color="#DC2626", s=50, zorder=7)
    ax.annotate(last_ym, xy=(u_last, v_last), xytext=(10, -10), textcoords="offset points", fontsize=7.5, fontweight="bold", color="#DC2626", ha="left")

    ax.text(0.97, 0.08, f"{r2_txt_all}\n{r2_txt_rec}", transform=ax.transAxes, ha="right", va="bottom", fontsize=7.5, color="#334155", bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#CBD5E1", alpha=0.9))
    ax.set_xlim(0, u_max)
    ax.set_ylim(0, v_max)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_clean(v, use_c, 1)))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_clean(v, use_c, 1)))
    ax.set_xlabel("u (%)", fontsize=8.5, color="#475569")
    ax.set_ylabel("v (%)", fontsize=8.5, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.8)
    fig.text(0.10, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.93, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/konjunktur-arbeitsmarkt/bev{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    fp.add_trace(go.Scatter(x=[0, round(lim, 2)], y=[0, round(lim, 2)], name=lbl_45, mode="lines", line=dict(color="#D97706", width=1.6, dash="dash"), hoverinfo="skip"))
    if len(ug_all) > 0:
        fp.add_trace(go.Scatter(x=[round(float(z), 2) for z in ug_all], y=[round(float(z), 2) for z in vg_all], mode="lines", line=dict(color="#64748B", width=1.2, dash="dot"), showlegend=False, hoverinfo="skip"))
    fp.add_trace(go.Scatter(x=[round(float(x), 2) for x in hist["u"]], y=[round(float(y), 2) for y in hist["v"]], text=list(hist.index), name=lbl_h, mode="markers", marker=dict(color="#94A3B8", size=6, opacity=0.6), hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.add_trace(go.Scatter(x=[round(float(x), 2) for x in rec["u"]], y=[round(float(y), 2) for y in rec["v"]], text=list(rec.index), name=lbl_r, mode="lines+markers", line=dict(color="#1B3A6B", width=1.6), marker=dict(color="#1B3A6B", size=7), hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    if has_prev:
        fp.add_trace(go.Scatter(x=[round(u_prev, 2)], y=[round(v_prev, 2)], text=[prev_ym], mode="markers+text", textposition="top right", textfont=dict(size=10, color="#DC2626"), marker=dict(color="#DC2626", size=9), showlegend=False, hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.add_trace(go.Scatter(x=[round(u_last, 2)], y=[round(v_last, 2)], text=[last_ym], mode="markers+text", textposition="bottom right", textfont=dict(size=10.5, color="#DC2626"), marker=dict(color="#DC2626", size=10), showlegend=False, hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{title_t}</b><br><span style='font-size:11px;color:#475569;'>{sub_t}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="closest", dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.2, color="#1E293B")),
        margin=dict(l=54, r=24, t=96, b=95), height=455,
        annotations=[
            dict(text=f"{r2_txt_all}<br>{r2_txt_rec}", x=0.98, y=0.05, xref="paper", yref="paper", showarrow=False, align="right", bgcolor="rgba(255,255,255,0.85)", bordercolor="#CBD5E1", borderwidth=1, font=dict(size=10, color="#334155"), xanchor="right", yanchor="bottom"),
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(title="u (%)", range=[0, u_max], fixedrange=True, gridcolor="#E2E8F0", linecolor="#94A3B8", tickfont=dict(size=10))
    fp.update_yaxes(title="v (%)", range=[0, v_max], fixedrange=True, gridcolor="#E2E8F0", linecolor="#94A3B8", tickfont=dict(size=10))
    if use_c:
        fp.update_layout(separators=",.")
    out_path = f"static/konjunktur-arbeitsmarkt/bev{t['sfx']}.html"
    fp.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def main():
    df, thr_low, thr_high = load_all_labor_data()
    gdp_bands = load_gdp_recession_bands()
    months = list(df.index)
    for lang in ("de", "en"):
        t = TEXTS[lang]
        render_ts_chart("u", lang, months, gdp_bands, [(df["u"].values, t["u_lbl"], "#1B3A6B", "-")], dec=2)
        render_ts_chart("v", lang, months, gdp_bands, [(df["v"].values, t["v_lbl"], "#0D9488", "-")], dec=2)
        render_ts_chart("theta", lang, months, gdp_bands, [(df["theta"].values, t["theta_lbl"], "#1B3A6B", "-")], ref_lines=[(1.0, "v = u", "#D97706")], dec=2)
        render_beveridge(lang, df)
        render_ts_chart("feru", lang, months, gdp_bands, [(df["u"].values, t["feru_u"], "#1B3A6B", "-"), (df["feru"].values, t["feru_star"], "#D97706", "--")], dec=2)
        render_ts_chart("gap", lang, months, gdp_bands, [(df["gap"].values, t["gap_lbl"], "#DC2626", "-")], dec=2, zero_line=True)
        render_ts_chart("rec_ind", lang, months, gdp_bands, [(df["michaillat"].values, t["rec_ind_lbl"], "#1B3A6B", "-")], ref_lines=[(thr_low, t["rec_t1"], "#D97706"), (thr_high, t["rec_t2"], "#DC2626")], dec=2, zero_line=True)
        render_ts_chart("rec_prob", lang, months, gdp_bands, [(df["prob"].values, t["rec_prob_lbl"], "#DC2626", "-")], dec=0, zero_line=True, y_range=[-4, 106])
    print(f"[OK] Michaillat-Saez Deutschland (DE & EN) von {min(months)} bis {max(months)} erstellt (BIP-Rezessionsbänder: {gdp_bands}).")

if __name__ == "__main__":
    main()

