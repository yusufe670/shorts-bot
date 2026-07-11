#!/usr/bin/env python3
"""
Telifsiz stok video kliplerini indirir (Pexels + Pixabay video API).
Her ikisi de: atıf gerekmez, ticari kullanım serbest.

Ortam değişkenleri: PEXELS_API_KEY, PIXABAY_API_KEY (en az biri)
"""
import json
import os
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read()


def pexels_videos(query, per_page=12):
    """Pexels video ara -> [(url, w, h)] (dikey öncelik)."""
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    out = []
    for orient in ("portrait", "landscape"):
        try:
            u = ("https://api.pexels.com/videos/search?query="
                 + urllib.parse.quote(query)
                 + f"&orientation={orient}&size=medium&per_page={per_page}")
            data = json.loads(_get(u, {"Authorization": key}))
            for v in data.get("videos", []):
                files = [f for f in v.get("video_files", []) if f.get("link")]
                # ~720-1080 yükseklik tercih et
                files.sort(key=lambda f: abs((f.get("height") or 0) - 1280))
                if files:
                    f = files[0]
                    out.append((f["link"], f.get("width") or 0, f.get("height") or 0))
        except Exception as e:
            print("  pexels hata:", str(e)[:100])
    return out


def pixabay_videos(query, per_page=20):
    """Pixabay video ara -> [(url, w, h)]."""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return []
    out = []
    try:
        u = ("https://pixabay.com/api/videos/?key=" + key
             + "&q=" + urllib.parse.quote(query)
             + f"&per_page={per_page}&safesearch=true")
        data = json.loads(_get(u))
        for hit in data.get("hits", []):
            vids = hit.get("videos", {})
            v = vids.get("large") or vids.get("medium") or vids.get("small")
            if v and v.get("url"):
                out.append((v["url"], v.get("width") or 0, v.get("height") or 0))
    except Exception as e:
        print("  pixabay hata:", str(e)[:100])
    return out


def download(url, dest, timeout=90):
    try:
        data = _get(url, timeout=timeout)
        if len(data) > 20000:
            dest.write_bytes(data)
            return True
    except Exception as e:
        print("  indirme hata:", str(e)[:100])
    return False


def fetch_for_queries(queries, dest_dir, want=6):
    """Sorgular için klip URL'leri topla, indir. -> indirilen dosya listesi."""
    seen, urls = set(), []
    for q in queries:
        for src in (pexels_videos, pixabay_videos):
            for (url, w, h) in src(q):
                if url not in seen:
                    seen.add(url); urls.append(url)
        if len(urls) >= want * 3:
            break
    files = []
    for i, url in enumerate(urls):
        if len(files) >= want:
            break
        p = dest_dir / f"clip_{len(files):02d}.mp4"
        if download(url, p):
            files.append(p)
    return files
