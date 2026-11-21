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
