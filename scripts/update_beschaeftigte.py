import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/beschaeftigte", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"

MONATE_DE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
MONATE_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")

WZ_META = [
    ("WZ08-10", "Herstellung von Nahrungs- und Futtermitteln", "Manufacture of food products"),
    ("WZ08-11", "Getränkeherstellung", "Manufacture of beverages"),
    ("WZ08-12", "Tabakverarbeitung", "Manufacture of tobacco products"),
    ("WZ08-13", "Herstellung von Textilien", "Manufacture of textiles"),
    ("WZ08-14", "Herstellung von Bekleidung", "Manufacture of wearing apparel"),
    ("WZ08-15", "Herstellung von Leder, Lederwaren und Schuhen", "Manufacture of leather and related products"),
    ("WZ08-16", "Herstellung von Holz-, Flecht-, Korb- und Korkwaren (ohne Möbel)", "Manufacture of wood and of products of wood and cork (except furniture)"),
    ("WZ08-17", "Herstellung von Papier, Pappe und Waren daraus", "Manufacture of paper and paper products"),
    ("WZ08-18", "Herstellung von Druckerzeugnissen, Vervielfältigung von Ton-, Bild- und Datenträgern", "Printing and reproduction of recorded media"),
    ("WZ08-19", "Kokerei und Mineralölverarbeitung", "Manufacture of coke and refined petroleum products"),
    ("WZ08-20", "Herstellung von chemischen Erzeugnissen", "Manufacture of chemicals and chemical products"),
    ("WZ08-21", "Herstellung von pharmazeutischen Erzeugnissen", "Manufacture of basic pharmaceutical products and pharmaceutical preparations"),
    ("WZ08-22", "Herstellung von Gummi- und Kunststoffwaren", "Manufacture of rubber and plastic products"),
    ("WZ08-23", "Herstellung von Glas und Glaswaren, Keramik, Verarbeitung von Steinen und Erden", "Manufacture of other non-metallic mineral products"),
    ("WZ08-24", "Metallerzeugung und -bearbeitung", "Manufacture of basic metals"),
    ("WZ08-25", "Herstellung von Metallerzeugnissen", "Manufacture of fabricated metal products (except machinery and equipment)"),
    ("WZ08-26", "Herstellung von DV-Geräten, elektronischen und optischen Erzeugnissen", "Manufacture of computer, electronic and optical products"),
    ("WZ08-27", "Herstellung von elektrischen Ausrüstungen", "Manufacture of electrical equipment"),
    ("WZ08-28", "Maschinenbau", "Manufacture of machinery and equipment n.e.c."),
    ("WZ08-29", "Herstellung von Kraftwagen und Kraftwagenteilen", "Manufacture of motor vehicles, trailers and semi-trailers"),
    ("WZ08-30", "Sonstiger Fahrzeugbau", "Manufacture of other transport equipment"),
    ("WZ08-31", "Herstellung von Möbeln", "Manufacture of furniture"),
    ("WZ08-32", "Herstellung von sonstigen Waren", "Other manufacturing"),
    ("WZ08-33", "Reparatur und Installation von Maschinen und Ausrüstungen", "Repair and installation of machinery and equipment"),
]

TEXTS = {
    "de": {
        "m": MONATE_DE,
        "total_code": "WZ08-C",
        "total_name": "Verarbeitendes Gewerbe insgesamt",
        "title_prefix": "Beschäftigte",
        "sub": "Tätige Personen in Betrieben mit 20 und mehr tätigen Personen (Ursprungswerte)",
        "leg": "Beschäftigte (Ursprungswerte)",
        "xlabel": "Monatswerte",
        "diff_title": "Differenz",
        "diff_unit": "Beschäftigte",
        "src": "Quelle: Statistisches Bundesamt | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": ""
    },
    "en": {
        "m": MONATE_EN,
        "total_code": "WZ08-C",
        "total_name": "Manufacturing total",
        "title_prefix": "Employees",
        "sub": "Persons employed in local units with 20 or more persons employed (unadjusted data)",
        "leg": "Employees (unadjusted data)",
        "xlabel": "Monthly values",
        "diff_title": "Change",
        "diff_unit": "employees",
        "src": "Source: Federal Statistical Office | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en"
    }
}

