"""Import cover images already identified on Wake Tech's public LibGuide.
Run locally or via the scheduled GitHub Action. Only downloads explicit listed URLs.
Never downloads arbitrary URLs from untrusted input supplied by website visitors.
"""
import io, json, time
from pathlib import Path
import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "cover_sources.json").read_text())
OUT = ROOT / "static" / "covers"
OUT.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; GameOn-EasternWake-CoverSync/1.0)"})
failed = []
saved = 0
for entry in SOURCES:
    item_id = entry["item_id"]
    dest = OUT / ("cover_" + item_id.split("-")[-1] + ".webp")
    if dest.exists() and dest.stat().st_size > 500:
        print(f"KEEP {dest.name}")
        continue
    try:
        url = entry.get("url")
        if not url and entry.get("page_url"):
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            page = session.get(entry["page_url"], timeout=25)
            page.raise_for_status()
            soup = BeautifulSoup(page.text, "html.parser")
            og = soup.find("meta", attrs={"property":"og:image"}) or soup.find("meta", attrs={"name":"twitter:image"})
            if not og or not og.get("content"):
                raise ValueError("No product cover metadata")
            url = urljoin(entry["page_url"], og["content"])
        if not url:
            raise ValueError("No image URL")
        if not url.startswith("https://"):
            raise ValueError("HTTPS required")
        res = session.get(url, timeout=25, allow_redirects=True)
        res.raise_for_status()
        if len(res.content) > 12_000_000:
            raise ValueError("image too large")
        im = Image.open(io.BytesIO(res.content))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((650, 650), Image.Resampling.LANCZOS)
        im.save(dest, "WEBP", quality=85, method=6)
        saved += 1
        print(f"SAVED {dest.name} ({dest.stat().st_size} bytes)")
    except Exception as err:
        print(f"FAILED {item_id}: {err}")
        failed.append(item_id)
    time.sleep(.2)
print(f"Saved: {saved}; failed: {len(failed)}")
if failed:
    print("Unresolved: " + ", ".join(failed))
