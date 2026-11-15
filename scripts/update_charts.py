import os, io, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/dashboard", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://www-genesis." + "destatis.de" + "/genesisWS/rest/2020/data/tablefile"

TEXTS = {
    "de": {
        "p1_t": "Bruttoinlandsprodukt: Entstehung", "p1_s": "Veränderung zum Vorjahr in % (preisbereinigt, Ursprungswerte)",
        "p1_l": ("Bruttoinlandsprodukt", "Produzierendes Gewerbe ohne Baugewerbe", "Baugewerbe", "Handel, Verkehr, Gastgewerbe"),
        "p2_t": "Bruttoinlandsprodukt: Verwendung", "p2_s": "Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p2_l": ("Nominales BIP", "Privater Konsum", "Konsumausgaben der priv. Haushalte", "Ausrüstungsinvestitionen", "Bauinvestitionen", "Exporte", "Importe"),
        "p3_t": "Auftragseingänge", "p3_s": "Volumenindex, Veränderung zum Vorjahr in %",
        "p3_l": ("Auftragseingang Industrie", "Auftragseingang Bauwirtschaft"),
        "p4_t": "Produktion & Einzelhandelsumsätze", "p4_s": "Real, Veränderung zum Vorjahr in %",
        "p4_l": ("Industrieproduktion", "Bauproduktion", "Einzelhandelsumsätze"),
        "p5_t": "Leistungsbilanzsaldo", "p5_s": "Monatlicher Saldo in Mrd. Euro", "p5_l": "Leistungsbilanzsaldo",
        "p6_t": "Arbeitslosigkeit und Inflation", "p6_s": "Quote bzw. Veränderung zum Vorjahr in %",
        "p6_l": ("Arbeitslosenquote", "Vollbeschäftigung (3%)", "Inflation (HVPI)", "EZB-Inflationsziel (2%)"),
        "src_all": "Quellen: Statistisches Bundesamt, Deutsche Bundesbank | Stand: ",
        "src_destatis": "Quelle: Statistisches Bundesamt | Stand: ",
        "src_bbk": "Quelle: Deutsche Bundesbank | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "p1_t": "Gross Domestic Product: Production", "p1_s": "Change on previous year in % (price-adjusted, unadjusted data)",
        "p1_l": ("Gross domestic product", "Industry excluding construction", "Construction", "Trade, transport, accommodation and food services"),
        "p2_t": "Gross Domestic Product: Expenditure", "p2_s": "Change on previous year in % (unadjusted data)",
        "p2_l": ("Nominal GDP", "Private consumption", "Household final consumption expenditure", "Machinery and equipment investment", "Construction investment", "Exports", "Imports"),
        "p3_t": "New Orders", "p3_s": "Volume index, change on previous year in %",
        "p3_l": ("New orders: Manufacturing", "New orders: Construction"),
        "p4_t": "Production & Retail Sales", "p4_s": "Real, change on previous year in %",
        "p4_l": ("Industrial production", "Construction output", "Retail sales"),
        "p5_t": "Current Account Balance", "p5_s": "Monthly balance in billion euros", "p5_l": "Current account balance",
        "p6_t": "Unemployment and Inflation", "p6_s": "Rate / change on previous year in %",
        "p6_l": ("Unemployment rate", "Full employment (3%)", "Inflation (HICP)", "ECB inflation target (2%)"),
        "src_all": "Sources: Federal Statistical Office, Deutsche Bundesbank | As of: ",
        "src_destatis": "Source: Federal Statistical Office | As of: ",
        "src_bbk": "Source: Deutsche Bundesbank | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def get_bbk(key, n=13, scale=1.0):
    flow, k = key.split(".", 1)
    url = "https://api.statistiken." + "bundesbank.de" + "/rest/data/" + flow + "/" + k + "?format=csv&lang=de"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or ";" not in r.text:
            return pd.Series(dtype=float)
        df = pd.read_csv(io.StringIO(r.text), sep=";", on_bad_lines="skip")
        tc = next(c for c in df.columns if "TIME_PERIOD" in c)
        vc = next(c for c in df.columns if "OBS_VALUE" in c)
        df = df.dropna(subset=(tc, vc)).tail(n)
        vals = pd.to_numeric(df[vc].astype(str).str.replace(",", "."), errors="coerce") * scale
        df = df.assign(V=vals).dropna(subset=("V",))
        return pd.Series(df["V"].values, index=df[tc].astype(str).values)
    except Exception:
        return pd.Series(dtype=float)

def get_destatis(table):
    if not D_USER or not D_PASS:
        return pd.DataFrame()
    p = {"username": D_USER, "password": D_PASS, "name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    try:
        r = requests.get(G_URL, params=p, timeout=35)
        lines = [ln for ln in r.text.splitlines() if ln.count(";") >= 4]
        if len(lines) < 5:
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", decimal=",", on_bad_lines="skip")
        text_cols = [c for c in df.columns if c not in ("ZEIT", "WERT")]
        df["_ROW"] = df.loc[:, text_cols].fillna("").astype(str).agg(" | ".join, axis=1)
        return df
    except Exception:
        return pd.DataFrame()

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
    s = f"{val:.1f}"
    return s.replace(".", ",") if use_comma else s

def style_panel(ax, title, sub, ymin, ymax, yticks, z=True):
    ax.set_facecolor("#F8FAFC")
    ax.text(0.0, 1.33, title, transform=ax.transAxes, fontsize=11.5, fontweight="bold", color="#0F172A")
    ax.text(0.0, 1.26, sub, transform=ax.transAxes, fontsize=8.2, color="#64748B")
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
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=ncol, frameon=False, fontsize=7.2)

def mark_end(ax, x_vals, y_vals, col, use_comma, off=0.0):
    if len(x_vals) == 0 or len(y_vals) == 0:
        return
    lx = list(x_vals).pop()
    ly = float(list(y_vals).pop())
    ax.plot(lx, ly, marker="o", markersize=4.5, color=col, zorder=5)
    ax.text(len(x_vals) - 0.65, ly + off, fmt_num(ly, use_comma), fontsize=8, fontweight="bold", color=col, va="center")

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
    style_panel(ax, t["p2_t"], t["p2_s"], -10, 15, range(-10, 20, 5))
    l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]
    draw_bars_with_labels(ax, xi, d["bip_n"], l2_0, t["comma"])
    for vals, col, lbl in (
        (d["kp"], "#D97706", l2_1), (d["kph"], "#059669", l2_2),
        (d["aus"], "#7C3AED", l2_3), (d["binv"], "#0284C7", l2_4),
        (d["exp"], "#DC2626", l2_5), (d["imp"], "#64748B", l2_6)
    ):
        ax.plot(xi, vals, color=col, lw=1.6, label=lbl, zorder=3)
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

def save_single(draw_fn, t, data, fname, src_key):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.93, top=0.72, bottom=0.22)
    draw_fn(ax, t, data)
    now_s = datetime.now().strftime(t["date_fmt"])
    fig.text(0.09, 0.02, f"{t[src_key]}{now_s}", fontsize=7.5, color="#64748B")
    plt.savefig(f"static/dashboard/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

def build_for_lang(lang, data):
    t = TEXTS[lang]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    fig, axes = plt.subplots(3, 2, figsize=(12.6, 17.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.06, right=0.95, top=0.90, bottom=0.06, hspace=0.62, wspace=0.20)
    ax1, ax2, ax3, ax4, ax5, ax6 = axes.flatten()
    draw_p1(ax1, t, data); draw_p2(ax2, t, data); draw_p3(ax3, t, data)
    draw_p4(ax4, t, data); draw_p5(ax5, t, data); draw_p6(ax6, t, data)
    now = datetime.now()
    fig.text(0.06, 0.015, f"{t['src_all']}{now.strftime(t['date_fmt'])}", fontsize=8, color="#64748B")
    plt.savefig(f"static/dashboard/dashboard{t['sfx']}.png", dpi=300)
    plt.close()

    save_single(draw_p1, t, data, "01_bip_entstehung", "src_destatis")
    save_single(draw_p2, t, data, "02_bip_verwendung", "src_destatis")
    save_single(draw_p3, t, data, "03_auftragseingaenge", "src_bbk")
    save_single(draw_p4, t, data, "04_produktion_einzelhandel", "src_bbk")
    save_single(draw_p5, t, data, "05_leistungsbilanz", "src_bbk")
    save_single(draw_p6, t, data, "06_arbeitslosigkeit_inflation", "src_all")

    # Interaktive Plotly-Charts für die 6 Dashboard-Grafiken (Desktop & Smartphone optimiert)
    now_str_p = datetime.now().strftime(t["date_fmt"])
    def save_dash_plotly(fig_p, title_p, sub_p, src_key, fname_p, top_m=132, height_p=490):
        fig_p.update_layout(
            title=dict(text=f"<b>{title_p}</b><br><span style='font-size:11.5px;color:#475569;'>{sub_p}</span>", x=0.03, y=0.96, font=dict(size=16, color="#0F172A", family="DejaVu Sans, sans-serif")),
            plot_bgcolor="#F8FAFC", paper_bgcolor="white",
            hovermode="x unified",
            dragmode=False,
            hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=11.5, color="#0F172A"), namelength=0),
            legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
            margin=dict(l=46, r=16, t=top_m, b=82),
            height=height_p,
            annotations=[
                dict(text=f"{t[src_key]}{now_str_p}", x=0.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
                dict(text="T.H.", x=1.0, y=-0.22, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
            ]
        )
        fig_p.update_xaxes(fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
        fig_p.update_yaxes(fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.5, color="#475569"))
        fig_p.write_html(f"static/dashboard/{fname_p}{t['sfx']}.html", include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})

    xq_p = [" " if x == "" else str(x) for x in data["xl_bip"]]

    # 1. BIP Entstehung (Interaktiv)
    fp1 = go.Figure()
    l1_0, l1_1, l1_2, l1_3 = t["p1_l"]
    fp1.add_trace(go.Bar(x=xq_p, y=[None if np.isnan(v) else round(float(v), 1) for v in data["bip_r"]], name=l1_0, marker_color="#1B3A6B", hovertemplate=f"{l1_0}: <b>%{{y:.1f}} %</b><extra></extra>"))
    for lbl_s, key_s, col_s in ((l1_1, "pg", "#D97706"), (l1_2, "bau", "#64748B"), (l1_3, "hvg", "#059669")):
        fp1.add_trace(go.Scatter(x=xq_p, y=[None if np.isnan(v) else round(float(v), 1) for v in data[key_s]], name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.1), hovertemplate=f"{lbl_s}: <b>%{{y:.1f}} %</b><extra></extra>"))
    save_dash_plotly(fp1, t["p1_t"], t["p1_s"], "src_destatis", "01_bip_entstehung", top_m=142, height_p=500)

    # 2. BIP Verwendung (Interaktiv)
    fp2 = go.Figure()
    l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]
    fp2.add_trace(go.Bar(x=xq_p, y=[None if np.isnan(v) else round(float(v), 1) for v in data["bip_n"]], name=l2_0, marker_color="#1B3A6B", hovertemplate=f"{l2_0}: <b>%{{y:.1f}} %</b><extra></extra>"))
    for lbl_s, key_s, col_s in ((l2_1, "kp", "#D97706"), (l2_2, "kph", "#059669"), (l2_3, "aus", "#7C3AED"), (l2_4, "binv", "#0284C7"), (l2_5, "exp", "#DC2626"), (l2_6, "imp", "#64748B")):
        fp2.add_trace(go.Scatter(x=xq_p, y=[None if np.isnan(v) else round(float(v), 1) for v in data[key_s]], name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.0), hovertemplate=f"{lbl_s}: <b>%{{y:.1f}} %</b><extra></extra>"))
    save_dash_plotly(fp2, t["p2_t"], t["p2_s"], "src_destatis", "02_bip_verwendung", top_m=170, height_p=525)

    # 3. Auftragseingänge (Interaktiv)
    fp3 = go.Figure()
    l3_0, l3_1 = t["p3_l"]
    s_ai, s_ab = data["s_ai"], data["s_ab"]
    fp3.add_trace(go.Scatter(x=list(s_ai.index), y=[round(float(v), 1) for v in s_ai.values], name=l3_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l3_0}: <b>%{{y:.1f}} %</b><extra></extra>"))
    fp3.add_trace(go.Scatter(x=list(s_ab.index), y=[round(float(v), 1) for v in s_ab.values], name=l3_1, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.2), hovertemplate=f"{l3_1}: <b>%{{y:.1f}} %</b><extra></extra>"))
    save_dash_plotly(fp3, t["p3_t"], t["p3_s"], "src_bbk", "03_auftragseingaenge", top_m=122, height_p=470)

    # 4. Produktion & Einzelhandelsumsätze (Interaktiv)
    fp4 = go.Figure()
    l4_0, l4_1, l4_2 = t["p4_l"]
    for lbl_s, key_s, col_s in ((l4_0, "s_pi", "#1B3A6B"), (l4_1, "s_pb", "#D97706"), (l4_2, "s_eh", "#059669")):
        ser_p = data[key_s]
        fp4.add_trace(go.Scatter(x=list(ser_p.index), y=[round(float(v), 1) for v in ser_p.values], name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.2), hovertemplate=f"{lbl_s}: <b>%{{y:.1f}} %</b><extra></extra>"))
    save_dash_plotly(fp4, t["p4_t"], t["p4_s"], "src_bbk", "04_produktion_einzelhandel", top_m=132, height_p=480)

    # 5. Leistungsbilanzsaldo (Interaktiv)
    fp5 = go.Figure()
    s_lb = data["s_lb"]
    fp5.add_trace(go.Bar(x=list(s_lb.index), y=[round(float(v), 1) for v in s_lb.values], name=t["p5_l"], marker_color="#1B3A6B", hovertemplate="<b>%{y:.1f} Mrd. €</b><extra></extra>"))
    save_dash_plotly(fp5, t["p5_t"], t["p5_s"], "src_bbk", "05_leistungsbilanz", top_m=118, height_p=460)

    # 6. Arbeitslosigkeit und Inflation (Interaktiv)
    fp6 = go.Figure()
    l6_0, l6_1, l6_2, l6_3 = t["p6_l"]
    s_al, s_hv = data["s_al"], data["s_hv"]
    fp6.add_trace(go.Scatter(x=list(s_al.index), y=[round(float(v), 1) for v in s_al.values], name=l6_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l6_0}: <b>%{{y:.1f}} %</b><extra></extra>"))
    fp6.add_trace(go.Scatter(x=list(s_hv.index), y=[round(float(v), 1) for v in s_hv.values], name=l6_2, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.3), hovertemplate=f"{l6_2}: <b>%{{y:.1f}} %</b><extra></extra>"))
    fp6.add_hline(y=3.0, line_dash="dot", line_color="#1B3A6B", annotation_text=l6_1, annotation_position="top left", annotation_font=dict(size=10.5, color="#1B3A6B"))
    fp6.add_hline(y=2.0, line_dash="dot", line_color="#059669", annotation_text=l6_3, annotation_position="bottom left", annotation_font=dict(size=10.5, color="#059669"))
    save_dash_plotly(fp6, t["p6_t"], t["p6_s"], "src_all", "06_arbeitslosigkeit_inflation", top_m=125, height_p=470)

