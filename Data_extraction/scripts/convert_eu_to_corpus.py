#!/usr/bin/env python3
"""Convert selected EMA/HMPC JSONL chunks to the project corpus schema."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "Data_extraction" / "data" / "eu_herbal" / "eu_chunks.jsonl"
OUTPUT = ROOT / "Ayushakti" / "knowledge-base" / "corpus" / "eu_herbal.json"
INCLUDED_KINDS = {"monograph", "report"}
TODAY = date.today().isoformat()


def load_chunks(path: Path) -> list[dict[str, Any]]:
    chunks = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            chunks.append(record)
    return chunks


def is_current_adopted_document(records: list[dict[str, Any]]) -> bool:
    first = records[0]
    if first.get("doc_kind") not in INCLUDED_KINDS or first.get("status") != "Adopted":
        return False
    names = " ".join(
        str(value or "").lower()
        for value in (first.get("doc_name"), first.get("pdf_file"))
    )
    return "superseded" not in names


def make_section_identifier(record: dict[str, Any]) -> str:
    number = str(record.get("section_number") or "").strip()
    title = str(record.get("section_title") or "").strip()
    if number:
        base = f"Section {number}"
        if title:
            base += f" {title}"
    else:
        base = title or "Unlabeled section"

    page = record.get("page_start")
    suffix = f" (p. {page})" if isinstance(page, int) and page > 0 else ""
    part = record.get("part")
    if isinstance(part, int) and part > 0:
        suffix = suffix[:-1] + f", part {part + 1})" if suffix else f" (part {part + 1})"

    max_base_length = 255 - len(suffix)
    return base[:max_base_length].rstrip() + suffix


def make_document(pdf_file: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    first = records[0]
    title = str(first.get("doc_name") or "").strip()
    source_url = first.get("source_url")
    if not title or len(title) > 500:
        raise ValueError(f"Invalid document title for {pdf_file!r}")
    if not source_url:
        raise ValueError(f"Missing official source URL for {pdf_file!r}")

    doc_kind = first["doc_kind"]
    document_type = "assessment report" if doc_kind == "report" else "monograph"
    last_updated = first.get("last_updated_date")
    version_tag = f"adopted-{str(last_updated)[:10]}" if last_updated else "adopted-date-unknown"
    herbs = []
    for record in records:
        herb = record.get("herb_latin_name")
        if herb and herb not in herbs:
            herbs.append(herb)
        for matched in record.get("matched_herbs") or []:
            if matched and matched not in herbs:
                herbs.append(matched)
    herb_context = "; ".join(herbs[:8])

    chunks = []
    for record in records:
        text = str(record.get("text") or "").strip()
        if not text:
            raise ValueError(f"Empty source text in {pdf_file!r}, chunk {record.get('id')!r}")
        section_title = str(record.get("section_title") or "").strip()
        section_number = str(record.get("section_number") or "").strip()
        chunk_title = section_title or section_number or "Unlabeled section"
        context_parts = [title, document_type]
        if herb_context:
            context_parts.append(herb_context)
        context_parts.append(chunk_title)
        chunks.append(
            {
                "section_identifier": make_section_identifier(record),
                "title": chunk_title,
                "source_url": source_url,
                "verbatim_text": text,
                "retrieval_context": " | ".join(context_parts),
            }
        )

    return {
        "title": title,
        "short_title": title,
        "authority": "European Medicines Agency (HMPC)",
        "document_type": document_type,
        "jurisdiction": "international",
        "category": "herbal",
        "source_url": source_url,
        "source_file": pdf_file,
        "version_tag": version_tag,
        "retrieved_date": TODAY,
        "verification_status": "pending_human_check",
        "document_note": (
            f"EMA catalog status: {first.get('status')}. The published document title "
            "is retained verbatim; titles that identify a draft remain labeled as draft. "
            "Superseded versions and non-adopted or unclassified records were excluded."
        ),
        "chunks": chunks,
    }


def convert(input_path: Path) -> dict[str, Any]:
    records = load_chunks(input_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        pdf_file = record.get("pdf_file")
        if not pdf_file:
            raise ValueError(f"Chunk {record.get('id')!r} is missing pdf_file")
        grouped[str(pdf_file)].append(record)

    documents = []
    for pdf_file in sorted(grouped):
        chunks = grouped[pdf_file]
        kinds = {record.get("doc_kind") for record in chunks}
        statuses = {record.get("status") for record in chunks}
        if len(kinds) != 1 or len(statuses) != 1:
            raise ValueError(f"Inconsistent kind or status within {pdf_file!r}")
        if is_current_adopted_document(chunks):
            documents.append(make_document(pdf_file, chunks))

    if not documents:
        raise ValueError("No current adopted monographs or reports found")
    titles = [document["title"] for document in documents]
    if len(titles) != len(set(titles)):
        raise ValueError("Selected EMA documents have duplicate titles")
    if not all(
        len(chunk["section_identifier"]) <= 255
        for document in documents
        for chunk in document["chunks"]
    ):
        raise ValueError("A generated section_identifier exceeds 255 characters")

    return {
        "corpus_id": "eu_herbal",
        "corpus_version": f"{TODAY}.1",
        "retrieved_date": TODAY,
        "collection_rules": (
            "EMA/HMPC herbal monographs and assessment reports with Adopted status "
            "are included. Superseded versions and other document kinds are excluded. "
            "Published document titles and chunk text are preserved; draft labels in "
            "titles are retained. Every document and chunk is pending human verification."
        ),
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    corpus = convert(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    chunks = sum(len(document["chunks"]) for document in corpus["documents"])
    print(
        f"Wrote {len(corpus['documents'])} documents and {chunks} chunks "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
