import os, io, re, csv, json, time, glob, zipfile, requests
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
        "p1_t": "Spannungszahl",
        "p1_l": ("Einfache Spannungszahl (Ursprungswerte)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p2_t": "Spannungszahl",
        "p2_l1": "Einfache Spannungszahl (Ursprungswerte)",
        "p2_l_vj": "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)",
        "p2_l_prefix": "Linie unveränderter wirtschaftlicher Aktivität (ausgehend von ",
        "p3_t": "Erweiterte Spannungszahl*",
        "p3_l": ("Erweiterte Spannungszahl (Ursprungswerte)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p4_t": "Erweiterte Spannungszahl*",
        "p5_t": "Spannungszahl und reales BIP",
        "p5_l": ("Reales BIP (Ursprungswerte)",
                 "Einfache Spannungszahl (Ursprungswerte)",
                 "Erweiterte Spannungszahl (berücksichtigt Kurzarbeit)"),
        "p5_yl": "Reales BIP,\nVeränderung gg. Vj., %",
        "p5_yr": "Spannungszahl,\nLinie unv. wirtschaftl. Aktivität",
        "x_m": "Monatswerte",
        "x_mq": "Monatswerte (Spannungszahl) / Quartalswerte (reales BIP)",
        "src_ba": "Quelle: Statistisches Bundesamt (BA-Daten), eigene Berechnungen | Stand: ",
        "src_ba_kug": "Quelle: Statistisches Bundesamt (BA-Daten), eigene Berechnungen; *berücksichtigt Kurzarbeit | Stand: ",
        "src_all": "Quellen: Statistisches Bundesamt (BA-Daten), eigene Berechnungen | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "m": MONATE_EN,
        "p1_t": "Economic Tension Number",
        "p1_l": ("Simple Economic Tension Number (unadjusted data)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p2_t": "Economic Tension Number",
        "p2_l1": "Simple Economic Tension Number (unadjusted data)",
        "p2_l_vj": "Line of unchanged economic activity (starting from previous year's month)",
        "p2_l_prefix": "Line of unchanged economic activity (starting from ",
        "p3_t": "Extended Economic Tension Number*",
        "p3_l": ("Extended Economic Tension Number (unadjusted data)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p4_t": "Extended Economic Tension Number*",
        "p5_t": "Economic Tension Number and Real GDP",
        "p5_l": ("Real GDP (unadjusted data)",
                 "Simple Economic Tension Number (unadjusted data)",
                 "Extended Economic Tension Number (includes short-time work)"),
        "p5_yl": "Real GDP,\nyoy change, %",
        "p5_yr": "Economic Tension Number,\nline of unch. economic activity",
        "x_m": "Monthly values",
        "x_mq": "Monthly values (Economic Tension Number) / Quarterly values (real GDP)",
        "src_ba": "Source: Federal Statistical Office (Federal Employment Agency data), own calculations | As of: ",
        "src_ba_kug": "Source: Federal Statistical Office (Federal Employment Agency data), own calculations; *includes short-time work | As of: ",
        "src_all": "Sources: Federal Statistical Office (Federal Employment Agency data), own calculations | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def fmt_num(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s

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
            scale = 0.001 if np.nanmedian(nums) > 20000 else 1.0
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
        if not df_ba.empty:
            for code_v, target_s in (("ERW007", "ste"), ("ERW006", "alo"), ("ERW064", "kug")):
                sub = df_ba[df_ba["_CODES"].apply(lambda s: {"DF", code_v}.issubset(s))].copy()
                sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
                sub = sub.dropna(subset=["V"]).drop_duplicates(subset=["ZEIT"], keep="first").sort_values("ZEIT")
                if not sub.empty:
                    vals = sub["V"].values
                    scale = 0.001 if np.nanmedian(vals) > 20000 else 1.0
                    s_new = pd.Series(vals * scale, index=sub["ZEIT"].astype(str).str.strip().values)
                    if target_s == "ste":
                        s_ste = s_new.combine_first(s_ste).sort_index()
                    elif target_s == "alo":
                        s_alo = s_new.combine_first(s_alo).sort_index()
                    else:
                        s_kug = s_new.combine_first(s_kug).sort_index()
    except Exception:
        pass

    return s_ste, s_alo, s_kug

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

def style_sz_ax(fig, ax, title, ymin, ymax, yticks, xlabel_text, xlabel_y=-0.31):
    fig.suptitle(title, x=0.09, y=0.96, ha="left", fontsize=12.5, fontweight="bold", color="#0F172A")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
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

def save_sz_plotly(fig_p, title_p, src_text, now_str, fname_p, sfx, height_p=460, top_m=95):
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
    fig_p.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.5, color="#475569"))
    out_path = f"static/spannungszahl/{fname_p}{sfx}.html"
    fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def build_charts_for_lang(lang, d_einf, d_erw, sz_einf, sz_erw, bip_q):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    fmt_arr = lambda seq: [fmt_num(v, use_c) for v in seq]

    months_all = [ym for ym in sz_einf.index if ym >= "2019-01"]
    if len(months_all) < 2:
        months_all = list(sz_einf.index)
    x_all = np.arange(len(months_all))
    y_einf = [float(sz_einf.loc[ym]) for ym in months_all]
    y_erw = [float(sz_erw.loc[ym]) if ym in sz_erw.index else np.nan for ym in months_all]
    vj_anchor = months_all[max(0, len(months_all) - 13)]

    def save_fig(fig, src_text, fname):
        fig.text(0.09, 0.015, f"{src_text}{now_str}", fontsize=7.0, color="#64748B")
        fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
        plt.savefig(f"static/spannungszahl/{fname}{t['sfx']}.png", dpi=300)
        plt.close()

    # 1. Einfache Spannungszahl (Gesamt)
    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.77, bottom=0.25)
    ymin_1 = min(-1200, int(np.floor((min(y_einf) - 300) / 300.0) * 300))
    ymax_1 = max(1200, int(np.ceil((max(y_einf) + 300) / 300.0) * 300))
    style_sz_ax(fig, ax, t["p1_t"], ymin_1, ymax_1, range(ymin_1, ymax_1 + 300, 300), t["x_m"], xlabel_y=-0.31)
    l1_a, l1_b = t["p1_l"]
    ax.plot(x_all, y_einf, color="#1B3A6B", lw=2.3, label=l1_a, zorder=3)
    s_unv1 = line_unv(d_einf, vj_anchor, months_all)
    if not s_unv1.empty:
        xu1 = [months_all.index(ym) for ym in s_unv1.index]
        ax.plot(xu1, s_unv1.values, color="#D97706", lw=1.7, ls="--", label=l1_b, zorder=4)
    draw_year_groups(ax, months_all, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.6)
    save_fig(fig, t["src_ba"], "01_einfache_spannungszahl")

    fp1 = go.Figure()
    fp1.add_trace(go.Scatter(x=months_all, y=[round(v, 1) for v in y_einf], customdata=fmt_arr(y_einf), name=l1_a, mode="lines", line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l1_a}: <b>%{{customdata}}</b><extra></extra>"))
    if not s_unv1.empty:
        yu1 = [round(float(v), 1) for v in s_unv1.values]
        fp1.add_trace(go.Scatter(x=list(s_unv1.index), y=yu1, customdata=fmt_arr(yu1), name=l1_b, mode="lines", line=dict(color="#D97706", width=1.8, dash="dash"), hovertemplate=f"{l1_b}: <b>%{{customdata}}</b><extra></extra>"))
    save_sz_plotly(fp1, t["p1_t"], t["src_ba"], now_str, "01_einfache_spannungszahl", t["sfx"], height_p=460, top_m=105)

    # 2. Einfache Spannungszahl (Zoom 13 Monate)
    months_z = months_all[-13:]
    xz = np.arange(len(months_z))
    yz = [float(sz_einf.loc[ym]) for ym in months_z]
    fig, ax = plt.subplots(figsize=(8.0, 5.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.70, bottom=0.25)
    ymin_z = int(np.floor((min(yz) - 150) / 100.0) * 100)
    ymax_z = int(np.ceil((max(yz) + 150) / 100.0) * 100)
    style_sz_ax(fig, ax, t["p2_t"], ymin_z, ymax_z, range(ymin_z, ymax_z + 100, 100), t["x_m"], xlabel_y=-0.31)
    ax.plot(xz, yz, color="#1B3A6B", lw=2.4, marker="o", ms=3.5, label=t["p2_l1"], zorder=4)
    fp2 = go.Figure()
    fp2.add_trace(go.Scatter(x=months_z, y=[round(v, 1) for v in yz], customdata=fmt_arr(yz), name=t["p2_l1"], mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.4), hovertemplate=f"{t['p2_l1']}: <b>%{{customdata}}</b><extra></extra>"))

    anchors_z = [
        (months_z[0], t["p2_l_vj"], "#D97706", "--"),
        (months_z[max(0, len(months_z) - 7)], f"{t['p2_l_prefix']}{t['m'][int(months_z[max(0, len(months_z) - 7)][5:7]) - 1]} {months_z[max(0, len(months_z) - 7)][:4]})", "#059669", ":"),
        (months_z[max(0, len(months_z) - 4)], f"{t['p2_l_prefix']}{t['m'][int(months_z[max(0, len(months_z) - 4)][5:7]) - 1]} {months_z[max(0, len(months_z) - 4)][:4]})", "#7C3AED", "-.")
    ]
    for anc_ym, anc_lbl, anc_col, anc_ls in anchors_z:
        su = line_unv(d_einf, anc_ym, months_z)
        if len(su) >= 2:
            xsu = [months_z.index(ym) for ym in su.index]
            ax.plot(xsu, su.values, color=anc_col, lw=1.7, ls=anc_ls, label=anc_lbl, zorder=3)
            ysu = [round(float(v), 1) for v in su.values]
            p_dash = "dash" if anc_ls == "--" else ("dot" if anc_ls == ":" else "dashdot")
            fp2.add_trace(go.Scatter(x=list(su.index), y=ysu, customdata=fmt_arr(ysu), name=anc_lbl, mode="lines", line=dict(color=anc_col, width=1.8, dash=p_dash), hovertemplate=f"{anc_lbl}: <b>%{{customdata}}</b><extra></extra>"))

    draw_year_groups(ax, months_z, t["m"], step=1, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.3)
    save_fig(fig, t["src_ba"], "02_einfache_spannungszahl_zoom")
    save_sz_plotly(fp2, t["p2_t"], t["src_ba"], now_str, "02_einfache_spannungszahl_zoom", t["sfx"], height_p=540, top_m=150)

    # 3. Erweiterte Spannungszahl (Gesamt)
    months_erw = [ym for ym in sz_erw.index if ym >= "2019-01"]
    if len(months_erw) < 2:
        months_erw = list(sz_erw.index)
    x_erw = np.arange(len(months_erw))
    y_erw_v = [float(sz_erw.loc[ym]) for ym in months_erw]
    vj_erw = months_erw[max(0, len(months_erw) - 13)]
    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.77, bottom=0.25)
    ymin_3 = min(-8000, int(np.floor((min(y_erw_v) - 500) / 1000.0) * 1000))
    ymax_3 = max(4000, int(np.ceil((max(y_erw_v) + 500) / 1000.0) * 1000))
    style_sz_ax(fig, ax, t["p3_t"], ymin_3, ymax_3, range(ymin_3, ymax_3 + 1000, 1000), t["x_m"], xlabel_y=-0.31)
    l3_a, l3_b = t["p3_l"]
    ax.plot(x_erw, y_erw_v, color="#D97706", lw=2.3, label=l3_a, zorder=3)
    s_unv3 = line_unv(d_erw, vj_erw, months_erw)
    if not s_unv3.empty:
        xu3 = [months_erw.index(ym) for ym in s_unv3.index]
        ax.plot(xu3, s_unv3.values, color="#1B3A6B", lw=1.7, ls="--", label=l3_b, zorder=4)
    draw_year_groups(ax, months_erw, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.6)
    save_fig(fig, t["src_ba_kug"], "03_erweiterte_spannungszahl")

    fp3 = go.Figure()
    fp3.add_trace(go.Scatter(x=months_erw, y=[round(v, 1) for v in y_erw_v], customdata=fmt_arr(y_erw_v), name=l3_a, mode="lines", line=dict(color="#D97706", width=2.3), hovertemplate=f"{l3_a}: <b>%{{customdata}}</b><extra></extra>"))
    if not s_unv3.empty:
        yu3 = [round(float(v), 1) for v in s_unv3.values]
        fp3.add_trace(go.Scatter(x=list(s_unv3.index), y=yu3, customdata=fmt_arr(yu3), name=l3_b, mode="lines", line=dict(color="#1B3A6B", width=1.8, dash="dash"), hovertemplate=f"{l3_b}: <b>%{{customdata}}</b><extra></extra>"))
    save_sz_plotly(fp3, t["p3_t"], t["src_ba_kug"], now_str, "03_erweiterte_spannungszahl", t["sfx"], height_p=460, top_m=105)

    # 4. Erweiterte Spannungszahl (Zoom 13 Monate)
    months_ez = months_erw[-13:]
    xez = np.arange(len(months_ez))
    yez = [float(sz_erw.loc[ym]) for ym in months_ez]
    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.77, bottom=0.25)
    ymin_4 = int(np.floor((min(yez) - 150) / 100.0) * 100)
    ymax_4 = int(np.ceil((max(yez) + 150) / 100.0) * 100)
    style_sz_ax(fig, ax, t["p4_t"], ymin_4, ymax_4, range(ymin_4, ymax_4 + 100, 100), t["x_m"], xlabel_y=-0.31)
    ax.plot(xez, yez, color="#D97706", lw=2.4, marker="o", ms=3.5, label=l3_a, zorder=4)
    su4 = line_unv(d_erw, months_ez[0], months_ez)
    fp4 = go.Figure()
    fp4.add_trace(go.Scatter(x=months_ez, y=[round(v, 1) for v in yez], customdata=fmt_arr(yez), name=l3_a, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.4), hovertemplate=f"{l3_a}: <b>%{{customdata}}</b><extra></extra>"))
    if len(su4) >= 2:
        xsu4 = [months_ez.index(ym) for ym in su4.index]
        ax.plot(xsu4, su4.values, color="#1B3A6B", lw=1.7, ls="--", label=l3_b, zorder=3)
        ysu4 = [round(float(v), 1) for v in su4.values]
        fp4.add_trace(go.Scatter(x=list(su4.index), y=ysu4, customdata=fmt_arr(ysu4), name=l3_b, mode="lines", line=dict(color="#1B3A6B", width=1.8, dash="dash"), hovertemplate=f"{l3_b}: <b>%{{customdata}}</b><extra></extra>"))
    draw_year_groups(ax, months_ez, t["m"], step=1, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.6)
    save_fig(fig, t["src_ba_kug"], "04_erweiterte_spannungszahl_zoom")
    save_sz_plotly(fp4, t["p4_t"], t["src_ba_kug"], now_str, "04_erweiterte_spannungszahl_zoom", t["sfx"], height_p=460, top_m=105)

    # 5. Spannungszahl und reales BIP (Dual-Achse)
    fig, ax1 = plt.subplots(figsize=(8.0, 5.5), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.88, top=0.72, bottom=0.25)
    style_sz_ax(fig, ax1, t["p5_t"], -12, 12, range(-12, 16, 4), t["x_mq"], xlabel_y=-0.31)
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
    bx, by, b_months = [], [], []
    for k, v in bip_q.items():
        m_part = q_to_m.get(k[-2:], "")
        ym_key = f"{k[:4]}-{m_part}"
        if ym_key in months_all:
            bx.append(months_all.index(ym_key))
            by.append(float(v))
            b_months.append(ym_key)
    p_bip = ax1.plot(bx, by, color="#059669", lw=2.2, label=l5_bip, zorder=4)
    for xi_b, yi_b in zip(bx, by):
        off = 0.7 if yi_b >= 0 else -1.2
        ax1.text(xi_b, yi_b + off, fmt_num(yi_b, t["comma"]), fontsize=6.7, color="#059669", ha="center", fontweight="bold")
    p_einf = ax2.plot(x_all, y_einf, color="#1B3A6B", lw=2.1, label=l5_einf, zorder=3)
    p_erw = ax2.plot(x_all, y_erw, color="#D97706", lw=2.1, label=l5_erw, zorder=3)
    draw_year_groups(ax1, months_all, t["m"], step=4, year_y=-0.24)
    lines = p_bip + p_einf + p_erw
    ax1.legend(lines, [l.get_label() for l in lines], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.6)
    save_fig(fig, t["src_all"], "05_spannungszahl_bip")

    fp5 = make_subplots(specs=[[{"secondary_y": True}]])
    fp5.add_trace(go.Scatter(x=b_months, y=[round(v, 1) for v in by], customdata=fmt_arr(by), name=l5_bip, mode="lines+markers", marker=dict(size=6), line=dict(color="#059669", width=2.3), connectgaps=True, hovertemplate=f"{l5_bip}: <b>%{{customdata}} %</b><extra></extra>"), secondary_y=False)
    fp5.add_trace(go.Scatter(x=months_all, y=[round(v, 1) for v in y_einf], customdata=fmt_arr(y_einf), name=l5_einf, mode="lines", line=dict(color="#1B3A6B", width=2.1), hovertemplate=f"{l5_einf}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    y_erw_clean = [None if np.isnan(v) else round(float(v), 1) for v in y_erw]
    fp5.add_trace(go.Scatter(x=months_all, y=y_erw_clean, customdata=fmt_arr(y_erw_clean), name=l5_erw, mode="lines", line=dict(color="#D97706", width=2.1), hovertemplate=f"{l5_erw}: <b>%{{customdata}}</b><extra></extra>"), secondary_y=True)
    fp5.update_yaxes(title_text=t["p5_yl"].replace("\n", " "), range=[-12, 12], dtick=4, fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, secondary_y=False)
    fp5.update_yaxes(title_text=t["p5_yr"].replace("\n", " "), range=[-8000, 8000], dtick=2000, fixedrange=True, showgrid=False, secondary_y=True)
    save_sz_plotly(fp5, t["p5_t"], t["src_all"], now_str, "05_spannungszahl_bip", t["sfx"], height_p=490, top_m=125)

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
    build_charts_for_lang("de", d_einf, d_erw, sz_einf, sz_erw, bip_q)
    build_charts_for_lang("en", d_einf, d_erw, sz_einf, sz_erw, bip_q)

if __name__ == "__main__":
    main()
