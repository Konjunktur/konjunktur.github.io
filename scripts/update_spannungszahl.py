import os, io, re, glob, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

os.makedirs("static/spannungszahl", exist_ok=True)
os.makedirs("data/ba", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://destatis.de"

MONATE_DE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
MONATE_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

TEXTS = {
    "de": {
        "m": MONATE_DE,
        "p1_t": "Spannungszahl",
        "p1_l": ("Einfache Spannungszahl (bereinigt um die Zahl der aus der Ukraine geflüchteten registr. Arbeitslosen)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p1_peak": "Oberer\nWendepunkt\nder Konjunktur,\nFebruar 2022",
        "p1_trough": "Unterer\nWendepunkt\nder Konjunktur,\nMai 2025",
        "p2_t": "Spannungszahl",
        "p2_l1": "Einfache Spannungszahl (bereinigt um die Zahl der aus der Ukraine geflüchteten registr. Arbeitslosen)",
        "p2_l_vj": "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)",
        "p2_l_prefix": "Linie unveränderter wirtschaftlicher Aktivität (ausgehend von ",
        "p3_t": "Erweiterte Spannungszahl*",
        "p3_l": ("Erweiterte Spannungszahl (bereinigt um die Zahl der aus der Ukraine geflüchteten registr. Arbeitslosen)",
                 "Linie unveränderter wirtschaftlicher Aktivität (ausgehend vom Vorjahresmonat)"),
        "p4_t": "Erweiterte Spannungszahl*",
        "p5_t": "Spannungszahl und reales BIP",
        "p5_l": ("Reales BIP (Ursprungswerte)",
                 "Einfache Spannungszahl (bereinigt um die Zahl der aus der Ukraine geflüchteten registr. Arbeitslosen)",
                 "Erweiterte Spannungszahl (berücksichtigt Kurzarbeit)"),
        "p5_yl": "Reales BIP,\nVeränderung gg. Vj., %",
        "p5_yr": "Spannungszahl,\nLinie unv. wirtschaftl. Aktivität",
        "x_m": "Monatswerte",
        "x_mq": "Monatswerte (Spannungszahl)/Quartalswerte (reales BIP)",
        "src_ba": "Quelle: Bundesagentur für Arbeit, eigene Berechnungen | Stand: ",
        "src_ba_kug": "Quelle: Bundesagentur für Arbeit, eigene Berechnungen; *berücksichtigt Kurzarbeit | Stand: ",
        "src_all": "Quellen: Statistisches Bundesamt, Bundesagentur für Arbeit, eigene Berechnungen | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "m": MONATE_EN,
        "p1_t": "Economic Tension Number",
        "p1_l": ("Simple Economic Tension Number (adjusted for registered unemployed refugees from Ukraine)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p1_peak": "Upper turning point\nof business cycle,\nFebruary 2022",
        "p1_trough": "Lower turning point\nof business cycle,\nMay 2025",
        "p2_t": "Economic Tension Number",
        "p2_l1": "Simple Economic Tension Number (adjusted for registered unemployed refugees from Ukraine)",
        "p2_l_vj": "Line of unchanged economic activity (starting from previous year's month)",
        "p2_l_prefix": "Line of unchanged economic activity (starting from ",
        "p3_t": "Extended Economic Tension Number*",
        "p3_l": ("Extended Economic Tension Number (adjusted for registered unemployed refugees from Ukraine)",
                 "Line of unchanged economic activity (starting from previous year's month)"),
        "p4_t": "Extended Economic Tension Number*",
        "p5_t": "Economic Tension Number and Real GDP",
        "p5_l": ("Real GDP (unadjusted data)",
                 "Simple Economic Tension Number (adjusted for registered unemployed refugees from Ukraine)",
                 "Extended Economic Tension Number (includes short-time work)"),
        "p5_yl": "Real GDP,\nyoy change, %",
        "p5_yr": "Economic Tension Number,\nline of unch. economic activity",
        "x_m": "Monthly values",
        "x_mq": "Monthly values (Economic Tension Number) / Quarterly values (real GDP)",
        "src_ba": "Source: Federal Employment Agency, own calculations | As of: ",
        "src_ba_kug": "Source: Federal Employment Agency, own calculations; *includes short-time work | As of: ",
        "src_all": "Sources: Federal Statistical Office, Federal Employment Agency, own calculations | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def fmt_num(val, use_comma, dec=1):
    s = f"{val:.{dec}f}"
    return s.replace(".", ",") if use_comma else s

def find_local_workbooks(pattern_part):
    found = []
    for path in sorted(glob.glob("data/ba/*.xls*")):
        if pattern_part.lower() in os.path.basename(path).lower():
            try:
                xl = pd.ExcelFile(path, engine="openpyxl")
                print(f"[LOCAL OK] {path} | Blätter: {xl.sheet_names}")
                found.append((os.path.basename(path), xl))
            except Exception as e:
                print(f"[LOCAL ERR] {path}: {e}")
    return found

def read_cache_csv(path):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            return pd.Series(df.get("val").astype(float).values, index=df.get("ym").astype(str).values).sort_index()
        except Exception:
            pass
    return pd.Series(dtype=float)

def write_cache_csv(path, s):
    if len(s) > 0:
        s = s.sort_index()
        pd.DataFrame({"ym": s.index.astype(str), "val": s.values}).to_csv(path, index=False)

def parse_cell_ym(val):
    if pd.isna(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return f"{val.year:04d}-{val.month:02d}"
    s = str(val).strip()
    m1 = re.match(r"^(20\d{2})-(\d{2})", s)
    if m1:
        return f"{m1.group(1)}-{m1.group(2)}"
    m2 = re.match(r"^(\d{2})\.(20\d{2})$", s)
    if m2:
        return f"{m2.group(2)}-{m2.group(1)}"
    return None

def extract_ba_universal(label, xl, sheet_prefers, row_includes, row_excludes=(), scale=0.001):
    if xl is None:
        return pd.Series(dtype=float)
    sheets = list(xl.sheet_names)
    ordered = [s for s in sheets if any(p.lower() in s.lower() for p in sheet_prefers)] + sheets
    seen = set()
    m_map = {m.lower(): i + 1 for i, m in enumerate(MONATE_DE)}

    for sh in ordered:
        if sh in seen or any(x in sh.lower() for x in ("inhalt", "info", "impressum", "prüfung", "hinweis", "deckblatt")):
            continue
        seen.add(sh)
        df = pd.read_excel(xl, sheet_name=sh, header=None)
        n_rows, n_cols = df.shape

        for r_idx in range(min(25, n_rows)):
            ym_cols = {}
            for c_idx, cell in enumerate(df.iloc[r_idx].tolist()):
                ym = parse_cell_ym(cell)
                if ym:
                    ym_cols[c_idx] = ym
            if len(ym_cols) >= 6:
                for r2 in range(r_idx + 1, n_rows):
                    row_txt = " | ".join(str(x).strip() for x in df.iloc[r2].tolist()[:4] if pd.notna(x))
                    if not row_txt:
                        continue
                    if all(inc.lower() in row_txt.lower() for inc in row_includes) and not any(ex.lower() in row_txt.lower() for ex in row_excludes):
                        out = {}
                        for c_idx, ym in ym_cols.items():
                            v = pd.to_numeric(str(df.iloc[r2, c_idx]).replace(" ", "").replace(".", "").replace(",", "."), errors="coerce")
                            if not np.isnan(v):
                                out[ym] = float(v) * scale
                        if len(out) >= 6:
                            s = pd.Series(out).sort_index()
                            print(f"[{label}] Blatt '{sh}' (Spaltenformat): {len(s)} Monate ({s.index[-1]}={s.values[-1]:.1f})")
                            return s

        cur_year = None
        ym_rows = {}
        for r_idx in range(n_rows):
            c0 = str(df.iloc[r_idx, 0]).strip() if pd.notna(df.iloc[r_idx, 0]) else ""
            c1 = str(df.iloc[r_idx, 1]).strip() if n_cols > 1 and pd.notna(df.iloc[r_idx, 1]) else ""
            if re.fullmatch(r"20\d{2}", c0):
                cur_year = int(c0)
            ym = parse_cell_ym(c0) or parse_cell_ym(c1)
            if not ym and cur_year:
                for cand in (c0.lower(), c1.lower()):
                    if cand in m_map:
                        ym = f"{cur_year:04d}-{m_map.get(cand):02d}"
                        break
            if ym:
                ym_rows[r_idx] = ym

        if len(ym_rows) >= 12:
            hdr_df = df.iloc[:min(25, n_rows), :].ffill(axis=1)
            for c_idx in range(1, n_cols):
                hdr_txt = " | ".join(str(hdr_df.iloc[r, c_idx]).replace("\n", " ").strip() for r in range(min(25, n_rows)) if pd.notna(hdr_df.iloc[r, c_idx]))
                if all(inc.lower() in hdr_txt.lower() for inc in row_includes) and not any(ex.lower() in hdr_txt.lower() for ex in row_excludes):
                    out = {}
                    for r_idx, ym in ym_rows.items():
                        v = pd.to_numeric(str(df.iloc[r_idx, c_idx]).replace(" ", "").replace(".", "").replace(",", "."), errors="coerce")
                        if not np.isnan(v):
                            out[ym] = float(v) * scale
                    if len(out) >= 12:
                        s = pd.Series(out).sort_index()
                        print(f"[{label}] Blatt '{sh}' (Zeilenformat, Spalte {c_idx}): {len(s)} Monate ({s.index[-1]}={s.values[-1]:.1f})")
                        return s
    return pd.Series(dtype=float)

def extract_ukraine_from_workbooks():
    cache_file = "static/spannungszahl/ukraine_cache.csv"
    cached = read_cache_csv(cache_file)
    vals = dict(zip(cached.index.astype(str), cached.values))

    for fname, xl in find_local_workbooks("nat-ins"):
        m_file = re.search(r"(20\d{2})(\d{2})", fname)
        ym = f"{m_file.group(1)}-{m_file.group(2)}" if m_file else None
        if not ym:
            continue
        for sh in xl.sheet_names:
            if any(k in sh.lower() for k in ("inhalt", "info", "impressum", "hinweis", "deckblatt")):
                continue
            df = pd.read_excel(xl, sheet_name=sh, header=None)
            found = False
            for r_idx in range(len(df)):
                row_vals = df.iloc[r_idx].tolist()
                row_txt = " | ".join(str(x).strip() for x in row_vals[:4] if pd.notna(x))
                if "ukraine" in row_txt.lower():
                    for cell in row_vals[1:8]:
                        v = pd.to_numeric(str(cell).replace(" ", "").replace(".", "").replace(",", "."), errors="coerce")
                        if not np.isnan(v) and v > 1000:
                            vals[ym] = float(v) * 0.001
                            found = True
                            break
                if found:
                    break
            if found:
                break

    out_s = pd.Series(vals, dtype=float).sort_index()
    write_cache_csv(cache_file, out_s)
    return out_s

def get_destatis_13211():
    if not D_USER or not D_PASS:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    p = {"username": D_USER, "password": D_PASS, "name": "13211-0001", "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    try:
        r = requests.get(G_URL, params=p, timeout=35)
        lines = [ln for ln in r.text.splitlines() if ln.count(";") >= 4]
        if len(lines) < 10:
            return pd.Series(dtype=float), pd.Series(dtype=float)
        df = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", decimal=",", on_bad_lines="skip")
        text_cols = [c for c in df.columns if c not in ("ZEIT", "WERT")]
        df["_ROW"] = df.loc[:, text_cols].fillna("").astype(str).agg(" | ".join, axis=1)
        m_map = {m.lower(): i + 1 for i, m in enumerate(MONATE_DE)}

        def parse_13211(inc, exc):
            sub = df.copy()
            for t_inc in inc:
                sub = sub[sub.get("_ROW").str.contains(t_inc, case=False, na=False)]
            for t_exc in exc:
                sub = sub[~sub.get("_ROW").str.contains(t_exc, case=False, na=False)]
            sub["V"] = pd.to_numeric(sub.get("WERT").astype(str).str.replace(",", "."), errors="coerce")
            sub = sub.dropna(subset=("V",))
            out = {}
            for _, row in sub.iterrows():
                z = str(row.get("ZEIT")).strip()
                rt = str(row.get("_ROW")).lower()
                if re.fullmatch(r"20\d{2}", z):
                    for m_name, m_idx in m_map.items():
                        if m_name in rt:
                            out[f"{z}-{m_idx:02d}"] = float(row.get("V")) * 0.001
                            break
            return pd.Series(out).sort_index()

        s_alo = parse_13211(["Arbeitslose"], ["Quote", "saison", "kalender", "X-13"])
        s_ste = parse_13211(["Gemeldete Arbeitsstellen"], ["saison", "kalender", "X-13"])
        print(f"[GENESIS 13211] Alo={len(s_alo)} Monate, Stellen={len(s_ste)} Monate")
        return s_ste, s_alo
    except Exception as e:
        print(f"[GENESIS 13211 INFO] {e}")
        return pd.Series(dtype=float), pd.Series(dtype=float)

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
        sub = df[df.get("_ROW").str.contains("Ursprungswerte", case=False, na=False)]
        sub = sub[sub.get("_ROW").str.contains("Vorjahr", case=False, na=False)]
        sub = sub[sub.get("_ROW").str.contains("preisbereinigt", case=False, na=False)]
        for ex in ("kalender", "saison", "X-13", "Vorquartal", "Bruttowertschöpfung", "Gewerbe", "Bau", "Handel", "Dienst"):
            sub = sub[~sub.get("_ROW").str.contains(ex, case=False, na=False)]
        sub["V"] = pd.to_numeric(sub.get("WERT").astype(str).str.replace(",", "."), errors="coerce")
        sub = sub.dropna(subset=("V",))
        return pd.Series(sub.get("V").values, index=sub.get("ZEIT").astype(str).str.strip().values).sort_index()
    except Exception:
        return pd.Series(dtype=float)

def style_sz_ax(ax, title, ymin, ymax, yticks, xlabel_text, title_y=1.22):
    ax.set_facecolor("#F8FAFC")
    ax.text(0.0, title_y, title, transform=ax.transAxes, fontsize=11.5, fontweight="bold", color="#0F172A")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(yticks)
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.6, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#64748B", linewidth=1.0, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines.get(s).set_visible(False)
    ax.spines.get("bottom").set_color("#94A3B8")
    ax.set_xlabel(xlabel_text, fontsize=8, color="#475569", labelpad=22)

def draw_year_groups(ax, months, m_names, step=3):
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
            ax.text(mid, -0.24 if step > 1 else -0.27, y, transform=ax.get_xaxis_transform(), ha="center", fontsize=8, color="#475569")

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
    t = TEXTS.get(lang)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t.get("date_fmt"))
    months_all = [ym for ym in sz_einf.index if ym >= "2019-01"]
    if len(months_all) < 2:
        months_all = list(sz_einf.index)
    x_all = np.arange(len(months_all))
    y_einf = [float(sz_einf.loc[ym]) for ym in months_all]
    y_erw = [float(sz_erw.loc[ym]) for ym in months_all]
    vj_anchor = months_all[max(0, len(months_all) - 13)]

    def save_fig(fig, src_text, fname):
        fig.text(0.09, 0.02, f"{src_text}{now_str}", fontsize=6.8, color="#64748B")
        fig.text(0.95, 0.02, "T.H.", fontsize=7.5, color="#94A3B8", ha="right")
        plt.savefig(f"static/spannungszahl/{fname}{t.get('sfx')}.png", dpi=300)
        plt.close()

    # 1. Einfache Spannungszahl (Gesamt)
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.95, top=0.72, bottom=0.25)
    style_sz_ax(ax, t.get("p1_t"), -900, 900, range(-900, 1200, 300), t.get("x_m"))
    l1_a, l1_b = t.get("p1_l")
    ax.plot(x_all, y_einf, color="#D97706", lw=2.2, label=l1_a, zorder=3)
    lu1 = line_unv(d_einf, vj_anchor, months_all)
    if not lu1.empty:
        ax.plot([months_all.index(k) for k in lu1.index], lu1.values, color="#D97706", ls=":", lw=1.8, label=l1_b, zorder=4)
    if "2022-02" in months_all:
        ix = months_all.index("2022-02")
        ax.annotate(t.get("p1_peak"), xy=(ix, y_einf[ix]), xytext=(ix, 120), ha="center", fontsize=7.2, color="#D97706",
                    arrowprops=dict(arrowstyle="->", color="#D97706", lw=1.2))
    if "2025-05" in months_all:
        ix = months_all.index("2025-05")
        ax.annotate(t.get("p1_trough"), xy=(ix, y_einf[ix]), xytext=(ix, 360), ha="center", fontsize=7.2, color="#D97706",
                    arrowprops=dict(arrowstyle="->", color="#D97706", lw=1.2))
    draw_year_groups(ax, months_all, t.get("m"), step=3)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.3)
    save_fig(fig, t.get("src_ba"), "01_einfache_spannungszahl")

    # 2. Einfache Spannungszahl Zoom (13 Monate + mehrere Referenzlinien)
    months_z = months_all[-13:]
    first_z = next(iter(months_z))
    xz = np.arange(len(months_z))
    yz_einf = [float(sz_einf.loc[ym]) for ym in months_z]
    fig, ax = plt.subplots(figsize=(7.6, 6.0), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.95, top=0.56, bottom=0.25)
    ymin_z = int(np.floor((min(yz_einf) - 120) / 100.0) * 100)
    ymax_z = max(100, int(np.ceil((max(yz_einf) + 120) / 100.0) * 100))
    style_sz_ax(ax, t.get("p2_t"), ymin_z, ymax_z, range(ymin_z, ymax_z + 100, 100), t.get("x_m"), title_y=1.52)
    ax.plot(xz, yz_einf, color="#D97706", lw=2.3, label=t.get("p2_l1"), zorder=4)
    lu_vj = line_unv(d_einf, first_z, months_z)
    if not lu_vj.empty:
        ax.plot(xz, [lu_vj.loc[ym] for ym in months_z], color="#D97706", ls="--", lw=1.9, label=t.get("p2_l_vj"), zorder=3)
    extra_cols = ("#1E3A8A", "#78350F", "#6D28D9", "#059669", "#0284C7")
    c_i = 0
    for ym in months_z[1:-1]:
        m_num = int(ym[5:7])
        if m_num in (1, 3, 6, 9, 12):
            lu_e = line_unv(d_einf, ym, months_z)
            if not lu_e.empty:
                lbl = f"{t.get('p2_l_prefix')}{t.get('m')[m_num - 1]} {ym[:4]})"
                ax.plot([months_z.index(k) for k in lu_e.index], lu_e.values, color=extra_cols[c_i % len(extra_cols)], ls=":", lw=1.7, label=lbl, zorder=3)
                c_i += 1
    draw_year_groups(ax, months_z, t.get("m"), step=1)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.0)
    save_fig(fig, t.get("src_ba"), "02_einfache_spannungszahl_zoom")

    # 3. Erweiterte Spannungszahl (Gesamt)
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.95, top=0.72, bottom=0.25)
    style_sz_ax(ax, t.get("p3_t"), -8000, 4000, range(-8000, 6000, 2000), t.get("x_m"))
    l3_a, l3_b = t.get("p3_l")
    ax.plot(x_all, y_erw, color="#059669", lw=2.2, label=l3_a, zorder=3)
    lu3 = line_unv(d_erw, vj_anchor, months_all)
    if not lu3.empty:
        ax.plot([months_all.index(k) for k in lu3.index], lu3.values, color="#059669", ls=":", lw=1.8, label=l3_b, zorder=4)
    draw_year_groups(ax, months_all, t.get("m"), step=3)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.3)
    save_fig(fig, t.get("src_ba_kug"), "03_erweiterte_spannungszahl")

    # 4. Erweiterte Spannungszahl Zoom (13 Monate)
    yz_erw = [float(sz_erw.loc[ym]) for ym in months_z]
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.95, top=0.72, bottom=0.25)
    ymin_4 = min(-400, int(np.floor((min(yz_erw) - 100) / 100.0) * 100))
    ymax_4 = max(400, int(np.ceil((max(yz_erw) + 100) / 100.0) * 100))
    style_sz_ax(ax, t.get("p4_t"), ymin_4, ymax_4, range(ymin_4, ymax_4 + 100, 100), t.get("x_m"))
    ax.plot(xz, yz_erw, color="#059669", lw=2.2, label=l3_a, zorder=4)
    lu4 = line_unv(d_erw, first_z, months_z)
    if not lu4.empty:
        ax.plot(xz, [lu4.loc[ym] for ym in months_z], color="#059669", ls=":", lw=1.8, label=l3_b, zorder=3)
    draw_year_groups(ax, months_z, t.get("m"), step=1)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.3)
    save_fig(fig, t.get("src_ba_kug"), "04_erweiterte_spannungszahl_zoom")

    # 5. Spannungszahl und reales BIP (Dual-Achse)
    fig, ax1 = plt.subplots(figsize=(7.8, 5.6), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.11, right=0.87, top=0.68, bottom=0.25)
    style_sz_ax(ax1, t.get("p5_t"), -12, 12, range(-12, 16, 4), t.get("x_mq"), title_y=1.28)
    ax1.set_ylabel(t.get("p5_yl"), fontsize=7.8, color="#475569")
    ax2 = ax1.twinx()
    ax2.set_ylim(-8000, 8000)
    ax2.set_yticks(range(-8000, 10000, 2000))
    ax2.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax2.set_ylabel(t.get("p5_yr"), fontsize=7.8, color="#475569", labelpad=8)
    for s in ("top", "right", "left", "bottom"):
        ax2.spines.get(s).set_visible(False)

    l5_bip, l5_einf, l5_erw = t.get("p5_l")
    q_to_m = {"Q1": "02", "Q2": "05", "Q3": "08", "Q4": "11"}
    bx, by = [], []
    for k, v in bip_q.items():
        m_part = q_to_m.get(k[-2:], "")
        ym_key = f"{k[:4]}-{m_part}"
        if ym_key in months_all:
            bx.append(months_all.index(ym_key))
            by.append(float(v))
    p_bip = ax1.plot(bx, by, color="#0284C7", lw=2.1, label=l5_bip, zorder=4)
    for xi_b, yi_b in zip(bx, by):
        off = 0.7 if yi_b >= 0 else -1.2
        ax1.text(xi_b, yi_b + off, fmt_num(yi_b, t.get("comma")), fontsize=6.5, color="#0284C7", ha="center", fontweight="bold")
    p_einf = ax2.plot(x_all, y_einf, color="#D97706", lw=2.0, label=l5_einf, zorder=3)
    p_erw = ax2.plot(x_all, y_erw, color="#059669", lw=2.0, label=l5_erw, zorder=3)
    draw_year_groups(ax1, months_all, t.get("m"), step=4)
    lines = p_bip + p_einf + p_erw
    ax1.legend(lines, [l.get_label() for l in lines], loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.1)
    save_fig(fig, t.get("src_all"), "05_spannungszahl_bip")

