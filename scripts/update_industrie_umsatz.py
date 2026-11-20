import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/umsatz-industrie", exist_ok=True)

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"

WZ_ALL_24 = [
    "WZ08-10", "WZ08-11", "WZ08-12", "WZ08-13", "WZ08-14", "WZ08-15",
    "WZ08-16", "WZ08-17", "WZ08-18", "WZ08-19", "WZ08-20", "WZ08-21",
    "WZ08-22", "WZ08-23", "WZ08-24", "WZ08-25", "WZ08-26", "WZ08-27",
    "WZ08-28", "WZ08-29", "WZ08-30", "WZ08-31", "WZ08-32", "WZ08-33",
]

TEXTS = {
    "de": {
        "unit": "Mrd. €",
        "xlabel": "Monatswerte",
        "tot": "Umsatz insgesamt",
        "dom": "Umsatz Inland",
        "for": "Umsatz Ausland",
        "share_for": "Anteil Ausland",
        "share_dom": "Anteil Inland",
        "latest_lbl": "Aktuellster Monat",
        "src": "Quelle: Statistisches Bundesamt (42111-0004), eigene Berechnungen | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": "",
        "charts": {
            "umsatz_gesamt": {
                "title": "Umsatz im Verarbeitenden Gewerbe insgesamt (WZ08-C)",
                "sub": "Umsatz insgesamt, Inlandsumsatz und Auslandsumsatz in Mrd. € (Ursprungswerte)"
            },
            "umsatz_autos": {
                "title": "Umsatz: Kraftwagen und Kraftwagenteile (WZ08-29)",
                "sub": "Umsatz insgesamt, Inlandsumsatz und Auslandsumsatz in Mrd. € (vergleichbar mit WAM2 Kap. 87)"
            },
            "umsatz_stahl": {
                "title": "Umsatz: Metallerzeugung/-bearbeitung sowie Metallerzeugnisse",
                "sub": "WZ08-24 (Metallerzeugung) vs. WZ08-24+25 (inkl. Metallerzeugnisse) in Mrd. € (vgl. WAM2 Kap. 72 / 72+73)",
                "lbl_a": "WZ08-24 (Metallerz.)",
                "lbl_b": "WZ08-24+25 (inkl. Erz.)"
            },
            "umsatz_chemie": {
                "title": "Umsatz: Chemische und pharmazeutische Erzeugnisse",
                "sub": "WZ08-20 (Chemie o. Pharma) vs. WZ08-20+21 (Chemie inkl. Pharma) in Mrd. € (vgl. WAM2 Kap. 28–38)",
                "lbl_a": "Chemie o. Pharma (WZ08-20)",
                "lbl_b": "Chemie inkl. Pharma (WZ08-20+21)"
            }
        }
    },
    "en": {
        "unit": "bn €",
        "xlabel": "Monthly values",
        "tot": "Total turnover",
        "dom": "Domestic turnover",
        "for": "Foreign turnover",
        "share_for": "Foreign share",
        "share_dom": "Domestic share",
        "latest_lbl": "Latest month",
        "src": "Source: Federal Statistical Office (42111-0004), own calculations | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en",
        "charts": {
            "umsatz_gesamt": {
                "title": "Total Manufacturing Turnover in Germany (WZ08-C)",
                "sub": "Total, domestic and foreign turnover in bn € (unadjusted data)"
            },
            "umsatz_autos": {
                "title": "Turnover: Motor Vehicles, Trailers and Semi-Trailers (WZ08-29)",
                "sub": "Total, domestic and foreign turnover in bn € (comparable to WAM2 Ch. 87)"
            },
            "umsatz_stahl": {
                "title": "Turnover: Basic Metals and Fabricated Metal Products",
                "sub": "WZ08-24 (Basic metals) vs. WZ08-24+25 (incl. metal products) in bn € (cf. WAM2 Ch. 72 / 72+73)",
                "lbl_a": "WZ08-24 (Basic metals)",
                "lbl_b": "WZ08-24+25 (incl. products)"
            },
            "umsatz_chemie": {
                "title": "Turnover: Chemicals and Pharmaceutical Products",
                "sub": "WZ08-20 (Chemicals excl. pharma) vs. WZ08-20+21 (incl. pharma) in bn € (cf. WAM2 Ch. 28–38)",
                "lbl_a": "Chemicals excl. pharma (WZ08-20)",
                "lbl_b": "Chemicals incl. pharma (WZ08-20+21)"
            }
        }
    }
}


