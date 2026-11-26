import os, io, re, csv, json, time, zipfile, requests, argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/dashboard", exist_ok=True)
D_USER, D_PASS = os.environ.get("DESTATIS_USER", ""), os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"
BBK_BASE = "https://api.statistiken." + "bundesbank.de/rest/data"

TEXTS = {
    "de": {
        "p1_t": "Bruttoinlandsprodukt: Entstehung", "p1_s": "Veränderung zum Vorjahr in % (preisbereinigt, Ursprungswerte)",
        "p1_l": ("Reales BIP", "Produzierendes Gewerbe (ohne Baugewerbe)", "Baugewerbe", "Handel, Verkehr, Gastgewerbe"),
        "p1_h": ("Reales BIP", "Prod. Gew. o. Bau", "Baugewerbe", "Handel/Verkehr/Gastg."),
        "p2_t": "Bruttoinlandsprodukt: Verwendung", "p2_s": "Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p2_l": ("Nominales BIP", "Konsumausgaben der privaten Haushalte", "Konsumausgaben des Staates", "Ausrüstungsinvestitionen", "Bauinvestitionen", "Exporte", "Importe"),
        "p2_h": ("Nom. BIP", "Konsum priv. HH", "Konsum Staat", "Ausrüstungen", "Bauten", "Exporte", "Importe"),
        "p3_t": "Auftragseingänge", "p3_s": "Volumenindex, Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p3_l": ("Auftragseingang Industrie", "Auftragseingang Bauwirtschaft"),
        "p4_t": "Produktion & Einzelhandelsumsätze", "p4_s": "Real, Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p4_l": ("Industrieproduktion", "Bauproduktion", "Einzelhandelsumsätze"),
        "p5_t": "Leistungsbilanzsaldo", "p5_s": "Monatlicher Saldo in Mrd. Euro (Ursprungswerte)", "p5_l": "Leistungsbilanzsaldo",
        "p6_t": "Arbeitslosigkeit und Inflation", "p6_s": "Quote bzw. Veränderung zum Vorjahr in % (Ursprungswerte)",
        "p6_l": ("Arbeitslosenquote", "Vollbeschäftigung (3%)", "Inflation (HVPI)", "EZB-Inflationsziel (2%)"),
        "unit_lb": "Mrd. €",
        "src_all": "Quellen: Statistisches Bundesamt (u. a. BA-Daten), Deutsche Bundesbank | Stand: ",
        "src_destatis": "Quelle: Statistisches Bundesamt | Stand: ",
        "src_ba_destatis": "Quelle: Statistisches Bundesamt (BA-Daten) | Stand: ",
        "src_bbk": "Quelle: Deutsche Bundesbank | Stand: ",
        "date_fmt": "%d.%m.%Y", "comma": True, "sfx": ""
    },
    "en": {
        "p1_t": "Gross Domestic Product: Production", "p1_s": "Change on previous year in % (price-adjusted, unadjusted data)",
        "p1_l": ("Real GDP", "Industry excluding construction", "Construction", "Trade, transport, accommodation and food services"),
        "p1_h": ("Real GDP", "Industry excl. constr.", "Construction", "Trade/transp./hosp."),
        "p2_t": "Gross Domestic Product: Expenditure", "p2_s": "Change on previous year in % (unadjusted data)",
        "p2_l": ("Nominal GDP", "Household final consumption expenditure", "Government final consumption expenditure", "Machinery and equipment investment", "Construction investment", "Exports", "Imports"),
        "p2_h": ("Nom. GDP", "Household consumption", "Government consumption", "Machinery/equip.", "Construction", "Exports", "Imports"),
        "p3_t": "New Orders", "p3_s": "Volume index, change on previous year in % (unadjusted data)",
        "p3_l": ("New orders: Manufacturing", "New orders: Construction"),
        "p4_t": "Production & Retail Sales", "p4_s": "Real, change on previous year in % (unadjusted data)",
        "p4_l": ("Industrial production", "Construction output", "Retail sales"),
        "p5_t": "Current Account Balance", "p5_s": "Monthly balance in billion euros (unadjusted data)", "p5_l": "Current account balance",
        "p6_t": "Unemployment and Inflation", "p6_s": "Rate / change on previous year in % (unadjusted data)",
        "p6_l": ("Unemployment rate", "Full employment (3%)", "Inflation (HICP)", "ECB inflation target (2%)"),
        "unit_lb": "bn €",
        "src_all": "Sources: Federal Statistical Office (incl. FEA data), Deutsche Bundesbank | As of: ",
        "src_destatis": "Source: Federal Statistical Office | As of: ",
        "src_ba_destatis": "Source: Federal Statistical Office (FEA data) | As of: ",
        "src_bbk": "Source: Deutsche Bundesbank | As of: ",
        "date_fmt": "%Y-%m-%d", "comma": False, "sfx": "_en"
    }
}

def get_bbk(keys, n=13, scale=1.0):
    for key in ([keys] if isinstance(keys, str) else keys):
        flow, k = key.split(".", 1)
        r = requests.get(f"{BBK_BASE}/{flow}/{k}?format=csv&lang=de&lastNObservations={n+2}", timeout=25)
        if r.status_code != 200: continue
        rows = []
        for ln in r.text.splitlines():
            parts = [p.strip().strip('"') for p in ln.split(";")]
            if len(parts) >= 2:
                pt, pv = parts.pop(0), parts.pop(0)
                if re.match(r"^\d{4}-\d{2}$", pt):
                    try: rows.append((pt, float(pv.replace(",", ".")) * scale))
                    except ValueError: pass
        if rows:
            df_s = pd.DataFrame(rows, columns=["t", "v"]).drop_duplicates(subset=["t"], keep="last")
            return pd.Series(df_s["v"].values, index=df_s["t"].values).tail(n)
    raise RuntimeError(f"Bundesbank-Abruf lieferte keine Daten für: {keys}")

