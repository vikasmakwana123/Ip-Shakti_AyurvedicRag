#!/usr/bin/env python3
"""
inspect_chunks.py - sanity-check eu_chunks.jsonl before you trust it. Stdlib only.

  python inspect_chunks.py                          # overall health + common section titles per kind
  python inspect_chunks.py --kind monograph         # only monographs
  python inspect_chunks.py --kind report --docs 3   # also show the section layout of 3 reports
  python inspect_chunks.py --file valeriana --docs 1 --show-text
"""
import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def alpha_ratio(text):
    return sum(ch.isalpha() or ch.isspace() for ch in text) / max(1, len(text))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", default="data/eu_herbal/eu_chunks.jsonl")
    ap.add_argument("--kind", help="doc_kind to inspect, e.g. monograph, report, summary")
    ap.add_argument("--file", help="substring of the PDF file name")
    ap.add_argument("--docs", type=int, default=0, help="show the section layout of N documents")
    ap.add_argument("--show-text", action="store_true", help="print the first 200 chars of each section")
    a = ap.parse_args()

    chunks = [json.loads(l) for l in Path(a.chunks).read_text("utf-8").splitlines() if l.strip()]
    if a.kind:
        chunks = [c for c in chunks if c.get("doc_kind") == a.kind]
    if a.file:
        chunks = [c for c in chunks if a.file.lower() in c.get("pdf_file", "").lower()]
    if not chunks:
        raise SystemExit("no chunks match")

    by_doc = defaultdict(list)
    for c in chunks:
        by_doc[c["pdf_file"]].append(c)

    # ---- overall -------------------------------------------------------- #
    lens = [len(c["text"]) for c in chunks]
    tiny = [c for c in chunks if len(c["text"]) < 80]
    huge = [c for c in chunks if len(c["text"]) > 2300]
    garbled = [c for c in chunks if len(c["text"]) > 200 and alpha_ratio(c["text"]) < 0.6]
    print(f"{len(chunks)} chunks from {len(by_doc)} PDFs")
    print(f"chunk length  min {min(lens)}  median {int(statistics.median(lens))}  max {max(lens)}")
    print(f"tiny (<80 chars): {len(tiny)}   oversize (>2300): {len(huge)}   "
          f"low-letter-ratio (garbled?): {len(garbled)}")
    print("chunks by kind:", dict(Counter(c.get("doc_kind") for c in chunks)))

    # ---- most common section titles per kind (shows whether structure is consistent) ---- #
    titles = defaultdict(Counter)
    for c in chunks:
        if c.get("part", 0) == 0:
            titles[c.get("doc_kind")][f"{c['section_number'] or '-'} {c['section_title'][:60]}"] += 1
    for kind, cnt in sorted(titles.items(), key=lambda x: str(x[0])):
        print(f"\n[{kind}] most common section titles")
        for t, n in cnt.most_common(12):
            print(f"  {n:4d}  {t}")

    # ---- suspicious documents ------------------------------------------- #
    print("\nSuspicious documents")
    flagged = 0
    for f, cs in by_doc.items():
        secs = {(c["section_number"], c["section_title"]) for c in cs}
        pages = max(c["page_start"] for c in cs)
        tiny_secs = sum(1 for c in cs if len(c["text"]) < 40)
        bad_titles = [t for _, t in secs if len(t.split()) > 12 or "et al" in t.lower()]
        reasons = []
        if len(secs) > max(30, 3 * pages):
            reasons.append(f"{len(secs)} sections on {pages} pages (false headings?)")
        if tiny_secs >= 3:
            reasons.append(f"{tiny_secs} near-empty sections")
        if bad_titles:
            reasons.append(f"{len(bad_titles)} odd titles e.g. '{bad_titles[0][:50]}'")
        if reasons:
            flagged += 1
            print(f"  ! {f[:70]}: " + "; ".join(reasons))
    print("  none" if not flagged else f"  ({flagged} documents flagged)")

    # ---- layout of a few documents -------------------------------------- #
    for f in list(by_doc)[: a.docs]:
        print(f"\n=== {f} ({by_doc[f][0].get('doc_name')}) ===")
        seen = set()
        for c in by_doc[f]:
            key = (c["section_number"], c["section_title"])
            if key in seen:
                continue
            seen.add(key)
            total = sum(len(x["text"]) for x in by_doc[f] if (x["section_number"], x["section_title"]) == key)
            print(f"  p{c['page_start']:<3} {c['section_number'] or '-':<6} {c['section_title'][:55]:<55} {total:>6} chars")
            if a.show_text:
                print("        " + re.sub(r"\s+", " ", c["text"][:200]))


if __name__ == "__main__":
    main()