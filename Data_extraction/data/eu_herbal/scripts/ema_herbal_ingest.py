#!/usr/bin/env python3
"""
ema_herbal_ingest.py - EU herbal-medicine corpus builder for IP-SAKTI Sahayak

Sub-commands
  pages     scrape the two overview HTML pages (BeautifulSoup)   -> out/html/*.json
  index     download EMA's machine-readable JSON indexes         -> out/index/*.json
  types     list document "type" values in EMA's documents JSON  (use to tune --match)
  download  fetch HMPC monograph / assessment-report PDFs        -> out/pdfs/ + out/manifest.jsonl
  parse     PDF -> text -> section chunks                        -> out/chunks.jsonl
  all       pages + index + download + parse

Install:  pip install requests beautifulsoup4 pdfplumber
Optional OCR fallback:  pip install pytesseract pdf2image  (plus tesseract + poppler binaries)

Example:
  python ema_herbal_ingest.py --out data/eu_herbal --contact you@example.org all
  python ema_herbal_ingest.py --out data/eu_herbal download --related-jsonl data/eu_herbal/related_documents.jsonl --processed-urls data/eu_herbal/processed_urls.txt --limit 100
"""
import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #
OVERVIEW_PAGES = {  # name -> fallback list of URLs (first one that works is used)
    "ema_herbal_overview": [
        "https://www.ema.europa.eu/en/human-regulatory-overview/herbal-medicinal-products",
        "https://www.ema.europa.eu/en/herbal-medicinal-products",
    ],
    "ec_herbal_overview": [
        "https://health.ec.europa.eu/medicinal-products/herbal-medicinal-products_en",
    ],
}

# EMA publishes its whole website as JSON (refreshed twice a day):
# https://www.ema.europa.eu/en/about-us/about-website/download-website-data-json-data-format
INDEX_URLS = {
    "herbal_medicines": "https://www.ema.europa.eu/en/media/70862",
    "documents_en": "https://www.ema.europa.eu/en/media/67425",  # large file
}

SKIP_EXT = (".xls", ".xlsx", ".doc", ".docx", ".zip", ".csv")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Polite HTTP client
# --------------------------------------------------------------------------- #

class Fetcher:
    def __init__(self, contact, delay=5.0):
        self.delay, self._last = delay, 0.0
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": f"ip-sakti-ingest/0.1 (+{contact})",
            "Accept": "application/json, text/html, application/pdf, */*"
        })

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=0,
            backoff_factor=2,
            allowed_methods=("GET",),
            respect_retry_after_header=False
        )

        self.s.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, url, stream=False):
        for attempt in range(4):
            wait = self.delay - (time.monotonic() - self._last)

            if wait > 0:
                time.sleep(wait)

            r = self.s.get(url, timeout=90, stream=stream)
            self._last = time.monotonic()

            if r.status_code == 429:
                r.close()

                if attempt == 3:
                    r.raise_for_status()

                retry_after = r.headers.get("Retry-After")

                try:
                    wait_time = float(retry_after)
                    if wait_time <= 0:
                        raise ValueError()
                except (TypeError, ValueError):
                    wait_time = 60 * (2 ** attempt)

                wait_time = min(max(wait_time, 60), 300)

                print(
                    f"[429] EMA rate limit reached. "
                    f"Waiting {wait_time:.0f} seconds..."
                )

                time.sleep(wait_time)
                continue

            r.raise_for_status()
            return r

        raise requests.exceptions.RequestException(
            f"Failed to retrieve URL after retries: {url}"
        )

