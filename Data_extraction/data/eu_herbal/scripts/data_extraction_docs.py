import hashlib, json, re, threading, time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_file

JSONL = "data/eu_herbal/related_documents.jsonl"
PDF_DIR = Path("data/eu_herbal/pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)
MIN_DELAY = 8            # seconds between requests to EMA
CONTACT = "you@example.com"
ALLOWED_HOST = "ema.europa.eu"

app = Flask(__name__)
lock = threading.Lock()
last_request = 0.0
blocked_until = 0.0
session = requests.Session()
session.headers["User-Agent"] = f"Research-Downloader/1.0 ({CONTACT})"


class RateLimited(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


def allowed(url):
    host = urlparse(url).hostname or ""
    return host == ALLOWED_HOST or host.endswith("." + ALLOWED_HOST)


def is_pdf(b):
    return b[:1024].lstrip().startswith(b"%PDF")


def cache_path(url):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlparse(url).path).name)[:100] or "doc"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return PDF_DIR / f"{hashlib.sha1(url.encode()).hexdigest()[:10]}_{name}"


def ema_get(url):
    """One polite request. Raises RateLimited instead of sleeping on 429."""
    global last_request, blocked_until
    with lock:
        now = time.monotonic()
        if now < blocked_until:
            raise RateLimited(int(blocked_until - now) + 1)
        wait = MIN_DELAY - (now - last_request)
        if wait > 0:
            time.sleep(wait)
        r = session.get(url, timeout=90)
        last_request = time.monotonic()
        if r.status_code == 429:
            ra = r.headers.get("Retry-After", "")
            secs = int(ra) if ra.isdigit() else 600
            blocked_until = time.monotonic() + secs
            raise RateLimited(secs)
        r.raise_for_status()
        return r


def find_pdf_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("#")[0]
        if href in seen or not urlparse(href).path.lower().endswith(".pdf"):
            continue
        m = re.search(r"(?:_|-)([a-z]{2})\.pdf$", urlparse(href).path.lower())
        if m and m.group(1) != "en":
            continue
        seen.add(href)
        out.append(href)
    return out


def fetch_pdf(url):
    """Return a local path to the PDF, using the cache when possible."""
    path = cache_path(url)
    if path.exists():
        return path
    r = ema_get(url)
    if not is_pdf(r.content):
        return None
    path.write_bytes(r.content)
    return path


@app.errorhandler(RateLimited)
def on_rate_limit(e):
    resp = jsonify(error="EMA rate limit", retry_after_seconds=e.seconds)
    resp.status_code = 429
    resp.headers["Retry-After"] = str(e.seconds)
    return resp


@app.get("/download")
def download():
    """GET /download?url=<direct PDF url>"""
    url = request.args.get("url", "")
    if not allowed(url):
        return jsonify(error="Only ema.europa.eu URLs are allowed"), 400
    path = fetch_pdf(url)
    if not path:
        return jsonify(error="URL is not a PDF"), 422
    return send_file(path, mimetype="application/pdf",
                     as_attachment=True, download_name=path.name)


@app.get("/document/<int:line>")
def document(line):
    """GET /document/56  -> line 56 of the JSONL (1-based)."""
    with open(JSONL, encoding="utf-8") as f:
        for i, text in enumerate(f, 1):
            if i == line:
                item = json.loads(text)
                break
        else:
            return jsonify(error="Line out of range"), 404

    url = item["document_url"]
    if not allowed(url):
        return jsonify(error="Blocked host"), 400

    cached = cache_path(url)
    if cached.exists():
        return send_file(cached, mimetype="application/pdf",
                         as_attachment=True, download_name=cached.name)

    r = ema_get(url)
    if is_pdf(r.content):
        cached.write_bytes(r.content)
        return send_file(cached, mimetype="application/pdf",
                         as_attachment=True, download_name=cached.name)

    links = find_pdf_links(r.text, r.url)
    if not links:
        return jsonify(name=item.get("name"), error="No PDF link found"), 404
    if len(links) == 1:
        path = fetch_pdf(links[0])
        if path:
            return send_file(path, mimetype="application/pdf",
                             as_attachment=True, download_name=path.name)
    return jsonify(name=item.get("name"), pdfs=[
        f"{request.host_url}download?url={l}" for l in links])


if __name__ == "__main__":
    app.run(port=5000)