def fmt_int(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{int(round(float(val))):,}"
    return s.replace(",", ".") if use_comma else s

def fmt_signed_int(val, use_comma):
    iv = int(round(float(val)))
    sign = "+" if iv > 0 else ("-" if iv < 0 else "±")
    s = f"{abs(iv):,}"
    if use_comma:
        s = s.replace(",", ".")
    return f"{sign}{s}"

def fmt_signed_pct(val, use_comma):
    fv = float(val)
    sign = "+" if fv > 0.005 else ("-" if fv < -0.005 else "±")
    s = f"{abs(fv):.1f}"
    if use_comma:
        s = s.replace(".", ",")
    return f"{sign}{s} %"

def _extract_payload(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def fetch_42111_0004():
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": "42111-0004", "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": "2019"}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    r.raise_for_status()
    raw = _extract_payload(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        rj.raise_for_status()
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            raise RuntimeError("Destatis Job-ID nicht gefunden für 42111-0004")
        raw = ""
        for _ in range(24):
            time.sleep(2.5)
            txt = _extract_payload(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
        if not raw:
            raise RuntimeError("Destatis Job für 42111-0004 nicht rechtzeitig fertig.")

    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)

    df = df[
        (df["2_variable_attribute_code"].astype(str).str.strip() == "DG") &
        (df["3_variable_attribute_code"].astype(str).str.strip() == "BETRIEBE") &
        (df["value_variable_code"].astype(str).str.strip() == "ERW012")
    ].copy()

    m_num = df["1_variable_attribute_code"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(2)
    df["ZEIT"] = df["time"].astype(str).str.strip() + "-" + m_num
    df["WZ"] = df["4_variable_attribute_code"].astype(str).str.strip()
    df["V"] = pd.to_numeric(df["value"].astype(str).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["V"])
    df = df[df["ZEIT"] >= "2019-01"].copy()

    piv = df.pivot_table(index="ZEIT", columns="WZ", values="V", aggfunc="first").sort_index()
    wz_codes = [c for c, _, _ in WZ_META if c in piv.columns]
    piv = piv[wz_codes].dropna(how="all")
    piv["WZ08-C"] = piv[wz_codes].sum(axis=1, min_count=len(wz_codes))
    return piv

def detect_peaks_and_lows(y_vals):
    n = len(y_vals)
    if n == 0:
        return []
    if n <= 3:
        return list(range(n))
    pts = {0, n - 1}
    w = max(5, n // 12)
    for i in range(1, n - 1):
        left = max(0, i - w)
        right = min(n, i + w + 1)
        win = y_vals[left:right]
        if y_vals[i] == max(win) and y_vals[i] > y_vals[i - 1] and y_vals[i] >= y_vals[i + 1]:
            pts.add(i)
        elif y_vals[i] == min(win) and y_vals[i] < y_vals[i - 1] and y_vals[i] <= y_vals[i + 1]:
            pts.add(i)
    sorted_pts = sorted(pts)
    filtered = [sorted_pts[0]]
    min_gap = max(8, n // 10)
    for idx in sorted_pts[1:-1]:
        if idx - filtered[-1] >= min_gap and (n - 1 - idx) >= min_gap:
            filtered.append(idx)
    if sorted_pts[-1] != filtered[-1]:
        filtered.append(sorted_pts[-1])
    return filtered


def draw_year_groups(ax, months, m_names, step=4, year_y=-0.30):
    ticks, labels = [], []
    for i, ym in enumerate(months):
        m = int(ym[5:7])
        if step == 1 or m in (1, 5, 9):
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

def choose_box_corner(y_vals, ymin, ymax):
    n = len(y_vals)
    y_norm = [(v - ymin) / (ymax - ymin) for v in y_vals]
    left_slice = y_norm[:max(1, int(n * 0.48))]
    right_slice = y_norm[min(n - 1, int(n * 0.52)):]

    scores = {
        "bl": min(left_slice),
        "tl": 1.0 - max(left_slice),
        "br": min(right_slice),
        "tr": 1.0 - max(right_slice),
    }
    scores["bl"] += 0.04
    scores["tl"] += 0.02
    return max(scores, key=scores.get)

def render_series_charts(lang, slug, code, title_name, ser):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])

    s_clean = ser.dropna()
    months = list(s_clean.index)
    y_vals = [float(v) for v in s_clean.values]
    x_idx = np.arange(len(months))

    latest_ym = months[-1]
    latest_val = y_vals[-1]
    ref_2019_ym = f"2019-{latest_ym[5:7]}"
    has_ref = ref_2019_ym in s_clean.index
    ref_2019_val = float(s_clean.loc[ref_2019_ym]) if has_ref else y_vals
    ref_used_ym = ref_2019_ym if has_ref else months

    diff_abs = latest_val - ref_2019_val
    diff_pct = ((latest_val / ref_2019_val) - 1.0) * 100.0 if ref_2019_val != 0 else 0.0

    m_ref_name = t["m"][int(ref_used_ym[5:7]) - 1]
    m_cur_name = t["m"][int(latest_ym[5:7]) - 1]
    diff_line_1 = f"{t['diff_title']} {m_ref_name} {ref_used_ym[:4]} – {m_cur_name} {latest_ym[:4]}:"
    diff_line_2 = f"{fmt_signed_int(diff_abs, use_c)} {t['diff_unit']} ({fmt_signed_pct(diff_pct, use_c)})"

    full_title = f"{t['title_prefix']} – {title_name} ({code})"
    key_indices = detect_peaks_and_lows(y_vals)

    ymin_raw, ymax_raw = min(y_vals), max(y_vals)
    span = max(ymax_raw - ymin_raw, ymax_raw * 0.05, 50.0)
    ymin = ymin_raw - span * 0.28
    ymax = ymax_raw + span * 0.30

    corner = choose_box_corner(y_vals, ymin, ymax)
    mpl_pos = {
        "bl": (0.02, 0.05, "left", "bottom"),
        "tl": (0.02, 0.95, "left", "top"),
        "br": (0.98, 0.05, "right", "bottom"),
        "tr": (0.98, 0.95, "right", "top"),
    }[corner]
    plotly_pos = {
        "bl": (0.02, 0.05, "left", "bottom"),
        "tl": (0.02, 0.95, "left", "top"),
        "br": (0.98, 0.05, "right", "bottom"),
        "tr": (0.98, 0.95, "right", "top"),
    }[corner]

    # 1. Statisches PNG
    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.11, right=0.95, top=0.77, bottom=0.28)
    fig.suptitle(full_title, x=0.11, y=0.96, ha="left", fontsize=11.5, fontweight="bold", color="#0F172A")
    fig.text(0.11, 0.915, t["sub"], ha="left", fontsize=8.0, color="#64748B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-1.5, len(months) + 2.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_int(x, use_c)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot(x_idx, y_vals, color="#1B3A6B", lw=2.3, label=t["leg"], zorder=3)
    ax.scatter([x_idx[i] for i in key_indices], [y_vals[i] for i in key_indices], color="#1B3A6B", s=22, zorder=4)

    for idx_k in key_indices:
        yv = y_vals[idx_k]
        if idx_k == len(y_vals) - 1:
            ax.text(x_idx[idx_k] + 0.8, yv, fmt_int(yv, use_c), fontsize=7.5, fontweight="bold", color="#1B3A6B", ha="left", va="center", zorder=5)
            continue
        is_peak = (idx_k == 0 and y_vals <= yv) or (0 < idx_k < len(y_vals) - 1 and yv >= y_vals[idx_k - 1] and yv >= y_vals[idx_k + 1])
        dy = span * 0.048 if is_peak else -span * 0.058
        va = "bottom" if is_peak else "top"
        ha = "left" if idx_k == 0 else "center"
        ax.text(x_idx[idx_k], yv + dy, fmt_int(yv, use_c), fontsize=7.3, fontweight="bold", color="#0F172A", ha=ha, va=va, zorder=5)

    bx_m, by_m, ha_m, va_m = mpl_pos
    ax.text(
        bx_m, by_m, f"{diff_line_1}\n{diff_line_2}",
        transform=ax.transAxes, ha=ha_m, va=va_m, fontsize=7.8, fontweight="bold", color="#0F172A",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#CBD5E1", linewidth=1.0), zorder=6
    )

    draw_year_groups(ax, months, t["m"], step=4, year_y=-0.30)
    ax.text(0.5, -0.37, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=1, frameon=False, fontsize=7.8)
    fig.text(0.11, 0.015, f"{t['src']}{now_str}", fontsize=7.2, color="#64748B")
    fig.text(0.95, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/beschaeftigte/{slug}{t['sfx']}.png", dpi=300)
    plt.close()

    # 2. Interaktives HTML (ohne Scrollbalken)
    fp = go.Figure()
    custom_y = [fmt_int(v, use_c) for v in y_vals]
    fp.add_trace(go.Scatter(
        x=months, y=[round(v) for v in y_vals], customdata=custom_y,
        name=t["leg"], mode="lines", line=dict(color="#1B3A6B", width=2.4),
        hovertemplate=f"{t['title_prefix']}: <b>%{{customdata}}</b><extra></extra>"
    ))
    pos_list = []
    for i in key_indices:
        if i == len(y_vals) - 1:
            pos_list.append("middle right" if y_vals[-2] > y_vals[-1] else "top center")
        elif (i == 0 and y_vals <= y_vals[i]) or (0 < i < len(y_vals) - 1 and y_vals[i] >= y_vals[i - 1]):
            pos_list.append("top center")
        else:
            pos_list.append("bottom center")

    fp.add_trace(go.Scatter(
        x=[months[i] for i in key_indices],
        y=[round(y_vals[i]) for i in key_indices],
        text=[fmt_int(y_vals[i], use_c) for i in key_indices],
        mode="markers+text",
        textposition=pos_list,
        textfont=dict(size=10, color="#0F172A", family="DejaVu Sans, sans-serif"),
        marker=dict(size=6, color="#1B3A6B"),
        showlegend=False, hoverinfo="skip"
    ))

    bx_p, by_p, xa_p, ya_p = plotly_pos
    t_vals = [m for m in months if m.endswith("-01") or m.endswith("-07")]
    fp.update_layout(
        title=dict(text=f"<b>{full_title}</b><br><span style='font-size:11.5px;color:#475569;'>{t['sub']}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="v", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=64, r=42, t=115, b=95), height=470,
        annotations=[
            dict(
                text=f"<b>{diff_line_1}</b><br><b>{diff_line_2}</b>",
                x=bx_p, y=by_p, xref="paper", yref="paper", showarrow=False, align="left",
                xanchor=xa_p, yanchor=ya_p,
                font=dict(size=11, color="#0F172A"),
                bgcolor="white", bordercolor="#CBD5E1", borderwidth=1, borderpad=6
            ),
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", tickformat=",.0f", separatethousands=True, tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    out_html = f"static/beschaeftigte/{slug}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def main():
    piv = fetch_42111_0004()
    latest_row = piv.iloc[-1]

    ranked_wz = sorted(
        [(code, de_lbl, en_lbl, float(latest_row.get(code, 0.0))) for code, de_lbl, en_lbl in WZ_META if code in piv.columns],
        key=lambda item: item[3],
        reverse=True
    )

    ordered_items = [("00_wz08_c_gesamt", "WZ08-C", TEXTS["de"]["total_name"], TEXTS["en"]["total_name"])]
    for rank_idx, (code, de_lbl, en_lbl, _) in enumerate(ranked_wz, start=1):
        slug = f"{rank_idx:02d}_{code.lower().replace('-', '_')}"
        ordered_items.append((slug, code, de_lbl, en_lbl))

    meta_out = []
    for slug, code, de_lbl, en_lbl in ordered_items:
        render_series_charts("de", slug, code, de_lbl, piv[code])
        render_series_charts("en", slug, code, en_lbl, piv[code])
        meta_out.append({"slug": slug, "code": code, "de": de_lbl, "en": en_lbl})

    with open("static/beschaeftigte/order.json", "w", encoding="utf-8") as fh:
        json.dump(meta_out, fh, ensure_ascii=False, indent=2)
    print(f"[OK] {len(ordered_items)} Grafiken (DE & EN) bis {piv.index[-1]} erzeugt.")

if __name__ == "__main__":
    main()