# --------------------------------------------------------------------------- #
# 1. HTML overview pages  (BeautifulSoup)
# --------------------------------------------------------------------------- #
def parse_html(html, url):
    """Turn a page into heading-delimited sections plus a list of document links."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header", "form", "noscript", "aside"]):
        t.decompose()
    root = soup.find("main") or soup.body or soup
    h1 = root.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (soup.title.string.strip() if soup.title else url)

    sections, cur = [], {"heading": title, "level": 1, "text": []}
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]):
        if el.name != "table" and el.find_parent("table"):
            continue  # handled with its table
        if el.name == "li" and el.find("p"):
            continue  # avoid double counting <li><p>
        if el.name in ("h1", "h2", "h3", "h4"):
            if cur["text"]:
                sections.append(cur)
            cur = {"heading": el.get_text(" ", strip=True), "level": int(el.name[1]), "text": []}
        elif el.name == "table":
            rows = [" | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"]))
                    for tr in el.find_all("tr")]
            cur["text"].append("\n".join(r for r in rows if r.strip(" |")))
        else:
            txt = el.get_text(" ", strip=True)
            if txt:
                cur["text"].append(("- " if el.name == "li" else "") + txt)
    if cur["text"]:
        sections.append(cur)

    links, seen = [], set()
    for a in root.find_all("a", href=True):
        href = urljoin(url, a["href"]).split("#")[0]
        if href in seen:
            continue
        seen.add(href)
        if href.lower().split("?")[0].endswith(".pdf") or "/documents/" in href:
            links.append({"url": href, "text": a.get_text(" ", strip=True)})
    return {
        "url": url, "title": title, "retrieved_at": now(),
        "sections": [{**s, "text": "\n".join(s["text"])} for s in sections],
        "links": links,
    }


def cmd_pages(f, out):
    dest = out / "html"
    dest.mkdir(parents=True, exist_ok=True)
    for name, urls in OVERVIEW_PAGES.items():
        for url in urls:
            try:
                page = parse_html(f.get(url).text, url)
            except requests.RequestException as e:
                print(f"[pages] {url} failed: {e}", file=sys.stderr)
                continue
            (dest / f"{name}.json").write_text(json.dumps(page, ensure_ascii=False, indent=2), "utf-8")
            print(f"[pages] {name}: {len(page['sections'])} sections, {len(page['links'])} doc links <- {url}")
            break


# --------------------------------------------------------------------------- #
# 2. EMA JSON indexes
# --------------------------------------------------------------------------- #
def cmd_index(f, out, refresh=False):
    dest = out / "index"
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in INDEX_URLS.items():
        path = dest / f"{name}.json"
        if path.exists() and not refresh:
            print(f"[index] {name}: cached")
            continue
        r = f.get(url, stream=True)
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
        head = path.read_bytes()[:64].lstrip(b"\xef\xbb\xbf \r\n")
        if not head.startswith((b"{", b"[")):
            print(f"[index] WARNING {name}: response is not JSON - check {url}", file=sys.stderr)
        print(f"[index] {name}: {path.stat().st_size / 1e6:.1f} MB")


def load_index(out, name):
    return json.loads((out / "index" / f"{name}.json").read_text("utf-8-sig"))


def walk_dicts(node):
    """Yield every dict in a nested JSON structure (robust to unknown wrappers/headers)."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_dicts(v)


def herbs_from_index(out):
    return [d for d in walk_dicts(load_index(out, "herbal_medicines")) if "herbal_medicine_url" in d]


def docs_from_index(out):
    return [d for d in walk_dicts(load_index(out, "documents_en")) if "document_url" in d]


def cmd_types(out):
    c = Counter(str(d.get("type")) for d in docs_from_index(out))
    for t, n in c.most_common(60):
        print(f"{n:7d}  {t}")


# --------------------------------------------------------------------------- #
# 3. PDF discovery + download
# --------------------------------------------------------------------------- #
def is_english(url):
    m = re.search(r"_([a-z]{2})\.pdf$", url.lower().split("?")[0])
    return (m is None) or m.group(1) == "en"


def guess_kind(url, name=""):
    hay = f"{url} {name}".lower()
    for key, kind in (("list-entry", "list_entry"), ("list entry", "list_entry"),
                      ("monograph", "monograph"), ("assessment-report", "assessment_report"),
                      ("assessment report", "assessment_report"), ("overview-comments", "overview_of_comments"),
                      ("overview of comments", "overview_of_comments"), ("public-statement", "public_statement")):
        if key in hay:
            return kind
    return "other"


