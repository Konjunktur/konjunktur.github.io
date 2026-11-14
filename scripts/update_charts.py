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
        "p1_t": "Bruttoinlandsprodukt: Entstehung", "p1_s": "Veränderung zum Vorjahr in % (preis- & kalenderbereinigt)",
        "p1_l": ("Reales BIP", "Prod. Gewerbe (o. Bau)", "Baugewerbe", "Handel, Verkehr, Gastgewerbe"),
        "p2_t": "Bruttoinlandsprodukt: Verwendung", "p2_s": "Veränderung zum Vorjahr in %",
        "p2_l": ("Nominales BIP", "Privater Konsum", "Staatskonsum", "Ausrüstungen", "Bauinvestitionen", "Exporte", "Importe"),
        "p3_t": "Auftragseingänge", "p3_s": "Volumenindex, Veränderung zum Vorjahr in %",
        "p3_l": ("Auftragseingang Industrie", "Auftragseingang Bauwirtschaft"),
        "p4_t": "Produktion & Einzelhandelsumsätze", "p4_s": "Real, Veränderung zum Vorjahr in %",
        "p4_l": ("Industrieproduktion", "Bauproduktion", "Einzelhandelsumsätze"),
        "p5_t": "Leistungsbilanzsaldo", "p5_s": "Monatlicher Saldo in Mrd. Euro", "p5_l": "Leistungsbilanzsaldo",
        "p6_t": "Arbeitslosigkeit und Inflation", "p6_s": "Quote bzw. Veränderung zum Vorjahr in %",
        "p6_l": ("Arbeitslosenquote", "Vollbeschäftigung (3%)", "Inflation (HVPI)", "EZB-Inflationsziel (2%)"),
        "src": "Quellen: Statistisches Bundesamt (BIP), Deutsche Bundesbank | Kalenderbereinigt, Veränderung zum Vorjahr in % | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "p1_t": "Gross Domestic Product: Production", "p1_s": "Change on previous year in % (price & calendar adjusted)",
        "p1_l": ("Real GDP", "Manufacturing (excl. construction)", "Construction", "Trade, transport, hospitality"),
        "p2_t": "Gross Domestic Product: Expenditure", "p2_s": "Change on previous year in %",
        "p2_l": ("Nominal GDP", "Private consumption", "Government consumption", "Machinery & equipment", "Construction investment", "Exports", "Imports"),
        "p3_t": "New Orders", "p3_s": "Volume index, change on previous year in %",
        "p3_l": ("New orders: Manufacturing", "New orders: Construction"),
        "p4_t": "Production & Retail Sales", "p4_s": "Real, change on previous year in %",
        "p4_l": ("Industrial production", "Construction output", "Retail sales"),
        "p5_t": "Current Account Balance", "p5_s": "Monthly balance in billion euros", "p5_l": "Current account balance",
        "p6_t": "Unemployment and Inflation", "p6_s": "Rate / change on previous year in %",
        "p6_l": ("Unemployment rate", "Full employment (3%)", "Inflation (HICP)", "ECB inflation target (2%)"),
        "src": "Sources: Federal Statistical Office (GDP), Deutsche Bundesbank | Calendar-adjusted, change on previous year in % | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def get_bbk(key, n=13, scale=1.0):
    flow, k = key.split(".", 1)
    url = f"https://bundesbank.de{flow}/{k}?format=csv&lang=de"
    try:
        r = requests.get(url, timeout=10)
        df = pd.read_csv(io.StringIO(r.text), sep=";")
        tc = next(c for c in df.columns if "TIME_PERIOD" in c)
        vc = next(c for c in df.columns if "OBS_VALUE" in c)
        df = df.dropna(subset=list((tc, vc))).tail(n)
        vals = df.get(vc).astype(str).str.replace(",", ".").astype(float) * scale
        return pd.Series(vals.values, index=df.get(tc).values)
    except Exception:
        return pd.Series(dtype=float)

def get_destatis(table):
    if not D_USER or not D_PASS:
        return pd.DataFrame()
    p = {"username": D_USER, "password": D_PASS, "name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    try:
        r = requests.get(G_URL, params=p, timeout=30)
        if len(r.text) < 200 or "Fehler" in r.text[:250]:
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO(r.text), sep=";", decimal=",")
        meta_cols = [c for c in df.columns if "CODE" in c or "LABEL" in c]
        df["_META"] = df[meta_cols].fillna("").astype(str).agg(" | ".join, axis=1)
        return df
    except Exception:
        return pd.DataFrame()

