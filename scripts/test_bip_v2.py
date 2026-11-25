import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime

import update_charts as charts
import update_spannungszahl as shade

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
SVR_BBK_INTERVALS = [
    ("2008-04", "2009-06"),
    ("2012-10", "2013-03"),
    ("2020-02", "2020-04"),
    ("2022-10", "2025-12"),
]


def load(name):
    df = pd.read_csv(os.path.join(CACHE, f"81000-{name}.csv"), sep=";", dtype=str, keep_default_na=False)
    cols = [c for c in df if c.endswith("_code") and c not in {"statistics_code", "time_code"}]
    df["_CODES"] = df[cols].apply(lambda row: set(v.strip() for v in row if v.strip()), axis=1)
    return df


def values(df, codes):
    times = charts.valid_times(df, codes, r"^(?:\d{4}|\d{4}-Q[1-4])$")
    return dict(zip(times, charts.extract_by_codes(df, codes, times, is_rate=True)))


def yoy(series, period):
    prior = f"{int(period[:4]) - 1}{period[4:]}"
    return (series[period] / series[prior] - 1) * 100 if period in series and series.get(prior) else np.nan


def growth_values(series, periods):
    return np.array([yoy(series, period) if period else np.nan for period in periods], dtype=float)


def period_months(period):
    if not period:
        return None
    if "-Q" not in period:
        return f"{period}-01", f"{period}-12"
    year, quarter = period.split("-Q")
    starts = {"1": "01", "2": "04", "3": "07", "4": "10"}
    ends = {"1": "03", "2": "06", "3": "09", "4": "12"}
    return f"{year}-{starts[quarter]}", f"{year}-{ends[quarter]}"


def add_recession_shading(ax, periods, bip_negative_periods):
    def add_spans(indices, color, alpha, zorder):
        if not indices:
            return
        start = previous = indices[0]
        for index in indices[1:] + [None]:
            if index is None or index != previous + 1:
                ax.axvspan(start - 0.5, previous + 0.5, color=color, alpha=alpha, zorder=zorder)
                if index is None:
                    break
                start = index
            previous = index

    bounds = [period_months(period) for period in periods]
    has_svr = False
    for start, end in SVR_BBK_INTERVALS:
        indices = [
            i for i, period in enumerate(bounds)
            if period and period[0] <= end and period[1] >= start
        ]
        if indices:
            add_spans(indices, "#E2E8F0", 0.85, 0)
            has_svr = True

    indices = [i for i, period in enumerate(periods) if period in bip_negative_periods]
    has_bip = bool(indices)
    if indices:
        add_spans(indices, "#93C5FD", 0.45, 0.5)

    handles = []
    if has_svr:
        handles.append(mpatches.Patch(color="#E2E8F0", label=shade.TEXTS["de"]["rec_svr"]))
    if has_bip:
        handles.append(mpatches.Patch(color="#93C5FD", alpha=0.55, label=shade.TEXTS["de"]["rec_bip"]))
    return handles


def draw_bars_with_auto_labels(ax, xi, bars, line_series, label, y_span):
    bar_container = ax.bar(
        xi, bars, width=0.52, facecolor="#DBEAFE", edgecolor="#1E3A8A",
        linewidth=1.1, label=label, zorder=2,
    )
    offset = y_span * 0.018
    for index, bar in enumerate(bar_container):
        value = float(bars[index])
        if np.isnan(value):
            continue
        line_values = [
            float(series[index]) for series in line_series
            if np.isfinite(series[index])
        ]
        top = max(value, 0.0)
        bottom = min(value, 0.0)
        above = min((v - top for v in line_values if v > top), default=0.0)
        below = min((bottom - v for v in line_values if v < bottom), default=0.0)
        place_above = above >= below
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            top + offset if place_above else bottom - offset,
            charts.fmt_num(value, True),
            ha="center",
            va="bottom" if place_above else "top",
            fontsize=6.2,
            color="#1E3A8A",
            fontweight="bold",
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 1.2},
            zorder=5,
        )