def fmt_num(val, use_comma, dec=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if use_comma else s


def fmt_axis(val, use_comma, dec=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    v = round(float(val), dec)
    if v == 0:
        v = 0.0
    s = f"{v:.{dec}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if use_comma else s


def _unpack(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text


def fetch_42111_0004_umsatz(startyear="2019"):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "name": "42111-0004",
        "area": "all",
        "compress": "false",
        "format": "ffcsv",
        "language": "de",
        "startyear": startyear,
    }
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90)
    r.raise_for_status()
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        rj.raise_for_status()
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            raise RuntimeError("Destatis Job-ID nicht gefunden für 42111-0004")
        raw = ""
        for _ in range(60):
            time.sleep(2.5)
            txt = _unpack(
                requests.post(
                    f"{G_BASE}/resultfile",
                    headers=headers,
                    data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"},
                    timeout=90,
                )
            )
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
        if not raw:
            raise RuntimeError("Destatis Job für 42111-0004 nicht rechtzeitig beendet.")

    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3:
        raise RuntimeError("Tabelle 42111-0004 lieferte zu wenig Zeilen.")
    hdr = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)

    target_vars = {"UMS002", "UMS003", "UMS004"}
    df = df[
        (df["2_variable_attribute_code"].astype(str).str.strip() == "DG") &
        (df["3_variable_attribute_code"].astype(str).str.strip() == "BETRIEBE") &
        (df["value_variable_code"].astype(str).str.strip().isin(target_vars))
    ].copy()

    m_num = df["1_variable_attribute_code"].astype(str).str.extract(r"(\d+)", expand=False).str.zfill(2)
    df["YM"] = df["time"].astype(str).str.strip() + "-" + m_num
    df["WZ"] = df["4_variable_attribute_code"].astype(str).str.strip()
    df["VAR"] = df["value_variable_code"].astype(str).str.strip()
    df["V"] = pd.to_numeric(df["value"].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
    df = df.dropna(subset=["V"])
    df = df[df["YM"].str.match(r"^\d{4}-\d{2}$") & (df["YM"] >= "2019-01")].copy()

    if "value_variable_unit" in df.columns and df["value_variable_unit"].notna().any():
        u_sample = str(next(iter(df["value_variable_unit"].dropna()))).lower()
        divisor = 1e6 if "tsd" in u_sample else (1e3 if "mio" in u_sample else 1e9)
    else:
        divisor = 1e6
    df["MRD"] = df["V"] / divisor

    raw_piv = {}
    for var_code in target_vars:
        sub = df[df["VAR"] == var_code]
        piv = sub.pivot_table(index="YM", columns="WZ", values="MRD", aggfunc="first").sort_index()
        if "WZ08-C" not in piv.columns:
            avail = [c for c in WZ_ALL_24 if c in piv.columns]
            piv["WZ08-C"] = piv[avail].sum(axis=1, min_count=len(avail))
        raw_piv[var_code] = piv

    common_idx = (
        raw_piv["UMS002"].index
        .intersection(raw_piv["UMS003"].index)
        .intersection(raw_piv["UMS004"].index)
        .sort_values()
    )
    for var_code in target_vars:
        raw_piv[var_code] = raw_piv[var_code].reindex(common_idx)

    return raw_piv


def extract_turnover_series(raw_piv, wz_list):
    tot = raw_piv["UMS002"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    dom = raw_piv["UMS003"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    for_s = raw_piv["UMS004"][wz_list].sum(axis=1, min_count=len(wz_list)).dropna()
    idx = tot.index.intersection(dom.index).intersection(for_s.index).sort_values()
    tot, dom, for_s = tot.loc[idx], dom.loc[idx], for_s.loc[idx]
    valid = tot > 0
    tot, dom, for_s = tot.loc[valid], dom.loc[valid], for_s.loc[valid]
    share_for = (for_s / tot) * 100.0
    share_dom = (dom / tot) * 100.0
    return tot, dom, for_s, share_dom, share_for


def _write_clean_html(fig, path):
    fig.write_html(path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_s)


def render_single(key, lang, tot, dom, for_s, share_dom, share_for):
    t = TEXTS[lang]
    ct = t["charts"][key]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])

    months = list(tot.index)
    x = np.arange(len(months))
    vt, vd, vf = tot.values, dom.values, for_s.values
    latest_ym = months[-1]
    sf_last = fmt_num(share_for.iloc[-1], use_c, 1)
    sd_last = fmt_num(share_dom.iloc[-1], use_c, 1)

    share_note = (
        f"{t['latest_lbl']} ({latest_ym}): "
        f"{t['share_for']} {sf_last} % | {t['share_dom']} {sd_last} %"
    )

    hi_raw = float(np.max(vt))
    ymin = 0.0
    ymax = hi_raw * 1.16
    dec = 1 if ymax >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    fig, ax = plt.subplots(figsize=(8.6, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.75, bottom=0.22)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, ct["sub"], ha="left", fontsize=7.8, color="#64748B")
    fig.text(0.09, 0.878, share_note, ha="left", fontsize=8.0, fontweight="bold", color="#1B3A6B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.4)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_axis(v, use_c, dec)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#94A3B8", lw=0.9, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot(x, vt, color="#0F172A", lw=2.3, label=t["tot"], zorder=4)
    ax.plot(x, vf, color="#1B3A6B", lw=2.1, label=t["for"], zorder=4)
    ax.plot(x, vd, color="#059669", lw=2.1, label=t["dom"], zorder=4)

    end_items = sorted([(vt[-1], "#0F172A"), (vf[-1], "#1B3A6B"), (vd[-1], "#059669")], key=lambda z: z[0])
    min_gap = (ymax - ymin) * 0.048
    placed_y = []
    for val_y, col in end_items:
        y_pos = val_y
        if placed_y and y_pos - placed_y[-1] < min_gap:
            y_pos = placed_y[-1] + min_gap
        placed_y.append(y_pos)
        ax.scatter([x[-1]], [val_y], color=col, s=18, zorder=5)
        ax.text(x[-1] + 0.6, y_pos, fmt_num(val_y, use_c, dec), fontsize=7.3, fontweight="bold", color=col, va="center", ha="left", zorder=5)

    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i] for i in tick_pos], ha="right")
    ax.text(0.5, -0.21, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.8, columnspacing=1.4)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/umsatz-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    t_vals = [months[i] for i in tick_pos]
    cd_tot = [[fmt_num(vt[i], use_c, dec), fmt_num(share_for.iloc[i], use_c, 1), fmt_num(share_dom.iloc[i], use_c, 1)] for i in range(len(months))]
    cd_for = [[fmt_num(vf[i], use_c, dec), fmt_num(share_for.iloc[i], use_c, 1)] for i in range(len(months))]
    cd_dom = [[fmt_num(vd[i], use_c, dec), fmt_num(share_dom.iloc[i], use_c, 1)] for i in range(len(months))]

    fp = go.Figure()
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), dec) for v in vt],
            customdata=cd_tot,
            name=t["tot"],
            mode="lines",
            line=dict(color="#0F172A", width=2.4),
            hovertemplate=f"{t['tot']}: <b>%{{customdata[0]}} {t['unit']}</b> ({t['share_for']}: %{{customdata[1]}} % | {t['share_dom']}: %{{customdata[2]}} %)<extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), dec) for v in vf],
            customdata=cd_for,
            name=t["for"],
            mode="lines",
            line=dict(color="#1B3A6B", width=2.2),
            hovertemplate=f"{t['for']}: <b>%{{customdata[0]}} {t['unit']}</b> ({t['share_for']}: %{{customdata[1]}} %)<extra></extra>",
        )
    )
    fp.add_trace(
        go.Scatter(
            x=months,
            y=[round(float(v), dec) for v in vd],
            customdata=cd_dom,
            name=t["dom"],
            mode="lines",
            line=dict(color="#059669", width=2.2),
            hovertemplate=f"{t['dom']}: <b>%{{customdata[0]}} {t['unit']}</b> ({t['share_dom']}: %{{customdata[1]}} %)<extra></extra>",
        )
    )
    fp.update_layout(
        title=dict(
            text=(
                f"<b>{ct['title']}</b><br>"
                f"<span style='font-size:11.5px;color:#475569;'>{ct['sub']}</span><br>"
                f"<span style='font-size:11.5px;color:#1B3A6B;font-weight:bold;'>{share_note}</span>"
            ),
            x=0.03,
            y=0.96,
            yanchor="top",
            font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=112, b=105),
        height=450,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/umsatz-industrie/{key}{t['sfx']}.html")


def render_dual(key, lang, tot_a, dom_a, for_a, sd_a, sf_a, tot_b, dom_b, for_b, sd_b, sf_b):
    t = TEXTS[lang]
    ct = t["charts"][key]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])

    months = list(tot_a.index)
    x = np.arange(len(months))
    vta, vda, vfa = tot_a.values, dom_a.values, for_a.values
    vtb, vdb, vfb = tot_b.values, dom_b.values, for_b.values
    latest_ym = months[-1]

    share_note = (
        f"{t['latest_lbl']} ({latest_ym}): "
        f"{ct['lbl_a']} ({t['share_for']} {fmt_num(sf_a.iloc[-1], use_c, 1)} % / {t['share_dom']} {fmt_num(sd_a.iloc[-1], use_c, 1)} %) | "
        f"{ct['lbl_b']} ({t['share_for']} {fmt_num(sf_b.iloc[-1], use_c, 1)} % / {t['share_dom']} {fmt_num(sd_b.iloc[-1], use_c, 1)} %)"
    )

    hi_raw = float(np.max(np.concatenate([vta, vtb])))
    ymin = 0.0
    ymax = hi_raw * 1.16
    dec = 1 if ymax >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    fig, ax = plt.subplots(figsize=(8.6, 5.9), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.69, bottom=0.20)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.918, ct["sub"], ha="left", fontsize=7.5, color="#64748B")
    fig.text(0.09, 0.883, share_note, ha="left", fontsize=7.4, fontweight="bold", color="#1B3A6B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.4)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_axis(v, use_c, dec)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#94A3B8", lw=0.9, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot(x, vta, color="#0F172A", lw=2.0, label=f"{t['tot']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vtb, color="#475569", lw=1.8, linestyle="--", label=f"{t['tot']} – {ct['lbl_b']}", zorder=4)
    ax.plot(x, vfa, color="#1B3A6B", lw=2.0, label=f"{t['for']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vfb, color="#3B82F6", lw=1.8, linestyle="--", label=f"{t['for']} – {ct['lbl_b']}", zorder=4)
    ax.plot(x, vda, color="#047857", lw=2.0, label=f"{t['dom']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vdb, color="#10B981", lw=1.8, linestyle="--", label=f"{t['dom']} – {ct['lbl_b']}", zorder=4)

    end_items = sorted(
        [
            (vta[-1], "#0F172A"),
            (vtb[-1], "#475569"),
            (vfa[-1], "#1B3A6B"),
            (vfb[-1], "#3B82F6"),
            (vda[-1], "#047857"),
            (vdb[-1], "#10B981"),
        ],
        key=lambda z: z[0],
    )
    min_gap = (ymax - ymin) * 0.042
    placed_y = []
    for val_y, col in end_items:
        y_pos = val_y
        if placed_y and y_pos - placed_y[-1] < min_gap:
            y_pos = placed_y[-1] + min_gap
        placed_y.append(y_pos)
        ax.scatter([x[-1]], [val_y], color=col, s=14, zorder=5)
        ax.text(x[-1] + 0.6, y_pos, fmt_num(val_y, use_c, dec), fontsize=6.9, fontweight="bold", color=col, va="center", ha="left", zorder=5)

    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i] for i in tick_pos], ha="right")
    ax.text(0.5, -0.19, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=2, frameon=False, fontsize=7.0, columnspacing=1.2)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/umsatz-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    t_vals = [months[i] for i in tick_pos]
    fp = go.Figure()
    traces = [
        (vta, f"{t['tot']} – {ct['lbl_a']}", "#0F172A", None, None),
        (vtb, f"{t['tot']} – {ct['lbl_b']}", "#475569", "dash", None),
        (vfa, f"{t['for']} – {ct['lbl_a']}", "#1B3A6B", None, sf_a),
        (vfb, f"{t['for']} – {ct['lbl_b']}", "#3B82F6", "dash", sf_b),
        (vda, f"{t['dom']} – {ct['lbl_a']}", "#047857", None, sd_a),
        (vdb, f"{t['dom']} – {ct['lbl_b']}", "#10B981", "dash", sd_b),
    ]
    for vals, name, col, dash_s, sh_ser in traces:
        line_kw = dict(color=col, width=2.1)
        if dash_s:
            line_kw["dash"] = dash_s
        if sh_ser is not None:
            sh_lbl = t["share_for"] if sh_ser is sf_a or sh_ser is sf_b else t["share_dom"]
            cd = [[fmt_num(vals[i], use_c, dec), fmt_num(sh_ser.iloc[i], use_c, 1)] for i in range(len(months))]
            ht = f"%{{customdata[0]}} {t['unit']} ({sh_lbl}: %{{customdata[1]}} %)<extra></extra>"
        else:
            cd = [fmt_num(v, use_c, dec) for v in vals]
            ht = f"%{{customdata}} {t['unit']}<extra></extra>"
        fp.add_trace(
            go.Scatter(
                x=months,
                y=[round(float(v), dec) for v in vals],
                customdata=cd,
                name=name,
                mode="lines",
                line=line_kw,
                hovertemplate=ht,
            )
        )

    fp.update_layout(
        title=dict(
            text=(
                f"<b>{ct['title']}</b><br>"
                f"<span style='font-size:11.5px;color:#475569;'>{ct['sub']}</span><br>"
                f"<span style='font-size:11px;color:#1B3A6B;font-weight:bold;'>{share_note}</span>"
            ),
            x=0.03,
            y=0.96,
            yanchor="top",
            font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=9.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=142, b=105),
        height=485,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right"),
        ],
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/umsatz-industrie/{key}{t['sfx']}.html")


def main():
    raw_piv = fetch_42111_0004_umsatz("2019")
    singles = {
        "umsatz_gesamt": extract_turnover_series(raw_piv, ["WZ08-C"]),
        "umsatz_autos": extract_turnover_series(raw_piv, ["WZ08-29"]),
    }
    duals = {
        "umsatz_stahl": (*extract_turnover_series(raw_piv, ["WZ08-24"]), *extract_turnover_series(raw_piv, ["WZ08-24", "WZ08-25"])),
        "umsatz_chemie": (*extract_turnover_series(raw_piv, ["WZ08-20"]), *extract_turnover_series(raw_piv, ["WZ08-20", "WZ08-21"])),
    }
    for lang in ("de", "en"):
        for k, vals in singles.items():
            render_single(k, lang, *vals)
        for k, vals in duals.items():
            render_dual(k, lang, *vals)
    print(f"[OK] Industrie-Umsatz-Grafiken (DE & EN) bis {singles['umsatz_gesamt'][0].index[-1]} erzeugt.")


if __name__ == "__main__":
    main()

