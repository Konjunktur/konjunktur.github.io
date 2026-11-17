import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/aussenhandel-industrie", exist_ok=True)
D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"

WA_CHEM_NARROW = {"WA28", "WA29", "WA31", "WA32", "WA33", "WA34", "WA35", "WA36", "WA37", "WA38"}
WA_CHEM_BROAD = WA_CHEM_NARROW | {"WA30"}

TEXTS = {
    "de": {
        "unit": "Mrd. €",
        "xlabel": "Monatswerte",
        "exp": "Exporte",
        "imp": "Importe",
        "bal": "Saldo (Exp. − Imp.)",
        "src": "Quelle: Statistisches Bundesamt | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": "",
        "charts": {
            "aussenhandel_gesamt": {
                "title": "Außenhandel Deutschlands insgesamt",
                "sub": "Exporte, Importe und Außenhandelssaldo in Mrd. € (Ursprungswerte)"
            },
            "aussenhandel_autos": {
                "title": "Außenhandel: Kraftwagen und Kraftwagenteile (Autos)",
                "sub": "Warenverzeichnis WAM2 (Kap. 87), Exporte, Importe und Saldo in Mrd. €"
            },
            "aussenhandel_stahl": {
                "title": "Außenhandel: Eisen und Stahl sowie Waren daraus",
                "sub": "WAM2 Kap. 72 (Eisen/Stahl) vs. Kap. 72+73 (inkl. Waren) in Mrd. €",
                "lbl_a": "Kap. 72 (Eisen/Stahl)",
                "lbl_b": "Kap. 72+73 (inkl. Waren)"
            },
            "aussenhandel_chemie": {
                "title": "Außenhandel: Chemische und pharmazeutische Erzeugnisse",
                "sub": "WAM2 Kap. 28–38 ohne Kap. 30 vs. inkl. Kap. 30 in Mrd. €",
                "lbl_a": "Chemie o. Pharma",
                "lbl_b": "Chemie inkl. Pharma"
            },
            "china_gesamt": {
                "title": "Außenhandel Deutschlands mit China insgesamt",
                "sub": "Exporte nach China, Importe aus China und Außenhandelssaldo in Mrd. €"
            },
            "china_autos": {
                "title": "Außenhandel mit China: Kraftwagen und Kraftwagenteile (Autos)",
                "sub": "Warenverzeichnis WAM2 (Kap. 87), Exporte, Importe und Saldo in Mrd. €"
            },
            "china_stahl": {
                "title": "Außenhandel mit China: Eisen und Stahl sowie Waren daraus",
                "sub": "WAM2 Kap. 72 (Eisen/Stahl) vs. Kap. 72+73 (inkl. Waren) in Mrd. €",
                "lbl_a": "Kap. 72 (Eisen/Stahl)",
                "lbl_b": "Kap. 72+73 (inkl. Waren)"
            },
            "china_chemie": {
                "title": "Außenhandel mit China: Chemische und pharmazeutische Erzeugnisse",
                "sub": "WAM2 Kap. 28–38 ohne Kap. 30 vs. inkl. Kap. 30 in Mrd. €",
                "lbl_a": "Chemie o. Pharma",
                "lbl_b": "Chemie inkl. Pharma"
            }
        }
    },

        "en": {
        "unit": "bn €",
        "xlabel": "Monthly values",
        "exp": "Exports",
        "imp": "Imports",
        "bal": "Balance (Exp. − Imp.)",
        "src": "Source: Federal Statistical Office | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en",
        "charts": {
            "aussenhandel_gesamt": {
                "title": "Germany's Total Foreign Trade",
                "sub": "Exports, imports and trade balance in bn € (unadjusted data)"
            },
            "aussenhandel_autos": {
                "title": "Foreign Trade: Motor Vehicles and Parts (Automotive)",
                "sub": "Commodity classification WAM2 (Ch. 87), exports, imports and balance in bn €"
            },
            "aussenhandel_stahl": {
                "title": "Foreign Trade: Iron, Steel and Articles Thereof",
                "sub": "WAM2 Ch. 72 (Iron & steel) vs. Ch. 72+73 (incl. articles) in bn €",
                "lbl_a": "Ch. 72 (Iron & steel)",
                "lbl_b": "Ch. 72+73 (incl. articles)"
            },
            "aussenhandel_chemie": {
                "title": "Foreign Trade: Chemical and Pharmaceutical Products",
                "sub": "WAM2 Ch. 28–38 excl. Ch. 30 vs. incl. Ch. 30 in bn €",
                "lbl_a": "Chemicals excl. pharma",
                "lbl_b": "Chemicals incl. pharma"
            },
            "china_gesamt": {
                "title": "Germany's Total Foreign Trade with China",
                "sub": "Exports to China, imports from China and trade balance in bn €"
            },
            "china_autos": {
                "title": "Foreign Trade with China: Motor Vehicles and Parts (Automotive)",
                "sub": "Commodity classification WAM2 (Ch. 87), exports, imports and balance in bn €"
            },
            "china_stahl": {
                "title": "Foreign Trade with China: Iron, Steel and Articles Thereof",
                "sub": "WAM2 Ch. 72 (Iron & steel) vs. Ch. 72+73 (incl. articles) in bn €",
                "lbl_a": "Ch. 72 (Iron & steel)",
                "lbl_b": "Ch. 72+73 (incl. articles)"
            },
            "china_chemie": {
                "title": "Foreign Trade with China: Chemical and Pharmaceutical Products",
                "sub": "WAM2 Ch. 28–38 excl. Ch. 30 vs. incl. Ch. 30 in bn €",
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

def _unpack(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def fetch_genesis_trade(table, startyear="2019", cvar1=None, ckey1=None, cvar2=None, ckey2=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    if cvar1 and ckey1:
        data["classifyingvariable1"] = cvar1
        data["classifyingkey1"] = ckey1
    if cvar2 and ckey2:
        data["classifyingvariable2"] = cvar2
        data["classifyingkey2"] = ckey2
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
        raise RuntimeError(f"Tabelle {table} lieferte zu wenig Zeilen.")
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

    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code", "value_variable_code"}]
    df["WAM"] = ""
    for c in code_cols:
        s_c = df[c].astype(str).str.strip()
        if s_c.str.match(r"^WA\d{2}$").any():
            df["WAM"] = s_c
            break

    df = df[df["YM"].str.match(r"^\d{4}-\d{2}$")].copy()
    if var_col:
        df = df[df[var_col].isin(["WERTA", "WERTE"])].copy()

    val_num = pd.to_numeric(df[v_col].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
    df = df[val_num.notna()].copy()
    val_num = val_num.loc[df.index]

    if unit_col and df[unit_col].notna().any():
        u_sample = str(df[unit_col].dropna().iloc).lower()
        divisor = 1e6 if "tsd" in u_sample else (1e3 if "mio" in u_sample else 1e9)
    else:
        divisor = 1e6
    df["MRD"] = val_num / divisor
    return df

def extract_series(df, wam_filter=None):
    sub = df if wam_filter is None else df[df["WAM"].isin(wam_filter)]
    piv = sub.pivot_table(index="YM", columns="value_variable_code", values="MRD", aggfunc="sum", dropna=True).sort_index()
    piv = piv[piv.index >= "2019-01"].dropna(subset=["WERTA", "WERTE"])
    piv = piv[(piv["WERTA"] > 0) & (piv["WERTE"] > 0)]
    exp = piv["WERTA"]
    imp = piv["WERTE"]
    bal = exp - imp
    return exp, imp, bal

def _write_clean_html(fig, path):
    fig.write_html(path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(path, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def render_single(key, lang, exp, imp, bal):
    t = TEXTS[lang]
    ct = t["charts"][key]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(exp.index)
    x = np.arange(len(months))
    ve, vi, vb = exp.values, imp.values, bal.values

    all_vals = np.concatenate([ve, vi, vb, [0.0]])
    ymin = np.floor(np.min(all_vals) * 1.12 * 10) / 10
    ymax = np.ceil(np.max(all_vals) * 1.15 * 10) / 10
    dec = 1 if (ymax - ymin) >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    # 1. PNG
    fig, ax = plt.subplots(figsize=(8.6, 5.2), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.79, bottom=0.23)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, ct["sub"], ha="left", fontsize=7.8, color="#64748B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_num(v, use_c, dec)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#94A3B8", lw=0.9, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    bar_colors = ["#16A34A" if v >= 0 else "#F87171" for v in vb]
    ax.bar(x, vb, width=0.68, color=bar_colors, alpha=0.35, label=t["bal"], zorder=2)
    ax.plot(x, ve, color="#1B3A6B", lw=2.1, label=t["exp"], zorder=4)
    ax.plot(x, vi, color="#DC2626", lw=2.1, label=t["imp"], zorder=4)

    end_items = sorted([(ve[-1], "#1B3A6B"), (vi[-1], "#DC2626"), (vb[-1], "#15803D" if vb[-1] >= 0 else "#B91C1C")], key=lambda z: z)
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
    plt.savefig(f"static/aussenhandel-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    # 2. HTML (Smartphone- & Desktop-optimiert: Legende fest unter Titel, Fußzeile fest am Container-Boden)
    t_vals = [months[i] for i in tick_pos]
    fp = go.Figure()
    fp.add_trace(go.Bar(x=months, y=[round(v, dec) for v in vb], customdata=[fmt_num(v, use_c, dec) for v in vb], name=t["bal"], marker_color=bar_colors, opacity=0.45, hovertemplate=f"{t['bal']}: <b>%{{customdata}} {t['unit']}</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in ve], customdata=[fmt_num(v, use_c, dec) for v in ve], name=t["exp"], mode="lines", line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{t['exp']}: <b>%{{customdata}} {t['unit']}</b><extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vi], customdata=[fmt_num(v, use_c, dec) for v in vi], name=t["imp"], mode="lines", line=dict(color="#DC2626", width=2.3), hovertemplate=f"{t['imp']}: <b>%{{customdata}} {t['unit']}</b><extra></extra>"))
    fp.update_layout(
        title=dict(text=f"<b>{ct['title']}</b><br><span style='font-size:11px;color:#475569;'>{ct['sub']}</span>", x=0.03, y=0.97, yref="container", yanchor="top", font=dict(size=13.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.03, y=0.865, yref="container", xanchor="left", yanchor="top", bgcolor="rgba(255,255,255,0)", font=dict(size=10, color="#1E293B")),
        margin=dict(l=46, r=20, t=122, b=78), height=455,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.03, y=0.015, xref="container", yref="container", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left", yanchor="bottom"),
            dict(text="T.H.", x=0.97, y=0.015, xref="container", yref="container", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right", yanchor="bottom")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/aussenhandel-industrie/{key}{t['sfx']}.html")

def render_dual(key, lang, exp_a, imp_a, bal_a, exp_b, imp_b, bal_b):
    t = TEXTS[lang]
    ct = t["charts"][key]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])
    months = list(exp_a.index)
    x = np.arange(len(months))
    vea, via, vba = exp_a.values, imp_a.values, bal_a.values
    veb, vib, vbb = exp_b.values, imp_b.values, bal_b.values

    all_vals = np.concatenate([vea, via, vba, veb, vib, vbb, [0.0]])
    ymin = np.floor(np.min(all_vals) * 1.12 * 10) / 10
    ymax = np.ceil(np.max(all_vals) * 1.15 * 10) / 10
    dec = 1 if (ymax - ymin) >= 15 else 2
    tick_pos = [i for i, ym in enumerate(months) if ym.endswith("-01") or ym.endswith("-07")]

    # 1. PNG
    fig, ax = plt.subplots(figsize=(8.6, 5.7), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.09, right=0.92, top=0.72, bottom=0.21)
    fig.suptitle(ct["title"], x=0.09, y=0.96, ha="left", fontsize=11.0, fontweight="bold", color="#0F172A")
    fig.text(0.09, 0.915, ct["sub"], ha="left", fontsize=7.6, color="#64748B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.8, len(months) + 3.2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: fmt_num(v, use_c, dec)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.2, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=7.8, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#94A3B8", lw=0.9, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    col_ba = ["#16A34A" if v >= 0 else "#EF4444" for v in vba]
    col_bb = ["#0D9488" if v >= 0 else "#F97316" for v in vbb]
    ax.bar(x - 0.19, vba, width=0.36, color=col_ba, alpha=0.42, label=f"Saldo – {ct['lbl_a']}", zorder=2)
    ax.bar(x + 0.19, vbb, width=0.36, color=col_bb, alpha=0.42, label=f"Saldo – {ct['lbl_b']}", zorder=2)

    ax.plot(x, vea, color="#1B3A6B", lw=2.0, label=f"{t['exp']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, veb, color="#3B82F6", lw=1.8, linestyle="--", label=f"{t['exp']} – {ct['lbl_b']}", zorder=4)
    ax.plot(x, via, color="#B91C1C", lw=2.0, label=f"{t['imp']} – {ct['lbl_a']}", zorder=4)
    ax.plot(x, vib, color="#F97316", lw=1.8, linestyle="--", label=f"{t['imp']} – {ct['lbl_b']}", zorder=4)

    end_items = sorted([(vea[-1], "#1B3A6B"), (veb[-1], "#3B82F6"), (via[-1], "#B91C1C"), (vib[-1], "#F97316")], key=lambda z: z)
    min_gap = (ymax - ymin) * 0.045
    placed_y = []
    for val_y, col in end_items:
        y_pos = val_y
        if placed_y and y_pos - placed_y[-1] < min_gap:
            y_pos = placed_y[-1] + min_gap
        placed_y.append(y_pos)
        ax.scatter([x[-1]], [val_y], color=col, s=15, zorder=5)
        ax.text(x[-1] + 0.6, y_pos, fmt_num(val_y, use_c, dec), fontsize=7.0, fontweight="bold", color=col, va="center", ha="left", zorder=5)

    ax.set_xticks(tick_pos)
    ax.set_xticklabels([months[i] for i in tick_pos], ha="right")
    ax.text(0.5, -0.20, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.2, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.01), ncol=2, frameon=False, fontsize=7.1, columnspacing=1.2)
    fig.text(0.09, 0.015, f"{t['src']}{now_str}", fontsize=7.1, color="#64748B")
    fig.text(0.92, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/aussenhandel-industrie/{key}{t['sfx']}.png", dpi=300)
    plt.close()

    # 2. HTML (Smartphone- & Desktop-optimiert: Legende fest unter Titel, Fußzeile fest am Container-Boden)
    t_vals = [months[i] for i in tick_pos]
    fp = go.Figure()
    fp.add_trace(go.Bar(x=months, y=[round(v, dec) for v in vba], customdata=[fmt_num(v, use_c, dec) for v in vba], name=f"Saldo – {ct['lbl_a']}", marker_color=col_ba, opacity=0.45, hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Bar(x=months, y=[round(v, dec) for v in vbb], customdata=[fmt_num(v, use_c, dec) for v in vbb], name=f"Saldo – {ct['lbl_b']}", marker_color=col_bb, opacity=0.45, hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vea], customdata=[fmt_num(v, use_c, dec) for v in vea], name=f"{t['exp']} – {ct['lbl_a']}", mode="lines", line=dict(color="#1B3A6B", width=2.2), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in veb], customdata=[fmt_num(v, use_c, dec) for v in veb], name=f"{t['exp']} – {ct['lbl_b']}", mode="lines", line=dict(color="#3B82F6", width=1.9, dash="dash"), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in via], customdata=[fmt_num(v, use_c, dec) for v in via], name=f"{t['imp']} – {ct['lbl_a']}", mode="lines", line=dict(color="#B91C1C", width=2.2), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))
    fp.add_trace(go.Scatter(x=months, y=[round(v, dec) for v in vib], customdata=[fmt_num(v, use_c, dec) for v in vib], name=f"{t['imp']} – {ct['lbl_b']}", mode="lines", line=dict(color="#F97316", width=1.9, dash="dash"), hovertemplate="%{customdata} " + t["unit"] + "<extra></extra>"))

    fp.update_layout(
        title=dict(text=f"<b>{ct['title']}</b><br><span style='font-size:11px;color:#475569;'>{ct['sub']}</span>", x=0.03, y=0.97, yref="container", yanchor="top", font=dict(size=13.5, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False, barmode="group",
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.03, y=0.875, yref="container", xanchor="left", yanchor="top", bgcolor="rgba(255,255,255,0)", font=dict(size=9.2, color="#1E293B")),
        margin=dict(l=46, r=20, t=168, b=78), height=505,
        annotations=[
            dict(text=f"{t['src']}{now_str}", x=0.03, y=0.015, xref="container", yref="container", showarrow=False, font=dict(size=9.5, color="#64748B"), xanchor="left", yanchor="bottom"),
            dict(text="T.H.", x=0.97, y=0.015, xref="container", yref="container", showarrow=False, font=dict(size=10, color="#94A3B8"), xanchor="right", yanchor="bottom")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], fixedrange=True, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#94A3B8", tickfont=dict(size=10, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    _write_clean_html(fp, f"static/aussenhandel-industrie/{key}{t['sfx']}.html")

def main():
    wam_keys = "WA28,WA29,WA30,WA31,WA32,WA33,WA34,WA35,WA36,WA37,WA38,WA72,WA73,WA87"
    df_tot = fetch_genesis_trade("51000-0002", "2019")
    df_cn_tot = fetch_genesis_trade("51000-0004", "2019", "STLAH", "STLAH720")
    df_wam = fetch_genesis_trade("51000-0006", "2019", "WAM2", wam_keys)
    df_cn_wam = fetch_genesis_trade("51000-0008", "2019", "STLAH", "STLAH720", "WAM2", wam_keys)

    singles = {
        "aussenhandel_gesamt": extract_series(df_tot),
        "aussenhandel_autos": extract_series(df_wam, {"WA87"}),
        "china_gesamt": extract_series(df_cn_tot),
        "china_autos": extract_series(df_cn_wam, {"WA87"}),
    }
    duals = {
        "aussenhandel_stahl": (*extract_series(df_wam, {"WA72"}), *extract_series(df_wam, {"WA72", "WA73"})),
        "aussenhandel_chemie": (*extract_series(df_wam, WA_CHEM_NARROW), *extract_series(df_wam, WA_CHEM_BROAD)),
        "china_stahl": (*extract_series(df_cn_wam, {"WA72"}), *extract_series(df_cn_wam, {"WA72", "WA73"})),
        "china_chemie": (*extract_series(df_cn_wam, WA_CHEM_NARROW), *extract_series(df_cn_wam, WA_CHEM_BROAD)),
    }

    for lang in ("de", "en"):
        for k, vals in singles.items():
            render_single(k, lang, *vals)
        for k, vals in duals.items():
            render_dual(k, lang, *vals)
    print("Außenhandels-Grafiken erfolgreich erstellt.")

if __name__ == "__main__":
    main()
