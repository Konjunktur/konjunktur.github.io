import os, io, re, csv, json, time, zipfile, requests
import pandas as pd
import numpy as np

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"
BBK_BASE = "https://api.statistiken." + "bundesbank.de/rest/data/"

u = f"{BBK_BASE}BBDL1/M.DE.N.?format=csv&lang=de"
r = requests.get(u, timeout=45)
first_line = next(iter(r.text.splitlines()), "")
sep = ";" if first_line.count(";") >= first_line.count(",") else ","
df = pd.read_csv(io.StringIO(r.text), sep=sep, low_memory=False)
time_col = next(iter(df.columns))
is_date = df[time_col].astype(str).str.match(r"^(19\d{2}|20\d{2})-\d{2}")
meta_df, data_df = df.loc[~is_date], df.loc[is_date]
yms = data_df[time_col].astype(str).str.slice(0, 7).values

s_alo, s_ste, s_alq = pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
for col in df.columns[1:]:
    if str(col).endswith("_FLAGS"):
        continue
    desc = " | ".join(str(x).strip() for x in meta_df[col].dropna().tolist()[:8])
    cl = f"{col} | {desc}".lower()
    if any(ex in cl for ex in ("saisonbereinigt", "kalenderbereinigt", "männer", "frauen", "ausländer", "zugang", "abgang", "anzeige", "index", "geringfügig", "beschäftigte", "sozialversicherungspflichtig", "unterbeschäftigung")):
        continue
    vals = pd.to_numeric(data_df[col].astype(str).str.replace(",", "."), errors="coerce")
    valid = vals.notna()
    if valid.sum() < 36:
        continue
    nums = vals.loc[valid].values
    ser = pd.Series(nums, index=yms[valid]).groupby(level=0).last().sort_index()
    if "arbeitslosenquote" in cl and "alle zivilen" in cl and ("insgesamt" in cl or "deutschland" in cl):
        if s_alq.empty or ser.index[-1] > s_alq.index[-1]:
            s_alq = ser
    elif "quote" not in cl and "%" not in cl:
        scale = 0.001 if np.nanmedian(nums) > 20000 else 1.0
        ser_s = ser * scale
        if "arbeitslose" in cl and ("insgesamt" in cl or "deutschland" in cl):
            if s_alo.empty or ser_s.index[-1] > s_alo.index[-1]:
                s_alo = ser_s
        elif ("gemeldete arbeitsstellen" in cl or "offene stellen" in cl) and ("insgesamt" in cl or "deutschland" in cl):
            if s_ste.empty or ser_s.index[-1] > s_ste.index[-1]:
                s_ste = ser_s

comb = pd.DataFrame({"alo": s_alo, "ste": s_ste, "alq": s_alq}).dropna()
comb["ep"] = comb["alo"] / (comb["alq"] / 100.0)
comb["u"] = comb["alo"] / comb["ep"] * 100.0
comb["v"] = comb["ste"] / comb["ep"] * 100.0
comb["u3"] = comb["u"].rolling(3).mean()
comb["v3"] = comb["v"].rolling(3).mean()
comb["du"] = comb["u3"] - comb["u3"].shift(1).rolling(12).min()
comb["dv"] = comb["v3"].shift(1).rolling(12).max() - comb["v3"]
comb["michez"] = np.minimum(comb["du"], comb["dv"])

print(f"Zeitraum: {comb.index[0]} bis {comb.index[-1]} (n={len(comb)})")
for label, start, end in [
    ("Rezession 1992-93", "1992-01", "1993-12"),
    ("Rezession 2001-03", "2001-01", "2003-12"),
    ("Finanzkrise 2008-09", "2008-01", "2009-12"),
    ("Expansion 2011-19 (Max)", "2011-01", "2019-12"),
    ("Corona 2020", "2020-01", "2020-12"),
    ("Phase 2022-26", "2022-01", "2026-12"),
]:
    sub = comb.loc[start:end, "michez"].dropna()
    if not sub.empty:
        print(f"{label:24s} -> Max: {sub.max():.3f} pp (im Monat {sub.idxmax()})")
