import os, json, requests

D_USER = os.environ.get("DESTATIS_USER", "")
D_PASS = os.environ.get("DESTATIS_PASS", "")
META_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/metadata"
CAT_BASE = "https://www-genesis." + "destatis.de/genesisWS/rest/2020/catalogue"
headers = {"username": D_USER, "password": D_PASS, "Content-Type": "application/x-www-form-urlencoded"}

for tbl in ["51000-0004", "51000-0006", "51000-0008"]:
    r = requests.post(f"{META_BASE}/table", headers=headers, data={"name": tbl, "area": "all", "language": "de"}, timeout=30).json()
    obj = r.get("Object", {})
    print(f"\n=== {tbl}: {obj.get('Content')} ===")
    print("Rows:", json.dumps(obj.get("Structure", {}).get("Rows"), ensure_ascii=False))
    for row in (obj.get("Structure", {}).get("Rows") or []):
        code = row.get("Code")
        if code not in ("JAHR", "MONAT"):
            rv = requests.post(f"{CAT_BASE}/values2variable", headers=headers, data={"name": code, "area": "all", "language": "de", "pagelength": "500"}, timeout=30).json()
            for item in (rv.get("List") or []):
                c_str, t_str = str(item.get("Code", "")), str(item.get("Content", ""))
                if any(k in t_str.lower() for k in ("china", "kraftwagen", "metall", "eisen", "stahl", "chem", "insgesamt")):
                    print(f"  [{code}] {c_str} -> {t_str}")
