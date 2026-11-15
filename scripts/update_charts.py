import os, io, zipfile, requests
import pandas as pd

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://destatis.de"

def inspect_destatis(table):
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    r = requests.post(G_URL, headers=headers, data=data, timeout=45)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        raw = zf.read(csv_name).decode("utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln.count(";") >= 4]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", decimal=",", on_bad_lines="skip")
    print(f"\n=== DESTATIS {table} (Zeilen: {len(df)}) ===")
    print(df.head(3).to_string())
    for c in df.columns:
        if "attribute_code" in c or "attribute_label" in c or "variable_label" in c:
            print(f"  {c}: {list(df[c].dropna().unique()[:8])}")

def inspect_bbk(pattern):
    flow, k = pattern.split(".", 1)
    url = f"https://bundesbank.de{flow}/{k}?format=csv&lang=de&lastNObservations=1"
    r = requests.get(url, timeout=25)
    print(f"\n=== BBK {pattern} (Status: {r.status_code}) ===")
    for ln in r.text.splitlines()[:15]:
        print(" ", ln[:180])

inspect_destatis("81000-0011")
inspect_destatis("81000-0020")
inspect_destatis("61121-0002")

inspect_bbk("BBDE1.M.DE.Y.BAA1..G.C..A")
inspect_bbk("BBDE1.M.DE.Y.BPA1..G.C..A")
inspect_bbk("BBDE1.M.DE.Y.BVA1..G.C..A")
inspect_bbk("BBDE1.M.DE.S.ABA1.A00000000.U.A.A00.A")
inspect_bbk("BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL")
