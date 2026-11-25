#!/usr/bin/env python3
"""
extract_pdfs.py - extract text from the EMA PDFs already in a folder and cut it into
citation-ready chunks. No downloading, no network.

Reads   data/eu_herbal/pdfs/*.pdf
        data/eu_herbal/related_documents.jsonl   (optional metadata)
Writes  data/eu_herbal/eu_chunks.jsonl
        data/eu_herbal/eu_extract_report.csv

Install: pip install pdfplumber        (OCR: pip install pytesseract pdf2image + Tesseract + Poppler)

Typical runs:
  python extract_pdfs.py --limit 50
  python extract_pdfs.py --two-column-kinds monograph
  python extract_pdfs.py --two-column-kinds monograph --ocr --tesseract-cmd "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

With --two-column-kinds, each such document is read both two-column and single-column,
and the layout that finds more known section headings is kept.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# HMPC monographs use SmPC-style numbering. Each number may have alternative titles.
KNOWN = {
    "1": ("Name of the medicinal product",),
    "2": ("Qualitative and quantitative composition",),
    "3": ("Pharmaceutical form",),
    "4": ("Clinical particulars",),
    "4.1": ("Therapeutic indications",),
    "4.2": ("Posology and method of administration",),
    "4.3": ("Contraindications",),
    "4.4": ("Special warnings and precautions for use",),
    "4.5": ("Interactions with other medicinal products and other forms of interaction",),
    "4.6": ("Fertility, pregnancy and lactation", "Pregnancy and lactation"),
    "4.7": ("Effects on ability to drive and use machines",),
    "4.8": ("Undesirable effects",),
    "4.9": ("Overdose",),
    "5": ("Pharmacological properties",),
    "5.1": ("Pharmacodynamic properties",),
    "5.2": ("Pharmacokinetic properties",),
    "5.3": ("Preclinical safety data",),
    "6": ("Pharmaceutical particulars",),
    "7": ("Date of compilation/last revision",),
}

HEAD_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+(.{3,600}?)\s*$")
GENERIC_TITLE = re.compile(r"^[A-Z][^\d]{2,100}$")

# Table-of-contents lines: "3.1 Overview ........ 12" or "3.1 Overview . . . . 12"
TOC_RE = re.compile(r"(?:\.\s?){4,}\s*\d{1,3}\s*$")

# Known heading in the MIDDLE of a line, e.g. "Not known. 4.6. Pregnancy and lactation ..."
_nums = "|".join(re.escape(n) for n in sorted(KNOWN, key=len, reverse=True))
_titles = "|".join(re.escape(t.lower()[:15]) for v in KNOWN.values() for t in v)
INLINE_RE = re.compile(rf"(?<=[.:;)])\s+(?=(?:{_nums})\.?\s+(?:{_titles}))", re.I)

# Kinds whose text is lists of citations or comment tables: no heading detection
FLAT_KINDS = {"references", "comments"}
INLINE_KINDS = {"monograph", "other"}

MIN_CHUNK_CHARS = 5   # drop stray fragments such as a lone page number


def sha1(s):
    return hashlib.sha1(s.encode()).hexdigest()


PREFIX_RE = re.compile(r"^([0-9a-f]{8,10})_(.+)$")


def url_key(url):
    """File name a downloader would have produced for this URL, without any hash prefix."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(urlparse(url).path).name)[:120]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name.lower()


def guess_kind(filename):
    f = filename.lower()
    for key, kind in (("monograph", "monograph"), ("assessment-report", "report"),
                      ("summary-public", "summary"), ("opinion", "opinion"),
                      ("list-references", "references"), ("overview-comments", "comments"),
                      ("call-submission", "call-data"), ("public-statement", "public-statement")):
        if key in f:
            return kind
    return "other"


# --------------------------------------------------------------------------- #
def fix_ocr(text):
    """Tesseract often reads '4.2' as '4,2' at the start of a line."""
    return re.sub(r"(?m)^(\s*\d{1,2}),(\d{1,2})(?=\.?\s)", r"\1.\2", text)


