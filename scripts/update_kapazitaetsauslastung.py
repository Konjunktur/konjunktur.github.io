import os, io, csv, requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import plotly.graph_objects as go

os.makedirs("static/kapazitaetsauslastung", exist_ok=True)

TEXTS = {
    "de": {
        "title": "Kapazitätsauslastung im Verarbeitenden Gewerbe",
        "sub": "In % der betriebsüblichen Vollauslastung (Datenerhebung am Anfang des Quartals)",
        "leg_q": "Quartalswerte",
        "leg_mean": "Mittelwert 1. Q. 1991 – 4. Q. 2019",
        "ylabel": "in %",
        "xlabel": "Quartalswerte",
        "src": "Quelle: Deutsche Bundesbank (EU-Kommission / DG ECFIN) | Stand: ",
        "date_fmt": "%d.%m.%Y",
        "comma": True,
        "sfx": ""
    },
    "en": {
        "title": "Capacity Utilisation in Manufacturing",
        "sub": "In % of full operating capacity (survey conducted at the beginning of the quarter)",
        "leg_q": "Quarterly values",
        "leg_mean": "Mean Q1 1991 – Q4 2019",
        "ylabel": "in %",
        "xlabel": "Quarterly values",
        "src": "Source: Deutsche Bundesbank (European Commission / DG ECFIN) | As of: ",
        "date_fmt": "%Y-%m-%d",
        "comma": False,
        "sfx": "_en"
    }
}

def fmt_val(val, use_comma):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    s = f"{float(val):.1f}"
    return s.replace(".", ",") if use_comma else s

def fetch_bundesbank_caputil():
    base = "https://api.statistiken." + "bundesbank.de/rest/data/"
    urls = [
        base + "BBXS1/Q.DE.Y.EUBUCS.MANU.MAN013.TT.PCT.I00?format=sdmx_csv",
        base + "BBXS1/Q.DE..EUBUCS.MANU.MAN013.TT.PCT.I00?format=sdmx_csv",
        base + "BBDE1/Q.DE.Y.BAA1.A2P000000.G.C.I00.A?format=sdmx_csv",
        base + "BBDE1/Q.DE..BAA1.A2P000000.G.C.I00.A?format=sdmx_csv",
    ]
    raw_txt = ""
    errs = []
    for u in urls:
        r = requests.get(u, timeout=60)
        if r.status_code == 200 and "-Q" in r.text:
            raw_txt = r.text
            break
        errs.append(f"{r.status_code}: {u}")
    if not raw_txt:
        raise RuntimeError("Bundesbank-Quartalsreihe nicht geladen: " + " | ".join(errs))

    sep = ";" if ";" in raw_txt.splitlines()[0] else ","
    rows = list(csv.reader(io.StringIO(raw_txt), delimiter=sep))
    hdr = [h.strip() for h in rows.pop(0)]
    t_idx = hdr.index("TIME_PERIOD")
    v_idx = hdr.index("OBS_VALUE")
    adj_idx = hdr.index("BBK_STD_ADJUSTMENT") if "BBK_STD_ADJUSTMENT" in hdr else -1

    records = []
    for row in rows:
        if len(row) <= max(t_idx, v_idx):
            continue
        tp = row[t_idx].strip()
        if "-Q" not in tp:
            continue
        val_str = row[v_idx].strip().replace(",", ".")
        if val_str in ("", ".", "NaN", "nan"):
            continue
        try:
            adj_prio = 0 if (adj_idx >= 0 and row[adj_idx].strip() == "N") else (1 if (adj_idx >= 0 and row[adj_idx].strip() == "Y") else 2)
            records.append((tp, adj_prio, float(val_str)))
        except ValueError:
            continue

    df = pd.DataFrame(records, columns=["Q", "PRIO", "V"]).sort_values(["Q", "PRIO"]).drop_duplicates(subset=["Q"], keep="first")
    return df.set_index("Q")["V"]

