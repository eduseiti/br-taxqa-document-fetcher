#!/usr/bin/env python3
"""
Receita Federal Norms Fetching Orchestrator (all act types)

Loads canonical records for any Receita-Federal-portal act type present in the
``ACT_TYPES`` registry and fetches them from the Receita norms portal
(``sijut2consulta``) via ``ReceitaNormaFetcher`` (plain ``requests``; no Selenium).
Generalizes the earlier IN-only orchestrator: it drives Instrução Normativa
(SRF/RFB), Solução de Consulta (Cosit), Ato Declaratório / Executivo /
Interpretativo / Normativo, Parecer Normativo, Portaria MF, Resolução CGSN, etc.

Output — one folder per document kind:

    output_receita_federal/
    ├── <type_slug>/
    │   ├── documents/   {prefix}_{number}_{YYYYMMDD}.{json,txt,docx}
    │   └── metadata/    fetch_report.json, needs_review.json
    ├── ...
    └── metadata/aggregate_report.json     # roll-up across all kinds

Usage:
    python fetch_receita_normas_main.py                     # default set (all registry)
    python fetch_receita_normas_main.py --only solucao_de_consulta_cosit
    python fetch_receita_normas_main.py --types instrucao_normativa_srf,ato_declaratorio_comum_srf
    python fetch_receita_normas_main.py --list             # show registry + canonical counts
    python fetch_receita_normas_main.py --limit 3 --dry-run
    python fetch_receita_normas_main.py --no-docx
"""

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import List

from canonical_loader import CanonicalDoc, load_canonical_docs
from receita_norma_fetcher import (
    ACT_TYPES, DEFAULT_VIEW_CHAIN, ReceitaNormaFetcher, ReceitaFetchResult,
)

CANONICAL_JSON = "output_canonical/canonical_referred_documents.json"
DEFAULT_OUTPUT_ROOT = "./output_receita_federal"

logger = logging.getLogger("fetch_receita_normas")


def fetch_type(type_slug: str, docs: List[CanonicalDoc], type_output_dir: str,
               save_docx: bool, delay: float, view_chain, fetch_attachments: bool,
               also_save_original: bool) -> List[dict]:
    """Fetch all records of one act type into its own folder; return report rows."""
    fetcher = ReceitaNormaFetcher(
        ACT_TYPES[type_slug], output_dir=type_output_dir,
        delay_between_requests=delay, save_docx=save_docx,
        view_chain=view_chain, fetch_attachments=fetch_attachments,
        also_save_original=also_save_original,
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
            "original_json_filename": r.original_json_filename,
            "text_filename": r.text_filename,
            "docx_filename": r.docx_filename,
            "error": r.error_message,
            "needs_review": r.needs_review,
            "review_reason": r.review_reason,
            "source_filenames": d.source_filenames,
            # Provenance for a moving target: ``vigente`` is the law as of
            # ``fetched_at``, and ``exibir_visoes`` shows which views existed, so
            # any act that fell back off ``vigente`` is visible in the report.
            "fetched_at": r.fetched_at,
            "exibir_visoes": r.exibir_visoes,
            "data_vigencia_inicio": r.data_vigencia_inicio,
            "act_revoked": r.act_revoked,
            "render_stats": r.render_stats,
        })
    return rows


def _summarize(records: List[dict]) -> dict:
    total = len(records)
    succeeded = [r for r in records if r["success"]]
    needs_review = [r for r in records if r.get("needs_review")]

    def stat(key: str) -> int:
        return sum((r.get("render_stats") or {}).get(key, 0) for r in succeeded)

    return {
        "total": total,
        "successful": len(succeeded),
        "failed": total - len(succeeded),
        "success_rate": round(len(succeeded) / total * 100, 2) if total else 0,
        "needs_review": len(needs_review),
        # Rendering roll-up: makes a view fallback, a lost annex or an
        # unconverted attachment visible without opening the documents.
        "views": dict(Counter(r.get("view") for r in succeeded)),
        "acts_revoked": sum(1 for r in succeeded if r.get("act_revoked")),
        "annotations": stat("annotations"),
        "segments_omitted": stat("segments_omitted"),
        "segments_struck_dropped": stat("segments_struck_dropped"),
        "attachments": stat("attachments"),
        "attachment_tables": stat("attachment_tables"),
        "attachments_failed": stat("attachments_failed"),
    }


def write_type_reports(type_slug: str, records: List[dict], type_output_dir: str) -> dict:
    """Write per-kind fetch_report.json + needs_review.json; return the summary."""
    metadata_dir = Path(type_output_dir) / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    summary = _summarize(records)
    with open(metadata_dir / "fetch_report.json", "w", encoding="utf-8") as f:
        json.dump({"type": type_slug, "summary": summary, "records": records},
                  f, ensure_ascii=False, indent=2)

    needs_review = [r for r in records if r.get("needs_review")]
    if needs_review:
        with open(metadata_dir / "needs_review.json", "w", encoding="utf-8") as f:
            json.dump(needs_review, f, ensure_ascii=False, indent=2)

    logger.info(f"[{type_slug}] reports -> {metadata_dir}")
    return summary


