import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/umsatz-industrie", exist_ok=True)

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"

TEXTS = {
    "de": {
        "unit": "Mrd. €",
        "xlabel": "Monatswerte",
        "tot": "Umsatz insgesamt",
        "dom": "Umsatz Inland",
        "for": "Umsatz Ausland",
        "share_lbl": "Aktueller Monat",
        "for_short": "Ausland",
        "dom_short": "Inland",
        "src": "Quelle: Statistisches Bundesamt (Tabellen 42111-0002 / 42111-0004) | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": "",
        "charts": {
            "umsatz_gesamt": {
                "title": "Umsatz im Verarbeitenden Gewerbe insgesamt",
                "sub": "WZ08-C: Umsatz insgesamt, Inlandsumsatz und Auslandsumsatz in Mrd. € (Ursprungswerte)"
            },
            "umsatz_autos": {
                "title": "Umsatz: Kraftwagen und Kraftwagenteile (Autos)",
                "sub": "WZ08-29: Umsatz insgesamt, Inlandsumsatz und Auslandsumsatz in Mrd. €"
            },
            "umsatz_stahl": {
                "title": "Umsatz: Metallerzeugung/-bearbeitung sowie Metallerzeugnisse",
                "sub": "WZ08-24 (Metallerzeugung) vs. WZ08-24+25 (inkl. Metallerzeugnisse) in Mrd. €",
                "lbl_a": "WZ08-24 (Metallerzeugung)",
                "lbl_b": "WZ08-24+25 (inkl. Erz.)"
            },
            "umsatz_chemie": {
                "title": "Umsatz: Chemische und pharmazeutische Erzeugnisse",
                "sub": "WZ08-20 (Chemie o. Pharma) vs. WZ08-20+21 (Chemie inkl. Pharma) in Mrd. €",
                "lbl_a": "Chemie o. Pharma",
                "lbl_b": "Chemie inkl. Pharma"
            }
        }
    },
    "en": {
        "unit": "bn €",
        "xlabel": "Monthly values",
        "tot": "Total turnover",
        "dom": "Domestic turnover",
        "for": "Foreign turnover",
        "share_lbl": "Latest month",
        "for_short": "Foreign",
        "dom_short": "Domestic",
        "src": "Source: Federal Statistical Office (Tables 42111-0002 / 42111-0004) | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en",
        "charts": {
            "umsatz_gesamt": {
                "title": "Total Turnover in German Manufacturing",
                "sub": "WZ08-C: Total, domestic and foreign turnover in bn € (unadjusted data)"
            },
            "umsatz_autos": {
                "title": "Turnover: Motor Vehicles and Parts (Automotive)",
                "sub": "WZ08-29: Total, domestic and foreign turnover in bn €"
            },
            "umsatz_stahl": {
                "title": "Turnover: Basic Metals and Fabricated Metal Products",
                "sub": "WZ08-24 (Basic metals) vs. WZ08-24+25 (incl. metal products) in bn €",
                "lbl_a": "WZ08-24 (Basic metals)",
                "lbl_b": "WZ08-24+25 (incl. products)"
            },
            "umsatz_chemie": {
                "title": "Turnover: Chemical and Pharmaceutical Products",
                "sub": "WZ08-20 (Chemicals excl. pharma) vs. WZ08-20+21 (incl. pharma) in bn €",
                "lbl_a": "Chemicals excl. pharma",
                "lbl_b": "Chemicals incl. pharma"
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

def normalize_wz(val):
    s = str(val).strip()
    m = re.search(r"WZ08-([A-Z]|\d{2,4})", s, flags=re.IGNORECASE)
    if not m:
        return ""
    code = m.group(1).upper()
    if code.isdigit() and len(code) == 3 and code.startswith("0"):
        code = code[1:]
    return f"WZ08-{code}"

def fetch_genesis_turnover(table, startyear="2019", cvar1=None, ckey1=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    if cvar1 and ckey1:
        data["classifyingvariable1"] = cvar1
        data["classifyingkey1"] = ckey1
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=90)
    r.raise_for_status()
    raw = _unpack(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=90)
        rj.raise_for_status()
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            raise RuntimeError(f"Job-ID nicht gefunden für {table}: {rj.text[:250]}")
        raw = ""
        for _ in range(120):
            time.sleep(3)
            txt = _unpack(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=90))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
        if not raw:
            raise RuntimeError(f"Job für {table} nicht rechtzeitig beendet.")
    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3:
        raise RuntimeError(f"Tabelle {table} lieferte zu wenig Zeilen: {raw[:250]}")
    hdr = [h.strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)
    col_map = {c.lower(): c for c in df.columns}
    t_col = col_map.get("time") or col_map.get("zeit")
    v_col = col_map.get("value") or col_map.get("wert")
    var_col = col_map.get("value_variable_code")
    unit_col = col_map.get("value_variable_unit")

    zeit_s = df[t_col].astype(str).str.strip()
    for c in df.columns:
        if c in (t_col, v_col) or "label" in c.lower():
            continue
        s_code = df[c].astype(str).str.strip()
        if s_code.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            m_ext = s_code.str.extract(r"([0-9]+)", expand=False).str.zfill(2)
            zeit_s = pd.Series(np.where(m_ext.notna(), zeit_s + "-" + m_ext.fillna(""), zeit_s), index=df.index)
            break
    df["YM"] = zeit_s

    df["WZ"] = ""
    for c in df.columns:
        if c in (t_col, v_col, "YM", "WZ"):
            continue
        norm_s = df[c].map(normalize_wz)
        if (norm_s != "").any():
            df["WZ"] = norm_s
            break

    df = df[(df["YM"].str.match(r"^\d{4}-\d{2}$")) & (df["WZ"] != "")].copy()
    if var_col:
        df = df[df[var_col].isin(["UMS002", "UMS003", "UMS004"])].copy()

    val_num = pd.to_numeric(df[v_col].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
    df = df[val_num.notna()].copy()
    val_num = val_num.loc[df.index]

    if unit_col and df[unit_col].notna().any():
        u_sample = str(next(iter(df[unit_col].dropna()))).lower()
        divisor = 1e6 if "tsd" in u_sample else (1e3 if "mio" in u_sample else 1e9)
    else:
        divisor = 1e6
    df["MRD"] = val_num / divisor
    return df

def extract_turnover_series(df, wz_list):
    sub = df[df["WZ"].isin(wz_list)].copy()
    piv = sub.pivot_table(index=["YM", "WZ"], columns="value_variable_code", values="MRD", aggfunc="first").reset_index()
    for col in ("UMS002", "UMS003", "UMS004"):
        if col not in piv.columns:
            piv[col] = np.nan
    piv = piv.dropna(subset=["UMS002", "UMS003", "UMS004"])
    grp = piv.groupby("YM")[["UMS002", "UMS003", "UMS004", "WZ"]].agg({
        "UMS002": "sum",
        "UMS003": "sum",
        "UMS004": "sum",
        "WZ": "nunique"
    }).sort_index()
    grp = grp[(grp.index >= "2019-01") & (grp["WZ"] == len(wz_list)) & (grp["UMS002"] > 0)].copy()
    if grp.empty:
        avail = sorted(df["WZ"].unique().tolist())
        raise KeyError(f"Keine vollständigen Daten für {wz_list}. Verfügbare WZ-Codes: {avail}")
    tot = grp["UMS002"]
    dom = grp["UMS003"]
    for_s = grp["UMS004"]
    return tot, dom, for_s

def _write_clean_html(fig, path):
    fig.write_html(path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def render_single(key, lang, tot, dom, for_s):
    t = TEXTS[lang]
    ct = t["charts"][key]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(tot.index)
    x = np.arange(len(months))
    vt, vd, vf = tot.values, dom.values, for_s.values

    latest_ym = months[-1]
    for_share = (vf[-1] / vt[-1]) * 100.0 if vt[-1] else 0.0
    dom_share = (vd[-1] / vt[-1]) * 100.0 if vt[-1] else 0.0
    share_badge = (
        f"{t['share_lbl']} ({latest_ym}): "
        f"{t['for_short']} {fmt_num(for_share, use_c, 1)} % | "
        f"{t['dom_short']} {fmt_num(dom_share, use_c, 1)} %"
    )
    sub_full = f"{ct['sub']}  •  {share_badge}"

    all_vals = np.concatenate([vt, vd, vf, [0.0]])
    lo_raw, hi_raw = float(np.min(all_vals)), float(np.max(all_vals))
    span = max(hi_raw - lo_raw, 0.2)
    ymin = 0.0
    ymax = hi_raw + span * 0.14
    dec = 1 if (ymax - ymin) >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    fig, ax = plt.subplots(figsize=(8.6, 5.3), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.78, bottom=0.23)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, sub_full, ha="left", fontsize=7.5, color="#475569")
    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.2)
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
    ax.plot(x, vd, color="#0D9488", lw=2.1, label=t["dom"], zorder=4)

    end_items = sorted([(vt[-1], "#0F172A"), (vf[-1], "#1B3A6B"), (vd[-1], "#0D9488")], key=lambda z: z)
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
    ax.text(0.5, -0.22, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=3, frameon=False, fontsize=7.8, columnspacing=1.4)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/umsatz-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    t_vals = [months[i] for i in tick_pos]
    for_pct_arr = [fmt_num((vf[i] / vt[i]) * 100.0, use_c, 1) if vt[i] else "" for i in range(len(months))]
    dom_pct_arr = [fmt_num((vd[i] / vt[i]) * 100.0, use_c, 1) if vt[i] else "" for i in range(len(months))]

    fp = go.Figure()
    fp.add_trace(go.Scatter(
        x=months, y=[round(v, dec) for v in vt],
        customdata=[fmt_num(v, use_c, dec) for v in vt],
        name=t["tot"], mode="lines", line=dict(color="#0F172A", width=2.4),
        hovertemplate=f"{t['tot']}: <b>%{{customdata}} {t['unit']}</b><extra></extra>"
    ))
    fp.add_trace(go.Scatter(
        x=months, y=[round(v, dec) for v in vf],
        customdata=list(zip([fmt_num(v, use_c, dec) for v in vf], for_pct_arr)),
        name=t["for"], mode="lines", line=dict(color="#1B3A6B", width=2.2),
        hovertemplate=f"{t['for']}: <b>%{{customdata[0]}} {t['unit']} (%{{customdata[1]}} %)</b><extra></extra>"
    ))
    fp.add_trace(go.Scatter(
        x=months, y=[round(v, dec) for v in vd],
        customdata=list(zip([fmt_num(v, use_c, dec) for v in vd], dom_pct_arr)),
        name=t["dom"], mode="lines", line=dict(color="#0D9488", width=2.2),
        hovertemplate=f"{t['dom']}: <b>%{{customdata[0]}} {t['unit']} (%{{customdata[1]}} %)</b><extra></extra>"
    ))
    fp.update_layout(
        title=dict(
            text=f"<b>{ct['title']}</b><br><span style='font-size:11px;color:#475569;'>{sub_full}</span>",
            x=0.03, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")
        ),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=96, b=105), height=445,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.31, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.31, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/umsatz-industrie/{key}{t['sfx']}.html")

def render_dual(key, lang, tot_a, dom_a, for_a, tot_b, dom_b, for_b):
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
    fa_pct = (vfa[-1] / vta[-1]) * 100.0 if vta[-1] else 0.0
    da_pct = (vda[-1] / vta[-1]) * 100.0 if vta[-1] else 0.0
    fb_pct = (vfb[-1] / vtb[-1]) * 100.0 if vtb[-1] else 0.0
    db_pct = (vdb[-1] / vtb[-1]) * 100.0 if vtb[-1] else 0.0

    share_line = (
        f"{t['share_lbl']} ({latest_ym}): "
        f"{ct['lbl_a']}: {t['for_short']} {fmt_num(fa_pct, use_c, 1)} % / {t['dom_short']} {fmt_num(da_pct, use_c, 1)} %  |  "
        f"{ct['lbl_b']}: {t['for_short']} {fmt_num(fb_pct, use_c, 1)} % / {t['dom_short']} {fmt_num(db_pct, use_c, 1)} %"
    )

    all_vals = np.concatenate([vta, vda, vfa, vtb, vdb, vfb, [0.0]])
    lo_raw, hi_raw = float(np.min(all_vals)), float(np.max(all_vals))
    span = max(hi_raw - lo_raw, 0.2)
    ymin = 0.0
    ymax = hi_raw + span * 0.14
    dec = 1 if (ymax - ymin) >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    fig, ax = plt.subplots(figsize=(8.6, 5.8), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.71, bottom=0.21)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.918, ct["sub"], ha="left", fontsize=7.5, color="#64748B")
    fig.text(0.09, 0.885, share_line, ha="left", fontsize=7.1, color="#1E293B", fontweight="bold")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_axis(v, use_c, dec)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#94A3B8", lw=0.9, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot(x, vta, color="#0F172A", lw=2.1, label=f"{t['tot']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vtb, color="#64748B", lw=1.9, linestyle="--", label=f"{t['tot']} – {ct['lbl_b']}", zorder=4)
    ax.plot(x, vfa, color="#1B3A6B", lw=2.0, label=f"{t['for']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vfb, color="#3B82F6", lw=1.8, linestyle="--", label=f"{t['for']} – {ct['lbl_b']}", zorder=4)
    ax.plot(x, vda, color="#0D9488", lw=2.0, label=f"{t['dom']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vdb, color="#F97316", lw=1.8, linestyle="--", label=f"{t['dom']} – {ct['lbl_b']}", zorder=4)

    end_items = sorted([
        (vta[-1], "#0F172A"), (vtb[-1], "#64748B"),
        (vfa[-1], "#1B3A6B"), (vfb[-1], "#3B82F6"),
        (vda[-1], "#0D9488"), (vdb[-1], "#F97316")
    ], key=lambda z: z)
    min_gap = (ymax - ymin) * 0.042
    placed_y = []
    for val_y, col in end_items:
        y_pos = val_y
        if placed_y and y_pos - placed_y[-1] < min_gap:
            y_pos = placed_y[-1] + min_gap
        placed_y.append(y_pos)
        ax.scatter([x[-1]], [val_y], color=col, s=14, zorder=5)
        ax.text(x[-1] + 0.6, y_pos, fmt_num(val_y, use_c, dec), fontsize=6.8, fontweight="bold", color=col, va="center", ha="left", zorder=5)

    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i] for i in tick_pos], ha="right")
    ax.text(0.5, -0.20, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=2, frameon=False, fontsize=7.0, columnspacing=1.2)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/umsatz-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    t_vals = [months[i] for i in tick_pos]
    fa_arr = [fmt_num((vfa[i] / vta[i]) * 100.0, use_c, 1) if vta[i] else "" for i in range(len(months))]
    da_arr = [fmt_num((vda[i] / vta[i]) * 100.0, use_c, 1) if vta[i] else "" for i in range(len(months))]
    fb_arr = [fmt_num((vfb[i] / vtb[i]) * 100.0, use_c, 1) if vtb[i] else "" for i in range(len(months))]
    db_arr = [fmt_num((vdb[i] / vtb[i]) * 100.0, use_c, 1) if vtb[i] else "" for i in range(len(months))]

    fp = go.Figure()
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vta], customdata=[fmt_num(v, use_c, dec) for v in vta], name=f"{t['tot']} – {ct['lbl_a']}", mode="lines", line=dict(color="#0F172A", width=2.2), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vtb], customdata=[fmt_num(v, use_c, dec) for v in vtb], name=f"{t['tot']} – {ct['lbl_b']}", mode="lines", line=dict(color="#64748B", width=1.9, dash="dash"), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vfa], customdata=list(zip([fmt_num(v, use_c, dec) for v in vfa], fa_arr)), name=f"{t['for']} – {ct['lbl_a']}", mode="lines", line=dict(color="#1B3A6B", width=2.2), hovertemplate="%{customdata[0]} " + t["unit"] + " (%{customdata[1]} %)<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vfb], customdata=list(zip([fmt_num(v, use_c, dec) for v in vfb], fb_arr)), name=f"{t['for']} – {ct['lbl_b']}", mode="lines", line=dict(color="#3B82F6", width=1.9, dash="dash"), hovertemplate="%{customdata[0]} " + t["unit"] + " (%{customdata[1]} %)<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vda], customdata=list(zip([fmt_num(v, use_c, dec) for v in vda], da_arr)), name=f"{t['dom']} – {ct['lbl_a']}", mode="lines", line=dict(color="#0D9488", width=2.2), hovertemplate="%{customdata[0]} " + t["unit"] + " (%{customdata[1]} %)<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vdb], customdata=list(zip([fmt_num(v, use_c, dec) for v in vdb], db_arr)), name=f"{t['dom']} – {ct['lbl_b']}", mode="lines", line=dict(color="#F97316", width=1.9, dash="dash"), hovertemplate="%{customdata[0]} " + t["unit"] + " (%{customdata[1]} %)<extra></extra>"))

    fp.update_layout(
        title=dict(
            text=f"<b>{ct['title']}</b><br><span style='font-size:10.5px;color:#475569;'>{ct['sub']}</span><br><span style='font-size:10.5px;color:#1E293B;'>{share_line}</span>",
            x=0.03, y=0.97, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")
        ),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.01, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=9.5, color="#1E293B")),
        margin=dict(l=52, r=24, t=132, b=105), height=480,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.31, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.31, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/umsatz-industrie/{key}{t['sfx']}.html")

def main():
    df_tot = fetch_genesis_turnover("42111-0002", "2019", "WZ08", "WZ08-C")
    df_wz = fetch_genesis_turnover("42111-0004", "2019", "WZ08", "WZ08-29,WZ08-24,WZ08-25,WZ08-20,WZ08-21")

    singles = {
        "umsatz_gesamt": extract_turnover_series(df_tot, ["WZ08-C"]),
        "umsatz_autos": extract_turnover_series(df_wz, ["WZ08-29"]),
    }
    duals = {
        "umsatz_stahl": (
            *extract_turnover_series(df_wz, ["WZ08-24"]),
            *extract_turnover_series(df_wz, ["WZ08-24", "WZ08-25"])
        ),
        "umsatz_chemie": (
            *extract_turnover_series(df_wz, ["WZ08-20"]),
            *extract_turnover_series(df_wz, ["WZ08-20", "WZ08-21"])
        ),
    }

    for lang in ("de", "en"):
        for k, vals in singles.items():
            render_single(k, lang, *vals)
        for k, vals in duals.items():
            render_dual(k, lang, *vals)

    print("Industrie-Umsatz-Grafiken erfolgreich erstellt.")

if __name__ == "__main__":
    main()
