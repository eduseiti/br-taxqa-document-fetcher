#!/usr/bin/env python3
"""
extract_canonical_names.py

Extract the canonical naming of every referred legal document captured in
referred_legal_documents_QA_2024_v1.1.json (the documents referred to by the
"P&R IRPF 2024 - v1.0 - 2024.05.03.pdf" file), grouped by legal-document type.

The `filename` field only hints at the type; the `filedata` field (full document
text) is the authoritative source and is used to confirm/correct the type and to
recover the canonical name. See the accompanying
`*_canonical_naming_extraction_plan.md` for the design.

Outputs (written under ./output_canonical/):
  - canonical_referred_documents.json   master per-record index
  - by_type/<type-slug>.md              one Markdown file per category
  - classification_review.md            mismatches, fallbacks, manual-review items
"""

import json
import os
import re
import unicodedata
from collections import defaultdict

INPUT_FILE = "referred_legal_documents_QA_2024_v1.1.json"
OUTPUT_DIR = "output_canonical"
BY_TYPE_DIR = os.path.join(OUTPUT_DIR, "by_type")

# ---------------------------------------------------------------------------
# Portuguese month handling / number normalization
# ---------------------------------------------------------------------------

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def dot_number(raw):
    """Normalize a numeric identifier to the dot thousands-separator style.

    e.g. '1627' -> '1.627', '5172' -> '5.172', '10.406' -> '10.406',
    '2.158-35' -> '2.158-35', '100' -> '100'. Non-numeric suffixes (like the
    '-35' of an MP) are preserved.
    """
    if raw is None:
        return None
    raw = raw.strip()
    m = re.match(r"^(\d[\d.]*)(.*)$", raw)
    if not m:
        return raw
    digits = m.group(1).replace(".", "")
    suffix = m.group(2)
    if not digits.isdigit():
        return raw
    n = int(digits)
    return f"{n:,}".replace(",", ".") + suffix


def normalize_date(raw):
    """Normalize a Portuguese date string to 'dd de mês de yyyy' (lower month)."""
    if not raw:
        return None
    raw = raw.strip().rstrip(".")
    m = re.match(
        r"(\d{1,2})[ºo]?\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", raw, re.I
    )
    if not m:
        return raw
    day = int(m.group(1))
    month = m.group(2).lower()
    year = m.group(3)
    # Brazilian legal-writing convention: the first day of a month is "1º".
    day_str = "1º" if day == 1 else str(day)
    return f"{day_str} de {month} de {year}"


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


# ---------------------------------------------------------------------------
# Source-format extractors. Each returns dict(name, number, date, type_label,
# issuing_body, source) or None.
# ---------------------------------------------------------------------------

# normas.leg.br pages start with this boilerplate; the canonical title sits
# between the private-use marker chars and the first '('.
NORMAS_TITLE_RE = re.compile(r"\s*(.+?)\s*\(", re.S)
# Title structure: "<name incl. body> nº <number>, de <date>"
TITLE_STRUCT_RE = re.compile(
    r"^(?P<name>.+?)\s+n[ºo°]\s*(?P<num>[\d.]+)"
    r"(?:\s*,?\s*de\s+(?P<date>\d{1,2}[ºo]?\s+de\s+[A-Za-zÀ-ÿ]+\s+de\s+\d{4}))?",
    re.I,
)

# planalto.gov.br: canonical title follows "Subchefia para Assuntos Jurídicos".
PLANALTO_RE = re.compile(
    r"Subchefia para Assuntos Jur[íi]dicos\s+"
    r"(?P<type>LEI\s+COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|"
    r"MEDIDA PROVIS[ÓO]RIA|EMENDA CONSTITUCIONAL)\s+"
    r"N\s*[ºo°]?\s*(?P<num>[\d.]+(?:-\d+)?)\s*,?\s+DE\s+"
    r"(?P<date>\d{1,2}[ºo]?\s+DE\s+[A-Za-zÀ-ÿ]+\s+DE\s+\d{4})",
    re.I,
)
PLANALTO_CONST_RE = re.compile(
    r"CONSTITUI[ÇC][ÃA]O DA REP[ÚU]BLICA FEDERATIVA DO BRASIL DE (\d{4})", re.I
)