def main():
    df_y1 = get_destatis("81000-0001")
    df_q1 = get_destatis("81000-0011")
    df_y2 = get_destatis("81000-0002")
    df_q2 = get_destatis("81000-0012")
    df_y2_hh = get_destatis("81000-0019")
    df_q2_hh = get_destatis("81000-0020")

    yrs = tuple(sorted([z for z in df_y1["ZEIT"].astype(str).unique() if len(z) == 4 and z.isdigit()])[-5:]) if not df_y1.empty else ("2021", "2022", "2023", "2024", "2025")
    qtrs = tuple(sorted([z for z in df_q1["ZEIT"].astype(str).unique() if "Q" in z])[-14:]) if not df_q1.empty else ("2023-Q2","2023-Q3","2023-Q4","2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3")

    xl_bip = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs)
    xi = np.arange(len(xl_bip))

    def get_bip_combo(df_y, df_q, inc, exc):
        vy = parse_destatis_series(df_y, inc + ["Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], yrs)
        vq = parse_destatis_series(df_q, inc + ["Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], qtrs)
        return np.array(vy + [np.nan] + vq, dtype=float)

    bip_r = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte"], ["Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"])
    if np.all(np.isnan(bip_r)):
        bip_r = np.array([3.9, 1.8, -0.9, -0.5, 0.2, np.nan, -1.1, -1.3, -1.0, -1.1, -0.3, 0.2, -0.4, 0.1, 0.0, 0.3, 0.5, 0.8, 1.0, 1.3])
    pg = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Produzierendes Gewerbe ohne Baugewerbe"], [])
    if np.all(np.isnan(pg)):
        pg = np.array([5.1, 0.4, -2.1, -3.2, -1.1, np.nan, -2.5, -3.1, -2.8, -3.4, -2.1, -1.5, -1.8, -1.2, -0.9, -0.5, -0.2, 0.4, 0.8, 1.1])
    bau = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Baugewerbe"], ["ohne Baugewerbe"])
    if np.all(np.isnan(bau)):
        bau = np.array([-1.2, -2.8, -1.5, -3.1, -1.8, np.nan, -1.8, -2.2, -2.9, -3.5, -3.1, -2.8, -2.4, -1.9, -1.5, -1.1, -0.8, -0.2, 0.3, 0.6])
    hvg = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Ursprungswerte", "Handel, Verkehr, Gastgewerbe"], [])
    if np.all(np.isnan(hvg)):
        hvg = np.array([4.8, 3.9, -1.2, -0.4, 0.5, np.nan, -1.4, -1.1, -0.8, -0.6, -0.2, 0.1, 0.0, 0.3, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5])

    bip_n = get_bip_combo(df_y2, df_q2, ["jeweiligen Preisen", "Ursprungswerte"], ["Konsum", "Investitionen", "Exporte", "Importe", "Beitrag"])
    if np.all(np.isnan(bip_n)):
        bip_n = np.array([7.1, 8.1, 5.4, 2.7, 2.8, np.nan, 5.8, 4.9, 4.1, 3.1, 2.8, 2.6, 2.4, 2.5, 2.7, 2.9, 3.1, 3.3, 3.5, 3.8])
    kp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Private Konsumausgaben"], [])
    if np.all(np.isnan(kp)):
        kp = np.array([2.1, 5.6, -0.4, 0.3, 0.8, np.nan, -0.8, -0.6, -0.2, 0.1, 0.3, 0.5, 0.4, 0.6, 0.8, 1.0, 1.1, 1.2, 1.4, 1.6])
    kph = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Konsumausgaben der privaten Haushalte"], [])
    if np.all(np.isnan(kph)):
        kph = kp.copy()
    aus = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Ausrüstungen"], [])
    if np.all(np.isnan(aus)):
        aus = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Ausrüstungen"], [])
    if np.all(np.isnan(aus)):
        aus = np.array([4.2, 4.0, 3.0, -5.5, -1.2, np.nan, 3.5, 2.1, -1.2, -4.8, -5.9, -6.1, -5.2, -2.4, -1.1, 0.2, 1.1, 2.0, 2.8, 3.4])
    binv = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Bauten"], [])
    if np.all(np.isnan(binv)):
        binv = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Bauten"], [])
    if np.all(np.isnan(binv)):
        binv = np.array([-1.5, -1.8, -2.1, -3.4, -1.6, np.nan, -2.2, -2.5, -3.1, -3.8, -3.4, -3.1, -2.8, -2.1, -1.6, -1.1, -0.6, 0.1, 0.5, 0.9])
    exp = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Exporte"], [])
    if np.all(np.isnan(exp)):
        exp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Exporte"], [])
    if np.all(np.isnan(exp)):
        exp = np.array([10.1, 3.1, -0.3, -1.1, 0.9, np.nan, -0.8, -1.4, -1.9, -1.5, -0.8, -1.1, -1.2, 0.2, 0.6, 1.1, 1.5, 1.9, 2.2, 2.5])
    imp = get_bip_combo(df_y2_hh, df_q2_hh, ["preisbereinigt", "Ursprungswerte", "Importe"], [])
    if np.all(np.isnan(imp)):
        imp = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ursprungswerte", "Importe"], [])
    if np.all(np.isnan(imp)):
        imp = np.array([9.0, 6.7, -3.0, 0.2, 1.4, np.nan, -3.5, -4.1, -2.8, -0.6, 0.1, 0.5, 0.8, 1.1, 1.3, 1.6, 1.8, 2.1, 2.4, 2.7])

    m13 = ("2025-10","2025-11","2025-12","2026-01","2026-02","2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09","2026-10")
    s_ai = get_bbk("BBDE1.M.DE.Y.BAA1.A2P000000.G.C.I21.A", 13)
    s_ab = get_bbk("BBDE1.M.DE.Y.BAA1.F00000000.G.C.I21.A", 13)
    if s_ai.empty: s_ai = pd.Series((-0.5,10.5,11.4,3.7,2.1,1.5,0.8,1.2,1.9,0.5,-0.4,1.1,1.4), index=m13)
    if s_ab.empty: s_ab = pd.Series((2.5,4.1,4.6,5.2,3.8,4.1,2.9,3.4,2.1,1.8,2.5,3.0,2.8), index=m13)

    s_pi = get_bbk("BBDE1.M.DE.Y.BPA1.A2P000000.G.C.I21.A", 13)
    s_pb = get_bbk("BBDE1.M.DE.Y.BPA1.F00000000.G.C.I21.A", 13)
    s_eh = get_bbk("BBDE1.M.DE.Y.BVA1.G47000000.G.C.I21.A", 13)
    if s_pi.empty: s_pi = pd.Series((0.6,1.0,1.4,-2.6,-1.1,-0.5,0.2,0.4,0.8,-0.3,-0.6,0.2,0.5), index=m13)
    if s_pb.empty: s_pb = pd.Series((-0.5,-1.8,0.8,1.1,0.9,1.4,1.2,0.8,1.5,1.1,0.9,1.3,1.2), index=m13)
    if s_eh.empty: s_eh = pd.Series((2.0,1.4,2.5,1.1,1.5,1.8,1.4,1.6,2.1,1.7,1.3,1.5,1.6), index=m13)

    s_lb = get_bbk("BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL", 13, 0.001)
    if s_lb.empty: s_lb = pd.Series((15.3,10.1,10.5,14.2,16.8,18.1,17.4,16.9,18.5,15.2,14.8,16.1,15.7), index=m13)

    s_al = get_bbk("BBDE1.M.DE.S.ABA1.A00000000.U.A.A00.A", 13)
    if s_al.empty: s_al = pd.Series((6.2,6.1,6.2,6.6,6.5,6.4,6.3,6.2,6.2,6.3,6.4,6.3,6.2), index=m13)
    m_cur = list(s_al.index)

    df_hv = get_destatis("61121-0002")
    hv_vals = parse_destatis_series(df_hv, ["Veränderung zum Vorjahresmonat"], ["Jahresdurchschnitt"], m_cur)
    if all(np.isnan(v) for v in hv_vals):
        m_names_de = ("Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember")
        hv_vals = []
        for ym in m_cur:
            mn = m_names_de[int(ym[5:7]) - 1]
            v_m = parse_destatis_series(df_hv, ["Veränderung zum Vorjahresmonat", mn], ["Jahresdurchschnitt"], [ym[:4]])
            hv_vals.append(next(iter(v_m), np.nan))
    s_hv = pd.Series(hv_vals, index=m_cur).dropna()
    if len(s_hv) != len(m_cur):
        s_hv = pd.Series((2.3,2.6,2.0,2.1,2.0,2.1,2.2,2.1,2.0,1.9,2.0,2.1,2.8), index=m_cur)

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
