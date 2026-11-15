import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/dashboard", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de" + "/genesisWS/rest/2020/data"
BBK_BASE = "https://bundesbank.de"

TEXTS = {
    "de": {
        "p1_t": "Bruttoinlandsprodukt: Entstehung", "p1_s": "Veränderung zum Vorjahr in % (preisbereinigt, Ursprungswerte)",
        "p1_l": ("Reales BIP", "Produzierendes Gewerbe ohne Baugewerbe", "Baugewerbe", "Handel, Verkehr, Gastgewerbe"),
        "p1_h": ("Reales BIP", "Prod. Gew. o. Bau", "Baugewerbe", "Handel/Verkehr/Gastg."),
        "p2_t": "Bruttoinlandsprodukt: Verwendung", "p2_s": "Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p2_l": ("Nominales BIP", "Privater Konsum", "Konsumausgaben der priv. Haushalte", "Ausrüstungsinvestitionen", "Bauinvestitionen", "Exporte", "Importe"),
        "p2_h": ("Nom. BIP", "Priv. Konsum", "Konsum priv. HH", "Ausrüstungen", "Bauten", "Exporte", "Importe"),
        "p3_t": "Auftragseingänge", "p3_s": "Volumenindex, Veränderung zum Vorjahr in %",
        "p3_l": ("Auftragseingang Industrie", "Auftragseingang Bauwirtschaft"),
        "p4_t": "Produktion & Einzelhandelsumsätze", "p4_s": "Real, Veränderung zum Vorjahr in %",
        "p4_l": ("Industrieproduktion", "Bauproduktion", "Einzelhandelsumsätze"),
        "p5_t": "Leistungsbilanzsaldo", "p5_s": "Monatlicher Saldo in Mrd. Euro", "p5_l": "Leistungsbilanzsaldo",
        "p6_t": "Arbeitslosigkeit und Inflation", "p6_s": "Quote bzw. Veränderung zum Vorjahr in %",
        "p6_l": ("Arbeitslosenquote", "Vollbeschäftigung (3%)", "Inflation (HVPI)", "EZB-Inflationsziel (2%)"),
        "unit_lb": "Mrd. €",
        "src_all": "Quellen: Statistisches Bundesamt, Deutsche Bundesbank | Stand: ",
        "src_destatis": "Quelle: Statistisches Bundesamt | Stand: ",
        "src_bbk": "Quelle: Deutsche Bundesbank | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "p1_t": "Gross Domestic Product: Production", "p1_s": "Change on previous year in % (price-adjusted, unadjusted data)",
        "p1_l": ("Real GDP", "Industry excluding construction", "Construction", "Trade, transport, accommodation and food services"),
        "p1_h": ("Real GDP", "Industry excl. constr.", "Construction", "Trade/transp./hosp."),
        "p2_t": "Gross Domestic Product: Expenditure", "p2_s": "Change on previous year in % (unadjusted data)",
        "p2_l": ("Nominal GDP", "Private consumption", "Household final consumption expenditure", "Machinery and equipment investment", "Construction investment", "Exports", "Imports"),
        "p2_h": ("Nom. GDP", "Priv. cons.", "Household cons.", "Machinery/equip.", "Construction", "Exports", "Imports"),
        "p3_t": "New Orders", "p3_s": "Volume index, change on previous year in %",
        "p3_l": ("New orders: Manufacturing", "New orders: Construction"),
        "p4_t": "Production & Retail Sales", "p4_s": "Real, change on previous year in %",
        "p4_l": ("Industrial production", "Construction output", "Retail sales"),
        "p5_t": "Current Account Balance", "p5_s": "Monthly balance in billion euros", "p5_l": "Current account balance",
        "p6_t": "Unemployment and Inflation", "p6_s": "Rate / change on previous year in %",
        "p6_l": ("Unemployment rate", "Full employment (3%)", "Inflation (HICP)", "ECB inflation target (2%)"),
        "unit_lb": "bn €",
        "src_all": "Sources: Federal Statistical Office, Deutsche Bundesbank | As of: ",
        "src_destatis": "Source: Federal Statistical Office | As of: ",
        "src_bbk": "Source: Deutsche Bundesbank | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def get_bbk(keys, n=13, scale=1.0):
    if isinstance(keys, str):
        keys = [keys]
    for key in keys:
        flow, k = key.split(".", 1)
        url = f"{BBK_BASE}/{flow}/{k}?format=csv&lang=de&lastNObservations={n+2}"
        r = requests.get(url, timeout=25)
        if r.status_code != 200:
            continue
        rows = []
        for ln in r.text.splitlines():
            parts = [p.strip().strip('"') for p in ln.split(";")]
            if len(parts) >= 2 and re.match(r"^\d{4}-\d{2}$", parts):
                try:
                    val = float(parts.replace(",", ".")) * scale
                    rows.append((parts, val))
                except ValueError:
                    pass
        if rows:
            df_s = pd.DataFrame(rows, columns=["t", "v"]).drop_duplicates(subset=["t"], keep="last")
            return pd.Series(df_s["v"].values, index=df_s["t"].values).tail(n)
    raise RuntimeError(f"Bundesbank-Abruf lieferte keine Daten für: {keys}")

def _extract_payload(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
            return zf.read(csv_name).decode("utf-8", errors="replace")
    return resp.text

def get_destatis(table, startyear="2021"):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    r.raise_for_status()
    raw_text = _extract_payload(r)
    if raw_text.lstrip().startswith("{"):
        r_job = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        r_job.raise_for_status()
        info = json.loads(r_job.text)
        msg = str(info.get("Status", {}).get("Content", ""))
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", msg)
        if not m:
            raise RuntimeError(f"Destatis Job-ID nicht gefunden für {table}: {info}")
        job_name = m.group(1)
        raw_text = ""
        for _ in range(24):
            time.sleep(2.5)
            r_res = requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": job_name, "area": "all", "compress": "false", "language": "de"}, timeout=60)
            txt = _extract_payload(r_res)
            if not txt.lstrip().startswith("{"):
                raw_text = txt
                break
        if not raw_text:
            raise RuntimeError(f"Destatis Job {job_name} für {table} nicht rechtzeitig fertig.")
    reader = csv.reader(io.StringIO(raw_text), delimiter=";", quotechar='"')
    rows = [row for row in reader if len(row) >= 5]
    if len(rows) < 3:
        raise RuntimeError(f"Destatis Tabelle {table} zu wenig Zeilen: {raw_text[:300]}")
    header = rows[0]
    width = len(header)
    clean_rows = [row[:width] for row in rows[1:] if len(row) >= width]
    df = pd.DataFrame(clean_rows, columns=header)
    col_map = {c.lower().strip(): c for c in df.columns}
    t_col = col_map.get("time") or col_map.get("zeit")
    v_col = col_map.get("value") or col_map.get("wert")
    if not t_col or not v_col:
        raise RuntimeError(f"Unerwartete Spalten in {table}: {list(df.columns)}")
    zeit_s = df[t_col].astype(str).str.strip()
    for c in df.columns:
        s_code = df[c].astype(str).str.strip()
        if s_code.str.match(r"^QUART0?[1-4]$").any():
            zeit_s = zeit_s + "-Q" + s_code.str[-1:]
            break
        if s_code.str.match(r"^MONAT(0?[1-9]|1[0-2])$").any():
            m_num = s_code.str.replace("MONAT", "", regex=False).str.zfill(2)
            zeit_s = zeit_s + "-" + m_num
            break
    df["ZEIT"] = zeit_s
    df["WERT"] = df[v_col]
    skip_cols = {"ZEIT", "WERT", t_col, v_col}
    text_cols = [c for c in df.columns if c not in skip_cols]
    df["_ROW"] = df.loc[:, text_cols].fillna("").astype(str).agg(" | ".join, axis=1)
    return df

def parse_destatis_series(df, include_terms, exclude_terms, target_times):
    if df.empty or "ZEIT" not in df.columns or "WERT" not in df.columns:
        return [np.nan] * len(target_times)
    sub = df.copy()
    for term in include_terms:
        sub = sub[sub["_ROW"].str.contains(term, case=False, regex=False, na=False)]
    for term in exclude_terms:
        sub = sub[~sub["_ROW"].str.contains(term, case=False, regex=False, na=False)]
    sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=("V",))
    m = dict(zip(sub["ZEIT"].astype(str).str.strip(), sub["V"]))
    return [m.get(t, m.get(t.replace("-", ""), m.get(t.replace("-Q", "Q"), np.nan))) for t in target_times]

def fmt_num(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.1f}"
    return s.replace(".", ",") if use_comma else s

def style_panel(ax, title, sub, ymin, ymax, yticks, z=True, title_y=1.40, sub_y=1.32):
    ax.set_facecolor("#F8FAFC")
    ax.text(0.0, title_y, title, transform=ax.transAxes, fontsize=11.5, fontweight="bold", color="#0F172A")
    ax.text(0.0, sub_y, sub, transform=ax.transAxes, fontsize=8.2, color="#64748B")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8, rotation=45, length=3, color="#CBD5E1")
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    if z:
        ax.axhline(0, color="#64748B", linewidth=1.1, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.text(1.0, -0.22, "T.H.", transform=ax.transAxes, ha="right", fontsize=7.5, color="#94A3B8")

def set_legend(ax, ncol=2):
    handles, labels = ax.get_legend_handles_labels()
    if len(handles) > 1 and not hasattr(handles[-1], "get_xydata"):
        handles = handles[-1:] + handles[:-1]
        labels = labels[-1:] + labels[:-1]
    ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=ncol, frameon=False, fontsize=6.9)

def mark_end(ax, x_vals, y_vals, col, use_comma, off=0.0):
    valid = [(x, float(y)) for x, y in zip(x_vals, y_vals) if not np.isnan(y)]
    if not valid:
        return
    lx, ly = valid.pop()
    ax.plot(lx, ly, marker="o", markersize=4.5, color=col, zorder=5)
    ax.text(lx + 0.35, ly + off, fmt_num(ly, use_comma), fontsize=8, fontweight="bold", color=col, va="center")

def draw_bars_with_labels(ax, xi, vals, label, use_comma):
    bars = ax.bar(xi, vals, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A", lw=1.1, label=label, zorder=2)
    for b in bars:
        h = b.get_height()
        if not np.isnan(h):
            off = 0.25 if h >= 0 else -0.35
            va = "bottom" if h >= 0 else "top"
            ax.text(b.get_x() + b.get_width() / 2, h + off, fmt_num(h, use_comma), ha="center", va=va, fontsize=6.2, color="#1E3A8A", fontweight="bold", zorder=4)

def draw_p1(ax, t, d):
    xi, xl_bip = d["xi"], d["xl_bip"]
    style_panel(ax, t["p1_t"], t["p1_s"], -10, 8, range(-10, 10, 2))
    l1_0, l1_1, l1_2, l1_3 = t["p1_l"]
    draw_bars_with_labels(ax, xi, d["bip_r"], l1_0, t["comma"])
    ax.plot(xi, d["pg"], color="#D97706", lw=1.9, marker="o", ms=2.5, label=l1_1, zorder=3)
    ax.plot(xi, d["bau"], color="#64748B", lw=1.9, marker="s", ms=2.5, label=l1_2, zorder=3)
    ax.plot(xi, d["hvg"], color="#059669", lw=1.9, marker="^", ms=2.8, label=l1_3, zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); set_legend(ax, 2)

def draw_p2(ax, t, d):
    xi, xl_bip = d["xi"], d["xl_bip"]
    style_panel(ax, t["p2_t"], t["p2_s"], -10, 15, range(-10, 20, 5), title_y=1.52, sub_y=1.43)
    l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]
    draw_bars_with_labels(ax, xi, d["bip_n"], l2_0, t["comma"])
    for vals, col, lbl, lstyle in (
        (d["kp"], "#D97706", l2_1, "-"),
        (d["kph"], "#059669", l2_2, "--"),
        (d["aus"], "#7C3AED", l2_3, "-"),
        (d["binv"], "#0284C7", l2_4, "-"),
        (d["exp"], "#DC2626", l2_5, "-"),
        (d["imp"], "#64748B", l2_6, "-")
    ):
        ax.plot(xi, vals, color=col, lw=1.7, ls=lstyle, label=lbl, zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); set_legend(ax, 2)

def draw_p3(ax, t, d):
    s_ai, s_ab = d["s_ai"], d["s_ab"]
    xm = np.arange(len(s_ai))
    style_panel(ax, t["p3_t"], t["p3_s"], -10, 20, range(-10, 25, 5))
    l3_0, l3_1 = t["p3_l"]
    ax.plot(xm, s_ai.values, color="#1B3A6B", lw=2.1, marker="o", ms=3, label=l3_0, zorder=3)
    ax.plot(xm, s_ab.values, color="#D97706", lw=2.0, marker="s", ms=3, label=l3_1, zorder=3)
    mark_end(ax, xm, s_ai.values, "#1B3A6B", t["comma"], 0.6)
    mark_end(ax, xm, s_ab.values, "#D97706", t["comma"], -0.6)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_ai.index)); set_legend(ax, 1)

