import os, io, re, csv, json, time, zipfile, requests
from operator import itemgetter
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("static/industrie", exist_ok=True)

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
        "total_name": "Verarbeitendes Gewerbe insgesamt",
        "title_sub": "Umsatz, Arbeitsstunden, Beschäftigte, Löhne – Veränderung gegenüber Vorjahr in %",
        "leg": (
            "Umsatz (linke Skala)",
            "Geleistete Arbeitsstunden (linke Skala)",
            "Bruttolöhne/-gehälter je Beschäftigten (linke Skala)",
            "Beschäftigte (rechte Skala)"
        ),
        "xlabel": "Monatswerte",
        "src": "Quelle: Statistisches Bundesamt, eigene Berechnungen | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": ""
    },
    "en": {
        "m": MONATE_EN,
        "total_name": "Manufacturing total",
        "title_sub": "Turnover, Hours Worked, Employees, Wages – Year-on-year change in %",
        "leg": (
            "Turnover (left scale)",
            "Hours worked (left scale)",
            "Gross wages and salaries per employee (left scale)",
            "Employees (right scale)"
        ),
        "xlabel": "Monthly values",
        "src": "Source: Federal Statistical Office, own calculations | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en"
    }
}


def fmt_rate(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.1f}"
    return s.replace(".", ",") if use_comma else s