def _extract_payload(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def get_destatis(table, startyear="2020"):
    if not D_USER or not D_PASS: raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60); r.raise_for_status()
    raw_text = _extract_payload(r)
    if raw_text.lstrip().startswith("{"):
        r_job = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60); r_job.raise_for_status()
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(r_job.text).get("Status", {}).get("Content", "")))
        if not m: raise RuntimeError(f"Destatis Job-ID nicht gefunden für {table}")
        raw_text = ""
        for _ in range(24):
            time.sleep(2.5)
            txt = _extract_payload(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
            if not txt.lstrip().startswith("{"): raw_text = txt; break
        if not raw_text: raise RuntimeError(f"Destatis Job für {table} nicht rechtzeitig fertig.")
    rows = [row for row in csv.reader(io.StringIO(raw_text), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3: raise RuntimeError(f"Destatis Tabelle {table} zu wenig Zeilen")
    header = [str(h).strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(header)] for row in rows if len(row) >= len(header)], columns=header)
    col_map = {c.lower(): c for c in df.columns}
    t_col, v_col = col_map.get("time") or col_map.get("zeit"), col_map.get("value") or col_map.get("wert")
    zeit_s = df[t_col].astype(str).str.strip()
    for c in df.columns:
        if c in (t_col, v_col) or "label" in c.lower(): continue
        s_code = df[c].astype(str).str.strip()
        if s_code.str.match(r"^QUART0?[1-4]$", case=False).any():
            q_ext = s_code.str.extract(r"([1-4])", expand=False)
            zeit_s = pd.Series(np.where(q_ext.notna(), zeit_s + "-Q" + q_ext.fillna(""), zeit_s), index=df.index)
            break
        if s_code.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            m_ext = s_code.str.extract(r"([0-9]+)", expand=False).str.zfill(2)
            zeit_s = pd.Series(np.where(m_ext.notna(), zeit_s + "-" + m_ext.fillna(""), zeit_s), index=df.index)
            break
    df["ZEIT"], df["WERT"] = zeit_s, df[v_col]
    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    df["_CODES"] = df.loc[:, code_cols].fillna("").astype(str).apply(lambda r: set(x.strip() for x in r if x.strip()), axis=1)
    return df


def load_destatis_cache(table):
    cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache", f"{table}.csv")
    if not os.path.isfile(cache_path):
        raise FileNotFoundError(f"Destatis-Cache fehlt: {cache_path}")
    df = pd.read_csv(cache_path, sep=";", dtype=str, keep_default_na=False)
    code_cols = [c for c in df.columns if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    df["_CODES"] = df[code_cols].fillna("").astype(str).apply(lambda row: set(v.strip() for v in row if v.strip()), axis=1)
    return df


def extract_by_codes(df, req_codes, target_times, is_rate=False):
    if df.empty or "ZEIT" not in df.columns: return [np.nan] * len(target_times)
    req_set = set(req_codes)
    sub = df[df["_CODES"].apply(lambda s: req_set.issubset(s))].copy()
    sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=("V",)).drop_duplicates(subset=["ZEIT"], keep="first")
    val_map = dict(zip(sub["ZEIT"].astype(str).str.strip(), sub["V"]))
    if is_rate:
        return [val_map.get(t, np.nan) for t in target_times]
    out = []
    for t in target_times:
        vc, yr_s, rest_s = val_map.get(t, np.nan), t[:4], t[4:]
        prev_t = (str(int(yr_s) - 1) + rest_s) if yr_s.isdigit() else ""
        vp = val_map.get(prev_t, np.nan)
        out.append(((vc / vp - 1.0) * 100.0) if (not np.isnan(vc) and not np.isnan(vp) and vp != 0) else np.nan)
    return out

def fmt_num(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)): return ""
    s = f"{float(val):.1f}"
    return s.replace(".", ",") if use_comma else s


def add_bar_value_annotations(fig, xi, bars, line_series, y_span, use_comma):
    offset = y_span * 0.018
    for index, value in enumerate(bars):
        value = float(value)
        if not np.isfinite(value):
            continue
        line_values = [
            float(series[index]) for series in line_series
            if np.isfinite(series[index])
        ]
        top, bottom = max(value, 0.0), min(value, 0.0)
        above = min((line_value - top for line_value in line_values if line_value > top), default=0.0)
        below = min((bottom - line_value for line_value in line_values if line_value < bottom), default=0.0)
        place_above = above >= below
        fig.add_annotation(
            x=float(xi[index]),
            y=top + offset if place_above else bottom - offset,
            xref="x",
            yref="y",
            text=fmt_num(value, use_comma),
            showarrow=False,
            xanchor="center",
            yanchor="bottom" if place_above else "top",
            bgcolor="rgba(255,255,255,0.85)",
            borderpad=1.2,
            font={"size": 10, "color": "#1E3A8A"},
        )


def fmt_clean(val, use_comma, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)): return ""
    v = round(float(val), dec)
    if v == 0: v = 0.0
    s = f"{v:.{dec}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if use_comma else s

def sync_ylim_like_plotly(vals, include_zero=True):
    clean = [float(v) for v in vals if v is not None and not np.isnan(v)]
    if include_zero:
        clean.append(0.0)
    if not clean:
        return -5.0, 5.0, np.arange(-5.0, 5.5, 2.5), 2.5
    d_min, d_max = min(clean), max(clean)
    span = max(d_max - d_min, 1.0)
    pad = span * 0.02
    lo_raw = 0.0 if d_min >= 0 else d_min - pad
    hi_raw = 0.0 if d_max <= 0 else d_max + pad
    for step in (0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 20.0):
        ylo = np.floor(lo_raw / step) * step
        yhi = np.ceil(hi_raw / step) * step
        if (yhi - ylo) / step <= 9:
            return ylo, yhi, np.arange(ylo, yhi + step * 0.1, step), step
    step = 20.0
    ylo = np.floor(lo_raw / step) * step
    yhi = np.ceil(hi_raw / step) * step
    return ylo, yhi, np.arange(ylo, yhi + step * 0.1, step), step

    step = 20.0
    ylo = np.floor(lo_raw / step) * step
    yhi = np.ceil(hi_raw / step) * step
    return ylo, yhi, np.arange(ylo, yhi + step * 0.1, step), step

