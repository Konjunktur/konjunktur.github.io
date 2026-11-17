import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/konjunktur-arbeitsmarkt", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"
BBK_BASE = "https://api.statistiken." + "bundesbank.de/rest/data/"

DE_RECESSIONS = [
    ("1992-04", "1993-06"),
    ("2001-04", "2003-06"),
    ("2008-04", "2009-06"),
    ("2020-01", "2020-06"),
    ("2023-01", "2024-06"),
]

TEXTS = {
    "de": {
        "src": "Quelle: Deutsche Bundesbank, Statistisches Bundesamt (BA) | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": "",
        "rec_lbl": "Rezessions-/Schwächephasen (DE)",
        "u": ("1. Arbeitslosenquote (u)", "Registrierte Arbeitslose in % aller zivilen Erwerbspersonen", "Arbeitslosenquote (u)"),
        "v": ("2. Vakanzrate (v)", "Gemeldete Arbeitsstellen in % aller zivilen Erwerbspersonen", "Vakanzrate (v)"),
        "theta": ("3. Arbeitsmarktanspannung (v / u)", "Verhältnis von Vakanzrate zu Arbeitslosenquote (Referenzlinie = 1)", "Anspannung (v / u)"),
        "bev": ("4. Beveridge-Kurve (Deutschland)", "Vakanzrate (v) vs. Arbeitslosenquote (u) mit 45°-Linie (v = u)", "Historie", "Aktuell (ab 2022)", "45°-Linie (v = u)"),
        "feru": ("5. Vollbeschäftigungs-Arbeitslosenquote (FERU u*)", "Geometrisches Mittel u* = √(u × v) im Vergleich zur tatsächlichen Quote (u)", "Tatsächliche Quote (u)", "FERU (u*)"),
        "gap": ("6. Arbeitslosigkeitslücke (u − u*)", "Abstand zwischen Arbeitslosenquote und FERU in Prozentpunkten (+ Unterauslastung / − Überhitzung)", "Arbeitslosigkeitslücke (u − u*)"),
        "rec_ind": ("7. Rezessionsindikator (Michez-Regel für Deutschland)", "Minimum aus 3M-Anstieg der Arbeitslosenquote und 3M-Rückgang der Vakanzrate (in %-Punkten)", "Rezessionsindikator", "Schwelle 1 (möglich)", "Schwelle 2 (sicher)"),
        "rec_prob": ("8. Rezessionswahrscheinlichkeit (duale Michez-Regel)", "Normierter Anteil zwischen unterer und oberer Rezessionsschwelle (in %)", "Rezessionswahrscheinlichkeit"),
    },
    "en": {
        "src": "Source: Deutsche Bundesbank, Federal Statistical Office (BA) | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en",
        "rec_lbl": "Recession / downturn periods (DE)",
        "u": ("1. Unemployment Rate (u)", "Registered unemployed in % of total civilian labor force", "Unemployment rate (u)"),
        "v": ("2. Vacancy Rate (v)", "Registered job openings in % of total civilian labor force", "Vacancy rate (v)"),
        "theta": ("3. Labor Market Tightness (v / u)", "Ratio of vacancy rate to unemployment rate (reference = 1)", "Tightness (v / u)"),
        "bev": ("4. Beveridge Curve (Germany)", "Vacancy rate (v) vs. unemployment rate (u) with 45° ray (v = u)", "History", "Recent (from 2022)", "45° ray (v = u)"),
        "feru": ("5. Full-Employment Rate of Unemployment (FERU u*)", "Geometric mean u* = √(u × v) vs. actual unemployment rate (u)", "Actual rate (u)", "FERU (u*)"),
        "gap": ("6. Unemployment Gap (u − u*)", "Distance between unemployment rate and FERU in percentage points (+ slack / − tight)", "Unemployment gap (u − u*)"),
        "rec_ind": ("7. Recession Indicator (Michez Rule for Germany)", "Minimum of 3M unemployment rate rise and 3M vacancy rate drop (in percentage points)", "Recession indicator", "Threshold 1 (possible)", "Threshold 2 (certain)"),
        "rec_prob": ("8. Recession Probability (Dual Michez Rule)", "Normalized share between lower and upper recession thresholds (in %)", "Recession probability"),
    }
}

