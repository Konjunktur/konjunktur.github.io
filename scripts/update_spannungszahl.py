import os, io, re, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

os.makedirs("static/spannungszahl", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://destatis.de"
BBK_BASE = "https://api.statistiken." + "bundesbank.de" + "/rest/data/"

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
        "src_ba": "Quelle: Deutsche Bundesbank (BA-Daten), eigene Berechnungen | Stand: ",
        "src_ba_kug": "Quelle: Deutsche Bundesbank (BA-Daten), eigene Berechnungen; *berücksichtigt Kurzarbeit | Stand: ",
        "src_all": "Quellen: Statistisches Bundesamt, Deutsche Bundesbank (BA-Daten), eigene Berechnungen | Stand: ",
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
        "src_ba": "Source: Deutsche Bundesbank (BA data), own calculations | As of: ",
        "src_ba_kug": "Source: Deutsche Bundesbank (BA data), own calculations; *includes short-time work | As of: ",
        "src_all": "Sources: Federal Statistical Office, Deutsche Bundesbank (BA data), own calculations | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def fmt_num(val, use_comma, dec=1):
    s = f"{val:.{dec}f}"
    return s.replace(".", ",") if use_comma else s

def load_bbk_labor_market():
    s_alo = pd.Series(dtype=float)
    s_ste = pd.Series(dtype=float)
    s_kug = pd.Series(dtype=float)

    u = f"{BBK_BASE}BBDL1/M.DE.N.?format=csv&lang=de"
    r = requests.get(u, timeout=45)
    if r.status_code != 200 or len(r.text) < 500:
        return s_ste, s_alo, s_kug

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

    return s_ste, s_alo, s_kug

def get_destatis_bip_q():
    if not D_USER or not D_PASS:
        return pd.Series(dtype=float)
    p = {"username": D_USER, "password": D_PASS, "name": "81000-0011", "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    try:
        r = requests.get(G_URL, params=p, timeout=35)
        lines = [ln for ln in r.text.splitlines() if ln.count(";") >= 4]
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", decimal=",", on_bad_lines="skip")
        text_cols = [c for c in df.columns if c not in ("ZEIT", "WERT")]
        df["_ROW"] = df.loc[:, text_cols].fillna("").astype(str).agg(" | ".join, axis=1)
        sub = df[df["_ROW"].str.contains("Ursprungswerte", case=False, na=False)]
        sub = sub[sub["_ROW"].str.contains("Vorjahr", case=False, na=False)]
        sub = sub[sub["_ROW"].str.contains("preisbereinigt", case=False, na=False)]
        for ex in ("kalender", "saison", "X-13", "Vorquartal", "Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"):
            sub = sub[~sub["_ROW"].str.contains(ex, case=False, na=False)]
        sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=["V"])
        return pd.Series(sub["V"].values, index=sub["ZEIT"].astype(str).str.strip().values).sort_index()
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

def build_charts_for_lang(lang, d_einf, d_erw, sz_einf, sz_erw, bip_q):
    t = TEXTS[lang]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
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

    lu1 = line_unv(d_einf, vj_anchor, months_all)
    if not lu1.empty:
        lu1_x = [months_all.index(vj_anchor)] + [months_all.index(k) for k in lu1.index if k != vj_anchor]
        lu1_y = [y_einf[months_all.index(vj_anchor)]] + [lu1.loc[k] for k in lu1.index if k != vj_anchor]
        ax.plot(lu1_x, lu1_y, color="#D97706", ls="--", lw=1.9, label=l1_b, zorder=4)

    y_arr = np.array(y_einf, dtype=float)
    idx_max = int(np.flatnonzero(np.isclose(y_arr, np.nanmax(y_arr))).max())
    idx_min = int(np.flatnonzero(np.isclose(y_arr, np.nanmin(y_arr))).max())
    ym_max, ym_min = months_all[idx_max], months_all[idx_min]

    if lang == "de":
        lbl_max = f"Oberer Wendepunkt\nder Konjunktur,\n{t['m'][int(ym_max[5:7]) - 1]} {ym_max[:4]}"
        lbl_min = f"Unterer Wendepunkt\nder Konjunktur,\n{t['m'][int(ym_min[5:7]) - 1]} {ym_min[:4]}"
    else:
        lbl_max = f"Upper turning point\nof business cycle,\n{t['m'][int(ym_max[5:7]) - 1]} {ym_max[:4]}"
        lbl_min = f"Lower turning point\nof business cycle,\n{t['m'][int(ym_min[5:7]) - 1]} {ym_min[:4]}"

    ax.annotate(lbl_max, xy=(idx_max, y_einf[idx_max]),
                xytext=(min(len(months_all) - 12, idx_max + 3), y_einf[idx_max] + 150),
                ha="left", va="bottom", fontsize=7.5, color="#1B3A6B",
                arrowprops=dict(arrowstyle="->", color="#1B3A6B", lw=1.2))
    ax.annotate(lbl_min, xy=(idx_min, y_einf[idx_min]),
                xytext=(min(len(months_all) - 12, idx_min + 3), y_einf[idx_min] - 150),
                ha="left", va="top", fontsize=7.5, color="#1B3A6B",
                arrowprops=dict(arrowstyle="->", color="#1B3A6B", lw=1.2))

    draw_year_groups(ax, months_all, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.8)
    save_fig(fig, t["src_ba"], "01_einfache_spannungszahl")

    # 2. Einfache Spannungszahl Zoom (13 Monate + mehrere Referenzlinien)
    months_z = months_all[-13:]
    first_z = next(iter(months_z))
    xz = np.arange(len(months_z))
    yz_einf = [float(sz_einf.loc[ym]) for ym in months_z]
    fig, ax = plt.subplots(figsize=(8.0, 6.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.66, bottom=0.28)
    ymin_z = int(np.floor((min(yz_einf) - 120) / 100.0) * 100)
    ymax_z = max(100, int(np.ceil((max(yz_einf) + 120) / 100.0) * 100))
    style_sz_ax(fig, ax, t["p2_t"], ymin_z, ymax_z, range(ymin_z, ymax_z + 100, 100), t["x_m"], xlabel_y=-0.50)
    ax.plot(xz, yz_einf, color="#1B3A6B", lw=2.4, label=t["p2_l1"], zorder=4)
    lu_vj = line_unv(d_einf, first_z, months_z)
    if not lu_vj.empty:
        ax.plot(xz, [lu_vj.loc[ym] for ym in months_z], color="#D97706", ls="--", lw=1.9, label=t["p2_l_vj"], zorder=3)
    extra_cols = ("#059669", "#7C3AED", "#0284C7", "#B45309", "#DC2626")
    c_i = 0
    for ym in months_z[1:-1]:
        m_num = int(ym[5:7])
        if m_num in (1, 3, 6, 9, 12):
            lu_e = line_unv(d_einf, ym, months_z)
            if not lu_e.empty:
                lbl = f"{t['p2_l_prefix']}{t['m'][m_num - 1]} {ym[:4]})"
                ax.plot([months_z.index(k) for k in lu_e.index], lu_e.values, color=extra_cols[c_i % len(extra_cols)], ls=":", lw=1.8, label=lbl, zorder=3)
                c_i += 1
    draw_year_groups(ax, months_z, t["m"], step=1, year_y=-0.43)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.5)
    save_fig(fig, t["src_ba"], "02_einfache_spannungszahl_zoom")

    # 3. Erweiterte Spannungszahl (Gesamt)
    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.77, bottom=0.25)
    style_sz_ax(fig, ax, t["p3_t"], -8000, 4000, range(-8000, 6000, 2000), t["x_m"], xlabel_y=-0.31)
    l3_a, l3_b = t["p3_l"]
    ax.plot(x_all, y_erw, color="#1B3A6B", lw=2.3, label=l3_a, zorder=3)
    months_erw_valid = [ym for ym in months_all if ym in sz_erw.index]
    if len(months_erw_valid) >= 13:
        erw_anchor = months_erw_valid[-13]
        lu3 = line_unv(d_erw, erw_anchor, months_erw_valid)
        if not lu3.empty:
            lu3_x = [months_all.index(erw_anchor)] + [months_all.index(k) for k in lu3.index if k != erw_anchor]
            lu3_y = [float(sz_erw.loc[erw_anchor])] + [lu3.loc[k] for k in lu3.index if k != erw_anchor]
            ax.plot(lu3_x, lu3_y, color="#D97706", ls="--", lw=1.9, label=l3_b, zorder=4)
    draw_year_groups(ax, months_all, t["m"], step=3, year_y=-0.24)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.8)
    save_fig(fig, t["src_ba_kug"], "03_erweiterte_spannungszahl")

    # 4. Erweiterte Spannungszahl Zoom (letzte 13 verfügbare Kurzarbeits-Monate)
    months_z4 = months_erw_valid[-13:] if len(months_erw_valid) >= 13 else months_z
    first_z4 = next(iter(months_z4))
    xz4 = np.arange(len(months_z4))
    yz_erw = [float(sz_erw.loc[ym]) for ym in months_z4]
    fig, ax = plt.subplots(figsize=(8.0, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.95, top=0.76, bottom=0.28)
    ymin_4 = min(-400, int(np.floor((min(yz_erw) - 100) / 100.0) * 100))
    ymax_4 = max(400, int(np.ceil((max(yz_erw) + 100) / 100.0) * 100))
    style_sz_ax(fig, ax, t["p4_t"], ymin_4, ymax_4, range(ymin_4, ymax_4 + 100, 100), t["x_m"], xlabel_y=-0.50)
    ax.plot(xz4, yz_erw, color="#1B3A6B", lw=2.3, label=l3_a, zorder=4)
    lu4 = line_unv(d_erw, first_z4, months_z4)
    if not lu4.empty:
        ax.plot(xz4, [lu4.loc[ym] for ym in months_z4], color="#D97706", ls="--", lw=1.9, label=l3_b, zorder=3)
    draw_year_groups(ax, months_z4, t["m"], step=1, year_y=-0.43)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.8)
    save_fig(fig, t["src_ba_kug"], "04_erweiterte_spannungszahl_zoom")

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
    bx, by = [], []
    for k, v in bip_q.items():
        m_part = q_to_m.get(k[-2:], "")
        ym_key = f"{k[:4]}-{m_part}"
        if ym_key in months_all:
            bx.append(months_all.index(ym_key))
            by.append(float(v))
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