def get_dynamic_bip_axes(df):
    if df.empty or "ZEIT" not in df.columns:
        yrs = ("2021", "2022", "2023", "2024", "2025")
        qtrs = ("2023-Q2","2023-Q3","2023-Q4","2024-Q1","2024-Q2","2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1","2026-Q2","2026-Q3")
        return yrs, qtrs
    zeiten = sorted(df["ZEIT"].astype(str).unique())
    yrs = tuple([z for z in zeiten if len(z) == 4 and z.isdigit()][-5:])
    qtrs = tuple([z for z in zeiten if "Q" in z][-14:])
    return yrs, qtrs

def parse_bip_series(df, must_contain, yrs, qtrs):
    """Filtert die Destatis-ffcsv-Tabelle anhand beliebiger Code/Label-Merkmale und Veränderungsrate (%)."""
    if df.empty or "ZEIT" not in df.columns or "WERT" not in df.columns:
        return [np.nan] * (len(yrs) + 1 + len(qtrs))
    sub = df[df["_META"].str.contains("Veränderung", case=False, na=False)].copy()
    for term in must_contain:
        sub = sub[sub["_META"].str.contains(term, case=False, regex=False, na=False)]
    sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=["V"])
    m = dict(zip(sub["ZEIT"].astype(str), sub["V"]))
    res = [m.get(y, np.nan) for y in yrs] + [np.nan]
    for q in qtrs:
        res.append(m.get(q, m.get(q.replace("-", ""), np.nan)))
    return res

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
    xi, xl_bip = d.get("xi"), d.get("xl_bip")
    style_panel(ax, t.get("p1_t"), t.get("p1_s"), -10, 8, range(-10, 10, 2))
    l1 = t.get("p1_l")
    draw_bars_with_labels(ax, xi, d.get("bip_r"), list(l1).pop(0), t.get("comma"))
    ax.plot(xi, d.get("pg"), color="#D97706", lw=1.9, marker="o", ms=2.5, label=list(l1).pop(1), zorder=3)
    ax.plot(xi, d.get("bau"), color="#64748B", lw=1.9, marker="o", ms=2.5, label=list(l1).pop(2), zorder=3)
    ax.plot(xi, d.get("hvg"), color="#059669", lw=1.9, marker="o", ms=2.5, label=list(l1).pop(3), zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.set_xlim(-0.7, len(xi)-0.2)
    set_legend(ax, ncol=2)

def draw_p2(ax, t, d):
    xi, xl_bip = d.get("xi"), d.get("xl_bip")
    style_panel(ax, t.get("p2_t"), t.get("p2_s"), -8, 12, range(-8, 14, 2))
    l2 = t.get("p2_l")
    draw_bars_with_labels(ax, xi, d.get("bip_n"), list(l2).pop(0), t.get("comma"))
    ax.plot(xi, d.get("kp"), color="#D97706", lw=1.7, label=list(l2).pop(1), zorder=3)
    ax.plot(xi, d.get("ks"), color="#64748B", lw=1.7, label=list(l2).pop(2), zorder=3)
    ax.plot(xi, d.get("aus"), color="#DC2626", lw=1.7, label=list(l2).pop(3), zorder=3)
    ax.plot(xi, d.get("binv"), color="#0284C7", lw=1.7, label=list(l2).pop(4), zorder=3)
    ax.plot(xi, d.get("exp"), color="#059669", lw=1.7, label=list(l2).pop(5), zorder=3)
    ax.plot(xi, d.get("imp"), color="#1E293B", lw=1.7, label=list(l2).pop(6), zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.set_xlim(-0.7, len(xi)-0.2)
    set_legend(ax, ncol=3)

def draw_p3(ax, t, d):
    style_panel(ax, t.get("p3_t"), t.get("p3_s"), -15, 15, range(-15, 20, 5))
    s_ai, s_ab = d.get("s_ai"), d.get("s_ab")
    l3 = t.get("p3_l")
    ax.plot(s_ai.index, s_ai.values, color="#1E3A8A", lw=2.1, marker="o", ms=3, label=list(l3).pop(0))
    ax.plot(s_ab.index, s_ab.values, color="#D97706", lw=2.1, marker="o", ms=3, label=list(l3).pop(1))
    mark_end(ax, s_ai.index, s_ai.values, "#1E3A8A", t.get("comma"), off=-0.9)
    mark_end(ax, s_ab.index, s_ab.values, "#D97706", t.get("comma"), off=0.9)
    ax.set_xlim(-0.5, len(s_ai) + 0.5); set_legend(ax, ncol=2)

def draw_p4(ax, t, d):
    style_panel(ax, t.get("p4_t"), t.get("p4_s"), -8, 8, range(-8, 10, 2))
    s_pi, s_pb, s_eh = d.get("s_pi"), d.get("s_pb"), d.get("s_eh")
    l4 = t.get("p4_l")
    ax.plot(s_pi.index, s_pi.values, color="#1E3A8A", lw=2.1, marker="o", ms=3, label=list(l4).pop(0))
    ax.plot(s_pb.index, s_pb.values, color="#D97706", lw=2.1, marker="o", ms=3, label=list(l4).pop(1))
    ax.plot(s_eh.index, s_eh.values, color="#059669", lw=2.1, marker="o", ms=3, label=list(l4).pop(2))
    mark_end(ax, s_pi.index, s_pi.values, "#1E3A8A", t.get("comma"))
    mark_end(ax, s_pb.index, s_pb.values, "#D97706", t.get("comma"), off=0.45)
    mark_end(ax, s_eh.index, s_eh.values, "#059669", t.get("comma"), off=-0.45)
    ax.set_xlim(-0.5, len(s_pi) + 0.5); set_legend(ax, ncol=3)

def draw_p5(ax, t, d):
    style_panel(ax, t.get("p5_t"), t.get("p5_s"), 0, 35, range(0, 40, 5), z=False)
    s_lb = d.get("s_lb")
    bars = ax.bar(s_lb.index, s_lb.values, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A", lw=1.1, label=t.get("p5_l"), zorder=2)
    for b in bars:
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.6, fmt_num(b.get_height(), t.get("comma")), ha="center", fontsize=7.5, color="#1E3A8A", fontweight="bold")
    set_legend(ax, ncol=1)

def draw_p6(ax, t, d):
    style_panel(ax, t.get("p6_t"), t.get("p6_s"), 0, 8, range(0, 10, 2), z=False)
    s_al, s_hv = d.get("s_al"), d.get("s_hv")
    l6 = t.get("p6_l")
    ax.plot(s_al.index, s_al.values, color="#0284C7", lw=2.1, marker="o", ms=3, label=list(l6).pop(0))
    ax.axhline(3.0, color="#0284C7", ls="--", lw=1.4, label=list(l6).pop(1))
    ax.plot(s_hv.index, s_hv.values, color="#D97706", lw=2.1, marker="o", ms=3, label=list(l6).pop(2))
    ax.axhline(2.0, color="#D97706", ls="--", lw=1.4, label=list(l6).pop(3))
    mark_end(ax, s_al.index, s_al.values, "#0284C7", t.get("comma"))
    mark_end(ax, s_hv.index, s_hv.values, "#D97706", t.get("comma"))
    ax.set_xlim(-0.5, len(s_al) + 0.5); set_legend(ax, ncol=2)

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
    df1 = get_destatis("81000-0011")
    yrs, qtrs = get_dynamic_bip_axes(df1)
    xl_bip = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs)
    xi = np.arange(len(xl_bip))

    bip_r = parse_bip_series(df1, ["Bruttoinlandsprodukt", "preisbereinigt", "kalender"], yrs, qtrs)
    pg    = parse_bip_series(df1, ["Produzierendes Gewerbe ohne Baugewerbe", "preisbereinigt", "kalender"], yrs, qtrs)
    bau   = parse_bip_series(df1, ["Baugewerbe", "preisbereinigt", "kalender"], yrs, qtrs)
    hvg   = parse_bip_series(df1, ["Handel, Verkehr, Gastgewerbe", "preisbereinigt", "kalender"], yrs, qtrs)

    df2 = get_destatis("81000-0012")
    bip_n = parse_bip_series(df2, ["Bruttoinlandsprodukt", "jeweiligen Preisen"], yrs, qtrs)
    kp    = parse_bip_series(df2, ["Private Konsumausgaben", "preisbereinigt"], yrs, qtrs)
    ks    = parse_bip_series(df2, ["Konsumausgaben des Staates", "preisbereinigt"], yrs, qtrs)
    aus   = parse_bip_series(df2, ["Ausrüstungen", "preisbereinigt"], yrs, qtrs)
    binv  = parse_bip_series(df2, ["Bauten", "preisbereinigt"], yrs, qtrs)
    exp   = parse_bip_series(df2, ["Exporte", "preisbereinigt"], yrs, qtrs)
    imp   = parse_bip_series(df2, ["Importe", "preisbereinigt"], yrs, qtrs)

    s_ai = get_bbk("BBDE1.M.DE.Y.BAA1.A2P000000.G.C.I21.A")
    s_ab = get_bbk("BBDE1.M.DE.Y.BAA1.F00000000.G.C.I21.A")
    s_pi = get_bbk("BBDE1.M.DE.Y.BPA1.A2P000000.G.C.I21.A")
    s_pb = get_bbk("BBDE1.M.DE.Y.BPA1.F00000000.G.C.I21.A")
    s_eh = get_bbk("BBDE1.M.DE.Y.BVA1.G47000000.G.C.I21.A")
    s_lb = get_bbk("BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL", 13, 0.001)
    s_al = get_bbk("BBDE1.M.DE.S.ABA1.A00000000.U.A.A00.A")
    s_hv = get_bbk("BBDP1.M.DE.N.HVPI.C.A00000.I15.A")

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

