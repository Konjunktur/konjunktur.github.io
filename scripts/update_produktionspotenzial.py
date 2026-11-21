#!/usr/bin/env python3
# Update-Skript: Produktionspotenzial nach Claus Koehler (DE & EN, PNG & HTML)

import io, math, os, re
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

OUT_DIR = Path("static/produktionspotenzial")
API_URL = "https://" + "www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
LT, GT = chr(60), chr(62)
SVR_Y = [(1992, 1993), (2001, 2003), (2008, 2009), (2020, 2020), (2022, 2025)]
SVR_Q = [("1992-01", "1993-04"), ("2001-01", "2003-02"), ("2008-02", "2009-02"), ("2020-01", "2020-02"), ("2022-04", "2025-04")]
C_NAVY, C_ORANGE, C_GREEN, C_SLATE, C_GRID = "#1E3A8A", "#D97706", "#059669", "#475569", "#E2E8F0"
C_SVR, C_BIP = "rgba(148,163,184,0.30)", "rgba(96,165,250,0.36)"


def _f(v) -> float:
    s = "" if v is None else str(v).strip().replace("\xa0", "").replace(" ", "")
    if s in ("", ".", "-", "...", "x", "/", "nan", "NaN", "None"):
        return np.nan
    try:
        return float(s.replace(".", "").replace(",", ".") if ("," in s and "." in s) else s.replace(",", "."))
    except ValueError:
        return np.nan


