#!/usr/bin/env python3
"""Append section-level text extracted from supplied English Indian Acts to india.json."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "Ayushakti" / "knowledge-base" / "source"
OUTPUT = ROOT / "Ayushakti" / "knowledge-base" / "corpus" / "india.json"
TODAY = date.today().isoformat()

ACTS = (
    {
        "file": "Copyright Act, 1957.pdf",
        "title": "The Copyright Act, 1957",
        "short_title": "Copyright Act, 1957",
        "category": "copyright",
        "document_type": "statute",
        "version_tag": "source-pdf-consolidation-date-not-stated",
        "start": re.compile(
            r"(?m)^[ \t]{0,24}1\.\s+.*?This Act may be called the Copyright Act, 1957"
        ),
        "max_section": 79,
        "min_sections": 60,
    },
    {
        "file": "Designs Act, 2000.pdf",
        "title": "The Designs Act, 2000",
        "short_title": "Designs Act, 2000",
        "category": "designs",
        "document_type": "statute",
        "version_tag": "as-on-2026-06-15",
        "start": re.compile(
            r"(?m)^[ \t]{0,24}1\.\s+.*?This Act may be called the Designs Act, 2000"
        ),
        "max_section": 48,
        "min_sections": 35,
    },
    {
        "file": "Plant Varieties and Farmers' Rights Act, 2001.pdf",
        "title": "The Protection of Plant Varieties and Farmers' Rights Act, 2001",
        "short_title": "Protection of Plant Varieties and Farmers' Rights Act, 2001",
        "category": "plant_varieties",
        "document_type": "statute",
        "version_tag": "2001-as-enacted",
        "start": re.compile(
            r"(?m)^.{0,80}?\b1\.\s+\(1\)\s+This Act may be called"
        ),
        "max_section": 97,
        "min_sections": 70,
    },
)

SECTION_LINE = re.compile(
    r"^[ \t]{0,80}.*?\b(\d{1,3}[A-Z]?)\.\s+\S",
    re.IGNORECASE | re.MULTILINE,
)
CAPTION = re.compile(
    r"^\s*\d{1,3}[A-Z]?\.\s+(.{2,160}?)(?:\.\s*[—–-]|\s+[—–-]\s*|$)",
    re.IGNORECASE,
)


def section_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Z]?)", value, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unrecognized section number: {value}")
    return int(match.group(1)), match.group(2).upper()


def extract_pdf_text(pdf_path: Path, pdftotext: str) -> str:
    result = subprocess.run(
        [pdftotext, "-enc", "UTF-8", "-layout", str(pdf_path), "-"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftotext failed for {pdf_path.name}: {error}")
    return result.stdout.decode("utf-8", errors="replace")


def split_sections(text: str, act: dict[str, Any]) -> list[dict[str, str]]:
    body = act["start"].search(text)
    if body is None:
        raise ValueError(f"Could not locate the Act text in {act['file']}")
    body_start = text.rfind("\n", 0, body.start()) + 1

    candidates: list[tuple[int, str, str]] = []
    previous_key = (0, "")
    for match in SECTION_LINE.finditer(text, body_start):
        section_number = match.group(1).upper()
        key = section_key(section_number)
        if key[0] > act["max_section"] or key <= previous_key:
            continue
        if key[0] - previous_key[0] > 5 and previous_key[0] != 0:
            continue
        line_end = text.find("\n", match.start())
        if line_end < 0:
            line_end = len(text)
        candidates.append((match.start(), section_number, text[match.start():line_end].strip()))
        previous_key = key

    if len(candidates) < act["min_sections"]:
        raise ValueError(
            f"Only detected {len(candidates)} section starts in {act['file']}; "
            "refusing to write a partial corpus entry"
        )

    sections = []
    for index, (start, section_number, heading_line) in enumerate(candidates):
        end = candidates[index + 1][0] if index + 1 < len(candidates) else len(text)
        verbatim_text = text[start:end].replace("\f", "\n").strip()
        if not verbatim_text:
            continue
        caption = CAPTION.match(heading_line)
        title = caption.group(1).strip() if caption else f"Section {section_number}"
        sections.append(
            {
                "section_identifier": f"Section {section_number}",
                "title": title[:250],
                "verbatim_text": verbatim_text,
                "retrieval_context": (
                    f"{act['short_title']} Section {section_number} {title}"
                )[:1000],
                "extraction_note": (
                    "Raw pdftotext output. Layout artifacts, footnotes, and amendment "
                    "markers may remain; verify this section against the source PDF."
                ),
            }
        )
    return sections


def make_document(act: dict[str, Any], chunks: list[dict[str, str]]) -> dict[str, Any]:
    document: dict[str, Any] = {
        "title": act["title"],
        "short_title": act["short_title"],
        "authority": "Government of India",
        "document_type": act["document_type"],
        "jurisdiction": "india",
        "category": act["category"],
        "source_file": act["file"],
        "version_tag": act["version_tag"],
        "retrieved_date": TODAY,
        "verification_status": "pending_human_check",
        "document_note": (
            "Automated section extraction from the supplied local PDF. The exact "
            "download URL was not supplied; section boundaries and extracted text "
            "require human verification before use."
        ),
        "chunks": chunks,
    }
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--reference-corpus", type=Path)
    parser.add_argument("--pdftotext", default=shutil.which("pdftotext"))
    args = parser.parse_args()

    if not args.pdftotext:
        raise RuntimeError("pdftotext was not found on PATH")

    if args.output.exists():
        corpus_path = args.output
    elif args.reference_corpus:
        corpus_path = args.reference_corpus
    else:
        raise RuntimeError(
            "No existing india.json found; supply the project reference with "
            "--reference-corpus"
        )

    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    documents = corpus.get("documents")
    if not isinstance(documents, list):
        raise ValueError("Reference corpus must contain a documents array")

    existing_files = {
        document.get("source_file")
        for document in documents
        if isinstance(document, dict)
    }
    added: list[dict[str, Any]] = []
    for act in ACTS:
        if act["file"] in existing_files:
            print(f"Already present; skipped {act['file']}")
            continue
        pdf_path = args.source_dir / act["file"]
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Required source PDF not found: {pdf_path}")
        text = extract_pdf_text(pdf_path, args.pdftotext)
        chunks = split_sections(text, act)
        added.append(make_document(act, chunks))
        print(f"Extracted {len(chunks)} sections from {act['file']}")

    if not added:
        print("No new documents to add.")
        return 0

    documents.extend(added)
    corpus["corpus_version"] = f"{TODAY}.1"
    corpus["retrieved_date"] = TODAY
    corpus["collection_rules"] = (
        str(corpus.get("collection_rules", "")).rstrip()
        + " Additional supplied PDFs were extracted mechanically; added records "
        "remain pending human verification."
    ).strip()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(added)} documents to {args.output}")
    print(
        "Not converted: Biological Diversity Rules, 2024.pdf. Its Hindi text "
        "has corrupted character mapping in pdftotext output; OCR/transcription "
        "is needed before it can be safely ingested."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