# senado / camara legislative pages: "DECRETO Nº N, DE <date> - Publicação"
SENADO_RE = re.compile(
    r"(?P<type>DECRETO-LEI|DECRETO)\s+N[ºo°]?\s*(?P<num>[\d.]+)\s*,?\s+DE\s+"
    r"(?P<date>\d{1,2}[ºo]?\s+DE\s+[A-Za-zÀ-ÿ]+\s+DE\s+\d{4})\s*-?\s*Publica",
    re.I,
)

TYPE_WORD = r"(LEI\s+COMPLEMENTAR|LEI|DECRETO-LEI|DECRETO|MEDIDA PROVIS[ÓO]RIA|EMENDA CONSTITUCIONAL)"


def extract_normas(fd):
    if not fd.startswith("NORMAS Contraste"):
        return None
    m = NORMAS_TITLE_RE.search(fd)
    if not m:
        return None
    title = m.group(1).strip()
    s = TITLE_STRUCT_RE.match(title)
    if not s:
        return {"name": title, "number": None, "date": None,
                "raw_title": title, "source": "normas.leg.br"}
    return {
        "name": s.group("name").strip(),
        "number": s.group("num"),
        "date": s.group("date"),
        "raw_title": title,
        "source": "normas.leg.br",
    }


def extract_planalto(fd):
    if PLANALTO_CONST_RE.search(fd[:400]):
        y = PLANALTO_CONST_RE.search(fd[:400]).group(1)
        return {"name": "Constituição da República Federativa do Brasil",
                "number": None, "date": y,
                "raw_title": f"Constituição Federal de {y}",
                "source": "planalto.gov.br"}
    m = PLANALTO_RE.search(fd)
    if not m:
        return None
    typ = re.sub(r"\s+", " ", m.group("type").strip()).title()
    typ = typ.replace("Lei Complementar", "Lei Complementar")
    return {
        "name": typ,
        "number": m.group("num"),
        "date": m.group("date"),
        "raw_title": f"{m.group('type').upper()} Nº {m.group('num')}, DE {m.group('date').upper()}",
        "source": "planalto.gov.br",
    }


def extract_senado(fd):
    m = SENADO_RE.search(fd)
    if not m:
        return None
    typ = m.group("type").title()
    return {
        "name": typ,
        "number": m.group("num"),
        "date": m.group("date"),
        "raw_title": f"{m.group('type').upper()} Nº {m.group('num')}, DE {m.group('date').upper()}",
        "source": "senado/camara",
    }


# For documents whose filedata header is not a clean canonical line (PGFN notes,
# STF/STJ jurisprudence, treaties, forms), fall back to parsing the filename and
# cross-checking against filedata. The filename here is the more reliable label.
FILENAME_STRUCT_RE = re.compile(
    r"^(?P<name>.+?)\s+n[ºo°]?\s*(?P<num>[\d.]+)", re.I
)


def parse_filename(fn):
    base = re.sub(r"\.txt$", "", fn).strip()
    m = FILENAME_STRUCT_RE.match(base)
    date_m = re.search(
        r"de\s+(\d{1,2}[ºo]?\s+de\s+[A-Za-zÀ-ÿ]+\s+de\s+\d{4})", base, re.I
    )
    if m:
        return {
            "name": m.group("name").strip(" ,"),
            "number": m.group("num"),
            "date": date_m.group(1) if date_m else None,
            "raw_title": base,
            "source": "filename",
        }
    return {"name": base, "number": None, "date": None,
            "raw_title": base, "source": "filename"}


# ---------------------------------------------------------------------------
# Canonicalization: colloquial aliases resolved to the underlying formal norm.
# When the underlying norm is recovered directly from filedata (planalto), no
# explicit mapping is needed; this map documents the alias for the review file
# and gives the human-readable alias to attach.
# ---------------------------------------------------------------------------

COLLOQUIAL_ALIASES = {
    "código tributário nacional": "CTN",
    "consolidação das leis do trabalho": "CLT",
    "estatuto da criança e do adolescente": "ECA",
    "código civil": "Código Civil",
    "constituição federal": "Constituição Federal",
}


