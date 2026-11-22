#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (DE & EN, .png & .html) fuer die Rubrik:
"Produktionspotenzial, Auslastung des Produktionspotenzials, angemessenes/nicht angemessenes Wirtschaftswachstum, notwendiges Wirtschaftswachstum"
Methode: Claus Koehler / Thorsten Hild
Datenbasis: Statistisches Bundesamt (Destatis GENESIS-Online: 81000-0001, 81000-0002,
            81000-0011, 81000-0012, 81000-0031, 13211-0002)
"""

import os
import re
import io
import csv
import json
import time
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import plotly.graph_objects as go
from plotly.subplots import make_subplots


G_BASE = "https://www-genesis.destatis.de/genesisWS/rest/2020/data"
D_USER = os.environ.get("DESTATIS_USER", "").strip()
D_PASS = os.environ.get("DESTATIS_PASS", "").strip()

OUT_DIR = "static/produktionspotenzial"

SVR_PHASES = [
    ("1992-Q1", "1993-Q2"),
    ("2001-Q1", "2003-Q2"),
    ("2008-Q2", "2009-Q2"),
    ("2020-Q1", "2020-Q2"),
    ("2022-Q4", "2025-Q4"),
]

ROMAN_Q = {"Q1": "I", "Q2": "II", "Q3": "III", "Q4": "IV"}

TXT = {
    "de": {
        "sfx": "",
        "comma": True,
        "date_fmt": "%d.%m.%Y",
        "m": ["Jan", "Feb", "Mrz", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        "src": "Quelle: Statistisches Bundesamt | Stand: ",
        "leg_svr": "Rezession/Schwäche (SVR/BBK)",
        "leg_bip": "Reales BIP < 0 % gg. Vj.",
        "c1_t": "Produktionspotenzial in Deutschland",
        "c1_s": "Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach Quartalswerte, in Mrd. €",
        "c1_l": ["Produktionspotenzial (Mrd. €)"],
        "c2_t": "Auslastung des Produktionspotenzials",
        "c2_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte ab 1991 + aktuelle Quartale)",
        "c2_l": ["Auslastung des Produktionspotenzials (%)", "Mittelwert 1991–2019"],
        "c3_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "c3_s": "Links: Zuwachsrate reales BIP − Potenzial (Ppkt.) | Rechts: Arbeitslose gg. Vj. (%)",
        "c3_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c4_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "c4_s": "Links: Zuwachsrate reales BIP − Potenzial (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "c4_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c5_t": "Auslastung des Produktionspotenzials",
        "c5_s": "Reales BIP in % des Produktionspotenzials (Jahreswerte ab 2019 und aktuelle Quartale)",
        "c5_l": ["Reales BIP in % des Produktionspotenzials"],
        "c6_t": "Angemessenes/nicht angemessenes Wachstum und Arbeitslosigkeit",
        "c6_s": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Arbeitslose gg. Vj. (%)",
        "c6_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Zuwachsrate Arbeitslose (%, rechts)"],
        "c7_t": "Angemessenes/nicht angemessenes Wachstum und Öffentliche Haushalte",
        "c7_s": "Links: Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt.) | Rechts: Finanzierungssaldo (% nom. BIP)",
        "c7_l": ["Angemessenes (+) / nicht angemessenes (−) Wachstum (Ppkt., links)", "Finanzierungssaldo des Staates (% nom. BIP, rechts)"],
        "c8_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Jahresbasis)",
        "c8_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø) = {wy} %",
        "c9_t": "Notwendiges Wirtschaftswachstum zum Abbau der Arbeitslosigkeit (Quartal)",
        "c9_s": "Ausgangspunkt {start_lbl} (ALQ {alq0} %) | Abbau um 1 Ppkt./Jahr bis ≤ 3,0 % | wY* (5J-Ø) = {wy} %",
        "cn_l": ["Arbeitslosenquote (%)", "Notwendiges Wirtschaftswachstum (%)"],
    },
    "en": {
        "sfx": "_en",
        "comma": False,
        "date_fmt": "%Y-%m-%d",
        "m": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "src": "Source: Federal Statistical Office | As of: ",
        "leg_svr": "Recession/Weakness (GCEE/BBK)",
        "leg_bip": "Real GDP < 0% YoY",
        "c1_t": "Potential Output in Germany",
        "c1_s": "Annual values from 1991 up to the last completed year, followed by quarterly values, in EUR bn",
        "c1_l": ["Potential output (EUR bn)"],
        "c2_t": "Capacity Utilization of Potential Output",
        "c2_s": "Real GDP as a percentage of potential output (annual values from 1991 + latest quarters)",
        "c2_l": ["Utilization of potential output (%)", "Average 1991–2019"],
        "c3_t": "Suitable/Unsuitable Economic Growth and Unemployment",
        "c3_s": "Left: Real GDP growth − potential growth (pp) | Right: Unemployed persons YoY (%)",
        "c3_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c4_t": "Suitable/Unsuitable Economic Growth and Public Finances",
        "c4_s": "Left: Real GDP growth − potential growth (pp) | Right: Government net lending/borrowing (% of nom. GDP)",
        "c4_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit/surplus (% of nom. GDP, right)"],
        "c5_t": "Utilization of Potential Output",
        "c5_s": "Real GDP as a percentage of potential output (annual values from 2019 and latest quarters)",
        "c5_l": ["Real GDP as a percentage of potential output"],
        "c6_t": "Suitable/Unsuitable GDP Growth and Unemployment",
        "c6_s": "Left: Suitable (+) / not suitable (−) real GDP growth (pp) | Right: Unemployed persons YoY (%)",
        "c6_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Number of unemployed persons, YoY (%, right)"],
        "c7_t": "Suitable/Unsuitable GDP Growth and Public Finances",
        "c7_s": "Left: Suitable (+) / not suitable (−) real GDP growth (pp) | Right: Government deficit (% of nom. GDP)",
        "c7_l": ["Suitable (+) / not suitable (−) real GDP growth (pp, left)", "Government deficit (% of nom. GDP, right)"],
        "c8_t": "Necessary Economic Growth to Reduce Unemployment (Annual Basis)",
        "c8_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y avg) = {wy}%",
        "c9_t": "Necessary Economic Growth to Reduce Unemployment (Quarterly Update)",
        "c9_s": "Starting point {start_lbl} (UR {alq0}%) | Reduction by 1 pp/year to ≤ 3.0% | wY* (5Y avg) = {wy}%",
        "cn_l": ["Unemployment rate (%)", "Necessary economic growth (%)"],
    },
}


def fmt_v(val, comma=True, dec=1):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.{dec}f}"
    return s.replace(".", ",") if comma else s


def _destatis_ffcsv(table, startyear="1991", extra=None):
    if not D_USER or not D_PASS:
        raise RuntimeError("DESTATIS_USER / DESTATIS_PASS fehlen in den Environment-Variablen.")

    headers = {
        "username": D_USER,
        "password": D_PASS,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "name": table,
        "area": "all",
        "compress": "false",
        "format": "ffcsv",
        "language": "de",
        "startyear": startyear,
    }
    if extra:
        data.update(extra)

    def _unpack(resp):
        if resp.content[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                cname = next(n for n in zf.namelist() if n.endswith(".csv"))
                return zf.read(cname).decode("utf-8", errors="replace")
        return resp.text

    raw = _unpack(
        requests.post(
            f"{G_BASE}/tablefile",
            headers=headers,
            data=data,
            timeout=90,
        )
    )
    if raw.lstrip().startswith("{"):
        rj = requests.post(
            f"{G_BASE}/tablefile",
            headers=headers,
            data={**data, "job": "true"},
            timeout=90,
        )
        st = str(json.loads(rj.text).get("Status", {}).get("Content", ""))
        match = re.search(r"([0-9A-Z\-]+_[0-9]+)", st)
        if not match:
            raise RuntimeError(
                f"Destatis Job-ID nicht gefunden ({table}): {st[:180]}"
            )

        job_id = match.group(1)
        raw = ""
        for _ in range(36):
            time.sleep(2.5)
            text = _unpack(
                requests.post(
                    f"{G_BASE}/resultfile",
                    headers=headers,
                    data={
                        "name": job_id,
                        "area": "all",
                        "compress": "false",
                        "language": "de",
                    },
                    timeout=90,
                )
            )
            if not text.lstrip().startswith("{"):
                raw = text
                break

        if not raw:
            raise RuntimeError(
                f"Destatis Job-Timeout ({table} / {job_id})"
            )

    rows = [
        row
        for row in csv.reader(
            io.StringIO(raw),
            delimiter=";",
            quotechar='"',
        )
        if len(row) >= 5
    ]
    if len(rows) < 3:
        return pd.DataFrame()

    header = [str(value).strip() for value in rows.pop(0)]
    df = pd.DataFrame(
        [
            row[:len(header)]
            for row in rows
            if len(row) >= len(header)
        ],
        columns=header,
    )

    column_map = {column.lower(): column for column in df.columns}
    time_col = column_map.get("time") or column_map.get("zeit")
    value_col = column_map.get("value") or column_map.get("wert")

    time_values = df[time_col].astype(str).str.strip()

    for column in df.columns:
        if column in (time_col, value_col) or "label" in column.lower():
            continue

        values = df[column].astype(str).str.strip()
        if values.str.match(r"^QUART0?[1-4]$", case=False).any():
            quarter = values.str.extract(r"([1-4])", expand=False)
            time_values = pd.Series(
                np.where(
                    quarter.notna(),
                    time_values + "-Q" + quarter.fillna(""),
                    time_values,
                ),
                index=df.index,
            )
            break

        if values.str.match(r"^MONAT0?(?:[1-9]|1[0-2])$", case=False).any():
            month = (
                values
                .str.extract(r"([0-9]+)", expand=False)
                .str.zfill(2)
            )
            time_values = pd.Series(
                np.where(
                    month.notna(),
                    time_values + "-" + month.fillna(""),
                    time_values,
                ),
                index=df.index,
            )
            break

    df["ZEIT"] = time_values
    df["NUM"] = pd.to_numeric(
        df[value_col].astype(str).str.replace(",", "."),
        errors="coerce",
    )
    return df.dropna(subset=["NUM"]).copy()


def _filter_series(
    df,
    req_codes,
    lbl_terms,
    z_regex,
    excl_terms=None,
    pick="max",
    allow_label_fallback=True,
):
    code_cols = [
        column
        for column in df.columns
        if column.endswith("_code")
        and column not in {"statistics_code", "time_code"}
    ]

    sub = pd.DataFrame()
    if req_codes and code_cols:
        code_sets = (
            df[code_cols]
            .fillna("")
            .astype(str)
            .apply(
                lambda row: {
                    value.strip().upper()
                    for value in row
                    if value.strip()
                },
                axis=1,
            )
        )
        sub = df[
            code_sets.apply(
                lambda codes: req_codes.issubset(codes)
            )
        ].copy()

    if sub.empty and lbl_terms and allow_label_fallback:
        label_cols = [
            column
            for column in df.columns
            if "label" in column.lower()
        ]
        label_text = (
            df[label_cols]
            .fillna("")
            .astype(str)
            .agg(" | ".join, axis=1)
            .str.lower()
        )
        mask = pd.Series(True, index=df.index)
        for term in lbl_terms:
            mask &= label_text.str.contains(term.lower(), regex=False)
        if excl_terms:
            for term in excl_terms:
                mask &= ~label_text.str.contains(term.lower(), regex=False)
        sub = df[mask].copy()

    sub = sub[
        sub["ZEIT"].astype(str).str.match(z_regex)
    ].copy()
    if sub.empty:
        return pd.Series(dtype=float)

    if pick == "max":
        series = sub.groupby("ZEIT")["NUM"].max()
    elif pick == "min":
        series = sub.groupby("ZEIT")["NUM"].min()
    else:
        series = (
            sub
            .drop_duplicates(subset=["ZEIT"], keep="first")
            .set_index("ZEIT")["NUM"]
        )

    result = series.sort_index()

    unit_cols = [
        column
        for column in sub.columns
        if "unit" in column.lower() or "einheit" in column.lower()
    ]
    if unit_cols:
        result.attrs["unit"] = " ".join(
            sub[unit_cols[0]].dropna().astype(str).unique()
        )

    return result


def _normalize_financing_balance(series):
    """Normiert den Finanzierungssaldo auf Mrd. EUR, falls Mill. EUR geliefert werden."""
    unit = str(series.attrs.get("unit", "")).lower()
    if "mill" in unit or "million" in unit or "mill." in unit:
        return series / 1000.0
    return series


def _scale_chain_index_to_base_year(chain_index, nominal_gdp):
    """Skaliert den Kettenindex auf das nominale BIP des Basisjahres 2020."""
    if chain_index.empty or nominal_gdp.empty or "2020" not in nominal_gdp.index:
        return pd.Series(dtype=float)

    base_gdp = float(nominal_gdp.loc["2020"])
    return base_gdp * chain_index / 100.0


def load_all_macro_data():
    df_bip_y = _destatis_ffcsv("81000-0001", "1991")
    df_bip_q = _destatis_ffcsv("81000-0002", "1991")

    bip_real_y = _filter_series(
        df_bip_y,
        {"WERTORG", "VGR014"},
        ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^\d{4}$",
        pick="max",
    )
    if bip_real_y.empty:
        bip_nom_y = _filter_series(
            df_bip_y,
            {"WERTORG", "VGR013"},
            ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
            r"^\d{4}$",
            pick="max",
        )
        bip_chain_y = _filter_series(
            df_bip_y,
            {"WERTORG", "VGRPKM"},
            ["originalwerte", "preisbereinigt", "verkettet"],
            r"^\d{4}$",
            pick="max",
        )
        bip_real_y = _scale_chain_index_to_base_year(
            bip_chain_y,
            bip_nom_y,
        )

    bip_nom_y = _filter_series(
        df_bip_y,
        {"WERTORG", "VGR013"},
        ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
        r"^\d{4}$",
        pick="max",
    )

    bip_real_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGR014"},
        ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )
    if bip_real_q.empty:
        bip_chain_q = _filter_series(
            df_bip_q,
            {"WERTORG", "VGRPKM"},
            ["originalwerte", "preisbereinigt", "verkettet"],
            r"^\d{4}-Q[1-4]$",
            pick="max",
        )
        bip_real_q = _scale_chain_index_to_base_year(
            bip_chain_q,
            bip_nom_y,
        )

    bip_nom_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGR013"},
        ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )

    bip_chain_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGRPKM"},
        ["originalwerte", "preisbereinigt", "verkettet"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )
    bip_chain_yoy = (bip_chain_q / bip_chain_q.shift(4) - 1.0) * 100.0

    df_et_y = _destatis_ffcsv("81000-0011", "1991")
    df_et_q = _destatis_ffcsv("81000-0012", "1991")

    et_y = _filter_series(
        df_et_y,
        {"WERTORG", "ERW060"},
        ["originalwerte", "erwerbstätige", "inland"],
        r"^\d{4}$",
        pick="max",
    )
    if et_y.empty:
        et_y = _filter_series(
            df_et_y,
            set(),
            ["originalwerte", "erwerbstätige", "inland"],
            r"^\d{4}$",
            pick="max",
        )

    et_q = _filter_series(
        df_et_q,
        {"WERTORG", "ERW060"},
        ["originalwerte", "erwerbstätige", "inland"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )
    if et_q.empty:
        et_q = _filter_series(
            df_et_q,
            set(),
            ["originalwerte", "erwerbstätige", "inland"],
            r"^\d{4}-Q[1-4]$",
            pick="max",
        )

    df_alo = _destatis_ffcsv("13211-0002", "1991")

    alo_m_raw = _filter_series(
        df_alo,
        {"ARB001"},
        ["arbeitslose"],
        r"^\d{4}-\d{2}$",
        excl_terms=["quote"],
        pick="max",
    )
    if alo_m_raw.empty:
        alo_m_raw = _filter_series(
            df_alo,
            set(),
            ["arbeitslose"],
            r"^\d{4}-\d{2}$",
            excl_terms=["quote"],
            pick="max",
        )
    alo_m = (
        alo_m_raw / 1000.0
        if not alo_m_raw.empty and alo_m_raw.median() > 50000
        else alo_m_raw
    )

    alq_m = _filter_series(
        df_alo,
        {"ALQ001"},
        ["arbeitslosenquote", "alle zivilen"],
        r"^\d{4}-\d{2}$",
        pick="min",
    )
    if alq_m.empty:
        alq_m = _filter_series(
            df_alo,
            set(),
            ["arbeitslosenquote", "alle zivilen"],
            r"^\d{4}-\d{2}$",
            pick="min",
        )
    if alq_m.empty:
        alq_m = _filter_series(
            df_alo,
            {"ALQ001"},
            ["arbeitslosenquote"],
            r"^\d{4}-\d{2}$",
            pick="min",
        )

    # Fallback: Arbeitslosenquote aus Arbeitslosen und zivilen Erwerbspersonen.
    if alq_m.empty and not alo_m.empty:
        labor_force = _filter_series(
            df_alo,
            {"ERW001"},
            ["zivile erwerbspersonen"],
            r"^\d{4}-\d{2}$",
            pick="max",
        )
        if labor_force.empty:
            labor_force = _filter_series(
                df_alo,
                set(),
                ["zivile erwerbspersonen"],
                r"^\d{4}-\d{2}$",
                pick="max",
            )

        common_months = alo_m.index.intersection(labor_force.index)
        if len(common_months):
            alq_m = (
                alo_m.loc[common_months]
                / labor_force.loc[common_months]
                * 100.0
            )

    alo_q = alo_m.groupby(
        lambda value: (
            f"{value[:4]}-Q"
            f"{(int(value[5:7]) - 1) // 3 + 1}"
        )
    ).mean()
    alo_y = alo_m.groupby(lambda value: value[:4]).mean()

    df_fin = _destatis_ffcsv("81000-0031", "1991")
    fin_y = _filter_series(
        df_fin,
        {"WERTORG"},
        ["originalwerte", "finanzierungssaldo", "gesamtstaat"],
        r"^\d{4}$",
        pick="first",
        allow_label_fallback=False,
    )
    fin_q = _filter_series(
        df_fin,
        {"WERTORG"},
        ["originalwerte", "finanzierungssaldo", "gesamtstaat"],
        r"^\d{4}-Q[1-4]$",
        pick="first",
        allow_label_fallback=False,
    )
    fin_y = _normalize_financing_balance(fin_y)
    fin_q = _normalize_financing_balance(fin_q)

    return {
        "bip_real_y": bip_real_y,
        "bip_nom_y": bip_nom_y,
        "bip_real_q": bip_real_q,
        "bip_nom_q": bip_nom_q,
        "bip_chain_yoy": bip_chain_yoy,
        "et_y": et_y,
        "et_q": et_q,
        "alo_m": alo_m,
        "alq_m": alq_m,
        "alo_q": alo_q,
        "alo_y": alo_y,
        "fin_y": fin_y,
        "fin_q": fin_q,
    }

def compute_koehler_tables(d):
    """Erzeugt Jahres- und Quartalstabellen nach der Claus-Köhler-Methode."""

    def as_series(key):
        value = d.get(key)
        if isinstance(value, pd.Series):
            result = value.copy()
        else:
            result = pd.Series(dtype=float)

        result = pd.to_numeric(result, errors="coerce").dropna()
        result.index = result.index.astype(str).str.strip()
        return result[~result.index.duplicated(keep="last")].sort_index()

    def annual_from_quarters(series, aggregation="mean"):
        if series.empty:
            return pd.Series(dtype=float)

        valid = series[
            series.index.str.match(r"^\d{4}-Q[1-4]$")
        ]
        if valid.empty:
            return pd.Series(dtype=float)

        grouped = valid.groupby(valid.index.str[:4])
        return grouped.sum() if aggregation == "sum" else grouped.mean()

    def annual_from_months(series):
        if series.empty:
            return pd.Series(dtype=float)

        valid = series[
            series.index.str.match(r"^\d{4}-\d{2}$")
        ]
        if valid.empty:
            return pd.Series(dtype=float)

        return valid.groupby(valid.index.str[:4]).mean()

    # Jahresreihen laden; fehlende Jahreswerte nach Möglichkeit aus den
    # verfügbaren Quartals- oder Monatsreihen ableiten.
    bip_real_y = as_series("bip_real_y")
    if bip_real_y.empty:
        bip_real_y = annual_from_quarters(
            as_series("bip_real_q"),
            aggregation="mean",
        )
        if not bip_real_y.empty:
            print(
                "[WARN] Jahresreihe reales BIP (81000-0001) ist leer; "
                "verwende Jahresmittel aus 81000-0002."
            )

    et_y = as_series("et_y")
    if et_y.empty:
        et_y = annual_from_quarters(
            as_series("et_q"),
            aggregation="mean",
        )
        if not et_y.empty:
            print(
                "[WARN] Jahresreihe Erwerbstätige Inland (81000-0011) "
                "ist leer; verwende Jahresmittel aus 81000-0012."
            )

    alo_y = as_series("alo_y")
    if alo_y.empty:
        alo_y = annual_from_months(as_series("alo_m"))
        if not alo_y.empty:
            print(
                "[WARN] Jahresreihe Arbeitslose (13211-0002) ist leer; "
                "verwende Monatsmittel aus 13211-0002."
            )
    if alo_y.empty:
        alo_y = annual_from_quarters(as_series("alo_q"))
        if not alo_y.empty:
            print(
                "[WARN] Jahresreihe Arbeitslose (13211-0002) ist leer; "
                "verwende Quartalsmittel aus 13211-0002."
            )

    missing_core = [
        label
        for label, series in [
            ("reales BIP 81000-0001 (Fallback: 81000-0002)", bip_real_y),
            ("Erwerbstätige Inland 81000-0011 (Fallback: 81000-0012)", et_y),
            ("Arbeitslose 13211-0002", alo_y),
        ]
        if series.empty
    ]
    if missing_core:
        raise ValueError(
            "Keine Jahres-Köhler-Tabelle möglich; folgende Reihen sind "
            "nach den Fallbacks leer: " + "; ".join(missing_core)
        )

    idx_y = (
        bip_real_y.index
        .intersection(et_y.index)
        .intersection(alo_y.index)
        .sort_values()
    )

    if idx_y.empty:
        raise ValueError(
            "Keine gemeinsamen Jahreswerte für die Köhler-Berechnung. "
            "Prüfe reales BIP (81000-0001/0002), Erwerbstätige Inland "
            "(81000-0011/0012) und Arbeitslose (13211-0002)."
        )

    df_y = pd.DataFrame(index=idx_y)
    df_y["bip_real"] = bip_real_y.loc[idx_y]
    df_y["et"] = et_y.loc[idx_y]
    df_y["alo"] = alo_y.loc[idx_y]
    df_y["prod"] = (df_y["bip_real"] * 1e6) / df_y["et"]
    df_y["pot"] = ((df_y["et"] + df_y["alo"]) * df_y["prod"]) / 1e6
    df_y["ausl"] = (df_y["bip_real"] / df_y["pot"]) * 100.0
    df_y["g_bip"] = (
        df_y["bip_real"] / df_y["bip_real"].shift(1) - 1.0
    ) * 100.0
    df_y["g_pot"] = (
        df_y["pot"] / df_y["pot"].shift(1) - 1.0
    ) * 100.0
    df_y["diff"] = df_y["g_bip"] - df_y["g_pot"]
    df_y["g_alo"] = (
        df_y["alo"] / df_y["alo"].shift(1) - 1.0
    ) * 100.0

    # Finanzierungssaldo und nominales BIP sind für diese Kennzahl nicht
    # Teil der Potenzialberechnung; fehlende Reihen bleiben daher NaN.
    fin_y = as_series("fin_y")
    if fin_y.empty:
        fin_y = annual_from_quarters(
            as_series("fin_q"),
            aggregation="sum",
        )
        if not fin_y.empty:
            print(
                "[WARN] Jahresreihe Finanzierungssaldo Gesamtstaat "
                "(81000-0031) ist leer; verwende Quartalssummen."
            )

    bip_nom_y = as_series("bip_nom_y")
    if bip_nom_y.empty:
        bip_nom_y = annual_from_quarters(
            as_series("bip_nom_q"),
            aggregation="mean",
        )
        if not bip_nom_y.empty:
            print(
                "[WARN] Jahresreihe nominales BIP (81000-0001) ist leer; "
                "verwende Quartalsmittel aus 81000-0002."
            )

    common_fin_y = (
        idx_y
        .intersection(fin_y.index)
        .intersection(bip_nom_y.index)
    )
    df_y["fin_pct"] = np.nan
    if len(common_fin_y):
        df_y.loc[common_fin_y, "fin_pct"] = (
            fin_y.loc[common_fin_y]
            / bip_nom_y.loc[common_fin_y]
        ) * 100.0

    # Quartalsreihen für dieselbe Köhler-Berechnung.
    bip_real_q = as_series("bip_real_q")
    et_q = as_series("et_q")
    alo_q = as_series("alo_q")

    # Falls die Quartals-Arbeitslosenreihe fehlt, aus den Monatswerten bilden.
    if alo_q.empty:
        alo_m = as_series("alo_m")
        if not alo_m.empty:
            alo_q = alo_m.groupby(
                lambda value: (
                    f"{value[:4]}-Q"
                    f"{(int(value[5:7]) - 1) // 3 + 1}"
                )
            ).mean()
            print(
                "[WARN] Quartalsreihe Arbeitslose ist leer; "
                "verwende Quartalsmittel aus den Monatswerten."
            )

    idx_q = (
        bip_real_q.index
        .intersection(et_q.index)
        .intersection(alo_q.index)
    )
    idx_q = idx_q[
        idx_q.str.match(r"^\d{4}-Q[1-4]$")
    ].sort_values()

    df_q = pd.DataFrame(index=idx_q)
    if not idx_q.empty:
        df_q["bip_real"] = bip_real_q.loc[idx_q]
        df_q["et"] = et_q.loc[idx_q]
        df_q["alo"] = alo_q.loc[idx_q]
        df_q["prod"] = (df_q["bip_real"] * 1e6) / df_q["et"]
        df_q["pot"] = ((df_q["et"] + df_q["alo"]) * df_q["prod"]) / 1e6
        df_q["ausl"] = (df_q["bip_real"] / df_q["pot"]) * 100.0
        df_q["g_bip"] = (
            df_q["bip_real"] / df_q["bip_real"].shift(4) - 1.0
        ) * 100.0
        df_q["g_pot"] = (
            df_q["pot"] / df_q["pot"].shift(4) - 1.0
        ) * 100.0
        df_q["diff"] = df_q["g_bip"] - df_q["g_pot"]
        df_q["g_alo"] = (
            df_q["alo"] / df_q["alo"].shift(4) - 1.0
        ) * 100.0

    fin_q = as_series("fin_q")
    bip_nom_q = as_series("bip_nom_q")
    common_fin_q = (
        idx_q
        .intersection(fin_q.index)
        .intersection(bip_nom_q.index)
    )
    df_q["fin_pct"] = np.nan
    if len(common_fin_q):
        df_q.loc[common_fin_q, "fin_pct"] = (
            fin_q.loc[common_fin_q]
            / bip_nom_q.loc[common_fin_q]
        ) * 100.0

    return (
        df_y[df_y.index >= "1991"].copy(),
        df_q[df_q.index >= "1991-Q1"].copy(),
    )


def build_hybrid_series(df_y, df_q, start_year="1991", add_gap=False):
    """Kombiniert abgeschlossene Jahreswerte mit verfügbaren Quartalswerten."""
    start_year = str(start_year)

    annual = df_y.copy()
    quarterly = df_q.copy()

    if not annual.empty:
        annual.index = annual.index.astype(str).str.strip()
    if not quarterly.empty:
        quarterly.index = quarterly.index.astype(str).str.strip()

    annual_years = sorted(
        year
        for year in annual.index
        if re.fullmatch(r"\d{4}", year) and year >= start_year
    )
    quarter_keys = sorted(
        quarter
        for quarter in quarterly.index
        if re.fullmatch(r"\d{4}-Q[1-4]", quarter)
    )

    q_counts = pd.Series(
        [quarter[:4] for quarter in quarter_keys],
        dtype="string",
    ).value_counts()

    completed_years = sorted(
        year
        for year, count in q_counts.items()
        if count == 4 and year in annual.index and year >= start_year
    )

    if not completed_years:
        if annual_years:
            completed_years = annual_years
            print(
                "[WARN] Keine vollständig mit Quartalen abgeglichenen "
                "Jahre gefunden; verwende die vorhandenen Jahreswerte aus "
                f"df_y: {', '.join(annual_years)}."
            )
        elif quarter_keys:
            print(
                "[WARN] Jahresreihe df_y ist leer oder enthält keine "
                "gültigen Jahreswerte; verwende die verfügbaren Quartale "
                "aus df_q."
            )
        else:
            missing = []
            if annual.empty:
                missing.append("df_y (Jahresreihen: reales BIP, Erwerbstätige, Arbeitslose)")
            if quarterly.empty:
                missing.append("df_q (Quartalsreihen: reales BIP, Erwerbstätige, Arbeitslose)")
            if not missing:
                missing.append(
                    "df_y und df_q enthalten keine gültigen Jahres- "
                    "oder Quartalsindizes"
                )
            message = (
                "build_hybrid_series kann keine Zeitreihe bilden. "
                "Leer/ungültig: " + "; ".join(missing)
            )
            print(f"[ERROR] {message}")
            raise ValueError(message)

    last_comp_y = completed_years[-1] if completed_years else None

    if last_comp_y is None:
        remaining_quarters = [
            quarter
            for quarter in quarter_keys
            if quarter[:4] >= start_year
        ]
    else:
        remaining_quarters = [
            quarter
            for quarter in quarter_keys
            if quarter[:4] > last_comp_y
        ]

    labels = []
    keys = []
    is_q = []

    for year in completed_years:
        labels.append(year)
        keys.append(("Y", year))
        is_q.append(False)

    if add_gap and remaining_quarters and completed_years:
        labels.append("")
        keys.append(("GAP", ""))
        is_q.append(False)

    for quarter in remaining_quarters:
        labels.append(
            f"{quarter[:4]} {ROMAN_Q[quarter[-2:]]}"
        )
        keys.append(("Q", quarter))
        is_q.append(True)

    if not keys:
        available_annual_columns = (
            ", ".join(map(str, annual.columns))
            if not annual.empty
            else "keine"
        )
        available_quarter_columns = (
            ", ".join(map(str, quarterly.columns))
            if not quarterly.empty
            else "keine"
        )
        message = (
            "build_hybrid_series fand trotz Prüfung keine verwendbaren "
            "Jahres- oder Quartalswerte. "
            f"df_y-Spalten: {available_annual_columns}; "
            f"df_q-Spalten: {available_quarter_columns}."
        )
        print(f"[ERROR] {message}")
        raise ValueError(message)

    def get_col(column):
        values = []
        for kind, key in keys:
            if kind == "Y":
                values.append(
                    float(annual.loc[key, column])
                    if column in annual.columns
                    else np.nan
                )
            elif kind == "Q":
                values.append(
                    float(quarterly.loc[key, column])
                    if column in quarterly.columns
                    else np.nan
                )
            else:
                values.append(np.nan)
        return values

    return labels, keys, is_q, get_col, completed_years

def get_recession_spans(keys, bip_chain_yoy):
    svr_spans = []
    bip_spans = []

    neg_q = {
        quarter
        for quarter, value in bip_chain_yoy.items()
        if not np.isnan(value) and value < 0
    }
    neg_y = {quarter[:4] for quarter in neg_q}

    def _in_svr(kind, key):
        if kind == "Q":
            return any(start <= key <= end for start, end in SVR_PHASES)
        if kind == "Y":
            return any(
                start[:4] <= key <= end[:4]
                for start, end in SVR_PHASES
            )
        return False

    def _in_bip(kind, key):
        if kind == "Q":
            return key in neg_q
        if kind == "Y":
            return key in neg_y
        return False

    def _collect(predicate):
        spans = []
        start = None

        for index, (kind, key) in enumerate(keys):
            if kind != "GAP" and predicate(kind, key):
                if start is None:
                    start = index
                end = index
            elif start is not None:
                spans.append((start - 0.5, end + 0.5))
                start = None

        if start is not None:
            spans.append((start - 0.5, len(keys) - 0.5))

        return spans

    return _collect(_in_svr), _collect(_in_bip)


def add_shades_mpl(ax, svr_spans, bip_spans, t):
    patches = []
    for x0, x1 in svr_spans:
        ax.axvspan(
            x0,
            x1,
            color="#CBD5E1",
            alpha=0.38,
            zorder=0,
        )
    if svr_spans:
        patches.append(
            mpatches.Patch(
                color="#CBD5E1",
                alpha=0.55,
                label=t["leg_svr"],
            )
        )

    for x0, x1 in bip_spans:
        ax.axvspan(
            x0,
            x1,
            color="#93C5FD",
            alpha=0.28,
            zorder=0,
        )
    if bip_spans:
        patches.append(
            mpatches.Patch(
                color="#93C5FD",
                alpha=0.45,
                label=t["leg_bip"],
            )
        )

    return patches


def add_shades_plotly(fp, svr_spans, bip_spans, t):
    shapes = []

    for x0, x1 in svr_spans:
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=x0,
                x1=x1,
                y0=0,
                y1=1,
                fillcolor="rgba(203,213,225,0.38)",
                line=dict(width=0),
                layer="below",
            )
        )

    for x0, x1 in bip_spans:
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=x0,
                x1=x1,
                y0=0,
                y1=1,
                fillcolor="rgba(147,197,253,0.28)",
                line=dict(width=0),
                layer="below",
            )
        )

    if shapes:
        fp.update_layout(shapes=shapes)

    if svr_spans:
        fp.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol="square",
                    color="rgba(203,213,225,0.85)",
                ),
                name=t["leg_svr"],
                hoverinfo="skip",
            )
        )

    if bip_spans:
        fp.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol="square",
                    color="rgba(147,197,253,0.75)",
                ),
                name=t["leg_bip"],
                hoverinfo="skip",
            )
        )


def _write_clean_html(fp, out_html):
    fp.write_html(
        out_html,
        include_plotlyjs="cdn",
        config={
            "displayModeBar": False,
            "responsive": True,
        },
    )
    with open(out_html, "r", encoding="utf-8") as file:
        html = file.read().replace(
            "<body>",
            '<body style="margin:0;padding:0;overflow:hidden;">',
        )
    with open(out_html, "w", encoding="utf-8") as file:
        file.write(html)


def compute_necessary_growth(d, df_y, completed_years, mode="year"):
    alq_s = d["alq_m"]
    if alq_s.empty:
        alq_vals = {}
        for ym in d["alo_m"].index:
            quarter_key = (
                f"{ym[:4]}-Q"
                f"{(int(ym[5:7]) - 1) // 3 + 1}"
            )
            if quarter_key in d["et_q"].index:
                unemployed = float(d["alo_m"].loc[ym])
                employed = float(d["et_q"].loc[quarter_key])
                alq_vals[ym] = round(
                    unemployed / (employed + unemployed) * 100.0,
                    1,
                )
        alq_s = pd.Series(alq_vals).sort_index()

    last_ym = alq_s.index[-1]
    cur_yr = int(last_ym[:4])

    if mode == "year":
        jan_ym = f"{cur_yr}-01"
        start_ym = jan_ym if jan_ym in alq_s.index else last_ym
    else:
        q_ends = [
            ym
            for ym in alq_s.index
            if ym[5:7] in ("03", "06", "09", "12")
        ]
        start_ym = q_ends[-1] if q_ends else last_ym

    alq0 = round(float(alq_s.loc[start_ym]), 1)

    # 5-Jahres-Mittel der Potenzialwachstumsraten der letzten
    # fünf abgeschlossenen Jahre.
    last5_y = completed_years[-5:]
    g_pot_5y = df_y.loc[last5_y, "g_pot"].dropna()
    wy_star = (
        round(float(g_pot_5y.mean()), 1)
        if not g_pot_5y.empty
        else 1.0
    )

    rows = [
        {
            "ym": start_ym,
            "yr": int(start_ym[:4]),
            "alq": alq0,
            "w_growth": np.nan,
        }
    ]
    prev_alq = alq0
    step_yr = int(start_ym[:4]) + 1

    while prev_alq > 3.0 and len(rows) <= 8:
        next_alq = round(max(prev_alq - 1.0, 0.0), 1)
        w_1_alq = (
            (1.0 + next_alq / 100.0)
            / (1.0 + prev_alq / 100.0)
            - 1.0
        ) * 100.0
        w_nec = round(wy_star - w_1_alq, 1)
        rows.append(
            {
                "ym": None,
                "yr": step_yr,
                "alq": next_alq,
                "w_growth": w_nec,
            }
        )
        prev_alq = next_alq
        step_yr += 1

    return start_ym, alq0, wy_star, rows

def save_dual_chart(
    lang,
    fname,
    title,
    sub,
    labels,
    line_vals,
    line_name,
    bar_vals,
    bar_name,
    bar_color,
    is_q,
    svr_spans,
    bip_spans,
    lmax,
    bmax,
    is_short=False,
):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))
    pp_unit = "Ppkt." if lang == "de" else "pp"

    fig, ax1 = plt.subplots(
        figsize=(8.2, 5.2),
        dpi=300,
        facecolor="white",
    )
    plt.subplots_adjust(left=0.09, right=0.90, top=0.77, bottom=0.20)
    ax2 = ax1.twinx()

    fig.suptitle(
        title,
        x=0.09,
        y=0.96,
        ha="left",
        fontsize=10.6,
        fontweight="bold",
        color="#0F172A",
    )
    fig.text(0.09, 0.915, sub, ha="left", fontsize=7.9, color="#334155")

    ax1.set_facecolor("#F8FAFC")
    shade_patches = add_shades_mpl(ax1, svr_spans, bip_spans, t)
    ax1.axhline(0, color="#64748B", lw=1.0, zorder=2)

    bars = ax2.bar(
        x,
        bar_vals,
        width=0.48 if is_short else 0.58,
        color=bar_color,
        alpha=0.82,
        label=bar_name,
        zorder=2,
    )
    line_array = np.array(line_vals, dtype=float)
    lines = ax1.plot(
        x,
        line_array,
        color="#1B3A6B",
        lw=2.3,
        marker="o" if is_short else None,
        markersize=4,
        label=line_name,
        zorder=4,
    )

    ax1.set_ylim(-lmax, lmax)
    ax2.set_ylim(-bmax, bmax)
    ax1.set_yticks(np.linspace(-lmax, lmax, 7))
    ax2.set_yticks(np.linspace(-bmax, bmax, 7))

    ax1.set_xticks(x)
    label_step = 1 if is_short else 2
    ax1.set_xticklabels(
        [
            label if (i % label_step == 0 or is_q[i]) else ""
            for i, label in enumerate(labels)
        ],
        rotation=90,
        fontsize=7.8,
        color="#475569",
    )
    ax1.tick_params(axis="y", labelsize=8.3, colors="#1B3A6B", length=0)
    ax2.tick_params(axis="y", labelsize=8.3, colors=bar_color, length=0)
    ax1.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)

    for axis in (ax1, ax2):
        for spine in ("top", "left", "right"):
            axis.spines[spine].set_visible(False)
    ax1.spines["bottom"].set_color("#94A3B8")

    handles = [lines[0], bars] + shade_patches
    ax1.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=2,
        frameon=False,
        fontsize=7.3,
    )
    fig.text(
        0.09,
        0.015,
        f"{t['src']}{now_s}",
        fontsize=6.8,
        color="#64748B",
    )
    fig.text(
        0.90,
        0.015,
        "T.H.",
        fontsize=7.8,
        color="#94A3B8",
        ha="right",
    )
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fig_plotly = make_subplots(specs=[[{"secondary_y": True}]])
    fig_plotly.add_trace(
        go.Bar(
            x=labels,
            y=[None if np.isnan(value) else round(value, 2) for value in bar_vals],
            customdata=[fmt_v(value, use_c, 1) for value in bar_vals],
            name=bar_name,
            marker_color=bar_color,
            opacity=0.82,
            hovertemplate=(
                f"{bar_name}: <b>%{{customdata}} %</b>"
                "<extra></extra>"
            ),
        ),
        secondary_y=True,
    )
    fig_plotly.add_trace(
        go.Scatter(
            x=labels,
            y=[
                None if np.isnan(value) else round(value, 2)
                for value in line_vals
            ],
            customdata=[fmt_v(value, use_c, 2) for value in line_vals],
            name=line_name,
            mode="lines+markers" if is_short else "lines",
            line=dict(color="#1B3A6B", width=2.4),
            connectgaps=False,
            hovertemplate=(
                f"{line_name}: <b>%{{customdata}} {pp_unit}</b>"
                "<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    add_shades_plotly(fig_plotly, svr_spans, bip_spans, t)
    fig_plotly.update_layout(
        title=dict(
            text=(
                f"<b>{title}</b><br>"
                f"<span style='font-size:11px;color:#334155;"
                f"font-weight:normal'>{sub}</span>"
            ),
            x=0.02,
            y=0.96,
            font=dict(size=13.5, color="#0F172A"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            yanchor="bottom",
            font=dict(size=9.5),
        ),
        margin=dict(l=48, r=48, t=122, b=76),
        height=470,
        annotations=[
            dict(
                text=f"{t['src']}{now_s}",
                x=0.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.5, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fig_plotly.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        tickfont=dict(size=9.8),
    )
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=[-lmax, lmax],
        tickvals=list(np.linspace(-lmax, lmax, 7)),
        zeroline=True,
        zerolinecolor="#64748B",
        secondary_y=False,
    )
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=[-bmax, bmax],
        tickvals=list(np.linspace(-bmax, bmax, 7)),
        showgrid=False,
        secondary_y=True,
    )
    _write_clean_html(
        fig_plotly,
        f"{OUT_DIR}/{fname}{t['sfx']}.html",
    )


def save_single_series_chart(
    lang,
    fname,
    title,
    sub,
    labels,
    series_list,
    is_q,
    unit_str,
    svr_spans,
    bip_spans,
    mean_val=None,
    mean_lbl=None,
    as_bar=False,
    is_short=False,
):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))

    fig, ax = plt.subplots(
        figsize=(8.2, 5.1),
        dpi=300,
        facecolor="white",
    )
    plt.subplots_adjust(left=0.09, right=0.96, top=0.77, bottom=0.20)
    fig.suptitle(
        title,
        x=0.09,
        y=0.96,
        ha="left",
        fontsize=10.8,
        fontweight="bold",
        color="#0F172A",
    )
    fig.text(0.09, 0.915, sub, ha="left", fontsize=7.9, color="#334155")
    ax.set_facecolor("#F8FAFC")
    shade_patches = add_shades_mpl(ax, svr_spans, bip_spans, t)

    all_values = []
    chart_handles = []

    for values, label, color in series_list:
        all_values.extend(
            value for value in values if not np.isnan(value)
        )
        if as_bar:
            bars = ax.bar(
                x,
                values,
                width=0.50,
                color=color,
                alpha=0.85,
                label=label,
                zorder=3,
            )
            chart_handles.append(bars)
            for x_value, value in zip(x, values):
                if not np.isnan(value):
                    ax.text(
                        x_value,
                        value + 0.12,
                        fmt_v(value, use_c, 1),
                        ha="center",
                        va="bottom",
                        fontsize=7.6,
                        fontweight="bold",
                        color="#0F172A",
                    )
        else:
            lines = ax.plot(
                x,
                values,
                color=color,
                lw=2.3,
                marker="o" if is_short else None,
                markersize=4,
                label=label,
                zorder=3,
            )
            chart_handles.extend(lines)

    if mean_val is not None and not np.isnan(mean_val):
        mean_string = fmt_v(mean_val, use_c, 1)
        mean_full_label = f"{mean_lbl} ({mean_string} %)"
        mean_line = ax.axhline(
            mean_val,
            color="#D97706",
            lw=1.7,
            ls="--",
            label=mean_full_label,
            zorder=4,
        )
        chart_handles.append(mean_line)
        ax.text(
            len(labels) - 0.6,
            mean_val + 0.15,
            mean_string,
            ha="right",
            va="bottom",
            fontsize=8.0,
            fontweight="bold",
            color="#D97706",
            bbox=dict(
                boxstyle="round,pad=0.15",
                facecolor="white",
                edgecolor="none",
                alpha=0.85,
            ),
        )

    if all_values:
        value_min = min(all_values)
        value_max = max(all_values)
        if as_bar:
            ax.set_ylim(
                max(0, np.floor(value_min - 1.0)),
                np.ceil(value_max + 0.8),
            )
        else:
            padding = (
                (value_max - value_min) * 0.14
                if value_max > value_min
                else 1.0
            )
            ax.set_ylim(
                max(0, value_min - padding),
                value_max + padding,
            )

    ax.set_xticks(x)
    label_step = 1 if is_short else 2
    ax.set_xticklabels(
        [
            label if (i % label_step == 0 or is_q[i]) else ""
            for i, label in enumerate(labels)
        ],
        rotation=90,
        fontsize=7.8,
        color="#475569",
    )
    ax.tick_params(axis="y", labelsize=8.4, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)

    for spine in ("top", "left", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(
        handles=chart_handles + shade_patches,
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=2,
        frameon=False,
        fontsize=7.4,
    )
    fig.text(
        0.09,
        0.015,
        f"{t['src']}{now_s}",
        fontsize=6.8,
        color="#64748B",
    )
    fig.text(
        0.96,
        0.015,
        "T.H.",
        fontsize=7.8,
        color="#94A3B8",
        ha="right",
    )
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fig_plotly = go.Figure()
    for values, label, color in series_list:
        y_values = [
            None if np.isnan(value) else round(value, 2)
            for value in values
        ]
        custom_values = [fmt_v(value, use_c, 1) for value in values]

        if as_bar:
            fig_plotly.add_trace(
                go.Bar(
                    x=labels,
                    y=y_values,
                    customdata=custom_values,
                    name=label,
                    marker_color=color,
                    text=custom_values,
                    textposition="outside",
                    hovertemplate=(
                        f"{label}: <b>%{{customdata}} {unit_str}</b>"
                        "<extra></extra>"
                    ),
                )
            )
        else:
            fig_plotly.add_trace(
                go.Scatter(
                    x=labels,
                    y=y_values,
                    customdata=custom_values,
                    name=label,
                    mode="lines+markers" if is_short else "lines",
                    line=dict(color=color, width=2.3),
                    connectgaps=False,
                    hovertemplate=(
                        f"{label}: <b>%{{customdata}} {unit_str}</b>"
                        "<extra></extra>"
                    ),
                )
            )

    if mean_val is not None and not np.isnan(mean_val):
        mean_string = fmt_v(mean_val, use_c, 1)
        mean_full_label = f"{mean_lbl} ({mean_string} %)"
        fig_plotly.add_trace(
            go.Scatter(
                x=labels,
                y=[round(mean_val, 2)] * len(labels),
                customdata=[mean_string] * len(labels),
                name=mean_full_label,
                mode="lines",
                line=dict(color="#D97706", width=1.8, dash="dash"),
                hovertemplate=(
                    f"{mean_full_label}: "
                    "<b>%{customdata} %</b><extra></extra>"
                ),
            )
        )

    add_shades_plotly(fig_plotly, svr_spans, bip_spans, t)
    fig_plotly.update_layout(
        title=dict(
            text=(
                f"<b>{title}</b><br>"
                f"<span style='font-size:11px;color:#334155;"
                f"font-weight:normal'>{sub}</span>"
            ),
            x=0.02,
            y=0.96,
            font=dict(size=13.5, color="#0F172A"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            yanchor="bottom",
            font=dict(size=9.5),
        ),
        margin=dict(l=48, r=24, t=122, b=76),
        height=470,
        annotations=[
            dict(
                text=f"{t['src']}{now_s}",
                x=0.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.5, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.24,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fig_plotly.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        tickfont=dict(size=9.8),
    )

    if as_bar and all_values:
        fig_plotly.update_yaxes(
            fixedrange=True,
            range=[
                max(0, np.floor(value_min - 1.0)),
                np.ceil(value_max + 0.8),
            ],
        )
    else:
        fig_plotly.update_yaxes(fixedrange=True)

    _write_clean_html(
        fig_plotly,
        f"{OUT_DIR}/{fname}{t['sfx']}.html",
    )


def save_necessary_chart(
    lang,
    fname,
    title_key,
    sub_key,
    start_ym,
    alq0,
    wy_star,
    rows,
):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    month_index = int(start_ym[5:7]) - 1
    start_label = f"{t['m'][month_index]} {start_ym[2:4]}"
    labels = [start_label] + [str(row["yr"]) for row in rows[1:]]
    alq_values = [row["alq"] for row in rows]
    necessary_values = [row["w_growth"] for row in rows]

    title = t[title_key]
    subtitle = t[sub_key].format(
        start_lbl=start_label,
        alq0=fmt_v(alq0, use_c, 1),
        wy=fmt_v(wy_star, use_c, 1),
    )
    alq_label, necessary_label = t["cn_l"]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(
        figsize=(8.2, 5.0),
        dpi=300,
        facecolor="white",
    )
    plt.subplots_adjust(left=0.09, right=0.96, top=0.77, bottom=0.17)
    fig.suptitle(
        title,
        x=0.09,
        y=0.96,
        ha="left",
        fontsize=10.6,
        fontweight="bold",
        color="#0F172A",
    )
    fig.text(
        0.09,
        0.915,
        subtitle,
        ha="left",
        fontsize=7.9,
        color="#334155",
    )
    ax.set_facecolor("#F8FAFC")

    bars = ax.bar(
        x,
        alq_values,
        width=0.45,
        color="#CBD5E1",
        edgecolor="#1B3A6B",
        lw=1.2,
        label=alq_label,
        zorder=2,
    )
    for x_value, value in zip(x, alq_values):
        ax.text(
            x_value,
            value + 0.18,
            fmt_v(value, use_c, 1),
            ha="center",
            va="bottom",
            fontsize=8.4,
            fontweight="bold",
            color="#1B3A6B",
        )

    line = ax.plot(
        x[1:],
        necessary_values[1:],
        color="#D97706",
        lw=2.5,
        marker="o",
        markersize=5,
        label=necessary_label,
        zorder=4,
    )

    for x_value, necessary_value, alq_value in zip(
        x[1:],
        necessary_values[1:],
        alq_values[1:],
    ):
        if abs((necessary_value - 0.50) - alq_value) < 0.45:
            y_position = necessary_value + 0.35
            vertical_alignment = "bottom"
        else:
            y_position = necessary_value - 0.42
            vertical_alignment = "top"

        ax.text(
            x_value,
            y_position,
            fmt_v(necessary_value, use_c, 1),
            ha="center",
            va=vertical_alignment,
            fontsize=8.4,
            fontweight="bold",
            color="#D97706",
            bbox=dict(
                boxstyle="round,pad=0.14",
                facecolor="white",
                edgecolor="none",
                alpha=0.88,
            ),
            zorder=5,
        )

    ax.set_ylim(0, max(8.0, np.ceil(alq0 + 1.5)))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.0, color="#334155")
    ax.tick_params(axis="y", labelsize=8.5, colors="#475569", length=0)
    ax.yaxis.grid(True, color="#E2E8F0", lw=0.8, zorder=0)

    for spine in ("top", "left", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")
    ax.legend(
        handles=[bars, line[0]],
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.02),
        ncol=2,
        frameon=False,
        fontsize=7.8,
    )
    fig.text(
        0.09,
        0.015,
        f"{t['src']}{now_s}",
        fontsize=6.8,
        color="#64748B",
    )
    fig.text(
        0.96,
        0.015,
        "T.H.",
        fontsize=7.8,
        color="#94A3B8",
        ha="right",
    )
    plt.savefig(f"{OUT_DIR}/{fname}{t['sfx']}.png", dpi=300)
    plt.close()

    fig_plotly = go.Figure()
    fig_plotly.add_trace(
        go.Bar(
            x=labels,
            y=alq_values,
            customdata=[fmt_v(value, use_c, 1) for value in alq_values],
            name=alq_label,
            marker_color="#CBD5E1",
            marker_line_color="#1B3A6B",
            marker_line_width=1.2,
            text=[fmt_v(value, use_c, 1) for value in alq_values],
            textposition="outside",
            hovertemplate=(
                f"{alq_label}: <b>%{{customdata}} %</b>"
                "<extra></extra>"
            ),
        )
    )
    fig_plotly.add_trace(
        go.Scatter(
            x=labels[1:],
            y=necessary_values[1:],
            customdata=[
                fmt_v(value, use_c, 1)
                for value in necessary_values[1:]
            ],
            name=necessary_label,
            mode="lines+markers+text",
            line=dict(color="#D97706", width=2.6),
            text=[
                fmt_v(value, use_c, 1)
                for value in necessary_values[1:]
            ],
            textposition="bottom center",
            hovertemplate=(
                f"{necessary_label}: <b>%{{customdata}} %</b>"
                "<extra></extra>"
            ),
        )
    )
    fig_plotly.update_layout(
        title=dict(
            text=(
                f"<b>{title}</b><br>"
                f"<span style='font-size:11px;color:#334155;"
                f"font-weight:normal'>{subtitle}</span>"
            ),
            x=0.02,
            y=0.96,
            font=dict(size=13.5, color="#0F172A"),
        ),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        hovermode="x unified",
        dragmode=False,
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.01,
            yanchor="bottom",
            font=dict(size=9.5),
        ),
        margin=dict(l=48, r=24, t=122, b=72),
        height=460,
        annotations=[
            dict(
                text=f"{t['src']}{now_s}",
                x=0.0,
                y=-0.21,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=9.5, color="#64748B"),
                xanchor="left",
            ),
            dict(
                text="T.H.",
                x=1.0,
                y=-0.21,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=10, color="#94A3B8"),
                xanchor="right",
            ),
        ],
    )
    fig_plotly.update_xaxes(type="category", fixedrange=True)
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=[0, max(8.0, np.ceil(alq0 + 1.5))],
    )
    _write_clean_html(
        fig_plotly,
        f"{OUT_DIR}/{fname}{t['sfx']}.html",
    )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    data = load_all_macro_data()
    df_y, df_q = compute_koehler_tables(data)

    (
        labels_long,
        keys_long,
        is_q_long,
        get_long,
        completed_years,
    ) = build_hybrid_series(
        df_y,
        df_q,
        start_year="1991",
        add_gap=False,
    )
    (
        labels_short,
        keys_short,
        is_q_short,
        get_short,
        _,
    ) = build_hybrid_series(
        df_y,
        df_q,
        start_year="2019",
        add_gap=True,
    )

    svr_long, bip_long = get_recession_spans(
        keys_long,
        data["bip_chain_yoy"],
    )
    svr_short, bip_short = get_recession_spans(
        keys_short,
        data["bip_chain_yoy"],
    )

    utilization_1991_2019 = df_y.loc[
        (df_y.index >= "1991") & (df_y.index <= "2019"),
        "ausl",
    ].dropna()
    mean_utilization_1991_2019 = (
        float(utilization_1991_2019.mean())
        if not utilization_1991_2019.empty
        else np.nan
    )

    start_year, alq_year, wy_year, rows_year = compute_necessary_growth(
        data,
        df_y,
        completed_years,
        mode="year",
    )
    start_quarter, alq_quarter, wy_quarter, rows_quarter = (
        compute_necessary_growth(
            data,
            df_y,
            completed_years,
            mode="quarter",
        )
    )

    for lang in ("de", "en"):
        text = TXT[lang]

        # 1–4: Lange Frist
        save_single_series_chart(
            lang,
            "01_potenzial_lang",
            text["c1_t"],
            text["c1_s"],
            labels_long,
            [
                (
                    get_long("pot"),
                    text["c1_l"][0],
                    "#1B3A6B",
                )
            ],
            is_q_long,
            "Mrd. €" if lang == "de" else "EUR bn",
            svr_long,
            bip_long,
        )
        save_single_series_chart(
            lang,
            "02_auslastung_lang",
            text["c2_t"],
            text["c2_s"],
            labels_long,
            [
                (
                    get_long("ausl"),
                    text["c2_l"][0],
                    "#1B3A6B",
                )
            ],
            is_q_long,
            "%",
            svr_long,
            bip_long,
            mean_val=mean_utilization_1991_2019,
            mean_lbl=text["c2_l"][1],
        )
        save_dual_chart(
            lang,
            "03_angemessen_alo_lang",
            text["c3_t"],
            text["c3_s"],
            labels_long,
            get_long("diff"),
            text["c3_l"][0],
            get_long("g_alo"),
            text["c3_l"][1],
            "#D97706",
            is_q_long,
            svr_long,
            bip_long,
            5.0,
            30.0,
        )
        save_dual_chart(
            lang,
            "04_angemessen_staat_lang",
            text["c4_t"],
            text["c4_s"],
            labels_long,
            get_long("diff"),
            text["c4_l"][0],
            get_long("fin_pct"),
            text["c4_l"][1],
            "#059669",
            is_q_long,
            svr_long,
            bip_long,
            5.0,
            10.0,
        )

        # 5–7: Kürzere Frist
        save_single_series_chart(
            lang,
            "05_auslastung_kurz",
            text["c5_t"],
            text["c5_s"],
            labels_short,
            [
                (
                    get_short("ausl"),
                    text["c5_l"][0],
                    "#D97706",
                )
            ],
            is_q_short,
            "%",
            svr_short,
            bip_short,
            as_bar=True,
            is_short=True,
        )
        save_dual_chart(
            lang,
            "06_angemessen_alo_kurz",
            text["c6_t"],
            text["c6_s"],
            labels_short,
            get_short("diff"),
            text["c6_l"][0],
            get_short("g_alo"),
            text["c6_l"][1],
            "#D97706",
            is_q_short,
            svr_short,
            bip_short,
            5.0,
            30.0,
            is_short=True,
        )
        save_dual_chart(
            lang,
            "07_angemessen_staat_kurz",
            text["c7_t"],
            text["c7_s"],
            labels_short,
            get_short("diff"),
            text["c7_l"][0],
            get_short("fin_pct"),
            text["c7_l"][1],
            "#059669",
            is_q_short,
            svr_short,
            bip_short,
            5.0,
            10.0,
            is_short=True,
        )

        # 8–9: Notwendiges Wirtschaftswachstum
        save_necessary_chart(
            lang,
            "08_notwendig_jahr",
            "c8_t",
            "c8_s",
            start_year,
            alq_year,
            wy_year,
            rows_year,
        )
        save_necessary_chart(
            lang,
            "09_notwendig_quartal",
            "c9_t",
            "c9_s",
            start_quarter,
            alq_quarter,
            wy_quarter,
            rows_quarter,
        )

    print(
        "[OK] Alle 36 Dateien (9 Grafiken x DE/EN x PNG/HTML) "
        "unter static/produktionspotenzial/ erzeugt."
    )


if __name__ == "__main__":
    main()
