#!/usr/bin/env python3
"""Apply reviewed corrections to output_canonical/canonical_referred_documents.json.

The canonical list is the fetcher's source of truth and the input of BR-TaxQA-R v2.0's dataset
build, which finds each act's document by type + number + date. Some records name the wrong act
(a same-numbered act of another year or type), so the build had to carry hand overrides for them.
This script writes the corrections into the list itself:

    python3 scripts/fix_canonical_records.py output_canonical/canonical_corrections_20261008.json

Each correction names a record by ``filename`` and gives the fields to ``set``. The record gets
``source: "manual"`` and ``correction: {date, was, reason}`` (``was`` is the old canonical_name).
A record whose ``set`` has ``status`` (``nonexistent_act`` / ``not_found``) keeps its other fields
apart from those listed. Re-running with the same corrections is a no-op (records that already
carry the correction are left alone). The per-type Markdown (``by_type/*.md``, ``index.md``) is
regenerated from the corrected list with ``extract_canonical_names``' writers.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import extract_canonical_names as ecn  # noqa: E402

CANONICAL = os.path.join(ROOT, ecn.OUTPUT_DIR, "canonical_referred_documents.json")


def apply(records: list[dict], corrections: dict) -> list[str]:
    by_name = {r["filename"]: r for r in records}
    log = []
    for c in corrections["corrections"]:
        rec = by_name.get(c["filename"])
        if rec is None:
            sys.exit(f"no canonical record for {c['filename']!r}")
        if rec.get("correction", {}).get("reason") == c["reason"]:
            continue
        was = rec["canonical_name"]
        rec.update(c["set"])
        rec["source"] = "manual"
        rec["correction"] = {"date": corrections["date"], "was": was, "reason": c["reason"]}
        log.append(f"[{rec['index']}] {c['filename']}: {was!r} -> "
                   f"{rec.get('status') or rec['canonical_name']!r}")
    return log


def write_markdown(records: list[dict]) -> None:
    buckets = defaultdict(list)
    for r in records:
        if r.get("canonical_name") is None:
            continue  # nonexistent act: listed in no category
        buckets[(r["type_bucket"], r["type_slug"])].append(r)
    os.chdir(ROOT)  # ecn writes relative to the repository root
    for name in os.listdir(ecn.BY_TYPE_DIR):
        os.remove(os.path.join(ecn.BY_TYPE_DIR, name))
    index_lines = ["# Canonical Referred Legal Documents — by Type\n",
                   f"Source: `{ecn.INPUT_FILE}` — {len(records)} referred documents "
                   "from *P&R IRPF 2024 - v1.0 - 2024.05.03.pdf*.\n",
                   "One file per category is written under `by_type/`. Records corrected by hand "
                   "carry a `correction` field in `canonical_referred_documents.json`.\n",
                   "| Type | Count | File |",
                   "| --- | ---: | --- |"]
    for (label, slug), recs in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
        fname = f"{slug}.md"
        index_lines.append(f"| {label} | {len(recs)} | [{fname}](by_type/{fname}) |")
        ecn.write_type_file(label, slug, recs)
    gone = [r for r in records if r.get("status")]
    if gone:
        index_lines += ["", "Records without a document (`status`):", ""]
        index_lines += [f"- `{r['filename']}`: {r['status']}" for r in gone]
    with open(os.path.join(ecn.OUTPUT_DIR, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("corrections")
    args = ap.parse_args()
    records = json.load(open(CANONICAL, encoding="utf-8"))
    corrections = json.load(open(args.corrections, encoding="utf-8"))
    for line in apply(records, corrections):
        print(line)
    with open(CANONICAL, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    write_markdown(records)


if __name__ == "__main__":
    main()
