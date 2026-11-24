#!/usr/bin/env python3
"""
Aktualisiert alle 9 Grafiken (DE & EN, .png & .html) fuer die Rubrik:
"Produktionspotenzial, Auslastung des Produktionspotenzials, angemessenes/nicht angemessenes Wirtschaftswachstum, notwendiges Wirtschaftswachstum"
Methode: Claus Koehler / Thorsten Hild
Datenbasis: Statistisches Bundesamt (Destatis GENESIS-Online: 81000-0001, 81000-0002,
            81000-0011, 81000-0012, 81000-0031, 13211-0001, 13211-0002)
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
    ("2008-04", "2009-06"),
    ("2012-10", "2013-03"),
    ("2020-02", "2020-04"),
    ("2022-10", "2025-12"),
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
        "c1_s": "Jahreswerte ab 1991 bis zum zuletzt abgeschlossenen Jahr, danach auf Jahresrate hochgerechnete Quartalswerte, in Mrd. €",
        "c1_l": ["Produktionspotenzial"],
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
        "c1_s": "Annual values from 1991 up to the last completed year, followed by annualized quarterly values, in EUR bn",
        "c1_l": ["Potential output"],
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


def _as_series(frame, col):
    s = frame[col]
    return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s


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

    time_values = _as_series(df, time_col).astype(str).str.strip()

    for column in df.columns:
        if column in (time_col, value_col) or "label" in column.lower():
            continue

        values = _as_series(df, column).astype(str).str.strip()
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
        _as_series(df, value_col).astype(str).str.replace(",", "."),
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
    require_labels=False,
):
    """Filtert GENESIS-Reihen nach Codes, Bezeichnungen oder beidem."""
    def _as_text_series(frame, col):
        s = frame[col]
        s = s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
        return s.astype(str).str.strip().str.lower()

    if df is None or df.empty or "ZEIT" not in df.columns or "NUM" not in df.columns:
        return pd.Series(dtype=float)

    df = df.loc[:, ~df.columns.duplicated()].copy()
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
                lambda codes: {
                    str(code).strip().upper()
                    for code in req_codes
                }.issubset(codes)
            )
        ].copy()

    if lbl_terms and (sub.empty or require_labels):
        label_df = sub if require_labels else df
        label_cols = [
            column
            for column in label_df.columns
            if "label" in column.lower()
        ]
        if label_cols:
            label_text = (
                pd.concat(
                    [_as_text_series(label_df, column) for column in label_cols],
                    axis=1,
                )
                .apply(lambda row: " | ".join(row), axis=1)
            )
            label_text = (
                label_text.iloc[:, 0]
                if isinstance(label_text, pd.DataFrame)
                else label_text
            )
            mask = pd.Series(True, index=label_df.index)
            for term in lbl_terms:
                mask &= label_text.str.contains(
                    term.lower(),
                    regex=False,
                )
            if excl_terms:
                for term in excl_terms:
                    mask &= ~label_text.str.contains(
                        term.lower(),
                        regex=False,
                    )
            sub = label_df[mask].copy()

    if sub.empty:
        return pd.Series(dtype=float)

    sub = sub[
        _as_series(sub, "ZEIT").astype(str).str.match(z_regex)
    ].copy()
    if sub.empty:
        return pd.Series(dtype=float)

    if pick == "max":
        result = sub.groupby("ZEIT")["NUM"].max()
    elif pick == "min":
        result = sub.groupby("ZEIT")["NUM"].min()
    else:
        result = (
            sub.drop_duplicates(subset=["ZEIT"], keep="first")
            .set_index("ZEIT")["NUM"]
        )

    return result.sort_index()


def load_all_macro_data():
    """Lädt Destatis-Reihen und bildet Fallbacks für fehlende Reihen."""
    df_bip_y = _destatis_ffcsv("81000-0001", "1991")
    df_bip_q = _destatis_ffcsv("81000-0002", "1991")

    def _normalize_persons(series):
        values = pd.to_numeric(series, errors="coerce")
        magnitude = values.abs()
        factors = pd.Series(1.0, index=values.index)
        # GENESIS can switch units within a table; normalize each observation.
        factors.loc[(magnitude > 0) & (magnitude < 1_000)] = 1_000_000.0
        factors.loc[(magnitude >= 1_000) & (magnitude < 100_000)] = 1_000.0
        return values * factors

    bip_real_y = _filter_series(
        df_bip_y,
        {"WERTORG", "VGR014"},
        ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^\d{4}$",
        pick="max",
    )
    bip_nom_y = _filter_series(
        df_bip_y,
        {"WERTORG", "VGR013"},
        ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
        r"^\d{4}$",
        pick="max",
    )

    # Falls die preisbereinigte BIP-Reihe fehlt, den Kettenindex VGRPKM
    # auf das nominale BIP des Basisjahres 2020 skalieren.
    if bip_real_y.empty:
        bip_chain_y = _filter_series(
            df_bip_y,
            {"WERTORG", "VGRPKM"},
            ["originalwerte", "preisbereinigt", "verkettet"],
            r"^\d{4}$",
            pick="max",
        )
        if (
            not bip_chain_y.empty
            and not bip_nom_y.empty
            and "2020" in bip_nom_y.index
        ):
            bip_real_y = (
                float(bip_nom_y.loc["2020"])
                * bip_chain_y
                / 100.0
            )

    bip_real_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGR014"},
        ["originalwerte", "preisbereinigt", "bruttoinlandsprodukt"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )
    bip_nom_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGR013"},
        ["originalwerte", "jeweiligen preisen", "bruttoinlandsprodukt"],
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
        if (
            not bip_chain_q.empty
            and not bip_nom_y.empty
            and "2020" in bip_nom_y.index
        ):
            bip_real_q = (
                float(bip_nom_y.loc["2020"])
                * bip_chain_q
                / 100.0
            )

    bip_chain_q = _filter_series(
        df_bip_q,
        {"WERTORG", "VGRPKM"},
        ["originalwerte", "preisbereinigt", "verkettet"],
        r"^\d{4}-Q[1-4]$",
        pick="max",
    )
    bip_chain_yoy = (
        bip_chain_q / bip_chain_q.shift(4) - 1.0
    ) * 100.0

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
            {"WERTORG"},
            ["originalwerte", "erwerbstätige", "inland"],
            r"^\d{4}$",
            pick="max",
        )
    et_y = _normalize_persons(et_y)

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
            {"WERTORG"},
            ["originalwerte", "erwerbstätige", "inland"],
            r"^\d{4}-Q[1-4]$",
            pick="max",
        )
    et_q = _normalize_persons(et_q)

    df_alo_1991 = _destatis_ffcsv("13211-0001", "1991")
    df_alo = _destatis_ffcsv("13211-0002", "2005")

    def _unemployed_monthly(df, value_code):
        dimension_col = "2_variable_attribute_label"
        if dimension_col in df.columns:
            total_mask = (
                df[dimension_col].astype(str).str.strip() == "Insgesamt"
            )
            if total_mask.any():
                df = df.loc[total_mask].copy()

        series = _filter_series(
            df,
            {value_code},
            [],
            r"^\d{4}-\d{2}$",
            pick="first",
        )
        if series.empty:
            series = _filter_series(
                df,
                set(),
                ["arbeitslose"],
                r"^\d{4}-\d{2}$",
                excl_terms=["quote"],
                pick="first",
            )
        return _normalize_persons(series)

    def _unemployed_annual(df):
        if df.empty or "ZEIT" not in df.columns or "NUM" not in df.columns:
            return pd.Series(dtype=float)

        df = df.loc[:, ~df.columns.duplicated()].copy()
        years = _as_series(df, "ZEIT").astype(str).str.strip()
        year_mask = years.str.fullmatch(r"\d{4}")
        label_cols = [
            column for column in df.columns if "label" in column.lower()
        ]
        code_cols = [
            column
            for column in df.columns
            if column.endswith("_code")
            and column not in {"statistics_code", "time_code"}
        ]
        subset = pd.DataFrame()
        if label_cols:
            labels = (
                df[label_cols]
                .fillna("")
                .astype(str)
                .agg(" | ".join, axis=1)
                .str.casefold()
            )
            unemployed_mask = labels.str.contains(
                "arbeitslose",
                regex=False,
            ) & ~labels.str.contains("arbeitslosenquote", regex=False)
            subset = df.loc[year_mask & unemployed_mask].copy()
        if subset.empty and code_cols:
            codes = df[code_cols].fillna("").astype(str).apply(
                lambda row: row.str.strip().str.upper().eq("ERW006").any(),
                axis=1,
            )
            subset = df.loc[year_mask & codes].copy()
        if subset.empty:
            return pd.Series(dtype=float)

        subset["PERSONS"] = _normalize_persons(
            _as_series(subset, "NUM"),
        )
        subset = subset.dropna(subset=["PERSONS"])
        output = {}
        region_cols = [
            column
            for column in subset.columns
            if "region" in column.lower()
            or "gebiet" in column.lower()
            or column == "1_variable_attribute_label"
        ]
        for year, year_rows in subset.groupby("ZEIT", sort=True):
            if not region_cols:
                output[str(year)] = float(year_rows["PERSONS"].iloc[0])
                continue

            region_values = (
                year_rows[region_cols]
                .fillna("")
                .astype(str)
                .apply(lambda column: column.str.casefold().str.strip())
            )
            for total_label in (
                "deutschland",
                "gesamtdeutschland",
                "insgesamt",
                "bundesgebiet",
            ):
                total_rows = year_rows.loc[
                    region_values.eq(total_label).any(axis=1)
                ]
                if not total_rows.empty:
                    output[str(year)] = float(total_rows["PERSONS"].iloc[0])
                    break
            else:
                former_west = year_rows.loc[
                    region_values.apply(
                        lambda column: column.str.contains(
                            "früheres bundesgebiet",
                            regex=False,
                        )
                    ).any(axis=1),
                    "PERSONS",
                ]
                new_states = year_rows.loc[
                    region_values.apply(
                        lambda column: column.str.contains(
                            "neue länder",
                            regex=False,
                        )
                    ).any(axis=1),
                    "PERSONS",
                ]
                if not former_west.empty and not new_states.empty:
                    output[str(year)] = float(
                        former_west.iloc[0] + new_states.iloc[0]
                    )
                elif len(year_rows) == 1:
                    output[str(year)] = float(
                        year_rows["PERSONS"].iloc[0]
                    )
        return pd.Series(output, dtype=float).sort_index()

    print("Rohe Spaltennamen von 13211-0001:")
    print(df_alo_1991.columns.tolist())
    print("Erste 10 rohen Zeilen von 13211-0001:")
    print(df_alo_1991.head(10).to_string(index=False))

    alo_1991_y = _unemployed_annual(df_alo_1991)
    if alo_1991_y.empty:
        alo_1991_m = _unemployed_monthly(df_alo_1991, "ERW006")
        if not alo_1991_m.empty:
            alo_1991_y = alo_1991_m.groupby(
                lambda value: value[:4]
            ).mean()
    if alo_1991_y.empty:
        print(
            "[DIAG] 13211-0001 enthält nach dem Arbeitslosen-/Gebietsfilter "
            "keine Jahresreihe. Spalten:"
        )
        print(df_alo_1991.columns.tolist())
        print("Keine Jahreswerte aus 13211-0001 extrahiert.")

    alo_m = _unemployed_monthly(df_alo, "ERW006").sort_index()

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

    if alq_m.empty and not alo_m.empty:
        civilian_labor_force = _filter_series(
            df_alo,
            {"ERW001"},
            ["zivile erwerbspersonen"],
            r"^\d{4}-\d{2}$",
            pick="max",
        )
        if civilian_labor_force.empty:
            civilian_labor_force = _filter_series(
                df_alo,
                set(),
                ["zivile erwerbspersonen"],
                r"^\d{4}-\d{2}$",
                pick="max",
            )
        civilian_labor_force = _normalize_persons(civilian_labor_force)

        common_months = alo_m.index.intersection(
            civilian_labor_force.index
        )
        if len(common_months):
            alq_m = (
                alo_m.loc[common_months]
                / civilian_labor_force.loc[common_months]
                * 100.0
            )

    alo_q = alo_m.groupby(
        lambda value: (
            f"{value[:4]}-Q"
            f"{(int(value[5:7]) - 1) // 3 + 1}"
        )
    ).mean()
    alo_monthly_y = alo_m.groupby(
        lambda value: value[:4]
    ).mean()
    alo_1991_y = alo_1991_y.loc[
        (alo_1991_y.index.astype(str) >= "1991")
        & (alo_1991_y.index.astype(str) <= "2004")
    ]
    expected_alo_years = pd.Index(
        [str(year) for year in range(1991, 2005)]
    )
    missing_alo_years = expected_alo_years.difference(alo_1991_y.index)
    if len(missing_alo_years):
        raise ValueError(
            "13211-0001 liefert keine lückenlose Arbeitslosen-Jahresreihe "
            "1991–2004. Fehlende Jahre: "
            f"{', '.join(missing_alo_years)}."
        )
    alo_monthly_y = alo_monthly_y.loc[
        alo_monthly_y.index.astype(str) >= "2005"
    ]
    alo_y = pd.concat([alo_1991_y, alo_monthly_y]).sort_index()
    alo_y_from_1991 = alo_y.loc[alo_y.index.astype(str) >= "1991"]
    print("Erste fünf Jahreswerte alo_y ab 1991:")
    print(alo_y_from_1991.head(5).to_string())
    if alo_y_from_1991.empty or alo_y_from_1991.index[0] != "1991":
        raise ValueError(
            "alo_y beginnt nicht 1991. Verfügbare Jahreswerte ab 1991: "
            f"{', '.join(alo_y_from_1991.index.astype(str)) or 'keine'}."
        )

    df_fin = _destatis_ffcsv("81000-0031", "1991")
    print("81000-0031: rohe Spaltennamen:")
    print(df_fin.columns.tolist())
    for column in (
        "value_variable_code",
        "value_variable_label",
        "1_variable_attribute_label",
    ):
        print(f"81000-0031: eindeutige Werte in {column}:")
        if column in df_fin.columns:
            print(df_fin[column].dropna().unique().tolist())
        else:
            print(f"<Spalte fehlt>; vorhandene Spalten: {df_fin.columns.tolist()}")
    print("81000-0031: erste 10 rohe Zeilen:")
    print(df_fin.head(10).to_string(index=False))

    def _government_amount_series(
        time_pattern,
        value_code=None,
        value_label=None,
    ):
        if df_fin.empty:
            return pd.Series(dtype=float)

        frame = df_fin.loc[:, ~df_fin.columns.duplicated()].copy()
        total_code_col = "1_variable_attribute_code"
        total_label_col = "1_variable_attribute_label"
        if (
            total_code_col not in frame.columns
            and total_label_col not in frame.columns
        ):
            return pd.Series(dtype=float)

        if value_label is not None:
            if "value_variable_label" not in frame.columns:
                return pd.Series(dtype=float)
            labels = (
                frame["value_variable_label"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.casefold()
            )
            wanted_label = value_label.casefold()
            is_series = labels.eq(wanted_label)
            if not is_series.any():
                is_series = labels.str.contains(
                    wanted_label,
                    regex=False,
                )
        elif value_code is not None and "value_variable_code" in frame.columns:
            is_series = (
                frame["value_variable_code"]
                .astype(str)
                .str.strip()
                .str.upper()
                .eq(value_code)
            )
        else:
            return pd.Series(dtype=float)

        is_total = pd.Series(False, index=frame.index)
        if total_code_col in frame.columns:
            is_total |= (
                frame[total_code_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
                .isin({"DG", "DINSG"})
            )
        if total_label_col in frame.columns:
            is_total |= (
                frame[total_label_col]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.casefold()
                .eq("deutschland insgesamt")
            )
        selected = frame.loc[is_series & is_total].copy()
        selected = selected.loc[
            selected["ZEIT"].astype(str).str.fullmatch(time_pattern)
        ]
        if selected.empty:
            return pd.Series(dtype=float)

        conflicting_years = (
            selected.groupby("ZEIT")["NUM"]
            .nunique()
            .loc[lambda values: values > 1]
        )
        if not conflicting_years.empty:
            raise ValueError(
                f"81000-0031 enthält mehrere Werte für "
                f"{value_label or value_code} / DINSG "
                f"in: {', '.join(conflicting_years.index.astype(str))}."
            )
        return (
            selected.drop_duplicates(subset=["ZEIT"])
            .set_index("ZEIT")["NUM"]
            .sort_index()
        )

    def _financing_balance(time_pattern):
        balance = _government_amount_series(
            time_pattern,
            value_label="Finanzierungssaldo des Staates",
        )
        if not balance.empty:
            return balance

        einnahmen = _government_amount_series(
            time_pattern,
            value_label="Einnahmen des Staates",
        )
        ausgaben = _government_amount_series(
            time_pattern,
            value_label="Ausgaben des Staates",
        )
        if einnahmen.empty:
            einnahmen = _government_amount_series(
                time_pattern,
                value_code="INM003",
            )
        if ausgaben.empty:
            ausgaben = _government_amount_series(
                time_pattern,
                value_code="ASG009",
            )
        return einnahmen.subtract(ausgaben).dropna()

    fin_y = _financing_balance(r"\d{4}")
    fin_q = _financing_balance(r"\d{4}-Q[1-4]")
    fin_y_is_pct = False
    fin_q_is_pct = False

    # Jahresreihen aus Quartals- bzw. Monatsreihen ergänzen, falls nötig.
    if bip_real_y.empty and not bip_real_q.empty:
        bip_real_y = bip_real_q.groupby(
            bip_real_q.index.str[:4]
        ).sum(min_count=4).dropna()
    if et_y.empty and not et_q.empty:
        et_y = et_q.groupby(et_q.index.str[:4]).mean()

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
        "fin_y_is_pct": fin_y_is_pct,
        "fin_q_is_pct": fin_q_is_pct,
        "fin_columns": df_fin.columns.tolist(),
    }


def compute_koehler_tables(d):
    """Berechnet das Produktionspotenzial nach der Claus-Köhler-Methode."""
    bip_real_y = d["bip_real_y"].copy()
    et_y = d["et_y"].copy()
    alo_y = d["alo_y"].copy()

    for series in (bip_real_y, et_y, alo_y):
        series.index = series.index.astype(str).str.strip()

    series_by_name = {
        "bip_real_y": bip_real_y,
        "et_y": et_y,
        "alo_y": alo_y,
    }
    year_coverage = {
        name: sorted(
            {
                year
                for year in series.index.astype(str)
                if re.fullmatch(r"\d{4}", year)
            }
        )
        for name, series in series_by_name.items()
    }
    coverage_text = "; ".join(
        f"{name}: {', '.join(years) if years else 'keine Jahreswerte'}"
        for name, years in year_coverage.items()
    )

    idx_y = (
        bip_real_y.index
        .intersection(et_y.index)
        .intersection(alo_y.index)
    )
    idx_y = idx_y[
        idx_y.str.fullmatch(r"\d{4}")
    ].sort_values()

    if idx_y.empty:
        raise ValueError(
            "Keine gemeinsamen Jahreswerte für die Köhler-Berechnung: "
            "prüfe die Reihenabdeckung. "
            f"Abdeckung (Jahre): {coverage_text}."
        )

    expected_years = pd.Index(
        [
            str(year)
            for year in range(1991, max(1991, int(idx_y[-1])) + 1)
        ]
    )
    missing_years = expected_years.difference(idx_y)
    if len(missing_years):
        raise ValueError(
            "Die gemeinsame Köhler-Jahresreihe ist nicht lückenlos ab 1991. "
            f"Fehlende gemeinsame Jahre: {', '.join(missing_years)}. "
            f"Abdeckung (Jahre): {coverage_text}."
        )
    if idx_y[0] != "1991":
        raise ValueError(
            "Die gemeinsame Köhler-Jahresreihe beginnt nicht 1991. "
            f"Erstes gemeinsames Jahr: {idx_y[0]}. "
            f"Abdeckung (Jahre): {coverage_text}."
        )

    df_y = pd.DataFrame(index=idx_y)
    df_y["bip_real"] = bip_real_y.loc[idx_y]
    df_y["et"] = et_y.loc[idx_y]
    df_y["alo"] = alo_y.loc[idx_y]

    # Claus-Köhler-Formeln unverändert.
    df_y["prod"] = (df_y["bip_real"] * 1e6) / df_y["et"]
    df_y["pot"] = ((df_y["et"] + df_y["alo"]) * df_y["prod"]) / 1e6
    df_y["ausl"] = (df_y["bip_real"] / df_y["pot"]) * 100.0
    df_y["g_bip"] = (
        df_y["bip_real"] / df_y["bip_real"].shift(1) - 1.0
    ) * 100.0
    df_y["g_pot_raw"] = (
        df_y["pot"] / df_y["pot"].shift(1) - 1.0
    ) * 100.0

    # Bei einem Wechsel der Destatis-Einheit kann ein einzelnes pot-Niveau
    # einen Kettenindex-Sprung erzeugen. Solche Sprünge werden gegen die
    # vorausgehenden normalen Jahresraten abgeglichen und aus pot sowie
    # g_pot entfernt.
    df_y["g_pot"] = df_y["g_pot_raw"].copy()
    for pos in range(1, len(df_y)):
        raw_growth = float(df_y["g_pot_raw"].iloc[pos])
        if not np.isfinite(raw_growth):
            continue
        previous = df_y["g_pot"].iloc[max(0, pos - 5):pos]
        previous = previous.dropna()
        if previous.empty:
            continue
        baseline = float(previous.median())
        if abs(raw_growth - baseline) >= 3.0:
            previous_pot = float(df_y["pot"].iloc[pos - 1])
            df_y.loc[df_y.index[pos], "g_pot"] = baseline
            df_y.loc[df_y.index[pos], "pot"] = (
                previous_pot * (1.0 + baseline / 100.0)
            )
            print(
                "[DIAG] g_pot-Ausreißer bereinigt: "
                f"{df_y.index[pos]} {raw_growth:.4f} % -> "
                f"{baseline:.4f} % (Median der bis zu fünf Vorjahre)."
            )

    df_y["ausl"] = (df_y["bip_real"] / df_y["pot"]) * 100.0
    df_y["diff"] = df_y["g_bip"] - df_y["g_pot"]
    df_y["g_alo"] = (
        df_y["alo"] / df_y["alo"].shift(1) - 1.0
    ) * 100.0

    fin_y = d["fin_y"].copy()
    bip_nom_y = d["bip_nom_y"].copy()
    fin_y_is_pct = bool(d.get("fin_y_is_pct", False))
    fin_y.index = fin_y.index.astype(str).str.strip()
    bip_nom_y.index = bip_nom_y.index.astype(str).str.strip()

    common_fin_y = (
        idx_y
        .intersection(fin_y.index)
        .intersection(bip_nom_y.index)
    )
    df_y["fin_pct"] = np.nan
    if len(common_fin_y):
        if fin_y_is_pct:
            df_y.loc[common_fin_y, "fin_pct"] = fin_y.loc[common_fin_y]
        else:
            fin_values = fin_y.loc[common_fin_y].astype(float)
            bip_values = bip_nom_y.loc[common_fin_y].astype(float)
            amount_scale = (
                1000.0
                if bip_values.abs().median() > 100_000.0
                else 1.0
            )
            fin_mrd = fin_values / amount_scale
            bip_mrd = bip_values / amount_scale
            df_y.loc[common_fin_y, "fin_pct"] = (
                fin_mrd / bip_mrd
            ) * 100.0
    if not np.isfinite(df_y["fin_pct"].to_numpy(dtype=float)).any() or np.isinf(
        df_y["fin_pct"].to_numpy(dtype=float)
    ).any():
        fin_columns = d.get("fin_columns", [])
        raise ValueError(
            "fin_pct enthält keine endlichen Werte: 81000-0031 lieferte keinen "
            "verwendbaren Finanzierungssaldo mit gemeinsamen Jahreswerten "
            "und nominalem BIP. Spalten von 81000-0031: "
            f"{fin_columns}"
        )
    print("fin_y.tail(10):")
    print(fin_y.tail(10).to_string())
    fin_pct = df_y["fin_pct"]
    print("fin_pct.tail(10):")
    print(fin_pct.tail(10).to_string())

    bip_real_q = d["bip_real_q"].copy()
    et_q = d["et_q"].copy()
    alo_q = d["alo_q"].copy()
    for series in (bip_real_q, et_q, alo_q):
        series.index = series.index.astype(str).str.strip()

    idx_q = (
        bip_real_q.index
        .intersection(et_q.index)
        .intersection(alo_q.index)
    )
    idx_q = idx_q[
        idx_q.str.fullmatch(r"\d{4}-Q[1-4]")
    ].sort_values()

    df_q = pd.DataFrame(index=idx_q)
    if not idx_q.empty:
        df_q["bip_real"] = bip_real_q.loc[idx_q]
        df_q["et"] = et_q.loc[idx_q]
        df_q["alo"] = alo_q.loc[idx_q]

        # Claus-Köhler-Formeln unverändert.
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

    fin_q = d["fin_q"].copy()
    bip_nom_q = d["bip_nom_q"].copy()
    fin_q_is_pct = bool(d.get("fin_q_is_pct", False))
    fin_q.index = fin_q.index.astype(str).str.strip()
    bip_nom_q.index = bip_nom_q.index.astype(str).str.strip()

    common_fin_q = (
        idx_q
        .intersection(fin_q.index)
        .intersection(bip_nom_q.index)
    )
    df_q["fin_pct"] = np.nan
    if len(common_fin_q):
        if fin_q_is_pct:
            df_q.loc[common_fin_q, "fin_pct"] = fin_q.loc[common_fin_q]
        else:
            fin_values = fin_q.loc[common_fin_q].astype(float)
            bip_values = bip_nom_q.loc[common_fin_q].astype(float)
            amount_scale = (
                1000.0
                if bip_values.abs().median() > 100_000.0
                else 1.0
            )
            fin_mrd = fin_values / amount_scale
            bip_mrd = bip_values / amount_scale
            df_q.loc[common_fin_q, "fin_pct"] = (
                fin_mrd / bip_mrd
            ) * 100.0

    return (
        df_y[df_y.index >= "1991"].copy(),
        df_q[df_q.index >= "1991-Q1"].copy(),
    )


def build_hybrid_series(df_y, df_q, start_year="1991", add_gap=False):
    """Verbindet abgeschlossene Jahreswerte und darauf folgende Quartale."""
    start_year = str(start_year)
    annual_years = sorted(
        year
        for year in df_y.index.astype(str)
        if re.fullmatch(r"\d{4}", year) and year >= start_year
    )
    quarter_keys = sorted(
        quarter
        for quarter in df_q.index.astype(str)
        if re.fullmatch(r"\d{4}-Q[1-4]", quarter)
        and quarter[:4] >= start_year
    )

    quarter_counts = pd.Series(
        [quarter[:4] for quarter in quarter_keys],
        dtype="string",
    ).value_counts()

    completed_years = sorted(
        year
        for year, count in quarter_counts.items()
        if count == 4 and year in df_y.index.astype(str)
        and year >= start_year
    )

    if not completed_years:
        if annual_years:
            completed_years = annual_years
            print(
                "[WARN] Keine vollständig mit Quartalen abgeglichenen "
                "Jahre gefunden; verwende vorhandene Jahreswerte aus df_y "
                f"({annual_years[0]}–{annual_years[-1]})."
            )
        elif not quarter_keys:
            raise ValueError(
                "build_hybrid_series: df_y enthält keine gültigen "
                "Jahreswerte und df_q keine gültigen Quartalswerte."
            )
        else:
            print(
                "[WARN] df_y enthält keine gültigen Jahreswerte; "
                "verwende verfügbare Quartale aus df_q."
            )

    last_completed_year = (
        completed_years[-1]
        if completed_years
        else None
    )
    displayed_annual_years = (
        [
            year for year in annual_years
            if year <= last_completed_year
        ]
        if last_completed_year is not None
        else annual_years
    )
    if last_completed_year is None:
        remaining_quarters = quarter_keys
    else:
        remaining_quarters = [
            quarter
            for quarter in quarter_keys
            if quarter[:4] > last_completed_year
        ]

    labels = []
    keys = []
    is_q = []

    for year in displayed_annual_years:
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
        raise ValueError(
            "build_hybrid_series: Nach den Prüfungen sind keine "
            "verwendbaren Jahres- oder Quartalswerte vorhanden."
        )

    def get_col(column):
        values = []
        for kind, key in keys:
            if kind == "Y":
                values.append(
                    float(df_y.loc[key, column])
                    if column in df_y.columns
                    else np.nan
                )
            elif kind == "Q":
                values.append(
                    float(df_q.loc[key, column])
                    if column in df_q.columns
                    else np.nan
                )
            else:
                values.append(np.nan)
        return values

    return labels, keys, is_q, get_col, completed_years


def get_recession_spans(keys, bip_chain_yoy):
    """Projiziert quartalsgenaue Phasen auf Jahres- und Quartalskategorien."""
    def month_number(year_month):
        year, month = (int(part) for part in year_month.split("-"))
        return year * 12 + month - 1

    def key_month_bounds(kind, key):
        if kind == "Y":
            start = int(key) * 12
            return start, start + 12
        if kind == "Q":
            quarter_start_month = (int(key[-1]) - 1) * 3
            start = int(key[:4]) * 12 + quarter_start_month
            return start, start + 3
        return None

    def project_period(start_month, end_month):
        spans = []
        for index, (kind, key) in enumerate(keys):
            bounds = key_month_bounds(kind, key)
            if bounds is None:
                continue
            cell_start, cell_end = bounds
            overlap_start = max(start_month, cell_start)
            overlap_end = min(end_month, cell_end)
            if overlap_start >= overlap_end:
                continue

            cell_width = cell_end - cell_start
            x_start = index - 0.5 + (overlap_start - cell_start) / cell_width
            x_end = index - 0.5 + (overlap_end - cell_start) / cell_width
            if spans and abs(spans[-1][1] - x_start) < 1e-9:
                spans[-1] = (spans[-1][0], x_end)
            else:
                spans.append((x_start, x_end))
        return spans

    def project_intervals(intervals):
        spans = sorted(
            span
            for start_month, end_month in intervals
            for span in project_period(start_month, end_month)
        )
        merged = []
        for x0, x1 in spans:
            if merged and x0 <= merged[-1][1] + 1e-9:
                merged[-1] = (merged[-1][0], max(merged[-1][1], x1))
            else:
                merged.append((x0, x1))
        return merged

    svr_intervals = [
        (month_number(start), month_number(end) + 1)
        for start, end in SVR_PHASES
    ]

    quarterly_bip_yoy = bip_chain_yoy.copy()
    quarterly_bip_yoy.index = quarterly_bip_yoy.index.astype(str)
    negative_quarters = []
    for quarter, value in quarterly_bip_yoy.items():
        if pd.notna(value) and value < 0 and re.fullmatch(r"\d{4}-Q[1-4]", quarter):
            bounds = key_month_bounds("Q", quarter)
            negative_quarters.append(bounds)

    negative_quarters.sort()
    bip_intervals = []
    for start_month, end_month in negative_quarters:
        if bip_intervals and start_month <= bip_intervals[-1][1]:
            bip_intervals[-1] = (
                bip_intervals[-1][0],
                max(bip_intervals[-1][1], end_month),
            )
        else:
            bip_intervals.append((start_month, end_month))

    return (
        project_intervals(svr_intervals),
        project_intervals(bip_intervals),
    )


def add_shades_mpl(ax, svr_spans, bip_spans, t):
    """Zeichnet SVR-Phasen grau und BIP-Rezessionen hellblau."""
    patches = []
    for x0, x1 in svr_spans:
        ax.axvspan(
            x0,
            x1,
            color="#E2E8F0",
            alpha=0.85,
            zorder=0,
        )
    for x0, x1 in bip_spans:
        ax.axvspan(
            x0,
            x1,
            color="#93C5FD",
            alpha=0.45,
            zorder=0.5,
        )
    if svr_spans:
        patches.append(
            mpatches.Patch(
                color="#E2E8F0",
                label=t["leg_svr"],
            )
        )
    if bip_spans:
        patches.append(
            mpatches.Patch(
                color="#93C5FD",
                alpha=0.55,
                label=t["leg_bip"],
            )
        )
    return patches


def add_shades_plotly(fp, svr_spans, bip_spans, t):
    """Zeichnet SVR-Phasen grau und BIP-Rezessionen hellblau."""
    shapes = [
        dict(
            type="rect",
            xref="x",
            yref="paper",
            x0=x0,
            x1=x1,
            y0=0,
            y1=1,
            fillcolor="rgba(203, 213, 225, 0.45)",
            line=dict(width=0),
            layer="below",
        )
        for x0, x1 in svr_spans
    ]
    shapes.extend(
        dict(
            type="rect",
            xref="x",
            yref="paper",
            x0=x0,
            x1=x1,
            y0=0,
            y1=1,
            fillcolor="rgba(147, 197, 253, 0.40)",
            line=dict(width=0),
            layer="below",
        )
        for x0, x1 in bip_spans
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
                    color="rgba(203, 213, 225, 0.85)",
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
                    color="rgba(147, 197, 253, 0.75)",
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
        alq_values = {}
        for ym in d["alo_m"].index:
            quarter_key = (
                f"{ym[:4]}-Q"
                f"{(int(ym[5:7]) - 1) // 3 + 1}"
            )
            if quarter_key in d["et_q"].index:
                unemployed = float(d["alo_m"].loc[ym])
                employed = float(d["et_q"].loc[quarter_key])
                alq_values[ym] = round(
                    unemployed / (employed + unemployed) * 100.0,
                    1,
                )
        alq_s = pd.Series(alq_values).sort_index()

    if alq_s.empty:
        raise ValueError(
            "compute_necessary_growth: Arbeitslosenquote ist leer; "
            "prüfe ALQ001 sowie Arbeitslose und zivile Erwerbspersonen "
            "aus 13211-0002."
        )

    alq_s = alq_s.sort_index()
    last_ym = alq_s.index[-1]
    current_year = int(last_ym[:4])

    if mode == "year":
        january = f"{current_year}-01"
        start_ym = january if january in alq_s.index else last_ym
    else:
        quarter_ends = [
            ym
            for ym in alq_s.index
            if ym[5:7] in ("03", "06", "09", "12")
        ]
        start_ym = quarter_ends[-1] if quarter_ends else last_ym

    alq0 = round(float(alq_s.loc[start_ym]), 1)

    # Arithmetisches Mittel der letzten fünf abgeschlossenen
    # Jahreswachstumsraten aus der Köhler-Jahrestabelle.
    completed_year_index = pd.Index(
        [str(year) for year in completed_years]
    )
    completed_growth = (
        df_y.loc[
            df_y.index.astype(str).isin(completed_year_index),
            "g_pot",
        ]
        .dropna()
        .tail(5)
    )
    if len(completed_growth) < 5:
        raise ValueError(
            "compute_necessary_growth: Für wY* liegen weniger als fünf "
            "abgeschlossene Jahreswachstumsraten vor."
        )
    wy_star = float(completed_growth.mean())
    if mode == "year":
        print("Letzte fünf abgeschlossene Werte df_y['g_pot'] (%):")
        print(completed_growth.to_string())
        print(f"wY* (5-Jahres-Mittel) = {wy_star:.6f} %")

    rows = [
        {
            "ym": start_ym,
            "yr": int(start_ym[:4]),
            "alq": alq0,
            "w_growth": np.nan,
        }
    ]

    previous_alq = alq0
    step_year = int(start_ym[:4]) + 1

    while previous_alq > 3.0 and len(rows) <= 8:
        next_alq = round(max(previous_alq - 1.0, 0.0), 1)
        growth_due_to_alq = (
            (1.0 + next_alq / 100.0)
            / (1.0 + previous_alq / 100.0)
            - 1.0
        ) * 100.0
        necessary_growth = round(
            wy_star - growth_due_to_alq,
            1,
        )
        rows.append(
            {
                "ym": None,
                "yr": step_year,
                "alq": next_alq,
                "w_growth": necessary_growth,
            }
        )
        previous_alq = next_alq
        step_year += 1

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
    show_y_grid=True,
):
    t = TXT[lang]
    use_c = t["comma"]
    now_s = datetime.now().strftime(t["date_fmt"])
    x = np.arange(len(labels))
    pp_unit = "Ppkt." if lang == "de" else "pp"
    line_array = np.array(line_vals, dtype=float)
    bar_array = np.array(bar_vals, dtype=float)
    finite_line = np.abs(line_array[np.isfinite(line_array)])
    finite_bar = np.abs(bar_array[np.isfinite(bar_array)])
    line_limit = float(lmax)
    bar_limit = float(bmax)
    line_range = (-line_limit, line_limit)
    bar_range = (-bar_limit, bar_limit)
    line_ticks = np.linspace(*line_range, 7)
    bar_ticks = np.linspace(*bar_range, 7)
    line_ticks[3] = 0.0
    bar_ticks[3] = 0.0

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
        bar_array,
        width=0.48 if is_short else 0.58,
        color=bar_color,
        alpha=0.82,
        label=bar_name,
        zorder=2,
    )
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

    ax1.set_ylim(*line_range)
    ax2.set_ylim(*bar_range)
    ax1.set_yticks(line_ticks)
    ax2.set_yticks(bar_ticks)

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
    ax1.yaxis.grid(show_y_grid, color="#E2E8F0", lw=0.8, zorder=0)

    for axis in (ax1, ax2):
        for spine in ("top", "left", "right"):
            axis.spines[spine].set_visible(False)
    ax1.spines["bottom"].set_color("#94A3B8")

    ax1.legend(
        handles=[lines[0], bars] + shade_patches,
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
            y=[None if np.isnan(v) else round(v, 2) for v in bar_vals],
            customdata=[fmt_v(v, use_c, 1) for v in bar_vals],
            name=bar_name,
            marker_color=bar_color,
            opacity=0.82,
            hovertemplate=f"{bar_name}: <b>%{{customdata}} %</b><extra></extra>",
        ),
        secondary_y=True,
    )
    fig_plotly.add_trace(
        go.Scatter(
            x=labels,
            y=[None if np.isnan(v) else round(v, 2) for v in line_vals],
            customdata=[fmt_v(v, use_c, 2) for v in line_vals],
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
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=9.8, color="#475569"),
    )
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=list(line_range),
        tickvals=line_ticks.tolist(),
        showgrid=show_y_grid,
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#64748B",
        zerolinewidth=1.2,
        tickfont=dict(size=10.5, color="#475569"),
        secondary_y=False,
    )
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=list(bar_range),
        tickvals=bar_ticks.tolist(),
        showgrid=False,
        zeroline=True,
        zerolinecolor="#64748B",
        zerolinewidth=1.2,
        tickfont=dict(size=10.5, color="#475569"),
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
    show_y_grid=True,
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

    all_vals = []
    chart_handles = []

    for vals, lbl, col in series_list:
        all_vals.extend([v for v in vals if not np.isnan(v)])
        if as_bar:
            bars = ax.bar(
                x,
                vals,
                width=0.50,
                color=col,
                alpha=0.85,
                label=lbl,
                zorder=3,
            )
            chart_handles.append(bars)
            for xi, v in zip(x, vals):
                if not np.isnan(v):
                    ax.text(
                        xi,
                        v + 0.12,
                        fmt_v(v, use_c, 1),
                        ha="center",
                        va="bottom",
                        fontsize=7.6,
                        fontweight="bold",
                        color="#0F172A",
                    )
        else:
            lines = ax.plot(
                x,
                vals,
                color=col,
                lw=2.3,
                marker="o" if is_short else None,
                markersize=4,
                label=lbl,
                zorder=3,
            )
            chart_handles.extend(lines)

    if mean_val is not None and not np.isnan(mean_val):
        m_str = fmt_v(mean_val, use_c, 1)
        m_full = f"{mean_lbl} ({m_str} %)"
        mean_line = ax.axhline(
            mean_val,
            color="#D97706",
            lw=1.7,
            ls="--",
            label=m_full,
            zorder=4,
        )
        chart_handles.append(mean_line)
        ax.text(
            len(labels) - 0.6,
            mean_val + 0.15,
            m_str,
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

    vmin = min(all_vals)
    vmax = max(all_vals)
    if as_bar:
        ax.set_ylim(
            max(0, np.floor(vmin - 1.0)),
            np.ceil(vmax + 0.8),
        )
    else:
        pad = (vmax - vmin) * 0.14 if vmax > vmin else 1.0
        ax.set_ylim(
            max(0, vmin - pad),
            vmax + pad,
        )

    ax.set_xticks(x)
    step_lbl = 1 if is_short else 2
    ax.set_xticklabels(
        [
            lbl if (i % step_lbl == 0 or is_q[i]) else ""
            for i, lbl in enumerate(labels)
        ],
        rotation=90,
        fontsize=7.8,
        color="#475569",
    )
    ax.tick_params(axis="y", labelsize=8.4, colors="#475569", length=0)
    ax.yaxis.grid(show_y_grid, color="#E2E8F0", lw=0.8, zorder=0)
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
    for vals, lbl, col in series_list:
        y_values = [
            None if np.isnan(v) else round(v, 2)
            for v in vals
        ]
        custom_values = [fmt_v(v, use_c, 1) for v in vals]

        if as_bar:
            fig_plotly.add_trace(
                go.Bar(
                    x=labels,
                    y=y_values,
                    customdata=custom_values,
                    name=lbl,
                    marker_color=col,
                    text=custom_values,
                    textposition="outside",
                    hovertemplate=(
                        f"{lbl}: <b>%{{customdata}} {unit_str}</b>"
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
                    name=lbl,
                    mode="lines+markers" if is_short else "lines",
                    line=dict(color=col, width=2.3),
                    connectgaps=False,
                    hovertemplate=(
                        f"{lbl}: <b>%{{customdata}} {unit_str}</b>"
                        "<extra></extra>"
                    ),
                )
            )

    if mean_val is not None and not np.isnan(mean_val):
        m_str = fmt_v(mean_val, use_c, 1)
        m_full = f"{mean_lbl} ({m_str} %)"
        fig_plotly.add_trace(
            go.Scatter(
                x=labels,
                y=[round(mean_val, 2)] * len(labels),
                customdata=[m_str] * len(labels),
                name=m_full,
                mode="lines",
                line=dict(color="#D97706", width=1.8, dash="dash"),
                hovertemplate=(
                    f"{m_full}: <b>%{{customdata}} %</b>"
                    "<extra></extra>"
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
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=9.8, color="#475569"),
    )
    if as_bar:
        fig_plotly.update_yaxes(
            fixedrange=True,
            range=[
                max(0, np.floor(vmin - 1.0)),
                np.ceil(vmax + 0.8),
            ],
            showgrid=show_y_grid,
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#64748B",
            zerolinewidth=1.2,
            tickfont=dict(size=10.5, color="#475569"),
        )
    else:
        fig_plotly.update_yaxes(
            fixedrange=True,
            showgrid=show_y_grid,
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#64748B",
            zerolinewidth=1.2,
            tickfont=dict(size=10.5, color="#475569"),
        )

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
    print(f"{sub_key}: wy_star exakt vor Untertitel = {wy_star!r}")
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
            customdata=[
                fmt_v(value, use_c, 1)
                for value in alq_values
            ],
            name=alq_label,
            marker_color="#CBD5E1",
            marker_line_color="#1B3A6B",
            marker_line_width=1.2,
            text=[
                fmt_v(value, use_c, 1)
                for value in alq_values
            ],
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
                f"{necessary_label}: "
                "<b>%{customdata} %</b><extra></extra>"
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
    fig_plotly.update_xaxes(
        type="category",
        fixedrange=True,
        tickangle=-45,
        showgrid=False,
        linecolor="#94A3B8",
        tickfont=dict(size=9.8, color="#475569"),
    )
    fig_plotly.update_yaxes(
        fixedrange=True,
        range=[0, max(8.0, np.ceil(alq0 + 1.5))],
        gridcolor="#E2E8F0",
        zeroline=True,
        zerolinecolor="#64748B",
        zerolinewidth=1.2,
        tickfont=dict(size=10.5, color="#475569"),
    )
    _write_clean_html(
        fig_plotly,
        f"{OUT_DIR}/{fname}{t['sfx']}.html",
    )


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})

    d = load_all_macro_data()
    df_y, df_q = compute_koehler_tables(d)
    df_y_1991_2025 = df_y.loc[
        (df_y.index >= "1991") & (df_y.index <= "2025"),
        ["bip_real", "et", "alo", "prod", "pot", "g_pot"],
    ]
    print(
        'df_y[["bip_real", "et", "alo", "prod", "pot", "g_pot"]] '
        "1991–2025:"
    )
    print(df_y_1991_2025.to_string())
    print("g_pot roh und bereinigt 2020–2025 (%):")
    print(
        df_y.loc[
            (df_y.index >= "2020") & (df_y.index <= "2025"),
            ["g_pot_raw", "g_pot"],
        ].to_string()
    )

    (
        lbl_long,
        keys_long,
        isq_long,
        get_long,
        completed_years,
    ) = build_hybrid_series(
        df_y,
        df_q,
        start_year="1991",
        add_gap=False,
    )
    (
        lbl_short,
        keys_short,
        isq_short,
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
        d["bip_chain_yoy"],
    )
    svr_short, _ = get_recession_spans(
        keys_short,
        d["bip_chain_yoy"],
    )
    bip_short = []

    ausl_91_19 = df_y.loc[
        (df_y.index >= "1991")
        & (df_y.index <= "2019"),
        "ausl",
    ].dropna()
    mean_ausl_91_19 = (
        float(ausl_91_19.mean())
        if not ausl_91_19.empty
        else np.nan
    )

    start_y, alq0_y, wy_y, rows_y = compute_necessary_growth(
        d,
        df_y,
        completed_years,
        mode="year",
    )
    start_q, alq0_q, wy_q, rows_q = compute_necessary_growth(
        d,
        df_y,
        completed_years,
        mode="quarter",
    )
    if wy_y != wy_q:
        raise RuntimeError(
            "wY* weicht zwischen Grafik 8 und Grafik 9 ab: "
            f"{wy_y!r} != {wy_q!r}"
        )
    for lang in ("de", "en"):
        t = TXT[lang]

        # 1–4: Lange Frist ab 1991
        pot_long = get_long("pot")
        pot_long = [
            value * 4 if is_quarter else value
            for value, is_quarter in zip(pot_long, isq_long)
        ]
        save_single_series_chart(
            lang,
            "01_potenzial_lang",
            t["c1_t"],
            t["c1_s"],
            lbl_long,
            [
                (
                    pot_long,
                    t["c1_l"][0],
                    "#1B3A6B",
                ),
            ],
            isq_long,
            "Mrd. €" if lang == "de" else "EUR bn",
            svr_long,
            bip_long,
            show_y_grid=False,
        )
        save_single_series_chart(
            lang,
            "02_auslastung_lang",
            t["c2_t"],
            t["c2_s"],
            lbl_long,
            [
                (
                    get_long("ausl"),
                    t["c2_l"][0],
                    "#1B3A6B",
                )
            ],
            isq_long,
            "%",
            svr_long,
            bip_long,
            mean_val=mean_ausl_91_19,
            mean_lbl=t["c2_l"][1],
            show_y_grid=False,
        )
        save_dual_chart(
            lang,
            "03_angemessen_alo_lang",
            t["c3_t"],
            t["c3_s"],
            lbl_long,
            get_long("diff"),
            t["c3_l"][0],
            get_long("g_alo"),
            t["c3_l"][1],
            "#D97706",
            isq_long,
            svr_long,
            bip_long,
            3.0,
            30.0,
            show_y_grid=False,
        )
        save_dual_chart(
            lang,
            "04_angemessen_staat_lang",
            t["c4_t"],
            t["c4_s"],
            lbl_long,
            get_long("diff"),
            t["c4_l"][0],
            get_long("fin_pct"),
            t["c4_l"][1],
            "#059669",
            isq_long,
            svr_long,
            bip_long,
            3.0,
            12.0,
            show_y_grid=False,
        )

        # 5–7: Kürzere Frist ab 2019
        save_single_series_chart(
            lang,
            "05_auslastung_kurz",
            t["c5_t"],
            t["c5_s"],
            lbl_short,
            [
                (
                    get_short("ausl"),
                    t["c5_l"][0],
                    "#D97706",
                )
            ],
            isq_short,
            "%",
            svr_short,
            bip_short,
            as_bar=True,
            is_short=True,
        )
        save_dual_chart(
            lang,
            "06_angemessen_alo_kurz",
            t["c6_t"],
            t["c6_s"],
            lbl_short,
            get_short("diff"),
            t["c6_l"][0],
            get_short("g_alo"),
            t["c6_l"][1],
            "#D97706",
            isq_short,
            svr_short,
            bip_short,
            3.0,
            30.0,
            is_short=True,
        )
        save_dual_chart(
            lang,
            "07_angemessen_staat_kurz",
            t["c7_t"],
            t["c7_s"],
            lbl_short,
            get_short("diff"),
            t["c7_l"][0],
            get_short("fin_pct"),
            t["c7_l"][1],
            "#059669",
            isq_short,
            svr_short,
            bip_short,
            3.0,
            12.0,
            is_short=True,
        )

        # 8–9: Notwendiges Wirtschaftswachstum
        save_necessary_chart(
            lang,
            "08_notwendig_jahr",
            "c8_t",
            "c8_s",
            start_y,
            alq0_y,
            wy_y,
            rows_y,
        )
        save_necessary_chart(
            lang,
            "09_notwendig_quartal",
            "c9_t",
            "c9_s",
            start_q,
            alq0_q,
            wy_q,
            rows_q,
        )

    print("\n=== KLARTEXT-DIAGNOSE PRODUKTIONSPOTENZIAL ===")
    print(
        "Jahresreihe df_y:",
        f"erstes Jahr={df_y.index.min()},",
        f"letztes Jahr={df_y.index.max()}",
    )

    ausl_valid = df_y["ausl"].dropna()
    if not ausl_valid.empty:
        print(
            "ausl Min/Max:",
            f"{ausl_valid.min():.4f}",
            "/",
            f"{ausl_valid.max():.4f}",
        )
    else:
        print("ausl Min/Max: k. A.")

    fin_valid = df_y["fin_pct"].dropna()
    if not fin_valid.empty:
        print(
            "fin_pct Min/Max:",
            f"{fin_valid.min():.4f}",
            "/",
            f"{fin_valid.max():.4f}",
        )
    else:
        print("fin_pct Min/Max: k. A.")

    print(
        f"wY* exakt berechnet: {wy_y:.6f} %",
        f"(gerundet in Grafiken: {wy_y:.1f} %)",
    )
    print("Erste 3 Zeilen der Abbaureihe:")
    print(
        pd.DataFrame(rows_y)
        .head(3)
        .to_string(index=False),
    )
    print("=" * 78)

    print(
        "[OK] Alle 36 Dateien "
        "(9 Grafiken x DE/EN x PNG/HTML) "
        "unter static/produktionspotenzial/ erzeugt."
    )


if __name__ == "__main__":
    main()
