# Plan — Canonical Naming of Referred Legal Documents by Type

**Date:** 2026-07-05
**Source:** `referred_legal_documents_QA_2024_v1.1.json` (referred legal documents captured from *P&R IRPF 2024 - v1.0 - 2024.05.03.pdf*)
**Goal:** Produce the canonical name of every referred legal document, grouped by legal-document type, using `filedata` (full document text) to confirm/correct the type hinted by `filename`.

---

## 1. Understanding of the Data

- The JSON is a **list of 478 objects**, each with exactly two fields:
  - `filename` — a human-authored label (e.g. `ADI RFB nº 12, de 2016.txt`). Gives a *hint* of the type but is inconsistent.
  - `filedata` — the full captured text of the legal document, usually opening with the **canonical header** (e.g. `Ato Declaratório Interpretativo RFB nº 12, de 23 de novembro de 2016 (Publicado(a) no DOU de 25/11/2016...)`).

### Why `filename` alone is insufficient (evidence from the data)
- **Inconsistent casing/spacing:** `Ato Declaratório PGFN` vs `Ato Declaratório PGFN Nº`; `Nota PGFN CRJ` vs `Nota PGFNCRJ`; `Parecer PGFNCAT`.
- **Abbreviations vs full form:** `ADI RFB` in a filename actually expands to `Ato Declaratório Interpretativo RFB` in `filedata`; `IN RFB` vs `Instrução Normativa RFB`.
- **Generic / colloquial names:** `Código Civil.txt`, `Código Tributário Nacional (CTN).txt`, `CLT`, `ECA`, `Carnê-Leão`, treaties (`Convenção de Viena...`), forms (`DIRF`, `Dmed`, `Dimob`). These need `filedata` to recover the underlying instrument (e.g. a `Lei` or `Decreto` number and date).
- **Ambiguous prefixes:** `ADI` could mean *Ato Declaratório Interpretativo* (RFB) **or** *Ação Direta de Inconstitucionalidade* (STF) — both appear in the dataset. Only `filedata` disambiguates.
- **Different source portals** produce different header formats: `normas.leg.br` items start with `NORMAS Contraste ...` then the canonical title; STF/STJ items (`Acórdão`, `Súmula`) and treaties have entirely different layouts.

### Observed source/header formats (to drive parsing)
1. **normas.leg.br (RFB/PGFN/Cosit/etc.)** — starts with `NORMAS Contraste   <Canonical Title>, de <date> (Publicado(a) no DOU de dd/mm/yyyy...)`. The canonical title sits between the `` marker and the `(Publicado...` parenthesis.
2. **Leis / Decretos / Medidas Provisórias** — planalto.gov.br style or normas.leg.br; canonical form `Lei nº N.NNN, de dd de mês de yyyy`.
3. **STF/STJ jurisprudence** (`Acórdão`, `RE`, `REsp`, `Súmula`) — different portal headers; canonical name is the case/súmula identifier.
4. **International treaties / conventions** — descriptive titles, often promulgated by a `Decreto` cited inside `filedata`.
5. **Forms / colloquial instruments** (DIRF, Dmed, CTN, CLT...) — canonical name is the underlying norm named in `filedata`.

---

## 2. Type Taxonomy (initial, to be confirmed against `filedata`)

Group into canonical type buckets. Draft buckets from the prefix survey:

- **Lei** (incl. Constituição Federal, CTN, CLT, Código Civil, ECA → resolve to their instituting Lei/Decreto)
- **Decreto** (incl. Decreto-Lei; treaties promulgated by Decreto)
- **Medida Provisória**
- **Instrução Normativa** (RFB / SRF)
- **Ato Declaratório** — **split into separate buckets by sub-species and issuing body**, each its own output file:
  - Interpretativo (ADI) — RFB, SRF
  - Normativo (ADN) — Cosit, CST
  - Executivo (ADE) — RFB, SRF, Codac
  - plain / other — PGFN, Cosar, RFB, and the "Ato Declaratório do Presidente da Mesa do Congresso Nacional"
- **Parecer Normativo** (CST / Cosit)
- **Parecer** (PGFN, SEI, PGFN-CAT, PGFN-CRJ, Cosit)
- **Nota** (PGFN-CRJ, SEI)
- **Solução de Consulta** (Cosit / Interna Cosit / SRRF Disit)
- **Solução de Divergência** (Cosit)
- **Despacho / Decisão** (Cosit)
- **Portaria** (PMF, Portaria Conjunta)
- **Resolução** (CGPC, CGSN, TSE)
- **Circular** (Bacen)
- **Súmula** (STJ, CARF)
- **Acórdão / Jurisprudência** (STF RE, STJ REsp, ADI)
- **Tratados / Convenções internacionais**
- **Outros / Formulários** (DIRF, Dmed, Dimob, DOI, Diat, DFB, Carnê-Leão) — flagged for manual canonicalization

Final buckets will be reconciled after step 4.

---

## 3. Processing Steps

