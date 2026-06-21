#!/usr/bin/env python3
"""
Image fetcher for "Follow the Money" reel pipeline.
Searches Wikimedia Commons for org-related images and downloads them
into a reel's images/ folder.

Usage:
    python fetch_images.py "FIFA" reels/ftm-fifa-2026-06-21
    python fetch_images.py "Bundesliga" reels/ftm-bundesliga-2026-06-21 --count 8
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MIN_WIDTH    = 800   # skip thumbnails and icons
MAX_IMAGES   = 8


def search_commons(query: str, limit: int = 20) -> list[dict]:
    """Search Wikimedia Commons and return image metadata dicts."""
    params = urllib.parse.urlencode({
        "action":      "query",
        "generator":   "search",
        "gsrsearch":   query,
        "gsrnamespace": 6,              # File namespace only
        "gsrlimit":    limit,
        "prop":        "imageinfo",
        "iiprop":      "url|mime|size|width|height",
        "format":      "json",
    })
    url = f"{COMMONS_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "follow-the-money-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    pages = data.get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        ii = (page.get("imageinfo") or [{}])[0]
        mime   = ii.get("mime", "")
        width  = ii.get("width", 0)
        url    = ii.get("url", "")
        if mime in ALLOWED_MIME and width >= MIN_WIDTH and url:
            results.append({
                "title": page.get("title", ""),
                "url":   url,
                "mime":  mime,
                "width": width,
            })
    return results


def _ext(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime, ".jpg")


def download_images(org: str, images_dir: Path, count: int = MAX_IMAGES,
                     extra_query: str = "") -> list[Path]:
    """
    Search Commons for `org` (+ optional extra_query terms), download up to
    `count` images into `images_dir`. Returns list of saved paths.
    """
    images_dir.mkdir(parents=True, exist_ok=True)

    query   = f"{org} {extra_query}".strip()
    print(f"  Searching Wikimedia Commons: '{query}'")
    results = search_commons(query, limit=count * 3)

    if not results:
        print(f"  No images found for '{query}' — try a different search term")
        return []

    print(f"  Found {len(results)} candidates, downloading up to {count}...")
    saved: list[Path] = []
    req_headers = {
        "User-Agent": "follow-the-money-bot/1.0",
        "Referer":    "https://commons.wikimedia.org/",
    }

    for i, img in enumerate(results[:count]):
        ext   = _ext(img["mime"])
        dest  = images_dir / f"{i + 1:02d}{ext}"
        try:
            req = urllib.request.Request(img["url"], headers=req_headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                dest.write_bytes(resp.read())
            print(f"  ✓ {dest.name}  ({img['width']}px)  {img['title'][:55]}")
            saved.append(dest)
        except Exception as e:
            print(f"  ✗ {img['title'][:55]} — {e}")

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Wikimedia Commons images for a Follow the Money reel."
    )
    parser.add_argument("org",      help="Organisation name (e.g. 'FIFA')")
    parser.add_argument("reel_dir", help="Reel folder path (e.g. reels/ftm-fifa-2026-06-21)")
    parser.add_argument("--count",  type=int, default=MAX_IMAGES,
                        help=f"Number of images to download (default: {MAX_IMAGES})")
    parser.add_argument("--query",  default="",
                        help="Extra search terms to add (e.g. 'stadium revenue')")
    args = parser.parse_args()

    reel_dir   = Path(args.reel_dir)
    images_dir = reel_dir / "images"

    if not reel_dir.exists():
        print(f"✗ Reel folder not found: {reel_dir}")
        sys.exit(1)

    saved = download_images(args.org, images_dir, count=args.count, extra_query=args.query)

    print()
    if saved:
        print(f"✓ {len(saved)} image(s) saved to {images_dir}")
        print()
        print("  Next step:")
        print(f"    uv run python reel_template/make_reel.py {reel_dir}")
    else:
        print("✗ No images downloaded.")
        print("  Try: python fetch_images.py '<org>' <reel_dir> --query 'stadium logo'")


if __name__ == "__main__":
    main()
