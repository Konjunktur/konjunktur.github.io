from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUTPUT_PERIODS = pd.period_range("2025-09", "2026-09", freq="M").astype(str).tolist()
INDEX_PERIODS = pd.period_range("2024-09", "2026-09", freq="M").astype(str).tolist()
MONTHS_DE = {
    "01": "Jan", "02": "Feb", "03": "Mär", "04": "Apr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dez",
}

CHART_3_SPECS = {
    "Verarb. Gewerbe: Insgesamt": (
        "42151-0004",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "X13JDKB",
            "4_variable_attribute_code": "INSGESAMT",
            "5_variable_attribute_code": "WZ08-C",
            "value_variable_code": "AUF102",
        },
    ),
    "Verarb. Gewerbe: Inland": (
        "42151-0004",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "X13JDKB",
            "4_variable_attribute_code": "INLAND",
            "5_variable_attribute_code": "WZ08-C",
            "value_variable_code": "AUF102",
        },
    ),
    "Verarb. Gewerbe: Ausland": (
        "42151-0004",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "X13JDKB",
            "4_variable_attribute_code": "AUSLAND",
            "5_variable_attribute_code": "WZ08-C",
            "value_variable_code": "AUF102",
        },
    ),
    "Bauhauptgew.: Hoch- und Tiefbau": (
        "44111-0009",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "BTR-20UMTP",
            "4_variable_attribute_code": "BAUART",
            "5_variable_attribute_code": "X13JDKB",
            "value_variable_code": "AUF102",
        },
    ),
    "Bauhauptgew.: Hochbau": (
        "44111-0009",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "BTR-20UMTP",
            "4_variable_attribute_code": "BAUART1",
            "5_variable_attribute_code": "X13JDKB",
            "value_variable_code": "AUF102",
        },
    ),
    "Bauhauptgew.: Tiefbau": (
        "44111-0009",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "BTR-20UMTP",
            "4_variable_attribute_code": "BAUART2",
            "5_variable_attribute_code": "X13JDKB",
            "value_variable_code": "AUF102",
        },
    ),
}

CHART_4_SPECS = {
    "Produktion Gesamtwirtschaft": (
        "48311-0001",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "X13JDKB",
            "value_variable_code": "PRO103",
        },
    ),
    "Einzelhandel ohne Kfz": (
        "45212-0005",
        {
            "2_variable_attribute_code": "DG",
            "3_variable_attribute_code": "REAL",
            "4_variable_attribute_code": "X13JDKB",
            "5_variable_attribute_code": "WZ08-47",
            "value_variable_code": "UMS103",
        },
    ),
}

SERIES_STYLES = {
    "Verarb. Gewerbe: Insgesamt": ("#1B3A6B", "o"),
    "Verarb. Gewerbe: Inland": ("#D97706", "s"),
    "Verarb. Gewerbe: Ausland": ("#059669", "^"),
    "Bauhauptgew.: Hoch- und Tiefbau": ("#0284C7", "D"),
    "Bauhauptgew.: Hochbau": ("#7C3AED", "v"),
    "Bauhauptgew.: Tiefbau": ("#64748B", "P"),
    "Produktion Gesamtwirtschaft": ("#1B3A6B", "o"),
    "Einzelhandel ohne Kfz": ("#059669", "s"),
}


def load_index_series(table_id, filters):
    frame = pd.read_csv(CACHE / f"{table_id}.csv", sep=";", dtype=str, keep_default_na=False)
    for column, code in filters.items():
        if column not in frame.columns:
            raise KeyError(f"{table_id}: fehlende Spalte {column}")
        frame = frame.loc[frame[column] == code]

    frame = frame.loc[frame["ZEIT"].isin(INDEX_PERIODS), ["ZEIT", "WERT"]].copy()
    if frame["ZEIT"].duplicated().any():
        duplicate_periods = frame.loc[frame["ZEIT"].duplicated(keep=False), "ZEIT"].tolist()
        raise ValueError(f"{table_id}: mehrere Treffer pro Monat: {duplicate_periods}")

    index_values = pd.to_numeric(frame["WERT"].str.replace(",", ".", regex=False), errors="coerce")
    index_values.index = frame["ZEIT"]
    return index_values.reindex(INDEX_PERIODS)


def year_over_year(index_values):
    growth = {}
    for period in OUTPUT_PERIODS:
        previous_period = f"{int(period[:4]) - 1}{period[4:]}"
        current_value = index_values.get(period, np.nan)
        previous_value = index_values.get(previous_period, np.nan)
        if pd.notna(current_value) and pd.notna(previous_value) and previous_value != 0:
            growth[period] = (current_value / previous_value - 1) * 100
        else:
            growth[period] = np.nan
    return pd.Series(growth, dtype=float)


def collect_series(specs):
    result = {}
    for label, (table_id, filters) in specs.items():
        result[label] = year_over_year(load_index_series(table_id, filters))
    return pd.DataFrame(result, index=OUTPUT_PERIODS)


def format_percent(value):
    if pd.isna(value):
        return "–"
    return f"{value:+.1f}".replace(".", ",")


def period_label(period):
    return f"{MONTHS_DE[period[5:7]]} {period[2:4]}"