def fetch_table(tid: str, start: int = 1991) -> pd.DataFrame:
    u = os.environ.get("DESTATIS_USER", "").strip()
    p = os.environ.get("DESTATIS_PASS", "").strip()
    if not u or not p:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    params = {"username": u, "password": p, "name": tid, "area": "all", "compress": "false",
              "transpose": "false", "startyear": str(start), "endyear": str(datetime.now().year + 1),
              "language": "de", "format": "ffcsv"}
    r = requests.get(API_URL, params=params, headers={"username": u, "password": p}, timeout=90)
    r.raise_for_status()
    lines = r.content.decode("utf-8-sig", errors="replace").splitlines()
    idx = next((i for i, l in enumerate(lines) if l.startswith(("statistics_code;", "Statistik_Code;"))), 0)
    df = pd.read_csv(io.StringIO("\n".join(lines[idx:])), sep=";", dtype=str, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    return df


def _col(df: pd.DataFrame, names: list) -> str:
    low = {c.lower(): c for c in df.columns}
    return next((low[n.lower()] for n in names if n.lower() in low), "")


def _extract(df: pd.DataFrame, inc: list, exc: list, lo: float, hi: float, yearly: bool) -> pd.Series:
    df = df.copy()
    for c in df.columns:
        if ("variable_code" in c.lower() or "merkmal" in c.lower()) and (df[c].fillna("") == "WERTORG").any():
            df = df[df[c].fillna("") == "WERTORG"]
    ct, cc, cv, cl = _col(df, ["time", "Zeit"]), _col(df, ["time_code", "Zeit_Code"]), _col(df, ["value", "Wert"]), _col(df, ["value_variable_label", "Wert_Merkmal_Label"])
    if yearly and cc and (df[cc].fillna("") == "JAHR").any():
        df = df[df[cc].fillna("") == "JAHR"]
    if cl and inc:
        lbl = df[cl].fillna("").str.lower()
        m = pd.Series(True, index=df.index)
        for k in inc:
            m &= lbl.str.contains(k.lower(), regex=False)
        for k in exc:
            m &= ~lbl.str.contains(k.lower(), regex=False)
        df = df[m]
    for c in df.columns:
        if c.endswith("_code") and c not in (cc, "statistics_code", "value_variable_code"):
            v = df[c].fillna("")
            if (v == "INSGESAMT").any():
                df = df[v == "INSGESAMT"]
            elif (v == "WZ08-00").any():
                df = df[v == "WZ08-00"]
    qmap, out = {"QUART1": 1, "QUART2": 2, "QUART3": 3, "QUART4": 4}, {}
    for _, r in df.iterrows():
        ys, qs, val = str(r[ct]).strip(), str(r[cc]).strip() if cc else "", _f(r[cv])
        if np.isnan(val) or not (lo <= val <= hi):
            continue
        if yearly and re.match(r"^\d{4}$", ys):
            out[int(ys)] = val
        elif not yearly and ys.isdigit() and qs in qmap:
            out[f"{int(ys):04d}-0{qmap[qs]}"] = val
    s = pd.Series(out, dtype=float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _q2y(sq: pd.Series, agg: str = "sum") -> pd.Series:
    if len(sq) == 0:
        return pd.Series(dtype=float)
    g = pd.DataFrame({"yr": [int(k[:4]) for k in sq.index], "v": sq.values}).groupby("yr")["v"]
    return (g.sum() if agg == "sum" else g.mean())[g.count() == 4].sort_index()

#!/usr/bin/env python3
# Update-Skript: Produktionspotenzial nach Claus Koehler (DE & EN, PNG & HTML)

import io, math, os, re
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

OUT_DIR = Path("static/produktionspotenzial")
API_URL = "https://" + "www-genesis.destatis.de/genesisWS/rest/2020/data/tablefile"
LT, GT = chr(60), chr(62)
SVR_Y = [(1992, 1993), (2001, 2003), (2008, 2009), (2020, 2020), (2022, 2025)]
SVR_Q = [("1992-01", "1993-04"), ("2001-01", "2003-02"), ("2008-02", "2009-02"), ("2020-01", "2020-02"), ("2022-04", "2025-04")]
C_NAVY, C_ORANGE, C_GREEN, C_SLATE, C_GRID = "#1E3A8A", "#D97706", "#059669", "#475569", "#E2E8F0"
C_SVR, C_BIP = "rgba(148,163,184,0.30)", "rgba(96,165,250,0.36)"


def _f(v) -> float:
    s = "" if v is None else str(v).strip().replace("\xa0", "").replace(" ", "")
    if s in ("", ".", "-", "...", "x", "/", "nan", "NaN", "None"):
        return np.nan
    try:
        return float(s.replace(".", "").replace(",", ".") if ("," in s and "." in s) else s.replace(",", "."))
    except ValueError:
        return np.nan


def fetch_table(tid: str, start: int = 1991) -> pd.DataFrame:
    u = os.environ.get("DESTATIS_USER", "").strip()
    p = os.environ.get("DESTATIS_PASS", "").strip()
    if not u or not p:
        raise RuntimeError("DESTATIS_USER oder DESTATIS_PASS fehlt.")
    params = {"username": u, "password": p, "name": tid, "area": "all", "compress": "false",
              "transpose": "false", "startyear": str(start), "endyear": str(datetime.now().year + 1),
              "language": "de", "format": "ffcsv"}
    r = requests.get(API_URL, params=params, headers={"username": u, "password": p}, timeout=90)
    r.raise_for_status()
    lines = r.content.decode("utf-8-sig", errors="replace").splitlines()
    idx = next((i for i, l in enumerate(lines) if l.startswith(("statistics_code;", "Statistik_Code;"))), 0)
    df = pd.read_csv(io.StringIO("\n".join(lines[idx:])), sep=";", dtype=str, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    return df


def _col(df: pd.DataFrame, names: list) -> str:
    low = {c.lower(): c for c in df.columns}
    return next((low[n.lower()] for n in names if n.lower() in low), "")


def _extract(df: pd.DataFrame, inc: list, exc: list, lo: float, hi: float, yearly: bool) -> pd.Series:
    df = df.copy()
    for c in df.columns:
        if ("variable_code" in c.lower() or "merkmal" in c.lower()) and (df[c].fillna("") == "WERTORG").any():
            df = df[df[c].fillna("") == "WERTORG"]
    ct, cc, cv, cl = _col(df, ["time", "Zeit"]), _col(df, ["time_code", "Zeit_Code"]), _col(df, ["value", "Wert"]), _col(df, ["value_variable_label", "Wert_Merkmal_Label"])
    if yearly and cc and (df[cc].fillna("") == "JAHR").any():
        df = df[df[cc].fillna("") == "JAHR"]
    if cl and inc:
        lbl = df[cl].fillna("").str.lower()
        m = pd.Series(True, index=df.index)
        for k in inc:
            m &= lbl.str.contains(k.lower(), regex=False)
        for k in exc:
            m &= ~lbl.str.contains(k.lower(), regex=False)
        df = df[m]
    for c in df.columns:
        if c.endswith("_code") and c not in (cc, "statistics_code", "value_variable_code"):
            v = df[c].fillna("")
            if (v == "INSGESAMT").any():
                df = df[v == "INSGESAMT"]
            elif (v == "WZ08-00").any():
                df = df[v == "WZ08-00"]
    qmap, out = {"QUART1": 1, "QUART2": 2, "QUART3": 3, "QUART4": 4}, {}
    for _, r in df.iterrows():
        ys, qs, val = str(r[ct]).strip(), str(r[cc]).strip() if cc else "", _f(r[cv])
        if np.isnan(val) or not (lo <= val <= hi):
            continue
        if yearly and re.match(r"^\d{4}$", ys):
            out[int(ys)] = val
        elif not yearly and ys.isdigit() and qs in qmap:
            out[f"{int(ys):04d}-0{qmap[qs]}"] = val
    s = pd.Series(out, dtype=float).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _q2y(sq: pd.Series, agg: str = "sum") -> pd.Series:
    if len(sq) == 0:
        return pd.Series(dtype=float)
    g = pd.DataFrame({"yr": [int(k[:4]) for k in sq.index], "v": sq.values}).groupby("yr")["v"]
    return (g.sum() if agg == "sum" else g.mean())[g.count() == 4].sort_index()

def _shade(fig: go.Figure, keys: list, wy_y: pd.Series, wy_q: pd.Series, l: str):
    svr_i = [i for i, (k, v) in enumerate(keys) if (any(a <= int(v) <= b for a, b in SVR_Y) if k == "Y" else any(a <= str(v) <= b for a, b in SVR_Q))]
    bip_i = [i for i, (k, v) in enumerate(keys) if (wy_y.get(int(v), 1) if k == "Y" else wy_q.get(str(v), 1)) < 0]
    for col, nm, idxs in (
        (C_SVR, "Rezessionsphasen (SVR/BBK)" if l == "de" else "Recession phases (SVR/BBK)", svr_i),
        (C_BIP, "Reales BIP < 0 % gg. Vj." if l == "de" else "Real GDP < 0% YoY", bip_i),
    ):
        s = tuple(sorted(set(idxs)))
        if s:
            st = pr = next(iter(s))
            for i in s[1:] + (-99,):
                if i == pr + 1:
                    pr = i
                else:
                    fig.add_vrect(x0=st - 0.5, x1=pr + 0.5, fillcolor=col, line_width=0, layer="below")
                    st = pr = i
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, symbol="square", color=col), name=nm))