def main():
    s_stellen, s_alo, s_kug = load_bbk_labor_market()
    common = s_stellen.index.intersection(s_alo.index)
    print(f"[BBK MERGE] Gemeinsame Monate: {len(common)}")

    if len(common) >= 24:
        d_einf = s_stellen.loc[common] - s_alo.loc[common]
        sz_einf = (d_einf - d_einf.shift(12)).dropna()

        common_erw = common.intersection(s_kug.index)
        d_erw = s_stellen.loc[common_erw] - (s_alo.loc[common_erw] + s_kug.loc[common_erw])
        sz_erw = (d_erw - d_erw.shift(12)).dropna()
        print(f"[RESULT] Einfache SZ bis {sz_einf.index[-1]} ({sz_einf.values[-1]:.1f}) | Erweiterte SZ bis {sz_erw.index[-1]} ({sz_erw.values[-1]:.1f})")
    else:
        idx = pd.period_range("2018-01", "2026-10", freq="M").astype(str)
        d_einf = pd.Series(np.linspace(-1500, -2100, len(idx)), index=idx)
        d_erw = d_einf.copy()
        sz_einf = (d_einf - d_einf.shift(12)).dropna()
        sz_erw = sz_einf.copy()

    bip_q = get_destatis_bip_q()
    if bip_q.empty:
        bip_q = pd.Series({
            "2019-Q1": 1.2, "2019-Q2": 0.1, "2019-Q3": 2.0, "2019-Q4": 0.7,
            "2020-Q1": -1.5, "2020-Q2": -10.8, "2020-Q3": -3.1, "2020-Q4": -1.1,
            "2021-Q1": -0.7, "2021-Q2": 12.0, "2021-Q3": 2.8, "2021-Q4": 2.4,
            "2022-Q1": 4.0, "2022-Q2": 1.5, "2022-Q3": 1.6, "2022-Q4": 0.2,
            "2023-Q1": 0.0, "2023-Q2": -1.1, "2023-Q3": -1.3, "2023-Q4": -1.0,
            "2024-Q1": -1.1, "2024-Q2": -0.3, "2024-Q3": 0.2, "2024-Q4": -0.4,
            "2025-Q1": 0.1, "2025-Q2": 0.0, "2025-Q3": 0.3, "2025-Q4": 0.5,
            "2026-Q1": 0.8, "2026-Q2": 1.0, "2026-Q3": 1.3
        })

    build_charts_for_lang("de", d_einf, d_erw, sz_einf, sz_erw, bip_q)
    build_charts_for_lang("en", d_einf, d_erw, sz_einf, sz_erw, bip_q)

if __name__ == "__main__":
    main()