def detect_colloquial_alias(fn):
    low = fn.lower()
    for key, alias in COLLOQUIAL_ALIASES.items():
        if key in low:
            return alias
    m = re.search(r"\(([^)]+)\)", fn)  # e.g. (DIRF), (Dmed), (CTN)
    if m and len(m.group(1)) <= 15 and m.group(1).isupper() is False:
        pass
    m2 = re.search(r"\(([A-Za-zçãõ-]{2,15})\)\.txt$", fn)
    if m2:
        return m2.group(1)
    return None


# ---------------------------------------------------------------------------
# Type classification. Maps a canonical `name` to a (bucket_label, slug).
# Ato Declaratório is split by sub-species + issuing body.
# ---------------------------------------------------------------------------

def classify(name, source, fn):
    """Return (bucket_label, bucket_slug) for the given canonical name."""
    n = name.strip()
    low = n.lower()

    # --- Ato Declaratório family: split by sub-species + issuing body --------
    if low.startswith("ato declaratório") or low.startswith("ato declaratorio"):
        # sub-species
        if "interpretativo" in low:
            species = "Interpretativo"
        elif "normativo" in low:
            species = "Normativo"
        elif "executivo" in low:
            species = "Executivo"
        else:
            species = "Comum"
        body = extract_body(n, ["RFB", "SRF", "PGFN", "Cosit", "CST", "Cosar",
                                "Codac"])
        if "presidente da mesa" in low:
            body = "Presidência da Mesa do Congresso Nacional"
        label = f"Ato Declaratório {species}" + (f" {body}" if body else "")
        return label, slugify(label)

    # --- other administrative acts -----------------------------------------
    rules = [
        ("instrução normativa", "Instrução Normativa", ["RFB", "SRF"]),
        ("solução de consulta interna", "Solução de Consulta Interna", ["Cosit"]),
        ("solução de consulta", "Solução de Consulta", ["Cosit", "SRRF"]),
        ("solução de divergência", "Solução de Divergência", ["Cosit"]),
        ("parecer normativo", "Parecer Normativo", ["CST", "Cosit"]),
        ("parecer", "Parecer", ["PGFN", "SEI", "Cosit", "PGFN-CAT",
                                "PGFN-CRJ", "PGFNCAT", "PGFNCRJ"]),
        ("nota", "Nota", ["PGFN", "SEI", "PGFN-CRJ", "PGFNCRJ"]),
        ("portaria", "Portaria", ["MF", "Conjunta"]),
        ("resolução", "Resolução", ["CGSN", "CGPC", "TSE"]),
        ("circular", "Circular", ["Banco Central", "Bacen"]),
        ("despacho", "Despacho", []),
        ("decisão", "Decisão", ["Cosit"]),
    ]
    for key, label_base, bodies in rules:
        if key in low:
            body = extract_body(n, bodies)
            label = label_base + (f" {body}" if body else "")
            return label, slugify(label)

    # --- primary legislation ------------------------------------------------
    if low.startswith("lei complementar"):
        return "Lei Complementar", "lei_complementar"
    if low.startswith("lei"):
        return "Lei", "lei"
    if low.startswith("decreto-lei"):
        return "Decreto-Lei", "decreto_lei"
    if low.startswith("decreto"):
        return "Decreto", "decreto"
    if low.startswith("medida provis"):
        return "Medida Provisória", "medida_provisoria"
    if low.startswith("emenda constitucional"):
        return "Emenda Constitucional", "emenda_constitucional"
    if low.startswith("constituição"):
        return "Constituição Federal", "constituicao_federal"

    # --- jurisprudence ------------------------------------------------------
    if "súmula carf" in low or "sumula carf" in low:
        return "Súmula CARF", "sumula_carf"
    if low.startswith("súmula") or low.startswith("sumula"):
        return "Súmula STJ", "sumula_stj"
    if "ação direta de inconstitucionalidade" in low or low.startswith("adi"):
        return "Jurisprudência - ADI (STF)", "jurisprudencia_adi_stf"
    if "acórdão" in low or low.startswith("re ") or "recurso extraordinário" in low:
        return "Jurisprudência - Acórdão/RE (STF)", "jurisprudencia_acordao_re_stf"
    if low.startswith("resp") or "recurso especial" in low:
        return "Jurisprudência - REsp (STJ)", "jurisprudencia_resp_stj"

    # --- treaties / conventions --------------------------------------------
    if any(low.startswith(w) for w in ("convenção", "convencao", "acordo",
                                       "convênio", "convenio", "tratado")):
        return "Tratados e Convenções Internacionais", "tratados_convencoes"

    # --- fallback -----------------------------------------------------------
    return "Outros", "outros"


