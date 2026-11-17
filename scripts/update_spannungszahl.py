import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("static/spannungszahl", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"
BBK_BASE = "https://api.statistiken." + "bundesbank.de/rest/data/"

MONATE_DE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
MONATE_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

TEXTS = {
    "de": {
        "m": MONATE_DE,
        "p1_t": "Einfache Spannungszahl (Gesamtzeitraum)",
        "p1_l": ("Einfache Spannungszahl (Ursprungswerte)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p2_t": "Einfache Spannungszahl (Aktueller 13-Monats-Verlauf)",
        "p2_l1": "Einfache Spannungszahl (Ursprungswerte)",
        "p2_l_vj": "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)",
        "p2_l_prefix": "Linie unveränderter wirtschaftlicher Aktivität (ab ",
        "p3_t": "Erweiterte Spannungszahl* (Gesamtzeitraum)",
        "p3_l": ("Erweiterte Spannungszahl (Ursprungswerte)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p4_t": "Erweiterte Spannungszahl* (Aktueller 13-Monats-Verlauf)",
        "p5_t": "Spannungszahl und reales BIP",
        "p5_l": ("Reales BIP (Ursprungswerte, linke Achse)",
                 "Einfache Spannungszahl (Ursprungswerte, rechte Achse)",
                 "Erweiterte Spannungszahl (inkl. Kurzarbeit, rechte Achse)"),
        "x_m": "Monatswerte",
        "x_mq": "Monatswerte (Spannungszahl) / Quartalswerte (reales BIP)",
        "src_ba": "Quelle: Statistisches Bundesamt (BA-Daten), eigene Berechnungen | Stand: ",
        "src_ba_kug": "Quelle: Statistisches Bundesamt (BA-Daten), eigene Berechnungen; *berücksichtigt Kurzarbeit | Stand: ",
        "src_all": "Quellen: Statistisches Bundesamt, eigene Berechnungen | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "m": MONATE_EN,
        "p1_t": "Simple Economic Tension Number (Full Period)",
        "p1_l": ("Simple Economic Tension Number (unadjusted data)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p2_t": "Simple Economic Tension Number (13-Month Trend)",
        "p2_l1": "Simple Economic Tension Number (unadjusted data)",
        "p2_l_vj": "Line of unchanged economic activity (starting from previous year's month)",
        "p2_l_prefix": "Line of unchanged economic activity (from ",
        "p3_t": "Extended Economic Tension Number* (Full Period)",
        "p3_l": ("Extended Economic Tension Number (unadjusted data)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p4_t": "Extended Economic Tension Number* (13-Month Trend)",
        "p5_t": "Economic Tension Number and Real GDP",
        "p5_l": ("Real GDP (unadjusted data, left axis)",
                 "Simple Economic Tension Number (unadjusted data, right axis)",
                 "Extended Economic Tension Number (incl. short-time work, right axis)"),
        "x_m": "Monthly values",
        "x_mq": "Monthly values (Economic Tension Number) / Quarterly values (real GDP)",
        "src_ba": "Source: Federal Statistical Office (FEA data), own calculations | As of: ",
        "src_ba_kug": "Source: Federal Statistical Office (FEA data), own calculations; *includes short-time work | As of: ",
        "src_all": "Sources: Federal Statistical Office, own calculations | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def fmt_num(val, use_comma, dec=1):
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

def _normalize_tsd(ser):
    if ser.empty:
        return ser
    s = ser.dropna().copy()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s.apply(lambda v: v / 1000.0 if abs(float(v)) > 15000 else float(v))
    return s

def _destatis_ffcsv(table, startyear="2018"):
    if not D_USER or not D_PASS:
        return pd.DataFrame()
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    def _unpack(resp):
        if resp.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
        return resp.text
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            return pd.DataFrame()
        raw = ""
        for _ in range(24):
            time.sleep(2.5)
            txt = _unpack(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3:
        return pd.DataFrame()
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)
    col_map = {c.lower(): c for c in df.columns}
    t_col, v_col = col_map.get("time") or col_map.get("zeit"), col_map.get("value") or col_map.get("wert")
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
    return df

def load_labor_market():
    s_alo = pd.Series(dtype=float)
    s_ste = pd.Series(dtype=float)
    s_kug = pd.Series(dtype=float)

    u = f"{BBK_BASE}BBDL1/M.DE.N.?format=csv&lang=de"
    r = requests.get(u, timeout=45)
    if r.status_code == 200 and len(r.text) >= 500:
        first_line = next(iter(r.text.splitlines()), "")
        sep = ";" if first_line.count(";") >= first_line.count(",") else ","
        df = pd.read_csv(io.StringIO(r.text), sep=sep, low_memory=False)
        time_col = next(iter(df.columns))
        is_date = df[time_col].astype(str).str.match(r"^(19\d{2}|20\d{2})-\d{2}")
        meta_df = df.loc[~is_date]
        data_df = df.loc[is_date]
        yms = data_df[time_col].astype(str).str.slice(0, 7).values
        for col in df.columns[1:]:
            if str(col).endswith("_FLAGS"):
                continue
            desc = " | ".join(str(x).strip() for x in meta_df[col].dropna().tolist()[:8])
            cl = f"{col} | {desc}".lower()
            if any(ex in cl for ex in ("quote", "%", "saisonbereinigt", "kalenderbereinigt", "männer", "frauen", "ausländer", "zugang", "abgang", "anzeige", "index", "geringfügig", "beschäftigte", "sozialversicherungspflichtig", "unterbeschäftigung")):
                continue
            vals = pd.to_numeric(data_df[col].astype(str).str.replace(",", "."), errors="coerce")
            valid = vals.notna()
            if valid.sum() < 36:
                continue
            nums = vals.loc[valid].values
            scale = 0.001 if np.nanmedian(nums) > 15000 else 1.0
            ser = pd.Series(nums * scale, index=yms[valid]).groupby(level=0).last().sort_index()
            if "arbeitslose" in cl and ("insgesamt" in cl or "deutschland" in cl):
                if s_alo.empty or ser.index[-1] > s_alo.index[-1]:
                    s_alo = ser
            elif ("gemeldete arbeitsstellen" in cl or "offene stellen" in cl) and ("insgesamt" in cl or "deutschland" in cl):
                if s_ste.empty or ser.index[-1] > s_ste.index[-1]:
                    s_ste = ser
            elif "kurzarbeiter" in cl and ("deutschland" in cl or "insgesamt" in cl):
                if s_kug.empty or ser.index[-1] > s_kug.index[-1]:
                    s_kug = ser

    try:
        df_ba = _destatis_ffcsv("13211-0002", "2022")
        if not df_ba.empty and "2_variable_attribute_label" in df_ba.columns:
            df_ba = df_ba[df_ba["2_variable_attribute_label"].astype(str).str.strip() == "Insgesamt"].copy()
        if not df_ba.empty:
            for code_v, target_s in (("ERW007", "ste"), ("ERW006", "alo"), ("ERW064", "kug")):
                sub = df_ba[df_ba["_CODES"].apply(lambda s: code_v in s)].copy()
                sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
                sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
                if not sub.empty:
                    vals = sub["V"].values
                    scale = 0.001 if np.nanmedian(vals) > 15000 else 1.0
                    s_new = pd.Series(vals * scale, index=sub["ZEIT"].astype(str).str.strip().values)
                    if target_s == "ste":
                        s_ste = s_new.combine_first(s_ste).sort_index()
                    elif target_s == "alo":
                        s_alo = s_new.combine_first(s_alo).sort_index()
                    else:
                        s_kug = s_new.combine_first(s_kug).sort_index()
    except Exception:
        pass

    return _normalize_tsd(s_ste), _normalize_tsd(s_alo), _normalize_tsd(s_kug)

def get_destatis_bip_q():
    try:
        df = _destatis_ffcsv("81000-0002", "2018")
        if df.empty:
            return pd.Series(dtype=float)
        req = {"DG", "WERTORG", "VGR014", "VGRPKM"}
        sub = df[df["_CODES"].apply(lambda s: req.issubset(s))].copy()
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
    except Exception:
        return pd.Series(dtype=float)

def style_sz_ax(fig, ax, title, ymin, ymax, yticks, xlabel_text, use_comma=True, xlabel_y=-0.31):
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=12.5, fontweight="bold", color="#0F172A")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_clean(x, use_comma, 2)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.8, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#64748B", linewidth=1.0, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.text(0.5, xlabel_y, xlabel_text, transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")

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

def line_unv(diff_series, anchor_ym, months):
    if anchor_ym not in diff_series.index:
        return pd.Series(dtype=float)
    d_t0 = float(diff_series.loc[anchor_ym])
    out = {}
    for ym in months:
        if ym < anchor_ym:
            continue
        y_num = int(ym[:4])
        m_num = int(ym[5:7])
        vj = f"{y_num - 1:04d}-{m_num:02d}"
        if vj in diff_series.index:
            out[ym] = d_t0 - float(diff_series.loc[vj])
    return pd.Series(out)

def save_sz_plotly(fig_p, title_p, src_text, now_str, fname_p, sfx, use_comma=True, height_p=460, top_m=95, tick_step=1):
    fig_p.update_layout(
        title=dict(text=f"<b>{title_p}</b>", x=0.03, y=0.96, yanchor="top", font=dict(size=16, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="v", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=top_m, b=95), height=height_p,
        annotations=[
            dict(text=f"{src_text}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    if use_comma:
        fig_p.update_layout(separators=",.")
    xaxis_kw = dict(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    if tick_step > 1 and len(fig_p.data) > 0:
        first_trace = next(iter(fig_p.data))
        if first_trace.x is not None:
            all_x = list(first_trace.x)
            t_vals = [x for i, x in enumerate(all_x) if i % tick_step == 0]
            xaxis_kw.update(tickmode="array", tickvals=t_vals, ticktext=t_vals)
    fig_p.update_xaxes(**xaxis_kw)
    fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.5, color="#475569"))
    out_path = f"static/spannungszahl/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def calc_sz_ylim(series_list):
    vals = []
    for s in series_list:
        if s is not None and len(s) > 0:
            vals.extend([float(v) for v in s.values if v is not None and not np.isnan(v)])
    if not vals:
        return -400.0, 300.0, np.arange(-400, 301, 100), 100.0
    lo_raw = min(min(vals), -300.0)
    hi_raw = max(max(vals), 200.0)
    span = max(hi_raw - lo_raw, 100.0)
    for step in (100.0, 200.0, 500.0, 1000.0):
        lo = np.floor((lo_raw - span * 0.08) / step) * step
        hi = np.ceil((hi_raw + span * 0.10) / step) * step
        if (hi - lo) / step <= 9:
            return lo, hi, np.arange(lo, hi + step * 0.1, step), step
    step = 1000.0
    lo = np.floor((lo_raw - span * 0.08) / step) * step
    hi = np.ceil((hi_raw + span * 0.10) / step) * step
    return lo, hi, np.arange(lo, hi + step * 0.1, step), step

def fmt_month_year(ym, m_names):
    return f"{m_names[int(ym[5:7]) - 1]} {ym[:4]}"

def build_spannungszahl(lang, s_ste, s_alo, s_kug, s_bip):
    t = TEXTS[lang]
    use_c = t["comma"]
    sfx = t["sfx"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])

    common_m = sorted(list(s_ste.index.intersection(s_alo.index).unique()))
    diff_einf = (s_ste.reindex(common_m) - s_alo.reindex(common_m)).dropna()
    kug_aligned = s_kug.reindex(diff_einf.index).fillna(0.0)
    diff_erw = (diff_einf - kug_aligned).dropna()

    m12 = sorted(list(diff_einf.index[-13:]))
    m_all = sorted(list(diff_einf.index[diff_einf.index >= "2019-01"]))
    anchors_12 = [m12[i] for i in (5, 8, 10) if len(m12) > i]
    styles_anc = [("#059669", ":"), ("#7C3AED", "-."), ("#DC2626", "--")]

    def _plot_series(diff_s, months_use, title_s, lbl_main, src_key, fname, top_adj=0.78, leg_fs=7.4, use_anchors=False, is_12m=False):
        y_main = diff_s.reindex(months_use)
        first_ym = next(iter(months_use))
        s_vj = line_unv(diff_s, first_ym, months_use)
        extra_s = [line_unv(diff_s, a, months_use) for a in anchors_12] if use_anchors else []
        ylo, yhi, yt, y_step = calc_sz_ylim([y_main, s_vj] + extra_s)

        fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=300, facecolor="white")
        bot_m = 0.28 if is_12m else 0.24
        plt.subplots_adjust(left=0.10, right=0.95, top=top_adj, bottom=bot_m)
        style_sz_ax(fig, ax, title_s, ylo, yhi, yt, t["x_m"], use_c, xlabel_y=(-0.39 if is_12m else -0.32))
        x = np.arange(len(months_use))
        mk_sz = 4 if is_12m else 0
        ax.plot(x, y_main.values, color="#1B3A6B", lw=(2.3 if is_12m else 1.8), marker=("o" if is_12m else None), ms=mk_sz, label=lbl_main, zorder=4)
        ax.plot(x, s_vj.reindex(months_use).values, color="#D97706", lw=(1.9 if is_12m else 1.5), ls="--", label=t["p2_l_vj"], zorder=3)

        fp = go.Figure()
        fp.add_trace(go.Scatter(x=months_use, y=[None if np.isnan(v) else round(float(v), 1) for v in y_main.values], customdata=[fmt_num(v, use_c) for v in y_main.values], name=lbl_main, mode=("lines+markers" if is_12m else "lines"), line=dict(color="#1B3A6B", width=2.2), hovertemplate=f"{lbl_main}: <b>%{{customdata}}</b><extra></extra>"))
        fp.add_trace(go.Scatter(x=months_use, y=[None if np.isnan(v) else round(float(v), 1) for v in s_vj.reindex(months_use).values], customdata=[fmt_num(v, use_c) for v in s_vj.reindex(months_use).values], name=t["p2_l_vj"], mode="lines", line=dict(color="#D97706", width=1.9, dash="dash"), hovertemplate=f"{t['p2_l_vj']}: <b>%{{customdata}}</b><extra></extra>"))

        if use_anchors:
            for anc, (col_a, ls_a) in zip(anchors_12, styles_anc):
                sa = line_unv(diff_s, anc, months_use).reindex(months_use)
                lbl_a = f"{t['p2_l_prefix']}{fmt_month_year(anc, t['m'])})"
                ax.plot(x, sa.values, color=col_a, lw=1.9, ls=ls_a, label=lbl_a, zorder=3)
                dash_p = "dot" if ls_a == ":" else ("dashdot" if ls_a == "-." else "dash")
                fp.add_trace(go.Scatter(x=months_use, y=[None if np.isnan(v) else round(float(v), 1) for v in sa.values], customdata=[fmt_num(v, use_c) for v in sa.values], name=lbl_a, mode="lines", line=dict(color=col_a, width=1.9, dash=dash_p), hovertemplate=f"{lbl_a}: <b>%{{customdata}}</b><extra></extra>"))

        draw_year_groups(ax, months_use, t["m"], step=(1 if is_12m else 3), year_y=(-0.31 if is_12m else -0.24))
        ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=leg_fs)
        fig.text(0.10, 0.015, f"{t[src_key]}{now_str}", fontsize=7.2, color="#64748B")
        fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
        plt.savefig(f"static/spannungszahl/{fname}{sfx}.png", dpi=300)
        plt.close()

        fp.update_yaxes(range=[ylo, yhi], dtick=y_step)
        save_sz_plotly(fp, title_s, t[src_key], now_str, fname, sfx, use_c, height_p=(520 if use_anchors else 455), top_m=(145 if use_anchors else 95), tick_step=(1 if is_12m else 6))

    p1_l0, _ = t["p1_l"]
    p3_l0, _ = t["p3_l"]
    _plot_series(diff_einf, m_all, t["p1_t"], p1_l0, "src_ba", "01_spannungszahl_einfach", top_adj=0.80, leg_fs=7.5, use_anchors=False, is_12m=False)
    _plot_series(diff_einf, m12, t["p2_t"], t["p2_l1"], "src_ba", "02_spannungszahl_linien", top_adj=0.71, leg_fs=6.8, use_anchors=True, is_12m=True)
    _plot_series(diff_erw, m_all, t["p3_t"], p3_l0, "src_ba_kug", "03_spannungszahl_erweitert", top_adj=0.80, leg_fs=7.5, use_anchors=False, is_12m=False)
    _plot_series(diff_erw, m12, t["p4_t"], p3_l0, "src_ba_kug", "04_spannungszahl_erweitert_linien", top_adj=0.71, leg_fs=6.8, use_anchors=True, is_12m=True)

    y_e_all = diff_einf.reindex(m_all)
    y_w_all = diff_erw.reindex(m_all)
    ylo5, yhi5, yt5, y_step5 = calc_sz_ylim([y_e_all, y_w_all])

    bip_map = {}
    for q_str, q_val in s_bip.items():
        if "-Q" not in q_str:
            continue
        yr, qn = q_str[:4], int(q_str[-1])
        mid_m = f"{yr}-{qn * 3 - 1:02d}"
        bip_map[mid_m] = float(q_val)
    bip_y_full = [bip_map.get(ym, None) for ym in m_all]
    bip_x_idx = [i for i, v in enumerate(bip_y_full) if v is not None]
    bip_y_vals = [bip_y_full[i] for i in bip_x_idx]

    fig, ax_r = plt.subplots(figsize=(8.4, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.89, top=0.76, bottom=0.24)
    style_sz_ax(fig, ax_r, t["p5_t"], ylo5, yhi5, yt5, t["x_mq"], use_c, xlabel_y=-0.32)
    ax_r.yaxis.tick_right()
    ax_r.yaxis.set_label_position("right")

    ax_l = ax_r.twinx()
    ax_l.yaxis.tick_left()
    ax_l.yaxis.set_label_position("left")
    ax_l.set_ylim(-12, 12)
    ax_l.set_yticks(np.arange(-12, 13, 4))
    ax_l.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_clean(x, use_c, 1)))
    ax_l.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    for s in ("top", "right", "left", "bottom"):
        ax_l.spines[s].set_visible(False)

    p5_l0, p5_l1, p5_l2 = t["p5_l"]
    x_all = np.arange(len(m_all))
    l_bip = ax_l.bar(bip_x_idx, bip_y_vals, width=2.2, color="#CBD5E1", alpha=0.65, label=p5_l0, zorder=1)
    l_einf, = ax_r.plot(x_all, y_e_all.values, color="#1B3A6B", lw=1.9, label=p5_l1, zorder=4)
    l_erw, = ax_r.plot(x_all, y_w_all.values, color="#D97706", lw=1.8, ls="--", label=p5_l2, zorder=5)

    draw_year_groups(ax_r, m_all, t["m"], step=3, year_y=-0.24)
    ax_r.legend(handles=[l_bip, l_einf, l_erw], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.2)
    fig.text(0.10, 0.015, f"{t['src_all']}{now_str}", fontsize=7.2, color="#64748B")
    fig.text(0.89, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/spannungszahl/05_spannungszahl_bip{sfx}.png", dpi=300)
    plt.close()

    fp5 = make_subplots(specs=[[{"secondary_y": True}]])
    fp5.add_trace(go.Bar(x=m_all, y=bip_y_full, customdata=[fmt_num(v, use_c) for v in bip_y_full], name=p5_l0, marker_color="#CBD5E1", opacity=0.75, hovertemplate=f"{p5_l0}: <b>%{{customdata}} %</b><extra></extra>"), secondary_y=False)
    fp5.add_trace(go.Scatter(x=m_all, y=[None if np.isnan(v) else round(float(v), 1) for v in y_e_all.values], customdata=[fmt_num(v, use_c) for v in y_e_all.values], name=p5_l1, mode="lines", line=dict(color="#1B3A6B", width=2.1), hovertemplate=f"{p5_l1}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    fp5.add_trace(go.Scatter(x=m_all, y=[None if np.isnan(v) else round(float(v), 1) for v in y_w_all.values], customdata=[fmt_num(v, use_c) for v in y_w_all.values], name=p5_l2, mode="lines", line=dict(color="#D97706", width=1.9, dash="dash"), hovertemplate=f"{p5_l2}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    save_sz_plotly(fp5, t["p5_t"], t["src_all"], now_str, "05_spannungszahl_bip", sfx, use_c, height_p=485, top_m=115, tick_step=6)
    fp5.update_yaxes(range=[-12, 12], dtick=4, fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", secondary_y=False)
    fp5.update_yaxes(range=[ylo5, yhi5], dtick=y_step5, fixedrange=True, showgrid=False, zeroline=False, secondary_y=True)
    out5 = f"static/spannungszahl/05_spannungszahl_bip{sfx}.html"
    fp5.write_html(out5, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out5, "r", encoding="utf-8") as fh:
        html5 = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out5, "w", encoding="utf-8") as fh:
        fh.write(html5)

def main():
    s_ste, s_alo, s_kug = load_labor_market()
    s_bip = get_destatis_bip_q()
    build_spannungszahl("de", s_ste, s_alo, s_kug, s_bip)
    build_spannungszahl("en", s_ste, s_alo, s_kug, s_bip)
    print(f"[OK] Spannungszahl (DE & EN) bis {s_ste.index[-1]} erzeugt.")

if __name__ == "__main__":
    main()