def main():
    y_gdp, q_gdp = load("0001"), load("0002")
    real = values(y_gdp, ["DG", "VGR014", "VGRPVK"])
    real.update(values(q_gdp, ["DG", "WERTORG", "VGR014", "VGRPVK"]))
    sector_files = [os.path.join(CACHE, f"81000-{name}.csv") for name in ("0013", "0014")]
    sectors = {key: {} for key in ("pg", "bau", "hvg")}
    if all(os.path.isfile(path) for path in sector_files):
        y_sector, q_sector = load("0013"), load("0014")
        for key, sector_code in (("pg", "WZ08-B-18"), ("bau", "WZ08-F"), ("hvg", "WZ08-G-01")):
            sectors[key] = values(y_sector, ["DG", "BWS001", "VGRPKM", sector_code])
            sectors[key].update(values(q_sector, ["DG", "WERTORG", "BWS001", "VGRPKM", sector_code]))
    else:
        print("Sektorlinien fehlen: erst python scripts/dump_destatis_cache.py ausführen.")

    quarters = sorted(t for t in real if "-Q" in t)
    years = [str(y) for y in range(2019, 2026)]
    quarter_view = quarters[-5:]
    periods = years + [""] + quarter_view
    labels = years + [""] + [f"Q{p[-1]} {p[2:4]}" for p in quarter_view]
    bars = growth_values(real, periods)
    lines = {key: growth_values(series, periods) for key, series in sectors.items()}

    t = dict(charts.TEXTS["de"])
    t["p1_l"] = ("Reales BIP", "Produzierendes Gewerbe (ohne Baugewerbe)", "Baugewerbe", "Handel, Verkehr, Gastgewerbe")
    data = {"xi": np.arange(len(periods)), "xl_bip": labels, "bip_r": bars, **lines}
    bip_negative_periods = {
        period for period in real
        if np.isfinite(yoy(real, period)) and yoy(real, period) < 0
    }
    fig, ax = plt.subplots(figsize=(12, 6), dpi=220, facecolor="white")
    plt.subplots_adjust(left=0.07, right=0.98, top=0.69, bottom=0.20)
    shading_handles = add_recession_shading(ax, periods, bip_negative_periods)
    charts.draw_p1(ax, t, data)
    handles, legend_labels = ax.get_legend_handles_labels()
    ax.yaxis.grid(False)
    ax.axvline(len(years) + 0.5, color="#94A3B8", linestyle="--", linewidth=0.9, zorder=1)
    ax.legend(handles + shading_handles, legend_labels + [h.get_label() for h in shading_handles],
              loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=6.9)
    fig.text(0.07, 0.035, f"Quelle: Statistisches Bundesamt (VGR) | Stand: {datetime.now():%d.%m.%Y}", fontsize=8, color="#64748B")
    fig.savefig(os.path.join(CACHE, "preview_01_entstehung.png"), dpi=220, bbox_inches="tight")
    plt.close(fig)

    y_use, q_use = load("0019"), load("0020")
    use_series = {
        "Nominales BIP": "VGR014",
        "Konsumausgaben der privaten Haushalte": "VGR026",
        "Konsumausgaben des Staates": "VGR015",
        "Ausrüstungsinvestitionen": "VGR008",
        "Bauinvestitionen": "VGR009",
        "Exporte": "EXP001",
        "Importe": "IMP001",
    }
    use_values = {}
    for label, code in use_series.items():
        price_basis = "VGRJPM" if label == "Nominales BIP" else "VGRPKM"
        use_values[label] = values(y_use, ["DG", code, price_basis])
        use_values[label].update(values(q_use, ["DG", "WERTORG", code, price_basis]))
    use_data = {
        label: growth_values(series, periods)
        for label, series in use_values.items()
    }

    fig, ax = plt.subplots(figsize=(12, 6), dpi=220, facecolor="white")
    plt.subplots_adjust(left=0.07, right=0.98, top=0.69, bottom=0.20)
    ylo, yhi, yt, _ = charts.sync_ylim_like_plotly(np.concatenate(list(use_data.values())))
    charts.style_panel(ax, t["p2_t"], t["p2_s"], ylo, yhi, yt, t["comma"], title_y=1.52, sub_y=1.43)
    line_labels = [label for label in use_series if label != "Nominales BIP"]
    draw_bars_with_auto_labels(
        ax,
        data["xi"],
        use_data["Nominales BIP"],
        [use_data[label] for label in line_labels],
        "Nominales BIP",
        yhi - ylo,
    )
    for label, color in (
        ("Konsumausgaben der privaten Haushalte", "#059669"),
        ("Konsumausgaben des Staates", "#D97706"),
        ("Ausrüstungsinvestitionen", "#7C3AED"),
        ("Bauinvestitionen", "#0284C7"),
        ("Exporte", "#DC2626"),
        ("Importe", "#64748B"),
    ):
        ax.plot(data["xi"], use_data[label], color=color, lw=1.7, label=label, zorder=3)
    ax.set_xticks(data["xi"])
    ax.set_xticklabels(data["xl_bip"])
    ax.axvline(len(years) + 0.5, color="#94A3B8", linestyle="--", linewidth=0.9, zorder=1)
    use_shading_handles = add_recession_shading(ax, periods, bip_negative_periods)
    ax.yaxis.grid(False)
    handles, legend_labels = ax.get_legend_handles_labels()
    ax.legend(handles + use_shading_handles, legend_labels + [h.get_label() for h in use_shading_handles],
              loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=6.9)
    fig.text(0.07, 0.035, f"Quelle: Statistisches Bundesamt (VGR) | Stand: {datetime.now():%d.%m.%Y}", fontsize=8, color="#64748B")
    fig.savefig(os.path.join(CACHE, "preview_02_verwendung.png"), dpi=220, bbox_inches="tight")
    plt.close(fig)

    print("Bruttoinlandsprodukt: Verwendung (Veränderung zum Vorjahr in %)")
    table_periods = years + quarter_view
    table_labels = years + [f"Q{period[-1]} {period[2:4]}" for period in quarter_view]
    print("Zeitraum | " + " | ".join(use_series))
    for period, label in zip(table_periods, table_labels):
        row = [charts.fmt_num(yoy(use_values[name], period), True) for name in use_series]
        print(f"{label} | " + " | ".join(row))
    print("Gespeichert: data/cache/preview_01_entstehung.png")
    print("Gespeichert: data/cache/preview_02_verwendung.png")


if __name__ == "__main__":
    main()