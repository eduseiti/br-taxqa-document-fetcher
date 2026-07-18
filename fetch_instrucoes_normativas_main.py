#!/usr/bin/env python3
"""
Instrução Normativa (Receita Federal) Fetching Orchestrator

Loads the canonical ``instrucao_normativa_srf`` records (and, optionally,
``instrucao_normativa_rfb``) and fetches them from the Receita Federal norms
portal via ``ReceitaNormaFetcher`` (plain ``requests``; no Selenium). Mirrors the
layout and reporting of ``fetch_decretos_main.py``.

Outputs go under ``output_instrucoes_normativas/``:
  * ``documents/`` — per act: ``{prefix}_{number}_{YYYYMMDD}.json`` (raw API
    JSON, lossless), ``.txt`` (reconstructed plain text), and ``.docx`` (parity).
  * ``metadata/fetch_report.json`` — per-record status + provenance.
  * ``metadata/needs_review.json`` — unmatched/ambiguous records with reasons.

Usage:
    python fetch_instrucoes_normativas_main.py                       # IN SRF
    python fetch_instrucoes_normativas_main.py --only instrucao_normativa_rfb
    python fetch_instrucoes_normativas_main.py --limit 3
    python fetch_instrucoes_normativas_main.py --dry-run
    python fetch_instrucoes_normativas_main.py --no-docx
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from canonical_loader import CanonicalDoc, load_canonical_docs
from receita_norma_fetcher import ACT_TYPES, ReceitaNormaFetcher, ReceitaFetchResult

CANONICAL_JSON = "output_canonical/canonical_referred_documents.json"
DEFAULT_TYPES = ["instrucao_normativa_srf"]

logger = logging.getLogger("fetch_instrucoes_normativas")


def fetch_type(type_slug: str, docs: List[CanonicalDoc], output_dir: str,
               save_docx: bool, delay: float) -> List[dict]:
    """Fetch all records of one act type; return report rows."""
    fetcher = ReceitaNormaFetcher(
        ACT_TYPES[type_slug], output_dir=output_dir,
        delay_between_requests=delay, save_docx=save_docx,
    )
    results: List[ReceitaFetchResult] = fetcher.fetch_many(docs, show_progress=True)

    rows = []
    for d, r in zip(docs, results):
        rows.append({
            "type": type_slug,
            "number": d.number,
            "date": d.date,
            "canonical_name": d.canonical_name,
            "id_ato": r.id_ato,
            "alternate_id_atos": r.alternate_id_atos,
            "view": r.view,
            "url": r.url,
            "success": r.success,
            "json_filename": r.json_filename,
            "text_filename": r.text_filename,
            "docx_filename": r.docx_filename,
            "error": r.error_message,
            "needs_review": r.needs_review,
            "review_reason": r.review_reason,
            "source_filenames": d.source_filenames,
        })
    return rows


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

    if needs_review:
        with open(metadata_dir / "needs_review.json", "w", encoding="utf-8") as f:
            json.dump(needs_review, f, ensure_ascii=False, indent=2)

    logger.info(f"Reports written to {metadata_dir}")
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Instrução Normativa documents from the Receita Federal portal")
    parser.add_argument("--only", choices=sorted(ACT_TYPES), default=None,
                        help="Fetch only one type (default: instrucao_normativa_srf)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of documents per type (for testing)")
    parser.add_argument("--output-dir", default="./output_instrucoes_normativas")
    parser.add_argument("--canonical-json", default=CANONICAL_JSON)
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay (s) between records (politeness)")
    parser.add_argument("--no-docx", action="store_true",
                        help="Skip .docx generation (JSON + .txt only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched without fetching")
    args = parser.parse_args()

    handlers = [logging.StreamHandler()]
    if not args.dry_run:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(args.output_dir) / "fetch_instrucoes_normativas.log"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    types = [args.only] if args.only else DEFAULT_TYPES
    all_records: List[dict] = []

    for slug in types:
        docs = load_canonical_docs(args.canonical_json, slug)
        if args.limit:
            docs = docs[:args.limit]

        if args.dry_run:
            print(f"\n=== {slug}: {len(docs)} document(s) ===")
            for d in docs:
                flag = " [needs_review: no date]" if d.needs_review else ""
                print(f"  nº {d.number} ({d.date}){flag}  ({d.canonical_name})")
            continue

        logger.info(f"Fetching {len(docs)} {slug} document(s)...")
        all_records += fetch_type(slug, docs, args.output_dir,
                                  save_docx=not args.no_docx, delay=args.delay)

    if args.dry_run:
        return 0

    summary = write_reports(all_records, args.output_dir)
    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
