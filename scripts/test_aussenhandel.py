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

def check_table(tbl):
    print(f"\n==================== TEST {tbl} ====================")
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": tbl, "area": "all", "compress": "false", "format": "ffcsv", "language": "de", "startyear": "2024"}
    r = requests.post(f"{G_BASE}/tablefile", headers=headers, data=data, timeout=60)
    raw = _extract(r)
    if raw.lstrip().startswith("{"):
        rj = requests.post(f"{G_BASE}/tablefile", headers=headers, data={**data, "job": "true"}, timeout=60)
        print("Job-Status:", rj.text[:300])
        m = re.search(r"([0-9A-Z\-]+_[0-9]+)", str(json.loads(rj.text).get("Status", {}).get("Content", "")))
        if not m:
            return
        for _ in range(30):
            time.sleep(3)
            txt = _extract(requests.post(f"{G_BASE}/resultfile", headers=headers, data={"name": m.group(1), "area": "all", "compress": "false", "language": "de"}, timeout=60))
            if not txt.lstrip().startswith("{"):
                raw = txt
                break
    rows = [row for row in csv.reader(io.StringIO(raw), delimiter=";", quotechar='"') if len(row) >= 5]
    if len(rows) < 3:
        print("Keine Daten / Fehler:", raw[:300])
        return
    hdr = [h.strip() for h in rows.pop(0)]
    df = pd.DataFrame([row[:len(hdr)] for row in rows if len(row) >= len(hdr)], columns=hdr)
    print("Spalten:", hdr)
    for c in hdr:
        if any(k in c.lower() for k in ("attribute", "value_variable")):
            uniques = df[c].astype(str).unique().tolist()
            print(f"\n--- {c} ({len(uniques)} Werte) ---")
            for u in uniques[:60]:
                if any(w in u.lower() for w in ("china", "insgesamt", "kraftwagen", "metall", "stahl", "chem", "ausfuhr", "einfuhr", "wert", "gp", "wz", "st-", "egw")):
                    print(" ", u)
            if len(uniques) <= 25:
                for u in uniques:
                    print("  [ALL]", u)

check_table("51000-0008")
