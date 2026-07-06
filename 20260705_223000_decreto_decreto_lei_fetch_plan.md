# Plan — Fetch `decreto` and `decreto_lei` documents

**Date:** 2026-07-05
**Source of truth:** `output_canonical/by_type/decreto.md` (38 refs) and `output_canonical/by_type/decreto_lei.md` (13 refs), backed by the structured records in `output_canonical/canonical_referred_documents.json` (fields: `type_slug`, `number`, `date`, `canonical_name`, `source`, `colloquial_alias`, `filename`, `index`).
**Goal:** Produce clean `.docx` files (document text only, no page chrome) for every `decreto` and `decreto_lei`, reusing the existing pipeline where possible and extending it for the two new sources.

---

## 0. Findings from investigation (why the plan is shaped this way)

### `decreto_lei` → normas.leg.br (Selenium, existing pipeline)
- The project **already has partial support**: `DOCUMENT_TYPE_CONVERTER` and the URN regex in `legal_document_fetcher_main.py:153` already know the `decreto.lei` token, and `validate_urns()` (`:374`) already accepts `urn:lex:br:federal:decreto.lei:`.
- But `LegalDocumentProcessor.construct_urn()` (`legal_document_processor.py:136`) **hard-codes `lei`** in the URN and the filename generator in `br_legal_parser` hard-codes the `lei_` prefix. These need a `type`/`urn_type` parameter.
- URN format for decreto-lei: `urn:lex:br:federal:decreto.lei:YYYY-MM-DD;NUMBER` (number without dots). This is the same SPA/Shadow-DOM page shape the existing fetcher already handles.
- All 13 `decreto_lei` records have a parseable date; 0 missing. Two entries share number 5.452 (CLT) with the same date — de-dup by (number, date).

### `decreto` → planalto.gov.br (static HTML, NEW path)
- normas.leg.br coverage for plain `decreto` is unreliable; the canonical records mark `source: "planalto.gov.br"` / `"senado/camara"`. Per the task, decrees come from planalto.
- **Access mechanism (verified live):** `https://www.planalto.gov.br/ccivil_03/decreto/_dec_ano.htm` is a **year index**. Each year links to a per-year (recent) or per-decade (older) index:
  - Recent years: `../_AtoYYYY-YYYY/YYYY/Decreto/_decretosYYYY.htm`
  - Older, grouped: `Quadros/1970-1979.htm`, `Quadros/1960-1969.htm`, `Quadros/anteriores_a_1960.htm`, and single-year `Quadros/1981.htm` etc.
- Each per-year/per-decade index lists **every decree as `NN.NNN, de D.M.YYYY` with a direct `href`** to the decree page. **The hrefs are irregular** and cannot be reliably formula-generated:
  - `../Antigos/D56435.htm`, `../1950-1969/D52288.htm`, `../../Atos/decretos/1969/D65919.html`, mixed `.htm`/`.html`, mixed folders.
  - Therefore: **scrape the index, match by (number, date), and follow the listed href.** Do NOT build decree URLs by string template.
- Decree pages are **static HTML in ISO-8859-1** (no charset meta, Latin-1 accents) — plain `requests` works, **no Selenium needed**.
- Page chrome to strip: a header block "Presidência da República / Casa Civil / Subchefia para Assuntos Jurídicos", plus surrounding `<table>` layout wrappers, nav, and footer. The real content begins at the `DECRETO Nº <num>, DE <date>.` marker.
- `Decreto nº 50.656` has **no date** in the canonical data → cannot be matched by (number+date); flag for manual resolution (the index can still be searched by number alone as a fallback).
- Several decrees appear multiple times with different `source filename` (e.g. `52.288`, `56.435`, `85.801`) — same decree, different referencing doc. De-dup the fetch by (number, date); keep the source-filename list in metadata.

---

## 1. Deliverables

1. `output_decretos/documents/*.docx` — one clean docx per unique (number, date), for both types.
2. Metadata/report JSON + CSV + failed-list, mirroring the existing `metadata/` outputs.
3. Filenames encode type: `decreto_lei_{NUMBER}_{YYYYMMDD}.docx` and `decreto_{NUMBER}_{YYYYMMDD}.docx`.
4. Updated `CLAUDE.md` note describing the new planalto path and the generalized URN types.

---

## 2. Work breakdown

### Task A — Canonical loader (new small module)
Add `canonical_loader.py` that reads `output_canonical/canonical_referred_documents.json`, filters by `type_slug`, and yields normalized records:
- Parse the Portuguese `date` string (`"8 de junho de 1965"`, `"1º de maio de 1943"`) → `YYYY-MM-DD`. **Reuse** the month map + ordinal handling already in `LegalDocumentProcessor` (`legal_document_processor.py:44` and the `[ºª°]` patterns) — factor that date parser into a shared function so both processor and loader use it.
- Normalize `number` by stripping dots (`"9.358"` → `"9358"`); keep the dotted form too for index matching.
- De-duplicate by `(type_slug, number, date)`, aggregating source filenames.
- Emit `LawDocument`-compatible objects with a new `doc_type` field (`"decreto"` / `"decreto_lei"`).

*Rationale:* the canonical JSON already has clean `number`/`date`/`canonical_name`, so we should drive off it rather than re-parsing raw filenames.

### Task B — Generalize `LegalDocumentProcessor` for URN type
In `legal_document_processor.py`:
- Add `doc_type: str = "lei"` to `LawDocument`.
- Change `construct_urn(number, date, urn_type="lei")` to emit `urn:lex:br:federal:{urn_type}:{date};{number}` where `urn_type ∈ {"lei", "lei.complementar", "decreto.lei"}`. Keep the placeholder-date fallback.
- Extract the Portuguese-date parser into a reusable method (shared with Task A).
- Keep existing `lei` behavior byte-for-byte (default arg) so current outputs don't change.

