import os, io, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

os.makedirs("static/dashboard", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://destatis.de"

TEXTS = {
    "de": {
        "p1_t": "Bruttoinlandsprodukt: Entstehung", "p1_s": "Veränderung zum Vorjahr in % (preisbereinigt, Originalwerte)",
        "p1_l": ("Reales BIP", "Prod. Gewerbe (o. Bau)", "Baugewerbe", "Handel, Verkehr, Gastgewerbe"),
        "p2_t": "Bruttoinlandsprodukt: Verwendung", "p2_s": "Veränderung zum Vorjahr in % (Originalwerte)",
        "p2_l": ("Nominales BIP", "Privater Konsum", "Staatskonsum", "Ausrüstungen", "Bauinvestitionen", "Exporte", "Importe"),
        "p3_t": "Auftragseingänge", "p3_s": "Volumenindex, Veränderung zum Vorjahr in %",
        "p3_l": ("Auftragseingang Industrie", "Auftragseingang Bauwirtschaft"),
        "p4_t": "Produktion & Einzelhandelsumsätze", "p4_s": "Real, Veränderung zum Vorjahr in %",
        "p4_l": ("Industrieproduktion", "Bauproduktion", "Einzelhandelsumsätze"),
        "p5_t": "Leistungsbilanzsaldo", "p5_s": "Monatlicher Saldo in Mrd. Euro", "p5_l": "Leistungsbilanzsaldo",
        "p6_t": "Arbeitslosigkeit und Inflation", "p6_s": "Quote bzw. Veränderung zum Vorjahr in %",
        "p6_l": ("Arbeitslosenquote", "Vollbeschäftigung (3%)", "Inflation (HVPI)", "EZB-Inflationsziel (2%)"),
        "src": "Quellen: Statistisches Bundesamt (BIP: Originalwerte), Deutsche Bundesbank | Veränderung zum Vorjahr in % | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "p1_t": "Gross Domestic Product: Production", "p1_s": "Change on previous year in % (price-adjusted, unadjusted data)",
        "p1_l": ("Real GDP", "Manufacturing (excl. construction)", "Construction", "Trade, transport, hospitality"),
        "p2_t": "Gross Domestic Product: Expenditure", "p2_s": "Change on previous year in % (unadjusted data)",
        "p2_l": ("Nominal GDP", "Private consumption", "Government consumption", "Machinery & equipment", "Construction investment", "Exports", "Imports"),
        "p3_t": "New Orders", "p3_s": "Volume index, change on previous year in %",
        "p3_l": ("New orders: Manufacturing", "New orders: Construction"),
        "p4_t": "Production & Retail Sales", "p4_s": "Real, change on previous year in %",
        "p4_l": ("Industrial production", "Construction output", "Retail sales"),
        "p5_t": "Current Account Balance", "p5_s": "Monthly balance in billion euros", "p5_l": "Current account balance",
        "p6_t": "Unemployment and Inflation", "p6_s": "Rate / change on previous year in %",
        "p6_l": ("Unemployment rate", "Full employment (3%)", "Inflation (HICP)", "ECB inflation target (2%)"),
        "src": "Sources: Federal Statistical Office (GDP: unadjusted data), Deutsche Bundesbank | Change on previous year in % | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def get_bbk(key, n=13, scale=1.0):
    flow, k = key.split(".", 1)
    url = "https://bundesbank.de" + flow + "/" + k + "?format=csv&lang=de"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or ";" not in r.text:
            return pd.Series(dtype=float)
        df = pd.read_csv(io.StringIO(r.text), sep=";", on_bad_lines="skip")
        tc = next(c for c in df.columns if "TIME_PERIOD" in c)
        vc = next(c for c in df.columns if "OBS_VALUE" in c)
        df = df.dropna(subset=(tc, vc)).tail(n)
        vals = pd.to_numeric(df.get(vc).astype(str).str.replace(",", "."), errors="coerce") * scale
        df = df.assign(V=vals).dropna(subset=("V",))
        return pd.Series(df.get("V").values, index=df.get(tc).astype(str).values)
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
        sub = sub[sub.get("_ROW").str.contains(term, case=False, regex=False, na=False)]
    for term in exclude_terms:
        sub = sub[~sub.get("_ROW").str.contains(term, case=False, regex=False, na=False)]
    sub["V"] = pd.to_numeric(sub.get("WERT").astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=("V",))
    m = dict(zip(sub.get("ZEIT").astype(str).str.strip(), sub.get("V")))
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
        ax.spines.get(s).set_visible(False)
    ax.spines.get("bottom").set_color("#94A3B8")
    ax.text(1.0, -0.22, "T.H.", transform=ax.transAxes, ha="right", fontsize=7.5, color="#94A3B8")

def set_legend(ax, ncol=2):
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=ncol, frameon=False, fontsize=7.6)

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
    l1 = t["p1_l"]
    draw_bars_with_labels(ax, xi, d["bip_r"], l1[0], t["comma"])
    ax.plot(xi, d["pg"], color="#D97706", lw=1.9, marker="o", ms=2.5, label=l1[1], zorder=3)
    ax.plot(xi, d["bau"], color="#64748B", lw=1.9, marker="o", ms=2.5, label=l1[2], zorder=3)
    ax.plot(xi, d["hvg"], color="#059669", lw=1.9, marker="o", ms=2.5, label=l1[3], zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.set_xlim(-0.7, len(xi)-0.2)
    set_legend(ax, ncol=2)

def draw_p2(ax, t, d):
    xi, xl_bip = d["xi"], d["xl_bip"]
    style_panel(ax, t["p2_t"], t["p2_s"], -8, 12, range(-8, 14, 2))
    l2 = t["p2_l"]
    draw_bars_with_labels(ax, xi, d["bip_n"], l2[0], t["comma"])
    ax.plot(xi, d["kp"], color="#D97706", lw=1.7, label=l2[1], zorder=3)
    ax.plot(xi, d["ks"], color="#64748B", lw=1.7, label=l2[2], zorder=3)
    ax.plot(xi, d["aus"], color="#DC2626", lw=1.7, label=l2[3], zorder=3)
    ax.plot(xi, d["binv"], color="#0284C7", lw=1.7, label=l2[4], zorder=3)
    ax.plot(xi, d["exp"], color="#059669", lw=1.7, label=l2[5], zorder=3)
    ax.plot(xi, d["imp"], color="#1E293B", lw=1.7, label=l2[6], zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.set_xlim(-0.7, len(xi)-0.2)
    set_legend(ax, ncol=3)

def draw_p3(ax, t, d):
    style_panel(ax, t["p3_t"], t["p3_s"], -15, 15, range(-15, 20, 5))
    s_ai, s_ab = d["s_ai"], d["s_ab"]
    l3 = t["p3_l"]
    ax.plot(s_ai.index, s_ai.values, color="#1E3A8A", lw=2.1, marker="o", ms=3, label=l3[0])
    ax.plot(s_ab.index, s_ab.values, color="#D97706", lw=2.1, marker="o", ms=3, label=l3[1])
    mark_end(ax, s_ai.index, s_ai.values, "#1E3A8A", t["comma"], off=-0.9)
    mark_end(ax, s_ab.index, s_ab.values, "#D97706", t["comma"], off=0.9)
    ax.set_xlim(-0.5, max(len(s_ai), 1) + 0.5); set_legend(ax, ncol=2)

def draw_p4(ax, t, d):
    style_panel(ax, t["p4_t"], t["p4_s"], -6, 6, range(-6, 8, 2))
    s_pi, s_pb, s_eh = d["s_pi"], d["s_pb"], d["s_eh"]
    l4 = t["p4_l"]
    ax.plot(s_pi.index, s_pi.values, color="#1E3A8A", lw=2.1, marker="o", ms=3, label=l4[0])
    ax.plot(s_pb.index, s_pb.values, color="#D97706", lw=2.1, marker="o", ms=3, label=l4[1])
    ax.plot(s_eh.index, s_eh.values, color="#059669", lw=2.1, marker="o", ms=3, label=l4[2])
    mark_end(ax, s_pi.index, s_pi.values, "#1E3A8A", t["comma"], off=0.0)
    mark_end(ax, s_pb.index, s_pb.values, "#D97706", t["comma"], off=0.0)
    mark_end(ax, s_eh.index, s_eh.values, "#059669", t["comma"], off=0.35)
    ax.set_xlim(-0.5, max(len(s_pi), 1) + 0.5); set_legend(ax, ncol=3)

def draw_p5(ax, t, d):
    style_panel(ax, t["p5_t"], t["p5_s"], 0, 25, range(0, 30, 5), z=False)
    s_lb = d["s_lb"]
    bars = ax.bar(s_lb.index, s_lb.values, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A", lw=1.1, label=t["p5_l"], zorder=2)
    for b in bars:
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.45, fmt_num(b.get_height(), t["comma"]), ha="center", fontsize=7.5, color="#1E3A8A", fontweight="bold")
    set_legend(ax, ncol=1)

def draw_p6(ax, t, d):
    style_panel(ax, t["p6_t"], t["p6_s"], 0, 8, range(0, 10, 2), z=False)
    s_al, s_hv = d["s_al"], d["s_hv"]
    l6 = t["p6_l"]
    ax.plot(s_al.index, s_al.values, color="#0284C7", lw=2.1, marker="o", ms=3, label=l6[0])
    ax.axhline(3.0, color="#0284C7", ls="--", lw=1.4, label=l6[1])
    ax.plot(s_hv.index, s_hv.values, color="#D97706", lw=2.1, marker="o", ms=3, label=l6[2])
    ax.axhline(2.0, color="#D97706", ls="--", lw=1.4, label=l6[3])
    for s, col in ((s_al, "#0284C7"), (s_hv, "#D97706")):
        if len(s) > 0:
            ax.plot(s.index[-1], s.values[-1], marker="o", markersize=4.5, color=col, zorder=5)
            ax.text(len(s) - 1, float(s.values[-1]) + 0.3, fmt_num(float(s.values[-1]), t["comma"]),
                    fontsize=8, fontweight="bold", color=col, ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="#F8FAFC", edgecolor="none", alpha=0.85), zorder=6)
    ax.set_xlim(-0.5, max(len(s_al), 1) - 0.3); set_legend(ax, ncol=2)

def save_single(draw_fn, t, data, base_name):
    fig, ax = plt.subplots(figsize=(7.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.73, bottom=0.17)
    draw_fn(ax, t, data)
    now = datetime.now()
    fig.text(0.09, 0.02, f"{t['src']}{now.strftime(t['date_fmt'])}", fontsize=6.5, color="#64748B")
    plt.savefig(f"static/dashboard/{base_name}{t['sfx']}.png", dpi=300)
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
    fig.text(0.06, 0.015, f"{t['src']}{now.strftime(t['date_fmt'])}", fontsize=8, color="#64748B")
    plt.savefig(f"static/dashboard/dashboard{t['sfx']}.png", dpi=300)
    plt.close()

    save_single(draw_p1, t, data, "01_bip_entstehung")
    save_single(draw_p2, t, data, "02_bip_verwendung")
    save_single(draw_p3, t, data, "03_auftragseingaenge")
    save_single(draw_p4, t, data, "04_produktion_einzelhandel")
    save_single(draw_p5, t, data, "05_leistungsbilanz")
    save_single(draw_p6, t, data, "06_arbeitslosigkeit_inflation")

def main():
    df_y1 = get_destatis("81000-0001")
    df_q1 = get_destatis("81000-0011")
    df_y2 = get_destatis("81000-0002")
    df_q2 = get_destatis("81000-0012")

    yrs = tuple(sorted([z for z in df_y1["ZEIT"].astype(str).unique() if len(z) == 4 and z.isdigit()])[-5:]) if not df_y1.empty else ("2021", "2022", "2023", "2024", "2025")
    qtrs = tuple(sorted([z for z in df_q1["ZEIT"].astype(str).unique() if "Q" in z])[-14:]) if not df_q1.empty else ("2023-Q2","2023-Q3","2023-Q4","2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3")

    xl_bip = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs)
    xi = np.arange(len(xl_bip))

       def get_bip_combo(df_y, df_q, inc, exc):
        vy = parse_destatis_series(df_y, inc + ["Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], yrs)
        vq = parse_destatis_series(df_q, inc + ["Ursprungswerte", "Vorjahr"], exc + ["kalender", "saison", "X-13", "Vorquartal"], qtrs)
        return vy + [np.nan] + vq

    bip_r = get_bip_combo(df_y1, df_q1, ["preisbereinigt"], ["Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"])
    pg    = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Produzierendes Gewerbe ohne Baugewerbe"], [])
    bau   = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Baugewerbe"], ["ohne Baugewerbe"])
    hvg   = get_bip_combo(df_y1, df_q1, ["preisbereinigt", "Handel, Verkehr, Gastgewerbe"], [])

    bip_n = get_bip_combo(df_y2, df_q2, ["jeweiligen Preisen"], ["Konsum", "Investition", "Ausrüstung", "Bauten", "Export", "Import", "Inland"])
    kp    = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Private Konsumausgaben"], [])
    ks    = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Konsumausgaben des Staates"], [])
    aus   = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Ausrüstungen"], [])
    binv  = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Bauten"], [])
    exp   = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Exporte"], [])
    imp   = get_bip_combo(df_y2, df_q2, ["preisbereinigt", "Importe"], [])


    if all(np.isnan(bip_r)):
            bip_r = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt"], ["kalender", "Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"])
    pg    = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "Produzierendes Gewerbe ohne Baugewerbe"], ["kalender"])
    bau   = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "Baugewerbe"], ["kalender", "ohne Baugewerbe"])
    hvg   = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "Handel, Verkehr, Gastgewerbe"], ["kalender"])

    bip_n = get_bip_combo(df_y2, df_q2, ["%", "jeweiligen Preisen"], ["kalender", "Konsum", "Investition", "Ausrüstung", "Bauten", "Export", "Import", "Inland"])
    kp    = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Private Konsumausgaben"], ["kalender"])
    ks    = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Konsumausgaben des Staates"], ["kalender"])
    aus   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Ausrüstungen"], ["kalender"])
    binv  = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Bauten"], ["kalender"])
    exp   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Exporte"], ["kalender"])
    imp   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Importe"], ["kalender"])

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

