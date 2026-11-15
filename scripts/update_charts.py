import os, io, zipfile, requests

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
G_URL = "https://destatis.de"

def inspect_destatis(table, extra=None):
    headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"name": table, "area": "all", "compress": "false", "format": "ffcsv", "language": "de"}
    if extra:
        data.update(extra)
    r = requests.post(G_URL, headers=headers, data=data, timeout=45)
    print(f"\n=== DESTATIS {table} extra={extra} (ZIP={r.content[:2] == b'PK'}, Bytes={len(r.content)}) ===")
    if r.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
            raw = zf.read(csv_name).decode("utf-8", errors="replace")
    else:
        raw = r.text
    for ln in raw.splitlines()[:12]:
        print(" ", ln[:180])

def inspect_bbk(pattern):
    flow, k = pattern.split(".", 1)
    url = f"https://bundesbank.de{flow}/{k}?format=csv&lang=de&lastNObservations=1"
    r = requests.get(url, timeout=25)
    print(f"\n=== BBK {pattern} (Status: {r.status_code}) ===")
    for ln in r.text.splitlines()[:20]:
        print(" ", ln[:180])

inspect_destatis("81000-0011")
inspect_destatis("81000-0011", {"startyear": "2021"})
inspect_destatis("81000-0020", {"startyear": "2021"})
inspect_destatis("61121-0002", {"startyear": "2024"})

inspect_bbk("BBDE1.M.DE.Y.BAA1..G.C..A")
inspect_bbk("BBDE1.M.DE.Y.BPA1..G.C..A")
inspect_bbk("BBDE1.M.DE.Y.BVA1..G.C..A")
inspect_bbk("BBDE1.M.DE.S.ABA1.A00000000.U.A.A00.A")
inspect_bbk("BBFBOPV.M.N.DE.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL")