def print_values(title, data):
    print(f"\n{title} (Veränderung zum Vorjahr in %)\n")
    printable = data.copy()
    printable.insert(0, "Zeitraum", [period_label(period) for period in data.index])
    for column in data.columns:
        printable[column] = data[column].map(format_percent)
    print(printable.to_string(index=False, justify="center"))


def add_data_table(fig, data):
    table_ax = fig.add_axes((0.055, 0.075, 0.91, 0.205))
    table_ax.axis("off")
    labels = [period_label(period) for period in data.index]
    cell_text = [
        [label, *(format_percent(value) for value in data[label])]
        for label in data.columns
    ]
    label_width = 0.255
    period_width = (1 - label_width) / len(labels)
    table = table_ax.table(
        cellText=cell_text,
        colLabels=["Reihe", *labels],
        colWidths=[label_width] + [period_width] * len(labels),
        cellLoc="center",
        colLoc="center",
        bbox=(0, 0, 1, 1),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.0)
    for (row, column), cell in table.get_celld().items():
        cell.set_facecolor("white")
        cell.set_edgecolor("#CBD5E1")
        cell.set_linewidth(0.35)
        cell.set_text_props(
            color="#1E293B" if row == 0 or column == 0 else "#334155",
            weight="bold" if row == 0 or column == 0 else "normal",
            ha="left" if column == 0 else "center",
        )
        cell.get_text().set_fontsize(6.6 if row == 0 else 7.0)


def render_chart(title, subtitle, data, filename, source_note):
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(12.6, 7.4), dpi=220, facecolor="white")
    ax = fig.add_axes((0.075, 0.36, 0.91, 0.405))
    fig.text(0.055, 0.965, title, fontsize=16, fontweight="bold", color="#0F172A", va="top")
    fig.text(0.055, 0.918, subtitle, fontsize=11.5, color="#64748B", va="top")

    lines = []
    for label in data.columns:
        color, marker = SERIES_STYLES[label]
        (line,) = ax.plot(
            np.arange(len(data)),
            data[label].to_numpy(dtype=float),
            color=color,
            linewidth=2.0,
            marker=marker,
            markersize=4,
            label=label,
            zorder=3,
        )
        lines.append(line)

    fig.legend(
        handles=lines,
        labels=list(data.columns),
        loc="upper left",
        bbox_to_anchor=(0.055, 0.875),
        ncol=3 if len(data.columns) > 3 else 2,
        frameon=False,
        fontsize=8.2,
        handlelength=2.0,
        columnspacing=1.4,
    )
    ax.set_facecolor("#F8FAFC")
    ax.set_xlim(-0.25, len(data) - 0.75)
    ax.set_xticks(np.arange(len(data)))
    ax.set_xticklabels([period_label(period) for period in data.index], rotation=45, ha="right")
    ax.set_ylabel("% gg. Vorjahr", fontsize=9, color="#475569")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))
    ax.tick_params(axis="both", colors="#475569", labelsize=8, length=3, color="#CBD5E1")
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.axhline(0, color="#64748B", linewidth=1.0, zorder=2)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    add_data_table(fig, data)
    fig.text(0.055, 0.025, source_note, fontsize=7.5, color="#64748B", va="bottom")
    fig.text(0.965, 0.025, "T.H.", fontsize=8, color="#94A3B8", ha="right", va="bottom")
    fig.savefig(CACHE / filename, dpi=220, facecolor="white")
    plt.close(fig)
    print(f"Gespeichert: data/cache/{filename}")


def main():
    assert OUTPUT_PERIODS[0] == "2025-09" and OUTPUT_PERIODS[-1] == "2026-09"
    chart_3 = collect_series(CHART_3_SPECS)
    chart_4 = collect_series(CHART_4_SPECS)

    assert chart_3.notna().all().all(), "Grafik 3 muss für alle Reihen 13 Werte enthalten."
    production_august = chart_4.loc["2026-08", "Produktion Gesamtwirtschaft"]
    assert np.isclose(round(production_august, 1), 1.5), (
        "Kontrollwert Produktion Gesamtwirtschaft, August 2026, muss +1,5 % sein."
    )
    assert pd.isna(chart_4.loc["2026-09", "Produktion Gesamtwirtschaft"]), (
        "Produktion Gesamtwirtschaft soll nur bis August 2026 vorliegen."
    )
    assert chart_4["Einzelhandel ohne Kfz"].notna().all(), (
        "Einzelhandel ohne Kfz muss bis September 2026 vorliegen."
    )

    print_values("Grafik 3: Auftragseingänge", chart_3)
    print_values("Grafik 4: Produktion und Einzelhandelsumsätze", chart_4)

    render_chart(
        "Auftragseingänge",
        "Volumenindex, Veränderung zum Vorjahr in % (kalenderbereinigte Werte)",
        chart_3,
        "preview_03_auftragseingaenge.png",
        "Quelle: Statistisches Bundesamt (Destatis) | Eigene Berechnung aus Indexwerten",
    )
    render_chart(
        "Produktion und Einzelhandelsumsätze",
        "Real, Veränderung zum Vorjahr in % (kalenderbereinigte Werte)",
        chart_4,
        "preview_04_produktion_einzelhandel.png",
        "Quelle: Statistisches Bundesamt (Destatis) | Eigene Berechnung aus Indexwerten",
    )


if __name__ == "__main__":
    main()