def extract_body(name, candidates):
    """Find the issuing body abbreviation present in the name."""
    for c in sorted(candidates, key=len, reverse=True):
        if re.search(r"\b" + re.escape(c) + r"\b", name, re.I):
            return c
    return None


# ---------------------------------------------------------------------------
# Canonical string assembly
# ---------------------------------------------------------------------------

def build_canonical(rec):
    """Assemble the canonical display name from name/number/date."""
    name = rec["name"]
    number = dot_number(rec["number"]) if rec["number"] else None
    date = normalize_date(rec["date"]) if rec["date"] else None

    # Constitution has no number
    if name.lower().startswith("constituição"):
        return f"{name} de {rec['date']}" if rec.get("date") else name

    parts = [name]
    if number:
        parts.append(f"nº {number}")
    text = " ".join(parts)
    if date:
        text += f", de {date}"
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_record(idx, item):
    fn = item["filename"]
    fd = item.get("filedata") or ""

    rec = (extract_normas(fd) or extract_planalto(fd) or extract_senado(fd)
           or parse_filename(fn))

    canonical = build_canonical(rec)
    bucket_label, bucket_slug = classify(rec["name"], rec["source"], fn)

    alias = detect_colloquial_alias(fn)

    # filename-vs-filedata type check: compare the leading type word
    fn_type = leading_type_word(fn)
    fd_type = leading_type_word(rec["name"])
    match = (fn_type == fd_type) if (fn_type and fd_type) else None

    return {
        "index": idx,
        "filename": fn,
        "canonical_name": canonical,
        "type_bucket": bucket_label,
        "type_slug": bucket_slug,
        "number": dot_number(rec["number"]) if rec["number"] else None,
        "date": normalize_date(rec["date"]) if rec["date"] else None,
        "source": rec["source"],
        "colloquial_alias": alias,
        "raw_title": rec.get("raw_title"),
        "filename_type": fn_type,
        "filedata_type": fd_type,
        "filename_vs_filedata_match": match,
    }