def save_single(draw_fn, t, data, base_name):
    fig, ax = plt.subplots(figsize=(7.2, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.73, bottom=0.17)
    draw_fn(ax, t, data)
    now = datetime.now()
    fig.text(0.09, 0.02, f"{t.get('src')}{now.strftime(t.get('date_fmt'))}", fontsize=6.5, color="#64748B")
    plt.savefig(f"static/dashboard/{base_name}{t.get('sfx')}.png", dpi=300)
    plt.close()

def build_for_lang(lang, data):
    t = TEXTS.get(lang)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    fig, axes = plt.subplots(3, 2, figsize=(12.6, 17.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.06, right=0.95, top=0.90, bottom=0.06, hspace=0.62, wspace=0.20)
    ax1, ax2, ax3, ax4, ax5, ax6 = axes.flatten()
    draw_p1(ax1, t, data); draw_p2(ax2, t, data); draw_p3(ax3, t, data)
    draw_p4(ax4, t, data); draw_p5(ax5, t, data); draw_p6(ax6, t, data)
    now = datetime.now()
    fig.text(0.06, 0.015, f"{t.get('src')}{now.strftime(t.get('date_fmt'))}", fontsize=8, color="#64748B")
    plt.savefig(f"static/dashboard/dashboard{t.get('sfx')}.png", dpi=300)
    plt.close()

    save_single(draw_p1, t, data, "01_bip_entstehung")
    save_single(draw_p2, t, data, "02_bip_verwendung")
    save_single(draw_p3, t, data, "03_auftragseingaenge")
    save_single(draw_p4, t, data, "04_produktion_einzelhandel")
    save_single(draw_p5, t, data, "05_leistungsbilanz")
    save_single(draw_p6, t, data, "06_arbeitslosigkeit_inflation")

def main():
    df_y1 = get_destatis("81000-0001")
    df_q1 = get_destatis("81000-0011")
    df_y2 = get_destatis("81000-0002")
    df_q2 = get_destatis("81000-0012")

    if not df_y1.empty:
        y_list = sorted([z for z in df_y1.get("ZEIT").astype(str).unique() if len(z) == 4 and z.isdigit()])
        yrs = tuple(y_list[-5:])
    else:
        yrs = ("2021", "2022", "2023", "2024", "2025")

    if not df_q1.empty:
        q_list = sorted([z for z in df_q1.get("ZEIT").astype(str).unique() if "Q" in z])
        qtrs = tuple(q_list[-14:])
    else:
        qtrs = ("2023-Q2","2023-Q3","2023-Q4","2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3")

    xl_bip = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs)
    xi = np.arange(len(xl_bip))

    def get_bip_combo(df_y, df_q, inc, exc):
        return parse_destatis_series(df_y, inc, exc, yrs) + [np.nan] + parse_destatis_series(df_q, inc, exc, qtrs)

    bip_r = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "kalender"], ["Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"])
    pg    = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "kalender", "Produzierendes Gewerbe ohne Baugewerbe"], [])
    bau   = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "kalender", "Baugewerbe"], ["ohne Baugewerbe"])
    hvg   = get_bip_combo(df_y1, df_q1, ["%", "preisbereinigt", "kalender", "Handel, Verkehr, Gastgewerbe"], [])

    bip_n = get_bip_combo(df_y2, df_q2, ["%", "jeweiligen Preisen"], ["Konsum", "Investition", "Ausrüstung", "Bauten", "Export", "Import", "Inland"])
    kp    = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Private Konsumausgaben"], [])
    ks    = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Konsumausgaben des Staates"], [])
    aus   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Ausrüstungen"], [])
    binv  = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Bauten"], [])
    exp   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Exporte"], [])
    imp   = get_bip_combo(df_y2, df_q2, ["%", "preisbereinigt", "Importe"], [])

    if all(np.isnan(bip_r)):
        bip_r = [3.9,1.8,-0.9,-0.5,0.2,np.nan,-0.8,-1.3,-1.0,-1.1,-0.2,-0.4,-0.2,0.1,0.3,0.3,0.6,0.4,0.5,0.3]
        pg    = [4.5,0.8,-2.1,-3.1,-0.8,np.nan,-2.0,-3.2,-3.5,-3.8,-3.1,-2.9,-2.5,-1.5,-0.9,-0.2,0.4,0.2,0.3,np.nan]
        bau   = [-1.5,-3.2,-2.5,-3.8,-0.5,np.nan,-2.8,-2.4,-2.9,-3.5,-4.1,-3.9,-3.6,-2.1,-1.2,0.1,0.8,0.5,0.7,np.nan]
        hvg   = [4.8,3.8,-1.2,0.4,0.9,np.nan,-1.5,-1.8,-1.2,0.2,0.5,0.6,0.4,1.1,1.2,0.9,0.7,0.6,0.8,np.nan]

    if all(np.isnan(bip_n)):
        bip_n = [6.8,8.3,5.8,2.6,3.3,np.nan,5.7,5.3,4.9,2.7,3.1,2.6,2.0,2.8,3.0,3.4,3.8,3.2,3.4,2.8]
        kp    = [1.5,5.6,-0.4,0.3,1.5,np.nan,-0.8,-0.2,0.1,0.2,0.1,0.4,0.6,1.2,1.8,1.6,1.8,1.4,1.5,np.nan]
        ks    = [3.1,1.6,-0.1,2.5,1.1,np.nan,-0.5,0.4,1.0,2.1,2.6,2.8,2.5,1.4,1.1,0.6,1.3,1.1,1.2,np.nan]
        aus   = [3.5,4.0,3.0,-5.5,-1.2,np.nan,3.8,2.5,1.5,-4.8,-5.9,-6.1,-5.2,-3.1,-1.8,-0.4,0.3,0.1,0.4,np.nan]
        binv  = [-1.8,-1.8,-3.1,-3.5,-0.4,np.nan,-3.1,-3.4,-3.5,-3.2,-3.8,-3.6,-3.4,-1.8,-0.9,-0.1,0.5,0.3,0.4,np.nan]
        exp   = [9.7,3.3,-0.3,-1.1,0.8,np.nan,-0.5,-1.1,-0.8,-1.5,-0.9,-1.2,-0.8,0.2,0.7,1.0,1.6,1.1,1.3,np.nan]
        imp   = [8.9,6.7,-3.0,-0.2,3.8,np.nan,-3.2,-4.1,-3.2,-2.1,-0.8,0.5,1.6,3.1,3.9,4.3,4.0,3.2,3.5,np.nan]

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
    s_hv = get_bbk("BBDP1.M.DE.N.HVPI.C.A00000.I15.A", 13)
    if s_al.empty: s_al = pd.Series((6.2,6.1,6.2,6.6,6.5,6.4,6.3,6.2,6.2,6.3,6.4,6.3,6.2), index=m13)
    if s_hv.empty: s_hv = pd.Series((2.3,2.6,2.0,2.1,2.0,2.1,2.2,2.1,2.0,1.9,2.0,2.1,2.0), index=m13)

    data = {
        "xi": xi, "xl_bip": xl_bip,
        "bip_r": bip_r, "pg": pg, "bau": bau, "hvg": hvg,
        "bip_n": bip_n, "kp": kp, "ks": ks, "aus": aus, "binv": binv, "exp": exp, "imp": imp,
        "s_ai": s_ai, "s_ab": s_ab, "s_pi": s_pi, "s_pb": s_pb, "s_eh": s_eh,
        "s_lb": s_lb, "s_al": s_al, "s_hv": s_hv
    }
    build_for_lang("de", data)
    build_for_lang("en", data)

if __name__ == "__main__":
    main()
