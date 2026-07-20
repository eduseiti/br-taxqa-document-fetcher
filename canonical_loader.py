#!/usr/bin/env python3
"""
Canonical Document Loader

Reads the curated `canonical_referred_documents.json` produced by the
canonical-naming extraction step and turns records of a given ``type_slug``
into ``LawDocument`` objects ready for fetching.

Unlike ``LegalDocumentProcessor`` (which re-parses raw dataset filenames), this
loader trusts the already-cleaned ``number`` / ``date`` / ``canonical_name``
fields in the canonical JSON. It parses the Portuguese long-form date, strips
dotted thousands from the number, and de-duplicates records that refer to the
same document (same number + date) while keeping every source filename.
"""

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from legal_document_processor import LawDocument, construct_urn_helper, parse_pt_date

logger = logging.getLogger(__name__)

# LexML URN type token per canonical type_slug.
TYPE_SLUG_TO_URN_TYPE = {
    "lei": "lei",
    "lei_complementar": "lei.complementar",
    "decreto_lei": "decreto.lei",
    "decreto": "decreto",
    # Receita Federal acts fetched from sijut2consulta (not LexML/normas.leg.br).
    # The URN token is informational only here — these are matched and fetched by
    # (tipo_code, orgao, number, date) against the Receita REST API, not by URN —
    # but a consistent token keeps CanonicalDoc.urn populated for reports. Any
    # Receita type_slug not listed falls back to a token derived from the slug
    # (see _urn_type_for), so the whole ACT_TYPES registry works without a parallel
    # list here.
    "instrucao_normativa_srf": "instrucao.normativa",
    "instrucao_normativa_rfb": "instrucao.normativa",
}


def _urn_type_for(type_slug: str) -> str:
    """URN type token for a canonical type_slug.

    Explicit map wins; otherwise derive an informational token by stripping the
    trailing órgão segment heuristically and dotting the rest (e.g.
    "ato_declaratorio_comum_pgfn" -> "ato.declaratorio.comum"). Used only to
    populate CanonicalDoc.urn for reports; Receita acts are not fetched by URN.
    """
    if type_slug in TYPE_SLUG_TO_URN_TYPE:
        return TYPE_SLUG_TO_URN_TYPE[type_slug]
    return type_slug.replace("_", ".")


@dataclass
class CanonicalDoc:
    """A de-duplicated canonical document ready to fetch."""
    number: str            # digits only, dots stripped (e.g. "5452")
    number_dotted: str     # as-published, dots kept (e.g. "5.452") for index matching
    date: Optional[str]    # YYYY-MM-DD or None
    year: Optional[str]
    doc_type: str          # urn type token: "decreto", "decreto.lei", ...
    canonical_name: str
    urn: str
    source_filenames: List[str] = field(default_factory=list)
    colloquial_alias: Optional[str] = None
    needs_review: bool = False  # True when date is missing (weak match key)

    def to_law_document(self) -> LawDocument:
        """Adapt to the LawDocument shape used by the existing fetcher."""
        return LawDocument(
            filename=self.source_filenames[0] if self.source_filenames else self.canonical_name,
            number=self.number,
            date=self.date,
            year=self.year,
            title=self.canonical_name,
            urn=self.urn,
            original_content="",
            doc_type=self.doc_type,
        )


def _normalize_number(raw: str) -> (str, str):
    """Return (digits_only, dotted) forms of a document number."""
    dotted = (raw or "").strip()
    digits = dotted.replace(".", "").replace(" ", "")
    return digits, dotted


def load_canonical_docs(
    json_path: str,
    type_slug: str,
) -> List[CanonicalDoc]:
    """
    Load and de-duplicate canonical documents of a single ``type_slug``.

    Args:
        json_path: Path to ``canonical_referred_documents.json``.
        type_slug: Canonical type bucket to load (e.g. "decreto", "decreto_lei").

    Returns:
        List of ``CanonicalDoc`` de-duplicated by (number, date), preserving
        first-seen order. Source filenames of merged duplicates are aggregated.
    """
    urn_type = _urn_type_for(type_slug)

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    by_key: "OrderedDict[tuple, CanonicalDoc]" = OrderedDict()

    for rec in records:
        if rec.get("type_slug") != type_slug:
            continue

        digits, dotted = _normalize_number(rec.get("number", ""))
        if not digits:
            logger.warning(f"Skipping record with no number: {rec.get('canonical_name')}")
            continue

        date = parse_pt_date(rec.get("date") or "")
        year = date.split("-")[0] if date else None
        key = (digits, date)  # date=None entries key on number alone

        filename = rec.get("filename")

        if key in by_key:
            # Same document referenced by another source file.
            if filename and filename not in by_key[key].source_filenames:
                by_key[key].source_filenames.append(filename)
            continue

        urn = construct_urn_helper(digits, date, urn_type)
        doc = CanonicalDoc(
            number=digits,
            number_dotted=dotted,
            date=date,
            year=year,
            doc_type=urn_type,
            canonical_name=rec.get("canonical_name", ""),
            urn=urn,
            source_filenames=[filename] if filename else [],
            colloquial_alias=rec.get("colloquial_alias"),
            needs_review=date is None,
        )
        by_key[key] = doc

    docs = list(by_key.values())
    n_review = sum(1 for d in docs if d.needs_review)
    logger.info(
        f"Loaded {len(docs)} unique {type_slug} document(s) "
        f"({n_review} without date -> needs_review)"
    )
    return docs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    default_json = "output_canonical/canonical_referred_documents.json"
    for slug in ("decreto_lei", "decreto"):
        print(f"\n=== {slug} ===")
        docs = load_canonical_docs(default_json, slug)
        for d in docs:
            flag = "  [NEEDS REVIEW: no date]" if d.needs_review else ""
            srcs = f"  <- {len(d.source_filenames)} src" if len(d.source_filenames) > 1 else ""
            print(f"  {d.urn}{srcs}{flag}")
