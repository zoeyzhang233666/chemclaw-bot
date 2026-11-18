# -*- coding: utf-8 -*-
"""Minimal, dependency-free HTTP helper used by every fetcher in this skill.

Design rules:
  * Every request is logged into a manifest (url, status, sha256, bytes, fetched_at)
    so the study can prove *which* data version it used.
  * No silent retries beyond `retries`, no value invention: failures raise.
"""
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _decode(raw):
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


def fetch(url, referer=None, timeout=40, retries=3, sleep_base=0.6, manifest=None, tag=""):
    """GET a URL, return decoded text. Records request into `manifest` list if given."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": referer or url,
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                status = r.status
            text = _decode(raw)
            if manifest is not None:
                manifest.append({
                    "tag": tag, "url": url, "status": status, "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest()[:16],
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            return text
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (404, 410):
                raise
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(sleep_base * (i + 1) + random.random() * 0.4)
    raise RuntimeError(f"fetch failed after {retries}: {url} :: {last}")


def save_manifest(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def file_sha256(path, n=16):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]