def fmt_num(val, use_comma, dec=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s

def _unpack(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def _destatis_ffcsv(table, startyear="2022"):
    if not D_USER or not D_PASS:
        return pd.DataFrame()
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            return pd.DataFrame()
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            txt = _unpack(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
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

def load_all_labor_data():
    s_alo = pd.Series(dtype=float)
    s_ste = pd.Series(dtype=float)
    s_alq = pd.Series(dtype=float)

    u = f"{BBK_BASE}BBDL1/M.DE.N.?format=csv&lang=de"
    r = requests.get(u, timeout=45)
    if r.status_code == 200 and len(r.text) >= 500:
        first_line = next(iter(r.text.splitlines()), "")
        sep = ";" if first_line.count(";") >= first_line.count(",") else ","
        df = pd.read_csv(io.StringIO(r.text), sep=sep, low_memory=False)
        time_col = next(iter(df.columns))
        is_date = df[time_col].astype(str).str.match(r"^(19\d{2}|20\d{2})-\d{2}")
        meta_df, data_df = df.loc[~is_date], df.loc[is_date]
        yms = data_df[time_col].astype(str).str.slice(0, 7).values

        for col in df.columns[1:]:
            if str(col).endswith("_FLAGS"):
                continue
            desc = " | ".join(str(x).strip() for x in meta_df[col].dropna().tolist()[:8])
            cl = f"{col} | {desc}".lower()
            if any(ex in cl for ex in ("saisonbereinigt", "kalenderbereinigt", "männer", "frauen", "ausländer", "zugang", "abgang", "anzeige", "index", "geringfügig", "beschäftigte", "sozialversicherungspflichtig", "unterbeschäftigung")):
                continue
            vals = pd.to_numeric(data_df[col].astype(str).str.replace(",", "."), errors="coerce")
            valid = vals.notna()
            if valid.sum() < 36:
                continue
            nums = vals.loc[valid].values
            ser = pd.Series(nums, index=yms[valid]).groupby(level=0).last().sort_index()
            if "arbeitslosenquote" in cl and "alle zivilen" in cl and ("insgesamt" in cl or "deutschland" in cl):
                if s_alq.empty or ser.index[-1] > s_alq.index[-1]:
                    s_alq = ser
            elif "quote" not in cl and "%" not in cl:
                scale = 0.001 if np.nanmedian(nums) > 20000 else 1.0
                ser_s = ser * scale
                if "arbeitslose" in cl and ("insgesamt" in cl or "deutschland" in cl):
                    if s_alo.empty or ser_s.index[-1] > s_alo.index[-1]:
                        s_alo = ser_s
                elif ("gemeldete arbeitsstellen" in cl or "offene stellen" in cl) and ("insgesamt" in cl or "deutschland" in cl):
                    if s_ste.empty or ser_s.index[-1] > s_ste.index[-1]:
                        s_ste = ser_s

    try:
        df_ba = _destatis_ffcsv("13211-0002", "2022")
        if not df_ba.empty and "2_variable_attribute_label" in df_ba.columns:
            df_ba = df_ba[df_ba["2_variable_attribute_label"].astype(str).str.strip() == "Insgesamt"].copy()
        if not df_ba.empty:
            for code_v, target_s in (("ERW007", "ste"), ("ERW006", "alo"), ("ERW112", "alq")):
                sub = df_ba[df_ba["_CODES"].apply(lambda s: code_v in s)].copy()
                sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
                sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
                if not sub.empty:
                    vals = sub["V"].values
                    if target_s == "alq":
                        s_new = pd.Series(vals, index=sub["ZEIT"].astype(str).str.strip().values)
                        s_alq = s_new.combine_first(s_alq).sort_index()
                    else:
                        scale = 0.001 if np.nanmedian(vals) > 20000 else 1.0
                        s_new = pd.Series(vals * scale, index=sub["ZEIT"].astype(str).str.strip().values)
                        if target_s == "ste":
                            s_ste = s_new.combine_first(s_ste).sort_index()
                        else:
                            s_alo = s_new.combine_first(s_alo).sort_index()
    except Exception:
        pass

    comb = pd.DataFrame({"alo": s_alo, "ste": s_ste, "alq": s_alq}).dropna()
    comb = comb[(comb["alo"] > 0) & (comb["ste"] > 0) & (comb["alq"] > 0)].copy()
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
    comb["michez"] = np.minimum(du, dv).clip(lower=0.0)

    rec_peaks = []
    for r_s, r_e in DE_RECESSIONS[:-1]:
        sub_r = comb.loc[r_s:r_e, "michez"].dropna()
        if not sub_r.empty:
            rec_peaks.append(float(sub_r.max()))
    non_rec_mask = pd.Series(True, index=comb.index)
    for r_s, r_e in DE_RECESSIONS:
        non_rec_mask.loc[r_s:r_e] = False
    exp_max = float(comb.loc[non_rec_mask, "michez"].max()) if non_rec_mask.any() else 0.10
    thr_low = round(max(exp_max + 0.01, min(rec_peaks) * 0.85 if rec_peaks else 0.15), 2)
    thr_high = round(max(thr_low + 0.15, float(np.median(rec_peaks)) if rec_peaks else 0.45), 2)
    comb["prob"] = ((comb["michez"] - thr_low) / (thr_high - thr_low) * 100.0).clip(0.0, 100.0)
    return comb, thr_low, thr_high

def _add_rec_bands_ax(ax, months):
    m_map = {ym: i for i, ym in enumerate(months)}
    for r_s, r_e in DE_RECESSIONS:
        vis = [i for ym, i in m_map.items() if r_s <= ym <= r_e]
        if vis:
            ax.axvspan(min(vis) - 0.5, max(vis) + 0.5, color="#CBD5E1", alpha=0.45, zorder=0)

def _add_rec_shapes_plotly(months):
    m_set = set(months)
    shapes = []
    for r_s, r_e in DE_RECESSIONS:
        vis = sorted([ym for ym in m_set if r_s <= ym <= r_e])
        if vis:
            shapes.append(dict(type="rect", xref="x", yref="paper", x0=vis, x1=vis[-1], y0=0, y1=1, fillcolor="#CBD5E1", opacity=0.35, line_width=0, layer="below"))
    return shapes

def _save_plotly(fig_p, title_p, sub_p, src_text, now_str, out_path, tick_step=12, shapes=None, zero_line=False):
    fig_p.update_layout(
        title=dict(text=f"<b>{title_p}</b><br><span style='font-size:11px;color:#475569;'>{sub_p}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.2, color="#1E293B")),
        margin=dict(l=50, r=24, t=96, b=95), height=445,
        shapes=shapes or [],
        annotations=[
            dict(text=f"{src_text}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    xaxis_kw = dict(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10, color="#475569"))
    if tick_step > 1 and fig_p.data and fig_p.data.x is not None:
        all_x = list(fig_p.data.x)
        t_vals = [x for i, x in enumerate(all_x) if i % tick_step == 0]
        xaxis_kw.update(tickmode="array", tickvals=t_vals, ticktext=t_vals)
    fig_p.update_xaxes(**xaxis_kw)
    fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=zero_line, zerolinecolor="#64748B", tickfont=dict(size=10, color="#475569"))
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def render_ts_chart(key, lang, months, series_list, ref_lines=None, dec=2, zero_line=False):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    title_t = t[key]
    sub_t = t[key]
    x = np.arange(len(months))
    step = max(12, (len(months) // 14 // 12) * 12)
    tick_pos = [i for i in range(0, len(months), step)]

    # PNG
    fig, ax = plt.subplots(figsize=(8.6, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.80, bottom=0.21)
    fig.suptitle(title_t, x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub_t, ha="left", fontsize=7.8, color="#64748B")
    ax.set_facecolor("#F8FAFC")
    _add_rec_bands_ax(ax, months)
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    if zero_line:
        ax.axhline(0, color="#64748B", lw=1.0, zorder=1)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_num(v, use_c, dec)))

    for vals, lbl, col, ls in series_list:
        ax.plot(x, vals, color=col, lw=2.0, linestyle=ls, label=str(lbl), zorder=4)
        ax.scatter([x[-1]], [vals[-1]], color=col, s=16, zorder=5)
        ax.text(x[-1] + 1.2, vals[-1], fmt_num(vals[-1], use_c, dec), fontsize=7.3, fontweight="bold", color=col, va="center", ha="left")
    for r_val, r_lbl, r_col in (ref_lines or []):
        ax.axhline(r_val, color=r_col, lw=1.4, linestyle="--", label=f"{r_lbl} ({fmt_num(r_val, use_c, dec)})", zorder=3)

    ax.set_xlim(-1, len(months) + 12)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i][:7] for i in tick_pos], ha="right")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.6)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/konjunktur-arbeitsmarkt/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    # HTML
    fp = go.Figure()
    for vals, lbl, col, ls in series_list:
        dash = "dash" if ls == "--" else "solid"
        fp.add_trace(go.Scatter(x=months, y=[round(float(v), dec) for v in vals], customdata=[fmt_num(v, use_c, dec) for v in vals], name=str(lbl), mode="lines", line=dict(color=col, width=2.2, dash=dash), hovertemplate=f"{lbl}: <b>%{{customdata}}</b><extra></extra>"))
    for r_val, r_lbl, r_col in (ref_lines or []):
        fp.add_trace(go.Scatter(x=months, y=[round(float(r_val), dec)] * len(months), customdata=[fmt_num(r_val, use_c, dec)] * len(months), name=f"{r_lbl} ({fmt_num(r_val, use_c, dec)})", mode="lines", line=dict(color=r_col, width=1.6, dash="dash"), hovertemplate=f"{r_lbl}: <b>%{{customdata}}</b><extra></extra>"))
    if use_c:
        fp.update_layout(separators=",.")
    _save_plotly(fp, title_t, sub_t, t["src"], now_str, f"static/konjunktur-arbeitsmarkt/{key}{t['sfx']}.html", tick_step=step, shapes=_add_rec_shapes_plotly(months), zero_line=zero_line)

def render_beveridge(lang, df):
    t = TEXTS[lang]
    use_c = t["comma"]
    now_str = datetime.now().strftime(t["date_fmt"])
    title_t, sub_t, lbl_h, lbl_r, lbl_45 = t["bev"]
    hist = df[df.index < "2022-01"]
    rec = df[df.index >= "2022-01"]
    lim = max(float(df["u"].max()), float(df["v"].max())) * 1.08

    # PNG
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
    ax.scatter(hist["u"], hist["v"], color="#94A3B8", s=16, alpha=0.55, label=lbl_h, zorder=3)
    ax.plot(rec["u"], rec["v"], color="#1B3A6B", lw=1.3, alpha=0.75, zorder=4)
    ax.scatter(rec["u"], rec["v"], color="#1B3A6B", s=22, label=lbl_r, zorder=5)
    ax.scatter([rec["u"].iloc[-1]], [rec["v"].iloc[-1]], color="#DC2626", s=45, zorder=6)
    ax.text(rec["u"].iloc[-1] + 0.18, rec["v"].iloc[-1], rec.index[-1], fontsize=7.5, fontweight="bold", color="#DC2626", va="center")

    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("u (%)", fontsize=8.5, color="#475569")
    ax.set_ylabel("v (%)", fontsize=8.5, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.8)
    fig.text(0.10, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.93, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/konjunktur-arbeitsmarkt/bev{t['sfx']}.png", dpi=300)
    plt.close()

    # HTML
    fp = go.Figure()
    fp.add_trace(go.Scatter(x=[0, round(lim, 2)], y=[0, round(lim, 2)], name=lbl_45, mode="lines", line=dict(color="#D97706", width=1.6, dash="dash"), hoverinfo="skip"))
    fp.add_trace(go.Scatter(x=[round(float(x), 2) for x in hist["u"]], y=[round(float(y), 2) for y in hist["v"]], text=list(hist.index), name=lbl_h, mode="markers", marker=dict(color="#94A3B8", size=6, opacity=0.6), hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.add_trace(go.Scatter(x=[round(float(x), 2) for x in rec["u"]], y=[round(float(y), 2) for y in rec["v"]], text=list(rec.index), name=lbl_r, mode="lines+markers", line=dict(color="#1B3A6B", width=1.6), marker=dict(color="#1B3A6B", size=7), hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.add_trace(go.Scatter(x=[round(float(rec["u"].iloc[-1]), 2)], y=[round(float(rec["v"].iloc[-1]), 2)], text=[rec.index[-1]], name=rec.index[-1], mode="markers+text", textposition="middle right", marker=dict(color="#DC2626", size=10), showlegend=False, hovertemplate="%{text}<br>u: %{x:.2f} % | v: %{y:.2f} %<extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{title_t}</b><br><span style='font-size:11px;color:#475569;'>{sub_t}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=14.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="closest", dragmode=False,
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.2, color="#1E293B")),
        margin=dict(l=54, r=24, t=96, b=95), height=455,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(title="u (%)", range=[0, lim], fixedrange=True, gridcolor="#E2E8F0", linecolor="#94A3B8", tickfont=dict(size=10))
    fp.update_yaxes(title="v (%)", range=[0, lim], fixedrange=True, gridcolor="#E2E8F0", linecolor="#94A3B8", tickfont=dict(size=10))
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
    months = list(df.index)
    for lang in ("de", "en"):
        t = TEXTS[lang]
        render_ts_chart("u", lang, months, [(df["u"].values, t["u"], "#1B3A6B", "-")], dec=2)
        render_ts_chart("v", lang, months, [(df["v"].values, t["v"], "#0D9488", "-")], dec=2)
        render_ts_chart("theta", lang, months, [(df["theta"].values, t["theta"], "#1B3A6B", "-")], ref_lines=[(1.0, "v = u", "#D97706")], dec=2)
        render_beveridge(lang, df)
        render_ts_chart("feru", lang, months, [(df["u"].values, t["feru"], "#1B3A6B", "-"), (df["feru"].values, t["feru"], "#D97706", "--")], dec=2)
        render_ts_chart("gap", lang, months, [(df["gap"].values, t["gap"], "#DC2626", "-")], dec=2, zero_line=True)
        render_ts_chart("rec_ind", lang, months, [(df["michez"].values, t["rec_ind"], "#1B3A6B", "-")], ref_lines=[(thr_low, t["rec_ind"], "#D97706"), (thr_high, t["rec_ind"], "#DC2626")], dec=2)
        render_ts_chart("rec_prob", lang, months, [(df["prob"].values, t["rec_prob"], "#DC2626", "-")], dec=0)
    print(f"[OK] Michaillat-Saez Deutschland (DE & EN) bis {months[-1]} erstellt (Schwellen: {thr_low}/{thr_high} pp).")

if __name__ == "__main__":
    main()