def read_pages(path, two_column=False, ocr=False, tess_cmd=None, poppler=None):
    """Return (pages, used_ocr)."""
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            if two_column:
                try:
                    x0, top, x1, bottom = p.bbox
                    mid = (x0 + x1) / 2
                    txt = (p.crop((x0, top, mid, bottom)).extract_text() or "") + "\n" + \
                          (p.crop((mid, top, x1, bottom)).extract_text() or "")
                except Exception:
                    txt = p.extract_text() or ""
            else:
                txt = p.extract_text() or ""
            pages.append(txt)
    used_ocr = False
    if ocr and pages and sum(map(len, pages)) / len(pages) < 50:
        try:
            from pdf2image import convert_from_path
            import pytesseract
            if tess_cmd:
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
            kw = {"poppler_path": poppler} if poppler else {}
            images = convert_from_path(str(path), dpi=300, **kw)
            pages = [fix_ocr(pytesseract.image_to_string(im, lang="eng")) for im in images]
            used_ocr = True
        except Exception as e:
            print(f"  ! OCR failed for {path.name}: {e}", file=sys.stderr)
    return pages, used_ocr


def strip_repeating(pages):
    """Remove running headers/footers (e.g. 'EMA/HMPC/123/2013  Page 3/9')."""
    if len(pages) < 3:
        return pages
    norm = lambda l: re.sub(r"\d+", "#", l.strip().lower())
    counts = Counter(norm(l) for p in pages for l in set(p.splitlines()) if l.strip())
    cut = 0.6 * len(pages)
    return ["\n".join(l for l in p.splitlines() if l.strip() and counts[norm(l)] < cut) for p in pages]


def to_lines(pages, inline=False):
    """Flatten pages to lines. Drops table-of-contents lines; optionally splits mid-line headings."""
    lines, line_page = [], []
    for n, p in enumerate(pages, 1):
        for l in p.splitlines():
            if TOC_RE.search(l):
                continue
            pieces = INLINE_RE.split(l) if inline else [l]
            for piece in pieces:
                if piece.strip():
                    lines.append(piece)
                    line_page.append(n)
    return lines, line_page


def count_known_headings(pages):
    """Number of known SmPC sections that survive WITH body text for this reading of the PDF."""
    cleaned = strip_repeating(pages)
    lines, line_page = to_lines(cleaned, inline=True)
    secs, mode = split_sections(lines, line_page)
    if mode != "numbered":
        return 0
    return sum(1 for s in secs if s["num"] in KNOWN)

def split_sections(lines, line_page, flat=False):
    """Return ([{'num','title','body','page'}], mode)."""
    if flat:
        return paragraph_sections(lines, line_page), "fallback"

    def scan(accept):
        hits = []
        for i, l in enumerate(lines):
            m = HEAD_RE.match(l)
            if m:
                t = accept(m.group(1), m.group(2).strip())
                if t:
                    hits.append((i, m.group(1), t[0], t[1]))   # (line, num, title, rest of line)
        return hits

    def known(num, title):
        for alt in KNOWN.get(num, ()):
            if title.lower().startswith(alt.lower()[:15]):
                rest = title[len(alt):].strip() if title.lower().startswith(alt.lower()) else ""
                return alt, rest
        return None

    def generic(num, title):
        if int(num.split(".")[0]) > 12:
            return None
        if not GENERIC_TITLE.match(title) or len(title.split()) > 12:
            return None
        if title[-1] in ",;." or "et al" in title.lower():
            return None
        return title, ""

    hits, used_generic = scan(known), False
    if len(hits) < 3:
        hits, used_generic = scan(generic), True
    if len(hits) < 3:
        return paragraph_sections(lines, line_page), "fallback"

    best = {}
    if hits[0][0] > 0:
        body = "\n".join(lines[:hits[0][0]]).strip()
        if body:
            best["front"] = {"num": "", "title": "Front matter", "body": body, "page": line_page[0], "idx": -1}
    for n, (i, num, title, rest) in enumerate(hits):
        end = hits[n + 1][0] if n + 1 < len(hits) else len(lines)
        body = "\n".join(([rest] if rest else []) + lines[i + 1:end]).strip()
        # if a number appears twice (e.g. leftover TOC entry), keep the longer one
        if body and (num not in best or len(body) > len(best[num]["body"])):
            best[num] = {"num": num, "title": title, "body": body, "page": line_page[i], "idx": i}
    secs = sorted(best.values(), key=lambda s: s["idx"])

    # form-style PDFs: few "headings" but giant sections -> labels are wrong, use plain chunks
    if used_generic and len(hits) < 10 and secs and max(len(s["body"]) for s in secs) > 25000:
        return paragraph_sections(lines, line_page), "fallback"
    return secs, "numbered"