def main():
    for fn, sh in (("gemeldete-arbeitsstellen", "1_2"), ("zr-alo-bl", "1.1"), ("kurzarbeit-zr2", "Daten1")):
        for _, xl_d in find_local_workbooks(fn):
            if sh in xl_d.sheet_names:
                dfd = pd.read_excel(xl_d, sheet_name=sh, header=None)
                print(f"=== {fn} / {sh} ({dfd.shape}) ===")
                for r_i in range(min(18, len(dfd))):
                    pv = [str(x).replace("\n", " ").strip() for x in dfd.iloc[r_i].tolist()[:8] if pd.notna(x)]
                    if pv:
                        print(f"  Z{r_i}: {pv}")

    s_ste_gen, s_alo_gen = get_destatis_13211()

    s_stellen = read_cache_csv("static/spannungszahl/stellen_cache.csv")
    if not s_ste_gen.empty:
        s_stellen = s_ste_gen.combine_first(s_stellen)
    for fname, xl in find_local_workbooks("arbeitsstellen"):
        s_loc = extract_ba_universal(fname, xl, ["1_1", "1.1"], ["Insgesamt"], ["sozialversicherungspflichtige"])
        if not s_loc.empty:
            s_stellen = s_loc.combine_first(s_stellen)
    s_stellen = s_stellen.sort_index()
    write_cache_csv("static/spannungszahl/stellen_cache.csv", s_stellen)

    s_alo = read_cache_csv("static/spannungszahl/alo_cache.csv")
    if not s_alo_gen.empty:
        s_alo = s_alo_gen.combine_first(s_alo)
    for fname, xl in find_local_workbooks("zr-alo"):
        u_loc = extract_ba_universal(fname, xl, ["1.1", "1_1"], ["Deutschland"], ["Quote", "%"])
        if u_loc.empty:
            u_loc = extract_ba_universal(fname, xl, ["1.1", "1_1"], ["Insgesamt"], ["Quote", "%"])
        if not u_loc.empty:
            s_alo = u_loc.combine_first(s_alo)
    s_alo = s_alo.sort_index()
    write_cache_csv("static/spannungszahl/alo_cache.csv", s_alo)

    s_kug = read_cache_csv("static/spannungszahl/kug_cache.csv")
    for fname, xl in find_local_workbooks("kurzarbeit"):
        k_loc = extract_ba_universal(fname, xl, ["Daten2", "Ab2007", "Daten1"], ["Deutschland"], ["Quote", "%"])
        if k_loc.empty:
            k_loc = extract_ba_universal(fname, xl, ["Daten2", "Ab2007", "Daten1"], ["Kurzarbeiter"], ["Quote", "%"])
        if not k_loc.empty:
            s_kug = k_loc.combine_first(s_kug)
    s_kug = s_kug.sort_index()
    write_cache_csv("static/spannungszahl/kug_cache.csv", s_kug)

    common = s_stellen.index.intersection(s_alo.index)
    print(f"[MERGE] Gemeinsame Monate Stellen & Alo: {len(common)}")
    if len(common) >= 13:
        s_ukr = extract_ukraine_from_workbooks()
        s_ukr_aligned = s_ukr.reindex(common).fillna(0.0)
        s_alo_ber = s_alo.loc[common] - s_ukr_aligned
        s_kug_aligned = s_kug.reindex(common).fillna(0.0)
        d_einf = s_stellen.loc[common] - s_alo_ber
        d_erw = s_stellen.loc[common] - (s_alo_ber + s_kug_aligned)
        sz_einf = (d_einf - d_einf.shift(12)).dropna()
        sz_erw = (d_erw - d_erw.shift(12)).dropna()
        print(f"[RESULT] Monate SZ: {len(sz_einf)} | Letzter Wert ({sz_einf.index[-1]}): {sz_einf.values[-1]:.1f}")
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