def match_herb(text, herbs_idx):
    t = (text or "").lower()
    for latin, genus_species in herbs_idx:
        if genus_species and genus_species in t:
            return latin
    return None


def is_ema_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and (host == "ema.europa.eu" or host.endswith(".ema.europa.eu"))
        and port in (None, 443)
    )


def read_url_file(path):
    urls, seen = [], set()
    with path.open(encoding="utf-8-sig") as fh:
        for line_number, line in enumerate(fh, 1):
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            if not is_ema_url(url) or not urlparse(url).path.lower().endswith(".pdf"):
                raise ValueError(
                    f"{path}:{line_number}: expected an HTTPS EMA PDF URL, got {url!r}"
                )
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def read_related_documents(path):
    documents, seen = [], set()
    skipped = 0
    with path.open(encoding="utf-8-sig") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {e}") from e
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            url = item.get("document_url") or item.get("pdf_url")
            if not isinstance(url, str) or not url or not urlparse(url).path.lower().endswith(".pdf"):
                skipped += 1
                continue
            if not is_ema_url(url):
                raise ValueError(f"{path}:{line_number}: not an HTTPS EMA URL: {url!r}")
            if url not in seen:
                seen.add(url)
                documents.append({
                    "url": url,
                    "name": item.get("name") or Path(urlparse(url).path).name,
                    "type": item.get("type"),
                    "last_updated_date": item.get("last_updated_date"),
                    "source": item.get("source") or "related_documents.jsonl",
                })
    return documents, skipped


def safe_pdf_name(url):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlparse(url).path).name)[:100]
    return name if name.lower().endswith(".pdf") else f"{name or 'doc'}.pdf"


