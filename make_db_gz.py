import gzip
import shutil
from pathlib import Path

src = Path("data/olist.db")
dst = Path("data/olist.db.gz")

with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=9) as f_out:
    shutil.copyfileobj(f_in, f_out)

print(f"{src.stat().st_size / 1e6:.1f} MB  ->  {dst.stat().st_size / 1e6:.1f} MB")