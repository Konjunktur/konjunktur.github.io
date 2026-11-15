import os, io, re, csv, json, time, zipfile, requests
import pandas as pd

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/data"

def _extract(resp):
    if resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            return zf.read(next(n for n in zf.namelist() if n.endswith(".csv"))).decode("utf-8", errors="replace")
    return resp.text

def inspect_table(table, startyear="2023"):
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": startyear}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    raw = _extract(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        for _ in range(24):
            time.sleep(2.5)
            txt = _extract(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    hdr = [h.strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)
    print(f"\n=== {table} (Zeilen: {len(df)}) ===")
    for c in hdr:
        if any(k in c.lower() for k in ("time", "attribute", "value_variable")):
            vals = [v for v in df[c].astype(str).unique() if v.strip()][:15]
            print(f"  {c}: {vals}")

for tbl, yr in [("81000-0015", "2023"), ("81000-0016", "2023"), ("81000-0019", "2023"), ("81000-0020", "2023"), ("44111-0005", "2024"), ("44111-0006", "2024"), ("44111-0007", "2024"), ("44111-0008", "2024")]:
    try:
        inspect_table(tbl, yr)
    except Exception as e:
        print(f"=== {tbl} FEHLER: {e} ===")