def write_aggregate_report(by_type: dict, output_root: str) -> dict:
    """Roll-up across all kinds under output_root/metadata/aggregate_report.json."""
    metadata_dir = Path(output_root) / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    overall = {
        "total": sum(s["total"] for s in by_type.values()),
        "successful": sum(s["successful"] for s in by_type.values()),
        "needs_review": sum(s["needs_review"] for s in by_type.values()),
    }
    overall["success_rate"] = (
        round(overall["successful"] / overall["total"] * 100, 2) if overall["total"] else 0
    )
    for key in ("acts_revoked", "annotations", "segments_omitted",
                "segments_struck_dropped", "attachments", "attachment_tables",
                "attachments_failed"):
        overall[key] = sum(s.get(key, 0) for s in by_type.values())
    views: Counter = Counter()
    for s in by_type.values():
        views.update(s.get("views") or {})
    overall["views"] = dict(views)
    aggregate = {"overall": overall, "by_type": by_type}
    with open(metadata_dir / "aggregate_report.json", "w", encoding="utf-8") as f:
        json.dump(aggregate, f, ensure_ascii=False, indent=2)
    logger.info(f"Aggregate report -> {metadata_dir / 'aggregate_report.json'}")
    return aggregate


def resolve_types(args) -> List[str]:
    """Determine which type_slugs to fetch from the CLI flags."""
    if args.only:
        return [args.only]
    if args.types:
        requested = [t.strip() for t in args.types.split(",") if t.strip()]
        unknown = [t for t in requested if t not in ACT_TYPES]
        if unknown:
            raise SystemExit(f"Unknown type_slug(s): {unknown}\nKnown: {sorted(ACT_TYPES)}")
        return requested
    # Default: the whole registry.
    types = list(ACT_TYPES)
    if args.exclude:
        excluded = {t.strip() for t in args.exclude.split(",") if t.strip()}
        types = [t for t in types if t not in excluded]
    return types


def print_registry(canonical_json: str) -> None:
    """--list: show every registry type with its canonical record count."""
    print(f"{'type_slug':<40} {'tipo':>5} {'órgão':<8} count")
    print("-" * 66)
    for slug, act in ACT_TYPES.items():
        try:
            n = len(load_canonical_docs(canonical_json, slug))
        except Exception:
            n = "?"
        print(f"{slug:<40} {act.tipo_code:>5} {str(act.orgao):<8} {n}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Receita Federal norms (all act types) from the sijut2consulta portal")
    parser.add_argument("--only", choices=sorted(ACT_TYPES), default=None,
                        help="Fetch only one registry type")
    parser.add_argument("--types", default=None,
                        help="Comma-separated subset of registry types to fetch")
    parser.add_argument("--exclude", default=None,
                        help="Comma-separated registry types to skip (default run only)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of documents per type (for testing)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_ROOT,
                        help="Root output folder (each kind gets its own subfolder)")
    parser.add_argument("--canonical-json", default=CANONICAL_JSON)
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay (s) between records (politeness)")
    parser.add_argument("--no-docx", action="store_true",
                        help="Skip .docx generation (JSON + .txt only)")
    parser.add_argument("--view", default=None,
                        choices=["vigente", "multivigente", "original", "conjunta"],
                        help="Pin the API view instead of the default "
                             f"{'->'.join(DEFAULT_VIEW_CHAIN)} chain. 'vigente' is the "
                             "law as currently in force (the default) and is a moving "
                             "target; 'original' is the as-published text, which carries "
                             "no amendment annotations.")
    parser.add_argument("--also-save-original", action="store_true",
                        help="Additionally save the 'original' view as "
                             "<stem>.original.json (one extra request per act)")
    parser.add_argument("--no-attachments", action="store_true",
                        help="Skip downloading by-reference annexes (PDF/DOC/ODS). "
                             "Inline HTML/JPEG annexes are still rendered.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched without fetching")
    parser.add_argument("--list", action="store_true",
                        help="List the registry with canonical counts and exit")
    args = parser.parse_args()

    if args.list:
        print_registry(args.canonical_json)
        return 0

    handlers = [logging.StreamHandler()]
    if not args.dry_run:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(args.output_dir) / "fetch_receita_normas.log"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    types = resolve_types(args)
    by_type_summary: dict = {}
    # --view pins a single view (no 406 fallback), so a run is reproducible;
    # otherwise the default chain applies.
    view_chain = (args.view,) if args.view else DEFAULT_VIEW_CHAIN
    logger.info(f"View chain: {' -> '.join(view_chain)}; "
                f"attachments={'off' if args.no_attachments else 'on'}")

    for slug in types:
        docs = load_canonical_docs(args.canonical_json, slug)
        if args.limit:
            docs = docs[:args.limit]

        if args.dry_run:
            print(f"\n=== {slug}: {len(docs)} document(s) "
                  f"(tipo={ACT_TYPES[slug].tipo_code}, órgão={ACT_TYPES[slug].orgao}) ===")
            for d in docs:
                flag = " [needs_review: no date]" if d.needs_review else ""
                print(f"  nº {d.number} ({d.date}){flag}  ({d.canonical_name})")
            continue

        if not docs:
            logger.info(f"[{slug}] no canonical records; skipping")
            continue

        type_output_dir = str(Path(args.output_dir) / slug)
        logger.info(f"Fetching {len(docs)} {slug} document(s) -> {type_output_dir}")
        rows = fetch_type(slug, docs, type_output_dir,
                          save_docx=not args.no_docx, delay=args.delay,
                          view_chain=view_chain,
                          fetch_attachments=not args.no_attachments,
                          also_save_original=args.also_save_original)
        by_type_summary[slug] = write_type_reports(slug, rows, type_output_dir)

    if args.dry_run:
        return 0

    aggregate = write_aggregate_report(by_type_summary, args.output_dir)
    print("\n=== Aggregate summary ===")
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