def draw_p4(ax, t, d):
    s_pi, s_pb, s_eh = d["s_pi"], d["s_pb"], d["s_eh"]
    xm = np.arange(len(s_pi))
    style_panel(ax, t["p4_t"], t["p4_s"], -6, 6, range(-6, 8, 2))
    l4_0, l4_1, l4_2 = t["p4_l"]
    ax.plot(xm, s_pi.values, color="#1B3A6B", lw=2.1, marker="o", ms=3, label=l4_0, zorder=3)
    ax.plot(xm, s_pb.values, color="#D97706", lw=2.0, marker="s", ms=3, label=l4_1, zorder=3)
    ax.plot(xm, s_eh.values, color="#059669", lw=2.0, marker="^", ms=3.5, label=l4_2, zorder=3)
    mark_end(ax, xm, s_pi.values, "#1B3A6B", t["comma"], -0.3)
    mark_end(ax, xm, s_pb.values, "#D97706", t["comma"], 0.3)
    mark_end(ax, xm, s_eh.values, "#059669", t["comma"], 0.3)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_pi.index)); set_legend(ax, 2)

def draw_p5(ax, t, d):
    s_lb = d["s_lb"]
    xm = np.arange(len(s_lb))
    style_panel(ax, t["p5_t"], t["p5_s"], 0, 30, range(0, 35, 5))
    draw_bars_with_labels(ax, xm, s_lb.values, t["p5_l"], t["comma"])
    ax.set_xticks(xm); ax.set_xticklabels(list(s_lb.index)); set_legend(ax, 1)