def leading_type_word(text):
    t = text.strip().lower()
    known = [
        "ato declaratório interpretativo", "ato declaratório normativo",
        "ato declaratório executivo", "ato declaratório",
        "instrução normativa", "solução de consulta interna",
        "solução de consulta", "solução de divergência",
        "parecer normativo", "parecer", "nota", "portaria", "resolução",
        "circular", "despacho", "decisão", "lei complementar", "decreto-lei",
        "lei", "decreto", "medida provisória", "emenda constitucional",
        "constituição", "súmula", "acórdão", "resp", "convenção", "acordo",
        "convênio", "adi", "ação direta",
    ]
    t = t.replace("ato declaratorio", "ato declaratório")
    for k in known:
        if t.startswith(k):
            return k
    return None


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "expected a JSON list"
    print(f"Loaded {len(data)} records from {INPUT_FILE}")

    records = []
    empties = []
    by_filedata = defaultdict(list)
    for idx, item in enumerate(data):
        fd = item.get("filedata") or ""
        if not fd:
            empties.append(idx)
        by_filedata[fd].append(idx)
        records.append(process_record(idx, item))

    # records sharing identical filedata (data-capture artifacts)
    dup_groups = [idxs for fd, idxs in by_filedata.items()
                  if fd and len(idxs) > 1]

    # group by bucket
    buckets = defaultdict(list)
    for r in records:
        buckets[(r["type_bucket"], r["type_slug"])].append(r)

    os.makedirs(BY_TYPE_DIR, exist_ok=True)

    # master json
    with open(os.path.join(OUTPUT_DIR, "canonical_referred_documents.json"),
              "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # per-type markdown files
    index_lines = ["# Canonical Referred Legal Documents — by Type\n",
                   f"Source: `{INPUT_FILE}` — {len(records)} referred documents "
                   "from *P&R IRPF 2024 - v1.0 - 2024.05.03.pdf*.\n",
                   "One file per category is written under `by_type/`.\n",
                   "| Type | Count | File |",
                   "| --- | ---: | --- |"]
    for (label, slug), recs in sorted(buckets.items(),
                                      key=lambda kv: (-len(kv[1]), kv[0][0])):
        fname = f"{slug}.md"
        index_lines.append(f"| {label} | {len(recs)} | [{fname}](by_type/{fname}) |")
        write_type_file(label, slug, recs)

    with open(os.path.join(OUTPUT_DIR, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines) + "\n")

    write_review(records, empties, dup_groups)

    print(f"Wrote {len(buckets)} category files to {BY_TYPE_DIR}/")
    print(f"Total records accounted for: {sum(len(v) for v in buckets.values())}")
    print(f"Records with empty filedata: {len(empties)}")


def write_type_file(label, slug, recs):
    recs_sorted = sorted(recs, key=lambda r: (r["number"] or "", r["index"]))
    lines = [f"# {label}\n", f"{len(recs)} document(s).\n"]
    for r in recs_sorted:
        alias = f"  _(alias: {r['colloquial_alias']})_" if r["colloquial_alias"] else ""
        lines.append(f"- **{r['canonical_name']}**{alias}")
        if r["filename"].rstrip(".txt") not in r["canonical_name"]:
            lines.append(f"  - source filename: `{r['filename']}`")
    with open(os.path.join(BY_TYPE_DIR, f"{slug}.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_review(records, empties, dup_groups=None):
    dup_groups = dup_groups or []
    mismatches = [r for r in records
                  if r["filename_vs_filedata_match"] is False]
    outros = [r for r in records if r["type_bucket"] == "Outros"]
    fn_fallback = [r for r in records if r["source"] == "filename"]

    lines = ["# Classification Review\n"]
    lines.append(f"- Total records: {len(records)}")
    lines.append(f"- Empty filedata: {len(empties)} {empties if empties else ''}")
    lines.append(f"- Filename↔filedata TYPE mismatches: {len(mismatches)}")
    lines.append(f"- Fell back to filename parsing: {len(fn_fallback)}")
    lines.append(f"- 'Outros' bucket (no formal norm identified): {len(outros)}")
    lines.append(f"- Groups of records sharing identical filedata "
                 f"(capture artifacts): {len(dup_groups)}\n")

    if dup_groups:
        lines.append("## Records with identical filedata (data-capture artifacts)\n")
        lines.append("These distinct filenames were captured with byte-identical "
                     "`filedata`, so they resolve to the same canonical name. This "
                     "is a source-dataset artifact, not an extraction error.\n")
        lines.append("| indices | shared canonical name | filenames |")
        lines.append("| --- | --- | --- |")
        by_idx = {r["index"]: r for r in records}
        for idxs in sorted(dup_groups):
            canon = by_idx[idxs[0]]["canonical_name"]
            fns = "<br>".join(f"`{by_idx[i]['filename']}`" for i in idxs)
            lines.append(f"| {idxs} | {canon} | {fns} |")
        lines.append("")

    lines.append("## Filename vs filedata type mismatches\n")
    lines.append("| idx | filename type | filedata type | canonical name | filename |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in mismatches:
        lines.append(f"| {r['index']} | {r['filename_type']} | "
                     f"{r['filedata_type']} | {r['canonical_name']} | "
                     f"`{r['filename']}` |")

    lines.append("\n## Records parsed from filename (no canonical filedata header)\n")
    lines.append("| idx | canonical name | type bucket | source | filename |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in fn_fallback:
        lines.append(f"| {r['index']} | {r['canonical_name']} | "
                     f"{r['type_bucket']} | {r['source']} | `{r['filename']}` |")

    lines.append("\n## 'Outros' bucket (needs manual canonicalization)\n")
    lines.append("| idx | canonical name | filename |")
    lines.append("| --- | --- | --- |")
    for r in outros:
        lines.append(f"| {r['index']} | {r['canonical_name']} | `{r['filename']}` |")

    with open(os.path.join(OUTPUT_DIR, "classification_review.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
