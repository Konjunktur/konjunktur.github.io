import os
import sys

sys.path.insert(0, "scripts")
from update_charts import get_destatis

TABLES = [
    "81000-0001",  # BIP Entstehung (Quartale)
    "81000-0002",  # BIP Entstehung (Jahre)
    "81000-0019",  # BIP Verwendung (Quartale)
    "81000-0020",  # BIP Verwendung (Jahre)
]

os.makedirs("data/cache", exist_ok=True)

for table_id in TABLES:
    df = get_destatis(table_id, "2018")
    out_path = f"data/cache/{table_id}.csv"
    df.to_csv(out_path, index=False, sep=";")
    print(f"[OK] {out_path} gespeichert ({len(df)} Zeilen)")