def render_caputil_charts(lang, ser):
    t = TEXTS[lang]
    use_c = t["comma"]
    plt.rcParams.update({"font.sans-serif": "DejaVu Sans"})
    now_str = datetime.now().strftime(t["date_fmt"])

    mean_ser = ser[(ser.index >= "1991-Q1") & (ser.index <= "2019-Q4")].dropna()
    mean_val = float(mean_ser.mean())

    plot_ser = ser[ser.index >= "2019-Q1"].dropna()
    quarters = list(plot_ser.index)
    y_vals = [float(v) for v in plot_ser.values]
    x_idx = np.arange(len(quarters))

    min_i = int(np.argmin(y_vals))
    max_i = int(np.argmax(y_vals))
    key_indices = sorted(list({0, min_i, max_i, len(y_vals) - 1}))

    all_v = y_vals + [mean_val]
    ymin_raw, ymax_raw = min(all_v), max(all_v)
    ymin = np.floor((ymin_raw - 2.2) / 2.0) * 2.0
    ymax = np.ceil((ymax_raw + 2.5) / 2.0) * 2.0
    step = 2.0 if (ymax - ymin) <= 24 else 4.0

    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=300, facecolor="white")
    plt.subplots_adjust(left=0.10, right=0.94, top=0.78, bottom=0.22)
    fig.suptitle(t["title"], x=0.10, y=0.96, ha="left", fontsize=11.5, fontweight="bold", color="#0F172A")
    fig.text(0.10, 0.915, t["sub"], ha="left", fontsize=8.0, color="#64748B")

    ax.set_facecolor("#F8FAFC")
    ax.set_ylim(ymin, ymax)
    ax.set_yticks(np.arange(ymin, ymax + step * 0.1, step))
    ax.set_xlim(-0.8, len(quarters) + 1.4)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: fmt_val(x, use_c)))
    ax.tick_params(axis="y", colors="#475569", labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors="#475569", labelsize=8.0, rotation=45, length=3, color="#CBD5E1")
    ax.yaxis.grid(True, color="#E2E8F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#94A3B8")

    ax.plot(x_idx, y_vals, color="#1B3A6B", lw=2.3, label=t["leg_q"], zorder=3)
    ax.axhline(mean_val, color="#D97706", lw=1.8, linestyle="--", label=t["leg_mean"], zorder=2)
    ax.scatter([x_idx[i] for i in key_indices], [y_vals[i] for i in key_indices], color="#1B3A6B", s=22, zorder=4)

    mean_x = len(quarters) * 0.42
    ax.text(mean_x, mean_val + (ymax - ymin) * 0.025, fmt_val(mean_val, use_c), fontsize=8.0, fontweight="bold", color="#D97706", ha="center", va="bottom", zorder=5)

    for idx_k in key_indices:
        yv = y_vals[idx_k]
        if idx_k == len(y_vals) - 1:
            ax.text(x_idx[idx_k] + 0.35, yv, fmt_val(yv, use_c), fontsize=7.6, fontweight="bold", color="#1B3A6B", ha="left", va="center", zorder=5)
            continue
        is_low = (idx_k == min_i and yv < y_vals[0])
        dy = -(ymax - ymin) * 0.045 if is_low else (ymax - ymin) * 0.032
        va = "top" if is_low else "bottom"
        ha = "left" if idx_k == 0 else "center"
        ax.text(x_idx[idx_k], yv + dy, fmt_val(yv, use_c), fontsize=7.6, fontweight="bold", color="#0F172A", ha=ha, va=va, zorder=5)

    tick_pos = [i for i in range(len(quarters)) if i % 2 == 0 or i == len(quarters) - 1]
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([quarters[i] for i in tick_pos], ha="right")

    ax.text(-0.01, 1.02, t["ylabel"], transform=ax.transAxes, ha="right", va="bottom", fontsize=7.8, color="#475569")
    ax.text(0.5, -0.22, t["xlabel"], transform=ax.transAxes, ha="center", va="top", fontsize=8.3, color="#475569")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.01, 1.02), ncol=2, frameon=False, fontsize=7.8, columnspacing=1.5)
    fig.text(0.10, 0.015, f"{t['src']}{now_str}", fontsize=7.2, color="#64748B")
    fig.text(0.94, 0.015, "T.H.", fontsize=8.0, color="#94A3B8", ha="right")
    plt.savefig(f"static/kapazitaetsauslastung/kapazitaetsauslastung{t['sfx']}.png", dpi=300)
    plt.close()

    fp = go.Figure()
    cd_q = [fmt_val(v, use_c) for v in y_vals]
    fp.add_trace(go.Scatter(
        x=quarters, y=[round(v, 1) for v in y_vals], customdata=cd_q,
        name=t["leg_q"], mode="lines", line=dict(color="#1B3A6B", width=2.4),
        hovertemplate=f"{t['leg_q']}: <b>%{{customdata}} %</b><extra></extra>"
    ))
    fp.add_trace(go.Scatter(
        x=quarters, y=[round(mean_val, 1)] * len(quarters), customdata=[fmt_val(mean_val, use_c)] * len(quarters),
        name=t["leg_mean"], mode="lines", line=dict(color="#D97706", width=1.9, dash="dash"),
        hovertemplate=f"{t['leg_mean']}: <b>%{{customdata}} %</b><extra></extra>"
    ))

    pos_list = []
    for i in key_indices:
        if i == len(y_vals) - 1:
            pos_list.append("middle right")
        elif i == min_i and y_vals[i] < y_vals[0]:
            pos_list.append("bottom center")
        else:
            pos_list.append("top center")

    fp.add_trace(go.Scatter(
        x=[quarters[i] for i in key_indices],
        y=[round(y_vals[i], 1) for i in key_indices],
        text=[fmt_val(y_vals[i], use_c) for i in key_indices],
        mode="markers+text",
        textposition=pos_list,
        textfont=dict(size=10, color="#0F172A", family="DejaVu Sans, sans-serif"),
        marker=dict(size=6, color="#1B3A6B"),
        showlegend=False, hoverinfo="skip"
    ))

    t_vals = [quarters[i] for i in tick_pos]
    fp.update_layout(
        title=dict(text=f"<b>{t['title']}</b><br><span style='font-size:11.5px;color:#475569;'>{t['sub']}</span>", x=0.03, y=0.96, yanchor="top", font=dict(size=15, color="#0F172A", family="DejaVu Sans, sans-serif")),
        plot_bgcolor="#F8FAFC", paper_bgcolor="white", hovermode="x unified", dragmode=False,
        hoverlabel=dict(bgcolor="white", bordercolor="#CBD5E1", font=dict(size=10.5, color="#0F172A"), namelength=0),
        legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0)", font=dict(size=10.5, color="#1E293B")),
        margin=dict(l=58, r=42, t=125, b=85), height=460,
        annotations=[
            dict(
                text=f"<b>{fmt_val(mean_val, use_c)}</b>",
                x=0.42, y=mean_val, xref="paper", yref="y", showarrow=False,
                yanchor="bottom", yshift=4, font=dict(size=11, color="#D97706")
            ),
            dict(text=f"{t['src']}{now_str}", x=0.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=10, color="#64748B"), xanchor="left"),
            dict(text="T.H.", x=1.0, y=-0.24, xref="paper", yref="paper", showarrow=False, font=dict(size=10.5, color="#94A3B8"), xanchor="right")
        ]
    )
    fp.update_xaxes(type="category", fixedrange=True, tickangle=-45, showgrid=False, linecolor="#94A3B8", tickmode="array", tickvals=t_vals, ticktext=t_vals, tickfont=dict(size=10.5, color="#475569"))
    fp.update_yaxes(range=[ymin, ymax], dtick=step, fixedrange=True, gridcolor="#E2E8F0", tickfont=dict(size=10.5, color="#475569"))
    if use_c:
        fp.update_layout(separators=",.")
    out_html = f"static/kapazitaetsauslastung/kapazitaetsauslastung{t['sfx']}.html"
    fp.write_html(out_html, include_plotlyjs="cdn", config={"displayModeBar": False, "responsive": True})
    with open(out_html, "r", encoding="utf-8") as fh:
        html_s = fh.read().replace("<body>", '<body style="margin:0;padding:0;overflow:hidden;">')
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(html_s)

def main():
    ser = fetch_bundesbank_caputil()
    render_caputil_charts("de", ser)
    render_caputil_charts("en", ser)
    print(f"[OK] Kapazitätsauslastung (DE & EN) bis {ser.index[-1]} erzeugt.")

if __name__ == "__main__":
    main()