1. **Load & validate** — read the JSON; assert 478 records, each with non-empty `filename` and `filedata`; report any empties.

2. **Header extraction per record** — implement a small set of format-specific extractors:
   - `normas.leg.br`: strip the `NORMAS Contraste  ` prefix, capture the canonical title up to `(Publicado`.
   - `Lei/Decreto/MP`: regex for `(Lei|Decreto(-Lei)?|Medida Provisória|Emenda Constitucional)\s+n[ºo°]?\s*[\d.]+,?\s*de\s+.*?\d{4}`.
   - STF/STJ/CARF: regex for `Súmula`, `Acórdão`, `RE nº`, `REsp nº`, `ADI nº`.
   - Fallback: first non-boilerplate line of `filedata`.

3. **Type classification** — assign each record to a bucket using `filedata`-derived signals first, `filename` only as tiebreaker. Record both the `filename`-hinted type and the `filedata`-confirmed type so mismatches are auditable.

4. **Canonical name normalization** — for each record produce a canonical string:
   - Issuing body normalized to standard abbreviation (RFB, SRF, PGFN, Cosit, CST, ...).
   - `nº`/number normalized to the **dot thousands-separator style** (e.g. `nº 1.627`, `nº 5.172`), regardless of how the source `filedata` renders it. Original raw number kept alongside for traceability.
   - Full publication date `de dd de mês de yyyy` where available.
   - **Canonicalize whenever possible (guiding principle):** for colloquial names, forms, treaties, and codes, resolve to the underlying formal norm found in `filedata` and place the record under that norm's type bucket. Examples:
     - `Código Tributário Nacional (CTN)` → `Lei nº 5.172, de 25 de outubro de 1966` (bucket: **Lei**)
     - `CLT` → `Decreto-Lei nº 5.452, de 1º de maio de 1943` (bucket: **Decreto-Lei / Decreto**)
     - `ECA` → `Lei nº 8.069, de 13 de julho de 1990` (bucket: **Lei**)
     - Treaties (e.g. `Convenção de Viena`) → the promulgating `Decreto nº …` cited in `filedata` (bucket: **Decreto**)
     - Forms (DIRF, Dmed, Dimob, DOI, Diat, DFB, Carnê-Leão) → the Instrução Normativa / Lei that institutes them, when identifiable in `filedata`.
   - The colloquial alias is always recorded alongside the canonical name (in the JSON and as a parenthetical note in the per-type file).
   - **Fallback:** only when no underlying formal norm is identifiable in `filedata`, keep the descriptive title as-is and place it in an **"Outros"** bucket, flagged in `classification_review.md`.

5. **Mismatch & ambiguity report** — list every record where `filename` type ≠ `filedata` type, and every record where the extractor fell back or failed, for manual review.

6. **Output generation** — **one output file per category** (not a single combined file):
   - `canonical_referred_documents.json` — master per-record index: index, original `filename`, extracted canonical name, confirmed type, source portal, `filename_vs_filedata_match` flag.
   - `by_type/<type-slug>.md` — **one Markdown file per type bucket**, each listing the canonical names for that category only (the requested deliverable, split by category). Ato Declaratório sub-species (Interpretativo / Normativo / Executivo / plain) and issuing body each get their **own file** (e.g. `by_type/ato_declaratorio_interpretativo_rfb.md`, `by_type/ato_declaratorio_normativo_cosit.md`).
   - `classification_review.md` — mismatches, fallbacks, and manual-review items.

7. **Manual verification pass** — spot-check each type bucket (esp. Ato Declaratório sub-species, ADI ambiguity, treaties, forms) and the mismatch report; correct extractor rules and re-run until the review list is empty or explicitly accepted.

---

## 4. Implementation Notes

- Single script `extract_canonical_names.py` (stdlib `json` + `re` only; no external deps needed for parsing text).
- Deterministic, idempotent; re-runnable as extractor rules are refined.
- Portuguese month-name → number map reused from the existing `legal_document_processor.py` date logic where possible.
- Keep original `filename` alongside every canonical name for traceability.

## 5. Deliverables Checklist

- [ ] `extract_canonical_names.py`
- [ ] `canonical_referred_documents.json` (master index)
- [ ] `by_type/<type-slug>.md` — **one file per category** ← **primary deliverable, split by category**
- [ ] `classification_review.md`
- [ ] Verified: 478 records accounted for, every mismatch reviewed.

## 6. Decisions (confirmed with user)

1. **Number formatting**: dot thousands-separator style — `nº 1.627`, `nº 5.172`.
2. **Ato Declaratório grouping**: split into sub-species (Interpretativo / Normativo / Executivo / plain) **and** by issuing body, each with its own output file.
3. **Output layout**: each category written to a **separate file** under `by_type/`, rather than one combined document.
4. **Colloquial/form/treaty/code items**: **canonicalize whenever possible** to the underlying formal norm found in `filedata` and file under that norm's type. Only fall back to the descriptive title (in an "Outros" bucket) when no underlying norm can be identified. The colloquial alias is always preserved.
