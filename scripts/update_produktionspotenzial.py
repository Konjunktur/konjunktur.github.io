#!/usr/bin/env python3
"""Update-Skript: Produktionspotenzial nach Claus Koehler (DE & EN, PNG & HTML)."""

import io
import math
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

OUT_DIR = Path("static/produktionspotenzial")
GENESIS_BASE = "https://destatis.de"
LT, GT = chr(60), chr(62)

SVR_Y = [(1992, 1993), (2001, 2003), (2008, 2009), (2020, 2020), (2022, 2025)]
SVR_Q = [("1992-01", "1993-04"), ("2001-01", "2003-02"), ("2008-02", "2009-02"), ("2020-01", "2020-02"), ("2022-04", "2025-04")]
C_NAVY, C_ORANGE, C_GREEN, C_SLATE, C_GRID = "#1E3A8A", "#D97706", "#059669", "#475569", "#E2E8F0"
C_SVR, C_BIP = "rgba(148,163,184,0.30)", "rgba(96,165,250,0.36)"


def _f(val) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    s = str(val).strip().replace("\xa0", "").replace(" ", "")
    if s in ("", ".", "-", "...", "x", "/", "nan", "NaN", "None"):
        return np.nan
    s = s.replace(".", "").replace(",", ".") if ("," in s and "." in s) else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def fetch_table(table_id: str, startyear: int = 1991) -> pd.DataFrame:
    user, pwd = os.environ.get("DESTATIS_USER", "").strip(), os.environ.get("DESTATIS_PASS", "").strip()
    if not user or not pwd:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    r = requests.get(
        f"{GENESIS_BASE}/data/tablefile",
        params={"username": user, "password": pwd, "name": table_id, "area": "all", "compress": "false",
                "transpose": "false", "startyear": str(startyear), "endyear": str(datetime.now().year + 1),
                "language": "de", "format": "ffcsv"},
        timeout=90,
    )
    r.raise_for_status()
    lines = r.content.decode("utf-8-sig", errors="replace").splitlines()
    idx = next((i for i, l in enumerate(lines) if l.startswith(("statistics_code;", "Statistik_Code;"))), 0)
    df = pd.read_csv(io.StringIO("\n".join(lines[idx:])), sep=";", dtype=str, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    return df


def _col(df: pd.DataFrame, names: list[str]) -> str:
    low = {c.lower(): c for c in df.columns}
    return next((low[n.lower()] for n in names if n.lower() in low), "")


def _prep_df(df: pd.DataFrame, inc: list[str], exc: list[str], is_year: bool) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if ("variable_code" in c.lower() or "merkmal" in c.lower()) and (df[c].fillna("") == "WERTORG").any():
            df = df[df[c].fillna("") == "WERTORG"]
    c_tc, c_vl = _col(df, ["time_code", "Zeit_Code"]), _col(df, ["value_variable_label", "Wert_Merkmal_Label"])
    if is_year and c_tc and (df[c_tc].fillna("") == "JAHR").any():
        df = df[df[c_tc].fillna("") == "JAHR"]
    if c_vl and inc:
        lbl = df[c_vl].fillna("").str.lower()
        m = pd.Series(True, index=df.index)
        for k in inc:
            m &= lbl.str.contains(k.lower(), regex=False)
        for k in exc:
            m &= ~lbl.str.contains(k.lower(), regex=False)
        df = df[m]
    for c in df.columns:
        if c.endswith("_code") and c not in (c_tc, "statistics_code", "value_variable_code"):
            v = df[c].fillna("")
            if (v == "INSGESAMT").any():
                df = df[v == "INSGESAMT"]
            elif (v == "WZ08-00").any():
                df = df[v == "WZ08-00"]
    return df


def extract_q(df: pd.DataFrame, inc: list[str], exc: list[str], vmin: float, vmax: float) -> pd.Series:
    df = _prep_df(df, inc, exc, False)
    ct, cc, cv = _col(df, ["time", "Zeit"]), _col(df, ["time_code", "Zeit_Code"]), _col(df, ["value", "Wert"])
    if not ct or not cv:
        return pd.Series(dtype=float)
    qmap, out = {"QUART1": 1, "QUART2": 2, "QUART3": 3, "QUART4": 4}, {}
    for _, r in df.iterrows():
        ys, qs = str(r[ct]).strip(), str(r[cc]).strip() if cc else ""
        if ys.isdigit() and qs in qmap:
            yr, qn = int(ys), qmap[qs]
        else:
            m = re.match(r"^(\d{4})[-/]?Q([1-4])$", ys)
            if not m:
                continue
            yr, qn = int(m.group(1)), int(m.group(2))
        val = _f(r[cv])
        if not np.isnan(val) and vmin <= val <= vmax:
            out[f"{yr:04d}-0{qn}"] = val
    s = pd.Series(out, dtype=float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def extract_y(df: pd.DataFrame, inc: list[str], exc: list[str], vmin: float, vmax: float) -> pd.Series:
    df = _prep_df(df, inc, exc, True)
    ct, cv = _col(df, ["time", "Zeit"]), _col(df, ["value", "Wert"])
    if not ct or not cv:
        return pd.Series(dtype=float)
    out = {}
    for _, r in df.iterrows():
        ys = str(r[ct]).strip()
        val = _f(r[cv])
        if re.match(r"^\d{4}$", ys) and not np.isnan(val) and vmin <= val <= vmax:
            out[int(ys)] = val
    s = pd.Series(out, dtype=float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def q_to_y(sq: pd.Series, agg: str = "sum") -> pd.Series:
    if len(sq) == 0:
        return pd.Series(dtype=float)
    g = pd.DataFrame({"yr": [int(k[:4]) for k in sq.index], "v": sq.values}).groupby("yr")["v"]
    res = g.sum() if agg == "sum" else g.mean()
    return res[g.count() == 4].sort_index()

def load_macro() -> dict:
    t_by, t_bq = fetch_table("81000-0001"), fetch_table("81000-0002")
    t_ey, t_eq = fetch_table("81000-0011"), fetch_table("81000-0012")
    t_fin, t_ay, t_am = fetch_table("81000-0031"), fetch_table("13211-0001"), fetch_table("13211-0002", 2005)

    br_q = extract_q(t_bq, ["bruttoinlandsprodukt", "preisbereinigt"], ["jeweiligen"], 300, 1500)
    bn_q = extract_q(t_bq, ["bruttoinlandsprodukt", "jeweiligen"], ["preisbereinigt"], 250, 2000)
    br_y = extract_y(t_by, ["bruttoinlandsprodukt", "preisbereinigt"], ["jeweiligen"], 1500, 5500).combine_first(q_to_y(br_q, "sum"))
    bn_y = extract_y(t_by, ["bruttoinlandsprodukt", "jeweiligen"], ["preisbereinigt"], 1200, 6500).combine_first(q_to_y(bn_q, "sum"))

    et_q = extract_q(t_eq, ["erwerbstätige", "inland"], ["arbeitnehmer"], 32000, 50000)
    if len(et_q) == 0:
        et_q = extract_q(t_eq, ["erwerbstätige"], ["arbeitnehmer"], 32000, 50000)
    et_y = extract_y(t_ey, ["erwerbstätige", "inland"], ["arbeitnehmer"], 32000, 50000)
    if len(et_y) == 0:
        et_y = extract_y(t_ey, ["erwerbstätige"], ["arbeitnehmer"], 32000, 50000)
    et_y = et_y.combine_first(q_to_y(et_q, "mean"))

    alo_y = extract_y(t_ay, ["arbeitslose"], ["quote"], 500_000, 7_000_000)
    ct, cc, cv, cl = _col(t_am, ["time", "Zeit"]), _col(t_am, ["time_code", "Zeit_Code"]), _col(t_am, ["value", "Wert"]), _col(t_am, ["value_variable_label", "Wert_Merkmal_Label"])
    mmap = {f"MONAT{m:02d}": m for m in range(1, 13)}
    alo_m_d, alq_all, alq_fb = {}, {}, {}
    for _, r in t_am.iterrows():
        ys, ts = str(r[ct]).strip(), str(r[cc]).strip() if cc else ""
        val = _f(r[cv])
        if not ys.isdigit() or ts not in mmap or np.isnan(val):
            continue
        ym, lbl = f"{int(ys):04d}-{mmap[ts]:02d}", str(r[cl]).lower() if cl else ""
        if "arbeitslose" in lbl and "quote" not in lbl and 500_000 <= val <= 7_000_000:
            alo_m_d[ym] = val
        elif "arbeitslosenquote" in lbl and 1.0 <= val <= 20.0:
            (alq_all if "alle zivilen erwerbspersonen" in lbl else alq_fb)[ym] = val
    alo_m = pd.Series(alo_m_d, dtype=float).sort_index()
    alq_m = pd.Series(alq_all if alq_all else alq_fb, dtype=float).sort_index()

    alo_q_d = {}
    if len(alo_m) > 0:
        dfm = pd.DataFrame({"yr": [int(k[:4]) for k in alo_m.index], "q": [(int(k[5:7]) - 1) // 3 + 1 for k in alo_m.index], "v": alo_m.values})
        for (yr, q), g in dfm.groupby(["yr", "q"]):
            if len(g) == 3:
                alo_q_d[f"{yr:04d}-0{q}"] = float(g["v"].mean())
        gy = dfm.groupby("yr")["v"]
        alo_y = alo_y.combine_first(gy.mean()[gy.count() == 12]).sort_index()
    alo_q_all = {f"{yr:04d}-0{q}": float(v) for yr, v in alo_y.items() if yr < 2005 for q in (1, 2, 3, 4)}
    alo_q_all.update(alo_q_d)
    alo_q = pd.Series(alo_q_all, dtype=float).sort_index()

    fin_y = extract_y(t_fin, ["finanzierungssaldo"], [], -500_000, 500_000)
    fin_q = extract_q(t_fin, ["finanzierungssaldo"], [], -300_000, 300_000)
    if len(fin_y) > 0 and fin_y.abs().median() > 1000:
        fin_y = fin_y / 1000.0
    if len(fin_q) > 0 and fin_q.abs().median() > 1000:
        fin_q = fin_q / 1000.0

    return {"br_y": br_y, "bn_y": bn_y, "br_q": br_q, "bn_q": bn_q, "et_y": et_y, "et_q": et_q,
            "alo_y": alo_y, "alo_q": alo_q, "alq_m": alq_m, "fin_y": fin_y, "fin_q": fin_q}


def build_datasets(m: dict) -> dict:
    iy = m["br_y"].index.intersection(m["et_y"].index).intersection(m["alo_y"].index).sort_values()
    iy = iy[iy >= 1991]
    last_y = int(iy.max())
    iq = m["br_q"].index.intersection(m["et_q"].index).intersection(m["alo_q"].index).sort_values()
    iq = iq[iq >= "1991-01"]

    pot_y = m["br_y"].loc[iy] * ((m["et_y"].loc[iy] + m["alo_y"].loc[iy] / 1000.0) / m["et_y"].loc[iy])
    util_y = (m["br_y"].loc[iy] / pot_y) * 100.0
    pot_q = m["br_q"].loc[iq] * ((m["et_q"].loc[iq] + m["alo_q"].loc[iq] / 1000.0) / m["et_q"].loc[iq])
    pot_q_ann, util_q = pot_q.rolling(4).sum(), (m["br_q"].loc[iq] / pot_q) * 100.0

    cq = [q for q in iq if int(q[:4]) > last_y]
    qlbl = lambda q: f"{q[:4]} " + {"01": "I", "02": "II", "03": "III", "04": "IV"}[q[5:7]]
    wy_y, wpot_y, walo_y, finp_y = m["br_y"].pct_change() * 100, pot_y.pct_change() * 100, m["alo_y"].pct_change() * 100, (m["fin_y"] / m["bn_y"]) * 100
    wy_q, wpot_q, walo_q, finp_q = m["br_q"].pct_change(4) * 100, pot_q.pct_change(4) * 100, m["alo_q"].pct_change(4) * 100, (m["fin_q"] / m["bn_q"]) * 100
    diff_y, diff_q = wy_y - wpot_y, wy_q - wpot_q

    iy_g, iy_s = [y for y in iy if y >= 1992 and not np.isnan(diff_y.get(y, np.nan))], [y for y in iy if y >= 2019]
    wpot_5 = wpot_y.dropna().tail(5)
    return {
        "wy_y": wy_y, "wy_q": wy_q, "alq_m": m["alq_m"],
        "lbl_l": [str(y) for y in iy] + [qlbl(q) for q in cq], "key_l": [("Y", y) for y in iy] + [("Q", q) for q in cq],
        "pot_l": [float(pot_y.loc[y]) for y in iy] + [float(pot_q_ann.loc[q]) for q in cq],
        "utl_l": [float(util_y.loc[y]) for y in iy] + [float(util_q.loc[q]) for q in cq],
        "mean_91_19": float(util_y.loc[(util_y.index >= 1991) & (util_y.index <= 2019)].mean()),
        "lbl_gl": [str(y) for y in iy_g] + [qlbl(q) for q in cq], "key_gl": [("Y", y) for y in iy_g] + [("Q", q) for q in cq],
        "dif_gl": [float(diff_y.loc[y]) for y in iy_g] + [float(diff_q.get(q, np.nan)) for q in cq],
        "alo_gl": [float(walo_y.get(y, np.nan)) for y in iy_g] + [float(walo_q.get(q, np.nan)) for q in cq],
        "fin_gl": [float(finp_y.get(y, np.nan)) for y in iy_g] + [float(finp_q.get(q, np.nan)) for q in cq],
        "lbl_s": [str(y) for y in iy_s] + [qlbl(q) for q in cq], "key_s": [("Y", y) for y in iy_s] + [("Q", q) for q in cq],
        "utl_s": [float(util_y.loc[y]) for y in iy_s] + [float(util_q.loc[q]) for q in cq],
        "dif_s": [float(diff_y.get(y, np.nan)) for y in iy_s] + [float(diff_q.get(q, np.nan)) for q in cq],
        "alo_s": [float(walo_y.get(y, np.nan)) for y in iy_s] + [float(walo_q.get(q, np.nan)) for q in cq],
        "fin_s": [float(finp_y.get(y, np.nan)) for y in iy_s] + [float(finp_q.get(q, np.nan)) for q in cq],
        "wpot_5m": float(wpot_5.mean()) if len(wpot_5) else 1.1,
        "wpot_5s": f"{int(wpot_5.index.min())}\u2013{int(wpot_5.index.max())}" if len(wpot_5) >= 2 else "",
        "de": datetime.now().strftime("%d.%m.%Y"), "en": datetime.now().strftime("%Y-%m-%d"),
    }


def _blocks(idxs: list[int]) -> list[tuple[float, float]]:
    if not idxs:
        return []
    s = sorted(set(idxs))
    res, st, pr = [], next(iter(s)), next(iter(s))
    for i in s[1:]:
        if i == pr + 1:
            pr = i
        else:
            res.append((st - 0.5, pr + 0.5))
            st = pr = i
    return res + [(st - 0.5, pr + 0.5)]


def add_shading(fig: go.Figure, keys: list[tuple], wy_y: pd.Series, wy_q: pd.Series, lang: str):
    svr = [i for i, (k, v) in enumerate(keys) if (any(a <= int(v) <= b for a, b in SVR_Y) if k == "Y" else any(a <= str(v) <= b for a, b in SVR_Q))]
    bip = [i for i, (k, v) in enumerate(keys) if (wy_y.get(int(v), 1) if k == "Y" else wy_q.get(str(v), 1)) < 0]
    for x0, x1 in _blocks(svr):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=C_SVR, line_width=0, layer="below")
    for x0, x1 in _blocks(bip):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=C_BIP, line_width=0, layer="below")
    for col, nm in ((C_SVR, "Rezessionsphasen (SVR/BBK)" if lang == "de" else "Recession phases (SVR/BBK)"),
                    (C_BIP, "Reales BIP < 0 % gg. Vj." if lang == "de" else "Real GDP < 0% YoY")):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, symbol="square", color=col), name=nm))

def finish_chart(fig: go.Figure, stem: str, title: str, sub: str, src: str, y1: str, r1=None, y2=None, r2=None, dt=2):
    fig.update_layout(
        title=dict(text=f"{LT}b{GT}{title}{LT}/b{GT}{LT}br{GT}{LT}span style='font-size:12px;color:#475569'{GT}{sub}{LT}/span{GT}",
                   x=0.01, y=0.97, font=dict(size=16, color="#0F172A", family="Inter,Arial,sans-serif")),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, x=0.0, bgcolor="rgba(255,255,255,0.85)", font=dict(size=11.5)),
        margin=dict(l=58, r=58 if y2 else 26, t=122, b=66), plot_bgcolor="#FFF", paper_bgcolor="#FFF",
        font=dict(family="Inter,Arial,sans-serif", color="#1E293B", size=12), hovermode="x unified", height=490,
    )
    fig.update_xaxes(type="category", showgrid=False, linecolor="#CBD5E1", tickangle=-45, nticks=max(10, 38 // dt))
    fig.update_yaxes(title_text=y1, gridcolor=C_GRID, zeroline=True, zerolinecolor="#94A3B8", range=r1, secondary_y=False if y2 else None)
    if y2:
        fig.update_yaxes(title_text=y2, showgrid=False, zeroline=False, range=r2, secondary_y=True)
    fig.add_annotation(text=src, xref="paper", yref="paper", x=0.0, y=-0.16, showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color="#64748B"))

    html = fig.to_html(include_plotlyjs="cdn", full_html=True, config={"displayModeBar": False, "responsive": True})
    css = f"{LT}style{GT}html,body{{margin:0;padding:0;overflow:hidden;width:100%;height:100%;background:#fff}}.plotly-graph-div{{width:100%!important;height:100%!important}}{LT}/style{GT}"
    (OUT_DIR / f"{stem}.html").write_text(html.replace(f"{LT}/head{GT}", f"{css}{LT}/head{GT}"), encoding="utf-8")
    try:
        fig.write_image(str(OUT_DIR / f"{stem}.png"), width=1100, height=520, scale=2)
    except Exception as e:
        print(f"[WARN] PNG {stem}: {e}")


def build_all_charts(s: dict):
    ex = f"{LT}extra{GT}{LT}/extra{GT}"
    src = lambda l: f"Quelle: Statistisches Bundesamt | Stand: {s['de']}" if l == "de" else f"Source: Federal Statistical Office | As of: {s['en']}"

    # 1. Produktionspotenzial
    for l in ("de", "en"):
        fig = go.Figure()
        add_shading(fig, s["key_l"], s["wy_y"], s["wy_q"], l)
        fig.add_trace(go.Scatter(x=s["lbl_l"], y=s["pot_l"], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                 name="Produktionspotenzial (Mrd. €)" if l == "de" else "Potential output (EUR bn)",
                                 hovertemplate=f"%{{x}}: %{{y:,.1f}}{ex}"))
        finish_chart(fig, "01_potenzial_lang" if l == "de" else "01_potenzial_lang_en",
                     "Entwicklung des Produktionspotenzials" if l == "de" else "Development of Potential Output",
                     "Preisbereinigtes Produktionspotenzial in Mrd. € | Jahreswerte ab 1991, danach Quartalswerte (4-Quartals-Summe)" if l == "de"
                     else "Price-adjusted potential output in EUR bn | Annual values from 1991, followed by quarterly values (4-quarter sum)",
                     src(l), "Mrd. €" if l == "de" else "EUR bn")

    # 2 & 5. Auslastung (lang & kurz)
    for st, prefix, lbl_k, key_k, val_k in ((False, "02_auslastung_lang", "lbl_l", "key_l", "utl_l"),
                                             (True, "05_auslastung_kurz", "lbl_s", "key_s", "utl_s")):
        vals = s[val_k]
        rng = [math.floor(min(vals) - 1.0), math.ceil(max(vals) + 0.5)]
        for l in ("de", "en"):
            fig = go.Figure()
            add_shading(fig, s[key_k], s["wy_y"], s["wy_q"], l)
            fig.add_trace(go.Scatter(x=s[lbl_k], y=vals, mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                     name="Auslastung des Produktionspotenzials (%)" if l == "de" else "Potential output utilization (%)",
                                     hovertemplate=f"%{{x}}: %{{y:.1f}} %{ex}"))
            if not st:
                mv = s["mean_91_19"]
                fig.add_hline(y=mv, line_dash="dash", line_color=C_SLATE,
                              annotation_text=f"Mittelwert 1991\u20132019: {mv:.1f} %".replace(".", ",") if l == "de" else f"Mean 1991\u20132019: {mv:.1f}%")
            t_de = "Auslastung des Produktionspotenzials (ab 2019)" if st else "Auslastung des Produktionspotenzials"
            t_en = "Potential Output Utilization (from 2019)" if st else "Potential Output Utilization"
            s_de = f"Reales BIP in % des Produktionspotenzials | Jahreswerte ab {'2019' if st else '1991'}, danach Quartalswerte"
            s_en = f"Real GDP as % of potential output | Annual values from {'2019' if st else '1991'}, followed by quarterly values"
            finish_chart(fig, prefix if l == "de" else f"{prefix}_en", t_de if l == "de" else t_en, s_de if l == "de" else s_en, src(l), "%", rng, dt=1 if st else 2)

    # 3, 4, 6, 7. Doppelachsen-Grafiken
    dual_specs = [
        ("alo", False, "03_angemessen_alo_lang", "lbl_gl", "key_gl", "dif_gl", "alo_gl", 30.0, C_ORANGE),
        ("staat", False, "04_angemessen_staat_lang", "lbl_gl", "key_gl", "dif_gl", "fin_gl", 12.0, C_GREEN),
        ("alo", True, "06_angemessen_alo_kurz", "lbl_s", "key_s", "dif_s", "alo_s", 20.0, C_ORANGE),
        ("staat", True, "07_angemessen_staat_kurz", "lbl_s", "key_s", "dif_s", "fin_s", 12.0, C_GREEN),
    ]
    for ind, st, prefix, lk, kk, dk, bk, lim, col in dual_specs:
        bvals = s[bk]
        vabs = [abs(v) for v in bvals if not np.isnan(v)]
        if vabs and max(vabs) > lim:
            lim = math.ceil(max(vabs) / 5.0) * 5.0
        for l in ("de", "en"):
            row_spec = [{"secondary_y": True}]
            fig = make_subplots(specs=[row_spec])
            add_shading(fig, s[kk], s["wy_y"], s["wy_q"], l)
            bname = ("Zuwachsrate Arbeitslose (% gg. Vj., rechts)" if l == "de" else "Unemployment growth (% YoY, right)") if ind == "alo" \
                else ("Finanzierungssaldo des Staates (% des nom. BIP, rechts)" if l == "de" else "Gov. net lending/borrowing (% of nom. GDP, right)")
            fig.add_trace(go.Bar(x=s[lk], y=bvals, name=bname, marker=dict(color=col, opacity=0.78), hovertemplate=f"%{{x}}: %{{y:+.1f}} %{ex}"), secondary_y=True)
            fig.add_trace(go.Scatter(x=s[lk], y=s[dk], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                     name="Wachstumsdifferenz wY \u2212 wY* (Ppkt., links)" if l == "de" else "Growth differential wY \u2212 wY* (pp, left)",
                                     hovertemplate=f"%{{x}}: %{{y:+.2f}}{ex}"), secondary_y=False)
            suf_de, suf_en = (" (ab 2019)" if st else ""), (" (from 2019)" if st else "")
            t = (f"Angemessenes/nicht angemessenes Wirtschaftswachstum und {'Arbeitslosigkeit' if ind == 'alo' else 'öffentliche Haushalte'}{suf_de}" if l == "de"
                 else f"Appropriate/Inappropriate Economic Growth and {'Unemployment' if ind == 'alo' else 'Public Finances'}{suf_en}")
            sub = ("Differenz wY \u2212 wY* (links) vs. " + ("Arbeitslosenentwicklung (rechts)" if ind == "alo" else "Finanzierungssaldo des Staates (rechts)") if l == "de"
                   else "Differential wY \u2212 wY* (left) vs. " + ("unemployment change (right)" if ind == "alo" else "government balance (right)"))
            finish_chart(fig, prefix if l == "de" else f"{prefix}_en", t, sub, src(l),
                         "Prozentpunkte (links)" if l == "de" else "Percentage points (left)", [-3.0, 3.0],
                         ("% gg. Vj. (rechts)" if ind == "alo" else "% des nom. BIP (rechts)") if l == "de" else ("% YoY (right)" if ind == "alo" else "% of nom. GDP (right)"),
                         [-lim, lim], dt=1 if st else 2)

    # 8 & 9. Notwendiges Wirtschaftswachstum
    alq_m = s["alq_m"]
    latest_ym = str(alq_m.index.max())
    for mode, prefix in (("year", "08_notwendig_jahr"), ("quarter", "09_notwendig_quartal")):
        if mode == "year":
            jk = f"{latest_ym[:4]}-01"
            ref = jk if jk in alq_m.index else str(alq_m.index.min())
        else:
            qe = [ym for ym in alq_m.index if ym[5:7] in ("03", "06", "09", "12")]
            ref = str(qe[-1]) if qe else latest_ym
        u0, wm = float(alq_m.loc[ref]), s["wpot_5m"]
        path = np.linspace(u0, 3.0, max(2, min(10, int(math.ceil((u0 - 3.0) / 0.45)))) + 1)
        req = [wm + max(0.0, (u - 3.0) / 0.45) for u in path]
        m_de = {"01": "Jan", "02": "Feb", "03": "Mrz", "04": "Apr", "05": "Mai", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dez"}[ref[5:7]]
        m_en = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}[ref[5:7]]
        for l in ("de", "en"):
            ml = f"{m_de if l == 'de' else m_en} {ref[2:4]}"
            xl = [f"{ml} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == 0 else (f"{'Ziel' if l == 'de' else 'Target'} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == len(path) - 1 else f"{'ALQ' if l == 'de' else 'UR'} {u:.1f}%") for i, u in enumerate(path)]
            tv = [f"{v:.1f} %".replace(".", ",") if l == "de" else f"{v:.1f}%" for v in req]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xl, y=req, mode="lines+markers+text", line=dict(color=C_ORANGE, width=3.0), marker=dict(size=8, color=C_ORANGE),
                                     name="Notwendiges reales BIP-Wachstum (%)" if l == "de" else "Necessary real GDP growth (%)",
                                     text=tv, textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(req))]))
            fig.add_hline(y=wm, line_dash="dash", line_color=C_NAVY, annotation_position="bottom left",
                          annotation_text=f"Potenzialwachstum wY* (5J-\u00d8 {s['wpot_5s']}): {wm:.1f} %".replace(".", ",") if l == "de" else f"Potential growth wY* (5Y avg {s['wpot_5s']}): {wm:.1f}%")

    # 3, 4, 6, 7. Doppelachsen-Grafiken
    dual_specs = [
        ("alo", False, "03_angemessen_alo_lang", "lbl_gl", "key_gl", "dif_gl", "alo_gl", 30.0, C_ORANGE),
        ("staat", False, "04_angemessen_staat_lang", "lbl_gl", "key_gl", "dif_gl", "fin_gl", 12.0, C_GREEN),
        ("alo", True, "06_angemessen_alo_kurz", "lbl_s", "key_s", "dif_s", "alo_s", 20.0, C_ORANGE),
        ("staat", True, "07_angemessen_staat_kurz", "lbl_s", "key_s", "dif_s", "fin_s", 12.0, C_GREEN),
    ]
    for ind, st, prefix, lk, kk, dk, bk, lim, col in dual_specs:
        bvals = s[bk]
        vabs = [abs(v) for v in bvals if not np.isnan(v)]
        if vabs and max(vabs) > lim:
            lim = math.ceil(max(vabs) / 5.0) * 5.0
        for l in ("de", "en"):
            row_spec = [{"secondary_y": True}]
            fig = make_subplots(specs=[row_spec])
            add_shading(fig, s[kk], s["wy_y"], s["wy_q"], l)
            bname = ("Zuwachsrate Arbeitslose (% gg. Vj., rechts)" if l == "de" else "Unemployment growth (% YoY, right)") if ind == "alo" \
                else ("Finanzierungssaldo des Staates (% des nom. BIP, rechts)" if l == "de" else "Gov. net lending/borrowing (% of nom. GDP, right)")
            fig.add_trace(go.Bar(x=s[lk], y=bvals, name=bname, marker=dict(color=col, opacity=0.78), hovertemplate=f"%{{x}}: %{{y:+.1f}} %{ex}"), secondary_y=True)
            fig.add_trace(go.Scatter(x=s[lk], y=s[dk], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                     name="Wachstumsdifferenz wY \u2212 wY* (Ppkt., links)" if l == "de" else "Growth differential wY \u2212 wY* (pp, left)",
                                     hovertemplate=f"%{{x}}: %{{y:+.2f}}{ex}"), secondary_y=False)
            suf_de, suf_en = (" (ab 2019)" if st else ""), (" (from 2019)" if st else "")
            t = (f"Angemessenes/nicht angemessenes Wirtschaftswachstum und {'Arbeitslosigkeit' if ind == 'alo' else 'öffentliche Haushalte'}{suf_de}" if l == "de"
                 else f"Appropriate/Inappropriate Economic Growth and {'Unemployment' if ind == 'alo' else 'Public Finances'}{suf_en}")
            sub = ("Differenz wY \u2212 wY* (links) vs. " + ("Arbeitslosenentwicklung (rechts)" if ind == "alo" else "Finanzierungssaldo des Staates (rechts)") if l == "de"
                   else "Differential wY \u2212 wY* (left) vs. " + ("unemployment change (right)" if ind == "alo" else "government balance (right)"))
            finish_chart(fig, prefix if l == "de" else f"{prefix}_en", t, sub, src(l),
                         "Prozentpunkte (links)" if l == "de" else "Percentage points (left)", [-3.0, 3.0],
                         ("% gg. Vj. (rechts)" if ind == "alo" else "% des nom. BIP (rechts)") if l == "de" else ("% YoY (right)" if ind == "alo" else "% of nom. GDP (right)"),
                         [-lim, lim], dt=1 if st else 2)

    # 8 & 9. Notwendiges Wirtschaftswachstum
    alq_m = s["alq_m"]
    latest_ym = str(alq_m.index.max())
    for mode, prefix in (("year", "08_notwendig_jahr"), ("quarter", "09_notwendig_quartal")):
        if mode == "year":
            jk = f"{latest_ym[:4]}-01"
            ref = jk if jk in alq_m.index else str(alq_m.index.min())
        else:
            qe = [ym for ym in alq_m.index if ym[5:7] in ("03", "06", "09", "12")]
            ref = str(qe[-1]) if qe else latest_ym
        u0, wm = float(alq_m.loc[ref]), s["wpot_5m"]
        path = np.linspace(u0, 3.0, max(2, min(10, int(math.ceil((u0 - 3.0) / 0.45)))) + 1)
        req = [wm + max(0.0, (u - 3.0) / 0.45) for u in path]
        m_de = {"01": "Jan", "02": "Feb", "03": "Mrz", "04": "Apr", "05": "Mai", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dez"}[ref[5:7]]
        m_en = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}[ref[5:7]]
        for l in ("de", "en"):
            ml = f"{m_de if l == 'de' else m_en} {ref[2:4]}"
            xl = [f"{ml} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == 0 else (f"{'Ziel' if l == 'de' else 'Target'} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == len(path) - 1 else f"{'ALQ' if l == 'de' else 'UR'} {u:.1f}%") for i, u in enumerate(path)]
            tv = [f"{v:.1f} %".replace(".", ",") if l == "de" else f"{v:.1f}%" for v in req]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xl, y=req, mode="lines+markers+text", line=dict(color=C_ORANGE, width=3.0), marker=dict(size=8, color=C_ORANGE),
                                     name="Notwendiges reales BIP-Wachstum (%)" if l == "de" else "Necessary real GDP growth (%)",
                                     text=tv, textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(req))]))
            fig.add_hline(y=wm, line_dash="dash", line_color=C_NAVY, annotation_position="bottom left",
                          annotation_text=f"Potenzialwachstum wY* (5J-\u00d8 {s['wpot_5s']}): {wm:.1f} %".replace(".", ",") if l == "de" else f"Potential growth wY* (5Y avg {s['wpot_5s']}): {wm:.1f}%")
            t = (f"Notwendiges Wirtschaftswachstum ({'Jahresbetrachtung ' + ref[:4] if mode == 'year' else 'Quartalsstand ' + ml})" if l == "de"
                 else f"Necessary Economic Growth ({'Annual View ' + ref[:4] if mode == 'year' else 'Quarterly Update ' + ml})")
            sub = "Erforderliche reale BIP-Zuwachsrate bis zur Vollbeschäftigungsgrenze (ALQ \u2264 3,0 %)" if l == "de" else "Required real GDP growth down to full employment (UR \u2264 3.0%)"
            finish_chart(fig, prefix if l == "de" else f"{prefix}_en", t, sub, src(l), "% gg. Vj." if l == "de" else "% YoY", [0.0, math.ceil(max(req) + 1.5)], dt=1)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_all_charts(build_datasets(load_macro()))
    print("Alle 9 Produktionspotenzial-Grafiken (DE & EN) erfolgreich erstellt.")


if __name__ == "__main__":
    main()