def draw_p6(ax, t, d):
    s_al, s_hv = d["s_al"], d["s_hv"]
    xm = np.arange(len(s_al))
    style_panel(ax, t["p6_t"], t["p6_s"], 0, 8, range(0, 10, 2), z=False)
    l6_0, l6_1, l6_2, l6_3 = t["p6_l"]
    ax.plot(xm, s_al.values, color="#1B3A6B", lw=2.2, marker="o", ms=3.2, label=l6_0, zorder=3)
    ax.axhline(3.0, color="#1B3A6B", ls=":", lw=1.3, label=l6_1, zorder=2)
    ax.plot(xm, s_hv.values, color="#D97706", lw=2.2, marker="s", ms=3.2, label=l6_2, zorder=3)
    ax.axhline(2.0, color="#059669", ls=":", lw=1.3, label=l6_3, zorder=2)
    mark_end(ax, xm, s_al.values, "#1B3A6B", t["comma"], 0.25)
    mark_end(ax, xm, s_hv.values, "#D97706", t["comma"], 0.25)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_al.index)); set_legend(ax, 2)

def save_single(draw_fn, t, data, fname, src_key, top_adj=0.68):
    fig, ax = plt.subplots(figsize=(7.4, 4.9), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.93, top=top_adj, bottom=0.22)
    draw_fn(ax, t, data)
    now_s = datetime.now().strftime(t["date_fmt"])
    fig.text(0.09, 0.02, f"{t[src_key]}{now_s}", fontsize=7.5, color="#64748B")
    plt.savefig(f"static/dashboard/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

def build_for_lang(lang, data):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    fig, axes = plt.subplots(3, 2, figsize=(12.6, 18.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.06, right=0.95, top=0.88, bottom=0.06, hspace=0.68, wspace=0.20)
    ax1, ax2, ax3, ax4, ax5, ax6 = axes.flatten()
    draw_p1(ax1, t, data); draw_p2(ax2, t, data); draw_p3(ax3, t, data)
    draw_p4(ax4, t, data); draw_p5(ax5, t, data); draw_p6(ax6, t, data)
    now = datetime.now()
    fig.text(0.06, 0.015, f"{t['src_all']}{now.strftime(t['date_fmt'])}", fontsize=8, color="#64748B")
    plt.savefig(f"static/dashboard/dashboard{t['sfx']}.png", dpi=300)
    plt.close()

    save_single(draw_p1, t, data, "01_bip_entstehung", "src_destatis", top_adj=0.68)
    save_single(draw_p2, t, data, "02_bip_verwendung", "src_destatis", top_adj=0.60)
    save_single(draw_p3, t, data, "03_auftragseingaenge", "src_bbk", top_adj=0.68)
    save_single(draw_p4, t, data, "04_produktion_einzelhandel", "src_bbk", top_adj=0.68)
    save_single(draw_p5, t, data, "05_leistungsbilanz", "src_bbk", top_adj=0.68)
    save_single(draw_p6, t, data, "06_arbeitslosigkeit_inflation", "src_all", top_adj=0.68)

    # Interaktive Plotly-Charts (ohne Scrollbalken, echtes Komma in DE)
    now_str_p = datetime.now().strftime(t["date_fmt"])
    def fmt_arr(seq):
        return [fmt_num(v, use_c) for v in seq]

    def save_dash_plotly(fig_p, title_p, sub_p, src_key, fname_p, top_m=145, height_p=475):
        fig_p.update_layout(
            title=dict(text=f"<b>{title_p}</b><br><span style='font-size:11.5px;color:#475569;'>{sub_p}</span>", x=0.03, y=0.98, yanchor="top", font=dict(size=16, color="#0F172A", family="DejaVu Sans, sans-serif")),
            plot_bgcolor="#F8FAFC", paper_bgcolor="white",
            hovermode="x unified",
            dragmode=False,
            hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
            legend=dict(orientation="v", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
            margin=dict(l=46, r=16, t=top_m, b=82),
            height=height_p,
            annotations=[
                dict(text=f"{t[src_key]}{now_str_p}", x=0.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
                dict(text="T.H.", x=1.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
            ]
        )
        fig_p.update_xaxes(fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
        fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.5, color="#475569"))
        out_path = f"static/dashboard/{fname_p}{t['sfx']}.html"
        fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
        with open(out_path, "r", encoding="utf-8") as fh:
            html_s = fh.read()
        html_s = html_s.replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html_s)

    xq_p = [" " if x == "" else str(x) for x in data["xl_bip"]]

    # 1. BIP Entstehung (Interaktiv)
    fp1 = go.Figure()
    l1_0, l1_1, l1_2, l1_3 = t["p1_l"]
    h1_0, h1_1, h1_2, h1_3 = t["p1_h"]
    y1_0 = [None if np.isnan(v) else round(float(v), 1) for v in data["bip_r"]]
    fp1.add_trace(go.Bar(x=xq_p, y=y1_0, customdata=fmt_arr(y1_0), name=l1_0, marker_color="#1B3A6B", hovertemplate=f"{h1_0}: <b>%{{customdata}} %</b><extra></extra>"))
    for lbl_s, hov_s, key_s, col_s in ((l1_1, h1_1, "pg", "#D97706"), (l1_2, h1_2, "bau", "#64748B"), (l1_3, h1_3, "hvg", "#059669")):
        ys = [None if np.isnan(v) else round(float(v), 1) for v in data[key_s]]
        fp1.add_trace(go.Scatter(x=xq_p, y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.1), hovertemplate=f"{hov_s}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp1, t["p1_t"], t["p1_s"], "src_destatis", "01_bip_entstehung", top_m=165, height_p=500)

    # 2. BIP Verwendung (Interaktiv, grüne Linie gestrichelt)
    fp2 = go.Figure()
    l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]
    h2_0, h2_1, h2_2, h2_3, h2_4, h2_5, h2_6 = t["p2_h"]
    y2_0 = [None if np.isnan(v) else round(float(v), 1) for v in data["bip_n"]]
    fp2.add_trace(go.Bar(x=xq_p, y=y2_0, customdata=fmt_arr(y2_0), name=l2_0, marker_color="#1B3A6B", hovertemplate=f"{h2_0}: <b>%{{customdata}} %</b><extra></extra>"))
    for lbl_s, hov_s, key_s, col_s, d_style in (
        (l2_1, h2_1, "kp", "#D97706", "solid"),
        (l2_2, h2_2, "kph", "#059669", "dash"),
        (l2_3, h2_3, "aus", "#7C3AED", "solid"),
        (l2_4, h2_4, "binv", "#0284C7", "solid"),
        (l2_5, h2_5, "exp", "#DC2626", "solid"),
        (l2_6, h2_6, "imp", "#64748B", "solid")
    ):
        ys = [None if np.isnan(v) else round(float(v), 1) for v in data[key_s]]
        fp2.add_trace(go.Scatter(x=xq_p, y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.0, dash=d_style), hovertemplate=f"{hov_s}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp2, t["p2_t"], t["p2_s"], "src_destatis", "02_bip_verwendung", top_m=245, height_p=580)

    # 3. Auftragseingänge (Interaktiv)
    fp3 = go.Figure()
    l3_0, l3_1 = t["p3_l"]
    s_ai, s_ab = data["s_ai"], data["s_ab"]
    y3_0 = [None if np.isnan(v) else round(float(v), 1) for v in s_ai.values]
    y3_1 = [None if np.isnan(v) else round(float(v), 1) for v in s_ab.values]
    fp3.add_trace(go.Scatter(x=list(s_ai.index), y=y3_0, customdata=fmt_arr(y3_0), name=l3_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l3_0}: <b>%{{customdata}} %</b><extra></extra>"))
    fp3.add_trace(go.Scatter(x=list(s_ab.index), y=y3_1, customdata=fmt_arr(y3_1), name=l3_1, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.2), hovertemplate=f"{l3_1}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp3, t["p3_t"], t["p3_s"], "src_bbk", "03_auftragseingaenge", top_m=125, height_p=460)

    # 4. Produktion & Einzelhandelsumsätze (Interaktiv)
    fp4 = go.Figure()
    l4_0, l4_1, l4_2 = t["p4_l"]
    for lbl_s, key_s, col_s in ((l4_0, "s_pi", "#1B3A6B"), (l4_1, "s_pb", "#D97706"), (l4_2, "s_eh", "#059669")):
        ser_p = data[key_s]
        ys = [None if np.isnan(v) else round(float(v), 1) for v in ser_p.values]
        fp4.add_trace(go.Scatter(x=list(ser_p.index), y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.2), hovertemplate=f"{lbl_s}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp4, t["p4_t"], t["p4_s"], "src_bbk", "04_produktion_einzelhandel", top_m=145, height_p=480)

    # 5. Leistungsbilanzsaldo (Interaktiv)
    fp5 = go.Figure()
    s_lb = data["s_lb"]
    y5 = [None if np.isnan(v) else round(float(v), 1) for v in s_lb.values]
    fp5.add_trace(go.Bar(x=list(s_lb.index), y=y5, customdata=fmt_arr(y5), name=t["p5_l"], marker_color="#1B3A6B", hovertemplate=f"<b>%{{customdata}} {t['unit_lb']}</b><extra></extra>"))
    save_dash_plotly(fp5, t["p5_t"], t["p5_s"], "src_bbk", "05_leistungsbilanz", top_m=110, height_p=445)

    # 6. Arbeitslosigkeit und Inflation (Interaktiv)
    fp6 = go.Figure()
    l6_0, l6_1, l6_2, l6_3 = t["p6_l"]
    s_al, s_hv = data["s_al"], data["s_hv"]
    y6_0 = [None if np.isnan(v) else round(float(v), 1) for v in s_al.values]
    y6_2 = [None if np.isnan(v) else round(float(v), 1) for v in s_hv.values]
    fp6.add_trace(go.Scatter(x=list(s_al.index), y=y6_0, customdata=fmt_arr(y6_0), name=l6_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l6_0}: <b>%{{customdata}} %</b><extra></extra>"))
    fp6.add_trace(go.Scatter(x=list(s_hv.index), y=y6_2, customdata=fmt_arr(y6_2), name=l6_2, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.3), hovertemplate=f"{l6_2}: <b>%{{customdata}} %</b><extra></extra>"))
    fp6.add_hline(y=3.0, line_dash="dot", line_color="#1B3A6B", annotation_text=l6_1, annotation_position="top left", annotation_font=dict(size=10.5, color="#1B3A6B"))
    fp6.add_hline(y=2.0, line_dash="dot", line_color="#059669", annotation_text=l6_3, annotation_position="bottom left", annotation_font=dict(size=10.5, color="#059669"))
    save_dash_plotly(fp6, t["p6_t"], t["p6_s"], "src_all", "06_arbeitslosigkeit_inflation", top_m=125, height_p=460)

def align_series(series_list):
    all_idx = sorted(set().union(*(s.index for s in series_list if not s.empty)))[-13:]
    return [s.reindex(all_idx) for s in series_list]

def verify_non_empty(name, arr):
    vals = [float(v) for v in arr if not np.isnan(v)]
    if not vals:
        raise RuntimeError(f"Zeitreihe '{name}' enthält keine echten Daten!")
    print(f"[OK] {name}: {len(vals)} Werte (letzter: {vals[-1]:.1f})")

def main():
    df_y1 = get_destatis("81000-0001", "2021")
    df_q1 = get_destatis("81000-0011", "2021")
    df_y2 = get_destatis("81000-0002", "2021")
    df_q2 = get_destatis("81000-0012", "2021")
    df_y2_hh = get_destatis("81000-0019", "2021")
    df_q2_hh = get_destatis("81000-0020", "2021")

    yrs = tuple(sorted([z for z in df_y1["ZEIT"].astype(str).unique() if len(z) == 4 and z.isdigit()])[-5:])
    qtrs = tuple(sorted([z for z in df_q1["ZEIT"].astype(str).unique() if "Q" in z])[-14:])
    print(f"[ZEITRAUM] Jahre: {yrs} | Quartale: {qtrs}")

    xl_bip = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs)
    xi = np.arange(len(xl_bip))

    def get_bip_combo(df_y, df_q, inc, exc):
        vy = parse_destatis_series(df_y, inc + ["Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], yrs)
        vq = parse_destatis_series(df_q, inc + ["Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], qtrs)
        return np.array(vy + [np.nan] + vq, dtype=float)

    bip_r = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte"], ["Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"])
    pg = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Produzierendes Gewerbe ohne Baugewerbe"], [])
    bau = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Baugewerbe"], ["ohne Baugewerbe"])
    hvg = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Handel, Verkehr, Gastgewerbe"], [])

    bip_n = get_bip_combo(df_y2, df_q2, ["jeweiligen Preisen", "Ursprungswerte"], ["Konsum", "Investitionen", "Exporte", "Importe", "Beitrag"])
    kp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Private Konsumausgaben"], [])
    kph = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "privaten Haushalte"], ["Organisationen"])
    if np.all(np.isnan(kph)):
        kph = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "privater Haushalte"], ["Organisationen"])
    aus = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Ausrüstungen"], [])
    if np.all(np.isnan(aus)):
        aus = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Ausrüstungen"], [])
    binv = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Bauten"], [])
    if np.all(np.isnan(binv)):
        binv = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Bauten"], [])
    exp = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Exporte"], [])
    if np.all(np.isnan(exp)):
        exp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Exporte"], [])
    imp = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Importe"], [])
    if np.all(np.isnan(imp)):
        imp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Importe"], [])

    s_ai, s_ab = align_series([
        get_bbk(["BBDE1.M.DE.Y.BAA1.A2P000000.G.C.I21.A", "BBDE1.M.DE.Y.BAA1.A2P000000.G.C.I15.A"], 13),
        get_bbk(["BBDE1.M.DE.Y.BAA1.F00000000.G.C.I21.A", "BBDE1.M.DE.Y.BAA1.F00000000.G.C.I15.A", "BBDE1.M.DE.Y.BAA1.F41000000.G.C.I21.A"], 13)
    ])

    s_pi, s_pb, s_eh = align_series([
        get_bbk(["BBDE1.M.DE.Y.BPA1.A2P000000.G.C.I21.A", "BBDE1.M.DE.Y.BPA1.A2P000000.G.C.I15.A"], 13),
        get_bbk(["BBDE1.M.DE.Y.BPA1.F00000000.G.C.I21.A", "BBDE1.M.DE.Y.BPA1.F00000000.G.C.I15.A"], 13),
        get_bbk(["BBDE1.M.DE.Y.BVA1.G47000000.G.C.I21.A", "BBDE1.M.DE.Y.BVA1.G47000000.G.C.I15.A"], 13)
    ])

    s_lb = get_bbk(["BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL"], 13, 0.001)
    s_al = get_bbk(["BBDE1.M.DE.S.ABA1.A00000000.U.A.A00.A"], 13)
    m_cur = list(s_al.index)

    df_hv = get_destatis("61121-0002", "2024")
    hv_vals = parse_destatis_series(df_hv, ["Veränderung zum Vorjahresmonat"], ["Jahresdurchschnitt"], m_cur)
    if all(np.isnan(v) for v in hv_vals):
        m_names_de = ("Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember")
        hv_vals = []
        for ym in m_cur:
            mn = m_names_de[int(ym[5:7]) - 1]
            v_m = parse_destatis_series(df_hv, ["Veränderung zum Vorjahresmonat", mn], ["Jahresdurchschnitt"], [ym[:4]])
            hv_vals.append(next(iter(v_m), np.nan))
    s_hv = pd.Series(hv_vals, index=m_cur)

    for nm, arr in (
        ("Reales BIP", bip_r), ("Prod. Gewerbe", pg), ("Baugewerbe", bau), ("Handel/Verkehr", hvg),
        ("Nominales BIP", bip_n), ("Privater Konsum", kp), ("Konsum priv. Haushalte", kph),
        ("Ausrüstungen", aus), ("Bauten", binv), ("Exporte", exp), ("Importe", imp),
        ("Auftragseingang Ind.", s_ai.values), ("Auftragseingang Bau", s_ab.values),
        ("Produktion Ind.", s_pi.values), ("Einzelhandel", s_eh.values),
        ("Leistungsbilanz", s_lb.values), ("Arbeitslosenquote", s_al.values),
        ("HVPI Inflation", s_hv.values)
    ):
        verify_non_empty(nm, arr)

    data = {
        "xi": xi, "xl_bip": xl_bip,
        "bip_r": bip_r, "pg": pg, "bau": bau, "hvg": hvg,
        "bip_n": bip_n, "kp": kp, "kph": kph, "aus": aus, "binv": binv, "exp": exp, "imp": imp,
        "s_ai": s_ai, "s_ab": s_ab, "s_pi": s_pi, "s_pb": s_pb, "s_eh": s_eh,
        "s_lb": s_lb, "s_al": s_al, "s_hv": s_hv
    }
    build_for_lang("de", data)
    build_for_lang("en", data)

if __name__ == "__main__":
    main()