def style_panel(ax, title, sub, ymin, ymax, yticks, use_comma, z=True, title_y=1.40, sub_y=1.32):
    ax.set_facecolor("#F8FAFC")
    ax.text(0.0, title_y, title, transform=ax.transAxes, fontsize=11.5, fontweight="bold", color="#0F172A")
    ax.text(0.0, sub_y, sub, transform=ax.transAxes, fontsize=8.2, color="#64748B")
    ax.set_ylim(ymin, ymax); ax.set_yticks(yticks)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_clean(x, use_comma, 1)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8, rotation=45, length=3, color="#CBD5E1")
    for lbl in ax.get_xticklabels(): lbl.set_ha("right")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    if z: ax.axhline(0, color="#64748B", linewidth=1.1, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.text(1.0, -0.24, "T.H.", transform=ax.transAxes, ha="right", fontsize=7.5, color="#94A3B8")

def set_legend(ax, ncol=2, extra_handles=None):
    handles, labels = ax.get_legend_handles_labels()
    if extra_handles:
        handles.extend(extra_handles)
        labels.extend(handle.get_label() for handle in extra_handles)
    elif len(handles) > 1 and not hasattr(handles[-1], "get_xydata"):
        handles, labels = handles[-1:] + handles[:-1], labels[-1:] + labels[:-1]
    ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=ncol, frameon=False, fontsize=6.9)

def mark_ends(ax, series_items, use_comma, y_span):
    pts = []
    for x_vals, y_vals, col in series_items:
        valid = [(x, float(y)) for x, y in zip(x_vals, y_vals) if not np.isnan(y)]
        if valid:
            lx, ly = valid.pop()
            pts.append([lx, ly, ly, col])
    if not pts:
        return
    pts.sort(key=lambda z: z[1])
    min_gap = y_span * 0.042
    for _ in range(4):
        for i in range(1, len(pts)):
            diff = pts[i][2] - pts[i - 1][2]
            if diff < min_gap:
                shift = (min_gap - diff) / 2.0
                pts[i - 1][2] -= shift
                pts[i][2] += shift
    for lx, orig_y, text_y, col in pts:
        ax.plot(lx, orig_y, marker="o", markersize=4.5, color=col, zorder=5)
        ax.text(lx + 0.85, text_y, fmt_num(orig_y, use_comma), fontsize=8, fontweight="bold", color=col, va="center", ha="right", zorder=6)

def draw_bars_with_labels(ax, xi, vals, label, use_comma, y_span=18.0):
    bars = ax.bar(xi, vals, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A", lw=1.1, label=label, zorder=2)
    off_b = y_span * 0.018
    for b in bars:
        h = b.get_height()
        if not np.isnan(h):
            ax.text(b.get_x() + b.get_width() / 2, h + (off_b if h >= 0 else -off_b), fmt_num(h, use_comma), ha="center", va=("bottom" if h >= 0 else "top"), fontsize=6.2, color="#1E3A8A", fontweight="bold", zorder=4)


def format_table_value(value, use_comma):
    if value is None or not np.isfinite(value):
        return "–"
    number = f"{float(value):.1f}"
    if use_comma:
        return f"{number.replace('.', ',')} %"
    return f"{number}%"


def build_chart_embed(lang, chart_key, height):
    is_english = lang == "en"
    suffix = TEXTS[lang]["sfx"]
    stem = f"{chart_key}{suffix}"
    chart_url = f"/dashboard/{stem}.html"
    fullscreen_label = "View fullscreen" if is_english else "In Vollbild anzeigen"
    return "\n".join((
        f'<iframe src="{chart_url}" style="width:100%; height:{height}px; border:none; overflow:hidden;" scrolling="no" loading="lazy"></iframe>',
        f"- [{fullscreen_label}](/dashboard/{stem}.png)",
    ))


def update_dashboard_content(lang, data):
    is_english = lang == "en"
    md_path = os.path.join("content", "dashboard", "_index.en.md" if is_english else "_index.md")
    with open(md_path, "r", encoding="utf-8") as file:
        content = file.read()
    chart_specs = (
        ("BIP_ENTSTEHUNG", "01_bip_entstehung", 485),
        ("BIP_VERWENDUNG", "02_bip_verwendung", 540),
    )
    for name, chart_key, height in chart_specs:
        start_marker, end_marker = f"<!-- {name}_CHART_START -->", f"<!-- {name}_CHART_END -->"
        pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
        if len(pattern.findall(content)) != 1:
            raise RuntimeError(f"Erwartete genau einen Grafik-Block {name} in {md_path}")
        replacement = f"{start_marker}\n{build_chart_embed(lang, chart_key, height)}\n{end_marker}"
        content = pattern.sub(lambda _: replacement, content, count=1)

    for name in ("BIP_ENTSTEHUNG", "BIP_VERWENDUNG"):
        start_marker, end_marker = f"<!-- TABLE_{name}_START -->", f"<!-- TABLE_{name}_END -->"
        pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
        matches = pattern.findall(content)
        if len(matches) > 1:
            raise RuntimeError(f"Unerwartet mehrere Tabellenmarker-Blöcke {name} in {md_path}")
        if matches:
            content = pattern.sub("", content, count=1)

    content = content.replace('<link rel="stylesheet" href="/dashboard/table-modal.css">\n', "")
    content = content.replace('<script src="/dashboard/table-modal.js" defer></script>\n', "")
    with open(md_path, "w", encoding="utf-8") as file:
        file.write(content)


def draw_bars_with_auto_labels(ax, xi, vals, line_series, label, use_comma, ylo, yhi):
    bars = ax.bar(xi, vals, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A", lw=1.1, label=label, zorder=2)
    offset = (yhi - ylo) * 0.018
    for index, bar in enumerate(bars):
        value = float(vals[index])
        if np.isnan(value):
            continue
        line_values = [float(series[index]) for series in line_series if np.isfinite(series[index])]
        top, bottom = max(value, 0.0), min(value, 0.0)
        above = min((v - top for v in line_values if v > top), default=0.0)
        below = min((bottom - v for v in line_values if v < bottom), default=0.0)
        place_above = above >= below
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            top + offset if place_above else bottom - offset,
            fmt_num(value, use_comma),
            ha="center", va="bottom" if place_above else "top",
            fontsize=6.2, color="#1E3A8A", fontweight="bold",
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 1.2},
            zorder=5,
        )