def download_pdf(f, url, path):
    """Stream a PDF to a temporary file and atomically move it into place."""
    temporary_path = path.with_name(path.name + ".part")
    digest = hashlib.sha256()
    size = 0
    header = bytearray()
    try:
        with f.get(url, stream=True) as response:
            if not is_ema_url(response.url):
                raise ValueError(f"redirected outside ema.europa.eu: {response.url}")
            with temporary_path.open("wb") as fh:
                for chunk in response.iter_content(1 << 16):
                    if not chunk:
                        continue
                    if len(header) < 1024:
                        header.extend(chunk[:1024 - len(header)])
                    fh.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        if not header.lstrip().startswith(b"%PDF"):
            raise ValueError("response is not a PDF")
        temporary_path.replace(path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    return size, digest.hexdigest()


def is_pdf_file(path):
    with path.open("rb") as fh:
        return fh.read(1024).lstrip().startswith(b"%PDF")


def select_from_documents(out, pattern):
    rx = re.compile(pattern, re.I)
    herbs = herbs_from_index(out) if (out / "index" / "herbal_medicines.json").exists() else []
    idx = []
    for h in herbs:
        bot = " ".join((h.get("botanical_name") or "").lower().split()[:2])
        idx.append((h.get("latin_name"), bot))
    seen, picked = set(), []
    for d in docs_from_index(out):
        url = d.get("document_url") or ""
        if not url or url in seen or url.lower().split("?")[0].endswith(SKIP_EXT) or not is_english(url):
            continue
        hay = " ".join(str(d.get(k) or "") for k in ("type", "name", "medicine_name")) + " " + url
        if rx.search(hay):
            seen.add(url)
            picked.append({"url": url, "name": d.get("name"), "type": d.get("type"),
                           "last_updated_date": d.get("last_updated_date"),
                           "herb_latin_name": match_herb(d.get("name"), idx), "source": "documents_json"})
    return picked


def select_from_herb_pages(f, out, limit):
    picked = []
    for h in herbs_from_index(out)[: limit or None]:
        page = h.get("herbal_medicine_url")
        if not page:
            continue
        try:
            links = parse_html(f.get(page).text, page)["links"]
        except requests.RequestException as e:
            print(f"[pages] {page}: {e}", file=sys.stderr)
            continue
        for l in links:
            u = l["url"]
            if u.lower().split("?")[0].endswith(SKIP_EXT) or not is_english(u):
                continue
            picked.append({"url": u, "name": l["text"], "type": guess_kind(u, l["text"]),
                           "last_updated_date": h.get("last_updated_date"),
                           "herb_latin_name": h.get("latin_name"), "herb_page": page,
                           "source": "herb_page"})
    return picked


def cmd_download(f, out, source, pattern, limit, refresh,
                 related_jsonl=None, processed_urls=None):
    picked = []
    skipped_non_pdfs = 0
    if related_jsonl:
        picked, skipped_non_pdfs = read_related_documents(related_jsonl)
    else:
        if source in ("docs", "both"):
            picked += select_from_documents(out, pattern)
        if source in ("pages", "both"):
            picked += select_from_herb_pages(f, out, limit)
    uniq = {p["url"]: p for p in picked}  # herb_page entries win (they carry the herb)
    pdf_dir = out / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.jsonl"
    processed = set()
    if processed_urls and processed_urls.exists():
        processed = set(read_url_file(processed_urls))
    elif processed_urls:
        processed_urls.parent.mkdir(parents=True, exist_ok=True)
    remaining = list(uniq.values())
    if processed_urls and not refresh:
        remaining = [item for item in remaining if item["url"] not in processed]
    items = remaining[: limit or None]
    done = set()
    if manifest_path.exists():
        for line_number, line in enumerate(manifest_path.read_text("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{manifest_path}:{line_number}: invalid JSON: {e}") from e
            url = record.get("url") or record.get("pdf_url") or record.get("document_url")
            local_path = record.get("local_path")
            if url and local_path:
                recorded_path = Path(local_path)
                if not recorded_path.is_absolute() and not recorded_path.exists():
                    recorded_path = pdf_dir / recorded_path.name
                if recorded_path.is_file():
                    done.add(url)
    n_new = 0
    n_skipped = 0
    with open(manifest_path, "a", encoding="utf-8") as mf:
        for it in items:
            url = it["url"]
            if url in processed and not refresh:
                n_skipped += 1
                continue
            if url in done and not refresh:
                n_skipped += 1
                if processed_urls:
                    with processed_urls.open("a", encoding="utf-8") as progress:
                        progress.write(url + "\n")
                    processed.add(url)
                continue
            name = safe_pdf_name(url)
            path = pdf_dir / f"{sha1(url)[:8]}_{name}"
            cached_path = next(
                (candidate for candidate in (
                    path,
                    pdf_dir / name,
                    pdf_dir / f"{sha1(url)[:10]}_{name}",
                ) if candidate.is_file() and is_pdf_file(candidate)),
                None,
            )
            if cached_path and not refresh:
                content_hash = hashlib.sha256()
                with cached_path.open("rb") as cached_file:
                    for chunk in iter(lambda: cached_file.read(1 << 16), b""):
                        content_hash.update(chunk)
                rec = {
                    **it, "local_path": str(cached_path),
                    "sha256": content_hash.hexdigest(),
                    "bytes": cached_path.stat().st_size,
                    "kind": guess_kind(url, it.get("name") or ""),
                    "retrieved_at": now(),
                }
                mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                done.add(url)
                n_skipped += 1
                if processed_urls:
                    with processed_urls.open("a", encoding="utf-8") as progress:
                        progress.write(url + "\n")
                    processed.add(url)
                continue
            try:
                size, content_hash = download_pdf(f, url, path)
            except requests.RequestException as e:
                print(f"[download] {url}: {e}", file=sys.stderr)
                continue
            except ValueError as e:
                print(f"[download] {url}: {e}", file=sys.stderr)
                continue
            rec = {**it, "local_path": str(path), "sha256": content_hash,
                   "bytes": size, "kind": guess_kind(url, it.get("name") or ""),
                   "retrieved_at": now()}
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_new += 1
            done.add(url)
            if processed_urls:
                with processed_urls.open("a", encoding="utf-8") as progress:
                    progress.write(url + "\n")
                processed.add(url)
    if skipped_non_pdfs:
        print(f"[download] skipped {skipped_non_pdfs} non-PDF records from {related_jsonl}")
    print(f"[download] {n_new} downloaded, {n_skipped} skipped "
          f"(candidates: {len(items)}) -> {pdf_dir}")


# --------------------------------------------------------------------------- #
# 4. PDF -> text -> section chunks
# --------------------------------------------------------------------------- #
# HMPC monographs follow the SmPC-style numbering below.
KNOWN_SECTIONS = {
    "1": "Name of the medicinal product", "2": "Qualitative and quantitative composition",
    "3": "Pharmaceutical form", "4": "Clinical particulars", "4.1": "Therapeutic indications",
    "4.2": "Posology and method of administration", "4.3": "Contraindications",
    "4.4": "Special warnings and precautions for use",
    "4.5": "Interactions with other medicinal products and other forms of interaction",
    "4.6": "Fertility, pregnancy and lactation", "4.7": "Effects on ability to drive and use machines",
    "4.8": "Undesirable effects", "4.9": "Overdose", "5": "Pharmacological properties",
    "5.1": "Pharmacodynamic properties", "5.2": "Pharmacokinetic properties",
    "5.3": "Preclinical safety data", "6": "Pharmaceutical particulars",
    "7": "Date of compilation/last revision",
}
HEAD_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+(.{3,150}?)\s*$")
GENERIC_TITLE_RE = re.compile(r"^[A-Z][^\d]{2,100}$")


def extract_pages(path, two_column=False, ocr=False):
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            if two_column:  # side-by-side "well-established use | traditional use" layouts
                w, h = p.width, p.height
                left = p.crop((0, 0, w / 2, h)).extract_text() or ""
                right = p.crop((w / 2, 0, w, h)).extract_text() or ""
                pages.append(left + "\n" + right)
            else:
                pages.append(p.extract_text() or "")
    if ocr and pages and sum(map(len, pages)) / len(pages) < 50:  # looks scanned
        from pdf2image import convert_from_path
        import pytesseract
        pages = [pytesseract.image_to_string(im, lang="eng") for im in convert_from_path(str(path), dpi=200)]
    return pages


def strip_repeating(pages):
    """Drop running headers/footers (lines repeated on most pages, e.g. 'EMA/HMPC/123/2013 Page 3/9')."""
    if len(pages) < 3:
        return pages
    norm = lambda l: re.sub(r"\d+", "#", l.strip().lower())
    counts = Counter(norm(l) for p in pages for l in set(p.splitlines()) if l.strip())
    limit = 0.6 * len(pages)
    return ["\n".join(l for l in p.splitlines() if counts[norm(l)] < limit and l.strip()) for p in pages]


def split_sections(text):
    lines = text.splitlines()

    def collect(accept):
        hits = []
        for i, l in enumerate(lines):
            m = HEAD_RE.match(l)
            if m:
                title = accept(m.group(1), m.group(2).strip())
                if title:
                    hits.append((i, m.group(1), title))
        return hits

    def known(num, title):
        k = KNOWN_SECTIONS.get(num)
        return k if k and title.lower().startswith(k.lower()[:15]) else None

    def generic(num, title):
        return title if GENERIC_TITLE_RE.match(title) and len(title.split()) <= 14 else None

    hits = collect(known)
    if len(hits) < 3:
        hits = collect(generic)
    if len(hits) < 3:  # unstructured document -> paragraph-sized chunks
        return chunk_paragraphs(text)

    secs = {}
    if hits[0][0] > 0:
        secs["front_matter"] = ("", "Front matter", "\n".join(lines[: hits[0][0]]).strip())
    for n, (i, num, title) in enumerate(hits):
        end = hits[n + 1][0] if n + 1 < len(hits) else len(lines)
        body = "\n".join(lines[i + 1: end]).strip()
        if num not in secs or len(body) > len(secs[num][2]):  # keep longest if heading repeats (TOC)
            secs[num] = (num, title, body)
    return [s for s in secs.values() if s[2]]


def chunk_paragraphs(text, size=1500):
    out, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(buf) + len(para) > size and buf:
            out.append(("", f"Part {len(out) + 1}", buf.strip()))
            buf = ""
        buf += para + "\n\n"
    if buf.strip():
        out.append(("", f"Part {len(out) + 1}", buf.strip()))
    return out


def cmd_parse(out, two_column, ocr):
    manifest = [json.loads(l) for l in (out / "manifest.jsonl").read_text("utf-8").splitlines() if l.strip()]
    n_chunks = 0
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for rec in manifest:
            try:
                pages = strip_repeating(extract_pages(rec["local_path"], two_column, ocr))
            except Exception as e:  # corrupt PDF etc.
                print(f"[parse] {rec['local_path']}: {e}", file=sys.stderr)
                continue
            text = "\n".join(pages)
            if len(text.strip()) < 100:
                print(f"[parse] no text layer (try --ocr): {rec['local_path']}", file=sys.stderr)
                continue
            for i, (num, title, body) in enumerate(split_sections(text)):
                fh.write(json.dumps({
                    "id": f"{sha1(rec['url'])[:10]}-{i:03d}",
                    "jurisdiction": "INT-EU", "instrument": "EMA/HMPC herbal document",
                    "doc_kind": rec.get("kind"), "doc_name": rec.get("name"),
                    "herb_latin_name": rec.get("herb_latin_name"),
                    "source_url": rec["url"], "pdf_sha256": rec["sha256"],
                    "last_updated_date": rec.get("last_updated_date"), "retrieved_at": rec["retrieved_at"],
                    "section_number": num, "section_title": title, "text": body,
                }, ensure_ascii=False) + "\n")
                n_chunks += 1
    print(f"[parse] {n_chunks} chunks -> {out / 'chunks.jsonl'}")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/eu_herbal", type=Path)
    ap.add_argument("--contact", default="unset@example.org", help="email/URL put in the User-Agent")
    ap.add_argument("--delay", type=float, default=8.0, help="seconds between requests")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pages")
    p = sub.add_parser("index"); p.add_argument("--refresh", action="store_true")
    sub.add_parser("types")
    for name in ("download", "all"):
        p = sub.add_parser(name)
        p.add_argument("--source", choices=("docs", "pages", "both"), default="both")
        p.add_argument("--match", default=r"herbal|hmpc", help="regex on type/name/URL for the documents JSON")
        p.add_argument("--limit", type=int, default=0,
                       help="maximum items to process this run (0 = no cap)")
        p.add_argument("--refresh", action="store_true")
        p.add_argument("--related-jsonl", type=Path,
                       help="use PDF records from this JSONL instead of index/page selection")
        p.add_argument("--processed-urls", type=Path,
                       help="skip URLs already listed here and record successful downloads")
        p.add_argument("--two-column", action="store_true")
        p.add_argument("--ocr", action="store_true")
    p = sub.add_parser("parse"); p.add_argument("--two-column", action="store_true"); p.add_argument("--ocr", action="store_true")
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    if a.contact == "unset@example.org":
        print("note: pass --contact you@example.org so EMA can reach you if your crawler misbehaves", file=sys.stderr)
    f = Fetcher(a.contact, a.delay)

    if a.cmd == "pages":
        cmd_pages(f, a.out)
    elif a.cmd == "index":
        cmd_index(f, a.out, a.refresh)
    elif a.cmd == "types":
        cmd_types(a.out)
    elif a.cmd == "download":
        cmd_download(f, a.out, a.source, a.match, a.limit, a.refresh,
                     a.related_jsonl, a.processed_urls)
    elif a.cmd == "parse":
        cmd_parse(a.out, a.two_column, a.ocr)
    elif a.cmd == "all":
        cmd_pages(f, a.out)
        cmd_index(f, a.out)
        cmd_download(f, a.out, a.source, a.match, a.limit, a.refresh,
                     a.related_jsonl, a.processed_urls)
        cmd_parse(a.out, a.two_column, a.ocr)


if __name__ == "__main__":
    main()