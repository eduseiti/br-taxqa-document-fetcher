#!/usr/bin/env python3
"""
Decreto / Decreto-Lei Fetching Orchestrator

Loads the canonical ``decreto`` and ``decreto_lei`` records and routes them to
the right source:

  * ``decreto_lei`` -> normas.leg.br via the existing Selenium-based
    ``br_legal_parser`` (LexML URN ``urn:lex:br:federal:decreto.lei:...``).
  * ``decreto``     -> planalto.gov.br via ``PlanaltoDecretoFetcher`` (static
    HTML, index-driven URL discovery).

Both paths produce clean ``.docx`` files (document text only). A unified set of
reports is written under ``<output_dir>/metadata/``.

Usage:
    python fetch_decretos_main.py                      # fetch both types
    python fetch_decretos_main.py --only decreto_lei   # one type
    python fetch_decretos_main.py --only decreto --limit 3
    python fetch_decretos_main.py --dry-run            # list what would be fetched
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import List

sys.path.append(os.path.join(os.path.dirname(__file__), "br_legal_parser"))

from canonical_loader import CanonicalDoc, load_canonical_docs
from planalto_decreto_fetcher import PlanaltoDecretoFetcher, DecreteFetchResult

CANONICAL_JSON = "output_canonical/canonical_referred_documents.json"

logger = logging.getLogger("fetch_decretos")


# --------------------------------------------------------------------------- #
# decreto_lei via normas.leg.br (Selenium)
# --------------------------------------------------------------------------- #
def fetch_decreto_lei(docs: List[CanonicalDoc], output_dir: str,
                      delay_between_requests: float = 2.0) -> List[dict]:
    """Fetch decreto-lei documents through the existing br_legal_parser path."""
    from legal_document_fetcher import LegalDocumentFetcher, FetcherConfig

    documents_dir = Path(output_dir) / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    config = FetcherConfig(
        output_dir=str(documents_dir),
        request_timeout=30,
        retry_attempts=3,
        delay_between_requests=delay_between_requests,
        create_output_dir=True,
        use_selenium=True,
        selenium_wait_time=20,
    )
    fetcher = LegalDocumentFetcher(config)
    urls = [f"https://normas.leg.br/?urn={d.urn}" for d in docs]

    results = fetcher.process_url_list(urls, show_progress=True)

    out = []
    for d, r in zip(docs, results):
        out.append({
            "type": "decreto_lei",
            "number": d.number,
            "date": d.date,
            "urn": d.urn,
            "url": r.url,
            "success": r.success,
            "filename": r.filename,
            "error": r.error_message,
            "needs_review": d.needs_review,
            "source_filenames": d.source_filenames,
            "canonical_name": d.canonical_name,
        })
    return out


# --------------------------------------------------------------------------- #
# decreto via planalto.gov.br (static)
# --------------------------------------------------------------------------- #
def fetch_decreto(docs: List[CanonicalDoc], output_dir: str,
                  delay_between_requests: float = 1.5) -> List[dict]:
    """Fetch decreto documents from planalto."""
    documents_dir = Path(output_dir) / "documents"
    fetcher = PlanaltoDecretoFetcher(
        output_dir=str(documents_dir),
        delay_between_requests=delay_between_requests,
    )
    results: List[DecreteFetchResult] = fetcher.fetch_many(docs, show_progress=True)

    out = []
    for d, r in zip(docs, results):
        out.append({
            "type": "decreto",
            "number": d.number,
            "date": d.date,
            "urn": d.urn,
            "url": r.url,
            "success": r.success,
            "filename": r.filename,
            "error": r.error_message,
            "needs_review": r.needs_review,
            "source_filenames": d.source_filenames,
            "canonical_name": d.canonical_name,
        })
    return out


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def write_reports(records: List[dict], output_dir: str) -> dict:
    metadata_dir = Path(output_dir) / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    total = len(records)
    succeeded = [r for r in records if r["success"]]
    failed = [r for r in records if not r["success"]]
    needs_review = [r for r in records if r.get("needs_review")]

    summary = {
        "total": total,
        "successful": len(succeeded),
        "failed": len(failed),
        "success_rate": round(len(succeeded) / total * 100, 2) if total else 0,
        "needs_review": len(needs_review),
        "by_type": {},
    }
    for t in sorted({r["type"] for r in records}):
        tr = [r for r in records if r["type"] == t]
        summary["by_type"][t] = {
            "total": len(tr),
            "successful": sum(1 for r in tr if r["success"]),
        }

    with open(metadata_dir / "fetch_report.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "records": records}, f, ensure_ascii=False, indent=2)

    if failed:
        with open(metadata_dir / "failed.json", "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
    if needs_review:
        with open(metadata_dir / "needs_review.json", "w", encoding="utf-8") as f:
            json.dump(needs_review, f, ensure_ascii=False, indent=2)

    logger.info(f"Reports written to {metadata_dir}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Fetch decreto / decreto-lei documents")
    parser.add_argument("--only", choices=["decreto", "decreto_lei"], default=None,
                        help="Fetch only one type (default: both)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of documents per type (for testing)")
    parser.add_argument("--output-dir", default="./output_decretos")
    parser.add_argument("--canonical-json", default=CANONICAL_JSON)
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched without fetching")
    args = parser.parse_args()

    handlers = [logging.StreamHandler()]
    if not args.dry_run:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(args.output_dir) / "fetch_decretos.log"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    types = [args.only] if args.only else ["decreto_lei", "decreto"]
    all_records: List[dict] = []

    for slug in types:
        docs = load_canonical_docs(args.canonical_json, slug)
        if args.limit:
            docs = docs[:args.limit]

        if args.dry_run:
            print(f"\n=== {slug}: {len(docs)} document(s) ===")
            for d in docs:
                flag = " [needs_review]" if d.needs_review else ""
                print(f"  {d.urn}{flag}  ({d.canonical_name})")
            continue

        logger.info(f"Fetching {len(docs)} {slug} document(s)...")
        if slug == "decreto_lei":
            all_records += fetch_decreto_lei(docs, args.output_dir)
        else:
            all_records += fetch_decreto(docs, args.output_dir)

    if args.dry_run:
        return 0

    summary = write_reports(all_records, args.output_dir)
    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