def draw_p1(ax, t, d):
    xi, xl_bip = d["xi"], d["xl_bip"]
    ylo, yhi, yt, _ = sync_ylim_like_plotly(np.concatenate([d["bip_r"], d["pg"], d["bau"], d["hvg"]]))
    style_panel(ax, t["p1_t"], t["p1_s"], ylo, yhi, yt, t["comma"])
    l1_0, l1_1, l1_2, l1_3 = t["p1_l"]
    draw_bars_with_auto_labels(ax, xi, d["bip_r"], [d["pg"], d["bau"], d["hvg"]], l1_0, t["comma"], ylo, yhi)
    for key, col, mk, ms, lbl in (("pg", "#D97706", "o", 2.5, l1_1), ("bau", "#64748B", "s", 2.5, l1_2), ("hvg", "#059669", "^", 2.8, l1_3)):
        ax.plot(xi, d[key], color=col, lw=1.9, marker=mk, ms=ms, label=lbl, zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.yaxis.grid(False); set_legend(ax, 2)

def draw_p2(ax, t, d):
    xi, xl_bip = d["xi"], d["xl_bip"]
    ylo, yhi, yt, _ = sync_ylim_like_plotly(np.concatenate([d["bip_n"], d["kp"], d["kph"], d["aus"], d["binv"], d["exp"], d["imp"]]))
    style_panel(ax, t["p2_t"], t["p2_s"], ylo, yhi, yt, t["comma"], title_y=1.52, sub_y=1.43)
    l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]
    draw_bars_with_auto_labels(ax, xi, d["bip_n"], [d[k] for k in ("kp", "kph", "aus", "binv", "exp", "imp")], l2_0, t["comma"], ylo, yhi)
    for vals, col, lbl, lstyle in ((d["kp"], "#059669", l2_1, "-"), (d["kph"], "#D97706", l2_2, "--"), (d["aus"], "#7C3AED", l2_3, "-"), (d["binv"], "#0284C7", l2_4, "-"), (d["exp"], "#DC2626", l2_5, "-"), (d["imp"], "#64748B", l2_6, "-")):
        ax.plot(xi, vals, color=col, lw=1.7, ls=lstyle, label=lbl, zorder=3)
    ax.set_xticks(xi); ax.set_xticklabels(xl_bip); ax.yaxis.grid(False)
    set_legend(ax, 3 if ax.figure.get_figwidth() < 10 else 2)

def draw_p3(ax, t, d):
    s_ai, s_ab = d["s_ai"], d["s_ab"]; xm = np.arange(len(s_ai))
    ylo, yhi, yt, _ = sync_ylim_like_plotly(list(s_ai.values) + list(s_ab.values))
    style_panel(ax, t["p3_t"], t["p3_s"], ylo, yhi, yt, t["comma"])
    l3_0, l3_1 = t["p3_l"]
    ax.plot(xm, s_ai.values, color="#1B3A6B", lw=2.1, marker="o", ms=3, label=l3_0, zorder=3)
    ax.plot(xm, s_ab.values, color="#D97706", lw=2.0, marker="s", ms=3, label=l3_1, zorder=3)
    mark_ends(ax, [(xm, s_ai.values, "#1B3A6B"), (xm, s_ab.values, "#D97706")], t["comma"], yhi - ylo)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_ai.index)); set_legend(ax, 1)

def draw_p4(ax, t, d):
    s_pi, s_pb, s_eh = d["s_pi"], d["s_pb"], d["s_eh"]; xm = np.arange(len(s_pi))
    ylo, yhi, yt, _ = sync_ylim_like_plotly(list(s_pi.values) + list(s_pb.values) + list(s_eh.values))
    style_panel(ax, t["p4_t"], t["p4_s"], ylo, yhi, yt, t["comma"])
    l4_0, l4_1, l4_2 = t["p4_l"]
    ax.plot(xm, s_pi.values, color="#1B3A6B", lw=2.1, marker="o", ms=3, label=l4_0, zorder=3)
    ax.plot(xm, s_pb.values, color="#D97706", lw=2.0, marker="s", ms=3, label=l4_1, zorder=3)
    ax.plot(xm, s_eh.values, color="#059669", lw=2.0, marker="^", ms=3.5, label=l4_2, zorder=3)
    mark_ends(ax, [(xm, s_pi.values, "#1B3A6B"), (xm, s_pb.values, "#D97706"), (xm, s_eh.values, "#059669")], t["comma"], yhi - ylo)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_pi.index)); set_legend(ax, 2)

def draw_p5(ax, t, d):
    s_lb = d["s_lb"]; xm = np.arange(len(s_lb))
    ylo, yhi, yt, _ = sync_ylim_like_plotly(list(s_lb.values))
    style_panel(ax, t["p5_t"], t["p5_s"], ylo, yhi, yt, t["comma"], z=(ylo < 0))
    draw_bars_with_labels(ax, xm, s_lb.values, t["p5_l"], t["comma"], yhi - ylo); ax.set_xticks(xm); ax.set_xticklabels(list(s_lb.index)); set_legend(ax, 1)

def draw_p6(ax, t, d):
    s_al, s_hv = d["s_al"], d["s_hv"]; xm = np.arange(len(s_al))
    ylo, yhi, yt, _ = sync_ylim_like_plotly(list(s_al.values) + list(s_hv.values) + [2.0, 3.0])
    style_panel(ax, t["p6_t"], t["p6_s"], ylo, yhi, yt, t["comma"], z=False)
    l6_0, l6_1, l6_2, l6_3 = t["p6_l"]
    ax.plot(xm, s_al.values, color="#1B3A6B", lw=2.2, marker="o", ms=3.2, label=l6_0, zorder=3); ax.axhline(3.0, color="#1B3A6B", ls=":", lw=1.3, label=l6_1, zorder=2)
    ax.plot(xm, s_hv.values, color="#D97706", lw=2.2, marker="s", ms=3.2, label=l6_2, zorder=3); ax.axhline(2.0, color="#D97706", ls=":", lw=1.3, label=l6_3, zorder=2)
    mark_ends(ax, [(xm, s_al.values, "#1B3A6B"), (xm, s_hv.values, "#D97706")], t["comma"], yhi - ylo)
    ax.set_xticks(xm); ax.set_xticklabels(list(s_al.index)); set_legend(ax, 2)