### Task C — `decreto_lei` via existing Selenium fetcher
- Feed the 13 de-duplicated `decreto_lei` records (URN type `decreto.lei`) through the **existing** `BRTaxQADocumentFetcher` → `br_legal_parser` path.
- **Fix filename generation:** `br_legal_parser/legal_document_fetcher.py:722 extract_law_number_from_url()` and `:758 generate_filename()` hard-code `lei_`. Derive the prefix from the URN's type token instead (`decreto_lei_…`). This is the only change needed in `br_legal_parser`.
- Everything else (Shadow-DOM extraction, content cleaning, title detection, docx builder) is reused unchanged — decreto-lei pages on normas.leg.br use the same viewer component.
- Verify one document end-to-end (e.g. DL 1.301/1973) before running the batch.

### Task D — NEW planalto `decreto` fetcher (`planalto_decreto_fetcher.py`)
A self-contained fetcher parallel to `br_legal_parser` but for static pages:

1. **Index resolver / URL discovery**
   - Fetch `_dec_ano.htm` once; parse the year→index-URL map (resolve relative paths against the base).
   - For a target decree with year `Y`: pick the year index if present, else the decade/grouped index (`1970-1979`, `1960-1969`, `anteriores_a_1960`) covering `Y`.
   - Fetch and cache each needed index page (decode ISO-8859-1). Parse anchors of the form `NN.NNN, de D.M.YYYY → href`. Build a lookup keyed by (normalized number, date).
   - Match the target by number **and** date; resolve the (possibly irregular, `.htm`/`.html`) href to an absolute URL. Fallback: match by number alone if date missing (the `50.656` case) and log it as needs-review.

2. **Fetch + clean content**
   - `requests.get` with the project User-Agent; follow redirects (planalto 301-lowercases filenames); decode as ISO-8859-1.
   - Parse with BeautifulSoup. **Isolate the decree body:** drop the "Presidência da República / Casa Civil / Subchefia…" header, page nav/footer, and layout `<table>` wrappers that aren't part of the enacted text. Practically: locate the `DECRETO N<...>o <num>, DE <date>` marker and keep content from there through the signature/`Brasília` closing block; strip `<script>/<style>/<a>`-nav and known chrome classes.
   - Reuse `WordDocumentBuilder` from `br_legal_parser` to emit the docx (headings/paragraphs/tables/images already handled). Add the canonical title as the docx title.

3. **Save** as `decreto_{NUMBER}_{YYYYMMDD}.docx` in `output_decretos/documents/`.

*Rationale for a separate module:* planalto is static + ISO-8859-1 + index-driven URL discovery — structurally different from the Selenium/Shadow-DOM SPA path. Sharing only `WordDocumentBuilder` keeps the docx output format identical across both sources.

### Task E — Orchestration + reporting
- Add a runner (extend `legal_document_fetcher_main.py` or a small `fetch_decretos_main.py`) that:
  - loads canonical decreto + decreto_lei records (Task A),
  - routes `decreto_lei` → Task C, `decreto` → Task D,
  - writes unified `metadata/` reports (success/fail counts, per-doc status, failed list for retry, and a `needs_review` list for undated/number-only matches),
  - applies rate limiting (reuse batch delay pattern; planalto is static so a smaller per-request delay is fine).

### Task F — Validation
- Reuse the shape of `tests/` and `validate_setup.py`. Add:
  - unit test for the Portuguese-date parser (incl. `1º`),
  - unit test for URN construction per type,
  - unit test for planalto index parsing against a saved fixture of `Quadros/1960-1969.htm` (offline; the "52.288 → ../1950-1969/D52288.htm" and "56.435 → ../Antigos/D56435.htm" cases),
  - a content-cleaning assertion: the produced docx text starts at "DECRETO Nº …" and does not contain "Subchefia para Assuntos Jurídicos".
- Manual spot-check 2–3 docx per type (one recent, one older/grouped-index, the CLT decreto-lei).

---

## 3. Edge cases to handle explicitly
- **`Decreto nº 50.656`** — no date → number-only index match, flag `needs_review`.
- **Duplicate references** (`52.288`, `56.435`, `85.801`, CLT) — fetch once per (number, date), record all source filenames.
- **`.htm` vs `.html`** and irregular folders — always take the href from the index, never template it.
- **ISO-8859-1 decoding** — decode planalto bytes explicitly; do not assume UTF-8.
- **Index page not found for a year** — fall back to the correct grouped/decade index; if still unmatched, log to failed list.
- **Redirect lowercasing** — follow redirects (`allow_redirects=True`).

## 4. Files touched / added
- Modify: `legal_document_processor.py` (URN type param, shared date parser), `br_legal_parser/legal_document_fetcher.py` (type-aware filename prefix), `legal_document_fetcher_main.py` (routing) or new `fetch_decretos_main.py`, `CLAUDE.md`.
- Add: `canonical_loader.py`, `planalto_decreto_fetcher.py`, tests + a saved index fixture.
- Output: `output_decretos/{documents,logs,metadata}/`.

## 5. Suggested execution order
B → A → C (proves the reused path on decreto-lei) → D (new planalto path) → E → F.
Start each source with a single-document dry run before the full batch.
```
```
```
```
```

## Open questions for you
1. **Output location** — new `output_decretos/` dir, or fold into the existing `fetched_documents/`? (Plan assumes a new dir.)
2. **`Decreto nº 50.656`** (no date) — attempt a number-only planalto match, or skip and list for manual handling?
3. For `decreto_lei`, prefer **normas.leg.br** (Selenium, per task) even though the canonical records list `source: planalto.gov.br` for most of them? (Plan follows the task: decreto-lei via normas URN, decreto via planalto.)