def paragraph_sections(lines, line_page, size=1500):
    out, buf, start = [], [], 0
    for i, l in enumerate(lines):
        if not buf:
            start = line_page[i]
        buf.append(l)
        if sum(map(len, buf)) >= size and l.rstrip().endswith((".", ":", ";")):
            out.append({"num": "", "title": f"Part {len(out) + 1}", "body": "\n".join(buf).strip(), "page": start})
            buf = []
    if buf:
        tail = "\n".join(buf).strip()
        if out and len(tail) < 200:                      # merge a tiny leftover into the previous part
            out[-1]["body"] += "\n" + tail
        else:
            out.append({"num": "", "title": f"Part {len(out) + 1}", "body": tail, "page": start})
    return out


def window(text, max_chars, overlap=150):
    """Split long text on line boundaries into <=max_chars windows with a small overlap."""
    if len(text) <= max_chars:
        return [text]
    parts, cur = [], ""
    for line in text.splitlines():
        if cur and len(cur) + len(line) + 1 > max_chars:
            parts.append(cur)
            cur = cur[-overlap:].split(" ", 1)[-1] + "\n"
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts]


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf-dir", default="data/eu_herbal/pdfs")
    ap.add_argument("--out", default="data/eu_herbal")
    ap.add_argument("--candidates", default="data/eu_herbal/related_documents.jsonl",
                    help="optional metadata file; skipped if missing")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--kinds", help="only these kinds, e.g. monograph,report,summary")
    ap.add_argument("--exclude-kinds", default="committee-report,agenda,minutes,presentation,mrl-report",
                    help="skip these kinds (default drops meeting papers); pass '' to keep everything")
    ap.add_argument("--max-chars", type=int, default=2000, help="max characters per chunk")
    ap.add_argument("--two-column", action="store_true", help="try two-column reading for ALL documents")
    ap.add_argument("--two-column-kinds", default="",
                    help="try two-column reading only for these kinds, e.g. monograph")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--tesseract-cmd", help=r"path to tesseract.exe if it is not on PATH")
    ap.add_argument("--poppler-path", help=r"folder containing pdftoppm.exe (Poppler bin)")
    a = ap.parse_args()

    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        sys.exit("pdfplumber is not installed for this Python.\n"
                 f"Run:  \"{sys.executable}\" -m pip install pdfplumber")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    two_col_kinds = {k for k in a.two_column_kinds.split(",") if k}

    # optional metadata, matched by hash prefix of the file name, else by file name
    by_hash, by_name, cand = {}, {}, Path(a.candidates)
    if cand.exists():
        for line in cand.read_text("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                url = row.get("document_url")
                if url:
                    by_hash[sha1(url)[:10]] = row
                    by_hash[sha1(url)[:8]] = row
                    by_name.setdefault(url_key(url), row)
        print(f"metadata loaded for {len(by_name)} documents from {cand}")
    else:
        print("no candidates file found - using file names only")

    recs, matched = [], 0
    for p in sorted(Path(a.pdf_dir).glob("*.pdf")):
        m = PREFIX_RE.match(p.name)
        rest = m.group(2) if m else p.name
        row = (by_hash.get(m.group(1)) if m else None) or by_name.get(rest.lower()) or {}
        matched += bool(row)
        herbs = row.get("matched_herbs") or []
        recs.append({
            "path": p, "_url": row.get("document_url"),
            "name": row.get("name") or Path(rest).stem.replace("-", " "),
            "kind": (row.get("type") or guess_kind(p.name)).replace("herbal-", ""),
            "status": row.get("status"), "reference_number": row.get("reference_number"),
            "last_updated_date": row.get("last_updated_date"),
            "matched_herbs": herbs, "herb_latin_name": herbs[0] if len(herbs) == 1 else None,
        })
    print(f"{len(recs)} PDFs in {a.pdf_dir}; metadata matched for {matched}")
    drop = {k for k in a.exclude_kinds.split(",") if k}
    if drop:
        before = len(recs)
        recs = [r for r in recs if r["kind"] not in drop]
        print(f"skipped {before - len(recs)} PDFs of kinds: {', '.join(sorted(drop))}")
    if a.kinds:
        want = set(a.kinds.split(","))
        recs = [r for r in recs if r["kind"] in want]
    if a.limit:
        recs = recs[:a.limit]
    print(f"{len(recs)} PDFs to process")

    report_rows, n_chunks = [], 0
    with open(out / "eu_chunks.jsonl", "w", encoding="utf-8") as fh:
        for k, r in enumerate(recs, 1):
            path, flags = r["path"], []
            kind = r.get("kind")
            flat = kind in FLAT_KINDS or guess_kind(path.name) in FLAT_KINDS
            try:
                two_col = a.two_column or kind in two_col_kinds
                raw, used_ocr = read_pages(path, two_col, a.ocr, a.tesseract_cmd, a.poppler_path)
                if two_col and not used_ocr:
                    # also read single-column; keep it only if it finds MORE known headings
                    alt, _ = read_pages(path, False, False)
                    if alt and count_known_headings(alt) > count_known_headings(raw):
                        raw = alt
                        flags.append("single_col_chosen")
                pages = strip_repeating(raw)
                if sum(map(len, pages)) < 0.3 * sum(map(len, raw)):   # never strip away the body
                    pages = raw
            except Exception as e:
                report_rows.append({"file": path.name, "kind": kind, "pages": 0, "chars": 0,
                                    "sections": 0, "chunks": 0, "mode": "", "flags": f"error:{e.__class__.__name__}"})
                print(f"  ! {path.name}: {e}", file=sys.stderr)
                continue
            if used_ocr:
                flags.append("ocr")
            file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            chars = sum(map(len, pages))
            if chars < 100:
                flags.append("no_text_layer(try --ocr)")
                sections, mode = [], "none"
            else:
                lines, line_page = to_lines(pages, inline=kind in INLINE_KINDS)
                sections, mode = split_sections(lines, line_page, flat=flat)
                if mode == "fallback":
                    flags.append("no_numbered_sections")
                if chars / max(1, len(pages)) < 400:
                    flags.append("sparse_text")
            n = 0
            for s in sections:
                head = f"{s['num']} {s['title']}".strip()
                for w, piece in enumerate(window(s["body"], a.max_chars)):
                    if len(piece.strip()) < MIN_CHUNK_CHARS:      # stray page number etc.
                        continue
                    fh.write(json.dumps({
                        "id": f"{sha1(r['_url'] or path.name)[:10]}-{n:03d}",
                        "jurisdiction": "INT-EU", "instrument": "EMA/HMPC herbal document",
                        "doc_kind": kind, "doc_name": r.get("name"),
                        "priority": "low" if flat else "normal",
                        "status": r.get("status"), "reference_number": r.get("reference_number"),
                        "last_updated_date": r.get("last_updated_date"),
                        "herb_latin_name": r.get("herb_latin_name"), "matched_herbs": r.get("matched_herbs"),
                        "source_url": r["_url"], "pdf_file": path.name, "pdf_sha256": file_sha,
                        "section_number": s["num"], "section_title": s["title"],
                        "page_start": s["page"], "part": w, "text": piece,
                        "embed_text": f"{r.get('name')} | {head}\n{piece}",
                    }, ensure_ascii=False) + "\n")
                    n += 1
            n_chunks += n
            report_rows.append({"file": path.name, "kind": kind, "pages": len(pages), "chars": chars,
                                "sections": len(sections), "chunks": n, "mode": mode, "flags": ";".join(flags)})
            if k % 50 == 0:
                print(f"  {k}/{len(recs)}")

    rp = out / "eu_extract_report.csv"
    with open(rp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "kind", "pages", "chars", "sections", "chunks", "mode", "flags"])
        w.writeheader()
        w.writerows(report_rows)

    # ---- console summary -------------------------------------------------- #
    print(f"\n{n_chunks} chunks -> {out / 'eu_chunks.jsonl'}\nreport -> {rp}\n")
    by = {}
    for row in report_rows:
        d = by.setdefault(row["kind"], Counter())
        d["pdfs"] += 1
        d["numbered"] += row["mode"] == "numbered"
        d["fallback"] += row["mode"] == "fallback"
        d["no_text"] += "no_text_layer" in row["flags"]
        d["ocr"] += "ocr" in row["flags"]
        d["single"] += "single_col_chosen" in row["flags"]
        d["errors"] += row["flags"].startswith("error")
    print(f"{'kind':<32}{'pdfs':>6}{'numbered':>10}{'fallback':>10}{'no_text':>9}{'ocr':>5}{'single':>8}{'errors':>8}")
    for kind, d in sorted(by.items(), key=lambda x: str(x[0])):
        print(f"{str(kind):<32}{d['pdfs']:>6}{d['numbered']:>10}{d['fallback']:>10}"
              f"{d['no_text']:>9}{d['ocr']:>5}{d['single']:>8}{d['errors']:>8}")


if __name__ == "__main__":
    main()