def add_png_data_table(fig, period_labels, rows, indicator_header, use_comma):
    row_count = len(rows) + 1
    table_height = 230 / 300 if row_count == 5 else 310 / 300
    footer_height = 68 / 300
    chart_gap_reduction = 60
    original_height = fig.get_figheight()
    new_height = original_height + table_height
    axes = list(fig.axes)
    fig.set_size_inches(fig.get_figwidth(), new_height)
    for ax in axes:
        x, y, width, height = ax.get_position().bounds
        y = (y * original_height + table_height) / new_height
        height = height * original_height / new_height
        gap = chart_gap_reduction / (300 * new_height)
        ax.set_position((x, y - gap, width, height + gap))

    plot_x, _, plot_width, _ = axes[0].get_position().bounds
    table_ax = fig.add_axes((
        plot_x,
        footer_height / new_height,
        plot_width,
        (table_height - footer_height) / new_height,
    ))
    table_ax.axis("off")
    cell_text = [
        [label, *(format_table_value(value, use_comma) for value in values)]
        for label, values in rows
    ]
    table = table_ax.table(
        cellText=cell_text,
        colLabels=[indicator_header, *period_labels],
        colWidths=[0.47] + [0.53 / len(period_labels)] * len(period_labels),
        cellLoc="center",
        colLoc="center",
        bbox=(0, 0, 1, 1),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(6.5)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#CBD5E1")
        cell.set_linewidth(0.35)
        if column == 0:
            cell.get_text().set_fontsize(6.8)
        if row == 0:
            cell.set_facecolor("#E2E8F0")
            cell.set_text_props(weight="bold", color="#0F172A", ha="left" if column == 0 else "center")
        elif row == 1:
            cell.set_facecolor("#F8FAFC" if column == 0 else "white")
            cell.set_text_props(weight="bold", color="#1E293B" if column == 0 else "#334155", ha="left" if column == 0 else "center")
        elif column == 0:
            cell.set_facecolor("#F8FAFC")
            cell.set_text_props(weight="bold", color="#1E293B", ha="left")
        else:
            cell.set_facecolor("white")
            cell.set_text_props(color="#334155")
    separator_x = 0.47 + 0.53 * 7 / len(period_labels)
    table_ax.plot(
        (separator_x, separator_x), (0, 1),
        color="#94A3B8", linewidth=0.7,
        transform=table_ax.transAxes, zorder=5,
    )


def save_single(draw_fn, t, data, fname, src_key, top_adj=0.68, table_rows=None):
    fig, ax = plt.subplots(figsize=(7.4, 4.9), dpi=300, facecolor="white"); plt.subplots_adjust(left=0.09, right=0.93, top=top_adj, bottom=0.24); draw_fn(ax, t, data)
    for txt in list(ax.texts):
        if txt.get_text() == "T.H.": txt.remove()
    if table_rows is not None:
        add_png_data_table(
            fig,
            data["bip_table_labels"],
            table_rows,
            "Indicator" if t["sfx"] else "Indikator",
            t["comma"],
        )
    footer_y = 0.004
    fig.text(0.09, footer_y, f"{t[src_key]}{datetime.now().strftime(t['date_fmt'])}", fontsize=7.5, color="#64748B")
    fig.text(0.93, footer_y, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/dashboard/{fname}{t['sfx']}.png", dpi=300); plt.close()

def build_for_lang(lang, data, bip_only=False):
    t, use_c = TEXTS[lang], TEXTS[lang]["comma"]; plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    if not bip_only:
        fig, axes = plt.subplots(3, 2, figsize=(12.6, 18.4), dpi=300, facecolor="white"); plt.subplots_adjust(left=0.06, right=0.95, top=0.88, bottom=0.06, hspace=0.68, wspace=0.20)
        ax1, ax2, ax3, ax4, ax5, ax6 = axes.flatten()
        draw_p1(ax1, t, data); draw_p2(ax2, t, data); draw_p3(ax3, t, data); draw_p4(ax4, t, data); draw_p5(ax5, t, data); draw_p6(ax6, t, data)
        fig.text(0.06, 0.015, f"{t['src_all']}{datetime.now().strftime(t['date_fmt'])}", fontsize=8, color="#64748B")
        plt.savefig(f"static/dashboard/dashboard{t['sfx']}.png", dpi=300); plt.close()
    singles = ((draw_p1, "01_bip_entstehung", "src_destatis", 0.68), (draw_p2, "02_bip_verwendung", "src_destatis", 0.60))
    if not bip_only:
        singles += ((draw_p3, "03_auftragseingaenge", "src_destatis", 0.68), (draw_p4, "04_produktion_einzelhandel", "src_destatis", 0.68), (draw_p5, "05_leistungsbilanz", "src_bbk", 0.68), (draw_p6, "06_arbeitslosigkeit_inflation", "src_ba_destatis", 0.68))
    png_table_rows = {
        "01_bip_entstehung": list(zip(t["p1_l"], [data[key] for key in ("bip_r_table", "pg_table", "bau_table", "hvg_table")])),
        "02_bip_verwendung": list(zip(t["p2_l"], [data[key] for key in ("bip_n_table", "kp_table", "kph_table", "aus_table", "binv_table", "exp_table", "imp_table")])),
    }
    for fn, nm, sk, tp in singles:
        save_single(fn, t, data, nm, sk, tp, png_table_rows.get(nm))
    update_dashboard_content(lang, data)
    now_str_p, fmt_arr = datetime.now().strftime(t["date_fmt"]), lambda seq: [fmt_num(v, use_c) for v in seq]

    def save_dash_plotly(fig_p, title_p, sub_p, src_key, fname_p, top_m=132, height_p=470, x_tick_labels=None, show_y_grid=True, title_y=0.955, legend_orientation="v", legend_y=1.01):
        fig_p.update_layout(
            title=dict(text=f"<b>{title_p}</b><br><span style='font-size:11.5px;color:#475569;'>{sub_p}</span>", x=0.03, y=title_y, yanchor="top", font=dict(size=16, color="#0F172A", family="DejaVu Sans, sans-serif")),
            plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
            hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
            legend=dict(orientation=legend_orientation, x=0.0, y=legend_y, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
            margin=dict(l=46, r=16, t=top_m, b=95), height=height_p,
            annotations=list(fig_p.layout.annotations or []) + [dict(text=f"{t[src_key]}{now_str_p}", x=0.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"), dict(text="T.H.", x=1.0, y=-0.30, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")]
        )
        if use_c:
            fig_p.update_layout(separators=",.")
        if x_tick_labels is None:
            fig_p.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
        else:
            fig_p.update_xaxes(type="linear", tickmode="array", tickvals=list(range(len(x_tick_labels))), ticktext=x_tick_labels, fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickfont=dict(size=10.5, color="#475569"))
        fig_p.update_yaxes(fixedrange=True, showgrid=show_y_grid, gridcolor="#E2E8F0", zeroline=True, zerolinecolor="#64748B", zerolinewidth=1.2, tickfont=dict(size=10.5, color="#475569"))
        out_path = f"static/dashboard/{fname_p}{t['sfx']}.html"
        fig_p.write_html(out_path, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
        with open(out_path, "r", encoding="utf-8") as fh: html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
        with open(out_path, "w", encoding="utf-8") as fh: fh.write(html_s)

    xq_p = [" " if x == "" else str(x) for x in data["xl_bip"]]
    fp1 = go.Figure(); l1_0, l1_1, l1_2, l1_3 = t["p1_l"]; h1_0, h1_1, h1_2, h1_3 = t["p1_h"]; y1_0 = [None if np.isnan(v) else round(float(v), 1) for v in data["bip_r"]]
    fp1.add_trace(go.Bar(x=list(data["xi"]), y=y1_0, customdata=fmt_arr(y1_0), name=l1_0, marker=dict(color="#DBEAFE", line=dict(color="#1E3A8A", width=1.1)), hovertemplate=f"{h1_0}: <b>%{{customdata}} %</b><extra></extra>"))
    for lbl_s, hov_s, key_s, col_s in ((l1_1, h1_1, "pg", "#D97706"), (l1_2, h1_2, "bau", "#64748B"), (l1_3, h1_3, "hvg", "#059669")):
        ys = [None if np.isnan(v) else round(float(v), 1) for v in data[key_s]]
        fp1.add_trace(go.Scatter(x=list(data["xi"]), y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.1), hovertemplate=f"{hov_s}: <b>%{{customdata}} %</b><extra></extra>"))
    y1_values = np.concatenate([data[key] for key in ("bip_r", "pg", "bau", "hvg")])
    y1_lo, y1_hi, _, _ = sync_ylim_like_plotly(y1_values)
    add_bar_value_annotations(fp1, data["xi"], data["bip_r"], [data[key] for key in ("pg", "bau", "hvg")], y1_hi - y1_lo, use_c)
    save_dash_plotly(fp1, t["p1_t"], t["p1_s"], "src_destatis", "01_bip_entstehung", 135, 480, xq_p, False, title_y=0.95, legend_orientation="h", legend_y=1.02)

    fp2 = go.Figure(); l2_0, l2_1, l2_2, l2_3, l2_4, l2_5, l2_6 = t["p2_l"]; h2_0, h2_1, h2_2, h2_3, h2_4, h2_5, h2_6 = t["p2_h"]; y2_0 = [None if np.isnan(v) else round(float(v), 1) for v in data["bip_n"]]
    fp2.add_trace(go.Bar(x=list(data["xi"]), y=y2_0, customdata=fmt_arr(y2_0), name=l2_0, marker=dict(color="#DBEAFE", line=dict(color="#1E3A8A", width=1.1)), hovertemplate=f"{h2_0}: <b>%{{customdata}} %</b><extra></extra>"))
    for lbl_s, hov_s, key_s, col_s, d_style in ((l2_1, h2_1, "kp", "#059669", "solid"), (l2_2, h2_2, "kph", "#D97706", "dash"), (l2_3, h2_3, "aus", "#7C3AED", "solid"), (l2_4, h2_4, "binv", "#0284C7", "solid"), (l2_5, h2_5, "exp", "#DC2626", "solid"), (l2_6, h2_6, "imp", "#64748B", "solid")):
        ys = [None if np.isnan(v) else round(float(v), 1) for v in data[key_s]]
        fp2.add_trace(go.Scatter(x=list(data["xi"]), y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.0, dash=d_style), hovertemplate=f"{hov_s}: <b>%{{customdata}} %</b><extra></extra>"))
    y2_values = np.concatenate([data[key] for key in ("bip_n", "kp", "kph", "aus", "binv", "exp", "imp")])
    y2_lo, y2_hi, _, _ = sync_ylim_like_plotly(y2_values)
    add_bar_value_annotations(fp2, data["xi"], data["bip_n"], [data[key] for key in ("kp", "kph", "aus", "binv", "exp", "imp")], y2_hi - y2_lo, use_c)
    save_dash_plotly(fp2, t["p2_t"], t["p2_s"], "src_destatis", "02_bip_verwendung", 155, 535, xq_p, False, title_y=0.95, legend_orientation="h", legend_y=1.02)

    if bip_only:
        return

    fp3 = go.Figure(); l3_0, l3_1 = t["p3_l"]; s_ai, s_ab = data["s_ai"], data["s_ab"]; y3_0, y3_1 = [None if np.isnan(v) else round(float(v), 1) for v in s_ai.values], [None if np.isnan(v) else round(float(v), 1) for v in s_ab.values]
    fp3.add_trace(go.Scatter(x=list(s_ai.index), y=y3_0, customdata=fmt_arr(y3_0), name=l3_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l3_0}: <b>%{{customdata}} %</b><extra></extra>"))
    fp3.add_trace(go.Scatter(x=list(s_ab.index), y=y3_1, customdata=fmt_arr(y3_1), name=l3_1, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.2), hovertemplate=f"{l3_1}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp3, t["p3_t"], t["p3_s"], "src_destatis", "03_auftragseingaenge", 112, 450)

    fp4 = go.Figure(); l4_0, l4_1, l4_2 = t["p4_l"]
    for lbl_s, key_s, col_s in ((l4_0, "s_pi", "#1B3A6B"), (l4_1, "s_pb", "#D97706"), (l4_2, "s_eh", "#059669")):
        ser_p = data[key_s]; ys = [None if np.isnan(v) else round(float(v), 1) for v in ser_p.values]
        fp4.add_trace(go.Scatter(x=list(ser_p.index), y=ys, customdata=fmt_arr(ys), name=lbl_s, mode="lines+markers", marker=dict(size=5), line=dict(color=col_s, width=2.2), hovertemplate=f"{lbl_s}: <b>%{{customdata}} %</b><extra></extra>"))
    save_dash_plotly(fp4, t["p4_t"], t["p4_s"], "src_destatis", "04_produktion_einzelhandel", 127, 465)

    fp5 = go.Figure(); s_lb = data["s_lb"]; y5 = [None if np.isnan(v) else round(float(v), 1) for v in s_lb.values]
    fp5.add_trace(go.Bar(x=list(s_lb.index), y=y5, customdata=fmt_arr(y5), name=t["p5_l"], marker_color="#1B3A6B", hovertemplate=f"<b>%{{customdata}} {t['unit_lb']}</b><extra></extra>"))
    save_dash_plotly(fp5, t["p5_t"], t["p5_s"], "src_bbk", "05_leistungsbilanz", 97, 435)

    fp6 = go.Figure(); l6_0, l6_1, l6_2, l6_3 = t["p6_l"]; s_al, s_hv = data["s_al"], data["s_hv"]; x6 = list(s_al.index); y6_0, y6_2 = [None if np.isnan(v) else round(float(v), 1) for v in s_al.values], [None if np.isnan(v) else round(float(v), 1) for v in s_hv.values]
    fp6.add_trace(go.Scatter(x=x6, y=y6_0, customdata=fmt_arr(y6_0), name=l6_0, mode="lines+markers", marker=dict(size=5), line=dict(color="#1B3A6B", width=2.3), hovertemplate=f"{l6_0}: <b>%{{customdata}} %</b><extra></extra>"))
    fp6.add_trace(go.Scatter(x=x6, y=[3.0]*len(x6), name=l6_1, mode="lines", line=dict(color="#1B3A6B", width=1.4, dash="dot"), hoverinfo="skip"))
    fp6.add_trace(go.Scatter(x=x6, y=y6_2, customdata=fmt_arr(y6_2), name=l6_2, mode="lines+markers", marker=dict(size=5), line=dict(color="#D97706", width=2.3), hovertemplate=f"{l6_2}: <b>%{{customdata}} %</b><extra></extra>"))
    fp6.add_trace(go.Scatter(x=x6, y=[2.0]*len(x6), name=l6_3, mode="lines", line=dict(color="#D97706", width=1.4, dash="dot"), hoverinfo="skip"))
    save_dash_plotly(fp6, t["p6_t"], t["p6_s"], "src_ba_destatis", "06_arbeitslosigkeit_inflation", 142, 480)

def align_series(series_list):
    all_idx = sorted(set().union(*(s.index for s in series_list if not s.empty)))[-13:]
    return [s.reindex(all_idx) for s in series_list]

def valid_times(df, req_codes, pattern):
    if df.empty or "ZEIT" not in df.columns:
        return []
    req_set = set(req_codes)
    sub = df[df["_CODES"].apply(lambda s: req_set.issubset(s))].copy()
    sub["V"] = pd.to_numeric(sub["WERT"].astype(str).str.replace(",", "."), errors="coerce")
    sub = sub.dropna(subset=["V"])
    return sorted([z for z in sub["ZEIT"].astype(str).str.strip().unique() if re.match(pattern, z)])

def main(bip_only=False):
    def fetch_bip_table(table):
        return load_destatis_cache(table) if bip_only else get_destatis(table, "2018")

    df_y1, df_q1 = fetch_bip_table("81000-0001"), fetch_bip_table("81000-0002")
    df_y1_br, df_q1_br = fetch_bip_table("81000-0013"), fetch_bip_table("81000-0014")
    df_y2, df_q2 = fetch_bip_table("81000-0019"), fetch_bip_table("81000-0020")

    yrs = tuple(str(year) for year in range(2019, 2026))
    qtrs = tuple(sorted(set(
        valid_times(df_q1, ["DG", "WERTORG", "VGR014", "VGRPKM"], r"^\d{4}-Q[1-4]$") +
        valid_times(df_q2, ["DG", "WERTORG", "VGR014", "VGRJPM"], r"^\d{4}-Q[1-4]$")
    ))[-5:])
    xl_bip, xi = yrs + ("",) + tuple(f"Q{q[-1]} {q[2:4]}" for q in qtrs), np.arange(len(yrs) + 1 + len(qtrs))

    def get_bip_series(df_y, df_q, codes_y, codes_q, is_rate=False):
        vy = extract_by_codes(df_y, codes_y, yrs, is_rate=is_rate)
        vq = extract_by_codes(df_q, codes_q, qtrs, is_rate=is_rate)
        return np.array(vy + [np.nan] + vq, dtype=float)

    bip_r = get_bip_series(df_y1, df_q1, ["DG", "VGR014", "VGRPKM"], ["DG", "WERTORG", "VGR014", "VGRPKM"], is_rate=False)
    pg = get_bip_series(df_y1_br, df_q1_br, ["DG", "BWS001", "VGRPKM", "WZ08-B-18"], ["DG", "WERTORG", "BWS001", "VGRPKM", "WZ08-B-18"])
    bau = get_bip_series(df_y1_br, df_q1_br, ["DG", "BWS001", "VGRPKM", "WZ08-F"], ["DG", "WERTORG", "BWS001", "VGRPKM", "WZ08-F"])
    hvg = get_bip_series(df_y1_br, df_q1_br, ["DG", "BWS001", "VGRPKM", "WZ08-G-01"], ["DG", "WERTORG", "BWS001", "VGRPKM", "WZ08-G-01"])

    bip_n = get_bip_series(df_y2, df_q2, ["DG", "VGR014", "VGRJPM"], ["DG", "WERTORG", "VGR014", "VGRJPM"])
    kp = get_bip_series(df_y2, df_q2, ["DG", "VGR026", "VGRPKM"], ["DG", "WERTORG", "VGR026", "VGRPKM"])
    kph = get_bip_series(df_y2, df_q2, ["DG", "VGR015", "VGRPKM"], ["DG", "WERTORG", "VGR015", "VGRPKM"])
    aus = get_bip_series(df_y2, df_q2, ["DG", "VGR008", "VGRPKM"], ["DG", "WERTORG", "VGR008", "VGRPKM"])
    binv = get_bip_series(df_y2, df_q2, ["DG", "VGR009", "VGRPKM"], ["DG", "WERTORG", "VGR009", "VGRPKM"])
    exp = get_bip_series(df_y2, df_q2, ["DG", "EXP001", "VGRPKM"], ["DG", "WERTORG", "EXP001", "VGRPKM"])
    imp = get_bip_series(df_y2, df_q2, ["DG", "IMP001", "VGRPKM"], ["DG", "WERTORG", "IMP001", "VGRPKM"])

    table_indices = list(range(len(yrs))) + list(range(len(yrs) + 1, len(xl_bip)))
    table_periods = yrs + qtrs
    table_labels = yrs + tuple(f"Q{quarter[-1]} {quarter[2:4]}" for quarter in qtrs)
    table_data = {
        f"{key}_table": np.array([series[index] for index in table_indices], dtype=float)
        for key, series in (
            ("bip_r", bip_r), ("pg", pg), ("bau", bau), ("hvg", hvg),
            ("bip_n", bip_n), ("kp", kp), ("kph", kph), ("aus", aus),
            ("binv", binv), ("exp", exp), ("imp", imp),
        )
    }
    data = {
        "xi": xi, "xl_bip": xl_bip,
        "bip_r": bip_r, "pg": pg, "bau": bau, "hvg": hvg,
        "bip_n": bip_n, "kp": kp, "kph": kph, "aus": aus,
        "binv": binv, "exp": exp, "imp": imp,
        "bip_table_labels": table_labels,
        **table_data,
    }
    if bip_only:
        build_for_lang("de", data, bip_only=True)
        build_for_lang("en", data, bip_only=True)
        return

    df_ind_ae = get_destatis("42151-0004", "2023")
    df_bau_ae = pd.DataFrame()
    for bau_tbl in ("44111-0009", "44111-0010", "44111-0011"):
        try:
            cand = get_destatis(bau_tbl, "2023")
            if any("AUF102" in s for s in cand["_CODES"]) and any(re.match(r"^\d{4}-\d{2}$", str(z)) for z in cand["ZEIT"].unique()):
                df_bau_ae = cand; break
        except Exception:
            pass
    m_ae = sorted(set(
        valid_times(df_ind_ae, ["DG", "WERTORG", "INSGESAMT", "WZ08-C", "AUF102"], r"^\d{4}-\d{2}$") +
        valid_times(df_bau_ae, ["DG", "WERTORG", "BTR-20UMTP", "BAUART", "AUF102"], r"^\d{4}-\d{2}$")
    ))[-13:]
    s_ai = pd.Series(extract_by_codes(df_ind_ae, ["DG", "WERTORG", "INSGESAMT", "WZ08-C", "AUF102"], m_ae), index=m_ae)
    s_ab = pd.Series(extract_by_codes(df_bau_ae, ["DG", "WERTORG", "BTR-20UMTP", "BAUART", "AUF102"], m_ae), index=m_ae)
    s_ai, s_ab = align_series([s_ai, s_ab])

    df_prod = get_destatis("42153-0001", "2023")
    df_eh = get_destatis("45212-0004", "2023")
    m_pe = sorted(set(
        valid_times(df_prod, ["DG", "WERTORG", "WZ08-B-20", "PRO101"], r"^\d{4}-\d{2}$") +
        valid_times(df_prod, ["DG", "WERTORG", "WZ08-F", "PRO101"], r"^\d{4}-\d{2}$") +
        valid_times(df_eh, ["DG", "REAL", "WZ08-47", "UMS103"], r"^\d{4}-\d{2}$")
    ))[-13:]
    s_pi = pd.Series(extract_by_codes(df_prod, ["DG", "WERTORG", "WZ08-B-20", "PRO101"], m_pe), index=m_pe)
    s_pb = pd.Series(extract_by_codes(df_prod, ["DG", "WERTORG", "WZ08-F", "PRO101"], m_pe), index=m_pe)
    s_eh = pd.Series(extract_by_codes(df_eh, ["DG", "REAL", "WZ08-47", "UMS103"], m_pe), index=m_pe)
    s_pi, s_pb, s_eh = align_series([s_pi, s_pb, s_eh])

    s_lb = get_bbk(["BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL"], 13, 0.001)

    df_al = get_destatis("13211-0002", "2023")
    if "2_variable_attribute_label" in df_al.columns:
        df_al = df_al[df_al["2_variable_attribute_label"].astype(str).str.strip() == "Insgesamt"].copy()
    df_hv = get_destatis("61121-0002", "2023")
    m_al_hv = sorted(set(
        valid_times(df_al, ["ERW112"], r"^\d{4}-\d{2}$") +
        valid_times(df_hv, ["DG", "VRM002"], r"^\d{4}-\d{2}$")
    ))[-13:]
    s_al = pd.Series(extract_by_codes(df_al, ["ERW112"], m_al_hv, is_rate=True), index=m_al_hv)
    s_hv = pd.Series(extract_by_codes(df_hv, ["DG", "VRM002"], m_al_hv, is_rate=True), index=m_al_hv)

    data.update({"s_ai": s_ai, "s_ab": s_ab, "s_pi": s_pi, "s_pb": s_pb, "s_eh": s_eh, "s_lb": s_lb, "s_al": s_al, "s_hv": s_hv})
    build_for_lang("de", data); build_for_lang("en", data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bip-only", action="store_true", help="Render GDP charts from local Destatis caches only")
    main(bip_only=parser.parse_args().bip_only)