def fmt_axis(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    v = round(float(val), 1)
    if v == 0:
        v = 0.0
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if use_comma else s


def _extract_payload(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text


def fetch_42111_0004_multi():
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": "42111-0004", "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": "2018"}
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
    target_vars = {"UMS002", "ARBST1", "ERW012", "VST003"}
    df = df[
        (df["2_variable_attribute_code"].astype(str).str.strip() == "DG") &
        (df["3_variable_attribute_code"].astype(str).str.strip() == "BETRIEBE") &
        (df["value_variable_code"].astype(str).str.strip().isin(target_vars))
    ].copy()
    m_num = df["1_variable_attribute_code"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(2)
    df["ZEIT"] = df["time"].astype(str).str.strip() + "-" + m_num
    df["WZ"] = df["4_variable_attribute_code"].astype(str).str.strip()
    df["VAR"] = df["value_variable_code"].astype(str).str.strip()
    df["V"] = pd.to_numeric(df["value"].astype(str).str.replace(",", "."), errors="coerce")
    df = df.dropna(subset=["V"])
    df = df[df["ZEIT"] >= "2018-01"].copy()
    wz_codes = [c for c, _, _ in WZ_META]
    raw_piv = {}
    for var_code in target_vars:
        sub = df[df["VAR"] == var_code]
        piv = sub.pivot_table(index="ZEIT", columns="WZ", values="V", aggfunc="first").sort_index()
        avail = [c for c in wz_codes if c in piv.columns]
        piv = piv[avail].dropna(how="all")
        piv["WZ08-C"] = piv[avail].sum(axis=1, min_count=len(avail))
        raw_piv[var_code] = piv
    common_idx = raw_piv["ERW012"].index.intersection(raw_piv["UMS002"].index).intersection(raw_piv["ARBST1"].index).intersection(raw_piv["VST003"].index).sort_values()
    for var_code in target_vars:
        raw_piv[var_code] = raw_piv[var_code].reindex(common_idx)
    wage_per_emp = raw_piv["VST003"] / raw_piv["ERW012"]
    yoy = {}
    for key, mat in (("ums", raw_piv["UMS002"]), ("hrs", raw_piv["ARBST1"]), ("emp", raw_piv["ERW012"]), ("wag", wage_per_emp)):
        yoy_mat = (mat / mat.shift(12) - 1.0) * 100.0
        yoy[key] = yoy_mat[yoy_mat.index >= "2019-01"]
    yoy["emp_lvl"] = raw_piv["ERW012"][raw_piv["ERW012"].index >= "2019-01"]
    return yoy


def nice_sym_range(vals):
    clean = [abs(float(v)) for v in vals if v is not None and not np.isnan(v)]
    m = max(clean) if clean else 10.0
    m = max(m * 1.15, 2.0)
    for step in (1.0, 2.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 150.0, 200.0):
        lim = np.ceil(m / step) * step
        if lim / step <= 6:
            return -lim, lim, step
    step = 250.0
    lim = np.ceil(m / step) * step
    return -lim, lim, step


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


def render_multi_charts(lang, slug, code, title_name, s_ums, s_hrs, s_wag, s_emp):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(s_emp.dropna().index)
    v_ums = [float(s_ums.get(m, np.nan)) for m in months]
    v_hrs = [float(s_hrs.get(m, np.nan)) for m in months]
    v_wag = [float(s_wag.get(m, np.nan)) for m in months]
    v_emp = [float(s_emp.get(m, np.nan)) for m in months]
    x_idx = np.arange(len(months))
    l_min, l_max, l_step = nice_sym_range(v_ums + v_hrs + v_wag)
    r_min, r_max, r_step = nice_sym_range(v_emp)
    c_ums, c_hrs, c_wag, c_emp = "#1B3A6B", "#7FA6C9", "#5C9E31", "#E03C31"
    full_title = f"{title_name} ({code})"

    # 1. PNG-Grafik (ohne Y-Achsenbeschriftung über den vertikalen Achsen)
    fig, ax1 = plt.subplots(figsize=(8.2, 5.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.11, right=0.88, top=0.74, bottom=0.27)
    fig.suptitle(full_title, x=0.11, y=0.96, ha="left", fontsize=11.5, fontweight="bold", color="#0F172A")
    fig.text(0.11, 0.915, t["title_sub"], ha="left", fontsize=8.3, color="#475569")
    ax1.set_facecolor("#F8FAFC")
    ax1.set_ylim(l_min, l_max)
    ax1.set_yticks(np.arange(l_min, l_max + l_step * 0.1, l_step))
    ax1.set_xlim(-1.0, len(months) + 2.8)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_axis(x, use_c)))
    ax1.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax1.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=90, length=3, color="#CBD5E1")
    ax1.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax1.axhline(0, color="#64748B", linewidth=0.9, zorder=1)
    ax1.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax1.spines[s].set_visible(False)
    ax1.spines["bottom"].set_color("#94A3B8")

    ax2 = ax1.twinx()
    ax2.set_ylim(r_min, r_max)
    ax2.set_yticks(np.arange(r_min, r_max + r_step * 0.1, r_step))
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_axis(x, use_c)))
    ax2.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    for s in ("top", "right", "left", "bottom"):
        ax2.spines[s].set_visible(False)

    l1, = ax1.plot(x_idx, v_ums, color=c_ums, lw=2.1, label=t["leg"][0], zorder=3)
    l2, = ax1.plot(x_idx, v_hrs, color=c_hrs, lw=1.9, label=t["leg"][1], zorder=3)
    l3, = ax1.plot(x_idx, v_wag, color=c_wag, lw=1.9, label=t["leg"][2], zorder=3)
    l4, = ax2.plot(x_idx, v_emp, color=c_emp, lw=2.2, label=t["leg"][3], zorder=4)

    end_items = []
    for val, col, y0, y1 in (
        (v_ums[-1], c_ums, l_min, l_max),
        (v_hrs[-1], c_hrs, l_min, l_max),
        (v_wag[-1], c_wag, l_min, l_max),
        (v_emp[-1], c_emp, r_min, r_max),
    ):
        if not np.isnan(val):
            norm_y = (val - y0) / (y1 - y0)
            end_items.append([norm_y, val, col])
    end_items.sort(key=itemgetter(0))
    for k in range(1, len(end_items)):
        if end_items[k][0] - end_items[k - 1][0] < 0.055:
            end_items[k][0] = min(0.97, end_items[k - 1][0] + 0.055)
    for norm_y, orig_val, col in end_items:
        ax1.text(
            x_idx[-1] + 0.7, norm_y, fmt_rate(orig_val, use_c),
            transform=ax1.get_xaxis_transform(), fontsize=7.4, fontweight="bold",
            color=col, ha="left", va="center", zorder=6
        )

    draw_year_groups(ax1, months, t["m"], step=4, year_y=-0.30)
    ax1.text(0.5, -0.37, t["xlabel"], transform=ax1.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")
    ax1.legend(handles=[l1, l2, l3, l4], loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, frameon=False, fontsize=7.4, columnspacing=1.2, handlelength=1.8)
    fig.text(0.11, 0.015, f"{t['src']}{now_str}", fontsize=7.2, color="#64748B")
    fig.text(0.88, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/industrie/{slug}{t['sfx']}.png", dpi=300)
    plt.close()

    # 2. Interaktive Plotly-HTML-Grafik (unverändert)
    fp = make_subplots(specs=[[{"secondary_y": True}]])
    for vals, name, col, sec_y in (
        (v_ums, t["leg"][0], c_ums, False),
        (v_hrs, t["leg"][1], c_hrs, False),
        (v_wag, t["leg"][2], c_wag, False),
        (v_emp, t["leg"][3], c_emp, True),
    ):
        cd = [fmt_rate(v, use_c) for v in vals]
        fp.add_trace(
            go.Scatter(
                x=months, y=[round(v, 1) if not np.isnan(v) else None for v in vals],
                customdata=cd, name=name, mode="lines", line=dict(color=col, width=2.2),
                hovertemplate=f"{name}: <b>%{{customdata}} %</b><extra></extra>"
            ),
            secondary_y=sec_y
        )
    t_vals = [m for m in months if m.endswith("-01") or m.endswith("-07")]
    fp.update_layout(
        title=dict(text=f"<b>{full_title}</b><br><span style='font-size:11.5px;color:#475569;'>{t['title_sub']}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.03, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10, color="#1E293B")),
        margin=dict(l=58, r=58, t=155, b=95), height=530,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.27, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.27, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[l_min, l_max], dtick=l_step, fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", tickfont=dict(size=10.5, color="#475569"), secondary_y=False)
    fp.update_yaxes(range=[r_min, r_max], dtick=r_step, fixedrange=True, showgrid=False, zeroline=False, tickfont=dict(size=10.5, color="#475569"), secondary_y=True)
    if use_c:
        fp.update_layout(separators=",.")
    out_html = f"static/industrie/{slug}{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def main():
    yoy_data = fetch_42111_0004_multi()
    emp_lvl = yoy_data["emp_lvl"]
    latest_row = emp_lvl.iloc[-1]
    ranked_wz = sorted(
        [(code, de_lbl, en_lbl, float(latest_row.get(code, 0.0))) for code, de_lbl, en_lbl in WZ_META if code in emp_lvl.columns],
        key=itemgetter(3),
        reverse=True
    )
    ordered_items = [("00_wz08_c_gesamt", "WZ08-C", TEXTS["de"]["total_name"], TEXTS["en"]["total_name"])]
    for rank_idx, (code, de_lbl, en_lbl, _) in enumerate(ranked_wz, start=1):
        slug = f"{rank_idx:02d}_{code.lower().replace('-', '_')}"
        ordered_items.append((slug, code, de_lbl, en_lbl))
    meta_out = []
    for slug, code, de_lbl, en_lbl in ordered_items:
        render_multi_charts(
            "de", slug, code, de_lbl,
            yoy_data["ums"][code], yoy_data["hrs"][code], yoy_data["wag"][code], yoy_data["emp"][code]
        )
        render_multi_charts(
            "en", slug, code, en_lbl,
            yoy_data["ums"][code], yoy_data["hrs"][code], yoy_data["wag"][code], yoy_data["emp"][code]
        )
        meta_out.append({"slug": slug, "code": code, "de": de_lbl, "en": en_lbl})
    with open("static/industrie/order.json", "w", encoding="utf-8") as fh:
        json.dump(meta_out, fh, ensure_ascii=False, indent=2)
    print(f"[OK] {len(ordered_items)} Industrie-Kennzahlen-Grafiken (DE & EN) bis {emp_lvl.index[-1]} erzeugt.")


if __name__ == "__main__":
    main()
