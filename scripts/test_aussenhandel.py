import os, json, requests

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
META_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/metadata"
CAT_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/catalogue"

headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}

for tbl in ["51000-0002", "51000-0008", "51000-0010"]:
    r = requests.post(f"{META_BASE}/table", headers=headers, data={"name": tbl, "area": "all", "language": "de"}, timeout=30)
    print(f"\n=== METADATA {tbl} ===")
    txt = r.text
    print(txt[:1800])

for var in ["ST-2-4", "WAM8", "GP09M2", "GP19M2"]:
    r = requests.post(f"{CAT_BASE}/values2variable", headers=headers, data={"name": var, "area": "all", "language": "de", "pagelength": "250"}, timeout=30)
    if "Object" in r.text and len(r.text) > 200:
        print(f"\n=== VALUES {var} ===")
        for line in json.dumps(r.json(), ensure_ascii=False).split("},"):
            if any(k in line.lower() for k in ("china", "kraftwagen", "metall", "stahl", "chem", "insgesamt")):
                print(" ", line[:220])