def _save(fig: go.Figure, stem: str, title: str, sub: str, src: str, y1: str, r1=None, y2=None, r2=None, dt=2):
    t_html = f"{LT}b{GT}{title}{LT}/b{GT}{LT}br{GT}{LT}span style='font-size:12px;color:#475569'{GT}{sub}{LT}/span{GT}"
    fig.update_layout(
        title=dict(text=t_html, x=0.01, y=0.97, font=dict(size=16)),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, x=0.0, bgcolor="rgba(255,255,255,0.85)"),
        margin=dict(l=58, r=58 if y2 else 26, t=122, b=66),
        plot_bgcolor="#FFF", paper_bgcolor="#FFF", hovermode="x unified", height=490,
    )
    fig.update_xaxes(type="category", showgrid=False, linecolor="#CBD5E1", tickangle=-45, nticks=max(10, 38 // dt))
    fig.update_yaxes(title_text=y1, gridcolor=C_GRID, zeroline=True, zerolinecolor="#94A3B8", range=r1, secondary_y=False if y2 else None)
    if y2:
        fig.update_yaxes(title_text=y2, showgrid=False, zeroline=False, range=r2, secondary_y=True)
    fig.add_annotation(text=src, xref="paper", yref="paper", x=0.0, y=-0.16, showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color="#64748B"))
    css = f"{LT}style{GT}html,body{{margin:0;padding:0;overflow:hidden;width:100%;height:100%;background:#fff}}.plotly-graph-div{{width:100%!important;height:100%!important}}{LT}/style{GT}"
    html = fig.to_html(include_plotlyjs="cdn", full_html=True, config={"displayModeBar": False, "responsive": True})
    (OUT_DIR / f"{stem}.html").write_text(html.replace(f"{LT}/head{GT}", f"{css}{LT}/head{GT}"), encoding="utf-8")
    try:
        fig.write_image(str(OUT_DIR / f"{stem}.png"), width=1100, height=520, scale=2)
    except Exception as e:
        print(f"[WARN] PNG {stem}: {e}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s, ex = build_data(), f"{LT}extra{GT}{LT}/extra{GT}"
    src = lambda l: f"Quelle: Statistisches Bundesamt | Stand: {s['de']}" if l == "de" else f"Source: Federal Statistical Office | As of: {s['en']}"

    for l in ("de", "en"):
        fig = go.Figure()
        _shade(fig, s["kl"], s["wy_y"], s["wy_q"], l)
        fig.add_trace(go.Scatter(x=s["ll"], y=s["pl"], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                 name="Produktionspotenzial (Mrd. €)" if l == "de" else "Potential output (EUR bn)",
                                 hovertemplate=f"%{{x}}: %{{y:,.1f}}{ex}"))
        _save(fig, "01_potenzial_lang" if l == "de" else "01_potenzial_lang_en",
              "Entwicklung des Produktionspotenzials" if l == "de" else "Development of Potential Output",
              "Preisbereinigtes Produktionspotenzial in Mrd. € | Jahreswerte ab 1991, danach Quartalswerte (4-Quartals-Summe)" if l == "de"
              else "Price-adjusted potential output in EUR bn | Annual values from 1991, followed by quarterly values (4-quarter sum)",
              src(l), "Mrd. €" if l == "de" else "EUR bn")

    for st, pfx, lk, kk, vk in ((False, "02_auslastung_lang", "ll", "kl", "ul"), (True, "05_auslastung_kurz", "ls", "ks", "us")):
        rng = [math.floor(min(s[vk]) - 1.0), math.ceil(max(s[vk]) + 0.5)]
        for l in ("de", "en"):
            fig = go.Figure()
            _shade(fig, s[kk], s["wy_y"], s["wy_q"], l)
            fig.add_trace(go.Scatter(x=s[lk], y=s[vk], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                     name="Auslastung (%)" if l == "de" else "Utilization (%)", hovertemplate=f"%{{x}}: %{{y:.1f}} %{ex}"))
            if not st:
                fig.add_hline(y=s["m91"], line_dash="dash", line_color=C_SLATE,
                              annotation_text=f"Mittelwert 1991\u20132019: {s['m91']:.1f} %".replace(".", ",") if l == "de" else f"Mean 1991\u20132019: {s['m91']:.1f}%")
            _save(fig, pfx if l == "de" else f"{pfx}_en",
                  ("Auslastung des Produktionspotenzials" + (" (ab 2019)" if st else "")) if l == "de"
                  else ("Potential Output Utilization" + (" (from 2019)" if st else "")),
                  f"Reales BIP in % des Produktionspotenzials | Jahreswerte ab {'2019' if st else '1991'}, danach Quartalswerte" if l == "de"
                  else f"Real GDP as % of potential output | Annual values from {'2019' if st else '1991'}, followed by quarterly values",
                  src(l), "%", rng, dt=1 if st else 2)

    dual_cfg = (
        ("alo", False, "03_angemessen_alo_lang", "lgl", "kgl", "dgl", "agl", 30.0, C_ORANGE),
        ("staat", False, "04_angemessen_staat_lang", "lgl", "kgl", "dgl", "fgl", 12.0, C_GREEN),
        ("alo", True, "06_angemessen_alo_kurz", "ls", "ks", "ds", "as", 20.0, C_ORANGE),
        ("staat", True, "07_angemessen_staat_kurz", "ls", "ks", "ds", "fs", 12.0, C_GREEN),
    )
    for ind, st, pfx, lk, kk, dk, bk, lim, col in dual_cfg:
        va = [abs(v) for v in s[bk] if not np.isnan(v)]
        if va and max(va) > lim:
            lim = math.ceil(max(va) / 5.0) * 5.0
        for l in ("de", "en"):
            rs = [{"secondary_y": True}]
            fig = make_subplots(specs=[rs])
            _shade(fig, s[kk], s["wy_y"], s["wy_q"], l)
            b_nm = ("Zuwachsrate Arbeitslose (% gg. Vj., rechts)" if l == "de" else "Unemployment growth (% YoY, right)") if ind == "alo" \
                else ("Finanzierungssaldo des Staates (% des nom. BIP, rechts)" if l == "de" else "Gov. net lending/borrowing (% of nom. GDP, right)")
            fig.add_trace(go.Bar(x=s[lk], y=s[bk], name=b_nm, marker=dict(color=col, opacity=0.78), hovertemplate=f"%{{x}}: %{{y:+.1f}} %{ex}"), secondary_y=True)
            fig.add_trace(go.Scatter(x=s[lk], y=s[dk], mode="lines+markers", line=dict(color=C_NAVY, width=2.8),
                                     name="Wachstumsdifferenz wY \u2212 wY* (Ppkt., links)" if l == "de" else "Growth differential wY \u2212 wY* (pp, left)",
                                     hovertemplate=f"%{{x}}: %{{y:+.2f}}{ex}"), secondary_y=False)
            _save(fig, pfx if l == "de" else f"{pfx}_en",
                  (f"Angemessenes/nicht angemessenes Wirtschaftswachstum und {'Arbeitslosigkeit' if ind == 'alo' else 'öffentliche Haushalte'}{' (ab 2019)' if st else ''}" if l == "de"
                   else f"Appropriate/Inappropriate Growth and {'Unemployment' if ind == 'alo' else 'Public Finances'}{' (from 2019)' if st else ''}"),
                  ("Differenz wY \u2212 wY* (links) vs. " + ("Arbeitslosenentwicklung (rechts)" if ind == "alo" else "Finanzierungssaldo des Staates (rechts)") if l == "de"
                   else "Differential wY \u2212 wY* (left) vs. " + ("unemployment change (right)" if ind == "alo" else "government balance (right)")),
                  src(l), "Prozentpunkte (links)" if l == "de" else "Percentage points (left)", [-3.0, 3.0],
                  ("% gg. Vj. (rechts)" if ind == "alo" else "% des nom. BIP (rechts)") if l == "de" else ("% YoY (right)" if ind == "alo" else "% of nom. GDP (right)"),
                  [-lim, lim], dt=1 if st else 2)

    alq_m, lym = s["alq_m"], str(s["alq_m"].index.max())
    for mode, pfx in (("year", "08_notwendig_jahr"), ("quarter", "09_notwendig_quartal")):
        q_ends = [ym for ym in alq_m.index if ym[5:7] in ("03", "06", "09", "12")]
        last_qe = tuple(q_ends)[len(q_ends) - 1] if q_ends else lym
        ref = (f"{lym[:4]}-01" if f"{lym[:4]}-01" in alq_m.index else str(alq_m.index.min())) if mode == "year" else str(last_qe)
        u0, wm = float(alq_m.loc[ref]), s["wp5m"]
        path = np.linspace(u0, 3.0, max(2, min(10, int(math.ceil((u0 - 3.0) / 0.45)))) + 1)
        req = [wm + max(0.0, (u - 3.0) / 0.45) for u in path]
        mde = {"01": "Jan", "02": "Feb", "03": "Mrz", "04": "Apr", "05": "Mai", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dez"}[ref[5:7]]
        men = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}[ref[5:7]]
        for l in ("de", "en"):
            ml = f"{mde if l == 'de' else men} {ref[2:4]}"
            xl = [f"{ml} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == 0 else (f"{'Ziel' if l == 'de' else 'Target'} ({'ALQ' if l == 'de' else 'UR'} {u:.1f}%)" if i == len(path) - 1 else f"{'ALQ' if l == 'de' else 'UR'} {u:.1f}%") for i, u in enumerate(path)]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xl, y=req, mode="lines+markers+text", line=dict(color=C_ORANGE, width=3.0), marker=dict(size=8, color=C_ORANGE),
                                     name="Notwendiges Wachstum (%)" if l == "de" else "Necessary growth (%)",
                                     text=[f"{v:.1f} %".replace(".", ",") if l == "de" else f"{v:.1f}%" for v in req],
                                     textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(req))]))
            fig.add_hline(y=wm, line_dash="dash", line_color=C_NAVY, annotation_position="bottom left",
                          annotation_text=f"Potenzialwachstum wY* (5J-\u00d8 {s['wp5s']}): {wm:.1f} %".replace(".", ",") if l == "de" else f"Potential growth wY* (5Y avg {s['wp5s']}): {wm:.1f}%")
            _save(fig, pfx if l == "de" else f"{pfx}_en",
                  f"Notwendiges Wirtschaftswachstum ({'Jahresbetrachtung ' + ref[:4] if mode == 'year' else 'Quartalsstand ' + ml})" if l == "de"
                  else f"Necessary Economic Growth ({'Annual View ' + ref[:4] if mode == 'year' else 'Quarterly Update ' + ml})",
                  "Erforderliche reale BIP-Zuwachsrate bis zur Vollbeschäftigungsgrenze (ALQ \u2264 3,0 %)" if l == "de"
                  else "Required real GDP growth down to full employment (UR \u2264 3.0%)",
                  src(l), "% gg. Vj." if l == "de" else "% YoY", [0.0, math.ceil(max(req) + 1.5)], dt=1)

    print("Alle 9 Produktionspotenzial-Grafiken (DE & EN) erfolgreich erstellt.")


if __name__ == "__main__":
    main()
